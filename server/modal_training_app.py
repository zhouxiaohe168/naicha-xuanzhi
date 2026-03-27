import modal
import os

_BASE = os.path.dirname(os.path.abspath(__file__))

app = modal.App("titan-ml-training")

training_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "numpy>=1.24",
        "pandas>=2.0",
        "scikit-learn>=1.4",
        "lightgbm>=4.0",
        "catboost>=1.2",
        "xgboost>=2.0",
        "joblib>=1.3",
        "ccxt>=4.0",
    )
    .add_local_file(os.path.join(_BASE, "titan_ml_features.py"), "/root/server/titan_ml_features.py")
    .add_local_file(os.path.join(_BASE, "titan_ml_labeling.py"), "/root/server/titan_ml_labeling.py")
    .add_local_file(os.path.join(_BASE, "titan_ml_validation.py"), "/root/server/titan_ml_validation.py")
    .add_local_file(os.path.join(_BASE, "titan_calibration.py"), "/root/server/titan_calibration.py")
)

model_volume = modal.Volume.from_name("titan-ml-models", create_if_missing=True)

ELITE_UNIVERSE = [
    'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'SUI', 'TON',
    'NEAR', 'APT', 'ATOM', 'LTC', 'TRX', 'HBAR',
    'BCH', 'XLM', 'ZEC', 'DASH', 'ICP', 'SEI', 'TIA', 'EGLD', 'CORE',
    'ONDO', 'MKR', 'PENDLE',
    'FET', 'TAO', 'RNDR', 'WLD', 'AKT', 'AGIX', 'GLM', 'FIL', 'AR', 'JASMY', 'HNT', 'THETA',
    'POL', 'MNT', 'OP', 'ARB', 'STRK', 'ZK', 'METIS', 'MANTA',
    'UNI', 'AAVE', 'JUP', 'CAKE', 'CRV', 'CVX', 'KNC', 'LDO', 'ENA', 'BNT', 'RPL',
    'DOGE', 'SHIB', 'PEPE', 'BONK', 'FLOKI', 'WIF',
    'IMX', 'AXS', 'SAND', 'MANA', 'CHZ', 'BEAM', 'GALA', 'MASK',
]

ML_CONFIG = {
    'HORIZON_BARS': 4,
    'LABEL_UP_PERCENTILE': 65,
    'LABEL_DOWN_PERCENTILE': 35,
    'MIN_SAMPLES_TO_TRAIN': 200,
    'HISTORY_BARS_1H': 8000,
    'HISTORY_BARS_4H': 6000,
    'HISTORY_BARS_1D': 1500,
    'MAX_ASSETS': 69,
}


def fetch_all_training_data(symbols, progress_callback=None):
    import ccxt
    import pandas as pd
    import time as _time

    exchange = ccxt.gate({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'},
    })

    training_map = {}
    total = min(ML_CONFIG['MAX_ASSETS'], len(symbols))

    for i, asset in enumerate(symbols[:total]):
        sym = f"{asset}/USDT"
        if progress_callback:
            progress_callback(f"获取 {asset} ({i+1}/{total})")

        try:
            data_1h = exchange.fetch_ohlcv(sym, '1h', limit=ML_CONFIG['HISTORY_BARS_1H'])
            _time.sleep(0.3)
            data_4h = exchange.fetch_ohlcv(sym, '4h', limit=ML_CONFIG['HISTORY_BARS_4H'])
            _time.sleep(0.3)
            data_1d = exchange.fetch_ohlcv(sym, '1d', limit=ML_CONFIG['HISTORY_BARS_1D'])
            _time.sleep(0.3)

            if len(data_1h) > 100 and len(data_4h) > 40:
                entry = {
                    '1h': pd.DataFrame(data_1h, columns=['t', 'o', 'h', 'l', 'c', 'v']),
                    '4h': pd.DataFrame(data_4h, columns=['t', 'o', 'h', 'l', 'c', 'v']),
                }
                if len(data_1d) > 30:
                    entry['1d'] = pd.DataFrame(data_1d, columns=['t', 'o', 'h', 'l', 'c', 'v'])
                training_map[asset] = entry
                print(f"[Modal] {asset}: 1h={len(data_1h)} 4h={len(data_4h)} 1d={len(data_1d)}")
            else:
                print(f"[Modal] {asset}: 数据不足 1h={len(data_1h)} 4h={len(data_4h)}")
        except Exception as e:
            print(f"[Modal] {asset}: 获取失败 {str(e)[:60]}")
            continue

    return training_map


