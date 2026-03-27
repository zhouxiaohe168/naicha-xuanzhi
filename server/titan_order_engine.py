import os
import json
import logging
import math
from datetime import datetime

logger = logging.getLogger("TitanOrderEngine")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TitanOrderEngine:

    REGIME_TP_SL = {
        "trending": {"tp_base": 2.2, "sl_base": 1.0, "rr_min": 1.8, "rr_max": 2.8},
        "ranging":  {"tp_base": 1.3, "sl_base": 1.0, "rr_min": 1.2, "rr_max": 1.8},
        "volatile": {"tp_base": 1.8, "sl_base": 1.3, "rr_min": 1.2, "rr_max": 2.0},
        "mixed":    {"tp_base": 1.8, "sl_base": 1.0, "rr_min": 1.5, "rr_max": 2.2},
    }

    ADX_TIER = {
        "strong":  {"min_adx": 30, "tp_boost": 1.15, "sl_factor": 1.0},
        "medium":  {"min_adx": 20, "tp_boost": 1.0,  "sl_factor": 1.0},
        "weak":    {"min_adx": 0,  "tp_boost": 0.85, "sl_factor": 0.9},
    }

    def __init__(self):
        self.decision_log = []

    def compute_order(self, context: dict) -> dict:
        price = context.get("price", 0)
        direction = context.get("direction", "long")
        atr = context.get("atr", 0)
        regime = context.get("regime", "mixed")
        adx = context.get("adx", 20)
        rsi = context.get("rsi", 50)
        signal_score = context.get("signal_score", 0)
        ml_prediction = context.get("ml_prediction", {})
        fng = context.get("fng", 50)
        atr_1h = context.get("atr_1h", 0)
        atr_daily = context.get("atr_daily", 0)

        if price <= 0 or atr <= 0:
            return self._empty_result("价格或ATR无效", context)

        chain = []

        chain.append(f"第1层-信号评分: {signal_score}分")

        ml_probs = ml_prediction.get("probabilities", {})
        ml_conf = ml_prediction.get("confidence", 0)
        ml_label = ml_prediction.get("label", "未知")
        meta_trade = ml_prediction.get("meta_trade", True)
        meta_conf = ml_prediction.get("meta_confidence", 100)

        prob_up = ml_probs.get("涨", 33)
        prob_down = ml_probs.get("跌", 33)
        prob_flat = ml_probs.get("横盘", 34)

        if direction == "long":
            direction_prob = prob_up
            counter_prob = prob_down
        else:
            direction_prob = prob_down
            counter_prob = prob_up

        chain.append(
            f"第2层-ML研判: {ml_label}(置信{ml_conf}%) "
            f"涨{prob_up}%/跌{prob_down}%/盘{prob_flat}% "
            f"Meta交易={'允许' if meta_trade else '禁止'}({meta_conf}%)"
        )

        regime_params = self.REGIME_TP_SL.get(regime, self.REGIME_TP_SL["mixed"])
        tp_base = regime_params["tp_base"]
        sl_base = regime_params["sl_base"]
        rr_min = regime_params["rr_min"]
        rr_max = regime_params["rr_max"]

        if adx >= 30:
            adx_tier = "strong"
        elif adx >= 20:
            adx_tier = "medium"
        else:
            adx_tier = "weak"

        adx_config = self.ADX_TIER[adx_tier]
        tp_base *= adx_config["tp_boost"]
        sl_base *= adx_config["sl_factor"]

        chain.append(
            f"第3层-环境匹配: {regime}市场 ADX={adx:.0f}({adx_tier}) "
            f"基础TP={tp_base:.2f}x SL={sl_base:.2f}x"
        )

        ml_tp_factor = 1.0
        ml_sl_factor = 1.0

        if direction_prob >= 70:
            ml_tp_factor = 1.20
            ml_sl_factor = 1.0
        elif direction_prob >= 60:
            ml_tp_factor = 1.10
            ml_sl_factor = 1.0
        elif direction_prob >= 50:
            ml_tp_factor = 1.0
            ml_sl_factor = 1.0
        elif direction_prob >= 40:
            ml_tp_factor = 0.85
            ml_sl_factor = 0.95
        else:
            ml_tp_factor = 0.70
            ml_sl_factor = 0.90

        if not meta_trade:
            ml_tp_factor *= 0.80
            ml_sl_factor *= 0.85

        tp_mult = tp_base * ml_tp_factor
        sl_mult = sl_base * ml_sl_factor

        atr_pct = atr / price * 100
        if atr_pct > 5.0:
            sl_mult *= 1.15
            chain.append(f"波动率保护: ATR%={atr_pct:.1f}% 止损放宽15%")
        elif atr_pct < 1.0:
            sl_mult *= 0.85
            tp_mult *= 0.90
            chain.append(f"低波动调整: ATR%={atr_pct:.1f}% 止损收紧15%")

        if atr_1h > 0 and atr > 0:
            intraday_ratio = atr_1h / (atr / 4)
            if intraday_ratio > 1.5:
                sl_mult *= 1.10
                chain.append(f"短周期波动偏高(1H/4H比={intraday_ratio:.2f}), SL+10%")

        if atr_daily > 0 and atr > 0:
            daily_ratio = atr_daily / (atr * 6)
            max_sl_distance = atr_daily * 0.5
            current_sl_distance = atr * sl_mult
            if current_sl_distance > max_sl_distance:
                capped_mult = max_sl_distance / atr
                chain.append(f"日线风险上限: SL从{sl_mult:.2f}x压缩至{capped_mult:.2f}x")
                sl_mult = capped_mult

        raw_rr = tp_mult / sl_mult if sl_mult > 0 else 1.5
        if raw_rr < rr_min:
            tp_mult = sl_mult * rr_min
            chain.append(f"盈亏比{raw_rr:.2f}低于下限{rr_min}, 上调TP至{tp_mult:.2f}x")
        elif raw_rr > rr_max:
            tp_mult = sl_mult * rr_max
            chain.append(f"盈亏比{raw_rr:.2f}超过上限{rr_max}, 下调TP至{tp_mult:.2f}x")

        final_rr = tp_mult / sl_mult if sl_mult > 0 else 1.5

        sl_pct = (atr * sl_mult) / price * 100
        min_sl_pct = 0.5
        max_sl_pct = 8.0
        if sl_pct < min_sl_pct:
            sl_mult = (price * min_sl_pct / 100) / atr
            chain.append(f"止损距离{sl_pct:.2f}%太小, 调至最低{min_sl_pct}%")
        elif sl_pct > max_sl_pct:
            sl_mult = (price * max_sl_pct / 100) / atr
            chain.append(f"止损距离{sl_pct:.2f}%过大, 限制在{max_sl_pct}%")
            tp_mult = sl_mult * min(final_rr, rr_max)

        if direction == "long":
            tp_price = round(price + atr * tp_mult, 8)
            sl_price = round(price - atr * sl_mult, 8)
        else:
            tp_price = round(price - atr * tp_mult, 8)
            sl_price = round(price + atr * sl_mult, 8)

        final_rr = tp_mult / sl_mult if sl_mult > 0 else 1.5
        tp_distance_pct = round(abs(tp_price - price) / price * 100, 2)
        sl_distance_pct = round(abs(sl_price - price) / price * 100, 2)

        chain.append(
            f"第4层-智能定价: TP={tp_mult:.2f}x({tp_distance_pct}%) "
            f"SL={sl_mult:.2f}x({sl_distance_pct}%) "
            f"盈亏比={final_rr:.2f}:1 "
            f"ML方向概率={direction_prob:.0f}%加成={ml_tp_factor:.2f}x"
        )

        risk_grade = self._assess_risk_grade(
            signal_score, ml_conf, direction_prob, meta_trade,
            regime, adx, fng, final_rr
        )

        chain.append(f"风险评级: {risk_grade['grade']} - {risk_grade['summary']}")

        partial_tp_plan = self._compute_partial_tp(
            price, tp_price, sl_price, direction, regime, direction_prob
        )

        entry_strategy = self._compute_entry_strategy(
            price, atr, direction, adx, rsi, direction_prob
        )

        result = {
            "tp_price": tp_price,
            "sl_price": sl_price,
            "tp_mult": round(tp_mult, 3),
            "sl_mult": round(sl_mult, 3),
            "risk_reward": round(final_rr, 2),
            "tp_distance_pct": tp_distance_pct,
            "sl_distance_pct": sl_distance_pct,
            "direction_prob": round(direction_prob, 1),
            "counter_prob": round(counter_prob, 1),
            "ml_tp_factor": round(ml_tp_factor, 2),
            "regime": regime,
            "adx_tier": adx_tier,
            "risk_grade": risk_grade,
            "decision_chain": chain,
            "partial_tp_plan": partial_tp_plan,
            "entry_strategy": entry_strategy,
            "meta_trade": meta_trade,
            "meta_confidence": meta_conf,
        }

        self.decision_log.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": context.get("symbol", ""),
            "direction": direction,
            "rr": final_rr,
            "tp_mult": tp_mult,
            "sl_mult": sl_mult,
            "ml_prob": direction_prob,
            "regime": regime,
            "risk_grade": risk_grade["grade"],
        })
        if len(self.decision_log) > 200:
            self.decision_log = self.decision_log[-200:]

        return result

    def _assess_risk_grade(self, score, ml_conf, dir_prob, meta_trade,
                           regime, adx, fng, rr):
        risk_points = 0
        factors = []

        if score >= 85:
            risk_points -= 2
            factors.append(f"高评分{score}")
        elif score >= 70:
            pass
        else:
            risk_points += 2
            factors.append(f"低评分{score}")

        if ml_conf >= 70:
            risk_points -= 1
            factors.append(f"ML高置信{ml_conf:.0f}%")
        elif ml_conf < 50:
            risk_points += 1
            factors.append(f"ML低置信{ml_conf:.0f}%")

        if dir_prob >= 65:
            risk_points -= 1
        elif dir_prob < 45:
            risk_points += 2
            factors.append(f"方向概率仅{dir_prob:.0f}%")

        if not meta_trade:
            risk_points += 2
            factors.append("Meta-Labeler不建议交易")

        if regime == "volatile":
            risk_points += 1
            factors.append("高波动环境")
        elif regime == "trending" and adx >= 25:
            risk_points -= 1

        if fng <= 15 or fng >= 85:
            risk_points += 1
            factors.append(f"极端情绪FNG={fng}")

        if rr < 1.5:
            risk_points += 1
            factors.append(f"盈亏比偏低{rr:.1f}")

        if risk_points <= -2:
            grade = "A"
            summary = "优质机会，信号强烈"
            color = "emerald"
        elif risk_points <= 0:
            grade = "B"
            summary = "良好机会，可正常建仓"
            color = "blue"
        elif risk_points <= 2:
            grade = "C"
            summary = "一般机会，建议轻仓"
            color = "amber"
        elif risk_points <= 4:
            grade = "D"
            summary = "高风险，需谨慎评估"
            color = "orange"
        else:
            grade = "F"
            summary = "极高风险，建议放弃"
            color = "red"

        return {
            "grade": grade,
            "points": risk_points,
            "summary": summary,
            "color": color,
            "factors": factors,
        }

    def _compute_partial_tp(self, price, tp_price, sl_price, direction, regime, dir_prob):
        tp_distance = abs(tp_price - price)
        sl_distance = abs(sl_price - price)

        if regime in ("trending",) and dir_prob >= 60:
            stage1_pct = 0.35
            stage1_at = 0.40
            stage2_pct = 0.35
            stage2_at = 0.70
            trail_remaining = True
        elif regime in ("ranging",):
            stage1_pct = 0.50
            stage1_at = 0.50
            stage2_pct = 0.30
            stage2_at = 0.80
            trail_remaining = False
        else:
            stage1_pct = 0.30
            stage1_at = 0.40
            stage2_pct = 0.30
            stage2_at = 0.70
            trail_remaining = True

        if direction == "long":
            s1_price = round(price + tp_distance * stage1_at, 8)
            s2_price = round(price + tp_distance * stage2_at, 8)
            breakeven_at = round(price + sl_distance * 0.3, 8)
        else:
            s1_price = round(price - tp_distance * stage1_at, 8)
            s2_price = round(price - tp_distance * stage2_at, 8)
            breakeven_at = round(price - sl_distance * 0.3, 8)

        return {
            "stage1": {
                "close_pct": int(stage1_pct * 100),
                "trigger_price": s1_price,
                "trigger_at_pct": int(stage1_at * 100),
                "description": f"到达{int(stage1_at*100)}%止盈距离时平{int(stage1_pct*100)}%仓位",
            },
            "stage2": {
                "close_pct": int(stage2_pct * 100),
                "trigger_price": s2_price,
                "trigger_at_pct": int(stage2_at * 100),
                "description": f"到达{int(stage2_at*100)}%止盈距离时再平{int(stage2_pct*100)}%仓位",
            },
            "remaining": {
                "pct": int((1 - stage1_pct - stage2_pct) * 100),
                "trail": trail_remaining,
                "description": f"剩余{int((1-stage1_pct-stage2_pct)*100)}%仓位{'追踪止盈' if trail_remaining else '到达TP全平'}",
            },
            "breakeven_trigger": breakeven_at,
            "breakeven_description": f"价格到达{breakeven_at}后止损移至保本价",
        }

    def _compute_entry_strategy(self, price, atr, direction, adx, rsi, dir_prob):
        if adx >= 30 and dir_prob >= 65:
            entry_type = "market"
            limit_offset = 0
            description = "强趋势+高概率，市价立即入场"
        elif adx >= 20:
            offset_pct = 0.15
            limit_offset = atr * offset_pct
            entry_type = "limit"
            if direction == "long":
                description = f"挂单略低于现价${limit_offset:.4f}入场，等待小回调"
            else:
                description = f"挂单略高于现价${limit_offset:.4f}入场，等待小反弹"
        else:
            offset_pct = 0.25
            limit_offset = atr * offset_pct
            entry_type = "limit"
            if direction == "long":
                description = f"震荡市挂单低于现价${limit_offset:.4f}，耐心等待"
            else:
                description = f"震荡市挂单高于现价${limit_offset:.4f}，耐心等待"

        if direction == "long":
            limit_price = round(price - limit_offset, 8) if entry_type == "limit" else price
        else:
            limit_price = round(price + limit_offset, 8) if entry_type == "limit" else price

        return {
            "type": entry_type,
            "market_price": price,
            "limit_price": limit_price,
            "offset_pct": round(limit_offset / price * 100, 3) if price > 0 else 0,
            "description": description,
        }

    def _empty_result(self, reason, context):
        return {
            "tp_price": 0,
            "sl_price": 0,
            "tp_mult": 0,
            "sl_mult": 0,
            "risk_reward": 0,
            "tp_distance_pct": 0,
            "sl_distance_pct": 0,
            "direction_prob": 0,
            "counter_prob": 0,
            "ml_tp_factor": 1.0,
            "regime": context.get("regime", "unknown"),
            "adx_tier": "weak",
            "risk_grade": {"grade": "F", "points": 10, "summary": reason,
                           "color": "red", "factors": [reason]},
            "decision_chain": [f"错误: {reason}"],
            "partial_tp_plan": {},
            "entry_strategy": {"type": "none", "description": reason},
            "meta_trade": False,
            "meta_confidence": 0,
        }

    def get_stats(self):
        recent = self.decision_log[-50:]
        if not recent:
            return {"total": 0, "avg_rr": 0, "grade_dist": {}}

        avg_rr = sum(d["rr"] for d in recent) / len(recent)
        grade_dist = {}
        for d in recent:
            g = d["risk_grade"]
            grade_dist[g] = grade_dist.get(g, 0) + 1

        return {
            "total": len(self.decision_log),
            "recent_count": len(recent),
            "avg_rr": round(avg_rr, 2),
            "grade_distribution": grade_dist,
            "recent_decisions": recent[-5:],
        }


order_engine = TitanOrderEngine()
