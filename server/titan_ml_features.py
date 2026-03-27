import numpy as np
import pandas as pd
import logging
from typing import Dict, Optional, List

logger = logging.getLogger("TitanMLFeatures")


class TitanFeatureStore:
    FEATURE_GROUPS = {
        'momentum': [
            'rsi_14_1h', 'rsi_14_4h', 'rsi_divergence',
            'macd_hist_1h', 'macd_signal_cross',
            'roc_5_1h', 'roc_10_1h', 'roc_20_4h',
            'momentum_rank_20',
        ],
        'trend': [
            'adx_14_4h', 'di_plus_minus_4h',
            'ema_cross_12_26', 'ema_slope_20',
            'trend_efficiency_5', 'trend_efficiency_20',
            'hurst_exponent',
            'psar_direction', 'psar_distance',
            'frac_diff_close',
        ],
        'volatility': [
            'bb_position', 'bb_width',
            'keltner_position',
            'atr_ratio_14', 'atr_percentile',
            'return_volatility_20',
            'vol_of_vol',
            'garman_klass_vol',
        ],
        'volume': [
            'volume_ratio_20', 'volume_trend_5_20',
            'obv_slope_5', 'obv_divergence',
            'mfi_14_1h',
            'vwap_ratio',
            'amihud_illiquidity',
            'kyle_lambda',
        ],
        'structure': [
            'market_structure',
            'donchian_position', 'vpoc_distance',
            'drawdown_from_high_20', 'rally_from_low_20',
            'consecutive_direction',
        ],
        'entropy': [
            'return_entropy_20',
            'volume_entropy_20',
            'price_complexity',
        ],
        'daily': [
            'daily_rsi', 'daily_adx', 'daily_bb_position',
            'daily_return_5d', 'daily_return_20d',
            'daily_volatility',
        ],
        'external': [
            'ext_fng', 'ext_fng_change',
            'ext_risk_mode',
            'ext_funding_rate_btc', 'ext_funding_rate_eth',
            'ext_funding_rate_momentum',
            'ext_oi_price_divergence',
            'ext_liq_imbalance',
            'ext_liq_intensity',
        ],
        'wq_alpha': [
            'wq_alpha1', 'wq_alpha2', 'wq_alpha6', 'wq_alpha12', 'wq_alpha14',
            'wq_alpha18', 'wq_alpha21', 'wq_alpha23', 'wq_alpha34', 'wq_alpha38',
            'wq_alpha41', 'wq_alpha43', 'wq_alpha44', 'wq_alpha53', 'wq_alpha101',
            'wq_alpha_mom_revert', 'wq_alpha_vol_price_div', 'wq_alpha_range_pos',
            'wq_alpha_co_hv', 'wq_alpha_vol_accel',
            'wq_alpha3', 'wq_alpha5', 'wq_alpha8', 'wq_alpha9', 'wq_alpha10',
            'wq_alpha13', 'wq_alpha15', 'wq_alpha16', 'wq_alpha17', 'wq_alpha20',
            'wq_alpha24', 'wq_alpha26', 'wq_alpha28', 'wq_alpha29', 'wq_alpha30',
            'wq_alpha33', 'wq_alpha35', 'wq_alpha37', 'wq_alpha40', 'wq_alpha42',
            'wq_alpha45', 'wq_alpha46', 'wq_alpha47', 'wq_alpha49', 'wq_alpha50',
            'wq_alpha51', 'wq_alpha52', 'wq_alpha54', 'wq_alpha55', 'wq_alpha56',
        ],
    }

    @staticmethod
    def get_all_feature_names() -> List[str]:
        names = []
        for group in TitanFeatureStore.FEATURE_GROUPS.values():
            names.extend(group)
        return sorted(set(names))

    @staticmethod
    def extract_features(df_1h: pd.DataFrame, df_4h: pd.DataFrame,
                         df_1d: Optional[pd.DataFrame] = None,
                         ext_data: Optional[Dict] = None) -> Optional[Dict[str, float]]:
        if len(df_1h) < 60 or len(df_4h) < 30:
            return None

        features = {}
        c1 = df_1h['c'].astype(float)
        h1 = df_1h['h'].astype(float)
        l1 = df_1h['l'].astype(float)
        o1 = df_1h['o'].astype(float)
        v1 = df_1h['v'].astype(float)
        c4 = df_4h['c'].astype(float)
        h4 = df_4h['h'].astype(float)
        l4 = df_4h['l'].astype(float)
        o4 = df_4h['o'].astype(float)
        v4 = df_4h['v'].astype(float)
        price = c4.iloc[-1]

        features.update(_momentum_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4))
        features.update(_trend_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4, price))
        features.update(_volatility_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4, price))
        features.update(_volume_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4, price))
        features.update(_structure_features(c1, h1, l1, c4, h4, l4, o4, price))
        features.update(_entropy_features(c1, v1))
        features.update(_daily_features(df_1d))
        features.update(_external_features(ext_data))
        features.update(_worldquant_alphas(c4, h4, l4, o4, v4))

        for k, v in features.items():
            if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
                features[k] = 0.0

        return features

    @staticmethod
    def build_feature_matrix(df_1h: pd.DataFrame, df_4h: pd.DataFrame,
                             df_1d: Optional[pd.DataFrame] = None,
                             ext_data: Optional[Dict] = None,
                             horizon: int = 4) -> Optional[tuple]:
        if len(df_1h) < 100 or len(df_4h) < 40:
            return None

        c1 = df_1h['c'].astype(float)
        h1 = df_1h['h'].astype(float)
        l1 = df_1h['l'].astype(float)
        o1 = df_1h['o'].astype(float)
        v1 = df_1h['v'].astype(float)
        c4 = df_4h['c'].astype(float)
        h4 = df_4h['h'].astype(float)
        l4 = df_4h['l'].astype(float)
        o4 = df_4h['o'].astype(float)
        v4 = df_4h['v'].astype(float)

        momentum_series = _momentum_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4)
        trend_series = _trend_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4)
        vol_series = _volatility_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4)
        volume_series = _volume_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4)
        struct_series = _structure_series(c1, h1, l1, c4, h4, l4, o4)
        entropy_series = _entropy_series(c1, v1)
        daily_series = _daily_series(df_1d)
        wq_series = _wq_alpha_series(c4, h4, l4, o4, v4)
        ext_snapshot = _external_features(ext_data)

        feature_names = TitanFeatureStore.get_all_feature_names()
        all_series = {**momentum_series, **trend_series, **vol_series,
                      **volume_series, **struct_series, **entropy_series,
                      **daily_series, **wq_series}

        start_idx = 60
        end_idx = len(c1) - horizon
        rows = []

        for i in range(start_idx, end_idx):
            i4 = min(i // 4, len(c4) - 1)
            if i4 < 30:
                continue
            i_d = min(i // 24, (len(df_1d) - 1) if df_1d is not None else 0)

            feat = {}
            for name in feature_names:
                if name.startswith('ext_'):
                    feat[name] = ext_snapshot.get(name, 0.0)
                elif name.startswith('daily_'):
                    s = all_series.get(name)
                    if s is not None and i_d < len(s):
                        val = s.iloc[i_d]
                        feat[name] = float(val) if not pd.isna(val) else 0.0
                    else:
                        feat[name] = 0.0
                elif name.startswith('wq_') or name in ['adx_14_4h', 'di_plus_minus_4h', 'bb_position',
                    'bb_width', 'atr_ratio_14', 'atr_percentile', 'return_volatility_20', 'vol_of_vol',
                    'garman_klass_vol', 'roc_20_4h', 'trend_efficiency_5', 'trend_efficiency_20',
                    'drawdown_from_high_20', 'rally_from_low_20']:
                    s = all_series.get(name)
                    if s is not None and i4 < len(s):
                        val = s.iloc[i4]
                        feat[name] = float(val) if not pd.isna(val) else 0.0
                    else:
                        feat[name] = 0.0
                else:
                    s = all_series.get(name)
                    if s is not None and i < len(s):
                        val = s.iloc[i]
                        feat[name] = float(val) if not pd.isna(val) else 0.0
                    else:
                        feat[name] = 0.0

            for k, v in feat.items():
                if np.isnan(v) or np.isinf(v):
                    feat[k] = 0.0

            row = [feat.get(n, 0.0) for n in feature_names]
            future_price = c1.iloc[i + horizon] if (i + horizon) < len(c1) else c1.iloc[-1]
            current_price = c1.iloc[i]
            ret = (future_price - current_price) / (current_price + 1e-10)
            row.append(float(ret))
            rows.append(row)

        if not rows:
            return None

        cols = feature_names + ['ret']
        df = pd.DataFrame(rows, columns=cols)
        return df, feature_names


def _safe(val, default=0.0):
    if val is None or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
        return default
    return float(val)


def _rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / (loss + 1e-10)
    return 100 - (100 / (1 + rs))


def _atr(h, l, c, period=14):
    tr = pd.concat([h - l, abs(h - c.shift(1)), abs(l - c.shift(1))], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _slope(series, window=5):
    x = np.arange(window, dtype=float)
    xm = x.mean()
    xdev = x - xm
    xss = (xdev ** 2).sum()
    def _s(w):
        return np.dot(xdev, w - w.mean()) / xss
    return series.rolling(window).apply(_s, raw=True)


def _hurst_exponent(series, max_lag=20):
    if isinstance(series, np.ndarray):
        series = pd.Series(series)
    if len(series) < max_lag * 2:
        return 0.5
    try:
        clean = series.dropna()
        if len(clean) < max_lag * 2:
            return 0.5
        lags = range(2, max_lag)
        tau = []
        for lag in lags:
            pp = clean.diff(lag).dropna()
            if len(pp) == 0:
                return 0.5
            tau.append(np.sqrt(np.abs(pp).mean()))
        if len(tau) < 2:
            return 0.5
        log_lags = np.log(np.array(list(lags), dtype=float))
        log_tau = np.log(np.array(tau, dtype=float))
        mask = np.isfinite(log_lags) & np.isfinite(log_tau)
        if mask.sum() < 2:
            return 0.5
        poly = np.polyfit(log_lags[mask], log_tau[mask], 1)
        val = float(poly[0])
        return float(np.clip(val, 0.0, 1.0)) if np.isfinite(val) else 0.5
    except Exception:
        return 0.5


def _fractional_diff(series, d=0.4, thresh=1e-5):
    w = [1.0]
    k = 1
    while True:
        w_k = -w[-1] * (d - k + 1) / k
        if abs(w_k) < thresh:
            break
        w.append(w_k)
        k += 1
        if k > 100:
            break
    w = np.array(w)
    width = len(w)
    result = pd.Series(index=series.index, dtype=float)
    for i in range(width - 1, len(series)):
        result.iloc[i] = np.dot(w, series.iloc[i - width + 1:i + 1].values[::-1])
    return result


def _shannon_entropy(series, bins=10, window=20):
    result = pd.Series(np.nan, index=series.index)
    for i in range(window, len(series)):
        w = series.iloc[i - window:i].values
        w_clean = w[np.isfinite(w)]
        if len(w_clean) < 3 or np.std(w_clean) < 1e-10:
            result.iloc[i] = 0.0
            continue
        try:
            counts, _ = np.histogram(w_clean, bins=bins)
            probs = counts / counts.sum()
            probs = probs[probs > 0]
            result.iloc[i] = -np.sum(probs * np.log2(probs))
        except (ValueError, FloatingPointError):
            result.iloc[i] = 0.0
    return result


def _kyle_lambda(close, volume, window=20):
    result = pd.Series(0.0, index=close.index)
    ret = close.pct_change()
    for i in range(window, len(close)):
        r = ret.iloc[i - window:i].values
        v = volume.iloc[i - window:i].values
        mask = np.isfinite(r) & np.isfinite(v)
        if mask.sum() < 5:
            continue
        r_clean = r[mask]
        signed_vol = np.sign(r_clean) * v[mask]
        if np.std(signed_vol) < 1e-10:
            continue
        try:
            poly = np.polyfit(signed_vol, r_clean, 1)
            result.iloc[i] = float(poly[0]) if np.isfinite(poly[0]) else 0.0
        except Exception:
            pass
    return result


def _amihud_illiquidity(close, volume, window=20):
    ret = close.pct_change().abs()
    dollar_vol = close * volume + 1e-10
    ratio = ret / dollar_vol
    return ratio.rolling(window).mean()


def _garman_klass_vol(h, l, o, c, window=20):
    log_hl = np.log(h / (l + 1e-10)) ** 2
    log_co = np.log(c / (o + 1e-10)) ** 2
    gk = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
    return gk.rolling(window).mean().apply(lambda x: np.sqrt(abs(x)) if not np.isnan(x) else 0.0)


def _momentum_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4):
    f = {}
    rsi1 = _rsi(c1, 14)
    rsi4 = _rsi(c4, 14)
    f['rsi_14_1h'] = _safe(rsi1.iloc[-1], 50.0)
    f['rsi_14_4h'] = _safe(rsi4.iloc[-1], 50.0)
    f['rsi_divergence'] = f['rsi_14_1h'] - f['rsi_14_4h']

    ema12 = c1.ewm(span=12, adjust=False).mean()
    ema26 = c1.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    f['macd_hist_1h'] = _safe(hist.iloc[-1])
    f['macd_signal_cross'] = 1.0 if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2] else \
                             (-1.0 if macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2] else 0.0)

    f['roc_5_1h'] = _safe((c1.iloc[-1] / (c1.iloc[-6] + 1e-10) - 1) * 100)
    f['roc_10_1h'] = _safe((c1.iloc[-1] / (c1.iloc[-11] + 1e-10) - 1) * 100)
    f['roc_20_4h'] = _safe((c4.iloc[-1] / (c4.iloc[-21] + 1e-10) - 1) * 100) if len(c4) > 21 else 0.0

    rank_20 = c1.pct_change().rolling(20).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
    f['momentum_rank_20'] = _safe(rank_20.iloc[-1], 0.5)

    return f


