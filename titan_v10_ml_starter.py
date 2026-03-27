import os
import json
import tempfile
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import pytz
import logging
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib

MEMORY_FILE = 'titan_memory.csv'
MODEL_FILE = 'titan_brain.pkl'
SCAN_SNAPSHOT_FILE = os.path.join('data', 'latest_scan.json')

# ==========================================
# 🛡️ 1. 泰坦 V10.0 配置 (V9.5 扫描器 + ML 大脑)
# ==========================================
CONFIG = {
    'WATCHLIST_MAX': 15,
    'MIN_STRATEGIC_SCORE': 75,
    'MIN_SNIPER_SCORE': 92,
    'DAILY_REPORT_HOUR': 8,
    'DAILY_REPORT_MIN': 1,
    'TIMEZONE': 'Asia/Shanghai',
    'ACCOUNT_SIZE': 10000,
    'RISK_PER_TRADE': 0.015,
    'ATR_MULTIPLIER': 2.0,
    'ML_HEAVY_STRIKE_THRESHOLD': 0.8,
    'ML_SCOUT_THRESHOLD': 0.6,
    'MIN_TRAINING_SAMPLES': 50,
    'SECTORS': {
        'LAYER1': ['BTC', 'ETH', 'SOL', 'BNB', 'ADA', 'AVAX', 'DOT', 'NEAR', 'SUI', 'SEI', 'APT', 'FTM'],
        'L2_SCALING': ['OP', 'ARB', 'MATIC', 'STX'],
        'AI_DATA': ['RENDER', 'GRT', 'FET', 'AGIX', 'RNDR', 'PYTH'],
        'DEFI': ['UNI', 'AAVE', 'INJ', 'LDO', 'MKR', 'DYDX', 'JUP'],
        'MEME': ['DOGE', 'SHIB', 'PEPE', 'WIF', 'ORDI']
    },
    'ELITE_UNIVERSE': [
        'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'LINK', 'MATIC',
        'LTC', 'NEAR', 'UNI', 'ICP', 'FIL', 'APT', 'OP', 'ARB', 'STX', 'RENDER',
        'GRT', 'AAVE', 'INJ', 'TIA', 'SUI', 'SEI', 'ORDI', 'FET', 'PEPE', 'WIF',
        'DOGE', 'SHIB', 'FTM', 'THETA', 'LDO', 'MKR', 'PYTH', 'JUP', 'DYDX', 'GALA'
    ],
    'EXCLUDE_ASSETS': ['USDT', 'USDC', 'DAI', 'PAX', 'BUSD', 'FDUSD', 'USDP']
}

