import logging
import time
import json
import os
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanConstitution")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSTITUTION_FILE = os.path.join(BASE_DIR, "data", "titan_constitution.json")


class TitanConstitution:

    RISK_LIMITS = {
        "MAX_DAILY_DRAWDOWN": 0.05,
        "MAX_TOTAL_DRAWDOWN": 0.15,
        "SINGLE_TRADE_RISK": 0.02,
        "MAX_TOTAL_EXPOSURE": 0.60,
        "ONCHAIN_EMERGENCY_THRESHOLD": -0.8,
    }

    EVOLUTION_TRIGGERS = {
        "WEEKLY_LOSS_TRIGGER": 0.03,
        "CONSECUTIVE_LOSS_TRIGGER": 3,
    }

    def __init__(self):
        self.permanent_breaker = False
        self.daily_breaker = False
        self.daily_breaker_until = 0
        self.onchain_emergency = False
        self.total_peak_equity = 100000
        self.daily_start_equity = 100000
        self.weekly_start_equity = 100000
        self.last_daily_reset = 0
        self.last_weekly_reset = 0
        self.evolution_triggered_at = 0
        self.current_dd_pct = 0.0
        self.dd_size_mult = 1.0
        self.dd_level = "normal"
        self._load()

    def _load(self):
        try:
            if os.path.exists(CONSTITUTION_FILE):
                with open(CONSTITUTION_FILE, 'r') as f:
                    data = json.load(f)
                self.permanent_breaker = data.get("permanent_breaker", False)
                self.total_peak_equity = data.get("total_peak_equity", 100000)
                self.daily_start_equity = data.get("daily_start_equity", 100000)
                self.weekly_start_equity = data.get("weekly_start_equity", 100000)
                logger.info(f"宪法状态已恢复: peak={self.total_peak_equity}")
        except Exception as e:
            logger.warning(f"宪法加载失败: {e}")

    def save(self):
        try:
            atomic_json_save(CONSTITUTION_FILE, {
                "permanent_breaker": self.permanent_breaker,
                "total_peak_equity": self.total_peak_equity,
                "daily_start_equity": self.daily_start_equity,
                "weekly_start_equity": self.weekly_start_equity,
                "saved_at": time.time(),
            })
        except Exception:
            pass

    def update_equity(self, current_equity):
        now = time.time()

        if now - self.last_daily_reset > 86400:
            self.daily_start_equity = current_equity
            self.last_daily_reset = now
            self.daily_breaker = False

        if now - self.last_weekly_reset > 604800:
            self.weekly_start_equity = current_equity
            self.last_weekly_reset = now

        if current_equity > self.total_peak_equity:
            self.total_peak_equity = current_equity

        dd_pct = (self.total_peak_equity - current_equity) / (self.total_peak_equity + 1e-10) * 100
        self.current_dd_pct = round(dd_pct, 2)
        self.dd_size_mult, self.dd_level = self.get_drawdown_gradient(current_equity)
        if self.dd_size_mult < 1.0:
            logger.info(f"回撤梯度响应: dd={dd_pct:.1f}% mult={self.dd_size_mult} level={self.dd_level}")

    def check_health(self, current_equity, onchain_score=0, consecutive_losses=0):
        self.update_equity(current_equity)

        status = "HEALTHY"
        actions = []
        can_open_new = True

        total_dd = (self.total_peak_equity - current_equity) / (self.total_peak_equity + 1e-10)
        if total_dd >= self.RISK_LIMITS["MAX_TOTAL_DRAWDOWN"]:
            self.permanent_breaker = True
            status = "DEAD"
            actions.append(f"🚨 总回撤{total_dd*100:.1f}%触发永久熔断，清空所有仓位！")
            can_open_new = False
            self.save()
            return status, actions, can_open_new, True

        daily_dd = (self.daily_start_equity - current_equity) / (self.daily_start_equity + 1e-10)
        if daily_dd >= self.RISK_LIMITS["MAX_DAILY_DRAWDOWN"]:
            self.daily_breaker = True
            self.daily_breaker_until = time.time() + 86400
            status = "SICK"
            actions.append(f"⚠️ 单日亏损{daily_dd*100:.1f}%，暂停开新仓24h")
            can_open_new = False

        if self.permanent_breaker:
            status = "DEAD"
            actions.append("🚨 永久熔断已激活，禁止所有交易")
            can_open_new = False
            return status, actions, can_open_new, False

        if self.daily_breaker and time.time() < self.daily_breaker_until:
            can_open_new = False
            if status == "HEALTHY":
                status = "RECOVERING"
            actions.append("⏸️ 单日熔断冷却中，禁止开新仓")

        if onchain_score < self.RISK_LIMITS["ONCHAIN_EMERGENCY_THRESHOLD"]:
            self.onchain_emergency = True
            status = "EMERGENCY"
            actions.append(f"🔴 链上评分{onchain_score:.2f}极度危险，建议立即清仓")
            can_open_new = False
        else:
            self.onchain_emergency = False

        weekly_dd = (self.weekly_start_equity - current_equity) / (self.weekly_start_equity + 1e-10)
        need_evolution = False
        if weekly_dd >= self.EVOLUTION_TRIGGERS["WEEKLY_LOSS_TRIGGER"]:
            need_evolution = True
            actions.append(f"🔄 周亏损{weekly_dd*100:.1f}%，触发亏损驱动进化")

        if consecutive_losses >= self.EVOLUTION_TRIGGERS["CONSECUTIVE_LOSS_TRIGGER"]:
            need_evolution = True
            actions.append(f"🔄 连亏{consecutive_losses}笔，触发参数变异进化")

        force_liquidate = self.onchain_emergency
        self.save()
        return status, actions, can_open_new, force_liquidate

    def can_open_position(self, current_equity, position_value, total_exposure, sl_distance_pct=0.02):
        if self.permanent_breaker:
            return False, "永久熔断已激活"
        if self.daily_breaker and time.time() < self.daily_breaker_until:
            return False, "单日熔断冷却中"

        if total_exposure + position_value > current_equity * self.RISK_LIMITS["MAX_TOTAL_EXPOSURE"]:
            return False, f"总敞口超过{self.RISK_LIMITS['MAX_TOTAL_EXPOSURE']*100:.0f}%上限"

        risk_amount = position_value * sl_distance_pct
        max_risk = current_equity * self.RISK_LIMITS["SINGLE_TRADE_RISK"]
        if risk_amount > max_risk:
            return False, f"单笔风险${risk_amount:.0f}超过{self.RISK_LIMITS['SINGLE_TRADE_RISK']*100:.0f}%上限(${max_risk:.0f})"

        return True, "通过宪法审查"

    def get_drawdown_gradient(self, current_equity):
        """渐进式回撤响应 - 根据回撤深度返回仓位乘数"""
        if self.total_peak_equity <= 0:
            return 1.0, "normal"

        dd_pct = (self.total_peak_equity - current_equity) / self.total_peak_equity * 100

        if dd_pct < 1.5:
            return 1.0, "normal"
        elif dd_pct < 2.5:
            return 0.85, f"drawdown_gradient_1.5pct(dd={dd_pct:.1f}%)"
        elif dd_pct < 4.5:
            return 0.6, f"drawdown_gradient_2.5pct(dd={dd_pct:.1f}%)"
        elif dd_pct < 6.5:
            return 0.3, f"drawdown_gradient_4.5pct(dd={dd_pct:.1f}%)"
        elif dd_pct < 8.0:
            return 0.0, f"drawdown_freeze(dd={dd_pct:.1f}%)"
        else:
            return 0.0, f"permanent_breaker(dd={dd_pct:.1f}%)"

    def get_status(self):
        daily_active = self.daily_breaker and time.time() < self.daily_breaker_until
        if self.daily_breaker and not daily_active:
            self.daily_breaker = False

        can_open = not self.permanent_breaker and not daily_active and not self.onchain_emergency
        if self.permanent_breaker:
            status = "DEAD"
        elif daily_active:
            status = "RECOVERING"
        elif self.onchain_emergency:
            status = "EMERGENCY"
        else:
            status = "HEALTHY"
        return {
            "status": status,
            "can_open_new": can_open,
            "permanent_breaker": self.permanent_breaker,
            "daily_breaker": daily_active,
            "onchain_emergency": self.onchain_emergency,
            "total_peak_equity": round(self.total_peak_equity, 2),
            "daily_start_equity": round(self.daily_start_equity, 2),
            "weekly_start_equity": round(self.weekly_start_equity, 2),
            "risk_limits": self.RISK_LIMITS,
            "drawdown_gradient": {
                "current_dd_pct": self.current_dd_pct,
                "size_multiplier": self.dd_size_mult,
                "level": self.dd_level,
            },
        }

    def reset_permanent_breaker(self):
        self.permanent_breaker = False
        self.save()