def _momentum_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4):
    s = {}
    s['rsi_14_1h'] = _rsi(c1, 14)
    rsi4 = _rsi(c4, 14)
    s['rsi_14_4h'] = rsi4
    s['rsi_divergence'] = s['rsi_14_1h'] - rsi4.reindex(range(len(c1))).ffill().reindex(c1.index, method='ffill').fillna(50)

    ema12 = c1.ewm(span=12, adjust=False).mean()
    ema26 = c1.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    s['macd_hist_1h'] = macd - signal

    macd_cross = pd.Series(0.0, index=c1.index)
    for i in range(1, len(macd)):
        if macd.iloc[i] > signal.iloc[i] and macd.iloc[i-1] <= signal.iloc[i-1]:
            macd_cross.iloc[i] = 1.0
        elif macd.iloc[i] < signal.iloc[i] and macd.iloc[i-1] >= signal.iloc[i-1]:
            macd_cross.iloc[i] = -1.0
    s['macd_signal_cross'] = macd_cross

    s['roc_5_1h'] = (c1 / c1.shift(5) - 1) * 100
    s['roc_10_1h'] = (c1 / c1.shift(10) - 1) * 100
    s['roc_20_4h'] = (c4 / c4.shift(20) - 1) * 100

    s['momentum_rank_20'] = c1.pct_change().rolling(20).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)

    return s


