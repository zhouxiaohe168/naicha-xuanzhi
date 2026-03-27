import logging
import numpy as np
import pandas as pd
from datetime import datetime
import pytz

logger = logging.getLogger("TitanMTF")
BJ_TZ = pytz.timezone('Asia/Shanghai')

class TitanMTF:
    """Multi-Timeframe Engine - 多时间框架引擎
    
    Hierarchy:
    - Weekly: Major trend direction
    - Daily: Medium-term trend confirmation (closes at Beijing 08:00)
    - 4H: Opportunity zones (key update at Beijing 12:00)
    - 1H: Entry timing confirmation
    - 15m: Precise entry point
    
    Beijing Time K-line alignment:
    - Daily: 08:00 BJT close
    - 4H: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00 BJT
    - 1H: Every hour on the hour
    - 15m: :00, :15, :30, :45
    """
    
    SIGNAL_WEIGHTS = {
        'weekly': 0.15,
        'daily': 0.25,
        'h4': 0.30,
        'h1': 0.20,
        'm15': 0.10,
    }
    
    @staticmethod
    def get_beijing_time():
        return datetime.now(BJ_TZ)
    
    @staticmethod
    def is_kline_close(timeframe):
        """Check if current Beijing time is at a K-line close for given timeframe"""
        now = TitanMTF.get_beijing_time()
        h, m = now.hour, now.minute
        if timeframe == '1d':
            return h == 8 and m < 5
        elif timeframe == '4h':
            return h in [0, 4, 8, 12, 16, 20] and m < 5
        elif timeframe == '1h':
            return m < 5
        elif timeframe == '15m':
            return m % 15 < 2
        return False
    
    @staticmethod
    def analyze_trend(df, timeframe_label):
        """Analyze trend for a given timeframe. Returns dict with direction, strength, key_levels"""
        if df is None or len(df) < 30:
            return {'direction': 'unknown', 'strength': 0, 'bias': 0, 'label': timeframe_label}
        
        close = df['c'].astype(float)
        high = df['h'].astype(float)
        low = df['l'].astype(float)
        
        # MAs
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean() if len(close) >= 50 else ma20
        
        price = close.iloc[-1]
        ma20_val = ma20.iloc[-1]
        ma50_val = ma50.iloc[-1]
        
        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss_s = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / (loss_s + 1e-10)
        rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        
        # Trend direction
        ma_bullish = price > ma20_val > ma50_val
        ma_bearish = price < ma20_val < ma50_val
        
        # MA slope (last 5 bars)
        if len(ma20) >= 5:
            ma_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / (ma20.iloc[-5] + 1e-10) * 100
        else:
            ma_slope = 0
        
        # Direction scoring: -100 to +100
        bias = 0
        if ma_bullish:
            bias += 40
        elif ma_bearish:
            bias -= 40
        
        if rsi > 60:
            bias += 20
        elif rsi < 40:
            bias -= 20
        
        bias += ma_slope * 10
        bias = max(-100, min(100, bias))
        
        if bias > 30:
            direction = 'bullish'
        elif bias < -30:
            direction = 'bearish'
        else:
            direction = 'neutral'
        
        strength = abs(bias)
        
        # Support/Resistance (last 20 bars)
        recent_high = float(high.iloc[-20:].max())
        recent_low = float(low.iloc[-20:].min())
        
        return {
            'direction': direction,
            'strength': strength,
            'bias': round(bias, 1),
            'rsi': round(rsi, 1),
            'ma20': round(float(ma20_val), 6),
            'ma50': round(float(ma50_val), 6),
            'ma_slope': round(ma_slope, 2),
            'support': round(recent_low, 6),
            'resistance': round(recent_high, 6),
            'label': timeframe_label,
        }
    
    @staticmethod 
    def analyze_entry(df_1h, df_15m, direction_bias):
        """Analyze 1H and 15m for precise entry signals.
        direction_bias: 'bullish' or 'bearish' from higher timeframes.
        Returns entry signal dict.
        """
        result = {
            'entry_signal': False,
            'entry_quality': 0,
            'entry_timeframe': None,
            'entry_reason': '',
            'h1_aligned': False,
            'm15_aligned': False,
        }
        
        h1_trend = TitanMTF.analyze_trend(df_1h, '1H')
        m15_trend = TitanMTF.analyze_trend(df_15m, '15m')
        
        result['h1_trend'] = h1_trend
        result['m15_trend'] = m15_trend
        
        # Check 1H alignment with higher TF direction
        if direction_bias == 'bullish' and h1_trend['direction'] == 'bullish':
            result['h1_aligned'] = True
        elif direction_bias == 'bearish' and h1_trend['direction'] == 'bearish':
            result['h1_aligned'] = True
        
        # Check 15m alignment
        if direction_bias == 'bullish' and m15_trend['direction'] == 'bullish':
            result['m15_aligned'] = True
        elif direction_bias == 'bearish' and m15_trend['direction'] == 'bearish':
            result['m15_aligned'] = True
        
        # Entry quality scoring
        quality = 0
        reasons = []
        
        if result['h1_aligned']:
            quality += 40
            reasons.append('1H趋势对齐')
        
        if result['m15_aligned']:
            quality += 30
            reasons.append('15m趋势对齐')
        
        # RSI confirmation on 15m
        if direction_bias == 'bullish' and m15_trend['rsi'] < 40:
            quality += 20
            reasons.append('15m RSI超卖回升')
        elif direction_bias == 'bearish' and m15_trend['rsi'] > 60:
            quality += 20
            reasons.append('15m RSI超买回落')
        
        # MA slope confirmation on 1H
        if direction_bias == 'bullish' and h1_trend['ma_slope'] > 0:
            quality += 10
            reasons.append('1H均线上扬')
        elif direction_bias == 'bearish' and h1_trend['ma_slope'] < 0:
            quality += 10
            reasons.append('1H均线下行')
        
        result['entry_quality'] = min(quality, 100)
        result['entry_signal'] = quality >= 50
        result['entry_reason'] = ' + '.join(reasons) if reasons else '无入场条件'
        result['entry_timeframe'] = '15m' if result['m15_aligned'] else ('1H' if result['h1_aligned'] else None)
        
        return result
    
    @staticmethod
    def full_analysis(data_map):
        """Run full multi-timeframe analysis.
        data_map should contain keys: '1w', '1d', '4h', '1h', '15m'
        Returns comprehensive MTF report.
        """
        weekly = TitanMTF.analyze_trend(data_map.get('1w'), '周线')
        daily = TitanMTF.analyze_trend(data_map.get('1d'), '日线')
        h4 = TitanMTF.analyze_trend(data_map.get('4h'), '4H')
        
        # Weighted direction consensus
        directions = {
            'bullish': 0, 'bearish': 0, 'neutral': 0
        }
        
        tf_results = [
            (weekly, TitanMTF.SIGNAL_WEIGHTS['weekly']),
            (daily, TitanMTF.SIGNAL_WEIGHTS['daily']),
            (h4, TitanMTF.SIGNAL_WEIGHTS['h4']),
        ]
        
        for tf, weight in tf_results:
            d = tf.get('direction', 'neutral')
            directions[d] = directions.get(d, 0) + weight
        
        consensus_dir = max(directions, key=directions.get)
        consensus_score = round(directions[consensus_dir] / sum(directions.values()) * 100, 1) if sum(directions.values()) > 0 else 0
        
        # Alignment count
        aligned = sum(1 for tf, _ in tf_results if tf.get('direction') == consensus_dir)
        
        # Entry analysis
        entry = TitanMTF.analyze_entry(
            data_map.get('1h'), data_map.get('15m'), consensus_dir
        )
        
        # Overall MTF score: -100 (strong bearish) to +100 (strong bullish)
        weighted_bias = sum(tf.get('bias', 0) * w for tf, w in tf_results)
        if entry.get('h1_aligned'):
            h1_bias = entry.get('h1_trend', {}).get('bias', 0)
            weighted_bias += h1_bias * TitanMTF.SIGNAL_WEIGHTS['h1']
        if entry.get('m15_aligned'):
            m15_bias = entry.get('m15_trend', {}).get('bias', 0)
            weighted_bias += m15_bias * TitanMTF.SIGNAL_WEIGHTS['m15']
        
        # Beijing time info
        bj_now = TitanMTF.get_beijing_time()
        
        return {
            'weekly': weekly,
            'daily': daily,
            'h4': h4,
            'entry': entry,
            'consensus': {
                'direction': consensus_dir,
                'score': consensus_score,
                'aligned_count': aligned,
                'total_timeframes': 3,
                'weighted_bias': round(weighted_bias, 1),
            },
            'beijing_time': bj_now.strftime('%Y-%m-%d %H:%M:%S'),
            'next_daily_close': '08:00 BJT',
            'next_4h_close': f'{((bj_now.hour // 4 + 1) * 4) % 24:02d}:00 BJT',
            'mtf_signal': {
                'direction': consensus_dir,
                'entry_ready': entry.get('entry_signal', False),
                'entry_quality': entry.get('entry_quality', 0),
                'confidence': round(abs(weighted_bias), 1),
            }
        }
