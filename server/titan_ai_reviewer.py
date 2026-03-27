import os
import json
import time
import logging
from datetime import datetime
from server.titan_prompt_library import AI_REVIEWER_PROMPT, AI_REVIEWER_PRE_REVIEW_PROMPT, PHASE_ZERO_CONTEXT

logger = logging.getLogger("TitanAIReviewer")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW_PATH = os.path.join(BASE_DIR, "data", "titan_ai_reviews.json")

# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
REVIEW_MODEL = "gpt-4o-mini"
REVIEW_COOLDOWN = 60


class TitanAIReviewer:
    def __init__(self):
        self.reviews = []
        self.validated_patterns = []
        self.pending_trades = []
        self.stats = {
            "total_reviews": 0,
            "total_insights": 0,
            "validated_patterns": 0,
            "last_review": "",
            "last_batch_review": "",
        }
        self._last_review_time = 0
        self._load()

    def _load(self):
        try:
            if os.path.exists(REVIEW_PATH):
                with open(REVIEW_PATH, "r") as f:
                    data = json.load(f)
                self.reviews = data.get("reviews", [])
                self.validated_patterns = data.get("validated_patterns", [])
                self.stats = data.get("stats", self.stats)
                logger.info(f"AIReviewer loaded: {len(self.reviews)} reviews, {len(self.validated_patterns)} patterns")
        except Exception as e:
            logger.warning(f"AIReviewer load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(REVIEW_PATH), exist_ok=True)
            data = {
                "reviews": self.reviews[-200:],
                "validated_patterns": self.validated_patterns[-100:],
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(REVIEW_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"AIReviewer save failed: {e}")

    def queue_trade_for_review(self, trade_data):
        self.pending_trades.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **trade_data,
        })
        if len(self.pending_trades) >= 3:
            return self._should_batch_review()
        return False

    def _should_batch_review(self):
        if time.time() - self._last_review_time < REVIEW_COOLDOWN:
            return False
        return len(self.pending_trades) >= 3

    def review_single_trade(self, trade_data, synapse_context=None, signal_quality_context=None):
        now = time.time()
        if now - self._last_review_time < REVIEW_COOLDOWN:
            logger.info("AIReviewer: cooldown active, skipping")
            return None

        try:
            from server.titan_llm_client import chat_json

            prompt = self._build_single_review_prompt(trade_data, synapse_context, signal_quality_context)

            review = chat_json(
                module="ai_reviewer",
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )

            if not review:
                return self._rule_based_review(trade_data)

            review_entry = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "single_trade",
                "trade": {
                    "symbol": trade_data.get("symbol", ""),
                    "direction": trade_data.get("direction", ""),
                    "strategy": trade_data.get("strategy_type", ""),
                    "pnl_pct": trade_data.get("pnl_pct", 0),
                    "regime": trade_data.get("market_regime", ""),
                },
                "ai_analysis": review,
                "source": "llm",
            }

            self.reviews.append(review_entry)
            self.stats["total_reviews"] += 1
            self.stats["total_insights"] += len(review.get("insights", []))
            self.stats["last_review"] = review_entry["time"]
            self._last_review_time = now

            self._extract_and_validate_patterns(review)
            self.save()

            logger.info(f"AIReviewer: trade review complete - {trade_data.get('symbol','')} {trade_data.get('pnl_pct',0):+.1f}%")
            return review_entry

        except Exception as e:
            logger.warning(f"AIReviewer LLM review failed: {e}")
            return self._rule_based_review(trade_data)

    def _should_force_ai_review(self, trades):
        if not trades:
            return False
        losses = [t for t in trades if t.get("pnl_pct", 0) < 0]
        wins = [t for t in trades if t.get("pnl_pct", 0) > 0]
        total = len(trades)
        win_rate = len(wins) / total * 100 if total > 0 else 100

        if win_rate < 35:
            logger.info(f"AIReviewer: force AI path - win_rate={win_rate:.0f}%<35%")
            return True

        consecutive_losses = 0
        for t in reversed(trades):
            if t.get("pnl_pct", 0) < 0:
                consecutive_losses += 1
            else:
                break
        if consecutive_losses >= 3:
            logger.info(f"AIReviewer: force AI path - {consecutive_losses} consecutive losses")
            return True

        big_loss = any(abs(t.get("pnl_pct", 0)) > 5 or abs(t.get("pnl_value", t.get("pnl_usd", 0)) or 0) > 50 for t in losses)
        if big_loss:
            logger.info("AIReviewer: force AI path - big loss detected")
            return True

        return False

    def batch_review(self, trades=None, synapse_status=None, risk_budget_status=None, dispatcher_status=None):
        if trades is None:
            trades = self.pending_trades
        if not trades:
            return None

        now = time.time()
        if now - self._last_review_time < REVIEW_COOLDOWN:
            logger.info("AIReviewer: cooldown active for batch review")
            return None

        force_ai = self._should_force_ai_review(trades)

        try:
            from server.titan_llm_client import chat_json

            prompt = self._build_batch_review_prompt(trades, synapse_status, risk_budget_status, dispatcher_status)

            review = chat_json(
                module="ai_reviewer",
                messages=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )

            if not review and force_ai:
                logger.info("AIReviewer: first LLM attempt empty, retrying for forced AI review")
                review = chat_json(
                    module="ai_reviewer",
                    messages=[
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user", "content": prompt + "\n\n[重要] 当前交易表现需要深度AI分析，请务必给出详细复盘。"},
                    ],
                    max_tokens=16000,
                )

            if not review:
                return self._rule_based_batch_review(trades)

            review_entry = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "type": "batch_review",
                "trade_count": len(trades),
                "trades_summary": [
                    {"symbol": t.get("symbol", ""), "pnl_pct": t.get("pnl_pct", 0), "strategy": t.get("strategy_type", "")}
                    for t in trades[:10]
                ],
                "ai_analysis": review,
                "source": "llm",
                "forced_ai": force_ai,
            }

            self.reviews.append(review_entry)
            self.stats["total_reviews"] += 1
            self.stats["total_insights"] += len(review.get("insights", []))
            self.stats["last_batch_review"] = review_entry["time"]
            self._last_review_time = now

            self._extract_and_validate_patterns(review)
            self.pending_trades = []
            self.save()

            logger.info(f"AIReviewer: batch review of {len(trades)} trades complete (forced_ai={force_ai})")
            return review_entry

        except Exception as e:
            logger.warning(f"AIReviewer batch review failed: {e}")
            return self._rule_based_batch_review(trades)

    def _system_prompt(self):
        return AI_REVIEWER_PROMPT

    def _build_single_review_prompt(self, trade, synapse_ctx=None, sq_ctx=None):
        parts = [PHASE_ZERO_CONTEXT, f"""## 单笔交易复盘

**交易信息:**
- 资产: {trade.get('symbol', 'N/A')}
- 方向: {trade.get('direction', 'N/A')}
- 策略: {trade.get('strategy_type', 'N/A')}
- 盈亏: {trade.get('pnl_pct', 0):+.2f}%
- 持仓时间: {trade.get('holding_hours', 0):.1f}小时
- 市场环境: {trade.get('market_regime', 'N/A')}
- 信号评分: {trade.get('signal_score', 0)}
- 入场价: {trade.get('entry_price', 'N/A')}
- 出场价: {trade.get('exit_price', 'N/A')}
- 出场原因: {trade.get('close_reason', 'N/A')}"""]

        if synapse_ctx:
            parts.append(f"\n**协同学习上下文:**\n{json.dumps(synapse_ctx, ensure_ascii=False, indent=2)[:500]}")
        if sq_ctx:
            parts.append(f"\n**信号质量上下文:**\n{json.dumps(sq_ctx, ensure_ascii=False, indent=2)[:500]}")

        parts.append("\n请分析这笔交易的质量，找出可改进之处。")
        return "\n".join(parts)

    def _build_batch_review_prompt(self, trades, synapse_status=None, rb_status=None, disp_status=None):
        wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        losses = len(trades) - wins
        total_pnl = sum(t.get("pnl_pct", 0) for t in trades)
        avg_pnl = total_pnl / len(trades) if trades else 0

        by_strategy = {}
        for t in trades:
            s = t.get("strategy_type", "unknown")
            if s not in by_strategy:
                by_strategy[s] = {"wins": 0, "losses": 0, "pnl": 0}
            by_strategy[s]["wins" if t.get("pnl_pct", 0) > 0 else "losses"] += 1
            by_strategy[s]["pnl"] += t.get("pnl_pct", 0)

        parts = [PHASE_ZERO_CONTEXT, f"""## 批量交易复盘 ({len(trades)}笔)

**总体表现:**
- 胜/负: {wins}/{losses} (胜率{wins/len(trades)*100:.0f}%)
- 总PnL: {total_pnl:+.2f}%
- 平均PnL: {avg_pnl:+.2f}%

**按策略统计:**"""]

        for s, stats in by_strategy.items():
            total = stats["wins"] + stats["losses"]
            wr = stats["wins"] / total * 100 if total > 0 else 0
            parts.append(f"- {s}: {total}笔, 胜率{wr:.0f}%, PnL={stats['pnl']:+.2f}%")

        parts.append("\n**交易明细:**")
        for t in trades[:10]:
            emoji = "✅" if t.get("pnl_pct", 0) > 0 else "❌"
            parts.append(f"- {emoji} {t.get('symbol','?')} {t.get('direction','?')} [{t.get('strategy_type','?')}] {t.get('pnl_pct',0):+.2f}% ({t.get('market_regime','?')})")

        if synapse_status:
            parts.append(f"\n**Synapse状态:** {json.dumps(synapse_status, ensure_ascii=False)[:300]}")
        if rb_status:
            parts.append(f"\n**风险预算:** capital=${rb_status.get('total_capital',0):,.0f}, dd={rb_status.get('total_drawdown_pct',0):.2f}%")
        if disp_status:
            parts.append(f"\n**调度器:** regime={disp_status.get('current_regime','?')}, alloc={disp_status.get('allocation',{})}")

        parts.append("\n请进行全面复盘分析，找出系统性问题和改进方向。")
        return "\n".join(parts)

    def _extract_and_validate_patterns(self, review):
        patterns = review.get("patterns_found", [])
        for p in patterns:
            if p.get("confidence", 0) >= 0.7 and p.get("actionable", False):
                existing = [vp for vp in self.validated_patterns if vp.get("pattern") == p.get("pattern")]
                if existing:
                    existing[0]["occurrences"] = existing[0].get("occurrences", 1) + 1
                    existing[0]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if existing[0]["occurrences"] >= 3:
                        existing[0]["status"] = "validated"
                else:
                    self.validated_patterns.append({
                        **p,
                        "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "occurrences": 1,
                        "status": "pending_validation",
                    })
                    self.stats["validated_patterns"] = len([vp for vp in self.validated_patterns if vp.get("status") == "validated"])

    def _rule_based_review(self, trade):
        pnl = trade.get("pnl_pct", 0)
        holding = trade.get("holding_hours", 0)
        strategy = trade.get("strategy_type", "unknown")
        regime = trade.get("market_regime", "unknown")

        insights = []
        risk_warnings = []

        if pnl < -3:
            insights.append(f"大额亏损{pnl:.1f}%，需检查止损设置")
            risk_warnings.append("单笔亏损超过3%，建议收紧止损")
        elif pnl > 5:
            insights.append(f"优秀交易{pnl:.1f}%，记录成功模式")

        if holding < 0.5:
            insights.append("持仓时间不足30分钟，可能是过早止损")
        elif holding > 48:
            insights.append("持仓超过48小时，注意时间衰减风险")

        if strategy == "trend" and regime == "ranging":
            insights.append("趋势策略在震荡市使用，策略环境不匹配")
        elif strategy == "range" and regime == "trending":
            insights.append("区间策略在趋势市使用，策略环境不匹配")

        verdict = "良好" if pnl > 0 else "需改进"
        score = min(100, max(0, 50 + pnl * 10))

        review_entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "single_trade",
            "trade": {
                "symbol": trade.get("symbol", ""),
                "pnl_pct": pnl,
                "strategy": strategy,
            },
            "ai_analysis": {
                "verdict": verdict,
                "score": round(score),
                "insights": insights,
                "patterns_found": [],
                "risk_warnings": risk_warnings,
                "parameter_suggestions": [],
                "strategy_feedback": {},
                "next_actions": [],
            },
            "source": "rule_based",
        }

        self.reviews.append(review_entry)
        self.stats["total_reviews"] += 1
        self.stats["total_insights"] += len(insights)
        self.stats["last_review"] = review_entry["time"]
        self.save()
        return review_entry

    def _rule_based_batch_review(self, trades):
        wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
        total_pnl = sum(t.get("pnl_pct", 0) for t in trades)
        wr = wins / len(trades) * 100 if trades else 0

        insights = []
        if wr < 40:
            insights.append(f"胜率{wr:.0f}%偏低，需检查信号质量阈值")
        elif wr > 65:
            insights.append(f"胜率{wr:.0f}%优秀，当前策略配置有效")

        if total_pnl < 0:
            insights.append(f"总PnL为负({total_pnl:+.2f}%)，亏损交易的幅度过大")
        else:
            insights.append(f"总PnL为正({total_pnl:+.2f}%)，盈亏比健康")

        review_entry = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "batch_review",
            "trade_count": len(trades),
            "ai_analysis": {
                "verdict": "良好" if total_pnl > 0 else "需改进",
                "score": round(min(100, max(0, 50 + total_pnl * 5))),
                "insights": insights,
                "patterns_found": [],
                "risk_warnings": [],
                "parameter_suggestions": [],
                "strategy_feedback": {},
                "next_actions": ["继续积累交易数据", "等待更多样本以发现模式"],
            },
            "source": "rule_based",
        }

        self.reviews.append(review_entry)
        self.stats["total_reviews"] += 1
        self.stats["last_batch_review"] = review_entry["time"]
        self.pending_trades = []
        self.save()
        return review_entry

    def get_actionable_insights(self):
        if not self.reviews:
            return []
        recent = self.reviews[-5:]
        all_insights = []
        for r in recent:
            analysis = r.get("ai_analysis", {})
            for insight in analysis.get("insights", []):
                all_insights.append({
                    "time": r.get("time", ""),
                    "insight": insight,
                    "source": r.get("source", ""),
                    "type": r.get("type", ""),
                })
        return all_insights

    def get_status(self):
        recent_reviews = self.reviews[-5:]
        avg_score = 0
        if recent_reviews:
            scores = [r.get("ai_analysis", {}).get("score", 0) for r in recent_reviews]
            avg_score = sum(scores) / len(scores)

        return {
            "total_reviews": self.stats["total_reviews"],
            "total_insights": self.stats["total_insights"],
            "validated_patterns": len([p for p in self.validated_patterns if p.get("status") == "validated"]),
            "pending_patterns": len([p for p in self.validated_patterns if p.get("status") == "pending_validation"]),
            "last_review": self.stats["last_review"],
            "last_batch_review": self.stats["last_batch_review"],
            "avg_score": round(avg_score, 1),
            "pending_trades": len(self.pending_trades),
            "recent_reviews": [
                {
                    "time": r.get("time", ""),
                    "type": r.get("type", ""),
                    "verdict": r.get("ai_analysis", {}).get("verdict", ""),
                    "score": r.get("ai_analysis", {}).get("score", 0),
                    "insights_count": len(r.get("ai_analysis", {}).get("insights", [])),
                    "source": r.get("source", ""),
                }
                for r in recent_reviews
            ],
            "validated_patterns_list": [
                {
                    "pattern": p.get("pattern", ""),
                    "confidence": p.get("confidence", 0),
                    "occurrences": p.get("occurrences", 0),
                    "status": p.get("status", ""),
                    "suggestion": p.get("suggestion", ""),
                }
                for p in self.validated_patterns[-10:]
            ],
            "actionable_insights": self.get_actionable_insights()[-10:],
        }


    def proactive_weekly_review(self, paper_trader=None, extra_count=3):
        try:
            if not paper_trader:
                from server.api import paper_trader as pt
                paper_trader = pt
            trades = getattr(paper_trader, "trade_history", [])
            if not trades:
                return None

            reviewed_syms = set()
            for r in self.reviews[-20:]:
                for t in r.get("trades_summary", []):
                    reviewed_syms.add(f"{t.get('symbol','')}_{t.get('pnl_pct',0):.2f}")

            unreviewed = []
            for t in reversed(trades):
                key = f"{t.get('symbol','')}_{t.get('pnl_pct',0):.2f}"
                if key not in reviewed_syms:
                    unreviewed.append(t)
                if len(unreviewed) >= extra_count:
                    break

            if not unreviewed:
                unreviewed = trades[-extra_count:]

            result = self.batch_review(trades=unreviewed)
            if result:
                result["type"] = "proactive_weekly_review"
                result["proactive"] = True
                logger.info(f"AIReviewer: 主动周复盘完成, 回顾{len(unreviewed)}笔交易")
            return result
        except Exception as e:
            logger.warning(f"AIReviewer proactive review failed: {e}")
            return None

    def pre_trade_assessment(self, signal_data, market_context=None):
        score = signal_data.get("score", 0)
        direction = signal_data.get("direction", "long")
        ml_label = signal_data.get("ml_label", "")
        ml_conf = signal_data.get("ml_confidence", 0)
        rsi = signal_data.get("rsi", 50)
        adx = signal_data.get("adx", 20)
        regime = signal_data.get("regime_type", "")
        fng = signal_data.get("fng", 50)
        symbol = signal_data.get("symbol", "")
        atr_ratio = signal_data.get("atr_ratio", 0.02)

        approve = True
        reasons = []
        risk_flags = 0

        if direction == "long":
            if ml_label in ("看跌", "bearish", "down") and ml_conf >= 50:
                risk_flags += 2
                reasons.append(f"ML看跌({ml_conf:.0f}%)与做多方向冲突")
            if ml_label in ("横盘", "neutral", "sideways") and ml_conf >= 60:
                risk_flags += 1
                reasons.append(f"ML横盘({ml_conf:.0f}%)不支持做多")
            if ml_conf < 40 and score < 82:
                risk_flags += 1
                reasons.append(f"ML置信度过低({ml_conf:.0f}%)且评分不够高")
            if rsi > 75:
                risk_flags += 1
                reasons.append(f"RSI={rsi:.0f}超买区域")
            if regime in ("窄幅震荡",) and adx < 15:
                risk_flags += 1
                reasons.append(f"极弱趋势ADX={adx:.0f}")
            if fng >= 85:
                risk_flags += 1
                reasons.append(f"FNG={fng}极度贪婪")
            if adx < 12 and score < 80:
                risk_flags += 1
                reasons.append(f"ADX={adx:.0f}极低无趋势")
        elif direction == "grid":
            if adx > 30:
                risk_flags += 1
                reasons.append(f"ADX={adx:.0f}趋势过强,不适合网格")
            if atr_ratio > 0.06:
                risk_flags += 1
                reasons.append(f"波动率ATR%={atr_ratio*100:.1f}%过高,网格风险大")
            if fng >= 90 or fng <= 10:
                risk_flags += 1
                reasons.append(f"FNG={fng}情绪极端,不宜开网格")
        else:
            if ml_label in ("看涨", "bullish", "up") and ml_conf >= 55:
                risk_flags += 2
                reasons.append(f"ML看涨({ml_conf:.0f}%)与做空方向冲突")
            if rsi < 22:
                risk_flags += 1
                reasons.append(f"RSI={rsi:.0f}超卖严重")
            if fng <= 15:
                risk_flags += 1
                reasons.append(f"FNG={fng}极度恐慌")

        if atr_ratio > 0.08:
            risk_flags += 1
            reasons.append(f"波动率过高ATR%={atr_ratio*100:.1f}%")

        if regime in ("极端波动",):
            risk_flags += 2
            reasons.append("极端波动环境")

        if score < 75 and ml_conf < 50:
            risk_flags += 1
            reasons.append(f"信号弱(score={score},ML={ml_conf:.0f}%)")

        threshold = 2

        if risk_flags >= threshold:
            approve = False

        ai_actually_called = False
        if 72 <= score <= 78 and risk_flags >= 1 and approve:
            ai_actually_called = True
            try:
                from server.titan_llm_client import chat_json
                dir_cn = "做多" if direction == "long" else "做空"
                prompt = f"""快速研判：{symbol} {dir_cn}信号
评分:{score} ML:{ml_label}({ml_conf:.0f}%) RSI:{rsi:.0f} ADX:{adx:.0f} 环境:{regime} FNG:{fng}
风险标记:{risk_flags} 原因:{'; '.join(reasons) if reasons else '无'}
回复JSON: {{"approve": true/false, "reason": "简短理由(20字内)"}}"""
                ai_result = chat_json(
                    module="ai_reviewer",
                    messages=[
                        {"role": "system", "content": AI_REVIEWER_PRE_REVIEW_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=16000,
                )
                if not ai_result:
                    raise Exception("AI返回空结果")
                ai_approve = ai_result.get("approve", True)
                ai_reason = ai_result.get("reason", "")
                if not ai_approve:
                    approve = False
                    reasons.append(f"AI研判拒绝: {ai_reason}")
                else:
                    reasons.append(f"AI研判通过: {ai_reason}")
                logger.info(f"AI预审 {symbol} {dir_cn}: approve={ai_approve} reason={ai_reason}")
            except Exception as e:
                logger.warning(f"AI预审调用失败: {e}")
                ai_actually_called = False

        verdict = "通过" if approve else "拒绝"
        return {
            "approve": approve,
            "verdict": verdict,
            "risk_flags": risk_flags,
            "reasons": reasons,
            "ai_used": ai_actually_called,
        }


ai_reviewer = TitanAIReviewer()
