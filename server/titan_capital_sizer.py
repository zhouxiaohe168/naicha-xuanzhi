import os
import json
import math
import logging
import numpy as np
from datetime import datetime, date
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanCapitalSizer")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZER_PATH = os.path.join(BASE_DIR, "data", "titan_capital_sizer.json")
MM_MODEL_PATH = os.path.join(BASE_DIR, "data", "titan_mm_model.pkl")
MM_METRICS_PATH = os.path.join(BASE_DIR, "data", "titan_mm_metrics.json")
MC_STATE_PATH = os.path.join(BASE_DIR, "data", "titan_monte_carlo.json")

REGIME_MAP = {
    'trending': 0, '强趋势': 0, '趋势': 0, 'trending_bull': 0,
    'trending_bear': 1,
    'ranging': 2, '震荡': 2, '窄幅震荡': 2, 'range_low_vol': 2,
    'volatile': 3, '极端波动': 3, 'range_high_vol': 3,
    'crisis': 4,
    'mixed': 2, '过渡': 2, '未知': 2, 'unknown': 2,
}

MC_DEFAULTS = {
    "kelly_fraction": 0.5,
    "max_risk_per_trade": 0.02,
    "max_position_pct": 0.20,
    "drawdown_reduce_trigger": 0.06,
    "drawdown_reduce_factor": 0.5,
    "win_streak_boost": 1.2,
    "loss_streak_cut": 0.5,
    "max_streak_adjust": 4,
    "daily_loss_limit": 0.02,
    "correlation_cap": 0.7,
    "tp_tier1_pct": 0.3,
    "tp_tier1_atr": 1.0,
    "tp_tier2_pct": 0.3,
    "tp_tier2_atr": 2.0,
    "tp_trail_atr": 1.0,
    "pyramid_threshold_atr": 1.5,
    "pyramid_scale": 0.5,
    "max_pyramids": 2,
}


