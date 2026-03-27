import { useState, useMemo } from 'react';
import { Search, ArrowUpDown, Radar, Activity, TrendingUp, TrendingDown, Minus, ChevronDown, ChevronUp } from 'lucide-react';
import { useShield } from '../hooks/useShieldData';
import { ScoreChip, StrengthBar, EmptyState } from '../components/ProUI';
import KLineChart from '../components/KLineChart';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const dirColor = (d) => {
  if (!d) return 'text-slate-500';
  if (d.includes('上涨') || d.includes('突破') || d === '强势') return 'text-emerald-400';
  if (d.includes('下跌') || d.includes('崩')) return 'text-red-400';
  return 'text-amber-400';
};

const mlColor = (label) => {
  if (label === '看涨') return 'text-emerald-400';
  if (label === '看跌') return 'text-red-400';
  return 'text-amber-400';
};

const mlBg = (label) => {
  if (label === '看涨') return 'bg-emerald-500/10 border-emerald-500/20';
  if (label === '看跌') return 'bg-red-500/10 border-red-500/20';
  return 'bg-amber-500/10 border-amber-500/20';
};

const fmtConf = (v) => {
  if (v == null) return '--';
  const n = parseFloat(v);
  if (n > 1) return n.toFixed(1);
  return (n * 100).toFixed(1);
};

const fmtChange = (v) => {
  if (v == null) return '--';
  const n = parseFloat(v);
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
};