def run_training_pipeline(training_data_map):
    import sys
    sys.path.insert(0, "/root")

    import numpy as np
    import pandas as pd
    import joblib
    import json
    from datetime import datetime
    from collections import Counter

    from sklearn.ensemble import RandomForestClassifier, VotingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import accuracy_score, f1_score, classification_report

    import lightgbm as lgb

    from server.titan_ml_features import TitanFeatureStore, _atr
    from server.titan_ml_validation import PurgedKFold, select_features_by_importance
    from server.titan_ml_labeling import DynamicTripleBarrier, MetaLabeler, SampleWeighter
    from server.titan_calibration import TitanCalibratedClassifier

    HAS_CATBOOST = False
    CatBoostWrapper = None
    try:
        from catboost import CatBoostClassifier
        HAS_CATBOOST = True
    except ImportError:
        pass

    try:
        from xgboost import XGBClassifier
        HAS_XGBOOST = True
    except ImportError:
        HAS_XGBOOST = False

    horizon = ML_CONFIG.get('HORIZON_BARS', 4)

    all_X = []
    all_y = []
    feature_names = None
    skipped = 0

    for symbol, data in training_data_map.items():
        df_1h = data.get('1h')
        df_4h = data.get('4h')
        if df_1h is None or df_4h is None:
            skipped += 1
            continue
        if len(df_1h) < 100 or len(df_4h) < 40:
            skipped += 1
            continue

        try:
            df_1d = data.get('1d')
            result = TitanFeatureStore.build_feature_matrix(df_1h, df_4h, df_1d, None, horizon)
            if result is None:
                print(f"[Modal] {symbol}: build_feature_matrix返回None")
                skipped += 1
                continue

            df_matrix, fnames = result
            X = df_matrix[fnames].values.astype(np.float64)
            np.nan_to_num(X, copy=False, nan=0.0, posinf=1e6, neginf=-1e6)

            c4 = df_4h['c'].astype(float)
            h4 = df_4h['h'].astype(float)
            l4 = df_4h['l'].astype(float)
            atr4 = _atr(h4, l4, c4)
            vol4 = c4.pct_change().rolling(20).std()

            labeler = DynamicTripleBarrier(tp_mult=2.0, sl_mult=2.0, max_holding=horizon * 2)
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

            if len(X) > 10:
                all_X.append(X)
                all_y.append(label_arr)
                if feature_names is None:
                    feature_names = fnames
                print(f"[Modal] {symbol}: {len(X)} 样本, {len(fnames)} 特征")
            else:
                skipped += 1
        except Exception as e:
            print(f"[Modal] {symbol} 特征构建失败: {e}")
            import traceback
            traceback.print_exc()
            skipped += 1
            continue

    print(f"[Modal] 数据统计: 有效={len(all_X)}, 跳过={skipped}")

    if not all_X:
        return {"success": False, "error": "训练数据不足"}

    X_all = np.vstack(all_X)
    y_all = np.concatenate(all_y)

    nan_mask = np.isnan(X_all).any(axis=1) | np.isinf(X_all).any(axis=1) | np.isnan(y_all.astype(float))
    if nan_mask.sum() > 0:
        X_all = X_all[~nan_mask]
        y_all = y_all[~nan_mask]

    np.nan_to_num(X_all, copy=False, nan=0.0, posinf=1e6, neginf=-1e6)

    print(f"[Modal] 训练数据: {len(X_all)} 样本, {X_all.shape[1]} 特征")

    unique_classes, class_counts = np.unique(y_all, return_counts=True)
    class_dist = dict(zip(unique_classes.tolist(), class_counts.tolist()))
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

    if len(X_all) < ML_CONFIG['MIN_SAMPLES_TO_TRAIN']:
        return {"success": False, "error": f"样本不足: {len(X_all)} < {ML_CONFIG['MIN_SAMPLES_TO_TRAIN']}"}

    print(f"[Modal] 平衡后: {len(X_all)} 样本, 分布: {dict(zip(*np.unique(y_all, return_counts=True)))}")

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
    n_est = 300

    rf = RandomForestClassifier(
        n_estimators=n_est, max_depth=12, min_samples_split=8,
        min_samples_leaf=4, class_weight='balanced',
        random_state=42, n_jobs=-1,
    )
    lgbm_model = lgb.LGBMClassifier(
        n_estimators=n_est, max_depth=8, learning_rate=0.05,
        class_weight='balanced', random_state=42, n_jobs=-1, verbose=-1,
        num_leaves=32, min_child_samples=15,
        reg_alpha=0.1, reg_lambda=0.1,
        subsample=0.8, colsample_bytree=0.8,
    )

    if HAS_CATBOOST and n_samples <= 3000:
        cat_model = CatBoostClassifier(
            iterations=n_est, depth=6, learning_rate=0.05,
            random_seed=42, verbose=0,
            l2_leaf_reg=3.0, subsample=0.8, bootstrap_type='Bernoulli',
        )
        ensemble = VotingClassifier(
            estimators=[('rf', rf), ('lgbm', lgbm_model), ('catboost', cat_model)],
            voting='soft', weights=[2, 4, 3],
        )
        ensemble_type = "RF+LGBM+CatBoost"
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
        ensemble_type = "RF+LGBM+XGB"
    else:
        lr = LogisticRegression(
            max_iter=3000, class_weight='balanced', random_state=42, C=0.8, solver='lbfgs',
        )
        ensemble = VotingClassifier(
            estimators=[('rf', rf), ('lgbm', lgbm_model), ('lr', lr)],
            voting='soft', weights=[3, 4, 1],
        )
        ensemble_type = "RF+LGBM+LR"

    print(f"[Modal] 训练集成模型: {ensemble_type}, 训练集={len(X_train_sel)}, 测试集={len(X_test_sel)}")
    ensemble.fit(X_train_sel, y_train, sample_weight=w_train)

    calibrated = TitanCalibratedClassifier(ensemble, n_splits=3)
    calibrated.fit(X_train_sel, y_train)

    y_pred_train = calibrated.predict(X_train_sel)
    proba_train = calibrated.predict_proba(X_train_sel) if hasattr(calibrated, 'predict_proba') else None
    meta_labeler = MetaLabeler(threshold=0.55)
    has_meta = False
    try:
        meta_labeler.fit(X_train_sel, y_pred_train, y_train, proba_train)
        has_meta = True
    except Exception:
        pass

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

    label_names = {0: '跌', 1: '横盘', 2: '涨'}
    test_classes = sorted(np.unique(np.concatenate([y_test, y_pred])))
    tgt_names = [label_names.get(c, str(c)) for c in test_classes]
    report = classification_report(y_test, y_pred, labels=test_classes, target_names=tgt_names, output_dict=True, zero_division=0)
    per_class = {}
    for cls_name in ['跌', '横盘', '涨']:
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

    label_dist = dict(Counter(int(v) for v in y_all))
    label_dist_named = {
        '涨': label_dist.get(2, 0),
        '横盘': label_dist.get(1, 0),
        '跌': label_dist.get(0, 0),
    }

    model_path = "/vol/titan_ml_model.pkl"
    metrics_path = "/vol/titan_ml_metrics.json"
    meta_path = "/vol/titan_meta_labeler.pkl"

    joblib.dump(calibrated, model_path)
    if has_meta:
        joblib.dump(meta_labeler, meta_path)

    metrics = {
        "accuracy": round(acc * 100, 1),
        "f1": round(f1 * 100, 1),
        "cv_accuracy": round(cv_mean * 100, 1),
        "cv_std": round(cv_std * 100, 2),
        "samples_trained": int(len(X_all)),
        "last_train": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "feature_engine": "RG-v2.0-Modal",
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
        "meta_labeler": has_meta,
        "trained_on": "modal_cloud",
        "assets_count": len(training_data_map),
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
        ],
    }

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"[Modal] 训练完成! 准确率={acc*100:.1f}% F1={f1*100:.1f}% CV={cv_mean*100:.1f}±{cv_std*100:.1f}% 样本={len(X_all)} 特征={len(selected_features)}/{len(feature_names)} 集成={ensemble_type}")

    return {
        "success": True,
        "metrics": metrics,
    }


