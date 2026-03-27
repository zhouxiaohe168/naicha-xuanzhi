import { useState, useEffect } from 'react';
import {
  Filter, Target, BarChart3, TrendingUp, Loader2, AlertTriangle, RefreshCw
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid
} from 'recharts';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

export default function SignalQualityPanel() {
  const [rejectionStats, setRejectionStats] = useState(null);
  const [rejectedSignals, setRejectedSignals] = useState([]);
  const [assetAccuracy, setAssetAccuracy] = useState(null);
  const [scanSummaries, setScanSummaries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [r1, r2, r3, r4] = await Promise.allSettled([
        fetch('/api/rejection-stats').then(r => r.ok ? r.json() : null),
        fetch('/api/rejected-signals?limit=50').then(r => r.ok ? r.json() : null),
        fetch('/api/asset-accuracy').then(r => r.ok ? r.json() : null),
        fetch('/api/scan-summaries?days=7').then(r => r.ok ? r.json() : null),
      ]);
      if (r1.status === 'fulfilled' && r1.value) setRejectionStats(r1.value?.data || r1.value);
      if (r2.status === 'fulfilled' && r2.value) setRejectedSignals(r2.value?.data || r2.value?.signals || (Array.isArray(r2.value) ? r2.value : []));
      if (r3.status === 'fulfilled' && r3.value) setAssetAccuracy(r3.value?.data || r3.value);
      if (r4.status === 'fulfilled' && r4.value) setScanSummaries(r4.value?.data || r4.value?.summaries || (Array.isArray(r4.value) ? r4.value : []));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-4 border border-slate-800">
        <div className="flex items-center gap-2 text-slate-500 text-[10px]">
          <Loader2 className="w-3 h-3 animate-spin" /> 加载信号质量数据...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="shield-glass rounded-xl p-4 border border-red-500/20">
        <div className="flex items-center gap-2 text-red-400 text-[10px]">
          <AlertTriangle className="w-3 h-3" /> 加载失败: {error}
        </div>
      </div>
    );
  }

  const stats = rejectionStats || {};
  const totalScanned = stats.total_scanned || 0;
  const totalRejected = stats.total_rejected || 0;
  const totalPassed = stats.total_passed || 0;
  const rejectionRate = totalScanned > 0 ? ((totalRejected / totalScanned) * 100).toFixed(1) : '0';
  const filterBreakdown = stats.by_filter || stats.filter_breakdown || {};

  const filterBarData = Object.entries(filterBreakdown)
    .map(([name, count]) => ({ name: name.replace(/_/g, ' '), count: typeof count === 'number' ? count : (count?.count || 0) }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  const assets = assetAccuracy?.assets || assetAccuracy?.data || assetAccuracy || {};
  const assetEntries = Object.entries(typeof assets === 'object' && !Array.isArray(assets) ? assets : {})
    .filter(([k]) => k !== 'status' && k !== 'message')
    .map(([symbol, data]) => ({
      symbol,
      accuracy: typeof data === 'number' ? data : (data?.accuracy || data?.win_rate || 0),
      trades: typeof data === 'object' ? (data?.trades || data?.trade_count || data?.total || 0) : 0,
      pnl: typeof data === 'object' ? (data?.total_pnl || data?.pnl || 0) : 0,
    }))
    .sort((a, b) => b.accuracy - a.accuracy);

  const summaries = Array.isArray(scanSummaries) ? scanSummaries : [];
  const breadthData = summaries.map(s => ({
    date: s.date || s.timestamp || '',
    scanned: s.total_scanned || s.scanned || 0,
    passed: s.total_passed || s.passed || 0,
    rejected: s.total_rejected || s.rejected || 0,
    passRate: s.total_scanned > 0 ? ((s.total_passed || s.passed || 0) / (s.total_scanned || s.scanned || 1) * 100) : 0,
  })).reverse();

  return (
    <div className="shield-glass rounded-xl p-4 border border-slate-800">
      <div className="flex items-center gap-2 mb-4">
        <Filter className="w-4 h-4 text-amber-400" />
        <span className="text-[11px] font-black text-white uppercase tracking-wider">信号质量分析</span>
        <button
          onClick={fetchAll}
          className="ml-auto flex items-center gap-1 text-[8px] font-bold px-2 py-1 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 hover:bg-amber-500/25 transition-all"
        >
          <RefreshCw className="w-2.5 h-2.5" /> 刷新
        </button>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">总扫描</div>
            <div className="text-lg font-black text-cyan-400">{totalScanned.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">通过信号</div>
            <div className="text-lg font-black text-emerald-400">{totalPassed.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">拒绝信号</div>
            <div className="text-lg font-black text-red-400">{totalRejected.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">拒绝率</div>
            <div className={`text-lg font-black ${parseFloat(rejectionRate) > 80 ? 'text-red-400' : parseFloat(rejectionRate) > 50 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {rejectionRate}%
            </div>
          </div>
        </div>

        {filterBarData.length > 0 && (
          <div>
            <div className="text-[9px] font-bold text-white mb-2 flex items-center gap-1">
              <BarChart3 className="w-3 h-3 text-amber-400" /> 过滤器拒绝分布
            </div>
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={filterBarData} layout="vertical" margin={{ top: 2, right: 10, left: 2, bottom: 2 }}>
                  <XAxis type="number" tick={{ fontSize: 8, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 7, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={80} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {filterBarData.map((_, i) => (
                      <Cell key={i} fill={i === 0 ? '#ef4444' : i < 3 ? '#f59e0b' : '#3b82f6'} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {assetEntries.length > 0 && (
          <div>
            <div className="text-[9px] font-bold text-white mb-2 flex items-center gap-1">
              <Target className="w-3 h-3 text-cyan-400" /> 资产准确率排行
            </div>
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left py-2 px-2 font-black">资产</th>
                    <th className="text-right py-2 px-2 font-black">准确率</th>
                    <th className="text-right py-2 px-2 font-black">交易数</th>
                    <th className="text-right py-2 px-2 font-black">总PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {assetEntries.slice(0, 15).map((item, i) => {
                    const accPct = (item.accuracy * 100).toFixed(1);
                    return (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                        <td className="py-1.5 px-2 font-bold text-white">{item.symbol}</td>
                        <td className="py-1.5 px-2 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  item.accuracy >= 0.55 ? 'bg-emerald-500' : item.accuracy >= 0.4 ? 'bg-amber-500' : 'bg-red-500'
                                }`}
                                style={{ width: `${Math.min(100, item.accuracy * 100)}%` }}
                              />
                            </div>
                            <span className={`font-bold ${
                              item.accuracy >= 0.55 ? 'text-emerald-400' : item.accuracy >= 0.4 ? 'text-amber-400' : 'text-red-400'
                            }`}>{accPct}%</span>
                          </div>
                        </td>
                        <td className="py-1.5 px-2 text-right text-slate-300 font-mono">{item.trades}</td>
                        <td className={`py-1.5 px-2 text-right font-bold ${item.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {item.pnl !== 0 ? `${item.pnl >= 0 ? '+' : ''}${item.pnl.toFixed(2)}%` : '--'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {breadthData.length > 0 && (
          <div>
            <div className="text-[9px] font-bold text-white mb-2 flex items-center gap-1">
              <TrendingUp className="w-3 h-3 text-emerald-400" /> 市场广度趋势 (近7日)
            </div>
            <div className="h-36">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={breadthData} margin={{ top: 5, right: 10, left: 0, bottom: 2 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                  <XAxis dataKey="date" tick={{ fontSize: 7, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 7, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} />
                  <Line type="monotone" dataKey="scanned" stroke="#06b6d4" strokeWidth={1.5} dot={false} name="扫描" />
                  <Line type="monotone" dataKey="passed" stroke="#10b981" strokeWidth={1.5} dot={false} name="通过" />
                  <Line type="monotone" dataKey="rejected" stroke="#ef4444" strokeWidth={1.5} dot={false} name="拒绝" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {!totalScanned && assetEntries.length === 0 && breadthData.length === 0 && filterBarData.length === 0 && (
          <div className="text-center py-6">
            <AlertTriangle className="w-6 h-6 text-slate-600 mx-auto mb-2" />
            <div className="text-[10px] text-slate-500">暂无信号质量数据 — 系统运行后将自动收集</div>
          </div>
        )}
      </div>
    </div>
  );
}
