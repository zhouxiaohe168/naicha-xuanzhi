import os
import json
import time
import logging
import asyncio
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, f1_score, classification_report
import lightgbm as lgb

from server.titan_calibration import TitanCalibratedClassifier, apply_triple_barrier_labels
from server.titan_ml_features import TitanFeatureStore
from server.titan_ml_validation import PurgedKFold, WalkForwardCV, compute_feature_importance_mdi, select_features_by_importance
from server.titan_ml_labeling import DynamicTripleBarrier, MetaLabeler, SampleWeighter
from server.titan_ml_regime import TitanMLRegimeDetector
from server.titan_money_manager import TitanMoneyManager, money_manager

try:
    from catboost import CatBoostClassifier as _RawCatBoost
    from sklearn.base import BaseEstimator, ClassifierMixin

    class CatBoostClassifier(BaseEstimator, ClassifierMixin):
        _estimator_type = "classifier"

        def __init__(self, iterations=300, depth=8, learning_rate=0.03,
                     class_weights=None, random_seed=42, verbose=0,
                     l2_leaf_reg=3.0, subsample=0.8, bootstrap_type='Bernoulli'):
            self.iterations = iterations
            self.depth = depth
            self.learning_rate = learning_rate
            self.class_weights = class_weights
            self.random_seed = random_seed
            self.verbose = verbose
            self.l2_leaf_reg = l2_leaf_reg
            self.subsample = subsample
            self.bootstrap_type = bootstrap_type
            self._model = None

        def __sklearn_tags__(self):
            tags = super().__sklearn_tags__()
            tags.estimator_type = 'classifier'
            try:
                from sklearn.utils._tags import ClassifierTags
                tags.classifier_tags = ClassifierTags()
            except ImportError:
                pass
            return tags

        def fit(self, X, y, sample_weight=None, **kwargs):
            self._model = _RawCatBoost(
                iterations=self.iterations, depth=self.depth,
                learning_rate=self.learning_rate, class_weights=self.class_weights,
                random_seed=self.random_seed, verbose=self.verbose,
                l2_leaf_reg=self.l2_leaf_reg, subsample=self.subsample,
                bootstrap_type=self.bootstrap_type,
            )
            self._model.fit(X, y, sample_weight=sample_weight)
            self.classes_ = self._model.classes_
            return self

        def predict(self, X):
            return self._model.predict(X).flatten()

        def predict_proba(self, X):
            return self._model.predict_proba(X)

    HAS_CATBOOST = True
except ImportError:
    HAS_CATBOOST = False

try:
    from xgboost import XGBClassifier
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

logger = logging.getLogger("TitanML")

def _default_external_features():
    return {
        'ext_fng': 50.0, 'ext_btc_netflow': 0.0, 'ext_whale_activity': 0.0,
        'ext_sentiment_global': 0.5, 'ext_btc_sentiment': 0.5,
        'ext_social_volume_norm': 0.0, 'ext_gold_change': 0.0,
        'ext_dxy_change': 0.0, 'ext_spy_change': 0.0, 'ext_risk_mode': 0.0,
        'ext_ob_imbalance': 0.0, 'ext_ob_spread': 0.0,
        'ext_sopr_score': 0.0, 'ext_onchain_composite': 0.0,
    }

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "data", "titan_ml_model.pkl")
METRICS_PATH = os.path.join(BASE_DIR, "data", "titan_ml_metrics.json")
DEEP_TRAIN_FLAG = os.path.join(BASE_DIR, "data", "titan_deep_trained.flag")

ML_CONFIG = {
    'HORIZON_BARS': 4,
    'LABEL_UP_PERCENTILE': 65,
    'LABEL_DOWN_PERCENTILE': 35,
    'RETRAIN_INTERVAL_HOURS': 1,
    'MIN_SAMPLES_TO_TRAIN': 200,
    'HISTORY_BARS': 1000,
    'BLEND_WEIGHT_RULE': 0.65,
    'BLEND_WEIGHT_ML': 0.35,
    'SIDEWAYS_CLASS_WEIGHT': 2.5,
}


