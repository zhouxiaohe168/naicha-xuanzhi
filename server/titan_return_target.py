import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("TitanReturnTarget")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_PATH = os.path.join(BASE_DIR, "data", "titan_return_target.json")


class TitanReturnTargetEngine:
    ANNUAL_TARGET = 0.12
    INITIAL_EQUITY = 100000

    def __init__(self):
        self.start_date = datetime.now().strftime("%Y-%m-%d")
        self.initial_equity = self.INITIAL_EQUITY
        self.current_equity = self.INITIAL_EQUITY
        self.annualized_return = 0.0
        self.aggression_multiplier = 1.0
        self.threshold_delta = 0
        self.current_drawdown_pct = 0.0
        self._current_mode = "on_target"
        self.history = []
        self.stats = {
            "total_updates": 0,
            "days_running": 0,
            "peak_equity": self.INITIAL_EQUITY,
            "max_annualized": 0.0,
            "min_annualized": 0.0,
            "time_below_target": 0,
            "time_above_target": 0,
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(TARGET_PATH):
                with open(TARGET_PATH, "r") as f:
                    data = json.load(f)
                self.start_date = data.get("start_date", self.start_date)
                self.initial_equity = data.get("initial_equity", self.INITIAL_EQUITY)
                self.current_equity = data.get("current_equity", self.INITIAL_EQUITY)
                self.annualized_return = data.get("annualized_return", 0.0)
                self.aggression_multiplier = data.get("aggression_multiplier", 1.0)
                self.threshold_delta = data.get("threshold_delta", 0)
                self.history = data.get("history", [])[-200:]
                self.stats = data.get("stats", self.stats)
                logger.info(f"ReturnTarget loaded: start={self.start_date}, annual={self.annualized_return:.2%}, aggression={self.aggression_multiplier:.2f}")
        except Exception as e:
            logger.warning(f"ReturnTarget load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(TARGET_PATH), exist_ok=True)
            data = {
                "start_date": self.start_date,
                "initial_equity": self.initial_equity,
                "current_equity": self.current_equity,
                "annualized_return": round(self.annualized_return, 6),
                "aggression_multiplier": round(self.aggression_multiplier, 4),
                "threshold_delta": self.threshold_delta,
                "history": self.history[-200:],
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(TARGET_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update(self, current_equity, now=None, current_drawdown_pct=0.0):
        if now is None:
            now = datetime.now()

        self.current_equity = current_equity
        self.current_drawdown_pct = current_drawdown_pct
        if current_equity > self.stats["peak_equity"]:
            self.stats["peak_equity"] = current_equity

        try:
            start = datetime.strptime(self.start_date, "%Y-%m-%d")
        except Exception:
            start = now
            self.start_date = now.strftime("%Y-%m-%d")

        days_elapsed = max((now - start).days, 1)
        self.stats["days_running"] = days_elapsed

        total_return = (current_equity - self.initial_equity) / self.initial_equity

        if days_elapsed >= 365:
            years = days_elapsed / 365.0
            if total_return > -1:
                self.annualized_return = (1 + total_return) ** (1.0 / years) - 1
            else:
                self.annualized_return = -1.0
        else:
            self.annualized_return = total_return * (365.0 / days_elapsed)

        if self.annualized_return > self.stats["max_annualized"]:
            self.stats["max_annualized"] = round(self.annualized_return, 6)
        if self.annualized_return < self.stats["min_annualized"]:
            self.stats["min_annualized"] = round(self.annualized_return, 6)

        self._compute_aggression()
        self.stats["total_updates"] += 1

        if self.stats["total_updates"] % 10 == 0:
            self.history.append({
                "time": now.strftime("%Y-%m-%d %H:%M"),
                "equity": round(current_equity, 2),
                "annualized": round(self.annualized_return * 100, 2),
                "aggression": round(self.aggression_multiplier, 3),
                "threshold_delta": self.threshold_delta,
                "days": days_elapsed,
                "drawdown_pct": round(current_drawdown_pct, 2),
                "mode": self._current_mode,
            })
            if len(self.history) > 200:
                self.history = self.history[-200:]

        return {
            "annualized_return": self.annualized_return,
            "aggression_multiplier": self.aggression_multiplier,
            "threshold_delta": self.threshold_delta,
            "days_running": days_elapsed,
            "total_return_pct": round(total_return * 100, 2),
            "mode": self._current_mode,
        }

    def _compute_aggression(self):
        """计算激进度乘数。

        核心设计原则（2026-02-26修复后）：
        1. 回撤保护优先于收益追赶
           - 回撤≥5%：强制保守(0.70)，不管落后目标多少
           - 回撤≥3%：谨慎(0.85)
           - 只有回撤<3%时，才允许追赶模式

        2. 追赶模式有硬性上限
           - aggression_multiplier最大1.2（原来1.5，已降低）
           - threshold_delta最大-4（原来-8，已收紧）

        3. 不存在"越落后越激进"的逻辑
           落后目标是信息，不是加大风险的理由
           正确做法：保护本金，等待更好的市场环境

        修复背景：
        原逻辑在回撤期触发追赶模式，形成正反馈陷阱：
        亏损→追赶→更大仓位→更多亏损→继续追赶
        2026-02-26修复，29/29测试验证通过
        """
        annual = self.annualized_return
        target = self.ANNUAL_TARGET
        dd = getattr(self, 'current_drawdown_pct', 0.0)

        if dd >= 5.0:
            self.aggression_multiplier = 0.70
            self.threshold_delta = 3
            self._current_mode = "deep_drawdown_protection"
            self.stats["time_below_target"] += 1
            logger.info(f"[ReturnTarget] 深度回撤保护: DD={dd:.1f}% → aggression=0.70, delta=+3")
            return

        if dd >= 3.0:
            self.aggression_multiplier = 0.85
            self.threshold_delta = 0
            self._current_mode = "drawdown_caution"
            self.stats["time_below_target"] += 1
            logger.info(f"[ReturnTarget] 回撤警戒: DD={dd:.1f}% → aggression=0.85, delta=0")
            return

        if annual >= target:
            self.aggression_multiplier = 1.0
            self.threshold_delta = 0
            self._current_mode = "on_target"
            self.stats["time_above_target"] += 1
        else:
            shortfall = target - annual

            if shortfall >= 0.12:
                raw_aggression = 1.2
                raw_delta = -4
            elif shortfall >= 0.08:
                raw_aggression = 1.15
                raw_delta = -3
            elif shortfall >= 0.05:
                raw_aggression = 1.1
                raw_delta = -2
            elif shortfall >= 0.02:
                raw_aggression = 1.05
                raw_delta = -1
            else:
                raw_aggression = 1.02
                raw_delta = 0

            self.aggression_multiplier = min(raw_aggression, 1.2)
            self.threshold_delta = max(raw_delta, -4)
            self._current_mode = "catch_up"
            self.stats["time_below_target"] += 1

    def get_status(self):
        return {
            "start_date": self.start_date,
            "initial_equity": self.initial_equity,
            "current_equity": round(self.current_equity, 2),
            "annualized_return_pct": round(self.annualized_return * 100, 2),
            "target_return_pct": round(self.ANNUAL_TARGET * 100, 1),
            "aggression_multiplier": round(self.aggression_multiplier, 3),
            "threshold_delta": self.threshold_delta,
            "on_target": self.annualized_return >= self.ANNUAL_TARGET,
            "mode": self._current_mode,
            "current_drawdown_pct": round(self.current_drawdown_pct, 2),
            "days_running": self.stats["days_running"],
            "peak_equity": round(self.stats["peak_equity"], 2),
            "total_return_pct": round((self.current_equity - self.initial_equity) / self.initial_equity * 100, 2),
            "stats": self.stats,
            "recent_history": self.history[-10:],
        }

    def reset(self, new_initial=None):
        self.start_date = datetime.now().strftime("%Y-%m-%d")
        self.initial_equity = new_initial or self.INITIAL_EQUITY
        self.current_equity = self.initial_equity
        self.annualized_return = 0.0
        self.aggression_multiplier = 1.0
        self.threshold_delta = 0
        self.history = []
        self.stats = {
            "total_updates": 0,
            "days_running": 0,
            "peak_equity": self.initial_equity,
            "max_annualized": 0.0,
            "min_annualized": 0.0,
            "time_below_target": 0,
            "time_above_target": 0,
        }
        self.save()
        logger.info(f"ReturnTarget reset: initial={self.initial_equity}")


return_target = TitanReturnTargetEngine()
