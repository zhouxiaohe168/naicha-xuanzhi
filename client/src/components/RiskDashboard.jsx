import { useState, useEffect } from 'react';
import { Shield, AlertTriangle, Loader2, RefreshCw, Lock, Unlock, DollarSign, Gauge, Activity } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const COLORS = ['#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#f97316', '#3b82f6', '#14b8a6'];

export default function RiskDashboard() {
  const [riskMatrix, setRiskMatrix] = useState(null);
  const [capitalSizer, setCapitalSizer] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [rmRes, csRes] = await Promise.all([
        fetch('/api/risk-matrix').then(r => r.json()).catch(() => null),
        fetch('/api/capital-sizer').then(r => r.json()).catch(() => null),
      ]);
      setRiskMatrix(rmRes);
      setCapitalSizer(csRes);
    } catch (e) {
      setError('加载风控数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-6 border border-slate-800 text-center">
        <Loader2 className="w-5 h-5 animate-spin text-slate-500 mx-auto mb-2" />
        <div className="text-[10px] text-slate-500">加载风控数据...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="shield-glass rounded-xl p-6 border border-red-500/20 text-center">
        <AlertTriangle className="w-5 h-5 text-red-400 mx-auto mb-2" />
        <div className="text-xs text-red-400">{error}</div>
        <button onClick={fetchData} className="mt-2 text-[10px] text-cyan-400 hover:underline">重试</button>
      </div>
    );
  }

  const config = riskMatrix?.config || {};
  const circuitBreakerActive = riskMatrix?.circuit_breaker_active || false;
  const dailyStopActive = riskMatrix?.daily_stop_active || false;
  const recentWarnings = riskMatrix?.recent_warnings || [];
  const recentBlocks = riskMatrix?.recent_blocks || [];

  const totalSized = capitalSizer?.total_sized || 0;
  const avgPosPct = capitalSizer?.avg_position_pct || 0;
  const kellyAvg = capitalSizer?.kelly_fraction_avg || 0;
  const globalMults = capitalSizer?.global_multipliers || {};
  const recentSizings = capitalSizer?.recent_sizings || [];

  const defenseLines = [
    {
      line: '第一道防线',
      label: '仓位限制',
      status: config.max_position_pct ? 'active' : 'unknown',
      detail: config.max_position_pct ? `单仓上限 ${(config.max_position_pct * 100).toFixed(1)}%` : '未配置',
      color: 'emerald',
    },
    {
      line: '第二道防线',
      label: '熔断机制',
      status: circuitBreakerActive ? 'triggered' : 'standby',
      detail: circuitBreakerActive ? '熔断已触发' : `阈值 ${((config.circuit_breaker_threshold || 0) * 100).toFixed(1)}%`,
      color: circuitBreakerActive ? 'red' : 'amber',
    },
    {
      line: '第三道防线',
      label: '每日止损',
      status: dailyStopActive ? 'triggered' : 'standby',
      detail: dailyStopActive ? '日内已暂停' : `限额 ${((config.daily_loss_limit || 0) * 100).toFixed(1)}%`,
      color: dailyStopActive ? 'red' : 'cyan',
    },
  ];

  const multEntries = Object.entries(globalMults).filter(([, v]) => typeof v === 'number');
  const multNames = {
    regime_mult: '市场环境',
    performance_mult: '绩效表现',
    volatility_mult: '波动率',
    drawdown_mult: '回撤',
    confidence_mult: '信心度',
    kelly_mult: 'Kelly系数',
    correlation_mult: '相关性',
  };

  const donutData = multEntries.map(([k, v]) => ({
    name: multNames[k] || k.replace(/_mult$/, '').replace(/_/g, ' '),
    value: Math.abs(v),
    raw: v,
  })).filter(d => d.value > 0);

  const statusColor = (s) => {
    if (s === 'active' || s === 'standby') return 'text-emerald-400';
    if (s === 'triggered') return 'text-red-400';
    return 'text-slate-400';
  };

  const StatusIcon = ({ status }) => {
    if (status === 'triggered') return <Lock className="w-4 h-4 text-red-400" />;
    return <Unlock className="w-4 h-4 text-emerald-400" />;
  };

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-400" />
          <span className="text-[11px] font-black text-white uppercase tracking-wider">风控仪表盘</span>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-1 text-[8px] font-bold px-2 py-1 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/25 transition-all"
        >
          <RefreshCw className="w-2.5 h-2.5" />
          刷新
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {defenseLines.map((d, i) => (
          <div
            key={i}
            className={`shield-glass rounded-xl p-4 border ${
              d.color === 'red' ? 'border-red-500/20' :
              d.color === 'amber' ? 'border-amber-500/20' :
              d.color === 'cyan' ? 'border-cyan-500/20' :
              'border-emerald-500/20'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className={`text-[9px] font-black uppercase ${
                d.color === 'red' ? 'text-red-400' :
                d.color === 'amber' ? 'text-amber-400' :
                d.color === 'cyan' ? 'text-cyan-400' :
                'text-emerald-400'
              }`}>{d.line}</span>
              <StatusIcon status={d.status} />
            </div>
            <div className="text-sm font-black text-white mb-1">{d.label}</div>
            <div className={`text-[10px] ${statusColor(d.status)}`}>{d.detail}</div>
            <div className={`mt-2 text-[8px] px-2 py-0.5 rounded-full inline-block ${
              d.status === 'triggered' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
              d.status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
              'bg-slate-700/20 text-slate-400 border border-slate-700'
            }`}>
              {d.status === 'triggered' ? '已触发' : d.status === 'active' ? '运行中' : '待命'}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="shield-glass rounded-xl p-4 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className="w-4 h-4 text-amber-400" />
            <span className="text-[10px] font-black text-amber-400">资金分配乘数</span>
          </div>
          {donutData.length > 0 ? (
            <div className="flex items-center gap-2">
              <div className="w-32 h-32 flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={donutData}
                      cx="50%"
                      cy="50%"
                      innerRadius={30}
                      outerRadius={55}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {donutData.map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', fontSize: '10px' }}
                      formatter={(val, name) => [`${val.toFixed(3)}`, name]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 space-y-1">
                {donutData.map((d, i) => (
                  <div key={i} className="flex items-center gap-2 text-[9px]">
                    <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                    <span className="text-slate-400 flex-1 truncate">{d.name}</span>
                    <span className="text-white font-bold">{d.raw.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-6 text-[10px] text-slate-600">暂无乘数数据</div>
          )}
        </div>

        <div className="shield-glass rounded-xl p-4 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <Gauge className="w-4 h-4 text-violet-400" />
            <span className="text-[10px] font-black text-violet-400">资金管理概览</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-950/40 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-slate-500">总定标次数</div>
              <div className="text-lg font-black text-white">{totalSized}</div>
            </div>
            <div className="bg-slate-950/40 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-slate-500">平均仓位</div>
              <div className="text-lg font-black text-cyan-400">{(avgPosPct * 100).toFixed(2)}%</div>
            </div>
            <div className="bg-slate-950/40 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-slate-500">Kelly均值</div>
              <div className="text-lg font-black text-amber-400">{kellyAvg.toFixed(4)}</div>
            </div>
            <div className="bg-slate-950/40 rounded-lg p-2.5 text-center">
              <div className="text-[8px] text-slate-500">近期定标</div>
              <div className="text-lg font-black text-emerald-400">{recentSizings.length}</div>
            </div>
          </div>
        </div>
      </div>

      {Object.keys(config).length > 0 && (
        <div className="shield-glass rounded-xl p-4 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span className="text-[10px] font-black text-cyan-400">风控参数配置</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.entries(config).map(([k, v]) => {
              const nameMap = {
                max_position_pct: '最大仓位',
                circuit_breaker_threshold: '熔断阈值',
                daily_loss_limit: '日损限额',
                max_drawdown_pct: '最大回撤',
                max_open_positions: '最大持仓数',
                max_correlated_positions: '最大相关仓位',
                risk_per_trade: '单笔风险',
                max_leverage: '最大杠杆',
              };
              const display = typeof v === 'number'
                ? (v < 1 && v > 0 ? `${(v * 100).toFixed(1)}%` : v.toFixed(2))
                : safe(v);
              return (
                <div key={k} className="bg-slate-950/40 rounded-lg p-2 flex items-center justify-between">
                  <span className="text-[8px] text-slate-500 truncate">{nameMap[k] || k}</span>
                  <span className="text-[10px] font-bold text-white ml-2">{display}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {(recentWarnings.length > 0 || recentBlocks.length > 0) && (
        <div className="shield-glass rounded-xl p-4 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span className="text-[10px] font-black text-amber-400">近期风控事件</span>
          </div>
          {recentBlocks.length > 0 && (
            <div className="mb-3">
              <div className="text-[9px] text-red-400 font-bold mb-1.5">拦截记录 ({recentBlocks.length})</div>
              <div className="space-y-1 max-h-[150px] overflow-y-auto">
                {recentBlocks.slice(0, 10).map((b, i) => (
                  <div key={i} className="text-[10px] text-slate-300 bg-red-500/5 border border-red-500/10 rounded-lg px-3 py-1.5">
                    {typeof b === 'object' ? (b.reason || b.message || JSON.stringify(b)) : String(b)}
                  </div>
                ))}
              </div>
            </div>
          )}
          {recentWarnings.length > 0 && (
            <div>
              <div className="text-[9px] text-amber-400 font-bold mb-1.5">警告记录 ({recentWarnings.length})</div>
              <div className="space-y-1 max-h-[150px] overflow-y-auto">
                {recentWarnings.slice(0, 10).map((w, i) => (
                  <div key={i} className="text-[10px] text-slate-300 bg-amber-500/5 border border-amber-500/10 rounded-lg px-3 py-1.5">
                    {typeof w === 'object' ? (w.reason || w.message || JSON.stringify(w)) : String(w)}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {recentSizings.length > 0 && (
        <div className="shield-glass rounded-xl p-4 border border-slate-800">
          <div className="flex items-center gap-2 mb-3">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span className="text-[10px] font-black text-emerald-400">近期仓位定标</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-[9px]">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="text-left py-1.5 px-2">资产</th>
                  <th className="text-right py-1.5 px-2">仓位%</th>
                  <th className="text-right py-1.5 px-2">Kelly</th>
                  <th className="text-right py-1.5 px-2">乘数</th>
                </tr>
              </thead>
              <tbody>
                {recentSizings.slice(0, 10).map((s, i) => (
                  <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20">
                    <td className="py-1.5 px-2 text-white font-bold">{s.asset || s.symbol || '--'}</td>
                    <td className="py-1.5 px-2 text-right text-cyan-400">{((s.position_pct || 0) * 100).toFixed(2)}%</td>
                    <td className="py-1.5 px-2 text-right text-amber-400">{(s.kelly_fraction || 0).toFixed(4)}</td>
                    <td className="py-1.5 px-2 text-right text-slate-300">{(s.final_multiplier || s.multiplier || 1).toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}