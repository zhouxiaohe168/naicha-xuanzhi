import { useState, useCallback } from 'react';
import { Wallet, Target, Clock, TrendingUp, TrendingDown, AlertTriangle, Shield, ChevronDown, ChevronUp, CandlestickChart, X, Grid3X3, DollarSign, BarChart3, Activity, Archive, Layers, ArrowUpDown, Info } from 'lucide-react';
import { useShield } from '../hooks/useShieldData';
import { AnimatedNumber, GaugeRing, StatusDot, PortfolioDonut, EmptyState } from '../components/ProUI';
import KLineChart from '../components/KLineChart';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const pnlColor = (v) => {
  const n = parseFloat(v) || 0;
  if (n > 0) return 'text-emerald-400';
  if (n < 0) return 'text-red-400';
  return 'text-slate-400';
};

const advisorLabel = (action) => {
  const map = { hold: '持有', add: '加仓', reduce: '减仓', close: '平仓' };
  return map[action] || action || '持有';
};

const advisorColor = (action) => {
  if (action === 'add') return 'text-emerald-400 bg-emerald-500/10';
  if (action === 'reduce') return 'text-amber-400 bg-amber-500/10';
  if (action === 'close') return 'text-red-400 bg-red-500/10';
  return 'text-cyan-400 bg-cyan-500/10';
};

