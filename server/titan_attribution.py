import os
import json
import math
import logging
from datetime import datetime

logger = logging.getLogger("TitanAttribution")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTRIBUTION_PATH = os.path.join(BASE_DIR, "data", "titan_attribution.json")
MAX_TRADES = 10000


class TitanAttribution:
    def __init__(self):
        self.trades = []
        self._load()

    def _load(self):
        try:
            if os.path.exists(ATTRIBUTION_PATH):
                with open(ATTRIBUTION_PATH, "r") as f:
                    data = json.load(f)
                self.trades = data.get("trades", [])
                logger.info(f"Attribution loaded: {len(self.trades)} trades")
        except Exception as e:
            logger.warning(f"Attribution load failed: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(ATTRIBUTION_PATH), exist_ok=True)
            data = {
                "trades": self.trades[-MAX_TRADES:],
                "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(ATTRIBUTION_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Attribution save failed: {e}")

    def record_trade(self, trade_info):
        trade = {
            "symbol": trade_info.get("symbol", "UNKNOWN"),
            "direction": trade_info.get("direction", "long"),
            "entry_price": trade_info.get("entry_price", 0),
            "exit_price": trade_info.get("exit_price", 0),
            "pnl_pct": trade_info.get("pnl_pct", 0),
            "pnl_usd": trade_info.get("pnl_usd", 0),
            "strategy_type": trade_info.get("strategy_type", "trend"),
            "signal_score": trade_info.get("signal_score", 0),
            "entry_time": trade_info.get("entry_time", ""),
            "exit_time": trade_info.get("exit_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "holding_hours": trade_info.get("holding_hours", 0),
            "timeframe": trade_info.get("timeframe", "1h"),
            "market_regime": trade_info.get("market_regime", "unknown"),
            "recorded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.trades.append(trade)
        if len(self.trades) > MAX_TRADES:
            self.trades = self.trades[-MAX_TRADES:]
        self._save()
        logger.info(f"Trade recorded: {trade['symbol']} {trade['direction']} pnl={trade['pnl_pct']}%")

    def _calc_sharpe(self, returns_list):
        if not returns_list or len(returns_list) < 2:
            return 0.0
        mean_r = sum(returns_list) / len(returns_list)
        variance = sum((r - mean_r) ** 2 for r in returns_list) / (len(returns_list) - 1)
        std_r = math.sqrt(variance) if variance > 0 else 0
        if std_r == 0:
            return 0.0
        return round(mean_r / std_r * math.sqrt(252), 2)

    def _calc_group_stats(self, group_trades):
        if not group_trades:
            return {"total_pnl": 0, "trade_count": 0, "win_rate": 0, "avg_pnl": 0, "sharpe": 0}
        pnls = [t["pnl_pct"] for t in group_trades]
        wins = sum(1 for p in pnls if p > 0)
        return {
            "total_pnl": round(sum(pnls), 2),
            "trade_count": len(group_trades),
            "win_rate": round(wins / len(group_trades) * 100, 1),
            "avg_pnl": round(sum(pnls) / len(group_trades), 2),
            "sharpe": self._calc_sharpe(pnls),
        }

    def by_strategy(self):
        groups = {}
        for t in self.trades:
            st = t.get("strategy_type", "unknown")
            groups.setdefault(st, []).append(t)
        return {k: self._calc_group_stats(v) for k, v in groups.items()}

    def by_asset(self):
        groups = {}
        for t in self.trades:
            sym = t.get("symbol", "UNKNOWN")
            groups.setdefault(sym, []).append(t)

        asset_stats = {k: self._calc_group_stats(v) for k, v in groups.items()}

        sorted_by_pnl = sorted(asset_stats.items(), key=lambda x: x[1]["total_pnl"], reverse=True)
        sorted_by_count = sorted(asset_stats.items(), key=lambda x: x[1]["trade_count"], reverse=True)

        return {
            "assets": asset_stats,
            "top_winners": [{"symbol": k, **v} for k, v in sorted_by_pnl[:5] if v["total_pnl"] > 0],
            "top_losers": [{"symbol": k, **v} for k, v in sorted_by_pnl[-5:] if v["total_pnl"] < 0],
            "most_traded": [{"symbol": k, **v} for k, v in sorted_by_count[:5]],
        }

    def by_session(self):
        sessions = {"asia": [], "europe": [], "us": []}
        for t in self.trades:
            exit_time = t.get("exit_time", "")
            if not exit_time:
                continue
            try:
                dt = datetime.strptime(exit_time, "%Y-%m-%d %H:%M:%S")
                hour_utc8 = (dt.hour + 8) % 24
                if 0 <= hour_utc8 < 8:
                    sessions["asia"].append(t)
                elif 8 <= hour_utc8 < 16:
                    sessions["europe"].append(t)
                else:
                    sessions["us"].append(t)
            except (ValueError, TypeError):
                continue
        return {k: self._calc_group_stats(v) for k, v in sessions.items()}

    def by_regime(self):
        groups = {}
        for t in self.trades:
            regime = t.get("market_regime", "unknown")
            groups.setdefault(regime, []).append(t)
        return {k: self._calc_group_stats(v) for k, v in groups.items()}

    def by_signal_quality(self):
        buckets = {"80-85": [], "85-90": [], "90-95": [], "95-100": []}
        for t in self.trades:
            score = t.get("signal_score", 0)
            if 80 <= score < 85:
                buckets["80-85"].append(t)
            elif 85 <= score < 90:
                buckets["85-90"].append(t)
            elif 90 <= score < 95:
                buckets["90-95"].append(t)
            elif score >= 95:
                buckets["95-100"].append(t)
        return {k: self._calc_group_stats(v) for k, v in buckets.items()}

    def get_summary(self):
        return {
            "total_trades": len(self.trades),
            "by_strategy": self.by_strategy(),
            "by_asset": self.by_asset(),
            "by_session": self.by_session(),
            "by_regime": self.by_regime(),
            "by_signal_quality": self.by_signal_quality(),
            "overall": self._calc_group_stats(self.trades),
        }

    def get_allocation_advice(self):
        advice = {
            "strategy": None,
            "assets": [],
            "session": None,
            "signal_quality": None,
            "reasoning": [],
        }

        strategy_stats = self.by_strategy()
        if strategy_stats:
            best_strategy = max(strategy_stats.items(), key=lambda x: x[1].get("sharpe", 0))
            if best_strategy[1]["trade_count"] >= 5:
                advice["strategy"] = {
                    "recommended": best_strategy[0],
                    "sharpe": best_strategy[1]["sharpe"],
                    "win_rate": best_strategy[1]["win_rate"],
                }
                advice["reasoning"].append(
                    f"Strategy '{best_strategy[0]}' has best Sharpe ({best_strategy[1]['sharpe']}) "
                    f"with {best_strategy[1]['win_rate']}% win rate over {best_strategy[1]['trade_count']} trades"
                )

        asset_data = self.by_asset()
        top_winners = asset_data.get("top_winners", [])
        if top_winners:
            focus_assets = [w["symbol"] for w in top_winners[:3] if w.get("trade_count", 0) >= 3]
            advice["assets"] = focus_assets
            if focus_assets:
                advice["reasoning"].append(f"Focus on assets: {', '.join(focus_assets)} (top performers)")

        session_stats = self.by_session()
        if session_stats:
            active_sessions = {k: v for k, v in session_stats.items() if v["trade_count"] >= 3}
            if active_sessions:
                best_session = max(active_sessions.items(), key=lambda x: x[1].get("sharpe", 0))
                advice["session"] = {
                    "recommended": best_session[0],
                    "sharpe": best_session[1]["sharpe"],
                    "win_rate": best_session[1]["win_rate"],
                }
                advice["reasoning"].append(
                    f"Best session: {best_session[0]} (Sharpe {best_session[1]['sharpe']}, "
                    f"win rate {best_session[1]['win_rate']}%)"
                )

        quality_stats = self.by_signal_quality()
        if quality_stats:
            active_buckets = {k: v for k, v in quality_stats.items() if v["trade_count"] >= 3}
            if active_buckets:
                best_bucket = max(active_buckets.items(), key=lambda x: x[1].get("win_rate", 0))
                advice["signal_quality"] = {
                    "recommended_bucket": best_bucket[0],
                    "win_rate": best_bucket[1]["win_rate"],
                    "avg_pnl": best_bucket[1]["avg_pnl"],
                }
                advice["reasoning"].append(
                    f"Signal scores {best_bucket[0]} have best win rate ({best_bucket[1]['win_rate']}%)"
                )

        if not advice["reasoning"]:
            advice["reasoning"].append("Insufficient trade data for allocation advice (need more trades)")

        return advice

    def get_status(self):
        if not self.trades:
            return {
                "total_trades": 0,
                "total_pnl_pct": 0,
                "total_pnl_usd": 0,
                "win_rate": 0,
                "strategies": {},
                "top_asset": None,
                "best_session": None,
            }

        total_pnl_pct = round(sum(t.get("pnl_pct", 0) for t in self.trades), 2)
        total_pnl_usd = round(sum(t.get("pnl_usd", 0) for t in self.trades), 2)
        wins = sum(1 for t in self.trades if t.get("pnl_pct", 0) > 0)
        win_rate = round(wins / len(self.trades) * 100, 1)

        strategy_stats = self.by_strategy()

        asset_data = self.by_asset()
        top_asset = asset_data["top_winners"][0]["symbol"] if asset_data.get("top_winners") else None

        session_stats = self.by_session()
        best_session = None
        if session_stats:
            active = {k: v for k, v in session_stats.items() if v["trade_count"] > 0}
            if active:
                best_session = max(active.items(), key=lambda x: x[1]["total_pnl"])[0]

        return {
            "total_trades": len(self.trades),
            "total_pnl_pct": total_pnl_pct,
            "total_pnl_usd": total_pnl_usd,
            "win_rate": win_rate,
            "strategies": strategy_stats,
            "top_asset": top_asset,
            "best_session": best_session,
        }


    def get_chart_data(self):
        if not self.trades:
            return {"equity_curve": [], "drawdown_series": [], "pnl_waterfall": [], "cumulative_by_strategy": {}, "monthly_pnl": []}

        equity = 100000
        peak = equity
        equity_curve = []
        drawdown_series = []
        strategy_cumulative = {}

        for t in self.trades:
            pnl_usd = t.get("pnl_usd", 0)
            if pnl_usd == 0 and t.get("pnl_pct", 0) != 0:
                pnl_usd = equity * t["pnl_pct"] / 100
            equity += pnl_usd
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100 if peak > 0 else 0

            ts = t.get("exit_time", t.get("recorded_at", ""))
            equity_curve.append({"time": ts, "equity": round(equity, 2), "pnl": round(pnl_usd, 2)})
            drawdown_series.append({"time": ts, "drawdown": round(-dd, 2)})

            strat = t.get("strategy_type", "unknown")
            if strat not in strategy_cumulative:
                strategy_cumulative[strat] = []
            prev = strategy_cumulative[strat][-1]["cumulative"] if strategy_cumulative[strat] else 0
            strategy_cumulative[strat].append({"time": ts, "cumulative": round(prev + pnl_usd, 2)})

        strategy_summary = self.by_strategy()
        pnl_waterfall = []
        for strat, stats in sorted(strategy_summary.items(), key=lambda x: x[1].get("total_pnl", 0), reverse=True):
            pnl_waterfall.append({
                "name": strat,
                "total_pnl": stats["total_pnl"],
                "trades": stats["trade_count"],
                "win_rate": stats["win_rate"],
            })

        monthly = {}
        for t in self.trades:
            ts = t.get("exit_time", t.get("recorded_at", ""))
            if len(ts) >= 7:
                month_key = ts[:7]
                if month_key not in monthly:
                    monthly[month_key] = {"month": month_key, "pnl": 0, "trades": 0, "wins": 0}
                monthly[month_key]["pnl"] = round(monthly[month_key]["pnl"] + t.get("pnl_pct", 0), 3)
                monthly[month_key]["trades"] += 1
                if t.get("pnl_pct", 0) > 0:
                    monthly[month_key]["wins"] += 1

        for m in monthly.values():
            if m["trades"] > 0:
                m["win_rate"] = round(m["wins"] / m["trades"] * 100, 1)

        return {
            "equity_curve": equity_curve[-500:],
            "drawdown_series": drawdown_series[-500:],
            "pnl_waterfall": pnl_waterfall,
            "cumulative_by_strategy": {k: v[-200:] for k, v in strategy_cumulative.items()},
            "monthly_pnl": sorted(monthly.values(), key=lambda x: x["month"]),
        }


attribution = TitanAttribution()