export default function SignalRadar() {
  const {
    sortedCruise, filteredCruise, cruise,
    searchTerm, setSearchTerm,
    filterMode, setFilterMode,
    sortField, sortDir, toggleSort,
    totalScanned, scanMode, scanProgress, data,
  } = useShield();

  const [chartSymbol, setChartSymbol] = useState(null);
  const [expandedIdx, setExpandedIdx] = useState(null);

  const filters = [
    { id: 'ALL', label: '全部' },
    { id: 'ALPHA', label: '强信号' },
    { id: 'ML_BULL', label: 'ML看涨' },
    { id: 'BEARISH', label: '看跌' },
  ];

  const heatGroups = useMemo(() => {
    const bull = [];
    const bear = [];
    const neutral = [];
    cruise.forEach(item => {
      const label = item.ml?.label;
      const dir = item.daily?.direction || '';
      if (label === '看涨' || dir.includes('上涨') || dir.includes('突破')) {
        bull.push(item);
      } else if (label === '看跌' || dir.includes('下跌') || dir.includes('崩')) {
        bear.push(item);
      } else {
        neutral.push(item);
      }
    });
    return { bull, bear, neutral };
  }, [cruise]);

  const handleCardClick = (idx, sym) => {
    if (expandedIdx === idx) {
      setExpandedIdx(null);
      setChartSymbol(null);
    } else {
      setExpandedIdx(idx);
      setChartSymbol(sym);
    }
  };

  return (
    <div className="space-y-4 animate-fadeIn">
      {chartSymbol && expandedIdx == null && (
        <KLineChart symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
      )}

      <div className="shield-glass rounded-2xl p-4">
        <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
          <div className="relative flex-1 w-full sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="搜索标的..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white focus:border-amber-500 focus:outline-none focus:ring-1 focus:ring-amber-500/20 transition-all"
            />
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            {filters.map(f => (
              <button
                key={f.id}
                onClick={() => setFilterMode(f.id)}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-black uppercase transition-all ${
                  filterMode === f.id
                    ? 'bg-gradient-to-r from-amber-500 to-orange-500 text-black shadow-lg shadow-amber-500/20'
                    : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-300'
                }`}
              >
                {f.label}
              </button>
            ))}

            <div className="border-l border-slate-700 pl-2 flex gap-1">
              <button
                onClick={() => toggleSort('score')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-bold flex items-center gap-1 transition-all ${
                  sortField === 'score' ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-800 text-slate-500 hover:text-slate-300'
                }`}
              >
                <ArrowUpDown className="w-3 h-3" /> 评分
              </button>
              <button
                onClick={() => toggleSort('ml')}
                className={`px-2 py-1.5 rounded-lg text-[10px] font-bold flex items-center gap-1 transition-all ${
                  sortField === 'ml' ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-800 text-slate-500 hover:text-slate-300'
                }`}
              >
                <ArrowUpDown className="w-3 h-3" /> ML
              </button>
            </div>

            <div className="flex items-center gap-2 ml-1">
              <span className="text-[10px] text-slate-500 font-mono tabular-nums">
                {filteredCruise.length}/{cruise.length}
              </span>
              <span className={`flex items-center gap-1 px-2 py-1 rounded-lg border text-[9px] font-bold ${scanProgress.scanning ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-violet-500/10 border-violet-500/20 text-violet-400'}`}>
                <Radar className={`w-3 h-3 ${scanProgress.scanning ? 'animate-spin' : ''}`} />
                {scanProgress.scanning
                  ? `扫描中 ${scanProgress.current}/${scanProgress.total}`
                  : `${scanMode} · ${cruise.length}个标的`
                }
              </span>
            </div>
          </div>
        </div>
      </div>

      {sortedCruise.length === 0 ? (
        <EmptyState icon={Radar} title="雷达扫描中..." subtitle="等待信号引擎返回数据" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {sortedCruise.map((item, idx) => {
            const ml = item.ml;
            const daily = item.daily;
            const sym = item.symbol || '???';
            const strategy = item.strategy || '';
            const score = item.score || 0;
            const isExpanded = expandedIdx === idx;
            const changePct = daily?.change_pct;
            const changeColor = changePct != null ? (changePct >= 0 ? 'text-emerald-400' : 'text-red-400') : 'text-slate-500';

            return (
              <div
                key={sym + '-' + idx}
                className="shield-glass rounded-xl p-4 transition-all cursor-pointer hover:border-amber-500/30 animate-slideUp"
                style={{ animationDelay: `${idx * 20}ms` }}
                onClick={() => handleCardClick(idx, sym)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <ScoreChip score={score} size="sm" />
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-black text-white truncate">{sym}</span>
                        {strategy && (
                          <span className="text-[8px] font-bold bg-slate-800/80 text-slate-400 px-1.5 py-0.5 rounded shrink-0">{strategy}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] text-slate-300 font-mono tabular-nums">${item.price?.toLocaleString?.() ?? safe(item.price)}</span>
                        <span className={`text-[10px] font-bold tabular-nums ${changeColor}`}>
                          {fmtChange(changePct)}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="hidden sm:flex flex-col items-end gap-1 shrink-0">
                    {ml && (
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${mlBg(ml.label)} ${mlColor(ml.label)}`}>
                        {ml.label} {fmtConf(ml.confidence)}%
                      </span>
                    )}
                    {daily?.direction && (
                      <span className={`text-[9px] font-bold ${dirColor(daily.direction)}`}>
                        {daily.direction}
                      </span>
                    )}
                  </div>

                  <div className="sm:hidden flex items-center gap-2 shrink-0">
                    {ml && (
                      <span className={`text-[9px] font-bold ${mlColor(ml.label)}`}>{ml.label}</span>
                    )}
                    {isExpanded ? <ChevronUp className="w-3 h-3 text-slate-500" /> : <ChevronDown className="w-3 h-3 text-slate-500" />}
                  </div>
                </div>

                <div className="hidden sm:flex items-center gap-2 mt-2 flex-wrap">
                  {item.vol_rank != null && (
                    <span className="text-[8px] font-bold bg-slate-800/60 text-slate-400 px-1.5 py-0.5 rounded">
                      量排 #{safe(item.vol_rank)}
                    </span>
                  )}
                  {item.rsi != null && (
                    <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${
                      item.rsi > 70 ? 'bg-red-500/10 text-red-400' : item.rsi < 30 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800/60 text-slate-400'
                    }`}>
                      RSI {typeof item.rsi === 'number' ? Math.round(item.rsi) : safe(item.rsi)}
                    </span>
                  )}
                  {item.adx != null && (
                    <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${
                      item.adx > 25 ? 'bg-amber-500/10 text-amber-400' : 'bg-slate-800/60 text-slate-400'
                    }`}>
                      ADX {typeof item.adx === 'number' ? item.adx.toFixed(1) : safe(item.adx)}
                    </span>
                  )}
                  {item.atr_pct != null && (
                    <span className="text-[8px] font-bold bg-slate-800/60 text-slate-400 px-1.5 py-0.5 rounded">
                      ATR {typeof item.atr_pct === 'number' ? item.atr_pct.toFixed(2) : safe(item.atr_pct)}%
                    </span>
                  )}
                </div>

                {(() => {
                  const stats = item.trade_stats || item.history_stats;
                  const totalTrades = stats?.total || stats?.count || 0;
                  const accuracy = stats?.accuracy ?? stats?.win_rate;
                  if (totalTrades < 5 || accuracy == null) {
                    return (
                      <div className="mt-2 flex items-center gap-1.5">
                        <span className="text-[8px] font-bold text-slate-600">历史准确率:</span>
                        <span className="text-[8px] font-bold text-slate-600">数据不足</span>
                      </div>
                    );
                  }
                  const pct = typeof accuracy === 'number' && accuracy <= 1 ? accuracy * 100 : accuracy;
                  const accColor = pct >= 55 ? 'text-emerald-400' : pct >= 45 ? 'text-amber-400' : 'text-red-400';
                  const accDot = pct >= 55 ? '🟢' : pct >= 45 ? '🟡' : '🔴';
                  return (
                    <div className="mt-2 flex items-center gap-1.5">
                      <span className="text-[8px] font-bold text-slate-500">历史准确率:</span>
                      <span className={`text-[8px] font-bold ${accColor}`}>{pct.toFixed(0)}% ({totalTrades}笔)</span>
                      <span className="text-[8px]">{accDot}</span>
                    </div>
                  );
                })()}

                <div className="mt-2">
                  <StrengthBar value={score} max={100} />
                </div>

                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-slate-800 animate-fadeIn">
                    <div className="sm:hidden flex flex-wrap items-center gap-2 mb-3">
                      {daily?.direction && (
                        <span className={`text-[9px] font-bold ${dirColor(daily.direction)}`}>{daily.direction}</span>
                      )}
                      {item.vol_rank != null && (
                        <span className="text-[8px] font-bold bg-slate-800/60 text-slate-400 px-1.5 py-0.5 rounded">量排 #{safe(item.vol_rank)}</span>
                      )}
                      {item.rsi != null && (
                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${
                          item.rsi > 70 ? 'bg-red-500/10 text-red-400' : item.rsi < 30 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-slate-800/60 text-slate-400'
                        }`}>
                          RSI {typeof item.rsi === 'number' ? Math.round(item.rsi) : safe(item.rsi)}
                        </span>
                      )}
                      {item.adx != null && (
                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${
                          item.adx > 25 ? 'bg-amber-500/10 text-amber-400' : 'bg-slate-800/60 text-slate-400'
                        }`}>
                          ADX {typeof item.adx === 'number' ? item.adx.toFixed(1) : safe(item.adx)}
                        </span>
                      )}
                      {item.atr_pct != null && (
                        <span className="text-[8px] font-bold bg-slate-800/60 text-slate-400 px-1.5 py-0.5 rounded">
                          ATR {typeof item.atr_pct === 'number' ? item.atr_pct.toFixed(2) : safe(item.atr_pct)}%
                        </span>
                      )}
                    </div>
                    <div className="rounded-xl overflow-hidden border border-slate-800 bg-slate-950/60" style={{ height: 320 }}>
                      <KLineChart symbol={sym} onClose={() => { setExpandedIdx(null); setChartSymbol(null); }} />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {cruise.length > 0 && (
        <div className="shield-glass rounded-xl p-4">
          <h3 className="text-xs font-black text-slate-400 uppercase mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" /> 市场热力分布
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-[10px] font-bold text-emerald-400">看涨 ({heatGroups.bull.length})</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {heatGroups.bull.slice(0, 30).map((item, i) => (
                  <div
                    key={i}
                    className="group relative w-5 h-5 rounded-full bg-emerald-500/30 border border-emerald-500/40 hover:bg-emerald-500/60 transition-all cursor-default flex items-center justify-center"
                    title={`${item.symbol} · 评分${item.score}`}
                  >
                    <span className="text-[6px] font-bold text-emerald-300 truncate leading-none">
                      {(item.symbol || '').replace('/USDT', '').slice(0, 3)}
                    </span>
                  </div>
                ))}
                {heatGroups.bull.length === 0 && <span className="text-[9px] text-slate-600">暂无</span>}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Minus className="w-3.5 h-3.5 text-amber-400" />
                <span className="text-[10px] font-bold text-amber-400">横盘 ({heatGroups.neutral.length})</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {heatGroups.neutral.slice(0, 30).map((item, i) => (
                  <div
                    key={i}
                    className="group relative w-5 h-5 rounded-full bg-amber-500/30 border border-amber-500/40 hover:bg-amber-500/60 transition-all cursor-default flex items-center justify-center"
                    title={`${item.symbol} · 评分${item.score}`}
                  >
                    <span className="text-[6px] font-bold text-amber-300 truncate leading-none">
                      {(item.symbol || '').replace('/USDT', '').slice(0, 3)}
                    </span>
                  </div>
                ))}
                {heatGroups.neutral.length === 0 && <span className="text-[9px] text-slate-600">暂无</span>}
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <TrendingDown className="w-3.5 h-3.5 text-red-400" />
                <span className="text-[10px] font-bold text-red-400">看跌 ({heatGroups.bear.length})</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {heatGroups.bear.slice(0, 30).map((item, i) => (
                  <div
                    key={i}
                    className="group relative w-5 h-5 rounded-full bg-red-500/30 border border-red-500/40 hover:bg-red-500/60 transition-all cursor-default flex items-center justify-center"
                    title={`${item.symbol} · 评分${item.score}`}
                  >
                    <span className="text-[6px] font-bold text-red-300 truncate leading-none">
                      {(item.symbol || '').replace('/USDT', '').slice(0, 3)}
                    </span>
                  </div>
                ))}
                {heatGroups.bear.length === 0 && <span className="text-[9px] text-slate-600">暂无</span>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
