import os
import json
import re
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger("TitanSelfInspector")

INSPECTION_REPORT_PATH = "data/titan_inspection_reports.json"
INSPECTION_CONFIG_PATH = "data/titan_inspection_config.json"

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"
SEVERITY_SUGGESTION = "suggestion"


class InspectionFinding:
    def __init__(self, inspector: str, severity: str, title: str,
                 detail: str, evidence: str = "", fix_hint: str = "",
                 category: str = "general"):
        self.inspector = inspector
        self.severity = severity
        self.title = title
        self.detail = detail
        self.evidence = evidence
        self.fix_hint = fix_hint
        self.category = category
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "inspector": self.inspector,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "evidence": self.evidence,
            "fix_hint": self.fix_hint,
            "category": self.category,
            "timestamp": self.timestamp,
        }


class InspectionReport:
    def __init__(self):
        self.findings: List[InspectionFinding] = []
        self.start_time = datetime.now()
        self.end_time = None
        self.inspectors_run = []
        self.ai_summary = ""
        self.inspector_analyses: Dict[str, str] = {}

    def add(self, finding: InspectionFinding):
        self.findings.append(finding)

    def finalize(self):
        self.end_time = datetime.now()

    def to_dict(self):
        return {
            "timestamp": self.start_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else 0,
            "inspectors_run": self.inspectors_run,
            "total_findings": len(self.findings),
            "by_severity": {
                "critical": sum(1 for f in self.findings if f.severity == SEVERITY_CRITICAL),
                "warning": sum(1 for f in self.findings if f.severity == SEVERITY_WARNING),
                "info": sum(1 for f in self.findings if f.severity == SEVERITY_INFO),
                "suggestion": sum(1 for f in self.findings if f.severity == SEVERITY_SUGGESTION),
            },
            "findings": [f.to_dict() for f in self.findings],
            "ai_summary": self.ai_summary,
            "inspector_analyses": self.inspector_analyses,
        }