def _trend_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4, price):
    f = {}
    atr4 = _atr(h4, l4, c4)
    plus_dm = h4.diff().clip(lower=0)
    minus_dm = (-l4.diff()).clip(lower=0)
    p_di = 100 * (plus_dm.rolling(14).mean() / (atr4 + 1e-10))
    m_di = 100 * (minus_dm.rolling(14).mean() / (atr4 + 1e-10))
    dx = 100 * abs(p_di - m_di) / (p_di + m_di + 1e-10)
    adx = dx.rolling(14).mean()
    f['adx_14_4h'] = _safe(adx.iloc[-1], 15.0)
    f['di_plus_minus_4h'] = _safe((p_di.iloc[-1] - m_di.iloc[-1]))

    ema12 = c1.ewm(span=12, adjust=False).mean()
    ema26 = c1.ewm(span=26, adjust=False).mean()
    f['ema_cross_12_26'] = 1.0 if ema12.iloc[-1] > ema26.iloc[-1] else -1.0

    ema20 = c1.ewm(span=20, adjust=False).mean()
    f['ema_slope_20'] = _safe(_slope(ema20, 5).iloc[-1])

    diff_abs_5 = c4.diff().abs().rolling(5).sum()
    f['trend_efficiency_5'] = _safe((c4.iloc[-1] - c4.iloc[-5]) / (diff_abs_5.iloc[-1] + 1e-10)) if len(c4) > 5 else 0.0
    diff_abs_20 = c4.diff().abs().rolling(20).sum()
    f['trend_efficiency_20'] = _safe((c4.iloc[-1] - c4.iloc[-20]) / (diff_abs_20.iloc[-1] + 1e-10)) if len(c4) > 20 else 0.0

    f['hurst_exponent'] = _hurst_exponent(c1.iloc[-100:].values)

    n = len(c1)
    psar_val = c1.copy()
    bull = True
    af = 0.02
    hp_v = h1.iloc[0]
    lp_v = l1.iloc[0]
    for i in range(1, n):
        if bull:
            psar_val.iloc[i] = psar_val.iloc[i-1] + af * (hp_v - psar_val.iloc[i-1])
            if l1.iloc[i] < psar_val.iloc[i]:
                bull = False
                psar_val.iloc[i] = hp_v
                lp_v = l1.iloc[i]
                af = 0.02
            else:
                if h1.iloc[i] > hp_v:
                    hp_v = h1.iloc[i]
                    af = min(af + 0.02, 0.20)
        else:
            psar_val.iloc[i] = psar_val.iloc[i-1] + af * (lp_v - psar_val.iloc[i-1])
            if h1.iloc[i] > psar_val.iloc[i]:
                bull = True
                psar_val.iloc[i] = lp_v
                hp_v = h1.iloc[i]
                af = 0.02
            else:
                if l1.iloc[i] < lp_v:
                    lp_v = l1.iloc[i]
                    af = min(af + 0.02, 0.20)
    f['psar_direction'] = 1.0 if c1.iloc[-1] > psar_val.iloc[-1] else -1.0
    f['psar_distance'] = _safe((c1.iloc[-1] - psar_val.iloc[-1]) / (c1.iloc[-1] + 1e-10))

    fd = _fractional_diff(np.log(c1 + 1e-10), d=0.4)
    f['frac_diff_close'] = _safe(fd.iloc[-1])

    return f


def _trend_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4):
    s = {}
    atr4 = _atr(h4, l4, c4)
    plus_dm = h4.diff().clip(lower=0)
    minus_dm = (-l4.diff()).clip(lower=0)
    p_di = 100 * (plus_dm.rolling(14).mean() / (atr4 + 1e-10))
    m_di = 100 * (minus_dm.rolling(14).mean() / (atr4 + 1e-10))
    dx = 100 * abs(p_di - m_di) / (p_di + m_di + 1e-10)
    s['adx_14_4h'] = dx.rolling(14).mean()
    s['di_plus_minus_4h'] = p_di - m_di

    ema12 = c1.ewm(span=12, adjust=False).mean()
    ema26 = c1.ewm(span=26, adjust=False).mean()
    s['ema_cross_12_26'] = (ema12 > ema26).astype(float) * 2 - 1

    ema20 = c1.ewm(span=20, adjust=False).mean()
    s['ema_slope_20'] = _slope(ema20, 5)

    diff_abs_5 = c4.diff().abs().rolling(5).sum()
    s['trend_efficiency_5'] = (c4 - c4.shift(4)) / (diff_abs_5 + 1e-10)
    diff_abs_20 = c4.diff().abs().rolling(20).sum()
    s['trend_efficiency_20'] = (c4 - c4.shift(19)) / (diff_abs_20 + 1e-10)

    hurst_s = pd.Series(0.5, index=c1.index)
    for i in range(100, len(c1)):
        hurst_s.iloc[i] = _hurst_exponent(c1.iloc[i-100:i].values)
    s['hurst_exponent'] = hurst_s

    n = len(c1)
    psar_dir = pd.Series(1.0, index=c1.index)
    psar_dist = pd.Series(0.0, index=c1.index)
    psar_v = c1.copy()
    bull = True
    af = 0.02
    hp_v = h1.iloc[0]
    lp_v = l1.iloc[0]
    for i in range(1, n):
        if bull:
            psar_v.iloc[i] = psar_v.iloc[i-1] + af * (hp_v - psar_v.iloc[i-1])
            if l1.iloc[i] < psar_v.iloc[i]:
                bull = False
                psar_v.iloc[i] = hp_v
                lp_v = l1.iloc[i]
                af = 0.02
            elif h1.iloc[i] > hp_v:
                hp_v = h1.iloc[i]
                af = min(af + 0.02, 0.20)
        else:
            psar_v.iloc[i] = psar_v.iloc[i-1] + af * (lp_v - psar_v.iloc[i-1])
            if h1.iloc[i] > psar_v.iloc[i]:
                bull = True
                psar_v.iloc[i] = lp_v
                hp_v = h1.iloc[i]
                af = 0.02
            elif l1.iloc[i] < lp_v:
                lp_v = l1.iloc[i]
                af = min(af + 0.02, 0.20)
        psar_dir.iloc[i] = 1.0 if c1.iloc[i] > psar_v.iloc[i] else -1.0
        psar_dist.iloc[i] = (c1.iloc[i] - psar_v.iloc[i]) / (c1.iloc[i] + 1e-10)
    s['psar_direction'] = psar_dir
    s['psar_distance'] = psar_dist

    fd = _fractional_diff(np.log(c1 + 1e-10), d=0.4)
    s['frac_diff_close'] = fd

    return s


