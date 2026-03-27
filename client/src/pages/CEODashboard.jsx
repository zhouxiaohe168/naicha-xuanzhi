import { useState, useEffect, useCallback } from 'react';
import { useShield } from '../hooks/useShieldData';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { GaugeRing, AnimatedNumber, StatusDot } from '../components/ProUI';
import MonteCarloViz from '../components/MonteCarloViz';
import AttributionChart from '../components/AttributionChart';
import {
  Crown, TrendingUp, Shield, Brain, Cpu, Radio, BookOpen,
  Zap, BarChart3, Activity, Wallet, Target, Eye, Database,
  FileText, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp,
  Clock, Crosshair, PieChart
} from 'lucide-react';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const metricColor = (value, good, ok) => {
  if (value == null) return 'text-slate-400';
  if (value >= good) return 'text-emerald-400';
  if (value >= ok) return 'text-amber-400';
  return 'text-red-400';
};

const metricColorInverse = (value, bad, warn) => {
  if (value == null) return 'text-slate-400';
  if (value <= bad) return 'text-emerald-400';
  if (value <= warn) return 'text-amber-400';
  return 'text-red-400';
};

const PhaseZeroTracker = ({ wallStreetMetrics, paperPortfolio }) => {
  const PHASE_START = new Date('2026-02-26T00:00:00');
  const PHASE_DAYS = 56;
  const TRADE_TARGET = 100;
  const CONDITION_A_DEADLINE = '2026-03-26';
  const CONDITION_B_DEADLINE = '2026-04-23';

  const now = new Date();
  const elapsed = Math.max(0, Math.floor((now - PHASE_START) / (1000 * 60 * 60 * 24)));
  const dayProgress = Math.min(elapsed, PHASE_DAYS);
  const dayPct = Math.min((dayProgress / PHASE_DAYS) * 100, 100);

  const ws = wallStreetMetrics || {};
  const pp = paperPortfolio || {};
  const totalTrades = ws.total_trades ?? pp.total_trades ?? 0;
  const tradePct = Math.min((totalTrades / TRADE_TARGET) * 100, 100);

  const directionAccuracy = ws.direction_accuracy ?? pp.direction_accuracy ?? null;
  const hasEnoughData = totalTrades >= 5;

  return (
    <div className="shield-glass border border-amber-500/30 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-black text-amber-400 uppercase tracking-widest flex items-center gap-2">
          <Clock className="w-4 h-4" /> 阶段零观察期
        </h3>
        <span className="text-[9px] font-black text-amber-400/80 bg-amber-500/10 border border-amber-500/20 rounded-full px-3 py-1">
          观察期进行中，不做代码改动
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[9px] text-slate-500 font-black uppercase">天数进度</span>
            <span className="text-[10px] font-black text-amber-400 tabular-nums">第 {dayProgress} 天 / {PHASE_DAYS}天</span>
          </div>
          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-amber-500 to-amber-400 rounded-full transition-all duration-500" style={{ width: `${dayPct}%` }} />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[9px] text-slate-500 font-black uppercase">交易笔数</span>
            <span className="text-[10px] font-black text-amber-400 tabular-nums">{totalTrades} / {TRADE_TARGET}</span>
          </div>
          <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 rounded-full transition-all duration-500" style={{ width: `${tradePct}%` }} />
          </div>
        </div>

        <div>
          <div className="text-[9px] text-slate-500 font-black uppercase mb-1.5">方向准确率</div>
          <div className={`text-lg font-black tabular-nums ${hasEnoughData ? (directionAccuracy >= 45 ? 'text-emerald-400' : 'text-red-400') : 'text-slate-500'}`}>
            {hasEnoughData && directionAccuracy != null ? `${Number(directionAccuracy).toFixed(1)}%` : '--.--%'}
            <span className="text-[9px] text-slate-500 font-bold ml-1.5">目标≥45%</span>
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-[9px] text-slate-500 font-bold">条件A截止</span>
            <span className="text-[10px] font-black text-amber-400 tabular-nums">{CONDITION_A_DEADLINE}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[9px] text-slate-500 font-bold">条件B截止</span>
            <span className="text-[10px] font-black text-amber-400 tabular-nums">{CONDITION_B_DEADLINE}</span>
          </div>
        </div>
      </div>

      <div className="mt-4 p-3 rounded-xl bg-blue-500/5 border border-blue-500/20">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[9px] text-blue-400 font-black uppercase">Condition B 胜率目标</span>
          <span className="text-[10px] font-black text-blue-400 tabular-nums">
            {hasEnoughData && directionAccuracy != null ? `${Number(directionAccuracy).toFixed(1)}%` : '--'} / 45%
          </span>
        </div>
        <div className="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden relative">
          <div className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all duration-500"
            style={{ width: `${hasEnoughData && directionAccuracy != null ? Math.min(Number(directionAccuracy) / 45 * 100, 100) : 0}%` }} />
          <div className="absolute h-full w-0.5 bg-yellow-400 top-0" style={{ left: `${42 / 45 * 100}%` }} title="修复后预期42%" />
        </div>
        <div className="flex justify-between text-[8px] mt-1.5 text-slate-500">
          <span>清洁基线: 34%</span>
          <span className="text-yellow-400">修复后预期: 42-47%</span>
          <span>目标: 45%</span>
        </div>
        <div className="text-[8px] text-slate-600 text-center mt-1.5">
          距 Condition B 评估还有 {Math.max(0, Math.ceil((new Date('2026-04-23') - now) / 86400000))} 天
        </div>
      </div>
    </div>
  );
};

