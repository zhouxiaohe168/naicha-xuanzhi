import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("TitanCounterfactual")


class TitanCounterfactualEngine:
    """反事实推理引擎 - 分析每笔交易的替代路径

    平仓后自动触发，分析4个反事实场景：
    1. 如果在峰值80%止盈
    2. 如果SL扩大50%
    3. 如果不进场
    4. 最佳交易时段分析
    """

    def analyze_after_close(self, trade: dict) -> Dict[str, Any]:
        """平仓后反事实分析

        Args:
            trade: 交易记录字典

        Returns:
            反事实分析结果
        """
        cf = {}

        entry = trade.get("entry_price", 0)
        exit_p = trade.get("exit_price", 0)
        sl = trade.get("sl_price", 0)
        tp = trade.get("tp_price", 0)
        peak = trade.get("peak_unrealized_pnl", 0)
        direction = trade.get("direction", "long")
        pnl_pct = trade.get("pnl_pct", 0)
        pnl_usd = trade.get("pnl_usd", 0)
        hold_h = trade.get("holding_hours", 0)

        cf["early_tp"] = self._analyze_early_tp(peak, pnl_pct)
        cf["wider_sl"] = self._analyze_wider_sl(entry, sl, exit_p, direction, pnl_pct)
        cf["no_trade"] = self._analyze_no_trade(pnl_usd, pnl_pct)
        cf["timing"] = self._analyze_timing(trade)

        primary_lessons = self._extract_lessons(cf)
        peak_giveback = 0
        if peak > 0 and pnl_pct < peak:
            peak_giveback = round((peak - pnl_pct) / max(peak, 0.01) * 100, 1)

        self._record(trade, cf, primary_lessons, peak_giveback)

        return {
            "early_tp": cf["early_tp"],
            "wider_sl": cf["wider_sl"],
            "no_trade": cf["no_trade"],
            "timing": cf["timing"],
            "primary_lessons": primary_lessons,
            "peak_giveback_pct": peak_giveback,
        }

    def _analyze_early_tp(self, peak: float, actual_pnl: float) -> dict:
        peak_exit_pnl = peak * 0.8 if peak > 0 else 0
        better = peak_exit_pnl > actual_pnl and peak > 0
        return {
            "peak_pnl": round(peak, 2),
            "early_exit_pnl": round(peak_exit_pnl, 2),
            "actual_pnl": round(actual_pnl, 2),
            "better": better,
            "lesson": "追踪止损触发太晚" if better else "追踪止损时机合适",
        }

    def _analyze_wider_sl(self, entry: float, sl: float, exit_p: float,
                          direction: str, pnl_pct: float) -> dict:
        if entry <= 0:
            return {"would_survive": False, "additional_risk": 0, "lesson": "数据不足"}

        sl_distance = abs(entry - sl) / entry
        wider_sl_distance = sl_distance * 1.5

        if direction == "long":
            wider_sl_price = entry * (1 - wider_sl_distance)
            would_survive = pnl_pct < 0 and exit_p > wider_sl_price
        else:
            wider_sl_price = entry * (1 + wider_sl_distance)
            would_survive = pnl_pct < 0 and exit_p < wider_sl_price

        return {
            "would_survive": would_survive,
            "sl_distance_pct": round(sl_distance * 100, 2),
            "wider_sl_distance_pct": round(wider_sl_distance * 100, 2),
            "additional_risk": round(sl_distance * 50, 2),
            "lesson": "SL过窄被噪音扫出" if would_survive else "SL距离合适",
        }

    def _analyze_no_trade(self, pnl_usd: float, pnl_pct: float) -> dict:
        return {
            "opportunity_cost": round(pnl_usd, 2),
            "was_correct_to_trade": pnl_pct > 0,
            "lesson": "正确进场" if pnl_pct > 0 else "应该跳过这个信号",
        }

    def _analyze_timing(self, trade: dict) -> dict:
        created_at = trade.get("created_at")
        if created_at and hasattr(created_at, "hour"):
            entry_hour = created_at.hour
        else:
            entry_hour = datetime.now(timezone.utc).hour

        session = self._get_session(entry_hour)
        return {
            "entry_session": session,
            "entry_hour_utc": entry_hour,
            "lesson": f"进场于{session}时段",
        }

    def _get_session(self, hour: int) -> str:
        if 0 <= hour < 8:
            return "亚洲"
        elif 8 <= hour < 13:
            return "欧洲"
        elif 13 <= hour < 17:
            return "欧美重叠"
        else:
            return "美洲"

    def _extract_lessons(self, cf: dict) -> list:
        lessons = []
        if cf["early_tp"].get("better"):
            lessons.append("trailing_sl_too_late")
        if cf["wider_sl"].get("would_survive"):
            lessons.append("sl_too_tight")
        if not cf["no_trade"].get("was_correct_to_trade"):
            lessons.append("signal_quality_poor")
        if not lessons:
            lessons.append("correct_decision")
        return lessons

    def _record(self, trade: dict, cf: dict, lessons: list, peak_giveback: float):
        try:
            from server.titan_db import db_connection
            import json
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO counterfactuals
                    (trade_id, early_tp_better, wider_sl_survives,
                     was_correct_to_trade, peak_giveback_pct,
                     primary_lessons, analysis_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    trade.get("id"),
                    cf["early_tp"].get("better", False),
                    cf["wider_sl"].get("would_survive", False),
                    cf["no_trade"].get("was_correct_to_trade", False),
                    peak_giveback,
                    lessons,
                    json.dumps(cf, ensure_ascii=False, default=str),
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"[Counterfactual] 记录失败: {e}")
