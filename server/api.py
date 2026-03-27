import os
import json
import uuid
import time
import asyncio
import threading
import logging
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from collections import deque
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import requests
import pytz
import ccxt.async_support as ccxt

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

logger = logging.getLogger(__name__)

from server.titan_ml import ml_engine, TitanMLEngine, ML_CONFIG as ML_ENGINE_CONFIG, TitanBacktester, adaptive_weights, RegimeDetector, titan_critic
from server.titan_money_manager import TitanMoneyManager, money_manager
from server.titan_modal_client import (
    trigger_training as modal_trigger_training,
    check_training_status as modal_check_status,
    download_and_install_model as modal_download_model,
    train_and_wait as modal_train_and_wait,
    get_modal_status,
    trigger_mm_training as modal_trigger_mm,
    check_mm_training_status as modal_check_mm,
    download_and_install_mm_model as modal_download_mm,
    get_mm_status,
    trigger_deep_all_training as modal_trigger_deep_all,
    check_deep_all_status as modal_check_deep_all,
    download_deep_all_models as modal_download_deep_all,
    get_deep_all_status,
)
from server.titan_analyst import TitanAnalyst
from server.titan_agent import agent_memory, governor, feedback_engine
from server.titan_simulator import simulator
from server.titan_external_data import TitanExternalDataManager
from server.titan_darwin import darwin_lab
from server.titan_hippocampus import hippocampus
from server.titan_unified_memory import unified_memory
from server.titan_agi import titan_agi
from server.titan_mtf import TitanMTF
from server.titan_mega_backtest import mega_backtest
from server.titan_risk_matrix import risk_matrix
from server.titan_attribution import attribution
from server.titan_monte_carlo import monte_carlo
from server.titan_constitution import TitanConstitution
from server.titan_paper_trader import TitanPaperTrader
from server.titan_dispatcher import dispatcher
from server.titan_grid import grid_engine
from server.titan_synapse import TitanSynapse
from server.titan_risk_budget import TitanRiskBudget
from server.titan_signal_quality import TitanSignalQuality
from server.titan_ai_reviewer import ai_reviewer
from server.titan_watchdog import watchdog
from server.titan_strategies import TitanStrategyRouter
from server.titan_capital_sizer import capital_sizer
from server.titan_unified_decision import unified_decision
from server.titan_return_target import return_target
from server.titan_ai_coordinator import ai_coordinator
from server.titan_perception_brain import TitanPerceptionBrain
from server.titan_strategy_brain import TitanStrategyBrain
from server.titan_debate_system import TitanDebateSystem

_perception_brain = TitanPerceptionBrain()
_strategy_brain = TitanStrategyBrain()
_debate_system = TitanDebateSystem()
from server.titan_position_guard import TitanPositionGuard
from server.titan_position_advisor import position_advisor
from server.titan_autopilot import TitanAutoPilot, TitanSignalGate
from server.titan_order_engine import order_engine
from server.titan_db import TitanDB, init_db
from server.titan_state import CONFIG, TitanState, get_coin_tier
from server.routes.grid import router as grid_router
from server.routes.ml_training import router as ml_training_router
from server.routes.ai_reports import router as ai_reports_router
from server.routes.trading import router as trading_router
from server.routes.data import router as data_router
from server.routes.system import router as system_router
from server.routes.ai_modules import router as ai_modules_router
from server.routes.decisions import router as decisions_router

try:
    init_db()
except Exception as _db_err:
    print(f"[DB] 数据库初始化失败(非致命): {_db_err}", flush=True)

MAX_POSITIONS = 10
REBALANCE_COOLDOWN_SECONDS = 1800


class TitanTechAnalyst:
    @staticmethod
    def get_fibonacci_levels(df, period=100):
        recent_high = df['h'].iloc[-period:].max()
        recent_low = df['l'].iloc[-period:].min()
        diff = recent_high - recent_low

        levels = {
            "0.236": recent_high - 0.236 * diff,
            "0.382": recent_high - 0.382 * diff,
            "0.500": recent_high - 0.5 * diff,
            "0.618": recent_high - 0.618 * diff,
            "High": recent_high,
            "Low": recent_low
        }

        curr = df['c'].iloc[-1]
        pos_desc = "区间运行"
        if abs(curr - levels["0.618"]) / curr < 0.01:
            pos_desc = "测试 0.618 黄金支撑"
        elif abs(curr - levels["High"]) / curr < 0.01:
            pos_desc = "测试前高压力"
        elif abs(curr - levels["Low"]) / curr < 0.01:
            pos_desc = "测试前低支撑"

        return levels, pos_desc

    @staticmethod
    def identify_candle_pattern(df):
        c = df['c'].iloc[-1]
        o = df['o'].iloc[-1]
        h = df['h'].iloc[-1]
        l = df['l'].iloc[-1]
        c_prev = df['c'].iloc[-2]
        o_prev = df['o'].iloc[-2]

        body = abs(c - o)
        upper_shadow = h - max(c, o)
        lower_shadow = min(c, o) - l

        patterns = []
        if c > o and c_prev < o_prev and c > o_prev and o < c_prev:
            patterns.append("看涨吞没")
        elif c < o and c_prev > o_prev and c < o_prev and o > c_prev:
            patterns.append("看跌吞没")
        if body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5:
            patterns.append("锤子线(探底)")
        if body > 0 and upper_shadow > body * 2 and lower_shadow < body * 0.5:
            patterns.append("射击之星(见顶)")

        return " | ".join(patterns) if patterns else "普通K线"

    @staticmethod
    def analyze_wave_structure(df):
        highs = df['h'].iloc[-5:].values
        lows = df['l'].iloc[-5:].values

        if highs[4] > highs[2] > highs[0] and lows[4] > lows[2]:
            return "上升脉冲"
        elif highs[4] < highs[2] < highs[0] and lows[4] < lows[2]:
            return "下降趋势"
        else:
            return "盘整结构"

    @staticmethod
    def generate_full_report(df_4h):
        fib, fib_pos = TitanTechAnalyst.get_fibonacci_levels(df_4h)
        pattern = TitanTechAnalyst.identify_candle_pattern(df_4h)
        wave = TitanTechAnalyst.analyze_wave_structure(df_4h)
        rsi = TitanMath.RSI(df_4h['c']).iloc[-1]

        suggestion = "观望"
        if "上升" in wave and rsi < 70:
            suggestion = "持有/低吸"
        elif "下降" in wave:
            suggestion = "减仓/规避"
        elif "0.618" in fib_pos:
            suggestion = "关注支撑博反弹"

        return {
            "candle": pattern,
            "fib_status": fib_pos,
            "wave": wave,
            "rsi": int(rsi) if not pd.isna(rsi) else 50,
            "suggestion": suggestion,
            "fib_high": round(fib["High"], 4),
            "fib_low": round(fib["Low"], 4),
            "fib_618": round(fib["0.618"], 4),
        }