const WsBox = ({ label, value, color, target }) => (
  <div className="bg-[#020617]/60 border border-slate-700/40 rounded-xl p-3 text-center">
    <div className="text-[8px] text-slate-500 font-black uppercase tracking-wide">{label}</div>
    <div className={`text-xl font-black tabular-nums ${color}`}>{safe(value)}</div>
    {target && <div className="text-[8px] text-slate-600 mt-0.5">{target}</div>}
  </div>
);

const ModuleRow = ({ name, status, metric }) => (
  <div className="flex items-center justify-between py-1.5 border-b border-slate-800/50 last:border-0">
    <div className="flex items-center gap-2">
      <StatusDot status={status} pulse={status === 'healthy'} />
      <span className="text-[10px] font-bold text-slate-300">{name}</span>
    </div>
    <span className="text-[10px] font-black text-slate-400 tabular-nums">{safe(metric)}</span>
  </div>
);

const GradeRing = ({ grade, score }) => {
  const gradeColors = { A: '#10b981', B: '#34d399', C: '#f59e0b', D: '#f97316', F: '#ef4444' };
  const color = gradeColors[grade] || '#64748b';
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-20 h-20">
        <svg viewBox="0 0 36 36" className="w-full h-full">
          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="#1e293b" strokeWidth="2.5" />
          <path d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke={color} strokeWidth="2.5" strokeDasharray={`${score}, 100`} strokeLinecap="round" />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-2xl font-black" style={{ color }}>{grade}</span>
        </div>
      </div>
      <div className="text-[9px] text-slate-500 mt-1">{score}/100</div>
    </div>
  );
};

