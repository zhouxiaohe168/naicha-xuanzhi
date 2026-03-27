import logging
import time
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("TitanPortfolioAnalyst")

SECTOR_MAP = {
    "BTC生态": {"BTC", "ETH", "SOL", "BNB", "DOT", "ATOM", "AVAX", "SUI", "NEAR", "APT", "ADA", "TON", "XRP", "HBAR", "LTC", "TRX"},
    "DeFi": {"UNI", "AAVE", "CRV", "CVX", "CAKE", "LDO", "PENDLE", "ENA", "MKR", "KNC", "BNT", "RPL", "JUP"},
    "AI": {"FET", "TAO", "RNDR", "WLD", "AKT", "AGIX", "GLM"},
    "L2": {"OP", "ARB", "STRK", "ZK", "METIS", "MANTA", "MNT", "POL"},
    "Meme": {"DOGE", "SHIB", "PEPE", "BONK", "FLOKI", "WIF", "BRETT", "POPCAT", "MOODENG", "GOAT", "PNUT"},
    "存储/基础设施": {"FIL", "AR", "HNT", "THETA", "JASMY", "ICP"},
    "GameFi": {"IMX", "AXS", "SAND", "MANA", "BEAM", "GALA", "CHZ", "MASK"},
}


def _get_symbol_sector(symbol: str) -> str:
    base = symbol.replace("/USDT", "").replace("_USDT", "").replace("USDT", "").upper()
    for sector, assets in SECTOR_MAP.items():
        if base in assets:
            return sector
    return "其他"


