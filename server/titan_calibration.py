import numpy as np
import pandas as pd
import logging
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger("TitanCalibration")


class TitanCalibratedClassifier:
    """
    Titan V17.5 概率校准器 (3-Class Isotonic Regression)
    
    解决: ML模型过度自信 -> Kelly公式重仓 -> 亏损
    方案: 每个类别独立校准, 使用out-of-fold预测防止过拟合
    """
    def __init__(self, base_estimator, n_splits=5):
        self.base_estimator = base_estimator
        self.n_splits = n_splits
        self.calibrators = {}
        self.classes_ = None

    def fit(self, X, y):
        self.base_estimator.fit(X, y)
        self.classes_ = self.base_estimator.classes_

        oof_probs = np.zeros((len(X), len(self.classes_)))
        tscv = TimeSeriesSplit(n_splits=self.n_splits)

        for train_idx, val_idx in tscv.split(X):
            X_tr, X_val = X[train_idx], X[val_idx]
            y_tr = y[train_idx]

            from sklearn.base import clone
            fold_model = clone(self.base_estimator)
            fold_model.fit(X_tr, y_tr)

            fold_probs = fold_model.predict_proba(X_val)
            fold_classes = list(fold_model.classes_)

            for i, cls in enumerate(self.classes_):
                if cls in fold_classes:
                    cls_idx = fold_classes.index(cls)
                    oof_probs[val_idx, i] = fold_probs[:, cls_idx]
                else:
                    oof_probs[val_idx, i] = 0.0

        used_mask = oof_probs.sum(axis=1) > 0

        self.calibrators = {}
        for i, cls in enumerate(self.classes_):
            iso = IsotonicRegression(out_of_bounds='clip', y_min=0.01, y_max=0.99)
            raw_p = oof_probs[used_mask, i]
            binary_y = (y[used_mask] == cls).astype(float)

            if len(np.unique(binary_y)) < 2:
                self.calibrators[cls] = None
                continue

            iso.fit(raw_p, binary_y)
            self.calibrators[cls] = iso

        logger.info(f"[Calibration] 3-class isotonic calibration complete, classes={list(self.classes_)}")
        return self

    def predict_proba(self, X):
        raw_probs = self.base_estimator.predict_proba(X)
        raw_classes = list(self.base_estimator.classes_)

        calibrated = np.zeros_like(raw_probs)
        for i, cls in enumerate(self.classes_):
            if cls in raw_classes:
                raw_idx = raw_classes.index(cls)
                raw_col = raw_probs[:, raw_idx]
            else:
                raw_col = np.zeros(len(X))

            iso = self.calibrators.get(cls)
            if iso is not None:
                calibrated[:, i] = iso.transform(raw_col)
            else:
                calibrated[:, i] = raw_col

        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums > 0, row_sums, 1.0)
        calibrated = calibrated / row_sums

        return calibrated

    def predict(self, X):
        probs = self.predict_proba(X)
        indices = np.argmax(probs, axis=1)
        return self.classes_[indices]

    @property
    def named_estimators_(self):
        return self.base_estimator.named_estimators_

    @property
    def feature_importances_(self):
        if hasattr(self.base_estimator, 'feature_importances_'):
            return self.base_estimator.feature_importances_
        return None


def apply_triple_barrier_labels(close_series, high_series, low_series, atr_series,
                                 tp_mult=3.0, sl_mult=1.5, holding_period=12):
    """
    三重屏障标签法 (Triple Barrier Method)
    
    替代P30/P70百分位标签, 直接模拟交易TP/SL逻辑:
    - Label  1: 先碰到止盈线 (+tp_mult * ATR)
    - Label -1: 先碰到止损线 (-sl_mult * ATR)
    - Label  0: 超时未触碰 (震荡)
    """
    n = len(close_series)
    labels = np.zeros(n, dtype=int)

    close_vals = close_series.values if hasattr(close_series, 'values') else np.asarray(close_series)
    high_vals = high_series.values if hasattr(high_series, 'values') else np.asarray(high_series)
    low_vals = low_series.values if hasattr(low_series, 'values') else np.asarray(low_series)
    atr_vals = atr_series.values if hasattr(atr_series, 'values') else np.asarray(atr_series)

    for i in range(n - holding_period):
        price = close_vals[i]
        atr = atr_vals[i]
        if np.isnan(atr) or atr < 1e-10:
            labels[i] = 0
            continue

        tp_price = price + atr * tp_mult
        sl_price = price - atr * sl_mult

        first_tp = -1
        first_sl = -1
        for j in range(1, holding_period + 1):
            idx = i + j
            if idx >= n:
                break
            if first_tp < 0 and high_vals[idx] >= tp_price:
                first_tp = j
            if first_sl < 0 and low_vals[idx] <= sl_price:
                first_sl = j
            if first_tp >= 0 and first_sl >= 0:
                break

        if first_tp >= 0 and first_sl < 0:
            labels[i] = 1
        elif first_sl >= 0 and first_tp < 0:
            labels[i] = -1
        elif first_tp >= 0 and first_sl >= 0:
            labels[i] = 1 if first_tp <= first_sl else -1
        else:
            labels[i] = 0

    return labels
