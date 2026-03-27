import time
import logging
import asyncio
import requests
import os
import random
from datetime import datetime, timedelta

import pandas as pd
from server.titan_prompt_library import EXTERNAL_DATA_PROMPT

logger = logging.getLogger("TitanExternalData")


class ExternalDataCache:
    def __init__(self):
        self.onchain = {"btc_netflow": 0, "whale_tx_count": 0, "whale_volume_usd": 0, "exchange_reserve_trend": "neutral", "last_updated": 0}
        self.glassnode = {"signal": "NEUTRAL", "score": 0, "details": {"net_flow_score": 0, "whale_score": 0, "sopr_score": 0}, "narrative": "等待初始化", "last_updated": 0}
        self.sentiment = {"global_score": 50, "btc_sentiment": 50, "btc_social_volume": 0, "top_mentions": [], "last_updated": 0}
        self.orderbook = {}
        self.macro = {"gold_price": 0, "gold_change_pct": 0, "dxy_proxy": 100, "dxy_change_pct": 0, "spy_price": 0, "spy_change_pct": 0, "us10y_yield": 0, "risk_mode": "neutral", "correlation_btc_gold": 0, "correlation_btc_spy": 0, "last_updated": 0}
        self.btc_price_history = []
        self.coinglass = {"btc_oi": 0, "btc_oi_change_24h": 0, "btc_funding_rate": 0, "btc_long_short_ratio": 1.0, "btc_liquidation_24h": {"long": 0, "short": 0, "total": 0}, "top_oi_coins": [], "funding_heatmap": {}, "signal": "NEUTRAL", "score": 0, "narrative": "等待初始化", "last_updated": 0}
        self.news = {"articles": [], "btc_sentiment": "neutral", "sentiment_score": 0, "hot_topics": [], "alert_count": 0, "last_updated": 0}

        self.TTL_ONCHAIN = 300
        self.TTL_GLASSNODE = 3600
        self.TTL_SENTIMENT = 300
        self.TTL_ORDERBOOK = 120
        self.TTL_MACRO = 600
        self.TTL_COINGLASS = 180
        self.TTL_NEWS = 300

    def is_stale(self, category):
        ttl_map = {"onchain": self.TTL_ONCHAIN, "glassnode": self.TTL_GLASSNODE, "sentiment": self.TTL_SENTIMENT, "orderbook": self.TTL_ORDERBOOK, "macro": self.TTL_MACRO, "coinglass": self.TTL_COINGLASS, "news": self.TTL_NEWS}
        data_map = {"onchain": self.onchain, "glassnode": self.glassnode, "sentiment": self.sentiment, "orderbook": self.orderbook, "macro": self.macro, "coinglass": self.coinglass, "news": self.news}
        data = data_map.get(category, {})
        ttl = ttl_map.get(category, 300)
        last = data.get("last_updated", 0) if isinstance(data, dict) else 0
        return (time.time() - last) > ttl

    def get_snapshot(self):
        return {
            "onchain": dict(self.onchain),
            "glassnode": dict(self.glassnode),
            "sentiment": dict(self.sentiment),
            "macro": dict(self.macro),
            "coinglass": dict(self.coinglass),
            "news": dict(self.news),
            "orderbook_summary": self._summarize_orderbook(),
        }

    def _summarize_orderbook(self):
        if not self.orderbook:
            return {"available": False}
        summaries = {}
        for sym, data in list(self.orderbook.items())[:10]:
            summaries[sym] = {
                "bid_depth": data.get("bid_depth", 0),
                "ask_depth": data.get("ask_depth", 0),
                "imbalance": data.get("imbalance", 0),
                "spread_pct": data.get("spread_pct", 0),
            }
        return {"available": True, "assets": summaries}

    def get_ml_features(self, symbol=None):
        features = {}
        features["ext_fng"] = self.onchain.get("fng_value", 50)

        gn = self.glassnode
        gn_details = gn.get("details", {})
        if gn.get("last_updated", 0) > 0 and gn_details.get("net_flow_score", 0) != 0:
            features["ext_btc_netflow"] = gn_details.get("net_flow_score", 0)
            features["ext_whale_activity"] = gn_details.get("whale_score", 0)
        else:
            features["ext_btc_netflow"] = self.onchain.get("btc_netflow", 0)
            features["ext_whale_activity"] = min(self.onchain.get("whale_tx_count", 0) / 50.0, 2.0)

        features["ext_sopr_score"] = gn_details.get("sopr_score", 0)
        features["ext_onchain_composite"] = gn.get("score", 0) / 100.0
        features["ext_sentiment_global"] = self.sentiment.get("global_score", 50) / 100.0
        features["ext_btc_sentiment"] = self.sentiment.get("btc_sentiment", 50) / 100.0
        features["ext_social_volume_norm"] = min(self.sentiment.get("btc_social_volume", 0) / 10000.0, 3.0)
        features["ext_gold_change"] = self.macro.get("gold_change_pct", 0)
        features["ext_dxy_change"] = self.macro.get("dxy_change_pct", 0)
        features["ext_spy_change"] = self.macro.get("spy_change_pct", 0)
        risk_map = {"risk_on": 1.0, "neutral": 0.0, "risk_off": -1.0}
        features["ext_risk_mode"] = risk_map.get(self.macro.get("risk_mode", "neutral"), 0.0)

        if symbol and symbol in self.orderbook:
            ob = self.orderbook[symbol]
            features["ext_ob_imbalance"] = ob.get("imbalance", 0)
            features["ext_ob_spread"] = ob.get("spread_pct", 0)
        else:
            features["ext_ob_imbalance"] = 0.0
            features["ext_ob_spread"] = 0.0

        cg = self.coinglass
        if cg.get("last_updated", 0) > 0:
            features["ext_cg_oi_change"] = cg.get("btc_oi_change_24h", 0) / 100.0
            features["ext_cg_funding"] = min(max(cg.get("btc_funding_rate", 0) * 1000, -1.0), 1.0)
            features["ext_cg_ls_ratio"] = cg.get("btc_long_short_ratio", 1.0) - 1.0
            liq = cg.get("btc_liquidation_24h", {})
            total_liq = liq.get("total", 0)
            long_liq = liq.get("long", 0)
            features["ext_cg_liq_bias"] = ((long_liq / (total_liq + 1e-10)) - 0.5) * 2 if total_liq > 0 else 0
            cg_score_map = {"BULLISH": 1.0, "NEUTRAL": 0.0, "BEARISH": -1.0}
            features["ext_cg_signal"] = cg_score_map.get(cg.get("signal", "NEUTRAL"), 0.0)
        else:
            features["ext_cg_oi_change"] = 0.0
            features["ext_cg_funding"] = 0.0
            features["ext_cg_ls_ratio"] = 0.0
            features["ext_cg_liq_bias"] = 0.0
            features["ext_cg_signal"] = 0.0

        news = self.news
        if news.get("last_updated", 0) > 0:
            features["ext_news_sentiment"] = news.get("sentiment_score", 0) / 100.0
            features["ext_news_alert_count"] = min(news.get("alert_count", 0) / 10.0, 1.0)
        else:
            features["ext_news_sentiment"] = 0.0
            features["ext_news_alert_count"] = 0.0

        return features


