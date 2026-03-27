import numpy as np
import pandas as pd
import logging

logger = logging.getLogger("TitanStrategies")


class TitanMeanReversion:
    def __init__(self):
        self.name = "MeanReversion"
        self.bb_period = 20
        self.bb_std = 2.0
        self.rsi_period = 14
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.mfi_period = 14

    def analyze(self, df_1h, df_4h=None):
        result = {
            "strategy": self.name,
            "signal": "无",
            "direction": None,
            "confidence": 0,
            "entry_reason": "",
            "tp_pct": 0,
            "sl_pct": 0,
        }
        try:
            if df_1h is None or len(df_1h) < 50:
                return result

            c = df_1h['c'].astype(float)
            h = df_1h['h'].astype(float)
            l = df_1h['l'].astype(float)
            v = df_1h['v'].astype(float)
            price = c.iloc[-1]

            ma = c.rolling(self.bb_period).mean()
            std = c.rolling(self.bb_period).std()
            bb_upper = ma + self.bb_std * std
            bb_lower = ma - self.bb_std * std
            bb_mid = ma

            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / (bb_mid.iloc[-1] + 1e-10)
            bb_pos = (price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1] + 1e-10)

            delta = c.diff()
            gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
            rs = gain / (loss + 1e-10)
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            tp = (h + l + c) / 3
            rmf = tp * v
            ch = tp.diff()
            fp = rmf.where(ch > 0, 0).rolling(self.mfi_period).sum()
            fn = rmf.where(ch <= 0, 0).rolling(self.mfi_period).sum()
            mfi = (100 - (100 / (1 + fp / (fn + 1e-10)))).iloc[-1]

            vol_ratio = v.iloc[-1] / (v.rolling(20).mean().iloc[-1] + 1e-10)

            prev_bb_pos = (c.iloc[-2] - bb_lower.iloc[-2]) / (bb_upper.iloc[-2] - bb_lower.iloc[-2] + 1e-10)

            long_signals = 0
            short_signals = 0
            reasons_long = []
            reasons_short = []

            if bb_pos < 0.05:
                long_signals += 2
                reasons_long.append(f"BB下轨突破(pos={bb_pos:.2f})")
            elif bb_pos < 0.15:
                long_signals += 1
                reasons_long.append(f"BB下轨附近(pos={bb_pos:.2f})")

            if bb_pos > 0.95:
                short_signals += 2
                reasons_short.append(f"BB上轨突破(pos={bb_pos:.2f})")
            elif bb_pos > 0.85:
                short_signals += 1
                reasons_short.append(f"BB上轨附近(pos={bb_pos:.2f})")

            if rsi < self.rsi_oversold:
                long_signals += 2
                reasons_long.append(f"RSI超卖({rsi:.0f})")
            elif rsi < 40:
                long_signals += 1
                reasons_long.append(f"RSI偏低({rsi:.0f})")

            if rsi > self.rsi_overbought:
                short_signals += 2
                reasons_short.append(f"RSI超买({rsi:.0f})")
            elif rsi > 60:
                short_signals += 1
                reasons_short.append(f"RSI偏高({rsi:.0f})")

            if mfi < 20:
                long_signals += 1
                reasons_long.append(f"MFI资金流入低({mfi:.0f})")
            if mfi > 80:
                short_signals += 1
                reasons_short.append(f"MFI资金流出高({mfi:.0f})")

            if prev_bb_pos < 0.05 and bb_pos > prev_bb_pos:
                long_signals += 1
                reasons_long.append("BB反弹确认")
            if prev_bb_pos > 0.95 and bb_pos < prev_bb_pos:
                short_signals += 1
                reasons_short.append("BB回落确认")

            if bb_width < 0.03:
                long_signals = max(0, long_signals - 1)
                short_signals = max(0, short_signals - 1)

            if long_signals >= 3 and long_signals > short_signals:
                conf = min(95, 40 + long_signals * 10 + (30 - rsi) * 0.5)
                result["signal"] = "做多"
                result["direction"] = "LONG"
                result["confidence"] = round(conf)
                result["entry_reason"] = " | ".join(reasons_long)
                result["tp_pct"] = round(bb_width * 50, 2)
                result["sl_pct"] = round(bb_width * 25, 2)
            elif short_signals >= 3 and short_signals > long_signals:
                conf = min(95, 40 + short_signals * 10 + (rsi - 70) * 0.5)
                result["signal"] = "做空"
                result["direction"] = "SHORT"
                result["confidence"] = round(conf)
                result["entry_reason"] = " | ".join(reasons_short)
                result["tp_pct"] = round(bb_width * 50, 2)
                result["sl_pct"] = round(bb_width * 25, 2)

        except Exception as e:
            logger.debug(f"MeanReversion分析异常: {e}")
        return result