class AdaptiveWeightManager:
    def __init__(self):
        self.ml_predictions = []
        self.max_history = 200
        self.ml_weight_override: float | None = None
        self.performance_score = 0.5
        self._last_eval_time = 0

    TIMEFRAME_EVAL_WINDOWS = {
        '15m': 900,
        '1h': 3600,
        '4h': 14400,
        '1d': 86400,
    }

    def record_prediction(self, symbol, price, ml_label, ml_confidence, rule_direction, timeframe='1h'):
        self.ml_predictions.append({
            'time': time.time(),
            'symbol': symbol,
            'entry_price': price,
            'ml_label': ml_label,
            'ml_confidence': ml_confidence,
            'rule_direction': rule_direction,
            'timeframe': timeframe,
            'outcome': None,
            'exit_price': None,
        })
        if len(self.ml_predictions) > self.max_history:
            self.ml_predictions = self.ml_predictions[-self.max_history:]

    def update_outcomes(self, current_prices):
        updated = 0
        for pred in self.ml_predictions:
            if pred['outcome'] is not None:
                continue
            sym = pred['symbol']
            if sym not in current_prices:
                continue
            age = time.time() - pred['time']
            tf = pred.get('timeframe', '1h')
            min_age = self.TIMEFRAME_EVAL_WINDOWS.get(tf, 3600)
            if age < min_age:
                continue
            current = current_prices[sym]
            entry = pred['entry_price']
            if entry <= 0:
                continue
            ret = (current - entry) / entry
            threshold = 0.005 if tf in ('15m', '1h') else 0.01
            if pred['ml_label'] == '看涨':
                pred['outcome'] = 'correct' if ret > threshold else ('wrong' if ret < -threshold else 'neutral')
            elif pred['ml_label'] == '看跌':
                pred['outcome'] = 'correct' if ret < -threshold else ('wrong' if ret > threshold else 'neutral')
            else:
                pred['outcome'] = 'correct' if abs(ret) < threshold * 2 else 'neutral'
            pred['exit_price'] = current
            updated += 1
        return updated

    def evaluate_ml_performance(self):
        evaluated = [p for p in self.ml_predictions if p['outcome'] is not None and p['outcome'] != 'neutral']
        if len(evaluated) < 10:
            self.performance_score = 0.5
            return self.get_adaptive_weights()

        recent = evaluated[-50:]
        correct = sum(1 for p in recent if p['outcome'] == 'correct')
        total = len(recent)
        accuracy = correct / total

        mid_conf = [p for p in recent if 55 <= p['ml_confidence'] <= 70]
        mid_conf_acc = 0
        if len(mid_conf) >= 5:
            mid_conf_acc = sum(1 for p in mid_conf if p['outcome'] == 'correct') / len(mid_conf)

        self.performance_score = accuracy * 0.6 + mid_conf_acc * 0.4 if len(mid_conf) >= 5 else accuracy

        self._last_eval_time = time.time()
        return self.get_adaptive_weights()

    def get_adaptive_weights(self):
        if self.performance_score >= 0.65:
            w_ml = 0.45
            w_rule = 0.55
            tier = "高信任"
        elif self.performance_score >= 0.55:
            w_ml = 0.35
            w_rule = 0.65
            tier = "标准"
        elif self.performance_score >= 0.45:
            w_ml = 0.20
            w_rule = 0.80
            tier = "低信任"
        else:
            w_ml = 0.10
            w_rule = 0.90
            tier = "降级"

        if self.ml_weight_override is not None:
            w_ml = max(0.05, min(0.60, self.ml_weight_override))
            w_rule = 1.0 - w_ml
            tier = f"{tier}(手动覆盖)"

        return {
            'w_rule': w_rule,
            'w_ml': w_ml,
            'tier': tier,
            'performance': round(self.performance_score * 100, 1),
            'evaluated': len([p for p in self.ml_predictions if p['outcome'] is not None]),
            'total_recorded': len(self.ml_predictions),
        }

    def get_dynamic_weights_for_signal(self, ml_confidence):
        base = self.get_adaptive_weights()
        w_ml = base['w_ml']
        if ml_confidence >= 75:
            w_ml = min(0.55, w_ml * 1.3)
        elif ml_confidence >= 60:
            w_ml = w_ml * 1.1
        elif ml_confidence < 40:
            w_ml = w_ml * 0.5
        w_rule = 1.0 - w_ml
        return w_rule, w_ml

    def check_direction_agreement(self, rule_score, ml_label, ml_confidence):
        if ml_confidence < 50:
            return True, "ML低置信-规则主导"

        rule_bullish = rule_score >= 60
        rule_bearish = rule_score <= 40
        ml_bullish = ml_label == "看涨"
        ml_bearish = ml_label == "看跌"

        if ml_bullish and rule_bearish:
            return False, "方向冲突:ML看涨vs规则看空"
        if ml_bearish and rule_bullish:
            return False, "方向冲突:ML看跌vs规则看多"

        return True, "方向一致"

    def get_status(self):
        weights = self.get_adaptive_weights()
        evaluated = [p for p in self.ml_predictions if p['outcome'] is not None]
        correct = sum(1 for p in evaluated if p['outcome'] == 'correct')
        wrong = sum(1 for p in evaluated if p['outcome'] == 'wrong')

        agreements = sum(1 for p in self.ml_predictions if p.get('rule_direction') == p.get('ml_label'))
        conflicts = len(self.ml_predictions) - agreements

        return {
            **weights,
            'ml_correct': correct,
            'ml_wrong': wrong,
            'direction_agreements': agreements,
            'direction_conflicts': conflicts,
        }


adaptive_weights = AdaptiveWeightManager()


class RegimeDetector:
    """Market regime detection engine - determines "weather" conditions"""
    
    @staticmethod
    def detect(d4h_df, d1h_df=None):
        """Returns regime dict with: type, volatility, trend_intensity, action_modifier"""
        try:
            close = d4h_df['c']
            if len(close) < 30:
                return {'type': '未知', 'volatility': 'normal', 'trend_intensity': 0, 'action_modifier': 1.0, 'bb_width': 0, 'adx': 0}
            
            high, low = d4h_df['h'], d4h_df['l']
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            
            plus_dm = high.diff()
            minus_dm = -low.diff()
            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
            plus_di = 100 * (plus_dm.rolling(14).mean() / (atr + 1e-10))
            minus_di = 100 * (minus_dm.rolling(14).mean() / (atr + 1e-10))
            dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
            adx_val = dx.rolling(14).mean().iloc[-1]
            if pd.isna(adx_val):
                adx_val = 20
            
            sma20 = close.rolling(20).mean()
            std20 = close.rolling(20).std()
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            bb_width = ((bb_upper - bb_lower) / (sma20 + 1e-10)).iloc[-1]
            if pd.isna(bb_width):
                bb_width = 0.04
            
            atr_val = atr.iloc[-1]
            price = close.iloc[-1]
            atr_pct = (atr_val / price * 100) if price > 0 else 2.0
            
            atr_series = (atr / close * 100).dropna()
            atr_percentile = (atr_series < atr_pct).mean() * 100 if len(atr_series) > 10 else 50
            
            if adx_val > 30 and bb_width > 0.06:
                regime_type = '强趋势'
                action_modifier = 1.2
                volatility = 'high'
            elif adx_val > 25:
                regime_type = '趋势'
                action_modifier = 1.0
                volatility = 'normal'
            elif adx_val < 18 and bb_width < 0.03:
                regime_type = '窄幅震荡'
                action_modifier = 0.3
                volatility = 'low'
            elif adx_val < 20:
                regime_type = '震荡'
                action_modifier = 0.6
                volatility = 'normal'
            elif atr_percentile > 90:
                regime_type = '极端波动'
                action_modifier = 0.2
                volatility = 'extreme'
            else:
                regime_type = '过渡'
                action_modifier = 0.8
                volatility = 'normal'
            
            trend_intensity = round(float(adx_val), 1)
            
            return {
                'type': regime_type,
                'volatility': volatility,
                'trend_intensity': trend_intensity,
                'action_modifier': round(action_modifier, 2),
                'bb_width': round(float(bb_width * 100), 2),
                'adx': round(float(adx_val), 1),
                'atr_percentile': round(float(atr_percentile), 1),
            }
        except Exception as e:
            logger.warning(f"RegimeDetector异常: {e}")
            return {'type': '未知', 'volatility': 'normal', 'trend_intensity': 0, 'action_modifier': 1.0, 'bb_width': 0, 'adx': 0, 'atr_percentile': 50}

    REGIME_TO_STANDARD = {
        '强趋势': 'trending',
        '趋势': 'trending',
        '震荡': 'ranging',
        '窄幅震荡': 'ranging',
        '极端波动': 'volatile',
        '过渡': 'mixed',
        '未知': 'mixed',
    }

    @staticmethod
    def to_standard(regime_type_cn):
        return RegimeDetector.REGIME_TO_STANDARD.get(regime_type_cn, 'mixed')

    @staticmethod
    def detect_standard(d4h_df, d1h_df=None):
        result = RegimeDetector.detect(d4h_df, d1h_df)
        result['standard'] = RegimeDetector.to_standard(result.get('type', '未知'))
        return result


