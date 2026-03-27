import numpy as np
import pandas as pd
import logging
from typing import List, Tuple, Optional
from sklearn.model_selection import BaseCrossValidator

logger = logging.getLogger("TitanMLValidation")


class PurgedKFold(BaseCrossValidator):
    def __init__(self, n_splits=5, embargo_pct=0.01, purge_pct=0.01):
        self.n_splits = n_splits
        self.embargo_pct = embargo_pct
        self.purge_pct = purge_pct

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, X, y=None, groups=None):
        n_samples = len(X)
        indices = np.arange(n_samples)
        fold_size = n_samples // self.n_splits
        embargo_size = max(1, int(n_samples * self.embargo_pct))
        purge_size = max(1, int(n_samples * self.purge_pct))

        for i in range(self.n_splits):
            test_start = i * fold_size
            test_end = (i + 1) * fold_size if i < self.n_splits - 1 else n_samples

            test_indices = indices[test_start:test_end]

            purge_start = max(0, test_start - purge_size)
            embargo_end = min(n_samples, test_end + embargo_size)
            excluded = set(range(purge_start, embargo_end))
            train_indices = np.array([idx for idx in indices if idx not in excluded])

            if len(train_indices) == 0 or len(test_indices) == 0:
                continue

            yield train_indices, test_indices


class WalkForwardCV(BaseCrossValidator):
    def __init__(self, n_splits=5, train_ratio=0.7, embargo_pct=0.01):
        self.n_splits = n_splits
        self.train_ratio = train_ratio
        self.embargo_pct = embargo_pct

    def get_n_splits(self, X=None, y=None, groups=None):
        return self.n_splits

    def split(self, X, y=None, groups=None):
        n_samples = len(X)
        step = max(1, int(n_samples * (1 - self.train_ratio) / self.n_splits))
        embargo_size = max(1, int(n_samples * self.embargo_pct))

        for i in range(self.n_splits):
            test_start = int(n_samples * self.train_ratio) + i * step
            test_end = test_start + step
            if test_end > n_samples:
                test_end = n_samples
            if test_start >= n_samples:
                break

            train_end = test_start - embargo_size
            if train_end <= 0:
                continue

            train_indices = np.arange(0, train_end)
            test_indices = np.arange(test_start, test_end)

            if len(train_indices) == 0 or len(test_indices) == 0:
                continue

            yield train_indices, test_indices


class CombinatorialPurgedCV(BaseCrossValidator):
    def __init__(self, n_splits=6, n_test_splits=2, embargo_pct=0.01, purge_pct=0.01):
        self.n_splits = n_splits
        self.n_test_splits = n_test_splits
        self.embargo_pct = embargo_pct
        self.purge_pct = purge_pct

    def get_n_splits(self, X=None, y=None, groups=None):
        from math import comb
        return comb(self.n_splits, self.n_test_splits)

    def split(self, X, y=None, groups=None):
        from itertools import combinations
        n_samples = len(X)
        fold_size = n_samples // self.n_splits
        embargo_size = max(1, int(n_samples * self.embargo_pct))
        purge_size = max(1, int(n_samples * self.purge_pct))

        folds = []
        for i in range(self.n_splits):
            start = i * fold_size
            end = (i + 1) * fold_size if i < self.n_splits - 1 else n_samples
            folds.append(np.arange(start, end))

        for test_combo in combinations(range(self.n_splits), self.n_test_splits):
            test_indices = np.concatenate([folds[j] for j in test_combo])
            test_set = set(test_indices)

            excluded = set()
            for j in test_combo:
                start = folds[j][0]
                end = folds[j][-1]
                for k in range(max(0, start - purge_size), min(n_samples, end + embargo_size + 1)):
                    excluded.add(k)

            train_indices = np.array([idx for idx in range(n_samples) if idx not in excluded and idx not in test_set])

            if len(train_indices) > 0 and len(test_indices) > 0:
                yield train_indices, test_indices


def compute_cv_score(model, X, y, cv, scoring='accuracy'):
    from sklearn.metrics import accuracy_score, log_loss, f1_score
    scores = []

    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        if scoring == 'accuracy':
            scores.append(accuracy_score(y_test, y_pred))
        elif scoring == 'f1_macro':
            scores.append(f1_score(y_test, y_pred, average='macro', zero_division=0))
        elif scoring == 'log_loss':
            if hasattr(model, 'predict_proba'):
                y_prob = model.predict_proba(X_test)
                scores.append(-log_loss(y_test, y_prob, labels=model.classes_))
            else:
                scores.append(0.0)

    return np.mean(scores) if scores else 0.0, np.std(scores) if scores else 1.0


def compute_feature_importance_mdi(model, feature_names):
    if hasattr(model, 'feature_importances_'):
        imp = model.feature_importances_
        return dict(zip(feature_names, imp))
    return {}


def compute_feature_importance_mda(model, X, y, cv, n_repeats=3):
    from sklearn.metrics import accuracy_score
    importances = np.zeros(X.shape[1])

    for train_idx, test_idx in cv.split(X, y):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        model.fit(X_train, y_train)
        baseline_score = accuracy_score(y_test, model.predict(X_test))

        for j in range(X.shape[1]):
            scores = []
            for _ in range(n_repeats):
                X_perm = X_test.copy()
                np.random.shuffle(X_perm[:, j])
                perm_score = accuracy_score(y_test, model.predict(X_perm))
                scores.append(baseline_score - perm_score)
            importances[j] += np.mean(scores)

    n_splits = cv.get_n_splits()
    if n_splits > 0:
        importances /= n_splits

    return importances


def select_features_by_importance(importances: dict, top_k: int = 40,
                                  min_threshold: float = 0.001) -> List[str]:
    sorted_feats = sorted(importances.items(), key=lambda x: x[1], reverse=True)
    selected = []
    for name, imp in sorted_feats:
        if len(selected) >= top_k:
            break
        if imp >= min_threshold:
            selected.append(name)
    return selected if selected else [name for name, _ in sorted_feats[:top_k]]
