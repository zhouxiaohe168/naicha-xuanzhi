import os
import json
import logging
import time
from datetime import datetime, date
from server.titan_prompt_library import TRADE_JUDGE_PROMPT

logger = logging.getLogger("TitanTradeJudge")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADES_PATH = os.path.join(BASE_DIR, "data", "titan_trades.json")
JUDGE_STATE_PATH = os.path.join(BASE_DIR, "data", "titan_trade_judge.json")


class TitanTradeJudge:

    def __init__(self):
        self.verdicts = []
        self.stats = {
            "total_judged": 0,
            "approved": 0,
            "reduced": 0,
            "rejected": 0,
            "ai_calls": 0,
            "rule_only": 0,
            "last_judge": "",
        }
        self.symbol_history = {}
        self.rejected_symbols = []
        self._build_symbol_history()
        self._load()

    def _load(self):
        try:
            if os.path.exists(JUDGE_STATE_PATH):
                with open(JUDGE_STATE_PATH, "r") as f:
                    data = json.load(f)
                self.stats = data.get("stats", self.stats)
                self.verdicts = data.get("verdicts", [])[-50:]
                self.rejected_symbols = data.get("rejected_symbols", [])
        except Exception as e:
            logger.warning(f"TradeJudge load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(JUDGE_STATE_PATH), exist_ok=True)
            data = {
                "stats": self.stats,
                "verdicts": self.verdicts[-50:],
                "rejected_symbols": self.rejected_symbols[-20:],
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(JUDGE_STATE_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_symbol_history(self):
        try:
            if os.path.exists(TRADES_PATH):
                with open(TRADES_PATH, "r") as f:
                    trades = json.load(f)
                for t in trades:
                    sym = t.get("symbol", "")
                    if not sym:
                        continue
                    if sym not in self.symbol_history:
                        self.symbol_history[sym] = {
                            "wins": 0, "losses": 0, "total_pnl": 0.0,
                            "avg_hold_hours": 0, "trades": 0,
                        }
                    h = self.symbol_history[sym]
                    h["trades"] += 1
                    if t.get("result") == "win":
                        h["wins"] += 1
                    else:
                        h["losses"] += 1
                    h["total_pnl"] += t.get("pnl_pct", 0)
                    hold = t.get("hold_hours", 0)
                    h["avg_hold_hours"] = (h["avg_hold_hours"] * (h["trades"] - 1) + hold) / h["trades"]
        except Exception as e:
            logger.warning(f"TradeJudge build history failed: {e}")

    def refresh_history(self):
        self.symbol_history = {}
        self._build_symbol_history()

    def judge(self, context, mc_state, position_amount, equity, cto_directives=None):
        symbol = context.get("symbol", "UNKNOWN")
        signal_score = context.get("signal_score", 0)
        ml_confidence = context.get("ml_confidence", 0)
        regime = context.get("regime", "unknown")
        strategy = context.get("strategy", "trend")
        drawdown_pct = context.get("drawdown_pct", 0)
        coin_tier = context.get("coin_tier", 2)
        consecutive_losses = context.get("consecutive_losses", 0)
        direction = context.get("direction", "long")

        position_pct = position_amount / max(equity, 1) * 100
        daily_pnl_used = mc_state.get("daily_pnl_used_pct", 0)
        daily_limit = mc_state.get("daily_loss_limit", 0.02) * 100
        exposure_pct = mc_state.get("current_exposure_pct", 0)
        exposure_cap = mc_state.get("exposure_cap_pct", 90)

        score = 100
        reasons = []
        adjustments = []

        sym_clean = symbol.replace("/USDT", "").replace("/USDT:USDT", "")
        hist = self.symbol_history.get(sym_clean, None)

        if cto_directives:
            bl = cto_directives.get("asset_blacklist", [])
            if sym_clean in bl or symbol in bl:
                self.stats["total_judged"] += 1
                self.stats["rejected"] = self.stats.get("rejected", 0) + 1
                self.stats["last_judge"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                verdict_record = {
                    "time": self.stats["last_judge"],
                    "symbol": sym_clean,
                    "verdict": "reject",
                    "score": 0,
                    "multiplier": 0.0,
                    "position_pct": round(position_pct, 2),
                    "reasons": [f"CTO黑名单: {sym_clean}在CTO战略禁止清单中"],
                    "ai_used": False,
                    "direction": direction,
                }
                self.verdicts.append(verdict_record)
                if len(self.verdicts) > 50:
                    self.verdicts = self.verdicts[-50:]
                logger.info(f"[TradeJudge] {sym_clean} → REJECT (CTO黑名单)")
                return {"verdict": "reject", "score": 0, "multiplier": 0.0,
                        "reasons": [f"CTO黑名单: {sym_clean}在战略禁止清单中"], "ai_used": False}

            open_pos = context.get("open_positions", 0)
            max_pos = cto_directives.get("max_concurrent_positions", 10)
            if open_pos >= max_pos:
                score -= 30
                reasons.append(f"CTO指令: 持仓{open_pos}已达上限{max_pos}")
                adjustments.append(0.3)

            aggr = cto_directives.get("aggression_mode", "moderate")
            if aggr == "conservative":
                score -= 10
                adjustments.append(0.8)
                reasons.append("CTO指令: 防守模式,收紧入场")
            elif aggr == "aggressive":
                score += 5
                adjustments.append(1.1)
                reasons.append("CTO指令: 进攻模式,适度放宽")

            strat_pref = cto_directives.get("strategy_preference", "balanced")
            strat_aliases = {
                "trend": ["trend", "trend_following"],
                "range": ["range", "range_harvester"],
                "grid": ["grid"],
            }
            pref_group = strat_aliases.get(strat_pref, [strat_pref])
            strat_match = strategy in pref_group or strat_pref == strategy
            if strat_pref != "balanced" and not strat_match:
                score -= 5
                reasons.append(f"CTO偏好{strat_pref}策略,当前{strategy}非首选")
                adjustments.append(0.9)
            elif strat_match and strat_pref != "balanced":
                score += 5
                reasons.append(f"CTO偏好{strat_pref}策略,当前匹配")

            min_score = cto_directives.get("min_signal_score", 73)
            if signal_score < min_score:
                score -= 15
                reasons.append(f"CTO指令: 信号{signal_score}<最低要求{min_score}")
                adjustments.append(0.6)

            wl = cto_directives.get("asset_whitelist", [])
            if sym_clean in wl or symbol in wl:
                score += 10
                reasons.append(f"CTO白名单: {sym_clean}在优先交易清单中")
                adjustments.append(1.15)

        if hist and hist["trades"] >= 3:
            wr = hist["wins"] / hist["trades"]
            if wr == 0:
                score -= 40
                reasons.append(f"{sym_clean}历史{hist['trades']}笔全亏,高危")
                adjustments.append(0.3)
            elif wr < 0.25:
                score -= 25
                reasons.append(f"{sym_clean}历史胜率{wr*100:.0f}%极低")
                adjustments.append(0.5)
            elif wr < 0.35:
                score -= 10
                reasons.append(f"{sym_clean}历史胜率{wr*100:.0f}%偏低")
                adjustments.append(0.75)
            elif wr >= 0.6:
                score += 10
                reasons.append(f"{sym_clean}历史胜率{wr*100:.0f}%优秀")
                adjustments.append(1.15)

            if hist["total_pnl"] < -5:
                score -= 15
                reasons.append(f"{sym_clean}累计亏损{hist['total_pnl']:.1f}%")
                adjustments.append(0.7)

        if daily_limit > 0 and daily_pnl_used > 0:
            usage_ratio = daily_pnl_used / daily_limit
            if usage_ratio > 0.8:
                score -= 30
                reasons.append(f"日亏损已用{usage_ratio*100:.0f}%,接近熔断")
                adjustments.append(0.4)
            elif usage_ratio > 0.5:
                score -= 15
                reasons.append(f"日亏损已用{usage_ratio*100:.0f}%")
                adjustments.append(0.7)

        if exposure_cap > 0:
            exp_usage = exposure_pct / exposure_cap
            if exp_usage > 0.85:
                score -= 20
                reasons.append(f"总暴露{exposure_pct:.0f}%接近上限{exposure_cap:.0f}%")
                adjustments.append(0.6)
            elif exp_usage > 0.7:
                score -= 10
                reasons.append(f"总暴露{exposure_pct:.0f}%较高")
                adjustments.append(0.8)

        if consecutive_losses >= 3:
            score -= 20
            reasons.append(f"连亏{consecutive_losses}笔,审慎")
            adjustments.append(0.6)

        if coin_tier == 3 and position_pct > 5:
            score -= 15
            reasons.append(f"低级别币种仓位{position_pct:.1f}%过大")
            adjustments.append(0.6)

        if signal_score < 70 and ml_confidence < 50:
            score -= 20
            reasons.append(f"信号{signal_score}分+ML{ml_confidence}%均弱")
            adjustments.append(0.6)
        elif signal_score >= 90 and ml_confidence >= 70:
            score += 15
            reasons.append("信号+ML双强确认")
            adjustments.append(1.1)

        if regime == "volatile" and strategy == "trend":
            score -= 10
            reasons.append("高波动环境趋势策略风险升高")
            adjustments.append(0.8)
        elif regime == "trending" and strategy == "trend":
            score += 5
            reasons.append("趋势环境+趋势策略匹配")

        if drawdown_pct > 5:
            score -= 15
            reasons.append(f"回撤{drawdown_pct:.1f}%较深,保守为上")
            adjustments.append(0.6)

        score = max(0, min(100, score))

        final_mult = 1.0
        for adj in adjustments:
            final_mult *= adj
        final_mult = max(0.1, min(1.5, final_mult))

        if score >= 75:
            verdict = "approve"
        elif score >= 45:
            verdict = "reduce"
            final_mult = min(final_mult, 0.7)
        else:
            verdict = "reject"
            final_mult = 0.0

        use_ai = (
            position_pct >= 5.0 and
            score >= 30 and score <= 80 and
            self.stats["ai_calls"] < 50
        )

        ai_verdict = None
        ai_reasoning = None

        if use_ai:
            ai_result = self._ai_deep_judge(context, mc_state, score, reasons, position_pct)
            if ai_result:
                ai_verdict = ai_result.get("verdict", verdict)
                ai_reasoning = ai_result.get("reasoning", "")
                ai_mult = ai_result.get("size_multiplier", 1.0)

                if ai_verdict == "reject":
                    verdict = "reject"
                    final_mult = 0.0
                    reasons.append(f"AI审判: 否决 - {ai_reasoning[:60]}")
                elif ai_verdict == "reduce":
                    if verdict == "approve":
                        verdict = "reduce"
                    final_mult = min(final_mult, ai_mult)
                    reasons.append(f"AI审判: 减仓至{ai_mult*100:.0f}% - {ai_reasoning[:60]}")
                else:
                    final_mult = max(final_mult, min(ai_mult, 1.3))
                    reasons.append(f"AI审判: 通过 - {ai_reasoning[:60]}")

                self.stats["ai_calls"] += 1
        else:
            self.stats["rule_only"] += 1

        self.stats["total_judged"] += 1
        self.stats[verdict if verdict != "approve" else "approved"] = self.stats.get(verdict if verdict != "approve" else "approved", 0) + 1
        if verdict == "approve":
            self.stats["approved"] = self.stats.get("approved", 0)
        self.stats["last_judge"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        verdict_record = {
            "time": self.stats["last_judge"],
            "symbol": sym_clean,
            "verdict": verdict,
            "score": score,
            "multiplier": round(final_mult, 3),
            "position_pct": round(position_pct, 2),
            "reasons": reasons[:5],
            "ai_used": use_ai and ai_verdict is not None,
            "direction": direction,
        }
        self.verdicts.append(verdict_record)
        if len(self.verdicts) > 50:
            self.verdicts = self.verdicts[-50:]

        if verdict == "reject":
            if sym_clean not in self.rejected_symbols:
                self.rejected_symbols.append(sym_clean)
            if len(self.rejected_symbols) > 20:
                self.rejected_symbols = self.rejected_symbols[-20:]

        if self.stats["total_judged"] % 5 == 0:
            self.save()

        logger.info(f"[TradeJudge] {sym_clean} → {verdict.upper()} (score={score}, mult={final_mult:.3f}, reasons={len(reasons)})")
        return {
            "verdict": verdict,
            "score": score,
            "multiplier": final_mult,
            "reasons": reasons,
            "ai_used": use_ai and ai_verdict is not None,
        }

    def _ai_deep_judge(self, context, mc_state, rule_score, rule_reasons, position_pct):
        try:
            from server.titan_llm_client import chat_json

            symbol = context.get("symbol", "?")
            signal_score = context.get("signal_score", 0)
            ml_confidence = context.get("ml_confidence", 0)
            regime = context.get("regime", "unknown")
            direction = context.get("direction", "long")
            drawdown_pct = context.get("drawdown_pct", 0)

            sym_clean = symbol.replace("/USDT", "").replace("/USDT:USDT", "")
            hist = self.symbol_history.get(sym_clean, {})
            hist_text = f"历史{hist.get('trades',0)}笔,胜率{hist.get('wins',0)}/{hist.get('trades',1)}" if hist else "无历史"

            prompt = f"""你是量化基金的交易审判官。评估这笔交易是否应该执行。

交易信息:
- 币种: {symbol}, 方向: {direction}
- 信号评分: {signal_score}/100, ML置信度: {ml_confidence}%
- 市场环境: {regime}, 回撤: {drawdown_pct:.1f}%
- 预计仓位: {position_pct:.1f}%

MC宪法状态:
- 日亏损已用: {mc_state.get('daily_pnl_used_pct', 0):.2f}% / {mc_state.get('daily_loss_limit', 0.02)*100:.2f}%
- 总暴露: {mc_state.get('current_exposure_pct', 0):.0f}% / {mc_state.get('exposure_cap_pct', 90):.0f}%

规则审判: {rule_score}分
规则理由: {'; '.join(rule_reasons[:3])}

币种历史: {hist_text}

请用JSON回复(不要markdown):
{{"verdict": "approve/reduce/reject", "size_multiplier": 0.1-1.3, "reasoning": "一句话理由", "risk_flag": "low/medium/high"}}"""

            result = chat_json(
                module="trade_judge",
                messages=[
                    {"role": "system", "content": TRADE_JUDGE_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
            )
            if not result:
                return None
            result["size_multiplier"] = max(0.1, min(1.3, float(result.get("size_multiplier", 1.0))))
            return result
        except Exception as e:
            logger.warning(f"[TradeJudge] AI judge failed: {e}")
            return None

    def get_status(self):
        recent = self.verdicts[-10:] if self.verdicts else []
        approve_rate = 0
        if self.stats["total_judged"] > 0:
            approve_rate = round(self.stats.get("approved", 0) / self.stats["total_judged"] * 100, 1)

        return {
            "stats": self.stats,
            "approve_rate": approve_rate,
            "recent_verdicts": recent,
            "rejected_symbols": self.rejected_symbols[-10:],
            "symbol_history_count": len(self.symbol_history),
        }


trade_judge = TitanTradeJudge()
