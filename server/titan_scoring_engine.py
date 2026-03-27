import os
import json
import time
import logging
import numpy as np
import pandas as pd
from server.titan_prompt_library import SCORING_ENGINE_PROMPT

logger = logging.getLogger("TitanScoringEngine")

AI_ENABLED = True
AI_TIMEOUT = 8
AI_MODEL = "gpt-4o-mini"

CONSENSUS_MIN_DIMENSIONS = 4
DIMENSION_MAX_SCORE = 20
TOTAL_DIMENSIONS = 6

AI_WEIGHT = 0.15
RULE_WEIGHT = 0.85


def _safe(val, default=0):
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return default
    return float(val)


def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - signal_line
    return macd, signal_line, hist


def _adx(df, period=14):
    high = df['h']
    low = df['l']
    close = df['c']
    plus_dm = high.diff()
    minus_dm = low.diff().apply(lambda x: -x)
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (plus_dm.rolling(window=period).mean() / (atr + 1e-10))
    minus_di = 100 * (minus_dm.rolling(window=period).mean() / (atr + 1e-10))
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10) * 100
    adx = dx.rolling(window=period).mean()
    return adx


def _atr(df, period=14):
    high = df['h']
    low = df['l']
    close = df['c']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def _bbands(series, period=20, std_dev=2):
    mid = series.rolling(window=period).mean()
    std = series.rolling(window=period).std()
    upper = mid + std_dev * std
    lower = mid - std_dev * std
    return upper, mid, lower


def _obv(df):
    close = df['c']
    volume = df['v']
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return (volume * direction).cumsum()


def _vwap(df):
    tp = (df['h'] + df['l'] + df['c']) / 3
    cum_vol = df['v'].cumsum()
    cum_tp_vol = (tp * df['v']).cumsum()
    return cum_tp_vol / (cum_vol + 1e-10)


class DimensionResult:
    def __init__(self, name, direction, score, rationale):
        self.name = name
        self.direction = direction
        self.score = min(score, DIMENSION_MAX_SCORE)
        self.rationale = rationale


