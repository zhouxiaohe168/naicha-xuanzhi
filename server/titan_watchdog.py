import os
import json
import time
import logging
import traceback
from datetime import datetime
from server.titan_prompt_library import WATCHDOG_PROMPT

logger = logging.getLogger("TitanWatchdog")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHDOG_PATH = os.path.join(BASE_DIR, "data", "titan_watchdog.json")

# the newest OpenAI model is "gpt-5" which was released August 7, 2025.
# do not change this unless explicitly requested by the user
WATCHDOG_MODEL = "gpt-4o-mini"
AI_DIAGNOSIS_COOLDOWN = 120


class TitanWatchdog:
    SEVERITY_LEVELS = {
        "critical": 4,
        "error": 3,
        "warning": 2,
        "info": 1,
    }

    def __init__(self):
        self.alerts = []
        self.active_alerts = []
        self.health_checks = {}
        self.anomaly_rules = []
        self.stats = {
            "total_alerts": 0,
            "critical_count": 0,
            "error_count": 0,
            "warning_count": 0,
            "auto_resolved": 0,
            "last_check": "",
            "last_ai_diagnosis": "",
            "system_health": "healthy",
        }
        self._last_ai_time = 0
        self._load()

    def _load(self):
        try:
            if os.path.exists(WATCHDOG_PATH):
                with open(WATCHDOG_PATH, "r") as f:
                    data = json.load(f)
                self.alerts = data.get("alerts", [])
                self.active_alerts = data.get("active_alerts", [])
                self.health_checks = data.get("health_checks", {})
                self.anomaly_rules = data.get("anomaly_rules", [])
                self.stats = data.get("stats", self.stats)
                logger.info(f"Watchdog loaded: {len(self.alerts)} alerts, {len(self.active_alerts)} active")
        except Exception as e:
            logger.warning(f"Watchdog load failed: {e}")

    def save(self):
        try:
            os.makedirs(os.path.dirname(WATCHDOG_PATH), exist_ok=True)
            data = {
                "alerts": self.alerts[-500:],
                "active_alerts": self.active_alerts,
                "health_checks": self.health_checks,
                "anomaly_rules": self.anomaly_rules[-50:],
                "stats": self.stats,
                "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(WATCHDOG_PATH, "w") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Watchdog save failed: {e}")

    def report_alert(self, category, severity, title, detail, context=None, auto_resolve=False):
        if severity not in self.SEVERITY_LEVELS:
            severity = "warning"

        alert = {
            "id": f"alert_{int(time.time()*1000)}",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "category": category,
            "severity": severity,
            "title": title,
            "detail": detail,
            "context": context or {},
            "status": "active",
            "resolution": None,
            "ai_diagnosis": None,
        }

        self.alerts.append(alert)
        self.active_alerts.append(alert)
        self.stats["total_alerts"] += 1
        self.stats[f"{severity}_count"] = self.stats.get(f"{severity}_count", 0) + 1

        if severity in ["critical", "error"]:
            self._update_system_health()

        if auto_resolve:
            alert["status"] = "auto_resolved"
            alert["resolution"] = "系统自动处理"
            self.active_alerts = [a for a in self.active_alerts if a["id"] != alert["id"]]
            self.stats["auto_resolved"] += 1

        self.save()
        log_fn = logger.critical if severity == "critical" else logger.error if severity == "error" else logger.warning
        log_fn(f"Watchdog [{severity.upper()}] {category}: {title}")

        return alert

    def resolve_alert(self, alert_id, resolution="手动解决"):
        for alert in self.active_alerts:
            if alert["id"] == alert_id:
                alert["status"] = "resolved"
                alert["resolution"] = resolution
                alert["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                break
        self.active_alerts = [a for a in self.active_alerts if a["status"] == "active"]
        self._update_system_health()
        self.save()

    def run_health_check(self, paper_trader=None, risk_budget=None, dispatcher=None,
                          synapse=None, signal_quality=None, constitution=None,
                          market_data=None):
        checks = {}
        now = datetime.now()

        if paper_trader:
            try:
                positions = paper_trader.get_open_positions() if hasattr(paper_trader, 'get_open_positions') else []
                equity = getattr(paper_trader, 'equity', 0)
                checks["paper_trader"] = {"status": "ok", "positions": len(positions), "equity": equity}

                for pos in positions:
                    pnl_pct = pos.get("pnl_pct", 0)
                    if pnl_pct < -5:
                        self.report_alert(
                            "position_risk", "warning",
                            f"{pos.get('symbol','?')} 亏损{pnl_pct:.1f}%",
                            f"持仓亏损超过5%，建议检查止损设置",
                            {"symbol": pos.get("symbol"), "pnl_pct": pnl_pct},
                        )
                    if pnl_pct < -10:
                        self.report_alert(
                            "position_risk", "error",
                            f"{pos.get('symbol','?')} 严重亏损{pnl_pct:.1f}%",
                            f"持仓亏损超过10%，触发风控警报",
                            {"symbol": pos.get("symbol"), "pnl_pct": pnl_pct},
                        )
            except Exception as e:
                checks["paper_trader"] = {"status": "error", "error": str(e)}
                self.report_alert("system", "error", "PaperTrader异常", str(e))

        if risk_budget:
            try:
                status = risk_budget.get_status()
                dd = status.get("total_drawdown_pct", 0)
                daily_pnl = status.get("daily_pnl", 0)
                daily_limit = status.get("daily_loss_limit", 0)
                capital = status.get("total_capital", 0)

                checks["risk_budget"] = {"status": "ok", "capital": capital, "drawdown": dd}

                if dd > 5:
                    self.report_alert(
                        "risk", "error",
                        f"总回撤{dd:.1f}%超过5%警戒线",
                        "系统回撤偏高，建议减少仓位或暂停交易",
                        {"drawdown_pct": dd, "capital": capital},
                    )
                elif dd > 3:
                    self.report_alert(
                        "risk", "warning",
                        f"总回撤{dd:.1f}%接近警戒线",
                        "回撤趋势需要关注",
                        {"drawdown_pct": dd},
                    )

                if daily_limit > 0 and abs(daily_pnl) > daily_limit * 0.8:
                    self.report_alert(
                        "risk", "warning",
                        f"日亏损已达限额{abs(daily_pnl)/daily_limit*100:.0f}%",
                        f"日PnL=${daily_pnl:,.2f}, 限额=${daily_limit:,.2f}",
                        {"daily_pnl": daily_pnl, "daily_limit": daily_limit},
                    )

                for s, b in status.get("strategy_budgets", {}).items():
                    if b.get("frozen"):
                        self.report_alert(
                            "risk", "warning",
                            f"策略{s}已被冻结",
                            f"回撤触发冻结，需手动或次日自动解冻",
                            {"strategy": s, "frozen": True},
                        )
            except Exception as e:
                checks["risk_budget"] = {"status": "error", "error": str(e)}
                self.report_alert("system", "error", "RiskBudget异常", str(e))

        if dispatcher:
            try:
                d_status = dispatcher.get_status()
                checks["dispatcher"] = {
                    "status": "ok",
                    "regime": d_status.get("current_regime", "unknown"),
                    "switches": d_status.get("switch_count", 0),
                }
                if d_status.get("current_regime") == "unknown":
                    self.report_alert(
                        "data", "warning",
                        "Dispatcher无法识别市场环境",
                        "市场数据可能不足或ADX计算异常",
                    )
            except Exception as e:
                checks["dispatcher"] = {"status": "error", "error": str(e)}
                self.report_alert("system", "error", "Dispatcher异常", str(e))

        if synapse:
            try:
                s_status = synapse.get_status()
                checks["synapse"] = {
                    "status": "ok",
                    "broadcasts": s_status.get("total_broadcasts", 0),
                    "rules": s_status.get("active_rules", 0),
                }
            except Exception as e:
                checks["synapse"] = {"status": "error", "error": str(e)}
                self.report_alert("system", "error", "Synapse异常", str(e))

        if signal_quality:
            try:
                sq_status = signal_quality.get_status()
                checks["signal_quality"] = {
                    "status": "ok",
                    "conditions": sq_status.get("total_conditions", 0),
                    "calibrated": sq_status.get("calibrated_conditions", 0),
                }
            except Exception as e:
                checks["signal_quality"] = {"status": "error", "error": str(e)}
                self.report_alert("system", "error", "SignalQuality异常", str(e))

        if market_data:
            try:
                btc_price = market_data.get("btc_price", 0)
                if btc_price <= 0:
                    self.report_alert(
                        "data", "error",
                        "BTC价格数据异常",
                        f"BTC价格为{btc_price}，数据源可能中断",
                        {"btc_price": btc_price},
                    )

                scan_count = market_data.get("scan_count", 0)
                last_scan = market_data.get("last_scan", "")
                if last_scan:
                    try:
                        last_dt = datetime.strptime(last_scan, "%Y-%m-%d %H:%M:%S")
                        minutes_ago = (now - last_dt).total_seconds() / 60
                        if minutes_ago > 30:
                            self.report_alert(
                                "data", "warning",
                                f"扫描数据过时({minutes_ago:.0f}分钟前)",
                                "市场扫描可能卡住，建议检查API连接",
                                {"minutes_ago": minutes_ago},
                            )
                    except (ValueError, TypeError):
                        pass

                checks["market_data"] = {"status": "ok", "btc_price": btc_price, "scan_count": scan_count}
            except Exception as e:
                checks["market_data"] = {"status": "error", "error": str(e)}

        if constitution:
            try:
                c_status = constitution.get_status() if hasattr(constitution, 'get_status') else {}
                status_val = c_status.get("status", "HEALTHY")
                checks["constitution"] = {"status": "ok", "state": status_val}
                if status_val not in ("HEALTHY", "active"):
                    status_cn = {"DEAD": "永久熔断", "RECOVERING": "恢复中(日暂停)", "EMERGENCY": "链上紧急"}.get(status_val, status_val)
                    self.report_alert(
                        "circuit_breaker", "critical",
                        f"宪法熔断器状态: {status_cn}",
                        "熔断器已触发或系统处于非活跃状态",
                        {"constitution_status": status_val},
                    )
                else:
                    self.active_alerts = [
                        a for a in self.active_alerts
                        if a.get("category") != "circuit_breaker"
                        or "Constitution" not in a.get("title", "")
                        and "宪法熔断器" not in a.get("title", "")
                    ]
            except Exception as e:
                checks["constitution"] = {"status": "error", "error": str(e)}

        self.health_checks = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "checks": checks,
            "overall": "healthy" if all(c.get("status") == "ok" for c in checks.values()) else "degraded",
        }
        self.stats["last_check"] = self.health_checks["time"]
        self._update_system_health()
        self._deduplicate_active_alerts()
        self.save()

        return self.health_checks

    def _deduplicate_active_alerts(self):
        seen = {}
        deduped = []
        for alert in self.active_alerts:
            key = f"{alert['category']}:{alert['title']}"
            if key not in seen:
                seen[key] = alert
                deduped.append(alert)
            else:
                if alert["timestamp"] > seen[key]["timestamp"]:
                    deduped = [a for a in deduped if a["id"] != seen[key]["id"]]
                    deduped.append(alert)
                    seen[key] = alert
        self.active_alerts = deduped

    def _update_system_health(self):
        critical = sum(1 for a in self.active_alerts if a.get("severity") == "critical")
        errors = sum(1 for a in self.active_alerts if a.get("severity") == "error")

        if critical > 0:
            self.stats["system_health"] = "critical"
        elif errors >= 3:
            self.stats["system_health"] = "degraded"
        elif errors > 0:
            self.stats["system_health"] = "warning"
        else:
            self.stats["system_health"] = "healthy"

    def ai_diagnose(self, force=False):
        now = time.time()
        if not force and now - self._last_ai_time < AI_DIAGNOSIS_COOLDOWN:
            return None

        if not self.active_alerts:
            return {"diagnosis": "系统健康，无异常", "suggestions": []}

        try:
            from server.titan_llm_client import chat_json

            alerts_text = "\n".join([
                f"[{a['severity'].upper()}] {a['category']}: {a['title']} - {a['detail']}"
                for a in self.active_alerts[:15]
            ])

            health_text = json.dumps(self.health_checks.get("checks", {}), ensure_ascii=False, indent=2)[:800]

            prompt = f"""你是Titan V19.2交易系统的AI值班员。请分析以下系统警报，诊断问题根因，并给出具体解决方案。

## 重要背景
系统正处于【阶段零观察期】(2026-02-26启动)。此阶段不做代码修改、不调整参数，只观察积累数据。
信号层v3.0于2月24日上线，修复前的历史数据不代表当前系统能力。
资金利用率低、持仓少是阶段零的正常状态，不要建议"提升激进度"或"降低信号门槛"。

## 当前活跃警报 ({len(self.active_alerts)}个)
{alerts_text}

## 系统健康检查
{health_text}

请以JSON格式回复：
{{
  "overall_assessment": "系统整体评估",
  "root_causes": ["根因1", "根因2"],
  "diagnosis": [
    {{"alert": "警报标题", "cause": "原因分析", "solution": "解决方案", "priority": "high/medium/low"}}
  ],
  "immediate_actions": ["需立即执行的操作"],
  "prevention_suggestions": ["预防建议"],
  "code_fix_hints": ["可能需要修复的代码问题描述"]
}}"""

            result = chat_json(
                module="watchdog",
                messages=[
                    {"role": "system", "content": WATCHDOG_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,
            )

            if not result:
                return self._rule_based_diagnosis()
            self._last_ai_time = now
            self.stats["last_ai_diagnosis"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save()

            logger.info(f"Watchdog AI diagnosis complete: {len(result.get('diagnosis', []))} items")
            return result

        except Exception as e:
            logger.warning(f"Watchdog AI diagnosis failed: {e}")
            return self._rule_based_diagnosis()

    def _rule_based_diagnosis(self):
        diagnosis = []
        for alert in self.active_alerts[:10]:
            cat = alert.get("category", "")
            severity = alert.get("severity", "")

            if cat == "position_risk":
                diagnosis.append({
                    "alert": alert["title"],
                    "cause": "持仓亏损过大",
                    "solution": "检查止损设置，考虑手动平仓或收紧止损",
                    "priority": "high" if severity in ["critical", "error"] else "medium",
                })
            elif cat == "risk":
                diagnosis.append({
                    "alert": alert["title"],
                    "cause": "系统风险控制触发",
                    "solution": "减少仓位，等待回撤修复",
                    "priority": "high",
                })
            elif cat == "data":
                diagnosis.append({
                    "alert": alert["title"],
                    "cause": "数据源异常",
                    "solution": "检查API连接状态，验证数据完整性",
                    "priority": "high" if severity == "error" else "medium",
                })
            elif cat == "system":
                diagnosis.append({
                    "alert": alert["title"],
                    "cause": "模块运行异常",
                    "solution": "检查日志，重启相关模块",
                    "priority": "high",
                })
            else:
                diagnosis.append({
                    "alert": alert["title"],
                    "cause": "未分类异常",
                    "solution": "需人工排查",
                    "priority": "medium",
                })

        return {
            "overall_assessment": f"发现{len(self.active_alerts)}个活跃警报",
            "root_causes": list(set(d["cause"] for d in diagnosis)),
            "diagnosis": diagnosis,
            "immediate_actions": ["检查持仓风险", "验证数据源"],
            "prevention_suggestions": ["定期检查系统健康"],
            "code_fix_hints": [],
        }

    def log_exception(self, module_name, error, context=None):
        tb = traceback.format_exc() if error else ""
        self.report_alert(
            "exception", "error",
            f"{module_name}抛出异常: {type(error).__name__}",
            f"{str(error)[:200]}\n{tb[:300]}",
            {"module": module_name, **(context or {})},
        )

    def get_status(self):
        severity_dist = {}
        for a in self.active_alerts:
            sev = a.get("severity", "info")
            severity_dist[sev] = severity_dist.get(sev, 0) + 1

        category_dist = {}
        for a in self.active_alerts:
            cat = a.get("category", "other")
            category_dist[cat] = category_dist.get(cat, 0) + 1

        return {
            "system_health": self.stats["system_health"],
            "total_alerts": self.stats["total_alerts"],
            "active_alerts_count": len(self.active_alerts),
            "auto_resolved": self.stats["auto_resolved"],
            "last_check": self.stats["last_check"],
            "last_ai_diagnosis": self.stats["last_ai_diagnosis"],
            "severity_distribution": severity_dist,
            "category_distribution": category_dist,
            "active_alerts": [
                {
                    "id": a["id"],
                    "time": a["time"],
                    "severity": a["severity"],
                    "category": a["category"],
                    "title": a["title"],
                    "detail": a["detail"][:100],
                    "ai_diagnosis": a.get("ai_diagnosis"),
                }
                for a in sorted(self.active_alerts, key=lambda x: -self.SEVERITY_LEVELS.get(x.get("severity", "info"), 0))[:20]
            ],
            "recent_alerts": [
                {
                    "time": a["time"],
                    "severity": a["severity"],
                    "title": a["title"],
                    "status": a["status"],
                }
                for a in self.alerts[-20:]
            ],
            "health_checks": self.health_checks,
        }


watchdog = TitanWatchdog()