@app.function(
    image=training_image,
    cpu=8.0,
    memory=8192,
    timeout=1800,
    volumes={"/vol": model_volume},
)
def train_titan_ml(symbols: list = None, max_assets: int = 69):
    import time as _time
    start = _time.time()

    if symbols is None:
        symbols = ELITE_UNIVERSE

    print(f"[Modal] 开始训练: {len(symbols[:max_assets])} 个资产")

    training_data = fetch_all_training_data(symbols[:max_assets])

    if not training_data:
        return {"success": False, "error": "无法获取训练数据", "elapsed": round(_time.time() - start, 1)}

    print(f"[Modal] 数据获取完成: {len(training_data)} 个资产, 开始训练...")

    result = run_training_pipeline(training_data)
    result["elapsed"] = round(_time.time() - start, 1)
    result["assets_fetched"] = len(training_data)

    if result.get("success"):
        model_volume.commit()

    return result


@app.function(
    image=training_image,
    cpu=1.0,
    memory=512,
    timeout=60,
    volumes={"/vol": model_volume},
)
def download_model():
    import joblib
    import json

    model_volume.reload()

    model_path = "/vol/titan_ml_model.pkl"
    metrics_path = "/vol/titan_ml_metrics.json"
    meta_path = "/vol/titan_meta_labeler.pkl"

    result = {"success": False}

    if os.path.exists(model_path):
        model_bytes = open(model_path, "rb").read()
        result["model"] = model_bytes
        result["success"] = True
    else:
        result["error"] = "模型文件不存在"
        return result

    if os.path.exists(metrics_path):
        with open(metrics_path, "r") as f:
            result["metrics"] = json.load(f)

    if os.path.exists(meta_path):
        meta_bytes = open(meta_path, "rb").read()
        result["meta_labeler"] = meta_bytes

    return result


