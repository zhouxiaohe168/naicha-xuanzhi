import { useState, useEffect } from 'react';
import {
  Brain, Shield, Activity, AlertTriangle, Clock, CheckCircle2,
  Zap, Target, TrendingUp, TrendingDown, Eye, BarChart3,
  Users, Cpu, RefreshCw, ChevronDown, ChevronUp, Gauge, Send, X, Check,
  Search, Bug
} from 'lucide-react';
import { useShield } from '../hooks/useShieldData';
import RiskDashboard from '../components/RiskDashboard';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const fmtTime = (t) => {
  if (!t) return '--';
  try {
    const d = new Date(typeof t === 'number' ? t * 1000 : t);
    return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return '--'; }
};

const severityColor = (s) => {
  if (s === 'high' || s === 'critical') return 'text-red-400 bg-red-500/10 border-red-500/20';
  if (s === 'medium') return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
};

const statusDot = (s) => {
  if (s === 'ok') return 'bg-emerald-400';
  if (s === 'warn' || s === 'warning') return 'bg-amber-400';
  return 'bg-red-400';
};

export default function CTOHeadquarters() {
  const { data, agiData, aiDiagnostic, constitutionStatus, coordinatorData } = useShield();
  const [autopilot, setAutopilot] = useState(null);
  const [expandedCycle, setExpandedCycle] = useState(null);
  const [section, setSection] = useState('cto_report');
  const [expandedDim, setExpandedDim] = useState(null);
  const [resolving, setResolving] = useState({});
  const [ceoNotes, setCeoNotes] = useState({});
  const [briefings, setBriefings] = useState({});
  const [briefingStatus, setBriefingStatus] = useState('idle');
  const [briefingTime, setBriefingTime] = useState(null);
  const [briefingGenerating, setBriefingGenerating] = useState(false);
  const [ctoReport, setCtoReport] = useState(null);
  const [ctoReportTime, setCtoReportTime] = useState(null);
  const [ctoReportGenerating, setCtoReportGenerating] = useState(false);
  const [inspectionReport, setInspectionReport] = useState(null);
  const [inspectionRunning, setInspectionRunning] = useState(false);
  const [expandedFinding, setExpandedFinding] = useState(null);

  useEffect(() => {
    if (section === 'self_inspection' && !inspectionReport) {
      fetch('/api/self-inspection/report').then(r => r.json()).then(d => {
        if (d && d.findings) setInspectionReport(d);
      }).catch(() => {});
    }
  }, [section]);

  const runInspection = async (inspectorName) => {
    setInspectionRunning(true);
    try {
      const url = inspectorName
        ? `/api/self-inspection/run?inspector=${inspectorName}`
        : '/api/self-inspection/run';
      const r = await fetch(url, { method: 'POST' });
      const d = await r.json();
      setInspectionReport(d);
    } catch (e) {
      console.error('Inspection failed:', e);
    } finally {
      setInspectionRunning(false);
    }
  };

  useEffect(() => {
    const fetchAP = async () => {
      try {
        const r = await fetch('/api/autopilot/status');
        const d = await r.json();
        setAutopilot(d);
      } catch {}
    };
    fetchAP();
    const t = setInterval(fetchAP, 30000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    fetch('/api/department-briefings').then(r => r.ok ? r.json() : null).then(d => {
      if (d && d.briefings && Object.keys(d.briefings).length > 0) {
        setBriefings(d.briefings);
        setBriefingStatus(d.status || 'ok');
        setBriefingTime(d.generated_at);
      }
    }).catch(() => {});
    fetch('/api/cto-report').then(r => r.ok ? r.json() : null).then(d => {
      if (d && d.report) {
        setCtoReport(d.report);
        setCtoReportTime(d.generated_at);
      }
    }).catch(() => {});
  }, []);

  const generateBriefings = async () => {
    setBriefingGenerating(true);
    try {
      const r = await fetch('/api/department-briefings/generate', { method: 'POST' });
      const d = await r.json();
      if (d && d.briefings) {
        setBriefings(d.briefings);
        setBriefingStatus(d.status || 'ok');
        setBriefingTime(d.generated_at);
      }
    } catch (e) {
      console.error('生成部门汇报失败:', e);
    } finally {
      setBriefingGenerating(false);
    }
  };

  const generateCtoReport = async () => {
    setCtoReportGenerating(true);
    try {
      const r = await fetch('/api/cto-report/generate', { method: 'POST' });
      const d = await r.json();
      if (d && d.report) {
        setCtoReport(d.report);
        setCtoReportTime(d.generated_at);
      }
    } catch (e) {
      console.error('生成CTO报告失败:', e);
    } finally {
      setCtoReportGenerating(false);
    }
  };

  const coordinator = coordinatorData || data?.ai_coordinator || {};
  const intelligence = coordinator?.intelligence_summary || {};
  const directives = coordinator?.stats || {};
  const adaptive = data?.adaptive_weights || {};
  const feedback = data?.feedback || {};
  const constitution = constitutionStatus || data?.constitution || {};
  const watchdog = data?.watchdog || {};
  const diag = aiDiagnostic?.latest_report || {};

  const sections = [
    { key: 'cto_report', label: 'CTO汇报', icon: Shield },
    { key: 'overview', label: '全局总览', icon: Gauge },
    { key: 'cycles', label: '运行日志', icon: Clock },
    { key: 'departments', label: '部门汇报', icon: Users },
    { key: 'directives', label: '战略指令', icon: Target },
    { key: 'decisions', label: '待决策', icon: AlertTriangle },
    { key: 'self_inspection', label: '系统自检', icon: Search },
    { key: 'risk_control', label: '风控', icon: Shield },
  ];

  const deptMap = {
    reviewer: { name: '审查部', icon: Eye, color: 'cyan' },
    diagnostic: { name: '诊断部', icon: Activity, color: 'emerald' },
    return_rate: { name: '收益部', icon: TrendingUp, color: 'amber' },
    synapse: { name: '协同部', icon: Zap, color: 'violet' },
    agent_memory: { name: '记忆部', icon: Brain, color: 'pink' },
    agi: { name: 'AGI智脑', icon: Cpu, color: 'cyan' },
  };

  const renderCtoReport = () => {
    const riskColorMap = { low: 'text-emerald-400', medium: 'text-amber-400', high: 'text-red-400' };
    const riskLabelMap = { low: '低风险', medium: '中等风险', high: '高风险' };
    const riskBgMap = { low: 'from-emerald-500/10 border-emerald-500/20', medium: 'from-amber-500/10 border-amber-500/20', high: 'from-red-500/10 border-red-500/20' };
    const riskIconColor = { low: 'bg-emerald-500/15 text-emerald-400', medium: 'bg-amber-500/15 text-amber-400', high: 'bg-red-500/15 text-red-400' };

    const r = ctoReport || {};
    const riskLevel = r.risk_level || 'medium';
    const title = r.title || r.summary?.slice(0, 20) || 'CTO汇报';

    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="flex items-center justify-between">
          <div className="text-xs text-slate-500">
            {ctoReportTime ? `上次生成: ${ctoReportTime}` : '尚未生成CTO汇报'}
          </div>
          <button
            onClick={generateCtoReport}
            disabled={ctoReportGenerating}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              ctoReportGenerating
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-400 border border-amber-500/30 hover:from-amber-500/30 hover:to-orange-500/30'
            }`}
          >
            {ctoReportGenerating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                CTO思考中...
              </>
            ) : (
              <>
                <Shield className="w-3.5 h-3.5" />
                生成CTO汇报
              </>
            )}
          </button>
        </div>

        {ctoReport ? (
          <div className="space-y-4">
            <div className={`bg-gradient-to-br ${riskBgMap[riskLevel]} to-transparent border rounded-2xl p-6`}>
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${riskIconColor[riskLevel]}`}>
                  <Shield className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <div className="text-sm font-black text-white">{title}</div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className={`text-[10px] font-bold ${riskColorMap[riskLevel]}`}>
                      {riskLabelMap[riskLevel] || riskLevel}
                    </span>
                    <span className="text-[9px] text-slate-600">|</span>
                    <span className="text-[9px] text-slate-500">CTO → CEO 汇报</span>
                  </div>
                </div>
              </div>

              {r.summary && (
                <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap pl-4 border-l-2 border-amber-500/30 mb-4">
                  {r.summary}
                </div>
              )}

              {r.report && !r.summary && (
                <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap pl-4 border-l-2 border-amber-500/30 mb-4">
                  {r.report}
                </div>
              )}
            </div>

            {r.key_findings?.length > 0 && (
              <div className="bg-gradient-to-br from-blue-500/10 to-transparent border border-blue-500/20 rounded-2xl p-5">
                <div className="text-[10px] text-blue-400 font-black mb-3 flex items-center gap-2">
                  <Eye className="w-3.5 h-3.5" /> 关键发现
                </div>
                <div className="space-y-2">
                  {r.key_findings.map((item, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0 mt-1.5" />
                      <div className="text-xs text-slate-300 leading-relaxed">{item}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {r.risk_alerts?.length > 0 && (
              <div className="bg-gradient-to-br from-red-500/10 to-transparent border border-red-500/20 rounded-2xl p-5">
                <div className="text-[10px] text-red-400 font-black mb-3 flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5" /> 风险预警
                </div>
                <div className="space-y-2">
                  {r.risk_alerts.map((item, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0 mt-1.5" />
                      <div className="text-xs text-slate-300 leading-relaxed">{item}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {r.action_items?.length > 0 && (
              <div className="bg-gradient-to-br from-teal-500/10 to-transparent border border-teal-500/20 rounded-2xl p-5">
                <div className="text-[10px] text-teal-400 font-black mb-3 flex items-center gap-2">
                  <Target className="w-3.5 h-3.5" /> 行动建议
                </div>
                <div className="space-y-2">
                  {r.action_items.map((item, i) => (
                    <div key={i} className="flex items-start gap-3">
                      <div className="w-5 h-5 rounded-lg bg-teal-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
                        <span className="text-[10px] font-black text-teal-400">{i + 1}</span>
                      </div>
                      <div className="text-xs text-slate-300 leading-relaxed">{item}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {r.agi_insight && (
              <div className="bg-gradient-to-br from-violet-500/10 to-transparent border border-violet-500/20 rounded-2xl p-5">
                <div className="text-[10px] text-violet-400 font-black mb-3 flex items-center gap-2">
                  <Brain className="w-3.5 h-3.5" /> AGI 智脑洞察
                </div>
                <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap pl-4 border-l-2 border-violet-500/30">
                  {r.agi_insight}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-gradient-to-br from-slate-500/5 to-transparent border border-slate-700/30 rounded-2xl p-8 text-center">
            <Shield className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <div className="text-sm text-slate-500 mb-1">CTO尚未生成汇报</div>
            <div className="text-[10px] text-slate-600">点击上方"生成CTO汇报"按钮，AI将综合所有部门数据为您生成专业汇报</div>
          </div>
        )}
      </div>
    );
  };

  const renderOverview = () => (
    <div className="space-y-4 animate-fadeIn">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">自动驾驶</div>
          <div className={`text-lg font-black ${autopilot?.running ? 'text-emerald-400' : 'text-red-400'}`}>
            {autopilot?.running ? '运行中' : '已停止'}
          </div>
          <div className="text-[9px] text-slate-600">周期 #{safe(autopilot?.cycle_count)}</div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">运行时间</div>
          <div className="text-lg font-black text-cyan-400">{(autopilot?.uptime_hours || 0).toFixed(1)}h</div>
          <div className="text-[9px] text-slate-600">连续运行</div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">拦截交易</div>
          <div className="text-lg font-black text-amber-400">{safe(autopilot?.blocked_trades_count)}</div>
          <div className="text-[9px] text-slate-600">风控拦截</div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">待决策</div>
          <div className={`text-lg font-black ${(autopilot?.pending_ceo_decisions || 0) > 0 ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`}>
            {safe(autopilot?.pending_ceo_decisions)}
          </div>
          <div className="text-[9px] text-slate-600">需CEO处理</div>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">系统健康</div>
          <div className={`text-lg font-black ${(watchdog?.system_health === 'healthy' || watchdog?.system_health === 'ok') ? 'text-emerald-400' : 'text-amber-400'}`}>
            {watchdog?.system_health === 'healthy' ? '健康' : safe(watchdog?.system_health)}
          </div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">ML权重</div>
          <div className="text-lg font-black text-violet-400">{((adaptive?.w_ml || 0) * 100).toFixed(0)}%</div>
          <div className="text-[9px] text-slate-600">规则 {((adaptive?.w_rule || 0) * 100).toFixed(0)}%</div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">ML准确率</div>
          <div className="text-lg font-black text-cyan-400">{(feedback?.rolling_accuracy || 0).toFixed(0)}%</div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black uppercase">宪法状态</div>
          <div className={`text-lg font-black ${
            constitution?.status === 'HEALTHY' || constitution?.can_open_new
              ? 'text-emerald-400' 
              : constitution?.permanent_breaker ? 'text-red-400'
              : constitution?.daily_breaker ? 'text-amber-400'
              : 'text-red-400'
          }`}>
            {constitution?.status === 'HEALTHY' || constitution?.can_open_new 
              ? '正常运行' 
              : constitution?.permanent_breaker ? '永久熔断'
              : constitution?.daily_breaker ? '日内暂停'
              : '限制中'}
          </div>
          <div className="text-[8px] text-slate-600">
            {constitution?.can_open_new ? '可开仓' : '禁止开仓'}
          </div>
        </div>
      </div>

      {autopilot?.schedule && (
        <div className="shield-glass rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-cyan-400" />
            <span className="text-[10px] font-black text-cyan-400">系统调度计划</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-950/30 rounded-lg p-2.5 border border-yellow-500/20">
              <div className="text-[8px] text-yellow-400 mb-1">⚡ 快速监控</div>
              <div className="text-xs font-bold text-yellow-300">每5秒</div>
              <div className="text-[8px] text-yellow-500/70">行情刷新+持仓TP/SL</div>
            </div>
            <div className="bg-slate-950/30 rounded-lg p-2.5">
              <div className="text-[8px] text-slate-500 mb-1">全量扫描</div>
              <div className="text-xs font-bold text-white">每{autopilot.schedule.scan_interval_min}分钟</div>
              <div className="text-[8px] text-slate-600">95标的信号分析</div>
            </div>
            <div className="bg-slate-950/30 rounded-lg p-2.5">
              <div className="text-[8px] text-slate-500 mb-1">运营邮件</div>
              <div className="text-xs font-bold text-white">每日{autopilot.schedule.email_count_daily}封</div>
              <div className="text-[8px] text-emerald-400">
                {autopilot.schedule.email_hours?.map(h => `${h}:00`).join(' / ')}
              </div>
              <div className="text-[8px] text-slate-600">下一封: {autopilot.schedule.next_email_hour}:00</div>
            </div>
            <div className="bg-slate-950/30 rounded-lg p-2.5">
              <div className="text-[8px] text-slate-500 mb-1">云端训练</div>
              <div className="text-xs font-bold text-white">每日{autopilot.schedule.training_count_daily}次</div>
              <div className="text-[8px] text-violet-400">
                {autopilot.schedule.training_hours?.map(h => `${h}:00`).join(' / ')}
              </div>
              <div className="text-[8px] text-slate-600">下一次: {autopilot.schedule.next_training_hour}:00</div>
            </div>
          </div>
        </div>
      )}

      {diag?.diagnosis && (() => {
        const d = diag.diagnosis;
        const dims = d?.dimensions || {};
        const dimNames = {
          trading_performance: { label: '交易表现', color: 'amber', icon: '📊' },
          ml_model_health: { label: 'ML模型', color: 'violet', icon: '🤖' },
          risk_control: { label: '风控管理', color: 'cyan', icon: '🛡️' },
          strategy_allocation: { label: '策略配置', color: 'emerald', icon: '⚖️' },
          signal_quality: { label: '信号质量', color: 'pink', icon: '📡' },
          capital_efficiency: { label: '资金效率', color: 'blue', icon: '💰' },
          evolution_progress: { label: '进化进展', color: 'orange', icon: '🧬' },
        };
        const scoreColor = (s) => s >= 70 ? 'text-emerald-400' : s >= 50 ? 'text-amber-400' : 'text-red-400';
        const scoreBg = (s) => s >= 70 ? 'bg-emerald-500' : s >= 50 ? 'bg-amber-500' : 'bg-red-500';

        return (
          <div className="space-y-3">
            <div className="shield-glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-black text-emerald-400">AI诊断总结</span>
                <span className={`ml-2 text-[10px] px-2 py-0.5 rounded-full font-bold ${
                  d?.severity === 'critical' ? 'bg-red-500/20 text-red-400' :
                  d?.severity === 'warning' ? 'bg-amber-500/20 text-amber-400' :
                  'bg-emerald-500/20 text-emerald-400'
                }`}>
                  健康分 {d?.health_score || '--'}/100
                </span>
                <span className="text-[9px] text-slate-600 ml-auto">{fmtTime(diag.timestamp)}</span>
              </div>
              {d?.summary && (
                <div className="text-xs text-slate-300 leading-relaxed mb-3">{d.summary}</div>
              )}
              {d?.vs_last && (
                <div className="text-[10px] text-cyan-400 bg-cyan-500/5 rounded-lg px-3 py-1.5 border border-cyan-500/10">
                  {d.vs_last}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {Object.entries(dims).map(([key, dim]) => {
                const meta = dimNames[key] || { label: key, color: 'slate', icon: '📋' };
                const isExpanded = expandedDim === key;
                return (
                  <div key={key} className="col-span-1">
                    <button
                      onClick={() => setExpandedDim(isExpanded ? null : key)}
                      className={`w-full shield-glass rounded-xl p-3 text-left transition-all hover:bg-slate-800/30 ${isExpanded ? 'ring-1 ring-amber-500/30' : ''}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[9px] font-bold text-slate-500">{meta.icon} {meta.label}</span>
                        <span className={`text-sm font-black ${scoreColor(dim.score)}`}>{dim.score}</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${scoreBg(dim.score)}`} style={{ width: `${dim.score}%` }} />
                      </div>
                      <div className="text-[8px] text-slate-500 mt-1 line-clamp-2">{dim.status}</div>
                    </button>
                  </div>
                );
              })}
            </div>

            {expandedDim && dims[expandedDim] && (() => {
              const dim = dims[expandedDim];
              const meta = dimNames[expandedDim] || { label: expandedDim, icon: '📋' };
              return (
                <div className="shield-glass rounded-xl p-4 animate-fadeIn">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-black text-white">{meta.icon} {meta.label}详情</span>
                    <button onClick={() => setExpandedDim(null)} className="text-slate-500 hover:text-white">
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="text-[10px] text-slate-400 mb-3">{dim.status}</div>
                  {dim.issues?.length > 0 && (
                    <div className="mb-3">
                      <div className="text-[9px] text-red-400 font-bold mb-1.5">发现问题</div>
                      {dim.issues.map((issue, j) => (
                        <div key={j} className="text-[10px] text-slate-400 mb-1 pl-3 border-l-2 border-red-500/20">{issue}</div>
                      ))}
                    </div>
                  )}
                  {dim.suggestions?.length > 0 && (
                    <div>
                      <div className="text-[9px] text-emerald-400 font-bold mb-1.5">优化建议</div>
                      {dim.suggestions.map((sug, j) => (
                        <div key={j} className="text-[10px] text-slate-300 mb-1.5 pl-3 border-l-2 border-emerald-500/20">{sug}</div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        );
      })()}

      {autopilot?.recent_blocked?.length > 0 && (
        <div className="shield-glass rounded-xl p-4">
          <div className="text-[9px] text-red-400 font-black uppercase mb-3">最近拦截记录</div>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {autopilot.recent_blocked.slice().reverse().slice(0, 10).map((b, i) => {
              const timeStr = b.time ? b.time.replace('T', ' ').slice(5, 16) : '';
              const reasonCn = (b.reason || '')
                .replace(/volatile/gi, '高波动')
                .replace(/ranging/gi, '震荡')
                .replace(/mixed/gi, '混合')
                .replace(/trending/gi, '趋势')
                .replace(/trend_following/gi, '趋势跟踪')
                .replace(/range_harvester/gi, '区间收割')
                .replace(/signal_score/gi, '信号评分')
                .replace(/ml_confidence/gi, 'ML置信度');
              return (
                <div key={i} className="bg-slate-950/40 rounded-lg px-3 py-2.5 border border-slate-800/50">
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${b.direction === 'long' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                        {b.direction === 'long' ? '做多' : '做空'}
                      </span>
                      <span className="text-xs text-white font-bold">{b.symbol}</span>
                      <span className="text-[10px] text-slate-500 font-mono">评分{b.score}</span>
                      <span className="text-[10px] text-slate-500 font-mono">ML{(b.ml_confidence || 0).toFixed(0)}%</span>
                    </div>
                    {timeStr && <span className="text-[9px] text-slate-600 font-mono">{timeStr}</span>}
                  </div>
                  <div className="text-[10px] text-amber-400/80 leading-relaxed">{reasonCn}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );

  const renderCycles = () => {
    const cycles = autopilot?.recent_cycles || [];
    const actions = autopilot?.recent_actions || [];
    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="shield-glass rounded-xl p-4">
          <div className="text-[9px] text-cyan-400 font-black uppercase mb-3">自动驾驶周期记录</div>
          {cycles.length === 0 ? (
            <div className="text-xs text-slate-500 text-center py-4">暂无周期记录</div>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {cycles.slice().reverse().map((c, i) => (
                <div key={i} className="bg-slate-950/40 rounded-lg border border-slate-800/50">
                  <button
                    onClick={() => setExpandedCycle(expandedCycle === c.cycle ? null : c.cycle)}
                    className="w-full flex items-center justify-between px-3 py-2 text-[10px]"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-slate-500">#{c.cycle}</span>
                      <span className="text-slate-400">{fmtTime(c.time)}</span>
                      {c.summary && Object.entries(c.summary).map(([k, v]) => (
                        <span key={k} className="flex items-center gap-0.5">
                          <span className={`w-1.5 h-1.5 rounded-full ${statusDot(v)}`} />
                          <span className="text-[8px] text-slate-600">{k}</span>
                        </span>
                      ))}
                    </div>
                    {expandedCycle === c.cycle ? <ChevronUp className="w-3 h-3 text-slate-500" /> : <ChevronDown className="w-3 h-3 text-slate-500" />}
                  </button>
                  {expandedCycle === c.cycle && (
                    <div className="px-3 pb-2 border-t border-slate-800/30">
                      {c.decisions?.length > 0 ? (
                        c.decisions.map((d, j) => (
                          <div key={j} className="text-[9px] text-slate-400 mt-1">{JSON.stringify(d, null, 0)}</div>
                        ))
                      ) : (
                        <div className="text-[9px] text-slate-600 mt-1">无异常决策</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="shield-glass rounded-xl p-4">
          <div className="text-[9px] text-amber-400 font-black uppercase mb-3">历史操作记录</div>
          {actions.length === 0 ? (
            <div className="text-xs text-slate-500 text-center py-4">暂无操作记录</div>
          ) : (
            <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
              {actions.slice().reverse().map((a, i) => {
                const actionMap = {
                  'update_signal_gate': '信号门更新',
                  'scan_complete': '扫描完成',
                  'scan_start': '开始扫描',
                  'retrain_model': 'ML模型重训',
                  'auto_cloud_training': '定时云训练',
                  'adjust_weights': '权重调整',
                  'risk_check': '风控检查',
                  'rebalance': '组合再平衡',
                  'open_position': '开仓操作',
                  'close_position': '平仓操作',
                  'stop_loss': '止损触发',
                  'take_profit': '止盈触发',
                  'calibrate': '模型校准',
                  'constitution_check': '宪法检查',
                  'daily_report': '每日报告',
                  'pause_trading': '暂停交易',
                  'tighten_filters': '收紧过滤',
                  'suggest_retrain': '建议重训',
                };
                const reasonMap = (r) => {
                  if (!r) return '--';
                  return r
                    .replace(/个信号条件质量过差/g, '个信号条件未达标，已过滤')
                    .replace(/executed_blocked/g, '已拦截')
                    .replace(/signal_gate/g, '信号质量门')
                    ;
                };
                const resultMap = (r) => {
                  if (!r) return '';
                  return r
                    .replace(/executed_blocked=/g, '拦截了')
                    .replace(/(\d+)$/, '$1个低质量信号')
                    ;
                };
                const actionLabel = actionMap[a.action] || a.action;
                const logLevel = (() => {
                  const act = a.action || '';
                  const reason = (a.reason || '').toLowerCase();
                  const result = (a.result || '').toLowerCase();
                  if (reason.includes('critical') || result.includes('critical')) return 'CRITICAL';
                  if (act === 'stop_loss' || act === 'pause_trading' || reason.includes('error') || result.includes('error') || result.includes('fail')) return 'ERROR';
                  if (act === 'tighten_filters' || act === 'suggest_retrain' || act === 'risk_check' || reason.includes('warn') || reason.includes('过差')) return 'WARNING';
                  if (act === 'open_position' || act === 'close_position' || act === 'take_profit' || act === 'scan_complete') return 'SUCCESS';
                  return 'INFO';
                })();
                const logStyle = {
                  CRITICAL: 'bg-red-500/10 border border-red-500/30 animate-pulse',
                  ERROR: 'bg-red-500/10 border border-red-500/30',
                  WARNING: 'bg-amber-500/10 border border-amber-500/30',
                  SUCCESS: 'bg-emerald-500/10 border border-emerald-500/30',
                  INFO: 'bg-slate-950/30 border border-slate-800/50',
                }[logLevel];
                return (
                  <div key={i} className={`rounded-lg px-3 py-2 ${logStyle}`}>
                    <div className="flex items-center justify-between text-[10px]">
                      <span className="text-slate-500">{fmtTime(a.time)}</span>
                      <span className="text-cyan-400 font-bold">{actionLabel}</span>
                    </div>
                    <div className="flex items-center justify-between mt-0.5">
                      <span className="text-[9px] text-slate-400 max-w-[250px]">{reasonMap(a.reason)}</span>
                      <span className="text-[8px] text-emerald-400/60">{resultMap(a.result)}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    );
  };

  const renderDepartments = () => {
    const hasBriefings = briefings && Object.keys(briefings).length > 0;
    const colorMap = {
      cyan: { border: 'border-cyan-500/30', bg: 'from-cyan-500/10', text: 'text-cyan-400', accent: 'bg-cyan-500/10', dot: 'bg-cyan-400' },
      emerald: { border: 'border-emerald-500/30', bg: 'from-emerald-500/10', text: 'text-emerald-400', accent: 'bg-emerald-500/10', dot: 'bg-emerald-400' },
      amber: { border: 'border-amber-500/30', bg: 'from-amber-500/10', text: 'text-amber-400', accent: 'bg-amber-500/10', dot: 'bg-amber-400' },
      violet: { border: 'border-violet-500/30', bg: 'from-violet-500/10', text: 'text-violet-400', accent: 'bg-violet-500/10', dot: 'bg-violet-400' },
      pink: { border: 'border-pink-500/30', bg: 'from-pink-500/10', text: 'text-pink-400', accent: 'bg-pink-500/10', dot: 'bg-pink-400' },
    };

    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-slate-500">
              {briefingTime ? `上次生成: ${briefingTime}` : '尚未生成AI汇报'}
            </div>
          </div>
          <button
            onClick={generateBriefings}
            disabled={briefingGenerating}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              briefingGenerating
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-teal-500/20 to-cyan-500/20 text-teal-400 border border-teal-500/30 hover:from-teal-500/30 hover:to-cyan-500/30'
            }`}
          >
            {briefingGenerating ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                AI思考中...
              </>
            ) : (
              <>
                <Brain className="w-3.5 h-3.5" />
                生成AI汇报
              </>
            )}
          </button>
        </div>

        {Object.entries(deptMap).map(([key, dept]) => {
          const briefing = briefings[key];
          const rawData = intelligence[key];
          const c = colorMap[dept.color] || colorMap.cyan;

          return (
            <div key={key} className={`bg-gradient-to-br ${c.bg} to-transparent border ${c.border} rounded-2xl p-5 transition-all hover:shadow-lg hover:shadow-${dept.color}-500/5`}>
              <div className="flex items-center gap-3 mb-3">
                <div className={`w-8 h-8 rounded-xl ${c.accent} flex items-center justify-center`}>
                  <dept.icon className={`w-4 h-4 ${c.text}`} />
                </div>
                <div className="flex-1">
                  <div className={`text-sm font-black ${c.text}`}>{dept.name}</div>
                  <div className="text-[9px] text-slate-600">
                    {{reviewer:'交易复盘 · 亏损分析 · 模式验证', diagnostic:'系统健康 · 风险检查 · 问题发现', return_rate:'收益监控 · 业绩诊断 · 攻守建议', synapse:'策略协调 · 资产配置 · 跨策学习', agent_memory:'经验积累 · 规则管理 · 模式记忆', agi:'深度反思 · 市场洞察 · 策略进化'}[key]}
                  </div>
                </div>
                <div className={`w-2 h-2 rounded-full ${rawData ? c.dot : 'bg-slate-600'}`} title={rawData ? '数据就绪' : '无数据'} />
              </div>

              {briefing ? (
                <div className="relative">
                  <div className="text-xs text-slate-200 leading-relaxed whitespace-pre-wrap pl-4 border-l-2 border-slate-700/50">
                    {briefing}
                  </div>
                </div>
              ) : rawData?.summary ? (
                <div className="text-xs text-slate-500 italic pl-4 border-l-2 border-slate-800/50">
                  {rawData.summary}
                  <span className="text-[9px] text-slate-600 ml-2">(点击"生成AI汇报"获取详细分析)</span>
                </div>
              ) : (
                <div className="text-xs text-slate-600 pl-4 border-l-2 border-slate-800/50">
                  等待数据采集...
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const renderDirectives = () => {
    const stats = coordinator?.stats || {};
    const moduleMetrics = coordinator?.module_metrics || {};
    const reflection = coordinator?.reflection;
    const outlook = coordinator?.market_outlook;
    const sd = coordinator?.strategic_directives || {};

    const statLabels = {
      total_coordinations: '总协调次数', total_ai_analyses: 'AI分析次数',
      last_coordination: '上次协调', last_ai_analysis: '上次AI分析',
      module_sync_count: '模块同步次数', ai_accuracy_score: 'AI准确率',
      reflection_count: '反思次数',
    };
    const metricLabels = {
      ml_accuracy: 'ML准确率', ml_win_rate: 'ML胜率', rule_win_rate: '规则胜率',
      signal_quality_avg: '信号质量均值', regime: '市场环境', drawdown_pct: '回撤比例',
      consecutive_losses: '连续亏损', consecutive_wins: '连续盈利', daily_pnl: '当日盈亏',
      total_trades: '总交易数', synapse_rule_count: '协同规则数', frozen_strategies: '冻结策略',
      capital_utilization: '资金利用率', grid_active: '网格活跃数', grid_win_rate: '网格胜率',
      grid_geo_wr: '网格几何胜率', grid_arith_wr: '网格算术胜率', grid_trailing_shifts: '网格跟踪调整',
      ml_weight: 'ML权重', rule_weight: '规则权重', max_drawdown_ever: '历史最大回撤',
      strategy_budgets: '策略预算', active_strategies: '活跃策略', equity: '总资产',
      total_pnl: '累计盈亏', open_positions: '持仓数', max_dd_pct: '最大回撤%',
      feedback_suggestions: '反馈建议数', advisor_actions: '顾问动作',
    };
    const aggrMap = { conservative: '保守', moderate: '适中', aggressive: '激进' };
    const regimeMap = { trending: '趋势', ranging: '震荡', volatile: '波动', unknown: '未知' };

    const formatMetricValue = (k, v) => {
      if (k === 'regime') return regimeMap[v] || v;
      if (k.includes('rate') || k.includes('accuracy') || k === 'capital_utilization' || k === 'drawdown_pct' || k === 'max_dd_pct' || k === 'max_drawdown_ever')
        return typeof v === 'number' ? `${(v * (v < 1 ? 100 : 1)).toFixed(1)}%` : String(v);
      if (k === 'equity' || k === 'total_pnl' || k === 'daily_pnl')
        return typeof v === 'number' ? `$${v.toLocaleString()}` : String(v);
      if (k === 'active_strategies' && Array.isArray(v))
        return v.map(s => ({trend:'趋势',range:'区间',grid:'网格'}[s] || s)).join(' / ');
      if (k === 'strategy_budgets' && typeof v === 'object')
        return Object.entries(v).map(([s, d]) => `${({trend:'趋势',range:'区间',grid:'网格'}[s]||s)}: $${(d?.available||0).toLocaleString()}`).join(', ');
      if (typeof v === 'object') return JSON.stringify(v);
      return String(v);
    };

    const getMetricColor = (k, v) => {
      if (k === 'regime') return v === 'trending' ? 'text-emerald-400' : v === 'volatile' ? 'text-red-400' : 'text-amber-400';
      if (k === 'consecutive_losses') return v > 3 ? 'text-red-400' : v > 0 ? 'text-amber-400' : 'text-emerald-400';
      if (k === 'consecutive_wins') return v > 0 ? 'text-emerald-400' : 'text-slate-400';
      if (k === 'total_pnl' || k === 'daily_pnl') return v >= 0 ? 'text-emerald-400' : 'text-red-400';
      return 'text-white';
    };

    const coreMetrics = ['regime', 'equity', 'total_pnl', 'total_trades', 'ml_win_rate', 'rule_win_rate', 'drawdown_pct', 'open_positions'];
    const tradingMetrics = ['consecutive_wins', 'consecutive_losses', 'daily_pnl', 'capital_utilization', 'grid_active', 'grid_win_rate'];
    const systemMetrics = Object.keys(moduleMetrics).filter(k => !coreMetrics.includes(k) && !tradingMetrics.includes(k));

    return (
      <div className="space-y-4 animate-fadeIn">
        {outlook && (
          <div className="bg-gradient-to-br from-cyan-500/10 to-transparent border border-cyan-500/20 rounded-2xl p-5">
            <div className="text-[10px] text-cyan-400 font-black mb-2">市场展望</div>
            <div className="text-xs text-slate-200 leading-relaxed">{safe(outlook)}</div>
          </div>
        )}

        {Object.keys(sd).length > 0 && (
          <div className="bg-gradient-to-br from-amber-500/10 to-transparent border border-amber-500/20 rounded-2xl p-5">
            <div className="text-[10px] text-amber-400 font-black mb-3">CTO战略指令</div>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/30">
                <div className="text-[9px] text-slate-500">策略偏好</div>
                <div className="text-sm font-black text-amber-400 mt-1">
                  {{trend:'趋势跟踪',range:'区间收割',grid:'网格交易'}[sd.strategy_preference] || sd.strategy_preference || '--'}
                </div>
              </div>
              <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/30">
                <div className="text-[9px] text-slate-500">攻守模式</div>
                <div className={`text-sm font-black mt-1 ${sd.aggression_mode === 'aggressive' ? 'text-red-400' : sd.aggression_mode === 'conservative' ? 'text-cyan-400' : 'text-emerald-400'}`}>
                  {aggrMap[sd.aggression_mode] || sd.aggression_mode || '--'}
                </div>
              </div>
              <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/30">
                <div className="text-[9px] text-slate-500">最大并发持仓</div>
                <div className="text-sm font-black text-violet-400 mt-1">{sd.max_concurrent_positions ?? '--'} 个</div>
              </div>
              <div className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/30">
                <div className="text-[9px] text-slate-500">最低信号分</div>
                <div className="text-sm font-black text-teal-400 mt-1">{sd.min_signal_score ?? '--'} 分</div>
              </div>
              {sd.asset_blacklist?.length > 0 && (
                <div className="bg-slate-950/50 rounded-xl p-3 border border-red-500/20 col-span-2 sm:col-span-2">
                  <div className="text-[9px] text-red-400">黑名单资产</div>
                  <div className="text-[10px] text-red-300 mt-1 leading-relaxed">{sd.asset_blacklist.join(', ')}</div>
                </div>
              )}
            </div>

            {sd.regime_strategy_map && (
              <div className="mt-3">
                <div className="text-[9px] text-slate-500 mb-2">环境-策略权重分配</div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {Object.entries(sd.regime_strategy_map).map(([regime, weights]) => (
                    <div key={regime} className="bg-slate-950/50 rounded-lg p-2 border border-slate-800/20">
                      <div className="text-[9px] text-cyan-400 font-bold mb-1">{regimeMap[regime] || regime}</div>
                      {Object.entries(weights).map(([strat, w]) => (
                        <div key={strat} className="flex justify-between text-[9px]">
                          <span className="text-slate-500">{{trend:'趋势',range:'区间',grid:'网格'}[strat] || strat}</span>
                          <span className="text-white font-bold">{(w * 100).toFixed(0)}%</span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {sd.directives_updated_at && (
              <div className="text-[9px] text-slate-600 mt-3">更新时间: {sd.directives_updated_at}</div>
            )}
          </div>
        )}

        <div className="bg-gradient-to-br from-violet-500/10 to-transparent border border-violet-500/20 rounded-2xl p-5">
          <div className="text-[10px] text-violet-400 font-black mb-3">核心运营指标</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {coreMetrics.map(k => {
              const v = moduleMetrics[k];
              if (v === undefined) return null;
              return (
                <div key={k} className="bg-slate-950/50 rounded-xl p-3 border border-slate-800/30 text-center">
                  <div className="text-[9px] text-slate-500">{metricLabels[k] || k}</div>
                  <div className={`text-sm font-black mt-1 ${getMetricColor(k, v)}`}>{formatMetricValue(k, v)}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-gradient-to-br from-teal-500/10 to-transparent border border-teal-500/20 rounded-2xl p-5">
          <div className="text-[10px] text-teal-400 font-black mb-3">交易执行指标</div>
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {tradingMetrics.map(k => {
              const v = moduleMetrics[k];
              if (v === undefined) return null;
              return (
                <div key={k} className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/20 text-center">
                  <div className="text-[8px] text-slate-500">{metricLabels[k] || k}</div>
                  <div className={`text-xs font-black mt-0.5 ${getMetricColor(k, v)}`}>{formatMetricValue(k, v)}</div>
                </div>
              );
            })}
          </div>
        </div>

        {reflection && (
          <div className="bg-gradient-to-br from-pink-500/10 to-transparent border border-pink-500/20 rounded-2xl p-5">
            <div className="text-[10px] text-pink-400 font-black mb-2">CTO反思录</div>
            {typeof reflection === 'object' ? (
              <div className="space-y-2">
                {reflection.accuracy_score !== undefined && (
                  <div className="text-xs text-slate-300">准确率评分: <span className={`font-black ${reflection.accuracy_score >= 0.6 ? 'text-emerald-400' : 'text-amber-400'}`}>{(reflection.accuracy_score * 100).toFixed(0)}%</span></div>
                )}
                {reflection.lessons?.length > 0 && (
                  <div className="space-y-1">
                    {reflection.lessons.map((l, i) => <div key={i} className="text-[10px] text-slate-400 pl-3 border-l-2 border-pink-500/30">{l}</div>)}
                  </div>
                )}
                {reflection.time && <div className="text-[9px] text-slate-600 mt-2">反思时间: {reflection.time}</div>}
              </div>
            ) : (
              <div className="text-xs text-slate-300 leading-relaxed">{safe(reflection)}</div>
            )}
          </div>
        )}

        <div className="bg-gradient-to-br from-emerald-500/10 to-transparent border border-emerald-500/20 rounded-2xl p-5">
          <div className="text-[10px] text-emerald-400 font-black mb-3">自适应权重系统</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="bg-slate-950/50 rounded-xl p-3 text-center border border-slate-800/20">
              <div className="text-[9px] text-slate-500">ML权重</div>
              <div className="text-sm font-black text-violet-400">{((adaptive?.w_ml || 0) * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-slate-950/50 rounded-xl p-3 text-center border border-slate-800/20">
              <div className="text-[9px] text-slate-500">规则权重</div>
              <div className="text-sm font-black text-cyan-400">{((adaptive?.w_rule || 0) * 100).toFixed(1)}%</div>
            </div>
            <div className="bg-slate-950/50 rounded-xl p-3 text-center border border-slate-800/20">
              <div className="text-[9px] text-slate-500">当前层级</div>
              <div className="text-sm font-black text-amber-400">{safe(adaptive?.tier)}</div>
            </div>
            <div className="bg-slate-950/50 rounded-xl p-3 text-center border border-slate-800/20">
              <div className="text-[9px] text-slate-500">ML评估数</div>
              <div className="text-sm font-black text-emerald-400">{safe(adaptive?.evaluated)}</div>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-slate-500/10 to-transparent border border-slate-500/20 rounded-2xl p-5">
          <div className="text-[10px] text-slate-400 font-black mb-3">系统运行统计</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {Object.entries(stats).map(([k, v]) => (
              <div key={k} className="bg-slate-950/50 rounded-lg p-2.5 border border-slate-800/20 text-center">
                <div className="text-[8px] text-slate-500">{statLabels[k] || k}</div>
                <div className="text-xs text-white font-bold mt-0.5">
                  {k === 'ai_accuracy_score' ? `${(v * 100).toFixed(0)}%` : typeof v === 'object' ? JSON.stringify(v) : String(v)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const handleResolve = async (index, action) => {
    setResolving(prev => ({ ...prev, [index]: true }));
    try {
      const res = await fetch(`/api/autopilot/resolve/${index}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, note: ceoNotes[index] || '' }),
      });
      if (res.ok) {
        const apRes = await fetch('/api/autopilot/status');
        const apData = await apRes.json();
        setAutopilot(apData);
        setCeoNotes(prev => { const n = { ...prev }; delete n[index]; return n; });
      }
    } catch (e) {
      console.error('Resolve failed:', e);
    } finally {
      setResolving(prev => ({ ...prev, [index]: false }));
    }
  };

  const renderDecisions = () => {
    const decisions = autopilot?.ceo_decisions || [];
    const pending = decisions.filter(d => !d.resolved);
    const resolved = decisions.filter(d => d.resolved);
    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="shield-glass rounded-xl p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className={`w-4 h-4 ${pending.length > 0 ? 'text-amber-400' : 'text-emerald-400'}`} />
              <span className="text-xs font-black text-white">
                {pending.length > 0 ? `${pending.length} 项待处理` : '无待处理事项'}
              </span>
            </div>
            <span className="text-[9px] text-slate-500">{resolved.length} 项已处理</span>
          </div>
        </div>

        {(() => {
          const recs = coordinator?.recommendations || {};
          const metrics = coordinator?.module_metrics || {};
          const hasPriority = recs.priority_action && recs.priority_action.length > 0;
          const hasOutlook = recs.market_outlook && recs.market_outlook.length > 0;
          const hasReflection = recs.reflection && recs.reflection.length > 0;

          const regime = metrics.regime || recs.regime_bias || '--';
          const regimeMap = { 'trending_up': '上涨趋势', 'trending_down': '下跌趋势', 'volatile': '震荡波动', 'ranging': '横盘震荡', 'mean_reverting': '均值回归', 'breakout': '突破行情' };
          const regimeLabel = regimeMap[regime] || regime;
          const sizeMult = recs.size_multiplier ?? 1.0;
          const throttle = recs.throttle_level || 'normal';
          const throttleMap = { 'normal': '正常', 'cautious': '谨慎', 'aggressive': '激进', 'minimal': '极度保守' };
          const riskLevel = recs.risk_level || 'standard';
          const riskMap = { 'standard': '标准', 'elevated': '升高', 'high': '高风险', 'low': '低风险', 'reduced': '降低' };
          const mlAcc = metrics.ml_accuracy;
          const winRate = metrics.rule_win_rate;
          const totalTrades = metrics.total_trades || 0;
          const openPos = metrics.open_positions || 0;
          const drawdown = metrics.max_dd_pct || 0;
          const utilization = metrics.capital_utilization || 0;

          const smartAdvice = [];
          if (mlAcc != null && mlAcc < 0.55) smartAdvice.push('ML准确率偏低，建议降低ML权重或重新训练');
          if (winRate != null && winRate < 0.35) smartAdvice.push('规则胜率不足35%，建议审查策略参数');
          if (drawdown > 5) smartAdvice.push(`最大回撤${drawdown.toFixed(1)}%已接近警戒线，建议缩小仓位`);
          if (utilization > 0.8) smartAdvice.push('资金利用率过高，注意分散风险');
          if (utilization < 0.05 && totalTrades > 10) smartAdvice.push('资金利用率极低，可适当提升仓位上限');
          if (regime === 'volatile') smartAdvice.push('当前震荡市，区间策略更优，趋势策略宜轻仓');
          if (regime === 'trending_up') smartAdvice.push('上涨趋势确认，趋势跟踪策略可适当加仓');
          if (regime === 'trending_down') smartAdvice.push('下跌趋势中，建议以防守为主，严控回撤');
          if (smartAdvice.length === 0) smartAdvice.push('系统整体运行正常，建议保持当前策略配置');

          return (
            <div className="bg-gradient-to-r from-violet-500/10 to-transparent border border-violet-500/20 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Brain className="w-4 h-4 text-violet-400" />
                <span className="text-[10px] font-black text-violet-400">CTO研判建议</span>
                <span className={`text-[8px] px-2 py-0.5 rounded ${
                  regime === 'volatile' || regime === 'ranging' ? 'bg-amber-500/10 text-amber-400' :
                  regime === 'trending_up' ? 'bg-emerald-500/10 text-emerald-400' :
                  regime === 'trending_down' ? 'bg-red-500/10 text-red-400' :
                  'bg-slate-700/20 text-slate-400'
                }`}>{regimeLabel}</span>
              </div>

              {hasPriority && (
                <div className="text-xs text-slate-300 leading-relaxed mb-2 bg-violet-500/5 rounded-lg px-3 py-2 border border-violet-500/10">
                  {recs.priority_action}
                </div>
              )}
              {hasOutlook && (
                <div className="text-[10px] text-cyan-400 bg-cyan-500/5 rounded-lg px-3 py-1.5 border border-cyan-500/10 mb-2">
                  市场展望：{recs.market_outlook}
                </div>
              )}
              {hasReflection && (
                <div className="text-[10px] text-pink-400 bg-pink-500/5 rounded-lg px-3 py-1.5 border border-pink-500/10 mb-2">
                  CTO反思：{recs.reflection}
                </div>
              )}

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                <div className="bg-slate-950/40 rounded-lg p-2 text-center">
                  <div className="text-[8px] text-slate-500">仓位系数</div>
                  <div className={`text-sm font-black ${sizeMult >= 1 ? 'text-emerald-400' : sizeMult >= 0.5 ? 'text-amber-400' : 'text-red-400'}`}>
                    {sizeMult.toFixed(2)}x
                  </div>
                </div>
                <div className="bg-slate-950/40 rounded-lg p-2 text-center">
                  <div className="text-[8px] text-slate-500">油门档位</div>
                  <div className="text-sm font-black text-white">{throttleMap[throttle] || throttle}</div>
                </div>
                <div className="bg-slate-950/40 rounded-lg p-2 text-center">
                  <div className="text-[8px] text-slate-500">风险等级</div>
                  <div className={`text-sm font-black ${riskLevel === 'standard' || riskLevel === 'low' ? 'text-emerald-400' : riskLevel === 'elevated' ? 'text-amber-400' : 'text-red-400'}`}>
                    {riskMap[riskLevel] || riskLevel}
                  </div>
                </div>
                <div className="bg-slate-950/40 rounded-lg p-2 text-center">
                  <div className="text-[8px] text-slate-500">资金利用</div>
                  <div className="text-sm font-black text-cyan-400">{(utilization * 100).toFixed(1)}%</div>
                </div>
              </div>

              <div className="space-y-1">
                <div className="text-[9px] text-amber-400 font-bold">智能建议</div>
                {smartAdvice.map((advice, i) => (
                  <div key={i} className="text-[10px] text-slate-300 pl-2 border-l-2 border-violet-500/20 leading-relaxed">
                    {advice}
                  </div>
                ))}
              </div>

              {recs.rebalance_advice && (
                <div className="flex gap-2 mt-3">
                  {Object.entries(recs.rebalance_advice).map(([k, v]) => {
                    const nameMap = { trend: '趋势', range: '区间', grid: '网格' };
                    return (
                      <div key={k} className="flex-1 bg-slate-950/30 rounded-lg p-2 text-center">
                        <div className="text-[8px] text-slate-500">{nameMap[k] || k}</div>
                        <div className="text-xs font-bold text-white">{(v * 100).toFixed(0)}%</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })()}

        {pending.length === 0 && (
          <div className="shield-glass rounded-2xl p-8 text-center">
            <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <div className="text-sm font-bold text-white">系统自主运行正常</div>
            <div className="text-xs text-slate-500 mt-1">无需CEO介入</div>
          </div>
        )}

        {pending.map((d, idx) => {
          const realIndex = decisions.indexOf(d);
          const note = ceoNotes[realIndex] || '';
          return (
            <div key={realIndex} className={`rounded-xl p-4 border ${severityColor(d.severity)}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  <span className="text-xs font-black">{safe(d.title)}</span>
                  <span className={`text-[8px] px-2 py-0.5 rounded-full border ${
                    d.severity === 'high' || d.severity === 'critical' ? 'border-red-500/30 text-red-400 bg-red-500/10' :
                    d.severity === 'medium' ? 'border-amber-500/30 text-amber-400 bg-amber-500/10' :
                    'border-slate-700 text-slate-500 bg-slate-700/20'
                  }`}>
                    {d.severity === 'high' || d.severity === 'critical' ? '紧急' : d.severity === 'medium' ? '中等' : '一般'}
                  </span>
                </div>
                <span className="text-[9px] text-slate-500">{fmtTime(d.time)}</span>
              </div>
              <div className="text-xs text-slate-300 leading-relaxed mb-3">{safe(d.detail)}</div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={note}
                    onChange={(e) => setCeoNotes(prev => ({ ...prev, [realIndex]: e.target.value }))}
                    placeholder="CEO批注（可选）..."
                    className="flex-1 px-3 py-1.5 bg-slate-950/60 border border-slate-700 rounded-lg text-[10px] text-white placeholder-slate-600 focus:outline-none focus:border-amber-500/50"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleResolve(realIndex, 'approve')}
                    disabled={resolving[realIndex]}
                    className="flex items-center gap-1 px-3 py-1.5 bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 rounded-lg text-[10px] font-bold hover:bg-emerald-500/30 transition-all disabled:opacity-50"
                  >
                    <Check className="w-3 h-3" />
                    同意执行
                  </button>
                  <button
                    onClick={() => handleResolve(realIndex, 'dismiss')}
                    disabled={resolving[realIndex]}
                    className="flex items-center gap-1 px-3 py-1.5 bg-slate-700/30 text-slate-400 border border-slate-700 rounded-lg text-[10px] font-bold hover:bg-slate-700/50 transition-all disabled:opacity-50"
                  >
                    <X className="w-3 h-3" />
                    暂不处理
                  </button>
                  {resolving[realIndex] && (
                    <span className="text-[9px] text-amber-400 animate-pulse">处理中...</span>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {resolved.length > 0 && (
          <div className="shield-glass rounded-xl p-4">
            <div className="text-[9px] text-slate-500 font-black uppercase mb-2">已处理 ({resolved.length})</div>
            <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
              {resolved.map((d, i) => (
                <div key={i} className="flex items-center justify-between text-[10px] bg-slate-950/30 rounded-lg px-3 py-2 opacity-60">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                    <span className="text-slate-400">{safe(d.title)}</span>
                  </div>
                  <span className="text-slate-600">{fmtTime(d.time)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {agiData?.status?.latest_reflection && (() => {
          const ref = agiData.status.latest_reflection;
          const isObj = typeof ref === 'object' && ref !== null;
          const findings = isObj ? (ref.findings || []) : [];
          const recs = isObj ? (ref.recommendations || []) : [];
          const cog = isObj ? (ref.cognitive_state || {}) : {};
          const refTime = isObj ? ref.time : '';
          const refType = isObj ? ref.type : '';
          const typeMap = {
            'periodic_review': '定期检视',
            'trade_reflection': '交易复盘',
            'market_shift': '市场变化',
            'performance_review': '绩效评估',
          };
          return (
            <div className="shield-glass rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Brain className="w-4 h-4 text-pink-400" />
                  <span className="text-[10px] font-black text-pink-400">AGI最新反思</span>
                  {refType && <span className="text-[8px] px-2 py-0.5 rounded bg-pink-500/10 text-pink-300">{typeMap[refType] || refType}</span>}
                </div>
                <span className="text-[9px] text-slate-600">{refTime}</span>
              </div>
              {findings.length > 0 && (
                <div className="mb-2">
                  <div className="text-[9px] text-amber-400 font-bold mb-1">发现</div>
                  {findings.map((f, i) => (
                    <div key={i} className="text-[10px] text-slate-300 mb-0.5 pl-2 border-l-2 border-amber-500/20">
                      {typeof f === 'object' && f !== null ? JSON.stringify(f) : f}
                    </div>
                  ))}
                </div>
              )}
              {recs.length > 0 && (
                <div className="mb-2">
                  <div className="text-[9px] text-emerald-400 font-bold mb-1">建议</div>
                  {recs.map((r, i) => (
                    <div key={i} className="text-[10px] text-slate-300 mb-0.5 pl-2 border-l-2 border-emerald-500/20">
                      {typeof r === 'object' && r !== null
                        ? `${r.type === 'increase_ml_weight' ? '提升ML权重' : r.type === 'reduce_ml_weight' ? '降低ML权重' : r.type || ''}${r.current_accuracy != null ? ` (当前准确率${r.current_accuracy}%` : ''}${r.suggested_weight != null ? `, 建议权重${r.suggested_weight})` : ''}`
                        : r}
                    </div>
                  ))}
                </div>
              )}
              {Object.keys(cog).length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {cog.confidence_calibration != null && (
                    <span className="text-[8px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">信心度 {(cog.confidence_calibration * 100).toFixed(0)}%</span>
                  )}
                  {cog.risk_appetite && (
                    <span className="text-[8px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">风险偏好 {cog.risk_appetite === 'moderate' ? '适中' : cog.risk_appetite === 'aggressive' ? '激进' : cog.risk_appetite === 'conservative' ? '保守' : cog.risk_appetite}</span>
                  )}
                  {cog.total_reflections != null && (
                    <span className="text-[8px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">累计反思 {cog.total_reflections}次</span>
                  )}
                  {cog.insight_count != null && (
                    <span className="text-[8px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">洞察 {cog.insight_count}个</span>
                  )}
                </div>
              )}
              {!isObj && <div className="text-xs text-slate-300">{String(ref)}</div>}
            </div>
          );
        })()}

        {agiData?.status?.latest_journal && (() => {
          const jnl = agiData.status.latest_journal;
          const entries = Array.isArray(jnl) ? jnl : (typeof jnl === 'object' ? [jnl] : []);
          if (entries.length === 0) return null;
          return (
            <div className="shield-glass rounded-xl p-4">
              <div className="flex items-center gap-2 mb-3">
                <Eye className="w-4 h-4 text-cyan-400" />
                <span className="text-[10px] font-black text-cyan-400">AGI日记</span>
              </div>
              <div className="space-y-3 max-h-[300px] overflow-y-auto">
                {entries.slice(0, 5).map((entry, i) => {
                  const isObj = typeof entry === 'object' && entry !== null;
                  const typeMap = {
                    'llm_deep_reflection': '深度思考',
                    'trade_analysis': '交易分析',
                    'market_observation': '市场观察',
                    'periodic_review': '定期回顾',
                  };
                  return (
                    <div key={i} className="bg-slate-950/40 rounded-lg p-3 border border-slate-800/30">
                      <div className="flex items-center justify-between mb-1.5">
                        {isObj && entry.type && (
                          <span className="text-[8px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 font-bold">{typeMap[entry.type] || entry.type}</span>
                        )}
                        {isObj && entry.time && (
                          <span className="text-[8px] text-slate-600">{entry.time}</span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-300 leading-relaxed">
                        {(() => {
                          if (!isObj) return String(entry);
                          const raw = entry.insight || entry.summary;
                          if (!raw) return JSON.stringify(entry);
                          let parsed = null;
                          try { parsed = typeof raw === 'string' ? JSON.parse(raw) : raw; } catch { parsed = null; }
                          if (!parsed || typeof parsed !== 'object') return raw;

                          const labelMap = {
                            current_weakness: '当前弱点', weakness: '当前弱点',
                            worst_environment: '最差环境', worst_market_env: '最差环境',
                            parameter_adjustments: '参数调整建议', parameter_adjustment: '参数调整建议',
                            parameter_adjustment_suggestion: '参数调整建议',
                            next_learning_priority: '下一步学习重点', next_learning_focus: '下一步学习重点',
                            threshold_increase: '建议提高', threshold_decrease: '建议降低',
                            increase_threshold: '建议提高', decrease_threshold: '建议降低',
                            signal_gate_score: '信号门槛', position_size: '仓位大小', risk_aversion: '风险厌恶度',
                            regime: '市场环境', reason: '原因',
                          };
                          const renderVal = (val, depth = 0) => {
                            if (val === null || val === undefined) return null;
                            if (typeof val === 'string' || typeof val === 'number') return <span>{String(val)}</span>;
                            if (typeof val === 'object') {
                              return (
                                <div className={depth > 0 ? 'pl-3 border-l border-slate-700/40 mt-1' : ''}>
                                  {Object.entries(val).map(([k, v]) => (
                                    <div key={k} className="mb-1.5">
                                      <span className="text-cyan-400/80 font-medium">{labelMap[k] || k}：</span>
                                      {typeof v === 'object' && v !== null
                                        ? renderVal(v, depth + 1)
                                        : <span className="text-slate-200">{String(v)}</span>}
                                    </div>
                                  ))}
                                </div>
                              );
                            }
                            return <span>{String(val)}</span>;
                          };
                          return renderVal(parsed);
                        })()}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </div>
    );
  };

  const sevIcon = (s) => {
    if (s === 'critical') return { color: 'text-red-400 bg-red-500/10 border-red-500/20', label: '严重', dot: 'bg-red-400' };
    if (s === 'warning') return { color: 'text-amber-400 bg-amber-500/10 border-amber-500/20', label: '警告', dot: 'bg-amber-400' };
    if (s === 'suggestion') return { color: 'text-blue-400 bg-blue-500/10 border-blue-500/20', label: '建议', dot: 'bg-blue-400' };
    return { color: 'text-slate-400 bg-slate-500/10 border-slate-500/20', label: '信息', dot: 'bg-slate-400' };
  };

  const inspectorNames = {
    logic_auditor: '逻辑审计员',
    config_sentinel: '配置哨兵',
    performance_doctor: '性能诊断师',
    anomaly_patrol: '异常巡检员',
    architecture_advisor: '架构顾问',
    binance_readiness: '币安就绪评估',
  };

  const renderSelfInspection = () => {
    const rpt = inspectionReport;
    return (
      <div className="space-y-3">
        <div className="bg-slate-900/60 backdrop-blur border border-slate-700/50 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white">系统自检中心</span>
              <span className="text-[9px] text-slate-500">6个AI检查员 · 全方位健康诊断</span>
            </div>
            <button
              onClick={() => runInspection()}
              disabled={inspectionRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-bold bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/30 transition-all disabled:opacity-50"
            >
              <RefreshCw className={`w-3 h-3 ${inspectionRunning ? 'animate-spin' : ''}`} />
              {inspectionRunning ? '检查中...' : '运行全部自检'}
            </button>
          </div>

          {!rpt || !rpt.findings ? (
            <div className="text-center py-8 text-slate-500 text-xs">
              尚未执行自检。点击上方按钮开始全面系统检查。
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-2 text-center">
                  <div className="text-lg font-black text-red-400">{rpt.by_severity?.critical || 0}</div>
                  <div className="text-[9px] text-red-400/70">严重</div>
                </div>
                <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-2 text-center">
                  <div className="text-lg font-black text-amber-400">{rpt.by_severity?.warning || 0}</div>
                  <div className="text-[9px] text-amber-400/70">警告</div>
                </div>
                <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-2 text-center">
                  <div className="text-lg font-black text-blue-400">{rpt.by_severity?.suggestion || 0}</div>
                  <div className="text-[9px] text-blue-400/70">建议</div>
                </div>
                <div className="bg-slate-500/10 border border-slate-500/20 rounded-xl p-2 text-center">
                  <div className="text-lg font-black text-slate-300">{rpt.by_severity?.info || 0}</div>
                  <div className="text-[9px] text-slate-400">信息</div>
                </div>
              </div>

              {rpt.ai_summary && (
                <div className="bg-violet-500/10 border border-violet-500/20 rounded-xl p-3 mb-3">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Brain className="w-3.5 h-3.5 text-violet-400" />
                    <span className="text-[10px] font-bold text-violet-400">AI总结</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap">{rpt.ai_summary}</p>
                </div>
              )}

              <div className="text-[9px] text-slate-500 mb-2">
                检查时间: {fmtTime(rpt.timestamp)} · 耗时: {rpt.duration_seconds?.toFixed(1)}s · 检查器: {rpt.inspectors_run?.join(', ')}
              </div>
            </>
          )}
        </div>

        {rpt?.findings?.length > 0 && (
          <div className="space-y-2">
            {Object.entries(
              rpt.findings.reduce((acc, f) => {
                const key = f.inspector;
                if (!acc[key]) acc[key] = [];
                acc[key].push(f);
                return acc;
              }, {})
            ).map(([inspector, findings]) => (
              <div key={inspector} className="bg-slate-900/60 backdrop-blur border border-slate-700/50 rounded-2xl p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Bug className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-[11px] font-bold text-white">{inspectorNames[inspector] || inspector}</span>
                  <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-700/50 text-slate-400">{findings.length}项</span>
                </div>

                {rpt.inspector_analyses?.[inspector] && (
                  <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-2.5 mb-2">
                    <div className="flex items-center gap-1.5 mb-1">
                      <Brain className="w-3 h-3 text-emerald-400" />
                      <span className="text-[9px] font-bold text-emerald-400">AI深度分析</span>
                    </div>
                    <p className="text-[10px] text-slate-300 leading-relaxed whitespace-pre-wrap">{rpt.inspector_analyses[inspector]}</p>
                  </div>
                )}

                <div className="space-y-1.5">
                  {findings.map((f, i) => {
                    const sv = sevIcon(f.severity);
                    const fKey = `${inspector}-${i}`;
                    const isExpanded = expandedFinding === fKey;
                    const categoryMap = {
                      threshold_conflict: '参数冲突', duplicate_logic: '重复逻辑', parameter_drift: '参数偏差',
                      risk_alignment: '风控对齐', config_integrity: '配置完整性', config_staleness: '配置时效',
                      trading_health: '交易健康', signal_health: '信号健康', module_health: '模块健康',
                      model_freshness: '模型时效', grid_health: '网格健康', code_quality: '代码质量',
                      readiness: '实盘就绪', general: '常规检查'
                    };
                    const friendlyCategory = categoryMap[f.category] || f.category || '常规检查';
                    return (
                      <div
                        key={i}
                        className={`border rounded-xl p-2.5 cursor-pointer transition-all ${sv.color}`}
                        onClick={() => setExpandedFinding(isExpanded ? null : fKey)}
                      >
                        <div className="flex items-start gap-2">
                          <div className={`w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0 ${sv.dot}`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-current/10">{sv.label}</span>
                              <span className="text-[9px] px-1.5 py-0.5 rounded bg-slate-700/30 text-slate-400">{friendlyCategory}</span>
                              <span className="text-[10px] font-bold truncate">{f.title}</span>
                            </div>
                            <p className="text-[10px] opacity-80 leading-relaxed">{f.detail}</p>
                            {isExpanded && f.fix_hint && (
                              <div className="mt-2 bg-emerald-500/5 border border-emerald-500/10 rounded-lg p-2">
                                <div className="flex items-center gap-1 mb-1">
                                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                  <span className="text-[9px] font-bold text-emerald-400">改进建议</span>
                                </div>
                                <span className="text-[10px] text-slate-300 leading-relaxed">{f.fix_hint}</span>
                              </div>
                            )}
                          </div>
                          {isExpanded ? <ChevronUp className="w-3 h-3 opacity-50 flex-shrink-0" /> : <ChevronDown className="w-3 h-3 opacity-50 flex-shrink-0" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="bg-slate-900/60 backdrop-blur border border-slate-700/50 rounded-2xl p-3">
          <div className="text-[10px] font-bold text-white mb-2">单独运行检查器</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(inspectorNames).map(([key, name]) => (
              <button
                key={key}
                onClick={() => runInspection(key)}
                disabled={inspectionRunning}
                className="px-2.5 py-1.5 rounded-lg text-[9px] font-bold bg-slate-800/60 text-slate-400 border border-slate-700/50 hover:text-cyan-400 hover:border-cyan-500/30 transition-all disabled:opacity-50"
              >
                {name}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <Cpu className="w-5 h-5 text-violet-400" />
        <h2 className="text-lg font-black text-white">CTO总部</h2>
        <span className="text-[9px] text-slate-600 font-bold">AI协调中心 · 自动驾驶控制台</span>
      </div>

      <div className="flex gap-1.5 overflow-x-auto scrollbar-hide pb-1">
        {sections.map(s => (
          <button
            key={s.key}
            onClick={() => setSection(s.key)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-[10px] font-bold transition-all whitespace-nowrap ${
              section === s.key
                ? 'bg-violet-500/20 text-violet-400 border border-violet-500/30'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40 border border-transparent'
            }`}
          >
            <s.icon className="w-3.5 h-3.5" />
            {s.label}
          </button>
        ))}
      </div>

      {section === 'cto_report' && renderCtoReport()}
      {section === 'overview' && renderOverview()}
      {section === 'cycles' && renderCycles()}
      {section === 'departments' && renderDepartments()}
      {section === 'directives' && renderDirectives()}
      {section === 'decisions' && renderDecisions()}
      {section === 'self_inspection' && renderSelfInspection()}
      {section === 'risk_control' && <RiskDashboard />}
    </div>
  );
}