class TitanBreakout:
    def __init__(self):
        self.name = "Breakout"
        self.donchian_period = 20
        self.volume_confirm_ratio = 1.5
        self.atr_period = 14
        self.squeeze_threshold = 0.03

    def analyze(self, df_1h, df_4h=None):
        result = {
            "strategy": self.name,
            "signal": "无",
            "direction": None,
            "confidence": 0,
            "entry_reason": "",
            "tp_pct": 0,
            "sl_pct": 0,
        }
        try:
            if df_1h is None or len(df_1h) < 50:
                return result

            c = df_1h['c'].astype(float)
            h = df_1h['h'].astype(float)
            l = df_1h['l'].astype(float)
            v = df_1h['v'].astype(float)
            price = c.iloc[-1]

            don_upper = h.rolling(self.donchian_period).max()
            don_lower = l.rolling(self.donchian_period).min()
            don_range = don_upper - don_lower
            don_width = don_range / (c + 1e-10)

            tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(self.atr_period).mean()
            atr_val = atr.iloc[-1]

            vol_ma = v.rolling(20).mean()
            vol_ratio = v.iloc[-1] / (vol_ma.iloc[-1] + 1e-10)

            vol_5_avg = v.iloc[-5:].mean()
            vol_ratio_5 = vol_5_avg / (vol_ma.iloc[-1] + 1e-10)

            ma20 = c.rolling(20).mean()
            std20 = c.rolling(20).std()
            bb_width = (4 * std20 / (ma20 + 1e-10)).iloc[-1]

            was_squeezed = False
            for k in range(2, 8):
                if k < len(don_width) and don_width.iloc[-k] < self.squeeze_threshold:
                    was_squeezed = True
                    break

            prev_don_width = don_width.iloc[-5] if len(don_width) > 5 else don_width.iloc[-1]
            expanding = don_width.iloc[-1] > prev_don_width * 1.2

            long_signals = 0
            short_signals = 0
            reasons_long = []
            reasons_short = []

            if price >= don_upper.iloc[-1] * 0.998:
                long_signals += 2
                reasons_long.append(f"突破Donchian上轨({don_upper.iloc[-1]:.2f})")

            if price <= don_lower.iloc[-1] * 1.002:
                short_signals += 2
                reasons_short.append(f"跌破Donchian下轨({don_lower.iloc[-1]:.2f})")

            if vol_ratio > self.volume_confirm_ratio:
                if long_signals > 0:
                    long_signals += 2
                    reasons_long.append(f"放量确认({vol_ratio:.1f}x)")
                if short_signals > 0:
                    short_signals += 2
                    reasons_short.append(f"放量确认({vol_ratio:.1f}x)")
            elif vol_ratio > 1.2:
                if long_signals > 0:
                    long_signals += 1
                    reasons_long.append(f"温和放量({vol_ratio:.1f}x)")
                if short_signals > 0:
                    short_signals += 1
                    reasons_short.append(f"温和放量({vol_ratio:.1f}x)")

            if was_squeezed and expanding:
                long_signals += 1 if long_signals > 0 else 0
                short_signals += 1 if short_signals > 0 else 0
                if long_signals > 0:
                    reasons_long.append("盘整后突破")
                if short_signals > 0:
                    reasons_short.append("盘整后跌破")

            delta = c.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-10)
            rsi = (100 - (100 / (1 + rs))).iloc[-1]

            if rsi > 50 and long_signals > 0:
                long_signals += 1
                reasons_long.append(f"RSI动量支持({rsi:.0f})")
            if rsi < 50 and short_signals > 0:
                short_signals += 1
                reasons_short.append(f"RSI动量支持({rsi:.0f})")

            if c.iloc[-1] > c.iloc[-2] > c.iloc[-3] and long_signals > 0:
                long_signals += 1
                reasons_long.append("连续上涨K线")
            if c.iloc[-1] < c.iloc[-2] < c.iloc[-3] and short_signals > 0:
                short_signals += 1
                reasons_short.append("连续下跌K线")

            atr_pct = atr_val / (price + 1e-10) * 100

            if long_signals >= 3:
                conf = min(95, 35 + long_signals * 10 + (vol_ratio - 1) * 15)
                result["signal"] = "做多"
                result["direction"] = "LONG"
                result["confidence"] = round(conf)
                result["entry_reason"] = " | ".join(reasons_long)
                result["tp_pct"] = round(atr_pct * 3, 2)
                result["sl_pct"] = round(atr_pct * 1.5, 2)
            elif short_signals >= 3:
                conf = min(95, 35 + short_signals * 10 + (vol_ratio - 1) * 15)
                result["signal"] = "做空"
                result["direction"] = "SHORT"
                result["confidence"] = round(conf)
                result["entry_reason"] = " | ".join(reasons_short)
                result["tp_pct"] = round(atr_pct * 3, 2)
                result["sl_pct"] = round(atr_pct * 1.5, 2)

        except Exception as e:
            logger.debug(f"Breakout分析异常: {e}")
        return result


