import os
import logging
import time
from server.titan_prompt_library import ANALYST_PROMPT

logger = logging.getLogger("TitanAnalyst")

# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
MODEL_NAME = "gpt-4o-mini"

_last_agent_call = 0
AGENT_COOLDOWN = 30


class TitanAnalyst:
    """
    Titan V17.5 AI 智能体 (Hybrid Intelligence Engine)
    
    Agent Mode: LLM深度思考 (高置信/极端信号时触发)
    Reflex Mode: 毫秒级规则生成 (默认模式, 零延迟)
    """

    @staticmethod
    def generate_card_insight(symbol, price, ml_score, ml_confidence, tech_data, direction="long"):
        global _last_agent_call

        use_agent = (
            (ml_confidence >= 85) or
            (ml_score >= 90) or
            (ml_score <= 10)
        )

        now = time.time()
        if use_agent and (now - _last_agent_call) >= AGENT_COOLDOWN:
            try:
                result = TitanAnalyst._ask_agent(symbol, price, ml_score, ml_confidence, tech_data, direction)
                if result:
                    _last_agent_call = now
                    return result
            except Exception as e:
                logger.warning(f"Agent思考超时, 切回Reflex模式: {e}")

        return TitanAnalyst._reflex_insight(symbol, price, ml_score, ml_confidence, tech_data, direction)

    @staticmethod
    def _reflex_insight(symbol, price, ml_score, ml_confidence, tech_data, direction):
        if ml_score >= 80:
            sentiment = "BULLISH"
            sentiment_cn = "极强看涨"
            color = "green"
        elif ml_score >= 60:
            sentiment = "POSITIVE"
            sentiment_cn = "偏多"
            color = "green"
        elif ml_score <= 20:
            sentiment = "BEARISH"
            sentiment_cn = "看空"
            color = "red"
        elif ml_score <= 40:
            sentiment = "WEAK"
            sentiment_cn = "偏空"
            color = "red"
        else:
            sentiment = "NEUTRAL"
            sentiment_cn = "观望"
            color = "gray"

        reasons = []
        adx = tech_data.get('adx', 0)
        rsi = tech_data.get('rsi', 50)
        bb_pos = tech_data.get('bb_position', 0.5)

        if adx > 30:
            reasons.append("趋势有效")
        elif adx < 15:
            reasons.append("无趋势")
        if rsi < 30:
            reasons.append("超卖")
        elif rsi > 70:
            reasons.append("超买")
        if bb_pos > 0.9:
            reasons.append("触及布林上轨")
        elif bb_pos < 0.1:
            reasons.append("触及布林下轨")
        if ml_confidence >= 70:
            reasons.append(f"AI置信{ml_confidence:.0f}%")

        if ml_score >= 80:
            advice = "强势信号, 动量充足, 可考虑积极入场"
        elif ml_score >= 60:
            advice = "偏多格局, 回调可关注买入机会"
        elif ml_score <= 20:
            advice = "高概率下行, 规避风险"
        elif ml_score <= 40:
            advice = "弱势运行, 谨慎观望"
        else:
            advice = "震荡区间, 现金为王"

        return {
            "title": f"Titan Reflex | {sentiment} ({sentiment_cn})",
            "body": f"[{', '.join(reasons) if reasons else '综合分析'}] {advice}",
            "score": round(ml_score, 1),
            "confidence": round(ml_confidence, 1),
            "color": color,
            "is_agent": False,
        }

    @staticmethod
    def _ask_agent(symbol, price, ml_score, ml_confidence, tech_data, direction):
        adx = tech_data.get('adx', 0)
        rsi = tech_data.get('rsi', 50)
        funding = tech_data.get('funding_rate', None)
        oi = tech_data.get('open_interest', None)

        funding_str = f", Funding Rate={funding:.4f}" if funding else ""
        oi_str = f", Open Interest=${oi:,.0f}" if oi else ""

        prompt = f"""You are Titan, a calm, cynical, and mathematically precise crypto hedge fund manager.

Analyze this asset based on the data:
- Asset: {symbol} at ${price:.4f}
- Titan ML Score: {ml_score:.1f}/100 (higher=more bullish)
- ML Confidence: {ml_confidence:.1f}%
- Direction Bias: {direction}
- Indicators: ADX={adx:.1f}, RSI={rsi:.1f}{funding_str}{oi_str}

Task: Write a ONE-SENTENCE tactical command in Chinese. Be direct. Reference specific data points.
Style: Professional, brief, actionable. Max 40 characters."""

        try:
            from server.titan_llm_client import chat
            thought = chat(
                module="analyst",
                messages=[{"role": "system", "content": ANALYST_PROMPT},
                          {"role": "user", "content": prompt}],
                json_mode=False,
                max_tokens=80,
            )
            if not thought:
                return None
            thought = thought.strip()
        except Exception as e:
            logger.warning(f"LLM调用失败: {e}")
            return None

        if ml_score >= 60:
            color = "green"
        elif ml_score <= 40:
            color = "red"
        else:
            color = "gray"

        return {
            "title": "Titan Agent Insight",
            "body": thought,
            "score": round(ml_score, 1),
            "confidence": round(ml_confidence, 1),
            "color": color,
            "is_agent": True,
        }

    @staticmethod
    def generate_market_summary(cruise_data):
        if not cruise_data:
            return {"summary": "等待扫描数据...", "is_agent": False}

        bulls = sum(1 for c in cruise_data if c.get('score', 50) >= 60)
        bears = sum(1 for c in cruise_data if c.get('score', 50) <= 40)
        total = len(cruise_data)
        neutrals = total - bulls - bears

        top_3 = sorted(cruise_data, key=lambda x: x.get('score', 0), reverse=True)[:3]
        top_symbols = [c.get('symbol', '?') for c in top_3]

        if total >= 5:
            try:
                from server.titan_llm_client import chat
                prompt = f"""Market Snapshot:
- Bulls: {bulls}, Bears: {bears}, Neutral: {neutrals}, Total: {total}
- Top Picks: {', '.join(top_symbols)}

Write a very short market status line in Chinese (max 20 characters). 
Example: "多头主导, 关注山寨轮动" or "空头压制, 防守为先"."""

                resp_text = chat(
                    module="analyst",
                    messages=[{"role": "user", "content": prompt}],
                    json_mode=False,
                    max_tokens=60,
                )
                summary = resp_text.strip().strip('"').strip("'").strip('"').strip('"') if resp_text else None
                if summary and len(summary) >= 2:
                    return {"summary": summary, "is_agent": True, "bulls": bulls, "bears": bears, "total": total}
            except Exception as e:
                logger.warning(f"市场摘要LLM调用失败: {e}")

        if bulls > bears * 1.5 and bulls > 3:
            summary = "多头主导, 风险偏好上升"
        elif bears > bulls * 1.5 and bears > 3:
            summary = "空头压制, 防守为先"
        else:
            summary = "多空博弈, 震荡格局"

        return {"summary": summary, "is_agent": False, "bulls": bulls, "bears": bears, "total": total}
