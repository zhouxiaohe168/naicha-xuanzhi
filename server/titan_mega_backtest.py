import os
import json
import time
import random
import logging
from datetime import datetime
from copy import deepcopy

import numpy as np
import pandas as pd

logger = logging.getLogger("TitanMega")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "titan_mega_backtest.json")

PARAM_BOUNDS = {
    "rsi_entry": (20, 35),
    "tp_atr": (1.5, 4.0),
    "sl_atr": (0.5, 2.0),
    "adx_threshold": (18, 35),
    "ma_period": (15, 60),
    "kelly_fraction": (0.2, 0.8),
    "max_risk": (0.01, 0.05),
    "max_position": (0.08, 0.40),
}

MUTATION_SIGMA = {
    "rsi_entry": 3.0,
    "tp_atr": 0.4,
    "sl_atr": 0.3,
    "adx_threshold": 3.0,
    "ma_period": 5.0,
    "kelly_fraction": 0.1,
    "max_risk": 0.005,
    "max_position": 0.05,
}

DEFAULT_PARAMS = {
    "rsi_entry": 28,
    "tp_atr": 2.5,
    "sl_atr": 1.2,
    "adx_threshold": 25,
    "ma_period": 20,
    "kelly_fraction": 0.5,
    "max_risk": 0.02,
    "max_position": 0.20,
}