class TitanMomentumRotation:
    def __init__(self):
        self.name = "MomentumRotation"
        self.lookback_short = 5
        self.lookback_long = 20
        self.momentum_threshold = 3.0
        self.adx_min = 20

    def analyze(self, df_1h, df_4h=None):
        result = {
            "strategy": self.name,
            "signal": "无",
            "direction": None,
            "confidence": 0,
            "entry_reason": "",
            "tp_pct": 0,
            "sl_pct": 0,
            "momentum_score": 0,
            "relative_strength": 0,
        }
        try:
            if df_1h is None or len(df_1h) < 50:
                return result

            c = df_1h['c'].astype(float)
            h = df_1h['h'].astype(float)
            l = df_1h['l'].astype(float)
            v = df_1h['v'].astype(float)
            price = c.iloc[-1]

            mom_5 = (price / c.iloc[-self.lookback_short - 1] - 1) * 100
            mom_20 = (price / c.iloc[-self.lookback_long - 1] - 1) * 100

            mom_accel = mom_5 - (c.iloc[-2] / c.iloc[-self.lookback_short - 2] - 1) * 100

            ema12 = c.ewm(span=12, adjust=False).mean()
            ema26 = c.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            macd_hist = (macd_line - signal_line).iloc[-1]
            macd_hist_prev = (macd_line - signal_line).iloc[-2]

            plus_dm = h.diff().clip(lower=0)
            minus_dm = (-l.diff()).clip(lower=0)
            tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            p_di = 100 * (plus_dm.rolling(14).mean() / (atr + 1e-10))
            m_di = 100 * (minus_dm.rolling(14).mean() / (atr + 1e-10))
            dx = 100 * abs(p_di - m_di) / (p_di + m_di + 1e-10)
            adx = dx.rolling(14).mean().iloc[-1]

            vol_ma = v.rolling(20).mean()
            vol_ratio = v.iloc[-1] / (vol_ma.iloc[-1] + 1e-10)

            atr_val = atr.iloc[-1]
            atr_pct = atr_val / (price + 1e-10) * 100

            diff_abs_sum = c.diff().abs().rolling(10).sum()
            efficiency = abs(c.iloc[-1] - c.iloc[-10]) / (diff_abs_sum.iloc[-1] + 1e-10)

            momentum_score = 0
            if mom_5 > 0:
                momentum_score += mom_5 * 0.4
            else:
                momentum_score += mom_5 * 0.4
            if mom_20 > 0:
                momentum_score += mom_20 * 0.3
            else:
                momentum_score += mom_20 * 0.3
            momentum_score += mom_accel * 0.2
            if adx > self.adx_min:
                momentum_score *= (1 + (adx - self.adx_min) / 100)
            momentum_score += efficiency * 10 * 0.1

            result["momentum_score"] = round(momentum_score, 2)
            result["relative_strength"] = round(mom_20, 2)

            long_signals = 0
            short_signals = 0
            reasons_long = []
            reasons_short = []

            if mom_5 > self.momentum_threshold and mom_20 > 0:
                long_signals += 2
                reasons_long.append(f"强势动量(5h={mom_5:.1f}% 20h={mom_20:.1f}%)")
            elif mom_5 > 0 and mom_20 > self.momentum_threshold:
                long_signals += 1
                reasons_long.append(f"中期趋势(20h={mom_20:.1f}%)")

            if mom_5 < -self.momentum_threshold and mom_20 < 0:
                short_signals += 2
                reasons_short.append(f"弱势动量(5h={mom_5:.1f}% 20h={mom_20:.1f}%)")
            elif mom_5 < 0 and mom_20 < -self.momentum_threshold:
                short_signals += 1
                reasons_short.append(f"中期下跌(20h={mom_20:.1f}%)")

            if mom_accel > 1.0 and long_signals > 0:
                long_signals += 1
                reasons_long.append(f"动量加速({mom_accel:+.1f}%)")
            if mom_accel < -1.0 and short_signals > 0:
                short_signals += 1
                reasons_short.append(f"动量衰减({mom_accel:+.1f}%)")

            if macd_hist > 0 and macd_hist > macd_hist_prev and long_signals > 0:
                long_signals += 1
                reasons_long.append("MACD多头增强")
            if macd_hist < 0 and macd_hist < macd_hist_prev and short_signals > 0:
                short_signals += 1
                reasons_short.append("MACD空头增强")

            if adx > self.adx_min:
                if long_signals > 0:
                    long_signals += 1
                    reasons_long.append(f"ADX趋势确认({adx:.0f})")
                if short_signals > 0:
                    short_signals += 1
                    reasons_short.append(f"ADX趋势确认({adx:.0f})")

            if efficiency > 0.6:
                if long_signals > 0:
                    long_signals += 1
                    reasons_long.append(f"高效趋势({efficiency:.2f})")
                if short_signals > 0:
                    short_signals += 1
                    reasons_short.append(f"高效趋势({efficiency:.2f})")

            if long_signals >= 3:
                conf = min(95, 35 + long_signals * 8 + momentum_score * 2)
                result["signal"] = "做多"
                result["direction"] = "LONG"
                result["confidence"] = round(max(0, conf))
                result["entry_reason"] = " | ".join(reasons_long)
                result["tp_pct"] = round(atr_pct * 3.5, 2)
                result["sl_pct"] = round(atr_pct * 1.5, 2)
            elif short_signals >= 3:
                conf = min(95, 35 + short_signals * 8 + abs(momentum_score) * 2)
                result["signal"] = "做空"
                result["direction"] = "SHORT"
                result["confidence"] = round(max(0, conf))
                result["entry_reason"] = " | ".join(reasons_short)
                result["tp_pct"] = round(atr_pct * 3.5, 2)
                result["sl_pct"] = round(atr_pct * 1.5, 2)

        except Exception as e:
            logger.debug(f"MomentumRotation分析异常: {e}")
        return result

    def rank_universe(self, universe_data):
        rankings = []
        for symbol, data in universe_data.items():
            df_1h = data.get('1h')
            if df_1h is None or len(df_1h) < 30:
                continue
            c = df_1h['c'].astype(float)
            try:
                mom_5 = (c.iloc[-1] / c.iloc[-6] - 1) * 100
                mom_20 = (c.iloc[-1] / c.iloc[-21] - 1) * 100
                rs_score = mom_5 * 0.6 + mom_20 * 0.4
                rankings.append({"symbol": symbol, "rs_score": round(rs_score, 2), "mom_5": round(mom_5, 2), "mom_20": round(mom_20, 2)})
            except Exception:
                continue
        rankings.sort(key=lambda x: x["rs_score"], reverse=True)
        return rankings


