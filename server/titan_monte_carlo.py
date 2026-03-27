import os
import json
import random
import logging
from datetime import datetime
from copy import deepcopy

import numpy as np
import pandas as pd

logger = logging.getLogger("TitanMonteCarlo")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(BASE_DIR, "data", "titan_monte_carlo.json")

MM_PARAM_BOUNDS = {
    "kelly_fraction": (0.1, 0.8),
    "max_risk_per_trade": (0.005, 0.05),
    "max_position_pct": (0.05, 0.40),
    "drawdown_reduce_trigger": (0.03, 0.15),
    "drawdown_reduce_factor": (0.3, 0.8),
    "win_streak_boost": (1.0, 1.5),
    "loss_streak_cut": (0.3, 0.8),
    "max_streak_adjust": (2, 8),
    "tp_tier1_pct": (0.2, 0.5),
    "tp_tier1_atr": (0.8, 2.0),
    "tp_tier2_pct": (0.2, 0.4),
    "tp_tier2_atr": (1.5, 3.0),
    "tp_trail_atr": (0.5, 1.5),
    "pyramid_threshold_atr": (1.0, 2.5),
    "pyramid_scale": (0.3, 0.7),
    "max_pyramids": (1, 4),
    "daily_loss_limit": (0.01, 0.05),
    "correlation_cap": (0.5, 0.9),
}

MM_MUTATION_SIGMA = {
    "kelly_fraction": 0.08,
    "max_risk_per_trade": 0.005,
    "max_position_pct": 0.04,
    "drawdown_reduce_trigger": 0.02,
    "drawdown_reduce_factor": 0.08,
    "win_streak_boost": 0.08,
    "loss_streak_cut": 0.08,
    "max_streak_adjust": 1.0,
    "tp_tier1_pct": 0.05,
    "tp_tier1_atr": 0.2,
    "tp_tier2_pct": 0.04,
    "tp_tier2_atr": 0.3,
    "tp_trail_atr": 0.2,
    "pyramid_threshold_atr": 0.3,
    "pyramid_scale": 0.08,
    "max_pyramids": 0.8,
    "daily_loss_limit": 0.005,
    "correlation_cap": 0.08,
}

DEFAULT_MM_PARAMS = {
    "kelly_fraction": 0.5,
    "max_risk_per_trade": 0.02,
    "max_position_pct": 0.20,
    "drawdown_reduce_trigger": 0.06,
    "drawdown_reduce_factor": 0.5,
    "win_streak_boost": 1.2,
    "loss_streak_cut": 0.5,
    "max_streak_adjust": 4,
    "tp_tier1_pct": 0.3,
    "tp_tier1_atr": 1.0,
    "tp_tier2_pct": 0.3,
    "tp_tier2_atr": 2.0,
    "tp_trail_atr": 1.0,
    "pyramid_threshold_atr": 1.5,
    "pyramid_scale": 0.5,
    "max_pyramids": 2,
    "daily_loss_limit": 0.02,
    "correlation_cap": 0.7,
}

INT_PARAMS = {"max_streak_adjust", "max_pyramids"}


