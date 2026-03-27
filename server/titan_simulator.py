import os
import json
import time
import logging
import asyncio
from datetime import datetime
from copy import deepcopy

import numpy as np
import pandas as pd

logger = logging.getLogger("TitanSimulator")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM_RESULTS_PATH = os.path.join(BASE_DIR, "data", "titan_sim_results.json")


class EvolutionarySimulator:
    def __init__(self):
        self.status = "idle"
        self.progress = 0
        self.progress_msg = ""
        self.results = None
        self.running = False
        self._load_results()

    def _load_results(self):
        try:
            if os.path.exists(SIM_RESULTS_PATH):
                with open(SIM_RESULTS_PATH, "r") as f:
                    self.results = json.load(f)
                logger.info(f"模拟结果已加载: {self.results.get('completed_at', '未知')}")
        except Exception:
            pass

    def _save_results(self):
        try:
            os.makedirs(os.path.dirname(SIM_RESULTS_PATH), exist_ok=True)
            with open(SIM_RESULTS_PATH, "w") as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"模拟结果保存失败: {e}")

    async def run_simulation(self, exchange, symbols, years=1.0, initial_capital=10000.0, retrain_interval_bars=60, deadline_seconds=840, preloaded_data=None):
        if self.running:
            return {"error": "模拟正在运行中"}

        self.running = True
        self.status = "running"
        self.progress = 0
        self.progress_msg = "初始化..."
        import time as _time
        self._deadline = _time.time() + deadline_seconds

        try:
            result = await self._execute_walkforward(
                exchange, symbols, years, initial_capital, retrain_interval_bars, preloaded_data=preloaded_data
            )
            self.results = result
            self._save_results()
            self.status = "completed"
            self.progress = 100
            self.progress_msg = "模拟完成"
            return result
        except Exception as e:
            logger.error(f"模拟异常: {e}")
            import traceback
            traceback.print_exc()
            self.status = "error"
            self.progress_msg = f"异常: {str(e)[:100]}"
            return {"error": str(e)}
        finally:
            self.running = False

    async def _execute_walkforward(self, exchange, symbols, years, initial_capital, retrain_interval_bars, preloaded_data=None):
        from server.titan_ml import TitanMLEngine
        from server.titan_agent import StrategyGovernor, FeedbackEngine, AgentMemory

        sim_ml = TitanMLEngine()
        sim_memory = AgentMemory()
        sim_memory.session_count = 0
        sim_memory.critic_history = []
        sim_memory.critic_ban_rules = []
        sim_governor = StrategyGovernor()
        sim_governor.state["peak_equity"] = initial_capital
        sim_governor.state["current_equity"] = initial_capital
        sim_governor.config["score_threshold_normal"] = 60
        sim_governor.config["score_threshold_cautious"] = 65
        sim_governor.config["score_threshold_aggressive"] = 55
        sim_feedback = FeedbackEngine(sim_memory)

        GATE_MAX_CANDLES = 9500
        if years > 1.0:
            sim_timeframe = "4h"
            bars_per_day = 6
            bars_per_year = 365 * 6
        else:
            sim_timeframe = "1h"
            bars_per_day = 24
            bars_per_year = 365 * 24

        total_bars = min(int(bars_per_year * years), GATE_MAX_CANDLES)
        secondary_tf = "1d" if sim_timeframe == "4h" else "4h"
        secondary_bars = min(total_bars // 4, GATE_MAX_CANDLES)

        self.progress_msg = f"获取{len(symbols)}个资产历史数据 ({years}年, {sim_timeframe}周期, ~{total_bars}根K线)..."
        self.progress = 2
        logger.info(f"[模拟] 开始获取数据: {years}年, 主周期={sim_timeframe}, 目标K线={total_bars}")

        history_data = {}
        max_assets = min(len(symbols), 20)
        target_symbols = symbols[:max_assets]

        if preloaded_data:
            logger.info(f"[模拟] 使用预加载本地数据: {len(preloaded_data)}个资产")
            detected_tf = None
            for sym in target_symbols:
                if sym in preloaded_data:
                    try:
                        df_raw = preloaded_data[sym].copy()
                        for col in ['o','h','l','c','v']:
                            df_raw[col] = df_raw[col].astype(float)
                        if 't' in df_raw.columns and not pd.api.types.is_datetime64_any_dtype(df_raw['t']):
                            df_raw["t"] = pd.to_datetime(df_raw["t"], unit="ms")
                        df_raw = df_raw.drop_duplicates(subset=["t"]).sort_values("t").reset_index(drop=True)

                        if detected_tf is None and len(df_raw) >= 10:
                            time_diffs = df_raw['t'].diff().dropna()
                            median_hours = time_diffs.median().total_seconds() / 3600
                            if median_hours >= 3.0:
                                detected_tf = "4h"
                                sim_timeframe = "4h"
                                bars_per_day = 6
                                bars_per_year = 365 * 6
                                logger.info(f"[模拟] 检测到预加载数据为4H周期 (中位间隔={median_hours:.1f}h), 调整模拟参数")
                            else:
                                detected_tf = "1h"

                        if len(df_raw) >= 50:
                            if detected_tf == "4h":
                                df_daily = df_raw.set_index('t').resample('1D').agg({'o':'first','h':'max','l':'min','c':'last','v':'sum'}).dropna().reset_index()
                                history_data[sym] = {"1h": df_raw, "4h": df_daily if len(df_daily) > 10 else df_raw}
                            else:
                                df_sec = df_raw.iloc[::4].reset_index(drop=True)
                                history_data[sym] = {"1h": df_raw, "4h": df_sec}
                    except Exception as e:
                        logger.warning(f"[模拟] 本地数据处理{sym}失败: {e}")
            self.progress = 20
            self.progress_msg = f"本地数据加载完成: {len(history_data)}个资产 (周期={detected_tf or sim_timeframe})"
        else:
            for i, sym in enumerate(target_symbols):
                try:
                    ohlcv_main = await self._fetch_ohlcv_paginated(
                        exchange, f"{sym}/USDT", sim_timeframe, total_bars
                    )
                    if len(ohlcv_main) < 200:
                        logger.warning(f"[模拟] {sym} 数据不足: 仅{len(ohlcv_main)}根")
                        continue
                    df_main = pd.DataFrame(ohlcv_main, columns=["t", "o", "h", "l", "c", "v"])
                    df_main["t"] = pd.to_datetime(df_main["t"], unit="ms")
                    df_main = df_main.drop_duplicates(subset=["t"]).sort_values("t").reset_index(drop=True)

                    ohlcv_sec = await self._fetch_ohlcv_paginated(
                        exchange, f"{sym}/USDT", secondary_tf, secondary_bars
                    )
                    df_sec = pd.DataFrame(ohlcv_sec, columns=["t", "o", "h", "l", "c", "v"]) if len(ohlcv_sec) > 50 else None
                    if df_sec is not None:
                        df_sec["t"] = pd.to_datetime(df_sec["t"], unit="ms")
                        df_sec = df_sec.drop_duplicates(subset=["t"]).sort_values("t").reset_index(drop=True)

                    history_data[sym] = {"1h": df_main, "4h": df_sec if df_sec is not None else df_main.iloc[::4].reset_index(drop=True)}
                    actual_days = len(df_main) / bars_per_day
                    self.progress_msg = f"获取数据: {sym} ({i+1}/{max_assets}) - {len(df_main)}根{sim_timeframe}K线 ({actual_days:.0f}天)"
                    self.progress = 2 + int(18 * (i + 1) / max_assets)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"模拟获取{sym}失败: {e}")
                    continue

        if len(history_data) < 3:
            return {"error": f"数据不足: 仅获取{len(history_data)}个资产"}

        self.progress = 20
        actual_bars = {sym: len(d["1h"]) for sym, d in history_data.items()}
        total_fetched = sum(actual_bars.values())
        avg_bars = total_fetched // len(history_data) if history_data else 0
        self.progress_msg = f"数据准备完成: {len(history_data)}个资产, 平均{avg_bars}根K线 ({avg_bars/24:.0f}天)，开始Walk-Forward模拟..."

        capital = initial_capital
        equity_curve = []
        all_trades = []
        open_positions = {}
        peak = capital
        max_drawdown = 0
        evolution_log = []
        retrain_count = 0
        phase_metrics = []

        min_len = min(len(d["1h"]) for d in history_data.values())
        warmup = 200
        sim_start = warmup
        sim_end = min_len

        if sim_end - sim_start < 100:
            return {"error": f"数据不足: 仅{sim_end - sim_start}根可用K线"}

        total_sim_bars = sim_end - sim_start
        phase_size = max(retrain_interval_bars, 60)
        phase_start_capital = capital
        phase_trades = []

        import time as _time
        for bar_idx in range(sim_start, sim_end):
            bar_progress = bar_idx - sim_start
            if bar_progress % 50 == 0:
                pct = 20 + int(70 * bar_progress / total_sim_bars)
                self.progress = min(pct, 95)
                self.progress_msg = f"模拟进度: {bar_progress}/{total_sim_bars} bars | 资金: ${capital:.0f} | 交易: {len(all_trades)}笔"
                await asyncio.sleep(0.01)
                if hasattr(self, '_deadline') and _time.time() > self._deadline:
                    logger.warning(f"[模拟] 内部截止时间到达, bar={bar_progress}/{total_sim_bars}, 提前结束")
                    self.progress_msg = f"模拟截止: {bar_progress}/{total_sim_bars} bars已完成"
                    break

            if (bar_progress > 0 and bar_progress % retrain_interval_bars == 0):
                if hasattr(self, '_deadline') and _time.time() > self._deadline:
                    logger.warning(f"[模拟] 截止时间到达(训练前), bar={bar_progress}, 跳过后续")
                    break
                train_data = {}
                for sym, data in history_data.items():
                    train_end = bar_idx
                    train_start = max(0, train_end - 800)
                    df_1h_slice = data["1h"].iloc[train_start:train_end].copy()
                    df_4h = data.get("4h")
                    if df_4h is not None:
                        t_start = df_1h_slice["t"].iloc[0] if len(df_1h_slice) > 0 else None
                        if t_start is not None:
                            df_4h_slice = df_4h[df_4h["t"] >= t_start].copy()
                        else:
                            df_4h_slice = df_4h.iloc[:train_end//4].copy()
                    else:
                        df_4h_slice = pd.DataFrame()

                    if len(df_1h_slice) >= 100:
                        train_data[sym] = {"1h": df_1h_slice, "4h": df_4h_slice if len(df_4h_slice) > 20 else df_1h_slice.iloc[::4]}

                if train_data and len(train_data) >= 3:
                    try:
                        loop = asyncio.get_event_loop()
                        success = await loop.run_in_executor(None, sim_ml.train, train_data)
                        if success:
                            retrain_count += 1
                            acc = sim_ml.metrics.get("accuracy", 0)
                            f1 = sim_ml.metrics.get("f1", 0)

                            phase_wins = sum(1 for t in phase_trades if t["result"] == "win")
                            phase_total = len(phase_trades)
                            phase_return = (capital - phase_start_capital) / phase_start_capital * 100 if phase_start_capital > 0 else 0

                            phase_record = {
                                "retrain": retrain_count,
                                "bar": bar_progress,
                                "ml_accuracy": acc,
                                "ml_f1": f1,
                                "phase_trades": phase_total,
                                "phase_win_rate": round(phase_wins / phase_total * 100, 1) if phase_total > 0 else 0,
                                "phase_return": round(phase_return, 2),
                                "capital": round(capital, 2),
                                "samples": sim_ml.metrics.get("samples_trained", 0),
                            }
                            phase_metrics.append(phase_record)
                            evolution_log.append(f"[重训练#{retrain_count}] bar={bar_progress} 准确率={acc}% F1={f1}% 阶段收益={phase_return:.1f}%")

                            sim_feedback.auto_adjust_critic(sim_ml.critic if hasattr(sim_ml, 'critic') else type('', (), {'ban_rules': []})())

                            phase_start_capital = capital
                            phase_trades = []
                    except Exception as e:
                        logger.warning(f"模拟重训练失败 bar={bar_progress}: {e}")

            gov_params = sim_governor.get_trading_params()

            closed_syms = []
            for sym, pos in list(open_positions.items()):
                if sym not in history_data:
                    continue
                df = history_data[sym]["1h"]
                if bar_idx >= len(df):
                    continue

                price = df["c"].iloc[bar_idx]
                high = df["h"].iloc[bar_idx]
                low = df["l"].iloc[bar_idx]
                direction = pos.get("direction", "long")

                if direction == "long":
                    if high >= pos["tp"]:
                        pnl = (pos["tp"] - pos["entry"]) / pos["entry"] * pos["size"]
                        capital += pos["size"] + pnl
                        trade = {"sym": sym, "direction": "long", "entry": pos["entry"], "exit": pos["tp"],
                                 "pnl": round(pnl, 2), "result": "win", "bar": bar_progress}
                        all_trades.append(trade)
                        phase_trades.append(trade)
                        closed_syms.append(sym)
                        sim_governor.record_trade_result(True)
                    elif low <= pos["sl"]:
                        pnl = (pos["sl"] - pos["entry"]) / pos["entry"] * pos["size"]
                        capital += pos["size"] + pnl
                        result = "win" if pnl >= 0 else "loss"
                        trade = {"sym": sym, "direction": "long", "entry": pos["entry"], "exit": pos["sl"],
                                 "pnl": round(pnl, 2), "result": result, "bar": bar_progress}
                        all_trades.append(trade)
                        phase_trades.append(trade)
                        closed_syms.append(sym)
                        sim_governor.record_trade_result(pnl >= 0)
                    else:
                        profit_pct = (high - pos["entry"]) / pos["entry"]
                        atr_pct = pos["atr"] / pos["entry"] if pos["entry"] > 0 else 0.02
                        if profit_pct >= atr_pct * 3:
                            new_sl = high - pos["atr"] * 2.0
                            if new_sl > pos["sl"]:
                                pos["sl"] = new_sl
                        elif profit_pct >= atr_pct * 1.5:
                            be_sl = pos["entry"] * 1.003
                            if be_sl > pos["sl"]:
                                pos["sl"] = be_sl
                else:
                    if low <= pos["tp"]:
                        pnl = (pos["entry"] - pos["tp"]) / pos["entry"] * pos["size"]
                        capital += pos["size"] + pnl
                        trade = {"sym": sym, "direction": "short", "entry": pos["entry"], "exit": pos["tp"],
                                 "pnl": round(pnl, 2), "result": "win", "bar": bar_progress}
                        all_trades.append(trade)
                        phase_trades.append(trade)
                        closed_syms.append(sym)
                        sim_governor.record_trade_result(True)
                    elif high >= pos["sl"]:
                        pnl = (pos["entry"] - pos["sl"]) / pos["entry"] * pos["size"]
                        capital += pos["size"] + pnl
                        result = "win" if pnl >= 0 else "loss"
                        trade = {"sym": sym, "direction": "short", "entry": pos["entry"], "exit": pos["sl"],
                                 "pnl": round(pnl, 2), "result": result, "bar": bar_progress}
                        all_trades.append(trade)
                        phase_trades.append(trade)
                        closed_syms.append(sym)
                        sim_governor.record_trade_result(pnl >= 0)
                    else:
                        profit_pct = (pos["entry"] - low) / pos["entry"]
                        atr_pct = pos["atr"] / pos["entry"] if pos["entry"] > 0 else 0.02
                        if profit_pct >= atr_pct * 3:
                            new_sl = low + pos["atr"] * 2.0
                            if new_sl < pos["sl"]:
                                pos["sl"] = new_sl
                        elif profit_pct >= atr_pct * 1.5:
                            be_sl = pos["entry"] * 0.997
                            if be_sl < pos["sl"]:
                                pos["sl"] = be_sl

            for sym in closed_syms:
                del open_positions[sym]

            max_pos = gov_params.get("max_positions", 5)
            score_threshold = gov_params.get("score_threshold", 80)
            size_factor = gov_params.get("position_size_factor", 1.0)

            if gov_params.get("allow_new_trades", True) and len(open_positions) < max_pos and capital > 100:
                candidates = []
                for sym, data in history_data.items():
                    if sym in open_positions:
                        continue
                    df_1h = data["1h"]
                    if bar_idx >= len(df_1h) or bar_idx < 50:
                        continue

                    price = df_1h["c"].iloc[bar_idx]
                    signal = self._generate_ml_signal(sim_ml, data, bar_idx)
                    if signal and signal["score"] >= score_threshold:
                        signal["sym"] = sym
                        candidates.append(signal)

                candidates.sort(key=lambda x: -x["score"])

                for sig in candidates[:max(1, max_pos - len(open_positions))]:
                    pos_size = capital * 0.08 * size_factor
                    pos_size = min(pos_size, capital * 0.25)
                    if pos_size < 10 or pos_size > capital:
                        continue

                    price = sig["price"]
                    atr = sig["atr"]
                    direction = sig.get("direction", "long")

                    if direction == "long":
                        sl = price - atr * 2.0
                        tp = price + atr * 2.0
                    else:
                        sl = price + atr * 2.0
                        tp = price - atr * 2.0

                    capital -= pos_size
                    open_positions[sym] = {
                        "entry": price, "tp": tp, "sl": sl,
                        "size": pos_size, "atr": atr,
                        "direction": direction,
                    }

            unrealized = 0
            for sym, pos in open_positions.items():
                if sym in history_data:
                    df = history_data[sym]["1h"]
                    if bar_idx < len(df):
                        cur_price = df["c"].iloc[bar_idx]
                        if pos.get("direction", "long") == "long":
                            unrealized += (cur_price - pos["entry"]) / pos["entry"] * pos["size"]
                        else:
                            unrealized += (pos["entry"] - cur_price) / pos["entry"] * pos["size"]

            total_equity = capital + sum(p["size"] for p in open_positions.values()) + unrealized
            sim_governor.update_equity(total_equity)

            if total_equity > peak:
                peak = total_equity
            dd = (peak - total_equity) / peak * 100 if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

            if bar_progress % 24 == 0:
                ref_df = list(history_data.values())[0]["1h"]
                ts = str(ref_df["t"].iloc[bar_idx]) if bar_idx < len(ref_df) else f"bar_{bar_progress}"
                equity_curve.append({
                    "bar": bar_progress,
                    "time": ts,
                    "equity": round(total_equity, 2),
                    "drawdown": round(dd, 2),
                })

        final_equity = capital + sum(p["size"] for p in open_positions.values())
        total_trades = len(all_trades)
        wins = sum(1 for t in all_trades if t["result"] == "win")
        losses = total_trades - wins
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        avg_win = 0
        avg_loss = 0
        if wins > 0:
            avg_win = sum(t["pnl"] for t in all_trades if t["result"] == "win") / wins
        if losses > 0:
            avg_loss = abs(sum(t["pnl"] for t in all_trades if t["result"] == "loss") / losses)

        profit_factor = (avg_win * wins) / (avg_loss * losses + 1e-10) if losses > 0 else 999

        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)
        sharpe = 0
        if returns and len(returns) > 1:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = round((avg_ret / std_ret) * np.sqrt(365), 2)

        evolution_improved = False
        if len(phase_metrics) >= 3:
            early = phase_metrics[:len(phase_metrics)//3]
            late = phase_metrics[-len(phase_metrics)//3:]
            early_wr = np.mean([p["phase_win_rate"] for p in early]) if early else 0
            late_wr = np.mean([p["phase_win_rate"] for p in late]) if late else 0
            early_acc = np.mean([p["ml_accuracy"] for p in early]) if early else 0
            late_acc = np.mean([p["ml_accuracy"] for p in late]) if late else 0
            evolution_improved = late_wr > early_wr or late_acc > early_acc

        result = {
            "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "years": years,
                "initial_capital": initial_capital,
                "symbols": list(history_data.keys()),
                "symbol_count": len(history_data),
                "total_bars": total_sim_bars,
                "retrain_interval": retrain_interval_bars,
            },
            "performance": {
                "final_equity": round(final_equity, 2),
                "total_return_pct": round((final_equity - initial_capital) / initial_capital * 100, 2),
                "total_pnl": round(final_equity - initial_capital, 2),
                "max_drawdown_pct": round(max_drawdown, 2),
                "win_rate": round(win_rate, 1),
                "total_trades": total_trades,
                "wins": wins,
                "losses": losses,
                "profit_factor": round(profit_factor, 2) if profit_factor < 999 else 999,
                "sharpe_ratio": sharpe,
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
            },
            "evolution": {
                "retrain_count": retrain_count,
                "phases": phase_metrics,
                "improved_over_time": evolution_improved,
                "evolution_log": evolution_log[-50:],
            },
            "equity_curve": equity_curve[-1000:],
            "recent_trades": all_trades[-100:],
            "governor_final": sim_governor.get_status(),
        }
        return result

    async def _fetch_ohlcv_paginated(self, exchange, symbol, timeframe, target_bars, page_size=1000):
        all_data = []
        tf_ms = {"1h": 3600000, "4h": 14400000, "1d": 86400000}
        interval_ms = tf_ms.get(timeframe, 3600000)

        now_ms = int(time.time() * 1000)
        since_ms = now_ms - (target_bars * interval_ms)

        current_since = since_ms
        max_pages = (target_bars // page_size) + 2
        page = 0

        while page < max_pages:
            try:
                batch = await exchange.fetch_ohlcv(
                    symbol, timeframe, since=current_since, limit=page_size
                )
                if not batch:
                    break

                all_data.extend(batch)

                last_ts = batch[-1][0]
                if last_ts >= now_ms - interval_ms:
                    break

                current_since = last_ts + interval_ms
                page += 1
                await asyncio.sleep(0.15)
            except Exception as e:
                logger.warning(f"分页获取{symbol} {timeframe} page={page}失败: {e}")
                if page == 0:
                    raise
                break

        seen = set()
        unique_data = []
        for row in all_data:
            if row[0] not in seen:
                seen.add(row[0])
                unique_data.append(row)

        unique_data.sort(key=lambda x: x[0])
        logger.info(f"分页获取 {symbol} {timeframe}: {len(unique_data)}根K线 ({len(unique_data)/24:.0f}天) [{page+1}页]")
        return unique_data

    def _generate_ml_signal(self, ml_engine, data, bar_idx):
        df_1h = data["1h"]
        df_4h = data.get("4h")

        if bar_idx >= len(df_1h) or bar_idx < 50:
            return None

        price = df_1h["c"].iloc[bar_idx]

        try:
            atr_vals = self._calc_atr(df_1h, bar_idx)
            rsi_val = self._calc_rsi(df_1h["c"], bar_idx)
            ma20 = df_1h["c"].iloc[max(0, bar_idx-19):bar_idx+1].mean()
            ma50 = df_1h["c"].iloc[max(0, bar_idx-49):bar_idx+1].mean()

            if pd.isna(atr_vals) or pd.isna(rsi_val):
                return None

            adx_val = self._calc_simple_adx(df_1h, bar_idx)

            direction = "long"
            score = 50

            if ma20 > ma50:
                score += 10
                if price > ma20:
                    score += 5
                if rsi_val < 50 and rsi_val > 30:
                    score += 8
                if adx_val > 25:
                    score += 8
                elif adx_val > 20:
                    score += 4

                vol_ratio = df_1h["v"].iloc[bar_idx] / (df_1h["v"].iloc[max(0, bar_idx-20):bar_idx].mean() + 1e-10)
                if vol_ratio > 1.3:
                    score += 4

                if ml_engine.is_trained:
                    try:
                        df_1h_slice = df_1h.iloc[max(0, bar_idx-200):bar_idx+1]
                        df_4h_slice = df_4h.iloc[:bar_idx//4+1] if df_4h is not None else df_1h_slice.iloc[::4]
                        pred = ml_engine.predict(df_1h_slice, df_4h_slice)
                        if pred and pred.get("label") == "看涨":
                            score += 12
                            conf = pred.get("confidence", 50)
                            if conf > 60:
                                score += 5
                        elif pred and pred.get("label") == "看跌":
                            score -= 15
                    except Exception:
                        pass

                direction = "long"
            elif ma20 < ma50:
                score += 10
                if price < ma20:
                    score += 5
                if rsi_val > 50 and rsi_val < 70:
                    score += 8
                if adx_val > 25:
                    score += 8
                elif adx_val > 20:
                    score += 4

                if ml_engine.is_trained:
                    try:
                        df_1h_slice = df_1h.iloc[max(0, bar_idx-200):bar_idx+1]
                        df_4h_slice = df_4h.iloc[:bar_idx//4+1] if df_4h is not None else df_1h_slice.iloc[::4]
                        pred = ml_engine.predict(df_1h_slice, df_4h_slice)
                        if pred and pred.get("label") == "看跌":
                            score += 12
                            conf = pred.get("confidence", 50)
                            if conf > 60:
                                score += 5
                        elif pred and pred.get("label") == "看涨":
                            score -= 15
                    except Exception:
                        pass

                direction = "short"
            else:
                return None

            if score >= 60:
                return {
                    "price": price,
                    "atr": atr_vals,
                    "score": score,
                    "direction": direction,
                    "rsi": rsi_val,
                    "adx": adx_val,
                }
        except Exception:
            pass
        return None

    @staticmethod
    def _calc_atr(df, idx, period=14):
        start = max(0, idx - period)
        sl = df.iloc[start:idx + 1]
        if len(sl) < 2:
            return df["c"].iloc[idx] * 0.02
        tr1 = sl["h"] - sl["l"]
        tr2 = (sl["h"] - sl["c"].shift(1)).abs()
        tr3 = (sl["l"] - sl["c"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        val = tr.mean()
        return val if not pd.isna(val) else df["c"].iloc[idx] * 0.02

    @staticmethod
    def _calc_rsi(close, idx, period=14):
        start = max(0, idx - period - 1)
        sl = close.iloc[start:idx + 1]
        if len(sl) < period:
            return 50
        delta = sl.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return val if not pd.isna(val) else 50

    @staticmethod
    def _calc_simple_adx(df, idx, period=14):
        start = max(0, idx - period * 2)
        sl = df.iloc[start:idx + 1]
        if len(sl) < period + 1:
            return 20
        high = sl["h"]
        low = sl["l"]
        close = sl["c"]
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_di = 100 * (plus_dm.rolling(period).mean() / (atr + 1e-10))
        minus_di = 100 * (minus_dm.rolling(period).mean() / (atr + 1e-10))
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10) * 100
        adx = dx.rolling(period).mean()
        val = adx.iloc[-1]
        return val if not pd.isna(val) else 20

    def get_status(self):
        base = {
            "status": self.status,
            "progress": self.progress,
            "progress_msg": self.progress_msg,
            "running": self.running,
        }
        if self.results and "error" not in self.results:
            base["has_results"] = True
            base["completed_at"] = self.results.get("completed_at", "")
            perf = self.results.get("performance", {})
            base["summary"] = {
                "final_equity": perf.get("final_equity", 0),
                "total_return_pct": perf.get("total_return_pct", 0),
                "max_drawdown_pct": perf.get("max_drawdown_pct", 0),
                "win_rate": perf.get("win_rate", 0),
                "total_trades": perf.get("total_trades", 0),
                "sharpe_ratio": perf.get("sharpe_ratio", 0),
            }
            evo = self.results.get("evolution", {})
            base["evolution_summary"] = {
                "retrain_count": evo.get("retrain_count", 0),
                "improved": evo.get("improved_over_time", False),
            }
        else:
            base["has_results"] = False
        return base


simulator = EvolutionarySimulator()