class TitanMegaBacktest:
    def __init__(self):
        self.running = False
        self.progress = 0
        self.progress_msg = ""
        self.total_generations = 0
        self.total_backtests = 0
        self.best_calmar = -999.0
        self.best_params = deepcopy(DEFAULT_PARAMS)
        self.improvement_history = []
        self._load_state()

    def _load_state(self):
        try:
            if os.path.exists(STATE_PATH):
                with open(STATE_PATH, "r") as f:
                    state = json.load(f)
                self.total_generations = state.get("total_generations", 0)
                self.total_backtests = state.get("total_backtests", 0)
                self.best_calmar = state.get("best_calmar", -999.0)
                self.best_params = state.get("best_params", deepcopy(DEFAULT_PARAMS))
                self.improvement_history = state.get("improvement_history", [])
                logger.info(f"万次回测状态已加载: {self.total_backtests}次回测, 最佳Calmar={self.best_calmar:.4f}")
        except Exception as e:
            logger.warning(f"万次回测状态加载失败: {e}")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
            state = {
                "total_generations": self.total_generations,
                "total_backtests": self.total_backtests,
                "best_calmar": round(self.best_calmar, 6),
                "best_params": self.best_params,
                "improvement_history": self.improvement_history[-200:],
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(STATE_PATH, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"万次回测状态保存失败: {e}")

    def _mutate_params(self, base_params):
        mutated = {}
        for key, (lo, hi) in PARAM_BOUNDS.items():
            base_val = base_params.get(key, DEFAULT_PARAMS[key])
            sigma = MUTATION_SIGMA[key]
            new_val = base_val + random.gauss(0, sigma)
            new_val = max(lo, min(hi, new_val))
            if key in ("rsi_entry", "adx_threshold", "ma_period"):
                new_val = int(round(new_val))
            else:
                new_val = round(new_val, 4)
            mutated[key] = new_val
        return mutated

    def _compute_indicators(self, df):
        close = df["c"].values.astype(np.float64)
        high = df["h"].values.astype(np.float64)
        low = df["l"].values.astype(np.float64)

        delta = np.diff(close, prepend=close[0])
        gain = np.where(delta > 0, delta, 0.0)
        loss = np.where(delta < 0, -delta, 0.0)
        avg_gain = pd.Series(gain).rolling(14, min_periods=14).mean().values
        avg_loss = pd.Series(loss).rolling(14, min_periods=14).mean().values
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        tr = np.maximum(high - low,
                        np.maximum(np.abs(high - np.roll(close, 1)),
                                   np.abs(low - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).rolling(14, min_periods=14).mean().values

        plus_dm = np.where((high - np.roll(high, 1)) > (np.roll(low, 1) - low),
                           np.maximum(high - np.roll(high, 1), 0), 0.0)
        minus_dm = np.where((np.roll(low, 1) - low) > (high - np.roll(high, 1)),
                            np.maximum(np.roll(low, 1) - low, 0), 0.0)
        plus_dm[0] = 0.0
        minus_dm[0] = 0.0
        atr14 = atr + 1e-10
        plus_di = 100.0 * pd.Series(plus_dm).rolling(14, min_periods=14).mean().values / atr14
        minus_di = 100.0 * pd.Series(minus_dm).rolling(14, min_periods=14).mean().values / atr14
        dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
        adx = pd.Series(dx).rolling(14, min_periods=14).mean().values

        return close, high, low, rsi, atr, adx

    def _fast_backtest(self, df, params):
        if len(df) < 100:
            return {"total_return": 0, "max_drawdown": 1.0, "win_rate": 0,
                    "sharpe": 0, "calmar": -999, "trade_count": 0}

        close, high, low, rsi, atr, adx = self._compute_indicators(df)

        rsi_entry = params["rsi_entry"]
        rsi_short = 100 - rsi_entry
        tp_atr = params["tp_atr"]
        sl_atr = params["sl_atr"]
        adx_threshold = params["adx_threshold"]
        ma_period = params["ma_period"]
        kelly_frac = params["kelly_fraction"]
        max_risk = params["max_risk"]
        max_pos = params["max_position"]

        ma = pd.Series(close).rolling(ma_period, min_periods=ma_period).mean().values

        starting_equity = 10000.0
        equity = starting_equity
        peak_equity = starting_equity
        max_dd = 0.0
        position = 0
        entry_price = 0.0
        entry_atr = 0.0
        pos_size = 0.0
        wins = 0
        trades = 0
        trade_returns = []
        cooldown = 0

        start_idx = max(ma_period, 30)

        for i in range(start_idx, len(close)):
            if np.isnan(rsi[i]) or np.isnan(adx[i]) or np.isnan(atr[i]) or np.isnan(ma[i]):
                continue
            if cooldown > 0:
                cooldown -= 1

            if position == 0 and cooldown == 0:
                sl_dist = sl_atr * atr[i]
                if sl_dist <= 0 or close[i] <= 0 or atr[i] <= 0:
                    continue
                risk_amount = equity * max_risk
                calc_pos = min(risk_amount / (sl_dist / close[i]), equity * max_pos) * kelly_frac
                if calc_pos < equity * 0.005:
                    calc_pos = equity * 0.005

                if rsi[i] < rsi_entry and close[i] > ma[i] and adx[i] > adx_threshold:
                    position = 1
                    entry_price = close[i]
                    entry_atr = atr[i]
                    pos_size = calc_pos
                    trades += 1
                elif rsi[i] > rsi_short and close[i] < ma[i] and adx[i] > adx_threshold:
                    position = -1
                    entry_price = close[i]
                    entry_atr = atr[i]
                    pos_size = calc_pos
                    trades += 1
                elif rsi[i] < (rsi_entry - 5) and adx[i] <= adx_threshold:
                    position = 1
                    entry_price = close[i]
                    entry_atr = atr[i]
                    pos_size = calc_pos * 0.5
                    trades += 1
                elif rsi[i] > (rsi_short + 5) and adx[i] <= adx_threshold:
                    position = -1
                    entry_price = close[i]
                    entry_atr = atr[i]
                    pos_size = calc_pos * 0.5
                    trades += 1

            elif position == 1:
                tp_price = entry_price + tp_atr * entry_atr
                sl_price = entry_price - sl_atr * entry_atr
                if high[i] >= tp_price:
                    pnl = pos_size * (tp_price - entry_price) / entry_price
                    equity += pnl
                    trade_returns.append(pnl / (pos_size + 1e-10))
                    wins += 1
                    position = 0
                    cooldown = 2
                elif low[i] <= sl_price:
                    pnl = pos_size * (sl_price - entry_price) / entry_price
                    equity += pnl
                    trade_returns.append(pnl / (pos_size + 1e-10))
                    position = 0
                    cooldown = 3

            elif position == -1:
                tp_price = entry_price - tp_atr * entry_atr
                sl_price = entry_price + sl_atr * entry_atr
                if low[i] <= tp_price:
                    pnl = pos_size * (entry_price - tp_price) / entry_price
                    equity += pnl
                    trade_returns.append(pnl / (pos_size + 1e-10))
                    wins += 1
                    position = 0
                    cooldown = 2
                elif high[i] >= sl_price:
                    pnl = pos_size * (entry_price - sl_price) / entry_price
                    equity += pnl
                    trade_returns.append(pnl / (pos_size + 1e-10))
                    position = 0
                    cooldown = 3

            if equity > peak_equity:
                peak_equity = equity
            dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
            if dd > max_dd:
                max_dd = dd
            if equity <= starting_equity * 0.5:
                break

        total_return = (equity - starting_equity) / starting_equity
        win_rate = wins / trades if trades > 0 else 0.0

        if len(trade_returns) > 1:
            avg_r = np.mean(trade_returns)
            std_r = np.std(trade_returns)
            sharpe = (avg_r / (std_r + 1e-10)) * np.sqrt(252)
        else:
            sharpe = 0.0

        calmar = total_return / (max_dd + 1e-10) if max_dd > 0.001 else (total_return * 100 if total_return > 0 else -999)

        if trades < 5:
            calmar = -999

        return {
            "total_return": round(total_return, 6),
            "max_drawdown": round(max_dd, 6),
            "win_rate": round(win_rate, 4),
            "sharpe": round(sharpe, 4),
            "calmar": round(calmar, 4),
            "trade_count": trades,
        }

    def run_evolution_cycle(self, data_map, num_iterations=100):
        if self.running:
            return {"error": "万次回测引擎正在运行中"}

        self.running = True
        self.progress = 0
        self.progress_msg = "万次回测永动机启动..."

        try:
            valid_data = {}
            for sym, df in data_map.items():
                if isinstance(df, pd.DataFrame) and len(df) >= 100:
                    required = {"o", "h", "l", "c", "v"}
                    if required.issubset(set(df.columns)):
                        valid_data[sym] = df

            if not valid_data:
                self.running = False
                return {"error": "无有效OHLCV数据"}

            generation_best_calmar = self.best_calmar
            generation_best_params = deepcopy(self.best_params)
            improved = False

            for iteration in range(num_iterations):
                candidate = self._mutate_params(self.best_params)

                total_calmar = 0.0
                total_assets = 0

                for sym, df in valid_data.items():
                    result = self._fast_backtest(df, candidate)
                    if result["trade_count"] >= 5:
                        total_calmar += result["calmar"]
                        total_assets += 1

                self.total_backtests += len(valid_data)

                if total_assets > 0:
                    avg_calmar = total_calmar / total_assets
                else:
                    avg_calmar = -999

                if avg_calmar > generation_best_calmar:
                    generation_best_calmar = avg_calmar
                    generation_best_params = deepcopy(candidate)
                    improved = True
                    logger.info(f"[MegaBacktest] 新最佳Calmar={avg_calmar:.4f} @ 迭代{iteration+1}")

                self.progress = int((iteration + 1) / num_iterations * 100)
                self.progress_msg = f"迭代 {iteration+1}/{num_iterations} | 最佳Calmar: {generation_best_calmar:.4f}"

            self.total_generations += 1

            if improved:
                self.best_calmar = generation_best_calmar
                self.best_params = generation_best_params
                self.improvement_history.append({
                    "generation": self.total_generations,
                    "calmar": round(generation_best_calmar, 6),
                    "params": deepcopy(generation_best_params),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_backtests": self.total_backtests,
                })

            self._save_state()

            self.progress = 100
            self.progress_msg = "万次回测周期完成"

            return {
                "generation": self.total_generations,
                "iterations": num_iterations,
                "improved": improved,
                "best_calmar": round(self.best_calmar, 6),
                "best_params": deepcopy(self.best_params),
                "total_backtests": self.total_backtests,
                "assets_tested": len(valid_data),
            }
        except Exception as e:
            logger.error(f"万次回测异常: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}
        finally:
            self.running = False

    def get_best_params(self):
        return deepcopy(self.best_params)

    def get_status(self):
        return {
            "running": self.running,
            "progress": self.progress,
            "progress_msg": self.progress_msg,
            "total_backtests": self.total_backtests,
            "total_generations": self.total_generations,
            "best_calmar": round(self.best_calmar, 6),
            "best_params": deepcopy(self.best_params),
            "improvement_count": len(self.improvement_history),
            "last_improvement": self.improvement_history[-1] if self.improvement_history else None,
        }


mega_backtest = TitanMegaBacktest()