class GlassnodeFetcher:
    BASE_URL = "https://api.glassnode.com/v1"

    def __init__(self):
        self.api_key = os.environ.get("GLASSNODE_API_KEY", "")
        self.mock_mode = not bool(self.api_key)
        self.cache = {}
        self.cache_expiry = 3600
        if self.mock_mode:
            logger.info("Glassnode: 无API Key，启用模拟模式")

    def _get_params(self, asset="BTC", period="24h"):
        return {
            "a": asset,
            "api_key": self.api_key,
            "s": int((datetime.now() - timedelta(days=30)).timestamp()),
            "u": int(datetime.now().timestamp()),
            "i": period,
            "f": "json"
        }

    def _fetch_data(self, endpoint, params):
        if self.mock_mode:
            return self._generate_mock_data(endpoint)
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    time.sleep(2 ** attempt)
                else:
                    logger.warning(f"Glassnode {response.status_code}: {endpoint}")
                    break
            except Exception as e:
                logger.warning(f"Glassnode请求异常: {e}")
                time.sleep(2)
        return []

    def _generate_mock_data(self, endpoint):
        data = []
        base_time = int((datetime.now() - timedelta(days=30)).timestamp())
        for i in range(30):
            timestamp = base_time + (i * 86400)
            if "net_flow" in endpoint or "net_transfers" in endpoint:
                val = random.uniform(-2000, 2000)
            elif "balance_1k" in endpoint:
                val = 2000 + random.uniform(-10, 10)
            elif "sopr" in endpoint:
                val = 1.0 + random.uniform(-0.05, 0.05)
            else:
                val = random.random()
            data.append({"t": timestamp, "v": val})
        return data

    def get_exchange_net_flow_score(self, asset="BTC"):
        endpoint = "/metrics/transactions/transfers_volume_sum_net_transfers_exchanges_successful"
        data = self._fetch_data(endpoint, self._get_params(asset, "24h"))
        if not data:
            return 0
        try:
            df = pd.DataFrame(data)
            latest_flow = df['v'].iloc[-1]
            score = -(latest_flow / 5000.0)
            return max(min(score, 1.0), -1.0)
        except Exception:
            return 0

    def get_whale_accumulation_score(self, asset="BTC"):
        endpoint = "/metrics/addresses/count_balance_gte_1k"
        data = self._fetch_data(endpoint, self._get_params(asset, "24h"))
        if not data:
            return 0
        try:
            df = pd.DataFrame(data)
            last_7_days = df['v'].tail(7)
            if len(last_7_days) < 2:
                return 0
            change = last_7_days.iloc[-1] - last_7_days.iloc[0]
            score = change / 10.0
            return max(min(score, 1.0), -1.0)
        except Exception:
            return 0

    def get_market_sentiment_sopr(self, asset="BTC"):
        endpoint = "/metrics/indicators/sopr"
        data = self._fetch_data(endpoint, self._get_params(asset, "24h"))
        if not data:
            return 0
        try:
            df = pd.DataFrame(data)
            latest_sopr = df['v'].iloc[-1]
            if latest_sopr < 1.0:
                return min((1.0 - latest_sopr) * 10, 1.0)
            elif latest_sopr > 1.0:
                return max(-(latest_sopr - 1.0) * 10, -1.0)
            return 0
        except Exception:
            return 0

    def get_comprehensive_signal(self, asset="BTC"):
        flow_score = self.get_exchange_net_flow_score(asset)
        whale_score = self.get_whale_accumulation_score(asset)
        sopr_score = self.get_market_sentiment_sopr(asset)
        total_score = (flow_score * 0.5) + (whale_score * 0.3) + (sopr_score * 0.2)

        analysis = []
        if flow_score < -0.5:
            analysis.append(f"交易所检测到大量{asset}流入，潜在抛压")
        elif flow_score > 0.5:
            analysis.append(f"交易所{asset}持续流出，供应紧缺")
        if whale_score > 0.3:
            analysis.append("巨鲸地址增加，大户吸筹")
        elif whale_score < -0.3:
            analysis.append("巨鲸地址减少，大户离场")
        if sopr_score > 0.3:
            analysis.append("SOPR<1市场割肉，底部信号")
        elif sopr_score < -0.3:
            analysis.append("SOPR>1获利盘多，见顶风险")

        signal_type = "NEUTRAL"
        if total_score > 0.3:
            signal_type = "BULLISH"
        if total_score < -0.3:
            signal_type = "BEARISH"

        return {
            "signal": signal_type,
            "score": round(total_score * 100, 2),
            "details": {
                "net_flow_score": round(flow_score, 4),
                "whale_score": round(whale_score, 4),
                "sopr_score": round(sopr_score, 4)
            },
            "narrative": " | ".join(analysis) if analysis else "链上数据平稳，无显著异常"
        }


_glassnode_fetcher = None

def get_glassnode_fetcher():
    global _glassnode_fetcher
    if _glassnode_fetcher is None:
        _glassnode_fetcher = GlassnodeFetcher()
    return _glassnode_fetcher


class TitanOnChainFetcher:
    @staticmethod
    def fetch():
        result = {
            "btc_netflow": 0,
            "whale_tx_count": 0,
            "whale_volume_usd": 0,
            "exchange_reserve_trend": "neutral",
            "last_updated": time.time(),
        }

        try:
            r = requests.get("https://api.blockchain.info/stats", timeout=10)
            if r.status_code == 200:
                stats = r.json()
                result["btc_hash_rate"] = stats.get("hash_rate", 0)
                result["btc_tx_count_24h"] = stats.get("n_tx", 0)
                result["btc_blocks_mined"] = stats.get("n_blocks_mined", 0)
                result["btc_minutes_between_blocks"] = stats.get("minutes_between_blocks", 10)
                result["btc_total_btc_sent"] = stats.get("total_btc_sent", 0) / 1e8
                result["btc_market_price"] = stats.get("market_price_usd", 0)
        except Exception as e:
            logger.warning(f"Blockchain.info stats failed: {e}")

        try:
            r = requests.get("https://api.blockchain.info/charts/estimated-transaction-volume-usd?timespan=2days&format=json", timeout=10)
            if r.status_code == 200:
                data = r.json()
                values = data.get("values", [])
                if len(values) >= 2:
                    today_vol = values[-1].get("y", 0)
                    yest_vol = values[-2].get("y", 0)
                    if yest_vol > 0:
                        result["btc_volume_change"] = ((today_vol - yest_vol) / yest_vol) * 100
        except Exception as e:
            logger.warning(f"Blockchain.info volume chart failed: {e}")

        try:
            r = requests.get("https://api.blockchain.info/charts/exchange-trade-volume?timespan=2days&format=json", timeout=10)
            if r.status_code == 200:
                data = r.json()
                values = data.get("values", [])
                if len(values) >= 2:
                    curr = values[-1].get("y", 0)
                    prev = values[-2].get("y", 0)
                    result["btc_netflow"] = round((curr - prev) / (prev + 1e-10) * 100, 2)
                    result["exchange_reserve_trend"] = "inflow" if curr > prev else "outflow"
        except Exception as e:
            logger.warning(f"Blockchain.info exchange volume failed: {e}")

        try:
            r = requests.get("https://api.whale-alert.io/v1/status", timeout=5)
            if r.status_code == 200:
                result["whale_api_status"] = "online"
        except Exception:
            pass

        try:
            r = requests.get("https://api.blockchain.info/charts/n-unique-addresses?timespan=7days&format=json", timeout=10)
            if r.status_code == 200:
                data = r.json()
                values = data.get("values", [])
                if len(values) >= 2:
                    curr = values[-1].get("y", 0)
                    prev = values[-2].get("y", 0)
                    result["active_addresses_change"] = round(((curr - prev) / (prev + 1e-10)) * 100, 2)
                    result["active_addresses"] = curr
        except Exception as e:
            logger.warning(f"Active addresses fetch failed: {e}")

        return result


class TitanSentimentFetcher:
    @staticmethod
    def fetch():
        result = {
            "global_score": 50,
            "btc_sentiment": 50,
            "btc_social_volume": 0,
            "top_mentions": [],
            "last_updated": time.time(),
        }

        try:
            r = requests.get("https://api.alternative.me/fng/?limit=7", timeout=5)
            if r.status_code == 200:
                data = r.json().get("data", [])
                if data:
                    result["fng_value"] = int(data[0].get("value", 50))
                    result["fng_label"] = data[0].get("value_classification", "Neutral")
                    if len(data) >= 2:
                        prev = int(data[1].get("value", 50))
                        result["fng_change"] = result["fng_value"] - prev
                    if len(data) >= 7:
                        result["fng_7d_avg"] = round(sum(int(d.get("value", 50)) for d in data) / len(data), 1)
        except Exception as e:
            logger.warning(f"FNG API failed: {e}")

        try:
            r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10)
            if r.status_code == 200:
                data = r.json()
                coins = data.get("coins", [])
                trending = []
                for c in coins[:10]:
                    item = c.get("item", {})
                    trending.append({
                        "name": item.get("name", ""),
                        "symbol": item.get("symbol", ""),
                        "market_cap_rank": item.get("market_cap_rank", 0),
                        "score": item.get("score", 0),
                    })
                result["trending_coins"] = trending
                result["btc_social_volume"] = len(trending) * 100
        except Exception as e:
            logger.warning(f"CoinGecko trending failed: {e}")

        try:
            r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", {})
                result["total_market_cap_change_24h"] = round(data.get("market_cap_change_percentage_24h_usd", 0), 2)
                result["btc_dominance"] = round(data.get("market_cap_percentage", {}).get("btc", 0), 2)
                result["eth_dominance"] = round(data.get("market_cap_percentage", {}).get("eth", 0), 2)
                result["total_volume_usd"] = data.get("total_volume", {}).get("usd", 0)
                result["active_cryptos"] = data.get("active_cryptocurrencies", 0)

                mktcap_change = result["total_market_cap_change_24h"]
                fng = result.get("fng_value", 50)
                if fng >= 60 and mktcap_change > 2:
                    result["global_score"] = 75
                    result["btc_sentiment"] = 70
                elif fng <= 30 and mktcap_change < -2:
                    result["global_score"] = 25
                    result["btc_sentiment"] = 30
                elif fng >= 50:
                    result["global_score"] = 60
                    result["btc_sentiment"] = 55
                else:
                    result["global_score"] = 40
                    result["btc_sentiment"] = 45
        except Exception as e:
            logger.warning(f"CoinGecko global failed: {e}")

        return result


class TitanOrderBookFetcher:
    @staticmethod
    async def fetch(exchange, symbols):
        result = {}
        for sym in symbols[:15]:
            pair = f"{sym}/USDT"
            try:
                ob = await asyncio.wait_for(exchange.fetch_order_book(pair, limit=20), timeout=5)
                bids = ob.get("bids", [])
                asks = ob.get("asks", [])

                bid_depth = sum(b[0] * b[1] for b in bids[:10]) if bids else 0
                ask_depth = sum(a[0] * a[1] for a in asks[:10]) if asks else 0
                total_depth = bid_depth + ask_depth

                imbalance = (bid_depth - ask_depth) / (total_depth + 1e-10) if total_depth > 0 else 0

                best_bid = bids[0][0] if bids else 0
                best_ask = asks[0][0] if asks else 0
                mid_price = (best_bid + best_ask) / 2 if best_bid and best_ask else 0
                spread_pct = ((best_ask - best_bid) / (mid_price + 1e-10)) * 100 if mid_price > 0 else 0

                bid_walls = [{"price": b[0], "size_usd": round(b[0] * b[1], 2)} for b in bids[:5]]
                ask_walls = [{"price": a[0], "size_usd": round(a[0] * a[1], 2)} for a in asks[:5]]

                result[sym] = {
                    "bid_depth": round(bid_depth, 2),
                    "ask_depth": round(ask_depth, 2),
                    "imbalance": round(imbalance, 4),
                    "spread_pct": round(spread_pct, 4),
                    "bid_walls": bid_walls,
                    "ask_walls": ask_walls,
                    "mid_price": round(mid_price, 6),
                    "last_updated": time.time(),
                }
            except Exception as e:
                logger.debug(f"Order book fetch failed for {pair}: {e}")
                continue
        return result