def _volatility_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4, price):
    f = {}
    ma20 = c4.rolling(20).mean()
    std20 = c4.rolling(20).std()
    bb_up = ma20 + 2 * std20
    bb_low = ma20 - 2 * std20
    bb_w = bb_up - bb_low
    f['bb_position'] = _safe((price - bb_low.iloc[-1]) / (bb_w.iloc[-1] + 1e-10), 0.5)
    f['bb_width'] = _safe(bb_w.iloc[-1] / (ma20.iloc[-1] + 1e-10), 0.05)

    ema_k = c1.ewm(span=20, adjust=False).mean()
    atr_k = _atr(h1, l1, c1, 14)
    k_up = ema_k + 2 * atr_k
    k_low = ema_k - 2 * atr_k
    f['keltner_position'] = _safe((c1.iloc[-1] - k_low.iloc[-1]) / (k_up.iloc[-1] - k_low.iloc[-1] + 1e-10), 0.5)

    atr4 = _atr(h4, l4, c4)
    f['atr_ratio_14'] = _safe(atr4.iloc[-1] / (price + 1e-10), 0.02)
    atr_ma50 = atr4.rolling(50).mean()
    f['atr_percentile'] = _safe(atr4.iloc[-1] / (atr_ma50.iloc[-1] + 1e-10), 1.0)

    ret_vol = c4.pct_change().rolling(20).std()
    f['return_volatility_20'] = _safe(ret_vol.iloc[-1], 0.02)

    vol_of_vol = ret_vol.rolling(10).std()
    f['vol_of_vol'] = _safe(vol_of_vol.iloc[-1], 0.01)

    gk = _garman_klass_vol(h4, l4, o4, c4)
    f['garman_klass_vol'] = _safe(gk.iloc[-1], 0.02)

    return f


def _volatility_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4):
    s = {}
    ma20 = c4.rolling(20).mean()
    std20 = c4.rolling(20).std()
    bb_up = ma20 + 2 * std20
    bb_low = ma20 - 2 * std20
    bb_w = bb_up - bb_low
    s['bb_position'] = (c4 - bb_low) / (bb_w + 1e-10)
    s['bb_width'] = bb_w / (ma20 + 1e-10)

    ema_k = c1.ewm(span=20, adjust=False).mean()
    atr_k = _atr(h1, l1, c1, 14)
    k_up = ema_k + 2 * atr_k
    k_low = ema_k - 2 * atr_k
    s['keltner_position'] = (c1 - k_low) / (k_up - k_low + 1e-10)

    atr4 = _atr(h4, l4, c4)
    s['atr_ratio_14'] = atr4 / (c4 + 1e-10)
    atr_ma50 = atr4.rolling(50).mean()
    s['atr_percentile'] = atr4 / (atr_ma50 + 1e-10)

    ret_vol = c4.pct_change().rolling(20).std()
    s['return_volatility_20'] = ret_vol
    s['vol_of_vol'] = ret_vol.rolling(10).std()
    s['garman_klass_vol'] = _garman_klass_vol(h4, l4, o4, c4)

    return s


def _volume_features(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4, price):
    f = {}
    vol_ma20 = v1.rolling(20).mean()
    f['volume_ratio_20'] = _safe(v1.iloc[-1] / (vol_ma20.iloc[-1] + 1e-10), 1.0)

    vol_sma5 = v1.rolling(5).mean()
    f['volume_trend_5_20'] = _safe(vol_sma5.iloc[-1] / (vol_ma20.iloc[-1] + 1e-10), 1.0)

    obv = (np.sign(c1.diff()) * v1).fillna(0).cumsum()
    f['obv_slope_5'] = _safe(_slope(obv, 5).iloc[-1])
    obv_ma = obv.rolling(20).mean()
    f['obv_divergence'] = _safe((obv.iloc[-1] - obv_ma.iloc[-1]) / (abs(obv_ma.iloc[-1]) + 1e-10))

    tp = (h1 + l1 + c1) / 3
    rmf = tp * v1
    ch = tp.diff()
    fp = rmf.where(ch > 0, 0).rolling(14).sum()
    fn = rmf.where(ch <= 0, 0).rolling(14).sum()
    mfi = 100 - (100 / (1 + fp / (fn + 1e-10)))
    f['mfi_14_1h'] = _safe(mfi.iloc[-1], 50.0)

    vwap = (tp * v1).cumsum() / (v1.cumsum() + 1e-10)
    f['vwap_ratio'] = _safe(price / (vwap.iloc[-1] + 1e-10), 1.0)

    f['amihud_illiquidity'] = _safe(_amihud_illiquidity(c1, v1).iloc[-1])
    f['kyle_lambda'] = _safe(_kyle_lambda(c1, v1).iloc[-1])

    return f


def _volume_series(c1, h1, l1, o1, v1, c4, h4, l4, o4, v4):
    s = {}
    vol_ma20 = v1.rolling(20).mean()
    s['volume_ratio_20'] = v1 / (vol_ma20 + 1e-10)
    vol_sma5 = v1.rolling(5).mean()
    s['volume_trend_5_20'] = vol_sma5 / (vol_ma20 + 1e-10)

    obv = (np.sign(c1.diff()) * v1).fillna(0).cumsum()
    s['obv_slope_5'] = _slope(obv, 5)
    obv_ma = obv.rolling(20).mean()
    s['obv_divergence'] = (obv - obv_ma) / (obv_ma.abs() + 1e-10)

    tp = (h1 + l1 + c1) / 3
    rmf = tp * v1
    ch = tp.diff()
    fp = rmf.where(ch > 0, 0).rolling(14).sum()
    fn = rmf.where(ch <= 0, 0).rolling(14).sum()
    s['mfi_14_1h'] = 100 - (100 / (1 + fp / (fn + 1e-10)))

    vwap = (tp * v1).cumsum() / (v1.cumsum() + 1e-10)
    s['vwap_ratio'] = c1 / (vwap + 1e-10)

    s['amihud_illiquidity'] = _amihud_illiquidity(c1, v1)
    s['kyle_lambda'] = _kyle_lambda(c1, v1)

    return s