class LogicAuditor:
    NAME = "logic_auditor"
    DISPLAY = "逻辑审计员"

    def run(self, report: InspectionReport):
        report.inspectors_run.append(self.NAME)
        self._check_threshold_conflicts(report)
        self._check_duplicate_rules(report)
        self._check_parameter_consistency(report)
        self._check_risk_parameter_alignment(report)

    def _check_threshold_conflicts(self, report: InspectionReport):
        try:
            from server.titan_unified_decision import TitanUnifiedDecision
            from server.titan_autopilot import TitanSignalGate

            ud_instance = TitanUnifiedDecision()
            ud_base = getattr(ud_instance, 'BASE_THRESHOLD', None)

            gate_min = getattr(TitanSignalGate, 'MIN_SIGNAL_SCORE', None)
            gate_ml_min = getattr(TitanSignalGate, 'MIN_ML_CONFIDENCE', None)

            signal_gate_src = self._read_file_section("server/titan_autopilot.py", "volatile.*signal_score.*<")
            if signal_gate_src:
                matches = re.findall(r'signal_score\s*<\s*(\d+)', signal_gate_src)
                for m in matches:
                    gate_threshold = int(m)
                    if ud_base and gate_threshold > ud_base:
                        report.add(InspectionFinding(
                            self.NAME, SEVERITY_WARNING,
                            "信号过滤门槛冲突",
                            f"两个安全检查对信号的要求不一致：一个要求评分>={gate_threshold}分，另一个只要求>={ud_base}分。"
                            f"差距{gate_threshold - ud_base}分，可能导致本应通过的交易信号被误拦截。",
                            evidence=f"SignalGate: score<{gate_threshold} → block; UnifiedDecision base={ud_base}",
                            fix_hint=f"建议统一信号过滤标准，将高门槛降至{ud_base}分以避免过度拦截",
                            category="threshold_conflict"
                        ))

            trade_judge_src = self._read_file_section("server/titan_prompt_library.py", "volatile.*信号评分")
            if trade_judge_src:
                matches = re.findall(r'volatile.*?≥(\d+)', trade_judge_src)
                for m in matches:
                    tj_threshold = int(m)
                    if ud_base and tj_threshold > ud_base + 10:
                        report.add(InspectionFinding(
                            self.NAME, SEVERITY_INFO,
                            "AI审判标准偏高",
                            f"AI交易审判在震荡市的评分要求(>={tj_threshold}分)远高于系统实际标准({ud_base}分)。"
                            f"可能导致AI过于保守地拒绝交易信号。",
                            evidence=f"TradeJudge prompt: volatile≥{tj_threshold}; UD base={ud_base}",
                            fix_hint="建议将AI审判的评分标准与系统实际标准对齐，避免过度保守",
                            category="threshold_conflict"
                        ))
        except Exception as e:
            logger.warning(f"LogicAuditor threshold check failed: {e}")

    def _check_duplicate_rules(self, report: InspectionReport):
        try:
            src = self._read_file_full("server/titan_autopilot.py")
            if not src:
                return

            lines = src.split('\n')
            volatile_checks = []
            for i, line in enumerate(lines):
                if 'volatile' in line and 'signal_score' in line and '<' in line:
                    volatile_checks.append((i + 1, line.strip()))

            if len(volatile_checks) > 1:
                evidence = "\n".join(f"Line {ln}: {code}" for ln, code in volatile_checks)
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"信号拦截逻辑重复({len(volatile_checks)}处)",
                    f"系统在{len(volatile_checks)}个不同位置检查同一类信号条件，"
                    f"可能导致一个信号被重复拦截和记录，影响拦截统计准确性。",
                    evidence=evidence,
                    fix_hint="建议合并重复的检查逻辑，确保每个信号只被检查和记录一次",
                    category="duplicate_logic"
                ))
        except Exception as e:
            logger.warning(f"LogicAuditor duplicate check failed: {e}")

    def _check_parameter_consistency(self, report: InspectionReport):
        try:
            api_src = self._read_file_full("server/api.py")
            if not api_src:
                return

            api_max_pos = None
            match = re.search(r'MAX_POSITIONS\s*=\s*(\d+)', api_src)
            if match:
                api_max_pos = int(match.group(1))

            gov_data = self._load_json("data/titan_governor.json")
            if gov_data and api_max_pos:
                gov_max = gov_data.get("config", {}).get("max_positions")
                if gov_max and gov_max != api_max_pos:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_CRITICAL,
                        "最大持仓数量不一致",
                        f"系统两处设定的最大持仓限制不同：一处设为{api_max_pos}个，另一处设为{gov_max}个。"
                        f"这可能导致持仓管理混乱。",
                        evidence=f"api.py: MAX_POSITIONS={api_max_pos}; governor.json: max_positions={gov_max}",
                        fix_hint=f"建议统一最大持仓设置为{api_max_pos}个",
                        category="parameter_drift"
                    ))

            coord_data = self._load_json("data/titan_coordinator.json")
            if coord_data:
                coord_max = coord_data.get("recommendations", {}).get("max_concurrent_positions")
                if coord_max and api_max_pos and coord_max != api_max_pos:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_INFO,
                        "协调器max_positions与全局不一致",
                        f"Coordinator建议max_concurrent_positions={coord_max}，全局MAX_POSITIONS={api_max_pos}",
                        evidence=f"coordinator: {coord_max}; api: {api_max_pos}",
                        category="parameter_drift"
                    ))
        except Exception as e:
            logger.warning(f"LogicAuditor parameter check failed: {e}")

    def _check_risk_parameter_alignment(self, report: InspectionReport):
        try:
            constitution_data = self._load_json("data/titan_constitution.json")
            mc_data = self._load_json("data/titan_monte_carlo.json")
            if not constitution_data or not mc_data:
                return

            mc_constraints = mc_data.get("optimized_constraints", mc_data.get("constraints", {}))
            const_max_dd = constitution_data.get("max_drawdown_pct",
                            constitution_data.get("breakers", {}).get("max_drawdown_pct"))
            mc_dd_trigger = mc_constraints.get("drawdown_trigger")

            if const_max_dd and mc_dd_trigger:
                if abs(const_max_dd - mc_dd_trigger) > 2:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING,
                        "回撤触发值不一致",
                        f"Constitution max_drawdown={const_max_dd}% vs MC drawdown_trigger={mc_dd_trigger}%",
                        evidence=f"constitution: {const_max_dd}%; MC: {mc_dd_trigger}%",
                        fix_hint="MC模拟的drawdown_trigger应与Constitution保持一致",
                        category="risk_alignment"
                    ))
        except Exception as e:
            logger.warning(f"LogicAuditor risk alignment check failed: {e}")

    def _read_file_section(self, filepath, pattern):
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            matches = re.findall(f'.*{pattern}.*', content)
            return '\n'.join(matches) if matches else ""
        except:
            return ""

    def _read_file_full(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except:
            return ""

    def _load_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None


class ConfigSentinel:
    NAME = "config_sentinel"
    DISPLAY = "配置哨兵"

    CONFIG_FILES = [
        "data/titan_governor.json",
        "data/titan_coordinator.json",
        "data/titan_constitution.json",
        "data/titan_monte_carlo.json",
        "data/titan_autopilot.json",
        "data/titan_risk_budget.json",
        "data/titan_signal_quality.json",
        "data/titan_feedback.json",
        "data/titan_memory_bank.json",
        "data/titan_grid.json",
        "data/titan_coordinator.json",
    ]

    def run(self, report: InspectionReport):
        report.inspectors_run.append(self.NAME)
        self._check_empty_files(report)
        self._check_stale_files(report)
        self._check_file_integrity(report)
        self._check_config_vs_defaults(report)

    def _check_empty_files(self, report: InspectionReport):
        for fp in self.CONFIG_FILES:
            if not os.path.exists(fp):
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"配置文件缺失: {os.path.basename(fp)}",
                    f"文件 {fp} 不存在，相关模块可能使用默认值运行",
                    category="missing_file"
                ))
                continue

            try:
                size = os.path.getsize(fp)
                if size <= 5:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING,
                        f"配置文件近空: {os.path.basename(fp)} ({size}字节)",
                        f"文件 {fp} 几乎为空，模块可能无法加载持久化状态",
                        evidence=f"文件大小: {size}字节",
                        fix_hint="检查该模块是否正确初始化并保存状态",
                        category="empty_file"
                    ))
            except:
                pass

    def _check_stale_files(self, report: InspectionReport):
        stale_threshold = 24 * 3600
        critical_files = [
            ("data/titan_governor.json", "Governor策略状态", 6),
            ("data/titan_feedback.json", "反馈引擎", 24),
            ("data/titan_signal_quality.json", "信号质量评估", 6),
        ]

        for fp, name, max_hours in critical_files:
            if not os.path.exists(fp):
                continue
            try:
                mtime = os.path.getmtime(fp)
                age_hours = (time.time() - mtime) / 3600
                if age_hours > max_hours:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING if age_hours < 48 else SEVERITY_CRITICAL,
                        f"数据过期: {name}",
                        f"{fp} 上次更新在 {age_hours:.1f} 小时前（阈值 {max_hours}h）",
                        evidence=f"最后修改: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')}",
                        fix_hint=f"检查{name}模块是否正常运行和保存",
                        category="stale_data"
                    ))
            except:
                pass

    def _check_file_integrity(self, report: InspectionReport):
        for fp in self.CONFIG_FILES:
            if not os.path.exists(fp):
                continue
            try:
                with open(fp, 'r') as f:
                    content = f.read()
                if content.strip():
                    json.loads(content)
            except json.JSONDecodeError as e:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_CRITICAL,
                    f"JSON损坏: {os.path.basename(fp)}",
                    f"文件 {fp} JSON格式错误: {str(e)[:100]}",
                    evidence=str(e),
                    fix_hint="检查原子写入是否正常工作",
                    category="corrupted_file"
                ))
            except:
                pass

    def _check_config_vs_defaults(self, report: InspectionReport):
        try:
            gov_data = self._load_json("data/titan_governor.json")
            if gov_data:
                config = gov_data.get("config", {})
                if not config:
                    return
                expected = {
                    "score_threshold_normal": 78,
                }
                for key, expected_val in expected.items():
                    if key not in config:
                        continue
                    actual = config[key]
                    if actual != expected_val:
                        report.add(InspectionFinding(
                            self.NAME, SEVERITY_CRITICAL,
                            f"Governor配置偏移: {key}",
                            f"Governor文件中{key}={actual}，但代码期望值={expected_val}",
                            evidence=f"文件值: {actual}; 期望值: {expected_val}",
                            fix_hint="Governor._sync_system_constants()应在启动时修正此值",
                            category="config_drift"
                        ))
        except Exception as e:
            logger.warning(f"ConfigSentinel config check failed: {e}")

    def _load_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None