class TitanCritic:
    """Auto-reviews losing trades and generates ban rules with AI deep analysis"""
    
    def __init__(self):
        self.trade_history = []
        self.ban_rules = []
        self.max_history = 500
        self.review_interval = 50
        self._last_ai_review = None
        self._ai_review_count = 0
    
    def record_trade(self, trade_info):
        """Record completed trade for review"""
        self.trade_history.append({
            'time': time.time(),
            'symbol': trade_info.get('sym', ''),
            'direction': trade_info.get('direction', 'long'),
            'entry': trade_info.get('entry', 0),
            'exit': trade_info.get('exit', 0),
            'pnl': trade_info.get('pnl', 0),
            'result': trade_info.get('result', 'loss'),
            'score': trade_info.get('score', 0),
            'rsi': trade_info.get('rsi', 50),
            'adx': trade_info.get('adx', 20),
            'regime': trade_info.get('regime', '未知'),
            'bb_pos': trade_info.get('bb_pos', 0.5),
            'vol_ratio': trade_info.get('vol_ratio', 1.0),
        })
        if len(self.trade_history) > self.max_history:
            self.trade_history = self.trade_history[-self.max_history:]
        
        if len(self.trade_history) % self.review_interval == 0:
            self._auto_review()
    
    def _auto_review(self):
        """Analyze losing patterns and generate ban rules"""
        if len(self.trade_history) < 20:
            return
        
        losses = [t for t in self.trade_history[-100:] if t['result'] == 'loss']
        wins = [t for t in self.trade_history[-100:] if t['result'] == 'win']
        
        if len(losses) < 5:
            return
        
        new_rules = []
        
        regime_losses = {}
        regime_total = {}
        for t in self.trade_history[-100:]:
            r = t.get('regime', '未知')
            regime_total[r] = regime_total.get(r, 0) + 1
            if t['result'] == 'loss':
                regime_losses[r] = regime_losses.get(r, 0) + 1
        
        for regime, loss_count in regime_losses.items():
            total = regime_total.get(regime, 1)
            loss_rate = loss_count / total
            if loss_rate > 0.7 and total >= 5:
                rule = {'type': 'regime_ban', 'regime': regime, 'loss_rate': round(loss_rate, 2), 'samples': total,
                        'reason': f'{regime}环境亏损率{int(loss_rate*100)}%({loss_count}/{total})'}
                if not any(r.get('regime') == regime for r in self.ban_rules):
                    new_rules.append(rule)
        
        low_adx_losses = [t for t in losses if t.get('adx', 20) < 18]
        low_adx_total = [t for t in self.trade_history[-100:] if t.get('adx', 20) < 18]
        if len(low_adx_total) >= 5:
            low_adx_loss_rate = len(low_adx_losses) / len(low_adx_total)
            if low_adx_loss_rate > 0.65:
                rule = {'type': 'adx_filter', 'threshold': 18, 'loss_rate': round(low_adx_loss_rate, 2),
                        'reason': f'ADX<18时亏损率{int(low_adx_loss_rate*100)}%'}
                if not any(r.get('type') == 'adx_filter' for r in self.ban_rules):
                    new_rules.append(rule)
        
        extreme_rsi_losses = [t for t in losses if t.get('rsi', 50) < 25 or t.get('rsi', 50) > 75]
        extreme_rsi_total = [t for t in self.trade_history[-100:] if t.get('rsi', 50) < 25 or t.get('rsi', 50) > 75]
        if len(extreme_rsi_total) >= 5:
            extreme_loss_rate = len(extreme_rsi_losses) / len(extreme_rsi_total)
            if extreme_loss_rate > 0.7:
                rule = {'type': 'rsi_extreme_ban', 'loss_rate': round(extreme_loss_rate, 2),
                        'reason': f'极端RSI入场亏损率{int(extreme_loss_rate*100)}%'}
                if not any(r.get('type') == 'rsi_extreme_ban' for r in self.ban_rules):
                    new_rules.append(rule)
        
        high_vol_losses = [t for t in losses if t.get('vol_ratio', 1.0) > 2.0]
        high_vol_total = [t for t in self.trade_history[-100:] if t.get('vol_ratio', 1.0) > 2.0]
        if len(high_vol_total) >= 5:
            high_vol_loss_rate = len(high_vol_losses) / len(high_vol_total)
            if high_vol_loss_rate > 0.65:
                rule = {'type': 'fomo_ban', 'loss_rate': round(high_vol_loss_rate, 2),
                        'reason': f'追量入场亏损率{int(high_vol_loss_rate*100)}%'}
                if not any(r.get('type') == 'fomo_ban' for r in self.ban_rules):
                    new_rules.append(rule)
        
        self.ban_rules.extend(new_rules)
        if len(self.ban_rules) > 20:
            self.ban_rules = self.ban_rules[-20:]
        
        if new_rules:
            logger.info(f"Critic新增{len(new_rules)}条禁用规则: {[r['reason'] for r in new_rules]}")
    
    def should_block_trade(self, regime_type, adx, rsi, vol_ratio):
        """Check if the trade should be blocked by any ban rule"""
        for rule in self.ban_rules:
            if rule['type'] == 'regime_ban' and rule['regime'] == regime_type:
                return True, rule['reason']
            if rule['type'] == 'adx_filter' and adx < rule['threshold']:
                return True, rule['reason']
            if rule['type'] == 'rsi_extreme_ban' and (rsi < 25 or rsi > 75):
                return True, rule['reason']
            if rule['type'] == 'fomo_ban' and vol_ratio > 2.0:
                return True, rule['reason']
        return False, ""
    
    def ai_deep_review(self):
        try:
            from server.titan_llm_client import chat_json

            recent = self.trade_history[-30:]
            if len(recent) < 5:
                return None

            losses = [t for t in recent if t['result'] == 'loss']
            wins = [t for t in recent if t['result'] == 'win']

            loss_details = []
            for t in losses[-10:]:
                loss_details.append(f"{t['symbol']}: PnL={t['pnl']:.2f}% RSI={t['rsi']:.0f} ADX={t['adx']:.0f} 环境={t['regime']} 方向={t['direction']} BB={t['bb_pos']:.2f} Vol={t['vol_ratio']:.1f}")

            win_details = []
            for t in wins[-5:]:
                win_details.append(f"{t['symbol']}: PnL={t['pnl']:.2f}% RSI={t['rsi']:.0f} ADX={t['adx']:.0f} 方向={t['direction']}")

            from server.titan_prompt_library import LOSS_ANALYSIS_PROMPT, PHASE_ZERO_CONTEXT
            prompt = PHASE_ZERO_CONTEXT + f"""== 近期亏损交易 ({len(losses)}/{len(recent)}) ==
{chr(10).join(loss_details)}

== 近期盈利交易参考 ==
{chr(10).join(win_details)}

== 当前禁止规则 ==
{json.dumps([r['reason'] for r in self.ban_rules[-5:]], ensure_ascii=False)}

请深度分析以上交易记录，找出亏损根因和改进方法。"""

            result = chat_json(
                module="ml_engine",
                messages=[
                    {"role": "system", "content": LOSS_ANALYSIS_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )
            if not result:
                return None
            self._last_ai_review = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if hasattr(datetime, 'now') else str(time.time()),
                "analysis": result,
                "trades_analyzed": len(recent),
                "loss_count": len(losses),
            }
            self._ai_review_count += 1
            logger.info(f"Critic AI深度复盘: {result.get('loss_pattern','')}")
            return result
        except Exception as e:
            logger.warning(f"Critic AI复盘失败: {e}")
            return None

    def auto_apply_suggestions(self, review_result):
        if not review_result or not review_result.get("new_ban_suggestions"):
            return {"applied": 0, "rules": []}
        applied = []
        for suggestion in review_result["new_ban_suggestions"]:
            confidence = suggestion.get("confidence", 0)
            if confidence < 75:
                continue
            condition = suggestion.get("condition", "")
            reason = suggestion.get("reason", "")
            existing = any(
                r.get("reason") == reason or r.get("condition") == condition
                for r in self.ban_rules
            )
            if existing:
                continue
            rule = {
                "type": "ai_suggestion",
                "condition": condition,
                "reason": f"[AI复盘 {confidence}%] {reason}",
                "confidence": confidence,
                "source": "critic_ai_auto",
                "created_at": time.time(),
            }
            self.ban_rules.append(rule)
            applied.append({"condition": condition, "confidence": confidence})
            logger.info(f"Critic自动应用规则: {condition} (置信度{confidence}%)")
        return {"applied": len(applied), "rules": applied}

    def get_status(self):
        recent = self.trade_history[-50:] if self.trade_history else []
        wins = sum(1 for t in recent if t['result'] == 'win')
        losses = sum(1 for t in recent if t['result'] == 'loss')
        status = {
            'total_reviewed': len(self.trade_history),
            'active_rules': len(self.ban_rules),
            'rules': [{'reason': r['reason'], 'type': r['type']} for r in self.ban_rules],
            'recent_wins': wins,
            'recent_losses': losses,
            'recent_win_rate': round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0,
        }
        if self._last_ai_review:
            status['ai_review'] = self._last_ai_review
            status['ai_review_count'] = self._ai_review_count
        return status


titan_critic = TitanCritic()


class TitanMLEngine:
    def __init__(self):
        self.model = None
        self.is_trained = False
        self.last_train_time = None
        self.metrics = {
            "accuracy": 0,
            "f1": 0,
            "samples_trained": 0,
            "train_count": 0,
            "last_train": None,
            "model_version": "未训练",
        }
        self.prediction_log = []
        self._load_model()
        self._load_metrics()

    def _load_model(self):
        try:
            if os.path.exists(MODEL_PATH):
                self.model = joblib.load(MODEL_PATH)
                self.is_trained = True
                logger.info("ML模型已从磁盘加载")
        except Exception as e:
            logger.warning(f"ML模型加载失败: {e}")
            self.model = None
            self.is_trained = False

    def _save_model(self):
        try:
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            joblib.dump(self.model, MODEL_PATH)
            logger.info("ML模型已保存到磁盘")
        except Exception as e:
            logger.error(f"ML模型保存失败: {e}")

    def _load_metrics(self):
        try:
            if os.path.exists(METRICS_PATH):
                with open(METRICS_PATH, "r") as f:
                    saved = json.load(f)
                    self.metrics.update(saved)
                    if self.metrics.get("last_train"):
                        self.last_train_time = self.metrics["last_train"]
        except Exception:
            pass

    def _save_metrics(self):
        try:
            os.makedirs(os.path.dirname(METRICS_PATH), exist_ok=True)
            with open(METRICS_PATH, "w") as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    EXT_FEATURE_NAMES = [
        'ext_fng', 'ext_fng_change', 'ext_risk_mode',
        'ext_funding_rate_btc', 'ext_funding_rate_eth',
        'ext_funding_rate_momentum', 'ext_oi_price_divergence',
        'ext_liq_imbalance', 'ext_liq_intensity',
    ]

    FEATURE_ENGINE_VERSION = "v2.0-research"

    @staticmethod
    def extract_features(df_1h, df_4h, df_1d=None, ext_data=None):
        if ext_data is None:
            try:
                from server.titan_external_data import TitanExternalDataManager
                ext_mgr = TitanExternalDataManager.get_instance()
                if ext_mgr is not None:
                    ext_data = ext_mgr.get_ml_features()
            except Exception:
                pass
        return TitanFeatureStore.extract_features(df_1h, df_4h, df_1d, ext_data)

    @staticmethod
    def build_training_dataset(df_1h, df_4h, df_1d=None, ext_data=None):
        horizon = ML_CONFIG['HORIZON_BARS']

        if ext_data is None:
            try:
                from server.titan_external_data import TitanExternalDataManager
                ext_mgr = TitanExternalDataManager.get_instance()
                if ext_mgr is not None:
                    ext_data = ext_mgr.get_ml_features()
            except Exception:
                pass

        result = TitanFeatureStore.build_feature_matrix(df_1h, df_4h, df_1d, ext_data, horizon)
        if result is None:
            return None, None, None

        df_matrix, feature_names = result
        X = df_matrix[feature_names].values.astype(np.float64)
        np.nan_to_num(X, copy=False, nan=0.0, posinf=1e6, neginf=-1e6)

        c1 = df_1h['c'].astype(float)
        c4 = df_4h['c'].astype(float)
        h4 = df_4h['h'].astype(float)
        l4 = df_4h['l'].astype(float)

        from server.titan_ml_features import _atr
        atr4 = _atr(h4, l4, c4)
        vol4 = c4.pct_change().rolling(20).std()

        labeler = DynamicTripleBarrier(tp_mult=2.5, sl_mult=1.0, max_holding=horizon * 4, exclude_sideways=True)
        tb_labels = labeler.label(c4, atr4, vol4)

        n_rows = len(X)
        label_arr = np.zeros(n_rows, dtype=int)
        start_idx = 60
        for ri in range(n_rows):
            i = start_idx + ri
            i4 = min(i // 4, len(c4) - 1)
            if i4 < len(tb_labels):
                label_arr[ri] = tb_labels.iloc[i4]

        label_arr = label_arr + 1

        if labeler.exclude_sideways:
            valid_mask = label_arr != 1
            logger.info(f"[ML] 横盘样本排除: {np.sum(~valid_mask)}/{n_rows} ({np.sum(~valid_mask)/max(n_rows,1)*100:.1f}%)")
            label_remap = np.where(label_arr == 2, 1, 0)
            X_out = X[valid_mask]
            y_out = label_remap[valid_mask]
        else:
            valid_mask = np.ones(n_rows, dtype=bool)
            X_out = X[valid_mask]
            y_out = label_arr[valid_mask]

        return X_out, y_out, feature_names

    def _is_cloud_model(self):
        try:
            version = self.metrics.get("model_version", "")
            return "Modal" in version or "Cloud" in version
        except Exception:
            return False

    def train(self, training_data_map):
        if self._is_cloud_model() and self.is_trained:
            age_hours = 0
            if self.last_train_time:
                try:
                    last_dt = datetime.strptime(self.last_train_time, "%Y-%m-%d %H:%M:%S")
                    age_hours = (datetime.now() - last_dt).total_seconds() / 3600
                except Exception:
                    pass
            if age_hours < 48:
                logger.info(f"[ML] 跳过本地训练 — 已有云端模型 (版本: {self.metrics.get('model_version')}, 训练于 {age_hours:.1f}h前)")
                return False

        all_X = []
        all_y = []
        feature_names = None

        skipped_none = 0
        skipped_small = 0
        skipped_short = 0
        for symbol, data in training_data_map.items():
            df_1h = data.get('1h')
            df_4h = data.get('4h')
            if df_1h is None or df_4h is None:
                skipped_none += 1
                continue
            if len(df_1h) < 100 or len(df_4h) < 40:
                skipped_short += 1
                continue

            try:
                X, y, fnames = self.build_training_dataset(df_1h, df_4h, data.get('1d'))
                if X is not None and len(X) > 10:
                    all_X.append(X)
                    all_y.append(y)
                    if feature_names is None:
                        feature_names = fnames
                else:
                    skipped_small += 1
                    if X is None:
                        logger.warning(f"[ML] [{symbol}] build_training_dataset返回None (1h={len(df_1h)}, 4h={len(df_4h)})")
                    else:
                        logger.warning(f"[ML] [{symbol}] 样本数太少: {len(X)}")
            except Exception as e:
                logger.error(f"[ML] [{symbol}] build_training_dataset失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                continue

        logger.info(f"[ML] 训练数据统计: 有效={len(all_X)}, 无数据={skipped_none}, 太短={skipped_short}, 构建失败={skipped_small}, 总计={len(training_data_map)}")

        if not all_X:
            logger.warning("训练数据不足，跳过训练")
            return False

        X_all = np.vstack(all_X)
        y_all = np.concatenate(all_y)

        nan_rows = np.isnan(X_all).any(axis=1) | np.isinf(X_all).any(axis=1)
        nan_labels = np.isnan(y_all.astype(float))
        nan_mask = nan_rows | nan_labels
        if nan_mask.sum() > 0:
            logger.warning(f"[NaN清理] 移除 {nan_mask.sum()}/{len(X_all)} 个含NaN/Inf的样本 (特征NaN={nan_rows.sum()}, 标签NaN={nan_labels.sum()})")
            X_all = X_all[~nan_mask]
            y_all = y_all[~nan_mask]

        if len(X_all) == 0:
            logger.warning("NaN清理后无有效样本，跳过训练")
            return False

        np.nan_to_num(X_all, copy=False, nan=0.0, posinf=1e6, neginf=-1e6)
        
        nan_cols = np.isnan(X_all).any(axis=0) | np.isinf(X_all).any(axis=0)
        if nan_cols.any():
            logger.warning(f"[NaN清理] 仍有 {nan_cols.sum()} 列含NaN，强制替换")
            X_all = np.nan_to_num(X_all, nan=0.0, posinf=1e6, neginf=-1e6)
        
        logger.info(f"[训练数据] 样本={len(X_all)}, 特征={X_all.shape[1]}, 标签分布={dict(zip(*np.unique(y_all, return_counts=True)))}, NaN检查=OK")

        unique_classes, class_counts = np.unique(y_all, return_counts=True)
        class_dist = dict(zip(unique_classes.tolist(), class_counts.tolist()))
        logger.info(f"[Class Balance] 原始分布: {class_dist}")
        total_samples = sum(class_dist.values())
        min_sig_threshold = max(50, int(total_samples * 0.05))
        significant_classes = {cls: cnt for cls, cnt in class_dist.items() if cnt >= min_sig_threshold}
        if len(significant_classes) >= 2:
            min_significant = min(significant_classes.values())
            max_allowed = int(min_significant * 2.5)
            balanced_indices = []
            for cls in unique_classes:
                cls_idx = np.where(y_all == cls)[0]
                if class_dist[cls] < min_sig_threshold:
                    balanced_indices.extend(cls_idx)
                elif len(cls_idx) > max_allowed:
                    np.random.seed(42)
                    selected = np.random.choice(cls_idx, max_allowed, replace=False)
                    selected.sort()
                    balanced_indices.extend(selected)
                else:
                    balanced_indices.extend(cls_idx)
            balanced_indices = sorted(balanced_indices)
            X_all = X_all[balanced_indices]
            y_all = y_all[balanced_indices]
            logger.info(f"[Class Balance] 降采样后: {len(X_all)} 样本, 分布: {dict(zip(*np.unique(y_all, return_counts=True)))}")
        else:
            logger.info(f"[Class Balance] 跳过平衡(有效类别不足2个), 保留全部 {len(X_all)} 样本")

        if len(X_all) < ML_CONFIG['MIN_SAMPLES_TO_TRAIN']:
            logger.warning(f"样本数 {len(X_all)} 不足 {ML_CONFIG['MIN_SAMPLES_TO_TRAIN']}，跳过训练")
            return False

        MAX_TRAIN_SAMPLES = 8000
        if len(X_all) > MAX_TRAIN_SAMPLES:
            np.random.seed(42)
            stratified_idx = []
            unique_labels = np.unique(y_all)
            for lbl in unique_labels:
                lbl_idx = np.where(y_all == lbl)[0]
                lbl_ratio = len(lbl_idx) / len(y_all)
                lbl_quota = max(int(MAX_TRAIN_SAMPLES * lbl_ratio), min(len(lbl_idx), 50))
                if len(lbl_idx) <= lbl_quota:
                    stratified_idx.extend(lbl_idx)
                else:
                    selected = np.random.choice(lbl_idx, lbl_quota, replace=False)
                    stratified_idx.extend(selected)
            stratified_idx = sorted(stratified_idx)
            X_all = X_all[stratified_idx]
            y_all = y_all[stratified_idx]
            logger.info(f"[样本上限] 分层降采样至 {len(X_all)} 样本, 分布: {dict(zip(*np.unique(y_all, return_counts=True)))}")

        try:
            time_decay = SampleWeighter.compute_time_decay_weights(len(X_all), 0.999)

            purged_cv = PurgedKFold(n_splits=5, embargo_pct=0.02, purge_pct=0.01)
            folds = list(purged_cv.split(X_all))
            if not folds:
                folds = list(TimeSeriesSplit(n_splits=5).split(X_all))
            train_idx, test_idx = folds[-1]
            X_train, X_test = X_all[train_idx], X_all[test_idx]
            y_train, y_test = y_all[train_idx], y_all[test_idx]
            w_train = time_decay[train_idx]

            init_rf = RandomForestClassifier(
                n_estimators=200, max_depth=12, min_samples_split=10,
                min_samples_leaf=5, class_weight='balanced_subsample',
                random_state=42, n_jobs=-1,
            )
            init_rf.fit(X_train, y_train, sample_weight=w_train)

            importances = init_rf.feature_importances_
            importance_dict = dict(zip(feature_names, importances))
            selected_features = select_features_by_importance(importance_dict, top_k=45, min_threshold=0.005)
            if len(selected_features) < 15:
                sorted_feats = sorted(importance_dict.items(), key=lambda x: -x[1])
                selected_features = [f for f, _ in sorted_feats[:15]]

            sel_indices = [feature_names.index(f) for f in selected_features]
            X_train_sel = X_train[:, sel_indices]
            X_test_sel = X_test[:, sel_indices]

            n_samples = len(X_train_sel)
            n_est = 150 if n_samples > 3000 else 300
            rf = RandomForestClassifier(
                n_estimators=n_est, max_depth=12, min_samples_split=8,
                min_samples_leaf=4, class_weight='balanced',
                random_state=42, n_jobs=1,
            )
            lgbm_model = lgb.LGBMClassifier(
                n_estimators=n_est, max_depth=8, learning_rate=0.05,
                class_weight='balanced', random_state=42, n_jobs=1, verbose=-1,
                num_leaves=32, min_child_samples=15,
                reg_alpha=0.1, reg_lambda=0.1,
                subsample=0.8, colsample_bytree=0.8,
            )

            use_catboost = HAS_CATBOOST and n_samples <= 3000
            if use_catboost:
                cat_model = CatBoostClassifier(
                    iterations=n_est, depth=6, learning_rate=0.05,
                    class_weights=None,
                    random_seed=42, verbose=0,
                    l2_leaf_reg=3.0, subsample=0.8,
                    bootstrap_type='Bernoulli',
                )
                ensemble = VotingClassifier(
                    estimators=[('rf', rf), ('lgbm', lgbm_model), ('catboost', cat_model)],
                    voting='soft', weights=[2, 4, 3],
                )
            elif HAS_XGBOOST:
                xgb_model = XGBClassifier(
                    n_estimators=300, max_depth=8, learning_rate=0.03,
                    random_state=42, n_jobs=-1, verbosity=0,
                    reg_alpha=0.1, reg_lambda=1.0,
                    subsample=0.8, colsample_bytree=0.8,
                )
                ensemble = VotingClassifier(
                    estimators=[('rf', rf), ('lgbm', lgbm_model), ('xgb', xgb_model)],
                    voting='soft', weights=[2, 4, 3],
                )
            else:
                lr = LogisticRegression(
                    max_iter=3000, class_weight='balanced', random_state=42, C=0.8, solver='lbfgs',
                )
                ensemble = VotingClassifier(
                    estimators=[('rf', rf), ('lgbm', lgbm_model), ('lr', lr)],
                    voting='soft', weights=[3, 4, 1],
                )

            ensemble.fit(X_train_sel, y_train, sample_weight=w_train)

            calibrated = TitanCalibratedClassifier(ensemble, n_splits=3)
            calibrated.fit(X_train_sel, y_train)

            y_pred_train = calibrated.predict(X_train_sel)
            proba_train = calibrated.predict_proba(X_train_sel) if hasattr(calibrated, 'predict_proba') else None
            meta_labeler = MetaLabeler(threshold=0.55)
            try:
                meta_labeler.fit(X_train_sel, y_pred_train, y_train, proba_train)
                self._meta_labeler = meta_labeler
                logger.info("Meta-labeler训练成功")
            except Exception as me:
                logger.warning(f"Meta-labeler训练跳过: {me}")
                self._meta_labeler = None

            y_pred = calibrated.predict(X_test_sel)
            acc = accuracy_score(y_test, y_pred)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

            cv_scores = []
            for cv_train_idx, cv_test_idx in purged_cv.split(X_all):
                cv_X_train = X_all[cv_train_idx][:, sel_indices]
                cv_X_test = X_all[cv_test_idx][:, sel_indices]
                cv_y_train = y_all[cv_train_idx]
                cv_y_test = y_all[cv_test_idx]
                temp_rf = RandomForestClassifier(
                    n_estimators=100, max_depth=12, class_weight='balanced',
                    random_state=42, n_jobs=-1
                )
                temp_rf.fit(cv_X_train, cv_y_train)
                cv_scores.append(accuracy_score(cv_y_test, temp_rf.predict(cv_X_test)))
            cv_mean = np.mean(cv_scores) if cv_scores else acc
            cv_std = np.std(cv_scores) if cv_scores else 0.0

            n_unique = len(np.unique(y_all))
            if n_unique == 2:
                label_names = {0: '跌', 1: '涨'}
                report_classes = ['跌', '涨']
            else:
                label_names = {0: '跌', 1: '横盘', 2: '涨'}
                report_classes = ['跌', '横盘', '涨']
            test_classes = sorted(np.unique(np.concatenate([y_test, y_pred])))
            tgt_names = [label_names.get(c, str(c)) for c in test_classes]
            report = classification_report(y_test, y_pred, labels=test_classes, target_names=tgt_names, output_dict=True, zero_division=0)
            per_class = {}
            for cls_name in report_classes:
                if cls_name in report:
                    per_class[cls_name] = {
                        'precision': round(report[cls_name]['precision'] * 100, 1),
                        'recall': round(report[cls_name]['recall'] * 100, 1),
                        'f1': round(report[cls_name]['f1-score'] * 100, 1),
                        'support': int(report[cls_name]['support']),
                    }

            feat_imp = {}
            try:
                for est_name, est in ensemble.named_estimators_.items():
                    if hasattr(est, 'feature_importances_'):
                        for fname, imp in zip(selected_features, est.feature_importances_):
                            feat_imp[fname] = feat_imp.get(fname, 0) + round(float(imp) * 100, 2) / 2
                feat_imp = dict(sorted(feat_imp.items(), key=lambda x: -x[1]))
            except Exception:
                feat_imp = {}

            from collections import Counter
            label_dist = dict(Counter(int(v) for v in y_all))
            label_dist_named = {
                '涨': label_dist.get(1, 0),
                '横盘': label_dist.get(0, 0),
                '跌': label_dist.get(-1, 0),
            }

            self.model = calibrated
            self.is_trained = True
            self.last_train_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            train_count = self.metrics.get("train_count", 0) + 1

            if HAS_CATBOOST:
                ensemble_type = "RF+LGBM+CatBoost"
            elif HAS_XGBOOST:
                ensemble_type = "RF+LGBM+XGB"
            else:
                ensemble_type = "RF+LGBM+LR"

            self.metrics = {
                "accuracy": round(acc * 100, 1),
                "f1": round(f1 * 100, 1),
                "cv_accuracy": round(cv_mean * 100, 1),
                "cv_std": round(cv_std * 100, 2),
                "samples_trained": int(len(X_all)),
                "train_count": train_count,
                "last_train": self.last_train_time,
                "model_version": f"RG-v{train_count}",
                "feature_engine": self.FEATURE_ENGINE_VERSION,
                "feature_names": feature_names,
                "selected_features": selected_features,
                "total_features": len(feature_names),
                "selected_count": len(selected_features),
                "per_class": per_class,
                "feature_importance": feat_imp,
                "label_distribution": label_dist_named,
                "calibration": "isotonic_3class",
                "label_method": "dynamic_triple_barrier",
                "cv_method": "purged_kfold_embargo",
                "ensemble_type": ensemble_type,
                "meta_labeler": self._meta_labeler is not None if hasattr(self, '_meta_labeler') else False,
                "techniques": [
                    "Purged K-Fold with Embargo",
                    "Dynamic Triple Barrier Labels",
                    "Fractional Differentiation",
                    "Meta-Labeling",
                    "Time-Decay Sample Weights",
                    "Hurst Exponent",
                    "Kyle's Lambda",
                    "Shannon Entropy",
                    "WorldQuant Alpha 50+",
                    "CoinGlass Derivatives Features",
                ],
            }

            self._save_model()
            self._save_metrics()

            logger.info(f"🔬 Research-Grade ML训练完成: 准确率={acc*100:.1f}% (CV:{cv_mean*100:.1f}±{cv_std*100:.1f}%) F1={f1*100:.1f}% 样本={len(X_all)} 特征={len(selected_features)}/{len(feature_names)} 引擎={ensemble_type}")
            return True

        except Exception as e:
            logger.error(f"ML训练异常: {e}", exc_info=True)
            return False

    def predict(self, df_1h, df_4h, df_1d=None):
        if not self.is_trained or self.model is None:
            return {"label": "未知", "confidence": 0, "probabilities": {}}

        try:
            import warnings
            warnings.filterwarnings('ignore', message='X does not have valid feature names')
            feats = self.extract_features(df_1h, df_4h, df_1d)
            if feats is None:
                return {"label": "未知", "confidence": 0, "probabilities": {}}

            selected_features = self.metrics.get("selected_features")
            if selected_features:
                use_features = selected_features
            else:
                use_features = self.metrics.get("feature_names")
                if not use_features:
                    use_features = sorted(feats.keys())

            X = np.array([[feats.get(k, 0.0) for k in use_features]])
            np.nan_to_num(X, copy=False, nan=0.0, posinf=1e6, neginf=-1e6)
            pred = self.model.predict(X)[0]
            proba = self.model.predict_proba(X)[0]
            classes = list(self.model.classes_)

            meta_confidence = 1.0
            should_trade = True
            if hasattr(self, '_meta_labeler') and self._meta_labeler is not None:
                try:
                    trade_mask, trade_conf = self._meta_labeler.predict_trade(X, np.array([pred]), proba.reshape(1, -1))
                    should_trade = bool(trade_mask[0])
                    meta_confidence = float(trade_conf[0])
                except Exception:
                    pass

            prob_map = {}
            n_classes = len(classes)
            if n_classes == 2:
                cls_label_map = {0: "跌", 1: "涨"}
                label_map = {0: "看跌", 1: "看涨"}
                sideways_class = None
            else:
                cls_label_map = {0: "跌", 1: "横盘", 2: "涨"}
                label_map = {2: "看涨", 0: "看跌", 1: "横盘"}
                sideways_class = 1

            for cls, p in zip(classes, proba):
                name = cls_label_map.get(int(cls), "未知")
                prob_map[name] = round(float(p) * 100, 1)

            confidence = round(float(max(proba)) * 100, 1)

            if not should_trade and pred != sideways_class:
                confidence = round(confidence * 0.6, 1)

            return {
                "label": label_map.get(pred, "未知"),
                "confidence": confidence,
                "probabilities": prob_map,
                "meta_trade": should_trade,
                "meta_confidence": round(meta_confidence * 100, 1),
            }

        except Exception as e:
            logger.warning(f"ML预测异常: {e}")
            return {"label": "异常", "confidence": 0, "probabilities": {}}

    @staticmethod
    def blend_scores(rule_score, ml_prediction, symbol=None, price=0):
        if ml_prediction["confidence"] == 0:
            return rule_score, {"mode": "rules_only", "w_rule": 1.0, "w_ml": 0.0, "agreement": True, "reason": "ML无预测"}

        label = ml_prediction["label"]
        confidence = ml_prediction["confidence"]

        agreed, agree_reason = adaptive_weights.check_direction_agreement(rule_score, label, confidence)

        if not agreed and confidence >= 60:
            penalty = int((confidence - 50) * 0.15)
            score = max(30, min(70, rule_score))
            if symbol and price > 0:
                rule_dir = "看涨" if rule_score >= 60 else ("看跌" if rule_score <= 40 else "横盘")
                adaptive_weights.record_prediction(symbol, price, label, confidence, rule_dir)
            return score, {"mode": "conflict_dampened", "w_rule": 0.99, "w_ml": 0.01, "agreement": False,
                           "reason": agree_reason, "penalty": penalty}

        if label == "看涨":
            ml_score = 50 + (confidence - 50) * 0.6
        elif label == "看跌":
            ml_score = 50 - (confidence - 50) * 0.6
        else:
            ml_score = 50

        if confidence >= 80:
            ml_conf_decay = 0.50
            ml_conf_tier = "overconfident（实测16.7%准确率，衰减50%）"
        elif confidence >= 70:
            ml_conf_decay = 0.75
            ml_conf_tier = "moderately_high（实测25%准确率，衰减25%）"
        elif confidence >= 60:
            ml_conf_decay = 1.00
            ml_conf_tier = "reliable（实测60%准确率，不衰减）"
        else:
            ml_conf_decay = 0.80
            ml_conf_tier = "low（低置信度，轻微衰减）"

        deviation = ml_score - 50
        ml_score = 50 + deviation * ml_conf_decay

        w_rule, w_ml = adaptive_weights.get_dynamic_weights_for_signal(confidence)
        blended = w_rule * rule_score + w_ml * ml_score

        if symbol and price > 0:
            rule_dir = "看涨" if rule_score >= 60 else ("看跌" if rule_score <= 40 else "横盘")
            adaptive_weights.record_prediction(symbol, price, label, confidence, rule_dir)

        return max(0, min(100, int(blended))), {"mode": "adaptive", "w_rule": round(w_rule, 2), "w_ml": round(w_ml, 2),
                                                  "agreement": True, "reason": agree_reason,
                                                  "ml_confidence_tier": ml_conf_tier, "ml_conf_decay": ml_conf_decay}

    @staticmethod
    def needs_deep_training():
        return not os.path.exists(DEEP_TRAIN_FLAG)

    @staticmethod
    def mark_deep_trained():
        try:
            os.makedirs(os.path.dirname(DEEP_TRAIN_FLAG), exist_ok=True)
            with open(DEEP_TRAIN_FLAG, "w") as f:
                f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception:
            pass

    def get_status(self):
        if HAS_CATBOOST:
            default_ensemble = "RF+LGBM+CatBoost"
        elif HAS_XGBOOST:
            default_ensemble = "RF+LGBM+XGB"
        else:
            default_ensemble = "RF+LGBM+LR"
        ensemble_type = self.metrics.get("ensemble_type", default_ensemble)
        return {
            "is_trained": self.is_trained,
            "accuracy": self.metrics.get("accuracy", 0),
            "f1": self.metrics.get("f1", 0),
            "cv_accuracy": self.metrics.get("cv_accuracy", 0),
            "cv_std": self.metrics.get("cv_std", 0),
            "samples": self.metrics.get("samples_trained", 0),
            "train_count": self.metrics.get("train_count", 0),
            "last_train": self.metrics.get("last_train", "从未训练"),
            "model_version": self.metrics.get("model_version", "未训练"),
            "feature_engine": self.metrics.get("feature_engine", self.FEATURE_ENGINE_VERSION),
            "deep_trained": not self.needs_deep_training(),
            "per_class": {k.split('(')[0]: v for k, v in self.metrics.get("per_class", {}).items()},
            "feature_importance": self.metrics.get("feature_importance", {}),
            "label_distribution": self.metrics.get("label_distribution", {}),
            "model_type": f"Research-Grade Ensemble ({ensemble_type})",
            "ensemble_type": ensemble_type,
            "label_method": self.metrics.get("label_method", "dynamic_triple_barrier"),
            "calibration": self.metrics.get("calibration", "isotonic_3class"),
            "cv_method": self.metrics.get("cv_method", "purged_kfold_embargo"),
            "selected_features": self.metrics.get("selected_features", []),
            "total_features": self.metrics.get("total_features", 0),
            "selected_count": self.metrics.get("selected_count", 0),
            "meta_labeler": self.metrics.get("meta_labeler", False),
            "techniques": self.metrics.get("techniques", []),
        }


class TitanBacktester:
    def __init__(self):
        self.results = {}
        self.equity_curve = []
        self.trades = []

    @staticmethod
    def run(cruise_history, initial_capital=10000):
        if not cruise_history or len(cruise_history) < 2:
            return None

        capital = initial_capital
        equity_curve = [{"time": cruise_history[0].get("time", ""), "equity": capital}]
        trades = []
        open_positions = {}
        peak = capital
        max_drawdown = 0
        wins = 0
        losses = 0
        total_pnl = 0

        for snapshot in cruise_history:
            ts = snapshot.get("time", "")
            signals = snapshot.get("signals", [])

            closed_syms = []
            for sym, pos in open_positions.items():
                current = None
                for s in signals:
                    if s.get("sym") == sym:
                        current = s
                        break
                if not current:
                    continue

                price = current["price"]
                if price >= pos["tp"]:
                    pnl = (pos["tp"] - pos["entry"]) / pos["entry"] * pos["size"]
                    capital += pos["size"] + pnl
                    total_pnl += pnl
                    wins += 1
                    trades.append({
                        "sym": sym, "entry": pos["entry"], "exit": pos["tp"],
                        "pnl": round(pnl, 2), "pnl_pct": round((pos["tp"] - pos["entry"]) / pos["entry"] * 100, 2),
                        "result": "win", "entry_time": pos["time"], "exit_time": ts,
                    })
                    closed_syms.append(sym)
                elif price <= pos["sl"]:
                    pnl = (pos["sl"] - pos["entry"]) / pos["entry"] * pos["size"]
                    capital += pos["size"] + pnl
                    total_pnl += pnl
                    losses += 1
                    trades.append({
                        "sym": sym, "entry": pos["entry"], "exit": pos["sl"],
                        "pnl": round(pnl, 2), "pnl_pct": round((pos["sl"] - pos["entry"]) / pos["entry"] * 100, 2),
                        "result": "loss", "entry_time": pos["time"], "exit_time": ts,
                    })
                    closed_syms.append(sym)

            for sym in closed_syms:
                del open_positions[sym]

            for s in signals:
                sym = s.get("sym", "")
                score = s.get("score", 0)
                if score >= 80 and sym not in open_positions and capital > 0:
                    pos_size = min(capital * 0.1, s.get("pos_val", 500))
                    if pos_size < 10:
                        continue
                    capital -= pos_size
                    open_positions[sym] = {
                        "entry": s["price"], "tp": s["tp"], "sl": s["sl"],
                        "size": pos_size, "time": ts, "score": score,
                    }

            unrealized = 0
            for sym, pos in open_positions.items():
                for s in signals:
                    if s.get("sym") == sym:
                        unrealized += (s["price"] - pos["entry"]) / pos["entry"] * pos["size"]
                        break

            total_equity = capital + sum(p["size"] for p in open_positions.values()) + unrealized
            equity_curve.append({"time": ts, "equity": round(total_equity, 2)})

            if total_equity > peak:
                peak = total_equity
            dd = (peak - total_equity) / peak * 100 if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

        total_equity = capital + sum(p["size"] for p in open_positions.values())
        total_trades = wins + losses
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

        avg_win = 0
        avg_loss = 0
        if wins > 0:
            avg_win = sum(t["pnl"] for t in trades if t["result"] == "win") / wins
        if losses > 0:
            avg_loss = abs(sum(t["pnl"] for t in trades if t["result"] == "loss") / losses)
        profit_factor = (avg_win * wins) / (avg_loss * losses + 1e-10) if losses > 0 else float('inf')

        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i-1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                returns.append((curr - prev) / prev)
        sharpe = 0
        if returns and len(returns) > 1:
            avg_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > 0:
                sharpe = round((avg_ret / std_ret) * np.sqrt(252 * 24), 2)

        return {
            "total_return": round((total_equity - initial_capital) / initial_capital * 100, 2),
            "total_pnl": round(total_pnl, 2),
            "max_drawdown": round(max_drawdown, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": total_trades,
            "wins": wins,
            "losses": losses,
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else 999,
            "sharpe_ratio": sharpe,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "equity_curve": equity_curve[-200:],
            "recent_trades": trades[-50:],
            "open_positions": len(open_positions),
            "final_equity": round(total_equity, 2),
        }



ml_engine = TitanMLEngine()
backtester = TitanBacktester()
