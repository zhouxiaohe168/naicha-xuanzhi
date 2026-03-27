import logging
import time
from datetime import datetime
import pytz

logger = logging.getLogger("TitanPositionGuard")
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

BEARISH_PATTERNS = {
    "evening_star": "黄昏之星",
    "bearish_engulfing": "看跌吞没",
    "shooting_star": "射击之星",
    "dark_cloud": "乌云盖顶",
    "three_black_crows": "三只乌鸦",
    "hanging_man": "上吊线",
    "bearish_harami": "看跌孕线",
}

BULLISH_PATTERNS = {
    "morning_star": "晨星",
    "bullish_engulfing": "看涨吞没",
    "hammer": "锤子线",
    "piercing_line": "刺透形态",
    "three_white_soldiers": "三白兵",
    "inverted_hammer": "倒锤线",
    "bullish_harami": "看涨孕线",
}


class TitanPositionGuard:

    def __init__(self):
        self.check_interval = 900
        self.btc_alert_threshold = -0.03
        self.pattern_cache = {}
        self.guard_log = []

    def detect_kline_patterns(self, candles):
        if not candles or len(candles) < 3:
            return []

        patterns = []
        try:
            c = candles[-1]
            p = candles[-2]
            pp = candles[-3]

            c_open, c_high, c_low, c_close = float(c[1]), float(c[2]), float(c[3]), float(c[4])
            p_open, p_high, p_low, p_close = float(p[1]), float(p[2]), float(p[3]), float(p[4])
            pp_open, pp_high, pp_low, pp_close = float(pp[1]), float(pp[2]), float(pp[3]), float(pp[4])

            c_body = abs(c_close - c_open)
            p_body = abs(p_close - p_open)
            pp_body = abs(pp_close - pp_open)
            c_range = c_high - c_low
            p_range = p_high - p_low

            if c_body > 0 and p_body > 0 and c_range > 0:
                if p_close > p_open and c_close < c_open:
                    if c_body > p_body * 0.8 and c_open >= p_close and c_close <= p_open:
                        patterns.append({"pattern": "bearish_engulfing", "name": "看跌吞没", "type": "bearish", "strength": 0.8})

                if p_close < p_open and c_close > c_open:
                    if c_body > p_body * 0.8 and c_open <= p_close and c_close >= p_open:
                        patterns.append({"pattern": "bullish_engulfing", "name": "看涨吞没", "type": "bullish", "strength": 0.8})

                if pp_close > pp_open and p_body < pp_body * 0.3 and c_close < c_open and c_body > pp_body * 0.5:
                    patterns.append({"pattern": "evening_star", "name": "黄昏之星", "type": "bearish", "strength": 0.85})

                if pp_close < pp_open and p_body < pp_body * 0.3 and c_close > c_open and c_body > pp_body * 0.5:
                    patterns.append({"pattern": "morning_star", "name": "晨星", "type": "bullish", "strength": 0.85})

                upper_shadow = c_high - max(c_open, c_close)
                lower_shadow = min(c_open, c_close) - c_low
                if upper_shadow > c_body * 2 and lower_shadow < c_body * 0.3 and c_range > 0:
                    patterns.append({"pattern": "shooting_star", "name": "射击之星", "type": "bearish", "strength": 0.7})

                if lower_shadow > c_body * 2 and upper_shadow < c_body * 0.3 and c_range > 0:
                    patterns.append({"pattern": "hammer", "name": "锤子线", "type": "bullish", "strength": 0.7})

                if pp_close > pp_open and p_close > p_open and c_close > c_open:
                    if pp_body > 0 and p_body > 0 and c_body > 0:
                        if p_open > pp_close * 0.99 and c_open > p_close * 0.99:
                            patterns.append({"pattern": "three_white_soldiers", "name": "三白兵", "type": "bullish", "strength": 0.9})

                if pp_close < pp_open and p_close < p_open and c_close < c_open:
                    if pp_body > 0 and p_body > 0 and c_body > 0:
                        if p_open < pp_close * 1.01 and c_open < p_close * 1.01:
                            patterns.append({"pattern": "three_black_crows", "name": "三只乌鸦", "type": "bearish", "strength": 0.9})

                if p_close > p_open and c_close < c_open:
                    if c_close > p_open and c_open > p_close * 0.99:
                        if (p_close - c_close) > p_body * 0.5:
                            patterns.append({"pattern": "dark_cloud", "name": "乌云盖顶", "type": "bearish", "strength": 0.75})

                if p_close < p_open and c_close > c_open:
                    if c_close < p_open and c_open < p_close * 1.01:
                        if (c_close - p_close) > p_body * 0.5:
                            patterns.append({"pattern": "piercing_line", "name": "刺透形态", "type": "bullish", "strength": 0.75})

        except Exception as e:
            logger.warning(f"K线形态检测异常: {e}")

        return patterns

    def check_btc_correlation(self, btc_price_current, btc_price_prev, pos_direction):
        if not btc_price_current or not btc_price_prev or btc_price_prev == 0:
            return None

        btc_change = (btc_price_current - btc_price_prev) / btc_price_prev

        alert = None
        if pos_direction == "long" and btc_change < self.btc_alert_threshold:
            alert = {
                "type": "btc_correlation_alert",
                "severity": "high" if btc_change < -0.05 else "medium",
                "btc_change_pct": round(btc_change * 100, 2),
                "action": "建议减仓" if btc_change < -0.05 else "关注风险",
                "message": f"BTC急跌{btc_change*100:.1f}%，多头持仓风险升高",
            }
        elif pos_direction == "short" and btc_change > abs(self.btc_alert_threshold):
            alert = {
                "type": "btc_correlation_alert",
                "severity": "high" if btc_change > 0.05 else "medium",
                "btc_change_pct": round(btc_change * 100, 2),
                "action": "建议减仓" if btc_change > 0.05 else "关注风险",
                "message": f"BTC急涨{btc_change*100:.1f}%，空头持仓风险升高",
            }

        return alert

    def evaluate_position(self, pos, candles=None, btc_price_current=None, btc_price_prev=None, current_atr=None):
        warnings = []
        recommendations = []
        now = time.time()

        hold_hours = (now - pos.get("open_timestamp", now)) / 3600
        entry_price = pos["entry_price"]
        current_price = pos.get("current_price", entry_price)
        direction = pos["direction"]

        if direction == "long":
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - current_price) / entry_price * 100

        if candles and len(candles) >= 3:
            patterns = self.detect_kline_patterns(candles)
            for p in patterns:
                if direction == "long" and p["type"] == "bearish" and p["strength"] >= 0.7:
                    warnings.append({
                        "type": "pattern_reversal",
                        "pattern": p["name"],
                        "strength": p["strength"],
                        "message": f"检测到{p['name']}反转形态(强度{p['strength']})，多头持仓风险升高",
                        "action": "tighten_sl" if pnl_pct > 0 else "consider_close",
                    })
                elif direction == "short" and p["type"] == "bullish" and p["strength"] >= 0.7:
                    warnings.append({
                        "type": "pattern_reversal",
                        "pattern": p["name"],
                        "strength": p["strength"],
                        "message": f"检测到{p['name']}反转形态(强度{p['strength']})，空头持仓风险升高",
                        "action": "tighten_sl" if pnl_pct > 0 else "consider_close",
                    })
                elif direction == "long" and p["type"] == "bullish" and p["strength"] >= 0.8:
                    recommendations.append({
                        "type": "pattern_continuation",
                        "pattern": p["name"],
                        "message": f"检测到{p['name']}延续形态，趋势可能加速",
                        "action": "hold_or_add",
                    })
                elif direction == "short" and p["type"] == "bearish" and p["strength"] >= 0.8:
                    recommendations.append({
                        "type": "pattern_continuation",
                        "pattern": p["name"],
                        "message": f"检测到{p['name']}延续形态，下跌可能加速",
                        "action": "hold_or_add",
                    })

        btc_alert = self.check_btc_correlation(btc_price_current, btc_price_prev, direction)
        if btc_alert:
            warnings.append(btc_alert)

        if pnl_pct < -5 and hold_hours > 12:
            warnings.append({
                "type": "deep_loss",
                "message": f"持仓亏损{pnl_pct:.1f}%且持有{hold_hours:.0f}h，建议评估是否继续持有",
                "action": "consider_close",
            })

        if pnl_pct > 5 and hold_hours > 48:
            recommendations.append({
                "type": "profit_lock",
                "message": f"持仓盈利{pnl_pct:.1f}%且持有{hold_hours:.0f}h，建议锁定利润",
                "action": "tighten_sl",
            })

        if current_atr and pos.get("atr_at_entry"):
            atr_ratio = current_atr / pos["atr_at_entry"]
            if atr_ratio > 2.0:
                warnings.append({
                    "type": "volatility_spike",
                    "message": f"波动率飙升至入场时{atr_ratio:.1f}倍，市场环境剧变",
                    "action": "reduce_size",
                })

        confidence = 50
        if pnl_pct > 0:
            confidence += min(pnl_pct * 3, 30)
        else:
            confidence += max(pnl_pct * 2, -30)

        if len(warnings) > 0:
            confidence -= len(warnings) * 10
        if len(recommendations) > 0:
            confidence += len(recommendations) * 5

        confidence = max(0, min(100, confidence))

        action = "hold"
        if confidence < 20:
            action = "close"
        elif confidence < 35:
            action = "reduce"
        elif confidence < 50:
            action = "tighten_sl"

        return {
            "symbol": pos["symbol"],
            "direction": direction,
            "hold_hours": round(hold_hours, 1),
            "pnl_pct": round(pnl_pct, 2),
            "confidence": round(confidence),
            "action": action,
            "warnings": warnings,
            "recommendations": recommendations,
            "checked_at": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        }

    def guard_all_positions(self, paper_trader, price_map, candle_map=None, btc_data=None, atr_map=None):
        results = []
        actions_taken = []

        btc_current = btc_data.get("current") if btc_data else None
        btc_prev = btc_data.get("prev_4h") if btc_data else None

        for pid, pos in list(paper_trader.positions.items()):
            sym = pos["symbol"]

            now = time.time()
            last_check = pos.get("last_guard_check", 0)
            if (now - last_check) < self.check_interval:
                continue

            candles = candle_map.get(sym) if candle_map else None
            current_atr = atr_map.get(sym) if atr_map else None

            evaluation = self.evaluate_position(
                pos,
                candles=candles,
                btc_price_current=btc_current,
                btc_price_prev=btc_prev,
                current_atr=current_atr,
            )

            pos["last_guard_check"] = now
            pos["guard_warnings"] = [w.get("message", "") for w in evaluation.get("warnings", [])][:5]

            if evaluation["action"] == "close" and evaluation["confidence"] < 15:
                current_price = price_map.get(sym, pos.get("current_price", pos["entry_price"]))
                result = paper_trader.close_position(pid, current_price, "guard_close")
                if result:
                    actions_taken.append({
                        "action": "close",
                        "symbol": sym,
                        "reason": f"守卫评估置信度{evaluation['confidence']}，强制平仓",
                        "warnings": evaluation["warnings"],
                    })
                    logger.info(f"守卫平仓: {sym} 置信度={evaluation['confidence']}")

            elif evaluation["action"] == "tighten_sl":
                hold_hours = (now - pos.get("open_timestamp", now)) / 3600
                if hold_hours < 4.0:
                    logger.info(f"守卫持仓保护: {sym} 持仓{hold_hours:.1f}h<4h, 跳过SL收紧")
                    continue

                entry_price = pos["entry_price"]
                current_price = price_map.get(sym, pos.get("current_price", entry_price))
                if pos["direction"] == "long":
                    unrealized_pnl_pct = (current_price - entry_price) / entry_price * 100
                else:
                    unrealized_pnl_pct = (entry_price - current_price) / entry_price * 100

                if unrealized_pnl_pct < 1.0:
                    logger.info(f"守卫浮盈保护: {sym} 浮盈{unrealized_pnl_pct:.2f}%<1%, 不收紧SL")
                    continue

                atr = pos.get("atr_at_entry") or entry_price * 0.02
                if not atr or atr <= 0:
                    atr = entry_price * 0.02
                initial_sl = pos.get("initial_sl", pos["sl_price"])
                initial_sl_dist = abs(entry_price - initial_sl)
                if initial_sl_dist <= 0:
                    initial_sl_dist = atr * 2.5

                tighten_factor = 0.6
                if hold_hours < 6:
                    tighten_factor = 0.75

                min_sl_pct_floor = entry_price * 0.03
                min_sl_dist = max(initial_sl_dist * tighten_factor, atr * 1.5, min_sl_pct_floor)

                max_tighten_step = initial_sl_dist * 0.20
                if pos["direction"] == "long":
                    candidate_sl = max(pos["sl_price"], entry_price - min_sl_dist)
                    step = candidate_sl - pos["sl_price"]
                    if step > max_tighten_step:
                        candidate_sl = pos["sl_price"] + max_tighten_step
                    if candidate_sl > pos["sl_price"]:
                        pos["sl_price"] = candidate_sl
                        pos["trailing_sl"] = max(pos.get("trailing_sl", candidate_sl), candidate_sl)
                        actions_taken.append({
                            "action": "tighten_sl",
                            "symbol": sym,
                            "new_sl": candidate_sl,
                            "reason": f"守卫收紧止损(保留{min_sl_dist/atr:.1f}xATR,浮盈{unrealized_pnl_pct:.1f}%)",
                        })
                else:
                    candidate_sl = min(pos["sl_price"], entry_price + min_sl_dist)
                    step = pos["sl_price"] - candidate_sl
                    if step > max_tighten_step:
                        candidate_sl = pos["sl_price"] - max_tighten_step
                    if candidate_sl < pos["sl_price"]:
                        pos["sl_price"] = candidate_sl
                        pos["trailing_sl"] = min(pos.get("trailing_sl", candidate_sl), candidate_sl)
                        actions_taken.append({
                            "action": "tighten_sl",
                            "symbol": sym,
                            "new_sl": candidate_sl,
                            "reason": f"守卫收紧止损(保留{min_sl_dist/atr:.1f}xATR,浮盈{unrealized_pnl_pct:.1f}%)",
                        })

            for w in evaluation.get("warnings", []):
                if w.get("type") == "btc_correlation_alert" and w.get("severity") == "high":
                    pos["btc_corr_alert"] = True

            results.append(evaluation)

        if actions_taken:
            paper_trader.save()
            self.guard_log.extend(actions_taken)
            self.guard_log = self.guard_log[-100:]

        return {
            "checked": len(results),
            "actions": actions_taken,
            "evaluations": results,
            "timestamp": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        }

    def get_guard_log(self, limit=20):
        return list(reversed(self.guard_log[-limit:]))

    def get_status(self):
        return {
            "check_interval_seconds": self.check_interval,
            "btc_alert_threshold": self.btc_alert_threshold,
            "recent_actions": len(self.guard_log),
            "pattern_types": {
                "bearish": list(BEARISH_PATTERNS.values()),
                "bullish": list(BULLISH_PATTERNS.values()),
            },
        }