class TitanMonteCarlo:
    def __init__(self):
        self.running = False
        self.progress = 0
        self.progress_msg = ""
        self.total_simulations = 0
        self.total_generations = 0
        self.best_calmar = -999.0
        self.best_sharpe = -999.0
        self.best_params = deepcopy(DEFAULT_MM_PARAMS)
        self.improvement_history = []
        self.trade_pool = []
        self._load_state()

    def _load_state(self):
        try:
            if os.path.exists(STATE_PATH):
                with open(STATE_PATH, "r") as f:
                    state = json.load(f)
                self.total_simulations = state.get("total_simulations", 0)
                self.total_generations = state.get("total_generations", 0)
                self.best_calmar = state.get("best_calmar", -999.0)
                self.best_sharpe = state.get("best_sharpe", -999.0)
                self.best_params = state.get("best_params", deepcopy(DEFAULT_MM_PARAMS))
                self.improvement_history = state.get("improvement_history", [])
                logger.info(f"Monte Carlo状态已加载: {self.total_simulations}次模拟, 最佳Calmar={self.best_calmar:.4f}")
        except Exception as e:
            logger.warning(f"Monte Carlo状态加载失败: {e}")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
            state = {
                "total_simulations": self.total_simulations,
                "total_generations": self.total_generations,
                "best_calmar": round(self.best_calmar, 6),
                "best_sharpe": round(self.best_sharpe, 6),
                "best_params": {k: round(v, 6) if isinstance(v, float) else v for k, v in self.best_params.items()},
                "improvement_history": self.improvement_history[-100:],
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(STATE_PATH, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Monte Carlo状态保存失败: {e}")

    def _mutate_params(self, base_params):
        mutated = {}
        for key, (lo, hi) in MM_PARAM_BOUNDS.items():
            base_val = base_params.get(key, DEFAULT_MM_PARAMS.get(key, (lo + hi) / 2))
            sigma = MM_MUTATION_SIGMA.get(key, (hi - lo) * 0.1)
            new_val = base_val + random.gauss(0, sigma)
            new_val = max(lo, min(hi, new_val))
            if key in INT_PARAMS:
                new_val = int(round(new_val))
            else:
                new_val = round(new_val, 6)
            mutated[key] = new_val
        return mutated

    def build_trade_pool(self, data_map, strategy_params=None):
        from server.titan_mega_backtest import mega_backtest
        if strategy_params is None:
            strategy_params = mega_backtest.get_best_params()

        all_trades = []
        for sym, df in data_map.items():
            if not isinstance(df, pd.DataFrame) or len(df) < 100:
                continue
            required = {"o", "h", "l", "c", "v"}
            if not required.issubset(set(df.columns)):
                continue

            close, high, low, rsi, atr, adx = mega_backtest._compute_indicators(df)
            ma = pd.Series(close).rolling(int(strategy_params.get("ma_period", 20)),
                                          min_periods=int(strategy_params.get("ma_period", 20))).mean().values

            rsi_entry = strategy_params.get("rsi_entry", 28)
            rsi_short = 100 - rsi_entry
            adx_thresh = strategy_params.get("adx_threshold", 22)
            tp_atr_mult = strategy_params.get("tp_atr", 3.0)
            sl_atr_mult = strategy_params.get("sl_atr", 1.16)

            start_idx = max(int(strategy_params.get("ma_period", 20)), 30)
            position = 0
            entry_price = 0.0
            entry_atr = 0.0
            entry_idx = 0

            for i in range(start_idx, len(close)):
                if np.isnan(rsi[i]) or np.isnan(adx[i]) or np.isnan(atr[i]) or np.isnan(ma[i]):
                    continue

                if position == 0:
                    direction = 0
                    if rsi[i] < rsi_entry and close[i] > ma[i] and adx[i] > adx_thresh:
                        direction = 1
                    elif rsi[i] > rsi_short and close[i] < ma[i] and adx[i] > adx_thresh:
                        direction = -1
                    elif rsi[i] < (rsi_entry - 5) and adx[i] <= adx_thresh:
                        direction = 1
                    elif rsi[i] > (rsi_short + 5) and adx[i] <= adx_thresh:
                        direction = -1

                    if direction != 0:
                        position = direction
                        entry_price = close[i]
                        entry_atr = atr[i]
                        entry_idx = i

                elif position != 0:
                    if position == 1:
                        tp_price = entry_price + tp_atr_mult * entry_atr
                        sl_price = entry_price - sl_atr_mult * entry_atr
                        if high[i] >= tp_price or low[i] <= sl_price:
                            exit_price = tp_price if high[i] >= tp_price else sl_price
                            pnl_pct = (exit_price - entry_price) / entry_price
                            won = high[i] >= tp_price
                            bars_held = i - entry_idx
                            all_trades.append({
                                "sym": sym, "direction": 1, "pnl_pct": round(float(pnl_pct), 6),
                                "atr_at_entry": round(float(entry_atr), 8),
                                "entry_price": round(float(entry_price), 8),
                                "won": won, "bars_held": bars_held,
                                "high_excursion": round(float((max(high[entry_idx:i+1]) - entry_price) / entry_price), 6),
                                "low_excursion": round(float((entry_price - min(low[entry_idx:i+1])) / entry_price), 6),
                            })
                            position = 0
                    else:
                        tp_price = entry_price - tp_atr_mult * entry_atr
                        sl_price = entry_price + sl_atr_mult * entry_atr
                        if low[i] <= tp_price or high[i] >= sl_price:
                            exit_price = tp_price if low[i] <= tp_price else sl_price
                            pnl_pct = (entry_price - exit_price) / entry_price
                            won = low[i] <= tp_price
                            bars_held = i - entry_idx
                            all_trades.append({
                                "sym": sym, "direction": -1, "pnl_pct": round(float(pnl_pct), 6),
                                "atr_at_entry": round(float(entry_atr), 8),
                                "entry_price": round(float(entry_price), 8),
                                "won": won, "bars_held": bars_held,
                                "high_excursion": round(float((max(high[entry_idx:i+1]) - entry_price) / entry_price), 6),
                                "low_excursion": round(float((entry_price - min(low[entry_idx:i+1])) / entry_price), 6),
                            })
                            position = 0

        self.trade_pool = all_trades
        logger.info(f"交易池构建完成: {len(all_trades)}笔交易, {len(data_map)}个资产")
        return len(all_trades)

    def _simulate_equity(self, trades, params, num_paths=200, path_length=None):
        if not trades:
            return {"calmar": -999, "sharpe": -999, "avg_return": 0, "avg_dd": 1, "worst_dd": 1, "median_return": 0}

        if path_length is None:
            path_length = min(len(trades), 300)

        kelly = params["kelly_fraction"]
        max_risk = params["max_risk_per_trade"]
        max_pos = params["max_position_pct"]
        dd_trigger = params["drawdown_reduce_trigger"]
        dd_factor = params["drawdown_reduce_factor"]
        ws_boost = params["win_streak_boost"]
        ls_cut = params["loss_streak_cut"]
        max_streak = int(params["max_streak_adjust"])
        daily_limit = params["daily_loss_limit"]
        tp1_pct = params["tp_tier1_pct"]
        tp1_atr = params["tp_tier1_atr"]
        tp2_pct = params["tp_tier2_pct"]
        tp2_atr = params["tp_tier2_atr"]
        pyr_thresh = params["pyramid_threshold_atr"]
        pyr_scale = params["pyramid_scale"]
        max_pyr = int(params["max_pyramids"])

        trade_pnls = np.array([t["pnl_pct"] for t in trades])
        trade_wins = np.array([t["won"] for t in trades])
        trade_highs = np.array([t.get("high_excursion", 0) for t in trades])
        trade_atrs = np.array([t.get("atr_at_entry", 0.01) for t in trades])
        trade_syms = np.array([t.get("sym", "") for t in trades])
        trade_dirs = np.array([t.get("direction", 1) for t in trades])
        n_trades = len(trades)

        corr_cap = params["correlation_cap"]
        max_concurrent = max(2, int(1.0 / (1.0 - corr_cap + 0.01)))

        path_returns = []
        path_drawdowns = []
        path_sharpes = []

        for _ in range(num_paths):
            equity = 10000.0
            peak = 10000.0
            max_dd = 0.0
            consecutive_wins = 0
            consecutive_losses = 0
            daily_pnl = 0.0
            total_exposure = 0.0
            active_syms = set()
            period_returns = []

            indices = np.random.randint(0, n_trades, size=path_length)

            for idx in indices:
                raw_pnl = trade_pnls[idx]
                won = trade_wins[idx]
                high_exc = trade_highs[idx]
                t_atr = trade_atrs[idx]
                t_sym = trade_syms[idx]

                if len(active_syms) >= max_concurrent and t_sym not in active_syms:
                    equity += 0
                    period_returns.append(0)
                    continue

                dd_from_peak = (peak - equity) / peak if peak > 0 else 0
                if dd_from_peak > dd_trigger:
                    risk_scale = dd_factor
                else:
                    risk_scale = 1.0

                streak_scale = 1.0
                if consecutive_wins > 0:
                    streak_scale = min(ws_boost, 1.0 + (consecutive_wins / max_streak) * (ws_boost - 1.0))
                elif consecutive_losses > 0:
                    streak_scale = max(ls_cut, 1.0 - (consecutive_losses / max_streak) * (1.0 - ls_cut))

                pos_size = equity * max_risk * kelly * risk_scale * streak_scale
                remaining_capacity = equity * corr_cap - total_exposure
                if remaining_capacity < pos_size * 0.5:
                    pos_size *= 0.3
                pos_size = min(pos_size, equity * max_pos)
                pos_size = max(pos_size, equity * 0.002)

                if won and high_exc > 0 and t_atr > 0:
                    tier1_exit = tp1_atr * t_atr
                    tier2_exit = tp2_atr * t_atr
                    entry_p = 1.0

                    if high_exc >= tier2_exit / entry_p:
                        actual_pnl = (pos_size * tp1_pct * tp1_atr * t_atr / entry_p +
                                      pos_size * tp2_pct * tp2_atr * t_atr / entry_p +
                                      pos_size * (1 - tp1_pct - tp2_pct) * raw_pnl)
                    elif high_exc >= tier1_exit / entry_p:
                        actual_pnl = (pos_size * tp1_pct * tp1_atr * t_atr / entry_p +
                                      pos_size * (1 - tp1_pct) * raw_pnl)
                    else:
                        actual_pnl = pos_size * raw_pnl

                    if high_exc > pyr_thresh * t_atr and max_pyr > 0:
                        pyramid_pnl = pos_size * pyr_scale * raw_pnl * 0.5
                        actual_pnl += pyramid_pnl
                else:
                    actual_pnl = pos_size * raw_pnl

                daily_pnl += actual_pnl
                if daily_pnl < -(equity * daily_limit):
                    actual_pnl = 0
                    active_syms.clear()
                    total_exposure = 0

                active_syms.add(t_sym)
                total_exposure += pos_size
                if won:
                    total_exposure = max(0, total_exposure - pos_size)
                    active_syms.discard(t_sym)

                equity += actual_pnl
                period_returns.append(actual_pnl / (equity + 1e-10))

                if equity > peak:
                    peak = equity
                dd = (peak - equity) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd

                if won:
                    consecutive_wins += 1
                    consecutive_losses = 0
                else:
                    consecutive_losses += 1
                    consecutive_wins = 0

                if equity <= 5000:
                    break

            total_ret = (equity - 10000) / 10000
            path_returns.append(total_ret)
            path_drawdowns.append(max_dd)
            if len(period_returns) > 1:
                sr = (np.mean(period_returns) / (np.std(period_returns) + 1e-10)) * np.sqrt(252)
                path_sharpes.append(sr)

        avg_ret = np.mean(path_returns)
        median_ret = np.median(path_returns)
        avg_dd = np.mean(path_drawdowns)
        worst_dd = np.percentile(path_drawdowns, 95)
        avg_sharpe = np.mean(path_sharpes) if path_sharpes else 0

        calmar = avg_ret / (worst_dd + 1e-10) if worst_dd > 0.001 else (avg_ret * 50 if avg_ret > 0 else -999)
        if avg_dd > 0.5:
            calmar *= 0.1

        fitness = calmar * 0.4 + avg_sharpe * 0.3 + (1 - worst_dd) * 10 * 0.3
        if worst_dd > 0.15:
            fitness -= (worst_dd - 0.15) * 50
        if median_ret < 0:
            fitness -= abs(median_ret) * 20

        return {
            "calmar": round(calmar, 6),
            "sharpe": round(avg_sharpe, 6),
            "avg_return": round(avg_ret, 6),
            "median_return": round(median_ret, 6),
            "avg_dd": round(avg_dd, 6),
            "worst_dd": round(worst_dd, 6),
            "fitness": round(fitness, 6),
            "paths": num_paths,
        }

    def run_evolution(self, data_map, num_iterations=500, num_paths=300):
        if self.running:
            return {"error": "Monte Carlo引擎正在运行中"}

        self.running = True
        self.progress = 0
        self.progress_msg = "构建交易池..."

        try:
            trade_count = self.build_trade_pool(data_map)
            if trade_count < 20:
                self.running = False
                return {"error": f"交易池不足: 仅{trade_count}笔, 需要至少20笔"}

            self.progress_msg = f"交易池{trade_count}笔, 开始Monte Carlo进化..."

            gen_best_fitness = -999
            gen_best_calmar = -999
            gen_best_sharpe = -999
            gen_best_params = deepcopy(self.best_params)
            improved = False

            for iteration in range(num_iterations):
                candidate = self._mutate_params(self.best_params)
                result = self._simulate_equity(self.trade_pool, candidate, num_paths=num_paths)

                self.total_simulations += num_paths

                if result["fitness"] > gen_best_fitness:
                    gen_best_fitness = result["fitness"]
                    gen_best_calmar = result["calmar"]
                    gen_best_sharpe = result["sharpe"]
                    gen_best_params = deepcopy(candidate)
                    improved = True
                    if iteration % 50 == 0:
                        logger.info(f"[MonteCarlo] 新最佳 fitness={gen_best_fitness:.4f} calmar={gen_best_calmar:.4f} sharpe={gen_best_sharpe:.4f} @ 迭代{iteration+1}")

                self.progress = int((iteration + 1) / num_iterations * 100)
                self.progress_msg = (f"迭代 {iteration+1}/{num_iterations} | "
                                     f"Calmar: {gen_best_calmar:.3f} | "
                                     f"Sharpe: {gen_best_sharpe:.3f} | "
                                     f"95%DD: {result.get('worst_dd', 0):.1%}")

            self.total_generations += 1

            if improved:
                self.best_calmar = gen_best_calmar
                self.best_sharpe = gen_best_sharpe
                self.best_params = gen_best_params
                self.improvement_history.append({
                    "generation": self.total_generations,
                    "calmar": round(gen_best_calmar, 6),
                    "sharpe": round(gen_best_sharpe, 6),
                    "fitness": round(gen_best_fitness, 6),
                    "params": {k: round(v, 6) if isinstance(v, float) else v for k, v in gen_best_params.items()},
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_simulations": self.total_simulations,
                    "trade_pool_size": len(self.trade_pool),
                })

            self._save_state()
            self.progress = 100
            self.progress_msg = "Monte Carlo进化完成"

            return {
                "generation": self.total_generations,
                "iterations": num_iterations,
                "paths_per_iter": num_paths,
                "improved": improved,
                "best_calmar": round(self.best_calmar, 6),
                "best_sharpe": round(self.best_sharpe, 6),
                "best_params": {k: round(v, 6) if isinstance(v, float) else v for k, v in self.best_params.items()},
                "total_simulations": self.total_simulations,
                "trade_pool_size": len(self.trade_pool),
            }
        except Exception as e:
            logger.error(f"Monte Carlo异常: {e}")
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
            "total_simulations": self.total_simulations,
            "total_generations": self.total_generations,
            "best_calmar": round(self.best_calmar, 6),
            "best_sharpe": round(self.best_sharpe, 6),
            "best_params": {k: round(v, 6) if isinstance(v, float) else v for k, v in self.best_params.items()},
            "improvement_count": len(self.improvement_history),
            "last_improvement": self.improvement_history[-1] if self.improvement_history else None,
            "trade_pool_size": len(self.trade_pool),
        }

    def get_param_explanation(self):
        p = self.best_params
        return {
            "kelly_fraction": {"value": p.get("kelly_fraction", 0.5), "desc": "Kelly系数 - 每笔仓位占理论最优的比例"},
            "max_risk_per_trade": {"value": p.get("max_risk_per_trade", 0.02), "desc": "单笔最大风险占总资金比例"},
            "max_position_pct": {"value": p.get("max_position_pct", 0.2), "desc": "单笔最大仓位占总资金比例"},
            "drawdown_reduce_trigger": {"value": p.get("drawdown_reduce_trigger", 0.06), "desc": "回撤触发减仓阈值"},
            "drawdown_reduce_factor": {"value": p.get("drawdown_reduce_factor", 0.5), "desc": "回撤后仓位缩减倍数"},
            "win_streak_boost": {"value": p.get("win_streak_boost", 1.2), "desc": "连胜加码倍数"},
            "loss_streak_cut": {"value": p.get("loss_streak_cut", 0.5), "desc": "连败缩仓倍数"},
            "tp_tier1_pct": {"value": p.get("tp_tier1_pct", 0.3), "desc": "第一档止盈平仓比例"},
            "tp_tier1_atr": {"value": p.get("tp_tier1_atr", 1.0), "desc": "第一档止盈ATR倍数"},
            "tp_tier2_pct": {"value": p.get("tp_tier2_pct", 0.3), "desc": "第二档止盈平仓比例"},
            "tp_tier2_atr": {"value": p.get("tp_tier2_atr", 2.0), "desc": "第二档止盈ATR倍数"},
            "pyramid_threshold_atr": {"value": p.get("pyramid_threshold_atr", 1.5), "desc": "盈利加仓触发ATR倍数"},
            "pyramid_scale": {"value": p.get("pyramid_scale", 0.5), "desc": "加仓规模占原仓位比例"},
            "daily_loss_limit": {"value": p.get("daily_loss_limit", 0.02), "desc": "日亏损限额占总资金比例"},
        }


monte_carlo = TitanMonteCarlo()