@app.function(
    image=training_image,
    cpu=1.0,
    memory=256,
    timeout=30,
    volumes={"/vol": model_volume},
)
def check_model_status():
    import json

    model_volume.reload()

    model_path = "/vol/titan_ml_model.pkl"
    metrics_path = "/vol/titan_ml_metrics.json"

    result = {"model_exists": os.path.exists(model_path)}

    if os.path.exists(metrics_path):
        with open(metrics_path, "r") as f:
            metrics = json.load(f)
            result["metrics"] = {
                "accuracy": metrics.get("accuracy"),
                "f1": metrics.get("f1"),
                "cv_accuracy": metrics.get("cv_accuracy"),
                "samples_trained": metrics.get("samples_trained"),
                "last_train": metrics.get("last_train"),
                "ensemble_type": metrics.get("ensemble_type"),
                "assets_count": metrics.get("assets_count"),
            }

    return result


def generate_mm_training_data(training_data_map):
    import numpy as np
    import pandas as pd
    from collections import Counter

    POSITION_SIZES = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.13, 0.15]
    HOLD_PERIODS = [4, 8, 12]
    INITIAL_CAPITAL = 10000.0

    def calc_atr(h, l, c, period=14):
        tr1 = h - l
        tr2 = (h - c.shift(1)).abs()
        tr3 = (l - c.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def calc_adx(h, l, c, period=14):
        tr1 = h - l
        tr2 = (h - c.shift(1)).abs()
        tr3 = (l - c.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        plus_dm = h.diff().clip(lower=0)
        minus_dm = (-l.diff()).clip(lower=0)
        mask = plus_dm < minus_dm
        plus_dm[mask] = 0
        minus_dm[~mask] = 0
        plus_di = 100 * (plus_dm.rolling(period).mean() / (atr + 1e-10))
        minus_di = 100 * (minus_dm.rolling(period).mean() / (atr + 1e-10))
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di + 1e-10))
        adx = dx.rolling(period).mean()
        return adx

    def calc_rsi(close, period=14):
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / (loss + 1e-10)
        return 100 - 100 / (1 + rs)

    def detect_regime_num(close, atr_series, adx_series, idx):
        if idx < 60:
            return 2
        ema5 = close.iloc[max(0, idx-20):idx+1].ewm(span=5, adjust=False).mean().iloc[-1]
        ema20 = close.iloc[max(0, idx-40):idx+1].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = close.iloc[max(0, idx-80):idx+1].ewm(span=50, adjust=False).mean().iloc[-1]
        adx = adx_series.iloc[idx] if not pd.isna(adx_series.iloc[idx]) else 20
        price = close.iloc[idx]
        high_60 = close.iloc[max(0, idx-60):idx+1].max()
        dd = (price - high_60) / (high_60 + 1e-10)
        if dd < -0.15:
            return 4
        if adx > 25 and ema5 > ema20 > ema50:
            return 0
        if adx > 25 and ema5 < ema20 < ema50:
            return 1
        atr_val = atr_series.iloc[idx] if not pd.isna(atr_series.iloc[idx]) else 0
        atr_pct = atr_val / (price + 1e-10)
        if atr_pct > 0.04:
            return 3
        return 2

    all_samples = []
    asset_tiers = {}
    for sym in training_data_map:
        if sym in ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'SUI', 'TON', 'NEAR', 'APT', 'ATOM', 'LTC', 'TRX', 'HBAR']:
            asset_tiers[sym] = 1
        elif sym in ['DOGE', 'SHIB', 'PEPE', 'BONK', 'FLOKI', 'WIF']:
            asset_tiers[sym] = 3
        else:
            asset_tiers[sym] = 2

    for symbol, data in training_data_map.items():
        df_4h = data.get('4h')
        if df_4h is None or len(df_4h) < 100:
            continue

        c = df_4h['c'].astype(float)
        h = df_4h['h'].astype(float)
        l = df_4h['l'].astype(float)
        v = df_4h['v'].astype(float)
        atr = calc_atr(h, l, c)
        adx = calc_adx(h, l, c)
        rsi = calc_rsi(c)
        vol_20 = c.pct_change().rolling(20).std()
        tier = asset_tiers.get(symbol, 2)

        for idx in range(80, len(c) - max(HOLD_PERIODS) - 1, 2):
            price = c.iloc[idx]
            cur_atr = atr.iloc[idx]
            cur_adx = adx.iloc[idx]
            cur_rsi = rsi.iloc[idx]
            cur_vol = vol_20.iloc[idx]
            if pd.isna(cur_atr) or pd.isna(cur_adx) or price <= 0:
                continue

            regime = detect_regime_num(c, atr, adx, idx)
            atr_pct = cur_atr / price
            vol_val = cur_vol if not pd.isna(cur_vol) else 0.02

            ret_5 = (c.iloc[idx] / c.iloc[idx-5] - 1) if idx >= 5 else 0
            ret_20 = (c.iloc[idx] / c.iloc[idx-20] - 1) if idx >= 20 else 0
            peak = c.iloc[max(0, idx-60):idx+1].max()
            dd_pct = (price - peak) / (peak + 1e-10) * 100

            vol_rank = 0.5
            if idx >= 100:
                hist_vol = vol_20.iloc[max(0, idx-100):idx+1].dropna()
                if len(hist_vol) > 10:
                    vol_rank = float((hist_vol < vol_val).mean())

            features = {
                'regime': regime,
                'adx': float(cur_adx),
                'atr_pct': float(atr_pct),
                'rsi': float(cur_rsi) if not pd.isna(cur_rsi) else 50,
                'volatility': float(vol_val),
                'vol_rank': vol_rank,
                'ret_5': float(ret_5),
                'ret_20': float(ret_20),
                'drawdown_pct': float(dd_pct),
                'tier': tier,
            }

            best_score = -999
            best_size = 0.03

            for hold in HOLD_PERIODS:
                end_idx = min(idx + hold, len(c) - 1)
                future_high = h.iloc[idx+1:end_idx+1].max()
                future_low = l.iloc[idx+1:end_idx+1].min()
                final_price = c.iloc[end_idx]

                long_ret = (final_price - price) / price
                short_ret = (price - final_price) / price
                max_adverse_long = (price - future_low) / price
                max_adverse_short = (future_high - price) / price

                for direction_ret, max_adverse, direction in [
                    (long_ret, max_adverse_long, 'long'),
                    (short_ret, max_adverse_short, 'short'),
                ]:
                    for size_pct in POSITION_SIZES:
                        pnl = direction_ret * size_pct * INITIAL_CAPITAL
                        max_dd = max_adverse * size_pct * 100

                        if max_dd > 8:
                            risk_penalty = -5.0
                        elif max_dd > 5:
                            risk_penalty = -2.0
                        elif max_dd > 3:
                            risk_penalty = -0.5
                        else:
                            risk_penalty = 0

                        annualized = direction_ret * size_pct * (365 * 6 / hold) * 100
                        score = annualized + risk_penalty

                        if score > best_score:
                            best_score = score
                            best_size = size_pct

            noise = np.random.normal(0, 0.005)
            noisy_size = max(0.005, min(0.15, best_size + noise))
            features['optimal_size'] = round(noisy_size, 4)

            if noisy_size <= 0.02:
                features['risk_tier'] = 0
            elif noisy_size <= 0.05:
                features['risk_tier'] = 1
            elif noisy_size <= 0.10:
                features['risk_tier'] = 2
            else:
                features['risk_tier'] = 3

            all_samples.append(features)

        print(f"[Modal-MM] {symbol}: {len(c)-80} bars -> {len([s for s in all_samples if True])} cumulative samples")

    print(f"[Modal-MM] Total raw samples: {len(all_samples)}")
    return all_samples


