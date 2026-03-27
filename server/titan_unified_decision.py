import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("TitanUnifiedDecision")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISION_PATH = os.path.join(BASE_DIR, "data", "titan_unified_decision.json")


class TitanUnifiedDecision:
    def __init__(self):
        self.last_decision = {}
        self.decision_log = []
        self.stats = {
            "total_decisions": 0,
            "mode_counts": {"full": 0, "long_only": 0, "defensive": 0, "grid_focus": 0, "no_trade": 0},
            "last_decision_time": "",
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(DECISION_PATH):
                with open(DECISION_PATH, "r") as f:
                    data = json.load(f)
                self.last_decision = data.get("last_decision", {})
                self.decision_log = data.get("decision_log", [])[-50:]
                self.stats = data.get("stats", self.stats)
                logger.info(f"UnifiedDecision loaded: {self.stats['total_decisions']} decisions")
        except Exception as e:
            logger.warning(f"UnifiedDecision load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(DECISION_PATH), exist_ok=True)
            data = {
                "last_decision": self.last_decision,
                "decision_log": self.decision_log[-50:],
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(DECISION_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def evaluate(self, context):
        regime = context.get("regime", "unknown")
        coordinator_recs = context.get("coordinator_recommendations", {})
        constitution_status = context.get("constitution_status", {})
        fng = context.get("fng", 50)
        active_positions = context.get("active_positions", 0)
        active_grids = context.get("active_grids", 0)
        dispatcher_strategies = context.get("dispatcher_strategies", ["trend", "range", "grid"])
        return_target_status = context.get("return_target_status", {})

        throttle = coordinator_recs.get("throttle_level", "normal")
        risk_level = coordinator_recs.get("risk_level", "standard")
        size_mult = coordinator_recs.get("size_multiplier", 1.0)

        max_positions = context.get("max_positions", 10)  # default synced with MAX_POSITIONS in api.py
        if active_positions >= max_positions:
            return self._make_decision(
                mode="no_trade",
                enable_long=False, enable_short=False, enable_grid=False,
                long_threshold=999, short_threshold=999,
                grid_override=False,
                reasons=[f"持仓已达上限{max_positions}笔,等待平仓后再开新仓"],
                context=context
            )

        if constitution_status.get("permanent_breaker") or constitution_status.get("daily_breaker"):
            return self._make_decision(
                mode="no_trade",
                enable_long=False, enable_short=False, enable_grid=False,
                long_threshold=999, short_threshold=999,
                grid_override=False,
                reasons=["宪法熔断触发,暂停所有交易"],
                context=context
            )

        if risk_level == "critical":
            return self._make_decision(
                mode="defensive",
                enable_long=True, enable_short=True, enable_grid=False,
                long_threshold=82, short_threshold=70,
                grid_override=False,
                reasons=[f"严重风控: risk={risk_level}, 高分做多+高分做空对冲"],
                context=context
            )

        if throttle == "emergency":
            em_long_thr = 78
            em_short_thr = 65
            em_grid = True
            em_reasons = [f"紧急风控: throttle={throttle}, 允许做多+做空对冲+网格"]
            cap_util = context.get("capital_utilization", 50)
            if cap_util < 5:
                em_long_thr -= 5
                em_short_thr -= 3
                em_reasons.append(f"资金利用率{cap_util:.1f}%极低,紧急模式下放宽门槛")
            elif cap_util < 10 and active_positions < 3:
                em_long_thr -= 3
                em_reasons.append(f"资金利用率{cap_util:.1f}%过低,适度放宽")
            em_long_thr = max(65, em_long_thr)
            em_short_thr = max(50, em_short_thr)
            return self._make_decision(
                mode="defensive",
                enable_long=True, enable_short=True, enable_grid=em_grid,
                long_threshold=em_long_thr, short_threshold=em_short_thr,
                grid_override=False,
                reasons=em_reasons,
                context=context
            )

        enable_long = True
        enable_short = True
        enable_grid = "grid" in dispatcher_strategies or regime in ("ranging", "mixed", "unknown")
        long_threshold = 75
        short_threshold = 60
        reasons = []
        mode = "full"

        aggression = return_target_status.get("aggression_multiplier", 1.0)
        threshold_delta = return_target_status.get("threshold_delta", 0)
        if threshold_delta != 0:
            long_threshold = max(60, long_threshold + threshold_delta)
            short_threshold = max(40, short_threshold + threshold_delta)
            reasons.append(f"收益引擎: 年化{return_target_status.get('annualized_return_pct', 0):.1f}%"
                           f"{'<' if return_target_status.get('annualized_return_pct', 0) < 12 else '>='}"
                           f"12%目标, 门槛调整{threshold_delta:+d}")

        if regime == "trending":
            enable_long = True
            enable_short = True
            if "trend" not in dispatcher_strategies:
                long_threshold += 5
                reasons.append("趋势市非活跃策略,提高门槛")
            else:
                long_threshold = max(60, long_threshold - 3)
                reasons.append("趋势市+趋势策略活跃,适度放宽做多")

        elif regime == "ranging":
            enable_grid = True
            long_threshold += 3
            reasons.append("震荡市:优先网格+区间,做多门槛提高")

        elif regime == "volatile":
            enable_short = True
            enable_grid = False
            long_threshold += 3
            short_threshold -= 8
            reasons.append("高波动:关闭网格,做多适度提高门槛,做空放宽")

        else:
            reasons.append("混合市况:全模式开启,标准门槛")

        if throttle == "reduced":
            long_threshold += 3
            short_threshold += 5
            reasons.append("协调器降速:提高入场门槛")

        if fng <= 15:
            long_threshold = max(60, long_threshold - 5)
            short_threshold += 8
            reasons.append(f"极度恐惧(FNG={fng}):放宽做多(逆向贪婪),做空门槛提高")
        elif fng <= 25:
            long_threshold = max(62, long_threshold - 3)
            short_threshold += 5
            reasons.append(f"恐惧(FNG={fng}):适度放宽做多,做空门槛提高")
        elif fng >= 85:
            enable_long = True
            long_threshold += 5
            enable_short = True
            short_threshold = max(45, short_threshold - 8)
            reasons.append(f"极度贪婪(FNG={fng}):提高做多门槛,放宽做空")
        elif fng >= 75:
            long_threshold += 3
            short_threshold = max(48, short_threshold - 5)
            reasons.append(f"贪婪(FNG={fng}):适度提高做多门槛,做空适度放宽")

        if active_positions >= 7:
            long_threshold += 5
            short_threshold += 5
            reasons.append(f"持仓数{active_positions}≥7,显著提高新建仓门槛")
        elif active_positions >= 5:
            long_threshold += 3
            short_threshold += 3
            reasons.append(f"持仓数{active_positions}≥5,适度提高新建仓门槛")

        if active_grids >= 5:
            enable_grid = False
            reasons.append(f"活跃网格{active_grids}个已达上限5,暂停新网格")

        if size_mult < 0.5:
            long_threshold += 3
            reasons.append(f"协调器仓位因子{size_mult:.2f}偏低")

        cap_util = context.get("capital_utilization", 50)
        if cap_util < 5:
            if active_positions < 3:
                long_threshold -= 8
            else:
                long_threshold -= 3
            enable_grid = True
            reasons.append(f"资金利用率{cap_util:.1f}%极低,积极寻找入场机会")
        elif cap_util < 10 and active_positions < 3:
            long_threshold -= 5
            short_threshold -= 3
            reasons.append(f"资金利用率{cap_util:.1f}%过低,放宽入场门槛")

        min_long_thr = 65 if active_positions >= 4 else 62
        if throttle == "reduced" and active_positions >= 5:
            min_long_thr = 68
        long_threshold = max(min_long_thr, min(92, long_threshold))
        short_threshold = max(45, min(85, short_threshold))

        if not enable_long and not enable_short and not enable_grid:
            mode = "no_trade"
        elif not enable_short and not enable_grid:
            mode = "long_only"
        elif enable_grid and not enable_long and not enable_short:
            mode = "grid_focus"
        elif not enable_short and enable_grid:
            mode = "long_only"
        elif enable_grid and (enable_long or enable_short):
            mode = "full"
        elif enable_long and enable_short:
            mode = "full"
        elif enable_long and not enable_short:
            mode = "long_only"
        else:
            mode = "defensive"

        if regime == "volatile" and mode not in ("no_trade",) and not enable_short:
            mode = "defensive"
        elif regime == "ranging" and enable_grid:
            mode = "grid_focus"

        return self._make_decision(
            mode=mode,
            enable_long=enable_long, enable_short=enable_short, enable_grid=enable_grid,
            long_threshold=long_threshold, short_threshold=short_threshold,
            grid_override=None,
            reasons=reasons,
            context=context
        )

    def _make_decision(self, mode, enable_long, enable_short, enable_grid,
                       long_threshold, short_threshold, grid_override, reasons, context):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        decision = {
            "mode": mode,
            "enable_long": enable_long,
            "enable_short": enable_short,
            "enable_grid": enable_grid,
            "long_threshold": long_threshold,
            "short_threshold": short_threshold,
            "grid_override": grid_override,
            "reasons": reasons,
            "timestamp": now,
        }

        self.last_decision = decision
        self.stats["total_decisions"] += 1
        self.stats["last_decision_time"] = now
        if mode in self.stats["mode_counts"]:
            self.stats["mode_counts"][mode] += 1

        self.decision_log.append({
            "time": now,
            "mode": mode,
            "long": enable_long, "short": enable_short, "grid": enable_grid,
            "l_thr": long_threshold, "s_thr": short_threshold,
            "regime": context.get("regime", "unknown"),
            "fng": context.get("fng", 50),
            "reasons_short": "; ".join(reasons[:3]),
        })
        if len(self.decision_log) > 50:
            self.decision_log = self.decision_log[-50:]

        if self.stats["total_decisions"] % 5 == 0:
            self.save()

        return decision

    def get_status(self):
        return {
            "last_decision": self.last_decision,
            "stats": self.stats,
            "recent_decisions": self.decision_log[-5:],
        }


unified_decision = TitanUnifiedDecision()
