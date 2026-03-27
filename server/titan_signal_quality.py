import os
import json
import math
import logging
from datetime import datetime
from collections import defaultdict
from server.titan_prompt_library import SIGNAL_QUALITY_PROMPT, PHASE_ZERO_CONTEXT

logger = logging.getLogger("TitanSignalQuality")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQ_PATH = os.path.join(BASE_DIR, "data", "titan_signal_quality.json")


class TitanSignalQuality:
    def __init__(self):
        self.condition_stats = {}
        self.asset_stats = {}
        self.combo_stats = {}
        self.recent_scores = []
        self.calibration_table = {}
        self.stats = {"total_evaluated": 0, "avg_quality": 0.5, "last_update": ""}
        self._last_ai_evaluation = None
        self._load()

    def _load(self):
        try:
            if os.path.exists(SQ_PATH):
                with open(SQ_PATH, "r") as f:
                    data = json.load(f)
                self.condition_stats = data.get("condition_stats", {})
                self.asset_stats = data.get("asset_stats", {})
                self.combo_stats = data.get("combo_stats", {})
                self.calibration_table = data.get("calibration_table", {})
                self.stats = data.get("stats", self.stats)
                logger.info(f"SignalQuality loaded: {len(self.condition_stats)} conditions tracked")
        except Exception as e:
            logger.warning(f"SignalQuality load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(SQ_PATH), exist_ok=True)
            data = {
                "condition_stats": self.condition_stats,
                "asset_stats": self.asset_stats,
                "combo_stats": dict(list(self.combo_stats.items())[-500:]),
                "calibration_table": self.calibration_table,
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(SQ_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"SignalQuality save failed: {e}")

    def record_outcome(self, signal_conditions, is_win, pnl_pct, symbol="", regime="unknown"):
        asset = symbol.replace("/USDT", "").replace("_USDT", "")

        for cond in signal_conditions:
            if cond not in self.condition_stats:
                self.condition_stats[cond] = {"wins": 0, "losses": 0, "total_pnl": 0, "count": 0}
            cs = self.condition_stats[cond]
            cs["count"] += 1
            cs["wins" if is_win else "losses"] += 1
            cs["total_pnl"] = round(cs["total_pnl"] + pnl_pct, 4)

        if asset:
            if asset not in self.asset_stats:
                self.asset_stats[asset] = {"wins": 0, "losses": 0, "total_pnl": 0, "count": 0}
            a = self.asset_stats[asset]
            a["count"] += 1
            a["wins" if is_win else "losses"] += 1
            a["total_pnl"] = round(a["total_pnl"] + pnl_pct, 4)

        if len(signal_conditions) >= 2:
            combo_key = "|".join(sorted(signal_conditions[:4]))
            if combo_key not in self.combo_stats:
                self.combo_stats[combo_key] = {"wins": 0, "losses": 0, "count": 0}
            cb = self.combo_stats[combo_key]
            cb["count"] += 1
            cb["wins" if is_win else "losses"] += 1

        self._update_calibration()
        self.stats["total_evaluated"] += 1
        self.stats["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()

    def _update_calibration(self):
        for cond, stats in self.condition_stats.items():
            if stats["count"] >= 3:
                wr = stats["wins"] / stats["count"]
                avg_pnl = stats["total_pnl"] / stats["count"]
                reliability = min(1.0, stats["count"] / 50)
                if stats["count"] < 10:
                    wr = wr * 0.6 + 0.5 * 0.4
                elif stats["count"] < 20:
                    wr = wr * 0.8 + 0.5 * 0.2
                self.calibration_table[cond] = {
                    "win_rate": round(wr, 3),
                    "avg_pnl": round(avg_pnl, 4),
                    "samples": stats["count"],
                    "reliability": reliability,
                }

    def evaluate_signal(self, signal_conditions, symbol="", regime="unknown", base_score=50):
        if not signal_conditions:
            return {"quality_score": base_score, "adjustments": [], "confidence": 0.5}

        adjustments = []
        total_adj = 0
        confidence_factors = []

        for cond in signal_conditions:
            if cond in self.calibration_table:
                cal = self.calibration_table[cond]
                wr = cal["win_rate"]
                reliability = cal["reliability"]

                if wr > 0.6 and cal["samples"] >= 10:
                    adj = min(12, (wr - 0.5) * 25 * reliability)
                    adjustments.append({"condition": cond, "adj": round(adj, 1), "reason": f"胜率{wr:.0%}"})
                    total_adj += adj
                elif wr < 0.35 and cal["samples"] >= 15:
                    adj = max(-10, (wr - 0.5) * 20 * reliability)
                    adjustments.append({"condition": cond, "adj": round(adj, 1), "reason": f"胜率{wr:.0%}"})
                    total_adj += adj

                confidence_factors.append(reliability)

        asset = symbol.replace("/USDT", "").replace("_USDT", "")
        if asset in self.asset_stats:
            a = self.asset_stats[asset]
            if a["count"] >= 5:
                asset_wr = a["wins"] / a["count"]
                if asset_wr > 0.6:
                    adj = 5
                    adjustments.append({"condition": f"asset:{asset}", "adj": adj, "reason": f"历史胜率{asset_wr:.0%}"})
                    total_adj += adj
                elif asset_wr < 0.3 and a["count"] >= 10:
                    adj = -5
                    adjustments.append({"condition": f"asset:{asset}", "adj": adj, "reason": f"历史胜率{asset_wr:.0%}"})
                    total_adj += adj

        if len(signal_conditions) >= 2:
            combo_key = "|".join(sorted(signal_conditions[:4]))
            if combo_key in self.combo_stats:
                cb = self.combo_stats[combo_key]
                if cb["count"] >= 5:
                    combo_wr = cb["wins"] / cb["count"]
                    if combo_wr > 0.65:
                        adj = 10
                        adjustments.append({"condition": "combo_bonus", "adj": adj, "reason": f"组合胜率{combo_wr:.0%}"})
                        total_adj += adj
                    elif combo_wr < 0.3:
                        adj = -10
                        adjustments.append({"condition": "combo_penalty", "adj": adj, "reason": f"组合胜率{combo_wr:.0%}"})
                        total_adj += adj

        final_score = max(0, min(100, base_score + total_adj))
        avg_confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.3

        return {
            "quality_score": round(final_score, 1),
            "adjustments": adjustments,
            "confidence": round(avg_confidence, 2),
            "conditions_evaluated": len(signal_conditions),
            "calibrated_conditions": len([c for c in signal_conditions if c in self.calibration_table]),
        }

    def extract_conditions(self, report, regime="unknown"):
        conditions = []
        if not report:
            return conditions

        adx = report.get("adx", 0)
        if adx > 30:
            conditions.append("adx_strong")
        elif adx > 20:
            conditions.append("adx_moderate")
        else:
            conditions.append("adx_weak")

        rsi = report.get("rsi", 50)
        if rsi > 70:
            conditions.append("rsi_overbought")
        elif rsi < 30:
            conditions.append("rsi_oversold")
        elif 45 <= rsi <= 55:
            conditions.append("rsi_neutral")

        macd_hist = report.get("macd_hist", 0)
        if macd_hist > 0:
            conditions.append("macd_bullish")
        else:
            conditions.append("macd_bearish")

        bb_pos = report.get("bb_position", 0.5)
        if bb_pos > 0.8:
            conditions.append("bb_upper")
        elif bb_pos < 0.2:
            conditions.append("bb_lower")
        else:
            conditions.append("bb_middle")

        vol = report.get("volume_ratio", 1.0)
        if vol > 2.0:
            conditions.append("vol_surge")
        elif vol > 1.3:
            conditions.append("vol_above_avg")
        elif vol < 0.5:
            conditions.append("vol_dried")

        if regime != "unknown":
            conditions.append(f"regime_{regime}")

        ema_trend = report.get("ema_trend", "")
        if ema_trend:
            conditions.append(f"ema_{ema_trend}")

        return conditions

    def get_hot_conditions(self, min_samples=5, top_n=10):
        hot = []
        cold = []
        for cond, cal in self.calibration_table.items():
            if cal["samples"] >= min_samples:
                entry = {"condition": cond, **cal}
                if cal["win_rate"] > 0.55:
                    hot.append(entry)
                elif cal["win_rate"] < 0.4:
                    cold.append(entry)

        hot.sort(key=lambda x: -x["win_rate"])
        cold.sort(key=lambda x: x["win_rate"])
        return {"hot": hot[:top_n], "cold": cold[:top_n]}

    def ai_evaluate_summary(self):
        try:
            from server.titan_llm_client import chat_json
            hot_cold = self.get_hot_conditions()
            top_assets = sorted(
                [(a, s) for a, s in self.asset_stats.items() if s["count"] >= 3],
                key=lambda x: -(x[1]["wins"] / x[1]["count"]),
            )[:10]
            prompt = (
                PHASE_ZERO_CONTEXT
                + f"你是交易信号质量分析专家。请分析以下信号质量数据并给出结构化评估。\n\n"
                f"条件统计(共{len(self.condition_stats)}个):\n"
                f"- 校准条件数: {len(self.calibration_table)}\n"
                f"- 总评估次数: {self.stats['total_evaluated']}\n\n"
                f"热门高胜率条件: {json.dumps(hot_cold['hot'][:5], ensure_ascii=False)}\n"
                f"冷门低胜率条件: {json.dumps(hot_cold['cold'][:5], ensure_ascii=False)}\n\n"
                f"资产表现TOP: {json.dumps([{'asset': a, 'wr': round(s['wins']/s['count']*100,1), 'trades': s['count']} for a,s in top_assets[:5]], ensure_ascii=False)}\n\n"
                f"请用JSON格式返回：\n"
                f'{{"summary": "一段总结", "weak_signals": ["弱信号1","弱信号2"], "strong_signals": ["强信号1","强信号2"], "recommendations": ["建议1","建议2","建议3"]}}'
            )
            result = chat_json(
                module="signal_quality",
                messages=[{"role": "system", "content": SIGNAL_QUALITY_PROMPT},
                          {"role": "user", "content": prompt}],
                max_tokens=16000,
            )
            if not result:
                raise Exception("AI返回空结果")
            result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._last_ai_evaluation = result
            return result
        except Exception as e:
            fallback = {"summary": f"AI评估失败: {str(e)[:50]}", "weak_signals": [], "strong_signals": [], "recommendations": [], "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            self._last_ai_evaluation = fallback
            return fallback

    def get_status(self):
        hot_cold = self.get_hot_conditions()
        top_assets = sorted(
            [(a, s) for a, s in self.asset_stats.items() if s["count"] >= 3],
            key=lambda x: -(x[1]["wins"] / x[1]["count"]),
        )[:10]

        status = {
            "total_conditions": len(self.condition_stats),
            "calibrated_conditions": len(self.calibration_table),
            "total_evaluated": self.stats["total_evaluated"],
            "avg_quality": self.stats["avg_quality"],
            "last_update": self.stats["last_update"],
            "hot_conditions": hot_cold["hot"][:5],
            "cold_conditions": hot_cold["cold"][:5],
            "top_assets": [
                {"asset": a, "win_rate": round(s["wins"]/s["count"]*100, 1), "trades": s["count"], "pnl": s["total_pnl"]}
                for a, s in top_assets[:5]
            ],
            "condition_count": len(self.calibration_table),
        }
        if self._last_ai_evaluation:
            status["ai_evaluation"] = self._last_ai_evaluation
        return status
