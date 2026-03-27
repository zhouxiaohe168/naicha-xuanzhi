import numpy as np
import pandas as pd
import logging
import json
import os
import time
from typing import Optional, Dict, Tuple
from server.titan_prompt_library import ML_REGIME_PROMPT

logger = logging.getLogger("TitanMLRegime")


class TitanMLRegimeDetector:
    REGIMES = {
        0: 'trending_bull',
        1: 'trending_bear',
        2: 'range_low_vol',
        3: 'range_high_vol',
        4: 'crisis',
    }

    def __init__(self, cache_ttl=3600, cache_dir="data"):
        self.cache_ttl = cache_ttl
        self.cache_dir = cache_dir
        self.cache_file = os.path.join(cache_dir, "regime_cache.json")
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict:
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_cache(self):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f)
        except Exception:
            pass

    def detect_regime(self, close: pd.Series, volume: pd.Series,
                      high: Optional[pd.Series] = None,
                      low: Optional[pd.Series] = None) -> Tuple[int, str, float]:
        if len(close) < 30:
            return 2, 'range_low_vol', 0.5

        ret = close.pct_change().dropna()
        vol_20 = ret.rolling(20).std().iloc[-1] if len(ret) >= 20 else ret.std()
        if pd.isna(vol_20):
            vol_20 = 0.02

        ret_20 = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0.0
        ret_60 = (close.iloc[-1] / close.iloc[-60] - 1) if len(close) >= 60 else ret_20

        vol_rank = 0.5
        if len(ret) >= 100:
            hist_vol = ret.rolling(20).std().dropna()
            if len(hist_vol) > 0:
                vol_rank = (hist_vol < vol_20).mean()

        trend_strength = 0.0
        if len(close) >= 20:
            ema5 = close.ewm(span=5, adjust=False).mean()
            ema20 = close.ewm(span=20, adjust=False).mean()
            ema50 = close.ewm(span=50, adjust=False).mean() if len(close) >= 50 else ema20
            if ema5.iloc[-1] > ema20.iloc[-1] > ema50.iloc[-1]:
                trend_strength = 1.0
            elif ema5.iloc[-1] < ema20.iloc[-1] < ema50.iloc[-1]:
                trend_strength = -1.0
            elif ema5.iloc[-1] > ema20.iloc[-1]:
                trend_strength = 0.5
            elif ema5.iloc[-1] < ema20.iloc[-1]:
                trend_strength = -0.5

        drawdown = 0.0
        if high is not None and len(high) >= 20:
            rolling_max = high.rolling(60).max() if len(high) >= 60 else high.rolling(20).max()
            drawdown = (close.iloc[-1] - rolling_max.iloc[-1]) / (rolling_max.iloc[-1] + 1e-10)

        if drawdown < -0.15 and vol_rank > 0.8:
            regime_id = 4
            confidence = min(0.9, abs(drawdown) * 3)
        elif trend_strength >= 0.5 and ret_20 > 0.03:
            regime_id = 0
            confidence = min(0.9, abs(trend_strength) * 0.5 + abs(ret_20) * 3)
        elif trend_strength <= -0.5 and ret_20 < -0.03:
            regime_id = 1
            confidence = min(0.9, abs(trend_strength) * 0.5 + abs(ret_20) * 3)
        elif vol_rank > 0.6:
            regime_id = 3
            confidence = min(0.8, vol_rank)
        else:
            regime_id = 2
            confidence = min(0.8, 1.0 - vol_rank)

        return regime_id, self.REGIMES[regime_id], float(confidence)

    def detect_regime_series(self, close: pd.Series, volume: pd.Series,
                             high: Optional[pd.Series] = None,
                             low: Optional[pd.Series] = None) -> pd.Series:
        regimes = pd.Series(2, index=close.index, dtype=int)

        ret = close.pct_change()
        vol_20 = ret.rolling(20).std()
        ema5 = close.ewm(span=5, adjust=False).mean()
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        if high is not None:
            rolling_max = high.rolling(60).max()
            drawdown_series = (close - rolling_max) / (rolling_max + 1e-10)
        else:
            drawdown_series = pd.Series(0.0, index=close.index)

        hist_vol_median = vol_20.rolling(100).median()
        vol_relative = vol_20 / (hist_vol_median + 1e-10)
        ret_20 = close.pct_change(20)

        for i in range(60, len(close)):
            dd = drawdown_series.iloc[i]
            vr = vol_relative.iloc[i] if not pd.isna(vol_relative.iloc[i]) else 1.0
            r20 = ret_20.iloc[i] if not pd.isna(ret_20.iloc[i]) else 0.0

            if dd < -0.15 and vr > 1.5:
                regimes.iloc[i] = 4
            elif ema5.iloc[i] > ema20.iloc[i] > ema50.iloc[i] and r20 > 0.03:
                regimes.iloc[i] = 0
            elif ema5.iloc[i] < ema20.iloc[i] < ema50.iloc[i] and r20 < -0.03:
                regimes.iloc[i] = 1
            elif vr > 1.3:
                regimes.iloc[i] = 3
            else:
                regimes.iloc[i] = 2

        return regimes

    async def detect_regime_ai(self, close: pd.Series, volume: pd.Series,
                                symbol: str = "BTC") -> Tuple[int, str, float]:
        cache_key = f"{symbol}_{int(time.time() // self.cache_ttl)}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            return cached['id'], cached['name'], cached['confidence']

        rule_id, rule_name, rule_conf = self.detect_regime(close, volume)

        try:
            from server.titan_llm_client import chat_json

            ret_1d = (close.iloc[-1] / close.iloc[-24] - 1) * 100 if len(close) >= 24 else 0
            ret_7d = (close.iloc[-1] / close.iloc[-168] - 1) * 100 if len(close) >= 168 else 0
            ret_30d = (close.iloc[-1] / close.iloc[-720] - 1) * 100 if len(close) >= 720 else 0
            vol_20 = close.pct_change().rolling(20).std().iloc[-1] * 100
            price = close.iloc[-1]

            prompt = f"""Classify the current {symbol} market regime into exactly one category:
0: trending_bull (strong uptrend, aligned EMAs, positive momentum)
1: trending_bear (strong downtrend, negative momentum)
2: range_low_vol (sideways, low volatility, consolidation)
3: range_high_vol (choppy, high volatility, no clear direction)
4: crisis (sharp drawdown >15%, extreme volatility, capitulation)

Current data:
- Price: ${price:.2f}
- 1D return: {ret_1d:.2f}%
- 7D return: {ret_7d:.2f}%
- 30D return: {ret_30d:.2f}%
- 20-period hourly volatility: {vol_20:.3f}%
- Rule-based detection: {rule_name} (confidence: {rule_conf:.2f})

Respond with ONLY a JSON object: {{"regime": <0-4>, "confidence": <0.0-1.0>, "reasoning": "<brief>"}}"""

            result = chat_json(
                module="regime_detector",
                messages=[
                    {"role": "system", "content": ML_REGIME_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
            )

            if not result:
                return rule_id, rule_name, rule_conf
            ai_id = int(result.get('regime', rule_id))
            ai_conf = float(result.get('confidence', 0.5))

            if ai_id not in self.REGIMES:
                ai_id = rule_id

            final_conf = ai_conf * 0.6 + rule_conf * 0.4

            self._cache[cache_key] = {
                'id': ai_id, 'name': self.REGIMES[ai_id],
                'confidence': final_conf, 'reasoning': result.get('reasoning', '')
            }
            self._save_cache()

            logger.info(f"AI regime detection: {self.REGIMES[ai_id]} ({final_conf:.2f}) - {result.get('reasoning', '')}")
            return ai_id, self.REGIMES[ai_id], final_conf

        except Exception as e:
            logger.warning(f"AI regime detection failed, using rule-based: {e}")
            return rule_id, rule_name, rule_conf

    def get_regime_features(self, regime_id: int) -> Dict:
        one_hot = {f'regime_{i}': 1.0 if i == regime_id else 0.0 for i in range(5)}
        one_hot['regime_id'] = float(regime_id)
        return one_hot

    def get_regime_features_series(self, regime_series: pd.Series) -> pd.DataFrame:
        result = pd.DataFrame(index=regime_series.index)
        for i in range(5):
            result[f'regime_{i}'] = (regime_series == i).astype(float)
        result['regime_id'] = regime_series.astype(float)
        return result