def train_mm_model(samples):
    import numpy as np
    import json
    import joblib
    from datetime import datetime
    from collections import Counter
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_absolute_error, r2_score, accuracy_score
    import lightgbm as lgb

    feature_cols = ['regime', 'adx', 'atr_pct', 'rsi', 'volatility', 'vol_rank',
                    'ret_5', 'ret_20', 'drawdown_pct', 'tier']

    X = np.array([[s[f] for f in feature_cols] for s in samples], dtype=np.float64)
    y_size = np.array([s['optimal_size'] for s in samples], dtype=np.float64)
    y_tier = np.array([s['risk_tier'] for s in samples], dtype=int)

    np.nan_to_num(X, copy=False, nan=0.0, posinf=1e6, neginf=-1e6)

    n = len(X)
    split = int(n * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_size_train, y_size_test = y_size[:split], y_size[split:]
    y_tier_train, y_tier_test = y_tier[:split], y_tier[split:]

    print(f"[Modal-MM] Training: {len(X_train)} samples, Test: {len(X_test)} samples")
    print(f"[Modal-MM] Tier distribution train: {dict(Counter(y_tier_train))}")
    print(f"[Modal-MM] Tier distribution test: {dict(Counter(y_tier_test))}")
    print(f"[Modal-MM] Size stats: mean={y_size.mean():.4f} std={y_size.std():.4f}")

    lgbm_reg = lgb.LGBMRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.03,
        random_state=42, n_jobs=-1, verbose=-1,
        num_leaves=16, min_child_samples=50,
        reg_alpha=0.5, reg_lambda=0.5,
        subsample=0.7, colsample_bytree=0.7,
    )
    lgbm_reg.fit(X_train, y_size_train)

    y_pred_size = lgbm_reg.predict(X_test)
    y_pred_size = np.clip(y_pred_size, 0.01, 0.15)
    mae = mean_absolute_error(y_size_test, y_pred_size)
    r2 = r2_score(y_size_test, y_pred_size)

    def size_to_tier(s):
        if s <= 0.02: return 0
        if s <= 0.05: return 1
        if s <= 0.10: return 2
        return 3

    y_pred_tier = np.array([size_to_tier(s) for s in y_pred_size])
    tier_acc = accuracy_score(y_tier_test, y_pred_tier)

    cv_scores = []
    tscv = TimeSeriesSplit(n_splits=5)
    for train_idx, test_idx in tscv.split(X):
        temp_model = lgb.LGBMRegressor(
            n_estimators=150, max_depth=6, learning_rate=0.05,
            random_state=42, n_jobs=-1, verbose=-1,
        )
        temp_model.fit(X[train_idx], y_size[train_idx])
        pred = temp_model.predict(X[test_idx])
        cv_scores.append(mean_absolute_error(y_size[test_idx], pred))
    cv_mae_mean = np.mean(cv_scores)
    cv_mae_std = np.std(cv_scores)

    importances = dict(zip(feature_cols, [round(float(v)*100, 2) for v in lgbm_reg.feature_importances_ / lgbm_reg.feature_importances_.sum()]))

    print(f"[Modal-MM] Results: MAE={mae:.4f} R2={r2:.3f} TierAcc={tier_acc*100:.1f}%")
    print(f"[Modal-MM] CV MAE: {cv_mae_mean:.4f} ± {cv_mae_std:.4f}")
    print(f"[Modal-MM] Feature importance: {importances}")

    model_path = "/vol/titan_mm_model.pkl"
    metrics_path = "/vol/titan_mm_metrics.json"
    joblib.dump(lgbm_reg, model_path)

    metrics = {
        "model_type": "LightGBM_Regressor",
        "target": "optimal_position_size",
        "mae": round(mae, 5),
        "r2": round(r2, 4),
        "tier_accuracy": round(tier_acc * 100, 1),
        "cv_mae": round(cv_mae_mean, 5),
        "cv_mae_std": round(cv_mae_std, 5),
        "samples_total": len(X),
        "samples_train": len(X_train),
        "samples_test": len(X_test),
        "tier_distribution": dict(Counter(int(v) for v in y_tier)),
        "feature_names": feature_cols,
        "feature_importance": importances,
        "size_stats": {
            "mean": round(float(y_size.mean()), 4),
            "std": round(float(y_size.std()), 4),
            "median": round(float(np.median(y_size)), 4),
        },
        "last_train": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trained_on": "modal_cloud",
    }

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"[Modal-MM] Model saved. Size stats: mean={y_size.mean():.4f} median={np.median(y_size):.4f}")
    return {"success": True, "metrics": metrics}


