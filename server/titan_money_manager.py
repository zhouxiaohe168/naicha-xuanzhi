import os
import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd

logger = logging.getLogger("TitanML")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MM_METRICS_PATH = os.path.join(BASE_DIR, "data", "titan_mm_metrics.json")
MM_TRAIN_FLAG = os.path.join(BASE_DIR, "data", "titan_mm_trained.flag")


class TitanMoneyManager:
    def __init__(self):
        self.metrics = {}
        self.is_trained = False
        self._load_metrics()

    def _load_metrics(self):
        try:
            if os.path.exists(MM_METRICS_PATH):
                with open(MM_METRICS_PATH, "r") as f:
                    self.metrics = json.load(f)
                self.is_trained = True
                logger.info(f"资金管理指标已加载: {self.metrics.get('trained_at', '未知')}")
        except Exception:
            pass

    def _save_metrics(self):
        try:
            os.makedirs(os.path.dirname(MM_METRICS_PATH), exist_ok=True)
            with open(MM_METRICS_PATH, "w") as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @staticmethod
    def calc_kelly_fraction(win_rate, payoff_ratio, half_kelly=True):
        if win_rate <= 0 or payoff_ratio <= 0:
            return 0.0
        q = 1.0 - win_rate
        kelly = win_rate - (q / payoff_ratio)
        kelly = max(0.0, min(kelly, 1.0))
        if half_kelly:
            kelly *= 0.5
        return round(kelly, 4)

    @staticmethod
    def calc_atr_position(equity, atr, price, risk_pct=0.02, stop_mult=2.0):
        if atr <= 0 or price <= 0 or equity <= 0:
            return 0.0
        risk_dollar = equity * risk_pct
        qty = risk_dollar / (atr * stop_mult)
        position_value = qty * price
        return round(min(position_value, equity * 0.30), 2)

    @staticmethod
    def recommend_position(equity, win_rate, payoff_ratio, atr, price, max_cap=0.30):
        kelly_frac = TitanMoneyManager.calc_kelly_fraction(win_rate, payoff_ratio)
        kelly_amount = round(equity * kelly_frac, 2)

        atr_amount = TitanMoneyManager.calc_atr_position(equity, atr, price)

        recommended = min(kelly_amount, atr_amount)
        cap = equity * max_cap
        recommended = min(recommended, cap)
        recommended = max(recommended, 0)

        return {
            "kelly_fraction": kelly_frac,
            "kelly_amount": kelly_amount,
            "atr_amount": atr_amount,
            "recommended": round(recommended, 2),
            "cap_pct": round(recommended / equity * 100, 2) if equity > 0 else 0,
        }

    def run_historical_backtest(self, daily_data_map, ml_engine_ref, progress_callback=None):
        if not daily_data_map:
            logger.warning("资金管理回测: 无日线数据")
            return False

        try:
            initial_capital = 10000.0
            results_fixed = self._simulate_strategy(
                daily_data_map, ml_engine_ref, initial_capital, strategy="fixed", progress_callback=progress_callback
            )
            results_kelly_atr = self._simulate_strategy(
                daily_data_map, ml_engine_ref, initial_capital, strategy="kelly_atr", progress_callback=progress_callback
            )

            self.metrics = {
                "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "initial_capital": initial_capital,
                "symbols_used": len(daily_data_map),
                "fixed": results_fixed,
                "kelly_atr": results_kelly_atr,
                "improvement": {},
            }

            if results_fixed and results_kelly_atr:
                self.metrics["improvement"] = {
                    "return_diff": round(results_kelly_atr["total_return"] - results_fixed["total_return"], 2),
                    "drawdown_diff": round(results_fixed["max_drawdown"] - results_kelly_atr["max_drawdown"], 2),
                    "sharpe_diff": round(results_kelly_atr["sharpe_ratio"] - results_fixed["sharpe_ratio"], 2),
                }

            self.is_trained = True
            self._save_metrics()
            self._mark_trained()

            logger.info(
                f"资金管理回测完成: 固定={results_fixed['total_return']}% "
                f"凯利ATR={results_kelly_atr['total_return']}% "
                f"提升={self.metrics['improvement'].get('return_diff', 0)}%"
            )
            return True

        except Exception as e:
            logger.error(f"资金管理回测异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _simulate_strategy(self, daily_data_map, ml_engine_ref, initial_capital, strategy="fixed", progress_callback=None):
        capital = initial_capital
        equity_curve = []
        trades = []
        open_positions = {}
        peak = capital
        max_drawdown = 0
        wins = 0
        losses = 0

        all_dates = set()
        symbol_series = {}
        for sym, df in daily_data_map.items():
            if len(df) < 20:
                continue
            df = df.sort_values('t').reset_index(drop=True)
            atr_series = self._calc_atr_series(df)
            rsi_series = self._calc_rsi_series(df['c'])
            ma20 = df['c'].rolling(20).mean()
            ma50 = df['c'].rolling(50).mean()
            adx_series = self._calc_adx_series(df)
            macd_hist = self._calc_macd_histogram(df['c'])
            bb_upper, bb_lower = self._calc_bollinger_bands(df['c'])
            symbol_series[sym] = {
                'df': df, 'atr': atr_series, 'rsi': rsi_series,
                'ma20': ma20, 'ma50': ma50,
                'adx': adx_series, 'macd_hist': macd_hist,
                'bb_upper': bb_upper, 'bb_lower': bb_lower,
            }
            for t in df['t'].values:
                all_dates.add(t)

        btc_regime = self._build_btc_regime(daily_data_map)

        sorted_dates = sorted(all_dates)
        if len(sorted_dates) < 30:
            logger.warning(f"资金管理: 日期不足30天({len(sorted_dates)}), 跳过")
            return None

        if len(sorted_dates) < 100:
            logger.warning(f"资金管理: 仅{len(sorted_dates)}天数据, 结果为低置信度参考")

        total_days = len(sorted_dates)
        train_cutoff = int(total_days * 5 / 6)
        test_dates = sorted_dates[train_cutoff:]

        if len(test_dates) < 30:
            test_dates = sorted_dates[max(0, total_days - 365):]

        train_trades_for_stats = []
        train_dates = sorted_dates[:train_cutoff]

        for sym, data in symbol_series.items():
            df = data['df']
            for idx in range(50, len(df)):
                t = df['t'].iloc[idx]
                if t not in set(train_dates):
                    continue
                signal = self._generate_signal(data, idx)
                if signal and signal['action'] == 'buy':
                    future_idx = min(idx + 4, len(df) - 1)
                    entry_price = df['c'].iloc[idx]
                    exit_price = df['c'].iloc[future_idx]
                    pnl_pct = (exit_price - entry_price) / entry_price
                    train_trades_for_stats.append({'pnl_pct': pnl_pct, 'win': pnl_pct > 0})
                else:
                    short_signal = self._generate_short_signal(data, idx)
                    if short_signal and short_signal['action'] == 'sell':
                        future_idx = min(idx + 4, len(df) - 1)
                        entry_price = df['c'].iloc[idx]
                        exit_price = df['c'].iloc[future_idx]
                        pnl_pct = (entry_price - exit_price) / entry_price
                        train_trades_for_stats.append({'pnl_pct': pnl_pct, 'win': pnl_pct > 0})

        train_wins = sum(1 for t in train_trades_for_stats if t['win'])
        train_total = len(train_trades_for_stats) if train_trades_for_stats else 1
        hist_win_rate = train_wins / train_total
        winning_trades = [t['pnl_pct'] for t in train_trades_for_stats if t['win']]
        losing_trades = [abs(t['pnl_pct']) for t in train_trades_for_stats if not t['win']]
        avg_win = np.mean(winning_trades) if winning_trades else 0.02
        avg_loss = np.mean(losing_trades) if losing_trades else 0.02
        hist_payoff = avg_win / (avg_loss + 1e-10)

        test_date_set = set(test_dates)
        max_positions = 5

        for day_idx, t in enumerate(test_dates):
            if progress_callback and day_idx % 30 == 0:
                progress_callback(f"[{strategy}] 回测进度 {day_idx}/{len(test_dates)}")

            btc_bullish = btc_regime.get(t, True)

            closed_syms = []
            for sym, pos in list(open_positions.items()):
                if sym not in symbol_series:
                    continue
                df = symbol_series[sym]['df']
                mask = df['t'] == t
                if not mask.any():
                    continue
                idx_pos = df.index[mask][0]
                price = df['c'].iloc[idx_pos]
                high = df['h'].iloc[idx_pos]
                low = df['l'].iloc[idx_pos]

                current_sl = pos['sl']
                current_tp = pos['tp']
                direction = pos.get('direction', 'long')

                if direction == 'long':
                    profit_from_entry = (high - pos['entry']) / pos['entry']
                    atr_move = pos['atr']

                    if profit_from_entry >= atr_move / pos['entry'] * 3:
                        new_trail_sl = high - pos['atr'] * 2.0
                        if new_trail_sl > current_sl:
                            pos['sl'] = new_trail_sl
                            current_sl = new_trail_sl
                    elif profit_from_entry >= atr_move / pos['entry'] * 1.5:
                        breakeven_sl = pos['entry'] * 1.003
                        if breakeven_sl > current_sl:
                            pos['sl'] = breakeven_sl
                            current_sl = breakeven_sl

                    if high >= current_tp:
                        pnl = (current_tp - pos['entry']) / pos['entry'] * pos['size']
                        capital += pos['size'] + pnl
                        wins += 1
                        trades.append({
                            "sym": sym, "entry": round(pos['entry'], 4),
                            "exit": round(current_tp, 4), "pnl": round(pnl, 2),
                            "result": "win", "strategy": strategy,
                            "direction": direction,
                        })
                        closed_syms.append(sym)
                    elif low <= current_sl:
                        pnl = (current_sl - pos['entry']) / pos['entry'] * pos['size']
                        capital += pos['size'] + pnl
                        if pnl >= 0:
                            wins += 1
                            result_tag = "win"
                        else:
                            losses += 1
                            result_tag = "loss"
                        trades.append({
                            "sym": sym, "entry": round(pos['entry'], 4),
                            "exit": round(current_sl, 4), "pnl": round(pnl, 2),
                            "result": result_tag, "strategy": strategy,
                            "direction": direction,
                        })
                        closed_syms.append(sym)
                else:
                    profit_from_entry = (pos['entry'] - low) / pos['entry']
                    atr_move = pos['atr']

                    if profit_from_entry >= atr_move / pos['entry'] * 3:
                        new_trail_sl = low + pos['atr'] * 2.0
                        if new_trail_sl < current_sl:
                            pos['sl'] = new_trail_sl
                            current_sl = new_trail_sl
                    elif profit_from_entry >= atr_move / pos['entry'] * 1.5:
                        breakeven_sl = pos['entry'] * 0.997
                        if breakeven_sl < current_sl:
                            pos['sl'] = breakeven_sl
                            current_sl = breakeven_sl

                    if low <= current_tp:
                        pnl = (pos['entry'] - current_tp) / pos['entry'] * pos['size']
                        capital += pos['size'] + pnl
                        wins += 1
                        trades.append({
                            "sym": sym, "entry": round(pos['entry'], 4),
                            "exit": round(current_tp, 4), "pnl": round(pnl, 2),
                            "result": "win", "strategy": strategy,
                            "direction": direction,
                        })
                        closed_syms.append(sym)
                    elif high >= current_sl:
                        pnl = (pos['entry'] - current_sl) / pos['entry'] * pos['size']
                        capital += pos['size'] + pnl
                        if pnl >= 0:
                            wins += 1
                            result_tag = "win"
                        else:
                            losses += 1
                            result_tag = "loss"
                        trades.append({
                            "sym": sym, "entry": round(pos['entry'], 4),
                            "exit": round(current_sl, 4), "pnl": round(pnl, 2),
                            "result": result_tag, "strategy": strategy,
                            "direction": direction,
                        })
                        closed_syms.append(sym)

            for sym in closed_syms:
                del open_positions[sym]

            if len(open_positions) < max_positions:
                existing_directions = set(p.get('direction', 'long') for p in open_positions.values())
                portfolio_direction = None
                if len(existing_directions) == 1:
                    portfolio_direction = list(existing_directions)[0]

                candidates = []
                for sym, data in symbol_series.items():
                    if sym in open_positions:
                        continue
                    df = data['df']
                    mask = df['t'] == t
                    if not mask.any():
                        continue
                    idx = df.index[mask][0]
                    if idx < 50:
                        continue

                    if portfolio_direction != 'short':
                        signal = self._generate_signal(data, idx)
                        if signal and signal['action'] == 'buy':
                            signal['sym'] = sym
                            signal['idx'] = idx
                            signal['direction'] = 'long'
                            candidates.append(signal)
                            continue

                    if portfolio_direction != 'long':
                        short_signal = self._generate_short_signal(data, idx)
                        if short_signal and short_signal['action'] == 'sell':
                            short_signal['sym'] = sym
                            short_signal['idx'] = idx
                            short_signal['direction'] = 'short'
                            candidates.append(short_signal)

                candidates.sort(key=lambda x: -x.get('score', 0))

                for sig in candidates[:max(1, max_positions - len(open_positions))]:
                    price = sig['price']
                    atr = sig['atr']
                    direction = sig.get('direction', 'long')

                    if strategy == "fixed":
                        pos_size = capital * 0.10
                    else:
                        rec = self.recommend_position(
                            capital, hist_win_rate, hist_payoff, atr, price
                        )
                        pos_size = rec['recommended']
                        if pos_size < capital * 0.01:
                            pos_size = capital * 0.02

                    if direction == 'long' and not btc_bullish and strategy == "kelly_atr":
                        pos_size *= 0.5
                    elif direction == 'short' and btc_bullish and strategy == "kelly_atr":
                        pos_size *= 0.5

                    pos_size = min(pos_size, capital * 0.30)
                    if pos_size < 10 or pos_size > capital:
                        continue

                    if direction == 'long':
                        sl = price - atr * 1.5
                        tp = price + atr * 3.0
                    else:
                        sl = price + atr * 1.5
                        tp = price - atr * 3.0

                    capital -= pos_size
                    open_positions[sig['sym']] = {
                        "entry": price, "tp": tp, "sl": sl,
                        "size": pos_size, "atr": atr,
                        "direction": direction,
                    }

            unrealized = 0
            for sym, pos in open_positions.items():
                if sym not in symbol_series:
                    continue
                df = symbol_series[sym]['df']
                mask = df['t'] == t
                if mask.any():
                    cur_price = df['c'].iloc[df.index[mask][0]]
                    if pos.get('direction', 'long') == 'long':
                        unrealized += (cur_price - pos['entry']) / pos['entry'] * pos['size']
                    else:
                        unrealized += (pos['entry'] - cur_price) / pos['entry'] * pos['size']

            total_equity = capital + sum(p['size'] for p in open_positions.values()) + unrealized
            equity_curve.append({"day": day_idx, "equity": round(total_equity, 2)})

            if total_equity > peak:
                peak = total_equity
            dd = (peak - total_equity) / peak * 100 if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

        final_equity = capital + sum(p['size'] for p in open_positions.values())
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        avg_w = 0
        avg_l = 0
        if wins > 0:
            avg_w = sum(t["pnl"] for t in trades if t["result"] == "win") / wins
        if losses > 0:
            avg_l = abs(sum(t["pnl"] for t in trades if t["result"] == "loss") / losses)
        profit_factor = (avg_w * wins) / (avg_l * losses + 1e-10) if losses > 0 else 999

        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)
        sharpe = 0
        if returns and len(returns) > 1:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = round((avg_ret / std_ret) * np.sqrt(365), 2)

        return {
            "total_return": round((final_equity - initial_capital) / initial_capital * 100, 2),
            "final_equity": round(final_equity, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "profit_factor": round(profit_factor, 2) if profit_factor != 999 else 999,
            "sharpe_ratio": sharpe,
            "avg_win": round(avg_w, 2),
            "avg_loss": round(avg_l, 2),
            "equity_curve": equity_curve[-500:],
            "recent_trades": trades[-50:],
            "hist_win_rate": round(hist_win_rate * 100, 1),
            "hist_payoff_ratio": round(hist_payoff, 2),
            "kelly_fraction": self.calc_kelly_fraction(hist_win_rate, hist_payoff),
            "test_days": len(test_dates),
            "train_days": len(train_dates),
        }

    @staticmethod
    def _generate_signal(data, idx):
        df = data['df']
        rsi = data['rsi']
        ma20 = data['ma20']
        ma50 = data['ma50']
        atr = data['atr']
        adx = data.get('adx')
        macd_hist = data.get('macd_hist')
        bb_upper = data.get('bb_upper')
        bb_lower = data.get('bb_lower')

        price = df['c'].iloc[idx]
        rsi_val = rsi.iloc[idx] if idx < len(rsi) else 50
        ma20_val = ma20.iloc[idx] if idx < len(ma20) else price
        ma50_val = ma50.iloc[idx] if idx < len(ma50) else price
        atr_val = atr.iloc[idx] if idx < len(atr) else price * 0.02

        if pd.isna(rsi_val) or pd.isna(ma20_val) or pd.isna(ma50_val) or pd.isna(atr_val):
            return None

        adx_val = adx.iloc[idx] if adx is not None and idx < len(adx) and not pd.isna(adx.iloc[idx]) else 20
        macd_val = macd_hist.iloc[idx] if macd_hist is not None and idx < len(macd_hist) and not pd.isna(macd_hist.iloc[idx]) else 0
        bb_lo = bb_lower.iloc[idx] if bb_lower is not None and idx < len(bb_lower) and not pd.isna(bb_lower.iloc[idx]) else price * 0.98
        bb_up = bb_upper.iloc[idx] if bb_upper is not None and idx < len(bb_upper) and not pd.isna(bb_upper.iloc[idx]) else price * 1.02

        if rsi_val > 70:
            return None

        if adx_val < 15:
            return None

        if ma20_val < ma50_val:
            return None

        score = 50

        if price > ma50_val:
            score += 10
        if price > ma20_val:
            score += 5
        elif price > ma20_val * 0.98:
            score += 8

        ma_spread = (ma20_val - ma50_val) / ma50_val
        if ma_spread > 0.03:
            score += 6
        elif ma_spread > 0.01:
            score += 3

        if 35 <= rsi_val <= 50:
            score += 10
        elif rsi_val < 35:
            score += 6

        if adx_val > 25:
            score += 8
        elif adx_val > 20:
            score += 4

        if macd_val > 0:
            score += 4
        if idx >= 1 and macd_hist is not None and idx < len(macd_hist):
            prev_macd = macd_hist.iloc[idx - 1] if not pd.isna(macd_hist.iloc[idx - 1]) else 0
            if prev_macd < 0 and macd_val > 0:
                score += 8

        bb_range = bb_up - bb_lo if bb_up > bb_lo else 1e-10
        bb_pos = (price - bb_lo) / bb_range
        if 0.2 <= bb_pos <= 0.5:
            score += 6
        elif bb_pos > 0.85:
            score -= 8

        if idx >= 5:
            rsi_prev = rsi.iloc[idx - 5] if not pd.isna(rsi.iloc[idx - 5]) else rsi_val
            price_prev = df['c'].iloc[idx - 5]
            if price >= price_prev * 0.97 and rsi_val < rsi_prev and rsi_val < 50:
                score += 6

        vol_ratio = df['v'].iloc[idx] / (df['v'].iloc[max(0, idx - 20):idx].mean() + 1e-10)
        vol_5 = df['v'].iloc[max(0, idx - 5):idx + 1].mean()
        vol_20 = df['v'].iloc[max(0, idx - 20):idx].mean() + 1e-10
        vol_trend = vol_5 / vol_20
        
        price_change_5 = (price - df['c'].iloc[max(0, idx - 5)]) / df['c'].iloc[max(0, idx - 5)] if idx >= 5 else 0
        
        if price_change_5 < -0.01 and vol_trend < 0.8:
            score += 8
        elif price_change_5 > 0.01 and vol_trend > 1.3:
            score += 6
        elif price_change_5 > 0.02 and vol_trend < 0.7:
            score -= 5
        
        if vol_ratio > 1.5:
            score += 3
        elif vol_ratio > 1.2:
            score += 1

        if score >= 80:
            return {
                'action': 'buy', 'price': price, 'atr': atr_val,
                'score': score, 'rsi': rsi_val, 'adx': adx_val,
            }
        return None

    @staticmethod
    def _generate_short_signal(data, idx):
        df = data['df']
        rsi = data['rsi']
        ma20 = data['ma20']
        ma50 = data['ma50']
        atr = data['atr']
        adx = data.get('adx')
        macd_hist = data.get('macd_hist')
        bb_upper = data.get('bb_upper')
        bb_lower = data.get('bb_lower')

        price = df['c'].iloc[idx]
        rsi_val = rsi.iloc[idx] if idx < len(rsi) else 50
        ma20_val = ma20.iloc[idx] if idx < len(ma20) else price
        ma50_val = ma50.iloc[idx] if idx < len(ma50) else price
        atr_val = atr.iloc[idx] if idx < len(atr) else price * 0.02

        if pd.isna(rsi_val) or pd.isna(ma20_val) or pd.isna(ma50_val) or pd.isna(atr_val):
            return None

        adx_val = adx.iloc[idx] if adx is not None and idx < len(adx) and not pd.isna(adx.iloc[idx]) else 20
        macd_val = macd_hist.iloc[idx] if macd_hist is not None and idx < len(macd_hist) and not pd.isna(macd_hist.iloc[idx]) else 0
        bb_lo = bb_lower.iloc[idx] if bb_lower is not None and idx < len(bb_lower) and not pd.isna(bb_lower.iloc[idx]) else price * 0.98
        bb_up = bb_upper.iloc[idx] if bb_upper is not None and idx < len(bb_upper) and not pd.isna(bb_upper.iloc[idx]) else price * 1.02

        if rsi_val < 30:
            return None

        if adx_val < 15:
            return None

        if ma20_val > ma50_val:
            return None

        score = 50

        if price < ma50_val:
            score += 10
        if price < ma20_val:
            score += 5
        elif price < ma20_val * 1.02:
            score += 8

        ma_spread = (ma50_val - ma20_val) / ma50_val
        if ma_spread > 0.03:
            score += 6
        elif ma_spread > 0.01:
            score += 3

        if 50 <= rsi_val <= 65:
            score += 10
        elif rsi_val > 65:
            score += 6

        if adx_val > 25:
            score += 8
        elif adx_val > 20:
            score += 4

        if macd_val < 0:
            score += 4
        if idx >= 1 and macd_hist is not None and idx < len(macd_hist):
            prev_macd = macd_hist.iloc[idx - 1] if not pd.isna(macd_hist.iloc[idx - 1]) else 0
            if prev_macd > 0 and macd_val < 0:
                score += 8

        bb_range = bb_up - bb_lo if bb_up > bb_lo else 1e-10
        bb_pos = (price - bb_lo) / bb_range
        if 0.5 <= bb_pos <= 0.8:
            score += 6
        elif bb_pos < 0.15:
            score -= 8

        if idx >= 5:
            rsi_prev = rsi.iloc[idx - 5] if not pd.isna(rsi.iloc[idx - 5]) else rsi_val
            price_prev = df['c'].iloc[idx - 5]
            if price <= price_prev * 1.03 and rsi_val > rsi_prev and rsi_val > 50:
                score += 6

        vol_ratio = df['v'].iloc[idx] / (df['v'].iloc[max(0, idx - 20):idx].mean() + 1e-10)
        vol_5 = df['v'].iloc[max(0, idx - 5):idx + 1].mean()
        vol_20 = df['v'].iloc[max(0, idx - 20):idx].mean() + 1e-10
        vol_trend = vol_5 / vol_20
        
        price_change_5 = (price - df['c'].iloc[max(0, idx - 5)]) / df['c'].iloc[max(0, idx - 5)] if idx >= 5 else 0
        
        if price_change_5 > 0.01 and vol_trend < 0.8:
            score += 8
        elif price_change_5 < -0.01 and vol_trend > 1.3:
            score += 6
        elif price_change_5 < -0.02 and vol_trend < 0.7:
            score -= 5
        
        if vol_ratio > 1.5:
            score += 3
        elif vol_ratio > 1.2:
            score += 1

        if score >= 75:
            return {
                'action': 'sell', 'price': price, 'atr': atr_val,
                'score': score, 'rsi': rsi_val, 'adx': adx_val,
            }
        return None

    @staticmethod
    def _build_btc_regime(daily_data_map):
        regime = {}
        btc_df = daily_data_map.get("BTC")
        if btc_df is None:
            return regime
        btc_df = btc_df.sort_values('t').reset_index(drop=True)
        if len(btc_df) < 50:
            return regime
        ma50 = btc_df['c'].rolling(50).mean()
        for i in range(len(btc_df)):
            t = btc_df['t'].iloc[i]
            if pd.isna(ma50.iloc[i]):
                regime[t] = True
            else:
                regime[t] = btc_df['c'].iloc[i] > ma50.iloc[i]
        return regime

    @staticmethod
    def _calc_atr_series(df, period=14):
        high = df['h']
        low = df['l']
        close = df['c']
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    @staticmethod
    def _calc_rsi_series(close, period=14):
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _calc_adx_series(df, period=14):
        high = df['h']
        low = df['l']
        close = df['c']
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / (atr + 1e-10))
        minus_di = 100 * (minus_dm.rolling(period).mean() / (atr + 1e-10))
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10) * 100
        adx = dx.rolling(period).mean()
        return adx

    @staticmethod
    def _calc_macd_histogram(close, fast=12, slow=26, signal=9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return macd_line - signal_line

    @staticmethod
    def _calc_bollinger_bands(close, period=20, std_dev=2):
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + std_dev * std
        lower = sma - std_dev * std
        return upper, lower

    @staticmethod
    def needs_training():
        return not os.path.exists(MM_TRAIN_FLAG)

    @staticmethod
    def _mark_trained():
        try:
            os.makedirs(os.path.dirname(MM_TRAIN_FLAG), exist_ok=True)
            with open(MM_TRAIN_FLAG, "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

    def get_status(self):
        if not self.is_trained:
            return {"status": "untrained", "message": "资金管理模型未训练"}

        fixed = self.metrics.get("fixed", {})
        kelly_atr = self.metrics.get("kelly_atr", {})
        improvement = self.metrics.get("improvement", {})

        return {
            "status": "trained",
            "trained_at": self.metrics.get("trained_at", ""),
            "symbols_used": self.metrics.get("symbols_used", 0),
            "initial_capital": self.metrics.get("initial_capital", 10000),
            "fixed": {
                "total_return": fixed.get("total_return", 0),
                "final_equity": fixed.get("final_equity", 10000),
                "max_drawdown": fixed.get("max_drawdown", 0),
                "win_rate": fixed.get("win_rate", 0),
                "total_trades": fixed.get("total_trades", 0),
                "sharpe_ratio": fixed.get("sharpe_ratio", 0),
                "profit_factor": fixed.get("profit_factor", 0),
                "equity_curve": fixed.get("equity_curve", []),
                "recent_trades": fixed.get("recent_trades", []),
                "hist_win_rate": fixed.get("hist_win_rate", 0),
                "kelly_fraction": fixed.get("kelly_fraction", 0),
                "test_days": fixed.get("test_days", 0),
                "train_days": fixed.get("train_days", 0),
            },
            "kelly_atr": {
                "total_return": kelly_atr.get("total_return", 0),
                "final_equity": kelly_atr.get("final_equity", 10000),
                "max_drawdown": kelly_atr.get("max_drawdown", 0),
                "win_rate": kelly_atr.get("win_rate", 0),
                "total_trades": kelly_atr.get("total_trades", 0),
                "sharpe_ratio": kelly_atr.get("sharpe_ratio", 0),
                "profit_factor": kelly_atr.get("profit_factor", 0),
                "equity_curve": kelly_atr.get("equity_curve", []),
                "recent_trades": kelly_atr.get("recent_trades", []),
                "hist_win_rate": kelly_atr.get("hist_win_rate", 0),
                "hist_payoff_ratio": kelly_atr.get("hist_payoff_ratio", 0),
                "kelly_fraction": kelly_atr.get("kelly_fraction", 0),
                "test_days": kelly_atr.get("test_days", 0),
                "train_days": kelly_atr.get("train_days", 0),
            },
            "improvement": improvement,
        }


money_manager = TitanMoneyManager()
