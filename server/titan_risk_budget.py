import os
import json
import math
import logging
from datetime import datetime

logger = logging.getLogger("TitanRiskBudget")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RISK_BUDGET_PATH = os.path.join(BASE_DIR, "data", "titan_risk_budget.json")


class TitanRiskBudget:
    def __init__(self, total_capital=10000):
        self.total_capital = total_capital
        self.strategy_budgets = {
            "trend": {"base_pct": 0.40, "current_pct": 0.40, "used": 0, "max_drawdown_pct": 0.03, "current_dd": 0, "frozen": False},
            "range": {"base_pct": 0.30, "current_pct": 0.30, "used": 0, "max_drawdown_pct": 0.025, "current_dd": 0, "frozen": False},
            "grid": {"base_pct": 0.30, "current_pct": 0.30, "used": 0, "max_drawdown_pct": 0.02, "current_dd": 0, "frozen": False},
        }
        self.reserve_pct = 0.10
        self.daily_loss_limit_pct = 0.02
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.peak_capital = total_capital
        self.total_drawdown = 0.0
        self.max_drawdown_ever = 0.0
        self.rebalance_count = 0
        self.last_rebalance = ""
        self.last_daily_reset = ""
        self.history = []
        self._load()
        self._check_daily_reset()

    def _load(self):
        try:
            if os.path.exists(RISK_BUDGET_PATH):
                with open(RISK_BUDGET_PATH, "r") as f:
                    data = json.load(f)
                self.total_capital = data.get("total_capital", self.total_capital)
                self.strategy_budgets = data.get("strategy_budgets", self.strategy_budgets)
                self.daily_pnl = data.get("daily_pnl", 0)
                self.daily_trades = data.get("daily_trades", 0)
                self.peak_capital = data.get("peak_capital", self.total_capital)
                self.total_drawdown = data.get("total_drawdown", 0)
                self.max_drawdown_ever = data.get("max_drawdown_ever", 0)
                self.rebalance_count = data.get("rebalance_count", 0)
                self.last_rebalance = data.get("last_rebalance", "")
                self.last_daily_reset = data.get("last_daily_reset", "")
                self.history = data.get("history", [])
                logger.info(f"RiskBudget loaded: capital={self.total_capital}, dd={self.total_drawdown:.2%}")
        except Exception as e:
            logger.warning(f"RiskBudget load failed: {e}")

    def _check_daily_reset(self):
        today = datetime.now().strftime("%Y-%m-%d")
        if self.last_daily_reset != today:
            self.reset_daily()
            self.last_daily_reset = today
            self.save()
            logger.info(f"RiskBudget daily reset for {today}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(RISK_BUDGET_PATH), exist_ok=True)
            data = {
                "total_capital": self.total_capital,
                "strategy_budgets": self.strategy_budgets,
                "daily_pnl": self.daily_pnl,
                "daily_trades": self.daily_trades,
                "peak_capital": self.peak_capital,
                "total_drawdown": self.total_drawdown,
                "max_drawdown_ever": self.max_drawdown_ever,
                "rebalance_count": self.rebalance_count,
                "last_rebalance": self.last_rebalance,
                "last_daily_reset": self.last_daily_reset,
                "history": self.history[-200:],
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(RISK_BUDGET_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"RiskBudget save failed: {e}")

    def get_available_budget(self, strategy):
        if strategy not in self.strategy_budgets:
            return 0

        budget = self.strategy_budgets[strategy]
        if budget["frozen"]:
            return 0

        if self.daily_pnl < -(self.daily_loss_limit_pct * self.total_capital):
            return 0

        available_capital = self.total_capital * (1 - self.reserve_pct)
        strategy_capital = available_capital * budget["current_pct"]
        remaining = max(0, strategy_capital - budget["used"])
        return round(remaining, 2)

    def request_capital(self, strategy, amount):
        available = self.get_available_budget(strategy)
        if amount > available:
            amount = available
        if amount <= 0:
            return 0

        self.strategy_budgets[strategy]["used"] = round(
            self.strategy_budgets[strategy]["used"] + amount, 2
        )
        self.save()
        return round(amount, 2)

    def release_capital(self, strategy, amount, pnl_usd=0):
        if strategy not in self.strategy_budgets:
            return

        budget = self.strategy_budgets[strategy]
        budget["used"] = max(0, round(budget["used"] - amount, 2))

        self.total_capital = round(self.total_capital + pnl_usd, 2)
        self.daily_pnl = round(self.daily_pnl + pnl_usd, 2)
        self.daily_trades += 1

        if pnl_usd < 0:
            budget["current_dd"] = round(budget["current_dd"] + abs(pnl_usd), 2)
            dd_pct = budget["current_dd"] / (self.total_capital * budget["current_pct"]) if self.total_capital * budget["current_pct"] > 0 else 0
            if dd_pct >= budget["max_drawdown_pct"]:
                budget["frozen"] = True
                logger.warning(f"RiskBudget: {strategy} FROZEN - drawdown {dd_pct:.2%} >= limit {budget['max_drawdown_pct']:.2%}")
        else:
            budget["current_dd"] = max(0, round(budget["current_dd"] - pnl_usd * 0.5, 2))

        if self.total_capital > self.peak_capital:
            self.peak_capital = self.total_capital
        self.total_drawdown = round((self.peak_capital - self.total_capital) / self.peak_capital, 4) if self.peak_capital > 0 else 0
        self.max_drawdown_ever = max(self.max_drawdown_ever, self.total_drawdown)

        self.history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "strategy": strategy,
            "pnl_usd": pnl_usd,
            "capital": self.total_capital,
            "drawdown": self.total_drawdown,
        })

        self.save()

    def rebalance(self, dispatcher_allocation=None, synapse_advice=None,
                  performance_metrics=None, coordinator_advice=None,
                  cooldown_seconds=1800):
        if self.last_rebalance:
            try:
                last_dt = datetime.strptime(self.last_rebalance, "%Y-%m-%d %H:%M:%S")
                elapsed = (datetime.now() - last_dt).total_seconds()
                if elapsed < cooldown_seconds:
                    return
            except (ValueError, TypeError):
                pass

        if dispatcher_allocation:
            total = sum(dispatcher_allocation.values())
            if total > 0:
                for strategy in self.strategy_budgets:
                    if strategy in dispatcher_allocation:
                        new_pct = dispatcher_allocation[strategy] / total
                        old_pct = self.strategy_budgets[strategy]["current_pct"]
                        self.strategy_budgets[strategy]["current_pct"] = round(
                            old_pct * 0.7 + new_pct * 0.3, 4
                        )

        if synapse_advice:
            for strategy, advised_pct in synapse_advice.items():
                if strategy in self.strategy_budgets:
                    current = self.strategy_budgets[strategy]["current_pct"]
                    self.strategy_budgets[strategy]["current_pct"] = round(
                        current * 0.8 + advised_pct * 0.2, 4
                    )

        if performance_metrics:
            ml_acc = performance_metrics.get("ml_accuracy", 0.5)
            rule_wr = performance_metrics.get("rule_win_rate", 0.5)
            sq_avg = performance_metrics.get("signal_quality_avg", 0.5)
            dd = performance_metrics.get("drawdown_pct", 0)

            if dd > 4:
                for s in self.strategy_budgets:
                    self.strategy_budgets[s]["current_pct"] *= 0.85
            elif dd > 2:
                for s in self.strategy_budgets:
                    self.strategy_budgets[s]["current_pct"] *= 0.92

            if ml_acc > 0.6 and "trend" in self.strategy_budgets:
                self.strategy_budgets["trend"]["current_pct"] *= 1.05
            elif ml_acc < 0.4 and "trend" in self.strategy_budgets:
                self.strategy_budgets["trend"]["current_pct"] *= 0.90

            if sq_avg > 0.7:
                for s in self.strategy_budgets:
                    self.strategy_budgets[s]["current_pct"] *= 1.03
            elif sq_avg < 0.3:
                for s in self.strategy_budgets:
                    self.strategy_budgets[s]["current_pct"] *= 0.92

        if coordinator_advice:
            for strategy, pct in coordinator_advice.items():
                if strategy in self.strategy_budgets:
                    current = self.strategy_budgets[strategy]["current_pct"]
                    self.strategy_budgets[strategy]["current_pct"] = round(
                        current * 0.7 + pct * 0.3, 4
                    )

        total_pct = sum(b["current_pct"] for b in self.strategy_budgets.values())
        if total_pct > 0:
            for strategy in self.strategy_budgets:
                self.strategy_budgets[strategy]["current_pct"] = round(
                    self.strategy_budgets[strategy]["current_pct"] / total_pct, 4
                )

        self.rebalance_count += 1
        self.last_rebalance = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()
        parts = [f"{s}={b['current_pct']:.1%}" for s, b in self.strategy_budgets.items()]
        logger.info(f"RiskBudget rebalanced: {', '.join(parts)}")

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.daily_trades = 0
        for budget in self.strategy_budgets.values():
            if budget["frozen"] and budget["current_dd"] < budget["max_drawdown_pct"] * self.total_capital * 0.5:
                budget["frozen"] = False
                budget["current_dd"] = 0
                logger.info(f"RiskBudget: strategy unfrozen after daily reset")
        self.save()

    def unfreeze_strategy(self, strategy):
        if strategy in self.strategy_budgets:
            self.strategy_budgets[strategy]["frozen"] = False
            self.strategy_budgets[strategy]["current_dd"] = 0
            self.save()

    def get_position_size(self, strategy, signal_quality=1.0, risk_per_trade_pct=0.01):
        available = self.get_available_budget(strategy)
        if available <= 0:
            return 0

        quality_mult = max(0.5, min(1.5, signal_quality))
        dd_mult = 1.0
        if self.total_drawdown > 0.04:
            dd_mult = 0.5
        elif self.total_drawdown > 0.02:
            dd_mult = 0.75

        risk_capital = self.total_capital * risk_per_trade_pct * quality_mult * dd_mult
        position = min(risk_capital, available)
        return round(position, 2)

    def get_status(self):
        budgets = {}
        for s, b in self.strategy_budgets.items():
            available = self.get_available_budget(s)
            budgets[s] = {
                "allocation_pct": round(b["current_pct"] * 100, 1),
                "base_pct": round(b["base_pct"] * 100, 1),
                "used": b["used"],
                "available": available,
                "max_dd": round(b["max_drawdown_pct"] * 100, 2),
                "current_dd": b["current_dd"],
                "frozen": b["frozen"],
            }

        daily_limit = round(self.daily_loss_limit_pct * self.total_capital, 2)
        daily_remaining = round(daily_limit + self.daily_pnl, 2)

        return {
            "total_capital": self.total_capital,
            "peak_capital": self.peak_capital,
            "total_drawdown_pct": round(self.total_drawdown * 100, 2),
            "max_drawdown_ever_pct": round(self.max_drawdown_ever * 100, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_trades": self.daily_trades,
            "daily_loss_limit": daily_limit,
            "daily_remaining": max(0, daily_remaining),
            "reserve_pct": round(self.reserve_pct * 100, 1),
            "strategy_budgets": budgets,
            "rebalance_count": self.rebalance_count,
            "last_rebalance": self.last_rebalance,
            "equity_curve": [h["capital"] for h in self.history[-50:]],
        }