class PortfolioCorrelationAnalyst:

    def __init__(self):
        self.last_result = None
        self.last_run_time = 0

    def _get_risk_matrix(self):
        try:
            from server.titan_risk_matrix import TitanRiskMatrix
            return TitanRiskMatrix()
        except Exception:
            return None

    def analyze(self, positions: List[Dict], price_data: Dict, equity: float = 100000) -> Dict:
        if len(positions) < 1:
            return {
                "status": "no_positions",
                "correlation_risk": "low",
                "net_exposure_pct": 0,
                "risk_score": 0,
            }

        rm = self._get_risk_matrix()

        if rm:
            exposure = rm.check_net_exposure(positions)
            long_exposure = exposure.get("long", 0.0)
            short_exposure = exposure.get("short", 0.0)
            net_exposure_ratio = abs(exposure.get("net_exposure", 0.0))
        else:
            long_exposure = 0.0
            short_exposure = 0.0
            for pos in positions:
                val = abs(pos.get("position_value", pos.get("remaining_value", pos.get("size", 0))))
                if pos.get("direction", "long") == "long":
                    long_exposure += val
                else:
                    short_exposure += val
            total = long_exposure + short_exposure
            net_exposure_ratio = abs(long_exposure - short_exposure) / total if total > 0 else 0

        net_exposure_pct = round(net_exposure_ratio * 100, 1) if net_exposure_ratio <= 1.0 else round(abs(long_exposure - short_exposure) / equity * 100, 1)

        if rm:
            corr_matrix, valid_symbols = rm.calc_correlation_matrix(positions, price_data)
        else:
            corr_matrix, valid_symbols = np.array([]), []

        concentrated_pairs = []
        max_corr = 0.0
        matrix_data = None

        if len(valid_symbols) >= 2 and corr_matrix.size > 0:
            matrix_rows = []
            for i in range(len(valid_symbols)):
                row = []
                for j in range(len(valid_symbols)):
                    c = float(corr_matrix[i, j])
                    row.append(round(c, 3) if not np.isnan(c) else 0.0)
                matrix_rows.append(row)
            matrix_data = {
                "symbols": valid_symbols,
                "matrix": matrix_rows,
            }

            for i in range(len(valid_symbols)):
                for j in range(i + 1, len(valid_symbols)):
                    c = float(corr_matrix[i, j])
                    if not np.isnan(c):
                        if abs(c) > max_corr:
                            max_corr = abs(c)
                        if abs(c) > 0.5:
                            concentrated_pairs.append({
                                "pair": f"{valid_symbols[i]}-{valid_symbols[j]}",
                                "correlation": round(c, 3),
                            })

        concentrated_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        sector_concentration = {}
        sector_warnings = []
        for pos in positions:
            sym = pos.get("symbol", "").replace("/USDT", "").replace("_USDT", "")
            sector = _get_symbol_sector(sym)
            if sector not in sector_concentration:
                sector_concentration[sector] = []
            sector_concentration[sector].append(sym)

        for sector, syms in sector_concentration.items():
            if len(syms) > 2:
                sector_warnings.append(f"{sector}板块持仓{len(syms)}个({','.join(syms)})，过度集中")

        if max_corr > 0.8 or net_exposure_pct > 50:
            correlation_risk = "high"
        elif max_corr > 0.5 or net_exposure_pct > 30:
            correlation_risk = "medium"
        else:
            correlation_risk = "low"

        risk_score = 0
        if max_corr > 0.8:
            risk_score += 40
        elif max_corr > 0.5:
            risk_score += 20
        if net_exposure_pct > 50:
            risk_score += 30
        elif net_exposure_pct > 30:
            risk_score += 15
        if sector_warnings:
            risk_score += 15 * len(sector_warnings)
        risk_score = min(100, risk_score)

        rule_result = {
            "correlation_risk": correlation_risk,
            "net_exposure_pct": net_exposure_pct,
            "long_exposure_usd": round(long_exposure, 2),
            "short_exposure_usd": round(short_exposure, 2),
            "concentrated_pairs": concentrated_pairs[:10],
            "correlation_matrix": matrix_data,
            "sector_concentration": sector_concentration,
            "sector_warnings": sector_warnings,
            "max_correlation": round(max_corr, 3),
            "risk_score": risk_score,
            "position_count": len(positions),
            "timestamp": datetime.now().isoformat(),
        }

        ai_analysis = None
        if len(positions) >= 2:
            ai_analysis = self._ai_analyze(rule_result)

        if ai_analysis:
            rule_result["recommendation"] = ai_analysis.get("recommendation", "")
            rule_result["max_add_direction"] = ai_analysis.get("max_add_direction", "either")
            if ai_analysis.get("correlation_risk"):
                ai_risk = ai_analysis["correlation_risk"]
                if ai_risk == "high" and rule_result["correlation_risk"] != "high":
                    rule_result["correlation_risk"] = "high"
                    rule_result["risk_score"] = max(rule_result["risk_score"], 60)
        else:
            if net_exposure_pct > 50:
                rule_result["recommendation"] = f"净暴露{net_exposure_pct}%过高，建议减少{'做多' if long_exposure > short_exposure else '做空'}方向仓位"
            elif sector_warnings:
                rule_result["recommendation"] = "; ".join(sector_warnings)
            else:
                rule_result["recommendation"] = "组合风险可控"
            rule_result["max_add_direction"] = "short" if long_exposure > short_exposure * 2 else "either"

        rule_result["source"] = "ai" if ai_analysis else "rule_based"
        self.last_result = rule_result
        self.last_run_time = time.time()
        return rule_result

    def pre_trade_check(self, new_symbol: str, positions: List[Dict], price_data: Dict, equity: float = 100000) -> Dict:
        if not positions:
            return {"approved": True, "warnings": [], "risk_score": 0}

        warnings = []
        risk_score = 0

        rm = self._get_risk_matrix()
        if rm:
            corr_check = rm.check_correlation_risk(new_symbol, positions, price_data)
            if corr_check.get("same_bucket"):
                corr_assets = ", ".join(
                    [f"{a['symbol']}({a['correlation']:.2f})" for a in corr_check.get("correlated_assets", [])]
                )
                warnings.append(f"相关性风险: {new_symbol}与{corr_assets}高度相关")
                risk_score += 20

            exposure = rm.check_net_exposure(positions)
            if exposure.get("exceeded"):
                warnings.append(f"净敞口{exposure['net_exposure']:.2%}超过限制")
                risk_score += 15

        new_sector = _get_symbol_sector(new_symbol)
        same_sector_count = 0
        for pos in positions:
            sym = pos.get("symbol", "").replace("/USDT", "").replace("_USDT", "")
            if _get_symbol_sector(sym) == new_sector:
                same_sector_count += 1
        if same_sector_count >= 2:
            warnings.append(f"{new_sector}板块已有{same_sector_count}个持仓，新增{new_symbol}将过度集中")
            risk_score += 15

        risk_score = min(100, risk_score)
        return {
            "approved": risk_score < 50,
            "warnings": warnings,
            "risk_score": risk_score,
            "sector": new_sector,
            "same_sector_count": same_sector_count,
        }

    def _ai_analyze(self, rule_result: Dict) -> Optional[Dict]:
        try:
            from server.titan_llm_client import chat_json
            from server.titan_prompt_library import PORTFOLIO_CORRELATION_PROMPT, PHASE_ZERO_CONTEXT

            prompt = PHASE_ZERO_CONTEXT + f"""当前投资组合相关性分析数据：

持仓数量: {rule_result['position_count']}
做多暴露: ${rule_result['long_exposure_usd']}
做空暴露: ${rule_result['short_exposure_usd']}
净暴露: {rule_result['net_exposure_pct']}%
最大相关系数: {rule_result['max_correlation']}
高相关对: {rule_result['concentrated_pairs'][:5]}
板块集中: {rule_result['sector_concentration']}
板块警告: {rule_result['sector_warnings']}
规则风险评分: {rule_result['risk_score']}

请基于以上数据给出你的风险评估和建议。"""

            result = chat_json(
                module="portfolio_correlation",
                messages=[
                    {"role": "system", "content": PORTFOLIO_CORRELATION_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
            )
            return result
        except Exception as e:
            logger.warning(f"PortfolioCorrelation AI分析失败: {e}")
            return None

    def get_status(self):
        return {
            "last_result": self.last_result,
            "last_run_time": self.last_run_time,
        }


class RegimeTransitionDetector:

    def __init__(self):
        self.last_result = None
        self.last_run_time = 0
        self.history = []

    def detect(self, market_data: Dict) -> Dict:
        current_regime = market_data.get("regime", "unknown")
        btc_price = market_data.get("btc_price", 0)
        fng = market_data.get("fng", 50)
        fng_prev = market_data.get("fng_prev", fng)
        btc_vol_1h = market_data.get("btc_vol_1h", 0)
        btc_vol_7d_avg = market_data.get("btc_vol_7d_avg", 0)
        volume_ratio = market_data.get("volume_ratio", 1.0)
        recent_stop_losses = market_data.get("recent_stop_losses", 0)
        high_score_signals = market_data.get("high_score_signals", 0)

        signals = {}

        vol_accel = 0.0
        if btc_vol_7d_avg > 0:
            vol_accel = btc_vol_1h / btc_vol_7d_avg
        signals["volatility_acceleration"] = min(1.0, max(0.0, (vol_accel - 1.0) / 2.0))

        fng_change = abs(fng - fng_prev)
        signals["fng_momentum"] = min(1.0, fng_change / 20.0)

        signals["volume_anomaly"] = min(1.0, max(0.0, (volume_ratio - 1.0) / 3.0))

        sl_signal = min(1.0, recent_stop_losses / 3.0)
        signals["stop_loss_cluster"] = sl_signal

        transition_risk = "low"
        most_likely_next = current_regime
        probability = 0.1
        estimated_hours = 24

        if current_regime == "trending":
            danger = (signals["volatility_acceleration"] * 0.4 +
                      signals["fng_momentum"] * 0.25 +
                      signals["volume_anomaly"] * 0.2 +
                      signals["stop_loss_cluster"] * 0.15)
            if danger > 0.6:
                transition_risk = "high"
                most_likely_next = "volatile"
                probability = min(0.9, danger)
                estimated_hours = max(2, int(12 * (1 - danger)))
            elif danger > 0.3:
                transition_risk = "medium"
                most_likely_next = "volatile"
                probability = danger
                estimated_hours = max(6, int(24 * (1 - danger)))

        elif current_regime == "volatile":
            recovery = 0.0
            if fng > fng_prev and fng > 25:
                recovery += 0.3
            if signals["volatility_acceleration"] < 0.2:
                recovery += 0.3
            if high_score_signals > 3:
                recovery += 0.2
            if signals["stop_loss_cluster"] < 0.1:
                recovery += 0.2

            if recovery > 0.6:
                transition_risk = "medium"
                most_likely_next = "ranging"
                probability = min(0.8, recovery)
                estimated_hours = max(6, int(24 * (1 - recovery)))
            elif recovery > 0.3:
                transition_risk = "low"
                most_likely_next = "ranging"
                probability = recovery * 0.5
                estimated_hours = 24

        elif current_regime == "ranging":
            breakout = 0.0
            if signals["volume_anomaly"] > 0.5:
                breakout += 0.35
            if fng > 30 and fng > fng_prev + 5:
                breakout += 0.25
            if signals["volatility_acceleration"] > 0.3:
                breakout += 0.2
            if high_score_signals > 5:
                breakout += 0.2

            if breakout > 0.6:
                transition_risk = "medium"
                most_likely_next = "trending"
                probability = min(0.8, breakout)
                estimated_hours = max(4, int(18 * (1 - breakout)))
            elif breakout > 0.3:
                transition_risk = "low"
                most_likely_next = "trending"
                probability = breakout * 0.5
                estimated_hours = 18

        risk_score = 0
        if transition_risk == "high":
            risk_score = max(60, int(probability * 100))
        elif transition_risk == "medium":
            risk_score = max(30, int(probability * 80))
        else:
            risk_score = int(probability * 50)

        key_signals = []
        if signals["volatility_acceleration"] > 0.3:
            key_signals.append(f"BTC波动率加速{vol_accel:.1f}x(7日均值)")
        if signals["fng_momentum"] > 0.3:
            key_signals.append(f"FNG变化{fng_change}点({fng_prev}→{fng})")
        if signals["volume_anomaly"] > 0.3:
            key_signals.append(f"成交量异常{volume_ratio:.1f}x")
        if signals["stop_loss_cluster"] > 0.3:
            key_signals.append(f"近期{recent_stop_losses}笔止损触发")

        rule_result = {
            "current_regime": current_regime,
            "transition_risk": transition_risk,
            "most_likely_next": most_likely_next,
            "probability": round(probability, 2),
            "key_signals": key_signals,
            "estimated_hours": estimated_hours,
            "signal_strength": {k: round(v, 3) for k, v in signals.items()},
            "risk_score": risk_score,
            "timestamp": datetime.now().isoformat(),
        }

        ai_analysis = None
        if transition_risk in ("medium", "high"):
            ai_analysis = self._ai_analyze(rule_result, market_data)

        if ai_analysis:
            rule_result["recommendation"] = ai_analysis.get("recommendation", "")
            if ai_analysis.get("transition_risk") == "high" and rule_result["transition_risk"] != "high":
                rule_result["transition_risk"] = "high"
                rule_result["risk_score"] = max(rule_result["risk_score"], 60)
            if ai_analysis.get("key_signals"):
                for sig in ai_analysis["key_signals"]:
                    if sig not in rule_result["key_signals"]:
                        rule_result["key_signals"].append(sig)
        else:
            if transition_risk == "high":
                rule_result["recommendation"] = f"高风险预警: {current_regime}→{most_likely_next}切换概率{probability*100:.0f}%，建议收紧止损、减少新开仓"
            elif transition_risk == "medium":
                rule_result["recommendation"] = f"中风险预警: 关注{most_likely_next}切换信号，建议保持警惕"
            else:
                rule_result["recommendation"] = "市场状态稳定，无明显切换信号"

        rule_result["source"] = "ai" if ai_analysis else "rule_based"
        self.last_result = rule_result
        self.last_run_time = time.time()
        self.history.append(rule_result)
        self.history = self.history[-50:]
        return rule_result

    def _ai_analyze(self, rule_result: Dict, market_data: Dict) -> Optional[Dict]:
        try:
            from server.titan_llm_client import chat_json
            from server.titan_prompt_library import REGIME_TRANSITION_PROMPT, PHASE_ZERO_CONTEXT

            prompt = PHASE_ZERO_CONTEXT + f"""当前市场状态切换检测数据：

当前Regime: {rule_result['current_regime']}
规则检测结果:
- 切换风险: {rule_result['transition_risk']}
- 最可能切换到: {rule_result['most_likely_next']}
- 切换概率: {rule_result['probability']*100:.0f}%
- 预计切换时间: {rule_result['estimated_hours']}小时
- 关键信号: {rule_result['key_signals']}

信号强度:
- 波动率加速: {rule_result['signal_strength'].get('volatility_acceleration', 0)}
- FNG动量: {rule_result['signal_strength'].get('fng_momentum', 0)}
- 成交量异常: {rule_result['signal_strength'].get('volume_anomaly', 0)}
- 止损集群: {rule_result['signal_strength'].get('stop_loss_cluster', 0)}

市场数据:
- BTC价格: ${market_data.get('btc_price', 0)}
- FNG: {market_data.get('fng', 50)}
- 活跃持仓: {market_data.get('active_positions', 0)}

请评估切换风险并给出建议。"""

            result = chat_json(
                module="regime_transition",
                messages=[
                    {"role": "system", "content": REGIME_TRANSITION_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=600,
            )
            return result
        except Exception as e:
            logger.warning(f"RegimeTransition AI分析失败: {e}")
            return None

    def get_status(self):
        return {
            "last_result": self.last_result,
            "last_run_time": self.last_run_time,
            "history_count": len(self.history),
        }


portfolio_correlation_analyst = PortfolioCorrelationAnalyst()
regime_transition_detector = RegimeTransitionDetector()