class TitanMath:
    @staticmethod
    def RSI(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def EMA(series, period=20):
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def MACD(series, fast=12, slow=26, signal=9):
        exp1 = series.ewm(span=fast, adjust=False).mean()
        exp2 = series.ewm(span=slow, adjust=False).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        hist = macd - signal_line
        return macd, signal_line, hist

    @staticmethod
    def MFI(high, low, close, volume, period=14):
        tp = (high + low + close) / 3
        raw_money_flow = tp * volume
        change = tp.diff()
        flow_pos = raw_money_flow.copy()
        flow_neg = raw_money_flow.copy()
        flow_pos[change <= 0] = 0
        flow_neg[change > 0] = 0
        pos_mf = flow_pos.rolling(window=period).sum()
        neg_mf = flow_neg.rolling(window=period).sum()
        return 100 - (100 / (1 + pos_mf / (neg_mf + 1e-10)))

    @staticmethod
    def CCI(high, low, close, period=20):
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mad = (tp - sma).abs().rolling(window=period).mean()
        return (tp - sma) / (0.015 * mad + 1e-10)

    @staticmethod
    def WILLR(high, low, close, period=14):
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        return ((highest_high - close) / (highest_high - lowest_low + 1e-10)) * -100

    @staticmethod
    def SLOPE(series, period=5):
        y = series.values.astype(float)
        n = len(y)
        slopes = np.zeros(n)
        if n >= period:
            x = np.arange(period, dtype=float)
            x_mean = x.mean()
            denom = ((x - x_mean) ** 2).sum()
            for i in range(period - 1, n):
                window = y[i - period + 1:i + 1]
                slopes[i] = np.dot(x - x_mean, window - window.mean()) / denom
        return pd.Series(slopes, index=series.index)

    @staticmethod
    def ADX(df, period=14):
        plus_dm = df['h'].diff().clip(lower=0)
        minus_dm = (-df['l'].diff()).clip(lower=0)
        tr = pd.concat([df['h'] - df['l'], abs(df['h'] - df['c'].shift(1)), abs(df['l'] - df['c'].shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        p_di = 100 * (plus_dm.rolling(window=period).mean() / (atr + 1e-10))
        m_di = 100 * (minus_dm.rolling(window=period).mean() / (atr + 1e-10))
        dx = (100 * abs(p_di - m_di) / (p_di + m_di + 1e-10))
        return dx.rolling(window=period).mean()

    @staticmethod
    def VWAP(df):
        tp = (df['h'] + df['l'] + df['c']) / 3
        return (tp * df['v']).cumsum() / (df['v'].cumsum() + 1e-10)

    @staticmethod
    def BBANDS(series, period=20, std=2):
        ma = series.rolling(window=period).mean()
        sigma = series.rolling(window=period).std()
        return ma + std * sigma, ma, ma - std * sigma

    @staticmethod
    def ATR(df, period=14):
        h, l, c_prev = df['h'], df['l'], df['c'].shift(1)
        tr = pd.concat([h - l, abs(h - c_prev), abs(l - c_prev)], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def OBV(close, volume):
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return obv

    @staticmethod
    def STOCH(high, low, close, k_period=14, d_period=3):
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * ((close - lowest_low) / (highest_high - lowest_low + 1e-10))
        d = k.rolling(window=d_period).mean()
        return k, d

    @staticmethod
    def ICHIMOKU(high, low, close, tenkan=9, kijun=26, senkou_b=52):
        tenkan_sen = (high.rolling(tenkan).max() + low.rolling(tenkan).min()) / 2
        kijun_sen = (high.rolling(kijun).max() + low.rolling(kijun).min()) / 2
        senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun)
        senkou_b_line = ((high.rolling(senkou_b).max() + low.rolling(senkou_b).min()) / 2).shift(kijun)
        chikou = close.shift(-kijun)
        return tenkan_sen, kijun_sen, senkou_a, senkou_b_line, chikou

    @staticmethod
    def PSAR(high, low, close, af_start=0.02, af_max=0.20):
        n = len(close)
        psar = close.copy()
        bull = True
        af = af_start
        ep = low.iloc[0]
        hp = high.iloc[0]
        lp = low.iloc[0]
        psar.iloc[0] = close.iloc[0]
        for i in range(1, n):
            if bull:
                psar.iloc[i] = psar.iloc[i-1] + af * (hp - psar.iloc[i-1])
                if low.iloc[i] < psar.iloc[i]:
                    bull = False
                    psar.iloc[i] = hp
                    lp = low.iloc[i]
                    af = af_start
                else:
                    if high.iloc[i] > hp:
                        hp = high.iloc[i]
                        af = min(af + af_start, af_max)
            else:
                psar.iloc[i] = psar.iloc[i-1] + af * (lp - psar.iloc[i-1])
                if high.iloc[i] > psar.iloc[i]:
                    bull = True
                    psar.iloc[i] = lp
                    hp = high.iloc[i]
                    af = af_start
                else:
                    if low.iloc[i] < lp:
                        lp = low.iloc[i]
                        af = min(af + af_start, af_max)
        return psar

    @staticmethod
    def DONCHIAN(high, low, period=20):
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        mid = (upper + lower) / 2
        return upper, mid, lower

    @staticmethod
    def KELTNER(high, low, close, ema_period=20, atr_period=14, multiplier=2):
        ema = close.ewm(span=ema_period, adjust=False).mean()
        tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_period).mean()
        upper = ema + multiplier * atr
        lower = ema - multiplier * atr
        return upper, ema, lower

    @staticmethod
    def VOLUME_PROFILE(close, volume, bins=10):
        if len(close) < 20:
            return close.iloc[-1] if len(close) > 0 else 0
        price_min = close.min()
        price_max = close.max()
        bin_edges = np.linspace(price_min, price_max, bins + 1)
        vol_profile = np.zeros(bins)
        for i in range(bins):
            mask = (close >= bin_edges[i]) & (close < bin_edges[i + 1])
            vol_profile[i] = volume[mask].sum()
        poc_idx = np.argmax(vol_profile)
        poc_price = (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2
        return poc_price

    @staticmethod
    def MARKET_STRUCTURE(high, low, lookback=5):
        n = len(high)
        swing_highs = pd.Series(np.nan, index=high.index)
        swing_lows = pd.Series(np.nan, index=low.index)
        for i in range(lookback, n - lookback):
            if high.iloc[i] == high.iloc[i-lookback:i+lookback+1].max():
                swing_highs.iloc[i] = high.iloc[i]
            if low.iloc[i] == low.iloc[i-lookback:i+lookback+1].min():
                swing_lows.iloc[i] = low.iloc[i]
        recent_highs = swing_highs.dropna().tail(3)
        recent_lows = swing_lows.dropna().tail(3)
        structure = "neutral"
        if len(recent_highs) >= 2 and len(recent_lows) >= 2:
            hh = recent_highs.iloc[-1] > recent_highs.iloc[-2] if len(recent_highs) >= 2 else False
            hl = recent_lows.iloc[-1] > recent_lows.iloc[-2] if len(recent_lows) >= 2 else False
            lh = recent_highs.iloc[-1] < recent_highs.iloc[-2] if len(recent_highs) >= 2 else False
            ll = recent_lows.iloc[-1] < recent_lows.iloc[-2] if len(recent_lows) >= 2 else False
            if hh and hl:
                structure = "uptrend"
            elif lh and ll:
                structure = "downtrend"
            elif hh and ll:
                structure = "expansion"
            elif lh and hl:
                structure = "compression"
        return structure, swing_highs, swing_lows

    @staticmethod
    def get_fear_and_greed():
        try:
            r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=5).json()
            data = r.get('data', [])
            if not data:
                return {"value": 50, "label": "Neutral", "change": 0, "avg_7d": 50, "source": "default", "timestamp": 0}
            current = data[0]
            val = int(current.get('value', 50))
            label = current.get('value_classification', 'Neutral')
            ts = int(current.get('timestamp', 0))
            change = 0
            if len(data) >= 2:
                prev = int(data[1].get('value', val))
                change = val - prev
            avg_7d = val
            if len(data) >= 7:
                avg_7d = round(sum(int(d.get('value', 50)) for d in data) / len(data), 1)
            return {"value": val, "label": label, "change": change, "avg_7d": avg_7d, "source": "alternative.me", "timestamp": ts}
        except Exception:
            return {"value": 50, "label": "Neutral", "change": 0, "avg_7d": 50, "source": "default", "timestamp": 0}


class TitanBrain:
    @staticmethod
    def analyze_daily_trend(d1d):
        trend = {"direction": "中性", "ma_align": "无序", "rsi": 50, "strength": "弱", "detail": ""}
        try:
            close = d1d['c']
            if len(close) < 50:
                return trend

            ma7 = close.rolling(7).mean()
            ma20 = close.rolling(20).mean()
            ma50 = close.rolling(50).mean()

            ma7_v = ma7.iloc[-1]
            ma20_v = ma20.iloc[-1]
            ma50_v = ma50.iloc[-1]
            price = close.iloc[-1]

            if pd.isna(ma7_v) or pd.isna(ma20_v) or pd.isna(ma50_v):
                return trend

            if ma7_v > ma20_v > ma50_v:
                trend["ma_align"] = "多头排列"
                if price > ma7_v:
                    trend["direction"] = "强势上涨"
                    trend["strength"] = "强"
                else:
                    trend["direction"] = "上涨回踩"
                    trend["strength"] = "中"
            elif ma7_v < ma20_v < ma50_v:
                trend["ma_align"] = "空头排列"
                if price < ma7_v:
                    trend["direction"] = "强势下跌"
                    trend["strength"] = "强"
                else:
                    trend["direction"] = "下跌反弹"
                    trend["strength"] = "中"
            else:
                trend["ma_align"] = "交叉震荡"
                trend["direction"] = "震荡"
                trend["strength"] = "弱"

            rsi_d = TitanMath.RSI(close).iloc[-1]
            trend["rsi"] = round(float(rsi_d), 1) if not pd.isna(rsi_d) else 50

            change_5d = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 6 else 0
            change_20d = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 21 else 0

            parts = [f"日线{trend['direction']}", f"均线{trend['ma_align']}"]
            parts.append(f"RSI({trend['rsi']})")
            parts.append(f"5日涨幅{change_5d:+.1f}%")
            parts.append(f"20日涨幅{change_20d:+.1f}%")
            trend["detail"] = " | ".join(parts)
            trend["change_5d"] = round(change_5d, 1)
            trend["change_20d"] = round(change_20d, 1)
        except Exception:
            pass
        return trend

    @staticmethod
    def compute_confluence(daily_trend, ml_pred, regime, rsi_1h, ext_features, hip_result=None):
        dimensions = {}
        d_dir = daily_trend.get("direction", "未知")
        if d_dir in ("强势上涨", "上涨回踩"):
            dimensions["technical"] = 1.0
        elif d_dir in ("强势下跌", "下跌反弹"):
            dimensions["technical"] = -1.0
        else:
            dimensions["technical"] = 0.0

        ml_label = ml_pred.get("label", "横盘") if ml_pred.get("confidence", 0) > 40 else "无"
        ml_conf = ml_pred.get("confidence", 0)
        if ml_label == "看涨":
            dimensions["ml"] = min(ml_conf / 100.0, 1.0)
        elif ml_label == "看跌":
            dimensions["ml"] = -min(ml_conf / 100.0, 1.0)
        else:
            dimensions["ml"] = 0.0

        whale = ext_features.get("ext_whale_activity", 0)
        netflow = ext_features.get("ext_btc_netflow", 0)
        sopr = ext_features.get("ext_sopr_score", 0)
        onchain_avg = (whale + netflow + sopr) / 3.0
        dimensions["onchain"] = max(-1.0, min(1.0, onchain_avg))

        fng_val = ext_features.get("ext_fng", 50)
        sentiment_global = ext_features.get("ext_sentiment_global", 0.5)
        if fng_val < 25:
            dimensions["sentiment"] = -0.8
        elif fng_val > 75:
            dimensions["sentiment"] = 0.8
        else:
            dimensions["sentiment"] = (sentiment_global - 0.5) * 2.0

        rsi_val = float(rsi_1h) if not pd.isna(rsi_1h) else 50
        if rsi_val < 30:
            dimensions["momentum"] = 0.7
        elif rsi_val > 70:
            dimensions["momentum"] = -0.7
        else:
            dimensions["momentum"] = (50 - rsi_val) / 50.0

        if hip_result and hip_result.get("avg_similarity", 0) > 0.3:
            if hip_result["signal"] == "BULLISH":
                dimensions["fractal"] = min(hip_result["confidence"], 1.0)
            elif hip_result["signal"] == "BEARISH":
                dimensions["fractal"] = -min(hip_result["confidence"], 1.0)
            else:
                dimensions["fractal"] = 0.0
        else:
            dimensions["fractal"] = 0.0

        signs = [1 if v > 0.2 else (-1 if v < -0.2 else 0) for v in dimensions.values()]
        bullish_count = sum(1 for s in signs if s > 0)
        bearish_count = sum(1 for s in signs if s < 0)
        total_dims = len(dimensions)

        if bullish_count >= 4:
            confluence_level = "强共振做多"
            confluence_score = sum(max(0, v) for v in dimensions.values()) / total_dims
        elif bearish_count >= 4:
            confluence_level = "强共振做空"
            confluence_score = sum(min(0, v) for v in dimensions.values()) / total_dims
        elif bullish_count >= 3:
            confluence_level = "共振做多"
            confluence_score = sum(max(0, v) for v in dimensions.values()) / total_dims * 0.7
        elif bearish_count >= 3:
            confluence_level = "共振做空"
            confluence_score = sum(min(0, v) for v in dimensions.values()) / total_dims * 0.7
        else:
            confluence_level = "信号分歧"
            confluence_score = 0.0

        return {
            "level": confluence_level,
            "score": round(confluence_score, 3),
            "dimensions": {k: round(v, 3) for k, v in dimensions.items()},
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
        }

    @staticmethod
    def check_onchain_veto(ext_features, direction="long"):
        whale = ext_features.get("ext_whale_activity", 0)
        netflow = ext_features.get("ext_btc_netflow", 0)
        sopr = ext_features.get("ext_sopr_score", 0)
        onchain_composite = ext_features.get("ext_onchain_composite", 0)

        veto = False
        veto_reason = ""
        veto_strength = 0

        if direction == "long":
            if whale <= -0.6 and netflow <= -0.4:
                veto = True
                veto_reason = f"巨鲸抛售(whale:{whale:.2f})+交易所净流入(netflow:{netflow:.2f})"
                veto_strength = abs(whale) + abs(netflow)
            elif onchain_composite <= -0.7:
                veto = True
                veto_reason = f"链上综合极度悲观({onchain_composite:.2f})"
                veto_strength = abs(onchain_composite)
            elif whale <= -0.8:
                veto = True
                veto_reason = f"巨鲸大规模出货(whale:{whale:.2f})"
                veto_strength = abs(whale)
        elif direction == "short":
            if whale >= 0.6 and netflow >= 0.4:
                veto = True
                veto_reason = f"巨鲸大量吸筹(whale:{whale:.2f})+交易所净流出(netflow:{netflow:.2f})"
                veto_strength = whale + netflow
            elif onchain_composite >= 0.7:
                veto = True
                veto_reason = f"链上综合极度看好({onchain_composite:.2f})"
                veto_strength = onchain_composite

        return {"veto": veto, "reason": veto_reason, "strength": round(veto_strength, 3)}

    @staticmethod
    def analyze(data_map, fng_value, is_crash, hip_result=None):
        d15m, d1h, d4h = data_map['15m'], data_map['1h'], data_map['4h']
        d1d = data_map.get('1d')
        price = d15m['c'].iloc[-1]

        if is_crash:
            return 0, price, 0, 0, 0, "熔断中", "KILL", {}, {}, {}, {"icon": "🔴", "advice": "熔断回避", "reason": "市场熔断"}, {'type': '极端波动', 'volatility': 'extreme', 'trend_intensity': 0, 'action_modifier': 0}

        daily_trend = TitanBrain.analyze_daily_trend(d1d) if d1d is not None and len(d1d) > 20 else {"direction": "未知", "ma_align": "数据不足", "rsi": 50, "strength": "弱", "detail": ""}

        regime = RegimeDetector.detect(d4h)

        try:
            ext_mgr = TitanExternalDataManager.get_instance()
            ext_features = ext_mgr.get_ml_features() if ext_mgr else {}
        except Exception:
            ext_features = {}

        tech_report = TitanTechAnalyst.generate_full_report(d4h)

        atr_4h = TitanMath.ATR(d4h).iloc[-1]  # type: ignore[union-attr]
        if pd.isna(atr_4h) or atr_4h == 0:
            atr_4h = price * 0.02

        adx_4h_val = TitanMath.ADX(d4h).iloc[-1]
        if pd.isna(adx_4h_val):
            adx_4h_val = 15
        tech_report["adx"] = round(float(adx_4h_val), 1) if not pd.isna(adx_4h_val) else 0
        macd_line, _, macd_hist_val = TitanMath.MACD(d4h['c'])
        mh = macd_hist_val.iloc[-1] if len(macd_hist_val) > 0 else 0
        tech_report["macd_hist"] = round(float(mh), 4) if not pd.isna(mh) else 0
        tech_report["atr"] = round(float(atr_4h), 6)

        try:
            closes_4h = d4h['c'].values
            highs_4h = d4h['h'].values if 'h' in d4h.columns else None
            lows_4h = d4h['l'].values if 'l' in d4h.columns else None
            if len(closes_4h) >= 12:
                ema5 = pd.Series(closes_4h).ewm(span=5).mean().iloc[-1]
                ema12 = pd.Series(closes_4h).ewm(span=12).mean().iloc[-1]
                diff_pct = (ema5 - ema12) / (ema12 + 1e-10) * 100
                up_votes = 0
                down_votes = 0
                if diff_pct > 0.1:
                    up_votes += 1
                elif diff_pct < -0.1:
                    down_votes += 1
                if closes_4h[-1] > closes_4h[-4]:
                    up_votes += 1
                else:
                    down_votes += 1
                if closes_4h[-1] > closes_4h[-2]:
                    up_votes += 1
                else:
                    down_votes += 1
                if closes_4h[-1] > ema12:
                    up_votes += 1
                else:
                    down_votes += 1
                if highs_4h is not None and lows_4h is not None and len(highs_4h) >= 5:
                    if highs_4h[-1] > max(highs_4h[-5:-1]):
                        up_votes += 1
                    elif lows_4h[-1] < min(lows_4h[-5:-1]):
                        down_votes += 1
                if up_votes >= 3:
                    tech_report["direction_4h"] = "up"
                elif down_votes >= 3:
                    tech_report["direction_4h"] = "down"
                else:
                    tech_report["direction_4h"] = "neutral"
                tech_report["direction_4h_votes"] = f"up={up_votes},dn={down_votes}"
            else:
                tech_report["direction_4h"] = "neutral"
        except Exception:
            tech_report["direction_4h"] = "neutral"

        rsi_1h_val = TitanMath.RSI(d1h['c']).iloc[-1] if len(d1h) > 14 else 50
        tech_report["rsi_1h"] = round(float(rsi_1h_val), 1) if not pd.isna(rsi_1h_val) else 50
        rsi_1h = rsi_1h_val

        from server.titan_scoring_engine import TitanScoringEngine
        current_macro = TitanState.market_snapshot.get("btc_pulse", {}).get("macro_trend", "neutral")
        engine_result = TitanScoringEngine.score(
            data_map, fng_value, ext_features, False, regime, daily_trend, tech_report, atr_4h,
            btc_macro_trend=current_macro
        )

        score = engine_result["score"]
        strategy_type = engine_result["strategy_type"]
        signal_details = engine_result["signal_details"]
        sl_atr_mult = engine_result["sl_mult"]
        tp_atr_mult = engine_result["tp_mult"]
        consensus_dir = engine_result["direction"]

        if consensus_dir == "long":
            risk_dist = atr_4h * sl_atr_mult
            sl = price - risk_dist
            tp = price + atr_4h * tp_atr_mult
        elif consensus_dir == "short":
            risk_dist = atr_4h * sl_atr_mult
            sl = price + risk_dist
            tp = price - atr_4h * tp_atr_mult
        else:
            risk_dist = atr_4h * sl_atr_mult
            sl = price - risk_dist
            tp = price + atr_4h * tp_atr_mult

        signal_details.append(f"🧬动态SL/TP(SL:{sl_atr_mult:.1f}x TP:{tp_atr_mult:.1f}x)")

        mc_params = monte_carlo.get_best_params()
        mc_kelly = mc_params.get("kelly_fraction", 0.5)
        mc_max_risk = mc_params.get("max_risk_per_trade", 0.02)
        mc_max_pos = mc_params.get("max_position_pct", 0.20)
        mc_dd_trigger = mc_params.get("drawdown_reduce_trigger", 0.06)
        mc_dd_factor = mc_params.get("drawdown_reduce_factor", 0.5)

        consensus_count = engine_result.get("consensus", 0)
        if consensus_count >= 5:
            risk_per_trade = mc_max_risk * 1.2
        elif consensus_count >= 4:
            risk_per_trade = mc_max_risk
        else:
            risk_per_trade = mc_max_risk * 0.5

        risk_per_trade *= mc_kelly

        bt_status = TitanState.backtest_result or {}
        current_dd = abs(bt_status.get("drawdown", 0)) / 100 if bt_status.get("drawdown") else 0
        if current_dd > mc_dd_trigger:
            risk_per_trade *= mc_dd_factor
            signal_details.append(f"⚠回撤{current_dd:.1%}→缩仓{mc_dd_factor:.0%}")

        max_loss_usd = CONFIG['ACCOUNT_SIZE'] * risk_per_trade
        sl_distance_pct = risk_dist / price if price > 0 else 0.02
        pos_val = max_loss_usd / (sl_distance_pct + 1e-10)
        pos_val = min(pos_val, CONFIG['ACCOUNT_SIZE'] * mc_max_pos)

        signal_details.append(f"💰资管(K:{mc_kelly:.0%} R:{risk_per_trade:.2%})")

        ml_pred = ml_engine.predict(d1h, d4h)
        blend_info = {"mode": "rules_only", "w_rule": 1.0, "w_ml": 0.0, "agreement": True, "reason": "ML无预测"}
        if ml_pred["confidence"] > 0:
            original_score = score
            score, blend_info = TitanMLEngine.blend_scores(score, ml_pred, symbol=None, price=price)
            if not blend_info.get("agreement"):
                signal_details.append(f"⚠ML方向冲突({blend_info['reason']})")
            elif ml_pred["label"] == "看涨" and ml_pred["confidence"] > 60:
                signal_details.append(f"ML看涨({ml_pred['confidence']}%)")
            elif ml_pred["label"] == "看跌" and ml_pred["confidence"] > 60:
                signal_details.append(f"ML看跌({ml_pred['confidence']}%)")
            w_info = f"R{int(blend_info['w_rule']*100)}:M{int(blend_info['w_ml']*100)}"
            signal_details.append(f"[{w_info}]")

        ml_pred["blend_info"] = blend_info

        ml_direction_tag = ml_pred.get("label", "横盘") if ml_pred.get("confidence", 0) > 0 else "neutral"
        ml_conf_val = ml_pred.get("confidence", 0)

        ml_score_adj = 0
        if ml_conf_val > 85 and ml_direction_tag == "看涨":
            ml_score_adj = -8
        elif ml_conf_val > 70 and ml_direction_tag == "看涨":
            ml_score_adj = -5

        if ml_score_adj != 0:
            score += ml_score_adj
            signal_details.append(f"ML防守{ml_score_adj}(conf={ml_conf_val:.0f}%)")

        ml_pred["ml_score_adj"] = ml_score_adj
        ml_pred["ml_direction_used"] = ml_direction_tag
        ml_pred["ml_conf_used"] = ml_conf_val

        direction = "long" if score >= 50 else "short"
        veto = TitanBrain.check_onchain_veto(ext_features, direction)
        if veto["veto"]:
            if direction == "long" and score >= 60:
                score = min(score, 55)
                signal_details.append(f"🚫链上否决({veto['reason'][:20]})")
                TitanState.add_log("warn", f"链上一票否决权触发: {veto['reason']}")
            elif direction == "short" and score <= 40:
                score = max(score, 45)
                signal_details.append(f"🚫链上否决做空({veto['reason'][:20]})")

        ml_pred["onchain_veto"] = veto

        ml_pred["scoring_engine"] = {
            "consensus": engine_result.get("consensus"),
            "bullish": engine_result.get("bullish_count"),
            "bearish": engine_result.get("bearish_count"),
            "neutral": engine_result.get("neutral_count"),
            "direction": consensus_dir,
            "ai_verdict": engine_result.get("ai_verdict"),
            "dimensions": [{"name": d.name, "direction": d.direction, "score": d.score, "rationale": d.rationale} for d in engine_result.get("dimensions", [])],
        }

        smart_advice = TitanBrain.generate_smart_advice(
            score, daily_trend, strategy_type, ml_pred, rsi_1h, tech_report
        )

        mc_tp1_atr = mc_params.get("tp_tier1_atr", 1.0)
        mc_tp2_atr = mc_params.get("tp_tier2_atr", 2.0)
        mc_tp1_pct = mc_params.get("tp_tier1_pct", 0.3)
        mc_tp2_pct = mc_params.get("tp_tier2_pct", 0.3)
        tp_tier1 = price + atr_4h * mc_tp1_atr
        tp_tier2 = price + atr_4h * mc_tp2_atr
        if mc_params.get("tp_tier1_atr") and smart_advice.get("advice"):
            smart_advice["tp_tiers"] = {
                "tier1": {"price": round(tp_tier1, 2), "pct": round(mc_tp1_pct * 100), "atr": round(mc_tp1_atr, 2)},
                "tier2": {"price": round(tp_tier2, 2), "pct": round(mc_tp2_pct * 100), "atr": round(mc_tp2_atr, 2)},
                "trail": {"pct": round((1 - mc_tp1_pct - mc_tp2_pct) * 100), "atr": round(mc_params.get("tp_trail_atr", 1.0), 2)},
            }

        try:
            strat_result = strategy_router.analyze_all(d1h, d4h, regime.get("type"))
            rec = strat_result.get("recommended", {})
            if rec.get("signal") not in ("观望", None) and rec.get("confidence", 0) > 50:
                strat_name = rec.get("strategy", "")
                strat_dir = rec.get("direction", "")
                strat_conf = rec.get("confidence", 0)
                signal_details.append(f"💡{strat_name}:{strat_dir}({strat_conf}%)")
            ml_pred["strategy_analysis"] = strat_result
        except Exception:
            pass

        note_str = f"[{strategy_type}|{regime['type']}|共识{engine_result.get('consensus', 0)}/6] " + " ".join(signal_details)
        return score, price, sl, tp, pos_val, note_str, "ACTIVE", tech_report, ml_pred, daily_trend, smart_advice, regime

    @staticmethod
    def generate_smart_advice(score, daily_trend, strategy_type, ml_pred, rsi_1h, tech_report):
        d_dir = daily_trend.get("direction", "未知")
        d_strength = daily_trend.get("strength", "弱")
        d_rsi = daily_trend.get("rsi", 50)
        ml_label = ml_pred.get("label", "横盘") if ml_pred.get("confidence", 0) > 0 else "无"
        ml_conf = ml_pred.get("confidence", 0)
        wave = tech_report.get("wave", "") if tech_report else ""
        candle = tech_report.get("candle", "") if tech_report else ""
        rsi_val = float(rsi_1h) if not pd.isna(rsi_1h) else 50

        daily_bull = d_dir in ("强势上涨", "上涨回踩")
        daily_bear = d_dir in ("强势下跌", "下跌反弹")
        ml_bull = ml_label == "看涨" and ml_conf >= 60
        ml_bear = ml_label == "看跌" and ml_conf >= 60
        rsi_oversold = rsi_val < 30
        rsi_overbought = rsi_val > 70
        has_bullish_pattern = any(k in candle for k in ("看涨吞没", "锤子线")) if candle else False
        has_bearish_pattern = any(k in candle for k in ("看跌吞没", "射击之星")) if candle else False
        wave_up = "上升" in wave if wave else False
        wave_down = "下降" in wave if wave else False

        if score >= 70 and daily_bull and ml_bull:
            icon = "🟢"
            advice = "强烈做多"
            reason = f"日线{d_dir}+ML看涨{ml_conf}%+高评分{score}"
        elif score >= 70 and daily_bull:
            icon = "🟢"
            advice = "顺势做多"
            reason = f"日线{d_dir}+评分{score}"
        elif score >= 70 and ml_bull and not daily_bear:
            icon = "🟢"
            advice = "积极做多"
            reason = f"ML看涨{ml_conf}%+高评分{score}"
        elif daily_bull and rsi_oversold:
            icon = "🟡"
            advice = "逢低布局"
            reason = f"日线{d_dir}但RSI超卖{int(rsi_val)}"
        elif daily_bull and ml_bull:
            icon = "🟢"
            advice = "顺势关注"
            reason = f"日线+ML共振看涨"
        elif daily_bull and score >= 60:
            icon = "🟡"
            advice = "等待回踩做多"
            reason = f"日线多头+评分{score}"
        elif daily_bear and ml_bear:
            icon = "🔴"
            advice = "强烈回避"
            reason = f"日线{d_dir}+ML看跌{ml_conf}%"
        elif daily_bear and rsi_overbought:
            icon = "🔴"
            advice = "反弹出货"
            reason = f"空头趋势+RSI超买{int(rsi_val)}"
        elif daily_bear and rsi_oversold and has_bullish_pattern:
            icon = "🟡"
            advice = "超跌反弹关注"
            reason = f"空头超卖+{candle}"
        elif daily_bear and rsi_oversold:
            icon = "🟡"
            advice = "等待企稳"
            reason = f"空头超卖RSI{int(rsi_val)}，勿抄底"
        elif daily_bear:
            icon = "🔴"
            advice = "回避观望"
            reason = f"日线{d_dir}"
        elif ml_bull and rsi_oversold:
            icon = "🟡"
            advice = "逢低试探"
            reason = f"ML看涨+RSI超卖"
        elif ml_bear and rsi_overbought:
            icon = "🔴"
            advice = "高位警惕"
            reason = f"ML看跌+RSI超买"
        elif strategy_type == "趋势" and score >= 60:
            icon = "🟡"
            advice = "趋势跟随"
            reason = f"4H趋势明确+评分{score}"
        elif strategy_type == "震荡" and rsi_oversold:
            icon = "🟡"
            advice = "区间低吸"
            reason = f"震荡区间+RSI超卖"
        elif strategy_type == "震荡" and rsi_overbought:
            icon = "🟡"
            advice = "区间高抛"
            reason = f"震荡区间+RSI超买"
        else:
            icon = "⚪"
            advice = "观望等待"
            reason = "信号不明确"

        return {
            "icon": icon,
            "advice": advice,
            "reason": reason,
        }


class TitanMailer:
    @staticmethod
    def get_receivers():
        receivers = []
        r1 = os.getenv('RECEIVER_EMAIL')
        r2 = os.getenv('RECEIVER_EMAIL_2')
        if r1:
            receivers.append(r1)
        if r2:
            receivers.append(r2)
        return receivers

    @staticmethod
    def send_report(alpha_signals, market_info, ml_status):
        sender = os.getenv('SENDER_EMAIL')
        password = os.getenv('SENDER_PASSWORD')
        receivers = TitanMailer.get_receivers()
        if not sender or not password or not receivers:
            logging.getLogger("Titan").warning("邮件配置缺失，跳过发送")
            return False

        tz = pytz.timezone(CONFIG['TIMEZONE'])
        now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
        btc = market_info.get('btc', {})
        fng = market_info.get('fng', {})

        rows = ""
        for i, sig in enumerate(alpha_signals):
            ml = sig.get('ml', {})
            ml_label = ml.get('label', '-')
            ml_conf = ml.get('confidence', 0)
            ml_color = "#10b981" if ml_label == "看涨" else ("#ef4444" if ml_label == "看跌" else "#f59e0b")
            adv = sig.get('advice', {})
            adv_text = adv.get('advice', '-')
            adv_reason = adv.get('reason', '')
            adv_color = "#10b981" if adv.get('icon') == '🟢' else ("#ef4444" if adv.get('icon') == '🔴' else "#f59e0b")
            daily_dir = sig.get('daily', {}).get('direction', '-')
            rows += f"""
            <tr style="text-align:center; font-size:11px; border-bottom:1px solid #f1f5f9;">
                <td style="padding:10px 4px; color:#94a3b8;">{i+1}</td>
                <td style="font-weight:800; color:#1e293b;">{sig['symbol']}</td>
                <td style="color:#6366f1; font-weight:900;">{sig['score']}</td>
                <td style="font-weight:bold;">${sig['price']}</td>
                <td style="color:#ef4444;">{sig['sl']}</td>
                <td style="color:#10b981;">{sig['tp']}</td>
                <td style="color:{ml_color}; font-weight:900;">{ml_label} {ml_conf}%</td>
                <td style="font-size:10px; color:#64748b;">{daily_dir}</td>
                <td style="color:{adv_color}; font-weight:900; font-size:10px;">{adv_text}</td>
            </tr>"""

        ml_info = ""
        if ml_status.get('is_trained'):
            ml_info = f"""
            <div style="display:flex; gap:10px; margin-bottom:20px;">
                <div style="flex:1; background:#f0fdf4; padding:12px; border-radius:8px; text-align:center;">
                    <div style="font-size:9px; color:#94a3b8; font-weight:700;">ML准确率</div>
                    <div style="font-size:16px; font-weight:900; color:#10b981;">{ml_status.get('accuracy',0)}%</div>
                </div>
                <div style="flex:1; background:#eff6ff; padding:12px; border-radius:8px; text-align:center;">
                    <div style="font-size:9px; color:#94a3b8; font-weight:700;">F1分数</div>
                    <div style="font-size:16px; font-weight:900; color:#3b82f6;">{ml_status.get('f1',0)}%</div>
                </div>
                <div style="flex:1; background:#faf5ff; padding:12px; border-radius:8px; text-align:center;">
                    <div style="font-size:9px; color:#94a3b8; font-weight:700;">模型版本</div>
                    <div style="font-size:16px; font-weight:900; color:#8b5cf6;">{ml_status.get('model_version','N/A')}</div>
                </div>
            </div>"""

        body = f"""
        <html>
        <body style="margin:0; padding:20px; background-color:#f1f5f9; font-family:sans-serif;">
            <div style="max-width:780px; margin:auto; background:#fff; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
                <div style="background:linear-gradient(135deg,#1e3a8a,#7c3aed); padding:28px; color:#fff;">
                    <div style="font-size:10px; font-weight:800; letter-spacing:2px; color:#fbbf24; margin-bottom:6px;">TITAN V17.1 | RF ML ENHANCED</div>
                    <h1 style="margin:0; font-size:22px; font-weight:900;">Alpha信号报告 | {len(alpha_signals)} 个强信号</h1>
                </div>
                <div style="padding:25px;">
                    <div style="display:flex; gap:12px; margin-bottom:20px;">
                        <div style="flex:1; background:#f8fafc; padding:14px; border-radius:8px; border:1px solid #f1f5f9; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">BTC</div>
                            <div style="font-size:18px; font-weight:900; color:#1e293b;">${btc.get('price','N/A')}</div>
                            <div style="font-size:11px; color:{'#10b981' if str(btc.get('change','')).startswith('+') or (isinstance(btc.get('change',''),str) and not btc.get('change','').startswith('-')) else '#ef4444'};">{btc.get('change','')}</div>
                        </div>
                        <div style="flex:1; background:#f8fafc; padding:14px; border-radius:8px; border:1px solid #f1f5f9; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">恐惧贪婪指数</div>
                            <div style="font-size:18px; font-weight:900; color:#f59e0b;">{fng.get('value','N/A')} ({fng.get('label','N/A')})</div>
                        </div>
                        <div style="flex:1; background:#f8fafc; padding:14px; border-radius:8px; border:1px solid #f1f5f9; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">扫描标的</div>
                            <div style="font-size:18px; font-weight:900; color:#6366f1;">{market_info.get('total_scanned', 100)}</div>
                        </div>
                    </div>
                    {ml_info}
                    <table style="width:100%; border-collapse:collapse;">
                        <thead>
                            <tr style="background:#1e293b; color:#fff; font-size:10px;">
                                <th style="padding:10px;">#</th><th>资产</th><th>评分</th><th>价格</th><th>止损</th><th>目标</th><th>ML预测</th><th>日线</th><th>AI研判</th>
                            </tr>
                        </thead>
                        <tbody>{rows if alpha_signals else "<tr><td colspan='9' style='padding:40px; text-align:center; color:#94a3b8;'>当前无Alpha信号 (评分≥80)</td></tr>"}</tbody>
                    </table>
                </div>
                <div style="background:#f8fafc; padding:14px; text-align:center; font-size:10px; color:#cbd5e1; border-top:1px solid #f1f5f9;">
                    {now_str} | Titan V17.1 动态猎场 | RandomForest ML + 技术分析混合决策
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html', 'utf-8')
        count = len(alpha_signals)
        msg['Subject'] = Header(f"Titan Alpha报告 | {count}个信号 | {now_str}", 'utf-8')
        msg['From'] = sender
        msg['To'] = ', '.join(receivers)
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, receivers, msg.as_string())
            logging.getLogger("Titan").info(f"邮件报告已发送至 {len(receivers)} 个收件人")
            return True
        except Exception as e:
            logging.getLogger("Titan").error(f"邮件发送失败: {e}")
            return False


    @staticmethod
    def send_daily_report(cruise_data, market_info, ml_status):
        sender = os.getenv('SENDER_EMAIL')
        password = os.getenv('SENDER_PASSWORD')
        receivers = TitanMailer.get_receivers()
        if not sender or not password or not receivers:
            logging.getLogger("Titan").warning("邮件配置缺失，跳过每日报告")
            return False

        tz = pytz.timezone(CONFIG['TIMEZONE'])
        now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')
        date_str = datetime.now(tz).strftime('%Y-%m-%d')
        btc = market_info.get('btc', {})
        fng = market_info.get('fng', {})

        bullish = [c for c in cruise_data if c.get('daily', {}).get('direction') in ('强势上涨', '上涨回踩')]
        bearish = [c for c in cruise_data if c.get('daily', {}).get('direction') in ('强势下跌', '下跌反弹')]
        ranging = [c for c in cruise_data if c.get('daily', {}).get('direction') == '震荡']
        alpha = [c for c in cruise_data if c['score'] >= 80]
        watch = [c for c in cruise_data if 70 <= c['score'] < 80]

        def make_trend_row(item, idx):
            d = item.get('daily', {})
            ml = item.get('ml', {})
            adv = item.get('advice', {})
            ml_label = ml.get('label', '-')
            ml_conf = ml.get('confidence', 0)
            dir_color = "#10b981" if d.get('direction', '') in ('强势上涨', '上涨回踩') else ("#ef4444" if d.get('direction', '') in ('强势下跌', '下跌反弹') else "#f59e0b")
            ml_color = "#10b981" if ml_label == "看涨" else ("#ef4444" if ml_label == "看跌" else "#94a3b8")
            adv_color = "#10b981" if adv.get('icon') == '🟢' else ("#ef4444" if adv.get('icon') == '🔴' else "#f59e0b")
            c5 = d.get('change_5d', 0)
            c20 = d.get('change_20d', 0)
            c5_color = "#10b981" if c5 > 0 else "#ef4444"
            c20_color = "#10b981" if c20 > 0 else "#ef4444"
            return f"""
            <tr style="text-align:center; font-size:11px; border-bottom:1px solid #f1f5f9;">
                <td style="padding:8px 4px; color:#94a3b8;">{idx+1}</td>
                <td style="font-weight:800; color:#1e293b;">{item['symbol']}</td>
                <td style="font-weight:bold;">${item['price']}</td>
                <td style="color:#6366f1; font-weight:900;">{item['score']}</td>
                <td style="color:{dir_color}; font-weight:700;">{d.get('direction', '-')}</td>
                <td style="color:{c5_color}; font-weight:600;">{c5:+.1f}%</td>
                <td style="color:{c20_color}; font-weight:600;">{c20:+.1f}%</td>
                <td style="color:{adv_color}; font-weight:900; font-size:10px;">{adv.get('advice', '-')}</td>
            </tr>"""

        bullish_rows = "".join([make_trend_row(c, i) for i, c in enumerate(sorted(bullish, key=lambda x: x['score'], reverse=True)[:20])])
        bearish_rows = "".join([make_trend_row(c, i) for i, c in enumerate(sorted(bearish, key=lambda x: x['score'])[:20])])
        alpha_rows = "".join([make_trend_row(c, i) for i, c in enumerate(sorted(alpha, key=lambda x: x['score'], reverse=True))])

        def make_section(title, color, rows, count):
            if not rows:
                return f'<div style="margin-bottom:20px;"><h3 style="color:{color}; font-size:14px; margin:0 0 8px;">{title} (0)</h3><p style="color:#94a3b8; font-size:12px;">暂无</p></div>'
            return f"""
            <div style="margin-bottom:20px;">
                <h3 style="color:{color}; font-size:14px; margin:0 0 8px;">{title} ({count})</h3>
                <table style="width:100%; border-collapse:collapse;">
                    <thead><tr style="background:#1e293b; color:#fff; font-size:10px;">
                        <th style="padding:8px;">#</th><th>资产</th><th>价格</th><th>评分</th><th>日线方向</th><th>5日</th><th>20日</th><th>AI研判</th>
                    </tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>"""

        ml_info = ""
        if ml_status.get('is_trained'):
            ml_info = f"""
            <div style="display:flex; gap:10px; margin-bottom:20px;">
                <div style="flex:1; background:#f0fdf4; padding:12px; border-radius:8px; text-align:center;">
                    <div style="font-size:9px; color:#94a3b8; font-weight:700;">ML准确率</div>
                    <div style="font-size:16px; font-weight:900; color:#10b981;">{ml_status.get('accuracy',0)}%</div>
                </div>
                <div style="flex:1; background:#eff6ff; padding:12px; border-radius:8px; text-align:center;">
                    <div style="font-size:9px; color:#94a3b8; font-weight:700;">F1分数</div>
                    <div style="font-size:16px; font-weight:900; color:#3b82f6;">{ml_status.get('f1',0)}%</div>
                </div>
                <div style="flex:1; background:#faf5ff; padding:12px; border-radius:8px; text-align:center;">
                    <div style="font-size:9px; color:#94a3b8; font-weight:700;">训练样本</div>
                    <div style="font-size:16px; font-weight:900; color:#8b5cf6;">{ml_status.get('total_samples','N/A')}</div>
                </div>
            </div>"""

        body = f"""
        <html>
        <body style="margin:0; padding:20px; background-color:#f1f5f9; font-family:sans-serif;">
            <div style="max-width:800px; margin:auto; background:#fff; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
                <div style="background:linear-gradient(135deg,#0f172a,#1e3a8a); padding:28px; color:#fff;">
                    <div style="font-size:10px; font-weight:800; letter-spacing:2px; color:#fbbf24; margin-bottom:6px;">TITAN {CONFIG['VERSION']} | 每日市场分析报告</div>
                    <h1 style="margin:0; font-size:22px; font-weight:900;">📊 {date_str} 日线收盘分析</h1>
                    <p style="margin:6px 0 0; font-size:12px; color:#93c5fd;">扫描 {len(cruise_data)} 个标的 | 多头 {len(bullish)} | 空头 {len(bearish)} | 震荡 {len(ranging)} | Alpha信号 {len(alpha)}</p>
                </div>
                <div style="padding:25px;">
                    <div style="display:flex; gap:12px; margin-bottom:20px;">
                        <div style="flex:1; background:#f8fafc; padding:14px; border-radius:8px; border:1px solid #f1f5f9; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">BTC</div>
                            <div style="font-size:18px; font-weight:900; color:#1e293b;">${btc.get('price','N/A')}</div>
                            <div style="font-size:11px; color:{'#10b981' if str(btc.get('change','')).startswith('+') or (isinstance(btc.get('change',''),str) and not btc.get('change','').startswith('-')) else '#ef4444'};">{btc.get('change','')}</div>
                        </div>
                        <div style="flex:1; background:#f8fafc; padding:14px; border-radius:8px; border:1px solid #f1f5f9; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">恐惧贪婪指数</div>
                            <div style="font-size:18px; font-weight:900; color:#f59e0b;">{fng.get('value','N/A')} ({fng.get('label','N/A')})</div>
                        </div>
                        <div style="flex:1; background:#f0fdf4; padding:14px; border-radius:8px; border:1px solid #dcfce7; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">多头趋势</div>
                            <div style="font-size:18px; font-weight:900; color:#10b981;">{len(bullish)}</div>
                        </div>
                        <div style="flex:1; background:#fef2f2; padding:14px; border-radius:8px; border:1px solid #fecaca; text-align:center;">
                            <div style="font-size:9px; color:#94a3b8; font-weight:700;">空头趋势</div>
                            <div style="font-size:18px; font-weight:900; color:#ef4444;">{len(bearish)}</div>
                        </div>
                    </div>
                    {ml_info}
                    {make_section("🚀 Alpha信号 (评分≥80)", "#6366f1", alpha_rows, len(alpha))}
                    {make_section("📈 日线多头趋势 (Top 20)", "#10b981", bullish_rows, len(bullish))}
                    {make_section("📉 日线空头趋势 (Top 20)", "#ef4444", bearish_rows, len(bearish))}
                </div>
                <div style="background:#f8fafc; padding:14px; text-align:center; font-size:10px; color:#cbd5e1; border-top:1px solid #f1f5f9;">
                    {now_str} | Titan {CONFIG['VERSION']} 动态猎场 | 每日日线收盘分析报告
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html', 'utf-8')
        msg['Subject'] = Header(f"Titan每日报告 | {date_str} | 多头{len(bullish)} 空头{len(bearish)} Alpha{len(alpha)}", 'utf-8')
        msg['From'] = sender
        msg['To'] = ', '.join(receivers)
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, receivers, msg.as_string())
            logging.getLogger("Titan").info(f"每日分析报告已发送至 {len(receivers)} 个收件人")
            return True
        except Exception as e:
            logging.getLogger("Titan").error(f"每日报告发送失败: {e}")
            return False


    _last_emergency_email_time = 0

    @staticmethod
    def send_cto_alert(alert_type, summary, details, auto_actions, coordinator_recs=None):
        sender = os.getenv('SENDER_EMAIL')
        password = os.getenv('SENDER_PASSWORD')
        receivers = TitanMailer.get_receivers()
        if not sender or not password or not receivers:
            logging.getLogger("Titan").warning("邮件配置缺失，跳过CTO预警")
            return False

        now_ts = time.time()
        if now_ts - TitanMailer._last_emergency_email_time < 7200:
            logging.getLogger("Titan").info("CTO预警冷却中(2小时间隔)")
            return False

        tz = pytz.timezone(CONFIG['TIMEZONE'])
        now_str = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

        severity_colors = {
            "critical": ("#dc2626", "#fef2f2", "🚨 紧急"),
            "warning": ("#f59e0b", "#fffbeb", "⚠️ 警告"),
            "info": ("#3b82f6", "#eff6ff", "ℹ️ 通知"),
        }
        color, bg, label = severity_colors.get(alert_type, severity_colors["warning"])

        details_html = ""
        for d in details[:8]:
            details_html += f'<div style="padding:8px 12px; border-left:3px solid {color}; background:{bg}; margin-bottom:6px; font-size:12px; color:#1e293b; border-radius:0 6px 6px 0;">{d}</div>'

        actions_html = ""
        for a in auto_actions[:6]:
            status_icon = "✅" if a.get("applied") else "⏳"
            actions_html += f'<div style="padding:8px 12px; background:#f0fdf4; border-left:3px solid #10b981; margin-bottom:6px; font-size:12px; border-radius:0 6px 6px 0;">{status_icon} {a.get("action", "")}</div>'

        recs_html = ""
        if coordinator_recs:
            recs_html = f"""
            <div style="margin-top:16px; padding:14px; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
                <div style="font-size:11px; font-weight:800; color:#64748b; margin-bottom:8px;">📊 CTO当前推荐参数</div>
                <div style="display:flex; gap:8px; flex-wrap:wrap;">
                    <div style="flex:1; min-width:80px; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                        <div style="font-size:9px; color:#94a3b8;">仓位乘数</div>
                        <div style="font-size:16px; font-weight:900; color:#6366f1;">{coordinator_recs.get('size_multiplier', 'N/A')}</div>
                    </div>
                    <div style="flex:1; min-width:80px; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                        <div style="font-size:9px; color:#94a3b8;">油门</div>
                        <div style="font-size:16px; font-weight:900; color:#f59e0b;">{coordinator_recs.get('throttle_level', 'N/A')}</div>
                    </div>
                    <div style="flex:1; min-width:80px; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                        <div style="font-size:9px; color:#94a3b8;">偏向</div>
                        <div style="font-size:16px; font-weight:900; color:#1e293b;">{coordinator_recs.get('regime_bias', 'N/A')}</div>
                    </div>
                    <div style="flex:1; min-width:80px; text-align:center; padding:8px; background:#fff; border-radius:6px;">
                        <div style="font-size:9px; color:#94a3b8;">风险</div>
                        <div style="font-size:16px; font-weight:900; color:#dc2626;">{coordinator_recs.get('risk_level', 'N/A')}</div>
                    </div>
                </div>
                <div style="margin-top:8px; font-size:11px; color:#64748b;">{coordinator_recs.get('reasoning', '')[:200]}</div>
            </div>"""

        body = f"""
        <html>
        <body style="margin:0; padding:20px; background-color:#f1f5f9; font-family:sans-serif;">
            <div style="max-width:680px; margin:auto; background:#fff; border-radius:12px; overflow:hidden; border:2px solid {color}; box-shadow:0 4px 20px rgba(0,0,0,0.1);">
                <div style="background:linear-gradient(135deg,{color},#1e293b); padding:24px; color:#fff;">
                    <div style="font-size:10px; font-weight:800; letter-spacing:2px; color:#fbbf24; margin-bottom:4px;">神盾计划 | AI CTO 预警系统</div>
                    <h1 style="margin:0; font-size:20px; font-weight:900;">{label} {summary}</h1>
                    <p style="margin:6px 0 0; font-size:11px; color:#cbd5e1;">{now_str} | 自动检测 & 自动应对</p>
                </div>
                <div style="padding:20px;">
                    <div style="margin-bottom:16px;">
                        <div style="font-size:12px; font-weight:800; color:#1e293b; margin-bottom:8px;">🔍 检测到的问题</div>
                        {details_html}
                    </div>
                    <div style="margin-bottom:16px;">
                        <div style="font-size:12px; font-weight:800; color:#1e293b; margin-bottom:8px;">🛡️ 系统已自动执行</div>
                        {actions_html if actions_html else '<div style="padding:8px; color:#94a3b8; font-size:12px;">无自动操作</div>'}
                    </div>
                    {recs_html}
                    <div style="margin-top:16px; padding:12px; background:#fef3c7; border-radius:8px; border:1px solid #fcd34d;">
                        <div style="font-size:11px; color:#92400e; font-weight:700;">💡 CTO建议：请在方便时登录仪表盘查看详情，系统已自动采取保护措施，暂无需手动干预。</div>
                    </div>
                </div>
                <div style="background:#f8fafc; padding:12px; text-align:center; font-size:10px; color:#94a3b8; border-top:1px solid #e2e8f0;">
                    神盾计划：不死量化 | AI CTO 7×24小时值守 | 每2小时最多1封预警
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html', 'utf-8')
        msg['Subject'] = Header(f"[神盾CTO预警] {label} {summary[:50]} | {now_str}", 'utf-8')
        msg['From'] = sender
        msg['To'] = ', '.join(receivers)
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, receivers, msg.as_string())
            TitanMailer._last_emergency_email_time = now_ts
            logging.getLogger("Titan").info(f"CTO预警邮件已发送: {alert_type} - {summary[:60]}")
            return True
        except Exception as e:
            logging.getLogger("Titan").error(f"CTO预警邮件发送失败: {e}")
            return False

    @staticmethod
    def ai_generate_summary(alpha_signals, market_info, ml_status, paper_portfolio):
        try:
            from server.titan_llm_client import chat
            from server.titan_prompt_library import CEO_REPORT_PROMPT
            btc = market_info.get("btc", {})
            fng = market_info.get("fng", {})
            prompt = (
                f"数据：\n"
                f"- Alpha信号数量: {len(alpha_signals) if alpha_signals else 0}\n"
                f"- BTC价格: ${btc.get('price', 'N/A')}, 涨跌: {btc.get('change', 'N/A')}\n"
                f"- 恐惧贪婪指数: {fng.get('value', 'N/A')} ({fng.get('label', 'N/A')})\n"
                f"- ML准确率: {ml_status.get('accuracy', 0)}%, F1: {ml_status.get('f1', 0)}%, 已训练: {ml_status.get('is_trained', False)}\n"
                f"- 模拟组合: 持仓数{paper_portfolio.get('active_positions', 0)}, "
                f"总收益: {paper_portfolio.get('total_pnl', 0)}, 胜率: {paper_portfolio.get('win_rate', 0)}%\n"
                f"- 前3个信号: {', '.join([s.get('symbol','?') + '(' + str(s.get('score',0)) + ')' for s in (alpha_signals or [])[:3]])}\n\n"
                f"请给出：1) 一句话市场总结 2) 当前风险评估 3) 三个可操作建议"
            )
            content = chat(
                module="api_ceo_report",
                messages=[{"role": "system", "content": CEO_REPORT_PROMPT},
                          {"role": "user", "content": prompt}],
                json_mode=False,
                max_tokens=16000,
            )
            return content.strip() if content else "AI摘要生成中..."
        except Exception as e:
            return f"AI摘要生成失败: {str(e)[:50]}"


class TitanCommander:
    def __init__(self):
        self.exchange = ccxt.gateio({'enableRateLimit': True})
        self.swap_exchange = ccxt.gateio({'enableRateLimit': True, 'options': {'defaultType': 'swap'}})
        self.logger = logging.getLogger("Titan")
        self._last_training_data = {}
        self._last_email_time = 0
        self._daily_report_sent_date = None
        self._last_deep_evolution_hour = -1
        self._last_diag_hour = -1
        self._last_agi_reflect_hour = -1
        self._last_comprehensive_optimize_date = None
        self._emergency_optimize_triggered_today = None
        self._last_cto_briefing_hour = -1
        self._last_cto_briefing_date = None
        self._last_weekly_full_pipeline_week = None
        self._derivatives_cache = {}
        self._fetch_count = 0
        self._signal_cooldowns = {}
        self.REJECTED_COOLDOWN_MINUTES = 20
        self.NO_SIGNAL_COOLDOWN_MINUTES = 10

    async def fetch_matrix(self, sym):
        try:
            tasks = [self.exchange.fetch_ohlcv(sym, tf, limit=100) for tf in ['15m', '1h', '4h', '1d']]
            res = await asyncio.gather(*tasks, return_exceptions=True)
            if any(isinstance(r, Exception) for r in res):
                return None
            return {tf: pd.DataFrame(d, columns=['t', 'o', 'h', 'l', 'c', 'v']) for tf, d in zip(['15m', '1h', '4h', '1d'], res)}
        except Exception:
            return None

    async def fetch_derivatives(self, symbols):
        cache = {}
        try:
            import requests as req
            r = req.get('https://api.gateio.ws/api/v4/futures/usdt/tickers', timeout=10)
            tickers = r.json()
            ticker_map = {}
            for t in tickers:
                contract = t.get('contract', '')
                base = contract.replace('_USDT', '')
                ticker_map[base] = t
            contracts_r = req.get('https://api.gateio.ws/api/v4/futures/usdt/contracts', timeout=10)
            contracts = contracts_r.json()
            quanto_map = {}
            for c in contracts:
                name = c.get('name', '').replace('_USDT', '')
                quanto_map[name] = float(c.get('quanto_multiplier', 1) or 1)
            for asset in symbols[:20]:
                t = ticker_map.get(asset, {})
                funding_rate = float(t.get('funding_rate', 0) or 0)
                total_size = float(t.get('total_size', 0) or 0)
                mark_price = float(t.get('mark_price', 0) or 0)
                quanto = quanto_map.get(asset, 1)
                oi_value = total_size * quanto * mark_price
                cache[asset] = {
                    'funding_rate': round(funding_rate * 100, 4),
                    'open_interest': round(oi_value, 2)
                }
        except Exception as e:
            self.logger.warning(f"衍生品数据获取部分失败: {e}")
        self._derivatives_cache = cache
        return cache

    def _is_junk(self, symbol: str) -> bool:
        base = symbol.split('/')[0] if '/' in symbol else symbol
        if base in CONFIG['STABLECOIN_BLACKLIST']:
            return True
        if base in CONFIG.get('ASSET_BLACKLIST', set()):
            return True
        for suffix in CONFIG['JUNK_SUFFIXES']:
            if base.endswith(suffix):
                return True
        return False

    async def fetch_dynamic_universe(self):
        core_watchlist = list(CONFIG['CORE_WATCHLIST'])
        core_set = set(core_watchlist)
        try:
            print("[SCAN] 核心关注清单优先模式: 锁定80个指定标的...", flush=True)
            tickers = await asyncio.wait_for(self.exchange.fetch_tickers(), timeout=30)
            print(f"[SCAN] 获取到 {len(tickers)} 个交易对行情", flush=True)

            ticker_cache = {}
            for sym, ticker in tickers.items():
                if sym.endswith('/USDT'):
                    base = sym.split('/')[0]
                    ticker_cache[base] = {
                        'change_24h': float(ticker.get('percentage', 0) or 0),
                        'volume_24h': float(ticker.get('quoteVolume', 0) or 0),
                        'high_24h': float(ticker.get('high', 0) or 0),
                        'low_24h': float(ticker.get('low', 0) or 0),
                    }
            TitanState.market_snapshot['_ticker_cache'] = ticker_cache

            available_core = []
            unavailable_core = []
            for asset in core_watchlist:
                sym = f"{asset}/USDT"
                if sym in tickers:
                    available_core.append(asset)
                else:
                    unavailable_core.append(asset)

            if unavailable_core:
                print(f"[SCAN] 核心清单中 {len(unavailable_core)} 个标的在交易所无交易对: {unavailable_core[:10]}...", flush=True)

            supplement = []
            sup_limit = CONFIG.get('DYNAMIC_SUPPLEMENT_LIMIT', 20)
            usdt_pairs = []
            for sym, ticker in tickers.items():
                if not sym.endswith('/USDT'):
                    continue
                if self._is_junk(sym):
                    continue
                base = sym.split('/')[0]
                if base in core_set:
                    continue
                if base in CONFIG['STABLECOIN_BLACKLIST']:
                    continue
                vol_usdt = float(ticker.get('quoteVolume', 0) or 0)
                if vol_usdt < CONFIG['VOLUME_MIN_USDT']:
                    continue
                usdt_pairs.append((base, vol_usdt))

            usdt_pairs.sort(key=lambda x: x[1], reverse=True)
            supplement = [p[0] for p in usdt_pairs[:sup_limit]]

            universe = available_core + supplement
            core_count = len(available_core)
            sup_count = len(supplement)

            print(f"[SCAN] 猎场构成: 核心{core_count}个 + 动态补充{sup_count}个 = 共{len(universe)}个", flush=True)
            TitanState.add_log("system", f"智能猎场: 核心{core_count} + 动态补充{sup_count} = {len(universe)}个标的")
            return universe, f"核心{core_count}+补充{sup_count}"

        except Exception as e:
            self.logger.warning(f"动态猎场失败，启用精英回退: {e}")
            TitanState.add_log("warn", f"猎场API异常，回退至核心关注清单: {str(e)[:50]}")
            return core_watchlist, "核心回退"

    def filter_correlated_signals(self, items, data_cache, threshold=0.85):
        alpha_items = [item for item in items if item['score'] >= 65]
        if len(alpha_items) < 2:
            return items

        alpha_items.sort(key=lambda x: -x['score'])
        kept_symbols = set()

        for item in alpha_items:
            sym = item['symbol']
            is_correlated = False
            for kept_sym in kept_symbols:
                kept_data = data_cache.get(kept_sym, {}).get('1h')
                new_data = data_cache.get(sym, {}).get('1h')
                if kept_data is None or new_data is None:
                    continue
                if len(kept_data) < 30 or len(new_data) < 30:
                    continue

                r1 = kept_data['c'].pct_change().dropna().tail(60)
                r2 = new_data['c'].pct_change().dropna().tail(60)
                min_len = min(len(r1), len(r2))
                if min_len < 20:
                    continue
                corr = r1.iloc[-min_len:].reset_index(drop=True).corr(r2.iloc[-min_len:].reset_index(drop=True))
                if not pd.isna(corr) and abs(corr) > threshold:
                    is_correlated = True
                    item['note'] = item.get('note', '') + f" ⚠相关性过高({kept_sym}:{corr:.2f})"
                    item['score'] = min(item['score'], 79)
                    TitanState.add_log("info", f"相关性过滤: {sym} 与 {kept_sym} 相关性{corr:.2f}, 降级至{item['score']}")
                    break

            if not is_correlated:
                kept_symbols.add(sym)

        return items

    async def run_scan_loop(self):
        self.logger.info(f"泰坦 {CONFIG['VERSION']} 动态猎场启动")
        TitanState.add_log("system", f"泰坦 {CONFIG['VERSION']} 动态猎场启动")
        print(f"[SCAN] 泰坦 {CONFIG['VERSION']} 动态猎场启动", flush=True)

        while True:
            try:
                now_bj = datetime.now(pytz.timezone('Asia/Shanghai'))
                minute = now_bj.minute
                is_hour = minute < 2
                is_quarter = minute % 15 < 2

                if is_quarter:
                    scan_tag = "1h+15m收盘" if is_hour else "15m收盘"
                else:
                    scan_tag = "常规扫描"

                self._fetch_count += 1
                print(f"[SCAN] 开始扫描周期 [{scan_tag}]...", flush=True)
                fng_data = TitanMath.get_fear_and_greed()
                fng = fng_data["value"]
                print(f"[SCAN] FNG={fng} ({fng_data['label']}), 获取BTC数据...", flush=True)
                btc_data = await self.fetch_matrix('BTC/USDT')
                print(f"[SCAN] BTC数据: {'OK' if btc_data else 'FAIL'}", flush=True)
                is_crash = False
                crash_reason = ""

                if btc_data:
                    open_p = btc_data['1h']['o'].iloc[-1]
                    close_p = btc_data['1h']['c'].iloc[-1]
                    change = (close_p - open_p) / (open_p + 1e-10)

                    change_4h = 0
                    if len(btc_data['4h']) >= 2:
                        open_4h = btc_data['4h']['o'].iloc[-1]
                        close_4h = btc_data['4h']['c'].iloc[-1]
                        change_4h = (close_4h - open_4h) / (open_4h + 1e-10)

                    if change < CONFIG['BTC_CRASH_THRESHOLD']:
                        is_crash = True
                        crash_reason = f"BTC 1H急跌{change*100:.1f}%"
                    elif change_4h < CONFIG['BTC_CRASH_THRESHOLD']:
                        is_crash = True
                        crash_reason = f"BTC 4H下跌{change_4h*100:.1f}%"

                    if is_crash:
                        TitanState.add_log("error", f"🚨 熔断触发: {crash_reason}，全局评分降级保护")

                    btc_macro_trend = "neutral"
                    btc_ma20_val = 0
                    if len(btc_data['4h']) >= 20:
                        closes_4h = btc_data['4h']['c'].values[-20:]
                        btc_ma20_val = float(closes_4h.mean())
                        ma20_prev = float(closes_4h[:-1].mean())
                        ma20_slope_neg = btc_ma20_val < ma20_prev
                        ma20_slope_pos = btc_ma20_val > ma20_prev
                        btc_current = float(btc_data['4h']['c'].iloc[-1])
                        if btc_current < btc_ma20_val and ma20_slope_neg:
                            btc_macro_trend = "bearish"
                        elif btc_current > btc_ma20_val and ma20_slope_pos:
                            btc_macro_trend = "bullish"

                    btc_current_price = float(btc_data['15m']['c'].iloc[-1])
                    TitanState.market_snapshot["btc_pulse"] = {
                        "price": round(btc_current_price, 2),
                        "change": f"{change * 100:.2f}%",
                        "change_4h": f"{change_4h * 100:.2f}%",
                        "fng": fng,
                        "fng_detail": fng_data,
                        "is_crash": is_crash,
                        "crash_reason": crash_reason,
                        "macro_trend": btc_macro_trend,
                        "ma20_4h": round(btc_ma20_val, 2),
                    }
                    print(f"[SCAN] BTC宏观趋势: {btc_macro_trend} (MA20={btc_ma20_val:.0f}, 现价={btc_current_price:.0f})", flush=True)

                print("[SCAN] 开始获取动态猎场...", flush=True)
                universe, hunt_mode = await self.fetch_dynamic_universe()
                print(f"[SCAN] 猎场完成: {len(universe)} 个标的 [{hunt_mode}]", flush=True)
                TitanState.market_snapshot["scan_mode"] = hunt_mode
                TitanState.add_log("system", f"[{scan_tag}] 开始扫描 {len(universe)} 个标的 [{hunt_mode}]...")

                try:
                    refreshed = await external_data.refresh_all(self.exchange, universe[:10])
                    if refreshed:
                        print(f"[SCAN] 外部数据刷新: {', '.join(refreshed)}", flush=True)
                    TitanState.market_snapshot["external"] = external_data.get_snapshot()
                except Exception as e:
                    print(f"[SCAN] 外部数据刷新异常: {e}", flush=True)

                try:
                    await self.fetch_derivatives(universe[:20])
                except Exception:
                    pass

                opps = []
                cruise_map = {}
                training_data = {}
                scan_count = 0
                total_universe = len(universe)
                TitanState.market_snapshot["scan_progress"] = {
                    "current": 0, "total": total_universe, "scanning": True,
                    "last_updated": time.time()
                }
                for asset in universe:
                    sym = f"{asset}/USDT"
                    scan_count += 1
                    if scan_count % 10 == 1:
                        print(f"[SCAN] 分析进度: {scan_count}/{total_universe} ({sym})", flush=True)
                    try:
                        data = await asyncio.wait_for(self.fetch_matrix(sym), timeout=15)
                    except asyncio.TimeoutError:
                        TitanState.add_log("warn", f"{sym} 数据获取超时")
                        continue
                    if not data:
                        continue

                    try:
                        hippocampus.memorize(asset, data['4h']['c'].values)
                    except Exception:
                        pass
                    hip_result = hippocampus.recall(asset, data['4h']['c'].values)

                    res = TitanBrain.analyze(data, fng, is_crash, hip_result=hip_result)
                    if len(res) == 12:
                        score, price, sl, tp, pos_val, note, status, tech_report, ml_pred, daily_trend, smart_advice, regime = res
                    else:
                        score, price, sl, tp, pos_val, note, status, tech_report, ml_pred, daily_trend, smart_advice = res
                        regime = {'type': '未知', 'volatility': 'normal', 'trend_intensity': 0, 'action_modifier': 1.0}

                    if score >= 65 or score <= 35:
                        try:
                            from server.titan_scoring_engine import TitanScoringEngine
                            scoring_data = ml_pred.get("scoring_engine", {})
                            if scoring_data and scoring_data.get("dimensions"):
                                data_summary = f"Regime:{regime.get('type','?')} ADX:{tech_report.get('adx',0)} RSI1H:{tech_report.get('rsi_1h',50)} MACD:{tech_report.get('macd_hist',0)} FNG:{fng}"
                                ai_engine_result = {
                                    "score": score,
                                    "direction": scoring_data.get("direction", "neutral"),
                                    "dimensions": [],
                                    "signal_details": [],
                                    "ai_verdict": None
                                }
                                from server.titan_scoring_engine import DimensionResult
                                for dim_d in scoring_data.get("dimensions", []):
                                    ai_engine_result["dimensions"].append(
                                        DimensionResult(dim_d["name"], dim_d["direction"], dim_d["score"], dim_d["rationale"])
                                    )
                                ai_engine_result = TitanScoringEngine.apply_ai_scoring(
                                    ai_engine_result, asset, price, data_summary
                                )
                                if ai_engine_result.get("ai_verdict") and not ai_engine_result["ai_verdict"].get("error"):
                                    score = ai_engine_result["score"]
                                    ai_v = ai_engine_result["ai_verdict"]
                                    ml_pred["ai_verdict"] = ai_v
                                    dir_cn = {"bullish": "看涨", "bearish": "看跌", "neutral": "中性"}.get(ai_v.get("direction", ""), "中性")
                                    ai_tag = "AI✓" if ai_v.get("agreement") else "AI✗"
                                    note = note + f" 🤖{ai_tag}{dir_cn}({ai_v.get('confidence',0)}%)"
                        except Exception as ai_err:
                            logger.warning(f"AI评分跳过 {asset}: {ai_err}")

                    deriv = self._derivatives_cache.get(asset, {})

                    tech_for_ai = {
                        'adx': tech_report.get('adx', 0) if tech_report else 0,
                        'rsi': tech_report.get('rsi', 50) if tech_report else 50,
                        'bb_position': tech_report.get('bb_position', 0.5) if tech_report else 0.5,
                        'funding_rate': deriv.get('funding_rate'),
                        'open_interest': deriv.get('open_interest'),
                    }
                    ml_conf = ml_pred.get('confidence', 0) if ml_pred else 0
                    direction = "short" if status == "short" else "long"
                    ai_insight = TitanAnalyst.generate_card_insight(
                        asset, price, score, ml_conf, tech_for_ai, direction
                    )

                    cap_data = {}
                    confluence = ml_pred.get("confluence", {}) if ml_pred else {}
                    veto = ml_pred.get("onchain_veto", {}) if ml_pred else {}

                    if confluence.get("level") == "信号分歧" and score >= 75:
                        score -= 15
                    if hip_result and hip_result.get("signal") == "BEARISH" and direction == "long" and hip_result.get("confidence", 0) > 0.6:
                        score -= 10
                    elif hip_result and hip_result.get("signal") == "BULLISH" and direction == "short" and hip_result.get("confidence", 0) > 0.6:
                        score -= 10

                    if score >= 70:
                        titan_agi.record_decision(asset, score, direction, note, {
                            "regime": regime.get("type", "未知"),
                            "fng": fng,
                            "confluence_level": confluence.get("level", "未知"),
                            "veto_active": veto.get("veto", False),
                            "funding_rate": None,
                            "ml_confidence": ml_conf,
                        })

                    item = {
                        "sym": sym,
                        "symbol": asset,
                        "score": int(score),
                        "price": round(float(price), 6),
                        "strategy": note.split(']')[0].replace('[', '') if ']' in note else "观察",
                        "note": note,
                        "sl": round(float(sl), 4),
                        "tp": round(float(tp), 4),
                        "pos_val": round(float(pos_val), 2),
                        "report": tech_report,
                        "ml": ml_pred,
                        "daily": daily_trend,
                        "advice": smart_advice,
                        "ai_insight": ai_insight,
                        "regime": regime,
                        "funding_rate": deriv.get('funding_rate', None),
                        "open_interest": deriv.get('open_interest', None),
                        "confluence": confluence,
                        "capital": {},
                        "hippocampus": hip_result,
                    }
                    opps.append(item)
                    cruise_map[asset] = item

                    TitanState.market_snapshot["scan_progress"]["current"] = scan_count
                    TitanState.market_snapshot["scan_progress"]["last_updated"] = time.time()
                    TitanState.market_snapshot["cruise"] = list(cruise_map.values())

                    training_data[asset] = {'1h': data['1h'], '4h': data['4h']}

                    if score >= 60:
                        try:
                            _shadow_fng = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                            _shadow_macro = TitanState.market_snapshot.get("btc_pulse", {}).get("macro_trend", "neutral")
                            _shadow_regime = str(dispatcher.current_regime) if dispatcher else "unknown"
                            _shadow_funding = external_data.get("btc_funding_rate", 0) if 'external_data' in dir() else 0

                            _perception_brain.get_market_pulse(
                                symbol=sym,
                                klines=data if data else None,
                                regime=_shadow_regime,
                                fng=_shadow_fng,
                                btc_trend=_shadow_macro,
                                funding_rate=_shadow_funding
                            )

                            _sig_direction = "long" if score >= 50 else "short"
                            _debate_system.debate(
                                symbol=sym,
                                signal={
                                    "symbol": sym,
                                    "direction": _sig_direction,
                                    "signal_score": int(score),
                                    "score": int(score),
                                    "rsi": tech_report.get("rsi", 50) if tech_report else 50,
                                    "adx": tech_report.get("adx", 25) if tech_report else 25,
                                    "ml": ml_pred or {},
                                },
                                market_context={
                                    "fng": _shadow_fng,
                                    "regime": _shadow_regime,
                                    "btc_macro_trend": _shadow_macro,
                                    "funding_rate": _shadow_funding,
                                    "open_positions": len(paper_trader.positions),
                                }
                            )
                        except Exception as _shadow_err:
                            logger.debug(f"Shadow记录异常: {_shadow_err}")

                    if score >= 70:
                        suggestion = tech_report.get('suggestion', '') if tech_report else ''
                        ml_tag = f" ML:{ml_pred['label']}" if ml_pred.get('confidence', 0) > 0 else ""
                        TitanState.add_log("success", f"Alpha信号: {sym} 评分{score} ({suggestion}){ml_tag}")
                    elif score >= 60:
                        TitanState.add_log("info", f"关注: {sym} 评分{score}")

                self._last_training_data = training_data

                scan_data_cache = {}
                for asset_key in universe:
                    if asset_key in training_data:
                        scan_data_cache[asset_key] = training_data[asset_key]
                opps = self.filter_correlated_signals(opps, scan_data_cache)

                current_prices = {o['symbol']: o['price'] for o in opps if o['price'] > 0}
                adaptive_weights.update_outcomes(current_prices)
                if len(adaptive_weights.ml_predictions) >= 10:
                    adaptive_weights.evaluate_ml_performance()
                    aw_status = adaptive_weights.get_adaptive_weights()
                    if aw_status['evaluated'] > 0 and aw_status['evaluated'] % 20 == 0:
                        TitanState.add_log("system", f"自适应权重: ML{int(aw_status['w_ml']*100)}% 规则{int(aw_status['w_rule']*100)}% [{aw_status['tier']}] 准确率{aw_status['performance']}%")

                TitanState.market_snapshot["cruise"] = opps
                TitanState.market_snapshot["scan_progress"] = {
                    "current": total_universe, "total": total_universe, "scanning": False,
                    "last_updated": time.time()
                }

                # === Dispatcher: Evaluate Market Regime ===
                try:
                    scan_fng = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                    dispatcher.evaluate_regime(opps, fng=scan_fng)
                    TitanState.market_snapshot["dispatcher"] = dispatcher.get_status()
                except Exception as e:
                    print(f"[SCAN] Dispatcher异常: {e}", flush=True)

                # === Return Target Engine: Update ===
                try:
                    rt_price_map = {o['symbol']: o['price'] for o in opps if o.get('price', 0) > 0}
                    rt_equity = paper_trader.get_equity(rt_price_map, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                    rt_peak = getattr(paper_trader, 'peak_equity', rt_equity)
                    rt_dd = (rt_peak - rt_equity) / (rt_peak + 1e-10) * 100 if rt_peak > 0 else 0.0
                    rt_result = return_target.update(rt_equity, current_drawdown_pct=rt_dd)
                    TitanState.market_snapshot["return_target"] = return_target.get_status()
                except Exception as e:
                    print(f"[SCAN] 收益引擎异常: {e}", flush=True)
                    rt_result = {"aggression_multiplier": 1.0, "threshold_delta": 0, "annualized_return": 0}

                # === Return Rate Cognitive Agent (every 10 scans) ===
                try:
                    if TitanState.market_snapshot.get("total_scanned", 0) % 10 == 0:
                        from server.titan_return_rate_agent import return_rate_agent
                        rra_context = {
                            "return_target": return_target.get_status(),
                            "paper_portfolio": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
                            "trades_history": paper_trader.trade_history[-20:] if hasattr(paper_trader, 'trade_history') else [],
                            "coordinator_recs": ai_coordinator.recommendations,
                            "dispatcher_regime": dispatcher.current_regime,
                            "risk_budget": risk_budget.get_status(),
                            "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
                            "unified_decision": unified_decision.get_status() if 'unified_decision' in dir() else {},
                            "ml_accuracy": TitanState.market_snapshot.get("ml_status", {}).get("accuracy", 0),
                            "synapse": synapse.get_status(),
                            "signal_quality": signal_quality.get_status(),
                        }
                        rra_result = return_rate_agent.periodic_review(rra_context, agent_memory, ai_coordinator, return_target)
                        TitanState.market_snapshot["return_rate_agent"] = return_rate_agent.get_status()
                        if rra_result.get("applied", 0) > 0:
                            TitanState.add_log("system", f"🧠 收益智能体: {rra_result.get('applied')}条建议已自动应用")
                except Exception as e:
                    print(f"[SCAN] 收益智能体异常: {e}", flush=True)

                # === Unified Decision Maker ===
                try:
                    actual_grid_capital = grid_engine.get_total_capital_used()
                    rb_grid_used = risk_budget.strategy_budgets.get("grid", {}).get("used", 0)
                    if abs(actual_grid_capital - rb_grid_used) > 10:
                        risk_budget.strategy_budgets["grid"]["used"] = round(actual_grid_capital, 2)
                        risk_budget.save()

                    trend_exposure = sum(p.get("position_value", 0) for p in paper_trader.positions.values())
                    rb_trend_used = risk_budget.strategy_budgets.get("trend", {}).get("used", 0)
                    if abs(trend_exposure - rb_trend_used) > 10:
                        risk_budget.strategy_budgets["trend"]["used"] = round(trend_exposure, 2)
                        risk_budget.save()

                    c_status_ud = constitution.get_status()
                    rb_status = risk_budget.get_status()
                    total_used = sum(b.get("used", 0) for b in rb_status.get("strategy_budgets", {}).values())
                    cap_util = round(total_used / max(rb_status.get("total_capital", 1), 1) * 100, 1)
                    ud_context = {
                        "regime": dispatcher.current_regime,
                        "coordinator_recommendations": ai_coordinator.recommendations,
                        "constitution_status": c_status_ud,
                        "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
                        "active_positions": len(paper_trader.positions),
                        "active_grids": len(grid_engine.active_grids),
                        "dispatcher_strategies": dispatcher.active_strategies,
                        "return_target_status": return_target.get_status(),
                        "max_positions": MAX_POSITIONS,
                        "capital_utilization": cap_util,
                    }
                    trade_decision = unified_decision.evaluate(ud_context)
                    TitanState.market_snapshot["unified_decision"] = unified_decision.get_status()
                except Exception as e:
                    print(f"[SCAN] 统一决策异常: {e}", flush=True)
                    trade_decision = {
                        "enable_long": True, "enable_short": True, "enable_grid": True,
                        "long_threshold": 75, "short_threshold": 60, "mode": "full",
                    }

                # === Grid Engine: Update Active Grids ===
                try:
                    pt_price_map_grid = {o['symbol']: o['price'] for o in opps if o.get('price', 0) > 0}
                    if grid_engine.active_grids and pt_price_map_grid:
                        grid_ml_map = {o['symbol']: o.get('ml', {}) for o in opps if o.get('ml')}
                        closed_grids, grid_trades = grid_engine.update_grids(pt_price_map_grid, ml_predictions=grid_ml_map)
                        for cg in closed_grids:
                            grid_mode = cg.get("spacing_mode", "arithmetic")
                            trailing_info = f" 追踪={cg.get('trailing_shifts',0)}次" if cg.get("trailing_enabled") else ""
                            TitanState.add_log("action",
                                f"🕸️ 网格关闭: {cg['symbol']} PnL=${cg.get('grid_pnl',0):.2f} 模式={grid_mode}{trailing_info} 原因={cg.get('close_reason','')}")
                            grid_pnl_usd = cg.get("grid_pnl", 0)
                            grid_capital = cg.get("capital_used", 0) or cg.get("allocation", 1)
                            grid_pnl_pct = round((grid_pnl_usd / grid_capital * 100) if grid_capital > 0 else 0, 2)
                            import uuid
                            grid_trade_id = uuid.uuid4().hex[:8]
                            created_str = cg.get("created_at", "")
                            try:
                                grid_open_time = datetime.fromisoformat(created_str) if created_str else datetime.now()
                            except Exception:
                                grid_open_time = datetime.now()
                            grid_hold_hours = round((datetime.now() - grid_open_time).total_seconds() / 3600, 1) if grid_open_time else 0
                            TitanDB.save_trade({
                                "id": grid_trade_id,
                                "symbol": cg["symbol"],
                                "direction": "grid",
                                "strategy_type": f"grid_{grid_mode}",
                                "entry_price": cg.get("entry_price", 0),
                                "exit_price": cg.get("close_price", cg.get("last_price", 0)),
                                "tp_price": cg.get("upper", 0),
                                "sl_price": cg.get("lower", 0),
                                "position_value": grid_capital,
                                "pnl_pct": grid_pnl_pct,
                                "pnl_value": round(grid_pnl_usd, 2),
                                "result": "win" if grid_pnl_usd > 0 else "loss",
                                "reason": cg.get("close_reason", "grid_complete"),
                                "signal_score": 0,
                                "ml_confidence": 0,
                                "ai_verdict": "",
                                "mtf_alignment": 0,
                                "open_time": grid_open_time.isoformat() if hasattr(grid_open_time, 'isoformat') else str(grid_open_time),
                                "close_time": datetime.now().isoformat(),
                                "hold_hours": grid_hold_hours,
                                "regime": dispatcher.current_regime,
                                "is_grid_trade": True,
                                "grid_count": cg.get("grid_count", 0),
                                "buys_filled": cg.get("filled_buys", 0),
                                "sells_filled": cg.get("filled_sells", 0),
                                "spacing_mode": grid_mode,
                                "trailing_shifts": cg.get("trailing_shifts", 0),
                                "boundary_source": cg.get("boundary_source", ""),
                            })
                            attribution.record_trade({
                                "symbol": cg["symbol"], "direction": "grid", "pnl_pct": grid_pnl_pct,
                                "pnl_usd": grid_pnl_usd, "strategy_type": f"grid_{grid_mode}",
                                "entry_time": cg.get("created_at", ""), "holding_hours": 0,
                                "market_regime": dispatcher.current_regime,
                            })
                            try:
                                synapse.broadcast_trade_result({
                                    "symbol": cg["symbol"], "strategy_type": f"grid_{grid_mode}",
                                    "pnl_pct": grid_pnl_pct,
                                    "market_regime": dispatcher.current_regime,
                                    "direction": "grid", "signal_score": 0, "holding_hours": 0,
                                    "spacing_mode": grid_mode,
                                    "trailing_shifts": cg.get("trailing_shifts", 0),
                                    "boundary_source": cg.get("boundary_source", "atr_fallback"),
                                })
                                risk_budget.release_capital("grid", cg.get("capital_used", 0), cg.get("grid_pnl", 0))
                                grid_conditions = {"strategy": "grid", "spacing_mode": grid_mode, "trailing": cg.get("trailing_enabled", False)}
                                signal_quality.record_outcome(grid_conditions, cg.get("grid_pnl", 0) > 0, cg.get("grid_pnl", 0), cg["symbol"], dispatcher.current_regime)
                                titan_critic.record_trade({
                                    "symbol": cg["symbol"], "direction": "grid",
                                    "pnl_pct": grid_pnl_pct,
                                    "strategy_type": f"grid_{grid_mode}",
                                    "market_regime": dispatcher.current_regime,
                                    "entry_price": cg.get("entry_price", 0),
                                    "exit_price": cg.get("last_price", cg.get("entry_price", 0)),
                                    "holding_hours": 0,
                                    "close_reason": cg.get("close_reason", "grid_complete"),
                                })
                                grid_ml_label = cg.get("bias", "横盘")
                                if grid_ml_label == "bullish":
                                    grid_ml_label = "看涨"
                                elif grid_ml_label == "bearish":
                                    grid_ml_label = "看跌"
                                else:
                                    grid_ml_label = "横盘"
                                adaptive_weights.record_prediction(
                                    cg["symbol"], cg.get("entry_price", 0),
                                    grid_ml_label, 50, grid_ml_label
                                )
                            except Exception:
                                pass

                    if trade_decision.get("enable_grid", True) and dispatcher.should_activate_grid() and len(grid_engine.active_grids) < 8:
                        candidates = grid_engine.select_grid_candidates(opps)
                        pt_equity = paper_trader.get_equity(pt_price_map_grid, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                        grid_budget_limit = CONFIG.get('GRID_BUDGET_LIMIT', 5000)
                        grid_capital = min(dispatcher.get_capital_for_strategy("grid", pt_equity), grid_budget_limit)
                        grid_used_capital = sum(g.get("capital", 0) for g in grid_engine.active_grids.values())
                        grid_allowed_pairs = CONFIG.get('GRID_ALLOWED_PAIRS', set())
                        grid_liq_only = CONFIG.get('GRID_HIGH_LIQUIDITY_ONLY', False)
                        for cand in candidates[:3]:
                            if cand["symbol"] not in grid_engine.active_grids:
                                cand_base = cand["symbol"].replace("/USDT", "").replace("_USDT", "")
                                if grid_liq_only and cand_base not in grid_allowed_pairs:
                                    TitanState.add_log("gate", f"🕸️🚫 网格流动性过滤: {cand['symbol']} 不在高流动性白名单中")
                                    continue
                                est_grid_cost = grid_capital / max(1, 8 - len(grid_engine.active_grids))
                                if grid_used_capital + est_grid_cost > grid_budget_limit:
                                    TitanState.add_log("gate", f"🕸️🚫 网格预算将超限: 已用${grid_used_capital:.0f}+预估${est_grid_cost:.0f}>${grid_budget_limit}")
                                    break
                                grid_report = cand.get("report", {})
                                if not grid_report or not grid_report.get("adx") or not cand.get("atr"):
                                    continue
                                grid_ml = cand.get("ml", {})
                                grid_review = ai_reviewer.pre_trade_assessment({
                                    "symbol": cand["symbol"], "score": cand.get("grid_score", 60),
                                    "direction": "grid",
                                    "ml_label": grid_ml.get("label", "横盘"),
                                    "ml_confidence": grid_ml.get("confidence", 0),
                                    "rsi": grid_report.get("rsi", 50),
                                    "adx": grid_report.get("adx", 20),
                                    "regime_type": dispatcher.current_regime,
                                    "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
                                    "atr_ratio": grid_report.get("atr", 0) / (cand.get("price", 1) + 1e-10),
                                })
                                if not grid_review.get("approve", True):
                                    TitanState.add_log("system",
                                        f"🕸️❌ 网格拒绝: {cand['symbol']} AI研判={grid_review.get('verdict','')} "
                                        f"风险标记={grid_review.get('risk_flags',0)} {'; '.join(grid_review.get('reasons',[])[:2])}")
                                    continue
                                ml_pred = grid_ml
                                grid = grid_engine.generate_grid(
                                    cand["symbol"], cand["price"], cand["atr"],
                                    ml_pred=ml_pred, equity=grid_capital,
                                    adx=cand.get("adx"), regime=dispatcher.current_regime
                                )
                                grid_engine.activate_grid(cand["symbol"], grid)
                                grid_alloc = grid.get("capital", est_grid_cost)
                                grid_used_capital += grid_alloc
                                try:
                                    risk_budget.request_capital("grid", grid_alloc)
                                except Exception:
                                    pass
                                trailing_tag = " 🔄追踪" if grid.get("trailing_enabled") else ""
                                TitanState.add_log("action",
                                    f"🕸️ 网格激活: {cand['symbol']} {grid.get('spacing_mode','arith')}模式 "
                                    f"范围{grid['range_pct']}% {grid['grid_count']}格 偏向={grid['bias']}{trailing_tag} 💰${grid.get('capital',0):.0f}")
                                try:
                                    TitanDB.save_grid_activity({
                                        "symbol": cand["symbol"], "action": "activate",
                                        "spacing_mode": grid.get("spacing_mode", "arith"),
                                        "grid_count": grid.get("grid_count"),
                                        "range_pct": grid.get("range_pct"),
                                        "bias": grid.get("bias"),
                                        "capital": grid.get("capital", est_grid_cost),
                                        "regime": dispatcher.current_regime,
                                    })
                                except Exception:
                                    pass

                    grid_engine.save()
                    TitanState.market_snapshot["grid"] = grid_engine.get_status()
                except Exception as e:
                    print(f"[SCAN] Grid引擎异常: {e}", flush=True)

                # === Auto Trading: 全自动下单（双向交易） ===
                try:
                    ud_long_thr = max(trade_decision.get("long_threshold", 68), 65)
                    ud_short_thr = max(trade_decision.get("short_threshold", 55), 50)
                    ud_enable_long = trade_decision.get("enable_long", True)
                    ud_enable_short = trade_decision.get("enable_short", True)
                    rt_aggression = rt_result.get("aggression_multiplier", 1.0)

                    _db_wr_stats = paper_trader._get_db_trade_stats()
                    if _db_wr_stats:
                        total_t_wr = _db_wr_stats['wins'] + _db_wr_stats['losses']
                        _wr_wins = _db_wr_stats['wins']
                    else:
                        total_t_wr = paper_trader.total_wins + paper_trader.total_losses
                        _wr_wins = paper_trader.total_wins
                    if total_t_wr >= 10:
                        curr_wr = _wr_wins / max(1, total_t_wr)
                        if curr_wr < 0.20:
                            ud_long_thr = max(ud_long_thr, 76)
                            ud_short_thr = max(ud_short_thr, 60)
                        elif curr_wr < 0.30:
                            ud_long_thr = max(ud_long_thr, 73)
                            ud_short_thr = max(ud_short_thr, 56)
                        elif curr_wr < 0.35:
                            ud_long_thr = max(ud_long_thr, 70)
                            ud_short_thr = max(ud_short_thr, 53)

                    alpha_long_signals = []
                    if ud_enable_long:
                        for o in opps:
                            if o['score'] >= ud_long_thr:
                                alpha_long_signals.append(o)
                            else:
                                try:
                                    _o_ml = o.get("ml", {}) or {}
                                    _o_mc = _o_ml.get("confidence", 0)
                                    _o_price = o.get("price")
                                    _fng_r = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                                    _macro_r = TitanState.market_snapshot.get("btc_pulse", {}).get("macro_trend", "neutral")
                                    _regime_r = dispatcher.current_regime if dispatcher else "unknown"
                                    TitanDB.record_rejection(
                                        symbol=o.get("symbol", "?"), direction="long",
                                        signal_score=o["score"], ml_confidence=_o_mc,
                                        rejected_by="PreScan_score",
                                        rejection_reason=f"预扫描评分{o['score']}<{ud_long_thr}",
                                        btc_macro_trend=_macro_r, fng_value=_fng_r,
                                        regime=_regime_r, price=_o_price
                                    )
                                except Exception as _e:
                                    logger.debug(f"PreScan rejection record failed: {_e}")
                    alpha_short_candidates = []
                    for o in opps:
                        o_ml = o.get("ml", {})
                        o_ml_label = o_ml.get("label", "") if o_ml else ""
                        o_ml_conf = o_ml.get("confidence", 0) if o_ml else 0
                        o_report = o.get("report", {})
                        o_rsi = o_report.get("rsi", 50) if o_report else 50
                        o_adx = o_report.get("adx", 20) if o_report else 20
                        o_regime = o.get("regime", {})
                        o_regime_type = o_regime.get("type", "") if o_regime else ""
                        o_score = o.get("score", 50)

                        short_score = 0
                        if o_ml_label in ("看跌", "bearish", "down"):
                            if o_ml_conf >= 70:
                                short_score += 40
                            elif o_ml_conf >= 50:
                                short_score += 30
                            elif o_ml_conf >= 35:
                                short_score += 20
                        if o_rsi > 75:
                            short_score += 25
                        elif o_rsi > 65:
                            short_score += 18
                        elif o_rsi > 55:
                            short_score += 8
                        if o_adx > 30:
                            short_score += 15
                        elif o_adx > 20:
                            short_score += 10
                        if o_regime_type in ("trending",) and o_score < 45:
                            short_score += 15
                        elif o_regime_type in ("volatile", "ranging") and o_rsi > 60:
                            short_score += 12
                        fng_val = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                        if fng_val >= 75:
                            short_score += 18
                        elif fng_val >= 65:
                            short_score += 12
                        elif fng_val <= 15:
                            short_score += 20
                        elif fng_val <= 25:
                            short_score += 15
                        elif fng_val <= 35:
                            short_score += 8
                        o_daily = o.get("daily", {})
                        if o_daily and o_daily.get("trend") in ("下跌", "bearish", "down"):
                            short_score += 18
                        o_bb = o_report.get("bb_position", 0.5) if o_report else 0.5
                        if o_bb > 0.85:
                            short_score += 15
                        elif o_bb > 0.75:
                            short_score += 8
                        o_macd = o_report.get("macd_hist", 0) if o_report else 0
                        if o_macd < 0:
                            short_score += 10

                        if short_score >= ud_short_thr:
                            alpha_short_candidates.append({**o, "_short_score": short_score})
                        else:
                            try:
                                TitanDB.record_rejection(
                                    symbol=o.get("symbol", "?"), direction="short",
                                    signal_score=o.get("score", 0), ml_confidence=o_ml_conf,
                                    rejected_by="PreScan_short_score",
                                    rejection_reason=f"做空评分{short_score}<{ud_short_thr}",
                                    btc_macro_trend=TitanState.market_snapshot.get("btc_pulse", {}).get("macro_trend", "neutral"),
                                    fng_value=TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
                                    regime=dispatcher.current_regime if dispatcher else "unknown",
                                    price=o.get("price")
                                )
                            except Exception as _e:
                                logger.debug(f"PreScan short rejection record failed: {_e}")

                    if not ud_enable_short:
                        alpha_short_candidates = []
                    alpha_short_candidates.sort(key=lambda x: x["_short_score"], reverse=True)

                    all_trade_signals = []
                    for sig in alpha_long_signals:
                        all_trade_signals.append({"signal": sig, "direction": "long"})
                    for sig in alpha_short_candidates[:5]:
                        all_trade_signals.append({"signal": sig, "direction": "short"})

                    opp_scores = sorted([o.get("score", 0) for o in opps], reverse=True)
                    top5_scores = opp_scores[:5] if opp_scores else []
                    n_pass_long = len(alpha_long_signals)
                    n_pass_short = len(alpha_short_candidates)
                    print(f"[SCAN] 📊 决策摘要: 做多门槛={ud_long_thr} 做空门槛={ud_short_thr} | "
                          f"通过做多={n_pass_long} 通过做空={n_pass_short} | "
                          f"Top5评分={top5_scores} | 持仓={len(paper_trader.positions)} "
                          f"FNG={TitanState.market_snapshot.get('btc_pulse', {}).get('fng', 50)} "
                          f"regime={dispatcher.current_regime}", flush=True)

                    pt_equity_at = paper_trader.get_equity(pt_price_map_grid, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                    total_exposure_at = paper_trader.get_total_exposure()
                    fng_at = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                    c_status_at = constitution.get_status()
                    total_trades_check = paper_trader.total_wins + paper_trader.total_losses
                    overall_win_rate = paper_trader.total_wins / max(1, total_trades_check)
                    low_winrate_penalty = 0
                    if total_trades_check >= 10 and overall_win_rate < 0.30:
                        low_winrate_penalty = 15
                        if overall_win_rate < 0.20:
                            low_winrate_penalty = 25

                    can_auto_trade = (
                        not c_status_at.get("permanent_breaker") and
                        not c_status_at.get("daily_breaker") and
                        pt_equity_at > 0 and
                        total_exposure_at < pt_equity_at * 0.65 and
                        len(paper_trader.positions) < MAX_POSITIONS and
                        paper_trader.consecutive_losses < 3
                    )

                    if autopilot.trading_paused:
                        can_auto_trade = False

                    if not can_auto_trade:
                        print(f"[SCAN] ⚠️ 自动交易被禁用: perm_breaker={c_status_at.get('permanent_breaker')} daily_breaker={c_status_at.get('daily_breaker')} equity={pt_equity_at:.0f} exposure={total_exposure_at:.0f}/{pt_equity_at*0.65:.0f} positions={len(paper_trader.positions)}/{MAX_POSITIONS} cons_loss={paper_trader.consecutive_losses}/3 ap_paused={autopilot.trading_paused}", flush=True)

                    now_ts = time.time()
                    self._signal_cooldowns = {s: t for s, t in self._signal_cooldowns.items() if t > now_ts}

                    def _safe_record_rejection(sym, direction, score, ml_conf, rejected_by, reason, detail=None):
                        try:
                            _fng = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                            _macro = TitanState.market_snapshot.get("btc_pulse", {}).get("macro_trend", "neutral")
                            _regime = dispatcher.current_regime if dispatcher else "unknown"
                            _price = None
                            for _ts in all_trade_signals:
                                if _ts["signal"]["symbol"] == sym:
                                    _price = _ts["signal"].get("price")
                                    break
                            TitanDB.record_rejection(
                                symbol=sym, direction=direction, signal_score=score,
                                ml_confidence=ml_conf, rejected_by=rejected_by,
                                rejection_reason=reason, rejection_detail=detail,
                                btc_macro_trend=_macro, fng_value=_fng, regime=_regime, price=_price
                            )
                        except Exception:
                            pass

                    if can_auto_trade and all_trade_signals:
                        existing_symbols = {p["symbol"] for p in paper_trader.positions.values()}
                        traded_count = 0
                        max_positions_limit = MAX_POSITIONS
                        cooldown_count = sum(1 for item in all_trade_signals if self._signal_cooldowns.get(item["signal"]["symbol"], 0) > now_ts)
                        print(f"[SCAN] 🔍 开始交易决策: {len(all_trade_signals)}个候选信号 (冷却中:{cooldown_count})", flush=True)
                        try:
                            with open("data/titan_config.json") as _cf:
                                _live_config = json.load(_cf)
                        except Exception as _cfg_err:
                            logger.warning(f"Config加载失败，bonus逻辑降级: {_cfg_err}")
                            _live_config = {}
                        for trade_item in all_trade_signals:
                            if traded_count >= 3:
                                break
                            if len(paper_trader.positions) >= max_positions_limit:
                                break
                            sig = trade_item["signal"]
                            sig_direction = trade_item["direction"]
                            sym = sig["symbol"]
                            if sym in existing_symbols:
                                continue

                            cooldown_until = self._signal_cooldowns.get(sym, 0)
                            if time.time() < cooldown_until:
                                continue

                            cto_blacklist = ai_coordinator.strategic_directives.get("asset_blacklist", [])
                            asset_clean = sym.replace("/USDT", "").replace("USDT", "")
                            if asset_clean in cto_blacklist or sym in cto_blacklist:
                                print(f"[SCAN] 🚫 {sym}: CTO黑名单 跳过", flush=True)
                                self._signal_cooldowns[sym] = time.time() + 1800
                                _safe_record_rejection(sym, sig_direction, sig.get("score", 0), sig.get("ml", {}).get("confidence", 0) if sig.get("ml") else 0, 'CTO_blacklist', f'CTO黑名单: {asset_clean}')
                                continue

                            sig_score = sig["score"]
                            sig_price = sig["price"]
                            sig_ml = sig.get("ml", {})
                            sig_ml_conf = sig_ml.get("confidence", 0) if sig_ml else 0
                            sig_ml_label = sig_ml.get("label", "") if sig_ml else ""
                            sig_report = sig.get("report", {})
                            sig_atr = sig_report.get("atr", sig_price * 0.02) if sig_report else sig_price * 0.02
                            if sig_atr == 0:
                                sig_atr = sig_price * 0.02

                            strategy_at = dispatcher.get_strategy_for_signal(sig)

                            if strategy_at == "range":
                                current_regime = dispatcher.current_regime if dispatcher else "unknown"
                                if current_regime != "ranging":
                                    print(f"[SCAN] ❌ {sym}: Range策略跳过 当前regime={current_regime}（需要ranging）", flush=True)
                                    _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_regime', f'Range策略regime={current_regime}需要ranging')
                                    continue

                            symbol_bonus = _live_config.get("symbol_score_bonus", {})
                            sym_adj = symbol_bonus.get(sym, 0)

                            from datetime import timezone as _tz
                            _bj_hour = (datetime.now(_tz.utc).hour + 8) % 24
                            session_cfg = _live_config.get("session_score_bonus", {})
                            if _bj_hour in [4, 5]:
                                _session_bonus = session_cfg.get("best", 3)
                            elif _bj_hour in [19, 20, 21]:
                                _session_bonus = session_cfg.get("good", 3)
                            elif _bj_hour == 9:
                                _session_bonus = session_cfg.get("morning", 2)
                            else:
                                _session_bonus = 0

                            effective_threshold = 65 + sym_adj
                            effective_score = sig_score + _session_bonus

                            if effective_score < effective_threshold:
                                detail = f'评分{sig_score}'
                                if _session_bonus: detail += f'+时段{_session_bonus}'
                                if sym_adj: detail += f'(门槛{effective_threshold})'
                                detail += f'<{effective_threshold}'
                                print(f"[SCAN] ❌ {sym}: {detail} 跳过", flush=True)
                                self._signal_cooldowns[sym] = time.time() + self.NO_SIGNAL_COOLDOWN_MINUTES * 60
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_score', detail)
                                continue

                            if sig_ml_conf < 50:
                                print(f"[SCAN] ❌ {sym}: ML置信度{sig_ml_conf:.0f}<50 跳过", flush=True)
                                self._signal_cooldowns[sym] = time.time() + self.NO_SIGNAL_COOLDOWN_MINUTES * 60
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_ml_confidence', f'ML置信度{sig_ml_conf:.0f}<50')
                                continue

                            at_fng = TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50)
                            scan_macro = TitanState.market_snapshot.get("btc_pulse", {}).get("macro_trend", "neutral")

                            if sig_direction == "long" and at_fng < 5 and strategy_at == "trend":
                                TitanState.add_log("gate", f"🛑 极恐禁多: {sym} FNG={at_fng}<5, Trend策略禁止做多")
                                print(f"[SCAN] ❌ {sym}: FNG={at_fng}<5 极恐禁多", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_fng', f'FNG={at_fng}<5极恐禁多')
                                continue
                            elif sig_direction == "long" and at_fng < 15 and strategy_at == "trend" and sig_score < 73:
                                TitanState.add_log("gate", f"⚠️ 极恐高门槛: {sym} FNG={at_fng}<15, 趋势做多需≥73分(当前{sig_score})")
                                print(f"[SCAN] ❌ {sym}: FNG={at_fng}<15 需≥73分(当前{sig_score})", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_fng', f'FNG={at_fng}<15需≥73分(当前{sig_score})')
                                continue

                            ml_paradox_check = "passed"
                            ml_paradox_reason = ""
                            if sig_ml_conf > 75:
                                if sig_direction == "long" and scan_macro == "bearish":
                                    ml_paradox_check = "rejected"
                                    ml_paradox_reason = f"ML={sig_ml_conf:.0f}>75做多但BTC宏观bearish"
                                    TitanState.add_log("gate", f"🛑 ML悖论拒绝: {sym} {ml_paradox_reason}")
                                    print(f"[SCAN] ❌ {sym}: ML悖论拒绝 {ml_paradox_reason}", flush=True)
                                    _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_ml_paradox', ml_paradox_reason)
                                    continue
                                elif sig_direction == "short" and scan_macro == "bullish":
                                    ml_paradox_check = "rejected"
                                    ml_paradox_reason = f"ML={sig_ml_conf:.0f}>75做空但BTC宏观bullish"
                                    TitanState.add_log("gate", f"🛑 ML悖论拒绝: {sym} {ml_paradox_reason}")
                                    print(f"[SCAN] ❌ {sym}: ML悖论拒绝 {ml_paradox_reason}", flush=True)
                                    _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_ml_paradox', ml_paradox_reason)
                                    continue

                            sig_adx = sig_report.get("adx", 0)
                            if strategy_at == "range" and scan_macro != "neutral" and sig_adx > 25:
                                TitanState.add_log("gate", f"🛑 Range趋势禁入: {sym} macro={scan_macro} ADX={sig_adx:.0f}>25, Range策略不在趋势中开仓")
                                print(f"[SCAN] ❌ {sym}: Range策略禁入 macro={scan_macro} ADX={sig_adx:.0f}>25", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_regime', f'Range策略禁入macro={scan_macro}ADX={sig_adx:.0f}')
                                continue

                            sig_4h_dir = sig_report.get("direction_4h", "neutral") if sig_report else "neutral"
                            sig_4h_votes = sig_report.get("direction_4h_votes", "") if sig_report else ""
                            if sig_4h_dir != "neutral":
                                print(f"[SCAN] 🔍 {sym}: 4H方向={sig_4h_dir} 信号={sig_direction} ({sig_4h_votes})", flush=True)
                            if sig_direction == "long" and sig_4h_dir == "down":
                                TitanState.add_log("gate", f"🛑 4H逆势拒绝: {sym} 做多但4H方向=down")
                                print(f"[SCAN] ❌ {sym}: 4H逆势拒绝 做多但4H=down (历史0%胜率)", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_4h_direction', f'4H逆势: 做多但4H=down')
                                continue
                            elif sig_direction == "short" and sig_4h_dir == "up":
                                TitanState.add_log("gate", f"🛑 4H逆势拒绝: {sym} 做空但4H方向=up")
                                print(f"[SCAN] ❌ {sym}: 4H逆势拒绝 做空但4H=up", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_4h_direction', f'4H逆势: 做空但4H=up')
                                continue

                            sig_for_gate = {**sig, "direction": sig_direction}
                            gate_ok, gate_reasons = TitanSignalGate.should_allow(
                                signal=sig_for_gate,
                                regime=dispatcher.current_regime,
                                strategy=strategy_at,
                                ml_confidence=sig_ml_conf,
                                signal_score=sig_score,
                                report=sig_report,
                                autopilot=autopilot,
                                min_score_override=ud_long_thr if sig_direction == "long" else ud_short_thr,
                            )
                            if not gate_ok:
                                TitanState.add_log("gate", f"🚫 信号门控拦截: {sym} {sig_direction} | {'; '.join(gate_reasons[:2])}")
                                print(f"[SCAN] ❌ {sym}: 门控拦截 {'; '.join(gate_reasons[:2])}", flush=True)
                                self._signal_cooldowns[sym] = time.time() + self.REJECTED_COOLDOWN_MINUTES * 60
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'SignalGate_rules', '; '.join(gate_reasons[:2]))
                                continue

                            available_budget = risk_budget.get_available_budget(strategy_at)
                            if available_budget < 100:
                                print(f"[SCAN] ❌ {sym}: 预算不足 strategy={strategy_at} budget={available_budget:.0f}<100", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'RiskBudget', f'预算不足{strategy_at}={available_budget:.0f}<100')
                                continue

                            total_trades_at = paper_trader.total_wins + paper_trader.total_losses
                            wr_at = paper_trader.total_wins / max(1, total_trades_at)
                            sq_score_at = signal_quality.stats.get("avg_quality", 0.5) if hasattr(signal_quality, 'stats') else 0.5
                            aw_at = adaptive_weights.get_adaptive_weights()

                            sizing_ctx = {
                                "symbol": sym,
                                "equity": pt_equity_at,
                                "signal_score": sig_score,
                                "ml_confidence": sig_ml_conf,
                                "atr": sig_atr,
                                "price": sig_price,
                                "regime": dispatcher.current_regime,
                                "strategy": strategy_at,
                                "fng": fng_at,
                                "win_rate": wr_at,
                                "payoff_ratio": 1.5,
                                "consecutive_wins": paper_trader.consecutive_wins,
                                "consecutive_losses": paper_trader.consecutive_losses,
                                "total_exposure": total_exposure_at,
                                "available_budget": available_budget,
                                "signal_quality_score": sq_score_at,
                                "synapse_confidence": 1.0,
                                "adaptive_w_ml": aw_at.get("w_ml", 0.35),
                                "drawdown_pct": risk_budget.total_drawdown * 100,
                                "coin_tier": get_coin_tier(sym),
                            }
                            sizing_result = capital_sizer.calculate_position(sizing_ctx)
                            rec_amount = sizing_result["amount"]
                            rec_msg = sizing_result["message"]

                            dd_mult, dd_reason = constitution.get_drawdown_gradient(pt_equity_at)
                            if dd_mult < 1.0:
                                rec_amount = round(rec_amount * dd_mult, 2)
                                if dd_mult <= 0:
                                    print(f"[SCAN] ❌ {sym}: 回撤梯度冻结 {dd_reason}", flush=True)
                                    _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'Constitution_drawdown', f'回撤梯度冻结{dd_reason}')
                                    continue
                                print(f"[SCAN] ⚠️ {sym}: 回撤梯度收缩 mult={dd_mult} {dd_reason}", flush=True)

                            if rec_amount <= 0 or rec_msg != "OK":
                                print(f"[SCAN] ❌ {sym}: 仓位计算拒绝 amount={rec_amount} msg={rec_msg}", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'CapitalSizer', f'仓位计算拒绝amount={rec_amount}msg={rec_msg}')
                                continue

                            if sig_direction == "short":
                                rec_amount = round(rec_amount * 0.85, 2)

                            btc_macro_filter = "none"
                            if scan_macro == "bearish" and sig_direction == "long":
                                original_amt = rec_amount
                                rec_amount = round(rec_amount * 0.30, 2)
                                btc_macro_filter = "bearish_long_reduced"
                                print(f"[SCAN] ⚠️ {sym}: BTC宏观bearish做多缩仓30% ${original_amt:.2f}→${rec_amount:.2f}", flush=True)
                            elif scan_macro == "bullish" and sig_direction == "short":
                                original_amt = rec_amount
                                rec_amount = round(rec_amount * 0.30, 2)
                                btc_macro_filter = "bullish_short_reduced"
                                print(f"[SCAN] ⚠️ {sym}: BTC宏观bullish做空缩仓30% ${original_amt:.2f}→${rec_amount:.2f}", flush=True)

                            fng_paradox_adj = 1.0
                            if sig_ml_conf > 75:
                                if sig_direction == "long" and at_fng < 15:
                                    fng_paradox_adj = 0.40
                                    rec_amount = round(rec_amount * 0.40, 2)
                                    ml_paradox_check = "size_reduced"
                                    ml_paradox_reason = f"ML={sig_ml_conf:.0f}>75做多+FNG={at_fng}<15"
                                    print(f"[SCAN] ⚠️ {sym}: FNG悖论缩仓40% {ml_paradox_reason}", flush=True)
                                elif sig_direction == "short" and at_fng > 85:
                                    fng_paradox_adj = 0.40
                                    rec_amount = round(rec_amount * 0.40, 2)
                                    ml_paradox_check = "size_reduced"
                                    ml_paradox_reason = f"ML={sig_ml_conf:.0f}>75做空+FNG={at_fng}>85"
                                    print(f"[SCAN] ⚠️ {sym}: FNG悖论缩仓40% {ml_paradox_reason}", flush=True)

                            scoring_engine_data = sig_ml.get("scoring_engine", {}) if sig_ml else {}
                            se_sl = scoring_engine_data.get("sl_mult", 2.5) if scoring_engine_data else 2.5
                            se_tp = scoring_engine_data.get("tp_mult", 3.5) if scoring_engine_data else 3.5
                            mega_p = mega_backtest.get_best_params() if hasattr(mega_backtest, 'get_best_params') else {}
                            tp_m = max(mega_p.get("tp_atr", se_tp), se_tp)
                            sl_m = max(mega_p.get("sl_atr", se_sl), se_sl)

                            if sig_score >= 75 and sig_ml_conf >= 60:
                                tp_m = max(tp_m, 4.0)
                            elif sig_score >= 70:
                                tp_m = max(tp_m, 3.5)

                            if sig_direction == "long":
                                tp_price_at = round(sig_price + sig_atr * tp_m, 6)
                                sl_price_at = round(sig_price - sig_atr * sl_m, 6)
                            else:
                                tp_price_at = round(sig_price - sig_atr * tp_m, 6)
                                sl_price_at = round(sig_price + sig_atr * sl_m, 6)

                            MIN_SL_DISTANCE = 0.03
                            MAX_SL_DISTANCE = 0.15
                            sl_dist = abs(sl_price_at - sig_price) / sig_price if sig_price > 0 else 0.02
                            if sl_dist < MIN_SL_DISTANCE:
                                print(f"[SCAN] [SL保护] {sym} SL从{sl_dist:.2%}扩展到{MIN_SL_DISTANCE:.1%}", flush=True)
                                if sig_direction == "long":
                                    sl_price_at = round(sig_price * (1 - MIN_SL_DISTANCE), 6)
                                else:
                                    sl_price_at = round(sig_price * (1 + MIN_SL_DISTANCE), 6)
                                sl_dist = MIN_SL_DISTANCE
                            elif sl_dist > MAX_SL_DISTANCE:
                                print(f"[SCAN] [SL上限] {sym} SL从{sl_dist:.2%}压缩到{MAX_SL_DISTANCE:.0%}", flush=True)
                                if sig_direction == "long":
                                    sl_price_at = round(sig_price * (1 - MAX_SL_DISTANCE), 6)
                                else:
                                    sl_price_at = round(sig_price * (1 + MAX_SL_DISTANCE), 6)
                                sl_dist = MAX_SL_DISTANCE
                            MAX_TP_SL_RATIO = 3.5
                            MIN_TP_SL_RATIO = 2.0
                            _sl_dist_r = abs(sig_price - sl_price_at) / sig_price if sig_price > 0 else 0.02
                            _tp_dist_r = abs(tp_price_at - sig_price) / sig_price if sig_price > 0 else 0.06
                            _current_ratio = _tp_dist_r / (_sl_dist_r + 1e-10)

                            if _current_ratio > MAX_TP_SL_RATIO:
                                _tp_dist_capped = _sl_dist_r * MAX_TP_SL_RATIO
                                if sig_direction == "long":
                                    tp_price_at = round(sig_price * (1 + _tp_dist_capped), 6)
                                else:
                                    tp_price_at = round(sig_price * (1 - _tp_dist_capped), 6)
                                print(f"[SCAN] [TP/SL修复] {sym} 比例从{_current_ratio:.1f}:1压缩到{MAX_TP_SL_RATIO}:1 TP={tp_price_at:.6f}", flush=True)
                            elif _current_ratio < MIN_TP_SL_RATIO:
                                _tp_dist_floor = _sl_dist_r * MIN_TP_SL_RATIO
                                if sig_direction == "long":
                                    tp_price_at = round(sig_price * (1 + _tp_dist_floor), 6)
                                else:
                                    tp_price_at = round(sig_price * (1 - _tp_dist_floor), 6)
                                print(f"[SCAN] [TP/SL修复] {sym} 比例从{_current_ratio:.1f}:1提升到{MIN_TP_SL_RATIO}:1 TP={tp_price_at:.6f}", flush=True)

                            can_open_at, const_reason = constitution.can_open_position(pt_equity_at, rec_amount, total_exposure_at, sl_dist)
                            if not can_open_at:
                                print(f"[SCAN] ❌ {sym}: 宪法拒绝 reason={const_reason}", flush=True)
                                _safe_record_rejection(sym, sig_direction, sig_score, sig_ml_conf, 'Constitution', f'宪法拒绝{const_reason}')
                                continue

                            risk_budget.request_capital(strategy_at, rec_amount)

                            dir_cn = "做多" if sig_direction == "long" else "做空"
                            short_tag = f" 做空评分={sig.get('_short_score', 0)}" if sig_direction == "short" else ""
                            ai_tag = ""

                            rule_dir = "看涨" if sig_score >= 60 else ("看跌" if sig_score <= 40 else "中性")
                            adaptive_weights.record_prediction(sym, sig_price, sig_ml_label, sig_ml_conf, rule_dir)

                            _cg_data = external_data.cache.coinglass if external_data else {}
                            _entry_ind = {
                                "rsi": round(sig_report.get("rsi", 50), 1) if sig_report else 50,
                                "rsi_1h": round(sig_report.get("rsi_1h", 50), 1) if sig_report else 50,
                                "adx": round(sig_report.get("adx", 20), 1) if sig_report else 20,
                                "bb_position": round(sig_report.get("bb_position", 0.5), 3) if sig_report else 0.5,
                                "macd_hist": round(sig_report.get("macd_hist", 0), 6) if sig_report else 0,
                                "volume_ratio": round(sig_report.get("volume_ratio", 1.0), 2) if sig_report else 1.0,
                                "atr": round(sig_atr, 6),
                                "btc_trend": scan_macro,
                                "fng": fng_at,
                                "regime": str(dispatcher.current_regime),
                                "sl_distance_pct": round(_sl_dist_r * 100, 2),
                                "tp_sl_ratio": round((tp_price_at - sig_price) / (sig_price - sl_price_at), 2) if sig_direction == "long" and (sig_price - sl_price_at) > 0 else (round((sig_price - tp_price_at) / (sl_price_at - sig_price), 2) if sig_direction == "short" and (sl_price_at - sig_price) > 0 else 0),
                                "ml_label": sig_ml_label,
                                "ml_confidence": round(sig_ml_conf, 1),
                                "funding_rate": _cg_data.get("btc_funding_rate", 0),
                                "strategy": strategy_at,
                                "long_threshold": ud_long_thr,
                            }

                            pid_at = paper_trader.open_position(
                                symbol=sym,
                                direction=sig_direction,
                                entry_price=sig_price,
                                tp_price=tp_price_at,
                                sl_price=sl_price_at,
                                position_value=rec_amount,
                                signal_score=sig_score,
                                ml_confidence=sig_ml_conf,
                                atr_value=sig_atr,
                                ai_verdict=f"Auto {dir_cn} Score:{sig_score} ML:{sig_ml_conf:.0f}%{short_tag}",
                                mtf_alignment=0,
                                strategy_type=strategy_at,
                                regime_at_entry=dispatcher.current_regime.get("type", "unknown") if isinstance(dispatcher.current_regime, dict) else str(dispatcher.current_regime or "unknown"),
                                fng_at_entry=fng_at,
                                btc_price_at_entry=TitanState.market_snapshot.get("btc_pulse", {}).get("price", 0),
                                entry_indicators=_entry_ind,
                                decision_chain={
                                    "signal_score": sig_score,
                                    "ml_confidence": sig_ml_conf,
                                    "ml_label": sig_ml_label,
                                    "ml_multiplier": sizing_result.get("multipliers", {}).get("ml"),
                                    "ml_confidence_tier": "extreme" if sig_ml_conf >= 80 else ("high" if sig_ml_conf >= 70 else ("optimal" if sig_ml_conf >= 60 else ("medium" if sig_ml_conf >= 50 else "low"))),
                                    "strategy": strategy_at,
                                    "regime": str(dispatcher.current_regime),
                                    "fng": fng_at,
                                    "gate_passed": True,
                                    "sizing_amount": rec_amount,
                                    "tp_mult": tp_m,
                                    "sl_mult": sl_m,
                                    "btc_macro_trend": scan_macro,
                                    "btc_macro_filter": btc_macro_filter,
                                    "ml_paradox_check": ml_paradox_check,
                                    "ml_paradox_reason": ml_paradox_reason,
                                    "direction_4h": sig_4h_dir,
                                },
                            )

                            existing_symbols.add(sym)
                            total_exposure_at += rec_amount
                            traded_count += 1

                            TitanState.add_log("action",
                                f"🤖 自动{dir_cn}: {sym} @ ${sig_price:.4f} 金额=${rec_amount:.2f} 评分{sig_score}{short_tag}{ai_tag} TP=${tp_price_at:.4f} SL=${sl_price_at:.4f}")
                            print(f"[AUTO] 自动{dir_cn}: {sym} score={sig_score} amount=${rec_amount:.2f}{short_tag}{ai_tag}", flush=True)

                            try:
                                _trade_asset = sym.replace("/USDT", "").replace("USDT", "")
                                _trade_klines = training_data.get(_trade_asset) if 'training_data' in dir() else None
                                _shadow_pulse = _perception_brain.get_market_pulse(
                                    symbol=sym, klines=_trade_klines,
                                    regime=str(dispatcher.current_regime),
                                    fng=fng_at, btc_trend=scan_macro,
                                    funding_rate=external_data.get("btc_funding_rate", 0))
                                _shadow_weights = _strategy_brain.get_current_weights()
                                _shadow_debate = _debate_system.debate(
                                    symbol=sym,
                                    signal={"symbol": sym, "direction": sig_direction, "signal_score": sig_score,
                                            "score": sig_score,
                                            "rsi": sig_report.get("rsi", 50), "adx": sig_report.get("adx", 25),
                                            "ml": sig.get("ml", {})},
                                    market_context={"fng": fng_at, "regime": str(dispatcher.current_regime),
                                                    "btc_macro_trend": scan_macro,
                                                    "funding_rate": external_data.get("btc_funding_rate", 0),
                                                    "market_pulse": _shadow_pulse,
                                                    "open_positions": len(paper_trader.positions)})
                                print(f"[SHADOW] {sym} 辩论:{_shadow_debate['verdict']} "
                                      f"置信度{_shadow_debate['confidence']:.2f} "
                                      f"多头{_shadow_debate.get('bull_score',0):.0f} "
                                      f"空头{_shadow_debate.get('bear_score',0):.0f}", flush=True)
                            except Exception as _se:
                                logger.debug(f"Shadow模式异常（不影响交易）: {_se}")

                except Exception as e:
                    print(f"[SCAN] 自动交易异常: {e}", flush=True)

                # === Paper Trader Auto TP/SL Check ===
                try:
                    pt_price_map = {o['symbol']: o['price'] for o in opps if o.get('price', 0) > 0}
                    pt_atr_map = {}
                    for o in opps:
                        if o.get('price', 0) > 0 and o.get('report', {}).get('atr'):
                            pt_atr_map[o['symbol']] = o['report']['atr']
                    closed_trades = []
                    async with TitanState.get_position_lock():
                        if len(paper_trader.positions) > MAX_POSITIONS and pt_price_map:
                            cleanup_trades = paper_trader.smart_liquidate_worst(pt_price_map, max_keep=MAX_POSITIONS - 2, reason="over_limit_cleanup")
                            for ct in cleanup_trades:
                                TitanState.add_log("action",
                                    f"🧹 超限清仓: {ct['symbol']} {ct['direction']} PnL={ct['pnl_pct']:+.2f}% 优先平掉亏损最大仓位")
                        if paper_trader.positions and pt_price_map:
                            current_regime = getattr(dispatcher, 'current_regime', None)
                            closed_trades = paper_trader.update_positions(pt_price_map, atr_map=pt_atr_map, regime=current_regime)
                    for ct in closed_trades:
                        TitanState.add_log("action", 
                            f"📊 模拟自动平仓: {ct['symbol']} {ct['direction']} {ct['reason']} PnL={ct['pnl_pct']:+.2f}%")
                        try:
                            titan_agi.record_outcome(ct['symbol'], ct['pnl_pct'], ct['reason'], {
                                "signal_score": ct.get('signal_score', 0),
                                "ml_confidence": ct.get('ml_confidence', 0),
                                "hold_hours": ct.get('hold_hours', 0),
                            })
                            ct_strategy = ct.get("strategy_type", dispatcher.get_strategy_for_signal({"report": {"adx": 20}, "regime": {}}))
                            attribution.record_trade({
                                "symbol": ct["symbol"],
                                "direction": ct.get("direction", "long"),
                                "entry_price": ct.get("entry_price", 0),
                                "exit_price": ct.get("exit_price", 0),
                                "pnl_pct": ct["pnl_pct"],
                                "pnl_usd": ct.get("pnl_value", 0),
                                "strategy_type": ct_strategy,
                                "signal_score": ct.get("signal_score", 0),
                                "entry_time": ct.get("open_time", ""),
                                "exit_time": ct.get("close_time", ""),
                                "holding_hours": ct.get("hold_hours", 0),
                                "market_regime": dispatcher.current_regime,
                            })
                            ct_report = ct.get("report", {})
                            titan_critic.record_trade({
                                "sym": ct["symbol"],
                                "direction": ct.get("direction", "long"),
                                "entry": ct.get("entry_price", 0),
                                "exit": ct.get("exit_price", 0),
                                "pnl": ct["pnl_pct"],
                                "result": "win" if ct["pnl_pct"] > 0 else "loss",
                                "score": ct.get("signal_score", 0),
                                "rsi": ct_report.get("rsi", 50) if ct_report else 50,
                                "adx": ct_report.get("adx", 20) if ct_report else 20,
                                "regime": dispatcher.current_regime,
                                "bb_pos": ct_report.get("bb_position", 0.5) if ct_report else 0.5,
                                "vol_ratio": ct_report.get("vol_ratio", 1.0) if ct_report else 1.0,
                            })
                            feedback_engine.record_prediction_outcome(
                                ct["symbol"],
                                ct.get("ml_label", "unknown"),
                                "win" if ct["pnl_pct"] > 0 else "loss",
                                features_snapshot={
                                    "regime": dispatcher.current_regime,
                                    "adx": ct_report.get("adx", 20) if ct_report else 20,
                                    "vol_ratio": ct_report.get("vol_ratio", 1.0) if ct_report else 1.0,
                                },
                                direction=ct.get("direction", "long"),
                            )
                            governor.record_trade_result(ct["pnl_pct"] > 0)
                            dispatcher.update_performance(ct_strategy, ct.get("result", "loss"))
                            synapse.broadcast_trade_result({
                                "symbol": ct["symbol"],
                                "strategy_type": ct_strategy,
                                "pnl_pct": ct["pnl_pct"],
                                "market_regime": dispatcher.current_regime,
                                "direction": ct.get("direction", "long"),
                                "signal_score": ct.get("signal_score", 0),
                                "holding_hours": ct.get("hold_hours", 0),
                            })
                            risk_budget.release_capital(
                                ct_strategy,
                                ct.get("position_value", 0),
                                ct.get("pnl_value", 0),
                            )
                            conditions = signal_quality.extract_conditions(ct.get("report", {}), dispatcher.current_regime)
                            signal_quality.record_outcome(conditions, ct["pnl_pct"] > 0, ct["pnl_pct"], ct["symbol"], dispatcher.current_regime)
                            ai_reviewer.queue_trade_for_review({
                                "symbol": ct["symbol"],
                                "direction": ct.get("direction", "long"),
                                "strategy_type": ct_strategy,
                                "pnl_pct": ct["pnl_pct"],
                                "holding_hours": ct.get("hold_hours", 0),
                                "market_regime": dispatcher.current_regime,
                                "signal_score": ct.get("signal_score", 0),
                                "entry_price": ct.get("entry_price", 0),
                                "exit_price": ct.get("exit_price", 0),
                                "close_reason": ct.get("reason", "auto"),
                            })
                            external_data.memory_bank.record_trade_pattern({
                                "symbol": ct["symbol"],
                                "direction": ct.get("direction", "long"),
                                "result": "win" if ct["pnl_pct"] > 0 else "loss",
                                "pnl_pct": ct["pnl_pct"],
                                "regime": dispatcher.current_regime,
                                "strategy": ct_strategy,
                                "signal_score": ct.get("signal_score", 0),
                                "ml_confidence": ct.get("ml_confidence", 0),
                                "holding_hours": ct.get("hold_hours", 0),
                                "lesson": ct.get("reason", "auto"),
                            })
                        except Exception:
                            pass
                    
                    # === Position Guard Check ===
                    try:
                        if paper_trader.positions and pt_price_map:
                            candle_map = {}
                            for o in opps:
                                sym = o.get('symbol')
                                if sym and o.get('candles'):
                                    candle_map[sym] = o['candles'][-5:]
                            btc_data = None
                            btc_price = TitanState.market_snapshot.get("btc_pulse", {}).get("price")
                            if btc_price:
                                btc_data = {"current": btc_price, "prev_4h": btc_price * (1 + (TitanState.market_snapshot.get("btc_pulse", {}).get("change_raw", 0) or 0))}
                            guard_result = position_guard.guard_all_positions(
                                paper_trader, pt_price_map, candle_map=candle_map, btc_data=btc_data, atr_map=pt_atr_map)
                            for act in guard_result.get("actions", []):
                                TitanState.add_log("action", f"🛡️ 持仓守卫: {act['symbol']} {act['action']} - {act['reason']}")
                            TitanState.market_snapshot["position_guard"] = {
                                "last_check": guard_result.get("timestamp"),
                                "checked": guard_result.get("checked", 0),
                                "actions_count": len(guard_result.get("actions", [])),
                                "evaluations": guard_result.get("evaluations", [])[:10],
                            }
                    except Exception as e:
                        print(f"[SCAN] 持仓守卫异常: {e}", flush=True)

                    try:
                        if paper_trader.positions and pt_price_map:
                            pos_display = paper_trader.get_positions_display(pt_price_map)
                            advisor_context = {
                                "regime": getattr(dispatcher, 'current_regime', 'unknown'),
                                "btc_price": TitanState.market_snapshot.get("btc_pulse", {}).get("price", 0),
                                "btc_change": TitanState.market_snapshot.get("btc_pulse", {}).get("change", "0"),
                                "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
                                "size_multiplier": ai_coordinator.get_size_multiplier(),
                                "drawdown_pct": ai_coordinator.module_metrics.get("drawdown_pct", 0),
                                "consecutive_wins": paper_trader.consecutive_wins,
                                "consecutive_losses": paper_trader.consecutive_losses,
                            }
                            advisor_results = position_advisor.advise_all_positions(pos_display, advisor_context)
                            for adv in advisor_results:
                                pid = adv.get("position_id")
                                if pid and pid in paper_trader.positions:
                                    paper_trader.positions[pid]["ai_advisor"] = {
                                        "action": adv.get("action", "hold"),
                                        "confidence": adv.get("confidence", 50),
                                        "summary": adv.get("summary", ""),
                                        "risk": adv.get("risk_assessment", "medium"),
                                        "urgency": adv.get("urgency", "low"),
                                        "reasoning": adv.get("reasoning_chain", [])[:3],
                                        "timestamp": adv.get("timestamp", ""),
                                        "source": adv.get("source", "rule"),
                                    }
                            paper_trader.save()
                            TitanState.market_snapshot["position_advisor"] = {
                                "last_run": datetime.now(pytz.timezone('Asia/Shanghai')).strftime("%Y-%m-%d %H:%M:%S"),
                                "positions_advised": len(advisor_results),
                                "actions": {a.get("action", "hold"): sum(1 for x in advisor_results if x.get("action") == a.get("action")) for a in advisor_results},
                            }
                    except Exception as e:
                        print(f"[SCAN] AI持仓顾问异常: {e}", flush=True)

                    onchain_score = 0
                    try:
                        ext_snap = external_data.get_snapshot()
                        if ext_snap and 'composite_score' in ext_snap:
                            onchain_score = ext_snap['composite_score']
                    except Exception:
                        pass
                    
                    pt_equity = paper_trader.get_equity(pt_price_map, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                    c_status, c_actions, c_can_open, c_force_liq = constitution.check_health(
                        pt_equity, onchain_score, paper_trader.consecutive_losses)
                    
                    if c_force_liq and paper_trader.positions:
                        liquidated = paper_trader.force_liquidate_all(pt_price_map, "constitution_emergency")
                        for lt in liquidated:
                            TitanState.add_log("error", 
                                f"🚨 宪法紧急清仓: {lt['symbol']} PnL={lt['pnl_pct']:+.2f}%")
                    
                    for action in c_actions:
                        TitanState.add_log("warn" if "⚠" in action else "system", action)
                    
                    TitanState.market_snapshot["paper_trader"] = paper_trader.get_portfolio_summary(pt_price_map, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                    TitanState.market_snapshot["paper_positions"] = paper_trader.get_positions_display(pt_price_map)
                    TitanState.market_snapshot["constitution"] = {
                        "status": c_status,
                        "can_open_new": c_can_open,
                        "actions": c_actions,
                        **constitution.get_status(),
                    }
                except Exception as e:
                    print(f"[SCAN] Paper trader更新异常: {e}", flush=True)

                TitanState.market_snapshot["total_scanned"] = len(universe)
                TitanState.record_backtest_snapshot(opps)
                print(f"[SCAN] ✅ 扫描完成: {len(opps)}/{len(universe)} 标的 [{hunt_mode}]", flush=True)
                TitanState.add_log("system", f"[{scan_tag}] 扫描完成，{len(opps)}/{len(universe)} 标的已更新 [{hunt_mode}]")
                self.logger.info(f"扫描完成: {len(opps)}/{len(universe)} 标的 [{hunt_mode}] [{scan_tag}]")

                try:
                    _all_scores = sorted([o.get("score", 0) for o in opps], reverse=True)
                    _n_long_raw = sum(1 for o in opps if o.get("score", 0) > 0)
                    _n_short_raw = sum(1 for o in opps if (o.get("ml", {}) or {}).get("label", "") in ("看跌", "bearish"))
                    _n_passed_long_pre = len(alpha_long_signals) if 'alpha_long_signals' in dir() else 0
                    _n_passed_short_pre = len(alpha_short_candidates) if 'alpha_short_candidates' in dir() else 0
                    _n_traded = traded_count if 'traded_count' in dir() else 0
                    _btc_pulse_ss = TitanState.market_snapshot.get("btc_pulse", {})
                    _total_with_signal = _n_long_raw + _n_short_raw
                    _breadth = round(_n_long_raw / max(1, _total_with_signal) * 100, 1) if _total_with_signal > 0 else 50.0
                    TitanDB.save_scan_summary({
                        "total_scanned": len(opps),
                        "long_signals": _n_long_raw,
                        "short_signals": _n_short_raw,
                        "passed_long_prescan": _n_passed_long_pre,
                        "passed_short_prescan": _n_passed_short_pre,
                        "passed_all_gates": _n_traded,
                        "trades_opened": _n_traded,
                        "top5_scores": _all_scores[:5],
                        "long_threshold": ud_long_thr if 'ud_long_thr' in dir() else 65,
                        "short_threshold": ud_short_thr if 'ud_short_thr' in dir() else 50,
                        "fng_value": _btc_pulse_ss.get("fng", 0),
                        "btc_price": _btc_pulse_ss.get("price", 0),
                        "btc_macro_trend": scan_macro if 'scan_macro' in dir() else "",
                        "regime": str(dispatcher.current_regime) if dispatcher else "",
                        "market_breadth_long_pct": _breadth,
                    })
                except Exception as _ss_e:
                    self.logger.debug(f"扫描汇总保存失败: {_ss_e}")

                try:
                    pt_eq = paper_trader.get_equity(pt_price_map, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit) if pt_price_map else paper_trader.get_equity(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                    total_t = paper_trader.total_wins + paper_trader.total_losses
                    wr = (paper_trader.total_wins / total_t * 100) if total_t > 0 else 0
                    peak_eq = paper_trader.peak_equity
                    dd = ((peak_eq - pt_eq) / peak_eq * 100) if peak_eq > 0 else 0
                    btc_pulse_snap = TitanState.market_snapshot.get("btc_pulse", {})
                    ml_st = ml_engine.get_status()
                    TitanDB.save_system_snapshot({
                        "equity": pt_eq,
                        "capital": paper_trader.capital,
                        "total_trades": total_t,
                        "win_rate": round(wr, 1),
                        "max_drawdown": round(dd, 2),
                        "regime": dispatcher.current_regime,
                        "fng": btc_pulse_snap.get("fng", 0),
                        "btc_price": btc_pulse_snap.get("price", 0),
                        "ml_accuracy": ml_st.get("accuracy", 0),
                        "health_score": TitanState.market_snapshot.get("diagnostics", {}).get("health_score", 0),
                        "active_positions": len(paper_trader.positions),
                        "active_grids": len(grid_engine.active_grids),
                    })
                except Exception as e:
                    print(f"[DB] 系统快照保存失败: {e}", flush=True)

                alpha = [o for o in opps if o['score'] >= 80]
                now_ts = time.time()
                if alpha and (now_ts - self._last_email_time) > 1800:
                    market_info = {
                        'btc': TitanState.market_snapshot.get('btc_pulse', {}),
                        'fng': TitanState.market_snapshot.get('btc_pulse', {}).get('fng_detail', {}),
                        'total_scanned': len(universe),
                    }
                    ml_s = ml_engine.get_status()
                    sent = TitanMailer.send_report(alpha, market_info, ml_s)
                    if sent:
                        self._last_email_time = now_ts
                        TitanState.add_log("system", f"Alpha邮件报告已发送 ({len(alpha)}个信号, {len(TitanMailer.get_receivers())}个收件人)")

                today_bj = now_bj.strftime('%Y-%m-%d')
                if now_bj.hour == 8 and self._daily_report_sent_date != today_bj and len(opps) > 0:
                    market_info = {
                        'btc': TitanState.market_snapshot.get('btc_pulse', {}),
                        'fng': TitanState.market_snapshot.get('btc_pulse', {}).get('fng_detail', {}),
                        'total_scanned': len(universe),
                    }
                    ml_s = ml_engine.get_status()
                    sent = TitanMailer.send_daily_report(opps, market_info, ml_s)
                    if sent:
                        self._daily_report_sent_date = today_bj
                        TitanState.add_log("system", f"📊 每日日线分析报告已发送 ({today_bj})")

                if now_bj.hour == 3 and minute < 2:
                    if not darwin_lab.running:
                        try:
                            TitanState.add_log("system", "🧬 Darwin Lab自动进化启动 (凌晨3点定时)")
                            asyncio.create_task(darwin_lab.run_evolution(
                                self.exchange, universe[:10], generations=8, population_size=20
                            ))
                        except Exception as e:
                            TitanState.add_log("warn", f"Darwin自动进化失败: {e}")

                if minute < 3 and self._last_deep_evolution_hour != now_bj.hour:
                    self._last_deep_evolution_hour = now_bj.hour
                    try:
                        TitanState.add_log("system", f"🔬 自动深度复盘启动 (北京时间 {now_bj.strftime('%H:%M')})")
                        print(f"[AUTO-EVO] 深度复盘启动 BJ {now_bj.strftime('%H:%M')}", flush=True)
                        from server.routes.system import full_training_cycle
                        evo_result = await full_training_cycle()
                        ok_steps = sum(1 for s in evo_result.get("steps", []) if s.get("status") == "ok")
                        total_steps = len(evo_result.get("steps", []))
                        TitanState.add_log("system",
                            f"🔬 深度复盘完成: {ok_steps}/{total_steps}步成功, 耗时{evo_result.get('elapsed_seconds', 0):.1f}s")
                        print(f"[AUTO-EVO] 深度复盘完成: {ok_steps}/{total_steps} steps", flush=True)
                    except Exception as e:
                        TitanState.add_log("warn", f"自动深度复盘异常: {str(e)[:80]}")
                        print(f"[AUTO-EVO] 深度复盘异常: {e}", flush=True)

                if self._fetch_count % 15 == 0 and not mega_backtest.running:
                    try:
                        evo_data = {}
                        evo_symbols = universe[:50]
                        for i in range(0, len(evo_symbols), 5):
                            batch = evo_symbols[i:i+5]
                            fetch_tasks = [self.exchange.fetch_ohlcv(f"{s}/USDT", '1h', limit=1000) for s in batch]
                            fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
                            for s, r in zip(batch, fetch_results):
                                if not isinstance(r, Exception) and r and len(r) > 100:
                                    evo_data[s] = pd.DataFrame(r, columns=['t','o','h','l','c','v'])
                            await asyncio.sleep(0.2)
                        if len(evo_data) >= 10:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, mega_backtest.run_evolution_cycle, evo_data, 100)
                            TitanState.add_log("system",
                                f"🔄 自动进化: MegaBacktest 100次迭代 {len(evo_data)}资产 Calmar={mega_backtest.best_calmar:.3f}")
                            if self._fetch_count % 45 == 0 and not monte_carlo.running:
                                await loop.run_in_executor(None, monte_carlo.run_evolution, evo_data, 100, 200)
                                TitanState.add_log("system",
                                    f"🔄 自动进化: MC资管 100迭代 Calmar={monte_carlo.best_calmar:.3f}")
                    except Exception as e:
                        TitanState.add_log("warn", f"自动进化异常: {str(e)[:60]}")

                if minute < 2 and self._last_diag_hour != now_bj.hour:
                    self._last_diag_hour = now_bj.hour
                    try:
                        ml_acc = feedback_engine.get_rolling_accuracy()
                        gov_status = governor.get_status()
                        reflection = titan_agi.self_reflect(
                            ml_accuracy=ml_acc,
                            governor_state=gov_status,
                        )
                        if reflection.get("findings"):
                            TitanState.add_log("system", f"🧠 AGI自省完成: {len(reflection['findings'])}条发现")
                    except Exception as e:
                        TitanState.add_log("warn", f"AGI自省异常: {e}")

                    try:
                        from server.titan_ai_diagnostic import ai_diagnostic
                        diag_modules = {
                            "ml_engine": ml_engine,
                            "paper_trader": paper_trader,
                            "return_target": return_target,
                            "risk_budget": risk_budget,
                            "dispatcher": dispatcher,
                            "synapse": synapse,
                            "signal_quality": signal_quality,
                            "ai_coordinator": ai_coordinator,
                            "unified_decision": unified_decision,
                            "constitution": constitution,
                            "adaptive_weights": adaptive_weights,
                            "feedback_engine": feedback_engine,
                            "mega_backtest": mega_backtest,
                            "grid_engine": grid_engine,
                            "market_snapshot": TitanState.market_snapshot,
                        }
                        try:
                            from server.titan_return_rate_agent import return_rate_agent
                            diag_modules["return_rate_agent"] = return_rate_agent
                        except Exception:
                            pass
                        loop = asyncio.get_event_loop()
                        diag_result = await loop.run_in_executor(None, ai_diagnostic.run_diagnostic, diag_modules)
                        if diag_result.get("status") == "ok":
                            health = diag_result.get("health_score", 0)
                            severity = diag_result.get("severity", "unknown")
                            TitanState.add_log("system", f"🏥 AI系统诊断完成: 健康分{health}/100 [{severity}]")

                            try:
                                self._check_cto_alert(health, severity, diag_result, paper_trader, constitution, ai_coordinator)
                            except Exception as alert_err:
                                self.logger.warning(f"CTO预警检查异常: {alert_err}")

                            try:
                                self._auto_execute_diagnostic(health, diag_result)
                            except Exception as exec_err:
                                self.logger.warning(f"自动执行诊断建议异常: {exec_err}")
                        else:
                            TitanState.add_log("warn", f"AI诊断: {diag_result.get('status','unknown')}")
                    except Exception as e:
                        TitanState.add_log("warn", f"AI系统诊断异常: {str(e)[:60]}")

                if now_bj.hour in {0, 4, 8, 12, 16, 20} and minute < 2 and self._last_agi_reflect_hour != now_bj.hour:
                    self._last_agi_reflect_hour = now_bj.hour
                    try:
                        btc_info = TitanState.market_snapshot.get("btc_pulse", {})
                        summary = f"BTC:{btc_info.get('price',0)}, FNG:{btc_info.get('fng',50)}"
                        result = await titan_agi.llm_deep_reflection(summary)
                        if result.get("success"):
                            TitanState.add_log("system", f"🧠 AGI深度反思完成(LLM)")
                    except Exception as e:
                        TitanState.add_log("warn", f"AGI深度反思异常: {e}")

                if now_bj.hour == 4 and minute < 3 and self._last_comprehensive_optimize_date != today_bj:
                    self._last_comprehensive_optimize_date = today_bj
                    TitanState.add_log("system", "🔧 综合优化自动触发 (每日凌晨4:00定时)")
                    async def _auto_optimize_task():
                        try:
                            opt_result = await comprehensive_optimize(source="auto_daily_4am")
                            steps_ok = sum(1 for s in opt_result.get("steps", []) if s.get("status") != "error")
                            TitanState.add_log("system", f"✅ 综合优化自动完成: {steps_ok}/{len(opt_result.get('steps', []))}步")
                        except Exception as e:
                            TitanState.add_log("warn", f"综合优化自动执行异常: {str(e)[:60]}")
                    asyncio.create_task(_auto_optimize_task())

                try:
                    from server.titan_ai_diagnostic import ai_diagnostic
                    last_diag = getattr(ai_diagnostic, '_last_result', {})
                    diag_health = last_diag.get("health_score", 100)
                    last_diag_time = last_diag.get("timestamp", "")
                    if diag_health < 60 and not getattr(self, '_emergency_optimize_triggered_today', None) == today_bj:
                        self._emergency_optimize_triggered_today = today_bj
                        TitanState.add_log("system", f"⚠️ 综合优化紧急触发 (健康分={diag_health}<60)")
                        async def _emergency_optimize_task():
                            try:
                                opt_result = await comprehensive_optimize(source=f"auto_emergency_health_{diag_health}")
                                TitanState.add_log("system", f"🚨 紧急综合优化完成: {len(opt_result.get('steps', []))}步")
                            except Exception as opt_err:
                                TitanState.add_log("warn", f"紧急综合优化异常: {str(opt_err)[:60]}")
                        asyncio.create_task(_emergency_optimize_task())
                except Exception:
                    pass

                if now_bj.hour in {8, 20} and minute < 3:
                    cto_today = today_bj
                    if self._last_cto_briefing_date != cto_today or self._last_cto_briefing_hour != now_bj.hour:
                        self._last_cto_briefing_date = cto_today
                        self._last_cto_briefing_hour = now_bj.hour
                        TitanState.add_log("system", f"📋 CTO简报自动生成 (每日{now_bj.hour}:00定时)")
                        try:
                            asyncio.create_task(_run_cto_briefing())
                        except Exception as e:
                            TitanState.add_log("warn", f"CTO简报自动触发失败: {e}")

                if now_bj.hour == 12 and minute < 3:
                    inspect_today = now_bj.strftime('%Y-%m-%d')
                    if getattr(self, '_last_self_inspection_date', None) != inspect_today:
                        self._last_self_inspection_date = inspect_today
                        TitanState.add_log("system", "🔍 系统自检自动触发 (每日12:00定时)")
                        async def _auto_self_inspection():
                            try:
                                result = self_inspector.run_all(use_ai_summary=True)
                                critical = result.get("by_severity", {}).get("critical", 0)
                                warning = result.get("by_severity", {}).get("warning", 0)
                                total = result.get("total_findings", 0)
                                TitanState.add_log("system", f"✅ 系统自检完成: {total}项发现 (严重{critical} 警告{warning})")
                                if critical > 0:
                                    TitanState.add_log("warn", f"⚠️ 自检发现{critical}个严重问题，请查看CTO仪表盘")
                            except Exception as e:
                                TitanState.add_log("warn", f"系统自检异常: {str(e)[:60]}")
                        asyncio.create_task(_auto_self_inspection())

                current_week = now_bj.isocalendar()[1]
                if now_bj.weekday() == 6 and now_bj.hour == 2 and minute < 3:
                    if self._last_weekly_full_pipeline_week != current_week:
                        self._last_weekly_full_pipeline_week = current_week
                        TitanState.add_log("system", "🏭 每周全量6步流水线自动启动 (每周日凌晨2:00)")
                        async def _weekly_full_pipeline():
                            try:
                                result = await start_deep_training_all(start_step=1)
                                TitanState.add_log("system", f"🏭 每周全量流水线已提交: {result.get('status', 'unknown')}, {result.get('total_assets', 0)}个资产")
                            except Exception as e:
                                TitanState.add_log("warn", f"每周全量流水线启动失败: {str(e)[:80]}")
                        asyncio.create_task(_weekly_full_pipeline())

                if self._fetch_count % 10 == 0:
                    titan_agi.save()
                    agent_memory.save()

                    try:
                        pt_equity_snap = paper_trader.get_equity({}, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit)
                        external_data.memory_bank.record_performance_snapshot({
                            "equity": pt_equity_snap,
                            "total_trades": paper_trader.total_wins + paper_trader.total_losses,
                            "win_rate": round(paper_trader.total_wins / max(1, paper_trader.total_wins + paper_trader.total_losses) * 100, 1),
                            "sharpe": 0,
                            "max_drawdown": getattr(paper_trader, "max_drawdown_pct", 0),
                            "open_positions": len(paper_trader.positions),
                            "regime": dispatcher.current_regime,
                        })
                    except Exception:
                        pass

            except Exception as e:
                self.logger.error(f"扫描错误: {e}")
                TitanState.add_log("warn", f"扫描异常: {str(e)[:60]}")
            finally:
                TitanState.market_snapshot["scan_progress"] = {
                    "current": TitanState.market_snapshot.get("scan_progress", {}).get("total", 0),
                    "total": TitanState.market_snapshot.get("scan_progress", {}).get("total", 0),
                    "scanning": False,
                    "last_updated": time.time()
                }

            await asyncio.sleep(60)

    async def run_fast_monitor_loop(self):
        FAST_INTERVAL = 5
        self.logger.info("⚡ 快速行情监控启动 (5秒刷新)")
        TitanState.add_log("system", "⚡ 快速行情+持仓监控启动 (5秒刷新)")
        print("[FAST] 快速行情+持仓监控启动 (每5秒)", flush=True)
        tick_count = 0
        last_ticker_time = 0
        consecutive_errors = 0
        for wait_i in range(30):
            if hasattr(self.exchange, 'markets') and self.exchange.markets:
                print(f"[FAST] 交易所已就绪 ({len(self.exchange.markets)}市场)", flush=True)
                break
            await asyncio.sleep(2)
        else:
            print("[FAST] 交易所加载超时，尝试自行加载...", flush=True)
            try:
                await self.exchange.load_markets()
                print(f"[FAST] 自行加载成功 ({len(self.exchange.markets)}市场)", flush=True)
            except Exception as e:
                print(f"[FAST] 加载失败: {e}", flush=True)

        while True:
            try:
                tick_count += 1
                now_ts = time.time()

                backoff = max(5, min(consecutive_errors * 5, 30))
                if now_ts - last_ticker_time >= backoff:
                    try:
                        tracked_symbols = set()
                        for pid, pos in paper_trader.positions.items():
                            sym = pos.get('symbol', '')
                            if sym:
                                tracked_symbols.add(f"{sym}/USDT")
                        for gsym in grid_engine.active_grids:
                            if gsym:
                                tracked_symbols.add(f"{gsym}/USDT")
                        tracked_symbols.add("BTC/USDT")
                        tracked_symbols.add("ETH/USDT")

                        if len(tracked_symbols) <= 10:
                            price_map = {}
                            for sym in tracked_symbols:
                                try:
                                    ticker = await asyncio.wait_for(
                                        self.exchange.fetch_ticker(sym), timeout=5
                                    )
                                    base = sym.split('/')[0]
                                    last_p = float(ticker.get('last', 0) or 0)
                                    if last_p > 0:
                                        price_map[base] = last_p
                                except Exception:
                                    pass
                        else:
                            tickers = await asyncio.wait_for(
                                self.exchange.fetch_tickers(), timeout=15
                            )
                            price_map = {}
                            for sym, ticker in tickers.items():
                                if sym.endswith('/USDT'):
                                    base = sym.split('/')[0]
                                    last_p = float(ticker.get('last', 0) or 0)
                                    if last_p > 0:
                                        price_map[base] = last_p

                        last_ticker_time = time.time()
                        consecutive_errors = 0

                        TitanState.market_snapshot['_live_prices'] = price_map
                        TitanState.market_snapshot['_live_price_ts'] = time.time()

                        btc_p = price_map.get('BTC', 0)
                        if btc_p > 0:
                            TitanState.market_snapshot['btc_price'] = btc_p

                        if tick_count % 60 == 1:
                            print(f"[FAST] tick#{tick_count} 行情刷新: {len(price_map)}对 BTC=${btc_p:.0f} (追踪{len(tracked_symbols)})", flush=True)

                    except asyncio.TimeoutError:
                        consecutive_errors += 1
                        if tick_count <= 3 or tick_count % 12 == 0:
                            print(f"[FAST] tick#{tick_count} 行情获取超时(退避{backoff}s)", flush=True)
                    except Exception as e:
                        consecutive_errors += 1
                        err_msg = str(e)[:80]
                        if '429' in err_msg or 'rate' in err_msg.lower():
                            consecutive_errors = max(consecutive_errors, 3)
                            print(f"[FAST] 限流检测，退避至{backoff}s", flush=True)
                        elif tick_count <= 5 or tick_count % 12 == 0:
                            print(f"[FAST] tick#{tick_count} 行情异常: {err_msg}", flush=True)

                live_prices = TitanState.market_snapshot.get('_live_prices', {})

                if paper_trader.positions and live_prices:
                    try:
                        async with TitanState.get_position_lock():
                            current_regime = getattr(dispatcher, 'current_regime', None)
                            closed_trades = paper_trader.update_positions(live_prices, regime=current_regime)
                        for ct in closed_trades:
                            reason_cn = {"tp_hit": "止盈", "sl_hit": "止损", "trailing_sl": "追踪止损"}.get(ct.get('reason',''), ct.get('reason',''))
                            TitanState.add_log("action",
                                f"⚡ 快速平仓: {ct['symbol']} {ct['direction']} {reason_cn} PnL={ct['pnl_pct']:+.2f}%")
                            print(f"[FAST] 平仓: {ct['symbol']} {reason_cn} PnL={ct['pnl_pct']:+.2f}%", flush=True)
                            try:
                                ct_strategy = ct.get("strategy_type", "trend")
                                attribution.record_trade({
                                    "symbol": ct["symbol"],
                                    "direction": ct.get("direction", "long"),
                                    "entry_price": ct.get("entry_price", 0),
                                    "exit_price": ct.get("exit_price", 0),
                                    "pnl_pct": ct["pnl_pct"],
                                    "pnl_usd": ct.get("pnl_value", 0),
                                    "strategy_type": ct_strategy,
                                    "signal_score": ct.get("signal_score", 0),
                                    "entry_time": ct.get("open_time", ""),
                                    "exit_time": ct.get("close_time", ""),
                                    "holding_hours": ct.get("hold_hours", 0),
                                    "market_regime": dispatcher.current_regime,
                                })
                                titan_critic.record_trade({
                                    "sym": ct["symbol"],
                                    "direction": ct.get("direction", "long"),
                                    "entry": ct.get("entry_price", 0),
                                    "exit": ct.get("exit_price", 0),
                                    "pnl": ct["pnl_pct"],
                                    "result": "win" if ct["pnl_pct"] > 0 else "loss",
                                    "score": ct.get("signal_score", 0),
                                    "regime": dispatcher.current_regime,
                                })
                                feedback_engine.record_prediction_outcome(
                                    ct["symbol"],
                                    ct.get("ml_label", "unknown"),
                                    "win" if ct["pnl_pct"] > 0 else "loss",
                                    features_snapshot={
                                        "regime": dispatcher.current_regime,
                                        "adx": ct.get("report", {}).get("adx", 20) if ct.get("report") else 20,
                                        "vol_ratio": ct.get("report", {}).get("vol_ratio", 1.0) if ct.get("report") else 1.0,
                                    },
                                    direction=ct.get("direction", "long"),
                                )
                                risk_budget.release_capital(
                                    ct_strategy,
                                    ct.get("position_value", 0),
                                    ct.get("pnl_value", 0),
                                )
                                signal_quality.record_outcome(
                                    {"strategy": ct_strategy},
                                    ct["pnl_pct"] > 0,
                                    ct["pnl_pct"],
                                    ct["symbol"],
                                    dispatcher.current_regime,
                                )
                            except Exception:
                                pass
                    except Exception as e:
                        if tick_count % 60 == 0:
                            print(f"[FAST] 持仓监控异常: {str(e)[:80]}", flush=True)

                if grid_engine.active_grids and live_prices:
                    try:
                        closed_grids, grid_trades = grid_engine.update_grids(live_prices, ml_predictions=None)
                        if grid_trades or closed_grids:
                            grid_engine.save()
                            for gt in grid_trades:
                                print(f"[FAST] 🔲 网格成交: {gt['symbol']} {gt['side'].upper()} @ {gt['price']}", flush=True)
                            for cg in closed_grids:
                                TitanState.add_log("action",
                                    f"⚡ 网格平仓: {cg['symbol']} PnL=${cg.get('grid_pnl',0):.2f}")
                                try:
                                    import uuid
                                    grid_mode = cg.get("spacing_mode", "arithmetic")
                                    grid_pnl_usd = cg.get("grid_pnl", 0)
                                    grid_capital = cg.get("capital_used", 0) or cg.get("allocation", 1)
                                    grid_pnl_pct = round((grid_pnl_usd / grid_capital * 100) if grid_capital > 0 else 0, 2)
                                    created_str = cg.get("created_at", "")
                                    try:
                                        grid_open_time = datetime.fromisoformat(created_str) if created_str else datetime.now()
                                    except Exception:
                                        grid_open_time = datetime.now()
                                    TitanDB.save_trade({
                                        "id": uuid.uuid4().hex[:8], "symbol": cg["symbol"], "direction": "grid",
                                        "strategy_type": f"grid_{grid_mode}", "entry_price": cg.get("entry_price", 0),
                                        "exit_price": cg.get("close_price", cg.get("last_price", 0)),
                                        "tp_price": cg.get("upper", 0), "sl_price": cg.get("lower", 0),
                                        "position_value": grid_capital, "pnl_pct": grid_pnl_pct,
                                        "pnl_value": round(grid_pnl_usd, 2),
                                        "result": "win" if grid_pnl_usd > 0 else "loss",
                                        "reason": cg.get("close_reason", "grid_complete"), "signal_score": 0,
                                        "ml_confidence": 0, "ai_verdict": "", "mtf_alignment": 0,
                                        "open_time": grid_open_time.isoformat() if hasattr(grid_open_time, 'isoformat') else str(grid_open_time),
                                        "close_time": datetime.now().isoformat(),
                                        "hold_hours": round((datetime.now() - grid_open_time).total_seconds() / 3600, 1),
                                        "regime": dispatcher.current_regime, "is_grid_trade": True,
                                        "spacing_mode": grid_mode,
                                    })
                                except Exception as e:
                                    print(f"[FAST] 网格交易写入DB失败: {e}", flush=True)
                        elif tick_count % 120 == 0:
                            grid_engine.save()
                    except Exception as e:
                        if tick_count % 60 == 0:
                            print(f"[FAST] 网格更新异常: {str(e)[:100]}", flush=True)

            except Exception as e:
                if tick_count % 60 == 0:
                    self.logger.error(f"快速监控异常: {e}")

            await asyncio.sleep(FAST_INTERVAL)

    def _auto_execute_diagnostic(self, health, diag_result):
        executed = []
        tz = pytz.timezone(CONFIG['TIMEZONE'])
        now_str = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

        priorities = diag_result.get("top_priorities", [])
        import re
        p1_assets = []
        for p in priorities:
            if p.get("auto_applicable") and p.get("action"):
                match = re.search(r'[\(（]([^)）]+)[\)）]', p["action"])
                if match:
                    found = [a.strip() for a in re.split(r'[,，、]', match.group(1)) if a.strip()]
                    p1_assets.extend(found)

        if p1_assets:
            import re as re_diag
            valid_sym = re_diag.compile(r'^[A-Z0-9]{2,15}$')
            frozen = []
            for asset in p1_assets[:5]:
                asset_clean = asset.replace("/USDT", "").replace("_USDT", "").upper().strip()
                if not valid_sym.match(asset_clean):
                    continue
                existing = any(r.get("type") == "asset_avoid" and r.get("asset") == asset_clean for r in synapse.cross_strategy_rules)
                if not existing:
                    synapse.cross_strategy_rules.append({
                        "type": "asset_avoid", "asset": asset_clean, "win_rate": 0, "trades": 0,
                        "applies_to": "all", "reason": f"自动诊断冻结 {now_str}",
                    })
                    frozen.append(asset_clean)
            if frozen:
                synapse.save()
                executed.append(f"冻结亏损资产: {', '.join(frozen)}")

        if health < 50:
            new_size = max(0.3, min(0.8, health / 100))
            old_size = ai_coordinator.recommendations.get("size_multiplier", 1.0)
            if abs(new_size - old_size) > 0.05:
                ai_coordinator.recommendations["size_multiplier"] = new_size
                ai_coordinator.recommendations["throttle_level"] = "tight" if health < 35 else "reduced"
                capital_sizer.update_global_multipliers("ai_override_mult", new_size)
                ai_coordinator.save()
                executed.append(f"仓位缩减 {old_size:.2f}→{new_size:.2f}")

        if health < 40:
            old_daily = constitution.RISK_LIMITS.get("MAX_DAILY_DRAWDOWN", 0.02)
            if old_daily > 0.015:
                constitution.RISK_LIMITS["MAX_DAILY_DRAWDOWN"] = 0.015
                constitution.RISK_LIMITS["MAX_TOTAL_DRAWDOWN"] = 0.03
                constitution.save()
                executed.append("收紧断路器: 日回撤1.5%/总回撤3%")

        try:
            fb_acc = feedback_engine.get_rolling_accuracy()
            fb_total = len(getattr(feedback_engine, 'accuracy_history', []))
            if fb_acc is not None and fb_acc < 40 and fb_total >= 20:
                feedback_engine.auto_adjust_critic(titan_critic)
                suggestions = feedback_engine.suggest_threshold_adjustments()
                applied_sug = 0
                for sug in suggestions:
                    if sug.get("type") == "increase_ml_weight_caution" and hasattr(adaptive_weights, 'ml_weight_override'):
                        adaptive_weights.ml_weight_override = sug.get("ml_weight", 0.25)
                        applied_sug += 1
                    elif sug.get("type") == "raise_score_threshold":
                        ai_coordinator.recommendations["min_score_threshold"] = sug.get("value", 85)
                        applied_sug += 1
                if applied_sug:
                    executed.append(f"ML反馈修正: {applied_sug}条")
        except Exception:
            pass

        dims = diag_result.get("dimensions", {})
        for dim_name, dim_data in dims.items():
            if not isinstance(dim_data, dict):
                continue
            for sug in dim_data.get("suggestions", []):
                if not isinstance(sug, str):
                    continue
                sug_lower = sug.lower()
                if "ml权重" in sug and ("降" in sug or "减" in sug):
                    try:
                        import re as _re
                        vals = _re.findall(r'(\d+\.?\d*)', sug)
                        if vals:
                            target_val = float(vals[-1])
                            if target_val < 1:
                                adaptive_weights.ml_weight_override = target_val
                                executed.append(f"ML权重→{target_val}")
                    except Exception:
                        pass
                elif "冻结" in sug and ("策略" in sug or "资产" in sug):
                    try:
                        import re as _re
                        match = _re.search(r'[\(（]([^)）]+)[\)）]', sug)
                        if match:
                            for a in _re.split(r'[,，、]', match.group(1)):
                                a_clean = a.strip().replace("/USDT", "").upper()
                                if a_clean and _re.match(r'^[A-Z0-9]{2,15}$', a_clean) and not any(r.get("type") == "asset_avoid" and r.get("asset") == a_clean for r in synapse.cross_strategy_rules):
                                    synapse.cross_strategy_rules.append({
                                        "type": "asset_avoid", "asset": a_clean, "win_rate": 0, "trades": 0,
                                        "applies_to": "all", "reason": f"诊断建议冻结 {now_str}",
                                    })
                                    executed.append(f"冻结{a_clean}")
                    except Exception:
                        pass

        coord_tips = ai_coordinator.recommendations.get("evolution_tips", [])
        priority_action = ai_coordinator.recommendations.get("priority_action", "")
        tip_actions = coord_tips + ([priority_action] if priority_action else [])
        for tip in tip_actions:
            if not isinstance(tip, str):
                continue
            tip_lower = tip.lower()
            if "重新训练" in tip or "触发训练" in tip or "retrain" in tip_lower:
                try:
                    in_progress = getattr(ml_engine, '_training_in_progress', False)
                    if not in_progress and self._last_training_data:
                        ml_engine.train(self._last_training_data)
                        executed.append("触发ML重新训练(CTO建议)")
                except Exception:
                    pass
            elif ("降低" in tip or "减少" in tip) and "仓位" in tip:
                try:
                    current_mult = ai_coordinator.recommendations.get("size_multiplier", 1.0)
                    if current_mult > 0.6:
                        new_mult = max(0.5, current_mult * 0.85)
                        ai_coordinator.recommendations["size_multiplier"] = round(new_mult, 3)
                        capital_sizer.update_global_multipliers("ai_override_mult", new_mult)
                        executed.append(f"CTO建议降仓→{new_mult:.2f}")
                except Exception:
                    pass
            elif "保守" in tip or "防守" in tip:
                try:
                    ai_coordinator.recommendations["risk_level"] = "conservative"
                    executed.append("切换保守模式(CTO建议)")
                except Exception:
                    pass

        exec_record = {
            "time": now_str,
            "health": health,
            "actions": executed if executed else ["无需干预"],
            "source": "auto_loop",
            "had_actions": len(executed) > 0,
        }
        if not hasattr(TitanState, '_auto_exec_history'):
            TitanState._auto_exec_history = []
        TitanState._auto_exec_history.append(exec_record)
        if len(TitanState._auto_exec_history) > 100:
            TitanState._auto_exec_history = TitanState._auto_exec_history[-50:]

        if executed:
            TitanState.add_log("system", f"🔄 自动闭环: {len(executed)}项建议已执行 → {' | '.join(executed[:3])}")

        try:
            history_path = os.path.join(CONFIG.get("DATA_DIR", "data"), "auto_exec_history.json")
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            with open(history_path, "w") as f:
                json.dump(TitanState._auto_exec_history[-100:], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _check_cto_alert(self, health, severity, diag_result, paper_trader, constitution, ai_coordinator):
        alert_details = []
        auto_actions = []
        alert_type = None
        summary = ""

        c_status = constitution.get_status() if hasattr(constitution, 'get_status') else {}
        cons_losses = getattr(paper_trader, 'consecutive_losses', 0)
        recs = getattr(ai_coordinator, 'recommendations', {})
        coord_status = ai_coordinator.get_status() if hasattr(ai_coordinator, 'get_status') else {}

        if c_status.get("permanent_breaker"):
            alert_type = "critical"
            summary = "永久熔断器已触发 — 系统停止交易"
            alert_details.append("永久熔断器已触发，所有交易活动已暂停")
            alert_details.append(f"当前回撤: {c_status.get('max_drawdown_pct', 0):.2f}%")
            auto_actions.append({"action": "所有新交易已自动阻止", "applied": True})

        if c_status.get("daily_breaker"):
            alert_type = alert_type or "critical"
            summary = summary or "当日熔断器已触发 — 今日暂停交易"
            alert_details.append("当日亏损触发熔断，今日交易已暂停")
            auto_actions.append({"action": "当日交易已自动暂停", "applied": True})

        if health < 25 and not alert_type:
            alert_type = "critical"
            summary = f"系统健康分极低: {health}/100"
            alert_details.append(f"系统健康评分: {health}/100 (危险)")
            alert_details.append(f"诊断严重级别: {severity}")

        if health < 40 and not alert_type:
            alert_type = "warning"
            summary = f"系统健康分偏低: {health}/100"
            alert_details.append(f"系统健康评分: {health}/100 (需关注)")

        if cons_losses >= 5:
            alert_type = alert_type or "warning"
            summary = summary or f"连续亏损{cons_losses}次 — 注意风控"
            alert_details.append(f"模拟交易连续亏损: {cons_losses}次")
            auto_actions.append({"action": f"仓位已自动缩减 (连亏惩罚)", "applied": True})

        frozen = coord_status.get("frozen_strategies", [])
        if isinstance(frozen, list) and len(frozen) >= 2:
            alert_type = alert_type or "warning"
            summary = summary or f"{len(frozen)}个策略被冻结"
            alert_details.append(f"被冻结策略: {', '.join(str(f) for f in frozen[:5])}")
            auto_actions.append({"action": "资金已自动转移至活跃策略", "applied": True})

        dims = diag_result.get("dimensions", {})
        for dim_name, dim_data in dims.items():
            if isinstance(dim_data, dict):
                dim_score = dim_data.get("score", 100)
                if dim_score < 20:
                    alert_details.append(f"⚠ {dim_name}: {dim_score}/100 — {dim_data.get('issues', ['偏低'])[0] if dim_data.get('issues') else '偏低'}")

        if recs.get("throttle_level") in ("emergency", "halt"):
            alert_type = alert_type or "warning"
            summary = summary or "CTO已启动紧急油门控制"
            alert_details.append(f"油门级别: {recs.get('throttle_level')}")
            auto_actions.append({"action": f"仓位乘数已调至 {recs.get('size_multiplier', 'N/A')}", "applied": True})

        if not alert_type:
            return

        coordinator_recs = {
            "size_multiplier": recs.get("size_multiplier", "N/A"),
            "throttle_level": recs.get("throttle_level", "N/A"),
            "regime_bias": recs.get("regime_bias", "N/A"),
            "risk_level": recs.get("risk_level", "N/A"),
            "reasoning": recs.get("reasoning", ""),
        }

        sent = TitanMailer.send_cto_alert(
            alert_type=alert_type,
            summary=summary,
            details=alert_details,
            auto_actions=auto_actions,
            coordinator_recs=coordinator_recs,
        )
        if sent:
            TitanState.add_log("system", f"📧 CTO预警邮件已发送: [{alert_type}] {summary[:40]}")

    async def fetch_training_history(self, symbols, limit=500):
        training_map = {}
        for asset in symbols[:30]:
            sym = f"{asset}/USDT"
            try:
                tasks = [
                    self.exchange.fetch_ohlcv(sym, '1h', limit=limit),
                    self.exchange.fetch_ohlcv(sym, '4h', limit=limit),
                ]
                res = await asyncio.gather(*tasks, return_exceptions=True)
                if any(isinstance(r, Exception) for r in res):
                    continue
                training_map[asset] = {
                    '1h': pd.DataFrame(res[0], columns=['t', 'o', 'h', 'l', 'c', 'v']),
                    '4h': pd.DataFrame(res[1], columns=['t', 'o', 'h', 'l', 'c', 'v']),
                }
            except Exception:
                continue
        return training_map

    async def _fetch_ohlcv_paginated(self, symbol, timeframe, total_bars):
        all_data = []
        batch = 1000
        now_ms = int(time.time() * 1000)

        if timeframe == '1h':
            bar_ms = 3600 * 1000
        elif timeframe == '4h':
            bar_ms = 4 * 3600 * 1000
        elif timeframe == '1d':
            bar_ms = 24 * 3600 * 1000
        else:
            bar_ms = 3600 * 1000

        since = now_ms - total_bars * bar_ms
        retries = 0

        while since < now_ms:
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=batch)
                if not ohlcv:
                    break
                all_data.extend(ohlcv)
                last_ts = ohlcv[-1][0]
                since = last_ts + bar_ms
                retries = 0
                await asyncio.sleep(0.3)
            except Exception as e:
                retries += 1
                if retries > 3:
                    break
                await asyncio.sleep(2 * retries)

        seen = set()
        unique = []
        for bar in all_data:
            if bar[0] not in seen:
                seen.add(bar[0])
                unique.append(bar)
        unique.sort(key=lambda x: x[0])
        return unique

    async def fetch_deep_training_history(self, symbols):
        training_map = {}
        total_1h = 8000
        total_4h = 6000
        total_1d = 1500
        max_assets = 69

        for i, asset in enumerate(symbols[:max_assets]):
            sym = f"{asset}/USDT"
            TitanState.add_log("ml", f"[深度训练] 获取 {asset} 历史数据 ({i+1}/{min(max_assets, len(symbols))})...")
            try:
                data_1h = await self._fetch_ohlcv_paginated(sym, '1h', total_1h)
                await asyncio.sleep(0.3)
                data_4h = await self._fetch_ohlcv_paginated(sym, '4h', total_4h)
                await asyncio.sleep(0.3)
                data_1d = await self._fetch_ohlcv_paginated(sym, '1d', total_1d)
                await asyncio.sleep(0.3)

                if len(data_1h) > 100 and len(data_4h) > 40:
                    entry = {
                        '1h': pd.DataFrame(data_1h, columns=['t', 'o', 'h', 'l', 'c', 'v']),
                        '4h': pd.DataFrame(data_4h, columns=['t', 'o', 'h', 'l', 'c', 'v']),
                    }
                    if len(data_1d) > 30:
                        entry['1d'] = pd.DataFrame(data_1d, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                    training_map[asset] = entry
                    daily_info = f" 1d={len(data_1d)}根" if len(data_1d) > 30 else ""
                    TitanState.add_log("ml", f"[深度训练] {asset}: 1h={len(data_1h)}根 4h={len(data_4h)}根{daily_info}")
                else:
                    TitanState.add_log("warn", f"[深度训练] {asset} 数据不足: 1h={len(data_1h)} 4h={len(data_4h)}")
            except Exception as e:
                TitanState.add_log("warn", f"[深度训练] {asset} 获取失败: {str(e)[:40]}")
                continue
        return training_map

    @staticmethod
    def _seconds_to_next_train_slot():
        bj_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(bj_tz)
        train_hours = [0, 4, 8, 12, 16, 20]
        current_hour = now.hour
        next_hour = None
        for h in train_hours:
            if h > current_hour:
                next_hour = h
                break
        if next_hour is None:
            next_hour = train_hours[0]
            next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0) + pd.Timedelta(days=1)
        else:
            next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        delta = (next_time - now).total_seconds()
        return max(60, int(delta))

    async def run_ml_training_loop(self):
        await asyncio.sleep(90)

        if ml_engine.needs_deep_training():
            TitanState.add_log("ml", "🧠 ML深度训练启动 — 获取深度历史数据(1h约11个月+4h约2.8年+1d约4年)，预计15-25分钟...")
            self.logger.info("ML深度训练启动: 5年历史数据")
            try:
                elite = list(CONFIG['ELITE_UNIVERSE'])
                training_data = await self.fetch_deep_training_history(elite)
                if training_data:
                    total_1h = sum(len(v['1h']) for v in training_data.values())
                    total_4h = sum(len(v['4h']) for v in training_data.values())
                    TitanState.add_log("ml", f"[深度训练] 数据获取完成: {len(training_data)}个资产, 1h={total_1h}根, 4h={total_4h}根")
                    TitanState.add_log("ml", "[深度训练] 开始训练模型...")

                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(None, ml_engine.train, training_data)
                    if success:
                        ml_engine.mark_deep_trained()
                        status = ml_engine.get_status()
                        TitanState.add_log("ml", f"🎯 ML深度训练完成! 准确率:{status['accuracy']}% F1:{status['f1']}% 样本:{status['samples']}")
                    else:
                        TitanState.add_log("warn", "ML深度训练跳过: 数据不足")
                else:
                    TitanState.add_log("warn", "ML深度训练数据获取失败")
            except Exception as e:
                self.logger.error(f"ML深度训练异常: {e}")
                TitanState.add_log("warn", f"ML深度训练异常: {str(e)[:50]}")
        else:
            TitanState.add_log("ml", "ML引擎常规首次训练启动（60天数据）...")
            self.logger.info("ML常规首次训练启动 (limit=2500)")
            try:
                elite = list(CONFIG['ELITE_UNIVERSE'])
                training_data = await self.fetch_training_history(elite, limit=2500)
                if training_data:
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(None, ml_engine.train, training_data)
                    if success:
                        status = ml_engine.get_status()
                        TitanState.add_log("ml", f"ML首次训练完成! 准确率:{status['accuracy']}% F1:{status['f1']}% 样本:{status['samples']}")
                    else:
                        TitanState.add_log("warn", "ML首次训练跳过: 数据不足")
            except Exception as e:
                self.logger.error(f"ML首次训练异常: {e}")
                TitanState.add_log("warn", f"ML首次训练异常: {str(e)[:50]}")

        while True:
            wait_sec = self._seconds_to_next_train_slot()
            bj_now = datetime.now(pytz.timezone('Asia/Shanghai'))
            TitanState.add_log("ml", f"下次训练: {wait_sec//3600}h{(wait_sec%3600)//60}m后 (北京时间 {bj_now.strftime('%H:%M')})")
            await asyncio.sleep(wait_sec)

            try:
                bj_train = datetime.now(pytz.timezone('Asia/Shanghai'))
                TitanState.add_log("ml", f"ML定时训练启动 (北京时间 {bj_train.strftime('%H:%M')})")
                self.logger.info(f"ML定时训练任务启动 (BJ {bj_train.strftime('%H:%M')})")

                elite = list(CONFIG['ELITE_UNIVERSE'])
                training_data = await self.fetch_training_history(elite, limit=2500)

                if training_data:
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(None, ml_engine.train, training_data)

                    if success:
                        status = ml_engine.get_status()
                        TitanState.add_log("ml", f"ML训练完成! 准确率:{status['accuracy']}% F1:{status['f1']}% 样本:{status['samples']}")
                    else:
                        TitanState.add_log("warn", "ML训练跳过: 数据不足")
                else:
                    TitanState.add_log("warn", "ML训练数据获取失败")

            except Exception as e:
                self.logger.error(f"ML训练异常: {e}")
                TitanState.add_log("warn", f"ML训练异常: {str(e)[:50]}")

    async def fetch_daily_history(self, symbols, total_bars=3000):
        daily_map = {}
        max_assets = min(len(symbols), 69)
        for i, asset in enumerate(symbols[:max_assets]):
            sym = f"{asset}/USDT"
            TitanState.add_log("ml", f"[资金管理] 获取 {asset} 日线数据 ({i+1}/{max_assets})...")
            try:
                data = await self._fetch_ohlcv_paginated(sym, '1d', total_bars)
                if len(data) > 100:
                    daily_map[asset] = pd.DataFrame(data, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                    TitanState.add_log("ml", f"[资金管理] {asset}: {len(data)}根日线")
                else:
                    TitanState.add_log("warn", f"[资金管理] {asset} 日线数据不足: {len(data)}")
                await asyncio.sleep(0.5)
            except Exception as e:
                TitanState.add_log("warn", f"[资金管理] {asset} 获取失败: {str(e)[:40]}")
                continue
        return daily_map

    async def run_mm_training_loop(self):
        await asyncio.sleep(120)

        if money_manager.needs_training():
            TitanState.add_log("ml", "💰 资金管理回测启动 — 获取8年日线数据(69资产)，预计10-15分钟...")
            self.logger.info("资金管理回测启动: 8年日线数据")
            try:
                elite = list(CONFIG['ELITE_UNIVERSE'])
                daily_data = await self.fetch_daily_history(elite, total_bars=3000)
                if daily_data:
                    total_bars_count = sum(len(v) for v in daily_data.values())
                    TitanState.add_log("ml", f"[资金管理] 数据获取完成: {len(daily_data)}个资产, 共{total_bars_count}根日线")
                    TitanState.add_log("ml", "[资金管理] 开始回测: 固定仓位 vs 凯利+ATR...")

                    def progress_cb(msg):
                        TitanState.add_log("ml", msg)

                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(
                        None, money_manager.run_historical_backtest, daily_data, ml_engine, progress_cb
                    )
                    if success:
                        status = money_manager.get_status()
                        fixed_ret = status.get('fixed', {}).get('total_return', 0)
                        ka_ret = status.get('kelly_atr', {}).get('total_return', 0)
                        imp = status.get('improvement', {}).get('return_diff', 0)
                        TitanState.add_log("ml",
                            f"💰 资金管理回测完成! 固定仓位:{fixed_ret}% 凯利ATR:{ka_ret}% 提升:{imp}%")
                    else:
                        TitanState.add_log("warn", "资金管理回测失败: 数据不足")
                else:
                    TitanState.add_log("warn", "资金管理日线数据获取失败")
            except Exception as e:
                self.logger.error(f"资金管理回测异常: {e}")
                TitanState.add_log("warn", f"资金管理回测异常: {str(e)[:50]}")
        else:
            TitanState.add_log("ml", "💰 资金管理模型已加载")

    async def close(self):
        await self.exchange.close()
        await self.swap_exchange.close()


app = FastAPI(title="Titan V17.3 Omni Evolution")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(grid_router)
app.include_router(ml_training_router)
app.include_router(ai_reports_router)
app.include_router(trading_router)
app.include_router(data_router)
app.include_router(system_router)
app.include_router(ai_modules_router)
app.include_router(decisions_router)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POSITIONS_FILE = os.path.join(BASE_DIR, "data", "positions.json")

positions = []
price_cache = {}
price_cache_lock = threading.Lock()
external_data = TitanExternalDataManager()
constitution = TitanConstitution()
paper_trader = TitanPaperTrader()
position_guard = TitanPositionGuard()
synapse = TitanSynapse()
risk_budget = TitanRiskBudget()
signal_quality = TitanSignalQuality()
autopilot = TitanAutoPilot()
strategy_router = TitanStrategyRouter()
dispatcher._memory_bank_ref = external_data.memory_bank

_btc_betas = {}
try:
    _btc_beta_path = os.path.join(CONFIG.get("DATA_DIR", "data"), "titan_correlation_matrix.json")
    if os.path.exists(_btc_beta_path):
        with open(_btc_beta_path, "r") as _bf:
            _btc_betas = json.load(_bf).get("btc_betas", {})
        if _btc_betas:
            print(f"[INIT] BTC Beta已加载: {len(_btc_betas)}个币种, 均值={sum(_btc_betas.values())/len(_btc_betas):.2f}", flush=True)
        else:
            print("[INIT] BTC Beta文件为空, 所有币种默认beta=1.0(无过滤)", flush=True)
    else:
        print("[INIT] BTC Beta文件不存在, 所有币种默认beta=1.0(无过滤)", flush=True)
except Exception as _be:
    print(f"[INIT] BTC Beta加载失败: {_be}, 默认beta=1.0(无过滤)", flush=True)


def load_positions():
    global positions
    try:
        if os.path.exists(POSITIONS_FILE):
            with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
                positions = json.load(f)
    except Exception:
        positions = []


def save_positions():
    try:
        os.makedirs(os.path.dirname(POSITIONS_FILE), exist_ok=True)
        with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


load_positions()


def enrich_positions(pos_list, cruise_data):
    prices = {}
    for item in cruise_data:
        sym_key = item.get("symbol", "")
        if sym_key:
            prices[sym_key] = item["price"]

    enriched = []
    for p in pos_list:
        pos = dict(p)
        entry = float(pos.get("entry", 0))
        amount = float(pos.get("amount", 0))
        current = prices.get(pos["sym"], entry)
        pos["current"] = round(current, 6)
        if entry > 0 and amount > 0:
            qty = amount / entry
            profit_amt = round((current - entry) * qty, 2)
            profit_pct = round(((current - entry) / entry) * 100, 2)
        else:
            profit_amt = 0.0
            profit_pct = 0.0
        pos["profit_amt"] = profit_amt
        pos["profit_pct"] = profit_pct
        enriched.append(pos)
    return enriched


commander = TitanCommander()

_app_ready = False


@app.on_event("startup")
async def startup():
    try:
        agent_memory.sync_to_critic(titan_critic)
        agent_memory.sync_to_adaptive(adaptive_weights)
        TitanState.add_log("system", f"智能体记忆已恢复: 第{agent_memory.session_count}次启动, {len(agent_memory.critic_history)}条交易记录")
    except Exception as e:
        logging.getLogger("Titan").error(f"智能体记忆恢复异常: {e}")

    try:
        unified_memory.register_backends(
            agent_memory=agent_memory,
            memory_bank=getattr(external_data, 'memory_bank', None),
            synapse=synapse,
            hippocampus=hippocampus,
        )
        TitanState.add_log("system", f"统一记忆系统已初始化: {unified_memory.get_status()['registered_backends']}/4个后端")
    except Exception as e:
        logging.getLogger("Titan").error(f"统一记忆初始化异常: {e}")

    if not titan_critic.trade_history:
        try:
            trades_path = os.path.join(os.path.dirname(__file__), "..", "data", "titan_trades.json")
            if os.path.exists(trades_path):
                with open(trades_path, "r") as f:
                    saved_trades = json.loads(f.read())
                for t in saved_trades:
                    titan_critic.trade_history.append({
                        'time': time.time(),
                        'symbol': t.get('symbol', ''),
                        'direction': t.get('direction', 'long'),
                        'entry': t.get('entry_price', 0),
                        'exit': t.get('exit_price', 0),
                        'pnl': t.get('pnl_pct', 0),
                        'result': t.get('result', 'loss'),
                        'score': t.get('signal_score', 0),
                        'rsi': t.get('rsi', 50),
                        'adx': t.get('adx', 20),
                        'regime': t.get('regime', '未知'),
                        'bb_pos': t.get('bb_pos', 0.5),
                        'vol_ratio': t.get('vol_ratio', 1.0),
                    })
                logging.getLogger("Titan").info(f"Critic从交易记录加载了{len(saved_trades)}条历史交易")
        except Exception as e:
            logging.getLogger("Titan").warning(f"加载交易记录到Critic失败: {e}")

    global _app_ready
    _app_ready = True
    logging.getLogger("Titan").info("✅ 应用启动完成(同步阶段)，开始接受请求")
    asyncio.create_task(_deferred_startup())


async def _deferred_startup():
    try:
        await commander.exchange.load_markets()
        logging.getLogger("Titan").info("交易所市场数据加载完成")
    except Exception as e:
        logging.getLogger("Titan").error(f"交易所市场数据加载失败: {e}")

    try:
        refreshed = await external_data.refresh_all()
        if refreshed:
            TitanState.market_snapshot["external"] = external_data.get_snapshot()
            logging.getLogger("Titan").info(f"启动时外部数据已刷新: {', '.join(refreshed)}")
    except Exception as e:
        logging.getLogger("Titan").warning(f"启动时外部数据刷新失败: {e}")

    asyncio.create_task(commander.run_scan_loop())
    asyncio.create_task(commander.run_fast_monitor_loop())
    asyncio.create_task(commander.run_ml_training_loop())
    asyncio.create_task(commander.run_mm_training_loop())
    asyncio.create_task(run_memory_sync_loop())

    autopilot_modules = {
        "risk_budget": risk_budget,
        "constitution": constitution,
        "ml_engine": ml_engine,
        "paper_trader": paper_trader,
        "signal_quality": signal_quality,
        "dispatcher": dispatcher,
        "state": TitanState,
        "synapse": synapse,
        "memory_bank": external_data,
        "commander": commander,
    }
    await autopilot.start(autopilot_modules)
    logging.getLogger("Titan").info("AutoPilot自动驾驶已随系统启动")


async def run_memory_sync_loop():
    while True:
        await asyncio.sleep(300)
        try:
            agent_memory.sync_from_critic(titan_critic)
            agent_memory.sync_from_adaptive(adaptive_weights)
            agent_memory.save()
            governor.save()

            try:
                feedback_engine.auto_adjust_critic(titan_critic)
                fb_status = feedback_engine.get_status()
                fb_rolling = fb_status.get("rolling_accuracy")
                fb_total = fb_status.get("total_predictions", 0)

                if fb_rolling is not None and fb_total >= 10:
                    current_ml_w = adaptive_weights.ml_weight_override
                    if fb_rolling < 40:
                        target_w = 0.15
                        if current_ml_w is None or current_ml_w > target_w:
                            adaptive_weights.ml_weight_override = target_w
                            TitanState.add_log("system", f"📊 反馈引擎: 滚动准确率{fb_rolling}%过低→ML权重降至{int(target_w*100)}%")
                    elif fb_rolling < 60:
                        target_w = 0.25
                        if current_ml_w is None or current_ml_w > target_w:
                            adaptive_weights.ml_weight_override = target_w
                            TitanState.add_log("system", f"📊 反馈引擎: 滚动准确率{fb_rolling}%偏低→ML权重回调至{int(target_w*100)}%")
                    elif fb_rolling >= 60:
                        target_w = 0.35
                        if current_ml_w is None or current_ml_w < target_w:
                            adaptive_weights.ml_weight_override = target_w
                            TitanState.add_log("system", f"📊 反馈引擎: 滚动准确率{fb_rolling}%良好→ML权重提升至{int(target_w*100)}%")

                fb_suggestions = feedback_engine.suggest_threshold_adjustments()
                for sug in fb_suggestions:
                    sug_type = sug.get("type", "")
                    if sug_type == "class_filter":
                        cls_name = sug.get("class", "")
                        if cls_name:
                            existing = [r for r in titan_critic.ban_rules if r.get("type") == "class_filter" and r.get("class") == cls_name]
                            if not existing:
                                titan_critic.ban_rules.append({
                                    "type": "class_filter", "class": cls_name,
                                    "reason": sug.get("reason", f"'{cls_name}'类准确率过低"),
                                })
                                TitanState.add_log("system", f"📊 反馈引擎: 过滤'{cls_name}'类预测(准确率过低)")
                    elif sug_type == "pattern_ban":
                        for pattern in sug.get("patterns", []):
                            existing = [r for r in titan_critic.ban_rules if r.get("type") == "feedback_ban" and r.get("pattern") == pattern]
                            if not existing:
                                titan_critic.ban_rules.append({
                                    "type": "feedback_ban", "pattern": pattern,
                                    "reason": f"反馈引擎自动禁用: 持续亏损模式",
                                })
                        if sug.get("patterns"):
                            TitanState.add_log("system", f"📊 反馈引擎: 禁用{len(sug['patterns'])}个亏损模式")
            except Exception as fb_err:
                logger.error(f"反馈引擎处理异常: {fb_err}")

            try:
                advice = attribution.get_allocation_advice()
                if advice and advice.get("strategy"):
                    dispatcher.adjust_allocation_from_attribution(advice)
            except Exception:
                pass

            try:
                grid_insights = grid_engine.learn_from_history()
                if grid_insights and grid_insights.get("recommendations"):
                    for rec in grid_insights["recommendations"]:
                        TitanState.add_log("system", f"🕸️ 网格学习: {rec}")
            except Exception:
                pass

            try:
                dispatcher.save()
            except Exception:
                pass

            try:
                risk_budget._check_daily_reset()
                synapse_advice = synapse.get_regime_allocation_advice(dispatcher.current_regime)

                total_scanned = TitanState.market_snapshot.get("total_scanned", 0)
                _reviewer = None
                _diagnostic = None
                _rra = None
                try:
                    _reviewer = ai_reviewer
                except Exception:
                    pass
                try:
                    from server.titan_ai_diagnostic import ai_diagnostic as _diag
                    _diagnostic = _diag
                except Exception:
                    pass
                try:
                    from server.titan_return_rate_agent import return_rate_agent as _rra_mod
                    _rra = _rra_mod
                except Exception:
                    pass

                coord_result = ai_coordinator.coordinate(
                    adaptive_weights=adaptive_weights,
                    risk_budget=risk_budget,
                    dispatcher=dispatcher,
                    synapse=synapse,
                    signal_quality=signal_quality,
                    paper_trader=paper_trader,
                    feedback=feedback_engine,
                    grid_engine=grid_engine,
                    use_ai=(total_scanned % 6 == 0),
                    reviewer=_reviewer,
                    diagnostic=_diagnostic,
                    return_rate_agent=_rra,
                    agent_memory=agent_memory,
                    agi=titan_agi,
                )

                perf_metrics = ai_coordinator.module_metrics
                coord_rebalance = ai_coordinator.get_rebalance_advice()

                risk_budget.rebalance(
                    dispatcher.allocation,
                    synapse_advice,
                    performance_metrics=perf_metrics,
                    coordinator_advice=coord_rebalance if coord_rebalance else None,
                    cooldown_seconds=REBALANCE_COOLDOWN_SECONDS,
                )

                capital_sizer.update_global_multipliers(
                    "ai_override_mult", ai_coordinator.get_size_multiplier()
                )
                capital_sizer.update_global_multipliers(
                    "return_target_mult", return_target.aggression_multiplier
                )
            except Exception as e:
                logging.getLogger("Titan").warning(f"协调器/再平衡异常: {e}")

            try:
                synapse.save()
                risk_budget.save()
                signal_quality.save()
                capital_sizer.save()
                unified_decision.save()
                return_target.save()
            except Exception:
                pass

            try:
                market_info = {
                    "btc_price": TitanState.market_snapshot.get("btc_pulse", {}).get("price", 0),
                    "scan_count": TitanState.market_snapshot.get("total_scanned", 0),
                    "last_scan": TitanState.market_snapshot.get("last_scan_time", ""),
                }
                watchdog.run_health_check(
                    paper_trader=paper_trader,
                    risk_budget=risk_budget,
                    dispatcher=dispatcher,
                    synapse=synapse,
                    signal_quality=signal_quality,
                    constitution=constitution,
                    market_data=market_info,
                )
            except Exception as wd_e:
                logging.getLogger("Titan").warning(f"Watchdog健康检查异常: {wd_e}")

            try:
                if ai_reviewer._should_batch_review():
                    ai_reviewer.batch_review(
                        synapse_status=synapse.get_status(),
                        risk_budget_status=risk_budget.get_status(),
                        dispatcher_status=dispatcher.get_status(),
                    )
            except Exception:
                pass

        except Exception as e:
            logging.getLogger("Titan").warning(f"记忆同步异常: {e}")
            try:
                watchdog.log_exception("memory_sync", e)
            except Exception:
                pass


@app.on_event("shutdown")
async def shutdown():
    agent_memory.sync_from_critic(titan_critic)
    agent_memory.sync_from_adaptive(adaptive_weights)
    agent_memory.save()
    governor.save()
    await commander.close()


def _get_return_rate_agent_status():
    try:
        from server.titan_return_rate_agent import return_rate_agent
        return return_rate_agent.get_status()
    except Exception:
        return {}

@app.get("/api/dashboard")
async def get_dashboard():
    snapshot = TitanState.market_snapshot
    cruise_data = snapshot.get("cruise", [])
    ticker_cache = snapshot.get("_ticker_cache", {})

    if ticker_cache:
        for item in cruise_data:
            asset = item.get("symbol", "")
            tk = ticker_cache.get(asset, {})
            if tk:
                item["change_24h"] = tk.get("change_24h", 0)
                item["volume_24h"] = tk.get("volume_24h", 0)
                item["high_24h"] = tk.get("high_24h", 0)
                item["low_24h"] = tk.get("low_24h", 0)

    enriched_pos = enrich_positions(positions, cruise_data) if positions else []

    market_summary = TitanAnalyst.generate_market_summary(cruise_data)

    live_prices = snapshot.get("_live_prices", {})
    cruise_prices = {o["symbol"]: o["price"] for o in cruise_data if o.get("price", 0) > 0}
    best_prices = {**cruise_prices, **live_prices}
    if not best_prices:
        best_prices = {pos["symbol"]: pos.get("current_price", pos["entry_price"]) for pos in paper_trader.positions.values()}
    live_price_age = time.time() - snapshot.get("_live_price_ts", 0)

    return {
        "market": {
            "btc_pulse": snapshot["btc_pulse"],
            "cruise": cruise_data,
            "logs": list(snapshot["logs"]),
            "scan_mode": snapshot.get("scan_mode", "待机"),
            "total_scanned": snapshot.get("total_scanned", 0),
            "scan_progress": snapshot.get("scan_progress", {"current": 0, "total": 0, "scanning": False, "last_updated": 0}),
            "ai_summary": market_summary,
            "price_freshness": round(live_price_age, 1),
        },
        "positions": enriched_pos,
        "ml_status": ml_engine.get_status(),
        "mm_status": money_manager.get_status(),
        "adaptive_weights": adaptive_weights.get_status(),
        "critic_status": titan_critic.get_status(),
        "agent_memory": agent_memory.get_status(),
        "governor": governor.get_status(),
        "feedback": feedback_engine.get_status(),
        "simulator": simulator.get_status(),
        "external_data": external_data.get_status(),
        "darwin_lab": darwin_lab.get_status(),
        "paper_trader": paper_trader.get_portfolio_summary(best_prices, grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
        "paper_positions": paper_trader.get_positions_display(best_prices) if paper_trader.positions else TitanState.market_snapshot.get("paper_positions", []),
        "constitution": constitution.get_status(),
        "dispatcher": dispatcher.get_status(),
        "grid": grid_engine.get_status(),
        "attribution": attribution.get_status(),
        "synapse": synapse.get_status(),
        "risk_budget": risk_budget.get_status(),
        "signal_quality": signal_quality.get_status(),
        "ai_reviewer": ai_reviewer.get_status(),
        "watchdog": watchdog.get_status(),
        "ai_coordinator": ai_coordinator.get_status(),
        "capital_sizer": capital_sizer.get_status(),
        "unified_decision": unified_decision.get_status(),
        "return_target": return_target.get_status(),
        "return_rate_agent": TitanState.market_snapshot.get("return_rate_agent") or _get_return_rate_agent_status(),
    }


@app.get("/api/backtest")
async def get_backtest():
    result = TitanState.backtest_result
    if result is None:
        return {"status": "collecting", "snapshots": len(TitanState.backtest_history), "message": "数据收集中，需要至少10次扫描快照"}
    return {"status": "ready", "snapshots": len(TitanState.backtest_history), "result": result}


@app.get("/api/status")
async def get_status():
    live_ts = TitanState.market_snapshot.get('_live_price_ts', 0)
    live_age = round(time.time() - live_ts, 1) if live_ts > 0 else -1
    return {
        "version": CONFIG['VERSION'],
        "status": "running",
        "positions_count": len(positions),
        "scanned": TitanState.market_snapshot.get("total_scanned", 0),
        "fast_monitor": {
            "active": live_ts > 0,
            "refresh_sec": 5,
            "last_update_age": live_age,
            "tracked_pairs": len(TitanState.market_snapshot.get('_live_prices', {})),
        },
    }


class SimRequest(BaseModel):
    years: float = 1.0
    initial_capital: float = 10000
    retrain_interval: int = 60


@app.post("/api/simulate")
async def start_simulation(req: SimRequest):
    if simulator.running:
        return {"status": "already_running", "progress": simulator.progress}

    symbols = list(CONFIG['ELITE_UNIVERSE'])

    async def run_sim():
        try:
            await simulator.run_simulation(
                commander.exchange, symbols,
                years=req.years,
                initial_capital=req.initial_capital,
                retrain_interval_bars=req.retrain_interval
            )
            TitanState.add_log("system", f"进化模拟完成: {req.years}年 ${req.initial_capital}起步")
        except Exception as e:
            logger.error(f"模拟异常: {e}")

    asyncio.create_task(run_sim())
    return {"status": "started", "config": {"years": req.years, "capital": req.initial_capital}}


@app.get("/api/simulate")
async def get_simulation():
    status = simulator.get_status()
    if simulator.results and not simulator.running:
        status["full_results"] = simulator.results
    return status


@app.get("/api/agent")
async def get_agent_status():
    return {
        "memory": agent_memory.get_status(),
        "governor": governor.get_status(),
        "feedback": feedback_engine.get_status(),
        "simulator": simulator.get_status(),
    }


@app.get("/api/hippocampus")
async def get_hippocampus_status():
    return hippocampus.get_status()


@app.get("/api/unified-memory")
async def get_unified_memory():
    return unified_memory.get_full_summary()


@app.get("/api/unified-memory/status")
async def get_unified_memory_status():
    return unified_memory.get_status()


@app.get("/api/unified-memory/query/{query_type}")
async def unified_memory_query(query_type: str, symbol: str = None, regime: str = None, direction: str = None, days: int = 30):
    kwargs = {}
    if symbol:
        kwargs["symbol"] = symbol
    if regime:
        kwargs["regime"] = regime
    if direction:
        kwargs["direction"] = direction
    if query_type == "performance_trend":
        kwargs["days"] = days
    return unified_memory.query(query_type, **kwargs)


@app.get("/api/wall-street-metrics")
async def get_wall_street_metrics():
    return autopilot._calc_wall_street_metrics({
        "paper_trader": paper_trader,
    })


@app.get("/api/agi")
async def get_agi_status():
    return {
        "status": titan_agi.get_status(),
        "learning": titan_agi.get_learning_summary(),
        "recommendations": titan_agi.get_active_recommendations(),
    }


@app.post("/api/agi/reflect")
async def trigger_agi_reflection():
    ml_acc = feedback_engine.get_rolling_accuracy()
    gov_status = governor.get_status()
    reflection = titan_agi.self_reflect(ml_accuracy=ml_acc, governor_state=gov_status)
    return reflection


@app.post("/api/agi/deep-reflect")
async def trigger_deep_reflection():
    btc_info = TitanState.market_snapshot.get("btc_pulse", {})
    summary = f"BTC:{btc_info.get('price',0)}, FNG:{btc_info.get('fng',50)}"
    result = await titan_agi.llm_deep_reflection(summary)
    return result


@app.get("/api/mtf/{symbol}")
async def get_mtf_analysis(symbol: str):
    try:
        sym = f"{symbol.upper()}_USDT"
        timeframes = ['1w', '1d', '4h', '1h', '15m']
        data_map = {}
        for tf in timeframes:
            try:
                ohlcv = await commander.exchange.fetch_ohlcv(sym, tf, limit=100)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                    data_map[tf] = df
            except Exception:
                pass
        if not data_map:
            return {"error": f"无法获取{symbol}数据"}
        result = TitanMTF.full_analysis(data_map)
        return result
    except Exception as e:
        return {"error": str(e)}


class MegaBacktestRequest(BaseModel):
    iterations: int = 100


@app.post("/api/mega-backtest/run")
async def start_mega_backtest(req: MegaBacktestRequest):
    if mega_backtest.running:
        return {"status": "already_running", "progress": mega_backtest.progress}

    symbols_to_use = list(CONFIG['ELITE_UNIVERSE'])

    async def run_mega():
        data_map = {}
        try:
            batch_size = 5
            for i in range(0, len(symbols_to_use), batch_size):
                batch = symbols_to_use[i:i+batch_size]
                tasks = []
                for sym_name in batch:
                    tasks.append(commander.exchange.fetch_ohlcv(f"{sym_name}_USDT", '1h', limit=1000))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for sym_name, res in zip(batch, results):
                    if not isinstance(res, Exception) and res and len(res) > 100:
                        data_map[sym_name] = pd.DataFrame(res, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                await asyncio.sleep(0.2)
            if data_map:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    mega_backtest.run_evolution_cycle,
                    data_map,
                    req.iterations
                )
                TitanState.add_log("system", f"万次回测完成: {req.iterations}次迭代, {len(data_map)}个资产, 最佳Calmar={mega_backtest.best_calmar:.3f}")
            else:
                mega_backtest.running = False
                TitanState.add_log("warning", "万次回测: 无有效数据")
        except Exception as e:
            logger.error(f"万次回测异常: {e}")
            mega_backtest.running = False

    asyncio.create_task(run_mega())
    return {"status": "started", "iterations": req.iterations, "assets": len(symbols_to_use)}


@app.get("/api/mega-backtest")
async def get_mega_backtest_status():
    return mega_backtest.get_status()


@app.get("/api/risk-matrix")
async def get_risk_matrix():
    return risk_matrix.get_status()


@app.get("/api/attribution")
async def get_attribution():
    return attribution.get_summary()


@app.get("/api/attribution/advice")
async def get_attribution_advice():
    return attribution.get_allocation_advice()


@app.get("/api/dispatcher")
async def get_dispatcher_status():
    return dispatcher.get_status()


@app.get("/api/v19/dashboard")
async def get_v19_dashboard():
    from server.routes.system import pipeline_state
    return {
        "version": CONFIG['VERSION'],
        "mtf": {"status": "ready"},
        "mega_backtest": mega_backtest.get_status(),
        "risk_matrix": risk_matrix.get_status(),
        "attribution": attribution.get_status(),
        "monte_carlo": monte_carlo.get_status(),
        "governor": governor.get_status(),
        "feedback": feedback_engine.get_status(),
        "paper_trader": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
        "constitution": constitution.get_status(),
        "pipeline": {
            "running": pipeline_state.running,
            "stage": pipeline_state.stage,
            "progress": pipeline_state.progress,
            "progress_msg": pipeline_state.progress_msg,
            "result": pipeline_state.result,
        },
        "synapse": synapse.get_status(),
        "risk_budget": risk_budget.get_status(),
        "signal_quality": signal_quality.get_status(),
        "ai_coordinator": ai_coordinator.get_status(),
        "capital_sizer": capital_sizer.get_status(),
        "unified_decision": unified_decision.get_status(),
        "return_target": return_target.get_status(),
    }


@app.get("/api/cto-alert/status")
async def get_cto_alert_status():
    last_sent = TitanMailer._last_emergency_email_time
    cooldown_remaining = max(0, 7200 - (time.time() - last_sent))
    return {
        "last_alert_time": last_sent,
        "last_alert_ago": f"{(time.time() - last_sent)/60:.0f}分钟前" if last_sent > 0 else "从未发送",
        "cooldown_remaining_min": f"{cooldown_remaining/60:.0f}",
        "can_send": cooldown_remaining <= 0,
        "email_configured": bool(os.getenv('SENDER_EMAIL') and os.getenv('SENDER_PASSWORD') and TitanMailer.get_receivers()),
    }

@app.get("/api/auto-exec-history")
async def get_auto_exec_history():
    history = getattr(TitanState, '_auto_exec_history', [])
    try:
        history_path = os.path.join(CONFIG.get("DATA_DIR", "data"), "auto_exec_history.json")
        if os.path.exists(history_path) and not history:
            with open(history_path, "r") as f:
                history = json.load(f)
    except Exception:
        pass
    return {"history": history[-20:], "total": len(history)}

@app.post("/api/cto-alert/test")
async def test_cto_alert():
    sent = TitanMailer.send_cto_alert(
        alert_type="info",
        summary="CTO预警系统测试 — 一切正常",
        details=[
            "这是一封测试邮件，验证CTO预警邮件系统是否正常工作",
            f"系统版本: {CONFIG.get('VERSION', 'N/A')}",
            f"当前时间: {datetime.now(pytz.timezone(CONFIG['TIMEZONE'])).strftime('%Y-%m-%d %H:%M')}",
        ],
        auto_actions=[{"action": "预警邮件系统测试通过", "applied": True}],
        coordinator_recs=ai_coordinator.recommendations,
    )
    if sent:
        TitanState.add_log("system", "📧 CTO预警测试邮件已发送")
        return {"status": "ok", "message": "测试预警邮件已发送"}
    else:
        return {"status": "failed", "message": "发送失败 (可能在冷却中或邮件未配置)"}

@app.get("/api/capital-sizer")
async def get_capital_sizer_status():
    return capital_sizer.get_status()


@app.get("/api/return-rate-agent")
async def get_return_rate_agent_status():
    from server.titan_return_rate_agent import return_rate_agent
    return return_rate_agent.get_status()


@app.post("/api/return-rate-agent/think")
async def trigger_return_rate_think():
    from server.titan_return_rate_agent import return_rate_agent
    context = {
        "return_target": return_target.get_status(),
        "paper_portfolio": paper_trader.get_portfolio_summary(grid_pnl=grid_engine.get_unrealized_pnl(), grid_realized_pnl=grid_engine.total_grid_profit),
        "trades_history": paper_trader.trade_history[-20:] if hasattr(paper_trader, 'trade_history') else [],
        "coordinator_recs": ai_coordinator.recommendations,
        "dispatcher_regime": dispatcher.current_regime,
        "risk_budget": risk_budget.get_status(),
        "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
        "unified_decision": unified_decision.get_status(),
        "ml_accuracy": TitanState.market_snapshot.get("ml_status", {}).get("accuracy", 0),
        "synapse": synapse.get_status(),
        "signal_quality": signal_quality.get_status(),
    }
    result = return_rate_agent.think(context, agent_memory, ai_coordinator, return_target)
    TitanState.market_snapshot["return_rate_agent"] = return_rate_agent.get_status()
    return result


@app.get("/api/strategy-performance")
async def get_strategy_performance():
    try:
        perf = synapse.strategy_performance
        chart_data = []
        for strategy, data in perf.items():
            total = data["wins"] + data["losses"]
            chart_data.append({
                "strategy": strategy,
                "wins": data["wins"],
                "losses": data["losses"],
                "total_trades": total,
                "win_rate": round(data["wins"] / total * 100, 1) if total > 0 else 0,
                "total_pnl": data["total_pnl"],
                "worst_assets": dict(sorted(data.get("worst_assets", {}).items(), key=lambda x: -x[1])[:5]),
                "best_regimes": {k: {"wins": v.get("wins",0), "losses": v.get("losses",0), "pnl": v.get("pnl",0)} for k, v in data.get("best_regimes", {}).items()},
            })
        return {"strategy_performance": chart_data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/ml-features")
async def get_ml_features():
    try:
        ml_status = ml_engine.get_status()
        feature_importance = ml_status.get("feature_importance", {})
        selected_features = ml_status.get("selected_features", [])
        sorted_features = sorted(feature_importance.items(), key=lambda x: -x[1]) if feature_importance else []
        return {
            "feature_importance": dict(sorted_features[:30]),
            "selected_features": selected_features,
            "total_features": len(feature_importance),
            "is_trained": ml_status.get("is_trained", False),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/protection-layers")
async def get_protection_layers():
    try:
        import json as _json
        config = {}
        try:
            with open("data/titan_config.json") as f:
                config = _json.load(f)
        except Exception:
            pass
        filter_4h = config.get("signal_gate_4h_filter", True)
        darwin = config.get("darwin_constraints", {})
        tp_sl_ratio = darwin.get("min_tp_sl_ratio", config.get("min_tp_sl_ratio", 2.0))
        cap_cfg = config.get("capital_sizer_hardcap", {})
        hard_max = cap_cfg.get("hard_max_position_usd", config.get("hard_max_position_usd", 500))
        hold_prot = config.get("hold_time_protection_enabled", True)

        layers = [
            {"name": "信号门槛", "value": f"{config.get('min_signal_score', 65)}分", "active": True},
            {"name": "4H方向过滤", "value": "逆势拒绝", "active": bool(filter_4h)},
            {"name": "SL距离范围", "value": f"{config.get('min_sl_distance', 0.03)*100:.0f}%-15%", "active": config.get('min_sl_distance', 0.03) >= 0.03},
            {"name": "TP/SL比", "value": f"\u2265{tp_sl_ratio}:1", "active": tp_sl_ratio >= 2.0},
            {"name": "ML防守性", "value": ">85%减8分", "active": True},
            {"name": "持仓保护", "value": "前4h不收紧+浮盈<1%不收紧", "active": bool(hold_prot)},
            {"name": "仓位上限", "value": f"${hard_max}", "active": True},
        ]
        active_count = sum(1 for l in layers if l["active"])
        return {
            "layers": layers,
            "all_active": active_count == len(layers),
            "protection_score": active_count,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

deep_training_state = {
    "running": False, "stage": "", "progress": 0, "progress_msg": "",
    "results": {}, "start_time": None, "total_assets": 0,
}
_deep_training_lock = asyncio.Lock()


@app.get("/api/strategy-analysis")
async def get_strategy_analysis():
    try:
        opps = TitanState.market_snapshot.get("cruise", [])
        results = []
        for opp in opps[:20]:
            ml_pred = opp.get("ml", {})
            strat = ml_pred.get("strategy_analysis", {})
            if strat:
                results.append({
                    "symbol": opp.get("symbol", ""),
                    "score": opp.get("score", 0),
                    "strategies": {
                        "mean_reversion": strat.get("mean_reversion", {}),
                        "breakout": strat.get("breakout", {}),
                        "momentum": strat.get("momentum", {}),
                    },
                    "recommended": strat.get("recommended", {}),
                    "regime": strat.get("regime", "unknown"),
                })
        return {
            "total": len(results),
            "strategies": ["MeanReversion", "Breakout", "MomentumRotation"],
            "analysis": results,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/ml/deep-training-all/status")
async def get_deep_training_status():
    return dict(deep_training_state)


@app.post("/api/ml/deep-training-all")
async def start_deep_training_all(start_step: int = 1):
    if deep_training_state["running"]:
        return {"status": "already_running", "stage": deep_training_state["stage"], "progress": deep_training_state["progress"]}

    elite = list(CONFIG['ELITE_UNIVERSE'])
    deep_training_state["running"] = True
    deep_training_state["total_assets"] = len(elite)
    deep_training_state["start_time"] = datetime.now(pytz.timezone(CONFIG['TIMEZONE'])).strftime("%Y-%m-%d %H:%M:%S")
    deep_training_state["results"] = {}

    async def run_all_training():
        try:
            if start_step <= 1:
                deep_training_state["stage"] = "ml_deep"
                deep_training_state["progress"] = 5
                deep_training_state["progress_msg"] = f"[1-2/6] 提交Modal云端训练: {len(elite)}个精英资产..."
                TitanState.add_log("ml", f"🧠 [全量深度学习] 启动! 目标: {len(elite)}个精英资产 → Modal云端")
            else:
                TitanState.add_log("ml", f"🧠 [全量深度学习] 从第{start_step}步继续! 跳过前{start_step-1}步")

            if start_step <= 2:
                try:
                    submit_result = await modal_trigger_deep_all(symbols=elite, max_assets=69)
                    if submit_result.get("status") == "submitted":
                        call_id = submit_result.get("call_id", "")
                        TitanState.add_log("ml", f"[1-2/6] Modal训练已提交! call_id={call_id[:12]}...")
                        deep_training_state["progress"] = 8
                        deep_training_state["progress_msg"] = f"[1-2/6] Modal云端训练中: 数据获取+Alpha+MM模型..."

                        max_wait = 2400
                        poll_interval = 20
                        waited = 0
                        while waited < max_wait:
                            await asyncio.sleep(poll_interval)
                            waited += poll_interval

                            status = await modal_check_deep_all()
                            modal_status = status.get("status", "unknown")

                            if modal_status == "completed":
                                result_data = status.get("result", {})
                                alpha_info = result_data.get("alpha", {})
                                mm_info = result_data.get("mm", {})
                                elapsed = result_data.get("elapsed", 0)
                                assets = result_data.get("assets_fetched", 0)

                                TitanState.add_log("ml", f"[1-2/6] Modal训练完成! {assets}资产, {elapsed}秒")

                                deep_training_state["progress"] = 15
                                deep_training_state["progress_msg"] = f"[1-2/6] 下载云端模型..."
                                TitanState.add_log("ml", "[1-2/6] 正在下载云端模型到本地...")

                                from server.titan_capital_sizer import capital_sizer
                                install_result = await modal_download_deep_all(ml_engine=ml_engine, capital_sizer=capital_sizer)

                                if install_result.get("status") == "ok":
                                    installed = install_result.get("installed", {})
                                    if installed.get("alpha"):
                                        ml_engine.mark_deep_trained()
                                        ml_status = ml_engine.get_status()
                                        deep_training_state["results"]["ml_engine"] = {
                                            "status": "ok",
                                            "accuracy": ml_status.get("accuracy", 0),
                                            "f1": ml_status.get("f1", 0),
                                            "samples": ml_status.get("samples", 0),
                                            "assets": assets,
                                            "trained_on": "modal_cloud",
                                        }
                                        TitanState.add_log("ml", f"✅ [1/6] Alpha模型(Modal): 准确率={ml_status.get('accuracy')}% F1={ml_status.get('f1')}%")
                                    else:
                                        deep_training_state["results"]["ml_engine"] = {"status": "failed", "reason": "Alpha模型下载失败"}

                                    if installed.get("mm"):
                                        deep_training_state["results"]["money_manager"] = {
                                            "status": "ok",
                                            "trained_on": "modal_cloud",
                                            "assets": assets,
                                        }
                                        mm_metrics = install_result.get("mm_metrics", {})
                                        TitanState.add_log("ml", f"✅ [2/6] MM模型(Modal): MAE={mm_metrics.get('mae')}, R2={mm_metrics.get('r2')}")
                                    else:
                                        deep_training_state["results"]["money_manager"] = {"status": "failed", "reason": "MM模型下载失败"}

                                    if install_result.get("ohlcv_cached"):
                                        TitanState.add_log("ml", "[1-2/6] OHLCV缓存已同步到本地")
                                else:
                                    deep_training_state["results"]["ml_engine"] = {"status": "error", "error": "模型下载失败"}
                                    deep_training_state["results"]["money_manager"] = {"status": "error", "error": "模型下载失败"}
                                    TitanState.add_log("warn", f"[1-2/6] 模型下载失败: {install_result.get('error', 'unknown')}")
                                break

                            elif modal_status in ("failed", "error", "timeout"):
                                error_msg = status.get("error", "Modal训练失败")
                                deep_training_state["results"]["ml_engine"] = {"status": "error", "error": error_msg}
                                deep_training_state["results"]["money_manager"] = {"status": "error", "error": error_msg}
                                TitanState.add_log("warn", f"[1-2/6] Modal训练失败: {error_msg[:80]}")
                                break
                            else:
                                minutes = waited // 60
                                deep_training_state["progress"] = min(18, 8 + int(waited / max_wait * 10))
                                deep_training_state["progress_msg"] = f"[1-2/6] Modal云端训练中... 已等待{minutes}分{waited%60}秒"
                        else:
                            deep_training_state["results"]["ml_engine"] = {"status": "timeout", "error": "Modal训练超时(40分钟)"}
                            deep_training_state["results"]["money_manager"] = {"status": "timeout"}
                            TitanState.add_log("warn", "[1-2/6] Modal训练超时(40分钟)")

                    elif submit_result.get("status") == "already_running":
                        TitanState.add_log("warn", "[1-2/6] Modal训练任务已在运行中")
                        deep_training_state["results"]["ml_engine"] = {"status": "already_running"}
                        deep_training_state["results"]["money_manager"] = {"status": "already_running"}
                    else:
                        error = submit_result.get("error", "提交失败")
                        TitanState.add_log("warn", f"[1-2/6] Modal提交失败: {error[:80]}")
                        deep_training_state["results"]["ml_engine"] = {"status": "error", "error": error}
                        deep_training_state["results"]["money_manager"] = {"status": "error", "error": error}

                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    logger.error(f"[Modal训练异常] {tb}")
                    deep_training_state["results"]["ml_engine"] = {"status": "error", "error": str(e)[:200]}
                    deep_training_state["results"]["money_manager"] = {"status": "error", "error": str(e)[:200]}
                    TitanState.add_log("warn", f"[1-2/6] Modal异常: {str(e)[:80]}")
            else:
                deep_training_state["results"]["ml_engine"] = {"status": "skipped"}
                deep_training_state["results"]["money_manager"] = {"status": "skipped"}

            local_ohlcv_map = {}
            local_daily_map = {}
            local_ohlcv_path = os.path.join(BASE_DIR, "data", "titan_historical_ohlcv.json")
            if os.path.exists(local_ohlcv_path):
                try:
                    with open(local_ohlcv_path) as f:
                        raw_ohlcv = json.load(f)
                    for coin, info in raw_ohlcv.items():
                        candles = info.get('data', [])
                        if len(candles) >= 100:
                            df = pd.DataFrame(candles, columns=['t','o','h','l','c','v'])
                            for col in ['o','h','l','c','v']:
                                df[col] = df[col].astype(float)
                            local_ohlcv_map[coin] = df

                            df_ts = df.copy()
                            df_ts['t'] = pd.to_datetime(df_ts['t'], unit='ms')
                            df_daily = df_ts.set_index('t').resample('1D').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'}).dropna().reset_index()
                            df_daily.rename(columns={'t':'t'}, inplace=True)
                            if len(df_daily) >= 20:
                                local_daily_map[coin] = df_daily
                    TitanState.add_log("ml", f"[本地数据] 加载完成: {len(local_ohlcv_map)}资产(K线), {len(local_daily_map)}资产(日线)")
                except Exception as e:
                    TitanState.add_log("warn", f"[本地数据] 加载失败: {str(e)[:50]}, 将降级到API获取")

            shared_1h_data = {}
            top_assets = elite[:40]
            if start_step <= 5:
                deep_training_state["stage"] = "mega_backtest"
                deep_training_state["progress"] = 35
                if local_ohlcv_map:
                    shared_1h_data = {s: local_ohlcv_map[s] for s in top_assets if s in local_ohlcv_map}
                    TitanState.add_log("ml", f"[3-5/6] 使用本地K线数据(共享): {len(shared_1h_data)}个资产")
                else:
                    deep_training_state["progress_msg"] = f"[3/6] 获取1h数据用于回测+蒙特卡洛..."
                    try:
                        batch_size = 5
                        for i in range(0, len(top_assets), batch_size):
                            batch = top_assets[i:i+batch_size]
                            tasks = [commander.exchange.fetch_ohlcv(f"{s}_USDT", '1h', limit=2000) for s in batch]
                            fetch_results = await asyncio.gather(*tasks, return_exceptions=True)
                            for s, r in zip(batch, fetch_results):
                                if not isinstance(r, Exception) and r and len(r) > 100:
                                    shared_1h_data[s] = pd.DataFrame(r, columns=['t','o','h','l','c','v'])
                            await asyncio.sleep(0.3)
                            deep_training_state["progress_msg"] = f"[3/6] 获取1h数据: {len(shared_1h_data)}/{len(top_assets)}..."
                        TitanState.add_log("ml", f"[3-5/6] 共获取{len(shared_1h_data)}个资产1h数据(共享), 每资产≤2000根")
                    except Exception as e:
                        TitanState.add_log("warn", f"[3/6] 数据获取异常: {str(e)[:50]}")

            if start_step <= 3:
                deep_training_state["progress"] = 40
                deep_training_state["progress_msg"] = f"[3/6] 万次回测进化: {len(shared_1h_data)}个资产, 500轮..."
                try:
                    if not mega_backtest.running and len(shared_1h_data) >= 10:
                        loop = asyncio.get_event_loop()
                        await asyncio.wait_for(
                            loop.run_in_executor(None, mega_backtest.run_evolution_cycle, shared_1h_data, 500),
                            timeout=300
                        )
                        deep_training_state["results"]["mega_backtest"] = {
                            "status": "ok", "assets": len(shared_1h_data),
                            "best_calmar": mega_backtest.best_calmar,
                            "rounds": 500,
                        }
                        TitanState.add_log("ml", f"✅ [3/6] 万次回测完成! {len(shared_1h_data)}资产×500轮, Calmar={mega_backtest.best_calmar:.3f}")
                    else:
                        deep_training_state["results"]["mega_backtest"] = {"status": "insufficient_data" if len(shared_1h_data) < 10 else "already_running"}
                except asyncio.TimeoutError:
                    deep_training_state["results"]["mega_backtest"] = {"status": "timeout", "msg": "超过5分钟限制"}
                    TitanState.add_log("warn", "[3/6] 万次回测超时(5分钟限制), 已安全中止")
                except Exception as e:
                    deep_training_state["results"]["mega_backtest"] = {"status": "error", "error": str(e)[:100]}
                    TitanState.add_log("warn", f"[3/6] 万次回测异常: {str(e)[:50]}")
            else:
                deep_training_state["results"]["mega_backtest"] = {"status": "skipped"}

            darwin_preloaded = {s: local_ohlcv_map[s] for s in top_assets if s in local_ohlcv_map} if local_ohlcv_map else None
            if start_step <= 4:
                deep_training_state["stage"] = "darwin"
                deep_training_state["progress"] = 55
                deep_training_state["progress_msg"] = f"[4/6] 达尔文进化: {len(top_assets)}个资产, 10代×30个体..."
                try:
                    if not darwin_lab.running:
                        await asyncio.wait_for(
                            darwin_lab.run_evolution(commander.exchange, top_assets, generations=10, population_size=30, preloaded_data=darwin_preloaded),
                            timeout=600
                        )
                        deep_training_state["results"]["darwin"] = {"status": "ok", "assets": len(top_assets), "generations": 10}
                        TitanState.add_log("ml", f"✅ [4/6] 达尔文进化完成! {len(top_assets)}资产, 10代×30个体")
                    else:
                        deep_training_state["results"]["darwin"] = {"status": "already_running"}
                except asyncio.TimeoutError:
                    deep_training_state["results"]["darwin"] = {"status": "timeout", "msg": "超过10分钟限制"}
                    TitanState.add_log("warn", "[4/6] 达尔文进化超时(10分钟限制), 已安全中止")
                except Exception as e:
                    deep_training_state["results"]["darwin"] = {"status": "error", "error": str(e)[:100]}
                    TitanState.add_log("warn", f"[4/6] 达尔文异常: {str(e)[:50]}")
            else:
                deep_training_state["results"]["darwin"] = {"status": "skipped"}

            if start_step <= 5:
                deep_training_state["stage"] = "monte_carlo"
                deep_training_state["progress"] = 70
                deep_training_state["progress_msg"] = f"[5/6] 蒙特卡洛模拟: {len(shared_1h_data)}个资产, 1000轮×500路径..."
                try:
                    if not monte_carlo.running and shared_1h_data:
                        loop = asyncio.get_event_loop()
                        await asyncio.wait_for(
                            loop.run_in_executor(None, monte_carlo.run_evolution, shared_1h_data, 1000, 500),
                            timeout=600
                        )
                        deep_training_state["results"]["monte_carlo"] = {
                            "status": "ok", "assets": len(shared_1h_data),
                            "best_calmar": monte_carlo.best_calmar,
                            "best_sharpe": monte_carlo.best_sharpe,
                            "rounds": 1000, "paths": 500,
                        }
                        TitanState.add_log("ml", f"✅ [5/6] 蒙特卡洛完成! {len(shared_1h_data)}资产×1000轮×500路径, Calmar={monte_carlo.best_calmar:.3f}")
                    else:
                        deep_training_state["results"]["monte_carlo"] = {"status": "no_data" if not shared_1h_data else "already_running"}
                except asyncio.TimeoutError:
                    deep_training_state["results"]["monte_carlo"] = {"status": "timeout", "msg": "超过10分钟限制"}
                    TitanState.add_log("warn", "[5/6] 蒙特卡洛超时(10分钟限制), 已安全中止")
                except Exception as e:
                    deep_training_state["results"]["monte_carlo"] = {"status": "error", "error": str(e)[:100]}
                    TitanState.add_log("warn", f"[5/6] 蒙特卡洛异常: {str(e)[:50]}")
            else:
                deep_training_state["results"]["monte_carlo"] = {"status": "skipped"}

            deep_training_state["stage"] = "simulation"
            deep_training_state["progress"] = 85
            top15_by_mcap = ['BTC', 'ETH', 'XRP', 'BNB', 'SOL', 'ADA', 'TRX', 'AVAX', 'SUI', 'TON', 'DOT', 'LTC', 'BCH', 'NEAR', 'ICP']
            sim_symbols = [s for s in top15_by_mcap if s in elite]
            batches = [sim_symbols[i:i+5] for i in range(0, len(sim_symbols), 5)]
            batch_results = []
            total_batches = len(batches)
            deep_training_state["progress_msg"] = f"[6/6] 进化模拟: 市值前15名, 分{total_batches}批×5个资产..."
            TitanState.add_log("ml", f"[6/6] 进化模拟启动: {len(sim_symbols)}个资产, 分{total_batches}批执行")
            TitanState.add_log("ml", f"  市值前15: {', '.join(sim_symbols)}")
            all_batches_ok = True
            sim_preloaded = {s: local_ohlcv_map[s] for s in sim_symbols if s in local_ohlcv_map} if local_ohlcv_map else None
            for batch_idx, batch in enumerate(batches):
                batch_num = batch_idx + 1
                batch_pct = 85 + int(13 * batch_idx / total_batches)
                deep_training_state["progress"] = batch_pct
                deep_training_state["progress_msg"] = f"[6/6] 第{batch_num}/{total_batches}批: {', '.join(batch)}..."
                TitanState.add_log("ml", f"  第{batch_num}批开始: {', '.join(batch)}")
                batch_preloaded = {s: sim_preloaded[s] for s in batch if s in sim_preloaded} if sim_preloaded else None
                try:
                    while simulator.running:
                        await asyncio.sleep(2)
                    await asyncio.wait_for(
                        simulator.run_simulation(commander.exchange, batch, years=0.25, initial_capital=10000, retrain_interval_bars=99999, deadline_seconds=600, preloaded_data=batch_preloaded),
                        timeout=720
                    )
                    batch_status = simulator.results or {}
                    perf = batch_status.get("performance", {})
                    total_trades = perf.get("total_trades", 0)
                    final_capital = perf.get("final_equity", 0)
                    batch_results.append({"batch": batch_num, "symbols": batch, "status": "ok", "trades": total_trades, "capital": round(final_capital, 2)})
                    TitanState.add_log("ml", f"  ✅ 第{batch_num}批完成: {', '.join(batch)} | 交易{total_trades}笔 | 资金${final_capital:.0f}")
                except asyncio.TimeoutError:
                    simulator.running = False
                    batch_results.append({"batch": batch_num, "symbols": batch, "status": "timeout"})
                    TitanState.add_log("warn", f"  ⏰ 第{batch_num}批超时(15分钟): {', '.join(batch)}")
                    all_batches_ok = False
                except Exception as e:
                    simulator.running = False
                    batch_results.append({"batch": batch_num, "symbols": batch, "status": "error", "error": str(e)[:80]})
                    TitanState.add_log("warn", f"  ❌ 第{batch_num}批异常: {str(e)[:50]}")
                    all_batches_ok = False
                await asyncio.sleep(1)
            ok_batches = sum(1 for b in batch_results if b["status"] == "ok")
            total_sim_trades = sum(b.get("trades", 0) for b in batch_results)
            if ok_batches == total_batches:
                deep_training_state["results"]["simulator"] = {"status": "ok", "assets": len(sim_symbols), "batches": f"{ok_batches}/{total_batches}", "trades": total_sim_trades, "batch_details": batch_results}
                TitanState.add_log("ml", f"✅ [6/6] 进化模拟全部完成! {len(sim_symbols)}个资产, {total_batches}批全部成功, 共{total_sim_trades}笔交易")
            elif ok_batches > 0:
                deep_training_state["results"]["simulator"] = {"status": "partial", "assets": len(sim_symbols), "batches": f"{ok_batches}/{total_batches}", "trades": total_sim_trades, "batch_details": batch_results}
                TitanState.add_log("warn", f"[6/6] 进化模拟部分完成: {ok_batches}/{total_batches}批成功, 共{total_sim_trades}笔交易")
            else:
                deep_training_state["results"]["simulator"] = {"status": "failed", "batches": f"0/{total_batches}", "batch_details": batch_results}
                TitanState.add_log("warn", f"[6/6] 进化模拟全部失败")

            deep_training_state["stage"] = "complete"
            deep_training_state["progress"] = 100
            ok_count = sum(1 for v in deep_training_state["results"].values() if v.get("status") in ("ok", "partial"))
            deep_training_state["progress_msg"] = f"全量深度学习完成! {ok_count}/6模型成功"
            TitanState.add_log("system", f"🎓 全量深度学习完成! {ok_count}/6模型成功, {len(elite)}个精英资产")
        except Exception as e:
            deep_training_state["progress_msg"] = f"异常: {str(e)[:50]}"
            TitanState.add_log("warn", f"全量深度学习异常: {str(e)[:50]}")
        finally:
            deep_training_state["running"] = False

    asyncio.create_task(run_all_training())
    TitanState.add_log("system", f"🚀 全量深度学习启动: {len(elite)}个精英资产 → Modal云端(Stage1-2) + 本地优化(Stage3-6)")
    return {
        "status": "started",
        "total_assets": len(elite),
        "training_mode": "modal_cloud + local_optimization",
        "models": ["ml_engine(Modal)", "money_manager(Modal)", "mega_backtest", "darwin", "monte_carlo", "simulator"],
        "elite_coins": elite,
    }


@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok" if _app_ready else "starting",
        "ready": _app_ready,
    }


STATIC_DIR = os.path.join(BASE_DIR, "client", "dist")
STATIC_ASSETS = os.path.join(STATIC_DIR, "assets")

_INDEX_HTML_CACHE = None

def _load_index_html():
    global _INDEX_HTML_CACHE
    if _INDEX_HTML_CACHE:
        return
    idx_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(idx_path):
        try:
            with open(idx_path, "r", encoding="utf-8") as _f:
                _INDEX_HTML_CACHE = _f.read()
        except Exception:
            pass

_load_index_html()


@app.get("/api/position-guard")
async def get_position_guard_status():
    try:
        guard_data = TitanState.market_snapshot.get("position_guard", {})
        return {
            "status": position_guard.get_status(),
            "last_check": guard_data,
            "recent_actions": position_guard.get_guard_log(20),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/position-advisor")
async def get_position_advisor_status():
    try:
        return {
            "status": position_advisor.get_status(),
            "snapshot": TitanState.market_snapshot.get("position_advisor", {}),
            "history": position_advisor.get_advice_history(20),
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/position-advisor/advise/{position_id}")
async def advise_single_position(position_id: str):
    try:
        if position_id not in paper_trader.positions:
            return JSONResponse(status_code=404, content={"error": "持仓不存在"})

        pt_price_map = {}
        for pid, pos in paper_trader.positions.items():
            pt_price_map[pos["symbol"]] = pos.get("current_price", pos["entry_price"])

        pos_display = paper_trader.get_positions_display(pt_price_map)
        target_pos = next((p for p in pos_display if p["id"] == position_id), None)
        if not target_pos:
            return JSONResponse(status_code=404, content={"error": "持仓显示数据未找到"})

        position_advisor.last_advice_time.pop(position_id, None)

        advisor_context = {
            "regime": getattr(dispatcher, 'current_regime', 'unknown'),
            "btc_price": TitanState.market_snapshot.get("btc_pulse", {}).get("price", 0),
            "btc_change": TitanState.market_snapshot.get("btc_pulse", {}).get("change", "0"),
            "fng": TitanState.market_snapshot.get("btc_pulse", {}).get("fng", 50),
            "size_multiplier": ai_coordinator.get_size_multiplier(),
            "drawdown_pct": ai_coordinator.module_metrics.get("drawdown_pct", 0),
            "consecutive_wins": paper_trader.consecutive_wins,
            "consecutive_losses": paper_trader.consecutive_losses,
        }

        advice = position_advisor.advise_position(target_pos, advisor_context)

        if advice and position_id in paper_trader.positions:
            paper_trader.positions[position_id]["ai_advisor"] = {
                "action": advice.get("action", "hold"),
                "confidence": advice.get("confidence", 50),
                "summary": advice.get("summary", ""),
                "risk": advice.get("risk_assessment", "medium"),
                "urgency": advice.get("urgency", "low"),
                "reasoning": advice.get("reasoning_chain", [])[:3],
                "timestamp": advice.get("timestamp", ""),
                "source": advice.get("source", "rule"),
            }
            paper_trader.save()

        return advice
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/attribution/chart-data")
async def get_attribution_chart_data():
    try:
        return attribution.get_chart_data()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


_MIME_TYPES = {
    ".js": "application/javascript",
    ".css": "text/css",
    ".html": "text/html",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".map": "application/json",
}

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    from fastapi.responses import HTMLResponse
    try:
        _load_index_html()
        if full_path:
            safe_path = os.path.normpath(full_path)
            if not safe_path.startswith(".."):
                file_path = os.path.join(STATIC_DIR, safe_path)
                try:
                    resolved = os.path.realpath(file_path)
                    real_static = os.path.realpath(STATIC_DIR)
                    if resolved.startswith(real_static) and os.path.isfile(resolved):
                        ext = os.path.splitext(resolved)[1].lower()
                        media_type = _MIME_TYPES.get(ext)
                        return FileResponse(resolved, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"} if ext in (".js", ".css", ".woff2") else {"Cache-Control": "no-cache"})
                except OSError:
                    pass
        if _INDEX_HTML_CACHE:
            return HTMLResponse(content=_INDEX_HTML_CACHE, headers={"Cache-Control": "no-cache"})
        return JSONResponse(content={"status": "starting" if not _app_ready else "ok", "message": "Titan API running. Frontend not built yet."})
    except Exception as e:
        if _INDEX_HTML_CACHE:
            return HTMLResponse(content=_INDEX_HTML_CACHE, headers={"Cache-Control": "no-cache"})
        return JSONResponse(content={"status": "starting", "message": "Titan API starting up..."})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run(app, host="0.0.0.0", port=port)
