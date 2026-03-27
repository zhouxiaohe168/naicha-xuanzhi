import os
import json
import time
import logging
from datetime import datetime
from collections import defaultdict
from server.titan_prompt_library import SYNAPSE_PROMPT, PHASE_ZERO_CONTEXT
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanSynapse")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNAPSE_PATH = os.path.join(BASE_DIR, "data", "titan_synapse.json")


class TitanSynapse:
    def __init__(self):
        self.knowledge_base = {
            "asset_insights": {},
            "regime_insights": {},
            "timing_insights": {},
            "correlation_map": {},
        }
        self.broadcast_log = []
        self.cross_strategy_rules = []
        self.strategy_performance = {
            "trend": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best_regimes": {}, "worst_assets": {}},
            "range": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best_regimes": {}, "worst_assets": {}},
            "grid": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best_regimes": {}, "worst_assets": {}},
        }
        self.signal_correlations = []
        self.stats = {"total_broadcasts": 0, "rules_generated": 0, "last_sync": ""}
        self._last_ai_insights = None
        self._load()

    def _load(self):
        try:
            if os.path.exists(SYNAPSE_PATH):
                with open(SYNAPSE_PATH, "r") as f:
                    data = json.load(f)
                self.knowledge_base = data.get("knowledge_base", self.knowledge_base)
                self.broadcast_log = data.get("broadcast_log", [])
                self.cross_strategy_rules = data.get("cross_strategy_rules", [])
                self.strategy_performance = data.get("strategy_performance", self.strategy_performance)
                self.stats = data.get("stats", self.stats)
                self._recent_broadcasts = set()
                for entry in self.broadcast_log:
                    self._recent_broadcasts.add(self._make_broadcast_key(entry))
                logger.info(f"Synapse loaded: {self.stats['total_broadcasts']} broadcasts, {len(self.cross_strategy_rules)} rules, {len(self._recent_broadcasts)} dedup keys")
        except Exception as e:
            logger.warning(f"Synapse load failed: {e}")

    def save(self):
        try:
            data = {
                "knowledge_base": self.knowledge_base,
                "broadcast_log": self.broadcast_log[-500:],
                "cross_strategy_rules": self.cross_strategy_rules[-100:],
                "strategy_performance": self.strategy_performance,
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            atomic_json_save(SYNAPSE_PATH, data)
        except Exception as e:
            logger.error(f"Synapse save failed: {e}")

    def _make_broadcast_key(self, entry):
        sym = entry.get("symbol", "")
        strat = entry.get("strategy", entry.get("strategy_type", ""))
        d = entry.get("direction", "")
        pnl = float(entry.get("pnl", entry.get("pnl_pct", 0)) or 0)
        score = entry.get("signal_score", 0)
        hrs = float(entry.get("holding_hours", 0) or 0)
        return f"{sym}_{strat}_{d}_{pnl:.4f}_{score}_{hrs:.1f}"

    def rebuild_from_db(self, db_rows):
        self.broadcast_log = []
        self.cross_strategy_rules = []
        self.knowledge_base = {"asset_insights": {}, "regime_insights": {}, "timing_insights": {}}
        self.strategy_performance = {
            "trend": {"wins": 0, "losses": 0, "total_pnl": 0, "best_regimes": {}, "worst_assets": {}},
            "range": {"wins": 0, "losses": 0, "total_pnl": 0, "best_regimes": {}, "worst_assets": {}},
            "grid": {"wins": 0, "losses": 0, "total_pnl": 0, "best_regimes": {}, "worst_assets": {}},
        }
        self._recent_broadcasts = set()
        self.stats = {"total_broadcasts": 0, "rules_generated": 0, "last_sync": ""}
        for t in db_rows:
            trade_info = {
                "symbol": t.get("symbol", ""),
                "strategy_type": t.get("strategy_type", "trend"),
                "pnl_pct": float(t.get("pnl_pct", 0) or 0),
                "market_regime": t.get("regime", "unknown") or "unknown",
                "direction": t.get("direction", "long"),
                "signal_score": float(t.get("signal_score", 0) or 0),
                "holding_hours": float(t.get("hold_hours", 0) or 0),
            }
            self.broadcast_trade_result(trade_info)
        self.save()
        logger.info(f"Synapse重建完成: {self.stats['total_broadcasts']}条广播, {len(self.cross_strategy_rules)}条规则")
        return self.stats["total_broadcasts"]

    def broadcast_trade_result(self, trade_info):
        symbol = trade_info.get("symbol", "UNKNOWN")
        strategy = trade_info.get("strategy_type", "trend")
        pnl = trade_info.get("pnl_pct", 0)
        regime = trade_info.get("market_regime", "unknown")
        direction = trade_info.get("direction", "long")
        signal_score = trade_info.get("signal_score", 0)
        holding_hours = trade_info.get("holding_hours", 0)

        dedup_key = self._make_broadcast_key({
            "symbol": symbol, "strategy": strategy, "direction": direction,
            "pnl": pnl, "signal_score": signal_score, "holding_hours": holding_hours,
        })
        if not hasattr(self, '_recent_broadcasts'):
            self._recent_broadcasts = set()
        if dedup_key in self._recent_broadcasts:
            return
        self._recent_broadcasts.add(dedup_key)
        if len(self._recent_broadcasts) > 500:
            self._recent_broadcasts = set(list(self._recent_broadcasts)[-200:])

        is_win = pnl > 0

        if strategy in self.strategy_performance:
            sp = self.strategy_performance[strategy]
            if is_win:
                sp["wins"] += 1
            else:
                sp["losses"] += 1
            sp["total_pnl"] = round(sp["total_pnl"] + pnl, 4)

            if regime not in sp["best_regimes"]:
                sp["best_regimes"][regime] = {"wins": 0, "losses": 0, "pnl": 0}
            rg = sp["best_regimes"][regime]
            rg["wins" if is_win else "losses"] += 1
            rg["pnl"] = round(rg["pnl"] + pnl, 4)

            base_symbol = symbol.replace("/USDT", "").replace("_USDT", "")
            if not is_win:
                if base_symbol not in sp["worst_assets"]:
                    sp["worst_assets"][base_symbol] = 0
                sp["worst_assets"][base_symbol] += 1

        asset_key = symbol.replace("/USDT", "").replace("_USDT", "")
        if asset_key not in self.knowledge_base["asset_insights"]:
            self.knowledge_base["asset_insights"][asset_key] = {
                "total_trades": 0, "wins": 0, "total_pnl": 0,
                "best_strategy": None, "by_strategy": {},
            }
        ai = self.knowledge_base["asset_insights"][asset_key]
        ai["total_trades"] += 1
        if is_win:
            ai["wins"] += 1
        ai["total_pnl"] = round(ai["total_pnl"] + pnl, 4)
        if strategy not in ai["by_strategy"]:
            ai["by_strategy"][strategy] = {"wins": 0, "losses": 0, "pnl": 0}
        bs = ai["by_strategy"][strategy]
        bs["wins" if is_win else "losses"] += 1
        bs["pnl"] = round(bs["pnl"] + pnl, 4)

        best_s = None
        best_wr = 0
        for s, stats in ai["by_strategy"].items():
            total = stats["wins"] + stats["losses"]
            if total >= 3:
                wr = stats["wins"] / total
                if wr > best_wr:
                    best_wr = wr
                    best_s = s
        ai["best_strategy"] = best_s

        if regime != "unknown":
            if regime not in self.knowledge_base["regime_insights"]:
                self.knowledge_base["regime_insights"][regime] = {
                    "total_trades": 0, "wins": 0, "best_strategy": None, "by_strategy": {},
                }
            ri = self.knowledge_base["regime_insights"][regime]
            ri["total_trades"] += 1
            if is_win:
                ri["wins"] += 1
            if strategy not in ri["by_strategy"]:
                ri["by_strategy"][strategy] = {"wins": 0, "losses": 0, "pnl": 0}
            rs = ri["by_strategy"][strategy]
            rs["wins" if is_win else "losses"] += 1
            rs["pnl"] = round(rs["pnl"] + pnl, 4)

            best_rs = None
            best_rwr = 0
            for s, stats in ri["by_strategy"].items():
                total = stats["wins"] + stats["losses"]
                if total >= 3:
                    wr = stats["wins"] / total
                    if wr > best_rwr:
                        best_rwr = wr
                        best_rs = s
            ri["best_strategy"] = best_rs

        hour = datetime.now().hour
        session = "asia" if 1 <= hour < 9 else "europe" if 9 <= hour < 17 else "us"
        if session not in self.knowledge_base["timing_insights"]:
            self.knowledge_base["timing_insights"][session] = {
                "total": 0, "wins": 0, "by_strategy": {},
            }
        ti = self.knowledge_base["timing_insights"][session]
        ti["total"] += 1
        if is_win:
            ti["wins"] += 1
        if strategy not in ti["by_strategy"]:
            ti["by_strategy"][strategy] = {"wins": 0, "losses": 0}
        ti["by_strategy"][strategy]["wins" if is_win else "losses"] += 1

        broadcast = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "strategy": strategy,
            "pnl": pnl,
            "regime": regime,
            "direction": direction,
            "signal_score": signal_score,
            "holding_hours": holding_hours,
        }
        self.broadcast_log.append(broadcast)
        self.stats["total_broadcasts"] += 1

        self._generate_cross_rules()
        self.stats["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save()

    def _generate_cross_rules(self):
        new_rules = []

        for asset, info in self.knowledge_base["asset_insights"].items():
            import re as _re
            if not _re.match(r'^[A-Z0-9]{2,15}$', asset):
                continue
            real_trades = info.get("real_trade_count", info["total_trades"])
            if real_trades >= 3:
                wr = info["wins"] / max(1, real_trades)
                if wr == 0 and real_trades >= 3:
                    rule = {
                        "type": "asset_avoid",
                        "asset": asset,
                        "win_rate": 0.0,
                        "trades": real_trades,
                        "applies_to": "all",
                        "reason": f"{asset} 跨策略胜率仅0.0%，所有策略应回避",
                    }
                    if not any(r.get("asset") == asset and r.get("type") == "asset_avoid" for r in self.cross_strategy_rules):
                        new_rules.append(rule)

                if info["best_strategy"] and info["total_trades"] >= 8:
                    best = info["best_strategy"]
                    best_stats = info["by_strategy"].get(best, {})
                    bt = best_stats.get("wins", 0) + best_stats.get("losses", 0)
                    if bt >= 3:
                        bwr = best_stats["wins"] / bt
                        if bwr > 0.6:
                            rule = {
                                "type": "asset_prefer_strategy",
                                "asset": asset,
                                "preferred_strategy": best,
                                "win_rate": round(bwr * 100, 1),
                                "reason": f"{asset} 在{best}策略下胜率{round(bwr*100,1)}%最优",
                            }
                            existing = [r for r in self.cross_strategy_rules
                                       if r.get("type") == "asset_prefer_strategy" and r.get("asset") == asset]
                            if not existing:
                                new_rules.append(rule)

        for regime, info in self.knowledge_base["regime_insights"].items():
            if info["total_trades"] >= 10 and info["best_strategy"]:
                best = info["best_strategy"]
                best_stats = info["by_strategy"].get(best, {})
                bt = best_stats.get("wins", 0) + best_stats.get("losses", 0)
                if bt >= 5:
                    bwr = best_stats["wins"] / bt
                    if bwr > 0.55:
                        rule = {
                            "type": "regime_best_strategy",
                            "regime": regime,
                            "best_strategy": best,
                            "win_rate": round(bwr * 100, 1),
                            "reason": f"{regime}市况下{best}策略表现最佳(胜率{round(bwr*100,1)}%)",
                        }
                        existing = [r for r in self.cross_strategy_rules
                                   if r.get("type") == "regime_best_strategy" and r.get("regime") == regime]
                        if not existing:
                            new_rules.append(rule)

        for strategy, perf in self.strategy_performance.items():
            for asset, loss_count in perf.get("worst_assets", {}).items():
                if loss_count >= 3:
                    rule = {
                        "type": "strategy_asset_ban",
                        "strategy": strategy,
                        "asset": asset,
                        "consecutive_losses": loss_count,
                        "reason": f"{strategy}策略在{asset}上连续亏损{loss_count}次，暂停该组合",
                    }
                    existing = [r for r in self.cross_strategy_rules
                               if r.get("type") == "strategy_asset_ban"
                               and r.get("strategy") == strategy and r.get("asset") == asset]
                    if not existing:
                        new_rules.append(rule)

        if new_rules:
            self.cross_strategy_rules.extend(new_rules)
            self.stats["rules_generated"] += len(new_rules)
            logger.info(f"Synapse: 生成{len(new_rules)}条跨策略规则")

    def should_trade(self, symbol, strategy, regime="unknown"):
        asset = symbol.replace("/USDT", "").replace("_USDT", "")
        for rule in self.cross_strategy_rules:
            rtype = rule.get("type")
            if rtype == "asset_avoid" and rule.get("asset") == asset:
                return False, rule["reason"]
            if rtype == "strategy_asset_ban" and rule.get("strategy") == strategy and rule.get("asset") == asset:
                return False, rule["reason"]

        return True, "OK"

    def get_preferred_strategy(self, symbol, regime="unknown"):
        asset = symbol.replace("/USDT", "").replace("_USDT", "")
        for rule in self.cross_strategy_rules:
            if rule.get("type") == "asset_prefer_strategy" and rule.get("asset") == asset:
                return rule["preferred_strategy"]
            if rule.get("type") == "regime_best_strategy" and rule.get("regime") == regime:
                return rule["best_strategy"]
        return None

    def get_regime_allocation_advice(self, regime):
        ri = self.knowledge_base["regime_insights"].get(regime, {})
        if not ri or ri.get("total_trades", 0) < 10:
            return None

        advice = {}
        total_by_strategy = {}
        for s, stats in ri.get("by_strategy", {}).items():
            total = stats.get("wins", 0) + stats.get("losses", 0)
            if total >= 3:
                wr = stats["wins"] / total
                total_by_strategy[s] = {"wr": wr, "total": total}

        if not total_by_strategy:
            return None

        total_wr = sum(v["wr"] for v in total_by_strategy.values())
        if total_wr > 0:
            for s, v in total_by_strategy.items():
                advice[s] = round(v["wr"] / total_wr, 3)

        return advice

    def ai_cross_strategy_insights(self):
        try:
            from server.titan_llm_client import chat_json
            strat_perf = {}
            for s, perf in self.strategy_performance.items():
                total = perf["wins"] + perf["losses"]
                strat_perf[s] = {"total": total, "wr": round(perf["wins"]/total*100, 1) if total > 0 else 0, "pnl": perf["total_pnl"]}
            regime_data = {}
            for regime, info in self.knowledge_base["regime_insights"].items():
                total = info.get("total_trades", 0)
                regime_data[regime] = {"total": total, "wr": round(info.get("wins",0)/total*100,1) if total > 0 else 0, "best": info.get("best_strategy")}
            timing_data = {}
            for session, info in self.knowledge_base["timing_insights"].items():
                total = info.get("total", 0)
                timing_data[session] = {"total": total, "wr": round(info.get("wins",0)/total*100,1) if total > 0 else 0}
            prompt = (
                PHASE_ZERO_CONTEXT
                + f"你是跨策略交易分析专家。分析以下多策略表现数据，找出隐藏模式。\n\n"
                f"策略表现: {json.dumps(strat_perf, ensure_ascii=False)}\n"
                f"市况分析: {json.dumps(regime_data, ensure_ascii=False)}\n"
                f"时段分析: {json.dumps(timing_data, ensure_ascii=False)}\n"
                f"跨策略规则({len(self.cross_strategy_rules)}条): {json.dumps(self.cross_strategy_rules[-5:], ensure_ascii=False)}\n\n"
                f"请用JSON格式返回：\n"
                f'{{"insights": ["洞察1","洞察2"], "hidden_patterns": ["隐藏模式1","隐藏模式2"], "allocation_advice": {{"trend": 0.4, "range": 0.3, "grid": 0.3}}}}'
            )
            result = chat_json(
                module="synapse",
                messages=[{"role": "system", "content": SYNAPSE_PROMPT},
                          {"role": "user", "content": prompt}],
                max_tokens=16000,
            )
            if not result:
                raise Exception("AI返回空结果")
            result["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._last_ai_insights = result
            return result
        except Exception as e:
            fallback = {"insights": [], "hidden_patterns": [], "allocation_advice": {}, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "error": f"AI分析失败: {str(e)[:50]}"}
            self._last_ai_insights = fallback
            return fallback

    def get_status(self):
        strat_summary = {}
        for s, perf in self.strategy_performance.items():
            total = perf["wins"] + perf["losses"]
            strat_summary[s] = {
                "total_trades": total,
                "win_rate": round(perf["wins"] / total * 100, 1) if total > 0 else 0,
                "total_pnl": perf["total_pnl"],
                "worst_assets": dict(sorted(perf.get("worst_assets", {}).items(), key=lambda x: -x[1])[:5]),
            }

        regime_summary = {}
        for regime, info in self.knowledge_base["regime_insights"].items():
            total = info.get("total_trades", 0)
            regime_summary[regime] = {
                "total_trades": total,
                "win_rate": round(info.get("wins", 0) / total * 100, 1) if total > 0 else 0,
                "best_strategy": info.get("best_strategy"),
            }

        timing_summary = {}
        for session, info in self.knowledge_base["timing_insights"].items():
            total = info.get("total", 0)
            timing_summary[session] = {
                "total": total,
                "win_rate": round(info.get("wins", 0) / total * 100, 1) if total > 0 else 0,
            }

        status = {
            "total_broadcasts": self.stats["total_broadcasts"],
            "active_rules": len(self.cross_strategy_rules),
            "rules_generated": self.stats["rules_generated"],
            "last_sync": self.stats["last_sync"],
            "strategy_performance": strat_summary,
            "regime_insights": regime_summary,
            "timing_insights": timing_summary,
            "recent_broadcasts": self.broadcast_log[-10:],
            "cross_rules": self.cross_strategy_rules[-20:],
        }
        if self._last_ai_insights:
            status["ai_insights"] = self._last_ai_insights
        return status
