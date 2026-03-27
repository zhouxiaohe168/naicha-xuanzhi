import asyncio
import json
import os
import logging
import time
import smtplib
import traceback
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.header import Header

import pytz
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanAutoPilot")


class TitanAutoPilot:
    CYCLE_INTERVAL = 900
    EMAIL_HOURS = [8, 12, 18, 22]
    TRAINING_HOURS = [4, 8, 16, 20]
    TIMEZONE = "Asia/Shanghai"
    STATE_FILE = "data/titan_autopilot.json"

    def __init__(self):
        self.running = False
        self.cycle_count = 0
        self.start_time = None
        self.last_email_hour = -1
        self.last_email_date = ""
        self.last_training_hour = -1
        self.last_training_date = ""
        self.last_proactive_review_date = ""
        self.pending_ceo_decisions = []
        self.module_reports = []
        self.actions_taken = []
        self.blocked_trades = []
        self.cycle_log = []
        self.training_status = {"running": False, "iteration": 0, "results": []}
        self.trading_paused = False
        self._load_state()

    def _load_state(self):
        try:
            if os.path.exists(self.STATE_FILE):
                with open(self.STATE_FILE, "r") as f:
                    data = json.load(f)
                self.cycle_count = data.get("cycle_count", 0)
                self.pending_ceo_decisions = data.get("pending_ceo_decisions", [])
                self.last_email_hour = data.get("last_email_hour", -1)
                self.last_email_date = data.get("last_email_date", "")
                self.last_training_hour = data.get("last_training_hour", -1)
                self.last_training_date = data.get("last_training_date", "")
                self.last_proactive_review_date = data.get("last_proactive_review_date", "")
                self.actions_taken = data.get("actions_taken", [])[-50:]
                self.blocked_trades = data.get("blocked_trades", [])[-100:]
                self.training_status = data.get("training_status", {"running": False, "iteration": 0, "results": []})
                self.trading_paused = data.get("trading_paused", False)
        except Exception as e:
            logger.warning(f"加载状态失败: {e}")

    def _save_state(self):
        try:
            data = {
                "cycle_count": self.cycle_count,
                "running": self.running,
                "trading_paused": self.trading_paused,
                "start_time": self.start_time,
                "pending_ceo_decisions": self.pending_ceo_decisions[-20:],
                "last_email_hour": self.last_email_hour,
                "last_email_date": self.last_email_date,
                "last_training_hour": self.last_training_hour,
                "last_training_date": self.last_training_date,
                "last_proactive_review_date": self.last_proactive_review_date,
                "actions_taken": self.actions_taken[-50:],
                "blocked_trades": self.blocked_trades[-100:],
                "training_status": self.training_status,
                "module_reports": self.module_reports[-10:],
                "saved_at": datetime.now().isoformat(),
            }
            atomic_json_save(self.STATE_FILE, data)
        except Exception as e:
            logger.error(f"保存状态失败: {e}")

    def get_now(self):
        tz = pytz.timezone(self.TIMEZONE)
        return datetime.now(tz)

    async def start(self, modules: dict):
        if self.running:
            logger.info("AutoPilot已在运行")
            return
        self.running = True
        self.start_time = time.time()
        logger.info("=== TitanAutoPilot 自动驾驶启动 ===")
        self._save_state()
        asyncio.create_task(self._main_loop(modules))

    def stop(self):
        self.running = False
        logger.info("=== TitanAutoPilot 自动驾驶停止 ===")
        self._save_state()

    async def _main_loop(self, modules: dict):
        while self.running:
            try:
                await self._execute_cycle(modules)
            except Exception as e:
                logger.error(f"AutoPilot循环异常: {e}\n{traceback.format_exc()}")
                self._escalate("系统异常", f"AutoPilot循环出错: {str(e)[:200]}", "critical")
            await asyncio.sleep(self.CYCLE_INTERVAL)

    async def _execute_cycle(self, modules: dict):
        self.cycle_count += 1
        now = self.get_now()
        cycle_start = time.time()
        logger.info(f"--- AutoPilot 第{self.cycle_count}轮巡检 @ {now.strftime('%H:%M:%S')} ---")

        reports = {}

        reports["risk"] = self._check_risk_system(modules)
        reports["ml"] = self._check_ml_status(modules)
        reports["trades"] = self._check_trade_performance(modules)
        reports["signal_quality"] = self._check_signal_quality(modules)
        reports["dispatcher"] = self._check_dispatcher(modules)
        reports["constitution"] = self._check_constitution(modules)
        reports["memory"] = self._check_memory(modules)

        self._sync_pause_flags(modules)
        self._decay_signal_gate_thresholds(reports)

        decisions = self._make_decisions(reports, modules)

        for decision in decisions:
            await self._execute_decision(decision, modules)

        self._check_email_schedule(modules, reports)
        await self._check_training_schedule(modules)
        self._check_proactive_review(modules)
        self._check_daily_learning_tasks(now)
        await self._backfill_4h_direction(modules)
        await self._verify_rejection_outcomes(modules)
        self._verify_cto_decisions(modules)
        self._sync_equity_to_coordinator(modules)
        self._run_regime_transition_check(modules)
        self._run_portfolio_correlation_check(modules)

        cycle_time = time.time() - cycle_start
        cycle_entry = {
            "cycle": self.cycle_count,
            "time": now.isoformat(),
            "duration_sec": round(cycle_time, 1),
            "reports_count": len(reports),
            "decisions_count": len(decisions),
            "pending_ceo": len(self.pending_ceo_decisions),
        }
        self.cycle_log.append(cycle_entry)
        self.cycle_log = self.cycle_log[-50:]

        self.module_reports.append({
            "cycle": self.cycle_count,
            "time": now.isoformat(),
            "summary": {k: v.get("status", "ok") for k, v in reports.items()},
            "decisions": [d.get("action", "") for d in decisions],
        })
        self.module_reports = self.module_reports[-20:]

        self._save_state()
        logger.info(f"--- 第{self.cycle_count}轮完成 耗时{cycle_time:.1f}s 决策{len(decisions)}个 ---")

    def _sync_equity_to_coordinator(self, modules):
        try:
            pt = modules.get("paper_trader")
            if not pt:
                return
            grid_pnl = 0
            grid_realized = 0
            try:
                from server.titan_grid import grid_engine
                grid_pnl = grid_engine.get_unrealized_pnl()
                grid_realized = grid_engine.total_grid_profit
            except Exception:
                pass
            equity = pt.get_equity(grid_pnl=grid_pnl, grid_realized_pnl=grid_realized)
            import json
            coord_path = "data/titan_coordinator.json"
            with open(coord_path) as f:
                coord = json.load(f)
            coord["current_equity"] = round(equity, 2)
            coord["peak_equity"] = round(max(coord.get("peak_equity", self.INITIAL_CAPITAL), equity), 2)
            from server.utils import atomic_json_save
            atomic_json_save(coord_path, coord)
        except Exception as e:
            logger.debug(f"权益同步到coordinator失败: {e}")

    def _run_regime_transition_check(self, modules):
        try:
            from server.titan_portfolio_analyst import regime_transition_detector
            from server.titan_state import TitanState as _TS
            dispatcher = modules.get("dispatcher")
            state = modules.get("state")
            snapshot = getattr(state, 'market_snapshot', {}) if state else {}
            btc_pulse = snapshot.get("btc_pulse", {})
            fng_detail = btc_pulse.get("fng_detail", {})
            cruise = snapshot.get("cruise", [])

            btc_vol_1h = 0
            btc_vol_7d_avg = 0
            volume_ratio = 1.0
            import numpy as _np
            for item in cruise:
                sym = item.get("sym", item.get("symbol", ""))
                if sym and "BTC" in sym and item.get("history"):
                    prices = _np.array(item["history"], dtype=float)
                    if len(prices) >= 2:
                        ret = abs(float(prices[-1] - prices[-2]) / (prices[-2] + 1e-10))
                        btc_vol_1h = ret
                    if len(prices) >= 168:
                        rets = _np.abs(_np.diff(prices[-168:])) / (prices[-168:-1] + 1e-10)
                        btc_vol_7d_avg = float(_np.mean(rets))
                    if item.get("volume_history"):
                        vols = item["volume_history"]
                        if len(vols) >= 7:
                            recent_vol = vols[-1] if vols else 0
                            avg_vol = sum(vols[-7:]) / 7
                            volume_ratio = recent_vol / (avg_vol + 1e-10) if avg_vol > 0 else 1.0
                    break

            high_score = sum(1 for item in cruise if item.get("score", 0) >= 65)
            pt = modules.get("paper_trader")
            recent_sl = 0
            if pt and hasattr(pt, 'get_recent_trades'):
                try:
                    for t in pt.get_recent_trades(10):
                        if t.get("close_reason", "").lower() in ("sl", "stop_loss", "sl_hit"):
                            recent_sl += 1
                except Exception:
                    pass

            market_data = {
                "regime": getattr(dispatcher, "current_regime", "unknown") if dispatcher else "unknown",
                "btc_price": btc_pulse.get("price", 0),
                "fng": btc_pulse.get("fng", 50),
                "fng_prev": fng_detail.get("avg_7d", btc_pulse.get("fng", 50)),
                "btc_vol_1h": btc_vol_1h,
                "btc_vol_7d_avg": btc_vol_7d_avg,
                "volume_ratio": volume_ratio,
                "recent_stop_losses": recent_sl,
                "high_score_signals": high_score,
                "active_positions": len(getattr(pt, 'positions', {})) if pt else 0,
            }

            result = regime_transition_detector.detect(market_data)
            if result.get("transition_risk") == "high":
                _TS.add_log("system", f"⚠️ Regime切换高风险预警: {result.get('current_regime')}→{result.get('most_likely_next')} 概率{result.get('probability', 0)*100:.0f}%")
                logger.warning(f"Regime切换高风险: {result}")
            elif result.get("transition_risk") == "medium":
                logger.info(f"Regime切换中风险: {result.get('current_regime')}→{result.get('most_likely_next')}")
        except Exception as e:
            logger.debug(f"Regime transition检查失败: {e}")

    def _run_portfolio_correlation_check(self, modules):
        try:
            from server.titan_portfolio_analyst import portfolio_correlation_analyst
            from server.titan_state import TitanState as _TS
            pt = modules.get("paper_trader")
            if not pt or not hasattr(pt, 'positions') or len(getattr(pt, 'positions', {})) < 2:
                return

            positions = list(pt.positions.values())
            state = modules.get("state")
            snapshot = getattr(state, 'market_snapshot', {}) if state else {}
            cruise = snapshot.get("cruise", [])
            price_data = {}
            for item in cruise:
                sym = item.get("sym", item.get("symbol", "")).replace("/USDT", "").replace("_USDT", "")
                history = item.get("history", [])
                if sym and history:
                    price_data[sym] = history

            grid_pnl = 0
            grid_realized = 0
            try:
                from server.titan_grid import grid_engine
                grid_pnl = grid_engine.get_unrealized_pnl()
                grid_realized = grid_engine.total_grid_profit
            except Exception:
                pass
            equity = pt.get_equity(grid_pnl=grid_pnl, grid_realized_pnl=grid_realized) if hasattr(pt, 'get_equity') else 100000

            result = portfolio_correlation_analyst.analyze(positions, price_data, equity)
            if result.get("correlation_risk") == "high":
                _TS.add_log("system", f"⚠️ 组合相关性高风险: 净暴露{result.get('net_exposure_pct', 0)}%, 风险分{result.get('risk_score', 0)}")
                logger.warning(f"组合相关性高风险: {result}")
            elif result.get("correlation_risk") == "medium":
                logger.info(f"组合相关性中风险: 净暴露{result.get('net_exposure_pct', 0)}%")
        except Exception as e:
            logger.debug(f"Portfolio correlation检查失败: {e}")

    def _verify_cto_decisions(self, modules):
        if self.cycle_count % 4 != 0:
            return
        try:
            from server.titan_db import db_connection
            import ccxt
            exchange = ccxt.gate()

            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id, target, created_at, target_price_at_decision
                    FROM cto_decisions
                    WHERE decision_type = 'blacklist_add'
                    AND verified_at IS NULL
                    AND target_price_at_decision IS NOT NULL
                    AND created_at < NOW() - INTERVAL '24 hours'
                    AND created_at > NOW() - INTERVAL '96 hours'
                    LIMIT 10
                """)
                decisions = cur.fetchall()

                if not decisions:
                    return

                logger.info(f"CTO决策验证: {len(decisions)}条待验证")

                for d in decisions:
                    try:
                        sym = d["target"]
                        ticker = exchange.fetch_ticker(f"{sym}/USDT")
                        if not ticker or not ticker.get("last"):
                            continue

                        price_now = ticker["last"]
                        price_at_decision = float(d["target_price_at_decision"])
                        hours_elapsed = (datetime.now() - d["created_at"]).total_seconds() / 3600
                        price_change_pct = (price_now - price_at_decision) / price_at_decision * 100

                        decision_correct = price_change_pct < -2.0

                        quality = 100 if price_change_pct < -5 else (75 if price_change_pct < -2 else (50 if price_change_pct < 2 else (25 if price_change_pct < 5 else 0)))

                        cur.execute("""
                            UPDATE cto_decisions
                            SET verified_at = NOW(),
                                verification_window_hours = %s,
                                price_change_pct = %s,
                                decision_correct = %s,
                                decision_quality_score = %s
                            WHERE id = %s
                        """, (int(hours_elapsed), round(price_change_pct, 2),
                              decision_correct, quality, d["id"]))
                        conn.commit()

                        logger.info(f"CTO验证: {sym} 拉黑后{hours_elapsed:.0f}h 价格{'↓' if price_change_pct<0 else '↑'}{abs(price_change_pct):.1f}% → {'正确' if decision_correct else '错误'}")

                    except Exception as sym_err:
                        logger.debug(f"CTO验证{d.get('target','')}失败: {sym_err}")
                        continue

        except Exception as e:
            logger.debug(f"CTO决策验证异常(非致命): {e}")

    def _sync_pause_flags(self, modules):
        constitution = modules.get("constitution")
        if not constitution:
            return
        const_breaker = getattr(constitution, 'daily_breaker', False)
        const_breaker_until = getattr(constitution, 'daily_breaker_until', 0)
        const_paused = const_breaker and time.time() < const_breaker_until
        if self.trading_paused and not const_paused:
            pt = modules.get("paper_trader")
            if pt:
                c_losses = getattr(pt, 'consecutive_losses', 0)
                if c_losses < 3:
                    self.trading_paused = False
                    state = modules.get("state")
                    if state and hasattr(state, "add_log"):
                        state.add_log("autopilot", "AutoPilot恢复交易: Constitution已解除暂停且连亏<3")
                    logger.info("AutoPilot恢复交易: 与Constitution同步")
        elif const_paused and not self.trading_paused:
            self.trading_paused = True
            logger.info("AutoPilot同步暂停: Constitution已暂停")

    def _decay_signal_gate_thresholds(self, reports):
        DEFAULT_SCORE = 73
        DEFAULT_ML = 40
        LEARNING_SCORE_CAP = 78
        LEARNING_ML_CAP = 50

        trade_report = reports.get("trades", {})
        c_losses = trade_report.get("consecutive_losses", 0)
        risk_report = reports.get("risk", {})
        risk_status = risk_report.get("status", "ok")

        if c_losses <= 4 and risk_status != "critical":
            decay_step = 3 if c_losses <= 1 else 2
            if TitanSignalGate.MIN_SIGNAL_SCORE > DEFAULT_SCORE:
                old_score = TitanSignalGate.MIN_SIGNAL_SCORE
                TitanSignalGate.MIN_SIGNAL_SCORE = max(DEFAULT_SCORE, TitanSignalGate.MIN_SIGNAL_SCORE - decay_step)
                if TitanSignalGate.MIN_SIGNAL_SCORE != old_score:
                    logger.info(f"SignalGate衰减: 最低评分 {old_score} → {TitanSignalGate.MIN_SIGNAL_SCORE}")
            if TitanSignalGate.MIN_ML_CONFIDENCE > DEFAULT_ML:
                old_ml = TitanSignalGate.MIN_ML_CONFIDENCE
                TitanSignalGate.MIN_ML_CONFIDENCE = max(DEFAULT_ML, TitanSignalGate.MIN_ML_CONFIDENCE - decay_step)
                if TitanSignalGate.MIN_ML_CONFIDENCE != old_ml:
                    logger.info(f"SignalGate衰减: 最低ML置信度 {old_ml} → {TitanSignalGate.MIN_ML_CONFIDENCE}")

    def _check_risk_system(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            risk_budget = modules.get("risk_budget")
            if risk_budget:
                dd = getattr(risk_budget, "total_drawdown", 0)
                if dd > 0.05:
                    report["status"] = "warning"
                    report["issues"].append(f"总回撤{dd*100:.1f}%超过5%警戒线")
                if dd > 0.07:
                    report["status"] = "critical"
                    report["issues"].append(f"总回撤{dd*100:.1f}%接近8%熔断线!")
                    self._escalate("风控警报", f"回撤已达{dd*100:.1f}%，接近8%熔断线", "critical")
                report["drawdown"] = dd
                budgets = getattr(risk_budget, "strategy_budgets", {})
                for strat, b in budgets.items():
                    if b.get("frozen"):
                        report["issues"].append(f"策略{strat}已被冻结")
            constitution = modules.get("constitution")
            if constitution:
                if getattr(constitution, "permanent_breaker", False):
                    report["status"] = "critical"
                    report["issues"].append("永久熔断器已触发!")
                    self._escalate("紧急!", "永久熔断器已触发,所有交易停止", "critical")
        except Exception as e:
            report["error"] = str(e)
        return report

    def _check_ml_status(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            ml = modules.get("ml_engine")
            if ml and hasattr(ml, "model"):
                metrics_path = "data/titan_ml_metrics.json"
                if os.path.exists(metrics_path):
                    with open(metrics_path) as f:
                        metrics = json.load(f)
                    acc = metrics.get("accuracy", 0)
                    f1 = metrics.get("f1", 0)
                    report["accuracy"] = acc
                    report["f1"] = f1
                    if acc < 65:
                        report["status"] = "warning"
                        report["issues"].append(f"ML准确率{acc}%低于65%，建议重训练")
                    if f1 < 60:
                        report["issues"].append(f"F1分数{f1}%偏低")
                    last_train = metrics.get("last_train", "")
                    if last_train:
                        try:
                            lt = datetime.fromisoformat(last_train)
                            age_hours = (datetime.now() - lt).total_seconds() / 3600
                            if age_hours > 24:
                                report["issues"].append(f"模型已{age_hours:.0f}小时未训练")
                        except:
                            pass
        except Exception as e:
            report["error"] = str(e)
        return report

    def _check_trade_performance(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            paper_trader = modules.get("paper_trader")
            if paper_trader:
                total = getattr(paper_trader, "total_wins", 0) + getattr(paper_trader, "total_losses", 0)
                wins = getattr(paper_trader, "total_wins", 0)
                wr = wins / max(1, total)
                report["win_rate"] = round(wr * 100, 1)
                report["total_trades"] = total
                report["positions"] = len(getattr(paper_trader, "positions", []))
                report["consecutive_losses"] = getattr(paper_trader, "consecutive_losses", 0)

                if wr < 0.30 and total >= 10:
                    report["status"] = "warning"
                    report["issues"].append(f"胜率{wr*100:.1f}%低于30%")
                if getattr(paper_trader, "consecutive_losses", 0) >= 3:
                    report["status"] = "warning"
                    report["issues"].append(f"连续亏损{paper_trader.consecutive_losses}笔")
                    self._escalate("交易警报", f"连续亏损{paper_trader.consecutive_losses}笔, 建议暂停交易", "high")
        except Exception as e:
            report["error"] = str(e)
        return report

    def _check_signal_quality(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            sq = modules.get("signal_quality")
            if sq:
                stats = getattr(sq, "condition_stats", {})
                bad_conditions = []
                for cond, data in stats.items():
                    total = data.get("count", 0)
                    wins = data.get("wins", 0)
                    if total >= 50:
                        wr = wins / total
                        if wr < 0.20:
                            bad_conditions.append(f"{cond}(胜率{wr*100:.0f}%/{total}笔)")
                if bad_conditions:
                    report["issues"].append(f"低质量信号条件: {', '.join(bad_conditions[:5])}")
                report["bad_conditions"] = bad_conditions
        except Exception as e:
            report["error"] = str(e)
        return report

    def _check_dispatcher(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            dispatcher = modules.get("dispatcher")
            if dispatcher:
                regime = getattr(dispatcher, "current_regime", "unknown")
                report["regime"] = regime
                alloc = getattr(dispatcher, "allocation", {})
                report["allocation"] = alloc
        except Exception as e:
            report["error"] = str(e)
        return report

    def _check_constitution(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            const = modules.get("constitution")
            if const:
                report["permanent_breaker"] = getattr(const, "permanent_breaker", False)
                peak = getattr(const, "total_peak_equity", 0)
                daily_start = getattr(const, "daily_start_equity", 0)
                report["peak_equity"] = peak
                report["daily_start"] = daily_start
        except Exception as e:
            report["error"] = str(e)
        return report

    def _check_memory(self, modules):
        report = {"status": "ok", "issues": []}
        try:
            mb_path = "data/titan_memory_bank.json"
            if os.path.exists(mb_path):
                with open(mb_path) as f:
                    mb = json.load(f)
                report["patterns"] = len(mb.get("trade_patterns", []))
                report["insights"] = len(mb.get("insights", []))
                report["rules"] = len(mb.get("rules", []))
        except Exception as e:
            report["error"] = str(e)
        return report

    def _make_decisions(self, reports, modules):
        decisions = []

        risk_report = reports.get("risk", {})
        if risk_report.get("status") == "critical":
            decisions.append({
                "action": "pause_trading",
                "reason": "风控系统报告严重风险",
                "auto": True,
            })

        trade_report = reports.get("trades", {})
        if trade_report.get("consecutive_losses", 0) >= 3:
            decisions.append({
                "action": "tighten_filters",
                "reason": f"连续亏损{trade_report['consecutive_losses']}笔",
                "auto": True,
            })

        ml_report = reports.get("ml", {})
        ml_acc = ml_report.get("accuracy", 100)
        if ml_acc < 65:
            decisions.append({
                "action": "suggest_retrain",
                "reason": f"ML准确率{ml_acc}%过低",
                "auto": False,
            })

        sq_report = reports.get("signal_quality", {})
        bad_conds = sq_report.get("bad_conditions", [])
        if len(bad_conds) >= 3:
            decisions.append({
                "action": "update_signal_gate",
                "reason": f"{len(bad_conds)}个信号条件质量过差",
                "auto": True,
            })

        trade_wr = trade_report.get("win_rate", 50)
        total_trades = trade_report.get("total_trades", 0)
        if total_trades >= 20 and trade_wr < 38:
            self._escalate(
                "胜率持续偏低",
                f"最近胜率仅{trade_wr:.1f}%，低于38%目标线。建议审查策略参数或暂停高亏损策略。",
                "high"
            )

        if trade_report.get("consecutive_losses", 0) >= 3 and total_trades >= 10:
            c_losses = trade_report["consecutive_losses"]
            if c_losses < 5:
                self._escalate(
                    "连续亏损预警",
                    f"已连续亏损{c_losses}笔，建议观察下一笔交易表现，若继续亏损考虑暂停策略或收紧过滤条件。",
                    "medium"
                )

        risk_dd = risk_report.get("drawdown", 0)
        if 0.03 < risk_dd < 0.05:
            self._escalate(
                "回撤接近预警线",
                f"当前回撤{risk_dd*100:.1f}%，已超过3%但未达5%警戒线。建议减小新仓位规模，密切关注回撤走势。",
                "medium"
            )

        ml_model_age = ml_report.get("issues", [])
        for issue in ml_model_age:
            if "未训练" in issue:
                self._escalate(
                    "模型需要更新",
                    f"ML模型长时间未训练。{issue}建议安排云端重训练以适应最新市场变化。",
                    "medium"
                )
                break

        return decisions

    async def _execute_decision(self, decision, modules):
        action = decision.get("action")
        reason = decision.get("reason")
        auto = decision.get("auto", False)
        now = self.get_now()

        if not auto:
            self._escalate("需要决策", f"{action}: {reason}", "medium")
            return

        entry = {
            "time": now.isoformat(),
            "action": action,
            "reason": reason,
            "result": "pending",
        }

        try:
            if action == "pause_trading":
                constitution = modules.get("constitution")
                if constitution and hasattr(constitution, "daily_pause"):
                    constitution.daily_pause = True
                    if hasattr(constitution, "save"):
                        constitution.save()
                self.trading_paused = True
                state = modules.get("state")
                if state and hasattr(state, "add_log"):
                    state.add_log("autopilot", f"⚠️ AutoPilot暂停交易: {reason}")
                entry["result"] = "executed_paused"

            elif action == "tighten_filters":
                TitanSignalGate.MIN_SIGNAL_SCORE = min(80, TitanSignalGate.MIN_SIGNAL_SCORE + 3)
                TitanSignalGate.MIN_ML_CONFIDENCE = min(52, TitanSignalGate.MIN_ML_CONFIDENCE + 3)
                state = modules.get("state")
                if state and hasattr(state, "add_log"):
                    state.add_log("autopilot", f"🔧 AutoPilot收紧过滤: 最低评分→{TitanSignalGate.MIN_SIGNAL_SCORE}, 最低ML→{TitanSignalGate.MIN_ML_CONFIDENCE}% | {reason}")
                entry["result"] = f"executed_score={TitanSignalGate.MIN_SIGNAL_SCORE}_ml={TitanSignalGate.MIN_ML_CONFIDENCE}"

            elif action == "update_signal_gate":
                sq = modules.get("signal_quality")
                if sq and hasattr(sq, "condition_stats"):
                    stats = sq.condition_stats
                    for cond, data in stats.items():
                        total = data.get("count", 0)
                        wins = data.get("wins", 0)
                        if total >= 50 and (wins / max(1, total)) < 0.15:
                            if cond not in TitanSignalGate.BLOCKED_CONDITIONS:
                                TitanSignalGate.BLOCKED_CONDITIONS[cond] = f"自动拉黑:胜率{wins/total*100:.0f}%({total}笔)"
                entry["result"] = f"executed_blocked={len(TitanSignalGate.BLOCKED_CONDITIONS)}"

            else:
                entry["result"] = "unknown_action"

        except Exception as e:
            entry["result"] = f"error: {str(e)[:100]}"

        self.actions_taken.append(entry)
        self.actions_taken = self.actions_taken[-50:]
        logger.info(f"AutoPilot决策执行: {action} -> {entry['result']}")

    def _escalate(self, title, detail, severity="medium"):
        now = self.get_now()
        item = {
            "time": now.isoformat(),
            "title": title,
            "detail": detail,
            "severity": severity,
            "resolved": False,
        }
        for existing in self.pending_ceo_decisions:
            if existing.get("title") == title and not existing.get("resolved"):
                existing["detail"] = detail
                existing["time"] = now.isoformat()
                return
        self.pending_ceo_decisions.append(item)
        self.pending_ceo_decisions = self.pending_ceo_decisions[-20:]
        logger.warning(f"升级CEO: [{severity}] {title} - {detail}")

    def _check_proactive_review(self, modules):
        now = self.get_now()
        current_date = now.strftime("%Y-%m-%d")
        weekday = now.weekday()
        hour = now.hour
        if weekday in (1, 3, 5) and hour == 10 and current_date != self.last_proactive_review_date:
            try:
                from server.titan_ai_reviewer import ai_reviewer
                paper_trader = modules.get("paper_trader")
                result = ai_reviewer.proactive_weekly_review(paper_trader=paper_trader, extra_count=3)
                if result:
                    self.last_proactive_review_date = current_date
                    self.actions_taken.append({
                        "time": now.isoformat(),
                        "action": "proactive_review",
                        "reason": "每周主动复盘3笔交易",
                        "result": "success",
                    })
                    logger.info("AutoPilot: 主动复盘完成，审查了3笔额外交易")
            except Exception as e:
                logger.warning(f"AutoPilot主动复盘失败: {e}")

    async def _backfill_4h_direction(self, modules):
        if self.cycle_count % 4 != 0:
            return
        try:
            from server.titan_db import TitanDB
            pending = TitanDB.get_trades_pending_4h_backfill(limit=20)
            if not pending:
                return

            commander = modules.get("commander")
            if not commander or not hasattr(commander, 'exchange'):
                logger.warning("4h回填: commander/exchange不可用，跳过")
                return

            filled = 0
            for trade in pending:
                try:
                    symbol = trade['symbol']
                    entry_price = trade['entry_price']
                    open_time = trade['open_time']
                    if not entry_price or entry_price <= 0:
                        continue

                    if hasattr(open_time, 'timestamp'):
                        open_ts = int(open_time.timestamp() * 1000)
                    else:
                        from datetime import datetime as dt
                        parsed = dt.fromisoformat(str(open_time).replace('Z', '+00:00'))
                        open_ts = int(parsed.timestamp() * 1000)

                    target_ts = open_ts + 4 * 3600 * 1000

                    import time as _time
                    if target_ts > int(_time.time() * 1000):
                        continue

                    sym_pair = f"{symbol}/USDT" if '/' not in symbol else symbol
                    ohlcv = await commander.exchange.fetch_ohlcv(
                        sym_pair, '1h', since=target_ts - 3600 * 1000, limit=2
                    )
                    if not ohlcv or len(ohlcv) == 0:
                        continue

                    price_4h = ohlcv[-1][4]
                    change_pct = (price_4h - entry_price) / entry_price * 100

                    if abs(change_pct) < 0.3:
                        direction = 'flat'
                    elif change_pct > 0:
                        direction = 'up'
                    else:
                        direction = 'down'

                    ok = TitanDB.update_signal_direction_4h(trade['id'], direction)
                    if ok:
                        filled += 1
                        logger.info(
                            f"4h direction backfill: trade {trade['id'][:8]} → {direction} "
                            f"(entry: {entry_price:.6f}, 4h price: {price_4h:.6f}, chg: {change_pct:+.2f}%)"
                        )
                except Exception as e:
                    logger.warning(f"4h回填单笔失败 {trade.get('id','?')[:8]}: {e}")
                    continue

            if filled > 0:
                self.actions_taken.append({
                    "time": self.get_now().isoformat(),
                    "action": "4h_direction_backfill",
                    "reason": f"回填{filled}/{len(pending)}笔交易的4h方向",
                    "result": "success",
                })
                logger.info(f"AutoPilot: 4h方向回填完成 {filled}/{len(pending)}")
        except Exception as e:
            logger.warning(f"4h方向回填任务失败: {e}")

    def _check_daily_learning_tasks(self, now):
        now_utc = now.astimezone(pytz.utc) if now.tzinfo else now
        hour_utc = now_utc.hour
        date_key = now_utc.strftime("%Y-%m-%d")

        last_run_date = self._get_last_daily_tasks_date()
        if last_run_date == date_key:
            return

        should_run = False
        trigger_reason = ""

        if hour_utc == 0 and now_utc.minute < 15:
            should_run = True
            trigger_reason = "UTC 00:00 定时触发"
        else:
            last_run_iso = self._get_last_daily_tasks_iso()
            if last_run_iso:
                try:
                    last_dt = datetime.fromisoformat(last_run_iso.replace('Z', '+00:00'))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=pytz.utc)
                    hours_since = (now_utc - last_dt).total_seconds() / 3600
                    if hours_since >= 23:
                        should_run = True
                        trigger_reason = f"备用触发(距上次{hours_since:.0f}h)"
                except Exception:
                    should_run = True
                    trigger_reason = "备用触发(上次时间解析失败)"
            else:
                should_run = True
                trigger_reason = "首次执行(无历史记录)"

        if not should_run:
            return

        logger.info(f"=== 日线学习任务开始 ({trigger_reason}) UTC {now_utc.strftime('%H:%M')} ===")
        task_results = {}

        try:
            from server.titan_strategy_brain import TitanStrategyBrain
            sb = TitanStrategyBrain()
            sb.update_weights_daily()
            task_results["strategy_brain"] = "ok"
            logger.info("[日线学习] 1/7 策略脑权重更新完成")
        except Exception as e:
            task_results["strategy_brain"] = f"error: {e}"
            logger.warning(f"[日线学习] 策略脑更新异常: {e}")

        try:
            from server.titan_memory_consumer import TitanMemoryConsumer
            consumer = TitanMemoryConsumer()
            consumer.consume_insights()
            task_results["memory_consumer"] = "ok"
            logger.info("[日线学习] 2/7 记忆消费完成")
        except Exception as e:
            task_results["memory_consumer"] = f"error: {e}"
            logger.warning(f"[日线学习] 记忆消费异常: {e}")

        try:
            from server.titan_proposal_translator import TitanProposalTranslator
            translator = TitanProposalTranslator()
            n_translated = translator.translate_pending_proposals()
            task_results["proposal_translator"] = f"ok ({n_translated} translated)"
            if n_translated > 0:
                logger.info(f"[日线学习] 3/7 提案转化: {n_translated}条定性提案已转化")
            else:
                logger.info("[日线学习] 3/7 提案转化: 无新提案需转化")
        except Exception as e:
            task_results["proposal_translator"] = f"error: {e}"
            logger.warning(f"[日线学习] 提案转化异常: {e}")

        try:
            from server.titan_evolution_executor import TitanEvolutionExecutor
            executor = TitanEvolutionExecutor()
            adopt_result = executor.run_auto_adopt()
            adopted_n = len(adopt_result.get('adopted', []))
            skipped_n = len(adopt_result.get('skipped', []))
            task_results["auto_adopt"] = f"ok (adopted={adopted_n}, skipped={skipped_n})"
            if adopted_n > 0:
                logger.info(f"[日线学习] 4/7 自动采纳{adopted_n}项进化提案")
            else:
                logger.info(f"[日线学习] 4/7 自动采纳: 无符合条件提案 (跳过{skipped_n}项)")
            executor.check_effects()
        except Exception as e:
            task_results["auto_adopt"] = f"error: {e}"
            logger.warning(f"[日线学习] 自动采纳异常: {e}")

        try:
            from server.titan_ai_coordinator import TitanAICoordinator
            coordinator = TitanAICoordinator()
            coordinator._consume_learning_journal()
            task_results["cto_journal"] = "ok"
            logger.info("[日线学习] 5/7 CTO学习日志消费完成")
        except Exception as e:
            task_results["cto_journal"] = f"error: {e}"
            logger.warning(f"[日线学习] CTO学习日志异常: {e}")

        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT target, confidence, notes
                    FROM evolution_proposals
                    WHERE confidence >= 0.75 AND status = 'pending'
                    ORDER BY confidence DESC LIMIT 10
                """)
                evo_rows = cur.fetchall()
                if evo_rows:
                    lines = [f"高置信度进化提案{len(evo_rows)}条待决策:"]
                    for p in evo_rows[:5]:
                        notes = (p.get('notes') or '')[:60]
                        lines.append(f"- [{p['confidence']}] {p['target']}: {notes}")
                    cur.execute("""
                        INSERT INTO learning_journal (source, content, priority, consumed_by_cto)
                        VALUES (%s, %s, %s, false)
                    """, ("evolution_to_agi", "\n".join(lines), "high"))
                    conn.commit()
                    task_results["evo_to_agi"] = f"ok ({len(evo_rows)} proposals pushed)"
                    logger.info(f"[日线学习] 6/8 Evolution→AGI: {len(evo_rows)}条高置信提案推送")
                else:
                    task_results["evo_to_agi"] = "ok (no high-conf proposals)"
                    logger.info("[日线学习] 6/8 Evolution→AGI: 无高置信度提案")
        except Exception as e:
            task_results["evo_to_agi"] = f"error: {e}"
            logger.warning(f"[日线学习] Evolution→AGI异常: {e}")

        try:
            from server.api import ai_coordinator as main_coordinator
            result = main_coordinator.generate_cto_report()
            status = result.get('status', 'unknown') if isinstance(result, dict) else 'ok'
            task_results["cto_report"] = f"ok ({status})"
            logger.info(f"[日线学习] 7/8 CTO报告自动生成完成: {status}")
        except Exception as e:
            task_results["cto_report"] = f"error: {e}"
            logger.warning(f"[日线学习] CTO报告生成异常: {e}")

        try:
            from server.titan_agi import TitanMetaCognition
            agi = TitanMetaCognition()
            market_summary = f"FNG={getattr(self, '_last_fng', 'N/A')}, 活跃仓位={len(getattr(self, 'positions', []))}"
            agi_result = agi.run_deep_reflection_sync(market_summary)
            if agi_result.get('success'):
                insight_len = len(agi_result.get('insight', ''))
                task_results["agi_reflection"] = f"ok ({insight_len}字)"
                logger.info(f"[日线学习] 8/9 AGI反思完成: {insight_len}字")
            else:
                task_results["agi_reflection"] = f"error: {agi_result.get('error', 'unknown')}"
                logger.warning(f"[日线学习] AGI反思失败: {agi_result.get('error')}")
        except Exception as e:
            task_results["agi_reflection"] = f"error: {e}"
            logger.warning(f"[日线学习] AGI反思异常: {e}")

        weekday_utc = now_utc.weekday()
        if weekday_utc == 6:
            try:
                from server.titan_backtester import TitanBacktester
                bt = TitanBacktester()
                report = bt.run_full_backtest(days=30)
                auto_count = len(report.get("auto_proposals", []))
                pending_count = len(report.get("pending_proposals", []))
                task_results["weekly_backtest"] = f"ok (auto={auto_count}, pending={pending_count})"
                logger.info(f"[日线学习] 8/8 每周回测完成 | {report.get('summary', '')}")
                self.actions_taken.append({
                    "time": now.isoformat(),
                    "action": "weekly_backtest",
                    "reason": f"回测完成: {report.get('summary', '')}",
                    "result": "success",
                })
            except Exception as e:
                task_results["weekly_backtest"] = f"error: {e}"
                logger.warning(f"[日线学习] 每周回测异常: {e}")
        else:
            task_results["weekly_backtest"] = "skipped (not Sunday)"

        self._mark_daily_tasks_done(date_key, task_results)
        ok_count = sum(1 for v in task_results.values() if str(v).startswith("ok"))
        total_count = len(task_results)
        logger.info(f"=== 日线学习任务完成 {ok_count}/{total_count} 成功 ===")

    def _get_last_daily_tasks_date(self):
        try:
            coord_path = os.path.join(os.path.dirname(__file__), "..", "data", "titan_coordinator.json")
            if os.path.exists(coord_path):
                with open(coord_path, 'r') as f:
                    coord = json.load(f)
                return coord.get('last_daily_tasks_date', '')
        except Exception:
            pass
        return ''

    def _get_last_daily_tasks_iso(self):
        try:
            coord_path = os.path.join(os.path.dirname(__file__), "..", "data", "titan_coordinator.json")
            if os.path.exists(coord_path):
                with open(coord_path, 'r') as f:
                    coord = json.load(f)
                return coord.get('last_evolution_run', '')
        except Exception:
            pass
        return ''

    def _mark_daily_tasks_done(self, date_key, task_results):
        try:
            coord_path = os.path.join(os.path.dirname(__file__), "..", "data", "titan_coordinator.json")
            coord = {}
            if os.path.exists(coord_path):
                with open(coord_path, 'r') as f:
                    coord = json.load(f)
            coord['last_daily_tasks_date'] = date_key
            coord['last_evolution_run'] = datetime.now(pytz.utc).isoformat()
            coord['last_daily_tasks_results'] = task_results
            atomic_json_save(coord_path, coord)
        except Exception as e:
            logger.warning(f"记录日线学习完成状态失败: {e}")

    async def _verify_rejection_outcomes(self, modules):
        if self.cycle_count % 2 != 0:
            return
        try:
            from server.titan_db import TitanDB
            pending = TitanDB.verify_rejections()
            if not pending:
                return

            commander = modules.get("commander")
            if not commander or not hasattr(commander, 'exchange'):
                return

            verified = 0
            for rej in pending:
                try:
                    symbol = rej['symbol']
                    price_at_rej = rej['price_at_rejection']
                    direction = rej['direction']
                    if not price_at_rej or price_at_rej <= 0:
                        continue

                    sym_pair = f"{symbol}/USDT" if '/' not in symbol else symbol
                    ticker = await commander.exchange.fetch_ticker(sym_pair)
                    if not ticker or 'last' not in ticker:
                        continue

                    current_price = ticker['last']
                    change_pct = (current_price - price_at_rej) / price_at_rej * 100

                    if direction == 'long':
                        was_correct = change_pct < -2.0
                    else:
                        was_correct = change_pct > 2.0

                    TitanDB.update_rejection_verification(
                        rej['id'], current_price, round(change_pct, 2), was_correct
                    )
                    verified += 1
                except Exception:
                    continue

            if verified > 0:
                logger.info(f"AutoPilot: 拒绝信号验证完成 {verified}/{len(pending)}")
        except Exception as e:
            logger.warning(f"拒绝信号验证任务失败: {e}")

    def _check_email_schedule(self, modules, reports):
        now = self.get_now()
        current_hour = now.hour
        current_date = now.strftime("%Y-%m-%d")

        if current_date != self.last_email_date:
            self.last_email_hour = -1
            self.last_email_date = current_date

        should_send = False
        for target_hour in self.EMAIL_HOURS:
            if current_hour >= target_hour and self.last_email_hour < target_hour:
                should_send = True
                break

        if should_send:
            try:
                self._send_operations_email(modules, reports)
                self.last_email_hour = current_hour
                self.last_email_date = current_date
            except Exception as e:
                logger.error(f"发送运营邮件失败: {e}")

    async def _check_training_schedule(self, modules):
        now = self.get_now()
        current_hour = now.hour
        current_date = now.strftime("%Y-%m-%d")

        if current_date != self.last_training_date:
            self.last_training_hour = -1
            self.last_training_date = current_date

        if self.training_status.get("running"):
            return

        should_train = False
        triggered_hour = None
        for target_hour in sorted(self.TRAINING_HOURS):
            if current_hour >= target_hour and self.last_training_hour < target_hour:
                should_train = True
                triggered_hour = target_hour
                break

        if should_train and triggered_hour is not None:
            try:
                logger.info(f"[AutoPilot] 定时云训练(Alpha+MM)触发 @ {now.strftime('%H:%M')} (计划: {triggered_hour}:00)")
                state_module = modules.get("state")
                if state_module and hasattr(state_module, "add_log"):
                    state_module.add_log("system", f"☁️ 定时云训练(Alpha+MM)启动 (计划时间: {triggered_hour}:00)")

                import asyncio
                from server.titan_modal_client import trigger_deep_all_training
                try:
                    result = await asyncio.wait_for(trigger_deep_all_training(max_assets=69), timeout=30)
                except asyncio.TimeoutError:
                    result = {"status": "timeout"}
                train_status = result.get("status", "unknown")
                logger.info(f"[AutoPilot] 云训练(DeepAll)提交结果: {train_status}")

                if state_module and hasattr(state_module, "add_log"):
                    state_module.add_log("ml", f"☁️ Modal DeepAll训练已提交: Alpha+MM模型, status={train_status}")

                self.actions_taken.append({
                    "time": now.isoformat(),
                    "action": "auto_cloud_training_deep_all",
                    "reason": f"定时训练(Alpha+MM) {triggered_hour}:00",
                    "result": f"status={train_status}",
                })
                self.actions_taken = self.actions_taken[-50:]

                self.last_training_hour = triggered_hour
                self.last_training_date = current_date
                self._save_state()
            except Exception as e:
                logger.error(f"定时云训练(DeepAll)失败: {e}")
                self.actions_taken.append({
                    "time": now.isoformat(),
                    "action": "auto_cloud_training_deep_all",
                    "reason": f"定时训练(Alpha+MM) {triggered_hour}:00",
                    "result": f"error: {str(e)[:100]}",
                })
                self.last_training_hour = triggered_hour
                self._save_state()

    def _gather_market_snapshot(self, modules):
        try:
            state = modules.get("state")
            if not state:
                return {"btc_price": 0, "btc_change": "N/A", "fng_value": "N/A", "fng_label": "", "total_scanned": 0}
            snapshot = getattr(state, 'market_snapshot', {})
            btc_pulse = snapshot.get("btc_pulse", {})
            fng_data = snapshot.get("fng", {})
            return {
                "btc_price": btc_pulse.get("price", 0),
                "btc_change": btc_pulse.get("change", "0%"),
                "fng_value": fng_data.get("value", "N/A") if isinstance(fng_data, dict) else fng_data,
                "fng_label": fng_data.get("label", "") if isinstance(fng_data, dict) else "",
                "total_scanned": snapshot.get("total_scanned", 0),
            }
        except Exception as e:
            logger.warning(f"获取市场快照失败: {e}")
            return {"btc_price": 0, "btc_change": "N/A", "fng_value": "N/A", "fng_label": "", "total_scanned": 0}

    def _gather_equity_data(self, modules):
        try:
            pt = modules.get("paper_trader")
            if not pt:
                return {"equity": 0, "capital": 0, "pnl": 0, "pnl_pct": 0, "positions": [], "recent_trades": []}
            equity = pt.get_equity() if hasattr(pt, 'get_equity') else 0
            capital = getattr(pt, 'capital', 0)
            initial = getattr(pt, 'INITIAL_CAPITAL', 100000)
            pnl = equity - initial
            pnl_pct = (pnl / initial * 100) if initial > 0 else 0
            positions_list = []
            for pid, pos in getattr(pt, 'positions', {}).items():
                positions_list.append({
                    "symbol": pos.get("symbol", "?"),
                    "direction": pos.get("direction", "?"),
                    "entry": pos.get("entry_price", 0),
                    "size": pos.get("size", 0),
                    "pnl_pct": pos.get("pnl_pct", 0),
                    "strategy": pos.get("strategy", ""),
                })
            recent_trades = []
            trade_log = getattr(pt, 'trade_history', getattr(pt, 'trade_log', []))
            for t in trade_log[-10:]:
                recent_trades.append({
                    "symbol": t.get("symbol", "?"),
                    "direction": t.get("direction", "?"),
                    "pnl_pct": t.get("pnl_pct", 0),
                    "result": t.get("result", ""),
                    "time": t.get("close_time", t.get("time", ""))[:16] if t.get("close_time", t.get("time")) else "",
                })
            return {
                "equity": equity,
                "capital": capital,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "peak_equity": getattr(pt, 'peak_equity', equity),
                "positions": positions_list,
                "recent_trades": recent_trades,
            }
        except Exception as e:
            logger.warning(f"获取权益数据失败: {e}")
            return {"equity": 0, "capital": 0, "pnl": 0, "pnl_pct": 0, "positions": [], "recent_trades": []}

    def _calc_wall_street_metrics(self, modules):
        import math
        metrics = {"sharpe": 0, "sortino": 0, "calmar": 0, "profit_factor": 0,
                   "avg_win": 0, "avg_loss": 0, "max_drawdown_pct": 0,
                   "win_rate": 0, "expectancy": 0, "total_return_pct": 0,
                   "annualized_return_pct": 0, "risk_reward_ratio": 0,
                   "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                   "best_trade": 0, "worst_trade": 0, "avg_holding_hours": 0,
                   "consecutive_wins_max": 0, "consecutive_losses_max": 0,
                   "volatility_annual": 0, "trading_days": 0,
                   "direction_accuracy": None, "long_accuracy": None,
                   "short_accuracy": None, "direction_sample": 0}
        try:
            pt = modules.get("paper_trader")
            if not pt:
                return metrics
            _TEST_SYMBOLS = {'STABLE', 'COINON', 'MY', 'USELESS', '我踏马来了'}
            trade_log = [t for t in getattr(pt, 'trade_history', getattr(pt, 'trade_log', []))
                         if t.get('symbol') not in _TEST_SYMBOLS]

            pnl_pcts = [t.get("pnl_pct", 0) for t in trade_log]
            pnl_vals = [t.get("pnl_value", 0) or 0 for t in trade_log]
            wins_pct = [p for p in pnl_pcts if p > 0]
            losses_pct = [p for p in pnl_pcts if p < 0]
            wins_val = [v for v in pnl_vals if v > 0]
            losses_val = [v for v in pnl_vals if v < 0]

            if len(trade_log) >= 2:
                metrics["total_trades"] = len(pnl_pcts)
                metrics["winning_trades"] = len(wins_pct)
                metrics["losing_trades"] = len(pnl_pcts) - len(wins_pct)
                metrics["win_rate"] = round(len(wins_pct) / len(pnl_pcts) * 100, 1) if pnl_pcts else 0
            metrics["avg_win"] = round(sum(wins_pct) / len(wins_pct), 2) if wins_pct else 0
            metrics["avg_loss"] = round(sum(losses_pct) / len(losses_pct), 2) if losses_pct else 0
            metrics["best_trade"] = round(max(pnl_vals), 2) if pnl_vals else 0
            metrics["worst_trade"] = round(min(pnl_vals), 2) if pnl_vals else 0

            gross_win_dollar = sum(wins_val) if wins_val else 0
            gross_loss_dollar = abs(sum(losses_val)) if losses_val else 0
            metrics["profit_factor"] = round(gross_win_dollar / gross_loss_dollar, 2) if gross_loss_dollar > 0 else (999 if gross_win_dollar > 0 else 0)

            metrics["expectancy"] = round(sum(pnl_vals) / len(pnl_vals), 2) if pnl_vals else 0

            if metrics["avg_loss"] != 0:
                metrics["risk_reward_ratio"] = round(abs(metrics["avg_win"] / metrics["avg_loss"]), 2)

            max_cw = 0
            max_cl = 0
            cw = 0
            cl = 0
            for v in pnl_vals:
                if v > 0:
                    cw += 1
                    cl = 0
                else:
                    cl += 1
                    cw = 0
                max_cw = max(max_cw, cw)
                max_cl = max(max_cl, cl)
            metrics["consecutive_wins_max"] = max_cw
            metrics["consecutive_losses_max"] = max_cl

            holding_hours = []
            for t in trade_log:
                h = t.get("hold_hours", t.get("holding_hours", 0))
                if h and h > 0:
                    holding_hours.append(h)
            if holding_hours:
                metrics["avg_holding_hours"] = round(sum(holding_hours) / len(holding_hours), 1)

            first_time = None
            last_time = None
            for t in trade_log:
                ct = t.get("close_time") or t.get("time", "")
                if ct:
                    if first_time is None or ct < first_time:
                        first_time = ct
                    if last_time is None or ct > last_time:
                        last_time = ct

            trading_days = 1
            if first_time and last_time:
                try:
                    from datetime import datetime as dt2
                    ft = dt2.fromisoformat(first_time[:19]) if isinstance(first_time, str) else first_time
                    lt = dt2.fromisoformat(last_time[:19]) if isinstance(last_time, str) else last_time
                    trading_days = max(1, (lt - ft).total_seconds() / 86400)
                except Exception:
                    trading_days = max(1, len(pnl_pcts) // 3)
            metrics["trading_days"] = trading_days

            initial = getattr(pt, 'INITIAL_CAPITAL', 100000)
            grid_pnl = 0
            grid_realized = 0
            try:
                from server.titan_grid import grid_engine
                grid_pnl = grid_engine.get_unrealized_pnl()
                grid_realized = grid_engine.total_grid_profit
            except Exception:
                pass
            equity = pt.get_equity(grid_pnl=grid_pnl, grid_realized_pnl=grid_realized) if hasattr(pt, 'get_equity') else initial
            total_return = (equity - initial) / initial * 100 if initial > 0 else 0
            metrics["total_return_pct"] = round(total_return, 2)

            years = trading_days / 365
            if years > 0 and equity > 0 and initial > 0:
                metrics["annualized_return_pct"] = round(((equity / initial) ** (1 / years) - 1) * 100, 2)
            else:
                metrics["annualized_return_pct"] = round(total_return, 2)

            peak = initial
            max_dd = 0
            running_equity = initial
            portfolio_returns = []
            for t in trade_log:
                pnl_val = t.get("pnl_value", 0) or 0
                ret = pnl_val / running_equity if running_equity > 0 else 0
                portfolio_returns.append(ret)
                running_equity += pnl_val
                peak = max(peak, running_equity)
                dd = (peak - running_equity) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)
            metrics["max_drawdown_pct"] = round(max_dd, 2)

            daily_returns = portfolio_returns

            if len(daily_returns) >= 2:
                mean_r = sum(daily_returns) / len(daily_returns)
                var_r = sum((r - mean_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
                std_r = math.sqrt(var_r) if var_r > 0 else 0

                trades_per_year = len(pnl_pcts) / max(years, 0.01)
                annual_std = std_r * math.sqrt(trades_per_year) if trades_per_year > 0 else 0
                metrics["volatility_annual"] = round(annual_std * 100, 2)

                if std_r > 0:
                    metrics["sharpe"] = round((mean_r / std_r) * math.sqrt(trades_per_year), 2)

                downside = [r for r in daily_returns if r < 0]
                if downside:
                    down_var = sum(r ** 2 for r in downside) / len(downside)
                    down_std = math.sqrt(down_var)
                    if down_std > 0:
                        metrics["sortino"] = round((mean_r / down_std) * math.sqrt(trades_per_year), 2)

            if max_dd > 0:
                metrics["calmar"] = round(metrics["annualized_return_pct"] / max_dd, 2)

            try:
                from server.titan_db import db_connection
                with db_connection(dict_cursor=True) as (conn, cur):
                    cur.execute("""
                        SELECT
                            COUNT(*) as total,
                            COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins
                        FROM trades
                        WHERE result IN ('win', 'loss') AND direction IS NOT NULL
                        AND (extra->>'is_test_data')::boolean IS NOT TRUE
                    """)
                    row = cur.fetchone()
                    if row and row['total'] > 0:
                        metrics["direction_accuracy"] = round(row['wins'] / row['total'] * 100, 1)
                        metrics["direction_sample"] = row['total']

                    cur.execute("""
                        SELECT direction,
                            COUNT(*) as total,
                            COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins
                        FROM trades
                        WHERE result IN ('win', 'loss') AND direction IS NOT NULL
                        AND (extra->>'is_test_data')::boolean IS NOT TRUE
                        GROUP BY direction
                    """)
                    for drow in cur.fetchall():
                        d = drow['direction']
                        if drow['total'] > 0:
                            acc = round(drow['wins'] / drow['total'] * 100, 1)
                            if d == 'long':
                                metrics["long_accuracy"] = acc
                            elif d == 'short':
                                metrics["short_accuracy"] = acc

                    cur.execute("""
                        SELECT COUNT(*) as total,
                            COALESCE(SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END), 0) as wins,
                            COALESCE(SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END), 0) as losses
                        FROM trades WHERE result IN ('win', 'loss')
                        AND (extra->>'is_test_data')::boolean IS NOT TRUE
                    """)
                    db_row = cur.fetchone()
                    if db_row and db_row['total'] > 0:
                        metrics["total_trades"] = db_row['total']
                        metrics["winning_trades"] = db_row['wins']
                        metrics["losing_trades"] = db_row['losses']
                        metrics["win_rate"] = round(db_row['wins'] / db_row['total'] * 100, 1)
            except Exception as e2:
                logger.warning(f"DB方向准确率查询失败: {e2}")

        except Exception as e:
            logger.warning(f"华尔街指标计算失败: {e}")
        return metrics

    def _send_operations_email(self, modules, reports):
        sender = os.getenv('SENDER_EMAIL')
        password = os.getenv('SENDER_PASSWORD')
        receivers = []
        r1 = os.getenv('RECEIVER_EMAIL')
        r2 = os.getenv('RECEIVER_EMAIL_2')
        if r1: receivers.append(r1)
        if r2: receivers.append(r2)
        if not sender or not password or not receivers:
            logger.warning("邮件配置缺失")
            return False

        now = self.get_now()
        now_str = now.strftime('%Y-%m-%d %H:%M')

        risk = reports.get("risk", {})
        ml = reports.get("ml", {})
        trades = reports.get("trades", {})
        dispatcher_r = reports.get("dispatcher", {})
        constitution = reports.get("constitution", {})
        memory = reports.get("memory", {})

        ws = self._calc_wall_street_metrics(modules)

        market = self._gather_market_snapshot(modules)
        equity_data = self._gather_equity_data(modules)

        risk_color = "#10b981" if risk.get("status") == "ok" else ("#f59e0b" if risk.get("status") == "warning" else "#ef4444")
        risk_text = "正常" if risk.get("status") == "ok" else ("警告" if risk.get("status") == "warning" else "严重")
        dd_pct = risk.get("drawdown", 0) * 100

        ml_acc = ml.get('accuracy', 'N/A')
        ml_f1 = ml.get('f1', 'N/A')
        ml_acc_str = f"{ml_acc}%" if ml_acc != 'N/A' else "待训练"
        ml_f1_str = f"{ml_f1}%" if ml_f1 != 'N/A' else "N/A"

        wr = trades.get('win_rate', 'N/A')
        wr_str = f"{wr}%" if wr != 'N/A' else "无交易"
        total_t = trades.get('total_trades', 0)
        open_pos = trades.get('positions', 0)

        regime = dispatcher_r.get('regime', '未知')
        regime_map = {"trending": "趋势", "ranging": "震荡", "volatile": "剧烈", "mixed": "混合"}
        regime_cn = regime_map.get(regime, regime)

        eq = equity_data.get("equity", 0)
        pnl = equity_data.get("pnl", 0)
        pnl_pct = equity_data.get("pnl_pct", 0)
        pnl_color = "#10b981" if pnl >= 0 else "#ef4444"

        btc_price = market.get("btc_price", 0)
        btc_change = market.get("btc_change", "N/A")
        fng_val = market.get("fng_value", "N/A")
        fng_label = market.get("fng_label", "")

        btc_change_val = 0
        try:
            btc_change_val = float(str(btc_change).replace('%', '').replace('+', ''))
        except:
            pass
        btc_color = "#10b981" if btc_change_val >= 0 else "#ef4444"

        pending_html = ""
        if self.pending_ceo_decisions:
            pending_rows = ""
            for item in self.pending_ceo_decisions:
                if not item.get("resolved"):
                    sev_color = "#ef4444" if item["severity"] == "critical" else ("#f59e0b" if item["severity"] == "high" else "#3b82f6")
                    pending_rows += f"""
                    <tr>
                        <td style="padding:8px;color:{sev_color};font-weight:bold;">{item['severity'].upper()}</td>
                        <td style="padding:8px;font-weight:bold;">{item['title']}</td>
                        <td style="padding:8px;font-size:11px;">{item['detail']}</td>
                        <td style="padding:8px;font-size:10px;color:#94a3b8;">{item['time'][:16]}</td>
                    </tr>"""
            if pending_rows:
                pending_html = f"""
                <div style="margin-top:20px;background:#fef2f2;border:2px solid #ef4444;border-radius:8px;padding:15px;">
                    <h3 style="margin:0 0 10px;color:#ef4444;">待CEO决策 ({len([x for x in self.pending_ceo_decisions if not x.get('resolved')])}项)</h3>
                    <table style="width:100%;border-collapse:collapse;font-size:12px;">
                        <tr style="background:#fecaca;"><th style="padding:8px;">级别</th><th>问题</th><th>详情</th><th>时间</th></tr>
                        {pending_rows}
                    </table>
                </div>"""

        actions_html = ""
        recent_actions = self.actions_taken[-10:]
        if recent_actions:
            action_rows = ""
            for a in recent_actions:
                res_color = "#10b981" if a["result"] == "executed" else "#f59e0b"
                action_rows += f"""
                <tr style="font-size:11px;border-bottom:1px solid #f1f5f9;">
                    <td style="padding:6px;">{a['time'][:16]}</td>
                    <td style="padding:6px;font-weight:bold;">{a['action']}</td>
                    <td style="padding:6px;">{a['reason'][:60]}</td>
                    <td style="padding:6px;color:{res_color};">{a['result']}</td>
                </tr>"""
            actions_html = f"""
            <div style="margin-top:15px;">
                <h3 style="margin:0 0 8px;color:#1e293b;font-size:14px;">AutoPilot执行记录</h3>
                <table style="width:100%;border-collapse:collapse;font-size:11px;">
                    <tr style="background:#f1f5f9;"><th style="padding:6px;">时间</th><th>动作</th><th>原因</th><th>结果</th></tr>
                    {action_rows}
                </table>
            </div>"""

        blocked_html = ""
        recent_blocked = self.blocked_trades[-10:]
        if recent_blocked:
            blocked_rows = "".join([
                f"<tr style='font-size:11px;border-bottom:1px solid #f1f5f9;'><td style='padding:4px;'>{b.get('time','')[:16]}</td><td style='padding:4px;font-weight:bold;'>{b.get('symbol','')}</td><td style='padding:4px;'>{b.get('reason','')[:80]}</td></tr>"
                for b in recent_blocked
            ])
            blocked_html = f"""
            <div style="margin-top:15px;">
                <h3 style="margin:0 0 8px;color:#f59e0b;font-size:14px;">信号门控拦截记录 (近{len(recent_blocked)}笔)</h3>
                <table style="width:100%;border-collapse:collapse;"><tr style="background:#fef3c7;"><th style="padding:4px;">时间</th><th>标的</th><th>拦截原因</th></tr>{blocked_rows}</table>
            </div>"""

        training_html = ""
        ts = self.training_status
        if ts.get("running") or ts.get("results"):
            t_status = "训练中" if ts.get("running") else "已完成"
            t_iter = ts.get("iteration", 0)
            t_results_rows = ""
            for r in ts.get("results", [])[-5:]:
                t_results_rows += f"<tr style='font-size:11px;'><td style='padding:4px;'>第{r.get('iteration',0)}轮</td><td style='padding:4px;'>{r.get('accuracy','N/A')}%</td><td style='padding:4px;'>{r.get('calmar','N/A')}</td><td style='padding:4px;'>{r.get('sharpe','N/A')}</td></tr>"
            training_html = f"""
            <div style="margin-top:15px;background:#eff6ff;border-radius:8px;padding:15px;">
                <h3 style="margin:0 0 8px;color:#3b82f6;font-size:14px;">深度训练状态: {t_status} (第{t_iter}轮)</h3>
                <table style="width:100%;border-collapse:collapse;"><tr style="background:#dbeafe;"><th style="padding:4px;">轮次</th><th>准确率</th><th>Calmar</th><th>Sharpe</th></tr>{t_results_rows}</table>
            </div>"""

        positions_html = ""
        pos_list = equity_data.get("positions", [])
        if pos_list:
            pos_rows = ""
            for p in pos_list:
                dir_icon = "LONG" if p["direction"] == "long" else "SHORT"
                dir_color = "#10b981" if p["direction"] == "long" else "#ef4444"
                p_pnl = p.get("pnl_pct", 0)
                p_pnl_color = "#10b981" if p_pnl >= 0 else "#ef4444"
                pos_rows += f"""<tr style="font-size:11px;border-bottom:1px solid #f1f5f9;">
                    <td style="padding:5px;font-weight:bold;">{p['symbol']}</td>
                    <td style="padding:5px;color:{dir_color};font-weight:bold;">{dir_icon}</td>
                    <td style="padding:5px;">${p['entry']:,.4f}</td>
                    <td style="padding:5px;color:{p_pnl_color};font-weight:bold;">{p_pnl:+.2f}%</td>
                    <td style="padding:5px;font-size:10px;color:#94a3b8;">{p.get('strategy','')}</td>
                </tr>"""
            positions_html = f"""
            <div style="margin-top:15px;">
                <h3 style="margin:0 0 8px;color:#1e293b;font-size:14px;">当前持仓 ({len(pos_list)}个)</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr style="background:#1e293b;color:#fff;font-size:10px;"><th style="padding:5px;">标的</th><th>方向</th><th>入场价</th><th>盈亏</th><th>策略</th></tr>
                    {pos_rows}
                </table>
            </div>"""
        else:
            positions_html = '<div style="margin-top:15px;"><h3 style="margin:0 0 8px;color:#1e293b;font-size:14px;">当前持仓</h3><p style="color:#94a3b8;font-size:12px;">暂无持仓</p></div>'

        recent_trades_html = ""
        recent_t = equity_data.get("recent_trades", [])
        if recent_t:
            t_rows = ""
            for t in reversed(recent_t[-8:]):
                t_pnl = t.get("pnl_pct", 0)
                t_color = "#10b981" if t_pnl >= 0 else "#ef4444"
                t_icon = "WIN" if t_pnl >= 0 else "LOSS"
                t_rows += f"""<tr style="font-size:11px;border-bottom:1px solid #f1f5f9;">
                    <td style="padding:4px;">{t.get('time','')}</td>
                    <td style="padding:4px;font-weight:bold;">{t['symbol']}</td>
                    <td style="padding:4px;color:{t_color};font-weight:bold;">{t_icon} {t_pnl:+.2f}%</td>
                </tr>"""
            recent_trades_html = f"""
            <div style="margin-top:15px;">
                <h3 style="margin:0 0 8px;color:#1e293b;font-size:14px;">近期平仓记录</h3>
                <table style="width:100%;border-collapse:collapse;">
                    <tr style="background:#f1f5f9;"><th style="padding:4px;">时间</th><th>标的</th><th>结果</th></tr>
                    {t_rows}
                </table>
            </div>"""

        error_modules = []
        for key, rpt in reports.items():
            if rpt.get("error"):
                error_modules.append(f"{key}: {rpt['error'][:50]}")
        error_html = ""
        if error_modules:
            error_html = f"""
            <div style="margin-top:15px;background:#fef2f2;border-radius:8px;padding:10px;">
                <h3 style="margin:0 0 5px;font-size:12px;color:#ef4444;">数据接口异常 ({len(error_modules)}项)</h3>
                <div style="font-size:10px;color:#dc2626;">{'<br>'.join(error_modules)}</div>
            </div>"""

        body = f"""
        <html>
        <body style="margin:0;padding:20px;background:#f1f5f9;font-family:sans-serif;">
        <div style="max-width:800px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;border:1px solid #e2e8f0;">
            <div style="background:linear-gradient(135deg,#0f172a,#1e3a8a);padding:25px;color:#fff;">
                <div style="font-size:10px;font-weight:800;letter-spacing:2px;color:#fbbf24;">TITAN AUTOPILOT | 自动驾驶运营报告</div>
                <h1 style="margin:5px 0 0;font-size:20px;">第{self.cycle_count}轮巡检 | {now_str}</h1>
                <p style="margin:6px 0 0;font-size:12px;color:#93c5fd;">权益 ${eq:,.2f} | 盈亏 {pnl_pct:+.2f}% | {open_pos}个持仓 | {total_t}笔交易</p>
            </div>
            <div style="padding:20px;">
                <div style="display:flex;gap:10px;margin-bottom:15px;flex-wrap:wrap;">
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid {btc_color};">
                        <div style="font-size:9px;color:#94a3b8;">BTC</div>
                        <div style="font-size:14px;font-weight:900;color:#1e293b;">${btc_price:,.0f}</div>
                        <div style="font-size:10px;color:{btc_color};">{btc_change}</div>
                    </div>
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid #f59e0b;">
                        <div style="font-size:9px;color:#94a3b8;">恐贪指数</div>
                        <div style="font-size:14px;font-weight:900;color:#f59e0b;">{fng_val}</div>
                        <div style="font-size:10px;color:#64748b;">{fng_label}</div>
                    </div>
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid {pnl_color};">
                        <div style="font-size:9px;color:#94a3b8;">权益/盈亏</div>
                        <div style="font-size:14px;font-weight:900;color:{pnl_color};">${eq:,.0f}</div>
                        <div style="font-size:10px;color:{pnl_color};">{pnl_pct:+.2f}%</div>
                    </div>
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid {risk_color};">
                        <div style="font-size:9px;color:#94a3b8;">风控/回撤</div>
                        <div style="font-size:14px;font-weight:900;color:{risk_color};">{risk_text}</div>
                        <div style="font-size:10px;color:#64748b;">{dd_pct:.2f}%</div>
                    </div>
                </div>
                <div style="display:flex;gap:10px;margin-bottom:15px;flex-wrap:wrap;">
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid #6366f1;">
                        <div style="font-size:9px;color:#94a3b8;">ML模型</div>
                        <div style="font-size:14px;font-weight:900;color:#6366f1;">{ml_acc_str}</div>
                        <div style="font-size:10px;color:#64748b;">F1: {ml_f1_str}</div>
                    </div>
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid #f59e0b;">
                        <div style="font-size:9px;color:#94a3b8;">胜率/交易</div>
                        <div style="font-size:14px;font-weight:900;color:#f59e0b;">{wr_str}</div>
                        <div style="font-size:10px;color:#64748b;">{total_t}笔 / {open_pos}持仓</div>
                    </div>
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid #10b981;">
                        <div style="font-size:9px;color:#94a3b8;">市场环境</div>
                        <div style="font-size:14px;font-weight:900;color:#10b981;">{regime_cn}</div>
                        <div style="font-size:10px;color:#64748b;">扫描{market.get('total_scanned',0)}标的</div>
                    </div>
                    <div style="flex:1;min-width:100px;background:#f8fafc;padding:12px;border-radius:8px;text-align:center;border-left:4px solid #8b5cf6;">
                        <div style="font-size:9px;color:#94a3b8;">知识库</div>
                        <div style="font-size:14px;font-weight:900;color:#8b5cf6;">{memory.get('patterns',0)}</div>
                        <div style="font-size:10px;color:#64748b;">{memory.get('insights',0)}洞察 {memory.get('rules',0)}规则</div>
                    </div>
                </div>

                <div style="margin-top:15px;background:linear-gradient(135deg,#0c4a6e,#1e3a5f);border-radius:8px;padding:15px;color:#fff;">
                    <h3 style="margin:0 0 10px;font-size:14px;color:#fbbf24;letter-spacing:1px;">PERFORMANCE ANALYTICS | 华尔街绩效面板</h3>
                    <div style="display:flex;gap:8px;flex-wrap:wrap;">
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">SHARPE RATIO</div>
                            <div style="font-size:18px;font-weight:900;color:{'#4ade80' if ws['sharpe']>=1 else '#fbbf24' if ws['sharpe']>=0 else '#f87171'};">{ws['sharpe']}</div>
                            <div style="font-size:8px;color:#94a3b8;">{'优秀' if ws['sharpe']>=2 else '良好' if ws['sharpe']>=1 else '一般' if ws['sharpe']>=0 else '亏损'}</div>
                        </div>
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">SORTINO RATIO</div>
                            <div style="font-size:18px;font-weight:900;color:{'#4ade80' if ws['sortino']>=1.5 else '#fbbf24' if ws['sortino']>=0 else '#f87171'};">{ws['sortino']}</div>
                            <div style="font-size:8px;color:#94a3b8;">{'优秀' if ws['sortino']>=3 else '良好' if ws['sortino']>=1.5 else '一般' if ws['sortino']>=0 else '亏损'}</div>
                        </div>
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">CALMAR RATIO</div>
                            <div style="font-size:18px;font-weight:900;color:{'#4ade80' if ws['calmar']>=1 else '#fbbf24' if ws['calmar']>=0.5 else '#f87171'};">{ws['calmar']}</div>
                            <div style="font-size:8px;color:#94a3b8;">目标>1.0</div>
                        </div>
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">PROFIT FACTOR</div>
                            <div style="font-size:18px;font-weight:900;color:{'#4ade80' if ws['profit_factor']>=1.5 else '#fbbf24' if ws['profit_factor']>=1 else '#f87171'};">{ws['profit_factor']}</div>
                            <div style="font-size:8px;color:#94a3b8;">目标>1.5</div>
                        </div>
                    </div>
                    <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">ANNUAL RETURN</div>
                            <div style="font-size:16px;font-weight:900;color:{'#4ade80' if ws['annualized_return_pct']>=0 else '#f87171'};">{ws['annualized_return_pct']:+.1f}%</div>
                            <div style="font-size:8px;color:#94a3b8;">目标≥12%</div>
                        </div>
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">MAX DRAWDOWN</div>
                            <div style="font-size:16px;font-weight:900;color:{'#4ade80' if ws['max_drawdown_pct']<5 else '#fbbf24' if ws['max_drawdown_pct']<8 else '#f87171'};">{ws['max_drawdown_pct']:.1f}%</div>
                            <div style="font-size:8px;color:#94a3b8;">上限8%</div>
                        </div>
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">EXPECTANCY</div>
                            <div style="font-size:16px;font-weight:900;color:{'#4ade80' if ws['expectancy']>0 else '#f87171'};">{ws['expectancy']:+.3f}%</div>
                            <div style="font-size:8px;color:#94a3b8;">每笔期望</div>
                        </div>
                        <div style="flex:1;min-width:90px;background:rgba(255,255,255,0.08);padding:10px;border-radius:6px;text-align:center;">
                            <div style="font-size:8px;color:#93c5fd;letter-spacing:1px;">RISK/REWARD</div>
                            <div style="font-size:16px;font-weight:900;color:{'#4ade80' if ws['risk_reward_ratio']>=1.5 else '#fbbf24' if ws['risk_reward_ratio']>=1 else '#f87171'};">{ws['risk_reward_ratio']}</div>
                            <div style="font-size:8px;color:#94a3b8;">盈亏比</div>
                        </div>
                    </div>
                    <div style="margin-top:8px;font-size:10px;color:#94a3b8;text-align:center;">
                        {ws['total_trades']}笔交易 | W{ws['winning_trades']}/L{ws['losing_trades']} | 最佳{ws['best_trade']:+.1f}% | 最差{ws['worst_trade']:+.1f}% | 年化波动{ws['volatility_annual']:.1f}% | 均持{ws['avg_holding_hours']:.0f}h | 连胜{ws['consecutive_wins_max']}/连亏{ws['consecutive_losses_max']}
                    </div>
                </div>

                {pending_html}
                {positions_html}
                {recent_trades_html}
                {training_html}
                {actions_html}
                {blocked_html}
                {error_html}

                <div style="margin-top:15px;background:#f0fdf4;border-radius:8px;padding:12px;">
                    <h3 style="margin:0 0 5px;font-size:13px;color:#166534;">各部门状态汇总</h3>
                    <div style="font-size:11px;color:#374151;">
                        风控部: {'🟢' if risk.get('status')=='ok' else '🟡' if risk.get('status')=='warning' else '🔴'} {risk_text}
                        {'| '+'; '.join(risk.get('issues',[])) if risk.get('issues') else ''}
                        <br>AI智能部: {'🟢' if ml.get('status')=='ok' else '🟡'} 准确率{ml_acc_str}
                        {'| '+'; '.join(ml.get('issues',[])) if ml.get('issues') else ''}
                        <br>交易部: {'🟢' if trades.get('status')=='ok' else '🟡'} 胜率{wr_str}
                        {'| '+'; '.join(trades.get('issues',[])) if trades.get('issues') else ''}
                        <br>战略部: 🟢 环境={regime_cn}
                        <br>学习部: 🟢 {memory.get('patterns',0)}模式 {memory.get('insights',0)}洞察
                    </div>
                </div>
            </div>
            <div style="background:#f8fafc;padding:12px;text-align:center;font-size:10px;color:#94a3b8;border-top:1px solid #f1f5f9;">
                Titan AutoPilot | 巡检 #{self.cycle_count} | {now_str} | 运行{(time.time()-(self.start_time or time.time()))/3600:.1f}h
            </div>
        </div>
        </body></html>"""

        msg = MIMEText(body, 'html', 'utf-8')
        pending_count = len([x for x in self.pending_ceo_decisions if not x.get("resolved")])
        subject_prefix = "[!] " if pending_count > 0 else ""
        eq_short = f"${eq:,.0f}" if eq > 0 else "N/A"
        msg['Subject'] = Header(f"{subject_prefix}Titan运营报告 #{self.cycle_count} | {eq_short} | {wr_str} | {now_str}", 'utf-8')
        msg['From'] = sender
        msg['To'] = ', '.join(receivers)

        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, receivers, msg.as_string())
            logger.info(f"运营邮件已发送至{len(receivers)}个收件人")
            return True
        except Exception as e:
            logger.error(f"运营邮件发送失败: {e}")
            return False

    def record_blocked_trade(self, symbol, direction, reason, score=0, ml_conf=0):
        now = self.get_now()
        self.blocked_trades.append({
            "time": now.isoformat(),
            "symbol": symbol,
            "direction": direction,
            "reason": reason,
            "score": score,
            "ml_confidence": ml_conf,
        })
        self.blocked_trades = self.blocked_trades[-200:]

    async def run_cyclic_training(self, modules, max_iterations=6, time_budget_hours=5.5):
        self.training_status = {"running": True, "iteration": 0, "results": [], "start_time": time.time()}
        self._save_state()
        logger.info(f"=== 循环深度训练启动: 最多{max_iterations}轮, 预算{time_budget_hours}h ===")

        deep_evolution = modules.get("deep_evolution")
        if not deep_evolution:
            logger.error("DeepEvolution模块未找到")
            self.training_status["running"] = False
            self._save_state()
            return

        start = time.time()
        for i in range(max_iterations):
            elapsed_hours = (time.time() - start) / 3600
            if elapsed_hours >= time_budget_hours:
                logger.info(f"时间预算用完({elapsed_hours:.1f}h), 停止训练")
                break

            self.training_status["iteration"] = i + 1
            self._save_state()
            logger.info(f"--- 循环训练第{i+1}/{max_iterations}轮 ---")

            try:
                result = await deep_evolution.run_full_pipeline(start_step=(i % 6) + 1)

                iter_result = {
                    "iteration": i + 1,
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_hours": round(elapsed_hours, 2),
                }

                ml_r = result.get("ml_engine", {})
                if ml_r.get("status") == "ok":
                    iter_result["accuracy"] = ml_r.get("accuracy")
                    iter_result["f1"] = ml_r.get("f1")

                mc_r = result.get("monte_carlo", {})
                if mc_r.get("status") == "ok":
                    iter_result["calmar"] = mc_r.get("best_calmar")
                    iter_result["sharpe"] = mc_r.get("best_sharpe")

                mb_r = result.get("mega_backtest", {})
                if mb_r.get("status") == "ok":
                    iter_result["mega_calmar"] = mb_r.get("best_calmar")

                self.training_status["results"].append(iter_result)
                self._save_state()
                logger.info(f"第{i+1}轮训练完成: {json.dumps(iter_result, ensure_ascii=False)[:200]}")

            except Exception as e:
                logger.error(f"第{i+1}轮训练异常: {e}")
                self.training_status["results"].append({
                    "iteration": i + 1,
                    "error": str(e)[:200],
                    "timestamp": datetime.now().isoformat(),
                })
                self._save_state()

            await asyncio.sleep(30)

        self.training_status["running"] = False
        self.training_status["end_time"] = time.time()
        total_time = (time.time() - start) / 3600
        logger.info(f"=== 循环训练完成: {self.training_status['iteration']}轮, 耗时{total_time:.1f}h ===")

        try:
            self._send_training_complete_email(modules)
        except Exception as e:
            logger.error(f"训练完成邮件发送失败: {e}")

        self._save_state()

    def _send_training_complete_email(self, modules):
        sender = os.getenv('SENDER_EMAIL')
        password = os.getenv('SENDER_PASSWORD')
        receivers = []
        r1 = os.getenv('RECEIVER_EMAIL')
        r2 = os.getenv('RECEIVER_EMAIL_2')
        if r1: receivers.append(r1)
        if r2: receivers.append(r2)
        if not sender or not password or not receivers:
            return

        now = self.get_now()
        ts = self.training_status
        total_iters = ts.get("iteration", 0)
        results = ts.get("results", [])

        results_rows = ""
        for r in results:
            results_rows += f"""
            <tr style="font-size:12px;border-bottom:1px solid #e2e8f0;">
                <td style="padding:8px;font-weight:bold;">第{r.get('iteration',0)}轮</td>
                <td style="padding:8px;">{r.get('accuracy','N/A')}%</td>
                <td style="padding:8px;">{r.get('mega_calmar','N/A')}</td>
                <td style="padding:8px;">{r.get('calmar','N/A')}</td>
                <td style="padding:8px;">{r.get('sharpe','N/A')}</td>
                <td style="padding:8px;font-size:10px;">{r.get('error','') if r.get('error') else '✅'}</td>
            </tr>"""

        body = f"""
        <html><body style="margin:0;padding:20px;background:#f1f5f9;font-family:sans-serif;">
        <div style="max-width:700px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;">
            <div style="background:linear-gradient(135deg,#059669,#10b981);padding:25px;color:#fff;">
                <div style="font-size:10px;font-weight:800;letter-spacing:2px;color:#fbbf24;">TITAN DEEP TRAINING COMPLETE</div>
                <h1 style="margin:5px 0 0;font-size:20px;">循环深度训练完成 | {total_iters}轮</h1>
            </div>
            <div style="padding:20px;">
                <table style="width:100%;border-collapse:collapse;">
                    <tr style="background:#f1f5f9;font-size:11px;"><th style="padding:8px;">轮次</th><th>ML准确率</th><th>Mega Calmar</th><th>MC Calmar</th><th>MC Sharpe</th><th>状态</th></tr>
                    {results_rows}
                </table>
            </div>
            <div style="padding:12px;text-align:center;font-size:10px;color:#94a3b8;">
                {now.strftime('%Y-%m-%d %H:%M')} | Titan AutoPilot 训练报告
            </div>
        </div></body></html>"""

        msg = MIMEText(body, 'html', 'utf-8')
        msg['Subject'] = Header(f"✅ Titan深度训练完成 | {total_iters}轮 | {now.strftime('%H:%M')}", 'utf-8')
        msg['From'] = sender
        msg['To'] = ', '.join(receivers)
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, receivers, msg.as_string())
            logger.info("训练完成邮件已发送")
        except Exception as e:
            logger.error(f"训练完成邮件失败: {e}")

    def get_status(self):
        now = self.get_now()
        current_hour = now.hour

        next_email = None
        for h in sorted(self.EMAIL_HOURS):
            if h > current_hour or (h > self.last_email_hour and current_hour >= h):
                next_email = h
                break
        if next_email is None and self.EMAIL_HOURS:
            next_email = self.EMAIL_HOURS[0]

        next_train = None
        effective_last_train = self.last_training_hour if self.last_training_date == now.strftime("%Y-%m-%d") else -1
        for h in sorted(self.TRAINING_HOURS):
            if h > effective_last_train and h > current_hour:
                next_train = h
                break
            elif h > effective_last_train and h <= current_hour:
                next_train = h
                break
        if next_train is None and self.TRAINING_HOURS:
            next_train = sorted(self.TRAINING_HOURS)[0]

        return {
            "running": self.running,
            "cycle_count": self.cycle_count,
            "cycle_interval_sec": self.CYCLE_INTERVAL,
            "start_time": self.start_time,
            "uptime_hours": round((time.time() - self.start_time) / 3600, 2) if self.start_time else 0,
            "pending_ceo_decisions": len([x for x in self.pending_ceo_decisions if not x.get("resolved")]),
            "ceo_decisions": self.pending_ceo_decisions,
            "recent_actions": self.actions_taken[-10:],
            "blocked_trades_count": len(self.blocked_trades),
            "recent_blocked": self.blocked_trades[-10:],
            "training_status": self.training_status,
            "last_email_hour": self.last_email_hour,
            "module_reports": self.module_reports[-5:],
            "schedule": {
                "scan_interval_min": self.CYCLE_INTERVAL // 60,
                "email_hours": self.EMAIL_HOURS,
                "email_count_daily": len(self.EMAIL_HOURS),
                "next_email_hour": next_email,
                "training_hours": self.TRAINING_HOURS,
                "training_count_daily": len(self.TRAINING_HOURS),
                "next_training_hour": next_train,
                "last_training_hour": self.last_training_hour,
            },
        }