class TitanCapitalSizer:
    def __init__(self):
        self.global_multipliers = {
            "regime_mult": 1.0,
            "performance_mult": 1.0,
            "drawdown_mult": 1.0,
            "signal_quality_mult": 1.0,
            "ai_override_mult": 1.0,
            "return_target_mult": 1.0,
        }
        self.sizing_history = []
        self.stats = {
            "total_sized": 0,
            "avg_position_pct": 0,
            "last_update": "",
            "kelly_fraction_avg": 0,
            "mm_model_active": False,
            "mm_predictions": 0,
        }
        self.mc_params = dict(MC_DEFAULTS)
        self.mc_calmar = 0.0
        self.mc_sharpe = 0.0
        self.mc_loaded = False
        self.daily_pnl = 0.0
        self.daily_pnl_date = ""
        self.mm_model = None
        self.mm_metrics = None
        self.mm_feature_names = ['regime', 'adx', 'atr_pct', 'rsi', 'volatility', 'vol_rank',
                                  'ret_5', 'ret_20', 'drawdown_pct', 'tier']
        self._load()
        self.load_mc_params()
        self.load_mm_model()

    def _load(self):
        try:
            if os.path.exists(SIZER_PATH):
                with open(SIZER_PATH, "r") as f:
                    data = json.load(f)
                self.global_multipliers = data.get("global_multipliers", self.global_multipliers)
                self.stats = data.get("stats", self.stats)
                self.sizing_history = data.get("sizing_history", [])[-100:]
                self.daily_pnl = data.get("daily_pnl", 0.0)
                self.daily_pnl_date = data.get("daily_pnl_date", "")
                logger.info(f"CapitalSizer loaded: {self.stats['total_sized']} sizings")
        except Exception as e:
            logger.warning(f"CapitalSizer load failed: {e}")

    def load_mc_params(self):
        try:
            if os.path.exists(MC_STATE_PATH):
                with open(MC_STATE_PATH, "r") as f:
                    mc_state = json.load(f)
                best = mc_state.get("best_params", {})
                if best:
                    for key in MC_DEFAULTS:
                        if key in best:
                            self.mc_params[key] = best[key]
                    self.mc_calmar = mc_state.get("best_calmar", 0)
                    self.mc_sharpe = mc_state.get("best_sharpe", 0)
                    self.mc_loaded = True
                    logger.info(f"[CapitalSizer] MC宪法层加载成功: kelly={self.mc_params['kelly_fraction']:.4f} "
                                f"maxRisk={self.mc_params['max_risk_per_trade']:.4f} "
                                f"maxPos={self.mc_params['max_position_pct']:.4f} "
                                f"ddTrigger={self.mc_params['drawdown_reduce_trigger']:.4f} "
                                f"dailyLimit={self.mc_params['daily_loss_limit']:.4f} "
                                f"Calmar={self.mc_calmar:.2f} Sharpe={self.mc_sharpe:.2f}")
                else:
                    logger.info("[CapitalSizer] MC状态无best_params, 使用默认值")
            else:
                logger.info("[CapitalSizer] MC状态文件不存在, 使用默认宪法参数")
        except Exception as e:
            logger.warning(f"[CapitalSizer] MC参数加载失败: {e}, 使用默认值")

    def load_mm_model(self):
        try:
            if os.path.exists(MM_MODEL_PATH):
                import joblib
                self.mm_model = joblib.load(MM_MODEL_PATH)
                self.stats["mm_model_active"] = True
                logger.info("[CapitalSizer] MM模型加载成功")

                if os.path.exists(MM_METRICS_PATH):
                    with open(MM_METRICS_PATH, "r") as f:
                        self.mm_metrics = json.load(f)
                    logger.info(f"[CapitalSizer] MM指标: MAE={self.mm_metrics.get('mae')} R2={self.mm_metrics.get('r2')}")
            else:
                self.mm_model = None
                self.stats["mm_model_active"] = False
        except Exception as e:
            logger.warning(f"[CapitalSizer] MM模型加载失败: {e}")
            self.mm_model = None
            self.stats["mm_model_active"] = False

    def predict_mm_size(self, context):
        if self.mm_model is None:
            return None

        try:
            regime_str = context.get("regime", "unknown")
            regime_num = REGIME_MAP.get(regime_str, 2)

            features = np.array([[
                regime_num,
                context.get("adx", 20),
                context.get("atr_pct", 0.02),
                context.get("rsi", 50),
                context.get("volatility", 0.02),
                context.get("vol_rank", 0.5),
                context.get("ret_5", 0),
                context.get("ret_20", 0),
                context.get("drawdown_pct", 0),
                context.get("coin_tier", 2),
            ]], dtype=np.float64)

            np.nan_to_num(features, copy=False, nan=0.0)

            predicted_size = float(self.mm_model.predict(features)[0])
            mc_max = self.mc_params["max_position_pct"]
            predicted_size = max(0.01, min(mc_max, predicted_size))

            self.stats["mm_predictions"] = self.stats.get("mm_predictions", 0) + 1
            return predicted_size

        except Exception as e:
            logger.warning(f"[CapitalSizer] MM预测失败: {e}")
            return None

    def _check_daily_loss(self, equity):
        today = date.today().isoformat()
        if self.daily_pnl_date != today:
            self.daily_pnl = 0.0
            self.daily_pnl_date = today

        limit = self.mc_params["daily_loss_limit"]
        if self.daily_pnl < -(equity * limit):
            return True, limit
        return False, limit

    def record_trade_pnl(self, pnl_amount):
        today = date.today().isoformat()
        if self.daily_pnl_date != today:
            self.daily_pnl = 0.0
            self.daily_pnl_date = today
        self.daily_pnl += pnl_amount
        self.save()

    def save(self):
        try:
            data = {
                "global_multipliers": self.global_multipliers,
                "stats": self.stats,
                "sizing_history": self.sizing_history[-100:],
                "daily_pnl": round(self.daily_pnl, 2),
                "daily_pnl_date": self.daily_pnl_date,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            atomic_json_save(SIZER_PATH, data)
        except Exception:
            pass

    def calculate_position(self, context):
        equity = context.get("equity", 10000)
        signal_score = context.get("signal_score", 0)
        ml_confidence = context.get("ml_confidence", 0)
        atr = context.get("atr", 0)
        price = context.get("price", 0)
        regime = context.get("regime", "unknown")
        strategy = context.get("strategy", "trend")
        fng = context.get("fng", 50)
        win_rate = context.get("win_rate", 0.45)
        payoff_ratio = context.get("payoff_ratio", 1.5)
        consecutive_wins = context.get("consecutive_wins", 0)
        consecutive_losses = context.get("consecutive_losses", 0)
        total_exposure = context.get("total_exposure", 0)
        available_budget = context.get("available_budget", equity)
        signal_quality_score = context.get("signal_quality_score", 0.5)
        synapse_confidence = context.get("synapse_confidence", 1.0)
        adaptive_w_ml = context.get("adaptive_w_ml", 0.35)
        drawdown_pct = context.get("drawdown_pct", 0)
        coin_tier = context.get("coin_tier", 2)

        if equity <= 0 or price <= 0:
            return self._result(0, "资金或价格无效", context)

        daily_blocked, daily_limit = self._check_daily_loss(equity)
        if daily_blocked:
            return self._result(0, f"日亏损已达{daily_limit*100:.2f}%上限(今日PnL={self.daily_pnl:.2f}), 暂停开仓", context)

        kelly_f = self._kelly_fraction(win_rate, payoff_ratio)
        kelly_amount = equity * kelly_f

        mc_max_risk = self.mc_params["max_risk_per_trade"]
        atr_amount = equity * 0.30
        if atr > 0:
            risk_dollar = equity * mc_max_risk
            qty = risk_dollar / (atr * 2.0)
            atr_amount = min(qty * price, equity * 0.30)

        base_amount = min(kelly_amount, atr_amount)

        score_mult = self._score_multiplier(signal_score)
        ml_mult = self._ml_multiplier(ml_confidence, adaptive_w_ml)
        regime_mult = self._regime_multiplier(regime, strategy)
        fng_mult = self._fng_multiplier(fng)
        streak_mult = self._streak_multiplier(consecutive_wins, consecutive_losses)
        sq_mult = self._signal_quality_multiplier(signal_quality_score)
        dd_mult = self._drawdown_multiplier(drawdown_pct)
        synapse_mult = max(0.3, min(1.5, synapse_confidence))
        tier_mult = {1: 1.0, 2: 0.85, 3: 0.55}.get(coin_tier, 0.7)

        signal_group = max(0.2, min(2.0,
            score_mult * ml_mult * sq_mult
        ))
        market_group = max(0.3, min(1.5,
            regime_mult * fng_mult * dd_mult
        ))
        history_group = max(0.4, min(1.3,
            streak_mult * synapse_mult * tier_mult
        ))

        combined_mult = (
            signal_group * 0.50 +
            market_group * 0.30 +
            history_group * 0.20
        )

        combined_mult *= self.global_multipliers.get("ai_override_mult", 1.0)
        combined_mult *= self.global_multipliers.get("return_target_mult", 1.0)

        combined_mult = max(0.1, min(3.0, combined_mult))

        final_amount = base_amount * combined_mult

        mm_predicted = self.predict_mm_size(context)
        mm_source = "rule"
        mm_r2 = self.mm_metrics.get("r2", -1) if self.mm_metrics else -1
        if mm_predicted is not None:
            if mm_r2 < 0.05:
                logger.info(f"[CapitalSizer] MM模型R²={mm_r2:.4f}，低于门槛0.05，跳过ML融合")
                mm_source = "rule_mm_skipped"
            elif mm_r2 < 0.15:
                mm_amount = equity * mm_predicted
                blend_w = 0.10
                final_amount = final_amount * (1 - blend_w) + mm_amount * blend_w
                mm_source = "blended_low_r2"
                logger.info(f"[CapitalSizer] MM模型R²={mm_r2:.4f}偏低，融合权重降至10%")
            else:
                mm_amount = equity * mm_predicted
                blend_w = 0.4
                final_amount = final_amount * (1 - blend_w) + mm_amount * blend_w
                mm_source = "blended"

        corr_cap = self.mc_params["correlation_cap"]
        mc_dd_trigger = self.mc_params["drawdown_reduce_trigger"]
        mc_dd_factor = self.mc_params["drawdown_reduce_factor"]

        if drawdown_pct / 100.0 > mc_dd_trigger:
            max_exposure_pct = corr_cap * mc_dd_factor
        else:
            max_exposure_pct = corr_cap
        max_exposure_pct = max(0.20, min(0.90, max_exposure_pct))

        try:
            from server.titan_trade_judge import trade_judge
            mc_state = {
                "daily_pnl_used_pct": abs(self.daily_pnl) * 100 if self.daily_pnl < 0 else 0,
                "daily_loss_limit": self.mc_params["daily_loss_limit"],
                "current_exposure_pct": total_exposure / max(equity, 1) * 100,
                "exposure_cap_pct": max_exposure_pct * 100,
            }
            cto_directives = None
            try:
                from server.titan_ai_coordinator import ai_coordinator
                cto_directives = ai_coordinator.get_strategic_directives()
            except Exception:
                pass
            judge_result = trade_judge.judge(context, mc_state, final_amount, equity, cto_directives=cto_directives)
            judge_verdict = judge_result.get("verdict", "approve")
            judge_mult = judge_result.get("multiplier", 1.0)

            if judge_verdict == "reject":
                return self._result(0, f"AI审判官否决: {'; '.join(judge_result.get('reasons',[''])[:2])}", context)
            elif judge_verdict == "reduce":
                final_amount *= judge_mult
        except Exception as e:
            logger.warning(f"TradeJudge error (bypassed): {e}")
            judge_result = None

        try:
            import json as _json
            with open(os.path.join(BASE_DIR, "data", "titan_config.json")) as _cf:
                _cfg = _json.load(_cf)
            _cap_cfg = _cfg.get("capital_sizer_hardcap", {})
            HARD_MAX_POSITION_USD = _cap_cfg.get("hard_max_position_usd", 200)
            HARD_MAX_POSITION_PCT = _cap_cfg.get("hard_max_position_pct", 0.10)
        except Exception:
            HARD_MAX_POSITION_USD = 200
            HARD_MAX_POSITION_PCT = 0.10

        mc_max_pos = self.mc_params["max_position_pct"]
        max_single = min(equity * mc_max_pos, HARD_MAX_POSITION_USD, equity * HARD_MAX_POSITION_PCT)
        min_single = min(50, max_single)
        final_amount = max(min_single, min(final_amount, max_single))

        if signal_score > 82:
            final_amount *= 0.5
            logger.info(f"[CapitalSizer] 🔥 过热信号压缩: score={signal_score}>82, 仓位减半→${final_amount:.2f}")

        remaining_capacity = equity * max_exposure_pct - total_exposure
        if remaining_capacity <= 0:
            return self._result(0, f"总敞口已达{max_exposure_pct*100:.0f}%上限(DD={drawdown_pct:.1f}%, MC约束)", context)
        final_amount = min(final_amount, remaining_capacity)

        final_amount = min(final_amount, available_budget)
        if final_amount < 50:
            return self._result(0, "可用预算不足", context)

        self.stats["total_sized"] += 1
        cap_pct = final_amount / equity * 100
        self.stats["avg_position_pct"] = round(
            (self.stats["avg_position_pct"] * (self.stats["total_sized"] - 1) + cap_pct) / self.stats["total_sized"], 2
        )
        self.stats["kelly_fraction_avg"] = round(
            (self.stats["kelly_fraction_avg"] * (self.stats["total_sized"] - 1) + kelly_f) / self.stats["total_sized"], 4
        )
        self.stats["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record = {
            "time": self.stats["last_update"],
            "symbol": context.get("symbol", ""),
            "amount": round(final_amount, 2),
            "cap_pct": round(cap_pct, 2),
            "kelly_f": kelly_f,
            "mm_source": mm_source,
            "mm_predicted": round(mm_predicted * 100, 2) if mm_predicted else None,
            "mc_driven": self.mc_loaded,
            "judge_verdict": judge_result.get("verdict", "n/a") if judge_result else "bypass",
            "judge_score": judge_result.get("score", 0) if judge_result else 0,
            "multipliers": {
                "score": round(score_mult, 3),
                "ml": round(ml_mult, 3),
                "regime": round(regime_mult, 3),
                "fng": round(fng_mult, 3),
                "streak": round(streak_mult, 3),
                "sq": round(sq_mult, 3),
                "dd": round(dd_mult, 3),
                "synapse": round(synapse_mult, 3),
                "tier": round(tier_mult, 3),
                "ai": round(self.global_multipliers.get("ai_override_mult", 1.0), 3),
                "judge": round(judge_result.get("multiplier", 1.0), 3) if judge_result else 1.0,
                "signal_group": round(signal_group, 3),
                "market_group": round(market_group, 3),
                "history_group": round(history_group, 3),
                "combined": round(combined_mult, 3),
                "mm_r2": round(mm_r2, 4),
                "mm_source": mm_source,
            },
        }
        self.sizing_history.append(record)
        if len(self.sizing_history) > 100:
            self.sizing_history = self.sizing_history[-100:]

        if self.stats["total_sized"] % 10 == 0:
            self.save()

        return self._result(round(final_amount, 2), "OK", context, record["multipliers"])

    def _kelly_fraction(self, win_rate, payoff_ratio):
        if win_rate <= 0 or payoff_ratio <= 0:
            return 0.01
        q = 1.0 - win_rate
        kelly = win_rate - (q / payoff_ratio)
        mc_kelly = self.mc_params["kelly_fraction"]
        kelly = max(0.005, min(kelly, 0.25))
        return round(kelly * mc_kelly, 4)

    def _score_multiplier(self, score):
        if score >= 95:
            return 1.8
        elif score >= 90:
            return 1.5
        elif score >= 85:
            return 1.2
        elif score >= 80:
            return 1.0
        elif score >= 70:
            return 0.7
        return 0.5

    def _ml_multiplier(self, ml_conf, w_ml):
        if ml_conf <= 0:
            return 1.0
        if ml_conf >= 80:
            conf_factor = 0.70
        elif ml_conf >= 70:
            conf_factor = 0.85
        elif ml_conf >= 60:
            conf_factor = 1.10
        elif ml_conf >= 50:
            conf_factor = 1.00
        else:
            conf_factor = 0.80
        return conf_factor

    def _regime_multiplier(self, regime, strategy):
        regime_strategy_map = {
            "trending": {"trend": 1.3, "range": 0.6, "grid": 0.7},
            "ranging": {"trend": 0.6, "range": 1.3, "grid": 1.2},
            "volatile": {"trend": 0.7, "range": 0.5, "grid": 0.8},
            "mixed": {"trend": 0.9, "range": 0.9, "grid": 1.0},
        }
        return regime_strategy_map.get(regime, {}).get(strategy, 1.0)

    def _fng_multiplier(self, fng):
        if fng <= 10:
            return 0.5
        elif fng <= 20:
            return 0.7
        elif fng <= 30:
            return 0.85
        elif fng >= 90:
            return 0.55
        elif fng >= 80:
            return 0.65
        elif fng >= 70:
            return 0.85
        return 1.0

    def _streak_multiplier(self, wins, losses):
        mc_boost = self.mc_params["win_streak_boost"]
        mc_cut = self.mc_params["loss_streak_cut"]
        mc_max = int(self.mc_params["max_streak_adjust"])

        if losses > 0:
            ratio = min(losses / mc_max, 1.0)
            return max(mc_cut, 1.0 - ratio * (1.0 - mc_cut))
        elif wins > 0:
            ratio = min(wins / mc_max, 1.0)
            return min(mc_boost, 1.0 + ratio * (mc_boost - 1.0))
        return 1.0

    def _signal_quality_multiplier(self, sq_score):
        if sq_score >= 0.8:
            return 1.4
        elif sq_score >= 0.6:
            return 1.15
        elif sq_score >= 0.4:
            return 1.0
        elif sq_score >= 0.2:
            return 0.7
        return 0.5

    def _drawdown_multiplier(self, dd_pct):
        mc_trigger = self.mc_params["drawdown_reduce_trigger"] * 100
        mc_factor = self.mc_params["drawdown_reduce_factor"]

        if dd_pct >= mc_trigger * 1.5:
            return mc_factor * 0.3
        elif dd_pct >= mc_trigger:
            return mc_factor
        elif dd_pct >= mc_trigger * 0.7:
            blend = (dd_pct - mc_trigger * 0.7) / (mc_trigger * 0.3)
            return 1.0 - blend * (1.0 - mc_factor)
        elif dd_pct >= mc_trigger * 0.3:
            return 0.9
        return 1.0

    def update_global_multipliers(self, key, value):
        if key in self.global_multipliers:
            self.global_multipliers[key] = max(0.1, min(3.0, value))
            self.save()

    def get_tp_params(self):
        return {
            "tp_tier1_pct": self.mc_params.get("tp_tier1_pct", 0.3),
            "tp_tier1_atr": self.mc_params.get("tp_tier1_atr", 1.0),
            "tp_tier2_pct": self.mc_params.get("tp_tier2_pct", 0.3),
            "tp_tier2_atr": self.mc_params.get("tp_tier2_atr", 2.0),
            "tp_trail_atr": self.mc_params.get("tp_trail_atr", 1.0),
            "pyramid_threshold_atr": self.mc_params.get("pyramid_threshold_atr", 1.5),
            "pyramid_scale": self.mc_params.get("pyramid_scale", 0.5),
            "max_pyramids": int(self.mc_params.get("max_pyramids", 2)),
        }

    def _result(self, amount, msg, context, multipliers=None):
        return {
            "amount": amount,
            "message": msg,
            "symbol": context.get("symbol", ""),
            "multipliers": multipliers or {},
        }

    def get_status(self):
        return {
            "total_sized": self.stats["total_sized"],
            "avg_position_pct": self.stats["avg_position_pct"],
            "kelly_fraction_avg": self.stats["kelly_fraction_avg"],
            "last_update": self.stats["last_update"],
            "global_multipliers": self.global_multipliers,
            "recent_sizings": self.sizing_history[-10:],
            "mc_constitution": {
                "loaded": self.mc_loaded,
                "calmar": self.mc_calmar,
                "sharpe": self.mc_sharpe,
                "params": {
                    "kelly_fraction": self.mc_params["kelly_fraction"],
                    "max_risk_per_trade": self.mc_params["max_risk_per_trade"],
                    "max_position_pct": self.mc_params["max_position_pct"],
                    "drawdown_reduce_trigger": self.mc_params["drawdown_reduce_trigger"],
                    "drawdown_reduce_factor": self.mc_params["drawdown_reduce_factor"],
                    "win_streak_boost": self.mc_params["win_streak_boost"],
                    "loss_streak_cut": self.mc_params["loss_streak_cut"],
                    "daily_loss_limit": self.mc_params["daily_loss_limit"],
                    "correlation_cap": self.mc_params["correlation_cap"],
                },
            },
            "daily_pnl": {
                "date": self.daily_pnl_date,
                "pnl": round(self.daily_pnl, 2),
                "limit": self.mc_params["daily_loss_limit"],
            },
            "mm_model": {
                "active": self.mm_model is not None,
                "predictions": self.stats.get("mm_predictions", 0),
                "metrics": {
                    "mae": self.mm_metrics.get("mae") if self.mm_metrics else None,
                    "r2": self.mm_metrics.get("r2") if self.mm_metrics else None,
                    "tier_accuracy": self.mm_metrics.get("tier_accuracy") if self.mm_metrics else None,
                    "last_train": self.mm_metrics.get("last_train") if self.mm_metrics else None,
                } if self.mm_metrics else None,
            },
            "trade_judge": self._get_judge_status(),
        }

    def _get_judge_status(self):
        try:
            from server.titan_trade_judge import trade_judge
            return trade_judge.get_status()
        except Exception:
            return {"stats": {}, "approve_rate": 0, "recent_verdicts": []}


capital_sizer = TitanCapitalSizer()
