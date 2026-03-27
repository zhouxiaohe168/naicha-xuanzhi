import logging
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Optional, Any

logger = logging.getLogger("TitanPerceptionBrain")


class TitanPerceptionBrain:
    """感知脑 - K线形态识别 + 市场微观结构感知

    Shadow模式运行：计算结果写入market_pulses表，不影响任何交易决策。
    Phase 1第2周激活，Phase 2接入主决策流。
    """

    def __init__(self):
        self.shadow_mode = True
        self._last_pulse = {}
        self._breadth_cache = None
        self._breadth_cache_time = 0
        logger.info("[PerceptionBrain] 初始化完成 (Shadow模式)")

    def analyze(self, symbol: str, kline_data: dict, market_context: dict) -> Dict[str, Any]:
        """对单个标的进行感知分析

        Args:
            symbol: 交易对符号
            kline_data: K线数据 - dict of DataFrames with columns ['t','o','h','l','c','v']
                        keys: '15m', '1h', '4h', '1d' (any subset)
            market_context: 市场上下文 (fng, regime, btc_trend, funding_rate等)

        Returns:
            MarketPulse字典，包含各维度感知评分
        """
        fng = market_context.get("fng", 50)
        funding_rate = market_context.get("funding_rate", 0)

        kline_pred = self._predict_kline_pattern(kline_data)
        momentum = self._assess_momentum(kline_data)
        volatility = self._classify_volatility(kline_data)
        reversal_risk = self._calc_reversal_risk(kline_data, fng, funding_rate)
        session_bias = self._get_session_bias()
        breadth = self._compute_breadth(market_context)

        composite = self._compute_composite(
            kline_pred, momentum, volatility,
            reversal_risk, session_bias, breadth
        )

        pulse = {
            "symbol": symbol,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kline_prediction": kline_pred,
            "momentum": momentum,
            "volatility": volatility,
            "reversal_risk": reversal_risk,
            "session_bias": session_bias,
            "breadth_score": breadth,
            "composite_score": composite,
        }

        self._last_pulse[symbol] = pulse

        if self.shadow_mode:
            self._record_pulse(pulse)

        return pulse

    def get_market_pulse(self, symbol: str, klines=None, regime=None,
                         fng=None, btc_trend=None, funding_rate=None) -> Dict[str, Any]:
        """获取市场脉冲（对外统一接口）"""
        market_context = {
            "regime": regime or "",
            "fng": fng or 50,
            "btc_trend": btc_trend or "",
            "funding_rate": funding_rate or 0,
        }
        return self.analyze(symbol, klines or {}, market_context)

    def get_latest_pulse(self, symbol: str) -> Optional[Dict[str, Any]]:
        """获取某标的最新感知脉冲"""
        return self._last_pulse.get(symbol)

    def get_all_pulses(self) -> Dict[str, Dict[str, Any]]:
        """获取所有标的的最新感知脉冲"""
        return dict(self._last_pulse)

    def _extract_closes(self, kline_data: dict, n: int = 30) -> list:
        """从kline_data提取收盘价序列，优先用1h"""
        for tf in ['1h', '4h', '15m', '1d']:
            df = kline_data.get(tf)
            if df is not None and hasattr(df, '__len__') and len(df) >= 10:
                try:
                    return [float(x) for x in df['c'].values[-n:]]
                except Exception:
                    continue
        return []

    def _extract_hlcv(self, kline_data: dict, n: int = 30):
        """提取HLCV数据，返回(highs, lows, closes, volumes)列表"""
        for tf in ['1h', '4h', '15m', '1d']:
            df = kline_data.get(tf)
            if df is not None and hasattr(df, '__len__') and len(df) >= 10:
                try:
                    sl = slice(-n, None)
                    highs = [float(x) for x in df['h'].values[sl]]
                    lows = [float(x) for x in df['l'].values[sl]]
                    closes = [float(x) for x in df['c'].values[sl]]
                    volumes = [float(x) for x in df['v'].values[sl]]
                    return highs, lows, closes, volumes
                except Exception:
                    continue
        return [], [], [], []

    def _extract_opens(self, kline_data: dict, n: int = 30) -> list:
        """从kline_data提取开盘价序列"""
        for tf in ['1h', '4h', '15m', '1d']:
            df = kline_data.get(tf)
            if df is not None and hasattr(df, '__len__') and len(df) >= 10:
                try:
                    return [float(x) for x in df['o'].values[-n:]]
                except Exception:
                    continue
        return []

    def _predict_kline_pattern(self, kline_data: dict) -> float:
        """K线形态预测 (Phase 2实现CNN/Transformer, 当前用规则引擎)

        Returns:
            -1.0 ~ 1.0 预测方向倾斜
        """
        highs, lows, closes, volumes = self._extract_hlcv(kline_data, 20)
        opens = self._extract_opens(kline_data, 20)
        if len(closes) < 10:
            return 0.0

        score = 0.0
        try:
            last_c = closes[-1]
            last_o = opens[-1] if opens else closes[-2] if len(closes) >= 2 else last_c
            body = last_c - last_o
            candle_range = highs[-1] - lows[-1] if highs[-1] > lows[-1] else 0.001

            body_ratio = abs(body) / candle_range if candle_range > 0 else 0

            if body > 0 and body_ratio > 0.6:
                score += 0.3
            elif body < 0 and body_ratio > 0.6:
                score -= 0.3

            upper_shadow = highs[-1] - max(last_c, last_o)
            lower_shadow = min(last_c, last_o) - lows[-1]

            if lower_shadow > 2 * abs(body) and body_ratio < 0.3:
                score += 0.25
            elif upper_shadow > 2 * abs(body) and body_ratio < 0.3:
                score -= 0.25

            if len(closes) >= 3:
                if closes[-3] > closes[-2] > closes[-1]:
                    score -= 0.2
                elif closes[-3] < closes[-2] < closes[-1]:
                    score += 0.2

            return max(-1.0, min(1.0, round(score, 3)))
        except Exception:
            return 0.0

    def _assess_momentum(self, kline_data: dict) -> float:
        """评估动量质量

        Returns:
            0.0-1.0 (0.5=中性)
        """
        closes = self._extract_closes(kline_data, 20)
        if len(closes) < 10:
            return 0.5

        try:
            mom_5 = (closes[-1] - closes[-5]) / closes[-5] if closes[-5] != 0 else 0
            mom_10 = (closes[-1] - closes[-10]) / closes[-10] if closes[-10] != 0 else 0

            _, _, _, volumes = self._extract_hlcv(kline_data, 20)

            score = 0.5

            if mom_5 > 0.02:
                score += 0.15
            elif mom_5 < -0.02:
                score -= 0.15

            if mom_10 > 0.05:
                score += 0.15
            elif mom_10 < -0.05:
                score -= 0.15

            if len(volumes) >= 10:
                vol_avg = sum(volumes[-10:]) / 10
                vol_recent = sum(volumes[-3:]) / 3
                vol_ratio = vol_recent / vol_avg if vol_avg > 0 else 1.0

                if vol_ratio > 1.5:
                    score += 0.1
                elif vol_ratio < 0.7:
                    score -= 0.1

            return max(0.0, min(1.0, round(score, 3)))
        except Exception:
            return 0.5

    def _classify_volatility(self, kline_data: dict) -> str:
        """分类波动率状态

        Returns:
            'low' / 'normal' / 'high' / 'extreme'
        """
        highs, lows, closes, _ = self._extract_hlcv(kline_data, 14)
        if len(closes) < 5:
            return "normal"

        try:
            trs = []
            for i in range(1, len(closes)):
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1])
                )
                trs.append(tr)

            if not trs:
                return "normal"

            atr = sum(trs) / len(trs)
            atr_pct = atr / closes[-1] if closes[-1] > 0 else 0

            if atr_pct < 0.01:
                return "low"
            elif atr_pct < 0.025:
                return "normal"
            elif atr_pct < 0.05:
                return "high"
            else:
                return "extreme"
        except Exception:
            return "normal"

    def _calc_reversal_risk(self, kline_data: dict, fng=None, funding_rate=None) -> float:
        """计算反转风险

        Returns:
            0.0-1.0（越高越危险）
        """
        highs, lows, closes, _ = self._extract_hlcv(kline_data, 20)
        if len(closes) < 14:
            return 0.3

        try:
            risk = 0.2

            rsi_window = closes[-15:] if len(closes) >= 15 else closes
            gains = []
            losses = []
            for i in range(1, len(rsi_window)):
                diff = rsi_window[i] - rsi_window[i - 1]
                if diff > 0:
                    gains.append(diff)
                    losses.append(0)
                else:
                    gains.append(0)
                    losses.append(abs(diff))

            n_periods = len(gains)
            if n_periods > 0:
                avg_gain = sum(gains) / n_periods
                avg_loss = sum(losses) / n_periods
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                else:
                    rsi = 100 if avg_gain > 0 else 50

                if rsi > 75:
                    risk += 0.25
                elif rsi < 25:
                    risk += 0.15

            fng_val = float(fng) if fng else 50
            if fng_val < 15:
                risk += 0.20
            elif fng_val > 80:
                risk += 0.15

            if funding_rate:
                fr = float(funding_rate)
                if fr > 0.05:
                    risk += 0.15
                elif fr < -0.03:
                    risk += 0.10

            if len(highs) >= 10:
                recent_high = max(highs[-10:])
                if recent_high > 0:
                    dist_from_high = (recent_high - closes[-1]) / recent_high
                    if dist_from_high < 0.02:
                        risk += 0.10

            return max(0.0, min(1.0, round(risk, 3)))
        except Exception:
            return 0.3

    def _get_session_bias(self) -> float:
        """获取当前时段偏向

        Returns:
            -1.0到+1.0的浮点数
        """
        utc_hour = datetime.now(timezone.utc).hour

        if 13 <= utc_hour < 22:
            return 0.3
        elif 7 <= utc_hour < 16:
            return 0.1
        elif 0 <= utc_hour < 8:
            return -0.2
        else:
            return 0.0

    def _compute_breadth(self, market_context: dict) -> float:
        """市场广度评分（带60秒缓存避免重复DB查询）

        Returns:
            -1.0到+1.0
        """
        import time as _time
        now = _time.time()
        if self._breadth_cache is not None and (now - self._breadth_cache_time) < 60:
            return self._breadth_cache

        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT long_signals, short_signals, fng_value
                    FROM scan_summaries
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                row = cur.fetchone()

            if not row:
                self._breadth_cache = 0.0
                self._breadth_cache_time = now
                return 0.0

            long_n = int(row.get('long_signals', 0) or 0)
            short_n = int(row.get('short_signals', 0) or 0)
            total = long_n + short_n

            if total == 0:
                self._breadth_cache = 0.0
                self._breadth_cache_time = now
                return 0.0

            long_ratio = long_n / total
            breadth = (long_ratio - 0.5) * 2

            fng = float(row.get('fng_value', 50) or 50)
            if fng < 20:
                breadth -= 0.3
            elif fng > 70:
                breadth += 0.2

            result = max(-1.0, min(1.0, round(breadth, 3)))
            self._breadth_cache = result
            self._breadth_cache_time = now
            return result
        except Exception:
            return self._breadth_cache if self._breadth_cache is not None else 0.0

    def _compute_composite(self, kline_prob, momentum,
                           volatility, reversal_risk,
                           session_bias, breadth_score) -> float:
        """合成最终感知分数

        Returns:
            大约 -50到+50 的浮点分数（50为基准映射到0）
        """
        score = 0.0

        score += (momentum - 0.5) * 20

        score -= reversal_risk * 15

        if isinstance(session_bias, (int, float)):
            score += session_bias * 8

        if isinstance(breadth_score, (int, float)):
            score += breadth_score * 10

        vol_penalty = {
            'low': 0,
            'normal': 0,
            'high': -3,
            'extreme': -8
        }.get(volatility, 0)
        score += vol_penalty

        if isinstance(kline_prob, (int, float)) and kline_prob != 0.0:
            score += kline_prob * 12

        return round(score, 2)

    def _record_pulse(self, pulse: dict):
        """写入market_pulses表 (fire-and-forget)"""
        try:
            from server.titan_db import db_connection
            session_val = pulse["session_bias"]
            if isinstance(session_val, (int, float)):
                session_str = f"{session_val:+.1f}"
            else:
                session_str = str(session_val)

            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO market_pulses
                    (symbol, kline_prediction, momentum, volatility,
                     reversal_risk, session_bias, breadth_score, composite_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    pulse["symbol"],
                    pulse["kline_prediction"],
                    pulse["momentum"],
                    pulse["volatility"],
                    pulse["reversal_risk"],
                    session_str,
                    pulse["breadth_score"],
                    pulse["composite_score"],
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"[PerceptionBrain] 记录pulse失败: {e}")

    def get_status(self) -> dict:
        """返回模块状态摘要"""
        return {
            "module": "PerceptionBrain",
            "shadow_mode": self.shadow_mode,
            "tracked_symbols": len(self._last_pulse),
            "status": "shadow" if self.shadow_mode else "active",
        }
