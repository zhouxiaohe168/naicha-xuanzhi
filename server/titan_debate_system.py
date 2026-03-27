import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any

logger = logging.getLogger("TitanDebateSystem")


class TitanDebateSystem:
    """多智能体辩论系统 v1 - 多头律师 vs 空头律师 vs 风险法官

    Shadow模式运行：在信号生成后运行辩论，结果写入debate_records表，
    不影响任何交易决策。Phase 1第3周激活辩论，Phase 2接入决策流。
    """

    def __init__(self):
        self.shadow_mode = True
        self._debate_count = 0
        self._verdict_accuracy = 0.0
        logger.info("[DebateSystem] 初始化完成 (Shadow模式)")

    def debate(self, symbol: str, signal: dict, market_context: dict) -> Dict[str, Any]:
        """对一个交易信号进行多方辩论

        Args:
            symbol: 交易对符号
            signal: 信号数据 (score, direction, ml, indicators等)
            market_context: 市场上下文 (fng, regime, btc_trend, history等)

        Returns:
            辩论结果字典，包含verdict/confidence/reasoning
        """
        bull_case = self._bull_argument(signal, market_context)
        bear_case = self._bear_argument(signal, market_context)
        risk_assessment = self._risk_judge(signal, market_context)
        history = self._get_symbol_history(symbol)

        verdict = self._render_verdict(bull_case, bear_case, risk_assessment, history)

        result = {
            "symbol": symbol,
            "signal_score": signal.get("score", 0),
            "bull_score": bull_case["score"],
            "bear_score": bear_case["score"],
            "risk_level": risk_assessment["level"],
            "historical_wr": history.get("win_rate", 0),
            "verdict": verdict["decision"],
            "verdict_reason": verdict["reason"],
            "confidence": verdict["confidence"],
            "size_multiplier": verdict.get("size_multiplier", 1.0),
        }

        self._debate_count += 1

        if self.shadow_mode:
            self._record_debate(result)

        return result

    def verify_verdict(self, debate_id: int, trade_result: str):
        """验证辩论结论是否正确

        Args:
            debate_id: debate_records表ID
            trade_result: 'win' / 'loss' / 'rejected'
        """
        try:
            from server.titan_db import db_connection
            was_correct = None
            if trade_result == "win":
                was_correct = True
            elif trade_result == "loss":
                was_correct = False

            if was_correct is not None:
                with db_connection() as (conn, cur):
                    cur.execute("""
                        UPDATE debate_records
                        SET verdict_correct = %s
                        WHERE id = %s
                    """, (was_correct, debate_id))
                    conn.commit()
        except Exception as e:
            logger.warning(f"[DebateSystem] 验证verdict失败: {e}")

    def _bull_argument(self, signal: dict, context: dict) -> Dict[str, Any]:
        """多头律师论证 (stub: Phase 2升级为LLM Agent)

        Returns:
            {"score": 0-100, "reasons": [...], "confidence": 0-1}
        """
        score = 50
        reasons = []

        sig_score = signal.get("score", 0)
        if sig_score >= 75:
            score += 15
            reasons.append(f"信号评分{sig_score}强势")
        elif sig_score >= 65:
            score += 5
            reasons.append(f"信号评分{sig_score}中等")

        ml = signal.get("ml", {})
        if ml.get("label") == "看涨" and ml.get("confidence", 0) > 60:
            score += 10
            reasons.append(f"ML看涨置信度{ml.get('confidence', 0):.0f}%")

        return {"score": min(100, max(0, score)), "reasons": reasons, "confidence": score / 100}

    def _bear_argument(self, signal: dict, context: dict) -> Dict[str, Any]:
        """空头律师论证 (stub: Phase 2升级为LLM Agent)

        Returns:
            {"score": 0-100, "reasons": [...], "confidence": 0-1}
        """
        score = 50
        reasons = []

        fng = context.get("fng", 50)
        if fng < 20:
            score += 10
            reasons.append(f"FNG={fng}极度恐慌")

        regime = context.get("regime", "")
        if "volatile" in str(regime).lower():
            score += 10
            reasons.append("高波动环境不利")

        btc_trend = context.get("btc_macro_trend", "")
        if "bearish" in str(btc_trend).lower():
            score += 15
            reasons.append("BTC宏观看跌")

        return {"score": min(100, max(0, score)), "reasons": reasons, "confidence": score / 100}

    def _risk_judge(self, signal: dict, context: dict) -> Dict[str, Any]:
        """风险法官评估

        Returns:
            {"level": "low"/"medium"/"high", "factors": [...]}
        """
        factors = []
        risk_score = 0

        fng = context.get("fng", 50)
        if fng < 15:
            risk_score += 2
            factors.append(f"FNG={fng}极度恐慌")
        elif fng < 25:
            risk_score += 1
            factors.append(f"FNG={fng}恐惧")

        regime = str(context.get("regime", "")).lower()
        if "volatile" in regime:
            risk_score += 2
            factors.append("高波动环境")

        btc_trend = str(context.get("btc_macro_trend", "")).lower()
        if "bearish" in btc_trend:
            risk_score += 2
            factors.append("BTC宏观看跌")

        sig_score = signal.get("score", 0)
        if sig_score < 60:
            risk_score += 1
            factors.append(f"信号评分{sig_score}偏低")

        if risk_score >= 4:
            level = "high"
        elif risk_score >= 2:
            level = "medium"
        else:
            level = "low"

        if not factors:
            factors.append("风险因素正常")

        return {"level": level, "factors": factors}

    def _get_symbol_history(self, symbol: str) -> dict:
        """获取该标的历史交易表现

        Returns:
            {"trades": N, "win_rate": float, "avg_pnl": float}
        """
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        COUNT(*) as trades,
                        AVG(CASE WHEN result='win' THEN 1.0 ELSE 0.0 END) as win_rate,
                        AVG(pnl_pct) as avg_pnl
                    FROM trades
                    WHERE symbol = %s
                """, (symbol,))
                row = cur.fetchone()
                if row and row["trades"]:
                    return {
                        "trades": row["trades"],
                        "win_rate": float(row["win_rate"] or 0),
                        "avg_pnl": float(row["avg_pnl"] or 0),
                    }
        except Exception:
            pass
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0}

    def _render_verdict(self, bull: dict, bear: dict, risk: dict, history: dict) -> Dict[str, Any]:
        """综合裁决 (stub: Phase 2升级为加权融合+LLM审议)

        Returns:
            {"decision": str, "reason": str, "confidence": float, "size_multiplier": float}
        """
        net_score = bull["score"] - bear["score"]

        if history.get("trades", 0) >= 3:
            if history["win_rate"] > 0.5:
                net_score += 10
            elif history["win_rate"] < 0.3:
                net_score -= 15

        risk_penalty = {"low": 0, "medium": -10, "high": -25}.get(risk["level"], 0)
        final_score = net_score + risk_penalty

        if final_score > 20:
            return {
                "decision": "execute",
                "reason": f"多头证据强: {bull['reasons'][:2]}",
                "confidence": min(0.95, final_score / 100),
                "size_multiplier": 1.0,
            }
        elif final_score > 5:
            return {
                "decision": "reduce_size",
                "reason": "信号中等，保守执行",
                "confidence": 0.6,
                "size_multiplier": 0.7,
            }
        else:
            return {
                "decision": "reject",
                "reason": f"空头证据更强: {bear['reasons'][:2]}",
                "confidence": 0.7,
                "size_multiplier": 0,
            }

    def _record_debate(self, result: dict):
        """写入debate_records表 (fire-and-forget)"""
        try:
            from server.titan_db import db_connection
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO debate_records
                    (symbol, signal_score, bull_score, bear_score,
                     risk_level, historical_wr, verdict, verdict_reason, confidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    result["symbol"],
                    result["signal_score"],
                    result["bull_score"],
                    result["bear_score"],
                    result["risk_level"],
                    result["historical_wr"],
                    result["verdict"],
                    result["verdict_reason"],
                    result["confidence"],
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"[DebateSystem] 记录辩论失败: {e}")

    def get_debate_accuracy(self, days: int = 7) -> Dict[str, float]:
        """获取辩论准确率统计

        Args:
            days: 回溯天数

        Returns:
            各agent的准确率
        """
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN verdict_correct = TRUE THEN 1 ELSE 0 END) as correct,
                        AVG(bull_score) as avg_bull,
                        AVG(bear_score) as avg_bear
                    FROM debate_records
                    WHERE created_at >= NOW() - INTERVAL '%s days'
                      AND verdict_correct IS NOT NULL
                """, (days,))
                row = cur.fetchone()
                if row and row["total"]:
                    return {
                        "total": row["total"],
                        "accuracy": float(row["correct"] or 0) / max(row["total"], 1),
                        "avg_bull_score": float(row["avg_bull"] or 0),
                        "avg_bear_score": float(row["avg_bear"] or 0),
                    }
        except Exception as e:
            logger.warning(f"[DebateSystem] 查询准确率失败: {e}")
        return {"total": 0, "accuracy": 0, "avg_bull_score": 0, "avg_bear_score": 0}

    def get_status(self) -> dict:
        """返回模块状态摘要"""
        return {
            "module": "DebateSystem",
            "shadow_mode": self.shadow_mode,
            "debate_count": self._debate_count,
            "status": "shadow" if self.shadow_mode else "active",
        }
