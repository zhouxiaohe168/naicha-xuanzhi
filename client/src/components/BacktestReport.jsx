import { useState, useEffect } from 'react';
import { BarChart3, Loader2, RefreshCw, TrendingUp, TrendingDown, AlertTriangle } from 'lucide-react';

const AccuracyBar = ({ value, label, sampleSize, significant }) => {
  const pct = (value * 100).toFixed(1);
  const color = value >= 0.55 ? 'bg-emerald-500' : value >= 0.40 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = value >= 0.55 ? 'text-emerald-400' : value >= 0.40 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="flex items-center gap-2 py-1">
      <span className="text-[8px] text-slate-400 w-24 truncate" title={label}>{label}</span>
      <div className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${Math.min(100, value * 100)}%` }} />
      </div>
      <span className={`text-[9px] font-bold ${textColor} w-10 text-right`}>{pct}%</span>
      <span className={`text-[7px] ${significant ? 'text-slate-400' : 'text-slate-600'} w-8 text-right`}>n={sampleSize}</span>
    </div>
  );
};

export default function BacktestReport() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);

  const fetchReports = () => {
    fetch('/api/backtest-reports?limit=5')
      .then(r => r.json())
      .then(d => setReports(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchReports(); }, []);

  const runBacktest = () => {
    setRunning(true);
    fetch('/api/run-backtest?days=30', { method: 'POST' })
      .then(r => r.json())
      .then(() => { fetchReports(); })
      .catch(() => {})
      .finally(() => setRunning(false));
  };

  const latest = reports[0];
  const sq = latest?.signal_accuracy || {};
  const sp = latest?.strategy_performance || {};

  const sqEntries = Object.entries(sq)
    .filter(([k]) => !k.startsWith('gate_') && k !== 'no_data')
    .sort((a, b) => (b[1]?.accuracy || 0) - (a[1]?.accuracy || 0));

  const gateEntries = Object.entries(sq)
    .filter(([k]) => k.startsWith('gate_'))
    .sort((a, b) => (a[1]?.accuracy || 0) - (b[1]?.accuracy || 0));

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-4 border border-slate-800">
        <div className="flex items-center gap-2 text-slate-500 text-[10px]">
          <Loader2 className="w-3 h-3 animate-spin" /> 加载回测报告...
        </div>
      </div>
    );
  }

  return (
    <div className="shield-glass rounded-xl p-4 border border-slate-800">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-4 h-4 text-cyan-400" />
        <span className="text-[11px] font-black text-white uppercase tracking-wider">回测报告</span>
        <button
          onClick={runBacktest}
          disabled={running}
          className="ml-auto flex items-center gap-1 text-[8px] font-bold px-2 py-1 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/25 disabled:opacity-50 transition-all"
        >
          <RefreshCw className={`w-2.5 h-2.5 ${running ? 'animate-spin' : ''}`} />
          {running ? '运行中...' : '立即回测'}
        </button>
      </div>

      {!latest ? (
        <div className="text-[10px] text-slate-600 text-center py-6">
          暂无回测报告 — 点击"立即回测"或等待周日自动执行
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-[8px] text-slate-500 mb-2">
            {latest.created_at ? new Date(latest.created_at).toLocaleString('zh-CN') : ''} | {latest.summary}
          </div>

          <div>
            <div className="text-[9px] font-bold text-white mb-1 flex items-center gap-1">
              <TrendingUp className="w-3 h-3 text-emerald-400" /> 信号准确率分析
            </div>
            <div className="space-y-0.5">
              {sqEntries.map(([key, data]) => (
                <AccuracyBar
                  key={key}
                  label={key}
                  value={data.accuracy || 0}
                  sampleSize={data.sample_size || 0}
                  significant={data.significant}
                />
              ))}
            </div>
          </div>

          {gateEntries.length > 0 && (
            <div>
              <div className="text-[9px] font-bold text-white mb-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-amber-400" /> 过滤器准确率
              </div>
              <div className="space-y-0.5">
                {gateEntries.map(([key, data]) => (
                  <AccuracyBar
                    key={key}
                    label={key.replace('gate_', '')}
                    value={data.accuracy || 0}
                    sampleSize={data.sample_size || 0}
                    significant={data.significant}
                  />
                ))}
              </div>
            </div>
          )}

          {Object.keys(sp).length > 0 && (
            <div>
              <div className="text-[9px] font-bold text-white mb-1 flex items-center gap-1">
                <TrendingDown className="w-3 h-3 text-purple-400" /> 策略表现
              </div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(sp).map(([strat, data]) => (
                  <div key={strat} className="bg-slate-900/50 rounded-lg p-2 border border-slate-800/50">
                    <div className="text-[8px] font-bold text-cyan-400 mb-1">{strat}</div>
                    <div className="grid grid-cols-2 gap-x-2 text-[7px]">
                      <span className="text-slate-500">胜率</span>
                      <span className={`font-bold ${(data.win_rate || 0) >= 0.45 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {((data.win_rate || 0) * 100).toFixed(0)}%
                      </span>
                      <span className="text-slate-500">笔数</span>
                      <span className="text-slate-300 font-bold">{data.trade_count || 0}</span>
                      <span className="text-slate-500">总PnL</span>
                      <span className={`font-bold ${(data.total_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {(data.total_pnl_pct || 0).toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {latest.pending_proposals > 0 && (
            <div className="bg-amber-500/10 rounded-lg p-2 border border-amber-500/20">
              <span className="text-[8px] font-bold text-amber-400">
                {latest.pending_proposals} 项优化建议待审核 → evolution_proposals表
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
