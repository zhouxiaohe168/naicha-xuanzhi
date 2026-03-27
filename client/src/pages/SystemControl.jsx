import { useState, useCallback, useEffect } from 'react';
import {
  Power, Cloud, Bell, Play, Square, RefreshCw,
  TrendingUp, DollarSign, Target, Brain, Cpu, X,
  AlertTriangle, Info, AlertCircle, Clock, Zap, BarChart3,
  Shield, Activity
} from 'lucide-react';
import { useShield } from '../hooks/useShieldData';
import { StatusDot, GaugeRing } from '../components/ProUI';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const tabs = [
  { key: 'autopilot', label: '自动驾驶', icon: Power },
  { key: 'training', label: '云端训练', icon: Cloud },
  { key: 'llm', label: 'AI引擎', icon: Brain },
  { key: 'notifications', label: '系统通知', icon: Bell },
];

export default function SystemControl() {
  const {
    autopilotStatus, mlStatus, data, notifications,
    pipelineData, pipelinePolling, setPipelinePolling, fetchData,
    constitutionStatus, aiDiagnostic, paperPositions,
  } = useShield();

  const [activeSection, setActiveSection] = useState('autopilot');
  const [autopilotLoading, setAutopilotLoading] = useState(false);
  const [modalTrainLoading, setModalTrainLoading] = useState(false);
  const [modalStatusData, setModalStatusData] = useState(null);
  const [modalStatusLoading, setModalStatusLoading] = useState(false);
  const [megaLoading, setMegaLoading] = useState(false);
  const [llmData, setLlmData] = useState(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState(null);
  const [llmTestLoading, setLlmTestLoading] = useState(false);

  useEffect(() => {
    if (activeSection === 'llm' && !llmData) {
      (async () => {
        setLlmLoading(true);
        try {
          const [statusR, telR] = await Promise.all([
            fetch('/api/llm/status'), fetch('/api/llm/telemetry')
          ]);
          const status = await statusR.json();
          const tel = await telR.json();
          setLlmData({ ...status, telemetry: tel });
        } catch (e) { console.error(e); }
        setLlmLoading(false);
      })();
    }
  }, [activeSection]);
  const [megaResult, setMegaResult] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/mega-backtest');
        if (res.ok) setMegaResult(await res.json());
      } catch {}
    })();
  }, []);

  const toggleAutopilot = useCallback(async () => {
    setAutopilotLoading(true);
    try {
      const running = autopilotStatus?.running;
      await fetch(`/api/autopilot/${running ? 'stop' : 'start'}`, { method: 'POST' });
      setTimeout(() => { fetchData?.(); setAutopilotLoading(false); }, 1500);
    } catch {
      setAutopilotLoading(false);
    }
  }, [autopilotStatus, fetchData]);

  const triggerModalTrain = useCallback(async () => {
    setModalTrainLoading(true);
    try {
      await fetch('/api/modal/train', { method: 'POST' });
      fetchData?.();
    } catch {}
    setTimeout(() => setModalTrainLoading(false), 3000);
  }, [fetchData]);

  const checkModalStatus = useCallback(async () => {
    setModalStatusLoading(true);
    try {
      const res = await fetch('/api/modal/status');
      if (res.ok) setModalStatusData(await res.json());
    } catch {}
    setModalStatusLoading(false);
  }, []);

  const runMegaBacktest = useCallback(async () => {
    setMegaLoading(true);
    try {
      await fetch('/api/mega-backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ iterations: 100 }),
      });
      const res = await fetch('/api/mega-backtest');
      if (res.ok) setMegaResult(await res.json());
    } catch {}
    setTimeout(() => { setMegaLoading(false); fetchData?.(); }, 3000);
  }, [fetchData]);

  const moduleNameMap = { trade_judge: '交易裁判', ai_reviewer: 'AI审查', ai_diagnostic: 'AI诊断', position_advisor: '持仓顾问', signal_quality: '信号质量', synapse: '协同学习', deep_evolution: '深度进化', return_rate_agent: '收益诊断', scoring_engine: '评分引擎', watchdog: '看门狗', dispatcher: '调度器', agi: '总情报', analyst: '分析师', ml_regime: '市场研判', external_data: '外部数据', coordinator: 'CTO协调', signal_gate: '信号门控', memory_bank: '记忆系统' };
  const isRunning = autopilotStatus?.running;

  const healthScore = aiDiagnostic?.latest_report?.diagnosis?.health_score ?? aiDiagnostic?.latest_report?.health_score ?? null;
  const drawdownPct = constitutionStatus?.current_drawdown ?? paperPositions?.reduce?.((worst, p) => {
    const pnl = parseFloat(p.pnl_pct || p.profit_pct || 0);
    return pnl < worst ? pnl : worst;
  }, 0) ?? 0;
  const maxPositions = constitutionStatus?.max_positions ?? 5;
  const activePositionCount = paperPositions?.length ?? 0;
  const drawdownColor = Math.abs(drawdownPct) < 2 ? 'text-emerald-400' : Math.abs(drawdownPct) < 5 ? 'text-amber-400' : 'text-red-400';
  const drawdownBorder = Math.abs(drawdownPct) < 2 ? 'border-emerald-500/30' : Math.abs(drawdownPct) < 5 ? 'border-amber-500/30' : 'border-red-500/30';
  const healthColor = healthScore == null ? '#64748b' : healthScore >= 70 ? '#10b981' : healthScore >= 40 ? '#f59e0b' : '#ef4444';

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="shield-glass rounded-2xl p-4 border border-amber-500/40 shadow-lg shadow-amber-500/5">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-black text-amber-400 uppercase tracking-widest">紧急控制台</span>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 flex flex-col items-center gap-2">
            <div className="text-[9px] text-slate-500 font-black uppercase">自动驾驶</div>
            <div className="flex items-center gap-2">
              <StatusDot status={isRunning ? 'healthy' : 'offline'} />
              <span className={`text-sm font-black ${isRunning ? 'text-emerald-400' : 'text-red-400'}`}>
                {isRunning ? '运行中' : '已停止'}
              </span>
            </div>
            <button
              onClick={toggleAutopilot}
              disabled={autopilotLoading}
              className={`px-3 py-1 rounded-lg text-[10px] font-black transition-all ${
                autopilotLoading ? 'opacity-50 cursor-wait' :
                isRunning
                  ? 'bg-red-500/20 border border-red-500/30 text-red-400 hover:bg-red-500/30'
                  : 'bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/30'
              }`}
            >
              {autopilotLoading ? '切换中...' : isRunning ? '停止' : '启动'}
            </button>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 flex flex-col items-center gap-2">
            <div className="text-[9px] text-slate-500 font-black uppercase">系统健康</div>
            <GaugeRing value={healthScore ?? 0} max={100} size={52} color={healthColor} label="" />
            <span className="text-[10px] font-bold" style={{ color: healthColor }}>
              {healthScore != null ? `${Math.round(healthScore)}分` : '--'}
            </span>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 flex flex-col items-center gap-2">
            <div className="text-[9px] text-slate-500 font-black uppercase">当前回撤</div>
            <div className={`text-xl font-black ${drawdownColor}`}>
              {typeof drawdownPct === 'number' ? `${drawdownPct.toFixed(2)}%` : '--'}
            </div>
            <div className={`text-[9px] px-2 py-0.5 rounded-full border ${drawdownBorder} ${drawdownColor} font-bold`}>
              {Math.abs(drawdownPct) < 2 ? '安全' : Math.abs(drawdownPct) < 5 ? '警告' : '危险'}
            </div>
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 flex flex-col items-center gap-2">
            <div className="text-[9px] text-slate-500 font-black uppercase">活跃持仓</div>
            <div className="text-xl font-black text-cyan-400">
              {activePositionCount} <span className="text-sm text-slate-500">/ {maxPositions}</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5">
              <div
                className="h-1.5 rounded-full bg-cyan-500 transition-all"
                style={{ width: `${Math.min((activePositionCount / maxPositions) * 100, 100)}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveSection(tab.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all whitespace-nowrap ${
              activeSection === tab.key
                ? 'bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 shadow-lg shadow-cyan-500/10'
                : 'bg-slate-900/40 border border-slate-800 text-slate-500 hover:text-slate-300 hover:border-slate-700'
            }`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
            {tab.key === 'notifications' && notifications?.length > 0 && (
              <span className="ml-1 bg-red-500 text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full">
                {notifications.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {activeSection === 'autopilot' && (
        <div className="space-y-4">
          <div className="shield-glass rounded-2xl p-6 border border-slate-700/50">
            <div className="flex flex-col items-center gap-4">
              <div className="text-xs font-black text-slate-500 uppercase tracking-widest">自动驾驶控制</div>
              <button
                onClick={toggleAutopilot}
                disabled={autopilotLoading}
                className={`w-32 h-32 rounded-full flex items-center justify-center transition-all duration-500 ${
                  autopilotLoading ? 'opacity-50 cursor-wait' :
                  isRunning
                    ? 'bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-2xl shadow-emerald-500/40 hover:shadow-emerald-500/60 border-2 border-emerald-400/50'
                    : 'bg-gradient-to-br from-red-500 to-red-700 shadow-2xl shadow-red-500/40 hover:shadow-red-500/60 border-2 border-red-400/50'
                }`}
              >
                {autopilotLoading ? (
                  <RefreshCw className="w-10 h-10 text-white animate-spin" />
                ) : isRunning ? (
                  <Square className="w-10 h-10 text-white" />
                ) : (
                  <Play className="w-10 h-10 text-white ml-1" />
                )}
              </button>
              <div className="text-center">
                <div className={`text-lg font-black ${isRunning ? 'text-emerald-400' : 'text-red-400'}`}>
                  {autopilotLoading ? '切换中...' : isRunning ? '运行中' : '已停止'}
                </div>
                <div className="text-[10px] text-slate-500 mt-1">
                  {isRunning ? '点击停止自动驾驶' : '点击启动自动驾驶'}
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">运行状态</div>
              <div className="flex items-center justify-center gap-2 mt-1">
                <StatusDot status={isRunning ? 'healthy' : 'offline'} />
                <span className={`text-sm font-black ${isRunning ? 'text-emerald-400' : 'text-slate-500'}`}>
                  {isRunning ? '在线' : '离线'}
                </span>
              </div>
            </div>
            <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">循环次数</div>
              <div className="text-xl font-black text-white mt-1">{safe(autopilotStatus?.cycle_count)}</div>
            </div>
            <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">运行时长</div>
              <div className="text-[10px] font-bold text-slate-300 mt-1">{autopilotStatus?.uptime_hours ? autopilotStatus.uptime_hours.toFixed(1) + '小时' : '--'}</div>
            </div>
            <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">待处理决策</div>
              <div className="text-[10px] font-bold text-cyan-400 mt-1">{safe(autopilotStatus?.pending_ceo_decisions)}</div>
            </div>
          </div>

          <div className="shield-glass rounded-xl p-4 border border-slate-800">
            <div className="flex items-center gap-2 mb-2">
              <Clock className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-[10px] text-slate-500 font-black uppercase">循环间隔</span>
            </div>
            <div className="text-sm font-bold text-white">{autopilotStatus?.cycle_interval_sec ? `${Math.round(autopilotStatus.cycle_interval_sec / 60)}分钟` : safe(autopilotStatus?.cycle_interval)}</div>
          </div>

          {autopilotStatus?.recent_actions?.length > 0 && (
            <div className="shield-glass rounded-xl p-4 border border-slate-800">
              <div className="text-[10px] text-slate-500 font-black uppercase mb-2">最近操作</div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {autopilotStatus.recent_actions.slice().reverse().map((action, i) => (
                  <div key={i} className="text-[10px] text-slate-400 bg-slate-950/50 rounded-lg px-3 py-1.5">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500 font-mono">{action.time ? action.time.replace('T', ' ').slice(5, 16) : ''}</span>
                      <span className="text-cyan-400 font-bold">{
                        ({'update_signal_gate':'信号门更新','scan_complete':'扫描完成','auto_cloud_training':'定时云训练','retrain_model':'ML重训','adjust_weights':'权重调整','risk_check':'风控检查','open_position':'开仓','close_position':'平仓','stop_loss':'止损','take_profit':'止盈','calibrate':'校准','constitution_check':'宪法检查','daily_report':'每日报告','pause_trading':'暂停交易','tighten_filters':'收紧过滤','suggest_retrain':'建议重训'})[action.action] || action.action
                      }</span>
                    </div>
                    <div className="text-[9px] text-slate-500 mt-0.5">{action.reason || ''}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeSection === 'training' && (
        <div className="space-y-4">
          <div className="shield-glass rounded-2xl p-5 border border-slate-700/50">
            <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center gap-2 mb-4">
              <Brain className="w-4 h-4" /> ML 模型状态
            </h3>
            {(() => {
              const acc = mlStatus?.accuracy ?? 0;
              const f1Val = mlStatus?.f1 ?? 0;
              const pc = mlStatus?.per_class || {};
              const classes = Object.values(pc);
              const avgPrec = classes.length > 0 ? classes.reduce((s, c) => s + (c.precision || 0), 0) / classes.length : 0;
              const avgRecall = classes.length > 0 ? classes.reduce((s, c) => s + (c.recall || 0), 0) / classes.length : 0;
              return (
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  <div className="flex justify-center">
                    <GaugeRing value={acc} max={100} size={72} color="#10b981" label="准确率" />
                  </div>
                  <div className="flex justify-center">
                    <GaugeRing value={f1Val} max={100} size={72} color="#06b6d4" label="F1" />
                  </div>
                  <div className="flex justify-center">
                    <GaugeRing value={avgPrec} max={100} size={72} color="#f59e0b" label="精确率" />
                  </div>
                  <div className="flex justify-center">
                    <GaugeRing value={avgRecall} max={100} size={72} color="#8b5cf6" label="召回率" />
                  </div>
                </div>
              );
            })()}
            <div className="grid grid-cols-3 gap-3 mt-4">
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-2.5 text-center">
                <div className="text-[9px] text-slate-500 font-black uppercase">样本数</div>
                <div className="text-sm font-black text-white">{safe(mlStatus?.samples ?? mlStatus?.sample_count)}</div>
              </div>
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-2.5 text-center">
                <div className="text-[9px] text-slate-500 font-black uppercase">训练时间</div>
                <div className="text-[10px] font-bold text-slate-300">{safe(mlStatus?.last_train ?? mlStatus?.trained_at)}</div>
              </div>
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-2.5 text-center">
                <div className="text-[9px] text-slate-500 font-black uppercase">版本</div>
                <div className="text-sm font-black text-cyan-400">{safe(mlStatus?.model_version ?? mlStatus?.version)}</div>
              </div>
            </div>
          </div>

          <div className="shield-glass rounded-2xl p-5 border border-slate-700/50">
            <h3 className="text-xs font-black text-purple-400 uppercase tracking-widest flex items-center gap-2 mb-4">
              <Cloud className="w-4 h-4" /> Modal 云端训练
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <button
                onClick={triggerModalTrain}
                disabled={modalTrainLoading}
                className="px-4 py-3 bg-gradient-to-r from-purple-500/30 to-cyan-500/30 border border-purple-500/40 rounded-xl text-sm font-black text-purple-300 hover:from-purple-500/40 hover:to-cyan-500/40 transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {modalTrainLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Cpu className="w-4 h-4" />}
                {modalTrainLoading ? '训练启动中...' : '启动云端训练'}
              </button>
              <button
                onClick={checkModalStatus}
                disabled={modalStatusLoading}
                className="px-4 py-3 bg-slate-500/20 border border-slate-500/30 rounded-xl text-sm font-bold text-slate-300 hover:bg-slate-500/30 transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {modalStatusLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Info className="w-4 h-4" />}
                {modalStatusLoading ? '查询中...' : '查询训练状态'}
              </button>
              <button
                onClick={runMegaBacktest}
                disabled={megaLoading}
                className="px-4 py-3 bg-gradient-to-r from-amber-500/30 to-orange-500/30 border border-amber-500/40 rounded-xl text-sm font-black text-amber-300 hover:from-amber-500/40 hover:to-orange-500/40 transition disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {megaLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
                {megaLoading ? '回测运行中...' : 'Mega 回测'}
              </button>
            </div>

            {modalStatusData && (
              <div className="mt-4 bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                <div className="text-[9px] text-slate-500 font-black uppercase mb-2">云端训练状态</div>
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${modalStatusData.status === 'running' ? 'bg-emerald-400 animate-pulse' : modalStatusData.status === 'error' ? 'bg-red-400' : 'bg-slate-400'}`} />
                    <span className="text-xs font-bold text-slate-200">
                      {modalStatusData.status === 'running' ? '运行中' : modalStatusData.status === 'error' ? '出错' : modalStatusData.status === 'idle' ? '空闲' : modalStatusData.status || '未知'}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full ${modalStatusData.configured ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                      {modalStatusData.configured ? '已配置' : '未配置'}
                    </span>
                  </div>
                  {modalStatusData.last_result && (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-2">
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">准确率</div>
                        <div className={`text-sm font-black ${modalStatusData.last_result.accuracy >= 70 ? 'text-emerald-400' : 'text-amber-400'}`}>{modalStatusData.last_result.accuracy}%</div>
                      </div>
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">F1分数</div>
                        <div className={`text-sm font-black ${modalStatusData.last_result.f1 >= 70 ? 'text-emerald-400' : 'text-amber-400'}`}>{modalStatusData.last_result.f1}%</div>
                      </div>
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">训练样本</div>
                        <div className="text-sm font-black text-cyan-400">{(modalStatusData.last_result.samples / 1000).toFixed(1)}K</div>
                      </div>
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">覆盖币种</div>
                        <div className="text-sm font-black text-violet-400">{modalStatusData.last_result.assets}个</div>
                      </div>
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">耗时</div>
                        <div className="text-sm font-black text-slate-300">{Math.round(modalStatusData.last_result.elapsed / 60)}分钟</div>
                      </div>
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">模型组合</div>
                        <div className="text-[10px] font-bold text-slate-300">{modalStatusData.last_result.ensemble}</div>
                      </div>
                    </div>
                  )}
                  <div className="flex flex-col gap-1 mt-1 text-[10px] text-slate-500">
                    {modalStatusData.last_training && <span>上次训练: {modalStatusData.last_training}</span>}
                    {modalStatusData.last_success && <span>上次成功: {modalStatusData.last_success}</span>}
                    {modalStatusData.error && <span className="text-red-400">错误: {modalStatusData.error}</span>}
                  </div>
                </div>
              </div>
            )}

            {megaResult && (
              <div className="mt-4 bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                <div className="text-[9px] text-slate-500 font-black uppercase mb-2">万次回测结果</div>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${megaResult.running ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'}`} />
                    <span className="text-xs font-bold text-slate-200">
                      {megaResult.running ? '回测进行中...' : '回测完成'}
                    </span>
                    {megaResult.progress_msg && megaResult.running && (
                      <span className="text-[10px] text-cyan-400 font-mono">{megaResult.progress_msg}</span>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                    <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                      <div className="text-[9px] text-slate-500">最佳Calmar比率</div>
                      <div className={`text-sm font-black ${megaResult.best_calmar > 1 ? 'text-emerald-400' : megaResult.best_calmar > 0 ? 'text-amber-400' : 'text-red-400'}`}>
                        {megaResult.best_calmar != null ? megaResult.best_calmar.toFixed(4) : '--'}
                      </div>
                      <div className="text-[8px] text-slate-600">目标 &gt;1.0</div>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                      <div className="text-[9px] text-slate-500">累计回测次数</div>
                      <div className="text-sm font-black text-cyan-400">{(megaResult.total_backtests || 0).toLocaleString()}</div>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                      <div className="text-[9px] text-slate-500">进化代数</div>
                      <div className="text-sm font-black text-violet-400">{megaResult.total_generations || 0}</div>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                      <div className="text-[9px] text-slate-500">参数改进次数</div>
                      <div className="text-sm font-black text-amber-400">{megaResult.improvement_count || 0}</div>
                    </div>
                    {megaResult.best_score != null && (
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">最佳得分</div>
                        <div className="text-sm font-black text-emerald-400">{megaResult.best_score.toFixed(4)}</div>
                      </div>
                    )}
                    {megaResult.win_rate != null && (
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">胜率</div>
                        <div className="text-sm font-black text-cyan-400">{(megaResult.win_rate * 100).toFixed(1)}%</div>
                      </div>
                    )}
                    {megaResult.sharpe != null && (
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">夏普比率</div>
                        <div className="text-sm font-black text-amber-400">{megaResult.sharpe.toFixed(2)}</div>
                      </div>
                    )}
                    {megaResult.iterations != null && (
                      <div className="bg-slate-800/50 rounded-lg p-2 text-center">
                        <div className="text-[9px] text-slate-500">本次迭代</div>
                        <div className="text-sm font-black text-white">{megaResult.iterations}</div>
                      </div>
                    )}
                  </div>

                  {megaResult.best_params && (
                    <div>
                      <div className="text-[9px] text-slate-500 font-bold mb-1.5">最优策略参数</div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {Object.entries(megaResult.best_params).map(([k, v]) => {
                          const labels = {
                            rsi_entry: 'RSI入场阈值', tp_atr: '止盈(ATR倍数)', sl_atr: '止损(ATR倍数)',
                            adx_threshold: 'ADX趋势阈值', ma_period: '均线周期', kelly_fraction: '凯利系数',
                            max_risk: '单笔最大风险', max_position: '最大仓位比例'
                          };
                          const label = labels[k] || k;
                          const display = typeof v === 'number'
                            ? (k === 'max_risk' || k === 'max_position' || k === 'kelly_fraction')
                              ? (v * 100).toFixed(1) + '%'
                              : Number.isInteger(v) ? v : v.toFixed(2)
                            : v;
                          return (
                            <div key={k} className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-2 text-center">
                              <div className="text-[8px] text-slate-500">{label}</div>
                              <div className="text-xs font-black text-white">{display}</div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {megaResult.last_improvement && (
                    <div className="text-[10px] text-slate-500">
                      最近一次改进: Calmar {megaResult.last_improvement.calmar?.toFixed(4)} | 第{megaResult.last_improvement.total_backtests?.toLocaleString()}次回测
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeSection === 'llm' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-black text-cyan-400 flex items-center gap-2">
              <Brain className="w-4 h-4" /> AI引擎控制中心
            </h3>
            <button
              onClick={async () => {
                setLlmLoading(true);
                try {
                  const [statusR, telR] = await Promise.all([
                    fetch('/api/llm/status'), fetch('/api/llm/telemetry')
                  ]);
                  const status = await statusR.json();
                  const tel = await telR.json();
                  setLlmData({ ...status, telemetry: tel });
                } catch (e) { console.error(e); }
                setLlmLoading(false);
              }}
              className="text-[9px] bg-cyan-500/20 text-cyan-400 px-2 py-1 rounded-lg border border-cyan-500/30 flex items-center gap-1"
            >
              <RefreshCw className={`w-3 h-3 ${llmLoading ? 'animate-spin' : ''}`} /> 刷新
            </button>
          </div>

          <div className="bg-gradient-to-r from-cyan-950/50 to-blue-950/50 border border-cyan-500/20 rounded-xl p-3">
            <div className="flex items-center gap-2 mb-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-cyan-300">双引擎架构</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-slate-950/60 rounded-lg p-2 border border-emerald-500/20">
                <div className="text-[9px] text-slate-500">OpenAI (GPT)</div>
                <div className="text-xs font-bold text-emerald-400">在线</div>
                <div className="text-[8px] text-slate-600 mt-1">gpt-4o-mini</div>
              </div>
              <div className="bg-slate-950/60 rounded-lg p-2 border border-violet-500/20">
                <div className="text-[9px] text-slate-500">Modal (自有AI)</div>
                <div className="text-xs font-bold text-violet-400">就绪</div>
                <div className="text-[8px] text-slate-600 mt-1">Qwen2.5-7B</div>
              </div>
            </div>
          </div>

          {llmData?.provider_config && (
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
              <div className="text-xs font-bold text-slate-300 mb-2">模块引擎路由</div>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {Object.entries(llmData.provider_config).filter(([k]) => k !== 'default').map(([mod, prov]) => (
                  <div key={mod} className="flex items-center justify-between text-[10px] py-0.5">
                    <span className="text-slate-400">{moduleNameMap[mod] || mod}</span>
                    <button
                      onClick={async () => {
                        const next = prov === 'openai' ? 'modal' : 'openai';
                        try {
                          const r = await fetch('/api/llm/set-provider', {
                            method: 'POST', headers: {'Content-Type':'application/json'},
                            body: JSON.stringify({ module: mod, provider: next })
                          });
                          const d = await r.json();
                          if (d.config) setLlmData(prev => ({...prev, provider_config: d.config}));
                        } catch (e) { console.error(e); }
                      }}
                      className={`px-2 py-0.5 rounded text-[9px] font-bold border ${
                        prov === 'openai'
                          ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                          : 'bg-violet-500/20 text-violet-400 border-violet-500/30'
                      }`}
                    >
                      {prov === 'openai' ? 'GPT' : 'Modal'}
                    </button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2 mt-2 pt-2 border-t border-slate-800">
                <button
                  onClick={async () => {
                    try {
                      const r = await fetch('/api/llm/set-provider', {
                        method: 'POST', headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({ module: 'all', provider: 'openai' })
                      });
                      const d = await r.json();
                      if (d.config) setLlmData(prev => ({...prev, provider_config: d.config}));
                    } catch (e) { console.error(e); }
                  }}
                  className="flex-1 text-[9px] bg-emerald-500/20 text-emerald-400 px-2 py-1 rounded border border-emerald-500/30"
                >
                  全部→GPT
                </button>
                <button
                  onClick={async () => {
                    try {
                      const r = await fetch('/api/llm/set-provider', {
                        method: 'POST', headers: {'Content-Type':'application/json'},
                        body: JSON.stringify({ module: 'all', provider: 'modal' })
                      });
                      const d = await r.json();
                      if (d.config) setLlmData(prev => ({...prev, provider_config: d.config}));
                    } catch (e) { console.error(e); }
                  }}
                  className="flex-1 text-[9px] bg-violet-500/20 text-violet-400 px-2 py-1 rounded border border-violet-500/30"
                >
                  全部→Modal
                </button>
              </div>
            </div>
          )}

          {llmData?.telemetry && (
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
              <div className="text-xs font-bold text-slate-300 mb-2">调用遥测</div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(llmData.telemetry.provider_summary || {}).map(([prov, s]) => (
                  <div key={prov} className="bg-slate-900/60 rounded-lg p-2 border border-slate-700/50">
                    <div className="text-[9px] font-bold text-slate-400 mb-1">{prov === 'openai' ? 'GPT' : 'Modal'}</div>
                    <div className="text-[10px] text-slate-300">调用: {s.calls}</div>
                    <div className="text-[10px] text-emerald-400">成功率: {s.success_rate}</div>
                    <div className="text-[10px] text-cyan-400">均延迟: {s.avg_latency}</div>
                    {s.fallbacks_from_modal > 0 && (
                      <div className="text-[10px] text-amber-400">回退: {s.fallbacks_from_modal}</div>
                    )}
                  </div>
                ))}
              </div>
              {llmData.telemetry.recent_calls?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-slate-800">
                  <div className="text-[9px] text-slate-500 mb-1">最近调用</div>
                  <div className="space-y-0.5 max-h-32 overflow-y-auto">
                    {llmData.telemetry.recent_calls.slice(-10).reverse().map((c, i) => (
                      <div key={i} className="flex items-center gap-2 text-[9px]">
                        <span className="text-slate-600 font-mono w-12">{c.time}</span>
                        <span className="text-slate-400 w-24 truncate">{moduleNameMap[c.module] || c.module}</span>
                        <span className={`w-10 ${c.provider === 'openai' ? 'text-emerald-500' : 'text-violet-500'}`}>{c.provider === 'openai' ? 'GPT' : 'Modal'}</span>
                        <span className={c.success ? 'text-emerald-500' : 'text-red-500'}>{c.success ? '✓' : '✗'}</span>
                        <span className="text-slate-600">{c.latency}s</span>
                        {c.fallback && <span className="text-amber-500 text-[8px]">回退</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
            <div className="text-xs font-bold text-slate-300 mb-2">测试连接</div>
            <div className="flex gap-2">
              <button
                disabled={llmTestLoading}
                onClick={async () => {
                  setLlmTestLoading(true); setLlmTestResult(null);
                  try {
                    const r = await fetch('/api/llm/test', {
                      method: 'POST', headers: {'Content-Type':'application/json'},
                      body: JSON.stringify({ provider: 'openai' })
                    });
                    setLlmTestResult(await r.json());
                  } catch (e) { setLlmTestResult({ error: e.message }); }
                  setLlmTestLoading(false);
                }}
                className="flex-1 text-[10px] bg-emerald-500/20 text-emerald-400 px-2 py-1.5 rounded-lg border border-emerald-500/30 disabled:opacity-50"
              >
                {llmTestLoading ? '测试中...' : '测试 GPT'}
              </button>
              <button
                disabled={llmTestLoading}
                onClick={async () => {
                  setLlmTestLoading(true); setLlmTestResult(null);
                  try {
                    const r = await fetch('/api/llm/test', {
                      method: 'POST', headers: {'Content-Type':'application/json'},
                      body: JSON.stringify({ provider: 'modal' })
                    });
                    setLlmTestResult(await r.json());
                  } catch (e) { setLlmTestResult({ error: e.message }); }
                  setLlmTestLoading(false);
                }}
                className="flex-1 text-[10px] bg-violet-500/20 text-violet-400 px-2 py-1.5 rounded-lg border border-violet-500/30 disabled:opacity-50"
              >
                {llmTestLoading ? '测试中...' : '测试 Modal'}
              </button>
            </div>
            {llmTestResult && (
              <div className={`mt-2 p-2 rounded text-[10px] ${llmTestResult.error ? 'bg-red-500/10 text-red-400 border border-red-500/20' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'}`}>
                {llmTestResult.error ? `❌ ${llmTestResult.error}` : `✅ ${llmTestResult.provider === 'openai' ? 'GPT' : 'Modal'} 连接正常 (${llmTestResult.latency || '--'}秒)`}
              </div>
            )}
          </div>

          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
            <div className="text-xs font-bold text-slate-300 mb-2">Modal LLM 操作</div>
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  try {
                    const r = await fetch('/api/llm/modal-warmup', { method: 'POST' });
                    const d = await r.json();
                    alert(d.status === 'submitted' ? '预热任务已提交!' : `错误: ${d.error}`);
                  } catch (e) { alert(`错误: ${e.message}`); }
                }}
                className="flex-1 text-[10px] bg-violet-500/20 text-violet-400 px-2 py-1.5 rounded-lg border border-violet-500/30"
              >
                <Zap className="w-3 h-3 inline mr-1" />预热模型
              </button>
              <button
                onClick={async () => {
                  try {
                    const r = await fetch('/api/llm/modal-health');
                    const d = await r.json();
                    alert(`状态: ${d.status}\n模型: ${d.model_id}\n已缓存: ${d.model_cached ? '是' : '否'}\nGPU: ${d.gpu}`);
                  } catch (e) { alert(`错误: ${e.message}`); }
                }}
                className="flex-1 text-[10px] bg-blue-500/20 text-blue-400 px-2 py-1.5 rounded-lg border border-blue-500/30"
              >
                <BarChart3 className="w-3 h-3 inline mr-1" />健康检查
              </button>
            </div>
          </div>
        </div>
      )}

      {activeSection === 'notifications' && (
        <div className="shield-glass rounded-2xl p-5 border border-slate-700/50">
          <h3 className="text-xs font-black text-amber-400 uppercase tracking-widest flex items-center gap-2 mb-4">
            <Bell className="w-4 h-4" /> 系统通知
            {notifications?.length > 0 && (
              <span className="text-[9px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded-full font-bold">
                {notifications.length} 条
              </span>
            )}
          </h3>

          {(!notifications || notifications.length === 0) ? (
            <div className="text-center py-8">
              <Bell className="w-10 h-10 text-slate-700 mx-auto mb-2" />
              <div className="text-sm text-slate-500 font-bold">暂无通知</div>
              <div className="text-[10px] text-slate-600 mt-1">系统通知将在此处显示</div>
            </div>
          ) : (
            <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
              {notifications.map((n, i) => {
                const typeColors = {
                  system: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
                  info: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
                  warning: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
                  error: 'bg-red-500/20 text-red-400 border-red-500/30',
                };
                const typeIcons = {
                  system: Cpu,
                  info: Info,
                  warning: AlertTriangle,
                  error: AlertCircle,
                };
                const typeLabels = { system: '系统', info: '信息', warning: '警告', error: '错误' };
                const Icon = typeIcons[n.type] || Info;
                const iconColor = n.type === 'error' ? 'text-red-400' : n.type === 'warning' ? 'text-amber-400' : n.type === 'system' ? 'text-cyan-400' : 'text-blue-400';
                return (
                  <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                    <div className="flex items-start gap-2">
                      <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${iconColor}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded border ${typeColors[n.type] || typeColors.info}`}>
                            {typeLabels[n.type] || '信息'}
                          </span>
                          <span className="text-[9px] text-slate-600">{safe(n.time)}</span>
                          {n.read && <span className="text-[8px] text-slate-700">已读</span>}
                        </div>
                        <div className="text-[11px] text-slate-300 font-medium">{safe(n.msg || n.message)}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}