class TitanMacroFetcher:
    ALPHA_VANTAGE_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "")

    @staticmethod
    def fetch():
        result = {
            "gold_price": 0,
            "gold_change_pct": 0,
            "dxy_proxy": 100,
            "dxy_change_pct": 0,
            "spy_price": 0,
            "spy_change_pct": 0,
            "us10y_yield": 0,
            "risk_mode": "neutral",
            "correlation_btc_gold": 0,
            "correlation_btc_spy": 0,
            "last_updated": time.time(),
        }

        api_key = TitanMacroFetcher.ALPHA_VANTAGE_KEY
        if not api_key:
            logger.info("Alpha Vantage API key not set, using alternative sources")
            return TitanMacroFetcher._fetch_alternative(result)

        try:
            r = requests.get(f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=XAU&to_currency=USD&apikey={api_key}", timeout=10)
            if r.status_code == 200:
                data = r.json().get("Realtime Currency Exchange Rate", {})
                price = float(data.get("5. Exchange Rate", 0))
                result["gold_price"] = round(price, 2)
        except Exception as e:
            logger.warning(f"Alpha Vantage gold failed: {e}")

        try:
            r = requests.get(f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=EUR&to_currency=USD&apikey={api_key}", timeout=10)
            if r.status_code == 200:
                data = r.json().get("Realtime Currency Exchange Rate", {})
                eur_usd = float(data.get("5. Exchange Rate", 1.0))
                dxy_approx = 50.14348 * (eur_usd ** -0.576)
                result["dxy_proxy"] = round(dxy_approx, 2)
        except Exception as e:
            logger.warning(f"Alpha Vantage EUR/USD failed: {e}")

        try:
            r = requests.get(f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={api_key}", timeout=10)
            if r.status_code == 200:
                data = r.json().get("Global Quote", {})
                result["spy_price"] = round(float(data.get("05. price", 0)), 2)
                result["spy_change_pct"] = round(float(data.get("10. change percent", "0").replace("%", "")), 2)
        except Exception as e:
            logger.warning(f"Alpha Vantage SPY failed: {e}")

        result["risk_mode"] = TitanMacroFetcher._calc_risk_mode(result)
        return result

    @staticmethod
    def _fetch_alternative(result):
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,tether-gold&vs_currencies=usd&include_24hr_change=true", timeout=10)
            if r.status_code == 200:
                data = r.json()
                tgold = data.get("tether-gold", {})
                result["gold_price"] = round(tgold.get("usd", 0), 2)
                result["gold_change_pct"] = round(tgold.get("usd_24h_change", 0), 2)
        except Exception as e:
            logger.warning(f"CoinGecko gold proxy failed: {e}")

        try:
            r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
            if r.status_code == 200:
                data = r.json()
                rates = data.get("rates", {})
                eur = rates.get("EUR", 0.92)
                jpy = rates.get("JPY", 150)
                gbp = rates.get("GBP", 0.79)
                cad = rates.get("CAD", 1.36)
                sek = rates.get("SEK", 10.5)
                chf = rates.get("CHF", 0.88)
                eur_usd = 1.0 / (eur + 1e-10)
                usd_jpy = jpy
                gbp_usd = 1.0 / (gbp + 1e-10)
                usd_cad = cad
                usd_sek = sek
                usd_chf = chf
                dxy = 50.14348 * (eur_usd ** -0.576) * (usd_jpy ** 0.136) * (gbp_usd ** -0.119) * (usd_cad ** 0.091) * (usd_sek ** 0.042) * (usd_chf ** 0.036)
                result["dxy_proxy"] = round(dxy, 2)
                result["fx_rates"] = {"EUR/USD": round(eur_usd, 4), "USD/JPY": round(usd_jpy, 2), "GBP/USD": round(gbp_usd, 4)}
        except Exception as e:
            logger.warning(f"Exchange rate API failed: {e}")

        result["risk_mode"] = TitanMacroFetcher._calc_risk_mode(result)
        return result

    @staticmethod
    def _calc_risk_mode(data):
        score = 0
        gold_ch = data.get("gold_change_pct", 0)
        spy_ch = data.get("spy_change_pct", 0)
        dxy = data.get("dxy_proxy", 100)

        if gold_ch > 1:
            score -= 1
        elif gold_ch < -1:
            score += 1
        if spy_ch > 1:
            score += 1
        elif spy_ch < -1:
            score -= 1
        if dxy > 105:
            score -= 1
        elif dxy < 95:
            score += 1

        if score >= 2:
            return "risk_on"
        elif score <= -2:
            return "risk_off"
        return "neutral"


class TitanCoinGlassFetcher:
    BASE_URL = "https://open-api-v4.coinglass.com/api"

    def __init__(self):
        self.api_key = os.environ.get("COINGLASS_API_KEY", "")
        self.mock_mode = not bool(self.api_key)
        if self.mock_mode:
            logger.info("CoinGlass: 无API Key，启用智能模拟模式")

    def _headers(self):
        return {"accept": "application/json", "CG-API-KEY": self.api_key}

    def _fetch(self, endpoint, params=None):
        if self.mock_mode:
            return None
        url = f"{self.BASE_URL}{endpoint}"
        for attempt in range(3):
            try:
                r = requests.get(url, headers=self._headers(), params=params or {}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success") or data.get("code") == "0":
                        return data.get("data")
                elif r.status_code == 429:
                    time.sleep(2 ** attempt)
                else:
                    logger.warning(f"CoinGlass {r.status_code}: {endpoint}")
                    break
            except Exception as e:
                logger.warning(f"CoinGlass请求异常: {e}")
                time.sleep(1)
        return None

    def fetch_all(self):
        result = {
            "btc_oi": 0, "btc_oi_change_24h": 0,
            "btc_funding_rate": 0, "btc_long_short_ratio": 1.0,
            "btc_liquidation_24h": {"long": 0, "short": 0, "total": 0},
            "top_oi_coins": [], "funding_heatmap": {},
            "long_short_accounts": {},
            "top_trader_sentiment": {},
            "taker_buy_sell": {},
            "etf_flows": {},
            "exchange_balances": {},
            "whale_transfers": [],
            "oi_history": [],
            "liquidation_coins": [],
            "coinbase_premium": None,
            "ahr999": None,
            "signal": "NEUTRAL", "score": 0, "narrative": "等待数据",
            "last_updated": time.time(),
        }

        if self.mock_mode:
            return self._generate_mock()

        try:
            coins_data = self._fetch("/futures/coins-markets")
            if coins_data and isinstance(coins_data, list):
                btc_entry = None
                top_coins = []
                for coin in coins_data:
                    sym = coin.get("symbol", "")
                    if sym == "BTC":
                        btc_entry = coin
                    if coin.get("openInterest", 0) > 0:
                        top_coins.append({
                            "symbol": sym,
                            "oi": round(coin.get("openInterest", 0), 2),
                            "oi_change_24h": round(coin.get("openInterestChange24h", 0), 2),
                            "volume_24h": round(coin.get("volUsd", 0), 2),
                            "price": coin.get("price", 0),
                        })
                top_coins.sort(key=lambda x: x["oi"], reverse=True)
                result["top_oi_coins"] = top_coins[:20]

                if btc_entry:
                    result["btc_oi"] = round(btc_entry.get("openInterest", 0), 2)
                    result["btc_oi_change_24h"] = round(btc_entry.get("openInterestChange24h", 0), 2)
        except Exception as e:
            logger.warning(f"CoinGlass OI获取失败: {e}")

        if result["btc_oi"] == 0:
            try:
                r = requests.get("https://api.gateio.ws/api/v4/futures/usdt/contracts/BTC_USDT", timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    pos_size = float(d.get("position_size", 0))
                    quanto = float(d.get("quanto_multiplier", "0.0001"))
                    mark_price = float(d.get("mark_price", 0))
                    oi_usd = pos_size * quanto * mark_price
                    if oi_usd > 0:
                        result["btc_oi"] = round(oi_usd, 2)
                        result["btc_oi_source"] = "gate.io"
                        logger.info(f"BTC OI从Gate.io获取: ${oi_usd:,.0f}")
            except Exception as e:
                logger.warning(f"Gate.io OI备用获取失败: {e}")

        if not result["top_oi_coins"]:
            try:
                top_symbols = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "MATIC"]
                top_coins = []
                for sym in top_symbols:
                    try:
                        r = requests.get(f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{sym}_USDT", timeout=5)
                        if r.status_code == 200:
                            d = r.json()
                            pos_size = float(d.get("position_size", 0))
                            quanto = float(d.get("quanto_multiplier", "0.0001"))
                            mark_price = float(d.get("mark_price", 0))
                            oi_usd = pos_size * quanto * mark_price
                            if oi_usd > 100000:
                                top_coins.append({
                                    "symbol": sym,
                                    "oi": round(oi_usd, 2),
                                    "oi_change_24h": 0,
                                    "volume_24h": 0,
                                    "price": mark_price,
                                })
                    except Exception:
                        continue
                top_coins.sort(key=lambda x: x["oi"], reverse=True)
                result["top_oi_coins"] = top_coins
            except Exception as e:
                logger.warning(f"Gate.io 持仓排行备用获取失败: {e}")

        try:
            fr_data = self._fetch("/futures/funding-rate/exchange-list", {"symbol": "BTC"})
            if fr_data and isinstance(fr_data, list) and len(fr_data) > 0:
                btc_fr = next((x for x in fr_data if x.get("symbol") == "BTC"), fr_data[0])
                sm_list = btc_fr.get("stablecoin_margin_list", [])
                if sm_list:
                    rates = [float(x.get("funding_rate", 0)) for x in sm_list if x.get("funding_rate") is not None]
                    if rates:
                        avg_rate = sum(rates) / len(rates)
                        result["btc_funding_rate"] = round(avg_rate / 100, 6)
                        result["funding_heatmap"]["BTC"] = {
                            "avg_rate": result["btc_funding_rate"],
                            "exchanges": [{
                                "exchange": x.get("exchange", ""),
                                "rate": round(float(x.get("funding_rate", 0)) / 100, 6),
                            } for x in sm_list[:10]],
                        }
        except Exception as e:
            logger.warning(f"CoinGlass资金费率获取失败: {e}")

        try:
            liq_coins_data = self._fetch("/futures/liquidation/coin-list")
            if liq_coins_data and isinstance(liq_coins_data, list):
                btc_liq = next((c for c in liq_coins_data if c.get("symbol") == "BTC"), None)
                if btc_liq:
                    total_long = float(btc_liq.get("long_liquidation_usd_24h", 0))
                    total_short = float(btc_liq.get("short_liquidation_usd_24h", 0))
                    result["btc_liquidation_24h"] = {
                        "long": round(total_long, 2),
                        "short": round(total_short, 2),
                        "total": round(total_long + total_short, 2),
                    }
                liq_coins_data.sort(key=lambda x: float(x.get("liquidation_usd_24h", 0)), reverse=True)
                result["liquidation_coins"] = [{
                    "symbol": c.get("symbol", ""),
                    "long_vol": round(float(c.get("long_liquidation_usd_24h", 0)), 2),
                    "short_vol": round(float(c.get("short_liquidation_usd_24h", 0)), 2),
                    "total": round(float(c.get("liquidation_usd_24h", 0)), 2),
                } for c in liq_coins_data[:15]]
        except Exception as e:
            logger.warning(f"CoinGlass清算数据获取失败: {e}")

        try:
            ls_data = self._fetch("/futures/global-long-short-account-ratio/history", {"symbol": "BTC", "interval": "h1", "limit": 24})
            if ls_data and isinstance(ls_data, list) and len(ls_data) > 0:
                latest = ls_data[-1]
                result["btc_long_short_ratio"] = round(float(latest.get("longShortRatio", latest.get("long_short_ratio", 1.0))), 4)
                long_r = float(latest.get("longAccount", latest.get("long_account", 50)))
                short_r = float(latest.get("shortAccount", latest.get("short_account", 50)))
                result["long_short_accounts"] = {
                    "long_ratio": round(long_r, 2),
                    "short_ratio": round(short_r, 2),
                    "ratio": result["btc_long_short_ratio"],
                    "history": [{"time": int(item.get("createTime", item.get("time", 0)))} for item in ls_data[-24:]],
                }
        except Exception as e:
            logger.warning(f"CoinGlass多空比获取失败: {e}")

        try:
            top_ls = self._fetch("/futures/top-long-short-position-ratio/history", {"symbol": "BTC", "interval": "h1", "limit": 24})
            if top_ls and isinstance(top_ls, list) and len(top_ls) > 0:
                latest = top_ls[-1]
                long_r = float(latest.get("longAccount", latest.get("long_account", 50)))
                short_r = float(latest.get("shortAccount", latest.get("short_account", 50)))
                ratio = float(latest.get("longShortRatio", latest.get("long_short_ratio", 1.0)))
                result["top_trader_sentiment"] = {
                    "long_ratio": round(long_r, 2),
                    "short_ratio": round(short_r, 2),
                    "ratio": round(ratio, 4),
                }
        except Exception as e:
            logger.warning(f"CoinGlass顶级交易员数据获取失败: {e}")

        try:
            taker = self._fetch("/futures/aggregated-taker-buy-sell-volume/history", {"exchange_list": "Binance", "symbol": "BTC", "interval": "h1", "limit": 24})
            if taker and isinstance(taker, list) and len(taker) > 0:
                latest = taker[-1]
                buy_vol = float(latest.get("aggregated_buy_volume_usd", latest.get("buyVolUsd", 0)))
                sell_vol = float(latest.get("aggregated_sell_volume_usd", latest.get("sellVolUsd", 0)))
                ratio = buy_vol / (sell_vol + 1e-10)
                result["taker_buy_sell"] = {
                    "buy_vol": round(buy_vol, 2),
                    "sell_vol": round(sell_vol, 2),
                    "ratio": round(ratio, 4),
                }
        except Exception as e:
            logger.warning(f"CoinGlass Taker数据获取失败: {e}")

        try:
            etf_data = self._fetch("/etf/bitcoin/flow-history", {"limit": 14})
            if etf_data and isinstance(etf_data, list):
                etf_data_sorted = sorted(etf_data, key=lambda x: x.get("timestamp", 0), reverse=True)
                flows = []
                for item in etf_data_sorted[:14]:
                    ts = item.get("timestamp", 0)
                    from datetime import datetime
                    date_str = datetime.utcfromtimestamp(ts / 1000 if ts > 1e12 else ts).strftime("%m-%d") if ts else ""
                    flows.append({
                        "date": date_str,
                        "total_net_flow": round(float(item.get("flow_usd", 0)), 2),
                        "price": round(float(item.get("price_usd", 0)), 2),
                    })
                total_7d = sum(f["total_net_flow"] for f in flows[:7])
                result["etf_flows"] = {
                    "history": flows,
                    "net_7d": round(total_7d, 2),
                    "latest_flow": flows[0]["total_net_flow"] if flows else 0,
                }
        except Exception as e:
            logger.warning(f"CoinGlass ETF数据获取失败: {e}")

        result.update(self._analyze(result))
        result["last_updated"] = time.time()
        return result

    def _analyze(self, data):
        score = 0
        analysis = []

        fr = data.get("btc_funding_rate", 0)
        if fr > 0.0005:
            score -= 20
            analysis.append(f"资金费率偏高({fr*100:.4f}%)，多头过热")
        elif fr < -0.0003:
            score += 20
            analysis.append(f"资金费率为负({fr*100:.4f}%)，空头付费")
        elif fr > 0.0001:
            score -= 5
            analysis.append("资金费率正常偏多")
        else:
            analysis.append("资金费率中性")

        oi_change = data.get("btc_oi_change_24h", 0)
        if oi_change > 5:
            score += 10
            analysis.append(f"OI增长{oi_change:.1f}%，新资金入场")
        elif oi_change < -5:
            score -= 10
            analysis.append(f"OI下降{oi_change:.1f}%，资金出逃")

        liq = data.get("btc_liquidation_24h", {})
        total_liq = liq.get("total", 0)
        long_liq = liq.get("long", 0)
        if total_liq > 0:
            long_ratio = long_liq / (total_liq + 1e-10)
            if long_ratio > 0.7:
                score += 15
                analysis.append(f"多头清算占比{long_ratio*100:.0f}%，多头洗盘或见底")
            elif long_ratio < 0.3:
                score -= 15
                analysis.append(f"空头清算占比{(1-long_ratio)*100:.0f}%，空头回补或见顶")

        ls = data.get("long_short_accounts", {})
        ls_ratio = ls.get("ratio", 1.0)
        if ls_ratio > 1.5:
            score -= 10
            analysis.append(f"多空账户比{ls_ratio:.2f}，多头拥挤")
        elif ls_ratio < 0.7:
            score += 10
            analysis.append(f"多空账户比{ls_ratio:.2f}，空头拥挤")

        taker = data.get("taker_buy_sell", {})
        taker_ratio = taker.get("ratio", 1.0)
        if taker_ratio > 1.3:
            score += 5
            analysis.append("主动买入主导")
        elif taker_ratio < 0.7:
            score -= 5
            analysis.append("主动卖出主导")

        etf = data.get("etf_flows", {})
        etf_7d = etf.get("net_7d", 0)
        if etf_7d > 500e6:
            score += 10
            analysis.append(f"ETF 7日净流入${etf_7d/1e6:.0f}M，机构看多")
        elif etf_7d < -500e6:
            score -= 10
            analysis.append(f"ETF 7日净流出${abs(etf_7d)/1e6:.0f}M，机构撤退")

        cb_prem = data.get("coinbase_premium")
        if cb_prem is not None:
            if cb_prem > 50:
                score += 5
                analysis.append("Coinbase正溢价，美国买盘强")
            elif cb_prem < -50:
                score -= 5
                analysis.append("Coinbase负溢价，美国卖压重")

        signal = "NEUTRAL"
        if score > 20:
            signal = "BULLISH"
        elif score < -20:
            signal = "BEARISH"

        return {
            "signal": signal,
            "score": score,
            "narrative": " | ".join(analysis) if analysis else "衍生品市场数据平稳",
        }

    def _generate_mock(self):
        fr = random.uniform(-0.0003, 0.0008)
        oi = random.uniform(15e9, 25e9)
        oi_change = random.uniform(-8, 12)
        long_liq = random.uniform(20e6, 200e6)
        short_liq = random.uniform(20e6, 200e6)
        ls_ratio = random.uniform(0.8, 1.5)

        top_coins = []
        for sym, base_oi in [("BTC", oi), ("ETH", oi * 0.4), ("SOL", oi * 0.08), ("XRP", oi * 0.05), ("DOGE", oi * 0.03)]:
            top_coins.append({
                "symbol": sym,
                "oi": round(base_oi, 2),
                "oi_change_24h": round(random.uniform(-10, 15), 2),
                "volume_24h": round(base_oi * random.uniform(0.3, 0.8), 2),
                "price": 0,
            })

        result = {
            "btc_oi": round(oi, 2),
            "btc_oi_change_24h": round(oi_change, 2),
            "btc_funding_rate": round(fr, 6),
            "btc_long_short_ratio": round(ls_ratio, 4),
            "btc_liquidation_24h": {
                "long": round(long_liq, 2),
                "short": round(short_liq, 2),
                "total": round(long_liq + short_liq, 2),
            },
            "top_oi_coins": top_coins,
            "funding_heatmap": {
                "BTC": {
                    "avg_rate": round(fr, 6),
                    "exchanges": [
                        {"exchange": "Binance", "rate": round(fr + random.uniform(-0.0001, 0.0001), 6)},
                        {"exchange": "OKX", "rate": round(fr + random.uniform(-0.0001, 0.0001), 6)},
                        {"exchange": "Bybit", "rate": round(fr + random.uniform(-0.0001, 0.0001), 6)},
                    ],
                },
            },
            "last_updated": time.time(),
        }
        result.update(self._analyze(result))
        return result


    def fetch_global_market(self):
        import ccxt as ccxt_sync
        result = {
            "coins": [],
            "summary": {
                "total_oi": 0,
                "total_liquidation_24h": 0,
                "fng_index": 0,
                "fng_label": "",
                "btc_dominance": 0,
            },
            "gainers": [],
            "losers": [],
            "oi_gainers": [],
            "last_updated": time.time(),
        }

        spot_data = {}
        try:
            exchange = ccxt_sync.gateio({"timeout": 15000})
            tickers = exchange.fetch_tickers()
            for sym, t in tickers.items():
                if not sym.endswith("/USDT"):
                    continue
                base = sym.replace("/USDT", "")
                last = float(t.get("last", 0) or 0)
                if last <= 0:
                    continue
                spot_data[base] = {
                    "price": last,
                    "change_24h": float(t.get("percentage", 0) or 0),
                    "volume_24h": float(t.get("quoteVolume", 0) or 0),
                    "high_24h": float(t.get("high", 0) or 0),
                    "low_24h": float(t.get("low", 0) or 0),
                }
        except Exception as e:
            logger.warning(f"全局市场ccxt获取失败: {e}")

        fr_map = {}
        try:
            fr_all = self._fetch("/futures/funding-rate/exchange-list")
            if fr_all and isinstance(fr_all, list):
                for coin in fr_all:
                    sym = coin.get("symbol", "")
                    sm_list = coin.get("stablecoin_margin_list", [])
                    if sm_list:
                        rates = [float(x.get("funding_rate", 0)) for x in sm_list if x.get("funding_rate") is not None]
                        if rates:
                            fr_map[sym] = {
                                "avg_rate": round(sum(rates) / len(rates) / 100, 6),
                                "exchanges": len(rates),
                            }
        except Exception as e:
            logger.warning(f"全局资金费率获取失败: {e}")

        liq_map = {}
        total_liq = 0
        try:
            liq_data = self._fetch("/futures/liquidation/coin-list")
            if liq_data and isinstance(liq_data, list):
                for c in liq_data:
                    sym = c.get("symbol", "")
                    long_liq = float(c.get("long_liquidation_usd_24h", 0) or 0)
                    short_liq = float(c.get("short_liquidation_usd_24h", 0) or 0)
                    total = long_liq + short_liq
                    total_liq += total
                    liq_map[sym] = {
                        "long": round(long_liq, 2),
                        "short": round(short_liq, 2),
                        "total": round(total, 2),
                    }
        except Exception as e:
            logger.warning(f"全局清算数据获取失败: {e}")

        result["summary"]["total_liquidation_24h"] = round(total_liq, 2)

        try:
            fng_resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
            if fng_resp.status_code == 200:
                fng_data = fng_resp.json().get("data", [])
                if fng_data:
                    result["summary"]["fng_index"] = int(fng_data[0].get("value", 0))
                    result["summary"]["fng_label"] = fng_data[0].get("value_classification", "")
        except Exception:
            pass

        try:
            cg_resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=5)
            if cg_resp.status_code == 200:
                gdata = cg_resp.json().get("data", {})
                result["summary"]["btc_dominance"] = round(float(gdata.get("market_cap_percentage", {}).get("btc", 0)), 2)
                result["summary"]["total_market_cap"] = round(float(gdata.get("total_market_cap", {}).get("usd", 0)), 2)
        except Exception:
            pass

        all_symbols = set(list(spot_data.keys()) + list(fr_map.keys()) + list(liq_map.keys()))
        coins_list = []
        for sym in all_symbols:
            spot = spot_data.get(sym, {})
            fr = fr_map.get(sym, {})
            liq = liq_map.get(sym, {})
            price = spot.get("price", 0)
            if price <= 0:
                continue
            coins_list.append({
                "symbol": sym,
                "price": price,
                "change_24h": round(spot.get("change_24h", 0), 2),
                "volume_24h": round(spot.get("volume_24h", 0), 2),
                "high_24h": spot.get("high_24h", 0),
                "low_24h": spot.get("low_24h", 0),
                "funding_rate": fr.get("avg_rate", None),
                "fr_exchanges": fr.get("exchanges", 0),
                "liq_24h_long": liq.get("long", 0),
                "liq_24h_short": liq.get("short", 0),
                "liq_24h_total": liq.get("total", 0),
            })

        coins_list.sort(key=lambda x: x["volume_24h"], reverse=True)
        result["coins"] = coins_list[:200]

        sorted_by_change = sorted([c for c in coins_list if c["volume_24h"] > 100000], key=lambda x: x["change_24h"], reverse=True)
        result["gainers"] = sorted_by_change[:10]
        result["losers"] = sorted_by_change[-10:][::-1] if len(sorted_by_change) >= 10 else []

        return result


_coinglass_fetcher = None
_global_market_cache = {"data": None, "ts": 0}

def get_coinglass_fetcher():
    global _coinglass_fetcher
    if _coinglass_fetcher is None:
        _coinglass_fetcher = TitanCoinGlassFetcher()
    return _coinglass_fetcher

def get_global_market_data():
    global _global_market_cache
    now = time.time()
    if _global_market_cache["data"] and now - _global_market_cache["ts"] < 120:
        return _global_market_cache["data"]
    try:
        fetcher = get_coinglass_fetcher()
        data = fetcher.fetch_global_market()
        _global_market_cache = {"data": data, "ts": now}
        return data
    except Exception as e:
        logger.error(f"全局市场数据获取失败: {e}")
        return _global_market_cache.get("data") or {"coins": [], "summary": {}, "error": str(e)}


class TitanCryptoPanicFetcher:
    BASE_URL = "https://cryptopanic.com/api/v1"

    def __init__(self):
        self.api_key = os.environ.get("CRYPTOPANIC_API_KEY", "")
        self.mock_mode = not bool(self.api_key)
        if self.mock_mode:
            logger.info("CryptoPanic: 无API Key，启用模拟模式")

    def fetch(self):
        result = {
            "articles": [],
            "btc_sentiment": "neutral",
            "sentiment_score": 0,
            "hot_topics": [],
            "alert_count": 0,
            "last_updated": time.time(),
        }

        if self.mock_mode:
            return self._generate_mock()

        try:
            params = {
                "auth_token": self.api_key,
                "currencies": "BTC,ETH,SOL",
                "filter": "important",
                "kind": "news",
                "regions": "en",
            }
            r = requests.get(f"{self.BASE_URL}/posts/", params=params, timeout=10)
            if r.status_code == 200:
                data = r.json()
                articles = []
                pos_count = 0
                neg_count = 0
                total = 0

                for post in data.get("results", [])[:30]:
                    votes = post.get("votes", {})
                    pos = votes.get("positive", 0)
                    neg = votes.get("negative", 0)
                    imp = votes.get("important", 0)

                    if pos > neg:
                        sentiment = "positive"
                        pos_count += 1
                    elif neg > pos:
                        sentiment = "negative"
                        neg_count += 1
                    else:
                        sentiment = "neutral"
                    total += 1

                    currencies = [c.get("code", "") for c in post.get("currencies", [])]
                    articles.append({
                        "title": post.get("title", ""),
                        "published_at": post.get("published_at", ""),
                        "sentiment": sentiment,
                        "votes_positive": pos,
                        "votes_negative": neg,
                        "votes_important": imp,
                        "currencies": currencies,
                        "source": post.get("source", {}).get("title", ""),
                        "url": post.get("url", ""),
                    })

                result["articles"] = articles[:20]

                if total > 0:
                    score = ((pos_count - neg_count) / total) * 100
                    result["sentiment_score"] = round(score, 1)
                    if score > 30:
                        result["btc_sentiment"] = "bullish"
                    elif score < -30:
                        result["btc_sentiment"] = "bearish"
                    else:
                        result["btc_sentiment"] = "neutral"

                result["alert_count"] = sum(1 for a in articles if a.get("votes_important", 0) > 5)

                topic_counts = {}
                for a in articles:
                    for c in a.get("currencies", []):
                        topic_counts[c] = topic_counts.get(c, 0) + 1
                result["hot_topics"] = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            else:
                logger.warning(f"CryptoPanic API返回 {r.status_code}")
        except Exception as e:
            logger.warning(f"CryptoPanic获取失败: {e}")

        result["last_updated"] = time.time()
        return result

    def _generate_mock(self):
        sentiments = ["positive", "negative", "neutral"]
        topics = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
        mock_headlines = [
            ("比特币突破关键阻力位，市场情绪转好", "positive", ["BTC"]),
            ("SEC推迟ETF审批决定，市场观望", "neutral", ["BTC", "ETH"]),
            ("大型鲸鱼地址异动，疑似大额转移", "neutral", ["BTC"]),
            ("以太坊L2生态TVL创新高", "positive", ["ETH"]),
            ("SOL链Meme币热潮降温", "negative", ["SOL"]),
            ("Coinbase季度收入超预期", "positive", ["BTC", "ETH"]),
            ("机构投资者持续买入BTC现货ETF", "positive", ["BTC"]),
            ("监管机构对加密衍生品发出警告", "negative", ["BTC", "ETH"]),
            ("DeFi协议遭遇闪电贷攻击", "negative", ["ETH"]),
            ("BTC矿工收入持续下降", "negative", ["BTC"]),
        ]
        articles = []
        for i, (title, sent, currencies) in enumerate(mock_headlines):
            articles.append({
                "title": title,
                "published_at": (datetime.now() - timedelta(hours=i * 2)).isoformat(),
                "sentiment": sent,
                "votes_positive": random.randint(0, 50) if sent == "positive" else random.randint(0, 10),
                "votes_negative": random.randint(0, 50) if sent == "negative" else random.randint(0, 10),
                "votes_important": random.randint(0, 20),
                "currencies": currencies,
                "source": random.choice(["CoinDesk", "The Block", "Decrypt", "CoinTelegraph"]),
                "url": "",
            })

        pos = sum(1 for a in articles if a["sentiment"] == "positive")
        neg = sum(1 for a in articles if a["sentiment"] == "negative")
        total = len(articles)
        score = ((pos - neg) / total) * 100 if total > 0 else 0
        btc_sent = "bullish" if score > 30 else ("bearish" if score < -30 else "neutral")

        topic_counts = {}
        for a in articles:
            for c in a.get("currencies", []):
                topic_counts[c] = topic_counts.get(c, 0) + 1

        return {
            "articles": articles,
            "btc_sentiment": btc_sent,
            "sentiment_score": round(score, 1),
            "hot_topics": sorted(topic_counts.items(), key=lambda x: x[1], reverse=True),
            "alert_count": sum(1 for a in articles if a["votes_important"] > 5),
            "last_updated": time.time(),
        }


_cryptopanic_fetcher = None

def get_cryptopanic_fetcher():
    global _cryptopanic_fetcher
    if _cryptopanic_fetcher is None:
        _cryptopanic_fetcher = TitanCryptoPanicFetcher()
    return _cryptopanic_fetcher


class TitanMemoryBank:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.memory_file = os.path.join(data_dir, "titan_memory_bank.json")
        self.memories = {
            "trade_patterns": [],
            "regime_history": [],
            "insights": [],
            "rules": [],
            "performance_snapshots": [],
            "market_events": [],
        }
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.memory_file):
                import json
                with open(self.memory_file, "r") as f:
                    saved = json.load(f)
                    for key in self.memories:
                        if key in saved:
                            self.memories[key] = saved[key]
                self._recent_pattern_keys = set()
                for p in self.memories.get("trade_patterns", []):
                    self._recent_pattern_keys.add(self._make_pattern_key(p))
                logger.info(f"记忆库加载成功: {sum(len(v) for v in self.memories.values())}条记忆, {len(self._recent_pattern_keys)} dedup keys")
        except Exception as e:
            logger.warning(f"记忆库加载失败: {e}")

    def _save(self):
        try:
            import json
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.memory_file, "w") as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"记忆库保存失败: {e}")

    def _make_pattern_key(self, pattern):
        return (
            f"{pattern.get('symbol','')}_{pattern.get('strategy','')}_"
            f"{pattern.get('direction','')}_"
            f"{float(pattern.get('pnl_pct',0)):.4f}_"
            f"{pattern.get('signal_score',0)}_"
            f"{float(pattern.get('holding_hours',0)):.1f}"
        )

    def rebuild_from_db(self, db_rows):
        self.memories["trade_patterns"] = []
        self._recent_pattern_keys = set()
        added = 0
        for t in db_rows:
            pnl_val = float(t.get("pnl_value", 0) or 0)
            pattern = {
                "timestamp": str(t.get("created_at", "")),
                "symbol": t.get("symbol", ""),
                "strategy": t.get("strategy_type", ""),
                "direction": t.get("direction", ""),
                "result": "win" if pnl_val > 0 else "loss",
                "pnl_pct": float(t.get("pnl_pct", 0) or 0),
                "signal_score": float(t.get("signal_score", 0) or 0),
                "holding_hours": float(t.get("hold_hours", 0) or 0),
                "regime": t.get("regime", "unknown") or "unknown",
                "ml_confidence": float(t.get("ml_confidence", 0) or 0),
                "entry_conditions": {},
                "lesson": "",
            }
            key = self._make_pattern_key(pattern)
            if key not in self._recent_pattern_keys:
                self.memories["trade_patterns"].append(pattern)
                self._recent_pattern_keys.add(key)
                added += 1
        if len(self.memories["trade_patterns"]) > 500:
            self.memories["trade_patterns"] = self.memories["trade_patterns"][-500:]
        self._save()
        logger.info(f"MemoryBank重建完成: {added}条唯一记录")
        return added

    def record_trade_pattern(self, pattern):
        dedup_key = self._make_pattern_key(pattern)
        if not hasattr(self, '_recent_pattern_keys'):
            self._recent_pattern_keys = set()
        if dedup_key in self._recent_pattern_keys:
            return
        self._recent_pattern_keys.add(dedup_key)
        if len(self._recent_pattern_keys) > 500:
            self._recent_pattern_keys = set(list(self._recent_pattern_keys)[-200:])

        entry = {
            "timestamp": datetime.now().isoformat(),
            "symbol": pattern.get("symbol", ""),
            "direction": pattern.get("direction", ""),
            "result": pattern.get("result", ""),
            "pnl_pct": pattern.get("pnl_pct", 0),
            "regime": pattern.get("regime", ""),
            "strategy": pattern.get("strategy", ""),
            "signal_score": pattern.get("signal_score", 0),
            "ml_confidence": pattern.get("ml_confidence", 0),
            "holding_hours": pattern.get("holding_hours", 0),
            "entry_conditions": pattern.get("entry_conditions", {}),
            "lesson": pattern.get("lesson", ""),
        }
        self.memories["trade_patterns"].append(entry)
        self.memories["trade_patterns"] = self.memories["trade_patterns"][-500:]
        self._save()

        try:
            outcome = 1 if pattern.get("pnl_pct", 0) > 0 else -1
            importance = self._calc_importance(pattern)
            TitanDB.update_memory_strength(
                pattern_key=dedup_key,
                outcome=outcome,
                importance=importance,
            )
        except Exception as e:
            logger.debug(f"记忆强度更新异常: {e}")

    def _calc_importance(self, trade_data):
        importance = 1.0
        pnl_abs = abs(trade_data.get("pnl_pct", 0))
        if pnl_abs > 10:
            importance *= 2.0
        elif pnl_abs > 5:
            importance *= 1.5
        fng = trade_data.get("fng_at_entry", 50)
        if fng < 15 or fng > 80:
            importance *= 1.5
        if trade_data.get("holding_hours", 0) > 12:
            importance *= 1.3
        return round(importance, 2)

    def record_regime_change(self, old_regime, new_regime, context=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "from": old_regime,
            "to": new_regime,
            "context": context or {},
        }
        self.memories["regime_history"].append(entry)
        self.memories["regime_history"] = self.memories["regime_history"][-200:]
        self._save()

    def add_insight(self, category, insight, confidence=0.5, source="system"):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "insight": insight,
            "confidence": confidence,
            "source": source,
            "validated": False,
            "validation_count": 0,
        }
        self.memories["insights"].append(entry)
        self.memories["insights"] = self.memories["insights"][-200:]
        self._save()

    def add_rule(self, rule_type, condition, action, performance=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": rule_type,
            "condition": condition,
            "action": action,
            "performance": performance or {},
            "active": True,
            "hit_count": 0,
        }
        self.memories["rules"].append(entry)
        self.memories["rules"] = self.memories["rules"][-100:]
        self._save()

    def record_performance_snapshot(self, snapshot):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "equity": snapshot.get("equity", 0),
            "total_trades": snapshot.get("total_trades", 0),
            "win_rate": snapshot.get("win_rate", 0),
            "sharpe": snapshot.get("sharpe", 0),
            "max_drawdown": snapshot.get("max_drawdown", 0),
            "open_positions": snapshot.get("open_positions", 0),
            "regime": snapshot.get("regime", ""),
        }
        self.memories["performance_snapshots"].append(entry)
        self.memories["performance_snapshots"] = self.memories["performance_snapshots"][-1000:]
        self._save()

    def record_market_event(self, event_type, description, impact=0, data=None):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "description": description,
            "impact": impact,
            "data": data or {},
        }
        self.memories["market_events"].append(entry)
        self.memories["market_events"] = self.memories["market_events"][-300:]
        self._save()

    def get_similar_trades(self, symbol=None, regime=None, direction=None, limit=20):
        patterns = self.memories["trade_patterns"]
        filtered = patterns
        if symbol:
            filtered = [p for p in filtered if p.get("symbol") == symbol]
        if regime:
            filtered = [p for p in filtered if p.get("regime") == regime]
        if direction:
            filtered = [p for p in filtered if p.get("direction") == direction]
        return filtered[-limit:]

    def get_regime_stats(self):
        history = self.memories["regime_history"]
        if not history:
            return {"total_changes": 0, "regimes": {}}
        regime_counts = {}
        for entry in history:
            r = entry.get("to", "unknown")
            regime_counts[r] = regime_counts.get(r, 0) + 1
        return {
            "total_changes": len(history),
            "regimes": regime_counts,
            "last_change": history[-1] if history else None,
        }

    def get_active_rules(self):
        return [r for r in self.memories["rules"] if r.get("active", True)]

    def get_performance_trend(self, days=30):
        snapshots = self.memories["performance_snapshots"]
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        recent = [s for s in snapshots if s.get("timestamp", "") >= cutoff]
        return recent

    def get_advanced_stats(self, days=None):
        patterns = self.memories["trade_patterns"]
        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            patterns = [p for p in patterns if p.get("timestamp", "") >= cutoff]
        if not patterns:
            return {"total": 0, "regime_performance": {}, "symbol_performance": {},
                    "strategy_performance": {}, "holding_analysis": {},
                    "signal_score_buckets": {}, "direction_stats": {}, "time_distribution": {}}

        regime_groups = {}
        symbol_groups = {}
        strategy_groups = {}
        direction_groups = {"long": [], "short": []}
        hour_dist = {str(h): 0 for h in range(24)}

        for p in patterns:
            regime = p.get("regime", "unknown") or "unknown"
            symbol = p.get("symbol", "unknown") or "unknown"
            strategy = p.get("strategy", "unknown") or "unknown"
            direction = p.get("direction", "long")
            pnl = p.get("pnl_pct", 0)

            regime_groups.setdefault(regime, []).append(pnl)
            symbol_groups.setdefault(symbol, []).append(pnl)
            strategy_groups.setdefault(strategy, []).append(pnl)
            if direction in direction_groups:
                direction_groups[direction].append(pnl)

            ts = p.get("timestamp", "")
            if "T" in ts:
                try:
                    hour = ts.split("T")[1][:2]
                    hour_dist[hour] = hour_dist.get(hour, 0) + 1
                except Exception:
                    pass

        def calc_group(pnls):
            if not pnls:
                return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0, "best": 0, "worst": 0}
            wins = sum(1 for p in pnls if p > 0)
            return {
                "trades": len(pnls),
                "win_rate": round(wins / len(pnls) * 100, 1),
                "avg_pnl": round(sum(pnls) / len(pnls), 3),
                "total_pnl": round(sum(pnls), 3),
                "best": round(max(pnls), 3),
                "worst": round(min(pnls), 3),
            }

        holding_hours = [p.get("holding_hours", 0) for p in patterns if p.get("holding_hours")]
        holding_analysis = {}
        if holding_hours:
            short_term = [p for p in patterns if 0 < p.get("holding_hours", 0) <= 4]
            medium_term = [p for p in patterns if 4 < p.get("holding_hours", 0) <= 24]
            long_term = [p for p in patterns if p.get("holding_hours", 0) > 24]
            holding_analysis = {
                "short_0_4h": calc_group([p.get("pnl_pct", 0) for p in short_term]),
                "medium_4_24h": calc_group([p.get("pnl_pct", 0) for p in medium_term]),
                "long_24h_plus": calc_group([p.get("pnl_pct", 0) for p in long_term]),
                "avg_holding": round(sum(holding_hours) / len(holding_hours), 1),
            }

        score_buckets = {"low_0_60": [], "mid_60_80": [], "high_80_100": []}
        for p in patterns:
            sc = p.get("signal_score", 0)
            pnl = p.get("pnl_pct", 0)
            if sc < 60:
                score_buckets["low_0_60"].append(pnl)
            elif sc < 80:
                score_buckets["mid_60_80"].append(pnl)
            else:
                score_buckets["high_80_100"].append(pnl)

        return {
            "total": len(patterns),
            "regime_performance": {k: calc_group(v) for k, v in regime_groups.items()},
            "symbol_performance": {k: calc_group(v) for k, v in sorted(symbol_groups.items(), key=lambda x: sum(x[1]), reverse=True)[:20]},
            "strategy_performance": {k: calc_group(v) for k, v in strategy_groups.items()},
            "holding_analysis": holding_analysis,
            "signal_score_buckets": {k: calc_group(v) for k, v in score_buckets.items()},
            "direction_stats": {k: calc_group(v) for k, v in direction_groups.items()},
            "time_distribution": {k: v for k, v in hour_dist.items() if v > 0},
        }

    def generate_auto_rules(self, min_trades=3):
        patterns = self.memories["trade_patterns"]
        if len(patterns) < min_trades:
            return {"rules_generated": 0, "message": "交易数据不足，至少需要{}笔".format(min_trades)}

        new_rules = []

        regime_groups = {}
        for p in patterns:
            regime = p.get("regime", "unknown") or "unknown"
            regime_groups.setdefault(regime, []).append(p)

        for regime, trades in regime_groups.items():
            if len(trades) < min_trades:
                continue
            losses = [t for t in trades if t.get("pnl_pct", 0) < 0]
            loss_rate = len(losses) / len(trades)
            if loss_rate >= 0.7:
                rule = {
                    "type": "regime_avoid",
                    "condition": f"regime == '{regime}' and loss_rate >= 70%",
                    "action": f"减少{regime}环境下的交易频率，仓位缩减50%",
                    "performance": {"loss_rate": round(loss_rate * 100, 1), "sample_size": len(trades)},
                }
                self.add_rule(rule["type"], rule["condition"], rule["action"], rule["performance"])
                new_rules.append(rule)

        strategy_regime = {}
        for p in patterns:
            key = f"{p.get('strategy', 'unknown')}_{p.get('regime', 'unknown')}"
            strategy_regime.setdefault(key, []).append(p)

        for key, trades in strategy_regime.items():
            if len(trades) < min_trades:
                continue
            avg_pnl = sum(t.get("pnl_pct", 0) for t in trades) / len(trades)
            if avg_pnl < -1.0:
                parts = key.split("_", 1)
                rule = {
                    "type": "strategy_regime_ban",
                    "condition": f"strategy == '{parts[0]}' and regime == '{parts[1]}' and avg_pnl < -1%",
                    "action": f"禁止在{parts[1]}环境使用{parts[0]}策略",
                    "performance": {"avg_pnl": round(avg_pnl, 3), "sample_size": len(trades)},
                }
                self.add_rule(rule["type"], rule["condition"], rule["action"], rule["performance"])
                new_rules.append(rule)

        low_score_losses = [p for p in patterns if p.get("signal_score", 0) < 60 and p.get("pnl_pct", 0) < 0]
        if len(low_score_losses) >= min_trades:
            total_low = [p for p in patterns if p.get("signal_score", 0) < 60]
            if total_low:
                loss_rate = len(low_score_losses) / len(total_low)
                if loss_rate >= 0.65:
                    rule = {
                        "type": "signal_threshold",
                        "condition": f"signal_score < 60 and loss_rate >= 65%",
                        "action": "提高信号评分门槛至65以上，过滤低质量信号",
                        "performance": {"loss_rate": round(loss_rate * 100, 1), "sample_size": len(total_low)},
                    }
                    self.add_rule(rule["type"], rule["condition"], rule["action"], rule["performance"])
                    new_rules.append(rule)

        long_hold_losses = [p for p in patterns if p.get("holding_hours", 0) > 48 and p.get("pnl_pct", 0) < -2]
        if len(long_hold_losses) >= 2:
            rule = {
                "type": "holding_time_limit",
                "condition": "holding_hours > 48 and pnl < -2%",
                "action": "设置最大持仓时间为48小时，超时强制评估",
                "performance": {"sample_size": len(long_hold_losses), "avg_loss": round(sum(t.get("pnl_pct", 0) for t in long_hold_losses) / len(long_hold_losses), 3)},
            }
            self.add_rule(rule["type"], rule["condition"], rule["action"], rule["performance"])
            new_rules.append(rule)

        return {"rules_generated": len(new_rules), "rules": new_rules}

    async def ai_analyze(self, force=False):
        patterns = self.memories["trade_patterns"]
        regime_history = self.memories["regime_history"]
        events = self.memories["market_events"]
        snapshots = self.memories["performance_snapshots"]

        recent_patterns = patterns[-50:]
        recent_regimes = regime_history[-20:]
        recent_events = events[-10:]
        recent_snapshots = snapshots[-10:]

        stats = self.get_advanced_stats(days=30)

        import json
        from server.titan_prompt_library import PHASE_ZERO_CONTEXT
        prompt = PHASE_ZERO_CONTEXT + f"""你是一个专业的量化交易AI分析师。请分析以下记忆库数据并生成深度洞察。

## 交易模式 (最近{len(recent_patterns)}笔)
{json.dumps(recent_patterns[-20:], ensure_ascii=False, indent=1) if recent_patterns else '无数据'}

## 市场环境变化 (最近{len(recent_regimes)}次)
{json.dumps(recent_regimes[-10:], ensure_ascii=False, indent=1) if recent_regimes else '无数据'}

## 统计摘要
- 环境胜率: {json.dumps(stats.get('regime_performance', {}), ensure_ascii=False)}
- 方向统计: {json.dumps(stats.get('direction_stats', {}), ensure_ascii=False)}
- 持仓分析: {json.dumps(stats.get('holding_analysis', {}), ensure_ascii=False)}

## 近期市场事件
{json.dumps(recent_events[-5:], ensure_ascii=False, indent=1) if recent_events else '无数据'}

请返回JSON格式:
{{"insights": [{{"category": "分类(regime/strategy/risk/opportunity)", "insight": "洞察内容(中文,50字内)", "confidence": 0.7, "action": "建议操作(30字内)"}}], "risk_warnings": ["风险提示1", "风险提示2"], "opportunities": ["机会1"], "overall_assessment": "总体评估(100字内)"}}"""

        try:
            from server.titan_llm_client import chat_json
            result = chat_json(
                module="external_data",
                messages=[
                    {"role": "system", "content": EXTERNAL_DATA_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
            )
            if not result:
                raise Exception("AI返回空结果")

            for ins in result.get("insights", []):
                self.add_insight(
                    ins.get("category", "ai"),
                    ins.get("insight", ""),
                    ins.get("confidence", 0.5),
                    source="ai_deep_analysis",
                )

            return {
                "status": "ai_analyzed",
                "insights": result.get("insights", []),
                "risk_warnings": result.get("risk_warnings", []),
                "opportunities": result.get("opportunities", []),
                "overall_assessment": result.get("overall_assessment", ""),
                "stats": stats,
            }
        except Exception as e:
            logger.warning(f"AI记忆分析失败: {e}")
            return {"status": "error", "message": str(e), "stats": stats}

    def get_status(self):
        return {
            "total_memories": sum(len(v) for v in self.memories.values()),
            "trade_patterns": len(self.memories["trade_patterns"]),
            "regime_history": len(self.memories["regime_history"]),
            "insights": len(self.memories["insights"]),
            "rules": len(self.memories["rules"]),
            "performance_snapshots": len(self.memories["performance_snapshots"]),
            "market_events": len(self.memories["market_events"]),
            "active_rules": len(self.get_active_rules()),
            "recent_insights": self.memories["insights"][-5:],
            "recent_events": self.memories["market_events"][-5:],
            "regime_stats": self.get_regime_stats(),
        }


_memory_bank = None

def get_memory_bank():
    global _memory_bank
    if _memory_bank is None:
        _memory_bank = TitanMemoryBank()
    return _memory_bank


class TitanExternalDataManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        return cls._instance

    def __init__(self):
        self.cache = ExternalDataCache()
        self._fetch_count = 0
        self._errors = []
        self.memory_bank = get_memory_bank()
        TitanExternalDataManager._instance = self

    async def refresh_all(self, exchange=None, top_symbols=None):
        self._fetch_count += 1
        refreshed = []

        if self.cache.is_stale("onchain"):
            try:
                data = await asyncio.get_event_loop().run_in_executor(None, TitanOnChainFetcher.fetch)
                self.cache.onchain.update(data)
                refreshed.append("onchain")
            except Exception as e:
                self._errors.append(f"onchain: {e}")
                logger.warning(f"On-chain refresh failed: {e}")

        if self.cache.is_stale("glassnode"):
            try:
                gn = get_glassnode_fetcher()
                signal = await asyncio.get_event_loop().run_in_executor(None, gn.get_comprehensive_signal, "BTC")
                signal["last_updated"] = time.time()
                self.cache.glassnode.update(signal)
                refreshed.append("glassnode")
                logger.info(f"Glassnode信号: {signal['signal']} ({signal['score']}分) | {signal['narrative']}")
            except Exception as e:
                self._errors.append(f"glassnode: {e}")
                logger.warning(f"Glassnode refresh failed: {e}")

        if self.cache.is_stale("sentiment"):
            try:
                data = await asyncio.get_event_loop().run_in_executor(None, TitanSentimentFetcher.fetch)
                self.cache.sentiment.update(data)
                refreshed.append("sentiment")
            except Exception as e:
                self._errors.append(f"sentiment: {e}")
                logger.warning(f"Sentiment refresh failed: {e}")

        if self.cache.is_stale("macro"):
            try:
                data = await asyncio.get_event_loop().run_in_executor(None, TitanMacroFetcher.fetch)
                self.cache.macro.update(data)
                refreshed.append("macro")
            except Exception as e:
                self._errors.append(f"macro: {e}")
                logger.warning(f"Macro refresh failed: {e}")

        if exchange and top_symbols and self.cache.is_stale("orderbook"):
            try:
                data = await TitanOrderBookFetcher.fetch(exchange, top_symbols[:10])
                self.cache.orderbook = data
                self.cache.orderbook["last_updated"] = time.time()
                refreshed.append("orderbook")
            except Exception as e:
                self._errors.append(f"orderbook: {e}")
                logger.warning(f"Order book refresh failed: {e}")

        if self.cache.is_stale("coinglass"):
            try:
                cg = get_coinglass_fetcher()
                data = await asyncio.get_event_loop().run_in_executor(None, cg.fetch_all)
                self.cache.coinglass.update(data)
                refreshed.append("coinglass")
                logger.info(f"CoinGlass信号: {data['signal']} ({data['score']}分) | {data['narrative']}")

                if data.get("score", 0) > 30 or data.get("score", 0) < -30:
                    self.memory_bank.record_market_event(
                        "coinglass_extreme",
                        f"衍生品信号异常: {data['signal']} 得分={data['score']}",
                        impact=abs(data["score"]),
                        data={"oi_change": data.get("btc_oi_change_24h"), "funding": data.get("btc_funding_rate")},
                    )
            except Exception as e:
                self._errors.append(f"coinglass: {e}")
                logger.warning(f"CoinGlass refresh failed: {e}")

        if self.cache.is_stale("news"):
            try:
                cp = get_cryptopanic_fetcher()
                data = await asyncio.get_event_loop().run_in_executor(None, cp.fetch)
                self.cache.news.update(data)
                refreshed.append("news")

                if abs(data.get("sentiment_score", 0)) > 50:
                    self.memory_bank.record_market_event(
                        "news_extreme_sentiment",
                        f"新闻情绪极端: {data['btc_sentiment']} 得分={data['sentiment_score']}",
                        impact=abs(data["sentiment_score"]),
                        data={"alert_count": data.get("alert_count"), "hot_topics": data.get("hot_topics", [])[:5]},
                    )
            except Exception as e:
                self._errors.append(f"news: {e}")
                logger.warning(f"News refresh failed: {e}")

        return refreshed

    def get_snapshot(self):
        return self.cache.get_snapshot()

    def get_ml_features(self, symbol=None):
        return self.cache.get_ml_features(symbol)

    def get_status(self):
        return {
            "fetch_count": self._fetch_count,
            "onchain_age": round(time.time() - self.cache.onchain.get("last_updated", 0)),
            "glassnode_age": round(time.time() - self.cache.glassnode.get("last_updated", 0)),
            "sentiment_age": round(time.time() - self.cache.sentiment.get("last_updated", 0)),
            "macro_age": round(time.time() - self.cache.macro.get("last_updated", 0)),
            "coinglass_age": round(time.time() - self.cache.coinglass.get("last_updated", 0)),
            "news_age": round(time.time() - self.cache.news.get("last_updated", 0)),
            "orderbook_assets": len([k for k in self.cache.orderbook if k != "last_updated"]),
            "recent_errors": self._errors[-5:] if self._errors else [],
            "onchain": self.cache.onchain,
            "glassnode": self.cache.glassnode,
            "sentiment": self.cache.sentiment,
            "macro": self.cache.macro,
            "coinglass": self.cache.coinglass,
            "news": self.cache.news,
            "memory_bank": self.memory_bank.get_status(),
        }