@app.function(
    image=training_image,
    cpu=8.0,
    memory=8192,
    timeout=1800,
    volumes={"/vol": model_volume},
)
def train_titan_mm(symbols: list = None, max_assets: int = 69):
    import time as _time
    start = _time.time()

    if symbols is None:
        symbols = ELITE_UNIVERSE

    print(f"[Modal-MM] Starting MM training: {len(symbols[:max_assets])} assets")

    training_data = fetch_all_training_data(symbols[:max_assets])

    if not training_data:
        return {"success": False, "error": "No training data", "elapsed": round(_time.time() - start, 1)}

    print(f"[Modal-MM] Data fetched: {len(training_data)} assets, generating samples...")

    samples = generate_mm_training_data(training_data)

    if len(samples) < 1000:
        return {"success": False, "error": f"Insufficient samples: {len(samples)}", "elapsed": round(_time.time() - start, 1)}

    result = train_mm_model(samples)
    result["elapsed"] = round(_time.time() - start, 1)
    result["assets_fetched"] = len(training_data)

    if result.get("success"):
        model_volume.commit()

    return result


@app.function(
    image=training_image,
    cpu=1.0,
    memory=512,
    timeout=60,
    volumes={"/vol": model_volume},
)
def download_mm_model():
    import joblib
    import json

    model_volume.reload()

    model_path = "/vol/titan_mm_model.pkl"
    metrics_path = "/vol/titan_mm_metrics.json"

    result = {"success": False}

    if os.path.exists(model_path):
        model_bytes = open(model_path, "rb").read()
        result["model"] = model_bytes
        result["success"] = True
    else:
        result["error"] = "MM model not found"
        return result

    if os.path.exists(metrics_path):
        with open(metrics_path, "r") as f:
            result["metrics"] = json.load(f)

    return result


