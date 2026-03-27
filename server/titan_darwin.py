import os
import json
import time
import random
import logging
import asyncio
from datetime import datetime
from copy import deepcopy

import numpy as np
import pandas as pd
from deap import base, creator, tools, algorithms

logger = logging.getLogger("TitanDarwin")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVOLVED_CONFIG_PATH = os.path.join(BASE_DIR, "data", "titan_evolved_config.json")
EVOLUTION_LOG_PATH = os.path.join(BASE_DIR, "data", "titan_evolution_log.json")

GENE_BOUNDS = [
    (20, 45),
    (2.0, 6.0),
    (1.0, 3.0),
    (15, 35),
    (10, 60),
    (0.3, 1.0),
    (0.01, 0.05),
    (0.1, 0.4),
]

GENE_NAMES = ["rsi_entry", "tp_atr", "sl_atr", "adx_threshold", "ma_period",
              "kelly_fraction", "max_risk_per_trade", "max_position_pct"]

if not hasattr(creator, "FitnessMax"):
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
if not hasattr(creator, "Individual"):
    creator.create("Individual", list, fitness=creator.FitnessMax)


class TitanDarwinLab:
    def __init__(self):
        self.status = "idle"
        self.progress = 0
        self.progress_msg = ""
        self.running = False
        self.results = None
        self.evolution_log = []
        self._load_results()
        self._load_log()

    def _load_results(self):
        try:
            if os.path.exists(EVOLVED_CONFIG_PATH):
                with open(EVOLVED_CONFIG_PATH, "r") as f:
                    self.results = json.load(f)
                logger.info(f"进化配置已加载: {self.results.get('evolved_at', '未知')}")
        except Exception:
            pass

    def _load_log(self):
        try:
            if os.path.exists(EVOLUTION_LOG_PATH):
                with open(EVOLUTION_LOG_PATH, "r") as f:
                    self.evolution_log = json.load(f)
        except Exception:
            self.evolution_log = []

    def _save_results(self, config):
        try:
            os.makedirs(os.path.dirname(EVOLVED_CONFIG_PATH), exist_ok=True)
            with open(EVOLVED_CONFIG_PATH, "w") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.results = config
        except Exception as e:
            logger.error(f"进化配置保存失败: {e}")

    def _save_log(self):
        try:
            os.makedirs(os.path.dirname(EVOLUTION_LOG_PATH), exist_ok=True)
            with open(EVOLUTION_LOG_PATH, "w") as f:
                json.dump(self.evolution_log[-50:], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"进化日志保存失败: {e}")

    def get_status(self):
        return {
            "status": self.status,
            "progress": self.progress,
            "progress_msg": self.progress_msg,
            "running": self.running,
            "results": self.results,
            "evolution_count": len(self.evolution_log),
            "last_evolution": self.evolution_log[-1] if self.evolution_log else None,
        }

    def get_evolved_params(self):
        if self.results and self.results.get("enabled", False):
            return self.results
        return None

    async def run_evolution(self, exchange, symbols, generations=10, population_size=30, preloaded_data=None):
        if self.running:
            return {"error": "进化正在运行中"}

        self.running = True
        self.status = "running"
        self.progress = 0
        self.progress_msg = "初始化达尔文进化实验室..."

        try:
            result = await self._execute_evolution(exchange, symbols, generations, population_size, preloaded_data=preloaded_data)
            self.status = "completed"
            self.progress = 100
            self.progress_msg = "进化完成"
            return result
        except Exception as e:
            logger.error(f"进化异常: {e}")
            import traceback
            traceback.print_exc()
            self.status = "error"
            self.progress_msg = f"异常: {str(e)[:100]}"
            return {"error": str(e)}
        finally:
            self.running = False

    async def _execute_evolution(self, exchange, symbols, generations, population_size, preloaded_data=None):
        self.progress_msg = f"获取{len(symbols)}个资产历史数据..."
        self.progress = 5

        history_data = {}

        if preloaded_data:
            logger.info(f"[达尔文] 使用预加载本地数据: {len(preloaded_data)}个资产")
            for sym, df_raw in preloaded_data.items():
                try:
                    df = df_raw.copy()
                    if 't' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['t']):
                        df["t"] = pd.to_datetime(df["t"], unit="ms")
                    close = df["c"].values.astype(float)
                    high = df["h"].values.astype(float)
                    low = df["l"].values.astype(float)

                    delta = np.diff(close, prepend=close[0])
                    gain = np.where(delta > 0, delta, 0)
                    loss = np.where(delta < 0, -delta, 0)
                    avg_gain = pd.Series(gain).rolling(14).mean().values
                    avg_loss = pd.Series(loss).rolling(14).mean().values
                    rs = avg_gain / (avg_loss + 1e-10)
                    df["rsi"] = 100 - (100 / (1 + rs))

                    tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
                    df["atr"] = pd.Series(tr).rolling(14).mean().values

                    plus_dm = np.where((high - np.roll(high, 1)) > (np.roll(low, 1) - low), np.maximum(high - np.roll(high, 1), 0), 0)
                    minus_dm = np.where((np.roll(low, 1) - low) > (high - np.roll(high, 1)), np.maximum(np.roll(low, 1) - low, 0), 0)
                    atr14 = pd.Series(tr).rolling(14).mean().values + 1e-10
                    plus_di = 100 * pd.Series(plus_dm).rolling(14).mean().values / atr14
                    minus_di = 100 * pd.Series(minus_dm).rolling(14).mean().values / atr14
                    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
                    df["adx"] = pd.Series(dx).rolling(14).mean().values

                    df["ma20"] = pd.Series(close).rolling(20).mean().values
                    df["ma50"] = pd.Series(close).rolling(50).mean().values

                    df = df.dropna().reset_index(drop=True)
                    if len(df) >= 200:
                        history_data[sym] = df
                except Exception as e:
                    logger.warning(f"[达尔文] 本地数据处理{sym}失败: {e}")
            self.progress = 20
            self.progress_msg = f"本地数据加载完成: {len(history_data)}个资产"
        else:
            for i, sym in enumerate(symbols[:15]):
                try:
                    ohlcv = await exchange.fetch_ohlcv(f"{sym}/USDT", "1h", limit=1000)
                    if len(ohlcv) < 200:
                        continue
                    df = pd.DataFrame(ohlcv, columns=["t", "o", "h", "l", "c", "v"])
                    df["t"] = pd.to_datetime(df["t"], unit="ms")

                    close = df["c"].values
                    high = df["h"].values
                    low = df["l"].values

                    delta = np.diff(close, prepend=close[0])
                    gain = np.where(delta > 0, delta, 0)
                    loss = np.where(delta < 0, -delta, 0)
                    avg_gain = pd.Series(gain).rolling(14).mean().values
                    avg_loss = pd.Series(loss).rolling(14).mean().values
                    rs = avg_gain / (avg_loss + 1e-10)
                    df["rsi"] = 100 - (100 / (1 + rs))

                    tr = np.maximum(high - low, np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
                    df["atr"] = pd.Series(tr).rolling(14).mean().values

                    plus_dm = np.where((high - np.roll(high, 1)) > (np.roll(low, 1) - low), np.maximum(high - np.roll(high, 1), 0), 0)
                    minus_dm = np.where((np.roll(low, 1) - low) > (high - np.roll(high, 1)), np.maximum(np.roll(low, 1) - low, 0), 0)
                    atr14 = pd.Series(tr).rolling(14).mean().values + 1e-10
                    plus_di = 100 * pd.Series(plus_dm).rolling(14).mean().values / atr14
                    minus_di = 100 * pd.Series(minus_dm).rolling(14).mean().values / atr14
                    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
                    df["adx"] = pd.Series(dx).rolling(14).mean().values

                    df["ma20"] = pd.Series(close).rolling(20).mean().values
                    df["ma50"] = pd.Series(close).rolling(50).mean().values

                    df = df.dropna().reset_index(drop=True)
                    if len(df) >= 200:
                        history_data[sym] = df

                    self.progress_msg = f"获取数据: {sym} ({i+1}/{min(len(symbols), 15)})"
                    self.progress = 5 + int(15 * (i + 1) / min(len(symbols), 15))
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"进化获取{sym}失败: {e}")
                    continue

        if len(history_data) < 3:
            return {"error": f"数据不足: 仅获取{len(history_data)}个资产"}

        self.progress = 20
        self.progress_msg = f"数据就绪({len(history_data)}资产)，启动遗传算法..."

        toolbox = base.Toolbox()
        toolbox.register("attr_rsi", random.randint, GENE_BOUNDS[0][0], GENE_BOUNDS[0][1])
        toolbox.register("attr_tp", random.uniform, GENE_BOUNDS[1][0], GENE_BOUNDS[1][1])
        toolbox.register("attr_sl", random.uniform, GENE_BOUNDS[2][0], GENE_BOUNDS[2][1])
        toolbox.register("attr_adx", random.randint, GENE_BOUNDS[3][0], GENE_BOUNDS[3][1])
        toolbox.register("attr_ma", random.randint, GENE_BOUNDS[4][0], GENE_BOUNDS[4][1])
        toolbox.register("attr_kelly", random.uniform, GENE_BOUNDS[5][0], GENE_BOUNDS[5][1])
        toolbox.register("attr_risk", random.uniform, GENE_BOUNDS[6][0], GENE_BOUNDS[6][1])
        toolbox.register("attr_pos", random.uniform, GENE_BOUNDS[7][0], GENE_BOUNDS[7][1])

        toolbox.register("individual", tools.initCycle, creator.Individual,
                         (toolbox.attr_rsi, toolbox.attr_tp,
                          toolbox.attr_sl, toolbox.attr_adx,
                          toolbox.attr_ma, toolbox.attr_kelly,
                          toolbox.attr_risk, toolbox.attr_pos), n=1)
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)

        def evaluate(individual):
            return self._backtest_strategy(individual, history_data)

        toolbox.register("evaluate", evaluate)
        toolbox.register("mate", tools.cxBlend, alpha=0.3)
        toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=[3, 0.5, 0.3, 3, 5, 0.1, 0.005, 0.05], indpb=0.3)
        toolbox.register("select", tools.selTournament, tournsize=3)

        pop = toolbox.population(n=population_size)
        hof = tools.HallOfFame(3)

        gen_stats = []
        for gen in range(generations):
            offspring = algorithms.varAnd(pop, toolbox, cxpb=0.5, mutpb=0.3)

            for ind in offspring:
                ind[0] = max(GENE_BOUNDS[0][0], min(GENE_BOUNDS[0][1], int(round(ind[0]))))
                ind[1] = max(GENE_BOUNDS[1][0], min(GENE_BOUNDS[1][1], round(ind[1], 2)))
                ind[2] = max(GENE_BOUNDS[2][0], min(GENE_BOUNDS[2][1], round(ind[2], 2)))
                ind[3] = max(GENE_BOUNDS[3][0], min(GENE_BOUNDS[3][1], int(round(ind[3]))))
                ind[4] = max(GENE_BOUNDS[4][0], min(GENE_BOUNDS[4][1], int(round(ind[4]))))
                ind[5] = max(GENE_BOUNDS[5][0], min(GENE_BOUNDS[5][1], round(ind[5], 3)))
                ind[6] = max(GENE_BOUNDS[6][0], min(GENE_BOUNDS[6][1], round(ind[6], 4)))
                ind[7] = max(GENE_BOUNDS[7][0], min(GENE_BOUNDS[7][1], round(ind[7], 3)))

            fitnesses = list(map(toolbox.evaluate, offspring))
            for ind, fit in zip(offspring, fitnesses):
                ind.fitness.values = fit

            pop = toolbox.select(offspring, k=population_size)
            hof.update(pop)

            fits = [ind.fitness.values[0] for ind in pop]
            avg_fit = np.mean(fits)
            max_fit = np.max(fits)
            min_fit = np.min(fits)

            gen_stats.append({
                "gen": gen + 1,
                "avg": round(float(avg_fit), 2),
                "max": round(float(max_fit), 2),
                "min": round(float(min_fit), 2),
                "best": [round(float(g), 2) for g in hof[0]],
            })

            pct = 20 + int(70 * (gen + 1) / generations)
            self.progress = min(pct, 95)
            self.progress_msg = f"进化第{gen+1}/{generations}代 | 最强适应度: {max_fit:.1f} | 平均: {avg_fit:.1f}"
            await asyncio.sleep(0.01)
            logger.info(f"[DARWIN] Gen {gen+1}: avg={avg_fit:.1f}, max={max_fit:.1f}, best={[round(g,1) for g in hof[0]]}")

        best = hof[0]
        config = {
            "rsi_entry": int(round(best[0])),
            "tp_atr": round(float(best[1]), 2),
            "sl_atr": round(float(best[2]), 2),
            "adx_threshold": int(round(best[3])),
            "ma_period": int(round(best[4])),
            "kelly_fraction": round(float(best[5]), 3),
            "max_risk_per_trade": round(float(best[6]), 4),
            "max_position_pct": round(float(best[7]), 3),
            "fitness": round(float(best.fitness.values[0]), 2),
            "evolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "generations": generations,
            "population_size": population_size,
            "assets_used": len(history_data),
            "enabled": True,
        }

        top3 = []
        for i, ind in enumerate(hof):
            top3.append({
                "rank": i + 1,
                "params": {GENE_NAMES[j]: round(float(ind[j]), 2) for j in range(len(GENE_NAMES))},
                "fitness": round(float(ind.fitness.values[0]), 2),
            })

        self._save_results(config)

        log_entry = {
            "timestamp": config["evolved_at"],
            "best_fitness": config["fitness"],
            "best_params": {k: config[k] for k in GENE_NAMES},
            "gen_stats_summary": {
                "first_gen_avg": gen_stats[0]["avg"] if gen_stats else 0,
                "last_gen_avg": gen_stats[-1]["avg"] if gen_stats else 0,
                "improvement": round(gen_stats[-1]["avg"] - gen_stats[0]["avg"], 2) if gen_stats else 0,
            }
        }
        self.evolution_log.append(log_entry)
        self._save_log()

        self.progress = 100
        return {
            "best_config": config,
            "top3": top3,
            "gen_stats": gen_stats,
            "assets_used": list(history_data.keys()),
        }

    def _backtest_strategy(self, individual, history_data):
        rsi_limit = max(20, min(50, int(round(individual[0]))))
        tp_mult = max(1.5, min(8.0, individual[1]))
        sl_mult = max(0.5, min(4.0, individual[2]))
        adx_limit = max(10, min(40, int(round(individual[3]))))
        ma_period = max(5, min(100, int(round(individual[4]))))
        kelly_frac = max(0.1, min(1.0, individual[5]))
        max_risk = max(0.005, min(0.1, individual[6]))
        max_pos_pct = max(0.05, min(0.5, individual[7]))

        starting_equity = 10000.0
        equity = starting_equity
        total_trades = 0
        total_wins = 0
        max_drawdown = 0
        peak_equity = starting_equity
        trade_returns = []

        for sym, df in history_data.items():
            if len(df) < ma_period + 50:
                continue

            close = df["c"].values
            rsi = df["rsi"].values
            atr = df["atr"].values
            adx = df["adx"].values

            if f"ma{ma_period}" in df.columns:
                ma = df[f"ma{ma_period}"].values
            else:
                ma = pd.Series(close).rolling(ma_period).mean().values

            position = 0
            entry_price = 0
            entry_atr = 0
            position_size = 0

            for i in range(ma_period + 14, len(df) - 1):
                if np.isnan(rsi[i]) or np.isnan(adx[i]) or np.isnan(atr[i]) or np.isnan(ma[i]):
                    continue

                if position == 0:
                    if rsi[i] < rsi_limit and adx[i] > adx_limit and close[i] > ma[i]:
                        position = 1
                        entry_price = close[i]
                        entry_atr = atr[i]
                        total_trades += 1

                        sl_distance = sl_mult * entry_atr
                        if sl_distance > 0 and entry_price > 0:
                            risk_amount = equity * max_risk
                            position_size = min(risk_amount / (sl_distance / entry_price), equity * max_pos_pct)
                            position_size *= kelly_frac
                        else:
                            position_size = equity * 0.01
                elif position == 1:
                    tp_price = entry_price + tp_mult * entry_atr
                    sl_price = entry_price - sl_mult * entry_atr

                    if close[i] >= tp_price:
                        pnl = position_size * (tp_price - entry_price) / entry_price
                        equity += pnl
                        trade_returns.append(pnl)
                        total_wins += 1
                        position = 0
                    elif close[i] <= sl_price:
                        pnl = position_size * (sl_price - entry_price) / entry_price
                        equity += pnl
                        trade_returns.append(pnl)
                        position = 0

                    if equity > peak_equity:
                        peak_equity = equity
                    dd = (peak_equity - equity) / peak_equity if peak_equity > 0 else 0
                    if dd > max_drawdown:
                        max_drawdown = dd

        if total_trades < 5:
            return (-200.0,)

        win_rate = total_wins / total_trades if total_trades > 0 else 0
        total_return = (equity - starting_equity) / starting_equity

        dd_penalty = max_drawdown * 200.0
        if max_drawdown > 0.3:
            dd_penalty += (max_drawdown - 0.3) * 500.0
        trade_penalty = 0 if total_trades >= 20 else (20 - total_trades) * 2

        fitness = total_return * 100 - dd_penalty - trade_penalty

        if equity > starting_equity:
            fitness += 30

        if len(trade_returns) > 1:
            avg_ret = np.mean(trade_returns)
            std_ret = np.std(trade_returns)
            if std_ret > 0:
                sharpe_like = avg_ret / std_ret
                fitness += sharpe_like * 20

        if win_rate > 0.55:
            fitness += 50
        elif win_rate < 0.35:
            fitness -= 50

        if sl_mult > 3.0:
            fitness -= 100

        tp_sl_ratio = tp_mult / max(sl_mult, 0.01)
        if tp_sl_ratio < 1.5:
            fitness -= 150
        elif tp_sl_ratio < 2.0:
            fitness -= 80 * (2.0 - tp_sl_ratio)

        if sl_mult < 1.5:
            fitness -= 60 * (1.5 - sl_mult)

        return (round(fitness, 2),)


darwin_lab = TitanDarwinLab()
