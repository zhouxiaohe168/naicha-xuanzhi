import { useState, useEffect } from 'react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend
} from 'recharts';
import { PieChart as PieChartIcon, BarChart3, Loader2, RefreshCw, Table2 } from 'lucide-react';

const COLORS = ['#10b981', '#06b6d4', '#8b5cf6', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#f97316'];

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

export default function AttributionChart() {
  const [attribution, setAttribution] = useState(null);
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const API = import.meta.env.VITE_API_URL || '';
      const [attrRes, chartRes] = await Promise.all([
        fetch(`${API}/api/attribution`),
        fetch(`${API}/api/attribution/chart-data`)
      ]);
      const attrData = await attrRes.json();
      const cData = await chartRes.json();
      if (!attrData.error) setAttribution(attrData);
      if (!cData.error) setChartData(cData);
    } catch (e) {
      console.error(e);
      setError('数据加载失败');
    }
    setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  if (loading) {
    return (
      <div className="shield-glass rounded-2xl p-6 border border-slate-800">
        <div className="flex items-center justify-center gap-2 text-slate-500 text-[10px] py-12">
          <Loader2 className="w-4 h-4 animate-spin" /> 加载收益归因数据...
        </div>
      </div>
    );
  }

  if (error || !attribution) {
    return (
      <div className="shield-glass rounded-2xl p-6 border border-slate-800">
        <div className="text-center py-12">
          <div className="text-[10px] text-slate-600 mb-3">{error || '暂无归因数据'}</div>
          <button
            onClick={fetchData}
            className="text-[9px] font-bold px-3 py-1.5 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/25 transition-all"
          >
            <RefreshCw className="w-3 h-3 inline mr-1" />重新加载
          </button>
        </div>
      </div>
    );
  }

  const byStrategy = attribution.by_strategy || {};
  const byAsset = attribution.by_asset?.assets || attribution.by_asset || {};

  const pieData = Object.entries(byStrategy).map(([name, data]) => ({
    name,
    value: Math.abs(data.total_pnl || 0),
    pnl: data.total_pnl || 0,
    trades: data.trade_count || 0,
  })).filter(d => d.value > 0);

  const equityCurve = chartData?.equity_curve || [];
  const barData = equityCurve.map(item => ({
    time: item.time,
    pnl: item.pnl || 0,
    equity: item.equity || 0,
  }));

  const strategyEntries = Object.entries(byStrategy).sort((a, b) => (b[1].total_pnl || 0) - (a[1].total_pnl || 0));

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-[#0f172a] border border-slate-700 rounded-lg p-2 text-[9px]">
        <div className="font-bold text-white mb-1">{d.name}</div>
        <div className={d.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>盈亏: ${d.pnl.toFixed(2)}</div>
        <div className="text-slate-400">交易: {d.trades}笔</div>
      </div>
    );
  };

  const BarTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-[#0f172a] border border-slate-700 rounded-lg p-2 text-[9px]">
        <div className="font-bold text-slate-300 mb-1">{label}</div>
        {payload.map((p, i) => (
          <div key={i} className={p.value >= 0 ? 'text-emerald-400' : 'text-red-400'}>
            盈亏: ${Number(p.value).toFixed(2)}
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-5 animate-fadeIn">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-black text-amber-400 uppercase tracking-widest flex items-center gap-2">
          <PieChartIcon className="w-4 h-4" /> 收益归因分析
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-slate-500">总交易: <span className="text-slate-300 font-bold">{attribution.total_trades || 0}</span></span>
          <button
            onClick={fetchData}
            className="text-[8px] font-bold px-2 py-1 rounded bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/25 transition-all"
          >
            <RefreshCw className="w-2.5 h-2.5 inline mr-1" />刷新
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="shield-glass rounded-2xl p-5 border border-slate-800">
          <h4 className="text-[10px] font-black text-violet-400 uppercase tracking-wide mb-4 flex items-center gap-2">
            <PieChartIcon className="w-3.5 h-3.5" /> 策略PnL分布
          </h4>
          {pieData.length > 0 ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="none" />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    formatter={(value, entry) => {
                      const item = pieData.find(d => d.name === value);
                      return (
                        <span className="text-[8px] text-slate-400">
                          {value} <span className={item?.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>${item?.pnl?.toFixed(2)}</span>
                        </span>
                      );
                    }}
                    wrapperStyle={{ fontSize: 9 }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-[10px] text-slate-600">暂无策略分布数据</div>
          )}
        </div>

        <div className="shield-glass rounded-2xl p-5 border border-slate-800">
          <h4 className="text-[10px] font-black text-cyan-400 uppercase tracking-wide mb-4 flex items-center gap-2">
            <BarChart3 className="w-3.5 h-3.5" /> 每日PnL走势
          </h4>
          {barData.length > 0 ? (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <XAxis dataKey="time" tick={{ fontSize: 8, fill: '#64748b' }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 8, fill: '#64748b' }} axisLine={false} tickLine={false} tickFormatter={v => `$${v.toFixed(0)}`} />
                  <Tooltip content={<BarTooltip />} />
                  <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
                    {barData.map((entry, i) => (
                      <Cell key={i} fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-56 flex items-center justify-center text-[10px] text-slate-600">暂无每日PnL数据</div>
          )}
        </div>
      </div>

      <div className="shield-glass rounded-2xl p-5 border border-slate-800">
        <h4 className="text-[10px] font-black text-emerald-400 uppercase tracking-wide mb-4 flex items-center gap-2">
          <Table2 className="w-3.5 h-3.5" /> 策略归因明细
        </h4>
        {strategyEntries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-[10px] min-w-[600px]">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="py-2 px-3 text-left text-slate-500 font-bold">策略</th>
                  <th className="py-2 px-3 text-right text-slate-500 font-bold">总PnL</th>
                  <th className="py-2 px-3 text-right text-slate-500 font-bold">交易数</th>
                  <th className="py-2 px-3 text-right text-slate-500 font-bold">胜率</th>
                  <th className="py-2 px-3 text-right text-slate-500 font-bold">均PnL</th>
                  <th className="py-2 px-3 text-right text-slate-500 font-bold">夏普</th>
                </tr>
              </thead>
              <tbody>
                {strategyEntries.map(([name, data], i) => (
                  <tr key={name} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <td className="py-2 px-3 font-bold text-slate-300 flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                      {name}
                    </td>
                    <td className={`py-2 px-3 text-right font-bold tabular-nums ${(data.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      ${(data.total_pnl || 0).toFixed(2)}
                    </td>
                    <td className="py-2 px-3 text-right text-slate-300 tabular-nums">{data.trade_count || 0}</td>
                    <td className={`py-2 px-3 text-right font-bold tabular-nums ${(data.win_rate || 0) >= 50 ? 'text-emerald-400' : (data.win_rate || 0) >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                      {data.win_rate != null ? `${Number(data.win_rate).toFixed(1)}%` : '--'}
                    </td>
                    <td className={`py-2 px-3 text-right tabular-nums ${(data.avg_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      ${(data.avg_pnl || 0).toFixed(2)}
                    </td>
                    <td className={`py-2 px-3 text-right font-bold tabular-nums ${(data.sharpe || 0) >= 1 ? 'text-emerald-400' : (data.sharpe || 0) >= 0 ? 'text-amber-400' : 'text-red-400'}`}>
                      {data.sharpe != null ? Number(data.sharpe).toFixed(2) : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-[10px] text-slate-600">暂无策略归因数据</div>
        )}

        {Object.keys(byAsset).length > 0 && (
          <div className="mt-5 pt-5 border-t border-slate-800">
            <h4 className="text-[10px] font-black text-amber-400 uppercase tracking-wide mb-3">资产归因</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
              {Object.entries(byAsset)
                .sort((a, b) => (b[1].total_pnl || 0) - (a[1].total_pnl || 0))
                .slice(0, 12)
                .map(([asset, data]) => (
                  <div key={asset} className="bg-slate-900/50 rounded-lg p-2.5 border border-slate-800/50">
                    <div className="text-[9px] font-bold text-cyan-400 mb-1">{asset}</div>
                    <div className={`text-sm font-black tabular-nums ${(data.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      ${(data.total_pnl || 0).toFixed(2)}
                    </div>
                    <div className="text-[8px] text-slate-500 mt-0.5">
                      {data.trade_count || 0}笔 | 胜率 {data.win_rate != null ? `${Number(data.win_rate).toFixed(0)}%` : '--'}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}