class PerformanceDoctor:
    NAME = "performance_doctor"
    DISPLAY = "性能诊断师"

    def run(self, report: InspectionReport):
        report.inspectors_run.append(self.NAME)
        self._check_win_rate_trend(report)
        self._check_signal_pass_rate(report)
        self._check_blocked_trade_patterns(report)
        self._check_strategy_performance(report)
        self._check_sentiment_btc_trend_param(report)
        self._check_ml_multiplier_sanity(report)

    def _check_win_rate_trend(self, report: InspectionReport):
        try:
            trades = self._load_json("data/titan_trades.json")
            if not trades or not isinstance(trades, list):
                return

            recent = trades[-20:]
            if len(recent) < 5:
                return

            wins = sum(1 for t in recent if t.get('pnl_pct', 0) > 0)
            win_rate = wins / len(recent) * 100

            if win_rate < 25:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_CRITICAL,
                    f"严重低胜率: 最近{len(recent)}笔胜率{win_rate:.0f}%",
                    f"胜率远低于45%目标。最近{len(recent)}笔交易中仅{wins}笔盈利。",
                    evidence=f"近{len(recent)}笔: {wins}胜/{len(recent)-wins}负 = {win_rate:.1f}%",
                    fix_hint="检查信号质量、入场时机、止损设置是否需要调整",
                    category="low_win_rate"
                ))
            elif win_rate < 35:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"低胜率预警: 最近{len(recent)}笔胜率{win_rate:.0f}%",
                    f"胜率低于35%，需关注。最近{len(recent)}笔中{wins}笔盈利。",
                    evidence=f"近{len(recent)}笔: {wins}胜/{len(recent)-wins}负 = {win_rate:.1f}%",
                    category="low_win_rate"
                ))

            total_pnl = sum(t.get('pnl_pct', 0) for t in recent)
            avg_win = 0
            avg_loss = 0
            win_trades = [t.get('pnl_pct', 0) for t in recent if t.get('pnl_pct', 0) > 0]
            loss_trades = [t.get('pnl_pct', 0) for t in recent if t.get('pnl_pct', 0) <= 0]
            if win_trades:
                avg_win = sum(win_trades) / len(win_trades)
            if loss_trades:
                avg_loss = abs(sum(loss_trades) / len(loss_trades))

            if avg_win > 0 and avg_loss > 0:
                profit_factor = avg_win / avg_loss
                if profit_factor < 1.0:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING,
                        f"盈亏比不足: {profit_factor:.2f}",
                        f"平均盈利{avg_win:.2f}% vs 平均亏损{avg_loss:.2f}%，盈亏比<1.0",
                        evidence=f"avg_win={avg_win:.2f}% avg_loss={avg_loss:.2f}% ratio={profit_factor:.2f}",
                        fix_hint="考虑放宽止盈或收紧止损",
                        category="poor_risk_reward"
                    ))
        except Exception as e:
            logger.warning(f"PerformanceDoctor win rate check failed: {e}")

    def _check_signal_pass_rate(self, report: InspectionReport):
        try:
            autopilot = self._load_json("data/titan_autopilot.json")
            if not autopilot:
                return

            blocked = autopilot.get("blocked_trades", [])
            cutoff = (datetime.now() - timedelta(days=7)).isoformat()
            recent_blocked = [b for b in blocked if b.get("time", "") >= cutoff]

            trades = self._load_json("data/titan_trades.json")
            recent_trades = []
            if trades:
                cutoff_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                recent_trades = [t for t in trades if t.get('open_time', '') >= cutoff_str]

            total_signals = len(recent_blocked) + len(recent_trades)
            if total_signals > 10:
                pass_rate = len(recent_trades) / total_signals * 100
                if pass_rate < 5:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_CRITICAL,
                        f"信号通过率极低: {pass_rate:.1f}%",
                        f"过去7天{total_signals}个信号中仅{len(recent_trades)}个通过，{len(recent_blocked)}个被拦截。"
                        f"可能存在门槛叠加导致的过度过滤。",
                        evidence=f"通过: {len(recent_trades)}; 拦截: {len(recent_blocked)}; 通过率: {pass_rate:.1f}%",
                        fix_hint="检查SignalGate、UnifiedDecision、Governor的门槛是否叠加过严",
                        category="low_pass_rate"
                    ))
                elif pass_rate < 15:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING,
                        f"信号通过率偏低: {pass_rate:.1f}%",
                        f"过去7天{len(recent_blocked)}个信号被拦截，{len(recent_trades)}个通过",
                        evidence=f"通过率: {pass_rate:.1f}%",
                        category="low_pass_rate"
                    ))
        except Exception as e:
            logger.warning(f"PerformanceDoctor pass rate check failed: {e}")

    def _check_blocked_trade_patterns(self, report: InspectionReport):
        try:
            autopilot = self._load_json("data/titan_autopilot.json")
            if not autopilot:
                return

            blocked = autopilot.get("blocked_trades", [])
            cutoff = (datetime.now() - timedelta(days=3)).isoformat()
            recent = [b for b in blocked if b.get("time", "") >= cutoff]

            if not recent:
                return

            reason_counts = {}
            for b in recent:
                reason = b.get("reason", "unknown")
                core = reason.split("(")[0].strip() if "(" in reason else reason[:50]
                reason_counts[core] = reason_counts.get(core, 0) + 1

            top_reason = max(reason_counts.items(), key=lambda x: x[1])
            if top_reason[1] > len(recent) * 0.5:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"拦截集中在单一原因: {top_reason[0][:40]}",
                    f"过去3天{len(recent)}个被拦截信号中{top_reason[1]}个({top_reason[1]/len(recent)*100:.0f}%)因同一原因被拦截。"
                    f"可能是某个门槛设置过于严格。",
                    evidence=f"Top原因: {top_reason[0]} ({top_reason[1]}/{len(recent)}次)",
                    fix_hint="考虑调整该特定拦截规则的阈值",
                    category="blocked_pattern"
                ))
        except Exception as e:
            logger.warning(f"PerformanceDoctor blocked pattern check failed: {e}")

    def _check_strategy_performance(self, report: InspectionReport):
        try:
            trades = self._load_json("data/titan_trades.json")
            if not trades or len(trades) < 10:
                return

            by_strategy = {}
            for t in trades[-50:]:
                s = t.get("strategy", "unknown")
                by_strategy.setdefault(s, []).append(t.get("pnl_pct", 0))

            for strategy, pnls in by_strategy.items():
                if len(pnls) >= 5:
                    wins = sum(1 for p in pnls if p > 0)
                    wr = wins / len(pnls) * 100
                    total = sum(pnls)
                    if wr < 20 and total < -2:
                        report.add(InspectionFinding(
                            self.NAME, SEVERITY_WARNING,
                            f"策略持续亏损: {strategy}",
                            f"策略 {strategy} 最近{len(pnls)}笔胜率{wr:.0f}%，累计亏损{total:.2f}%",
                            evidence=f"{strategy}: {wins}/{len(pnls)} wins, total={total:.2f}%",
                            fix_hint=f"考虑降低{strategy}策略权重或暂停该策略",
                            category="strategy_underperform"
                        ))
        except Exception as e:
            logger.warning(f"PerformanceDoctor strategy check failed: {e}")

    def _check_sentiment_btc_trend_param(self, report: InspectionReport):
        try:
            trades = self._load_json("data/titan_trades.json")
            if not trades:
                return
            cutoff = "2026-02-24"
            recent_post_fix = []
            for t in trades:
                created = t.get("created_at", t.get("open_time", ""))
                if isinstance(created, str) and created >= cutoff:
                    recent_post_fix.append(t)
            recent = recent_post_fix[-10:]
            if not recent:
                return
            missing = 0
            for t in recent:
                top_val = t.get("btc_macro_trend_at_entry")
                dc = t.get("decision_chain", {})
                if isinstance(dc, str):
                    try:
                        dc = json.loads(dc)
                    except:
                        dc = {}
                dc_val = dc.get("btc_macro_trend_at_entry") or dc.get("btc_macro_trend")
                if not top_val and not dc_val:
                    missing += 1
            if missing > 3:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_CRITICAL,
                    f"BTC趋势传参断裂: 最近10笔中{missing}笔缺失btc_macro_trend_at_entry",
                    f"情绪维度修复依赖btc_macro_trend传参，{missing}/10笔缺失说明传参链断裂",
                    evidence=f"缺失{missing}/10笔btc_macro_trend_at_entry",
                    fix_hint="检查api.py中score()调用是否传入btc_macro_trend参数",
                    category="sentiment_btc_trend_param"
                ))
            elif missing > 0:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"BTC趋势传参部分缺失: {missing}/10笔",
                    f"少量交易缺失btc_macro_trend_at_entry，可能是旧交易记录",
                    evidence=f"缺失{missing}/10笔",
                    category="sentiment_btc_trend_param"
                ))
        except Exception as e:
            logger.warning(f"PerformanceDoctor btc trend param check failed: {e}")

    def _check_ml_multiplier_sanity(self, report: InspectionReport):
        try:
            trades = self._load_json("data/titan_trades.json")
            if not trades or len(trades) < 10:
                return
            recent = trades[-20:]
            high_conf = []
            all_sizes = []
            for t in recent:
                size = t.get("position_size_pct", 0)
                conf = t.get("ml_confidence", 0)
                all_sizes.append(size)
                if conf and conf > 80:
                    high_conf.append(size)
            if not high_conf or not all_sizes:
                return
            avg_all = sum(all_sizes) / len(all_sizes)
            avg_high = sum(high_conf) / len(high_conf)
            if avg_all > 0 and avg_high > avg_all * 0.85:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_CRITICAL,
                    f"ML高置信度仓位异常偏大: 80+平均{avg_high:.2f}% vs 全部平均{avg_all:.2f}%",
                    f"ml_confidence>80的交易仓位应小于平均水平的85%，当前反而偏大，"
                    f"说明_ml_multiplier修复可能未生效",
                    evidence=f"80+仓位: {avg_high:.2f}%, 全部平均: {avg_all:.2f}%, 比值: {avg_high/avg_all:.2f}",
                    fix_hint="检查titan_capital_sizer.py的_ml_multiplier()是否正确衰减80+区间",
                    category="ml_multiplier_sanity"
                ))
        except Exception as e:
            logger.warning(f"PerformanceDoctor ml multiplier sanity check failed: {e}")

    def _load_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None


