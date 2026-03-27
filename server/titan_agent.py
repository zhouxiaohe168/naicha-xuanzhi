import os
import json
import time
import logging
from datetime import datetime

logger = logging.getLogger("TitanAgent")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_PATH = os.path.join(BASE_DIR, "data", "titan_memory.json")
GOVERNOR_PATH = os.path.join(BASE_DIR, "data", "titan_governor.json")
FEEDBACK_PATH = os.path.join(BASE_DIR, "data", "titan_feedback.json")


class AgentMemory:
    def __init__(self):
        self.critic_history = []
        self.critic_ban_rules = []
        self.adaptive_weights = {
            "ml_weight": 0.35,
            "rule_weight": 0.65,
            "performance_score": 0.5,
            "predictions": [],
        }
        self.pattern_memory = {}
        self.session_count = 0
        self.total_trades_seen = 0
        self.insights = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(MEMORY_PATH):
                with open(MEMORY_PATH, "r") as f:
                    data = json.load(f)
                self.critic_history = data.get("critic_history", [])
                self.critic_ban_rules = data.get("critic_ban_rules", [])
                self.adaptive_weights = data.get("adaptive_weights", self.adaptive_weights)
                self.pattern_memory = data.get("pattern_memory", {})
                self.session_count = data.get("session_count", 0) + 1
                self.total_trades_seen = data.get("total_trades_seen", 0)
                self.insights = data.get("insights", [])
                logger.info(f"记忆库已加载: {len(self.critic_history)}条交易记录, {len(self.critic_ban_rules)}条禁用规则, 第{self.session_count}次启动")
        except Exception as e:
            logger.warning(f"记忆库加载失败: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)
            data = {
                "critic_history": self.critic_history[-1000:],
                "critic_ban_rules": self.critic_ban_rules,
                "adaptive_weights": {
                    "ml_weight": self.adaptive_weights.get("ml_weight", 0.35),
                    "ml_weight_override": self.adaptive_weights.get("ml_weight_override"),
                    "rule_weight": self.adaptive_weights.get("rule_weight", 0.65),
                    "performance_score": self.adaptive_weights.get("performance_score", 0.5),
                    "predictions": self.adaptive_weights.get("predictions", [])[-200:],
                },
                "pattern_memory": self.pattern_memory,
                "session_count": self.session_count,
                "total_trades_seen": self.total_trades_seen,
                "insights": self.insights[-50:],
                "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(MEMORY_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"记忆库保存失败: {e}")

    def record_pattern(self, pattern_key, outcome):
        if pattern_key not in self.pattern_memory:
            self.pattern_memory[pattern_key] = {"wins": 0, "losses": 0, "total": 0, "last_seen": ""}
        p = self.pattern_memory[pattern_key]
        p["total"] += 1
        if outcome == "win":
            p["wins"] += 1
        else:
            p["losses"] += 1
        p["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        p["win_rate"] = round(p["wins"] / p["total"] * 100, 1) if p["total"] > 0 else 0

    def add_insight(self, insight_text):
        self.insights.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "insight": insight_text,
        })
        if len(self.insights) > 50:
            self.insights = self.insights[-50:]

    def get_pattern_win_rate(self, pattern_key):
        p = self.pattern_memory.get(pattern_key)
        if not p or p["total"] < 5:
            return None
        return p["win_rate"]

    def sync_from_critic(self, critic):
        self.critic_history = list(critic.trade_history)
        self.critic_ban_rules = list(critic.ban_rules)
        self.total_trades_seen = len(self.critic_history)

    def sync_to_critic(self, critic):
        if self.critic_history:
            critic.trade_history = list(self.critic_history)
        if self.critic_ban_rules:
            critic.ban_rules = list(self.critic_ban_rules)
        logger.info(f"记忆恢复到Critic: {len(self.critic_history)}条记录, {len(self.critic_ban_rules)}条规则")

    def sync_from_adaptive(self, adaptive_mgr):
        override = getattr(adaptive_mgr, "ml_weight_override", None)
        self.adaptive_weights["ml_weight_override"] = override
        self.adaptive_weights["ml_weight"] = override if override is not None else 0.35
        self.adaptive_weights["performance_score"] = getattr(adaptive_mgr, "performance_score", 0.5)
        preds = getattr(adaptive_mgr, "ml_predictions", [])
        self.adaptive_weights["predictions"] = preds[-200:] if preds else []

    def sync_to_adaptive(self, adaptive_mgr):
        if self.adaptive_weights.get("predictions"):
            adaptive_mgr.ml_predictions = list(self.adaptive_weights["predictions"])
        score = self.adaptive_weights.get("performance_score", 0.5)
        adaptive_mgr.performance_score = score
        override = self.adaptive_weights.get("ml_weight_override")
        adaptive_mgr.ml_weight_override = override
        logger.info(f"记忆恢复到AdaptiveWeights: score={score} override={override}")

    def get_status(self):
        top_patterns = sorted(
            [(k, v) for k, v in self.pattern_memory.items() if v["total"] >= 5],
            key=lambda x: -x[1]["total"]
        )[:10]
        return {
            "session_count": self.session_count,
            "total_trades_seen": self.total_trades_seen,
            "critic_records": len(self.critic_history),
            "ban_rules": len(self.critic_ban_rules),
            "patterns_tracked": len(self.pattern_memory),
            "insights_count": len(self.insights),
            "recent_insights": self.insights[-5:],
            "top_patterns": [{"pattern": k, **v} for k, v in top_patterns],
            "adaptive_weights": {
                "ml_weight": self.adaptive_weights.get("ml_weight", 0.35),
                "performance_score": self.adaptive_weights.get("performance_score", 0.5),
            },
        }


class StrategyGovernor:
    def __init__(self):
        self.config = {
            "daily_profit_target_pct": 3.0,
            "daily_loss_limit_pct": -5.0,
            "weekly_profit_target_pct": 10.0,
            "weekly_loss_limit_pct": -8.0,
            "max_drawdown_pause_pct": 15.0,
            "consecutive_loss_pause": 5,
            "score_threshold_normal": 78,
            "score_threshold_cautious": 85,
            "score_threshold_aggressive": 72,
            "max_positions": 10,
            "max_positions_cautious": 7,
        }
        self.state = {
            "mode": "normal",
            "daily_pnl_pct": 0.0,
            "weekly_pnl_pct": 0.0,
            "consecutive_losses": 0,
            "peak_equity": 10000,
            "current_equity": 10000,
            "drawdown_pct": 0.0,
            "paused": False,
            "pause_reason": "",
            "action_queue": [],
            "last_mode_change": "",
        }
        self.action_chains = []
        self._load()
        self._sync_system_constants()

    def _sync_system_constants(self):
        self.config["score_threshold_normal"] = 78
        self.config["score_threshold_cautious"] = 85
        self.config["score_threshold_aggressive"] = 72
        self.config["max_positions"] = 10
        self.config["max_positions_cautious"] = 7

    def _load(self):
        try:
            if os.path.exists(GOVERNOR_PATH):
                with open(GOVERNOR_PATH, "r") as f:
                    data = json.load(f)
                saved_config = data.get("config", {})
                for k, v in saved_config.items():
                    if k in self.config:
                        self.config[k] = v
                saved_state = data.get("state", {})
                for k, v in saved_state.items():
                    if k in self.state:
                        self.state[k] = v
                self.action_chains = data.get("action_chains", [])
                logger.info(f"Governor加载: mode={self.state['mode']}, drawdown={self.state['drawdown_pct']}%")
        except Exception as e:
            logger.warning(f"Governor加载失败: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(GOVERNOR_PATH), exist_ok=True)
            data = {
                "config": self.config,
                "state": {k: v for k, v in self.state.items() if k != "action_queue"},
                "action_chains": self.action_chains[-20:],
                "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(GOVERNOR_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Governor保存失败: {e}")

    def update_equity(self, current_equity, daily_pnl_pct=None, weekly_pnl_pct=None):
        self.state["current_equity"] = current_equity
        if current_equity > self.state["peak_equity"]:
            self.state["peak_equity"] = current_equity
        dd = (self.state["peak_equity"] - current_equity) / self.state["peak_equity"] * 100
        self.state["drawdown_pct"] = round(dd, 2)
        if daily_pnl_pct is not None:
            self.state["daily_pnl_pct"] = round(daily_pnl_pct, 2)
        if weekly_pnl_pct is not None:
            self.state["weekly_pnl_pct"] = round(weekly_pnl_pct, 2)
        self._evaluate_mode()

    def record_trade_result(self, is_win):
        if is_win:
            self.state["consecutive_losses"] = 0
        else:
            self.state["consecutive_losses"] += 1
        self._evaluate_mode()

    def _evaluate_mode(self):
        old_mode = self.state["mode"]

        if self.state["drawdown_pct"] >= self.config["max_drawdown_pause_pct"]:
            self.state["paused"] = True
            self.state["pause_reason"] = f"最大回撤{self.state['drawdown_pct']}%超过{self.config['max_drawdown_pause_pct']}%限制"
            self.state["mode"] = "paused"
            self._trigger_chain("max_drawdown_breach")
        elif self.state["daily_pnl_pct"] <= self.config["daily_loss_limit_pct"]:
            self.state["paused"] = True
            self.state["pause_reason"] = f"日亏损{self.state['daily_pnl_pct']}%触及{self.config['daily_loss_limit_pct']}%止损线"
            self.state["mode"] = "paused"
        elif self.state["consecutive_losses"] >= self.config["consecutive_loss_pause"]:
            self.state["mode"] = "cautious"
            self.state["pause_reason"] = f"连续亏损{self.state['consecutive_losses']}次"
            self._trigger_chain("consecutive_losses")
        elif self.state["drawdown_pct"] >= 8.0:
            self.state["mode"] = "cautious"
        elif self.state["daily_pnl_pct"] >= self.config["daily_profit_target_pct"]:
            self.state["mode"] = "conservative"
        elif self.state["drawdown_pct"] < 3.0 and self.state["consecutive_losses"] < 2:
            self.state["mode"] = "normal"
            self.state["paused"] = False
            self.state["pause_reason"] = ""
        else:
            self.state["mode"] = "normal"
            self.state["paused"] = False

        if old_mode != self.state["mode"]:
            self.state["last_mode_change"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            logger.info(f"Governor模式切换: {old_mode} → {self.state['mode']}")

    def _trigger_chain(self, trigger):
        chain_templates = {
            "max_drawdown_breach": [
                {"action": "close_weakest_positions", "desc": "平掉最弱仓位"},
                {"action": "reduce_position_size", "factor": 0.5, "desc": "仓位减半"},
                {"action": "raise_score_threshold", "value": 90, "desc": "提高信号门槛到90"},
                {"action": "wait_stabilize", "bars": 24, "desc": "等待24根K线稳定"},
            ],
            "consecutive_losses": [
                {"action": "reduce_position_size", "factor": 0.7, "desc": "仓位减30%"},
                {"action": "raise_score_threshold", "value": 85, "desc": "提高信号门槛到85"},
                {"action": "skip_low_adx", "threshold": 22, "desc": "跳过ADX<22的信号"},
            ],
            "btc_crash": [
                {"action": "close_all_long", "desc": "平掉所有多头"},
                {"action": "reduce_position_size", "factor": 0.3, "desc": "仓位降至30%"},
                {"action": "wait_stabilize", "bars": 12, "desc": "等待12根K线稳定"},
                {"action": "resume_cautious", "desc": "谨慎模式恢复"},
            ],
        }
        chain = chain_templates.get(trigger, [])
        if chain:
            self.action_chains.append({
                "trigger": trigger,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "actions": chain,
                "status": "triggered",
            })
            self.state["action_queue"] = list(chain)

    def get_trading_params(self):
        mode = self.state["mode"]
        if mode == "paused":
            return {
                "allow_new_trades": False,
                "score_threshold": 999,
                "max_positions": 0,
                "position_size_factor": 0,
                "reason": self.state["pause_reason"],
            }
        elif mode == "cautious":
            return {
                "allow_new_trades": True,
                "score_threshold": self.config["score_threshold_cautious"],
                "max_positions": self.config["max_positions_cautious"],
                "position_size_factor": 0.6,
                "reason": self.state.get("pause_reason", "谨慎模式"),
            }
        elif mode == "conservative":
            return {
                "allow_new_trades": True,
                "score_threshold": self.config["score_threshold_cautious"],
                "max_positions": self.config["max_positions"],
                "position_size_factor": 0.5,
                "reason": f"日盈利{self.state['daily_pnl_pct']}%已达目标,保守运行",
            }
        else:
            return {
                "allow_new_trades": True,
                "score_threshold": self.config["score_threshold_normal"],
                "max_positions": self.config["max_positions"],
                "position_size_factor": 1.0,
                "reason": "正常运行",
            }

    def get_status(self):
        params = self.get_trading_params()
        return {
            "mode": self.state["mode"],
            "paused": self.state["paused"],
            "daily_pnl_pct": self.state["daily_pnl_pct"],
            "weekly_pnl_pct": self.state["weekly_pnl_pct"],
            "drawdown_pct": self.state["drawdown_pct"],
            "consecutive_losses": self.state["consecutive_losses"],
            "peak_equity": self.state["peak_equity"],
            "current_equity": self.state["current_equity"],
            "trading_params": params,
            "last_mode_change": self.state["last_mode_change"],
            "action_chains_total": len(self.action_chains),
            "recent_chains": self.action_chains[-3:],
            "config": self.config,
        }

    def reset_daily(self):
        self.state["daily_pnl_pct"] = 0.0
        if self.state["mode"] == "paused" and self.state["drawdown_pct"] < self.config["max_drawdown_pause_pct"]:
            self.state["paused"] = False
            self.state["mode"] = "normal"
            self.state["pause_reason"] = ""

    def reset_weekly(self):
        self.state["weekly_pnl_pct"] = 0.0


class FeedbackEngine:
    def __init__(self, memory):
        self.memory = memory
        self.accuracy_history = []
        self.threshold_adjustments = {}
        self.max_history = 500
        self._load()

    def _load(self):
        try:
            if os.path.exists(FEEDBACK_PATH):
                with open(FEEDBACK_PATH, "r") as f:
                    data = json.load(f)
                self.accuracy_history = data.get("accuracy_history", [])
                self.threshold_adjustments = data.get("threshold_adjustments", {})
                logger.info(f"反馈引擎已恢复: {len(self.accuracy_history)}条预测记录")
        except Exception as e:
            logger.warning(f"反馈引擎加载失败: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(FEEDBACK_PATH), exist_ok=True)
            data = {
                "accuracy_history": self.accuracy_history[-self.max_history:],
                "threshold_adjustments": self.threshold_adjustments,
                "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_predictions": len(self.accuracy_history),
            }
            with open(FEEDBACK_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"反馈引擎保存失败: {e}")

    def record_prediction_outcome(self, symbol, predicted_label, actual_outcome, features_snapshot=None, direction=None):
        if direction:
            if direction == "long":
                correct = (predicted_label in ("看涨", "bullish", "up") and actual_outcome == "win") or \
                           (predicted_label in ("看跌", "bearish", "down") and actual_outcome == "loss")
            elif direction == "short":
                correct = (predicted_label in ("看跌", "bearish", "down") and actual_outcome == "win") or \
                           (predicted_label in ("看涨", "bullish", "up") and actual_outcome == "loss")
            else:
                correct = predicted_label == actual_outcome
        else:
            bullish_labels = ("看涨", "bullish", "up")
            bearish_labels = ("看跌", "bearish", "down")
            if predicted_label in bullish_labels:
                correct = actual_outcome == "win"
            elif predicted_label in bearish_labels:
                correct = actual_outcome == "loss"
            else:
                correct = actual_outcome == "win"

        self.accuracy_history.append({
            "time": time.time(),
            "symbol": symbol,
            "predicted": predicted_label,
            "actual": actual_outcome,
            "correct": correct,
            "direction": direction,
        })
        if len(self.accuracy_history) > self.max_history:
            self.accuracy_history = self.accuracy_history[-self.max_history:]

        self.save()

        regime = features_snapshot.get("regime", "未知") if features_snapshot else "未知"
        pattern_key = f"{regime}_{predicted_label}"
        self.memory.record_pattern(pattern_key, "win" if correct else "loss")

        if features_snapshot:
            adx_bucket = "high" if features_snapshot.get("adx", 20) > 25 else "low"
            vol_bucket = "high_vol" if features_snapshot.get("vol_ratio", 1.0) > 1.5 else "normal_vol"
            detailed_key = f"{regime}_{adx_bucket}_{vol_bucket}_{predicted_label}"
            self.memory.record_pattern(detailed_key, "win" if correct else "loss")

    def get_rolling_accuracy(self, window=100):
        actionable = [r for r in self.accuracy_history if r.get("actual") in ("win", "loss", "correct", "wrong")]
        if len(actionable) < 5:
            return None
        recent = actionable[-window:]
        correct = sum(1 for r in recent if r.get("correct") or r.get("actual") == "correct")
        return round(correct / len(recent) * 100, 1)

    def get_per_class_accuracy(self, window=100):
        actionable = [r for r in self.accuracy_history if r.get("actual") in ("win", "loss")]
        recent = actionable[-window:]
        classes = {}
        for r in recent:
            pred = r["predicted"]
            if pred not in classes:
                classes[pred] = {"correct": 0, "total": 0}
            classes[pred]["total"] += 1
            if r["correct"]:
                classes[pred]["correct"] += 1
        return {k: round(v["correct"] / v["total"] * 100, 1) if v["total"] > 0 else 0 for k, v in classes.items()}

    def suggest_threshold_adjustments(self):
        suggestions = []
        rolling_acc = self.get_rolling_accuracy()
        if rolling_acc is not None:
            if rolling_acc < 40:
                suggestions.append({
                    "type": "raise_score_threshold",
                    "reason": f"滚动准确率仅{rolling_acc}%，建议提高信号阈值",
                    "value": 85,
                })
                suggestions.append({
                    "type": "increase_ml_weight_caution",
                    "reason": f"ML准确率低，建议降低ML权重",
                    "ml_weight": 0.25,
                })
            elif rolling_acc > 55:
                suggestions.append({
                    "type": "lower_score_threshold",
                    "reason": f"滚动准确率{rolling_acc}%良好，可降低阈值捕获更多机会",
                    "value": 78,
                })
                suggestions.append({
                    "type": "increase_ml_weight",
                    "reason": f"ML表现优秀，建议提高ML权重",
                    "ml_weight": 0.45,
                })

        per_class = self.get_per_class_accuracy()
        for cls, acc in per_class.items():
            if acc < 30:
                suggestions.append({
                    "type": "class_filter",
                    "class": cls,
                    "reason": f"'{cls}'类准确率仅{acc}%，建议过滤该类预测",
                })

        weak_patterns = []
        for pattern_key, stats in self.memory.pattern_memory.items():
            if stats["total"] >= 10 and stats.get("win_rate", 50) < 30:
                weak_patterns.append(pattern_key)
        if weak_patterns:
            suggestions.append({
                "type": "pattern_ban",
                "patterns": weak_patterns[:5],
                "reason": f"发现{len(weak_patterns)}个持续亏损模式",
            })

        return suggestions

    def auto_adjust_critic(self, critic):
        if len(self.accuracy_history) < 50:
            return
        rolling_acc = self.get_rolling_accuracy(50)
        if rolling_acc is not None and rolling_acc < 35:
            weak_patterns = []
            for pattern_key, stats in self.memory.pattern_memory.items():
                if stats["total"] >= 8 and stats.get("win_rate", 50) < 25:
                    parts = pattern_key.split("_")
                    if len(parts) >= 2:
                        regime = parts[0]
                        existing = [r for r in critic.ban_rules if r.get("type") == "feedback_ban" and r.get("pattern") == pattern_key]
                        if not existing:
                            critic.ban_rules.append({
                                "type": "feedback_ban",
                                "pattern": pattern_key,
                                "win_rate": stats["win_rate"],
                                "samples": stats["total"],
                                "reason": f"反馈学习: {pattern_key} 胜率仅{stats['win_rate']}%({stats['total']}次)",
                            })
                            weak_patterns.append(pattern_key)
            if weak_patterns:
                self.memory.add_insight(f"反馈引擎自动添加{len(weak_patterns)}条禁用规则: {weak_patterns[:3]}")
                logger.info(f"反馈引擎: 新增{len(weak_patterns)}条feedback_ban规则")

    def get_status(self):
        rolling_acc = self.get_rolling_accuracy()
        per_class = self.get_per_class_accuracy()
        suggestions = self.suggest_threshold_adjustments()
        return {
            "total_predictions": len(self.accuracy_history),
            "rolling_accuracy": rolling_acc,
            "per_class_accuracy": per_class,
            "suggestions": suggestions,
            "threshold_adjustments": self.threshold_adjustments,
        }


agent_memory = AgentMemory()
governor = StrategyGovernor()
feedback_engine = FeedbackEngine(agent_memory)