class TitanScoringEngine:

    @staticmethod
    def score(data_map, fng_value, ext_features, is_crash, regime, daily_trend, tech_report, atr_4h, btc_macro_trend=None):
        if is_crash:
            return {
                "score": 0, "direction": "neutral", "strategy_type": "观察",
                "dimensions": [], "consensus": 0, "signal_details": ["熔断中"],
                "sl_mult": 2.0, "tp_mult": 3.0, "ai_verdict": None
            }

        d15m = data_map['15m']
        d1h = data_map['1h']
        d4h = data_map['4h']
        d1d = data_map.get('1d')
        price = _safe(d15m['c'].iloc[-1])

        dims = []
        dims.append(TitanScoringEngine._dim_trend_structure(d1h, d4h, d1d, price))
        dims.append(TitanScoringEngine._dim_momentum(d1h, d4h, price))
        dims.append(TitanScoringEngine._dim_volatility(d4h, price, regime))
        dims.append(TitanScoringEngine._dim_volume(d1h, d4h))
        dims.append(TitanScoringEngine._dim_key_levels(d4h, price, atr_4h))
        dims.append(TitanScoringEngine._dim_sentiment(fng_value, ext_features, daily_trend, regime, btc_macro_trend=btc_macro_trend))

        bullish_count = sum(1 for d in dims if d.direction == "bullish")
        bearish_count = sum(1 for d in dims if d.direction == "bearish")
        neutral_count = sum(1 for d in dims if d.direction == "neutral")

        if bullish_count >= CONSENSUS_MIN_DIMENSIONS:
            consensus_dir = "long"
            raw_score = sum(d.score for d in dims if d.direction == "bullish")
            raw_score += sum(d.score * 0.3 for d in dims if d.direction == "neutral")
        elif bearish_count >= CONSENSUS_MIN_DIMENSIONS:
            consensus_dir = "short"
            raw_score = sum(d.score for d in dims if d.direction == "bearish")
            raw_score += sum(d.score * 0.3 for d in dims if d.direction == "neutral")
        else:
            consensus_dir = "neutral"
            raw_score = sum(d.score * 0.5 for d in dims)

        max_possible = DIMENSION_MAX_SCORE * TOTAL_DIMENSIONS
        if consensus_dir == "long":
            normalized = 50 + (raw_score / max_possible) * 50
        elif consensus_dir == "short":
            normalized = 50 - (raw_score / max_possible) * 50
        else:
            normalized = 45 + (raw_score / max_possible) * 10

        consensus_count = max(bullish_count, bearish_count)

        if consensus_dir == "long":
            strategy_type = "趋势" if regime.get("type") in ("趋势", "强趋势") else "震荡"
        elif consensus_dir == "short":
            strategy_type = "趋势" if regime.get("type") in ("趋势", "强趋势") else "震荡"
        else:
            strategy_type = "观察"

        signal_details = []
        signal_details.append(f"维度共识:{consensus_count}/{TOTAL_DIMENSIONS} {'多头' if consensus_dir == 'long' else '空头' if consensus_dir == 'short' else '中性'}")
        for d in dims:
            icon = "🟢" if d.direction == "bullish" else "🔴" if d.direction == "bearish" else "⚪"
            signal_details.append(f"{icon}{d.name}({d.score:.0f}): {d.rationale}")

        if bullish_count >= 2 and bearish_count >= 2:
            conflict_dims = [d.name for d in dims if d.direction != consensus_dir and d.direction != "neutral"]
            if conflict_dims:
                signal_details.append(f"⚠分歧维度: {','.join(conflict_dims)}")
                normalized = normalized * 0.92

        sl_mult, tp_mult = TitanScoringEngine._dynamic_sl_tp(d4h, price, atr_4h, regime, consensus_dir)

        score = max(0, min(100, int(normalized)))

        overheat_note = None
        if score >= 85 and consensus_dir == "long":
            try:
                closes_4h = d4h['c'].dropna()
                if len(closes_4h) >= 20:
                    recent_gain = (float(closes_4h.iloc[-1]) - float(closes_4h.iloc[-20])) / float(closes_4h.iloc[-20])
                    if recent_gain > 0.15:
                        overheat_note = f"过热惩罚: 近20根4hK涨{recent_gain:.1%}>15%, {score}→78"
                        score = min(score, 78)
                    elif recent_gain > 0.08:
                        overheat_note = f"过热警告: 近20根4hK涨{recent_gain:.1%}>8%, {score}→82"
                        score = min(score, 82)
            except Exception:
                pass
        elif score <= 15 and consensus_dir == "short":
            try:
                closes_4h = d4h['c'].dropna()
                if len(closes_4h) >= 20:
                    recent_drop = (float(closes_4h.iloc[-20]) - float(closes_4h.iloc[-1])) / float(closes_4h.iloc[-20])
                    if recent_drop > 0.15:
                        overheat_note = f"超卖惩罚: 近20根4hK跌{recent_drop:.1%}>15%, {score}→22"
                        score = max(score, 22)
                    elif recent_drop > 0.08:
                        overheat_note = f"超卖警告: 近20根4hK跌{recent_drop:.1%}>8%, {score}→18"
                        score = max(score, 18)
            except Exception:
                pass

        if overheat_note:
            signal_details.append(f"🔥{overheat_note}")
            logger.info(f"[ScoringEngine] {overheat_note}")

        return {
            "score": score,
            "direction": consensus_dir,
            "strategy_type": strategy_type,
            "dimensions": dims,
            "consensus": consensus_count,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "signal_details": signal_details,
            "sl_mult": sl_mult,
            "tp_mult": tp_mult,
            "ai_verdict": None,
            "rule_score": score,
            "overheat_penalty": overheat_note,
        }

    @staticmethod
    def apply_ai_scoring(result, symbol, price, data_summary):
        if not AI_ENABLED:
            return result

        try:
            from server.titan_llm_client import chat_json

            dims_summary = []
            for d in result.get("dimensions", []):
                dims_summary.append(f"{d.name}: {d.direction}({d.score}) - {d.rationale}")

            prompt = f"""你是一位量化交易分析师。基于以下市场数据对 {symbol} 给出交易建议。

当前价格: {price}
规则引擎评分: {result['score']}/100 (方向: {result['direction']})
维度分析:
{chr(10).join(dims_summary)}

市场摘要:
{data_summary}

请用JSON格式回复:
{{"direction": "bullish/bearish/neutral", "confidence": 0-100, "reasoning": "简短理由(30字内)", "risk_warning": "风险提示(20字内)"}}"""

            ai_result = chat_json(
                module="scoring_engine",
                messages=[
                    {"role": "system", "content": SCORING_ENGINE_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=256,
            )

            if not ai_result:
                raise ValueError("AI返回空响应")

            ai_dir = ai_result.get("direction", "neutral")
            ai_conf = min(100, max(0, int(ai_result.get("confidence", 50))))
            ai_reasoning = ai_result.get("reasoning", "")
            ai_risk = ai_result.get("risk_warning", "")

            rule_score = result["score"]
            rule_dir = result["direction"]

            if ai_conf >= 80:
                ai_conf_decay = 0.50
                ai_conf_tier = "overconfident_decay50%"
            elif ai_conf >= 70:
                ai_conf_decay = 0.75
                ai_conf_tier = "high_decay25%"
            elif ai_conf >= 60:
                ai_conf_decay = 1.0
                ai_conf_tier = "reliable_no_decay"
            else:
                ai_conf_decay = 0.80
                ai_conf_tier = "low_decay20%"

            if ai_dir == "bullish":
                ai_score = 50 + (ai_conf / 100) * 50 * ai_conf_decay
            elif ai_dir == "bearish":
                ai_score = 50 - (ai_conf / 100) * 50 * ai_conf_decay
            else:
                ai_score = 50

            if (rule_dir == "long" and ai_dir == "bullish") or (rule_dir == "short" and ai_dir == "bearish"):
                blended = rule_score * RULE_WEIGHT + ai_score * AI_WEIGHT
                agreement = True
            elif rule_dir == "neutral" or ai_dir == "neutral":
                blended = rule_score * 0.9 + ai_score * 0.1
                agreement = True
            else:
                blended = rule_score * 0.92
                agreement = False

            blended = max(0, min(100, int(blended)))

            result["score"] = blended
            result["ai_verdict"] = {
                "direction": ai_dir,
                "confidence": ai_conf,
                "confidence_tier": ai_conf_tier,
                "confidence_decay": ai_conf_decay,
                "reasoning": ai_reasoning,
                "risk_warning": ai_risk,
                "agreement": agreement,
                "weight": AI_WEIGHT,
                "ai_score": round(ai_score, 1),
                "rule_score": rule_score,
                "blended_score": blended
            }

            ai_tag = "AI✓" if agreement else "AI✗"
            dir_cn = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(ai_dir, "中性")
            result["signal_details"].append(
                f"🤖{ai_tag} {dir_cn}({ai_conf}%) R{int(RULE_WEIGHT*100)}:A{int(AI_WEIGHT*100)} | {ai_reasoning}"
            )
            if ai_risk:
                result["signal_details"].append(f"⚠AI风险: {ai_risk}")

        except Exception as e:
            logger.warning(f"AI评分失败(降级为纯规则): {e}")
            result["ai_verdict"] = {"error": str(e), "fallback": True}

        return result

    @staticmethod
    def _dim_trend_structure(d1h, d4h, d1d, price):
        scores_bull = 0
        scores_bear = 0
        reasons = []

        if d4h is not None and len(d4h) > 50:
            ema20 = _ema(d4h['c'], 20).iloc[-1]
            ema50 = _ema(d4h['c'], 50).iloc[-1]
            ema20 = _safe(ema20)
            ema50 = _safe(ema50)

            if price > ema20 > ema50:
                scores_bull += 8
                reasons.append("4H均线多排")
            elif price < ema20 < ema50:
                scores_bear += 8
                reasons.append("4H均线空排")
            elif price > ema20:
                scores_bull += 3
                reasons.append("4H价>EMA20")
            elif price < ema20:
                scores_bear += 3
                reasons.append("4H价<EMA20")

        if d1h is not None and len(d1h) > 20:
            ema20_1h = _ema(d1h['c'], 20).iloc[-1]
            ema20_1h = _safe(ema20_1h)
            if price > ema20_1h:
                scores_bull += 3
            else:
                scores_bear += 3

        if d1d is not None and len(d1d) > 50:
            ema20_d = _ema(d1d['c'], 20).iloc[-1]
            ema50_d = _ema(d1d['c'], 50).iloc[-1]
            ema20_d = _safe(ema20_d)
            ema50_d = _safe(ema50_d)
            if price > ema20_d > ema50_d:
                scores_bull += 6
                reasons.append("日线多排")
            elif price < ema20_d < ema50_d:
                scores_bear += 6
                reasons.append("日线空排")
            elif price > ema20_d:
                scores_bull += 2
            elif price < ema20_d:
                scores_bear += 2

        try:
            vwap = _safe(_vwap(d4h).iloc[-1] if len(d4h) > 5 else price)
            if price > vwap * 1.005:
                scores_bull += 3
                reasons.append("VWAP之上")
            elif price < vwap * 0.995:
                scores_bear += 3
                reasons.append("VWAP之下")
        except Exception:
            pass

        if scores_bull > scores_bear:
            return DimensionResult("趋势结构", "bullish", scores_bull, " ".join(reasons) or "偏多")
        elif scores_bear > scores_bull:
            return DimensionResult("趋势结构", "bearish", scores_bear, " ".join(reasons) or "偏空")
        else:
            return DimensionResult("趋势结构", "neutral", max(scores_bull, scores_bear), "趋势不明")

    @staticmethod
    def _dim_momentum(d1h, d4h, price):
        scores_bull = 0
        scores_bear = 0
        reasons = []

        try:
            rsi_4h = _safe(_rsi(d4h['c']).iloc[-1], 50)
            rsi_1h = _safe(_rsi(d1h['c']).iloc[-1], 50)

            if rsi_4h < 35:
                scores_bull += 5
                reasons.append(f"RSI4H超卖({rsi_4h:.0f})")
            elif rsi_4h > 65:
                scores_bear += 5
                reasons.append(f"RSI4H超买({rsi_4h:.0f})")
            elif 40 <= rsi_4h <= 60:
                pass
            elif rsi_4h > 50:
                scores_bull += 2
            else:
                scores_bear += 2

            rsi_series = _rsi(d4h['c'])
            if len(rsi_series) >= 5:
                rsi_slope = _safe(rsi_series.iloc[-1]) - _safe(rsi_series.iloc[-5])
                if rsi_slope > 5:
                    scores_bull += 3
                    reasons.append("RSI上升")
                elif rsi_slope < -5:
                    scores_bear += 3
                    reasons.append("RSI下降")
        except Exception:
            pass

        try:
            macd_line, signal_line, macd_hist = _macd(d4h['c'])
            hist_now = _safe(macd_hist.iloc[-1])
            hist_prev = _safe(macd_hist.iloc[-2]) if len(macd_hist) > 1 else 0

            if hist_now > 0 and hist_now > hist_prev:
                scores_bull += 5
                reasons.append("MACD柱增长")
            elif hist_now < 0 and hist_now < hist_prev:
                scores_bear += 5
                reasons.append("MACD柱扩大")
            elif hist_now > 0:
                scores_bull += 2
            elif hist_now < 0:
                scores_bear += 2

            macd_now = _safe(macd_line.iloc[-1])
            sig_now = _safe(signal_line.iloc[-1])
            if len(macd_line) > 2:
                macd_prev = _safe(macd_line.iloc[-2])
                sig_prev = _safe(signal_line.iloc[-2])
                if macd_prev < sig_prev and macd_now > sig_now:
                    scores_bull += 4
                    reasons.append("MACD金叉")
                elif macd_prev > sig_prev and macd_now < sig_now:
                    scores_bear += 4
                    reasons.append("MACD死叉")
        except Exception:
            pass

        try:
            if len(d4h) > 10:
                highs = d4h['h'].values
                close = d4h['c'].values
                rsi_vals = _rsi(d4h['c']).values
                if len(highs) >= 10 and len(rsi_vals) >= 10:
                    price_higher = close[-1] > close[-5]
                    rsi_lower = _safe(rsi_vals[-1]) < _safe(rsi_vals[-5])
                    if price_higher and rsi_lower:
                        scores_bear += 3
                        reasons.append("顶背离")
                    price_lower = close[-1] < close[-5]
                    rsi_higher = _safe(rsi_vals[-1]) > _safe(rsi_vals[-5])
                    if price_lower and rsi_higher:
                        scores_bull += 3
                        reasons.append("底背离")
        except Exception:
            pass

        if scores_bull > scores_bear:
            return DimensionResult("动量确认", "bullish", scores_bull, " ".join(reasons) or "动量偏多")
        elif scores_bear > scores_bull:
            return DimensionResult("动量确认", "bearish", scores_bear, " ".join(reasons) or "动量偏空")
        else:
            return DimensionResult("动量确认", "neutral", max(scores_bull, scores_bear), "动量中性")

    @staticmethod
    def _dim_volatility(d4h, price, regime):
        scores_bull = 0
        scores_bear = 0
        reasons = []

        try:
            adx = _safe(_adx(d4h).iloc[-1], 20)

            adx_series = _adx(d4h)
            if len(adx_series) >= 5:
                adx_prev = _safe(adx_series.iloc[-5], 20)
                adx_rising = adx > adx_prev + 2

                if adx > 25 and adx_rising:
                    scores_bull += 6
                    reasons.append(f"ADX强+上升({adx:.0f}↑)")
                elif adx > 25:
                    scores_bull += 3
                    reasons.append(f"ADX趋势({adx:.0f})")
                elif adx < 15:
                    reasons.append(f"ADX极弱({adx:.0f})")
                else:
                    scores_bull += 1
        except Exception:
            pass

        try:
            upper, mid, lower = _bbands(d4h['c'])
            bb_width = (_safe(upper.iloc[-1]) - _safe(lower.iloc[-1])) / _safe(mid.iloc[-1], 1) * 100

            if len(upper) >= 10:
                prev_width = (_safe(upper.iloc[-10]) - _safe(lower.iloc[-10])) / _safe(mid.iloc[-10], 1) * 100
                if bb_width < prev_width * 0.7:
                    scores_bull += 4
                    reasons.append(f"BB收缩(蓄力)")
                elif bb_width > prev_width * 1.5:
                    reasons.append(f"BB扩张(趋势中)")
                    scores_bull += 2

            if price < _safe(lower.iloc[-1]):
                scores_bull += 5
                reasons.append("价<BB下轨")
            elif price > _safe(upper.iloc[-1]):
                scores_bear += 5
                reasons.append("价>BB上轨")
        except Exception:
            pass

        try:
            atr_series = _atr(d4h)
            if len(atr_series) >= 20:
                current_atr = _safe(atr_series.iloc[-1])
                median_atr = _safe(atr_series.iloc[-20:].median())
                atr_ratio = current_atr / median_atr if median_atr > 0 else 1.0

                if atr_ratio < 0.7:
                    scores_bull += 4
                    reasons.append(f"低波动(ATR偏低)")
                elif atr_ratio > 1.5:
                    scores_bear += 3
                    reasons.append(f"高波动(ATR偏高)")
                else:
                    scores_bull += 1
        except Exception:
            pass

        regime_type = regime.get("type", "")
        if regime_type in ("趋势", "强趋势"):
            scores_bull += 3
            reasons.append(f"✓{regime_type}环境")
        elif regime_type == "极端波动":
            scores_bear += 5
            reasons.append("极端波动环境")

        if scores_bull > scores_bear:
            return DimensionResult("波动环境", "bullish", scores_bull, " ".join(reasons) or "波动适中")
        elif scores_bear > scores_bull:
            return DimensionResult("波动环境", "bearish", scores_bear, " ".join(reasons) or "波动不利")
        else:
            return DimensionResult("波动环境", "neutral", max(scores_bull, scores_bear), "波动中性")

    @staticmethod
    def _dim_volume(d1h, d4h):
        scores_bull = 0
        scores_bear = 0
        reasons = []

        try:
            if 'v' in d4h.columns and len(d4h) >= 20:
                vol = d4h['v'].values
                avg_vol = np.mean(vol[-20:])
                current_vol = vol[-1]
                vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

                price_up = d4h['c'].iloc[-1] > d4h['c'].iloc[-2]
                price_down = d4h['c'].iloc[-1] < d4h['c'].iloc[-2]

                if vol_ratio > 1.5 and price_up:
                    scores_bull += 7
                    reasons.append(f"放量上涨({vol_ratio:.1f}x)")
                elif vol_ratio > 1.5 and price_down:
                    scores_bear += 7
                    reasons.append(f"放量下跌({vol_ratio:.1f}x)")
                elif vol_ratio < 0.5:
                    reasons.append("缩量")
                    scores_bull += 1
                elif price_up:
                    scores_bull += 2
                elif price_down:
                    scores_bear += 2
        except Exception:
            pass

        try:
            if len(d4h) >= 20:
                obv = _obv(d4h)
                if len(obv) >= 10:
                    obv_now = _safe(obv.iloc[-1])
                    obv_10ago = _safe(obv.iloc[-10])
                    obv_ema = _safe(_ema(obv, 10).iloc[-1])

                    if obv_now > obv_ema and obv_now > obv_10ago:
                        scores_bull += 6
                        reasons.append("OBV上升趋势")
                    elif obv_now < obv_ema and obv_now < obv_10ago:
                        scores_bear += 6
                        reasons.append("OBV下降趋势")
                    elif obv_now > obv_ema:
                        scores_bull += 2
                    elif obv_now < obv_ema:
                        scores_bear += 2
        except Exception:
            pass

        try:
            if len(d4h) >= 5:
                closes = d4h['c'].values[-5:]
                vols = d4h['v'].values[-5:]
                up_vol = sum(v for c, v, pc in zip(closes[1:], vols[1:], closes[:-1]) if c > pc)
                down_vol = sum(v for c, v, pc in zip(closes[1:], vols[1:], closes[:-1]) if c < pc)
                if up_vol > down_vol * 1.5:
                    scores_bull += 5
                    reasons.append("上涨量>下跌量")
                elif down_vol > up_vol * 1.5:
                    scores_bear += 5
                    reasons.append("下跌量>上涨量")
        except Exception:
            pass

        if scores_bull > scores_bear:
            return DimensionResult("成交量", "bullish", scores_bull, " ".join(reasons) or "量能偏多")
        elif scores_bear > scores_bull:
            return DimensionResult("成交量", "bearish", scores_bear, " ".join(reasons) or "量能偏空")
        else:
            return DimensionResult("成交量", "neutral", max(scores_bull, scores_bear), "量能中性")

    @staticmethod
    def _dim_key_levels(d4h, price, atr_4h):
        scores_bull = 0
        scores_bear = 0
        reasons = []

        try:
            if len(d4h) >= 50:
                high_max = d4h['h'].iloc[-50:].max()
                low_min = d4h['l'].iloc[-50:].min()
                fib_range = high_max - low_min

                fib_382 = high_max - fib_range * 0.382
                fib_500 = high_max - fib_range * 0.500
                fib_618 = high_max - fib_range * 0.618

                atr = _safe(atr_4h, price * 0.02)
                tolerance = atr * 0.5

                if abs(price - fib_618) < tolerance:
                    scores_bull += 6
                    reasons.append(f"测试Fib0.618支撑")
                elif abs(price - fib_500) < tolerance:
                    scores_bull += 4
                    reasons.append(f"测试Fib0.5")
                elif abs(price - fib_382) < tolerance:
                    scores_bear += 4
                    reasons.append(f"测试Fib0.382阻力")
        except Exception:
            pass

        try:
            if len(d4h) >= 20:
                recent_highs = []
                recent_lows = []
                closes = d4h['c'].values
                highs = d4h['h'].values
                lows = d4h['l'].values

                for i in range(2, min(len(d4h) - 2, 48)):
                    if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2]:
                        recent_highs.append(highs[i])
                    if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2]:
                        recent_lows.append(lows[i])

                atr = _safe(atr_4h, price * 0.02)

                near_support = any(abs(price - s) < atr * 0.8 and price >= s * 0.99 for s in recent_lows[-5:]) if recent_lows else False
                near_resistance = any(abs(price - r) < atr * 0.8 and price <= r * 1.01 for r in recent_highs[-5:]) if recent_highs else False

                if near_support:
                    scores_bull += 6
                    reasons.append("近支撑位")
                if near_resistance:
                    scores_bear += 6
                    reasons.append("近阻力位")

                if recent_highs:
                    highest_recent = max(recent_highs[-3:]) if len(recent_highs) >= 3 else max(recent_highs)
                    if price > highest_recent:
                        scores_bull += 5
                        reasons.append("突破前高")
                if recent_lows:
                    lowest_recent = min(recent_lows[-3:]) if len(recent_lows) >= 3 else min(recent_lows)
                    if price < lowest_recent:
                        scores_bear += 5
                        reasons.append("跌破前低")
        except Exception:
            pass

        try:
            if len(d4h) >= 10:
                price_position = (price - d4h['l'].iloc[-20:].min()) / (d4h['h'].iloc[-20:].max() - d4h['l'].iloc[-20:].min() + 1e-10)
                if price_position < 0.2:
                    scores_bull += 4
                    reasons.append(f"价格偏低位({price_position:.0%})")
                elif price_position > 0.8:
                    scores_bear += 4
                    reasons.append(f"价格偏高位({price_position:.0%})")
        except Exception:
            pass

        if scores_bull > scores_bear:
            return DimensionResult("关键位置", "bullish", scores_bull, " ".join(reasons) or "位置偏多")
        elif scores_bear > scores_bull:
            return DimensionResult("关键位置", "bearish", scores_bear, " ".join(reasons) or "位置偏空")
        else:
            return DimensionResult("关键位置", "neutral", max(scores_bull, scores_bear), "位置中性")

    @staticmethod
    def _dim_sentiment(fng_value, ext_features, daily_trend, regime, btc_macro_trend=None):
        scores_bull = 0
        scores_bear = 0
        reasons = []
        macro = btc_macro_trend or "neutral"

        fng = fng_value if fng_value else 50
        if fng <= 15:
            if macro == "bearish":
                scores_bear += 3
                reasons.append(f"极度恐惧({fng})+BTC下跌=恐慌做空")
            elif macro == "bullish":
                scores_bull += 6
                reasons.append(f"极度恐惧({fng})+BTC上升=逆向做多")
            else:
                scores_bull += 3
                reasons.append(f"极度恐惧({fng})+BTC中性=轻度看多")
        elif fng <= 25:
            if macro == "bearish":
                scores_bear += 2
                reasons.append(f"恐惧({fng})+BTC下跌=偏空")
            elif macro == "bullish":
                scores_bull += 4
                reasons.append(f"恐惧({fng})+BTC上升=偏多")
            else:
                scores_bull += 2
                reasons.append(f"恐惧({fng})+BTC中性=轻度偏多")
        elif fng >= 80:
            if macro == "bullish":
                scores_bull += 3
                reasons.append(f"极度贪婪({fng})+BTC上升=贪婪持多")
            elif macro == "bearish":
                scores_bear += 6
                reasons.append(f"极度贪婪({fng})+BTC下跌=逆向做空")
            else:
                scores_bear += 3
                reasons.append(f"极度贪婪({fng})+BTC中性=轻度看空")
        elif fng >= 65:
            if macro == "bullish":
                scores_bull += 2
                reasons.append(f"贪婪({fng})+BTC上升=偏多")
            elif macro == "bearish":
                scores_bear += 4
                reasons.append(f"贪婪({fng})+BTC下跌=偏空")
            else:
                scores_bear += 2
                reasons.append(f"贪婪({fng})+BTC中性=轻度偏空")
        else:
            reasons.append(f"FNG中性({fng})")

        if daily_trend:
            dt_dir = daily_trend.get("direction", "")
            dt_str = daily_trend.get("strength", "")
            if dt_dir in ("强势上涨",):
                scores_bull += 5
                reasons.append("日线强势上涨")
            elif dt_dir in ("上涨回踩",):
                scores_bull += 3
                reasons.append("日线回踩")
            elif dt_dir in ("强势下跌",):
                scores_bear += 5
                reasons.append("日线强势下跌")
            elif dt_dir in ("下跌反弹",):
                scores_bear += 3
                reasons.append("日线反弹")

        if ext_features:
            whale = ext_features.get("ext_whale_activity", 0)
            netflow = ext_features.get("ext_btc_netflow", 0)
            sopr = ext_features.get("ext_sopr_score", 0)

            if whale > 0.3:
                scores_bull += 3
                reasons.append("鲸鱼买入")
            elif whale < -0.3:
                scores_bear += 3
                reasons.append("鲸鱼抛售")

            if netflow > 0.3:
                scores_bull += 2
                reasons.append("交易所净流出")
            elif netflow < -0.3:
                scores_bear += 2
                reasons.append("交易所净流入")

        if scores_bull > scores_bear:
            return DimensionResult("市场情绪", "bullish", scores_bull, " ".join(reasons) or "情绪偏多")
        elif scores_bear > scores_bull:
            return DimensionResult("市场情绪", "bearish", scores_bear, " ".join(reasons) or "情绪偏空")
        else:
            return DimensionResult("市场情绪", "neutral", max(scores_bull, scores_bear), "情绪中性")

    @staticmethod
    def _dynamic_sl_tp(d4h, price, atr_4h, regime, direction):
        atr = _safe(atr_4h, price * 0.02)

        try:
            atr_series = _atr(d4h)
            if len(atr_series) >= 50:
                current_atr = _safe(atr_series.iloc[-1])
                sorted_atr = sorted(atr_series.iloc[-50:].dropna().values)
                if len(sorted_atr) > 0:
                    rank = sum(1 for x in sorted_atr if x <= current_atr)
                    percentile = rank / len(sorted_atr)
                else:
                    percentile = 0.5
            else:
                percentile = 0.5
        except Exception:
            percentile = 0.5

        if percentile >= 0.8:
            sl_mult = 2.5
            tp_mult = 3.0
        elif percentile >= 0.6:
            sl_mult = 2.0
            tp_mult = 3.5
        elif percentile >= 0.4:
            sl_mult = 1.8
            tp_mult = 4.0
        elif percentile >= 0.2:
            sl_mult = 1.5
            tp_mult = 4.5
        else:
            sl_mult = 1.3
            tp_mult = 5.0

        regime_type = regime.get("type", "")
        if regime_type in ("趋势", "强趋势"):
            tp_mult *= 1.2
        elif regime_type == "震荡":
            tp_mult *= 0.8
            sl_mult *= 0.9
        elif regime_type == "极端波动":
            sl_mult *= 1.3
            tp_mult *= 0.7

        sl_mult = max(1.0, min(3.5, sl_mult))
        tp_mult = max(1.5, min(6.0, tp_mult))

        sl_pct = (atr * sl_mult) / price
        if sl_pct < 0.015:
            sl_mult = 0.015 * price / atr if atr > 0 else 1.5

        return round(sl_mult, 2), round(tp_mult, 2)