class AnomalyPatrol:
    NAME = "anomaly_patrol"
    DISPLAY = "异常巡检员"

    def run(self, report: InspectionReport):
        report.inspectors_run.append(self.NAME)
        self._check_silent_modules(report)
        self._check_model_freshness(report)
        self._check_grid_health(report)
        self._check_memory_bank_growth(report)
        self._check_llm_telemetry(report)

    def _check_silent_modules(self, report: InspectionReport):
        modules_to_check = [
            ("data/titan_feedback.json", "反馈引擎", "accuracy_history", 48),
            ("data/titan_memory_bank.json", "记忆银行", "insights", 72),
            ("data/deep_evolution_log.json", "深度进化", None, 48),
        ]

        for filepath, name, list_key, max_hours_silent in modules_to_check:
            if not os.path.exists(filepath):
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"模块数据缺失: {name}",
                    f"{filepath} 文件不存在",
                    category="silent_module"
                ))
                continue

            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)

                if list_key:
                    records = data.get(list_key, [])
                elif isinstance(data, list):
                    records = data
                else:
                    continue

                if not records:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING,
                        f"模块无数据: {name}",
                        f"{name} 的记录列表为空，可能未正常运行",
                        category="silent_module"
                    ))
                    continue

                last_record = records[-1]
                last_ts = last_record.get("timestamp", last_record.get("time", ""))
                if last_ts:
                    try:
                        if 'T' in str(last_ts):
                            last_dt = datetime.fromisoformat(str(last_ts).replace('Z', ''))
                        else:
                            last_dt = datetime.strptime(str(last_ts)[:19], '%Y-%m-%d %H:%M:%S')
                        age_hours = (datetime.now() - last_dt).total_seconds() / 3600
                        if age_hours > max_hours_silent:
                            report.add(InspectionFinding(
                                self.NAME, SEVERITY_WARNING,
                                f"模块静默: {name} ({age_hours:.0f}h无新数据)",
                                f"{name}最后一条记录在{age_hours:.0f}小时前，超过{max_hours_silent}h阈值",
                                evidence=f"最后记录: {last_ts}",
                                fix_hint=f"检查{name}模块是否被正常调用",
                                category="silent_module"
                            ))
                    except:
                        pass
            except:
                pass

    def _check_model_freshness(self, report: InspectionReport):
        models = [
            ("data/titan_ml_model.pkl", "Alpha ML模型", 72),
            ("data/titan_mm_model.pkl", "MM资金管理模型", 120),
        ]

        for filepath, name, max_age_hours in models:
            if not os.path.exists(filepath):
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING,
                    f"模型缺失: {name}",
                    f"{filepath} 不存在，ML预测可能使用默认值",
                    category="model_issue"
                ))
                continue

            mtime = os.path.getmtime(filepath)
            age_hours = (time.time() - mtime) / 3600
            if age_hours > max_age_hours:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_WARNING if age_hours < 168 else SEVERITY_CRITICAL,
                    f"模型过期: {name} ({age_hours:.0f}h未更新)",
                    f"{name}上次训练在{age_hours:.0f}小时前。模型可能不反映近期市场状况。",
                    evidence=f"最后更新: {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')}",
                    fix_hint="触发云端重训练或检查Modal训练任务是否正常",
                    category="model_stale"
                ))

    def _check_grid_health(self, report: InspectionReport):
        try:
            grid_data = self._load_json("data/titan_grid.json")
            if not grid_data:
                return

            active = grid_data.get("active_grids", {})
            for sym, g in active.items():
                filled_buys = g.get("filled_buys", 0)
                filled_sells = g.get("filled_sells", 0)
                if filled_buys == 0 and filled_sells == 0:
                    orders = g.get("orders", [])
                    filled_buys = sum(1 for o in orders if o.get("side") == "buy" and o.get("filled"))
                    filled_sells = sum(1 for o in orders if o.get("side") == "sell" and o.get("filled"))
                total_fills = filled_buys + filled_sells
                created = g.get("created_at", "")

                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace('Z', ''))
                        age_hours = (datetime.now() - created_dt).total_seconds() / 3600
                        if age_hours > 48 and total_fills == 0:
                            report.add(InspectionFinding(
                                self.NAME, SEVERITY_WARNING,
                                f"网格无成交: {sym} 运行{age_hours:.0f}h",
                                f"{sym}网格已运行{age_hours:.0f}小时但零成交，网格线可能设置不合理或市场偏离范围",
                                evidence=f"创建: {created[:16]}, total_fills=0",
                                fix_hint=f"检查{sym}网格的价格范围是否覆盖当前价格",
                                category="grid_idle"
                            ))
                        elif age_hours > 72 and total_fills < 3:
                            report.add(InspectionFinding(
                                self.NAME, SEVERITY_INFO,
                                f"网格低活跃度: {sym} 运行{age_hours:.0f}h仅{total_fills}笔成交",
                                f"{sym}网格活跃度偏低，可能需要调整网格间距或范围",
                                evidence=f"创建: {created[:16]}, fills={total_fills} (buys={filled_buys}, sells={filled_sells})",
                                fix_hint=f"考虑缩窄{sym}网格范围或增加网格密度",
                                category="grid_low_activity"
                            ))
                    except:
                        pass
        except Exception as e:
            logger.warning(f"AnomalyPatrol grid check failed: {e}")

    def _check_memory_bank_growth(self, report: InspectionReport):
        try:
            mb_data = self._load_json("data/titan_memory_bank.json")
            if not mb_data:
                return

            insights = mb_data.get("insights", [])
            if len(insights) > 500:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_INFO,
                    f"记忆银行膨胀: {len(insights)}条记录",
                    f"记忆银行已累积{len(insights)}条洞察，可能需要清理旧记录以保持效率",
                    fix_hint="考虑归档超过30天的旧记录",
                    category="data_growth"
                ))
        except:
            pass

    def _check_llm_telemetry(self, report: InspectionReport):
        try:
            telemetry_path = "data/titan_llm_telemetry.json"
            if not os.path.exists(telemetry_path):
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_INFO,
                    "LLM遥测文件缺失",
                    "AI调用统计没有持久化，重启后遥测数据丢失",
                    fix_hint="考虑在LLMTelemetry中添加定期持久化",
                    category="monitoring_gap"
                ))
        except:
            pass

    def _load_json(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except:
            return None


class ArchitectureAdvisor:
    NAME = "architecture_advisor"
    DISPLAY = "架构顾问"

    def run(self, report: InspectionReport):
        report.inspectors_run.append(self.NAME)
        self._check_module_count(report)
        self._check_file_sizes(report)
        self._check_circular_imports(report)

    def _check_module_count(self, report: InspectionReport):
        try:
            titan_files = [f for f in os.listdir("server") if f.startswith("titan_") and f.endswith(".py")]
            if len(titan_files) > 40:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_INFO,
                    f"模块数量过多: {len(titan_files)}个Titan文件",
                    f"server/目录下有{len(titan_files)}个titan_*.py文件，模块数量较多。"
                    f"建议评估是否有可以合并的相似模块。",
                    evidence=f"模块总数: {len(titan_files)}",
                    fix_hint="考虑将功能相近的模块合并（如多个risk相关模块）",
                    category="complexity"
                ))
        except:
            pass

    def _check_file_sizes(self, report: InspectionReport):
        try:
            large_files = []
            for f in os.listdir("server"):
                if f.endswith(".py"):
                    fp = os.path.join("server", f)
                    lines = sum(1 for _ in open(fp, 'r'))
                    if lines > 1000:
                        large_files.append((f, lines))

            for f, lines in sorted(large_files, key=lambda x: -x[1])[:5]:
                if lines > 2000:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_WARNING,
                        f"超大文件: {f} ({lines}行)",
                        f"文件 server/{f} 有{lines}行代码，建议拆分以提高可维护性",
                        evidence=f"{f}: {lines} lines",
                        fix_hint="将相对独立的类或函数提取到单独模块",
                        category="large_file"
                    ))
                elif lines > 1000:
                    report.add(InspectionFinding(
                        self.NAME, SEVERITY_INFO,
                        f"大文件: {f} ({lines}行)",
                        f"server/{f} 超过1000行，关注可维护性",
                        evidence=f"{f}: {lines} lines",
                        category="large_file"
                    ))
        except:
            pass

    def _check_circular_imports(self, report: InspectionReport):
        try:
            import_map = {}
            for f in os.listdir("server"):
                if not f.endswith(".py"):
                    continue
                fp = os.path.join("server", f)
                imports = set()
                try:
                    with open(fp, 'r') as fh:
                        for line in fh:
                            line = line.strip()
                            if line.startswith("from server.titan_") or line.startswith("import server.titan_"):
                                match = re.search(r'titan_\w+', line)
                                if match:
                                    imports.add(match.group())
                except:
                    pass
                module_name = f.replace(".py", "")
                import_map[module_name] = imports

            for mod_a, imports_a in import_map.items():
                for mod_b in imports_a:
                    if mod_b in import_map and mod_a in import_map.get(mod_b, set()):
                        report.add(InspectionFinding(
                            self.NAME, SEVERITY_INFO,
                            f"双向依赖: {mod_a} <-> {mod_b}",
                            f"模块{mod_a}和{mod_b}互相导入，可能导致循环依赖问题",
                            category="circular_dependency"
                        ))
        except:
            pass


