import os
import json
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("TitanUnifiedMemory")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNIFIED_INDEX_PATH = os.path.join(BASE_DIR, "data", "titan_unified_memory_index.json")


class TitanUnifiedMemory:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._agent_memory = None
        self._memory_bank = None
        self._synapse = None
        self._hippocampus = None
        self._index = {"last_sync": "", "query_count": 0, "write_count": 0}
        self._load_index()
        TitanUnifiedMemory._instance = self

    def _load_index(self):
        try:
            if os.path.exists(UNIFIED_INDEX_PATH):
                with open(UNIFIED_INDEX_PATH, "r") as f:
                    self._index = json.load(f)
        except Exception:
            pass

    def _save_index(self):
        try:
            os.makedirs(os.path.dirname(UNIFIED_INDEX_PATH), exist_ok=True)
            self._index["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(UNIFIED_INDEX_PATH, "w") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"统一记忆索引保存失败: {e}")

    def register_backends(self, agent_memory=None, memory_bank=None, synapse=None, hippocampus=None):
        if agent_memory:
            self._agent_memory = agent_memory
        if memory_bank:
            self._memory_bank = memory_bank
        if synapse:
            self._synapse = synapse
        if hippocampus:
            self._hippocampus = hippocampus
        logger.info(f"统一记忆注册: agent={agent_memory is not None}, bank={memory_bank is not None}, synapse={synapse is not None}, hippo={hippocampus is not None}")

    def write(self, category, data):
        self._index["write_count"] = self._index.get("write_count", 0) + 1
        try:
            if category == "trade_result":
                self._write_trade_result(data)
            elif category == "pattern":
                self._write_pattern(data)
            elif category == "insight":
                self._write_insight(data)
            elif category == "rule":
                self._write_rule(data)
            elif category == "regime_change":
                self._write_regime_change(data)
            elif category == "performance_snapshot":
                self._write_performance_snapshot(data)
            elif category == "market_event":
                self._write_market_event(data)
            elif category == "ban_rule":
                self._write_ban_rule(data)
            else:
                logger.warning(f"未知记忆类别: {category}")
                return False
            self._save_index()
            return True
        except Exception as e:
            logger.error(f"统一记忆写入失败 [{category}]: {e}")
            return False

    def _write_trade_result(self, data):
        if self._synapse:
            self._synapse.broadcast_trade_result(data)
        if self._memory_bank:
            self._memory_bank.record_trade_pattern(data)
        if self._agent_memory:
            symbol = data.get("symbol", "")
            strategy = data.get("strategy_type", "unknown")
            regime = data.get("market_regime", "unknown")
            pnl = data.get("pnl_pct", 0)
            pattern_key = f"{symbol}_{strategy}_{regime}"
            self._agent_memory.record_pattern(pattern_key, "win" if pnl > 0 else "loss")
            self._agent_memory.total_trades_seen += 1

    def _write_pattern(self, data):
        if self._agent_memory:
            key = data.get("key", "unknown")
            outcome = data.get("outcome", "loss")
            self._agent_memory.record_pattern(key, outcome)

    def _write_insight(self, data):
        if self._memory_bank:
            self._memory_bank.add_insight(
                data.get("category", "general"),
                data.get("text", ""),
                data.get("confidence", 0.5),
                data.get("source", "system")
            )
        if self._agent_memory:
            self._agent_memory.add_insight(data.get("text", ""))

    def _write_rule(self, data):
        if self._memory_bank:
            self._memory_bank.add_rule(
                data.get("type", "general"),
                data.get("condition", ""),
                data.get("action", ""),
                data.get("performance")
            )

    def _write_regime_change(self, data):
        if self._memory_bank:
            self._memory_bank.record_regime_change(
                data.get("from", "unknown"),
                data.get("to", "unknown"),
                data.get("context")
            )

    def _write_performance_snapshot(self, data):
        if self._memory_bank:
            self._memory_bank.record_performance_snapshot(data)

    def _write_market_event(self, data):
        if self._memory_bank:
            self._memory_bank.record_market_event(
                data.get("event_type", "unknown"),
                data.get("description", ""),
                data.get("impact", 0),
                data.get("data")
            )

    def _write_ban_rule(self, data):
        if self._agent_memory:
            self._agent_memory.critic_ban_rules.append(data)
            self._agent_memory.save()

    def query(self, query_type, **kwargs):
        self._index["query_count"] = self._index.get("query_count", 0) + 1
        try:
            if query_type == "similar_trades":
                return self._query_similar_trades(**kwargs)
            elif query_type == "pattern_win_rate":
                return self._query_pattern_win_rate(**kwargs)
            elif query_type == "should_trade":
                return self._query_should_trade(**kwargs)
            elif query_type == "preferred_strategy":
                return self._query_preferred_strategy(**kwargs)
            elif query_type == "regime_stats":
                return self._query_regime_stats()
            elif query_type == "active_rules":
                return self._query_active_rules()
            elif query_type == "performance_trend":
                return self._query_performance_trend(**kwargs)
            elif query_type == "hippocampus_recall":
                return self._query_hippocampus_recall(**kwargs)
            elif query_type == "ban_rules":
                return self._query_ban_rules()
            elif query_type == "full_summary":
                return self.get_full_summary()
            else:
                return {"error": f"未知查询类型: {query_type}"}
        except Exception as e:
            logger.error(f"统一记忆查询失败 [{query_type}]: {e}")
            return {"error": str(e)}

    def _query_similar_trades(self, symbol=None, regime=None, direction=None, limit=20):
        if self._memory_bank:
            return self._memory_bank.get_similar_trades(symbol, regime, direction, limit)
        return []

    def _query_pattern_win_rate(self, pattern_key=""):
        if self._agent_memory:
            return self._agent_memory.get_pattern_win_rate(pattern_key)
        return None

    def _query_should_trade(self, symbol="", strategy="", regime="unknown"):
        results = {"allowed": True, "reasons": []}
        if self._synapse:
            allowed, reason = self._synapse.should_trade(symbol, strategy, regime)
            if not allowed:
                results["allowed"] = False
                results["reasons"].append(f"[Synapse] {reason}")
        if self._agent_memory:
            base = symbol.replace("/USDT", "").replace("_USDT", "")
            for rule in getattr(self._agent_memory, 'critic_ban_rules', []):
                ban_sym = rule.get("symbol", "") if isinstance(rule, dict) else ""
                if ban_sym and ban_sym.upper() == base.upper():
                    results["allowed"] = False
                    results["reasons"].append(f"[Critic] {rule.get('reason', '禁用')}")
        return results

    def _query_preferred_strategy(self, symbol="", regime="unknown"):
        if self._synapse:
            return self._synapse.get_preferred_strategy(symbol, regime)
        return None

    def _query_regime_stats(self):
        if self._memory_bank:
            return self._memory_bank.get_regime_stats()
        return {"total_changes": 0, "regimes": {}}

    def _query_active_rules(self):
        rules = []
        if self._memory_bank:
            rules.extend([{"source": "memory_bank", **r} for r in self._memory_bank.get_active_rules()])
        if self._synapse:
            rules.extend([{"source": "synapse", **r} for r in self._synapse.cross_strategy_rules])
        if self._agent_memory:
            for r in getattr(self._agent_memory, 'critic_ban_rules', []):
                if isinstance(r, dict):
                    rules.append({"source": "critic", **r})
        return rules

    def _query_performance_trend(self, days=30):
        if self._memory_bank:
            return self._memory_bank.get_performance_trend(days)
        return []

    def _query_hippocampus_recall(self, symbol="", closes=None):
        if self._hippocampus and closes:
            return self._hippocampus.recall(symbol, closes)
        return None

    def _query_ban_rules(self):
        rules = []
        if self._agent_memory:
            rules.extend(getattr(self._agent_memory, 'critic_ban_rules', []))
        return rules

    def get_full_summary(self):
        summary = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "backends": {
                "agent_memory": self._agent_memory is not None,
                "memory_bank": self._memory_bank is not None,
                "synapse": self._synapse is not None,
                "hippocampus": self._hippocampus is not None,
            },
            "stats": {
                "query_count": self._index.get("query_count", 0),
                "write_count": self._index.get("write_count", 0),
                "last_sync": self._index.get("last_sync", ""),
            },
            "agent_memory": {},
            "memory_bank": {},
            "synapse": {},
            "hippocampus": {},
        }

        if self._agent_memory:
            am_status = self._agent_memory.get_status()
            summary["agent_memory"] = {
                "session_count": am_status.get("session_count", 0),
                "total_trades_seen": am_status.get("total_trades_seen", 0),
                "ban_rules": am_status.get("ban_rules", 0),
                "patterns_tracked": am_status.get("patterns_tracked", 0),
                "insights_count": am_status.get("insights_count", 0),
                "recent_insights": am_status.get("recent_insights", [])[-3:],
                "top_patterns": am_status.get("top_patterns", [])[:5],
                "adaptive_weights": am_status.get("adaptive_weights", {}),
            }

        if self._memory_bank:
            mb = self._memory_bank.memories
            summary["memory_bank"] = {
                "trade_patterns": len(mb.get("trade_patterns", [])),
                "regime_history": len(mb.get("regime_history", [])),
                "insights": len(mb.get("insights", [])),
                "rules": len([r for r in mb.get("rules", []) if r.get("active", True)]),
                "performance_snapshots": len(mb.get("performance_snapshots", [])),
                "market_events": len(mb.get("market_events", [])),
                "regime_stats": self._memory_bank.get_regime_stats(),
            }

        if self._synapse:
            syn_status = self._synapse.get_status()
            summary["synapse"] = {
                "total_broadcasts": syn_status.get("total_broadcasts", 0),
                "active_rules": syn_status.get("active_rules", 0),
                "strategy_performance": syn_status.get("strategy_performance", {}),
                "regime_insights": syn_status.get("regime_insights", {}),
                "timing_insights": syn_status.get("timing_insights", {}),
            }

        if self._hippocampus:
            stats = getattr(self._hippocampus, 'stats', {})
            summary["hippocampus"] = {
                "total_memories": stats.get("total_memories", 0),
                "assets_loaded": stats.get("assets_loaded", 0),
                "recalls": stats.get("recalls", 0),
            }

        total_records = (
            summary["agent_memory"].get("total_trades_seen", 0) +
            summary["memory_bank"].get("trade_patterns", 0) +
            summary["synapse"].get("total_broadcasts", 0) +
            summary["hippocampus"].get("total_memories", 0)
        )
        total_rules = (
            summary["agent_memory"].get("ban_rules", 0) +
            summary["memory_bank"].get("rules", 0) +
            summary["synapse"].get("active_rules", 0)
        )
        summary["totals"] = {
            "total_records": total_records,
            "total_rules": total_rules,
            "total_insights": summary["agent_memory"].get("insights_count", 0) + summary["memory_bank"].get("insights", 0),
            "total_patterns": summary["agent_memory"].get("patterns_tracked", 0),
        }

        return summary

    def save_all(self):
        if self._agent_memory:
            self._agent_memory.save()
        if self._memory_bank:
            self._memory_bank._save()
        if self._synapse:
            self._synapse.save()
        self._save_index()
        logger.info("统一记忆: 全部后端已保存")

    def get_status(self):
        return {
            "registered_backends": sum([
                self._agent_memory is not None,
                self._memory_bank is not None,
                self._synapse is not None,
                self._hippocampus is not None,
            ]),
            "total_backends": 4,
            "query_count": self._index.get("query_count", 0),
            "write_count": self._index.get("write_count", 0),
            "last_sync": self._index.get("last_sync", ""),
        }


unified_memory = TitanUnifiedMemory.get_instance()