export default function PositionManager() {
  const {
    paperPositions = [], closePaperPosition,
    paperPortfolio, paperTrades = [],
    constitutionStatus, wallStreetMetrics,
    capitalSizerData, gridData, fetchData,
  } = useShield();

  const [activeTab, setActiveTab] = useState('positions');
  const [closingId, setClosingId] = useState(null);
  const [chartSymbol, setChartSymbol] = useState(null);
  const [riskOpen, setRiskOpen] = useState(false);
  const [closingGrid, setClosingGrid] = useState(null);

  const handleClose = async (posId) => {
    setClosingId(posId);
    try {
      await closePaperPosition(posId);
    } catch (e) {
      console.error(e);
    }
    setClosingId(null);
  };

  const closeGrid = useCallback(async (symbol) => {
    setClosingGrid(symbol);
    try {
      const res = await fetch(`/api/grid/close/${symbol}`, { method: 'POST' });
      if (res.ok) setTimeout(() => fetchData?.(), 2000);
    } catch (e) {
      console.error(e);
    }
    setTimeout(() => setClosingGrid(null), 2000);
  }, [fetchData]);

  const equity = parseFloat(paperPortfolio?.equity) || 0;
  const totalPnl = parseFloat(paperPortfolio?.total_pnl) || 0;
  const totalPnlPct = parseFloat(paperPortfolio?.total_pnl_pct || paperPortfolio?.total_return_pct) || 0;
  const winCount = paperPortfolio?.total_wins || 0;
  const lossCount = paperPortfolio?.total_losses || 0;
  const winRate = (winCount + lossCount) > 0 ? (winCount / (winCount + lossCount)) * 100 : 0;
  const maxDrawdown = parseFloat(paperPortfolio?.max_drawdown_pct) || 0;
  const currentDrawdown = parseFloat(constitutionStatus?.current_drawdown) || 0;
  const maxAllowedDrawdown = parseFloat(constitutionStatus?.max_allowed_drawdown) || 15;

  const [gridSubTab, setGridSubTab] = useState('overview');

  const grids = gridData?.grid_details ? Object.entries(gridData.grid_details).map(([sym, d]) => ({
    symbol: sym,
    direction: d.bias === 'long' ? 'long' : d.bias === 'short' ? 'short' : 'neutral',
    levels: d.grids,
    pnl: d.pnl,
    realized_pnl: d.realized_pnl || 0,
    inventory_pnl: d.inventory_pnl || 0,
    held_qty: d.held_qty || 0,
    avg_buy_price: d.avg_buy_price || 0,
    status: d.spacing_mode,
    range: d.range,
    created: d.created,
    buys_filled: d.buys_filled || 0,
    sells_filled: d.sells_filled || 0,
    total_orders: d.total_orders || 0,
    filled_orders: d.filled_orders || 0,
    pending_orders: d.pending_orders || 0,
    pending_buys: d.pending_buys || 0,
    pending_sells: d.pending_sells || 0,
    trailing: d.trailing_enabled,
    trailing_shifts: d.trailing_shifts || 0,
    boundary_source: d.boundary_source,
    capital_used: d.capital_used || 0,
    entry_price: d.entry_price || 0,
    current_price: d.current_price || 0,
    sl_price: d.sl_price || 0,
    upper: d.upper || 0,
    lower: d.lower || 0,
    last_update: d.last_update || '',
    amount_per_grid: d.amount_per_grid || 0,
  })) : [];

  const activeGridCount = gridData?.active_grids || 0;
  const gridTotalCapital = gridData?.total_capital_used || 0;
  const gridTotalOrders = gridData?.total_orders || 0;
  const gridFilledOrders = gridData?.total_filled_orders || 0;
  const gridPendingOrders = gridData?.pending_orders || 0;
  const gridPendingBuys = gridData?.pending_buy_orders || 0;
  const gridPendingSells = gridData?.pending_sell_orders || 0;
  const gridRealizedPnl = gridData?.total_profit || 0;
  const gridUnrealizedPnl = gridData?.unrealized_pnl || 0;
  const gridInventoryPnl = gridData?.inventory_pnl || 0;
  const gridRealizedGridPnl = gridData?.realized_grid_pnl || 0;
  const gridNetPnl = gridData?.net_pnl || 0;
  const gridWinRate = gridData?.win_rate || 0;
  const gridTotalTrades = gridData?.total_trades || 0;
  const gridHistory = gridData?.grid_history || [];

  const tabs = [
    { id: 'positions', label: '活跃持仓', icon: Target, count: paperPositions.length },
    { id: 'grid', label: '网格交易', icon: Grid3X3, count: activeGridCount },
    { id: 'history', label: '交易记录', icon: Clock, count: paperTrades.length },
  ];

  return (
    <div className="space-y-4 animate-fadeIn">
      {chartSymbol && (
        <KLineChart symbol={chartSymbol} onClose={() => setChartSymbol(null)} />
      )}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="shield-glass shield-glass-hover rounded-2xl p-4 gradient-border">
          <div className="text-[9px] text-slate-500 font-black uppercase tracking-widest mb-1">总资产</div>
          <div className="text-xl font-black text-white tabular-nums">
            $<AnimatedNumber value={equity} decimals={0} />
          </div>
          <div className="text-[9px] text-slate-600 mt-1">初始: ${safe(paperPortfolio?.initial_capital)}</div>
        </div>

        <div className="shield-glass shield-glass-hover rounded-2xl p-4 gradient-border">
          <div className="text-[9px] text-slate-500 font-black uppercase tracking-widest mb-1">累计盈亏</div>
          <div className={`text-xl font-black tabular-nums ${pnlColor(totalPnl)}`}>
            <AnimatedNumber value={totalPnl} decimals={2} prefix={totalPnl >= 0 ? '+$' : '-$'} />
          </div>
          <div className={`text-[9px] mt-1 font-bold tabular-nums ${pnlColor(totalPnlPct)}`}>
            {totalPnlPct >= 0 ? '+' : ''}{totalPnlPct.toFixed(2)}%
          </div>
        </div>

        <div className="shield-glass shield-glass-hover rounded-2xl p-4 gradient-border flex flex-col items-center justify-center">
          <GaugeRing value={winRate} max={100} size={56} strokeWidth={5}
            color={winRate >= 50 ? '#10b981' : '#f59e0b'} sublabel="%" />
          <span className="text-[9px] text-slate-500 font-black uppercase mt-1">胜率</span>
          <div className="text-[9px] text-slate-600 tabular-nums">{winCount}W / {lossCount}L</div>
        </div>

        <div className="shield-glass shield-glass-hover rounded-2xl p-4 gradient-border">
          <div className="text-[9px] text-slate-500 font-black uppercase tracking-widest mb-1">当前回撤</div>
          <div className={`text-xl font-black tabular-nums ${currentDrawdown > 10 ? 'text-red-400' : currentDrawdown > 5 ? 'text-amber-400' : 'text-emerald-400'}`}>
            {currentDrawdown.toFixed(2)}%
          </div>
          <div className="text-[9px] text-slate-600 mt-1">最大: {maxDrawdown.toFixed(2)}%</div>
        </div>
      </div>

      <div className="shield-glass-elevated rounded-2xl p-1.5 flex gap-1">
        {tabs.map(t => (
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
            <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-black ${
              activeTab === t.id ? 'bg-black/20 text-black' : 'bg-slate-800 text-slate-400'
            }`}>
              {t.count}
            </span>
          </button>
        ))}
      </div>

      {activeTab === 'positions' && (
        <div className="space-y-3">
          {paperPositions.length === 0 ? (
            <div className="shield-glass rounded-2xl p-5">
              <EmptyState icon={Target} title="暂无活跃持仓" subtitle="系统将自主寻找交易机会" />
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              {paperPositions.map(pos => {
                const pnlPct = parseFloat(pos.pnl_pct || pos.unrealized_pnl_pct) || 0;
                const pnlAmt = parseFloat(pos.pnl_amount || pos.unrealized_pnl) || 0;
                const isLong = (pos.direction || '').toLowerCase() === 'long';
                const confidence = parseFloat(pos.advisor_confidence) || 0;
                return (
                  <div key={pos.id} className="shield-glass shield-glass-hover rounded-2xl p-4 gradient-border transition-all">
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-lg font-black text-white">{safe(pos.symbol)}</h4>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-lg ${
                          isLong ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/15 text-red-400 border border-red-500/20'
                        }`}>
                          {isLong ? '做多' : '做空'}
                        </span>
                        {pos.strategy && (
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                            {safe(pos.strategy)}
                          </span>
                        )}
                        <button
                          onClick={() => setChartSymbol(pos.symbol)}
                          className="w-5 h-5 flex items-center justify-center rounded bg-slate-800/60 text-slate-500 hover:text-amber-400 hover:bg-amber-500/10 transition-all"
                        >
                          <CandlestickChart className="w-3 h-3" />
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2 mb-3 text-[10px]">
                      <div>
                        <span className="text-slate-500 block">入场价</span>
                        <span className="text-slate-300 font-mono tabular-nums font-bold">${Number(pos.entry_price || 0).toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">现价</span>
                        <span className="text-slate-300 font-mono tabular-nums font-bold">${Number(pos.current_price || 0).toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-slate-500 block">仓位</span>
                        <span className="text-slate-300 font-mono tabular-nums font-bold">${Number(pos.size || pos.amount || 0).toLocaleString()}</span>
                      </div>
                    </div>

                    <div className={`text-2xl font-black tabular-nums mb-3 ${pnlColor(pnlPct)}`}>
                      {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                      <span className={`text-sm ml-2 ${pnlColor(pnlAmt)}`}>
                        {pnlAmt >= 0 ? '+' : ''}{pnlAmt.toFixed(2)}
                      </span>
                    </div>

                    {(pos.advisor_action || pos.advisor_confidence) && (
                      <div className="flex items-center gap-2 mb-3 p-2 rounded-xl bg-slate-950/60 border border-slate-800/50">
                        <span className="text-[9px] text-slate-500 font-bold">AI顾问</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-lg ${advisorColor(pos.advisor_action)}`}>
                          {advisorLabel(pos.advisor_action)}
                        </span>
                        <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-500 transition-all"
                            style={{ width: `${Math.min(confidence * 100, 100)}%` }}
                          />
                        </div>
                        <span className="text-[9px] text-slate-500 tabular-nums font-bold">{(confidence * 100).toFixed(0)}%</span>
                      </div>
                    )}

                    <div className="flex flex-wrap items-center gap-2 text-[9px]">
                      {pos.sl_price && (
                        (() => {
                          const slPct = pos.entry_price > 0 ? Math.abs((pos.entry_price - pos.sl_price) / pos.entry_price * 100) : 0;
                          const slColor = slPct < 3 ? 'text-red-500 border-red-500/30 bg-red-500/15' : slPct < 6 ? 'text-yellow-400 border-yellow-500/20 bg-yellow-500/10' : 'text-green-400 border-green-500/20 bg-green-500/10';
                          return (
                            <span className={`px-1.5 py-0.5 rounded font-bold tabular-nums border ${slColor}`} title={slPct < 3 ? 'SL距离<3%: 危险区' : slPct < 6 ? 'SL距离3-6%: 正常' : 'SL距离>6%: 安全'}>
                              SL ${Number(pos.sl_price).toLocaleString()} ({slPct.toFixed(1)}%)
                            </span>
                          );
                        })()
                      )}
                      {pos.tp_price && (
                        <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/15 font-bold tabular-nums">
                          TP ${Number(pos.tp_price).toLocaleString()}
                        </span>
                      )}
                      {pos.direction_4h && (
                        (() => {
                          const isLongDir = (pos.direction || '').toLowerCase() === 'long';
                          const aligned = (isLongDir && pos.direction_4h === 'up') || (!isLongDir && pos.direction_4h === 'down');
                          return (
                            <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${aligned ? 'bg-green-900/40 text-green-400 border border-green-500/20' : 'bg-red-900/40 text-red-400 border border-red-500/20'}`}>
                              4H {pos.direction_4h === 'up' ? '\u2191' : pos.direction_4h === 'down' ? '\u2193' : '\u2194'}{aligned ? ' \u2713' : ' \u2717'}
                            </span>
                          );
                        })()
                      )}
                      <button
                        onClick={() => handleClose(pos.id)}
                        disabled={closingId === pos.id}
                        className="ml-auto text-slate-600 hover:text-red-400 text-[9px] font-bold border border-slate-800 hover:border-red-500/30 px-2 py-1 rounded-lg transition-all disabled:opacity-50"
                      >
                        {closingId === pos.id ? '...' : '紧急平仓'}
                      </button>
                    </div>

                    {pos.created_at && (() => {
                      const holdHours = (Date.now() - new Date(pos.created_at).getTime()) / 3600000;
                      const protectionPct = Math.min(holdHours / 2 * 100, 100);
                      const isProtected = holdHours < 2;
                      return (
                        <div className="mt-3 pt-2 border-t border-slate-800/40">
                          <div className="flex justify-between text-[9px] mb-1">
                            <span className="text-slate-500 flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {holdHours >= 24 ? `${Math.floor(holdHours / 24)}d ${Math.floor(holdHours % 24)}h` : `${holdHours.toFixed(1)}h`}
                            </span>
                            <span className={`font-bold ${isProtected ? 'text-yellow-400' : 'text-green-400'}`}>
                              {isProtected ? `P0-LAST ${Math.max(0, (2 - holdHours) * 60).toFixed(0)}min` : 'P0-LAST \u2713'}
                            </span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1 overflow-hidden">
                            <div className={`h-full rounded-full transition-all ${isProtected ? 'bg-yellow-400' : 'bg-green-400'}`} style={{ width: `${protectionPct}%` }} />
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {activeTab === 'grid' && (
        <div className="space-y-4">
          <div className="flex gap-1 p-1 bg-slate-900/60 rounded-xl border border-slate-800/50">
            {[
              { id: 'overview', label: '总览', icon: Layers },
              { id: 'active', label: `活跃持仓 (${activeGridCount})`, icon: Activity },
              { id: 'closed', label: `已关闭 (${gridTotalTrades})`, icon: Archive },
            ].map(st => (
              <button key={st.id} onClick={() => setGridSubTab(st.id)}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-[10px] font-bold transition-all flex-1 justify-center ${
                  gridSubTab === st.id
                    ? 'bg-blue-500/20 border border-blue-500/30 text-blue-300 shadow-sm'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/50'
                }`}>
                <st.icon className="w-3 h-3" />
                {st.label}
              </button>
            ))}
          </div>

          {gridSubTab === 'overview' && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="shield-glass rounded-xl p-3 border border-slate-800">
                  <div className="text-[9px] text-slate-500 font-black uppercase">投入资金</div>
                  <div className="text-xl font-black text-cyan-400 mt-1 tabular-nums">
                    ${gridTotalCapital > 1000 ? `${(gridTotalCapital / 1000).toFixed(1)}k` : gridTotalCapital.toFixed(0)}
                  </div>
                  <div className="text-[8px] text-slate-600 mt-0.5">{activeGridCount} 个活跃网格</div>
                </div>
                <div className="shield-glass rounded-xl p-3 border border-slate-800">
                  <div className="text-[9px] text-slate-500 font-black uppercase">订单统计</div>
                  <div className="text-xl font-black text-white mt-1 tabular-nums">{gridFilledOrders}<span className="text-slate-600 text-sm">/{gridTotalOrders}</span></div>
                  <div className="text-[8px] text-slate-600 mt-0.5">已成交 | 待执行 {gridPendingOrders} 单</div>
                </div>
                <div className="shield-glass rounded-xl p-3 border border-slate-800">
                  <div className="text-[9px] text-slate-500 font-black uppercase">活跃盈亏</div>
                  <div className={`text-xl font-black mt-1 tabular-nums ${pnlColor(gridUnrealizedPnl)}`}>
                    {gridUnrealizedPnl >= 0 ? '+' : ''}${gridUnrealizedPnl.toFixed(2)}
                  </div>
                  <div className="text-[8px] text-slate-600 mt-0.5">
                    {gridTotalCapital > 0 ? `网格利润 ${gridRealizedGridPnl >= 0 ? '+' : ''}$${gridRealizedGridPnl.toFixed(2)} | 持仓浮动 ${gridInventoryPnl >= 0 ? '+' : ''}$${gridInventoryPnl.toFixed(2)}` : '当前活跃网格'}
                  </div>
                </div>
                <div className="shield-glass rounded-xl p-3 border border-slate-800">
                  <div className="text-[9px] text-slate-500 font-black uppercase">已平仓盈亏</div>
                  <div className={`text-xl font-black mt-1 tabular-nums ${pnlColor(gridRealizedPnl)}`}>
                    {gridRealizedPnl >= 0 ? '+' : ''}${gridRealizedPnl.toFixed(2)}
                  </div>
                  <div className="text-[8px] text-slate-600 mt-0.5">{gridTotalTrades} 笔已关闭 | 胜率 {gridWinRate.toFixed(0)}%</div>
                </div>
              </div>

              <div className="shield-glass rounded-xl p-4 border border-slate-800">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] text-slate-400 font-bold flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5 text-cyan-400" /> 网格综合盈亏
                  </span>
                  <span className={`font-black tabular-nums text-lg ${pnlColor(gridNetPnl)}`}>
                    {gridNetPnl >= 0 ? '+' : ''}${gridNetPnl.toFixed(2)}
                  </span>
                </div>
                <div className="h-2 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${gridNetPnl >= 0 ? 'bg-gradient-to-r from-emerald-500 to-cyan-500' : 'bg-gradient-to-r from-red-500 to-orange-500'}`}
                    style={{ width: `${Math.min(Math.abs(gridNetPnl) / Math.max(gridTotalCapital, 1) * 100 * 20, 100)}%` }}
                  />
                </div>
                <div className="grid grid-cols-3 gap-2 mt-3">
                  <div className="bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/50">
                    <div className="text-[8px] text-slate-500 font-bold mb-1">网格交易利润</div>
                    <div className={`text-sm font-black tabular-nums ${pnlColor(gridRealizedGridPnl)}`}>
                      {gridRealizedGridPnl >= 0 ? '+' : ''}${gridRealizedGridPnl.toFixed(2)}
                    </div>
                  </div>
                  <div className="bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/50">
                    <div className="text-[8px] text-slate-500 font-bold mb-1">持仓浮动盈亏</div>
                    <div className={`text-sm font-black tabular-nums ${pnlColor(gridInventoryPnl)}`}>
                      {gridInventoryPnl >= 0 ? '+' : ''}${gridInventoryPnl.toFixed(2)}
                    </div>
                  </div>
                  <div className="bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/50">
                    <div className="text-[8px] text-slate-500 font-bold mb-1">已平仓盈亏</div>
                    <div className={`text-sm font-black tabular-nums ${pnlColor(gridRealizedPnl)}`}>
                      {gridRealizedPnl >= 0 ? '+' : ''}${gridRealizedPnl.toFixed(2)}
                    </div>
                  </div>
                </div>
                {gridRealizedPnl < 0 && (
                  <div className="mt-3 p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/20">
                    <div className="flex items-start gap-2 text-[9px] text-amber-400/80">
                      <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      <span>已平仓盈亏为负数是因为之前关闭的 {gridTotalTrades} 个网格中，有网格因止损或跌破区间而亏损关闭。这是正常的风控行为，不影响当前活跃网格的盈利。</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="shield-glass rounded-xl p-4 border border-slate-800">
                <div className="text-[9px] text-slate-400 font-bold mb-3 flex items-center gap-1.5">
                  <ArrowUpDown className="w-3.5 h-3.5 text-blue-400" /> 挂单分布
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div className="text-center">
                    <div className="text-[8px] text-slate-500 font-bold">待买入</div>
                    <div className="text-lg font-black text-cyan-400 tabular-nums">{gridPendingBuys}</div>
                    <div className="text-[8px] text-slate-600">等待低位接货</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[8px] text-slate-500 font-bold">待卖出</div>
                    <div className="text-lg font-black text-amber-400 tabular-nums">{gridPendingSells}</div>
                    <div className="text-[8px] text-slate-600">等待高位出货</div>
                  </div>
                  <div className="text-center">
                    <div className="text-[8px] text-slate-500 font-bold">已成交</div>
                    <div className="text-lg font-black text-emerald-400 tabular-nums">{gridFilledOrders}</div>
                    <div className="text-[8px] text-slate-600">买卖已完成</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {gridSubTab === 'active' && (
            <div className="space-y-3">
              {grids.length === 0 ? (
                <div className="shield-glass rounded-2xl p-8 border border-slate-800">
                  <EmptyState icon={Grid3X3} title="暂无活跃网格" subtitle="系统将根据市场环境自动创建网格" />
                </div>
              ) : (
                grids.map((g, i) => {
                  const priceChangePct = g.entry_price > 0 && g.current_price > 0
                    ? ((g.current_price - g.entry_price) / g.entry_price * 100)
                    : 0;
                  const pnlPct = g.capital_used > 0 ? (g.pnl / g.capital_used * 100) : 0;
                  const posInRange = g.upper > g.lower && g.current_price > 0
                    ? ((g.current_price - g.lower) / (g.upper - g.lower) * 100)
                    : 50;

                  return (
                    <div key={i} className="shield-glass rounded-2xl border border-slate-700/50 overflow-hidden">
                      <div className="p-4">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="text-lg font-black text-white">{g.symbol}</span>
                            <span className={`text-[9px] font-bold px-2 py-0.5 rounded-lg ${
                              g.direction === 'long' ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20' :
                              g.direction === 'short' ? 'bg-red-500/15 text-red-400 border border-red-500/20' :
                              'bg-blue-500/15 text-blue-400 border border-blue-500/20'
                            }`}>
                              {g.direction === 'long' ? '做多偏向' : g.direction === 'short' ? '做空偏向' : '中性'}
                            </span>
                            <span className="text-[8px] text-slate-500 px-1.5 py-0.5 bg-slate-800/60 rounded border border-slate-700/50">
                              {g.status === 'geometric' ? '等比网格' : '等差网格'}
                            </span>
                            {g.trailing && (
                              <span className="text-[8px] text-amber-400 px-1.5 py-0.5 bg-amber-500/10 rounded border border-amber-500/20">
                                追踪模式{g.trailing_shifts > 0 ? ` ×${g.trailing_shifts}` : ''}
                              </span>
                            )}
                          </div>
                          <button onClick={() => closeGrid(g.symbol)} disabled={closingGrid === g.symbol}
                            className="text-[10px] text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 px-3 py-1.5 rounded-lg transition font-bold disabled:opacity-50 shrink-0 border border-red-500/20">
                            {closingGrid === g.symbol ? '关闭中...' : '手动关闭'}
                          </button>
                        </div>

                        <div className="grid grid-cols-3 gap-3 mb-3">
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50">
                            <div className="text-[8px] text-slate-500 font-bold">入场价</div>
                            <div className="text-sm font-black text-white tabular-nums mt-0.5">${g.entry_price > 1 ? g.entry_price.toFixed(2) : g.entry_price.toFixed(6)}</div>
                          </div>
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50">
                            <div className="text-[8px] text-slate-500 font-bold">现价</div>
                            <div className={`text-sm font-black tabular-nums mt-0.5 ${pnlColor(priceChangePct)}`}>
                              ${g.current_price > 1 ? g.current_price.toFixed(2) : g.current_price.toFixed(6)}
                            </div>
                          </div>
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50">
                            <div className="text-[8px] text-slate-500 font-bold">价格变动</div>
                            <div className={`text-sm font-black tabular-nums mt-0.5 ${pnlColor(priceChangePct)}`}>
                              {priceChangePct >= 0 ? '+' : ''}{priceChangePct.toFixed(2)}%
                            </div>
                          </div>
                        </div>

                        <div className="mb-3">
                          <div className="flex items-center justify-between text-[8px] text-slate-500 mb-1">
                            <span>下限 ${g.lower > 1 ? g.lower.toFixed(2) : g.lower.toFixed(6)}</span>
                            <span className="text-[9px] text-slate-400 font-bold">价格在区间 {Math.min(Math.max(posInRange, 0), 100).toFixed(0)}%</span>
                            <span>上限 ${g.upper > 1 ? g.upper.toFixed(2) : g.upper.toFixed(6)}</span>
                          </div>
                          <div className="h-2 bg-slate-800 rounded-full relative overflow-hidden">
                            <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/20 via-blue-500/20 to-cyan-500/20 rounded-full" />
                            <div className="absolute top-0 h-full w-1.5 bg-white rounded-full shadow-lg shadow-white/30 transition-all"
                              style={{ left: `${Math.min(Math.max(posInRange, 0), 100)}%`, transform: 'translateX(-50%)' }} />
                          </div>
                          {g.sl_price > 0 && (
                            <div className="text-[8px] text-red-400/60 mt-1">止损: ${g.sl_price > 1 ? g.sl_price.toFixed(2) : g.sl_price.toFixed(6)}</div>
                          )}
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50 text-center">
                            <div className="text-[8px] text-slate-500 font-bold">投入资金</div>
                            <div className="text-sm font-black text-cyan-400 tabular-nums mt-0.5">${g.capital_used.toFixed(0)}</div>
                          </div>
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50 text-center">
                            <div className="text-[8px] text-slate-500 font-bold">订单成交</div>
                            <div className="text-sm font-black text-white tabular-nums mt-0.5">
                              {g.filled_orders}<span className="text-slate-600 text-[10px]">/{g.total_orders}</span>
                            </div>
                            <div className="text-[7px] text-slate-600">待执行 {g.pending_orders}</div>
                          </div>
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50 text-center">
                            <div className="text-[8px] text-slate-500 font-bold">买/卖成交</div>
                            <div className="text-sm tabular-nums mt-0.5">
                              <span className="text-cyan-400 font-black">{g.buys_filled}</span>
                              <span className="text-slate-600 mx-1">/</span>
                              <span className="text-amber-400 font-black">{g.sells_filled}</span>
                            </div>
                            <div className="text-[7px] text-slate-600">买入/卖出</div>
                          </div>
                          <div className="bg-slate-950/60 rounded-lg p-2 border border-slate-800/50 text-center">
                            <div className="text-[8px] text-slate-500 font-bold">总盈亏</div>
                            <div className={`text-sm font-black tabular-nums mt-0.5 ${pnlColor(g.pnl)}`}>
                              {g.pnl >= 0 ? '+' : ''}${(g.pnl || 0).toFixed(2)}
                            </div>
                            <div className="text-[7px] tabular-nums text-slate-500">
                              格利 <span className={pnlColor(g.realized_pnl)}>{g.realized_pnl >= 0 ? '+' : ''}{g.realized_pnl.toFixed(1)}</span>
                              {' '}浮动 <span className={pnlColor(g.inventory_pnl)}>{g.inventory_pnl >= 0 ? '+' : ''}{g.inventory_pnl.toFixed(1)}</span>
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 mt-3 text-[9px] text-slate-500 flex-wrap">
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {g.created || '--'}</span>
                          <span>策略: {g.boundary_source === 'monte_carlo' ? 'MC蒙特卡洛预测' : g.boundary_source === 'atr_fallback' ? 'ATR波动率回退' : safe(g.boundary_source)}</span>
                          <span>格数: {g.levels}</span>
                          {g.last_update && <span>更新: {g.last_update.split(' ')[1] || g.last_update}</span>}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {gridSubTab === 'closed' && (
            <div className="space-y-3">
              {gridHistory.length === 0 && gridTotalTrades === 0 ? (
                <div className="shield-glass rounded-2xl p-8 border border-slate-800">
                  <EmptyState icon={Archive} title="暂无已关闭网格" subtitle="网格关闭后记录会显示在这里" />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
                      <div className="text-[9px] text-slate-500 font-black uppercase">总已关闭</div>
                      <div className="text-xl font-black text-white tabular-nums mt-1">{gridTotalTrades}</div>
                    </div>
                    <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
                      <div className="text-[9px] text-slate-500 font-black uppercase">胜率</div>
                      <div className={`text-xl font-black tabular-nums mt-1 ${gridWinRate >= 50 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {gridWinRate.toFixed(0)}%
                      </div>
                    </div>
                    <div className="shield-glass rounded-xl p-3 border border-slate-800 text-center">
                      <div className="text-[9px] text-slate-500 font-black uppercase">累计盈亏</div>
                      <div className={`text-xl font-black tabular-nums mt-1 ${pnlColor(gridRealizedPnl)}`}>
                        {gridRealizedPnl >= 0 ? '+' : ''}${gridRealizedPnl.toFixed(2)}
                      </div>
                    </div>
                  </div>

                  {gridHistory.length > 0 ? (
                    <div className="space-y-2">
                      {gridHistory.slice().reverse().map((h, i) => {
                        const isWin = (h.pnl || 0) > 0;
                        const reasonMap = {
                          sl_hit: '止损触发', out_of_range_upper: '突破上沿',
                          out_of_range_lower: '跌破下沿', all_filled: '全部成交',
                          manual_close: '手动关闭', manual: '手动关闭'
                        };
                        return (
                          <div key={i} className="shield-glass rounded-xl border border-slate-700/50 p-4">
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-black text-white">{safe(h.symbol)}</span>
                                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-lg ${isWin ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/15 text-red-400 border border-red-500/20'}`}>
                                  {isWin ? '盈利' : '亏损'}
                                </span>
                                <span className="text-[8px] text-slate-500 px-1.5 py-0.5 bg-slate-800/60 rounded border border-slate-700/50">
                                  {reasonMap[h.reason] || h.reason || '未知'}
                                </span>
                                <span className="text-[8px] text-slate-600 px-1.5 py-0.5 bg-slate-800/40 rounded">
                                  {h.spacing_mode === 'geometric' ? '等比网格' : '等差网格'}
                                </span>
                              </div>
                              <div className="text-right shrink-0">
                                <div className={`text-sm font-black tabular-nums ${pnlColor(h.pnl)}`}>
                                  {(h.pnl || 0) >= 0 ? '+' : ''}${(h.pnl || 0).toFixed(2)}
                                </div>
                                {h.pnl_pct != null && (
                                  <div className={`text-[9px] tabular-nums ${pnlColor(h.pnl_pct)}`}>
                                    {h.pnl_pct >= 0 ? '+' : ''}{h.pnl_pct.toFixed(2)}%
                                  </div>
                                )}
                              </div>
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[10px]">
                              {h.capital > 0 && (
                                <div>
                                  <span className="text-slate-500">投入</span>
                                  <span className="text-slate-300 font-bold ml-1 tabular-nums">${h.capital.toFixed(0)}</span>
                                </div>
                              )}
                              {h.entry_price > 0 && (
                                <div>
                                  <span className="text-slate-500">入场</span>
                                  <span className="text-slate-300 font-bold ml-1 tabular-nums">${h.entry_price > 1 ? h.entry_price.toFixed(2) : h.entry_price.toFixed(6)}</span>
                                </div>
                              )}
                              {h.close_price > 0 && (
                                <div>
                                  <span className="text-slate-500">收盘</span>
                                  <span className="text-slate-300 font-bold ml-1 tabular-nums">${h.close_price > 1 ? h.close_price.toFixed(2) : h.close_price.toFixed(6)}</span>
                                </div>
                              )}
                              <div>
                                <span className="text-slate-500">成交</span>
                                <span className="text-cyan-400 font-bold ml-1">买{h.buys_filled || 0}</span>
                                <span className="text-slate-600 mx-0.5">/</span>
                                <span className="text-amber-400 font-bold">卖{h.sells_filled || 0}</span>
                              </div>
                              {h.grids > 0 && (
                                <div>
                                  <span className="text-slate-500">格数</span>
                                  <span className="text-slate-300 font-bold ml-1">{h.grids}</span>
                                </div>
                              )}
                              {h.total_orders > 0 && (
                                <div>
                                  <span className="text-slate-500">订单</span>
                                  <span className="text-slate-300 font-bold ml-1">{h.filled_orders || 0}/{h.total_orders}</span>
                                </div>
                              )}
                            </div>

                            <div className="flex items-center gap-3 mt-2 text-[8px] text-slate-600 flex-wrap">
                              {h.created_at && <span>建仓: {h.created_at}</span>}
                              {h.closed_at && <span>关闭: {h.closed_at}</span>}
                              {h.boundary_source && <span>策略: {h.boundary_source === 'monte_carlo' ? 'MC预测' : 'ATR回退'}</span>}
                              {h.trailing_enabled && <span className="text-amber-400">追踪模式 ×{h.trailing_shifts || 0}</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="shield-glass rounded-xl p-4 border border-slate-800">
                      <div className="flex items-start gap-2 text-[9px] text-amber-400/80">
                        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                        <span>已有 {gridTotalTrades} 笔已关闭网格记录（累计盈亏 ${gridRealizedPnl.toFixed(2)}），但详细历史记录在系统重启前已丢失。新关闭的网格将正常显示在这里。</span>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'history' && (
        <div className="shield-glass shield-glass-hover rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[10px] font-black text-amber-500 uppercase tracking-widest flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" /> 交易历史
            </h3>
            {paperTrades.length > 0 && (
              <div className="flex items-center gap-3 text-[9px]">
                <span className="text-emerald-400 font-bold">{paperTrades.filter(t => (parseFloat(t.pnl_pct) || 0) > 0 || t.result === '盈利').length}W</span>
                <span className="text-red-400 font-bold">{paperTrades.filter(t => (parseFloat(t.pnl_pct) || 0) <= 0 && t.result !== '盈利').length}L</span>
              </div>
            )}
          </div>

          {paperTrades.length === 0 ? (
            <EmptyState icon={Clock} title="暂无交易记录" subtitle="系统完成交易后将在此显示" />
          ) : (
            <>
              <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-500 font-black uppercase">
                      <th className="text-left py-2 px-2">资产</th>
                      <th className="text-left py-2 px-2">方向</th>
                      <th className="text-right py-2 px-2">入场价</th>
                      <th className="text-right py-2 px-2">出场价</th>
                      <th className="text-right py-2 px-2">盈亏%</th>
                      <th className="text-center py-2 px-2">结果</th>
                      <th className="text-center py-2 px-2">策略</th>
                      <th className="text-center py-2 px-2">AI评分</th>
                      <th className="text-center py-2 px-2">ML</th>
                      <th className="text-center py-2 px-2">持仓</th>
                      <th className="text-right py-2 px-2">时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paperTrades.map((t, i) => {
                      const tPnl = parseFloat(t.pnl_pct) || 0;
                      const isWin = tPnl > 0 || t.result === '盈利';
                      const isLong = (t.direction || '').toLowerCase() === 'long';
                      const stratMap = { trend: '趋势跟踪', grid: '网格交易', range: '区间收割', reversal: '反转', breakout: '突破' };
                      const strat = t.strategy_type || t.strategy || '';
                      const stratLabel = stratMap[strat] || strat || '--';
                      const stratColor = strat === 'trend' ? 'text-cyan-400 bg-cyan-500/10' : strat === 'grid' ? 'text-violet-400 bg-violet-500/10' : 'text-slate-400 bg-slate-500/10';
                      const score = t.signal_score || t.ai_score;
                      const verdict = t.ai_verdict;
                      const verdictMap = { approve: '通过', reject: '拒绝', reduce: '缩仓' };
                      const verdictLabel = verdict ? (verdictMap[verdict] || verdict) : '';
                      const scoreColor = score >= 75 ? 'text-emerald-400' : score >= 65 ? 'text-amber-400' : score ? 'text-red-400' : 'text-slate-600';
                      return (
                        <tr key={t.id || i} className="border-b border-slate-800/40 hover:bg-slate-800/20 transition-colors">
                          <td className="py-2.5 px-2 font-black text-white">{safe(t.symbol)}</td>
                          <td className="py-2.5 px-2">
                            <span className={`font-bold px-1.5 py-0.5 rounded ${isLong ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                              {isLong ? '做多' : '做空'}
                            </span>
                          </td>
                          <td className="py-2.5 px-2 text-right text-slate-400 font-mono tabular-nums">${safe(t.entry_price)}</td>
                          <td className="py-2.5 px-2 text-right text-slate-400 font-mono tabular-nums">${safe(t.exit_price)}</td>
                          <td className={`py-2.5 px-2 text-right font-bold tabular-nums ${pnlColor(tPnl)}`}>
                            {tPnl >= 0 ? '+' : ''}{tPnl.toFixed(2)}%
                          </td>
                          <td className="py-2.5 px-2 text-center">
                            <span className={`font-bold px-2 py-0.5 rounded-lg ${isWin ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                              {isWin ? '盈利' : '亏损'}
                            </span>
                          </td>
                          <td className="py-2.5 px-2 text-center">
                            <span className={`font-bold px-1.5 py-0.5 rounded text-[9px] ${stratColor}`}>{stratLabel}</span>
                          </td>
                          <td className="py-2.5 px-2 text-center">
                            <div className="flex flex-col items-center gap-0.5">
                              {score != null && <span className={`font-mono font-bold ${scoreColor}`}>{score}</span>}
                              {verdictLabel && <span className="text-[8px] text-slate-500">{verdictLabel}</span>}
                            </div>
                          </td>
                          <td className="py-2.5 px-2 text-center">
                            <span className={`font-mono font-bold text-[10px] ${(t.ml_confidence || 0) >= 85 ? 'text-red-500' : (t.ml_confidence || 0) >= 70 ? 'text-orange-400' : (t.ml_confidence || 0) >= 55 ? 'text-yellow-400' : 'text-green-400'}`} title="ML置信度越高风险越大（实战验证反指）">
                              {t.ml_confidence != null ? Math.round(t.ml_confidence) : '--'}
                            </span>
                          </td>
                          <td className="py-2.5 px-2 text-center text-[10px] text-slate-400 tabular-nums">
                            {t.hold_hours != null ? `${t.hold_hours}h` : '--'}
                          </td>
                          <td className="py-2.5 px-2 text-right text-slate-600 font-mono tabular-nums">{safe(t.close_time)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="md:hidden space-y-2 max-h-[60vh] overflow-y-auto">
                {paperTrades.map((t, i) => {
                  const tPnl = parseFloat(t.pnl_pct) || 0;
                  const isWin = tPnl > 0 || t.result === '盈利';
                  const isLong = (t.direction || '').toLowerCase() === 'long';
                  const stratMap = { trend: '趋势跟踪', grid: '网格交易', range: '区间收割', reversal: '反转', breakout: '突破' };
                  const strat = t.strategy_type || t.strategy || '';
                  const stratLabel = stratMap[strat] || strat || '--';
                  const stratColor = strat === 'trend' ? 'text-cyan-400 bg-cyan-500/10' : strat === 'grid' ? 'text-violet-400 bg-violet-500/10' : 'text-slate-400 bg-slate-500/10';
                  const score = t.signal_score || t.ai_score;
                  const verdict = t.ai_verdict;
                  const verdictMap = { approve: '通过', reject: '拒绝', reduce: '缩仓' };
                  const verdictLabel = verdict ? (verdictMap[verdict] || verdict) : '';
                  return (
                    <div key={t.id || i} className="bg-slate-950/60 border border-slate-800/50 rounded-xl p-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-black text-white text-xs">{safe(t.symbol)}</span>
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${isLong ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                            {isLong ? '做多' : '做空'}
                          </span>
                          <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${stratColor}`}>{stratLabel}</span>
                        </div>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-lg ${isWin ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                          {isWin ? '盈利' : '亏损'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-slate-500 tabular-nums">${safe(t.entry_price)} → ${safe(t.exit_price)}</span>
                        <span className={`font-bold tabular-nums ${pnlColor(tPnl)}`}>{tPnl >= 0 ? '+' : ''}{tPnl.toFixed(2)}%</span>
                      </div>
                      <div className="flex items-center justify-between text-[9px] mt-1">
                        <div className="flex items-center gap-2">
                          {score != null && <span className={`font-mono font-bold ${score >= 75 ? 'text-emerald-400' : score >= 65 ? 'text-amber-400' : 'text-red-400'}`}>AI:{score}</span>}
                          {verdictLabel && <span className="text-slate-500">{verdictLabel}</span>}
                        </div>
                        {t.ml_confidence != null && (
                          <span className={`text-[8px] font-bold ${(t.ml_confidence || 0) >= 85 ? 'text-red-500' : (t.ml_confidence || 0) >= 70 ? 'text-orange-400' : (t.ml_confidence || 0) >= 55 ? 'text-yellow-400' : 'text-green-400'}`} title="ML置信度越高风险越大">
                            ML:{Math.round(t.ml_confidence)}
                          </span>
                        )}
                        {t.hold_hours != null && (
                          <span className="text-[8px] text-slate-500">{t.hold_hours}h</span>
                        )}
                        <span className="font-mono tabular-nums text-slate-600">{safe(t.close_time)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}

      <div className="shield-glass rounded-2xl overflow-hidden">
        <button
          onClick={() => setRiskOpen(!riskOpen)}
          className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-800/20 transition-all"
        >
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-amber-500" />
            <span className="text-[11px] font-black text-amber-500 uppercase tracking-widest">风控仪表盘</span>
            {constitutionStatus && (() => {
              const isDead = constitutionStatus.drawdown_breaker_triggered === true;
              const isPaused = constitutionStatus.daily_pause_active === true;
              const st = isDead ? 'danger' : isPaused ? 'warning' : 'healthy';
              return (
                <span className={`text-[9px] px-2 py-0.5 rounded-lg font-bold inline-flex items-center gap-1 ${
                  st === 'danger' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                  st === 'warning' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                  'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                }`}>
                  <StatusDot status={st} pulse={false} />
                  {isDead ? '熔断' : isPaused ? '暂停' : '健康'}
                </span>
              );
            })()}
          </div>
          {riskOpen ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </button>

        {riskOpen && (
          <div className="px-4 pb-4 space-y-4 border-t border-slate-800/50">
            <div className="pt-4">
              <div className="flex items-center justify-between text-[10px] mb-2">
                <span className="text-slate-500 font-bold">宪法状态</span>
                <span className={`font-bold ${
                  constitutionStatus?.status === 'DEAD' ? 'text-red-400' :
                  constitutionStatus?.daily_pause_active ? 'text-amber-400' : 'text-emerald-400'
                }`}>
                  {constitutionStatus?.status === 'DEAD' ? '永久熔断' :
                   constitutionStatus?.daily_pause_active ? '日内暂停' :
                   constitutionStatus?.drawdown_breaker_triggered ? '回撤熔断' : '运行正常'}
                </span>
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between text-[10px] mb-1.5">
                <span className="text-slate-500 font-bold">当前回撤</span>
                <span className={`font-bold tabular-nums ${currentDrawdown > maxAllowedDrawdown * 0.8 ? 'text-red-400' : 'text-slate-300'}`}>
                  {currentDrawdown.toFixed(2)}% / {maxAllowedDrawdown.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 bg-slate-800 rounded-full overflow-hidden relative">
                <div
                  className={`h-full rounded-full transition-all ${
                    currentDrawdown > maxAllowedDrawdown * 0.8 ? 'bg-red-500' :
                    currentDrawdown > maxAllowedDrawdown * 0.5 ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${Math.min((currentDrawdown / maxAllowedDrawdown) * 100, 100)}%` }}
                />
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-red-400"
                  style={{ left: `${Math.min((maxAllowedDrawdown / (maxAllowedDrawdown + 5)) * 100, 95)}%` }}
                  title={`最大允许: ${maxAllowedDrawdown}%`}
                />
              </div>
            </div>

            {constitutionStatus?.drawdown_gradient && (
              <div className="flex items-center justify-between text-[10px] mt-1">
                <span className="text-slate-500 font-bold">仓位梯度</span>
                <div className="flex items-center gap-2">
                  <span className={`font-bold tabular-nums ${
                    constitutionStatus.drawdown_gradient.size_multiplier >= 1.0 ? 'text-emerald-400' :
                    constitutionStatus.drawdown_gradient.size_multiplier >= 0.6 ? 'text-amber-400' :
                    constitutionStatus.drawdown_gradient.size_multiplier > 0 ? 'text-orange-400' : 'text-red-400'
                  }`}>
                    {constitutionStatus.drawdown_gradient.size_multiplier >= 1.0 ? '100%' :
                     constitutionStatus.drawdown_gradient.size_multiplier > 0 ? `${(constitutionStatus.drawdown_gradient.size_multiplier * 100).toFixed(0)}%` : '冻结'}
                  </span>
                  <span className="text-[8px] text-slate-600">
                    {constitutionStatus.drawdown_gradient.level === 'normal' ? '正常' : '收缩'}
                  </span>
                </div>
              </div>
            )}

            <div>
              <div className="flex items-center justify-between text-[10px] mb-1.5">
                <span className="text-slate-500 font-bold">资金利用率</span>
                <span className="text-slate-300 font-bold tabular-nums">
                  {paperPositions.length > 0 ? `${paperPositions.length} 持仓` : '空仓'}
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-[9px]">
                <div className="bg-slate-950/60 rounded-lg p-2 text-center">
                  <div className="text-slate-500">连胜</div>
                  <div className="text-emerald-400 font-bold tabular-nums">{safe(paperPortfolio?.consecutive_wins)}</div>
                </div>
                <div className="bg-slate-950/60 rounded-lg p-2 text-center">
                  <div className="text-slate-500">连败</div>
                  <div className="text-red-400 font-bold tabular-nums">{safe(paperPortfolio?.consecutive_losses)}</div>
                </div>
                <div className="bg-slate-950/60 rounded-lg p-2 text-center">
                  <div className="text-slate-500">总交易</div>
                  <div className="text-slate-300 font-bold tabular-nums">{winCount + lossCount}</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