export default function CEODashboard() {
  const {
    wallStreetMetrics, equityHistory, paperPortfolio, paperPositions,
    coordinatorData, capitalSizerData, constitutionStatus,
    autopilotStatus, mlStatus, aiDiagnostic, data, v19Data,
    alphaSignals, riskBudgetData, signalQualityData, agentMemory, gridData,
    protectionLayers,
  } = useShield();

  const [activeTab, setActiveTab] = useState('overview');
  const [ceoReport, setCeoReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportExpanded, setReportExpanded] = useState(true);

  const fetchCeoReport = useCallback(async () => {
    setReportLoading(true);
    try {
      const API = import.meta.env.VITE_API_URL || '';
      const res = await fetch(`${API}/api/ceo-report`);
      const data = await res.json();
      if (!data.error) setCeoReport(data);
    } catch (e) { console.error(e); }
    setReportLoading(false);
  }, []);

  useEffect(() => { fetchCeoReport(); }, []);
  useEffect(() => {
    const t = setInterval(fetchCeoReport, 300000);
    return () => clearInterval(t);
  }, [fetchCeoReport]);

  const ws = wallStreetMetrics || {};
  const pp = paperPortfolio || {};
  const directives = coordinatorData?.strategic_directives || {};
  const winRate = parseFloat(pp.win_rate) || 0;
  const initialCapital = pp.initial_capital || 100000;

  const constitutionHealthy = constitutionStatus?.status !== 'DEAD' && !constitutionStatus?.permanent_breaker;
  const constitutionPaused = constitutionStatus?.daily_breaker || constitutionStatus?.daily_pause;

  const ceoTabs = [
    { id: 'overview', label: '总览', icon: Crown },
    { id: 'attribution', label: '收益归因', icon: PieChart },
    { id: 'monte-carlo', label: '风险模拟', icon: Activity },
  ];

  return (
    <div className="space-y-5 animate-fadeIn">

      <div className="shield-glass-elevated rounded-2xl p-1.5 flex gap-1">
        {ceoTabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-[11px] font-bold transition-all flex-1 justify-center ${
              activeTab === t.id
                ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-black shadow-lg shadow-amber-500/20'
                : 'text-slate-500 hover:bg-slate-800 hover:text-slate-300'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'monte-carlo' && <MonteCarloViz />}

      {activeTab === 'attribution' && <AttributionChart />}

      {activeTab === 'overview' && <>

      <PhaseZeroTracker wallStreetMetrics={wallStreetMetrics} paperPortfolio={pp} />

      {protectionLayers && (
        <div className="shield-glass border border-emerald-500/20 rounded-2xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[10px] font-black text-emerald-400 uppercase tracking-widest flex items-center gap-2">
              <Shield className="w-3.5 h-3.5" /> 7层交易保护
            </h3>
            <span className="text-[9px] font-black text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-full px-2.5 py-0.5">
              {protectionLayers.protection_score}/7 Active
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
            {(protectionLayers.layers || []).map((layer, i) => (
              <div key={i} className={`p-2 rounded-xl text-center border transition-all ${
                layer.active ? 'border-emerald-500/25 bg-emerald-500/5' : 'border-slate-700/40 bg-slate-800/30'
              }`}>
                <div className={`text-[8px] font-black mb-0.5 ${layer.active ? 'text-emerald-400' : 'text-slate-600'}`}>
                  {layer.name}
                </div>
                <div className={`text-[10px] font-bold tabular-nums ${layer.active ? 'text-emerald-300' : 'text-slate-500'}`}>
                  {layer.value}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 border border-amber-500/20 rounded-2xl p-5">
        <h3 className="text-xs font-black text-amber-400 uppercase tracking-widest flex items-center gap-2 mb-4">
          <Crown className="w-4 h-4" /> 华尔街绩效面板
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
          <WsBox label="夏普比率" value={ws.sharpe != null ? Number(ws.sharpe).toFixed(2) : null} color={metricColor(ws.sharpe, 1.5, 0.5)} target="目标 ≥1.5" />
          <WsBox label="索提诺比率" value={ws.sortino != null ? Number(ws.sortino).toFixed(2) : null} color={metricColor(ws.sortino, 2.0, 1.0)} target="目标 ≥2.0" />
          <WsBox label="卡玛比率" value={ws.calmar != null ? Number(ws.calmar).toFixed(2) : null} color={metricColor(ws.calmar, 3.0, 1.0)} target="目标 ≥3.0" />
          <WsBox label="盈利因子" value={ws.profit_factor != null ? Number(ws.profit_factor).toFixed(2) : null} color={metricColor(ws.profit_factor, 2.0, 1.2)} target="目标 ≥2.0" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <WsBox label="年化收益率" value={ws.annualized_return_pct != null ? `${Number(ws.annualized_return_pct).toFixed(1)}%` : null} color={metricColor(ws.annualized_return_pct, 30, 10)} target="目标 ≥30%" />
          <WsBox label="最大回撤" value={ws.max_drawdown_pct != null ? `${Number(ws.max_drawdown_pct).toFixed(1)}%` : null} color={metricColorInverse(Math.abs(ws.max_drawdown_pct || 0), 10, 20)} target="目标 ≤10%" />
          <WsBox label="每笔期望值" value={ws.expectancy != null ? `$${Number(ws.expectancy).toFixed(2)}` : null} color={metricColor(ws.expectancy, 50, 0)} target="目标 >0" />
          <WsBox label="盈亏比" value={ws.risk_reward_ratio != null ? Number(ws.risk_reward_ratio).toFixed(2) : null} color={metricColor(ws.risk_reward_ratio, 2.0, 1.0)} target="目标 ≥2.0" />
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[9px] text-slate-500 font-bold border-t border-slate-700/40 pt-3">
          <span>总交易: <span className="text-slate-300">{safe(ws.total_trades)}</span></span>
          <span>盈/亏: <span className="text-emerald-400">{safe(ws.winning_trades)}</span>/<span className="text-red-400">{safe(ws.losing_trades)}</span></span>
          <span>最佳: <span className="text-emerald-400">{ws.best_trade != null ? `$${Number(ws.best_trade).toFixed(0)}` : '--'}</span></span>
          <span>最差: <span className="text-red-400">{ws.worst_trade != null ? `$${Number(ws.worst_trade).toFixed(0)}` : '--'}</span></span>
          <span>波动率: <span className="text-slate-300">{ws.volatility_annual != null ? `${Number(ws.volatility_annual).toFixed(1)}%` : '--'}</span></span>
          <span>均持仓: <span className="text-slate-300">{ws.avg_holding_hours != null ? `${Number(ws.avg_holding_hours).toFixed(1)}h` : '--'}</span></span>
          <span>连胜/连亏: <span className="text-emerald-400">{safe(ws.consecutive_wins_max)}</span>/<span className="text-red-400">{safe(ws.consecutive_losses_max)}</span></span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="shield-glass rounded-2xl p-5">
          <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-4">
            <Wallet className="w-4 h-4" /> 组合总览
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="stat-card">
              <div className="text-[9px] text-slate-500 font-black uppercase">总资产</div>
              <div className="text-lg font-black text-white tabular-nums">
                $<AnimatedNumber value={pp.equity || 0} decimals={0} />
              </div>
            </div>
            <div className="stat-card">
              <div className="text-[9px] text-slate-500 font-black uppercase">累计收益</div>
              <div className={`text-lg font-black tabular-nums ${(pp.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {(pp.total_pnl || 0) >= 0 ? '+' : ''}$<AnimatedNumber value={pp.total_pnl || 0} decimals={0} />
              </div>
            </div>
            <div className="stat-card">
              <div className="text-[9px] text-slate-500 font-black uppercase">收益率</div>
              <div className={`text-lg font-black tabular-nums ${(pp.total_pnl_pct || pp.total_return_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                <AnimatedNumber value={pp.total_pnl_pct || pp.total_return_pct || 0} decimals={2} suffix="%" prefix={(pp.total_pnl_pct || pp.total_return_pct || 0) >= 0 ? '+' : ''} />
              </div>
            </div>
            <div className="flex flex-col items-center justify-center stat-card">
              <GaugeRing value={winRate} max={100} size={52} strokeWidth={4} color={winRate >= 50 ? '#10b981' : '#f59e0b'} sublabel="%" />
              <span className="text-[8px] text-slate-500 font-bold uppercase mt-1">胜率</span>
            </div>
            <div className="stat-card">
              <div className="text-[9px] text-slate-500 font-black uppercase">回撤</div>
              <div className="text-lg font-black text-red-400 tabular-nums">
                {pp.max_drawdown_pct ?? 0}%
              </div>
            </div>
          </div>
        </div>

        <div className="shield-glass rounded-2xl p-5">
          <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4" /> 权益曲线
          </h3>
          {equityHistory.length > 1 ? (
            <div className="h-48">
              <ResponsiveContainer width="100%" height={192}>
                <AreaChart data={equityHistory} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <defs>
                    <linearGradient id="ceoEqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#64748b' }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 8, fill: '#64748b' }} axisLine={false} tickLine={false} domain={['auto', 'auto']} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} formatter={(v) => [`$${Number(v).toLocaleString()}`, '净值']} labelFormatter={(l) => l} />
                  <ReferenceLine y={initialCapital} stroke="#475569" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey="equity" stroke="#06b6d4" fill="url(#ceoEqGrad)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-48 flex items-center justify-center text-[10px] text-slate-600">暂无权益数据</div>
          )}
        </div>
      </div>

      <div className="shield-glass rounded-2xl p-5">
        <h3 className="text-xs font-black text-violet-400 uppercase tracking-widest flex items-center gap-2 mb-4">
          <Cpu className="w-4 h-4" /> AI模块总结看板
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="border-l-2 border-emerald-500 pl-3">
            <div className="text-[9px] font-black text-emerald-400 uppercase tracking-wide mb-2">信号组</div>
            <ModuleRow
              name="ML引擎"
              status={parseFloat(mlStatus?.accuracy) >= 60 ? 'healthy' : parseFloat(mlStatus?.accuracy) >= 40 ? 'warning' : 'danger'}
              metric={mlStatus?.accuracy != null ? `${mlStatus.accuracy}%` : '--'}
            />
            <ModuleRow
              name="信号质量"
              status={signalQualityData ? 'healthy' : 'offline'}
              metric={alphaSignals?.length != null ? `${alphaSignals.length}个强信号` : '--'}
            />
            <ModuleRow
              name="扫描状态"
              status={data?.total_scanned > 0 ? 'healthy' : 'offline'}
              metric={data?.total_scanned != null ? `${data.total_scanned}已扫` : '--'}
            />
          </div>

          <div className="border-l-2 border-red-500 pl-3">
            <div className="text-[9px] font-black text-red-400 uppercase tracking-wide mb-2">风控组</div>
            <ModuleRow
              name="宪法状态"
              status={!constitutionStatus ? 'offline' : constitutionStatus.status === 'DEAD' || constitutionStatus.permanent_breaker ? 'danger' : constitutionPaused ? 'warning' : 'healthy'}
              metric={!constitutionStatus ? '--' : constitutionStatus.status === 'DEAD' ? '熔断' : constitutionPaused ? '暂停' : '健康'}
            />
            <ModuleRow
              name="风险预算"
              status={riskBudgetData ? 'healthy' : 'offline'}
              metric={(() => {
                if (!riskBudgetData) return '--';
                const remaining = riskBudgetData.daily_remaining;
                const limit = riskBudgetData.daily_loss_limit;
                if (remaining != null && limit) return `${((remaining / limit) * 100).toFixed(0)}%剩余`;
                if (riskBudgetData.rebalance_count != null) return `${riskBudgetData.rebalance_count}次平衡`;
                return '运行中';
              })()}
            />
            <ModuleRow
              name="资金定量器"
              status={capitalSizerData?.mc_constitution?.loaded ? 'healthy' : capitalSizerData ? 'warning' : 'offline'}
              metric={(() => {
                if (!capitalSizerData) return '--';
                const mc = capitalSizerData.mc_constitution;
                if (mc?.loaded && mc?.calmar != null) return `卡玛${Number(mc.calmar).toFixed(2)}`;
                if (capitalSizerData.total_sized > 0) return `${capitalSizerData.total_sized}次定量`;
                return 'MC已加载';
              })()}
            />
          </div>

          <div className="border-l-2 border-amber-500 pl-3">
            <div className="text-[9px] font-black text-amber-400 uppercase tracking-wide mb-2">执行组</div>
            <ModuleRow
              name="自动驾驶"
              status={autopilotStatus?.running ? 'healthy' : 'offline'}
              metric={autopilotStatus?.running ? `周期${autopilotStatus.cycle_count || 0}` : '离线'}
            />
            <ModuleRow
              name="持仓顾问"
              status={(paperPositions?.length || 0) + (gridData?.active_grids || 0) > 0 ? 'healthy' : 'warning'}
              metric={(() => {
                const pos = paperPositions?.length || 0;
                const grids = gridData?.active_grids || 0;
                if (pos > 0 && grids > 0) return `${pos}持仓+${grids}网格`;
                if (grids > 0) return `${grids}个网格`;
                return `${pos}个持仓`;
              })()}
            />
            <ModuleRow
              name="纸面交易"
              status={pp.equity ? 'healthy' : 'offline'}
              metric={pp.equity ? `$${Number(pp.equity).toFixed(0)}` : '--'}
            />
          </div>

          <div className="border-l-2 border-violet-500 pl-3">
            <div className="text-[9px] font-black text-violet-400 uppercase tracking-wide mb-2">学习组</div>
            <ModuleRow
              name="CTO协调"
              status={coordinatorData ? 'healthy' : 'offline'}
              metric={coordinatorData?.stats?.total_coordinations != null ? `${coordinatorData.stats.total_coordinations}周期` : '--'}
            />
            <ModuleRow
              name="AI诊断"
              status={(() => {
                const score = aiDiagnostic?.latest_report?.diagnosis?.health_score ?? data?.ai_reviewer?.avg_score;
                if (score == null) return 'offline';
                return score >= 70 ? 'healthy' : score >= 40 ? 'warning' : 'danger';
              })()}
              metric={(() => {
                const score = aiDiagnostic?.latest_report?.diagnosis?.health_score;
                if (score != null) return `${score}/100`;
                const avg = data?.ai_reviewer?.avg_score;
                if (avg != null) return `${avg}/100`;
                return '--';
              })()}
            />
            <ModuleRow
              name="记忆系统"
              status={agentMemory ? 'healthy' : v19Data ? 'healthy' : 'offline'}
              metric={(() => {
                if (agentMemory?.insights_count != null) return `${agentMemory.insights_count}条洞察`;
                if (agentMemory?.session_count != null) return `${agentMemory.session_count}次会话`;
                return aiDiagnostic?.stats?.total_diagnostics != null ? `${aiDiagnostic.stats.total_diagnostics}次诊断` : '--';
              })()}
            />
          </div>
        </div>
      </div>

      {coordinatorData?.intelligence_summary && Object.keys(coordinatorData.intelligence_summary).length > 0 && (
        <div className="shield-glass rounded-2xl p-5">
          <h3 className="text-xs font-black text-teal-400 uppercase tracking-widest flex items-center gap-2 mb-4">
            <BookOpen className="w-4 h-4" /> CTO部门汇报
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(coordinatorData.intelligence_summary).map(([dept, summary]) => {
              const deptMap = {
                reviewer: { name: '审查部', color: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/5', icon: '🔍' },
                diagnostic: { name: '诊断部', color: 'text-violet-400 border-violet-500/30 bg-violet-500/5', icon: '🩺' },
                return_rate: { name: '收益部', color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/5', icon: '📈' },
                synapse: { name: '协同部', color: 'text-amber-400 border-amber-500/30 bg-amber-500/5', icon: '🧠' },
                agent_memory: { name: '记忆部', color: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/5', icon: '💾' },
              };
              const info = deptMap[dept] || { name: dept, color: 'text-slate-400 border-slate-500/30 bg-slate-500/5', icon: '📋' };
              return (
                <div key={dept} className={`border rounded-xl p-3 ${info.color}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm">{info.icon}</span>
                    <span className="text-[10px] font-black uppercase tracking-wide">{info.name}</span>
                  </div>
                  <div className="text-[10px] text-slate-300 leading-relaxed line-clamp-3">
                    {typeof summary === 'object' ? (summary?.summary || JSON.stringify(summary)) : (summary || '暂无汇报')}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {coordinatorData?.strategic_directives && (
        <div className="shield-glass rounded-2xl p-5">
          <h3 className="text-xs font-black text-indigo-400 uppercase tracking-widest flex items-center gap-2 mb-4">
            <Eye className="w-4 h-4" /> CTO最新指令
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="stat-card">
              <div className="text-[8px] text-slate-500 font-bold">仓位倍率</div>
              <div className="text-sm font-black text-cyan-400 tabular-nums">{coordinatorData?.recent_coordinations?.[0]?.size_mult != null ? coordinatorData.recent_coordinations[0].size_mult + 'x' : '--'}</div>
            </div>
            <div className="stat-card">
              <div className="text-[8px] text-slate-500 font-bold">激进模式</div>
              <div className={`text-sm font-black tabular-nums ${directives.aggression_mode === 'conservative' ? 'text-emerald-400' : directives.aggression_mode === 'aggressive' ? 'text-red-400' : 'text-amber-400'}`}>
                {directives.aggression_mode === 'conservative' ? '保守' : directives.aggression_mode === 'aggressive' ? '激进' : directives.aggression_mode === 'normal' ? '标准' : safe(directives.aggression_mode)}
              </div>
            </div>
            <div className="stat-card">
              <div className="text-[8px] text-slate-500 font-bold">最大持仓数</div>
              <div className="text-sm font-black text-white tabular-nums">{safe(directives.max_concurrent_positions)}</div>
            </div>
            <div className="stat-card">
              <div className="text-[8px] text-slate-500 font-bold">最低信号分</div>
              <div className="text-sm font-black text-amber-400 tabular-nums">{safe(directives.min_signal_score)}</div>
            </div>
            <div className="stat-card">
              <div className="text-[8px] text-slate-500 font-bold">策略偏好</div>
              <div className="text-sm font-black text-violet-400 truncate">{safe(directives.strategy_preference)}</div>
            </div>
            <div className="stat-card">
              <div className="text-[8px] text-slate-500 font-bold">黑名单</div>
              <div className="text-[10px] font-black text-red-400 truncate">
                {Array.isArray(directives.asset_blacklist) ? (directives.asset_blacklist.length > 0 ? directives.asset_blacklist.join(', ') : '无') : safe(directives.asset_blacklist)}
              </div>
            </div>
          </div>
        </div>
      )}

      {ceoReport && (
        <div className="bg-gradient-to-br from-slate-900 via-[#0c1222] to-slate-900 border border-violet-500/30 rounded-2xl overflow-hidden">
          <div
            className="flex items-center justify-between p-5 cursor-pointer hover:bg-slate-800/30 transition-colors"
            onClick={() => setReportExpanded(!reportExpanded)}
          >
            <h3 className="text-xs font-black text-violet-400 uppercase tracking-widest flex items-center gap-2">
              <FileText className="w-4 h-4" /> CEO战略评估报告
            </h3>
            <div className="flex items-center gap-3">
              <span className="text-[8px] text-slate-500">{ceoReport.report_time}</span>
              <button onClick={(e) => { e.stopPropagation(); fetchCeoReport(); }} className="text-[8px] text-violet-400 hover:text-violet-300 font-bold">
                {reportLoading ? '刷新中...' : '刷新'}
              </button>
              {reportExpanded ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
            </div>
          </div>

          {reportExpanded && (
            <div className="px-5 pb-5 space-y-4">
              <div className="flex items-center gap-6 p-4 bg-slate-950/50 rounded-xl">
                <GradeRing grade={ceoReport.executive_summary?.health_grade} score={ceoReport.executive_summary?.health_score || 0} />
                <div className="flex-1">
                  <div className="text-sm font-bold text-white mb-1">{ceoReport.executive_summary?.verdict}</div>
                  {ceoReport.executive_summary?.key_issues?.length > 0 && (
                    <div className="space-y-1">
                      {ceoReport.executive_summary.key_issues.map((issue, i) => (
                        <div key={i} className="flex items-center gap-1.5">
                          <AlertTriangle className="w-3 h-3 text-amber-400 flex-shrink-0" />
                          <span className="text-[10px] text-amber-300">{issue}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-950/40 rounded-lg p-3 text-center">
                  <div className="text-[8px] text-slate-500 font-bold">市场环境</div>
                  <div className="text-sm font-black text-amber-400">{ceoReport.market_environment?.regime}</div>
                  <div className="text-[8px] text-slate-600">FNG: {ceoReport.market_environment?.fear_greed_index}</div>
                </div>
                <div className="bg-slate-950/40 rounded-lg p-3 text-center">
                  <div className="text-[8px] text-slate-500 font-bold">组合收益</div>
                  <div className={`text-sm font-black ${(ceoReport.portfolio_performance?.total_return_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {(ceoReport.portfolio_performance?.total_return_pct || 0).toFixed(3)}%
                  </div>
                  <div className="text-[8px] text-slate-600">${ceoReport.portfolio_performance?.total_pnl_usd?.toFixed(2)}</div>
                </div>
                <div className="bg-slate-950/40 rounded-lg p-3 text-center">
                  <div className="text-[8px] text-slate-500 font-bold">交易胜率</div>
                  <div className={`text-sm font-black ${(ceoReport.portfolio_performance?.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {ceoReport.portfolio_performance?.win_rate?.toFixed(1)}%
                  </div>
                  <div className="text-[8px] text-slate-600">{ceoReport.portfolio_performance?.total_trades}笔交易</div>
                </div>
                <div className="bg-slate-950/40 rounded-lg p-3 text-center">
                  <div className="text-[8px] text-slate-500 font-bold">最大回撤</div>
                  <div className={`text-sm font-black ${Math.abs(ceoReport.portfolio_performance?.max_drawdown_pct || 0) < 5 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {ceoReport.portfolio_performance?.max_drawdown_pct?.toFixed(3)}%
                  </div>
                  <div className="text-[8px] text-slate-600">风险: {ceoReport.portfolio_performance?.risk_assessment}</div>
                </div>
              </div>

              <div className="bg-slate-950/40 rounded-xl p-4">
                <div className="text-[10px] font-black text-cyan-400 mb-3">策略矩阵分析</div>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { key: 'trend_following', name: '趋势跟踪', icon: '📈', data: ceoReport.strategy_analysis?.trend_following },
                    { key: 'range_harvester', name: '区间收割', icon: '📊', data: ceoReport.strategy_analysis?.range_harvester },
                    { key: 'grid_trading', name: '网格交易', icon: '🔲', data: ceoReport.strategy_analysis?.grid_trading },
                  ].map(s => (
                    <div key={s.key} className="bg-slate-900/60 rounded-lg p-3">
                      <div className="text-[9px] font-bold text-slate-400 mb-2">{s.icon} {s.name}</div>
                      <div className="text-xs font-black text-white">{s.data?.total_trades || 0}笔</div>
                      <div className={`text-[10px] font-bold ${(s.data?.win_rate || 0) >= 40 ? 'text-emerald-400' : (s.data?.win_rate || 0) > 0 ? 'text-amber-400' : 'text-slate-600'}`}>
                        胜率: {s.data?.win_rate?.toFixed(1) || 0}%
                      </div>
                      <div className={`text-[10px] font-bold ${(s.data?.pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        盈亏: ${(s.data?.pnl || 0).toFixed(2)}
                      </div>
                      <div className={`text-[8px] mt-1 font-bold ${
                        s.data?.verdict?.includes('亏损') ? 'text-red-400' : s.data?.verdict?.includes('待激活') ? 'text-slate-500' : 'text-emerald-400'
                      }`}>
                        {s.data?.verdict}
                      </div>
                      {s.data?.worst_assets?.length > 0 && (
                        <div className="text-[7px] text-slate-600 mt-1">高亏损: {s.data.worst_assets.slice(0,3).join(', ')}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-slate-950/40 rounded-xl p-4">
                  <div className="text-[10px] font-black text-violet-400 mb-3">ML智能系统</div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">模型版本</span>
                      <span className="text-[10px] font-bold text-white">{ceoReport.ml_intelligence?.model_version}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">准确率</span>
                      <span className={`text-[10px] font-bold ${(ceoReport.ml_intelligence?.accuracy || 0) >= 70 ? 'text-emerald-400' : 'text-amber-400'}`}>
                        {ceoReport.ml_intelligence?.accuracy?.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">F1分数</span>
                      <span className="text-[10px] font-bold text-cyan-400">{ceoReport.ml_intelligence?.f1_score?.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">交叉验证</span>
                      <span className="text-[10px] font-bold text-white">{ceoReport.ml_intelligence?.cv_accuracy?.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">训练样本</span>
                      <span className="text-[10px] font-bold text-white">{(ceoReport.ml_intelligence?.training_samples || 0).toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">云端训练</span>
                      <span className={`text-[10px] font-bold ${ceoReport.ml_intelligence?.deep_trained ? 'text-emerald-400' : 'text-slate-500'}`}>
                        {ceoReport.ml_intelligence?.deep_trained ? '已完成' : '未完成'}
                      </span>
                    </div>
                  </div>
                  {ceoReport.ml_intelligence?.per_class && Object.keys(ceoReport.ml_intelligence.per_class).length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800/50">
                      <div className="text-[8px] text-slate-500 mb-2">分类详情</div>
                      {Object.entries(ceoReport.ml_intelligence.per_class).map(([cls, v]) => (
                        <div key={cls} className="flex items-center justify-between py-0.5">
                          <span className={`text-[9px] font-bold ${cls === '涨' ? 'text-emerald-400' : cls === '跌' ? 'text-red-400' : 'text-amber-400'}`}>{cls}</span>
                          <span className="text-[8px] text-slate-400">F1: {v.f1?.toFixed(1)}% | 召回: {v.recall?.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="bg-slate-950/40 rounded-xl p-4">
                  <div className="text-[10px] font-black text-emerald-400 mb-3">CTO自治状态</div>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">运行周期</span>
                      <span className="text-[10px] font-bold text-white">{ceoReport.cto_autonomy?.autopilot_cycles}次</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">运行时间</span>
                      <span className="text-[10px] font-bold text-cyan-400">{ceoReport.cto_autonomy?.uptime_hours?.toFixed(1)}h</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">ML权重</span>
                      <span className="text-[10px] font-bold text-violet-400">
                        {((ceoReport.cto_autonomy?.adaptive_weights?.ml_weight || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">规则权重</span>
                      <span className="text-[10px] font-bold text-white">
                        {((ceoReport.cto_autonomy?.adaptive_weights?.rule_weight || 0) * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">仓位乘数</span>
                      <span className="text-[10px] font-bold text-amber-400">{ceoReport.cto_autonomy?.coordinator?.size_multiplier}x</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-[9px] text-slate-500">风险级别</span>
                      <span className={`text-[10px] font-bold ${
                        ceoReport.cto_autonomy?.coordinator?.risk_level === 'low' ? 'text-emerald-400' : ceoReport.cto_autonomy?.coordinator?.risk_level === 'high' ? 'text-red-400' : 'text-amber-400'
                      }`}>{ceoReport.cto_autonomy?.coordinator?.risk_level}</span>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-800/50">
                    <div className="text-[8px] text-slate-500 mb-2">风控状态</div>
                    <div className="flex items-center gap-2">
                      {ceoReport.risk_control?.permanent_breaker ? (
                        <span className="text-[9px] font-bold text-red-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />永久熔断</span>
                      ) : ceoReport.risk_control?.daily_breaker ? (
                        <span className="text-[9px] font-bold text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3 h-3" />日内暂停</span>
                      ) : (
                        <span className="text-[9px] font-bold text-emerald-400 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />{ceoReport.risk_control?.constitution_status}</span>
                      )}
                    </div>
                    <div className="text-[8px] text-slate-600 mt-1">风控拦截: {ceoReport.risk_control?.blocked_trades_total}笔</div>
                  </div>
                </div>
              </div>

              {ceoReport.strategic_recommendations?.length > 0 && (
                <div className="bg-slate-950/40 rounded-xl p-4">
                  <div className="text-[10px] font-black text-amber-400 mb-3">战略建议</div>
                  <div className="space-y-2">
                    {ceoReport.strategic_recommendations.map((rec, i) => (
                      <div key={i} className={`flex items-start gap-3 p-3 rounded-lg ${
                        rec.priority === '高' ? 'bg-red-950/30 border border-red-500/20' :
                        rec.priority === '中' ? 'bg-amber-950/30 border border-amber-500/20' :
                        'bg-slate-900/50 border border-slate-700/20'
                      }`}>
                        <div className={`text-[9px] font-black px-2 py-0.5 rounded-full flex-shrink-0 ${
                          rec.priority === '高' ? 'bg-red-500/20 text-red-400' :
                          rec.priority === '中' ? 'bg-amber-500/20 text-amber-400' :
                          'bg-slate-500/20 text-slate-400'
                        }`}>{rec.priority}</div>
                        <div className="flex-1 min-w-0">
                          <div className="text-[9px] font-bold text-slate-300">[{rec.category}] {rec.action}</div>
                          <div className="text-[8px] text-slate-500 mt-0.5">{rec.expected_impact}</div>
                          {rec.auto_adjustable && (
                            <div className="text-[7px] text-emerald-500 mt-0.5 flex items-center gap-1">
                              <CheckCircle2 className="w-2.5 h-2.5" /> CTO可自动调整
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {ceoReport.market_environment?.market_assessment && (
                <div className="bg-slate-950/40 rounded-xl p-4">
                  <div className="text-[10px] font-black text-cyan-400 mb-2">市场展望</div>
                  <div className="text-[10px] text-slate-300 leading-relaxed">{ceoReport.market_environment.market_assessment}</div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      </>}

    </div>
  );
}