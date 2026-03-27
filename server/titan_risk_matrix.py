import logging
from datetime import datetime

import numpy as np

logger = logging.getLogger("TitanRisk")

DEFAULT_CONFIG = {
    "max_position_pct": 0.25,
    "max_portfolio_var": 0.05,
    "max_correlation": 0.7,
    "max_net_exposure": 0.6,
    "circuit_breaker_threshold": -0.05,
    "daily_loss_limit": -0.02,
    "decay_sharpe_threshold": 0.2,
    "max_consecutive_losses": 5,
}


class TitanRiskMatrix:
    def __init__(self, config=None):
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self.circuit_breaker_active = False
        self.daily_stop_active = False
        self.last_evaluation = None
        self._warnings_history = []
        self._blocks_history = []
        logger.info("TitanRiskMatrix 三线防御系统初始化完成")

    def check_trade_risk(self, signal):
        result = {"approved": True, "reasons": []}

        stop_loss = signal.get("stop_loss")
        atr = signal.get("atr", 0)
        entry_price = signal.get("entry_price", 0)
        position_pct = signal.get("position_pct", 0)

        if stop_loss is None or stop_loss == 0:
            result["approved"] = False
            result["reasons"].append("止损未设置")
            return result

        if atr > 0 and entry_price > 0:
            stop_distance = abs(entry_price - stop_loss)
            max_stop = 3 * atr
            if stop_distance > max_stop:
                result["approved"] = False
                result["reasons"].append(
                    f"止损距离{stop_distance:.4f}超过3ATR({max_stop:.4f})"
                )

        if position_pct > self.config["max_position_pct"]:
            result["approved"] = False
            result["reasons"].append(
                f"仓位{position_pct:.1%}超过最大允许{self.config['max_position_pct']:.1%}"
            )

        if result["approved"]:
            result["reasons"].append("交易级风控通过")

        return result

    def calc_correlation_matrix(self, positions, price_data):
        symbols = [p.get("symbol") for p in positions if p.get("symbol") in price_data]
        if len(symbols) < 2:
            return np.array([]), symbols

        returns_list = []
        valid_symbols = []
        for sym in symbols:
            prices = np.array(price_data[sym], dtype=float)
            if len(prices) < 31:
                continue
            prices = prices[-31:]
            rets = np.diff(prices) / (prices[:-1] + 1e-10)
            returns_list.append(rets)
            valid_symbols.append(sym)

        if len(valid_symbols) < 2:
            return np.array([]), valid_symbols

        min_len = min(len(r) for r in returns_list)
        returns_matrix = np.array([r[-min_len:] for r in returns_list])
        corr = np.corrcoef(returns_matrix)
        return corr, valid_symbols

    def calc_portfolio_var(self, positions, price_data, confidence=0.95):
        if not positions or not price_data:
            return 0.0

        portfolio_returns = []
        for pos in positions:
            sym = pos.get("symbol")
            size = pos.get("size", 0)
            direction = 1 if pos.get("direction", "long") == "long" else -1
            if sym not in price_data:
                continue
            prices = np.array(price_data[sym], dtype=float)
            if len(prices) < 31:
                continue
            prices = prices[-31:]
            rets = np.diff(prices) / (prices[:-1] + 1e-10)
            weighted = rets * size * direction
            if len(portfolio_returns) == 0:
                portfolio_returns = weighted.copy()
            else:
                min_len = min(len(portfolio_returns), len(weighted))
                portfolio_returns = portfolio_returns[-min_len:] + weighted[-min_len:]

        if len(portfolio_returns) == 0:
            return 0.0

        sorted_returns = np.sort(portfolio_returns)
        idx = int((1 - confidence) * len(sorted_returns))
        idx = max(0, min(idx, len(sorted_returns) - 1))
        var_value = float(-sorted_returns[idx])
        return max(var_value, 0.0)

    def check_net_exposure(self, positions):
        long_exposure = 0.0
        short_exposure = 0.0

        for pos in positions:
            size = abs(pos.get("size", 0))
            if pos.get("direction", "long") == "long":
                long_exposure += size
            else:
                short_exposure += size

        total = long_exposure + short_exposure
        if total == 0:
            return {"net_exposure": 0.0, "exceeded": False, "long": 0.0, "short": 0.0}

        net = (long_exposure - short_exposure) / total
        exceeded = abs(net) > self.config["max_net_exposure"]
        return {
            "net_exposure": round(net, 4),
            "exceeded": exceeded,
            "long": round(long_exposure, 4),
            "short": round(short_exposure, 4),
        }

    def check_correlation_risk(self, new_symbol, positions, price_data):
        result = {"correlated_assets": [], "same_bucket": False, "max_corr": 0.0}

        if new_symbol not in price_data:
            return result

        new_prices = np.array(price_data[new_symbol], dtype=float)
        if len(new_prices) < 31:
            return result
        new_prices = new_prices[-31:]
        new_rets = np.diff(new_prices) / (new_prices[:-1] + 1e-10)

        threshold = self.config["max_correlation"]

        for pos in positions:
            sym = pos.get("symbol")
            if sym == new_symbol or sym not in price_data:
                continue
            prices = np.array(price_data[sym], dtype=float)
            if len(prices) < 31:
                continue
            prices = prices[-31:]
            rets = np.diff(prices) / (prices[:-1] + 1e-10)
            min_len = min(len(new_rets), len(rets))
            if min_len < 5:
                continue
            corr = np.corrcoef(new_rets[-min_len:], rets[-min_len:])[0, 1]
            if not np.isnan(corr) and abs(corr) > threshold:
                result["correlated_assets"].append(
                    {"symbol": sym, "correlation": round(float(corr), 4)}
                )
                if abs(corr) > result["max_corr"]:
                    result["max_corr"] = round(float(abs(corr)), 4)

        result["same_bucket"] = len(result["correlated_assets"]) > 0
        return result

    def check_circuit_breaker(self, btc_data):
        if btc_data is None or len(btc_data) < 2:
            return {"triggered": False, "btc_change": 0.0}

        prices = np.array(btc_data, dtype=float)
        if len(prices) < 2:
            return {"triggered": False, "btc_change": 0.0}

        recent = prices[-1]
        hour_ago = prices[-min(len(prices), 60)]
        change = (recent - hour_ago) / (hour_ago + 1e-10)

        triggered = change <= self.config["circuit_breaker_threshold"]
        if triggered:
            self.circuit_breaker_active = True
            logger.warning(f"熔断触发! BTC 1h变动: {change:.2%}")

        return {"triggered": triggered, "btc_change": round(float(change), 4)}

    def check_daily_loss(self, daily_pnl, limit=None):
        if limit is None:
            limit = self.config["daily_loss_limit"]

        exceeded = daily_pnl <= limit
        if exceeded:
            self.daily_stop_active = True
            logger.warning(f"日亏损触发! PnL: {daily_pnl:.2%}, 限制: {limit:.2%}")

        return {"exceeded": exceeded, "daily_pnl": round(float(daily_pnl), 4), "limit": limit}

    def check_strategy_decay(self, strategy_returns, window=30):
        if strategy_returns is None or len(strategy_returns) < window:
            return {"decayed": False, "sharpe": 0.0, "message": "数据不足"}

        returns = np.array(strategy_returns[-window:], dtype=float)
        mean_ret = np.mean(returns)
        std_ret = np.std(returns)

        if std_ret < 1e-10:
            sharpe = 0.0
        else:
            sharpe = float(mean_ret / std_ret * np.sqrt(252))

        decayed = sharpe < self.config["decay_sharpe_threshold"]
        message = ""
        if decayed:
            message = f"策略衰退警告: 30日Sharpe={sharpe:.2f} < {self.config['decay_sharpe_threshold']}"
            logger.warning(message)

        return {"decayed": decayed, "sharpe": round(sharpe, 4), "message": message}

    def check_consecutive_losses(self, loss_count, max_allowed=None):
        if max_allowed is None:
            max_allowed = self.config["max_consecutive_losses"]

        exceeded = loss_count >= max_allowed
        if exceeded:
            logger.warning(f"连续亏损{loss_count}次, 超过限制{max_allowed}次")

        return {"exceeded": exceeded, "loss_count": loss_count, "max_allowed": max_allowed}

    def evaluate_risk(self, signal, positions, price_data, btc_data, daily_pnl):
        warnings = []
        blocks = []
        risk_score = 0

        trade_check = self.check_trade_risk(signal)
        if not trade_check["approved"]:
            blocks.extend(trade_check["reasons"])
            risk_score += 30

        exposure = self.check_net_exposure(positions)
        if exposure["exceeded"]:
            warnings.append(f"净敞口{exposure['net_exposure']:.2%}超过限制{self.config['max_net_exposure']:.2%}")
            risk_score += 15

        portfolio_var = self.calc_portfolio_var(positions, price_data)
        if portfolio_var > self.config["max_portfolio_var"]:
            warnings.append(f"组合VaR {portfolio_var:.4f}超过限制{self.config['max_portfolio_var']}")
            risk_score += 20

        new_symbol = signal.get("symbol", "")
        corr_check = self.check_correlation_risk(new_symbol, positions, price_data)
        correlation_alert = corr_check["same_bucket"]
        if correlation_alert:
            corr_assets = ", ".join(
                [f"{a['symbol']}({a['correlation']:.2f})" for a in corr_check["correlated_assets"]]
            )
            warnings.append(f"相关性风险: {new_symbol}与{corr_assets}高度相关")
            risk_score += 10

        cb = self.check_circuit_breaker(btc_data)
        circuit_breaker = cb["triggered"]
        if circuit_breaker:
            blocks.append(f"BTC熔断触发, 1h变动{cb['btc_change']:.2%}")
            risk_score += 30

        dl = self.check_daily_loss(daily_pnl)
        if dl["exceeded"]:
            blocks.append(f"日亏损{dl['daily_pnl']:.2%}超过限制{dl['limit']:.2%}")
            risk_score += 25

        loss_count = signal.get("consecutive_losses", 0)
        cl = self.check_consecutive_losses(loss_count)
        if cl["exceeded"]:
            blocks.append(f"连续亏损{cl['loss_count']}次")
            risk_score += 20

        strategy_returns = signal.get("strategy_returns")
        if strategy_returns is not None:
            decay = self.check_strategy_decay(strategy_returns)
            if decay["decayed"]:
                warnings.append(decay["message"])
                risk_score += 10

        try:
            from server.titan_portfolio_analyst import portfolio_correlation_analyst
            equity = signal.get("equity", 100000)
            ptc = portfolio_correlation_analyst.pre_trade_check(new_symbol, positions, price_data, equity)
            if ptc.get("warnings"):
                for w in ptc["warnings"]:
                    if w not in warnings:
                        warnings.append(w)
            risk_score += ptc.get("risk_score", 0) // 3
        except Exception as e:
            logger.debug(f"Portfolio pre-trade check跳过: {e}")

        risk_score = min(risk_score, 100)
        approved = len(blocks) == 0 and risk_score < 60

        report = {
            "approved": approved,
            "risk_score": risk_score,
            "warnings": warnings,
            "blocks": blocks,
            "portfolio_var": round(portfolio_var, 6),
            "correlation_alert": correlation_alert,
            "circuit_breaker": circuit_breaker,
        }

        self.last_evaluation = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "report": report,
        }
        self._warnings_history = (self._warnings_history + warnings)[-50:]
        self._blocks_history = (self._blocks_history + blocks)[-50:]

        if not approved:
            logger.info(f"风控拦截: score={risk_score}, blocks={blocks}")
        return report

    def get_status(self):
        return {
            "config": dict(self.config),
            "circuit_breaker_active": self.circuit_breaker_active,
            "daily_stop_active": self.daily_stop_active,
            "last_evaluation": self.last_evaluation,
            "recent_warnings": self._warnings_history[-10:],
            "recent_blocks": self._blocks_history[-10:],
        }


risk_matrix = TitanRiskMatrix()
