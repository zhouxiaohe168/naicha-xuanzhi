import logging
import json
import os
import time
import uuid
from datetime import datetime
import pytz
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanPaperTrader")

try:
    from server.titan_db import TitanDB
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSITIONS_FILE = os.path.join(BASE_DIR, "data", "titan_positions.json")
TRADES_FILE = os.path.join(BASE_DIR, "data", "titan_trades.json")

BEIJING_TZ = pytz.timezone('Asia/Shanghai')


class TitanPaperTrader:

    INITIAL_CAPITAL = 100000

    def __init__(self):
        self.capital = self.INITIAL_CAPITAL
        self.positions = {}
        self.trade_history = []
        self.total_wins = 0
        self.total_losses = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.peak_equity = self.INITIAL_CAPITAL
        self.max_drawdown_pct = 0
        self._load()

    def _load(self):
        try:
            if os.path.exists(POSITIONS_FILE):
                with open(POSITIONS_FILE, 'r') as f:
                    data = json.load(f)
                self.capital = data.get("capital", self.INITIAL_CAPITAL)
                self.positions = data.get("positions", {})
                self.total_wins = data.get("total_wins", 0)
                self.total_losses = data.get("total_losses", 0)
                self.consecutive_wins = data.get("consecutive_wins", 0)
                self.consecutive_losses = data.get("consecutive_losses", 0)
                self.peak_equity = data.get("peak_equity", self.INITIAL_CAPITAL)
                self.max_drawdown_pct = data.get("max_drawdown_pct", 0)
                for pid, pos in self.positions.items():
                    if "partial_closed" in pos and "tp_stage" not in pos:
                        if pos["partial_closed"]:
                            pos["tp_stage"] = 1
                        else:
                            pos["tp_stage"] = 0
                    if "tp_stage" not in pos:
                        pos["tp_stage"] = 0
                    if "vol_adjust_time" not in pos:
                        pos["vol_adjust_time"] = 0
                    if "last_guard_check" not in pos:
                        pos["last_guard_check"] = 0
                    if "guard_warnings" not in pos:
                        pos["guard_warnings"] = []
                    if "btc_corr_alert" not in pos:
                        pos["btc_corr_alert"] = False
                logger.info(f"持仓已恢复: {len(self.positions)}个持仓, 资金={self.capital:.2f}")
        except Exception as e:
            logger.warning(f"持仓加载失败: {e}")

        try:
            if os.path.exists(TRADES_FILE):
                with open(TRADES_FILE, 'r') as f:
                    self.trade_history = json.load(f)
                logger.info(f"交易历史已恢复: {len(self.trade_history)}笔")
        except Exception:
            self.trade_history = []

    def save(self):
        try:
            atomic_json_save(POSITIONS_FILE, {
                "capital": self.capital,
                "positions": self.positions,
                "total_wins": self.total_wins,
                "total_losses": self.total_losses,
                "consecutive_wins": self.consecutive_wins,
                "consecutive_losses": self.consecutive_losses,
                "peak_equity": self.peak_equity,
                "max_drawdown_pct": self.max_drawdown_pct,
                "saved_at": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception as e:
            logger.warning(f"持仓保存失败: {e}")

        try:
            recent = self.trade_history[-500:] if len(self.trade_history) > 500 else self.trade_history
            atomic_json_save(TRADES_FILE, recent)
        except Exception:
            pass

    def get_equity(self, price_map=None, grid_pnl=0.0, grid_realized_pnl=0.0):
        equity = self.capital + grid_realized_pnl
        for pid, pos in self.positions.items():
            sym = pos["symbol"]
            current_price = price_map.get(sym, pos["entry_price"]) if price_map else pos["entry_price"]
            if pos["direction"] == "long":
                pnl = (current_price - pos["entry_price"]) / pos["entry_price"] * pos["position_value"]
            else:
                pnl = (pos["entry_price"] - current_price) / pos["entry_price"] * pos["position_value"]
            equity += pos["position_value"] + pnl
        equity += grid_pnl
        return equity

    def get_total_exposure(self):
        return sum(p["position_value"] for p in self.positions.values())

    def calculate_recommended_amount(self, signal_score, ml_confidence, atr_ratio, fng_value):
        base_kelly = 0.02
        total_trades = self.total_wins + self.total_losses
        if total_trades >= 10:
            win_rate = self.total_wins / total_trades
            avg_win = 1.5
            avg_loss = 1.0
            kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss + 1e-10)
            base_kelly = max(0.005, min(kelly * 0.5, 0.05))

        equity = self.get_equity()
        base_amount = equity * base_kelly

        if atr_ratio > 0:
            volatility_adj = min(0.03 / (atr_ratio + 1e-10), 2.0)
            base_amount *= min(volatility_adj, 1.5)

        if signal_score >= 90:
            base_amount *= 1.5
        elif signal_score >= 85:
            base_amount *= 1.2

        if self.consecutive_losses >= 3:
            base_amount *= 0.25
        elif self.consecutive_losses >= 2:
            base_amount *= 0.5
        elif self.consecutive_wins >= 3:
            base_amount *= min(1.2, 1.5)

        if fng_value <= 15:
            base_amount *= 0.5
        elif fng_value <= 25:
            base_amount *= 0.7
        elif fng_value >= 80:
            base_amount *= 0.7

        max_single = equity * 0.05
        base_amount = max(100, min(base_amount, max_single))

        exposure = self.get_total_exposure()
        remaining_capacity = equity * 0.60 - exposure
        if remaining_capacity <= 0:
            return 0, "总敞口已达60%上限"

        base_amount = min(base_amount, remaining_capacity)
        return round(base_amount, 2), "OK"

    def open_position(self, symbol, direction, entry_price, tp_price, sl_price,
                      position_value, signal_score, ml_confidence, atr_value,
                      ai_verdict="", mtf_alignment=0, strategy_type="trend",
                      regime_at_entry="", fng_at_entry=50, btc_price_at_entry=0,
                      decision_chain=None, entry_indicators=None):
        pid = str(uuid.uuid4())[:8]
        now = datetime.now(BEIJING_TZ)

        initial_sl = sl_price
        trailing_activated = False

        self.capital -= position_value

        self.positions[pid] = {
            "id": pid,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "current_price": entry_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "initial_sl": initial_sl,
            "trailing_sl": sl_price,
            "trailing_activated": trailing_activated,
            "position_value": position_value,
            "remaining_value": position_value,
            "partial_closed": False,
            "tp_stage": 0,
            "signal_score": signal_score,
            "ml_confidence": ml_confidence,
            "atr_at_entry": atr_value,
            "ai_verdict": ai_verdict,
            "mtf_alignment": mtf_alignment,
            "strategy_type": strategy_type,
            "open_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "open_timestamp": time.time(),
            "highest_price": entry_price if direction == "long" else entry_price,
            "lowest_price": entry_price if direction == "short" else entry_price,
            "vol_adjust_time": 0,
            "last_guard_check": 0,
            "guard_warnings": [],
            "btc_corr_alert": False,
            "regime_at_entry": regime_at_entry,
            "fng_at_entry": fng_at_entry,
            "btc_price_at_entry": btc_price_at_entry,
            "decision_chain": decision_chain or {},
            "peak_unrealized_pnl": 0.0,
            "peak_unrealized_price": entry_price,
            "entry_indicators": entry_indicators or {},
        }

        self.save()
        if DB_AVAILABLE:
            try:
                TitanDB.save_position(self.positions[pid])
            except Exception as e:
                logger.warning(f"DB保存持仓失败: {e}")
        logger.info(f"模拟开仓: {symbol} {direction} @ {entry_price} 金额={position_value}")
        return pid

    def close_position(self, pid, current_price, reason="manual"):
        if pid not in self.positions:
            return None

        pos = self.positions[pid]
        now = datetime.now(BEIJING_TZ)

        if pos["direction"] == "long":
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
        else:
            pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100

        pnl_value = pos["remaining_value"] * pnl_pct / 100

        self.capital += pos["remaining_value"] + pnl_value

        is_win = pnl_value > 0
        is_loss = pnl_value < 0
        if is_win:
            self.total_wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        elif is_loss:
            self.total_losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        trade_record = {
            "id": pos["id"],
            "symbol": pos["symbol"],
            "direction": pos["direction"],
            "entry_price": pos["entry_price"],
            "exit_price": current_price,
            "tp_price": pos["tp_price"],
            "sl_price": pos["sl_price"],
            "position_value": pos["position_value"],
            "pnl_pct": round(pnl_pct, 2),
            "pnl_value": round(pnl_value, 2),
            "result": "win" if is_win else ("loss" if is_loss else "breakeven"),
            "reason": reason,
            "signal_score": pos["signal_score"],
            "ml_confidence": pos["ml_confidence"],
            "ai_verdict": pos["ai_verdict"],
            "mtf_alignment": pos["mtf_alignment"],
            "strategy_type": pos.get("strategy_type", "unknown"),
            "open_time": pos["open_time"],
            "close_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "hold_hours": round((time.time() - pos["open_timestamp"]) / 3600, 1),
            "regime": pos.get("regime_at_entry", ""),
            "regime_at_entry": pos.get("regime_at_entry", ""),
            "fng_at_entry": pos.get("fng_at_entry", 50),
            "btc_price_at_entry": pos.get("btc_price_at_entry", 0),
            "decision_chain": pos.get("decision_chain", {}),
            "peak_unrealized_pnl": pos.get("peak_unrealized_pnl", 0),
            "peak_unrealized_price": pos.get("peak_unrealized_price", 0),
            "initial_sl_price": pos.get("initial_sl", pos.get("sl_price", 0)),
            "sl_distance_pct": round(abs(pos.get("initial_sl", pos.get("sl_price", 0)) - pos.get("entry_price", 0)) / pos.get("entry_price", 1) * 100, 2) if pos.get("entry_price", 0) > 0 else 0,
            "btc_macro_trend_at_entry": pos.get("decision_chain", {}).get("btc_macro_trend", ""),
            "signal_direction_4h_result": pos.get("decision_chain", {}).get("direction_4h", ""),
            "entry_indicators": pos.get("entry_indicators", {}),
        }
        self.trade_history.append(trade_record)

        del self.positions[pid]
        self.save()
        if DB_AVAILABLE:
            try:
                TitanDB.save_trade(trade_record)
                TitanDB.remove_position(pid)
            except Exception as e:
                logger.warning(f"DB保存交易失败: {e}")
            try:
                TitanDB.record_position_event(
                    trade_id=pid, symbol=pos["symbol"], event_type='position_closed',
                    old_value=f"{pos['entry_price']:.6f}", new_value=f"{current_price:.6f}",
                    reason=reason, current_pnl_pct=round(pnl_pct, 2), current_price=current_price,
                    holding_hours=round((time.time() - pos["open_timestamp"]) / 3600, 1)
                )
            except Exception:
                pass
        try:
            from server.titan_capital_sizer import capital_sizer
            capital_sizer.record_trade_pnl(pnl_value)
        except Exception:
            pass
        try:
            from server.titan_counterfactual import TitanCounterfactualEngine
            cf_engine = TitanCounterfactualEngine()
            cf_trade = {
                "id": pos["id"],
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "entry_price": pos["entry_price"],
                "exit_price": current_price,
                "sl_price": pos["sl_price"],
                "tp_price": pos.get("tp_price"),
                "peak_unrealized_pnl": pos.get("peak_unrealized_pnl", 0),
                "pnl_pct": pnl_pct,
                "pnl_usd": pnl_value,
                "holding_hours": round((time.time() - pos["open_timestamp"]) / 3600, 1),
                "created_at": pos.get("open_time_dt"),
                "strategy": pos.get("strategy_type", "trend"),
            }
            cf_result = cf_engine.analyze_after_close(cf_trade)
            logger.info(f"[COUNTERFACTUAL] {pos['symbol']} 教训: {cf_result.get('primary_lessons', [])}")
        except Exception as e:
            logger.debug(f"反事实分析异常: {e}")
        logger.info(f"模拟平仓: {pos['symbol']} {reason} PnL={pnl_pct:.2f}% ${pnl_value:.2f}")
        return trade_record

    def _do_partial_close(self, pid, current_price, stage=1):
        pos = self.positions[pid]
        current_tp_stage = pos.get("tp_stage", 0)
        if pos.get("partial_closed") is True and current_tp_stage == 0:
            current_tp_stage = 1
            pos["tp_stage"] = 1

        if stage <= current_tp_stage:
            return None

        if stage == 1:
            close_ratio = 0.30
            stage_label = "第1阶段(SL×1.5)"
        elif stage == 2:
            close_ratio = 0.30
            stage_label = "第2阶段(SL×2.5)"
        else:
            return None

        close_value = pos["remaining_value"] * close_ratio
        if pos["direction"] == "long":
            pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
        else:
            pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100

        pnl_value = close_value * pnl_pct / 100
        self.capital += close_value + pnl_value
        pos["remaining_value"] -= close_value
        pos["tp_stage"] = stage
        pos["partial_closed"] = True

        if pnl_value > 0:
            self.total_wins += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        elif pnl_value < 0:
            self.total_losses += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        trade_record = {
            "id": pos["id"] + f"-partial-s{stage}",
            "symbol": pos["symbol"],
            "direction": pos["direction"],
            "entry_price": pos["entry_price"],
            "exit_price": current_price,
            "tp_price": pos["tp_price"],
            "sl_price": pos["sl_price"],
            "position_value": round(close_value, 2),
            "pnl_pct": round(pnl_pct, 2),
            "pnl_value": round(pnl_value, 2),
            "result": "win" if pnl_value > 0 else ("loss" if pnl_value < 0 else "breakeven"),
            "reason": f"partial_tp_s{stage}",
            "signal_score": pos["signal_score"],
            "ml_confidence": pos["ml_confidence"],
            "ai_verdict": pos["ai_verdict"],
            "mtf_alignment": pos["mtf_alignment"],
            "strategy_type": pos.get("strategy_type", "unknown"),
            "open_time": pos["open_time"],
            "close_time": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "hold_hours": round((time.time() - pos["open_timestamp"]) / 3600, 1),
            "regime": pos.get("regime_at_entry", ""),
            "regime_at_entry": pos.get("regime_at_entry", ""),
            "fng_at_entry": pos.get("fng_at_entry", 50),
            "btc_price_at_entry": pos.get("btc_price_at_entry", 0),
            "peak_unrealized_pnl": pos.get("peak_unrealized_pnl", 0),
            "initial_sl_price": pos.get("initial_sl", pos.get("sl_price", 0)),
            "sl_distance_pct": round(abs(pos.get("initial_sl", pos.get("sl_price", 0)) - pos.get("entry_price", 0)) / pos.get("entry_price", 1) * 100, 2) if pos.get("entry_price", 0) > 0 else 0,
            "btc_macro_trend_at_entry": pos.get("decision_chain", {}).get("btc_macro_trend", ""),
        }
        self.trade_history.append(trade_record)
        logger.info(f"分段止盈{stage_label}: {pos['symbol']} {close_ratio*100:.0f}%仓位 PnL={pnl_pct:.2f}%")
        return trade_record

    def _adjust_for_volatility(self, pos, current_atr, regime=None):
        if current_atr is None or current_atr <= 0:
            return

        entry_atr = pos.get("atr_at_entry", 0)
        if entry_atr <= 0:
            return

        now = time.time()
        last_adjust = pos.get("vol_adjust_time", 0)
        if now - last_adjust < 3600:
            return

        atr_ratio = current_atr / entry_atr
        direction = pos["direction"]
        initial_sl = pos.get("initial_sl", pos["sl_price"])

        if "vol_adjust_log" not in pos:
            pos["vol_adjust_log"] = []

        regime_factor = 1.0
        if regime == "volatile":
            regime_factor = 1.15
        elif regime == "trending":
            regime_factor = 0.95
        elif regime == "ranging":
            regime_factor = 0.90

        hold_hours = (now - pos.get("open_timestamp", now)) / 3600
        pnl_pct = 0
        cp = pos.get("current_price", pos["entry_price"])
        if direction == "long":
            pnl_pct = (cp - pos["entry_price"]) / pos["entry_price"] * 100
        else:
            pnl_pct = (pos["entry_price"] - cp) / pos["entry_price"] * 100

        sl_adjusted = False
        tp_adjusted = False
        adjust_reason = ""

        if atr_ratio >= 2.5:
            sl_widen = min(1.6, 1.3 * regime_factor)
            adjust_reason = f"极端波动(ATR×{atr_ratio:.1f}) 止损放宽{(sl_widen-1)*100:.0f}%"
            if direction == "long":
                sl_distance = pos["entry_price"] - initial_sl
                new_sl = pos["entry_price"] - sl_distance * sl_widen
                if new_sl < pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = min(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            else:
                sl_distance = initial_sl - pos["entry_price"]
                new_sl = pos["entry_price"] + sl_distance * sl_widen
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = max(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            tp_extend = min(1.4, 1.2 * regime_factor)
            tp_distance = abs(pos["tp_price"] - pos["entry_price"])
            if direction == "long":
                new_tp = pos["entry_price"] + tp_distance * tp_extend
                if new_tp > pos["tp_price"]:
                    pos["tp_price"] = new_tp
                    tp_adjusted = True
            else:
                new_tp = pos["entry_price"] - tp_distance * tp_extend
                if new_tp < pos["tp_price"]:
                    pos["tp_price"] = new_tp
                    tp_adjusted = True

        elif atr_ratio >= 1.8:
            sl_widen = min(1.4, 1.2 * regime_factor)
            adjust_reason = f"高波动(ATR×{atr_ratio:.1f}) 止损放宽{(sl_widen-1)*100:.0f}%"
            if direction == "long":
                sl_distance = pos["entry_price"] - initial_sl
                new_sl = pos["entry_price"] - sl_distance * sl_widen
                if new_sl < pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = min(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            else:
                sl_distance = initial_sl - pos["entry_price"]
                new_sl = pos["entry_price"] + sl_distance * sl_widen
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = max(pos["trailing_sl"], new_sl)
                    sl_adjusted = True

        elif atr_ratio >= 1.3:
            sl_widen = min(1.2, 1.1 * regime_factor)
            adjust_reason = f"波动升高(ATR×{atr_ratio:.1f}) 止损微调放宽{(sl_widen-1)*100:.0f}%"
            if direction == "long":
                sl_distance = pos["entry_price"] - initial_sl
                new_sl = pos["entry_price"] - sl_distance * sl_widen
                if new_sl < pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = min(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            else:
                sl_distance = initial_sl - pos["entry_price"]
                new_sl = pos["entry_price"] + sl_distance * sl_widen
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = max(pos["trailing_sl"], new_sl)
                    sl_adjusted = True

        elif atr_ratio <= 0.4 and hold_hours >= 4.0 and pnl_pct >= 1.0:
            sl_tighten = max(0.6, 0.7 / regime_factor)
            adjust_reason = f"极低波动(ATR×{atr_ratio:.1f}) 止损收紧{(1-sl_tighten)*100:.0f}%(浮盈{pnl_pct:.1f}%)"
            if direction == "long":
                sl_distance = pos["entry_price"] - initial_sl
                new_sl = pos["entry_price"] - max(sl_distance * sl_tighten, entry_atr * 1.5)
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = max(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            else:
                sl_distance = initial_sl - pos["entry_price"]
                new_sl = pos["entry_price"] + max(sl_distance * sl_tighten, entry_atr * 1.5)
                if new_sl < pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = min(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            tp_shrink = max(0.75, 0.85 / regime_factor)
            tp_distance = abs(pos["tp_price"] - pos["entry_price"])
            if direction == "long":
                new_tp = pos["entry_price"] + tp_distance * tp_shrink
                if new_tp < pos["tp_price"] and new_tp > pos["entry_price"]:
                    pos["tp_price"] = new_tp
                    tp_adjusted = True
            else:
                new_tp = pos["entry_price"] - tp_distance * tp_shrink
                if new_tp > pos["tp_price"] and new_tp < pos["entry_price"]:
                    pos["tp_price"] = new_tp
                    tp_adjusted = True

        elif atr_ratio <= 0.65 and hold_hours >= 4.0 and pnl_pct >= 1.0:
            sl_tighten = max(0.75, 0.8 / regime_factor)
            adjust_reason = f"低波动(ATR×{atr_ratio:.1f}) 止损收紧{(1-sl_tighten)*100:.0f}%(浮盈{pnl_pct:.1f}%)"
            if direction == "long":
                sl_distance = pos["entry_price"] - initial_sl
                new_sl = pos["entry_price"] - max(sl_distance * sl_tighten, entry_atr * 1.5)
                if new_sl > pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = max(pos["trailing_sl"], new_sl)
                    sl_adjusted = True
            else:
                sl_distance = initial_sl - pos["entry_price"]
                new_sl = pos["entry_price"] + max(sl_distance * sl_tighten, entry_atr * 1.5)
                if new_sl < pos["sl_price"]:
                    pos["sl_price"] = new_sl
                    pos["trailing_sl"] = min(pos["trailing_sl"], new_sl)
                    sl_adjusted = True

        if pnl_pct > 3 and atr_ratio > 1.5 and not pos.get("trailing_activated"):
            if direction == "long":
                breakeven_sl = pos["entry_price"] * 1.001
                if breakeven_sl > pos["sl_price"]:
                    pos["sl_price"] = breakeven_sl
                    pos["trailing_sl"] = breakeven_sl
                    sl_adjusted = True
                    adjust_reason += " + 盈利保护(移至保本)"
            else:
                breakeven_sl = pos["entry_price"] * 0.999
                if breakeven_sl < pos["sl_price"]:
                    pos["sl_price"] = breakeven_sl
                    pos["trailing_sl"] = breakeven_sl
                    sl_adjusted = True
                    adjust_reason += " + 盈利保护(移至保本)"

        if sl_adjusted or tp_adjusted:
            pos["vol_adjust_time"] = now
            pos["vol_atr_ratio"] = round(atr_ratio, 3)
            pos["vol_regime"] = regime or "unknown"
            log_entry = {
                "time": datetime.now(BEIJING_TZ).strftime("%m-%d %H:%M"),
                "atr_ratio": round(atr_ratio, 2),
                "regime": regime or "unknown",
                "sl_adjusted": sl_adjusted,
                "tp_adjusted": tp_adjusted,
                "new_sl": round(pos["sl_price"], 6),
                "new_tp": round(pos["tp_price"], 6),
                "reason": adjust_reason,
            }
            pos["vol_adjust_log"].append(log_entry)
            if len(pos["vol_adjust_log"]) > 10:
                pos["vol_adjust_log"] = pos["vol_adjust_log"][-10:]
            logger.info(f"波动率自适应: {pos['symbol']} {adjust_reason} SL={pos['sl_price']:.6f} TP={pos['tp_price']:.6f}")
            if DB_AVAILABLE:
                try:
                    TitanDB.record_position_event(
                        trade_id=pos["id"], symbol=pos["symbol"],
                        event_type='volatility_adjustment',
                        old_value=f"SL={pos.get('initial_sl', 0):.6f}",
                        new_value=f"SL={pos['sl_price']:.6f} TP={pos['tp_price']:.6f}",
                        reason=adjust_reason,
                        current_pnl_pct=pnl_pct,
                        current_price=pos.get("current_price", 0),
                        holding_hours=round(hold_hours, 1)
                    )
                except Exception:
                    pass

    def update_positions(self, price_map, atr_map=None, regime=None):
        closed_trades = []
        pids_to_check = list(self.positions.keys())

        for pid in pids_to_check:
            if pid not in self.positions:
                continue
            pos = self.positions[pid]
            sym = pos["symbol"]
            current_price = price_map.get(sym)
            if current_price is None:
                continue

            pos["current_price"] = current_price

            if pos["direction"] == "long":
                if current_price > pos["highest_price"]:
                    pos["highest_price"] = current_price
                pnl_move = (current_price - pos["entry_price"]) / pos["entry_price"]
            else:
                if current_price < pos["lowest_price"]:
                    pos["lowest_price"] = current_price
                pnl_move = (pos["entry_price"] - current_price) / pos["entry_price"]

            if pnl_move * 100 > pos.get("peak_unrealized_pnl", 0):
                pos["peak_unrealized_pnl"] = round(pnl_move * 100, 2)
                pos["peak_unrealized_price"] = current_price

            atr = pos.get("atr_at_entry", pos["entry_price"] * 0.02)
            tp_distance = abs(pos["tp_price"] - pos["entry_price"])

            if atr_map and sym in atr_map:
                self._adjust_for_volatility(pos, atr_map[sym], regime=regime)

            current_tp_stage = pos.get("tp_stage", 0)
            if pos.get("partial_closed") is True and current_tp_stage == 0:
                current_tp_stage = 1
                pos["tp_stage"] = 1

            sl_distance_abs = abs(pos["entry_price"] - pos["sl_price"])
            if pos["direction"] == "long":
                stage1_price = pos["entry_price"] + sl_distance_abs * 1.5
                stage2_price = pos["entry_price"] + sl_distance_abs * 2.5
            else:
                stage1_price = pos["entry_price"] - sl_distance_abs * 1.5
                stage2_price = pos["entry_price"] - sl_distance_abs * 2.5

            if current_tp_stage < 1:
                if (pos["direction"] == "long" and current_price >= stage1_price) or \
                   (pos["direction"] == "short" and current_price <= stage1_price):
                    result = self._do_partial_close(pid, current_price, stage=1)
                    if result:
                        closed_trades.append(result)

            if pid not in self.positions:
                continue

            current_tp_stage = pos.get("tp_stage", 0)
            if current_tp_stage == 1 and current_tp_stage < 2:
                if (pos["direction"] == "long" and current_price >= stage2_price) or \
                   (pos["direction"] == "short" and current_price <= stage2_price):
                    result = self._do_partial_close(pid, current_price, stage=2)
                    if result:
                        closed_trades.append(result)

            if pid not in self.positions:
                continue

            profit_in_atr = pnl_move * pos["entry_price"] / atr if atr > 0 else 0

            if profit_in_atr >= 2.5:
                trail_distance = atr * 0.5
                if not pos["trailing_activated"]:
                    pos["trailing_activated"] = True
                    logger.info(f"追踪止损第3阶段激活: {pos['symbol']} 利润>{2.5}倍ATR 追踪距离=0.5*ATR")
            elif profit_in_atr >= 1.5:
                trail_distance = atr * 0.7
                if not pos["trailing_activated"]:
                    pos["trailing_activated"] = True
                    logger.info(f"追踪止损第2阶段激活: {pos['symbol']} 利润>{1.5}倍ATR 追踪距离=0.7*ATR")
            elif profit_in_atr >= 0.5:
                trail_distance = atr * 1.0
                if not pos["trailing_activated"]:
                    pos["trailing_activated"] = True
                    logger.info(f"追踪止损第1阶段激活: {pos['symbol']} 利润>{0.5}倍ATR 追踪距离=1.0*ATR")
            else:
                trail_distance = None

            if trail_distance is not None and pos["trailing_activated"]:
                peak_pnl_pct = pos.get("peak_unrealized_pnl", 0) / 100.0
                if peak_pnl_pct > 0.03:
                    max_giveback_pct = peak_pnl_pct * 0.30
                    max_giveback_pct = max(max_giveback_pct, 0.015)
                    max_giveback_abs = max_giveback_pct * pos["entry_price"]
                    hold_hours_now = (time.time() - pos["open_timestamp"]) / 3600
                    if hold_hours_now > 12:
                        max_giveback_abs *= 0.80
                    old_trail = trail_distance
                    trail_distance = min(trail_distance, max_giveback_abs)
                    if trail_distance < old_trail:
                        if not pos.get("_giveback_logged"):
                            logger.info(f"回吐保护: {pos['symbol']} peak={peak_pnl_pct*100:.1f}% 追踪距离 {old_trail:.4f}->{trail_distance:.4f} (max回吐{max_giveback_pct*100:.1f}%)")
                            pos["_giveback_logged"] = True

                if pos["direction"] == "long":
                    new_trailing = pos["highest_price"] - trail_distance
                    if new_trailing > pos["trailing_sl"]:
                        old_sl = pos["trailing_sl"]
                        pos["trailing_sl"] = new_trailing
                        pos["sl_price"] = new_trailing
                        try:
                            from server.titan_db import TitanDB
                            TitanDB.record_position_event(
                                trade_id=pid, symbol=pos["symbol"], event_type='trailing_sl_updated',
                                old_value=f"{old_sl:.6f}", new_value=f"{new_trailing:.6f}",
                                reason=f"peak={pos.get('highest_price',0):.6f} trail_dist={trail_distance:.6f}",
                                current_pnl_pct=pnl_pct * 100, current_price=current_price,
                                holding_hours=round((time.time() - pos["open_timestamp"]) / 3600, 1)
                            )
                        except Exception:
                            pass
                else:
                    new_trailing = pos["lowest_price"] + trail_distance
                    if new_trailing < pos["trailing_sl"]:
                        old_sl = pos["trailing_sl"]
                        pos["trailing_sl"] = new_trailing
                        pos["sl_price"] = new_trailing
                        try:
                            from server.titan_db import TitanDB
                            TitanDB.record_position_event(
                                trade_id=pid, symbol=pos["symbol"], event_type='trailing_sl_updated',
                                old_value=f"{old_sl:.6f}", new_value=f"{new_trailing:.6f}",
                                reason=f"peak={pos.get('lowest_price',0):.6f} trail_dist={trail_distance:.6f}",
                                current_pnl_pct=pnl_pct * 100, current_price=current_price,
                                holding_hours=round((time.time() - pos["open_timestamp"]) / 3600, 1)
                            )
                        except Exception:
                            pass

            if pid not in self.positions:
                continue

            hold_hours = (time.time() - pos["open_timestamp"]) / 3600
            min_hold_hours = 2.0
            in_grace_period = hold_hours < min_hold_hours

            if pos["direction"] == "long":
                if current_price >= pos["tp_price"]:
                    result = self.close_position(pid, current_price, "tp_hit")
                    if result:
                        closed_trades.append(result)
                    continue
                emergency_sl = pos["entry_price"] * (1 - 0.05)
                if current_price <= pos["sl_price"]:
                    if in_grace_period and current_price > emergency_sl:
                        logger.debug(f"持仓保护期: {pos['symbol']} 持仓{hold_hours:.1f}h<1h, 暂不触发SL")
                        continue
                    result = self.close_position(pid, current_price, "sl_hit")
                    if result:
                        closed_trades.append(result)
                    continue
            else:
                if current_price <= pos["tp_price"]:
                    result = self.close_position(pid, current_price, "tp_hit")
                    if result:
                        closed_trades.append(result)
                    continue
                emergency_sl = pos["entry_price"] * (1 + 0.05)
                if current_price >= pos["sl_price"]:
                    if in_grace_period and current_price < emergency_sl:
                        logger.debug(f"持仓保护期: {pos['symbol']} 持仓{hold_hours:.1f}h<1h, 暂不触发SL")
                        continue
                    result = self.close_position(pid, current_price, "sl_hit")
                    if result:
                        closed_trades.append(result)
                    continue

            if hold_hours >= 96:
                result = self.close_position(pid, current_price, "time_stop_96h_强制")
                if result:
                    closed_trades.append(result)
                    logger.info(f"时间衰减强平: {pos['symbol']} 持仓超96小时 强制平仓")
                continue

            if hold_hours >= 72 and abs(pnl_move) < 0.02:
                result = self.close_position(pid, current_price, "time_stop_72h")
                if result:
                    closed_trades.append(result)
                    logger.info(f"时间衰减平仓: {pos['symbol']} 持仓超72小时 盈亏<2%")
                continue

            if hold_hours >= 48 and not pos["trailing_activated"]:
                initial_sl = pos.get("initial_sl", pos["sl_price"])
                if pos["direction"] == "long":
                    sl_distance = pos["entry_price"] - initial_sl
                    tightened_sl = pos["entry_price"] - sl_distance * 0.6
                    if tightened_sl > pos["sl_price"]:
                        pos["sl_price"] = tightened_sl
                        logger.info(f"时间衰减收紧SL(48h-40%): {pos['symbol']} 新SL={tightened_sl:.4f}")
                else:
                    sl_distance = initial_sl - pos["entry_price"]
                    tightened_sl = pos["entry_price"] + sl_distance * 0.6
                    if tightened_sl < pos["sl_price"]:
                        pos["sl_price"] = tightened_sl
                        logger.info(f"时间衰减收紧SL(48h-40%): {pos['symbol']} 新SL={tightened_sl:.4f}")

            elif hold_hours >= 24 and not pos["trailing_activated"]:
                initial_sl = pos.get("initial_sl", pos["sl_price"])
                if pos["direction"] == "long":
                    sl_distance = pos["entry_price"] - initial_sl
                    tightened_sl = pos["entry_price"] - sl_distance * 0.8
                    if tightened_sl > pos["sl_price"]:
                        pos["sl_price"] = tightened_sl
                        logger.info(f"时间衰减收紧SL(24h-20%): {pos['symbol']} 新SL={tightened_sl:.4f}")
                else:
                    sl_distance = initial_sl - pos["entry_price"]
                    tightened_sl = pos["entry_price"] + sl_distance * 0.8
                    if tightened_sl < pos["sl_price"]:
                        pos["sl_price"] = tightened_sl
                        logger.info(f"时间衰减收紧SL(24h-20%): {pos['symbol']} 新SL={tightened_sl:.4f}")

        if closed_trades:
            self.save()

        grid_pnl = 0
        grid_realized = 0
        try:
            from server.titan_grid import grid_engine
            grid_pnl = grid_engine.get_unrealized_pnl()
            grid_realized = grid_engine.total_grid_profit
        except Exception:
            pass
        equity = self.get_equity(price_map, grid_pnl=grid_pnl, grid_realized_pnl=grid_realized)
        if equity > self.peak_equity:
            self.peak_equity = equity
        current_dd = (self.peak_equity - equity) / (self.peak_equity + 1e-10) * 100
        if current_dd > self.max_drawdown_pct:
            self.max_drawdown_pct = round(current_dd, 4)

        return closed_trades

    def smart_liquidate_worst(self, price_map, max_keep=6, reason="smart_cleanup"):
        if len(self.positions) <= max_keep:
            return []
        scored = []
        for pid, pos in self.positions.items():
            sym = pos["symbol"]
            current_price = price_map.get(sym, pos.get("current_price", pos["entry_price"]))
            if pos["direction"] == "long":
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
            else:
                pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100
            scored.append((pid, pnl_pct))
        scored.sort(key=lambda x: x[1])
        to_close = len(self.positions) - max_keep
        closed = []
        for pid, pnl in scored[:to_close]:
            sym = self.positions[pid]["symbol"]
            price = price_map.get(sym, self.positions[pid].get("current_price", self.positions[pid]["entry_price"]))
            result = self.close_position(pid, price, reason)
            if result:
                closed.append(result)
        return closed

    def force_liquidate_all(self, price_map, reason="emergency"):
        closed = []
        for pid in list(self.positions.keys()):
            sym = self.positions[pid]["symbol"]
            price = price_map.get(sym, self.positions[pid]["current_price"])
            result = self.close_position(pid, price, reason)
            if result:
                closed.append(result)
        return closed

    def get_positions_display(self, price_map=None):
        result = []
        for pid, pos in self.positions.items():
            current_price = price_map.get(pos["symbol"], pos["current_price"]) if price_map else pos["current_price"]
            if pos["direction"] == "long":
                pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"] * 100
                tp_progress = (current_price - pos["entry_price"]) / (pos["tp_price"] - pos["entry_price"] + 1e-10) * 100
                sl_progress = (pos["entry_price"] - current_price) / (pos["entry_price"] - pos["initial_sl"] + 1e-10) * 100
            else:
                pnl_pct = (pos["entry_price"] - current_price) / pos["entry_price"] * 100
                tp_progress = (pos["entry_price"] - current_price) / (pos["entry_price"] - pos["tp_price"] + 1e-10) * 100
                sl_progress = (current_price - pos["entry_price"]) / (pos["initial_sl"] - pos["entry_price"] + 1e-10) * 100

            pnl_value = pos["remaining_value"] * pnl_pct / 100
            hold_hours = (time.time() - pos["open_timestamp"]) / 3600

            tp_stage = pos.get("tp_stage", 0)
            if pos.get("partial_closed") is True and tp_stage == 0:
                tp_stage = 1

            result.append({
                "id": pid,
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "entry_price": pos["entry_price"],
                "current_price": current_price,
                "tp_price": pos["tp_price"],
                "sl_price": pos["sl_price"],
                "trailing_sl": pos["trailing_sl"],
                "trailing_activated": pos["trailing_activated"],
                "partial_closed": pos.get("partial_closed", False),
                "tp_stage": tp_stage,
                "position_value": pos["remaining_value"],
                "amount": pos["remaining_value"],
                "pnl_pct": round(pnl_pct, 2),
                "pnl_value": round(pnl_value, 2),
                "unrealized_pnl": round(pnl_value, 2),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "tp_progress": round(min(max(tp_progress, 0), 100), 1),
                "sl_progress": round(min(max(sl_progress, 0), 100), 1),
                "hold_hours": round(hold_hours, 1),
                "signal_score": pos["signal_score"],
                "open_time": pos["open_time"],
                "tp_type": pos.get("tp_type", "standard"),
                "mechanism": pos.get("mechanism", "auto"),
                "vol_atr_ratio": pos.get("vol_atr_ratio", 1.0),
                "vol_regime": pos.get("vol_regime", "unknown"),
                "vol_adjust_log": pos.get("vol_adjust_log", [])[-5:],
                "guard_warnings": pos.get("guard_warnings", []),
                "btc_corr_alert": pos.get("btc_corr_alert", False),
                "ai_advisor": pos.get("ai_advisor", None),
            })
        return result

    def _get_db_trade_stats(self):
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                        COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses,
                        COALESCE(ROUND(SUM(pnl_value)::numeric, 2), 0) as total_pnl
                    FROM trades
                    WHERE result IN ('win', 'loss')
                    AND (extra->>'is_test_data')::boolean IS NOT TRUE
                """)
                row = cur.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.warning(f"DB交易统计查询失败: {e}")
        return None

    def _calc_direction_accuracy(self):
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins
                    FROM trades
                    WHERE result IN ('win', 'loss')
                    AND (extra->>'is_test_data')::boolean IS NOT TRUE
                    AND direction IS NOT NULL
                """)
                row = cur.fetchone()
                if row and row['total'] > 0:
                    return round(row['wins'] / row['total'] * 100, 1)
        except Exception as e:
            logger.warning(f"方向准确率查询失败: {e}")
        return None

    def get_portfolio_summary(self, price_map=None, grid_pnl=0.0, grid_realized_pnl=0.0):
        equity = self.get_equity(price_map, grid_pnl=grid_pnl, grid_realized_pnl=grid_realized_pnl)
        exposure = self.get_total_exposure()

        db_stats = self._get_db_trade_stats()
        if db_stats:
            total_trades = db_stats['total']
            total_wins = db_stats['wins']
            total_losses = db_stats['losses']
            total_pnl = float(db_stats['total_pnl']) + grid_pnl
        else:
            total_trades = self.total_wins + self.total_losses
            total_wins = self.total_wins
            total_losses = self.total_losses
            total_pnl = sum(t.get("pnl_value", 0) for t in self.trade_history) + grid_pnl

        win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        current_dd = (self.peak_equity - equity) / (self.peak_equity + 1e-10) * 100
        historical_max_dd = max(self.max_drawdown_pct, current_dd)

        direction_accuracy = self._calc_direction_accuracy()

        return {
            "capital": round(self.capital, 2),
            "equity": round(equity, 2),
            "total_value": round(equity, 2),
            "total_exposure": round(exposure, 2),
            "exposure_pct": round(exposure / (equity + 1e-10) * 100, 1),
            "open_positions": len(self.positions),
            "total_trades": total_trades,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "win_rate": round(win_rate, 1),
            "consecutive_wins": self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round((equity - self.INITIAL_CAPITAL) / self.INITIAL_CAPITAL * 100, 2),
            "max_drawdown_pct": round(historical_max_dd, 2),
            "current_drawdown_pct": round(current_dd, 2),
            "peak_equity": round(self.peak_equity, 2),
            "direction_accuracy": direction_accuracy,
        }

    def get_recent_trades(self, limit=20):
        return list(reversed(self.trade_history[-limit:]))
