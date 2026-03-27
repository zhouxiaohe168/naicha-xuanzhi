import React, { useState, useCallback } from 'react';
import { Grid3x3, Zap, AlertTriangle, CheckCircle, Settings, TrendingUp, DollarSign, Loader2, ChevronDown, ChevronUp } from 'lucide-react';

const API = '/api';

const suitColors = {
  suitable: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  moderate: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
  poor: 'text-red-400 bg-red-500/10 border-red-500/30',
};

const suitLabels = {
  suitable: '适合网格',
  moderate: '条件一般',
  poor: '不推荐',
};

const GridWorkshop = ({ symbols = [] }) => {
  const [symbol, setSymbol] = useState('');
  const [budget, setBudget] = useState(500);
  const [gridCount, setGridCount] = useState(10);
  const [rangePct, setRangePct] = useState(0);
  const [loading, setLoading] = useState(false);
  const [deploying, setDeploying] = useState(false);
  const [result, setResult] = useState(null);
  const [showGrids, setShowGrids] = useState(false);
  const [activeGrids, setActiveGrids] = useState(null);
  const [error, setError] = useState('');

  const analyze = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API}/grid/workshop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, budget, grid_count: gridCount, range_pct: rangePct }),
      });
      const data = await resp.json();
      if (data.status === 'ok') {
        setResult(data);
      } else {
        setError(data.message || '分析失败');
      }
    } catch (e) {
      setError('网络错误');
    }
    setLoading(false);
  }, [symbol, budget, gridCount, rangePct]);

  const deploy = useCallback(async () => {
    if (!symbol) return;
    setDeploying(true);
    setError('');
    try {
      const resp = await fetch(`${API}/grid/workshop/deploy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, budget, grid_count: gridCount, range_pct: rangePct }),
      });
      const data = await resp.json();
      if (data.status === 'ok') {
        setError('');
        loadActive();
      } else {
        setError(data.message || '部署失败');
      }
    } catch (e) {
      setError('网络错误');
    }
    setDeploying(false);
  }, [symbol, budget, gridCount, rangePct]);

  const loadActive = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/grid`);
      const data = await resp.json();
      setActiveGrids(data);
    } catch (e) {}
  }, []);

  const closeGrid = useCallback(async (sym) => {
    try {
      const resp = await fetch(`${API}/grid/close/${sym}`, { method: 'POST' });
      const data = await resp.json();
      if (data.status === 'ok') {
        loadActive();
      }
    } catch (e) {}
  }, []);

  React.useEffect(() => { loadActive(); }, []);

  const inputClass = "w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-white focus:border-blue-500 focus:outline-none transition-colors";

  return (
    <div className="space-y-4">
      <div className="shield-glass border border-slate-700 rounded-2xl p-4">
        <h3 className="text-base font-black flex items-center gap-2 mb-3">
          <Grid3x3 className="w-5 h-5 text-blue-400" />
          网格工坊
          <span className="text-[10px] text-slate-500 font-normal">智能区间网格配置器</span>
        </h3>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          <div>
            <label className="text-[10px] text-slate-500 font-bold mb-1 block">币种</label>
            <select value={symbol} onChange={e => setSymbol(e.target.value)} className={inputClass}>
              <option value="">选择币种</option>
              {symbols.map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-slate-500 font-bold mb-1 block">预算 ($)</label>
            <input type="number" value={budget} onChange={e => setBudget(parseFloat(e.target.value) || 0)} className={inputClass} />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 font-bold mb-1 block">网格数量</label>
            <input type="number" value={gridCount} min={3} max={50}
              onChange={e => setGridCount(parseInt(e.target.value) || 10)} className={inputClass} />
          </div>
          <div>
            <label className="text-[10px] text-slate-500 font-bold mb-1 block">
              范围% <span className="text-slate-600">(0=自动)</span>
            </label>
            <input type="number" value={rangePct} step={0.5} min={0} max={30}
              onChange={e => setRangePct(parseFloat(e.target.value) || 0)} className={inputClass} />
          </div>
        </div>

        <button onClick={analyze} disabled={!symbol || loading}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white font-bold text-sm py-2.5 rounded-xl transition-all flex items-center justify-center gap-2">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Settings className="w-4 h-4" />}
          {loading ? '分析中...' : '分析网格方案'}
        </button>

        {error && (
          <div className="mt-2 text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
      </div>

      {result && (
        <div className="shield-glass border border-slate-700 rounded-2xl p-4 space-y-3">
          <div className="flex justify-between items-start">
            <div>
              <h4 className="font-black text-base">{result.symbol} 网格方案</h4>
              <div className="text-[10px] text-slate-500">当前价: ${result.price}</div>
            </div>
            <div className={`px-3 py-1 rounded-full border text-xs font-bold ${suitColors[result.suitability]}`}>
              {result.suitability === 'suitable' && <CheckCircle className="w-3 h-3 inline mr-1" />}
              {result.suitability === 'moderate' && <AlertTriangle className="w-3 h-3 inline mr-1" />}
              {result.suitability === 'poor' && <AlertTriangle className="w-3 h-3 inline mr-1" />}
              {suitLabels[result.suitability]}
            </div>
          </div>

          {result.suitability_reasons?.map((r, i) => (
            <div key={i} className="text-[10px] text-slate-400">{r}</div>
          ))}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              { label: '价格区间', value: `$${result.lower.toFixed(2)} - $${result.upper.toFixed(2)}`, sub: `±${result.range_pct}%` },
              { label: '每格间距', value: `$${result.step_price.toFixed(4)}`, sub: `${result.step_pct}%` },
              { label: '单格利润', value: `${result.profit_per_grid_pct.toFixed(3)}%` },
              { label: '潜在总利润', value: `${result.total_profit_potential_pct.toFixed(2)}%` },
            ].map((item, i) => (
              <div key={i} className="bg-slate-950 rounded-lg p-2 text-center">
                <div className="text-[8px] text-slate-600">{item.label}</div>
                <div className="text-sm font-black text-white">{item.value}</div>
                {item.sub && <div className="text-[8px] text-slate-500">{item.sub}</div>}
              </div>
            ))}
          </div>

          <div className="grid grid-cols-4 gap-2">
            <div className="bg-slate-950 rounded-lg p-2 text-center">
              <div className="text-[8px] text-slate-600">买入格</div>
              <div className="text-sm font-black text-emerald-400">{result.buy_count}</div>
            </div>
            <div className="bg-slate-950 rounded-lg p-2 text-center">
              <div className="text-[8px] text-slate-600">卖出格</div>
              <div className="text-sm font-black text-red-400">{result.sell_count}</div>
            </div>
            <div className="bg-slate-950 rounded-lg p-2 text-center">
              <div className="text-[8px] text-slate-600">ADX</div>
              <div className="text-sm font-black">{result.market_info?.adx}</div>
            </div>
            <div className="bg-slate-950 rounded-lg p-2 text-center">
              <div className="text-[8px] text-slate-600">波动率</div>
              <div className="text-sm font-black">{result.market_info?.atr_pct}%</div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-700 bg-slate-950 overflow-hidden">
            <button onClick={() => setShowGrids(!showGrids)}
              className="w-full p-2 flex items-center justify-between text-[10px] text-blue-400 font-bold hover:bg-slate-800/50">
              <span>网格明细 ({result.grids?.length || 0}格)</span>
              {showGrids ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            {showGrids && (
              <div className="px-2.5 pb-2.5 max-h-60 overflow-y-auto">
                <table className="w-full text-[10px]">
                  <thead>
                    <tr className="text-slate-500">
                      <th className="text-left py-1">#</th>
                      <th className="text-right">价格</th>
                      <th className="text-center">方向</th>
                      <th className="text-right">距离</th>
                      <th className="text-right">金额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.grids?.map((g, i) => (
                      <tr key={i} className="border-t border-slate-800">
                        <td className="py-1 text-slate-500">{g.level}</td>
                        <td className="text-right font-mono text-white">${g.price.toFixed(4)}</td>
                        <td className={`text-center font-bold ${g.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}`}>
                          {g.side === 'buy' ? '买' : '卖'}
                        </td>
                        <td className={`text-right font-mono ${g.distance_pct < 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                          {g.distance_pct > 0 ? '+' : ''}{g.distance_pct}%
                        </td>
                        <td className="text-right font-mono text-slate-400">${g.amount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <button onClick={deploy} disabled={deploying || result.suitability === 'poor'}
            className={`w-full font-black text-sm py-3 rounded-xl transition-all flex items-center justify-center gap-2 ${
              result.suitability === 'poor'
                ? 'bg-red-500/20 text-red-400 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white'
            }`}>
            {deploying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            {deploying ? '部署中...' : result.suitability === 'poor' ? '环境不适合网格' : `部署网格 $${budget}`}
          </button>
        </div>
      )}

      {activeGrids && (
        <div className="shield-glass border border-slate-700 rounded-2xl p-4">
          <h4 className="text-sm font-black flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            活跃网格
            <span className="text-[10px] text-slate-500 font-normal">
              {Object.keys(activeGrids.active_grids || {}).length}个运行中
            </span>
          </h4>
          {Object.entries(activeGrids.active_grids || {}).length === 0 ? (
            <div className="text-center text-sm text-slate-500 py-4">暂无活跃网格</div>
          ) : (
            <div className="space-y-2">
              {Object.entries(activeGrids.active_grids || {}).map(([sym, grid]) => (
                <div key={sym} className="bg-slate-950 rounded-lg p-3 flex items-center justify-between">
                  <div>
                    <span className="text-sm font-bold text-white">{sym}</span>
                    <div className="text-[10px] text-slate-500">
                      ${(grid.lower_bound || 0).toFixed(2)} - ${(grid.upper_bound || 0).toFixed(2)}
                      · {grid.grid_count || 0}格
                      · PnL: <span className={`font-bold ${(grid.grid_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        ${(grid.grid_pnl || 0).toFixed(2)}
                      </span>
                    </div>
                  </div>
                  <button onClick={() => closeGrid(sym)}
                    className="text-[10px] text-red-400 hover:text-red-300 bg-red-500/10 px-2 py-1 rounded">
                    关闭
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default GridWorkshop;