class BinanceReadinessAssessor:
    NAME = "binance_readiness"
    DISPLAY = "币安就绪评估员"

    BINANCE_CHECKLIST = {
        "order_execution": {
            "title": "订单执行",
            "checks": [
                ("order_placement", "下单接口 (市价/限价/止损单)", "实盘需要：市价单(MARKET)、限价单(LIMIT)、止损限价单(STOP_LOSS_LIMIT)、OCO订单"),
                ("order_cancel", "撤单接口", "批量撤单+单个撤单+条件撤单"),
                ("order_status", "订单状态查询", "实时查询订单填充状态、部分成交处理"),
                ("order_amendment", "订单修改", "修改止损价/止盈价/数量而不撤单重挂"),
            ],
        },
        "position_management": {
            "title": "持仓管理",
            "checks": [
                ("position_sync", "仓位同步", "与币安实际持仓实时同步，防止本地状态与交易所不一致"),
                ("balance_check", "余额检查", "下单前验证可用余额，包含手续费预扣"),
                ("leverage_control", "杠杆控制", "合约交易的杠杆设置和管理"),
                ("margin_mode", "保证金模式", "逐仓/全仓模式切换和管理"),
            ],
        },
        "risk_controls": {
            "title": "风险控制",
            "checks": [
                ("emergency_close", "紧急平仓", "一键平仓所有持仓的紧急机制"),
                ("rate_limiting", "API限频", "遵守币安API限速（1200次/分钟），防止IP被封"),
                ("error_handling", "错误处理", "网络断开/API错误/订单拒绝的重试和降级逻辑"),
                ("kill_switch", "熔断开关", "异常情况下立即停止所有交易活动"),
            ],
        },
        "account_security": {
            "title": "账户安全",
            "checks": [
                ("api_key_management", "API密钥管理", "密钥加密存储，权限最小化（只读+现货交易，禁止提币）"),
                ("ip_whitelist", "IP白名单", "API密钥绑定服务器IP"),
                ("signature_verify", "签名验证", "HMAC-SHA256请求签名"),
            ],
        },
        "data_sync": {
            "title": "数据同步",
            "checks": [
                ("websocket_stream", "WebSocket实时数据", "用户数据流（订单更新、余额变动）、行情推送"),
                ("trade_reconciliation", "交易对账", "定期将本地记录与币安历史交易对账"),
                ("funding_rate", "资金费率同步", "实时获取和扣除资金费率（合约交易）"),
            ],
        },
        "paper_to_live": {
            "title": "模拟→实盘过渡",
            "checks": [
                ("dry_run_mode", "模拟运行模式", "可在实盘API上运行但不实际下单的调试模式"),
                ("gradual_rollout", "渐进式上线", "从小资金开始，逐步增加交易金额"),
                ("pnl_comparison", "盈亏对比", "模拟盘和实盘结果对比验证"),
                ("slippage_model", "滑点模型", "模拟盘需加入滑点模拟以更接近实盘"),
            ],
        },
    }

    def run(self, report: InspectionReport):
        report.inspectors_run.append(self.NAME)
        self._assess_current_readiness(report)
        self._check_existing_exchange_code(report)
        self._generate_upgrade_roadmap(report)

    def _assess_current_readiness(self, report: InspectionReport):
        ready_count = 0
        partial_count = 0
        missing_count = 0

        has_ccxt = self._check_import_exists("ccxt")
        has_paper_trader = os.path.exists("server/titan_paper_trader.py")
        has_order_engine = os.path.exists("server/titan_order_engine.py")
        has_constitution = os.path.exists("server/titan_constitution.py")
        has_risk_matrix = os.path.exists("server/titan_risk_matrix.py")

        assessment = {
            "order_placement": "partial" if has_order_engine else "missing",
            "order_cancel": "partial" if has_order_engine else "missing",
            "order_status": "partial" if has_paper_trader else "missing",
            "position_sync": "partial" if has_paper_trader else "missing",
            "balance_check": "partial" if has_paper_trader else "missing",
            "emergency_close": "ready" if has_constitution else "missing",
            "rate_limiting": "missing",
            "error_handling": "partial",
            "kill_switch": "ready" if has_constitution else "missing",
            "api_key_management": "missing",
            "websocket_stream": "missing",
            "trade_reconciliation": "missing",
            "dry_run_mode": "ready" if has_paper_trader else "missing",
            "slippage_model": "missing",
        }

        for key, status in assessment.items():
            if status == "ready":
                ready_count += 1
            elif status == "partial":
                partial_count += 1
            else:
                missing_count += 1

        total = ready_count + partial_count + missing_count
        readiness_pct = (ready_count + partial_count * 0.5) / max(total, 1) * 100

        report.add(InspectionFinding(
            self.NAME, SEVERITY_INFO,
            f"币安就绪度评估: {readiness_pct:.0f}%",
            f"就绪: {ready_count}项 | 部分就绪: {partial_count}项 | 缺失: {missing_count}项\n"
            f"当前系统以纸盘交易为主，已有PaperTrader和OrderEngine基础框架，"
            f"但缺少币安API直连、WebSocket实时流、限频控制、密钥管理等关键实盘组件。",
            evidence=f"ready={ready_count} partial={partial_count} missing={missing_count} score={readiness_pct:.0f}%",
            category="binance_readiness"
        ))

    def _check_existing_exchange_code(self, report: InspectionReport):
        try:
            exchange_refs = []
            for f in os.listdir("server"):
                if not f.endswith(".py"):
                    continue
                fp = os.path.join("server", f)
                try:
                    with open(fp, 'r') as fh:
                        content = fh.read()
                    if 'binance' in content.lower() or 'ccxt' in content.lower():
                        exchange_refs.append(f)
                except:
                    pass

            if exchange_refs:
                report.add(InspectionFinding(
                    self.NAME, SEVERITY_INFO,
                    f"已有交易所相关代码: {len(exchange_refs)}个文件",
                    f"文件: {', '.join(exchange_refs)}",
                    evidence=f"含binance/ccxt引用的文件: {exchange_refs}",
                    category="binance_existing"
                ))
        except:
            pass

    def _generate_upgrade_roadmap(self, report: InspectionReport):
        phases = [
            ("Phase 1: API连接层", [
                "实现BinanceConnector类：REST API封装 + HMAC签名",
                "WebSocket用户数据流：订单更新/余额变动实时推送",
                "API限频管理器：令牌桶算法，遵守1200次/分限制",
            ]),
            ("Phase 2: 订单引擎升级", [
                "PaperTrader→LiveTrader适配：统一接口，可切换模式",
                "订单类型支持：MARKET/LIMIT/STOP_LOSS_LIMIT/OCO",
                "部分成交处理 + 订单状态机",
            ]),
            ("Phase 3: 风控加固", [
                "实盘紧急平仓机制：一键平所有仓",
                "仓位对账：每分钟与交易所同步真实持仓",
                "滑点预估和手续费精确计算",
            ]),
            ("Phase 4: 灰度上线", [
                "影子交易模式：实盘API但不实际下单，对比纸盘结果",
                "小资金验证：$500起步，逐步扩大",
                "实盘vs纸盘盈亏差异监控",
            ]),
        ]

        roadmap_text = ""
        for phase, items in phases:
            roadmap_text += f"\n{phase}:\n"
            for item in items:
                roadmap_text += f"  - {item}\n"

        report.add(InspectionFinding(
            self.NAME, SEVERITY_SUGGESTION,
            "币安实盘升级路线图",
            roadmap_text.strip(),
            fix_hint="建议按Phase 1→4顺序实施，每个Phase完成后进行充分测试再进入下一阶段",
            category="binance_roadmap"
        ))

    def _check_import_exists(self, module_name):
        try:
            for f in os.listdir("server"):
                if not f.endswith(".py"):
                    continue
                with open(os.path.join("server", f), 'r') as fh:
                    if f"import {module_name}" in fh.read():
                        return True
            return False
        except:
            return False