class TitanSignalGate:
    BLOCKED_CONDITIONS = {
        "adx_strong": "ADX强趋势但胜率0%",
        "vol_surge": "波动率急升胜率仅14%",
    }

    WEAK_CONDITIONS = {
        "adx_weak": "ADX弱趋势胜率31%但亏多",
    }

    MIN_ML_CONFIDENCE = 40
    MIN_SIGNAL_SCORE = 73

    REGIME_STRATEGY_MAP = {
        "trending": ["trend_following", "trend", "grid"],
        "ranging": ["trend_following", "trend", "grid"],
        "volatile": ["trend_following", "trend", "grid"],
        "mixed": ["trend_following", "trend", "grid"],
    }

    MIN_ADX_FOR_TREND = 20
    MIN_RSI_LONG = 30
    MAX_RSI_LONG = 72
    MIN_RSI_SHORT = 28
    MAX_RSI_SHORT = 70

    @staticmethod
    def should_allow(signal: dict, regime: str, strategy: str, ml_confidence: float,
                     signal_score: float, report: dict = None, autopilot=None,
                     min_score_override: float = None) -> tuple:

        reasons = []
        sig_report = report or signal.get("report", {})
        adx = sig_report.get("adx", 20) if sig_report else 20
        rsi = sig_report.get("rsi", 50) if sig_report else 50
        direction = signal.get("direction", "long")

        vol_ratio = sig_report.get("volume_ratio", 1.0) if sig_report else 1.0
        atr_ratio = sig_report.get("atr_ratio", 0.02) if sig_report else 0.02
        if vol_ratio > 4.0 and atr_ratio > 0.08:
            reason = f"拦截: 极端波动 (vol_ratio={vol_ratio:.1f}, atr_ratio={atr_ratio:.3f})"
            reasons.append(reason)

        if strategy in ("trend_following", "trend"):
            regime_cn = {"ranging": "震荡", "volatile": "高波动", "mixed": "混合", "trending": "趋势"}.get(regime, regime)
            if regime in ("ranging",) and signal_score < 74:
                reason = f"拦截: {regime_cn}环境趋势交易要求评分>=74 (当前{signal_score})"
                reasons.append(reason)
            elif regime == "volatile" and signal_score < 73:
                reason = f"拦截: {regime_cn}环境趋势交易要求评分>=73 (当前{signal_score})"
                reasons.append(reason)
            elif regime == "mixed" and signal_score < 68:
                reason = f"拦截: {regime_cn}环境趋势交易要求评分>=68 (当前{signal_score})"
                reasons.append(reason)
        else:
            allowed_strategies = TitanSignalGate.REGIME_STRATEGY_MAP.get(regime, ["trend_following", "trend", "grid"])
            if strategy and strategy not in allowed_strategies:
                strategy_cn = {"trend_following": "趋势跟踪", "range_harvester": "区间收割", "grid": "网格"}.get(strategy, strategy)
                regime_cn = {"ranging": "震荡", "volatile": "高波动", "mixed": "混合", "trending": "趋势"}.get(regime, regime)
                reason = f"拦截: {strategy_cn}策略不适合{regime_cn}环境"
                reasons.append(reason)

        if direction == "long":
            effective_max_rsi = 82 if regime == "trending" else TitanSignalGate.MAX_RSI_LONG
            if rsi > effective_max_rsi and signal_score < 75:
                reason = f"拦截: 做多RSI过高({rsi:.0f}>{effective_max_rsi}) 追涨风险"
                reasons.append(reason)
            if rsi < TitanSignalGate.MIN_RSI_LONG and adx < 20:
                reason = f"拦截: 做多RSI过低({rsi:.0f}) ADX弱({adx:.0f}) 下跌趋势"
                reasons.append(reason)
        elif direction == "short":
            if rsi < TitanSignalGate.MIN_RSI_SHORT and signal_score < 75:
                reason = f"拦截: 做空RSI过低({rsi:.0f}<{TitanSignalGate.MIN_RSI_SHORT}) 追空风险"
                reasons.append(reason)
            if rsi > TitanSignalGate.MAX_RSI_SHORT and adx < 20:
                reason = f"拦截: 做空RSI过高({rsi:.0f}) ADX弱({adx:.0f}) 上涨趋势不宜空"
                reasons.append(reason)

        effective_min_score = min_score_override if min_score_override is not None else TitanSignalGate.MIN_SIGNAL_SCORE
        if signal_score < effective_min_score:
            reason = f"拦截: 信号评分{signal_score}<{effective_min_score}最低门槛"
            reasons.append(reason)

        if ml_confidence > 0 and ml_confidence < TitanSignalGate.MIN_ML_CONFIDENCE:
            reason = f"拦截: ML置信度{ml_confidence:.0f}%<{TitanSignalGate.MIN_ML_CONFIDENCE}%最低门槛"
            reasons.append(reason)

        if reasons and autopilot:
            sym = signal.get("symbol", "?")
            autopilot.record_blocked_trade(sym, direction, "; ".join(reasons), signal_score, ml_confidence)

        return (len(reasons) == 0, reasons)
