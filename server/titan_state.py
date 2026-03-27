import os
import asyncio
import pytz
from collections import deque
from datetime import datetime


CONFIG = {
    'VERSION': 'V19.2 泰坦神殿',
    'TIMEZONE': 'Asia/Shanghai',
    'ACCOUNT_SIZE': 10000,
    'RISK_BASE': 0.015,
    'RISK_MAX': 0.03,
    'BTC_CRASH_THRESHOLD': -0.03,
    'ADX_TREND_MIN': 25,
    'ADX_RANGE_MAX': 20,
    'TIER1_CORE': [
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'SUI', 'TON',
        'NEAR', 'APT', 'ATOM', 'LTC', 'TRX', 'HBAR',
    ],
    'TIER2_MAINSTREAM': [
        'BCH', 'XLM', 'ZEC', 'DASH', 'ICP', 'SEI', 'TIA', 'EGLD', 'CORE',
        'ONDO', 'MKR', 'PENDLE',
        'FET', 'TAO', 'RNDR', 'WLD', 'AKT', 'AGIX', 'GLM', 'FIL', 'AR', 'JASMY', 'HNT', 'THETA',
        'POL', 'MNT', 'OP', 'ARB', 'STRK', 'ZK', 'METIS', 'MANTA',
        'UNI', 'AAVE', 'JUP', 'CAKE', 'CRV', 'CVX', 'KNC', 'LDO', 'ENA', 'BNT', 'RPL',
        'DOGE', 'SHIB', 'PEPE', 'BONK', 'FLOKI', 'WIF',
        'IMX', 'AXS', 'SAND', 'MANA', 'CHZ', 'BEAM', 'GALA', 'MASK',
    ],
    'TIER3_SPECULATIVE': [
        'BRETT', 'POPCAT', 'MOODENG', 'GOAT', 'PNUT',
    ],
    'CORE_WATCHLIST': [
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'SUI', 'TON',
        'NEAR', 'APT', 'ATOM', 'LTC', 'TRX', 'HBAR',
        'BCH', 'XLM', 'ZEC', 'DASH', 'ICP', 'SEI', 'TIA', 'EGLD', 'CORE',
        'ONDO', 'MKR', 'PENDLE',
        'FET', 'TAO', 'RNDR', 'WLD', 'AKT', 'AGIX', 'GLM', 'FIL', 'AR', 'JASMY', 'HNT', 'THETA',
        'POL', 'MNT', 'OP', 'ARB', 'STRK', 'ZK', 'METIS', 'MANTA',
        'UNI', 'AAVE', 'JUP', 'CAKE', 'CRV', 'CVX', 'KNC', 'LDO', 'ENA', 'BNT', 'RPL',
        'DOGE', 'SHIB', 'PEPE', 'BONK', 'FLOKI', 'WIF', 'BRETT', 'POPCAT', 'MOODENG', 'GOAT', 'PNUT',
        'IMX', 'AXS', 'SAND', 'MANA', 'CHZ', 'BEAM', 'GALA', 'MASK',
    ],
    'ELITE_UNIVERSE': [
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'SUI', 'TON',
        'NEAR', 'APT', 'ATOM', 'LTC', 'TRX', 'HBAR',
        'BCH', 'XLM', 'ZEC', 'DASH', 'ICP', 'SEI', 'TIA', 'EGLD', 'CORE',
        'ONDO', 'MKR', 'PENDLE',
        'FET', 'TAO', 'RNDR', 'WLD', 'AKT', 'AGIX', 'GLM', 'FIL', 'AR', 'JASMY', 'HNT', 'THETA',
        'POL', 'MNT', 'OP', 'ARB', 'STRK', 'ZK', 'METIS', 'MANTA',
        'UNI', 'AAVE', 'JUP', 'CAKE', 'CRV', 'CVX', 'KNC', 'LDO', 'ENA', 'BNT', 'RPL',
        'DOGE', 'SHIB', 'PEPE', 'BONK', 'FLOKI', 'WIF',
        'IMX', 'AXS', 'SAND', 'MANA', 'CHZ', 'BEAM', 'GALA', 'MASK',
    ],
    'DYNAMIC_SUPPLEMENT_LIMIT': 20,
    'VOLUME_MIN_USDT': 1_000_000,
    'TOP_TICKERS_LIMIT': 100,
    'STABLECOIN_BLACKLIST': {'USDC', 'DAI', 'FDUSD', 'TUSD', 'USDP', 'USDD', 'BUSD', 'GUSD', 'FRAX', 'LUSD', 'PYUSD', 'USDT', 'UST', 'CEUR', 'CUSD', 'USD1', 'USDe'},
    'ASSET_BLACKLIST': {'XAUT', 'PAXG', 'BLUAI', 'POWER', 'USD1'},
    'JUNK_SUFFIXES': ('3S', '3L', '5S', '5L', 'UP', 'DOWN', 'BEAR', 'BULL', '2S', '2L', '4S', '4L'),
    'EMERGENCY_FREEZE_TREND': False,
    'GRID_HIGH_LIQUIDITY_ONLY': True,
    'GRID_ALLOWED_PAIRS': {'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'AVAX', 'DOT', 'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'FIL'},
    'GRID_BUDGET_LIMIT': 20000,
}

_TIER1_SET = set(CONFIG['TIER1_CORE'])
_TIER2_SET = set(CONFIG['TIER2_MAINSTREAM'])
_TIER3_SET = set(CONFIG['TIER3_SPECULATIVE'])

def get_coin_tier(symbol: str) -> int:
    base = symbol.replace("/USDT", "").replace("_USDT", "").replace("USDT", "")
    if base in _TIER1_SET:
        return 1
    elif base in _TIER2_SET:
        return 2
    elif base in _TIER3_SET:
        return 3
    return 2


class TitanState:
    market_snapshot = {
        "btc_pulse": {"price": 0, "change": "0%", "fng": 50, "fng_detail": {"value": 50, "label": "Neutral", "change": 0, "avg_7d": 50, "source": "default", "timestamp": 0}},
        "cruise": [],
        "logs": deque(maxlen=50),
        "scan_mode": "启动中",
        "total_scanned": 0,
        "scan_progress": {"current": 0, "total": 0, "scanning": False, "last_updated": 0},
    }
    backtest_history = deque(maxlen=500)
    backtest_result = None
    _position_lock = None
    _auto_exec_history = []

    @classmethod
    def get_position_lock(cls):
        if cls._position_lock is None:
            cls._position_lock = asyncio.Lock()
        return cls._position_lock

    @classmethod
    def add_log(cls, type_: str, msg: str):
        now = datetime.now(pytz.timezone(CONFIG['TIMEZONE'])).strftime('%H:%M:%S')
        cls.market_snapshot["logs"].appendleft({"time": now, "type": type_, "msg": msg})

    @classmethod
    def record_backtest_snapshot(cls, cruise_data):
        from server.titan_ml import TitanBacktester
        now = datetime.now(pytz.timezone(CONFIG['TIMEZONE'])).strftime('%Y-%m-%d %H:%M')
        snapshot = {
            "time": now,
            "signals": [
                {"sym": item["sym"], "score": item["score"], "price": item["price"],
                 "tp": item["tp"], "sl": item["sl"], "pos_val": item["pos_val"]}
                for item in cruise_data
            ]
        }
        cls.backtest_history.append(snapshot)
        if len(cls.backtest_history) >= 10:
            cls.backtest_result = TitanBacktester.run(list(cls.backtest_history))