@app.function(
    image=training_image,
    cpu=8.0,
    memory=8192,
    timeout=3600,
    volumes={"/vol": model_volume},
)
def train_deep_all(symbols: list = None, max_assets: int = 69):
    import time as _time
    start = _time.time()

    if symbols is None:
        symbols = ELITE_UNIVERSE

    target_symbols = symbols[:max_assets]
    print(f"[Modal-DeepAll] 全量深度训练启动: {len(target_symbols)} 个资产")
    print(f"[Modal-DeepAll] Stage 1/2: 获取历史数据...")

    training_data = fetch_all_training_data(target_symbols)

    if not training_data:
        return {"success": False, "error": "无法获取训练数据", "elapsed": round(_time.time() - start, 1)}

    total_1h = sum(len(v.get('1h', [])) for v in training_data.values())
    total_4h = sum(len(v.get('4h', [])) for v in training_data.values())
    total_1d = sum(len(v.get('1d', [])) for v in training_data.values() if '1d' in v)
    print(f"[Modal-DeepAll] 数据获取完成: {len(training_data)} 资产, 1h={total_1h} 4h={total_4h} 1d={total_1d}")

    data_elapsed = round(_time.time() - start, 1)
    print(f"[Modal-DeepAll] 数据获取耗时: {data_elapsed}秒")

    print(f"[Modal-DeepAll] Stage 1: Alpha ML 训练...")
    alpha_result = run_training_pipeline(training_data)
    alpha_elapsed = round(_time.time() - start - data_elapsed, 1)
    print(f"[Modal-DeepAll] Alpha训练耗时: {alpha_elapsed}秒, 成功={alpha_result.get('success')}")

    print(f"[Modal-DeepAll] Stage 2: MM 模型训练...")
    mm_samples = generate_mm_training_data(training_data)
    mm_result = {"success": False, "error": "样本不足"}
    if len(mm_samples) >= 1000:
        mm_result = train_mm_model(mm_samples)
    mm_elapsed = round(_time.time() - start - data_elapsed - alpha_elapsed, 1)
    print(f"[Modal-DeepAll] MM训练耗时: {mm_elapsed}秒, 成功={mm_result.get('success')}, 样本={len(mm_samples)}")

    total_elapsed = round(_time.time() - start, 1)

    ohlcv_cache = {}
    for sym, data in training_data.items():
        df_1h = data.get('1h')
        if df_1h is not None and len(df_1h) > 100:
            ohlcv_cache[sym] = df_1h.values.tolist()

    if alpha_result.get("success") or mm_result.get("success"):
        model_volume.commit()

    result = {
        "success": alpha_result.get("success", False) or mm_result.get("success", False),
        "alpha": {
            "success": alpha_result.get("success", False),
            "metrics": alpha_result.get("metrics"),
            "error": alpha_result.get("error"),
        },
        "mm": {
            "success": mm_result.get("success", False),
            "metrics": mm_result.get("metrics"),
            "error": mm_result.get("error"),
        },
        "assets_fetched": len(training_data),
        "data_stats": {"1h": total_1h, "4h": total_4h, "1d": total_1d},
        "elapsed": total_elapsed,
        "elapsed_detail": {"data": data_elapsed, "alpha": alpha_elapsed, "mm": mm_elapsed},
        "ohlcv_cache_keys": list(ohlcv_cache.keys()),
    }

    import json
    cache_path = "/vol/titan_ohlcv_cache.json"
    try:
        with open(cache_path, "w") as f:
            json.dump(ohlcv_cache, f)
        model_volume.commit()
        result["ohlcv_cached"] = True
        print(f"[Modal-DeepAll] OHLCV缓存已保存: {len(ohlcv_cache)}个资产")
    except Exception as e:
        result["ohlcv_cached"] = False
        print(f"[Modal-DeepAll] OHLCV缓存保存失败: {e}")

    print(f"[Modal-DeepAll] 全量训练完成! 总耗时={total_elapsed}秒")
    return result