class TitanSelfInspector:
    INSPECTORS = [
        LogicAuditor,
        ConfigSentinel,
        PerformanceDoctor,
        AnomalyPatrol,
        ArchitectureAdvisor,
        BinanceReadinessAssessor,
    ]

    def __init__(self):
        self.last_report: Optional[InspectionReport] = None
        self._load_history()

    def _load_history(self):
        try:
            if os.path.exists(INSPECTION_REPORT_PATH):
                with open(INSPECTION_REPORT_PATH, 'r') as f:
                    data = json.load(f)
                self.history = data.get("reports", [])
            else:
                self.history = []
        except:
            self.history = []

    def run_all(self, use_ai_summary: bool = True) -> Dict:
        report = InspectionReport()
        logger.info("=== 系统自检开始 ===")

        for InspectorClass in self.INSPECTORS:
            try:
                inspector = InspectorClass()
                inspector.run(report)
                logger.info(f"[自检] {inspector.DISPLAY} 完成")
            except Exception as e:
                logger.error(f"[自检] {InspectorClass.NAME} 异常: {e}")
                report.add(InspectionFinding(
                    InspectorClass.NAME, SEVERITY_CRITICAL,
                    f"检查器自身异常: {InspectorClass.DISPLAY}",
                    f"运行时错误: {str(e)[:200]}",
                    category="inspector_error"
                ))

        report.finalize()

        if use_ai_summary and report.findings:
            report.ai_summary = self._generate_ai_summary(report)

            findings_by_inspector = {}
            for f in report.findings:
                if f.inspector not in findings_by_inspector:
                    findings_by_inspector[f.inspector] = []
                findings_by_inspector[f.inspector].append(f)

            for insp_name, insp_findings in findings_by_inspector.items():
                if any(f.severity in (SEVERITY_CRITICAL, SEVERITY_WARNING) for f in insp_findings):
                    try:
                        analysis = self._generate_inspector_ai_analysis(insp_name, insp_findings)
                        if analysis:
                            report.inspector_analyses[insp_name] = analysis
                    except Exception as e:
                        logger.warning(f"Inspector AI analysis failed for {insp_name}: {e}")

        self.last_report = report

        report_dict = report.to_dict()
        self._save_report(report_dict)

        critical_count = report_dict["by_severity"]["critical"]
        warning_count = report_dict["by_severity"]["warning"]
        logger.info(f"=== 自检完成: {len(report.findings)}项发现 (严重:{critical_count} 警告:{warning_count}) ===")

        self._push_critical_to_learning_journal(report)

        return report_dict

    def run_single(self, inspector_name: str, use_ai_summary: bool = True) -> Dict:
        report = InspectionReport()

        inspector_map = {cls.NAME: cls for cls in self.INSPECTORS}
        if inspector_name not in inspector_map:
            return {"error": f"未知检查器: {inspector_name}", "available": list(inspector_map.keys())}

        InspectorClass = inspector_map[inspector_name]
        inspector = InspectorClass()
        inspector.run(report)
        report.finalize()

        if use_ai_summary and report.findings:
            analysis = self._generate_inspector_ai_analysis(inspector_name, report.findings)
            if analysis:
                report.inspector_analyses[inspector_name] = analysis
            report.ai_summary = analysis or ""

        report_dict = report.to_dict()
        return report_dict

    def _push_critical_to_learning_journal(self, report: InspectionReport):
        try:
            critical_findings = [f for f in report.findings if f.severity in (SEVERITY_CRITICAL, SEVERITY_WARNING)]
            if not critical_findings:
                return

            from server.titan_db import db_connection
            summary_lines = [f"[自检{report.start_time.strftime('%Y-%m-%d')}] {len(critical_findings)}项严重/警告发现:"]
            for f in critical_findings[:8]:
                title = f.title or f.detail[:60]
                summary_lines.append(f"- [{f.severity}] {f.inspector}: {title}")

            if report.ai_summary:
                summary_lines.append(f"\nAI总结: {report.ai_summary[:200]}")

            content = "\n".join(summary_lines)

            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO learning_journal (source, content, priority, consumed_by_cto)
                    VALUES (%s, %s, %s, false)
                """, ("self_inspection_critical", content, "high"))
                conn.commit()
            logger.info(f"[自检→CTO] 推送{len(critical_findings)}条critical/warning发现到学习日志")
        except Exception as e:
            logger.warning(f"[自检→CTO] 推送学习日志失败(非致命): {e}")

    def _generate_ai_summary(self, report: InspectionReport) -> str:
        try:
            from server.titan_llm_client import chat
            from server.titan_prompt_library import SELF_INSPECTION_DIRECTOR_PROMPT

            findings_text = ""
            for f in report.findings[:20]:
                findings_text += f"[{f.severity}] {f.inspector}|{f.title}: {f.detail[:120]}\n"
                if f.evidence:
                    findings_text += f"  证据: {f.evidence[:80]}\n"

            severity_summary = report.to_dict()["by_severity"]
            context = (
                f"严重度统计: 严重={severity_summary['critical']}, 警告={severity_summary['warning']}, "
                f"信息={severity_summary['info']}, 建议={severity_summary['suggestion']}\n"
                f"检查器运行: {', '.join(report.inspectors_run)}\n"
                f"耗时: {report.to_dict()['duration_seconds']:.1f}秒\n\n"
                f"发现详情:\n{findings_text}"
            )

            messages = [
                {"role": "system", "content": SELF_INSPECTION_DIRECTOR_PROMPT},
                {"role": "user", "content": f"以下是本轮自检结果，请作为自检总监向CEO汇报:\n\n{context}"},
            ]

            result = chat(
                module="self_inspector",
                messages=messages,
                json_mode=False,
                max_tokens=600,
            )
            return result.strip()
        except Exception as e:
            logger.warning(f"AI summary generation failed: {e}")
            critical = sum(1 for f in report.findings if f.severity == SEVERITY_CRITICAL)
            warning = sum(1 for f in report.findings if f.severity == SEVERITY_WARNING)
            return f"自检完成: 发现{len(report.findings)}项问题（严重{critical}项，警告{warning}项）。AI摘要生成失败: {str(e)[:50]}"

    def _generate_inspector_ai_analysis(self, inspector_name: str, findings: List[InspectionFinding]) -> str:
        try:
            from server.titan_llm_client import chat
            from server.titan_prompt_library import (
                LOGIC_AUDITOR_PROMPT, CONFIG_SENTINEL_PROMPT,
                PERFORMANCE_DOCTOR_PROMPT, ANOMALY_PATROL_PROMPT,
                ARCHITECTURE_ADVISOR_PROMPT, BINANCE_READINESS_PROMPT,
            )

            prompt_map = {
                "logic_auditor": LOGIC_AUDITOR_PROMPT,
                "config_sentinel": CONFIG_SENTINEL_PROMPT,
                "performance_doctor": PERFORMANCE_DOCTOR_PROMPT,
                "anomaly_patrol": ANOMALY_PATROL_PROMPT,
                "architecture_advisor": ARCHITECTURE_ADVISOR_PROMPT,
                "binance_readiness": BINANCE_READINESS_PROMPT,
            }

            system_prompt = prompt_map.get(inspector_name)
            if not system_prompt:
                return ""

            findings_text = ""
            for f in findings:
                findings_text += f"[{f.severity}] {f.title}\n  详情: {f.detail[:150]}\n"
                if f.evidence:
                    findings_text += f"  证据: {f.evidence[:100]}\n"
                if f.fix_hint:
                    findings_text += f"  修复建议: {f.fix_hint[:100]}\n"
                findings_text += "\n"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": (
                    f"你作为{inspector_name}刚完成了系统检查，发现了{len(findings)}个问题。\n\n"
                    f"检查结果:\n{findings_text}\n"
                    "请给出你的专业分析：\n"
                    "1. 这些问题中哪个最紧急？\n"
                    "2. 问题之间是否有关联（根因分析）？\n"
                    "3. 建议的修复优先级？\n"
                    "请用中文简洁回答，不超过200字。纯文本输出。"
                )},
            ]

            result = chat(
                module="self_inspector",
                messages=messages,
                json_mode=False,
                max_tokens=350,
            )
            return result.strip()
        except Exception as e:
            logger.warning(f"Inspector AI analysis failed for {inspector_name}: {e}")
            return ""

    def _save_report(self, report_dict: Dict):
        try:
            from server.titan_utils import atomic_json_save
        except ImportError:
            atomic_json_save = None

        self.history.append(report_dict)
        if len(self.history) > 30:
            self.history = self.history[-30:]

        data = {"reports": self.history, "last_updated": datetime.now().isoformat()}

        try:
            if atomic_json_save:
                atomic_json_save(INSPECTION_REPORT_PATH, data)
            else:
                with open(INSPECTION_REPORT_PATH, 'w') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save inspection report: {e}")

    def get_latest_report(self) -> Optional[Dict]:
        if self.last_report:
            return self.last_report.to_dict()
        if self.history:
            return self.history[-1]
        return None

    def get_report_history(self, limit: int = 10) -> List[Dict]:
        return self.history[-limit:]

    def get_available_inspectors(self) -> List[Dict]:
        return [
            {"name": cls.NAME, "display": cls.DISPLAY}
            for cls in self.INSPECTORS
        ]
