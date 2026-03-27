import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, Activity, Zap, Shield, TrendingUp, Settings, Play } from 'lucide-react';

const StatCard = ({ label, value, color, icon: Icon, sub }) => (
  <div className="bg-[#020617]/60 border border-slate-700/40 rounded-xl p-4 text-center">
    {Icon && <Icon className={`w-4 h-4 mx-auto mb-1.5 ${color}`} />}
    <div className="text-[8px] text-slate-500 font-black uppercase tracking-wide mb-1">{label}</div>
    <div className={`text-xl font-black tabular-nums ${color}`}>{value}</div>
    {sub && <div className="text-[8px] text-slate-600 mt-0.5">{sub}</div>}
  </div>
);

const ParamRow = ({ name, value, desc }) => (
  <div className="flex items-center justify-between py-2 border-b border-slate-800/50 last:border-0">
    <div className="flex-1 min-w-0">
      <div className="text-[10px] font-bold text-slate-300">{name}</div>
      {desc && <div className="text-[8px] text-slate-600 truncate">{desc}</div>}
    </div>
    <span className="text-[11px] font-black text-cyan-400 tabular-nums ml-3">
      {typeof value === 'number' ? (value < 1 ? (value * 100).toFixed(1) + '%' : value.toFixed(4)) : String(value ?? '--')}
    </span>
  </div>
);

export default function MonteCarloViz() {
  const [status, setStatus] = useState(null);
  const [explain, setExplain] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const API = import.meta.env.VITE_API_URL || '';

  const fetchData = async () => {
    try {
      const [sRes, eRes] = await Promise.all([
        fetch(`${API}/api/monte-carlo`),
        fetch(`${API}/api/monte-carlo/explain`),
      ]);
      const sData = await sRes.json();
      const eData = await eRes.json();
      setStatus(sData);
      setExplain(eData);
    } catch (e) {
      console.error('MonteCarloViz fetch error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);
  useEffect(() => {
    const t = setInterval(fetchData, 30000);
    return () => clearInterval(t);
  }, []);

  const triggerRun = async () => {
    setRunning(true);
    try {
      await fetch(`${API}/api/monte-carlo/run`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      setTimeout(fetchData, 2000);
    } catch (e) { console.error(e); }
    finally { setRunning(false); }
  };

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-6 border border-slate-800 flex items-center justify-center gap-2 text-slate-500 text-[10px]">
        <Loader2 className="w-4 h-4 animate-spin" /> 加载蒙特卡洛数据...
      </div>
    );
  }

  if (!status) {
    return (
      <div className="shield-glass rounded-xl p-6 border border-slate-800 text-center text-[10px] text-slate-600">
        无法加载蒙特卡洛数据
      </div>
    );
  }

  const isRunning = status.running;
  const hasSims = status.total_simulations > 0;
  const params = status.best_params || {};
  const paramEntries = explain ? Object.entries(explain) : Object.entries(params).map(([k, v]) => [k, { value: v, desc: '' }]);

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-black text-cyan-400 uppercase tracking-widest flex items-center gap-2">
          <Activity className="w-4 h-4" /> 蒙特卡洛风险模拟
        </h3>
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="text-[8px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 rounded-full px-3 py-1 flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              {status.progress_msg || '模拟中...'}
            </span>
          )}
          <button
            onClick={triggerRun}
            disabled={running || isRunning}
            className="flex items-center gap-1 text-[8px] font-bold px-3 py-1.5 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/25 disabled:opacity-50 transition-all"
          >
            {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            {isRunning ? '运行中' : '启动模拟'}
          </button>
        </div>
      </div>

      <div className={`shield-glass rounded-xl p-3 border ${isRunning ? 'border-amber-500/30' : hasSims ? 'border-emerald-500/30' : 'border-slate-700/40'}`}>
        <div className="flex items-center gap-2">
          <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-amber-400 animate-pulse' : hasSims ? 'bg-emerald-400' : 'bg-slate-600'}`} />
          <span className={`text-[10px] font-black uppercase tracking-wide ${isRunning ? 'text-amber-400' : hasSims ? 'text-emerald-400' : 'text-slate-500'}`}>
            {isRunning ? '优化进行中' : hasSims ? '优化已完成' : '等待首次运行'}
          </span>
          {isRunning && status.progress != null && (
            <div className="flex-1 ml-3">
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-amber-500 to-cyan-400 rounded-full transition-all duration-300" style={{ width: `${Math.min(100, (status.progress || 0) * 100)}%` }} />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="总模拟次数"
          value={hasSims ? status.total_simulations.toLocaleString() : '--'}
          color="text-cyan-400"
          icon={Zap}
          sub={status.total_generations > 0 ? `${status.total_generations} 代` : null}
        />
        <StatCard
          label="最优夏普"
          value={hasSims ? status.best_sharpe.toFixed(3) : '--'}
          color={status.best_sharpe >= 1.5 ? 'text-emerald-400' : status.best_sharpe > 0 ? 'text-amber-400' : 'text-slate-400'}
          icon={TrendingUp}
          sub="目标 ≥1.5"
        />
        <StatCard
          label="最优卡玛"
          value={hasSims ? status.best_calmar.toFixed(3) : '--'}
          color={status.best_calmar >= 3.0 ? 'text-emerald-400' : status.best_calmar > 0 ? 'text-amber-400' : 'text-slate-400'}
          icon={Shield}
          sub="目标 ≥3.0"
        />
        <StatCard
          label="改进次数"
          value={status.improvement_count ?? '--'}
          color="text-violet-400"
          icon={Settings}
          sub={status.trade_pool_size > 0 ? `交易池 ${status.trade_pool_size}` : null}
        />
      </div>

      {hasSims && paramEntries.length > 0 && (
        <div className="shield-glass rounded-xl p-5 border border-slate-800">
          <h4 className="text-[10px] font-black text-white uppercase tracking-widest mb-3 flex items-center gap-2">
            <Settings className="w-3.5 h-3.5 text-cyan-400" /> 最优参数详情
          </h4>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-x-6">
            {paramEntries.map(([key, data]) => (
              <ParamRow
                key={key}
                name={key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                value={typeof data === 'object' ? data.value : data}
                desc={typeof data === 'object' ? data.desc : null}
              />
            ))}
          </div>
        </div>
      )}

      {status.last_improvement && (
        <div className="shield-glass rounded-xl p-4 border border-emerald-500/20">
          <h4 className="text-[10px] font-black text-emerald-400 uppercase tracking-widest mb-2">最近一次改进</h4>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-[10px]">
            {Object.entries(status.last_improvement).map(([k, v]) => (
              <div key={k}>
                <div className="text-[8px] text-slate-500 font-bold uppercase">{k.replace(/_/g, ' ')}</div>
                <div className="text-slate-300 font-black tabular-nums">
                  {typeof v === 'number' ? v.toFixed(4) : String(v ?? '--')}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