def _structure_features(c1, h1, l1, c4, h4, l4, o4, price):
    f = {}
    lb = 5
    n = len(h1)
    if n > lb * 2:
        sh, sl = [], []
        for i in range(lb, n - lb):
            seg = h1.iloc[i-lb:i+lb+1]
            if h1.iloc[i] == seg.max():
                sh.append(h1.iloc[i])
            seg_l = l1.iloc[i-lb:i+lb+1]
            if l1.iloc[i] == seg_l.min():
                sl.append(l1.iloc[i])
        if len(sh) >= 2 and len(sl) >= 2:
            hh = sh[-1] > sh[-2]
            hl = sl[-1] > sl[-2]
            lh = sh[-1] < sh[-2]
            ll = sl[-1] < sl[-2]
            if hh and hl: f['market_structure'] = 1.0
            elif lh and ll: f['market_structure'] = -1.0
            elif hh and ll: f['market_structure'] = 0.5
            elif lh and hl: f['market_structure'] = -0.5
            else: f['market_structure'] = 0.0
        else:
            f['market_structure'] = 0.0
    else:
        f['market_structure'] = 0.0

    don_up = h1.rolling(20).max()
    don_low = l1.rolling(20).min()
    don_range = don_up - don_low
    f['donchian_position'] = _safe((c1.iloc[-1] - don_low.iloc[-1]) / (don_range.iloc[-1] + 1e-10), 0.5)

    if len(c1) >= 20:
        try:
            price_min = c1.iloc[-20:].min()
            price_max = c1.iloc[-20:].max()
            if price_max - price_min > 1e-10:
                bin_edges = np.linspace(price_min, price_max, 11)
                vol_profile = np.zeros(10)
                v1_last = v1 if 'v1' in dir() else pd.Series(1.0, index=c1.index)
                for bi in range(10):
                    mask = (c1.iloc[-20:] >= bin_edges[bi]) & (c1.iloc[-20:] < bin_edges[bi+1])
                    vol_profile[bi] = mask.sum()
                poc_idx = np.argmax(vol_profile)
                poc = (bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2
                f['vpoc_distance'] = _safe((c1.iloc[-1] - poc) / (c1.iloc[-1] + 1e-10))
            else:
                f['vpoc_distance'] = 0.0
        except Exception:
            f['vpoc_distance'] = 0.0
    else:
        f['vpoc_distance'] = 0.0

    high_20 = h4.rolling(20).max()
    f['drawdown_from_high_20'] = _safe((price - high_20.iloc[-1]) / (high_20.iloc[-1] + 1e-10))

    low_20 = l4.rolling(20).min()
    f['rally_from_low_20'] = _safe((price - low_20.iloc[-1]) / (low_20.iloc[-1] + 1e-10))

    recent_dirs = (c4.diff().iloc[-5:] > 0).astype(int)
    consec = 0
    last_d = int(recent_dirs.iloc[-1])
    for v in reversed(recent_dirs.values):
        if int(v) == last_d:
            consec += 1
        else:
            break
    f['consecutive_direction'] = float(consec if last_d == 1 else -consec)

    return f


def _structure_series(c1, h1, l1, c4, h4, l4, o4):
    s = {}
    lb = 5
    n = len(h1)
    ms = pd.Series(0.0, index=c1.index)
    for mi in range(lb * 2, n):
        seg_h = h1.iloc[mi - lb*2:mi+1]
        seg_l = l1.iloc[mi - lb*2:mi+1]
        sh, sl_v = [], []
        for si in range(lb, len(seg_h) - lb):
            if seg_h.iloc[si] == seg_h.iloc[si-lb:si+lb+1].max():
                sh.append(seg_h.iloc[si])
            if seg_l.iloc[si] == seg_l.iloc[si-lb:si+lb+1].min():
                sl_v.append(seg_l.iloc[si])
        if len(sh) >= 2 and len(sl_v) >= 2:
            hh = sh[-1] > sh[-2]
            hl = sl_v[-1] > sl_v[-2]
            lh = sh[-1] < sh[-2]
            ll = sl_v[-1] < sl_v[-2]
            if hh and hl: ms.iloc[mi] = 1.0
            elif lh and ll: ms.iloc[mi] = -1.0
            elif hh and ll: ms.iloc[mi] = 0.5
            elif lh and hl: ms.iloc[mi] = -0.5
    s['market_structure'] = ms

    don_up = h1.rolling(20).max()
    don_low = l1.rolling(20).min()
    don_range = don_up - don_low
    s['donchian_position'] = (c1 - don_low) / (don_range + 1e-10)

    vpoc = pd.Series(0.0, index=c1.index)
    v1_proxy = pd.Series(1.0, index=c1.index)
    for vi in range(20, len(c1)):
        wc = c1.iloc[vi-20:vi]
        p_min, p_max = wc.min(), wc.max()
        if p_max - p_min < 1e-10:
            continue
        be = np.linspace(p_min, p_max, 11)
        vp = np.zeros(10)
        for bi in range(10):
            mask = (wc >= be[bi]) & (wc < be[bi+1])
            vp[bi] = mask.sum()
        poc_i = np.argmax(vp)
        poc_p = (be[poc_i] + be[poc_i+1]) / 2
        vpoc.iloc[vi] = (c1.iloc[vi] - poc_p) / (c1.iloc[vi] + 1e-10)
    s['vpoc_distance'] = vpoc

    s['drawdown_from_high_20'] = (c4 - h4.rolling(20).max()) / (h4.rolling(20).max() + 1e-10)
    s['rally_from_low_20'] = (c4 - l4.rolling(20).min()) / (l4.rolling(20).min() + 1e-10)

    consec = pd.Series(0.0, index=c4.index)
    c4_dir = (c4.diff() > 0).astype(int)
    for ci in range(4, len(c4)):
        cnt = 0
        ld = c4_dir.iloc[ci]
        for j in range(ci, max(ci-5, -1), -1):
            if c4_dir.iloc[j] == ld:
                cnt += 1
            else:
                break
        consec.iloc[ci] = float(cnt if ld == 1 else -cnt)
    s['consecutive_direction'] = consec

    return s


def _entropy_features(c1, v1):
    f = {}
    ret = c1.pct_change().dropna()
    f['return_entropy_20'] = _safe(_shannon_entropy(ret, bins=10, window=20).iloc[-1])

    log_vol = np.log(v1 + 1)
    f['volume_entropy_20'] = _safe(_shannon_entropy(log_vol, bins=10, window=20).iloc[-1])

    if len(c1) >= 20:
        w = c1.iloc[-20:].values
        diffs = np.abs(np.diff(w))
        complexity = np.sum(diffs) / (np.abs(w[-1] - w[0]) + 1e-10)
        f['price_complexity'] = _safe(complexity)
    else:
        f['price_complexity'] = 1.0

    return f


def _entropy_series(c1, v1):
    s = {}
    ret = c1.pct_change()
    s['return_entropy_20'] = _shannon_entropy(ret, bins=10, window=20)

    log_vol = np.log(v1 + 1)
    s['volume_entropy_20'] = _shannon_entropy(log_vol, bins=10, window=20)

    complexity = pd.Series(1.0, index=c1.index)
    for i in range(20, len(c1)):
        w = c1.iloc[i-20:i].values
        diffs = np.abs(np.diff(w))
        total_path = np.sum(diffs)
        direct = np.abs(w[-1] - w[0]) + 1e-10
        complexity.iloc[i] = total_path / direct
    s['price_complexity'] = complexity

    return s


def _daily_features(df_1d):
    f = {}
    defaults = {
        'daily_rsi': 50.0, 'daily_adx': 15.0, 'daily_bb_position': 0.5,
        'daily_return_5d': 0.0, 'daily_return_20d': 0.0, 'daily_volatility': 0.02,
    }
    if df_1d is None or len(df_1d) < 30:
        return defaults

    cd = df_1d['c'].astype(float)
    hd = df_1d['h'].astype(float)
    ld = df_1d['l'].astype(float)

    rsi_d = _rsi(cd, 14)
    f['daily_rsi'] = _safe(rsi_d.iloc[-1], 50.0)

    atr_d = _atr(hd, ld, cd)
    plus_dm = hd.diff().clip(lower=0)
    minus_dm = (-ld.diff()).clip(lower=0)
    p_di = 100 * (plus_dm.rolling(14).mean() / (atr_d + 1e-10))
    m_di = 100 * (minus_dm.rolling(14).mean() / (atr_d + 1e-10))
    dx = 100 * abs(p_di - m_di) / (p_di + m_di + 1e-10)
    adx_d = dx.rolling(14).mean()
    f['daily_adx'] = _safe(adx_d.iloc[-1], 15.0)

    sma20 = cd.rolling(20).mean()
    std20 = cd.rolling(20).std()
    bb_up = sma20 + 2 * std20
    bb_low = sma20 - 2 * std20
    bb_w = bb_up - bb_low
    f['daily_bb_position'] = _safe((cd.iloc[-1] - bb_low.iloc[-1]) / (bb_w.iloc[-1] + 1e-10), 0.5)

    f['daily_return_5d'] = _safe((cd.iloc[-1] / (cd.iloc[-6] + 1e-10) - 1) * 100) if len(cd) > 6 else 0.0
    f['daily_return_20d'] = _safe((cd.iloc[-1] / (cd.iloc[-21] + 1e-10) - 1) * 100) if len(cd) > 21 else 0.0
    f['daily_volatility'] = _safe(cd.pct_change().rolling(20).std().iloc[-1], 0.02)

    return f


def _daily_series(df_1d):
    s = {}
    if df_1d is None or len(df_1d) < 30:
        return s

    cd = df_1d['c'].astype(float)
    hd = df_1d['h'].astype(float)
    ld = df_1d['l'].astype(float)

    s['daily_rsi'] = _rsi(cd, 14)

    atr_d = _atr(hd, ld, cd)
    plus_dm = hd.diff().clip(lower=0)
    minus_dm = (-ld.diff()).clip(lower=0)
    p_di = 100 * (plus_dm.rolling(14).mean() / (atr_d + 1e-10))
    m_di = 100 * (minus_dm.rolling(14).mean() / (atr_d + 1e-10))
    dx = 100 * abs(p_di - m_di) / (p_di + m_di + 1e-10)
    s['daily_adx'] = dx.rolling(14).mean()

    sma20 = cd.rolling(20).mean()
    std20 = cd.rolling(20).std()
    bb_up = sma20 + 2 * std20
    bb_low = sma20 - 2 * std20
    bb_w = bb_up - bb_low
    s['daily_bb_position'] = (cd - bb_low) / (bb_w + 1e-10)
    s['daily_return_5d'] = (cd / cd.shift(5) - 1) * 100
    s['daily_return_20d'] = (cd / cd.shift(20) - 1) * 100
    s['daily_volatility'] = cd.pct_change().rolling(20).std()

    return s


def _external_features(ext_data):
    defaults = {
        'ext_fng': 50.0, 'ext_fng_change': 0.0, 'ext_risk_mode': 0.0,
        'ext_funding_rate_btc': 0.0, 'ext_funding_rate_eth': 0.0,
        'ext_funding_rate_momentum': 0.0,
        'ext_oi_price_divergence': 0.0,
        'ext_liq_imbalance': 0.0, 'ext_liq_intensity': 0.0,
    }
    if ext_data is None:
        return defaults

    f = {}
    f['ext_fng'] = float(ext_data.get('ext_fng', ext_data.get('fng', 50.0)))
    f['ext_fng_change'] = float(ext_data.get('ext_fng_change', 0.0))
    f['ext_risk_mode'] = float(ext_data.get('ext_risk_mode', 0.0))

    f['ext_funding_rate_btc'] = float(ext_data.get('ext_funding_rate_btc',
                                      ext_data.get('funding_rate_btc', 0.0)))
    f['ext_funding_rate_eth'] = float(ext_data.get('ext_funding_rate_eth',
                                      ext_data.get('funding_rate_eth', 0.0)))
    f['ext_funding_rate_momentum'] = float(ext_data.get('ext_funding_rate_momentum', 0.0))

    f['ext_oi_price_divergence'] = float(ext_data.get('ext_oi_price_divergence', 0.0))
    f['ext_liq_imbalance'] = float(ext_data.get('ext_liq_imbalance', 0.0))
    f['ext_liq_intensity'] = float(ext_data.get('ext_liq_intensity', 0.0))

    for k, v in f.items():
        if np.isnan(v) or np.isinf(v):
            f[k] = defaults.get(k, 0.0)

    return f


def _worldquant_alphas(c4, h4, l4, o4, v4):
    f = {}
    try:
        ret4 = c4.pct_change()
        adv20 = v4.rolling(20).mean()

        neg_ret_std = ret4.where(ret4 < 0, 0).rolling(20).std()
        signed_pow = neg_ret_std.where(ret4 < 0, c4) ** 2
        argmax5 = signed_pow.rolling(5).apply(lambda x: x.argmax(), raw=True)
        f['wq_alpha1'] = _safe((argmax5.iloc[-1] / 4.0) - 0.5)

        log_vol_delta = np.log(v4 + 1).diff(2)
        intraday_ret = (c4 - o4) / (o4 + 1e-10)
        if len(log_vol_delta.dropna()) >= 6:
            corr_val = log_vol_delta.rolling(6).corr(intraday_ret).iloc[-1]
            f['wq_alpha2'] = _safe(-1 * corr_val)
        else:
            f['wq_alpha2'] = 0.0

        f['wq_alpha3'] = _safe(-1 * c4.rolling(10).corr(v4).iloc[-1]) if len(c4) >= 10 else 0.0

        f['wq_alpha5'] = _safe(-1 * (h4 * l4).apply(np.sqrt).diff(1).iloc[-1] / (c4.iloc[-1] + 1e-10))

        if len(o4) >= 10:
            corr_ov = o4.rolling(10).corr(v4).iloc[-1]
            f['wq_alpha6'] = _safe(-1 * corr_ov)
        else:
            f['wq_alpha6'] = 0.0

        f['wq_alpha8'] = _safe(-1 * (c4.rolling(5).sum() * ret4.rolling(5).sum() - c4.rolling(10).sum() * ret4.rolling(10).sum()).iloc[-1] / (c4.iloc[-1] ** 2 + 1e-10))

        ret_lag1 = ret4.shift(1)
        f['wq_alpha9'] = _safe(ret_lag1.iloc[-1] * (ret4.iloc[-1] if ret4.iloc[-1] > 0 else ret_lag1.iloc[-1]))

        close_max = c4.rolling(4).max()
        f['wq_alpha10'] = _safe((c4.iloc[-1] - close_max.iloc[-1]) / (close_max.iloc[-1] + 1e-10))

        vol_delta = v4.diff(1)
        price_delta = c4.diff(1)
        f['wq_alpha12'] = _safe(np.sign(vol_delta.iloc[-1]) * (-1 * price_delta.iloc[-1]) / (c4.iloc[-1] + 1e-10))

        cov_cp = c4.rolling(5).cov(v4)
        f['wq_alpha13'] = _safe(-1 * cov_cp.iloc[-1] / (c4.iloc[-1] * v4.iloc[-1] + 1e-10))

        ret_delta3 = ret4.diff(3)
        if len(o4) >= 10:
            corr_ov10 = o4.rolling(10).corr(v4).iloc[-1]
            f['wq_alpha14'] = _safe(-1 * _safe(ret_delta3.iloc[-1]) * _safe(corr_ov10))
        else:
            f['wq_alpha14'] = 0.0

        if len(h4) >= 3:
            f['wq_alpha15'] = _safe(-1 * h4.rolling(3).corr(v4).rolling(3).sum().iloc[-1])
        else:
            f['wq_alpha15'] = 0.0

        if len(h4) >= 5:
            f['wq_alpha16'] = _safe(-1 * h4.rolling(5).corr(v4).iloc[-1])
        else:
            f['wq_alpha16'] = 0.0

        ts_rank_c = c4.rolling(10).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) if len(c4) >= 10 else pd.Series(0.5, index=c4.index)
        f['wq_alpha17'] = _safe(-1 * ts_rank_c.iloc[-1] * ret4.iloc[-1])

        abs_co = abs(c4 - o4).rolling(5).std()
        co_mean = c4 - o4
        corr_co = c4.rolling(10).corr(o4) if len(c4) >= 10 else pd.Series(0, index=c4.index)
        raw18 = abs_co + co_mean + corr_co
        f['wq_alpha18'] = _safe(-1 * raw18.iloc[-1] / (c4.iloc[-1] + 1e-10))

        f['wq_alpha20'] = _safe(-1 * (c4.iloc[-1] - h4.iloc[-1]) / (h4.iloc[-1] - l4.iloc[-1] + 1e-10))

        mean8 = c4.rolling(8).mean()
        std8 = c4.rolling(8).std()
        mean2 = c4.rolling(2).mean()
        vol_ratio21 = v4 / (adv20 + 1e-10)
        try:
            if (mean8.iloc[-1] + std8.iloc[-1]) < mean2.iloc[-1]:
                f['wq_alpha21'] = -1.0
            elif mean2.iloc[-1] < (mean8.iloc[-1] - std8.iloc[-1]):
                f['wq_alpha21'] = 1.0
            else:
                f['wq_alpha21'] = 1.0 if vol_ratio21.iloc[-1] >= 1 else -1.0
        except Exception:
            f['wq_alpha21'] = 0.0

        mean_h20 = h4.rolling(20).mean()
        f['wq_alpha23'] = _safe(-1 * h4.diff(2).iloc[-1] / (h4.iloc[-1] + 1e-10)) if not pd.isna(mean_h20.iloc[-1]) and h4.iloc[-1] > mean_h20.iloc[-1] else 0.0

        f['wq_alpha24'] = _safe(-1 * c4.diff(5).iloc[-1] / (c4.iloc[-5] + 1e-10)) if len(c4) > 5 and c4.rolling(20).mean().iloc[-1] < c4.shift(5).rolling(20).mean().iloc[-1] else 0.0

        f['wq_alpha26'] = _safe(-1 * ret4.rolling(5).max().iloc[-1])

        hl_ratio = (h4 - l4) / (c4 + 1e-10)
        f['wq_alpha28'] = _safe(hl_ratio.rolling(20).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False).iloc[-1]) if len(c4) >= 20 else 0.5

        f['wq_alpha29'] = _safe(ret4.rolling(5).sum().iloc[-1])

        f['wq_alpha30'] = _safe((c4.iloc[-1] - c4.shift(1).iloc[-1]) / v4.rolling(20).std().iloc[-1]) if not pd.isna(v4.rolling(20).std().iloc[-1]) else 0.0

        f['wq_alpha33'] = _safe(-1 * (1 - o4.iloc[-1] / c4.iloc[-1]))

        ret_std2 = ret4.rolling(2).std()
        ret_std5 = ret4.rolling(5).std()
        vol_ratio_34 = ret_std2 / (ret_std5 + 1e-10)
        price_delta1 = c4.diff(1) / (c4 + 1e-10)
        r34 = (1 - vol_ratio_34) + (1 - price_delta1)
        f['wq_alpha34'] = _safe(r34.iloc[-1])

        f['wq_alpha35'] = _safe(ret4.iloc[-1] * v4.iloc[-1] / (adv20.iloc[-1] + 1e-10))

        if len(c4) >= 20:
            rank_vol = (adv20 / (v4 + 1e-10)).rolling(15).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) if len(c4) >= 15 else pd.Series(0.5, index=c4.index)
            f['wq_alpha37'] = _safe(rank_vol.iloc[-1] * ret4.iloc[-1])
        else:
            f['wq_alpha37'] = 0.0

        co_ratio = c4 / (o4 + 1e-10)
        f['wq_alpha38'] = _safe(-1 * ts_rank_c.iloc[-1] * co_ratio.iloc[-1])

        f['wq_alpha40'] = _safe(-1 * h4.rolling(10).std().iloc[-1] * h4.rolling(10).corr(v4).iloc[-1]) if len(h4) >= 10 else 0.0

        geo_mean = np.sqrt(h4 * l4)
        tp4 = (h4 + l4 + c4) / 3
        vwap4 = (tp4 * v4).cumsum() / (v4.cumsum() + 1e-10)
        f['wq_alpha41'] = _safe((geo_mean.iloc[-1] - vwap4.iloc[-1]) / (c4.iloc[-1] + 1e-10))

        f['wq_alpha42'] = _safe((c4.iloc[-1] - c4.rolling(10).mean().iloc[-1]) / (c4.rolling(10).std().iloc[-1] + 1e-10)) if len(c4) >= 10 else 0.0

        if len(v4) >= 20:
            vol_rank20 = (v4 / (adv20 + 1e-10)).rolling(20).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
            price_delta7 = c4.diff(7)
            price_rank8 = (-1 * price_delta7).rolling(8).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) if len(price_delta7.dropna()) >= 8 else pd.Series(0.5, index=c4.index)
            f['wq_alpha43'] = _safe(vol_rank20.iloc[-1] * price_rank8.iloc[-1])
        else:
            f['wq_alpha43'] = 0.0

        if len(h4) >= 5:
            vol_rank5 = v4.rolling(5).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
            corr_hv5 = h4.rolling(5).corr(vol_rank5).iloc[-1]
            f['wq_alpha44'] = _safe(-1 * corr_hv5)
        else:
            f['wq_alpha44'] = 0.0

        f['wq_alpha45'] = _safe(-1 * c4.rolling(5).mean().diff(1).iloc[-1] / (c4.iloc[-1] + 1e-10))

        f['wq_alpha46'] = _safe(ret4.rolling(10).mean().iloc[-1])

        f['wq_alpha47'] = _safe((h4.rolling(5).max().iloc[-1] / c4.iloc[-1] - 1) * v4.iloc[-1] / (adv20.iloc[-1] + 1e-10))

        cl_ratio = (c4 - l4) / (h4 - l4 + 1e-10)
        f['wq_alpha49'] = _safe(cl_ratio.diff(1).iloc[-1])

        f['wq_alpha50'] = _safe(-1 * v4.rolling(5).max().iloc[-1] / (adv20.iloc[-1] + 1e-10))

        f['wq_alpha51'] = _safe(ret4.iloc[-1]) if c4.iloc[-1] < c4.rolling(10).mean().iloc[-1] else _safe(-1 * ret4.iloc[-1])

        f['wq_alpha52'] = _safe(-1 * l4.rolling(5).min().diff(3).iloc[-1] / (l4.iloc[-1] + 1e-10))

        raw53 = ((c4 - l4) - (h4 - c4)) / (c4 - l4 + 1e-10)
        f['wq_alpha53'] = _safe(-1 * raw53.diff(9).iloc[-1])

        f['wq_alpha54'] = _safe(-1 * (l4.iloc[-1] - c4.iloc[-1]) * (o4.iloc[-1] ** 5) / ((l4.iloc[-1] - h4.iloc[-1]) * (c4.iloc[-1] ** 5) + 1e-10))

        if len(c4) >= 12:
            corr_hl = h4.rolling(12).corr(v4)
            rank_corr = corr_hl.rolling(6).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) if len(corr_hl.dropna()) >= 6 else pd.Series(0.5, index=c4.index)
            f['wq_alpha55'] = _safe(-1 * rank_corr.iloc[-1])
        else:
            f['wq_alpha55'] = 0.0

        ret_mean5 = ret4.rolling(5).mean()
        ret_mean20 = ret4.rolling(20).mean()
        f['wq_alpha_mom_revert'] = _safe((ret_mean5.iloc[-1] - ret_mean20.iloc[-1]) * -1)

        f['wq_alpha56'] = _safe(ret4.iloc[-1] * np.sign(vol_delta.iloc[-1]))

        log_vol = np.log(v4 + 1)
        log_vol_slope = log_vol.diff(5) / 5
        ret_slope = ret4.rolling(5).mean()
        f['wq_alpha_vol_price_div'] = _safe(log_vol_slope.iloc[-1] * np.sign(-ret_slope.iloc[-1]))

        high_rel = h4 / h4.rolling(20).max()
        low_rel = l4 / l4.rolling(20).min()
        f['wq_alpha_range_pos'] = _safe((high_rel.iloc[-1] + low_rel.iloc[-1]) / 2 - 1.0)

        co_corr20 = c4.rolling(20).corr(o4) if len(c4) >= 20 else pd.Series(0, index=c4.index)
        hv_corr20 = h4.rolling(20).corr(v4) if len(h4) >= 20 else pd.Series(0, index=h4.index)
        f['wq_alpha_co_hv'] = _safe(co_corr20.iloc[-1] - hv_corr20.iloc[-1])

        vol_accel = adv20.pct_change(5)
        f['wq_alpha_vol_accel'] = _safe(vol_accel.iloc[-1])

        f['wq_alpha101'] = _safe((c4.iloc[-1] - o4.iloc[-1]) / (h4.iloc[-1] - l4.iloc[-1] + 1e-10))

    except Exception as e:
        logger.warning(f"WQ Alpha计算异常: {e}")
        all_wq = [k for k in TitanFeatureStore.FEATURE_GROUPS.get('wq_alpha', []) if k not in f]
        for k in all_wq:
            f[k] = 0.0

    all_wq_names = TitanFeatureStore.FEATURE_GROUPS.get('wq_alpha', [])
    for k in all_wq_names:
        if k not in f:
            f[k] = 0.0

    return f


