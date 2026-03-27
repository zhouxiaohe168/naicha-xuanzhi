import numpy as np
import logging
import json
import os
import time
from datetime import datetime
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanGrid")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRID_PATH = os.path.join(BASE_DIR, "data", "titan_grid.json")


class TitanGridEngine:
    TRADING_FEE_RATE = 0.001
    ROUND_TRIP_FEE = TRADING_FEE_RATE * 2

    REGIME_CAPITAL_FRACTION = {
        "ranging": 0.25,
        "mixed": 0.20,
        "trending": 0.12,
        "volatile": 0.10,
        "unknown": 0.10,
    }

    INACTIVITY_TIMEOUT_HOURS = 36
    MIN_FILLS_THRESHOLD = 2

    DEFAULT_PARAMS = {
        "atr_multiplier": 4.0,
        "max_grid_range": 0.10,
        "min_profit_per_grid": 0.008,
        "max_grids": 20,
        "min_grids": 3,
        "capital_fraction": 0.20,
        "sl_below_grid": 0.03,
        "bias_shift": 0.02,
        "min_volume_24h": 500000,
        "ideal_atr_ratio_min": 0.015,
        "ideal_atr_ratio_max": 0.06,
        "mc_simulations": 1000,
        "mc_forecast_hours": 24,
        "mc_percentile_upper": 90,
        "mc_percentile_lower": 10,
        "trailing_prob_threshold": 0.60,
        "trailing_shift_pct": 0.5,
        "trailing_max_shifts": 5,
        "jump_intensity": 0.05,
        "jump_mean": 0.0,
        "jump_std": 0.03,
    }

    def __init__(self):
        self.params = dict(self.DEFAULT_PARAMS)
        self.active_grids = {}
        self.grid_history = []
        self.total_grid_profit = 0.0
        self.total_grid_trades = 0
        self.grid_wins = 0
        self.mode_stats = {
            "arithmetic": {"trades": 0, "wins": 0, "total_pnl": 0.0},
            "geometric": {"trades": 0, "wins": 0, "total_pnl": 0.0},
            "trailing": {"activations": 0, "successful_shifts": 0, "trailing_pnl": 0.0},
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(GRID_PATH):
                with open(GRID_PATH, "r") as f:
                    data = json.load(f)
                self.params = data.get("params", dict(self.DEFAULT_PARAMS))
                for k, v in self.DEFAULT_PARAMS.items():
                    if k not in self.params:
                        self.params[k] = v
                v23_enforced = {
                    "mc_simulations": 1000,
                    "jump_intensity": 0.05,
                    "jump_mean": 0.0,
                    "jump_std": 0.03,
                }
                migrated = False
                for k, v in v23_enforced.items():
                    if self.params.get(k) != v:
                        self.params[k] = v
                        migrated = True
                if migrated:
                    logger.info("V23 migration: enforced mc_simulations=1000, jump params")
                self.active_grids = data.get("active_grids", {})
                self.grid_history = data.get("grid_history", [])
                self.total_grid_profit = data.get("total_grid_profit", 0)
                self.total_grid_trades = data.get("total_grid_trades", 0)
                self.grid_wins = data.get("grid_wins", 0)
                self.mode_stats = data.get("mode_stats", self.mode_stats)
                if migrated:
                    self.save()
                logger.info(f"Grid engine loaded: {len(self.active_grids)} active grids")
        except Exception as e:
            logger.warning(f"Grid load failed: {e}")

    def save(self):
        try:
            data = {
                "params": self.params,
                "active_grids": self.active_grids,
                "grid_history": self.grid_history[-500:],
                "total_grid_profit": self.total_grid_profit,
                "total_grid_trades": self.total_grid_trades,
                "grid_wins": self.grid_wins,
                "mode_stats": self.mode_stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            atomic_json_save(GRID_PATH, data)
        except Exception as e:
            logger.error(f"Grid save failed: {e}")

    def _monte_carlo_forecast(self, price, atr, ml_pred=None):
        try:
            simulations = int(self.params.get("mc_simulations", 1000))
            hours = int(self.params.get("mc_forecast_hours", 24))
            dt = 1.0 / 24.0

            daily_vol = atr / price if price > 0 else 0.02
            sigma = daily_vol * np.sqrt(365)

            jump_intensity = self.params.get("jump_intensity", 0.05)
            jump_mean = self.params.get("jump_mean", 0.0)
            jump_std = self.params.get("jump_std", 0.03)

            mu = 0.0
            if ml_pred:
                prob_up = ml_pred.get("prob_up", 0.33)
                prob_down = ml_pred.get("prob_down", 0.33)
                if prob_up > 0.55:
                    mu = 0.5 * min(prob_up, 0.9)
                elif prob_down > 0.55:
                    mu = -0.5 * min(prob_down, 0.9)

            compensator = jump_intensity * (np.exp(jump_mean + 0.5 * jump_std**2) - 1)

            final_prices = np.zeros(simulations)
            for i in range(simulations):
                p = price
                for _ in range(hours):
                    shock = np.random.normal(0, 1)
                    drift = (mu - 0.5 * sigma**2 - compensator) * dt
                    diffusion = sigma * np.sqrt(dt) * shock

                    n_jumps = np.random.poisson(jump_intensity * dt)
                    jump_component = 0.0
                    if n_jumps > 0:
                        jumps = np.random.normal(jump_mean, jump_std, n_jumps)
                        jump_component = np.sum(jumps)

                    p = p * np.exp(drift + diffusion + jump_component)
                final_prices[i] = p

            upper_pct = self.params.get("mc_percentile_upper", 90)
            lower_pct = self.params.get("mc_percentile_lower", 10)
            upper_bound = float(np.percentile(final_prices, upper_pct))
            lower_bound = float(np.percentile(final_prices, lower_pct))
            median_price = float(np.median(final_prices))
            mc_confidence = 1.0 - (np.std(final_prices) / price)
            mc_confidence = max(0.0, min(1.0, mc_confidence))

            logger.info(f"🔮 MC先知-JD ({simulations}路径/{hours}h jump_λ={jump_intensity}): "
                        f"[{lower_bound:.2f}, {upper_bound:.2f}] conf={mc_confidence:.2f}")
            return {
                "upper": upper_bound,
                "lower": lower_bound,
                "median": median_price,
                "confidence": round(mc_confidence, 3),
                "simulations": simulations,
                "sigma": round(sigma, 4),
                "model": "merton_jump_diffusion",
                "jump_params": {"lambda": jump_intensity, "mu_j": jump_mean, "sigma_j": jump_std},
            }
        except Exception as e:
            logger.warning(f"MC forecast failed: {e}, falling back to ATR")
            return None

    def _select_spacing_mode(self, adx, atr_ratio, ml_pred=None):
        geo_score = 0
        arith_score = 0

        if adx < 20:
            geo_score += 30
        elif adx > 25:
            arith_score += 30
        else:
            geo_score += 15
            arith_score += 15

        if 0.02 <= atr_ratio <= 0.04:
            geo_score += 20
        elif atr_ratio > 0.04:
            arith_score += 20

        geo_stats = self.mode_stats.get("geometric", {})
        arith_stats = self.mode_stats.get("arithmetic", {})
        geo_trades = geo_stats.get("trades", 0)
        arith_trades = arith_stats.get("trades", 0)

        if geo_trades >= 5:
            geo_wr = geo_stats.get("wins", 0) / geo_trades
            geo_score += int(geo_wr * 30)
        if arith_trades >= 5:
            arith_wr = arith_stats.get("wins", 0) / arith_trades
            arith_score += int(arith_wr * 30)

        mode = "geometric" if geo_score >= arith_score else "arithmetic"
        logger.info(f"网格模式选择: {mode} (geo={geo_score} vs arith={arith_score})")
        return mode

    def select_grid_candidates(self, signals):
        candidates = []
        for s in signals:
            report = s.get("report", {})
            if not report:
                continue
            adx = report.get("adx", 50)
            atr = report.get("atr", 0)
            price = s.get("price", 0)
            if price <= 0 or atr <= 0:
                continue

            atr_ratio = atr / price

            if adx > 35:
                continue
            if atr_ratio < self.params["ideal_atr_ratio_min"] * 0.7:
                continue
            if atr_ratio > self.params["ideal_atr_ratio_max"] * 1.5:
                continue
            if s["symbol"] in self.active_grids:
                continue

            grid_score = 0
            if 15 <= adx <= 22:
                grid_score += 30
            elif adx < 15:
                grid_score += 20
            elif 22 < adx <= 30:
                grid_score += 10

            if 0.02 <= atr_ratio <= 0.04:
                grid_score += 30
            elif 0.015 <= atr_ratio <= 0.06:
                grid_score += 20
            elif 0.01 <= atr_ratio <= 0.09:
                grid_score += 10

            bb_pos = report.get("bb_position", 0.5)
            if 0.3 <= bb_pos <= 0.7:
                grid_score += 20
            elif 0.2 <= bb_pos <= 0.8:
                grid_score += 10

            rsi = report.get("rsi", 50)
            if 35 <= rsi <= 65:
                grid_score += 20
            elif 25 <= rsi <= 75:
                grid_score += 10

            vol_24h = s.get("volume_24h", 0) or report.get("volume_24h", 0)
            if vol_24h > 2000000:
                grid_score += 10

            candidates.append({
                "symbol": s["symbol"],
                "price": price,
                "atr": atr,
                "atr_ratio": atr_ratio,
                "adx": adx,
                "grid_score": grid_score,
                "ml": s.get("ml", {}),
                "report": report,
            })

        candidates.sort(key=lambda x: x["grid_score"], reverse=True)
        return candidates[:10]

    def _get_capital_fraction(self, regime=None):
        if regime and regime in self.REGIME_CAPITAL_FRACTION:
            return self.REGIME_CAPITAL_FRACTION[regime]
        return self.params.get("capital_fraction", 0.20)

    def generate_grid(self, symbol, price, atr, ml_pred=None, equity=100000, adx=None, regime=None):
        mc_result = self._monte_carlo_forecast(price, atr, ml_pred)

        if mc_result and mc_result["confidence"] > 0.3:
            mc_upper = mc_result["upper"]
            mc_lower = mc_result["lower"]
            mc_range = (mc_upper - mc_lower) / price
            min_range = (atr * 1.5) / price
            if mc_range < min_range:
                center = (mc_upper + mc_lower) / 2
                mc_upper = center * (1 + min_range / 2)
                mc_lower = center * (1 - min_range / 2)

            max_half = self.params["max_grid_range"] / 2
            upper = min(mc_upper, price * (1 + max_half))
            lower = max(mc_lower, price * (1 - max_half))
            grid_range_pct = (upper - lower) / price
            boundary_source = "monte_carlo"
        else:
            grid_range_pct = (atr * self.params["atr_multiplier"]) / price
            grid_range_pct = min(grid_range_pct, self.params["max_grid_range"])

            bias_shift = 0
            if ml_pred:
                prob_up = ml_pred.get("prob_up", 0.33)
                prob_down = ml_pred.get("prob_down", 0.33)
                if prob_up > 0.55:
                    bias_shift = self.params["bias_shift"]
                elif prob_down > 0.55:
                    bias_shift = -self.params["bias_shift"]

            upper = price * (1 + (grid_range_pct / 2) + bias_shift)
            lower = price * (1 - (grid_range_pct / 2) + bias_shift)
            mc_result = None
            boundary_source = "atr_fallback"

        min_net_profit = self.params["min_profit_per_grid"]
        effective_min_spacing = min_net_profit + self.ROUND_TRIP_FEE

        grid_count = int(grid_range_pct / effective_min_spacing)
        grid_count = max(self.params["min_grids"], min(self.params["max_grids"], grid_count))

        atr_ratio = atr / price if price > 0 else 0.03
        effective_adx = adx if adx is not None else 20
        spacing_mode = self._select_spacing_mode(effective_adx, atr_ratio, ml_pred)

        if spacing_mode == "geometric" and upper > lower > 0:
            price_levels = np.geomspace(lower, upper, grid_count).tolist()
            profit_per_grid = (price_levels[1] - price_levels[0]) / price_levels[0] if len(price_levels) > 1 else 0
            net_profit_per_grid = profit_per_grid - self.ROUND_TRIP_FEE
            logger.info(f"等比网格: 单格毛利={profit_per_grid:.2%} 手续费={self.ROUND_TRIP_FEE:.2%} 净利={net_profit_per_grid:.2%}")
        else:
            price_levels = np.linspace(lower, upper, grid_count).tolist()
            spacing_mode = "arithmetic"
            profit_per_grid = (price_levels[1] - price_levels[0]) / price_levels[0] if len(price_levels) > 1 else 0
            net_profit_per_grid = profit_per_grid - self.ROUND_TRIP_FEE

        trailing_threshold = self.params.get("trailing_prob_threshold", 0.60)
        prob_up = ml_pred.get("prob_up", 0) if ml_pred else 0
        trailing_enabled = prob_up > trailing_threshold

        capital_fraction = self._get_capital_fraction(regime)
        allocation = equity * capital_fraction
        amount_per_grid = allocation / grid_count

        orders = []
        buy_levels = sorted([p for p in price_levels if p < price and (price - p) / price > 0.001])
        sell_levels = sorted([p for p in price_levels if p > price and (p - price) / price > 0.001])

        for i, bp in enumerate(buy_levels):
            paired_sell = sell_levels[-(i+1)] if i < len(sell_levels) else None
            orders.append({
                "side": "buy", "price": round(bp, 8),
                "amount": round(amount_per_grid / bp, 6), "filled": False,
                "pair_id": i, "paired_sell_price": round(paired_sell, 8) if paired_sell else None,
            })

        for i, sp in enumerate(sell_levels):
            paired_buy = buy_levels[-(i+1)] if i < len(buy_levels) else None
            orders.append({
                "side": "sell", "price": round(sp, 8),
                "amount": round(amount_per_grid / sp, 6), "filled": False,
                "pair_id": len(buy_levels) - 1 - i if paired_buy else None,
                "paired_buy_price": round(paired_buy, 8) if paired_buy else None,
            })

        sl_price = lower * (1 - self.params["sl_below_grid"])

        bias = "neutral"
        if ml_pred:
            if ml_pred.get("prob_up", 0) > 0.55:
                bias = "bullish"
            elif ml_pred.get("prob_down", 0) > 0.55:
                bias = "bearish"

        grid = {
            "symbol": symbol,
            "entry_price": price,
            "upper": round(upper, 8),
            "lower": round(lower, 8),
            "sl_price": round(sl_price, 8),
            "grid_count": grid_count,
            "range_pct": round(grid_range_pct * 100, 2),
            "bias": bias,
            "allocation": round(allocation, 2),
            "amount_per_grid": round(amount_per_grid, 2),
            "orders": orders,
            "filled_buys": 0,
            "filled_sells": 0,
            "grid_pnl": 0.0,
            "total_fees": 0.0,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_fill_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "spacing_mode": spacing_mode,
            "profit_per_grid_pct": round(profit_per_grid * 100, 3) if profit_per_grid else 0,
            "net_profit_per_grid_pct": round(net_profit_per_grid * 100, 3),
            "fee_rate": self.ROUND_TRIP_FEE,
            "trailing_enabled": trailing_enabled,
            "trailing_shifts": 0,
            "trailing_max_shifts": int(self.params.get("trailing_max_shifts", 5)),
            "original_upper": round(upper, 8),
            "original_lower": round(lower, 8),
            "boundary_source": boundary_source,
            "mc_forecast": mc_result,
            "regime_at_open": regime or "unknown",
            "capital_fraction_used": round(capital_fraction, 3),
        }

        logger.info(f"网格生成: {symbol} mode={spacing_mode} trailing={'ON' if trailing_enabled else 'OFF'} "
                     f"range=[{lower:.2f},{upper:.2f}] grids={grid_count} source={boundary_source} "
                     f"regime={regime} cap_frac={capital_fraction:.0%} 净利/格={net_profit_per_grid:.2%}")
        return grid

    def activate_grid(self, symbol, grid):
        self.active_grids[symbol] = grid
        self.save()
        logger.info(f"Grid activated: {symbol} range={grid['lower']}-{grid['upper']} grids={grid['grid_count']}")
        return True

    def _perform_trailing_shift(self, grid, current_price):
        max_shifts = grid.get("trailing_max_shifts", 5)
        current_shifts = grid.get("trailing_shifts", 0)
        if current_shifts >= max_shifts:
            return False

        shift_pct = self.params.get("trailing_shift_pct", 0.5) / 100.0
        old_upper = grid["upper"]
        old_lower = grid["lower"]
        grid_range = old_upper - old_lower

        shift_amount = current_price * shift_pct
        new_upper = current_price + grid_range * 0.6
        new_lower = current_price - grid_range * 0.4

        unfilled_sells = [o for o in grid["orders"] if o["side"] == "sell" and not o["filled"]]
        filled_buys = [o for o in grid["orders"] if o["side"] == "buy" and o["filled"]]

        for sell_order in unfilled_sells:
            sell_order["price"] = round(sell_order["price"] + shift_amount, 8)

        grid_count = grid["grid_count"]
        spacing_mode = grid.get("spacing_mode", "arithmetic")
        allocation = grid["allocation"]
        amount_per_grid = allocation / grid_count

        new_buy_levels = []
        if spacing_mode == "geometric" and new_lower > 0:
            levels = np.geomspace(new_lower, current_price * 0.999, max(2, grid_count // 3)).tolist()
        else:
            levels = np.linspace(new_lower, current_price * 0.999, max(2, grid_count // 3)).tolist()

        existing_buy_prices = {round(o["price"], 6) for o in grid["orders"] if o["side"] == "buy" and not o["filled"]}
        for p in levels:
            rp = round(p, 8)
            if round(rp, 6) not in existing_buy_prices and (current_price - p) / current_price > 0.001:
                grid["orders"].append({
                    "side": "buy", "price": rp,
                    "amount": round(amount_per_grid / p, 6), "filled": False
                })

        grid["upper"] = round(new_upper, 8)
        grid["lower"] = round(new_lower, 8)
        grid["sl_price"] = round(new_lower * (1 - self.params["sl_below_grid"]), 8)
        grid["trailing_shifts"] = current_shifts + 1

        self.mode_stats["trailing"]["successful_shifts"] += 1
        logger.info(f"🔄 追踪上移 {grid['symbol']}: shift#{current_shifts+1} "
                     f"[{old_lower:.2f},{old_upper:.2f}] → [{new_lower:.2f},{new_upper:.2f}]")
        return True

    def _unpaired_buy_fees(self, grid):
        paired_sell_ids = {
            o.get("pair_id") for o in grid.get("orders", [])
            if o.get("side") == "sell" and o.get("filled") and o.get("pair_id") is not None
        }
        fees = 0.0
        for o in grid.get("orders", []):
            if o.get("side") == "buy" and o.get("filled") and o.get("pair_id") not in paired_sell_ids:
                fees += o["amount"] * o.get("fill_price", o["price"]) * self.TRADING_FEE_RATE
        return fees

    def _check_inactivity_timeout(self, grid):
        last_fill_str = grid.get("last_fill_time", grid.get("created_at", ""))
        if not last_fill_str:
            return False
        try:
            last_fill = datetime.strptime(last_fill_str, "%Y-%m-%d %H:%M:%S")
            hours_since = (datetime.now() - last_fill).total_seconds() / 3600
            total_fills = grid.get("filled_buys", 0) + grid.get("filled_sells", 0)
            if hours_since > self.INACTIVITY_TIMEOUT_HOURS and total_fills < self.MIN_FILLS_THRESHOLD:
                return True
            if hours_since > self.INACTIVITY_TIMEOUT_HOURS * 2:
                return True
        except Exception:
            pass
        return False

    def _find_paired_buy_price(self, sell_order, grid):
        paired_buy_price = sell_order.get("paired_buy_price")
        if paired_buy_price and paired_buy_price > 0:
            return paired_buy_price
        pair_id = sell_order.get("pair_id")
        if pair_id is not None:
            for o in grid["orders"]:
                if o.get("side") == "buy" and o.get("pair_id") == pair_id and o.get("filled"):
                    return o.get("fill_price", o.get("price", 0))
        return grid.get("entry_price", 0)

    def update_grids(self, price_map, ml_predictions=None):
        closed_grids = []
        grid_trades = []

        for symbol in list(self.active_grids.keys()):
            if symbol not in price_map:
                continue

            current_price = price_map[symbol]
            grid = self.active_grids[symbol]
            grid["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            grid["last_price"] = current_price

            if current_price <= grid["sl_price"]:
                pnl = grid["grid_pnl"] - (grid["allocation"] * self.params["sl_below_grid"]) - self._unpaired_buy_fees(grid)
                grid["grid_pnl"] = round(pnl, 2)
                grid["close_reason"] = "sl_hit"
                grid["close_price"] = current_price
                closed_grids.append(grid)
                del self.active_grids[symbol]
                continue

            if self._check_inactivity_timeout(grid):
                grid["grid_pnl"] = round(grid["grid_pnl"] - self._unpaired_buy_fees(grid), 2)
                grid["close_reason"] = "inactivity_timeout"
                grid["close_price"] = current_price
                logger.info(f"⏰ 网格超时关闭: {symbol} 活跃度不足")
                closed_grids.append(grid)
                del self.active_grids[symbol]
                continue

            if current_price > grid["upper"] * 1.02:
                should_trail = grid.get("trailing_enabled", False)
                if should_trail and ml_predictions:
                    ml_now = ml_predictions.get(symbol, {})
                    prob_down = ml_now.get("prob_down", 0)
                    if prob_down > 0.55:
                        should_trail = False
                        logger.info(f"🔄❌ 追踪取消: {symbol} ML转看跌 prob_down={prob_down:.0%}")

                if should_trail:
                    shifted = self._perform_trailing_shift(grid, current_price)
                    if shifted:
                        self.mode_stats["trailing"]["activations"] += 1
                        continue
                grid["grid_pnl"] = round(grid["grid_pnl"] - self._unpaired_buy_fees(grid), 2)
                grid["close_reason"] = "out_of_range_upper"
                grid["close_price"] = current_price
                closed_grids.append(grid)
                del self.active_grids[symbol]
                continue

            if current_price < grid["lower"] * 0.98:
                grid["grid_pnl"] = round(grid["grid_pnl"] - self._unpaired_buy_fees(grid), 2)
                grid["close_reason"] = "out_of_range_lower"
                grid["close_price"] = current_price
                closed_grids.append(grid)
                del self.active_grids[symbol]
                continue

            matched_buy_indices = set()
            for order in grid["orders"]:
                if order["filled"]:
                    order.pop("_sell_matched", None)
                    continue

                if order["side"] == "buy" and current_price <= order["price"]:
                    order["filled"] = True
                    order["fill_price"] = current_price
                    order["fill_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    grid["filled_buys"] += 1
                    grid["last_fill_time"] = order["fill_time"]

                    buy_fee = order["amount"] * current_price * self.TRADING_FEE_RATE
                    grid["total_fees"] = round(grid.get("total_fees", 0) + buy_fee, 4)

                    grid_trades.append({
                        "symbol": symbol,
                        "side": "buy",
                        "price": current_price,
                        "amount": order["amount"],
                        "fee": round(buy_fee, 4),
                        "time": order["fill_time"],
                    })

                elif order["side"] == "sell" and current_price >= order["price"]:
                    pair_id = order.get("pair_id")

                    paired_buy_filled = False
                    paired_buy_fill_price = None

                    if pair_id is not None:
                        for o in grid["orders"]:
                            if o.get("side") == "buy" and o.get("pair_id") == pair_id:
                                if o.get("filled"):
                                    paired_buy_filled = True
                                    paired_buy_fill_price = o.get("fill_price", o.get("price", 0))
                                break
                    else:
                        filled_buys_with_idx = sorted(
                            [(i, o) for i, o in enumerate(grid["orders"])
                             if o.get("side") == "buy" and o.get("filled")
                             and i not in matched_buy_indices],
                            key=lambda x: x[1].get("fill_price", x[1].get("price", 0))
                        )
                        if filled_buys_with_idx:
                            best_idx, best_buy = filled_buys_with_idx[0]
                            paired_buy_filled = True
                            paired_buy_fill_price = best_buy.get("fill_price", best_buy.get("price", 0))
                            matched_buy_indices.add(best_idx)

                    if not paired_buy_filled:
                        continue

                    order["filled"] = True
                    order["fill_price"] = current_price
                    order["fill_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    grid["filled_sells"] += 1
                    grid["last_fill_time"] = order["fill_time"]

                    paired_buy = paired_buy_fill_price if paired_buy_fill_price else self._find_paired_buy_price(order, grid)
                    gross_profit = order["amount"] * (current_price - paired_buy)
                    sell_fee = order["amount"] * current_price * self.TRADING_FEE_RATE
                    buy_fee_est = order["amount"] * paired_buy * self.TRADING_FEE_RATE
                    net_profit = gross_profit - sell_fee - buy_fee_est
                    grid["total_fees"] = round(grid.get("total_fees", 0) + sell_fee, 4)
                    grid["grid_pnl"] = round(grid["grid_pnl"] + net_profit, 4)

                    grid_trades.append({
                        "symbol": symbol,
                        "side": "sell",
                        "price": current_price,
                        "amount": order["amount"],
                        "paired_buy_price": round(paired_buy, 8),
                        "gross_profit": round(gross_profit, 4),
                        "fee": round(sell_fee + buy_fee_est, 4),
                        "net_profit": round(net_profit, 4),
                        "time": order["fill_time"],
                    })

            all_filled = all(o["filled"] for o in grid["orders"])
            if all_filled:
                grid["close_reason"] = "all_filled"
                grid["close_price"] = current_price
                closed_grids.append(grid)
                del self.active_grids[symbol]

        for g in closed_grids:
            self.total_grid_trades += 1
            self.total_grid_profit += g.get("grid_pnl", 0)
            pnl = g.get("grid_pnl", 0)
            is_win = pnl > 0
            if is_win:
                self.grid_wins += 1

            mode = g.get("spacing_mode", "arithmetic")
            if mode in self.mode_stats:
                self.mode_stats[mode]["trades"] += 1
                self.mode_stats[mode]["total_pnl"] += pnl
                if is_win:
                    self.mode_stats[mode]["wins"] += 1

            if g.get("trailing_enabled", False) and g.get("trailing_shifts", 0) > 0:
                self.mode_stats["trailing"]["trailing_pnl"] += pnl

            self.grid_history.append({
                "symbol": g["symbol"],
                "pnl": round(pnl, 4),
                "pnl_pct": round(pnl / max(g.get("allocation", 1), 1) * 100, 2),
                "reason": g.get("close_reason", "unknown"),
                "range": f"{g['lower']}-{g['upper']}",
                "grids": g["grid_count"],
                "buys_filled": g["filled_buys"],
                "sells_filled": g["filled_sells"],
                "total_orders": len(g.get("orders", [])),
                "filled_orders": sum(1 for o in g.get("orders", []) if o.get("filled")),
                "capital": round(g.get("allocation", 0), 2),
                "entry_price": g.get("entry_price", 0),
                "close_price": g.get("close_price", 0),
                "created_at": g.get("created_at", ""),
                "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "spacing_mode": mode,
                "trailing_enabled": g.get("trailing_enabled", False),
                "trailing_shifts": g.get("trailing_shifts", 0),
                "boundary_source": g.get("boundary_source", "atr_fallback"),
            })

        if closed_grids or grid_trades:
            self.save()

        return closed_grids, grid_trades

    def close_grid(self, symbol, current_price):
        if symbol not in self.active_grids:
            return None
        grid = self.active_grids[symbol]
        grid["grid_pnl"] = round(grid.get("grid_pnl", 0) - self._unpaired_buy_fees(grid), 2)
        grid["close_reason"] = "manual_close"
        grid["close_price"] = current_price

        self.total_grid_trades += 1
        pnl = grid.get("grid_pnl", 0)
        self.total_grid_profit += pnl
        if pnl > 0:
            self.grid_wins += 1

        mode = grid.get("spacing_mode", "arithmetic")
        if mode in self.mode_stats:
            self.mode_stats[mode]["trades"] += 1
            self.mode_stats[mode]["total_pnl"] += pnl
            if pnl > 0:
                self.mode_stats[mode]["wins"] += 1

        self.grid_history.append({
            "symbol": symbol,
            "pnl": round(pnl, 4),
            "pnl_pct": round(pnl / max(grid.get("allocation", 1), 1) * 100, 2),
            "reason": "manual_close",
            "range": f"{grid['lower']}-{grid['upper']}",
            "grids": grid["grid_count"],
            "buys_filled": grid["filled_buys"],
            "sells_filled": grid["filled_sells"],
            "total_orders": len(grid.get("orders", [])),
            "filled_orders": sum(1 for o in grid.get("orders", []) if o.get("filled")),
            "capital": round(grid.get("allocation", 0), 2),
            "entry_price": grid.get("entry_price", 0),
            "close_price": current_price,
            "created_at": grid.get("created_at", ""),
            "closed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "spacing_mode": mode,
            "trailing_enabled": grid.get("trailing_enabled", False),
            "trailing_shifts": grid.get("trailing_shifts", 0),
            "boundary_source": grid.get("boundary_source", "atr_fallback"),
        })

        del self.active_grids[symbol]
        self.save()
        return grid

    def mutate_params(self):
        mutations = {}
        mutable_keys = [
            "atr_multiplier", "min_profit_per_grid", "capital_fraction",
            "sl_below_grid", "bias_shift", "trailing_prob_threshold", "trailing_shift_pct",
            "jump_intensity", "jump_std",
        ]
        bounds = {
            "atr_multiplier": (2.0, 8.0),
            "min_profit_per_grid": (0.004, 0.015),
            "capital_fraction": (0.05, 0.30),
            "sl_below_grid": (0.01, 0.08),
            "bias_shift": (0.005, 0.05),
            "trailing_prob_threshold": (0.50, 0.80),
            "trailing_shift_pct": (0.2, 1.5),
            "jump_intensity": (0.01, 0.15),
            "jump_std": (0.01, 0.08),
        }
        for key in mutable_keys:
            if key not in self.params:
                continue
            old_val = self.params[key]
            mutation = np.random.normal(0, old_val * 0.1)
            new_val = old_val + mutation
            lo, hi = bounds.get(key, (old_val * 0.5, old_val * 2.0))
            new_val = max(lo, min(hi, new_val))
            self.params[key] = round(new_val, 6)
            mutations[key] = {"old": old_val, "new": self.params[key]}

        self.save()
        logger.info(f"Grid params mutated: {mutations}")
        return mutations

    def learn_from_history(self):
        if len(self.grid_history) < 5:
            return None

        recent = self.grid_history[-20:]
        win_grids = [g for g in recent if g.get("pnl", 0) > 0]

        win_rate = len(win_grids) / len(recent) if recent else 0
        avg_pnl = sum(g.get("pnl", 0) for g in recent) / len(recent)

        geo_recent = [g for g in recent if g.get("spacing_mode") == "geometric"]
        arith_recent = [g for g in recent if g.get("spacing_mode") == "arithmetic"]
        trailing_recent = [g for g in recent if g.get("trailing_shifts", 0) > 0]

        geo_wr = (sum(1 for g in geo_recent if g.get("pnl", 0) > 0) / len(geo_recent) * 100) if geo_recent else 0
        arith_wr = (sum(1 for g in arith_recent if g.get("pnl", 0) > 0) / len(arith_recent) * 100) if arith_recent else 0
        trailing_wr = (sum(1 for g in trailing_recent if g.get("pnl", 0) > 0) / len(trailing_recent) * 100) if trailing_recent else 0

        mc_recent = [g for g in recent if g.get("boundary_source") == "monte_carlo"]
        atr_recent = [g for g in recent if g.get("boundary_source") == "atr_fallback"]
        mc_wr = (sum(1 for g in mc_recent if g.get("pnl", 0) > 0) / len(mc_recent) * 100) if mc_recent else 0
        atr_wr = (sum(1 for g in atr_recent if g.get("pnl", 0) > 0) / len(atr_recent) * 100) if atr_recent else 0

        insights = {
            "recent_count": len(recent),
            "win_rate": round(win_rate * 100, 1),
            "avg_pnl": round(avg_pnl, 4),
            "total_profit": round(self.total_grid_profit, 2),
            "recommendations": [],
            "mode_analysis": {
                "geometric_win_rate": round(geo_wr, 1),
                "geometric_count": len(geo_recent),
                "arithmetic_win_rate": round(arith_wr, 1),
                "arithmetic_count": len(arith_recent),
                "trailing_win_rate": round(trailing_wr, 1),
                "trailing_count": len(trailing_recent),
                "mc_boundary_win_rate": round(mc_wr, 1),
                "mc_count": len(mc_recent),
                "atr_boundary_win_rate": round(atr_wr, 1),
                "atr_count": len(atr_recent),
            },
        }

        if win_rate < 0.4:
            self.params["sl_below_grid"] = min(self.params["sl_below_grid"] * 1.2, 0.08)
            self.params["capital_fraction"] = max(self.params["capital_fraction"] * 0.8, 0.05)
            insights["recommendations"].append("胜率低: 放宽止损+降低资金比例")

        if win_rate > 0.7:
            self.params["capital_fraction"] = min(self.params["capital_fraction"] * 1.1, 0.30)
            insights["recommendations"].append("胜率高: 提升资金配比")

        sl_closes = sum(1 for g in recent if g.get("reason") == "sl_hit")
        if sl_closes > len(recent) * 0.3:
            self.params["atr_multiplier"] = min(self.params["atr_multiplier"] * 1.15, 8.0)
            insights["recommendations"].append("止损频繁: 扩大网格范围")

        if len(trailing_recent) >= 3 and trailing_wr < 30:
            self.params["trailing_prob_threshold"] = min(self.params["trailing_prob_threshold"] + 0.05, 0.80)
            insights["recommendations"].append("追踪模式胜率低: 提高触发门槛")
        elif len(trailing_recent) >= 3 and trailing_wr > 70:
            self.params["trailing_prob_threshold"] = max(self.params["trailing_prob_threshold"] - 0.03, 0.50)
            insights["recommendations"].append("追踪模式表现好: 适当降低触发门槛")

        if len(mc_recent) >= 3 and mc_wr < atr_wr and len(atr_recent) >= 3:
            self.params["mc_simulations"] = max(int(self.params.get("mc_simulations", 500)) - 100, 200)
            insights["recommendations"].append("MC预测不如ATR: 降低MC权重")

        self.save()
        return insights

    def get_status(self):
        total_capital = sum(g.get("allocation", 0) for g in self.active_grids.values())
        total_orders = 0
        total_filled_orders = 0
        pending_buy_orders = 0
        pending_sell_orders = 0
        for g in self.active_grids.values():
            orders = g.get("orders", [])
            total_orders += len(orders)
            for o in orders:
                if o.get("filled"):
                    total_filled_orders += 1
                else:
                    if o.get("side") == "buy":
                        pending_buy_orders += 1
                    else:
                        pending_sell_orders += 1

        grid_details = {}
        total_realized = 0
        total_inventory_pnl = 0
        for sym, g in self.active_grids.items():
            orders = g.get("orders", [])
            g_total = len(orders)
            g_filled = sum(1 for o in orders if o.get("filled"))
            g_pending = g_total - g_filled
            pending_buys = sum(1 for o in orders if o.get("side") == "buy" and not o.get("filled"))
            pending_sells = sum(1 for o in orders if o.get("side") == "sell" and not o.get("filled"))
            buy_orders = [o for o in orders if o.get("side") == "buy"]
            sell_orders = [o for o in orders if o.get("side") == "sell"]

            inv_pnl, held_qty, avg_buy_price = self._calc_grid_inventory_pnl(g)
            realized = g.get("grid_pnl", 0)
            total_realized += realized
            total_inventory_pnl += inv_pnl

            grid_details[sym] = {
                "range": f"{g['lower']:.8f} - {g['upper']:.8f}",
                "range_pct": g["range_pct"],
                "bias": g["bias"],
                "grids": g["grid_count"],
                "buys_filled": g["filled_buys"],
                "sells_filled": g["filled_sells"],
                "total_orders": g_total,
                "filled_orders": g_filled,
                "pending_orders": g_pending,
                "pending_buys": pending_buys,
                "pending_sells": pending_sells,
                "total_buy_orders": len(buy_orders),
                "total_sell_orders": len(sell_orders),
                "pnl": round(realized + inv_pnl, 4),
                "realized_pnl": round(realized, 4),
                "inventory_pnl": round(inv_pnl, 4),
                "held_qty": round(held_qty, 6),
                "avg_buy_price": round(avg_buy_price, 8),
                "created": g["created_at"],
                "spacing_mode": g.get("spacing_mode", "arithmetic"),
                "trailing_enabled": g.get("trailing_enabled", False),
                "trailing_shifts": g.get("trailing_shifts", 0),
                "boundary_source": g.get("boundary_source", "atr_fallback"),
                "mc_forecast": g.get("mc_forecast"),
                "capital_used": round(g.get("allocation", 0), 2),
                "entry_price": g.get("entry_price", 0),
                "current_price": g.get("last_price", g.get("entry_price", 0)),
                "sl_price": g.get("sl_price", 0),
                "upper": g["upper"],
                "lower": g["lower"],
                "last_update": g.get("last_update", ""),
                "amount_per_grid": g.get("amount_per_grid", 0),
            }

        active_unrealized = round(total_realized + total_inventory_pnl, 2)

        return {
            "active_grids": len(self.active_grids),
            "grid_details": grid_details,
            "total_trades": self.total_grid_trades,
            "total_profit": round(self.total_grid_profit, 2),
            "unrealized_pnl": active_unrealized,
            "realized_grid_pnl": round(total_realized, 2),
            "inventory_pnl": round(total_inventory_pnl, 2),
            "net_pnl": round(self.total_grid_profit + active_unrealized, 2),
            "total_capital_used": round(total_capital, 2),
            "total_orders": total_orders,
            "total_filled_orders": total_filled_orders,
            "pending_orders": total_orders - total_filled_orders,
            "pending_buy_orders": pending_buy_orders,
            "pending_sell_orders": pending_sell_orders,
            "win_rate": round(self.grid_wins / self.total_grid_trades * 100, 1) if self.total_grid_trades > 0 else 0,
            "params": self.params,
            "history_count": len(self.grid_history),
            "grid_history": self.grid_history[-50:],
            "mode_stats": self.mode_stats,
            "version": "V23.0_NeuralGrid",
        }

    def _calc_grid_inventory_pnl(self, grid):
        orders = grid.get("orders", [])
        filled_buys = [o for o in orders if o.get("filled") and o.get("side") == "buy"]
        filled_sells = [o for o in orders if o.get("filled") and o.get("side") == "sell"]

        total_bought_qty = sum(o.get("amount", 0) for o in filled_buys)
        total_sold_qty = sum(o.get("amount", 0) for o in filled_sells)
        held_qty = total_bought_qty - total_sold_qty

        total_buy_cost = sum(o.get("amount", 0) * o.get("fill_price", o.get("price", 0)) for o in filled_buys)
        total_sell_proceeds = sum(o.get("amount", 0) * o.get("fill_price", o.get("price", 0)) for o in filled_sells)

        current_price = grid.get("last_price", grid.get("entry_price", 0))
        held_value = held_qty * current_price

        total_pnl = total_sell_proceeds + held_value - total_buy_cost
        realized = grid.get("grid_pnl", 0)
        inventory_pnl = total_pnl - realized

        avg_buy_price = total_buy_cost / total_bought_qty if total_bought_qty > 0 else 0

        return inventory_pnl, held_qty, avg_buy_price

    def get_unrealized_pnl(self):
        total = 0.0
        for g in self.active_grids.values():
            realized = g.get("grid_pnl", 0)
            inv_pnl, _, _ = self._calc_grid_inventory_pnl(g)
            total += realized + inv_pnl
        return round(total, 2)

    def get_net_pnl(self):
        return round(self.total_grid_profit + self.get_unrealized_pnl(), 2)

    def get_total_capital_used(self):
        return sum(g.get("allocation", 0) for g in self.active_grids.values())


grid_engine = TitanGridEngine()