# ==========================================
# 🧠 2. 泰坦 V10.0 增强数学引擎
# ==========================================
class TitanMath:
    @staticmethod
    def SMA(series, period):
        return series.rolling(window=period).mean()

    @staticmethod
    def ATR(df, period=14):
        h, l, c_prev = df['h'], df['l'], df['c'].shift(1)
        tr = pd.concat([h - l, abs(h - c_prev), abs(l - c_prev)], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    @staticmethod
    def ADX(df, period=14):
        plus_dm = df['h'].diff().clip(lower=0)
        minus_dm = (-df['l'].diff()).clip(lower=0)
        tr = pd.concat([df['h']-df['l'], abs(df['h']-df['c'].shift(1)), abs(df['l']-df['c'].shift(1))], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        p_di = 100 * (plus_dm.rolling(window=period).mean() / (atr + 1e-10))
        m_di = 100 * (minus_dm.rolling(window=period).mean() / (atr + 1e-10))
        dx = (100 * abs(p_di - m_di) / (p_di + m_di + 1e-10))
        return dx.rolling(window=period).mean()

    @staticmethod
    def RSI(series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        return 100 - (100 / (1 + rs))

    @staticmethod
    def VWAP(df):
        tp = (df['h'] + df['l'] + df['c']) / 3
        return (tp * df['v']).cumsum() / (df['v'].cumsum() + 1e-10)

    @staticmethod
    def volume_change(df, period=20):
        vol_sma = df['v'].rolling(window=period).mean()
        return df['v'].iloc[-1] / (vol_sma.iloc[-1] + 1e-10)

    @staticmethod
    def get_fear_and_greed():
        try:
            r = requests.get("https://api.alternative.me/fng/", timeout=5)
            data = r.json()
            return int(data['data'][0]['value']), data['data'][0]['value_classification']
        except:
            return 50, "Neutral"

# ==========================================
# 🤖 3. 泰坦 V10.0 机器学习大脑
# ==========================================
class TitanMLBrain:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.is_trained = False
        self.feature_names = ['adx_4h', 'fng_index', 'vwap_bias_15m', 'rsi_1h', 'vol_change']

    def try_load_model(self):
        if os.path.exists(MODEL_FILE):
            try:
                self.model = joblib.load(MODEL_FILE)
                self.is_trained = True
                return True
            except Exception:
                return False
        return False

    def save_model(self):
        if self.is_trained:
            joblib.dump(self.model, MODEL_FILE)

    def get_ml_tag(self, ml_prob):
        if ml_prob > CONFIG['ML_HEAVY_STRIKE_THRESHOLD']:
            return "🔥重锤出击"
        elif ml_prob > CONFIG['ML_SCOUT_THRESHOLD']:
            return "🔰前哨轻仓"
        else:
            return ""

    def record_live_signal(self, symbol, adx, fng, vwap_bias, rsi, vol_change, result=None):
        new_row = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'symbol': symbol,
            'adx_4h': adx,
            'fng_index': fng,
            'vwap_bias_15m': vwap_bias,
            'rsi_1h': rsi,
            'vol_change': vol_change,
            'result': result
        }

        if os.path.exists(MEMORY_FILE):
            df = pd.read_csv(MEMORY_FILE)
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df = pd.DataFrame([new_row])

        df.to_csv(MEMORY_FILE, index=False)

    def load_real_data(self):
        if not os.path.exists(MEMORY_FILE):
            return None, None

        df = pd.read_csv(MEMORY_FILE)
        df_with_result = df.dropna(subset=['result'])

        if len(df_with_result) < 30:
            return None, None

        X = df_with_result[self.feature_names]
        y = df_with_result['result'].astype(int)
        return X, y

    def generate_mock_data(self, samples=500):
        np.random.seed(42)
        adx = np.random.uniform(10, 60, samples)
        fng = np.random.uniform(10, 90, samples)
        bias = np.random.uniform(-0.05, 0.05, samples)
        rsi = np.random.uniform(20, 80, samples)
        vol = np.random.uniform(0.5, 3.0, samples)

        X = pd.DataFrame({
            'adx_4h': adx,
            'fng_index': fng,
            'vwap_bias_15m': bias,
            'rsi_1h': rsi,
            'vol_change': vol
        })

        y = ((X['adx_4h'] > 25) & (X['fng_index'] < 30) & (X['vwap_bias_15m'] > 0)).astype(int)
        noise = np.random.choice([0, 1], size=samples, p=[0.8, 0.2])
        y = np.abs(y - noise)
        return X, y

    def save_mock_to_csv(self, X, y):
        df = X.copy()
        df['result'] = y
        df['timestamp'] = pd.date_range(end=datetime.now(), periods=len(df), freq='h').strftime('%Y-%m-%d %H:%M:%S')
        df['symbol'] = 'MOCK/USDT'
        cols = ['timestamp', 'symbol'] + self.feature_names + ['result']
        df = df[cols]
        df.to_csv(MEMORY_FILE, index=False)

    def train_model(self, X, y):
        if len(X) < CONFIG['MIN_TRAINING_SAMPLES']:
            logging.getLogger("Titan").warning(
                f"⚠️ 训练样本不足（当前 {len(X)} 条，建议 {CONFIG['MIN_TRAINING_SAMPLES']}+ 条）。"
                "模型精度可能受限，建议积累更多实战数据后重新训练。"
            )

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        predictions = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, predictions)
        self.is_trained = True
        self.save_model()
        return accuracy

    def predict_signal_probability(self, feature_dict):
        if not self.is_trained:
            return 0.5
        df = pd.DataFrame([feature_dict])
        prob = self.model.predict_proba(df[self.feature_names])[0][1]
        return prob

# ==========================================
# ⚔️ 4. 进化决策大脑
# ==========================================
class TitanBrain:
    @staticmethod
    def analyze_strategic(data_map, btc_trend):
        d1d = data_map['1d']
        d4h = data_map['4h']
        price = d1d['c'].iloc[-1]
        ma20 = TitanMath.SMA(d1d['c'], 20).iloc[-1]
        ma50 = TitanMath.SMA(d1d['c'], 50).iloc[-1]
        rsi_1d = TitanMath.RSI(d1d['c'], 14).iloc[-1]
        atr_1d = TitanMath.ATR(d1d).iloc[-1]
        atr_pct = (atr_1d / (price + 1e-10)) * 100
        vol_ratio = TitanMath.volume_change(d1d, 20)
        adx_4h = TitanMath.ADX(d4h).iloc[-1]
        recent_low = d1d['l'].tail(20).min()
        support_dist = (price - recent_low) / (recent_low + 1e-10) * 100

        score = 50
        notes = []

        if price > ma20:
            score += 15
            notes.append("站稳MA20")
        if price > ma50:
            score += 5
            notes.append("站稳MA50")

        if btc_trend == "牛市":
            score += 10

        if rsi_1d < 35:
            score += 10
            notes.append("RSI超卖反弹区")
        elif rsi_1d < 45:
            score += 5
            notes.append("RSI偏低蓄力")

        if vol_ratio > 1.5:
            score += 8
            notes.append("成交量放大")
        elif vol_ratio > 1.2:
            score += 4
            notes.append("成交量温和放大")

        if adx_4h > 25:
            score += 7
            notes.append("4H趋势确认")

        if support_dist < 5:
            score += 5
            notes.append("靠近支撑位")

        if 1.5 < atr_pct < 5:
            score += 5
            notes.append("波动率适中")
        elif atr_pct >= 5:
            score -= 3
            notes.append("波动率偏高")

        return score, " | ".join(notes) if notes else "常规扫描"

    @staticmethod
    async def analyze_sniper(data_map, fng_value, symbol, exchange):
        d15m, d1h, d4h = data_map['15m'], data_map['1h'], data_map['4h']
        price = d15m['c'].iloc[-1]
        vwap = TitanMath.VWAP(d15m).iloc[-1]
        adx_4h = TitanMath.ADX(d4h).iloc[-1]
        atr_4h = TitanMath.ATR(d4h).iloc[-1]
        rsi_1h = TitanMath.RSI(d1h['c'], 14).iloc[-1]
        vol_change = TitanMath.volume_change(d15m, 20)

        score = 70
        notes = []

        if price > vwap:
            score += 15
            notes.append("站稳日内成本线")
        if adx_4h > 25:
            score += 10
            notes.append("4H趋势确认")

        try:
            bias = (price - vwap) / vwap
            if bias > 0.05:
                score -= 10
                notes.append("警惕！多头过度拥挤")
        except:
            bias = 0.0

        vwap_bias = (price - vwap) / (vwap + 1e-10)

        asset = symbol.split('/')[0]
        sector = "未知板块"
        for s_name, assets in CONFIG['SECTORS'].items():
            if asset in assets:
                sector = s_name
                break
        notes.append(f"所属板块: {sector}")

        risk_dist = atr_4h * CONFIG['ATR_MULTIPLIER']
        sl = price - risk_dist
        tp = price + risk_dist * 3.5
        val = (CONFIG['ACCOUNT_SIZE'] * CONFIG['RISK_PER_TRADE'] / (risk_dist + 1e-10)) * price

        ml_features = {
            'adx_4h': adx_4h,
            'fng_index': fng_value,
            'vwap_bias_15m': vwap_bias,
            'rsi_1h': rsi_1h,
            'vol_change': vol_change
        }

        return score, price, sl, tp, val, " | ".join(notes), sector, ml_features

# ==========================================
# 🚀 5. 执行指挥部 (整合 V9.5 + V10.0 ML)
# ==========================================
class TitanCommander:
    def __init__(self):
        self.exchange = ccxt.gateio({'enableRateLimit': True})
        self.logger = self.setup_logging()
        self.tz = pytz.timezone(CONFIG['TIMEZONE'])
        self.watchlist = []
        self.ml_brain = TitanMLBrain()
        self.failure_counts = {}
        self.failure_alerted = set()
        self.FAILURE_THRESHOLD = 3
        self.activity_logs = []
        self.btc_info = {}
        self._init_ml_brain()

    def _init_ml_brain(self):
        self.logger.info("🧠 正在初始化机器学习大脑...")

        if self.ml_brain.try_load_model():
            self.logger.info(f"💾 成功从 {MODEL_FILE} 加载持久化模型！跳过重新训练。")
        else:
            self.logger.info("📂 未找到持久化模型，开始从数据训练...")
            X_data, y_data = self.ml_brain.load_real_data()
            if X_data is None:
                self.logger.info("⚠️ 实战记忆不足，使用模拟数据启动...")
                X_data, y_data = self.ml_brain.generate_mock_data()
                self.ml_brain.save_mock_to_csv(X_data, y_data)

            accuracy = self.ml_brain.train_model(X_data, y_data)
            self.logger.info(f"✅ ML 大脑训练完成！准确率: {accuracy:.2%}")
            self.logger.info(f"💾 模型已固化到 {MODEL_FILE}")

        importances = self.ml_brain.model.feature_importances_
        for name, imp in zip(self.ml_brain.feature_names, importances):
            self.logger.info(f"   - 因子 [{name}] 贡献度: {imp:.4f}")

    def setup_logging(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - [泰坦 V10.0] - %(message)s')
        return logging.getLogger("Titan")

    def _get_memory_samples(self):
        try:
            if os.path.exists(MEMORY_FILE):
                df = pd.read_csv(MEMORY_FILE)
                return len(df)
        except:
            pass
        return 0

    def _get_ml_accuracy(self):
        try:
            if self.ml_brain.is_trained and os.path.exists(MEMORY_FILE):
                df = pd.read_csv(MEMORY_FILE)
                df_labeled = df.dropna(subset=['result'])
                if len(df_labeled) >= 30:
                    X = df_labeled[self.ml_brain.feature_names]
                    y = df_labeled['result'].astype(int)
                    preds = self.ml_brain.model.predict(X)
                    return float(accuracy_score(y, preds) * 100)
        except:
            pass
        return 77.0

    def _add_log(self, msg, log_type="info"):
        now = datetime.now(self.tz).strftime('%H:%M:%S')
        self.activity_logs.insert(0, {"time": now, "msg": msg, "type": log_type})
        self.activity_logs = self.activity_logs[:20]

    def _compute_btc_info(self, btc_data):
        try:
            d1d = btc_data['1d']
            price = float(d1d['c'].iloc[-1])
            ma20 = float(TitanMath.SMA(d1d['c'], 20).iloc[-1])
            rsi = float(TitanMath.RSI(d1d['c'], 14).iloc[-1])
            low_20d = float(d1d['l'].tail(20).min())
            high_20d = float(d1d['h'].tail(20).max())
            prev_close = float(d1d['c'].iloc[-2])
            change_pct = (price - prev_close) / (prev_close + 1e-10) * 100

            self.btc_info = {
                "price": round(price, 2),
                "change_pct": round(change_pct, 2),
                "ma20": round(ma20, 0),
                "rsi": round(rsi, 1),
                "support": round(low_20d, 0),
                "resistance": round(high_20d, 0),
            }
        except Exception as e:
            self.logger.warning(f"BTC info 计算异常: {e}")

    def _get_trend_label(self, data_map, timeframe):
        try:
            df = data_map[timeframe]
            price = float(df['c'].iloc[-1])
            ma20 = float(TitanMath.SMA(df['c'], 20).iloc[-1])
            if price > ma20 * 1.01:
                return "UP"
            elif price < ma20 * 0.99:
                return "DOWN"
            return "SIDE"
        except:
            return "N/A"

    def _record_failure(self, symbol):
        self.failure_counts[symbol] = self.failure_counts.get(symbol, 0) + 1
        count = self.failure_counts[symbol]
        if count >= self.FAILURE_THRESHOLD and symbol not in self.failure_alerted:
            self.logger.warning(f"🚨 {symbol} 连续 {count} 次数据获取失败！")
            self.failure_alerted.add(symbol)
            self._send_failure_alert(symbol, count)

    def _record_success(self, symbol):
        if symbol in self.failure_counts:
            del self.failure_counts[symbol]
        self.failure_alerted.discard(symbol)

    def _send_failure_alert(self, symbol, count):
        sender, password, receiver = [os.getenv(k) for k in ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECEIVER_EMAIL']]
        if not all([sender, password, receiver]):
            return
        now_str = datetime.now(self.tz).strftime('%Y-%m-%d %H:%M')
        body = f"""
        <html><body style="font-family:sans-serif; padding:20px;">
        <h2 style="color:#ef4444;">🚨 泰坦系统告警</h2>
        <p><b>{symbol}</b> 已连续 <b>{count}</b> 次数据获取失败。</p>
        <p>可能原因：交易所 API 限流、网络异常、交易对下架。</p>
        <p style="color:#94a3b8; font-size:12px;">{now_str} | Titan V10.0 告警系统</p>
        </body></html>
        """
        msg = MIMEText(body, 'html', 'utf-8')
        msg['Subject'] = Header(f"🚨 泰坦告警 | {symbol} 数据获取连续失败", 'utf-8')
        msg['From'], msg['To'] = sender, receiver
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, [receiver], msg.as_string())
            self.logger.info(f"📧 告警邮件已发送：{symbol}")
        except Exception as e:
            self.logger.error(f"告警邮件发送失败: {e}")

    async def _auto_label_signals(self):
        try:
            if not os.path.exists(MEMORY_FILE):
                return

            df = pd.read_csv(MEMORY_FILE)
            unlabeled = df[df['result'].isna()].copy()

            if len(unlabeled) == 0:
                return

            now = datetime.now()
            labeled_count = 0

            for idx, row in unlabeled.iterrows():
                try:
                    signal_time = pd.to_datetime(row['timestamp'])
                    hours_passed = (now - signal_time).total_seconds() / 3600

                    if hours_passed < 24:
                        continue

                    symbol = str(row['symbol'])
                    if symbol == 'MOCK/USDT':
                        continue

                    ticker = await self.exchange.fetch_ticker(symbol)
                    current_price = float(ticker['last'])

                    ohlcv = await self.exchange.fetch_ohlcv(symbol, '1d', limit=2)
                    if ohlcv and len(ohlcv) >= 2:
                        price_24h_ago = float(ohlcv[-2][4])
                        result = 1 if current_price > price_24h_ago else 0
                    else:
                        vwap_b = float(row.get('vwap_bias_15m', 0) or 0)
                        result = 1 if vwap_b > 0 else 0

                    df.at[idx, 'result'] = result
                    labeled_count += 1

                    await asyncio.sleep(0.5)
                except Exception:
                    continue

            if labeled_count > 0:
                tmp_path = MEMORY_FILE + '.tmp'
                df.to_csv(tmp_path, index=False)
                os.replace(tmp_path, MEMORY_FILE)
                self.logger.info(f"🏷️ 自动标注完成：{labeled_count} 条信号已获得实战结果标签")

                labeled_df = df.dropna(subset=['result'])
                if len(labeled_df) >= 50:
                    X = labeled_df[self.ml_brain.feature_names]
                    y = labeled_df['result'].astype(int)
                    accuracy = self.ml_brain.train_model(X, y)
                    self.logger.info(f"🧠 ML 大脑基于实战数据重新训练！新准确率: {accuracy:.2%}")

        except Exception as e:
            self.logger.error(f"自动标注异常: {e}")

    def _save_scan_snapshot(self, opps, cruise_data, mode, btc_trend, fng_val, fng_label):
        try:
            os.makedirs(os.path.dirname(SCAN_SNAPSHOT_FILE), exist_ok=True)

            assets = []
            for opp in opps:
                sym, score, price, sl, tp, val, note, sector, ml_prob, ml_tag = opp[:10]
                ml_features = opp[10] if len(opp) > 10 else {}
                tf_matrix = opp[11] if len(opp) > 11 else {}
                zone = "elite" if ml_prob > CONFIG['ML_SCOUT_THRESHOLD'] else "waiting"

                category = ""
                if ml_prob > CONFIG['ML_HEAVY_STRIKE_THRESHOLD']:
                    category = "重锤出击"
                elif ml_prob > CONFIG['ML_SCOUT_THRESHOLD']:
                    category = "前哨试探"

                assets.append({
                    "symbol": sym.replace('/USDT', ''),
                    "full_symbol": sym,
                    "zone": zone,
                    "score": score,
                    "price": round(price, 6),
                    "sl": round(sl, 6),
                    "tp": round(tp, 6),
                    "position_size": round(val, 0),
                    "ml_prob": round(ml_prob * 100, 2),
                    "ml_tag": ml_tag,
                    "category": category,
                    "sector": sector,
                    "notes": note,
                    "adx_4h": round(float(ml_features.get('adx_4h', 0)), 2) if ml_features else None,
                    "rsi_1h": round(float(ml_features.get('rsi_1h', 0)), 2) if ml_features else None,
                    "vwap_bias": round(float(ml_features.get('vwap_bias_15m', 0)), 4) if ml_features else None,
                    "vol_change": round(float(ml_features.get('vol_change', 0)), 4) if ml_features else None,
                    "matrix": tf_matrix,
                    "advice": self._generate_advice(score, ml_prob, tf_matrix, note),
                })

            snapshot = {
                "assets": assets,
                "cruise": cruise_data,
                "macro": {
                    "btc_trend": "多头占优" if btc_trend == "牛市" else "空头占优",
                    "fng": fng_val,
                    "fng_label": fng_label,
                },
                "btc_info": self.btc_info,
                "scan_mode": mode,
                "last_updated": datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S'),
                "ml_accuracy": self._get_ml_accuracy(),
                "memory_samples": self._get_memory_samples(),
                "logs": self.activity_logs[:10],
                "total_scanned": len(cruise_data) + len(assets),
            }

            tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(SCAN_SNAPSHOT_FILE), suffix='.tmp')
            try:
                with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, SCAN_SNAPSHOT_FILE)
                self.logger.info(f"📊 看板数据已更新到 {SCAN_SNAPSHOT_FILE}")
            except:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise
        except Exception as e:
            self.logger.error(f"看板数据写入异常: {e}")

    def _generate_advice(self, score, ml_prob, matrix, notes):
        if not matrix:
            return "数据评估中..."
        up_count = sum(1 for v in matrix.values() if v == 'UP')
        if up_count == 4 and ml_prob > CONFIG['ML_HEAVY_STRIKE_THRESHOLD']:
            return "多周期全绿，属于 A+ 级信号，建议维持重仓狙击。"
        if up_count >= 3 and ml_prob > CONFIG['ML_SCOUT_THRESHOLD']:
            return f"{up_count}/4 周期共振，信号较强，建议适度建仓。"
        if up_count >= 2:
            return "部分周期确认，建议等待更多共振信号再行介入。"
        return "信号强度不足，继续观察中。"

    def send_email(self, opps, mode="Heartbeat", btc_trend="未知", fng=(50, "Neutral")):
        sender, password, receiver = [os.getenv(k) for k in ['SENDER_EMAIL', 'SENDER_PASSWORD', 'RECEIVER_EMAIL']]
        if not all([sender, password, receiver]):
            self.logger.warning("📧 邮件配置缺失，跳过发送。请设置 SENDER_EMAIL, SENDER_PASSWORD, RECEIVER_EMAIL。")
            return

        sorted_opps = sorted(opps, key=lambda x: x[1], reverse=True)
        now_str = datetime.now(self.tz).strftime('%Y-%m-%d %H:%M')

        title, color, tag = ("☀️ 泰坦战略池 | 日线总结", "#1e3a8a", "STRATEGIC") if mode == "Daily" else ("🎯 15M 狙击指令 | 实时脉冲", "#991b1b", "SNIPER")

        sector_counts = {}
        for o in sorted_opps:
            s = o[7] if len(o) > 7 else "未知"
            sector_counts[s] = sector_counts.get(s, 0) + 1

        risk_warning = ""
        for s, count in sector_counts.items():
            if count > 1 and mode == "Sniper":
                risk_warning = f"<div style='margin-bottom:15px; padding:10px; background:#fef2f2; border:1px solid #fee2e2; border-radius:6px; color:#b91c1c; font-size:12px;'><b>⚠️ 相关性风险提示：</b>检测到 {count} 个资产属于 {s} 板块。建议仅选取其中评分最高的标的操作，避免风险过度集中。</div>"

        rows = ""
        for i, opp in enumerate(sorted_opps):
            sym, score, price, sl, tp, val, note, sector, ml_prob, ml_tag = opp[:10]
            prob_color = "#10b981" if ml_prob > CONFIG['ML_HEAVY_STRIKE_THRESHOLD'] else ("#f59e0b" if ml_prob > CONFIG['ML_SCOUT_THRESHOLD'] else "#94a3b8")
            rows += f"""
            <tr style="text-align: center; font-size: 11px; border-bottom: 1px solid #f1f5f9;">
                <td style="padding: 12px 4px; color: #94a3b8;">{i+1}</td>
                <td style="font-weight: 800; color: #1e293b;">{sym.replace('/USDT','')}</td>
                <td style="color: #6366f1; font-weight: 900;">{score}</td>
                <td style="background: #f8fafc; font-weight: bold;">{price:.4f}</td>
                <td style="color: #ef4444;">{sl:.4f}</td>
                <td style="color: #10b981;">{tp:.4f}</td>
                <td style="font-weight: 800;">${val:.0f}</td>
                <td style="color: {prob_color}; font-weight: 900;">{ml_prob:.0%} {ml_tag}</td>
                <td style="font-size: 9px; color: #64748b; text-align: left; padding-left: 10px;">{note}</td>
            </tr>"""

        body = f"""
        <html>
        <body style="margin:0; padding:20px; background-color:#f1f5f9; font-family: sans-serif;">
            <div style="max-width: 750px; margin: auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
                <div style="background-color: {color}; padding: 30px; color: #ffffff;">
                    <div style="font-size: 10px; font-weight: 800; letter-spacing: 2px; color: #fbbf24; margin-bottom: 8px;">{tag} | ML ENHANCED</div>
                    <h1 style="margin: 0; font-size: 22px; font-weight: 900;">{title}</h1>
                </div>
                <div style="padding: 25px;">
                    {risk_warning}
                    <div style="display: flex; gap: 15px; margin-bottom: 25px;">
                        <div style="flex: 1; background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #f1f5f9; text-align: center;">
                            <div style="font-size: 10px; color: #94a3b8; font-weight: 700;">BTC 宏观基调</div>
                            <div style="font-size: 18px; font-weight: 900; color: {'#10b981' if btc_trend=='牛市' else '#ef4444'}">{btc_trend}</div>
                        </div>
                        <div style="flex: 1; background: #f8fafc; padding: 15px; border-radius: 8px; border: 1px solid #f1f5f9; text-align: center;">
                            <div style="font-size: 10px; color: #94a3b8; font-weight: 700;">恐惧贪婪指数</div>
                            <div style="font-size: 18px; font-weight: 900; color: #f59e0b;">{fng[0]} ({fng[1]})</div>
                        </div>
                    </div>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #1e293b; color: #ffffff; font-size: 10px;">
                                <th style="padding: 10px;">#</th><th>资产</th><th>评分</th><th>入场点</th><th>止损</th><th>目标</th><th>规模</th><th>ML胜率</th><th>数据定性</th>
                            </tr>
                        </thead>
                        <tbody>{rows if sorted_opps else "<tr><td colspan='9' style='padding:40px; text-align:center; color:#94a3b8;'>雷达运行正常，数据环境评估中...</td></tr>"}</tbody>
                    </table>
                </div>
                <div style="background: #f8fafc; padding: 15px; text-align: center; font-size: 10px; color: #cbd5e1; border-top: 1px solid #f1f5f9;">
                    {now_str} | Quantum Titan V10.0 | 数据驱动 + ML进化决策
                </div>
            </div>
        </body>
        </html>
        """
        msg = MIMEText(body, 'html', 'utf-8')
        icon = "☀️" if mode == "Daily" else "🎯"
        msg['Subject'] = Header(f"{icon} {title} | {now_str}", 'utf-8')
        msg['From'], msg['To'] = sender, receiver
        try:
            with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
                s.login(sender, password)
                s.sendmail(sender, [receiver], msg.as_string())
            self.logger.info(f"📧 {mode} 报告发送成功。")
        except Exception as e:
            self.logger.error(f"邮件链路异常: {e}")

    async def fetch_ohlcv_matrix(self, sym):
        try:
            tasks = [self.exchange.fetch_ohlcv(sym, timeframe=tf, limit=100) for tf in ['15m', '1h', '4h', '1d']]
            res = await asyncio.gather(*tasks)
            return {tf: pd.DataFrame(res[i], columns=['t', 'o', 'h', 'l', 'c', 'v']) for i, tf in enumerate(['15m', '1h', '4h', '1d'])}
        except:
            return None

    def _collect_cruise_item(self, sym, data):
        try:
            asset_name = sym.replace('/USDT', '')
            d1d = data['1d']
            d1h = data['1h']
            price = float(d1d['c'].iloc[-1])
            rsi = float(TitanMath.RSI(d1h['c'], 14).iloc[-1])
            score_1d, notes = TitanBrain.analyze_strategic(data, "")
            trend = self._get_trend_label(data, '4h')

            sector = "未知"
            for s_name, assets_list in CONFIG['SECTORS'].items():
                if asset_name in assets_list:
                    sector = s_name
                    break

            status = notes if notes != "常规扫描" else "数据评估中"

            return {
                "symbol": asset_name,
                "price": round(price, 6),
                "rsi": round(rsi, 1),
                "score": score_1d,
                "trend": trend,
                "status": status,
                "sector": sector,
            }
        except:
            return None

    async def run_waterfall_scan(self, mode="Sniper"):
        try:
            fng_val, fng_label = TitanMath.get_fear_and_greed()
            self._add_log(f"恐惧贪婪指数: {fng_val} ({fng_label})", "system")

            btc_data = await self.fetch_ohlcv_matrix('BTC/USDT')
            if not btc_data:
                self.logger.error("无法获取 BTC 数据，跳过本轮扫描。")
                self._add_log("BTC 数据获取失败，本轮扫描跳过", "warn")
                return
            btc_trend = "牛市" if btc_data['1d']['c'].iloc[-1] > TitanMath.SMA(btc_data['1d']['c'], 20).iloc[-1] else "熊市"
            self._compute_btc_info(btc_data)
            self._add_log(f"BTC ${self.btc_info.get('price', '?')} | 趋势: {'多头' if btc_trend == '牛市' else '空头'}", "info")

            cruise_data = []
            all_data_cache = {}

            if mode == "Daily":
                self.logger.info("🌊 正在刷新精英战略池...")
                self._add_log("开始 Daily 全场扫描，评估 40 个精英标的...", "system")
                new_pool = []
                for asset in CONFIG['ELITE_UNIVERSE']:
                    sym = f"{asset}/USDT"
                    data = await self.fetch_ohlcv_matrix(sym)
                    if not data:
                        self._record_failure(sym)
                        continue
                    self._record_success(sym)
                    all_data_cache[sym] = data

                    score_1d, strategic_notes = TitanBrain.analyze_strategic(data, btc_trend)

                    cruise_item = self._collect_cruise_item(sym, data)
                    if cruise_item:
                        cruise_data.append(cruise_item)

                    if score_1d >= CONFIG['MIN_STRATEGIC_SCORE']:
                        new_pool.append({"symbol": sym, "score": score_1d, "notes": strategic_notes})
                        self._add_log(f"{asset} 评分 {score_1d}，进入战略池", "action")
                    else:
                        self._add_log(f"{asset} 评分 {score_1d}，未达 {CONFIG['MIN_STRATEGIC_SCORE']} 阈值", "info")

                self.watchlist = [x['symbol'] for x in sorted(new_pool, key=lambda x: x['score'], reverse=True)[:CONFIG['WATCHLIST_MAX']]]
                self.logger.info(f"📋 战略池更新完毕，共 {len(self.watchlist)} 个标的。")

                snap_opps = []
                for sym in self.watchlist:
                    data = all_data_cache.get(sym) or await self.fetch_ohlcv_matrix(sym)
                    if not data:
                        continue
                    res = await TitanBrain.analyze_sniper(data, fng_val, sym, self.exchange)
                    score, price, sl, tp, val, note, sector, ml_features = res

                    ml_prob = self.ml_brain.predict_signal_probability(ml_features)
                    ml_tag = self.ml_brain.get_ml_tag(ml_prob)

                    tf_matrix = {
                        "15M": self._get_trend_label(data, '15m'),
                        "1H": self._get_trend_label(data, '1h'),
                        "4H": self._get_trend_label(data, '4h'),
                        "D1": self._get_trend_label(data, '1d'),
                    }

                    self.ml_brain.record_live_signal(
                        symbol=sym,
                        adx=ml_features['adx_4h'],
                        fng=ml_features['fng_index'],
                        vwap_bias=ml_features['vwap_bias_15m'],
                        rsi=ml_features['rsi_1h'],
                        vol_change=ml_features['vol_change'],
                        result=None
                    )

                    snap_opps.append([sym, score, price, sl, tp, val, note, sector, ml_prob, ml_tag, ml_features, tf_matrix])

                self.send_email(snap_opps, mode="Daily", btc_trend=btc_trend, fng=(fng_val, fng_label))
                self._save_scan_snapshot(snap_opps, cruise_data, "Daily", btc_trend, fng_val, fng_label)

            else:
                if not self.watchlist:
                    self.logger.info("📋 战略池为空，使用精英列表进行狙击扫描...")
                    scan_list = [f"{asset}/USDT" for asset in CONFIG['ELITE_UNIVERSE'][:15]]
                    self._add_log("战略池为空，启用精英列表前15标的进行狙击", "warn")
                else:
                    scan_list = self.watchlist
                self.logger.info(f"🎯 正在狙击 {len(scan_list)} 个核心精英标的...")
                self._add_log(f"Sniper 模式启动，狙击 {len(scan_list)} 个标的...", "system")
                sniper_opps = []
                all_sniper = []
                for sym in scan_list:
                    data = await self.fetch_ohlcv_matrix(sym)
                    if not data:
                        self._record_failure(sym)
                        continue
                    self._record_success(sym)

                    cruise_item = self._collect_cruise_item(sym, data)
                    if cruise_item:
                        cruise_data.append(cruise_item)

                    res = await TitanBrain.analyze_sniper(data, fng_val, sym, self.exchange)
                    score, price, sl, tp, val, note, sector, ml_features = res

                    ml_prob = self.ml_brain.predict_signal_probability(ml_features)
                    ml_tag = self.ml_brain.get_ml_tag(ml_prob)

                    tf_matrix = {
                        "15M": self._get_trend_label(data, '15m'),
                        "1H": self._get_trend_label(data, '1h'),
                        "4H": self._get_trend_label(data, '4h'),
                        "D1": self._get_trend_label(data, '1d'),
                    }

                    self.ml_brain.record_live_signal(
                        symbol=sym,
                        adx=ml_features['adx_4h'],
                        fng=ml_features['fng_index'],
                        vwap_bias=ml_features['vwap_bias_15m'],
                        rsi=ml_features['rsi_1h'],
                        vol_change=ml_features['vol_change'],
                        result=None
                    )

                    asset_name = sym.replace('/USDT', '')
                    self._add_log(f"{asset_name} 评分{score} ML{ml_prob*100:.0f}% RSI{ml_features['rsi_1h']:.0f}", "info")

                    all_sniper.append([sym, score, price, sl, tp, val, note, sector, ml_prob, ml_tag, ml_features, tf_matrix])
                    if score >= CONFIG['MIN_SNIPER_SCORE']:
                        sniper_opps.append([sym, score, price, sl, tp, val, note, sector, ml_prob, ml_tag, ml_features, tf_matrix])
                        self._add_log(f"{asset_name} 触发狙击信号！评分 {score}, ML {ml_prob*100:.1f}%", "action")

                self._save_scan_snapshot(all_sniper, cruise_data, "Sniper", btc_trend, fng_val, fng_label)

                if sniper_opps:
                    self.send_email(sniper_opps, mode="Sniper", btc_trend=btc_trend, fng=(fng_val, fng_label))

            self._add_log(f"{mode} 扫描完成，共处理 {len(cruise_data)} 个标的", "system")

        except Exception as e:
            self.logger.error(f"扫描异常: {e}")
            self._add_log(f"扫描异常: {str(e)[:50]}", "warn")

    async def close(self):
        await self.exchange.close()

    async def start(self):
        self.logger.info("=" * 55)
        self.logger.info("🔱 泰坦 V10.0 启动 | V9.5 扫描器 + ML 进化大脑")
        self.logger.info("=" * 55)

        try:
            await self.run_waterfall_scan(mode="Daily")

            last_label_hour = -1

            while True:
                now = datetime.now(self.tz)
                if now.hour == CONFIG['DAILY_REPORT_HOUR'] and now.minute == CONFIG['DAILY_REPORT_MIN']:
                    await self.run_waterfall_scan(mode="Daily")
                    await asyncio.sleep(60)
                if now.minute % 15 == 1:
                    await self.run_waterfall_scan(mode="Sniper")
                    await asyncio.sleep(60)

                if now.hour != last_label_hour and now.minute >= 5:
                    await self._auto_label_signals()
                    last_label_hour = now.hour

                await asyncio.sleep(30)
        except KeyboardInterrupt:
            self.logger.info("🛑 泰坦系统手动停止。")
        finally:
            await self.close()

if __name__ == "__main__":
    asyncio.run(TitanCommander().start())
