import os
import json
import logging
import time
from datetime import datetime
import pytz
from server.titan_prompt_library import POSITION_ADVISOR_KNOWLEDGE, PHASE_ZERO_CONTEXT
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanPositionAdvisor")
BEIJING_TZ = pytz.timezone('Asia/Shanghai')
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADVISOR_LOG_PATH = os.path.join(BASE_DIR, "data", "titan_advisor_log.json")


class TitanPositionAdvisor:

    def __init__(self):
        self.advice_history = []
        self.cooldown_seconds = 900
        self.last_advice_time = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(ADVISOR_LOG_PATH):
                with open(ADVISOR_LOG_PATH, 'r') as f:
                    data = json.load(f)
                self.advice_history = data.get("history", [])[-100:]
                self.last_advice_time = data.get("last_advice_time", {})
        except Exception as e:
            logger.warning(f"持仓顾问日志加载失败: {e}")

    def save(self):
        try:
            atomic_json_save(ADVISOR_LOG_PATH, {
                "history": self.advice_history[-100:],
                "last_advice_time": self.last_advice_time,
                "saved_at": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception:
            pass

    def _build_position_prompt(self, pos, market_context):
        direction_cn = "做多" if pos["direction"] == "long" else "做空"
        pnl_pct = pos.get("pnl_pct", 0)
        hold_hours = pos.get("hold_hours", 0)

        guard_warnings = pos.get("guard_warnings", [])
        warnings_text = "\n".join(f"  - {w}" for w in guard_warnings) if guard_warnings else "  无"

        vol_log = pos.get("vol_adjust_log", [])
        vol_text = ""
        if vol_log:
            for v in vol_log[-3:]:
                vol_text += f"\n  - [{v.get('time','')}] {v.get('reason','')} ATR比={v.get('atr_ratio','')}"
        else:
            vol_text = "\n  暂无调整记录"

        return f"""## 持仓详情: {pos['symbol']}
- 方向: {direction_cn}
- 入场价: {pos['entry_price']}
- 现价: {pos.get('current_price', pos['entry_price'])}
- 止盈价: {pos.get('tp_price', 'N/A')}
- 止损价: {pos.get('sl_price', 'N/A')}
- 追踪止损: {pos.get('trailing_sl', 'N/A')} (已激活: {'是' if pos.get('trailing_activated') else '否'})
- 盈亏: {pnl_pct:+.2f}%
- 持仓时间: {hold_hours:.1f}小时
- 持仓金额: ${pos.get('position_value', 0):.2f} (剩余: ${pos.get('remaining_value', pos.get('position_value', 0)):.2f})
- 信号分数: {pos.get('signal_score', 0)}
- ML置信度: {pos.get('ml_confidence', 0):.2f}
- 止盈阶段: {pos.get('tp_stage', 0)}/2
- BTC关联预警: {'是' if pos.get('btc_corr_alert') else '否'}

## 守卫预警信号:
{warnings_text}

## 波动率调整历史:
{vol_text}

## 市场环境:
- 市场状态: {market_context.get('regime', 'unknown')}
- BTC价格: ${market_context.get('btc_price', 0):,.2f}
- BTC变化: {market_context.get('btc_change', 0)}%
- 恐惧贪婪指数: {market_context.get('fng', 50)}
- 当前波动率(ATR比): {pos.get('vol_atr_ratio', 1.0):.2f}
- AI协调器仓位乘数: {market_context.get('size_multiplier', 1.0):.2f}
- 系统回撤: {market_context.get('drawdown_pct', 0):.2f}%
- 连胜/连亏: {market_context.get('consecutive_wins', 0)}/{market_context.get('consecutive_losses', 0)}"""

    def advise_position(self, pos, market_context):
        pid = pos.get("id", "unknown")
        now = time.time()
        last_time = self.last_advice_time.get(pid, 0)
        if now - last_time < self.cooldown_seconds:
            cached = self._get_cached_advice(pid)
            if cached:
                return cached

        try:
            from server.titan_llm_client import chat_json

            system_prompt = POSITION_ADVISOR_KNOWLEDGE + """你是"神盾计划：不死量化"的AI持仓顾问。你负责对每一个活跃持仓进行实时评估。

## 你的角色
你是一位经验丰富的交易操盘手,专注于仓位管理。你需要综合考虑：
1. 当前盈亏状态和趋势
2. K线形态预警（守卫系统已检测的危险信号）
3. 波动率变化对止损的影响
4. BTC大盘关联性风险
5. 持仓时间与市场环境的匹配度
6. 追踪止损是否已激活、止盈阶段进度

## 决策原则
- "先活下来,再赚钱" — 保本优先
- 盈利持仓要"让利润奔跑",但要有合理的保护
- 亏损持仓要果断，不恋战
- 波动率飙升时放宽止损避免被震出，但要设合理上限
- 持仓超过48小时未盈利的仓位要重点关注
- BTC急跌时所有多头持仓风险都升高

## 输出要求
返回JSON格式:
{
  "action": "hold/add/reduce/close/tighten_sl",
  "confidence": 0-100,
  "reasoning_chain": [
    "第一步分析: ...",
    "第二步判断: ...",
    "第三步结论: ..."
  ],
  "risk_assessment": "low/medium/high/critical",
  "key_factors": ["影响判断的关键因素1", "因素2"],
  "suggested_sl": null,
  "suggested_tp": null,
  "urgency": "low/medium/high",
  "summary": "15字内的核心建议"
}

action说明:
- hold: 继续持有,当前状态良好
- add: 可考虑加仓(需要高置信度>80)
- reduce: 建议减仓(部分平仓)
- close: 建议立即全平
- tighten_sl: 收紧止损保护利润"""

            position_prompt = PHASE_ZERO_CONTEXT + self._build_position_prompt(pos, market_context)

            result = chat_json(
                module="position_advisor",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": position_prompt},
                ],
                max_tokens=1500,
            )

            if not result:
                return self._rule_based_advice(pos, market_context)

            result["position_id"] = pid
            result["symbol"] = pos.get("symbol", "")
            result["timestamp"] = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
            result["source"] = "ai"

            self.last_advice_time[pid] = now
            self.advice_history.append({
                "pid": pid,
                "symbol": pos.get("symbol"),
                "time": result["timestamp"],
                "action": result.get("action", "hold"),
                "confidence": result.get("confidence", 50),
                "summary": result.get("summary", ""),
                "risk": result.get("risk_assessment", "medium"),
                "pnl_at_advice": pos.get("pnl_pct", 0),
            })
            if len(self.advice_history) > 100:
                self.advice_history = self.advice_history[-100:]

            self.save()
            logger.info(f"AI持仓顾问: {pos.get('symbol')} → {result.get('action')} 置信度={result.get('confidence')} {result.get('summary','')}")
            try:
                from server.titan_db import TitanDB
                TitanDB.update_advisor_suggestion(pid, result.get("action", "hold"))
                TitanDB.record_position_event(
                    trade_id=pid, symbol=pos.get("symbol", ""),
                    event_type='advisor_suggestion',
                    new_value=result.get("action", "hold"),
                    reason=result.get("summary", ""),
                    current_pnl_pct=pos.get("pnl_pct", 0),
                    current_price=pos.get("current_price"),
                    holding_hours=pos.get("hold_hours", 0)
                )
            except Exception:
                pass
            return result

        except Exception as e:
            logger.warning(f"AI持仓顾问异常: {e}")
            return self._rule_based_advice(pos, market_context)

    def _rule_based_advice(self, pos, market_context):
        pnl_pct = pos.get("pnl_pct", 0)
        hold_hours = pos.get("hold_hours", 0)
        warnings = pos.get("guard_warnings", [])
        btc_alert = pos.get("btc_corr_alert", False)
        trailing = pos.get("trailing_activated", False)
        vol_ratio = pos.get("vol_atr_ratio", 1.0)

        confidence = 50
        action = "hold"
        reasoning = []
        risk = "medium"
        factors = []
        urgency = "low"

        if pnl_pct > 5:
            confidence += 20
            reasoning.append(f"盈利{pnl_pct:.1f}%，状态良好")
            factors.append(f"盈利{pnl_pct:.1f}%")
            if trailing:
                reasoning.append("追踪止损已激活，利润有保护")
                action = "hold"
            elif pnl_pct > 10:
                reasoning.append("盈利丰厚但追踪止损未激活，建议收紧止损")
                action = "tighten_sl"
        elif pnl_pct > 0:
            confidence += 10
            reasoning.append(f"小幅盈利{pnl_pct:.1f}%，继续观察")
            action = "hold"
        elif pnl_pct > -2:
            reasoning.append(f"轻微亏损{pnl_pct:.1f}%，在容忍范围内")
            action = "hold"
        elif pnl_pct > -5:
            confidence -= 10
            reasoning.append(f"亏损{pnl_pct:.1f}%，需要关注")
            factors.append(f"亏损{pnl_pct:.1f}%")
            urgency = "medium"
            if hold_hours > 24:
                action = "tighten_sl"
                reasoning.append(f"持仓{hold_hours:.0f}h且亏损，收紧止损")
        else:
            confidence -= 25
            reasoning.append(f"深度亏损{pnl_pct:.1f}%，风险升高")
            factors.append(f"深度亏损{pnl_pct:.1f}%")
            risk = "high"
            urgency = "high"
            if hold_hours > 12:
                action = "close"
                reasoning.append("亏损超5%且持仓超12h，建议止损")

        if warnings:
            confidence -= len(warnings) * 8
            factors.append(f"{len(warnings)}个预警信号")
            for w in warnings[:2]:
                reasoning.append(f"预警: {w}")
            if len(warnings) >= 2:
                urgency = "high"
                risk = "high"

        if btc_alert:
            confidence -= 15
            factors.append("BTC关联预警")
            reasoning.append("BTC走势异常，关联风险升高")
            urgency = "high" if urgency != "high" else urgency
            if pnl_pct < 0:
                action = "reduce"

        if vol_ratio > 2.0:
            factors.append(f"波动率飙升{vol_ratio:.1f}x")
            reasoning.append(f"波动率为入场时{vol_ratio:.1f}倍，市场环境剧变")
            if pnl_pct < 0:
                risk = "critical"

        if hold_hours > 72 and pnl_pct < 2:
            confidence -= 10
            reasoning.append(f"持仓{hold_hours:.0f}h但盈利不足，效率低")
            factors.append("长时间低效持仓")

        confidence = max(5, min(95, confidence))

        summary_map = {
            "hold": "继续持有观察",
            "add": "可考虑加仓",
            "reduce": "建议部分减仓",
            "close": "建议立即平仓",
            "tighten_sl": "收紧止损保护",
        }

        return {
            "position_id": pos.get("id", ""),
            "symbol": pos.get("symbol", ""),
            "action": action,
            "confidence": confidence,
            "reasoning_chain": reasoning,
            "risk_assessment": risk,
            "key_factors": factors,
            "suggested_sl": None,
            "suggested_tp": None,
            "urgency": urgency,
            "summary": summary_map.get(action, "继续观察"),
            "timestamp": datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "source": "rule",
        }

    def advise_all_positions(self, positions_display, market_context):
        results = []
        for pos in positions_display:
            advice = self.advise_position(pos, market_context)
            results.append(advice)
        return results

    def _get_cached_advice(self, pid):
        for h in reversed(self.advice_history):
            if h.get("pid") == pid:
                return {
                    "position_id": pid,
                    "symbol": h.get("symbol", ""),
                    "action": h.get("action", "hold"),
                    "confidence": h.get("confidence", 50),
                    "reasoning_chain": [f"(缓存) {h.get('summary', '')}"],
                    "risk_assessment": h.get("risk", "medium"),
                    "key_factors": [],
                    "urgency": "low",
                    "summary": h.get("summary", "缓存中"),
                    "timestamp": h.get("time", ""),
                    "source": "cached",
                }
        return None

    def get_advice_history(self, limit=20):
        return list(reversed(self.advice_history[-limit:]))

    def get_status(self):
        total = len(self.advice_history)
        action_counts = {}
        for h in self.advice_history[-50:]:
            a = h.get("action", "hold")
            action_counts[a] = action_counts.get(a, 0) + 1

        return {
            "total_advices": total,
            "active_positions_advised": len(self.last_advice_time),
            "cooldown_seconds": self.cooldown_seconds,
            "action_distribution": action_counts,
            "recent_advices": self.advice_history[-5:],
        }


position_advisor = TitanPositionAdvisor()