@app.function(
    image=training_image,
    cpu=1.0,
    memory=1024,
    timeout=120,
    volumes={"/vol": model_volume},
)
def download_deep_all_models():
    import joblib
    import json

    model_volume.reload()

    alpha_model_path = "/vol/titan_ml_model.pkl"
    alpha_metrics_path = "/vol/titan_ml_metrics.json"
    meta_path = "/vol/titan_meta_labeler.pkl"
    mm_model_path = "/vol/titan_mm_model.pkl"
    mm_metrics_path = "/vol/titan_mm_metrics.json"
    ohlcv_cache_path = "/vol/titan_ohlcv_cache.json"

    result = {"success": False, "alpha": {}, "mm": {}}

    if os.path.exists(alpha_model_path):
        result["alpha"]["model"] = open(alpha_model_path, "rb").read()
        result["alpha"]["has_model"] = True
        if os.path.exists(alpha_metrics_path):
            with open(alpha_metrics_path) as f:
                result["alpha"]["metrics"] = json.load(f)
        if os.path.exists(meta_path):
            result["alpha"]["meta_labeler"] = open(meta_path, "rb").read()
        result["success"] = True
    else:
        result["alpha"]["has_model"] = False

    if os.path.exists(mm_model_path):
        result["mm"]["model"] = open(mm_model_path, "rb").read()
        result["mm"]["has_model"] = True
        if os.path.exists(mm_metrics_path):
            with open(mm_metrics_path) as f:
                result["mm"]["metrics"] = json.load(f)
    else:
        result["mm"]["has_model"] = False

    if os.path.exists(ohlcv_cache_path):
        with open(ohlcv_cache_path) as f:
            result["ohlcv_cache"] = json.load(f)

    return result


@app.function(
    image=training_image,
    cpu=8.0,
    memory=8192,
    timeout=1800,
    volumes={"/vol": model_volume},
    schedule=modal.Cron("0 4 * * *"),
)
def scheduled_daily_training():
    print("[Modal] 定时每日训练启动...")
    result = train_deep_all.local(symbols=ELITE_UNIVERSE, max_assets=69)
    print(f"[Modal] 全量训练完成: Alpha={result.get('alpha',{}).get('success')}, MM={result.get('mm',{}).get('success')}")
    return result