def _wq_alpha_series(c4, h4, l4, o4, v4):
    s = {}
    try:
        ret4 = c4.pct_change()
        adv20 = v4.rolling(20).mean()

        s['wq_alpha1'] = ret4.rolling(20).std().rolling(5).apply(lambda x: x.argmax() / 4.0 - 0.5, raw=True)
        s['wq_alpha2'] = -1 * np.log(v4 + 1).diff(2).rolling(6).corr((c4 - o4) / (o4 + 1e-10))
        s['wq_alpha3'] = -1 * c4.rolling(10).corr(v4)
        s['wq_alpha5'] = -1 * (h4 * l4).apply(np.sqrt).diff(1) / (c4 + 1e-10)
        s['wq_alpha6'] = -1 * o4.rolling(10).corr(v4)
        s['wq_alpha8'] = -1 * (c4.rolling(5).sum() * ret4.rolling(5).sum() - c4.rolling(10).sum() * ret4.rolling(10).sum()) / (c4 ** 2 + 1e-10)
        s['wq_alpha9'] = ret4.shift(1) * ret4.where(ret4 > 0, ret4.shift(1))
        s['wq_alpha10'] = (c4 - c4.rolling(4).max()) / (c4.rolling(4).max() + 1e-10)
        s['wq_alpha12'] = np.sign(v4.diff(1)) * (-1 * c4.diff(1)) / (c4 + 1e-10)
        s['wq_alpha13'] = -1 * c4.rolling(5).cov(v4) / (c4 * v4 + 1e-10)
        s['wq_alpha14'] = -1 * ret4.diff(3) * o4.rolling(10).corr(v4)
        s['wq_alpha15'] = -1 * h4.rolling(3).corr(v4).rolling(3).sum()
        s['wq_alpha16'] = -1 * h4.rolling(5).corr(v4)
        s['wq_alpha17'] = -1 * c4.rolling(10).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) * ret4
        s['wq_alpha18'] = -1 * (abs(c4 - o4).rolling(5).std() + (c4 - o4) + c4.rolling(10).corr(o4)) / (c4 + 1e-10)
        s['wq_alpha20'] = -1 * (c4 - h4) / (h4 - l4 + 1e-10)
        s['wq_alpha21'] = pd.Series(0.0, index=c4.index)
        s['wq_alpha23'] = pd.Series(0.0, index=c4.index)
        s['wq_alpha24'] = pd.Series(0.0, index=c4.index)
        s['wq_alpha26'] = -1 * ret4.rolling(5).max()
        s['wq_alpha28'] = ((h4 - l4) / (c4 + 1e-10)).rolling(20).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        s['wq_alpha29'] = ret4.rolling(5).sum()
        s['wq_alpha30'] = (c4 - c4.shift(1)) / (v4.rolling(20).std() + 1e-10)
        s['wq_alpha33'] = -1 * (1 - o4 / c4)
        ret_std2 = ret4.rolling(2).std()
        ret_std5 = ret4.rolling(5).std()
        s['wq_alpha34'] = (1 - ret_std2 / (ret_std5 + 1e-10)) + (1 - c4.diff(1) / (c4 + 1e-10))
        s['wq_alpha35'] = ret4 * v4 / (adv20 + 1e-10)
        s['wq_alpha37'] = (adv20 / (v4 + 1e-10)).rolling(15).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) * ret4
        s['wq_alpha38'] = -1 * c4.rolling(10).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False) * c4 / (o4 + 1e-10)
        s['wq_alpha40'] = -1 * h4.rolling(10).std() * h4.rolling(10).corr(v4)
        geo_mean = np.sqrt(h4 * l4)
        tp4 = (h4 + l4 + c4) / 3
        vwap4 = (tp4 * v4).cumsum() / (v4.cumsum() + 1e-10)
        s['wq_alpha41'] = (geo_mean - vwap4) / (c4 + 1e-10)
        s['wq_alpha42'] = (c4 - c4.rolling(10).mean()) / (c4.rolling(10).std() + 1e-10)
        vol_rank20 = (v4 / (adv20 + 1e-10)).rolling(20).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        s['wq_alpha43'] = vol_rank20 * (-1 * c4.diff(7)).rolling(8).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        s['wq_alpha44'] = -1 * h4.rolling(5).corr(v4.rolling(5).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False))
        s['wq_alpha45'] = -1 * c4.rolling(5).mean().diff(1) / (c4 + 1e-10)
        s['wq_alpha46'] = ret4.rolling(10).mean()
        s['wq_alpha47'] = (h4.rolling(5).max() / c4 - 1) * v4 / (adv20 + 1e-10)
        s['wq_alpha49'] = ((c4 - l4) / (h4 - l4 + 1e-10)).diff(1)
        s['wq_alpha50'] = -1 * v4.rolling(5).max() / (adv20 + 1e-10)
        s['wq_alpha51'] = ret4.where(c4 < c4.rolling(10).mean(), -ret4)
        s['wq_alpha52'] = -1 * l4.rolling(5).min().diff(3) / (l4 + 1e-10)
        s['wq_alpha53'] = -1 * (((c4 - l4) - (h4 - c4)) / (c4 - l4 + 1e-10)).diff(9)
        s['wq_alpha54'] = -1 * (l4 - c4) * (o4 ** 5) / ((l4 - h4) * (c4 ** 5) + 1e-10)
        s['wq_alpha55'] = -1 * h4.rolling(12).corr(v4).rolling(6).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)
        s['wq_alpha56'] = ret4 * np.sign(v4.diff(1))
        s['wq_alpha101'] = (c4 - o4) / (h4 - l4 + 1e-10)
        s['wq_alpha_mom_revert'] = (ret4.rolling(5).mean() - ret4.rolling(20).mean()) * -1
        s['wq_alpha_vol_price_div'] = np.log(v4 + 1).diff(5) / 5 * np.sign(-ret4.rolling(5).mean())
        high_rel = h4 / h4.rolling(20).max()
        low_rel = l4 / l4.rolling(20).min()
        s['wq_alpha_range_pos'] = (high_rel + low_rel) / 2 - 1.0
        s['wq_alpha_co_hv'] = c4.rolling(20).corr(o4) - h4.rolling(20).corr(v4)
        s['wq_alpha_vol_accel'] = adv20.pct_change(5)
    except Exception as e:
        logger.warning(f"WQ Alpha Series异常: {e}")

    all_wq_names = TitanFeatureStore.FEATURE_GROUPS.get('wq_alpha', [])
    for k in all_wq_names:
        if k not in s:
            s[k] = pd.Series(0.0, index=c4.index)

    return s
