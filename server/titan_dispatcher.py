import logging
import time
import json
import os
from datetime import datetime
from server.titan_prompt_library import DISPATCHER_PROMPT, PHASE_ZERO_CONTEXT

logger = logging.getLogger("TitanDispatcher")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPATCHER_PATH = os.path.join(BASE_DIR, "data", "titan_dispatcher.json")


class TitanDispatcher:
    STRATEGIES = ["trend", "range", "grid"]
    
    DEFAULT_ALLOCATION = {
        "trend": 0.30,
        "range": 0.35,
        "grid": 0.35,
    }

    def __init__(self):
        self.current_regime = "unknown"
        self.active_strategies = ["trend", "range", "grid"]
        self.allocation = dict(self.DEFAULT_ALLOCATION)
        self.regime_history = []
        self.switch_count = 0
        self.last_switch_time = 0
        self._memory_bank_ref = None
        self.performance_tracker = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(DISPATCHER_PATH):
                with open(DISPATCHER_PATH, "r") as f:
                    data = json.load(f)
                self.current_regime = data.get("current_regime", "unknown")
                self.active_strategies = data.get("active_strategies", ["trend", "range"])
                self.allocation = data.get("allocation", dict(self.DEFAULT_ALLOCATION))
                self.switch_count = data.get("switch_count", 0)
                self.last_switch_time = data.get("last_switch_time", 0)
                self.performance_tracker = data.get("performance_tracker", {})
                self._update_active_strategies()
                logger.info(f"Dispatcher loaded: regime={self.current_regime}, strategies={self.active_strategies}")
        except Exception as e:
            logger.warning(f"Dispatcher load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(DISPATCHER_PATH), exist_ok=True)
            data = {
                "current_regime": self.current_regime,
                "active_strategies": self.active_strategies,
                "allocation": self.allocation,
                "switch_count": self.switch_count,
                "last_switch_time": self.last_switch_time,
                "performance_tracker": self.performance_tracker,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(DISPATCHER_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Dispatcher save failed: {e}")

    def evaluate_regime(self, signals, fng=None):
        if not signals:
            return self.current_regime

        adx_values = []
        atr_ratios = []
        for s in signals:
            regime = s.get("regime", {})
            report = s.get("report", {})
            adx = regime.get("adx", 0) or report.get("adx", 0)
            if adx > 0:
                adx_values.append(adx)
            price = s.get("price", 0)
            atr = report.get("atr", 0) or regime.get("atr", 0)
            if atr > 0 and price > 0:
                atr_ratios.append(atr / price)
            elif price > 0:
                atr_pct = regime.get("atr_percentile", 0)
                if atr_pct > 0:
                    atr_ratios.append(atr_pct / 100.0 * 0.05)

        if not adx_values:
            return self.current_regime

        avg_adx = sum(adx_values) / len(adx_values)
        avg_atr_ratio = sum(atr_ratios) / len(atr_ratios) if atr_ratios else 0.02
        high_adx_pct = sum(1 for a in adx_values if a > 25) / len(adx_values)

        if fng is not None and fng < 20:
            new_regime = "volatile"
            logger.warning(f"⚠️ 极度恐惧(FNG={fng}), 市场环境强制切换为高波动模式")
        elif avg_adx > 30 or high_adx_pct > 0.6:
            new_regime = "trending"
        elif avg_adx < 18 and avg_atr_ratio < 0.04:
            new_regime = "ranging"
        elif avg_atr_ratio > 0.06:
            new_regime = "volatile"
        else:
            new_regime = "mixed"

        if new_regime != self.current_regime:
            cooldown = 300
            if time.time() - self.last_switch_time > cooldown:
                old_regime = self.current_regime
                self.current_regime = new_regime
                self.switch_count += 1
                self.last_switch_time = time.time()
                self._update_active_strategies()
                self.regime_history.append({
                    "from": old_regime,
                    "to": new_regime,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "avg_adx": round(avg_adx, 1),
                    "avg_atr_ratio": round(avg_atr_ratio, 4),
                })
                if len(self.regime_history) > 100:
                    self.regime_history = self.regime_history[-100:]
                self.save()
                logger.info(f"Regime switch: {old_regime} -> {new_regime} (ADX={avg_adx:.1f}, ATR%={avg_atr_ratio:.4f})")
                try:
                    if self._memory_bank_ref:
                        self._memory_bank_ref.record_regime_change(
                            old_regime, new_regime,
                            context={"avg_adx": round(avg_adx, 1), "avg_atr_ratio": round(avg_atr_ratio, 4)}
                        )
                except Exception:
                    pass

        return self.current_regime

    def _update_active_strategies(self):
        regime = self.current_regime
        if regime == "trending":
            self.active_strategies = ["trend", "range", "grid"]
            self.allocation = {"trend": 0.35, "range": 0.30, "grid": 0.35}
        elif regime == "ranging":
            self.active_strategies = ["trend", "range", "grid"]
            self.allocation = {"trend": 0.20, "range": 0.40, "grid": 0.40}
        elif regime == "volatile":
            self.active_strategies = ["trend", "range", "grid"]
            self.allocation = {"trend": 0.20, "range": 0.40, "grid": 0.40}
        else:
            self.active_strategies = ["trend", "range", "grid"]
            self.allocation = {"trend": 0.30, "range": 0.35, "grid": 0.35}
        self._apply_performance_override()

    def _apply_performance_override(self):
        if not self.performance_tracker:
            return
        for strategy in self.STRATEGIES:
            perf = self.performance_tracker.get(strategy, {})
            total = perf.get("wins", 0) + perf.get("losses", 0)
            if total < 5:
                continue
            win_rate = perf["wins"] / total
            if win_rate < 0.25:
                old_alloc = self.allocation.get(strategy, 0)
                self.allocation[strategy] = max(0.05, old_alloc * 0.4)
                logger.info(f"绩效降权: {strategy} WR={win_rate:.1%} 配额{old_alloc:.0%}->{self.allocation[strategy]:.0%}")
            elif win_rate < 0.35:
                old_alloc = self.allocation.get(strategy, 0)
                self.allocation[strategy] = max(0.10, old_alloc * 0.6)
        total_alloc = sum(self.allocation.values())
        if total_alloc > 0 and abs(total_alloc - 1.0) > 0.01:
            for s in self.allocation:
                self.allocation[s] = round(self.allocation[s] / total_alloc, 3)

    def update_performance(self, strategy, result):
        if strategy not in self.performance_tracker:
            self.performance_tracker[strategy] = {"wins": 0, "losses": 0, "pnl": 0}
        if result == "win":
            self.performance_tracker[strategy]["wins"] += 1
        else:
            self.performance_tracker[strategy]["losses"] += 1
        self._apply_performance_override()
        self.save()

    def adjust_allocation_from_attribution(self, attribution_advice):
        if not attribution_advice:
            return
        
        strategy_rec = attribution_advice.get("strategy")
        if not strategy_rec:
            return

        recommended = strategy_rec.get("recommended", "")
        if recommended not in self.STRATEGIES:
            return

        boost = 0.10
        current = self.allocation.get(recommended, 0.33)
        new_val = min(current + boost, 0.60)
        self.allocation[recommended] = new_val

        remaining = 1.0 - new_val
        others = [s for s in self.STRATEGIES if s != recommended]
        for s in others:
            self.allocation[s] = round(remaining / len(others), 3)

        self.save()
        logger.info(f"Allocation adjusted from attribution: {self.allocation}")

    def get_strategy_for_signal(self, signal):
        report = signal.get("report", {})
        adx = report.get("adx", 0) if report else 0
        regime = signal.get("regime", {})
        regime_type = regime.get("type", "未知") if regime else "未知"
        bb_width = report.get("bb_width", 5) if report else 5
        atr_percentile = regime.get("atr_percentile", 50) if regime else 50

        if bb_width < 3 or atr_percentile < 30:
            if "grid" in self.active_strategies and adx < 25:
                return "grid"
            return "trend"

        if adx > 30 and regime_type in ["趋势", "强趋势"]:
            return "trend"
        elif 20 <= adx <= 30:
            return "trend"
        elif adx < 20:
            if "grid" in self.active_strategies:
                return "grid"
            return "trend"
        return "trend"

    def get_capital_for_strategy(self, strategy, total_equity):
        pct = self.allocation.get(strategy, 0.33)
        return total_equity * pct

    def should_activate_grid(self):
        if "grid" not in self.active_strategies:
            return False
        if self.current_regime in ["ranging", "mixed"]:
            return True
        if self.current_regime == "trending":
            grid_alloc = self.allocation.get("grid", 0)
            return grid_alloc >= 0.15
        if self.current_regime == "volatile":
            return self.allocation.get("grid", 0) >= 0.20
        return True

    def ai_analyze_market(self, signals, fng=50, btc_data=None):
        try:
            from server.titan_llm_client import chat_json

            signal_summary = []
            for s in signals[:10]:
                sym = s.get("sym", "?")
                report = s.get("report", {})
                regime = s.get("regime", {})
                signal_summary.append(f"{sym}: ADX={report.get('adx',0):.0f} RSI={report.get('rsi',0):.0f} ATR%={report.get('atr_pct',0):.2f} 趋势={regime.get('type','?')}")

            btc_info = ""
            if btc_data:
                btc_info = f"BTC: ${btc_data.get('price',0):,.0f} 24h变化={btc_data.get('change_pct',0):.1f}%"

            prompt = PHASE_ZERO_CONTEXT + f"""你是加密货币市场分析师。分析当前市场环境，给出策略配置建议。

当前环境: {self.current_regime}
FNG指数: {fng}
{btc_info}

TOP信号概览:
{chr(10).join(signal_summary[:8])}

当前配置: {json.dumps(self.allocation)}
活跃策略: {self.active_strategies}

请用JSON格式回答:
{{
  "market_assessment": "一句话市场评估",
  "regime_confidence": 0-100,
  "recommended_allocation": {{"trend": 0.0-1.0, "range": 0.0-1.0, "grid": 0.0-1.0}},
  "key_risks": ["风险1", "风险2"],
  "opportunities": ["机会1"],
  "trading_advice": "操作建议(30字以内)"
}}"""

            result = chat_json(
                module="dispatcher",
                messages=[
                    {"role": "system", "content": DISPATCHER_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )
            if not result:
                return None
            self._last_ai_analysis = result
            self._last_ai_time = time.time()
            logger.info(f"Dispatcher AI市场分析: {result.get('market_assessment','')}")
            return result
        except Exception as e:
            logger.warning(f"Dispatcher AI分析失败: {e}")
            return None

    def get_status(self):
        ai_analysis = getattr(self, '_last_ai_analysis', None)
        status = {
            "current_regime": self.current_regime,
            "active_strategies": self.active_strategies,
            "allocation": self.allocation,
            "switch_count": self.switch_count,
            "last_switch": datetime.fromtimestamp(self.last_switch_time).strftime("%Y-%m-%d %H:%M:%S") if self.last_switch_time > 0 else "N/A",
            "regime_history": self.regime_history[-10:],
        }
        if ai_analysis:
            status["ai_market_analysis"] = ai_analysis
        return status


dispatcher = TitanDispatcher()