class TitanStrategyRouter:
    def __init__(self):
        self.mean_reversion = TitanMeanReversion()
        self.breakout = TitanBreakout()
        self.momentum = TitanMomentumRotation()

    def analyze_all(self, df_1h, df_4h=None, regime=None):
        results = {
            "mean_reversion": self.mean_reversion.analyze(df_1h, df_4h),
            "breakout": self.breakout.analyze(df_1h, df_4h),
            "momentum": self.momentum.analyze(df_1h, df_4h),
        }

        best = self._select_best(results, regime)
        results["recommended"] = best
        results["regime"] = regime or "unknown"
        return results

    def _select_best(self, results, regime=None):
        regime = regime or "unknown"

        weights = {
            "mean_reversion": 1.0,
            "breakout": 1.0,
            "momentum": 1.0,
        }

        if regime in ("震荡", "range", "低波动", "ranging"):
            weights["mean_reversion"] = 1.8
            weights["breakout"] = 0.6
            weights["momentum"] = 0.8
        elif regime in ("上涨趋势", "下跌趋势", "trend", "趋势", "trending"):
            weights["mean_reversion"] = 0.5
            weights["breakout"] = 1.5
            weights["momentum"] = 1.8
        elif regime in ("高波动", "volatile"):
            weights["mean_reversion"] = 1.3
            weights["breakout"] = 1.4
            weights["momentum"] = 1.0
        elif regime in ("mixed",):
            weights["mean_reversion"] = 1.2
            weights["breakout"] = 1.0
            weights["momentum"] = 1.0

        best_strategy = None
        best_score = 0

        for name, result in results.items():
            if name in ("recommended", "regime"):
                continue
            if result["signal"] == "无":
                continue
            w = weights.get(name, 1.0)
            score = result["confidence"] * w
            if score > best_score:
                best_score = score
                best_strategy = {
                    "strategy": name,
                    "signal": result["signal"],
                    "direction": result["direction"],
                    "confidence": result["confidence"],
                    "weighted_score": round(best_score, 1),
                    "entry_reason": result["entry_reason"],
                    "tp_pct": result["tp_pct"],
                    "sl_pct": result["sl_pct"],
                }

        if best_strategy is None:
            return {
                "strategy": "none",
                "signal": "观望",
                "direction": None,
                "confidence": 0,
                "weighted_score": 0,
                "entry_reason": "三策略均无明确信号",
                "tp_pct": 0,
                "sl_pct": 0,
            }
        return best_strategy
