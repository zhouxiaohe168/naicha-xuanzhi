import { useState, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, Search, ArrowUpDown,
  BarChart3, Layers, Coins, Filter
} from 'lucide-react';
import { useShield } from '../hooks/useShieldData';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const fmtPrice = (p) => {
  if (p == null) return '--';
  const n = parseFloat(p);
  if (n >= 1000) return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (n >= 1) return n.toFixed(4);
  if (n >= 0.001) return n.toFixed(6);
  return n.toFixed(8);
};

const fmtVol = (v) => {
  if (v == null) return '--';
  const n = parseFloat(v);
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toFixed(0);
};

const fmtPct = (v) => {
  if (v == null) return '--';
  const n = parseFloat(v);
  return (n >= 0 ? '+' : '') + n.toFixed(2) + '%';
};

const SECTORS = {
  all: '全部',
  major: '主流',
  defi: 'DeFi',
  layer1: 'Layer1',
  layer2: 'Layer2',
  ai: 'AI',
  meme: 'Meme',
  gamefi: 'GameFi',
};

const SECTOR_MAP = {
  BTC: 'major', ETH: 'major', BNB: 'major', SOL: 'major', XRP: 'major',
  ADA: 'major', DOGE: 'major', DOT: 'major', AVAX: 'major', LINK: 'major',
  TRX: 'major', LTC: 'major', BCH: 'major', NEAR: 'major', ETC: 'major',
  UNI: 'defi', AAVE: 'defi', SUSHI: 'defi', CRV: 'defi', COMP: 'defi',
  SNX: 'defi', '1INCH': 'defi', DYDX: 'defi', CAKE: 'defi', LDO: 'defi',
  PENDLE: 'defi', JUP: 'defi',
  MATIC: 'layer2', POL: 'layer2', ARB: 'layer2', OP: 'layer2', IMX: 'layer2',
  STRK: 'layer2', METIS: 'layer2', MANTA: 'layer2', ZK: 'layer2',
  ATOM: 'layer1', FTM: 'layer1', ALGO: 'layer1', HBAR: 'layer1',
  ICP: 'layer1', FIL: 'layer1', APT: 'layer1', SUI: 'layer1', SEI: 'layer1',
  INJ: 'layer1', TIA: 'layer1', TON: 'layer1',
  FET: 'ai', RNDR: 'ai', AGIX: 'ai', WLD: 'ai', TAO: 'ai', AR: 'ai',
  RENDER: 'ai', AKT: 'ai', OCEAN: 'ai',
  SHIB: 'meme', PEPE: 'meme', FLOKI: 'meme', BONK: 'meme', WIF: 'meme',
  PEOPLE: 'meme', NEIRO: 'meme', TURBO: 'meme', BRETT: 'meme',
  AXS: 'gamefi', SAND: 'gamefi', MANA: 'gamefi', GALA: 'gamefi',
  ENJ: 'gamefi', PIXEL: 'gamefi',
};

export default function MarketDashboard() {
  const { data, coinglassData, externalData } = useShield();
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState('volume');
  const [sortDir, setSortDir] = useState('desc');
  const [sector, setSector] = useState('all');
  const [viewMode, setViewMode] = useState('spot');

  const cruise = data?.cruise || [];
  const cg = coinglassData || externalData?.coinglass;

  const enrichedData = useMemo(() => {
    return cruise.map(item => {
      const sym = item.symbol?.replace('/USDT', '').replace('_USDT', '') || '';
      const daily = item.daily || {};
      const change24h = item.change_24h ?? daily.change_pct ?? daily.pct_change ?? 0;
      const volume = item.volume_24h ?? daily.volume_usdt ?? daily.quote_volume ?? 0;
      const fundingRate = item.funding_rate;
      const oi = item.open_interest;
      const sectorTag = SECTOR_MAP[sym] || 'other';
      const direction = daily.direction || '';
      const rsi = daily.rsi;

      return {
        symbol: sym,
        price: item.price,
        change24h,
        volume,
        score: item.score,
        strategy: item.strategy,
        fundingRate,
        oi,
        sector: sectorTag,
        regime: item.regime,
        ml: item.ml,
        direction,
        rsi,
      };
    });
  }, [cruise]);

  const filtered = useMemo(() => {
    let result = enrichedData;
    if (search) {
      const q = search.toUpperCase();
      result = result.filter(r => r.symbol.includes(q));
    }
    if (sector !== 'all') {
      result = result.filter(r => r.sector === sector);
    }
    result.sort((a, b) => {
      const av = a[sortKey] ?? 0;
      const bv = b[sortKey] ?? 0;
      return sortDir === 'desc' ? bv - av : av - bv;
    });
    return result;
  }, [enrichedData, search, sortKey, sortDir, sector]);

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const SortHeader = ({ label, field, className = '' }) => (
    <button
      onClick={() => toggleSort(field)}
      className={`flex items-center gap-0.5 text-[8px] font-black uppercase ${
        sortKey === field ? 'text-amber-400' : 'text-slate-500'
      } ${className}`}
    >
      {label}
      {sortKey === field && (
        <ArrowUpDown className="w-2.5 h-2.5" />
      )}
    </button>
  );

  const sectorCounts = useMemo(() => {
    const counts = { all: enrichedData.length };
    enrichedData.forEach(r => {
      counts[r.sector] = (counts[r.sector] || 0) + 1;
    });
    return counts;
  }, [enrichedData]);

  const stats = useMemo(() => {
    const up = enrichedData.filter(r => (r.change24h || 0) > 0).length;
    const down = enrichedData.filter(r => (r.change24h || 0) < 0).length;
    const totalVol = enrichedData.reduce((s, r) => s + (r.volume || 0), 0);
    const avgChange = enrichedData.length > 0
      ? enrichedData.reduce((s, r) => s + (r.change24h || 0), 0) / enrichedData.length
      : 0;
    return { up, down, totalVol, avgChange };
  }, [enrichedData]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <Coins className="w-5 h-5 text-amber-400" />
        <h2 className="text-lg font-black text-white">全局看板</h2>
        <span className="text-[9px] text-slate-600 font-bold">{enrichedData.length} 标的实时监控</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black">上涨/下跌</div>
          <div className="text-sm font-black">
            <span className="text-emerald-400">{stats.up}</span>
            <span className="text-slate-600 mx-1">/</span>
            <span className="text-red-400">{stats.down}</span>
          </div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black">平均涨跌</div>
          <div className={`text-sm font-black ${stats.avgChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {fmtPct(stats.avgChange)}
          </div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black">总成交额</div>
          <div className="text-sm font-black text-cyan-400">${fmtVol(stats.totalVol)}</div>
        </div>
        <div className="shield-glass rounded-xl p-3 text-center">
          <div className="text-[9px] text-slate-500 font-black">BTC资金费</div>
          <div className={`text-sm font-black ${(cg?.btc_funding_rate || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {cg?.btc_funding_rate != null ? (cg.btc_funding_rate * 100).toFixed(4) + '%' : '--'}
          </div>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 items-start sm:items-center">
        <div className="relative flex-1 w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="搜索币种..."
            className="w-full pl-8 pr-3 py-2 bg-slate-950/60 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-600 focus:outline-none focus:border-amber-500/50"
          />
        </div>
        <div className="flex gap-1 overflow-x-auto scrollbar-hide">
          {Object.entries(SECTORS).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setSector(key)}
              className={`px-2.5 py-1.5 rounded-lg text-[9px] font-bold whitespace-nowrap transition-all ${
                sector === key
                  ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                  : 'text-slate-500 hover:text-slate-300 border border-transparent'
              }`}
            >
              {label} {sectorCounts[key] ? `(${sectorCounts[key]})` : ''}
            </button>
          ))}
        </div>
      </div>

      <div className="shield-glass rounded-2xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-800/50">
                <th className="text-left px-3 py-2.5 text-[8px] text-slate-500 font-black uppercase w-8">#</th>
                <th className="text-left px-3 py-2.5 text-[8px] text-slate-500 font-black uppercase">币种</th>
                <th className="text-right px-3 py-2.5"><SortHeader label="价格" field="price" /></th>
                <th className="text-right px-3 py-2.5"><SortHeader label="24H涨跌" field="change24h" /></th>
                <th className="text-right px-3 py-2.5 hidden sm:table-cell"><SortHeader label="成交额" field="volume" /></th>
                <th className="text-right px-3 py-2.5 hidden sm:table-cell"><SortHeader label="评分" field="score" /></th>
                <th className="text-right px-3 py-2.5 hidden md:table-cell"><SortHeader label="资金费" field="fundingRate" /></th>
                <th className="text-right px-3 py-2.5 hidden md:table-cell"><SortHeader label="持仓量" field="oi" /></th>
                <th className="text-left px-3 py-2.5 hidden lg:table-cell text-[8px] text-slate-500 font-black uppercase">方向</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, i) => (
                <tr key={item.symbol} className="border-b border-slate-800/20 hover:bg-slate-800/20 transition-colors">
                  <td className="px-3 py-2 text-[10px] text-slate-600">{i + 1}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className="text-white font-bold text-xs">{item.symbol}</span>
                      <span className={`text-[7px] px-1.5 py-0.5 rounded font-bold ${
                        item.sector === 'major' ? 'bg-amber-500/10 text-amber-400' :
                        item.sector === 'defi' ? 'bg-violet-500/10 text-violet-400' :
                        item.sector === 'layer1' ? 'bg-cyan-500/10 text-cyan-400' :
                        item.sector === 'layer2' ? 'bg-blue-500/10 text-blue-400' :
                        item.sector === 'ai' ? 'bg-emerald-500/10 text-emerald-400' :
                        item.sector === 'meme' ? 'bg-pink-500/10 text-pink-400' :
                        item.sector === 'gamefi' ? 'bg-orange-500/10 text-orange-400' :
                        'bg-slate-700/30 text-slate-500'
                      }`}>
                        {SECTORS[item.sector] || item.sector}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-white tabular-nums text-[11px]">
                    ${fmtPrice(item.price)}
                  </td>
                  <td className={`px-3 py-2 text-right font-bold tabular-nums text-[11px] ${
                    (item.change24h || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {fmtPct(item.change24h)}
                  </td>
                  <td className="px-3 py-2 text-right text-slate-400 hidden sm:table-cell tabular-nums text-[10px]">
                    ${fmtVol(item.volume)}
                  </td>
                  <td className="px-3 py-2 text-right hidden sm:table-cell">
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-lg ${
                      (item.score || 0) >= 70 ? 'bg-emerald-500/10 text-emerald-400' :
                      (item.score || 0) >= 50 ? 'bg-amber-500/10 text-amber-400' :
                      'bg-slate-700/20 text-slate-500'
                    }`}>
                      {safe(item.score)}
                    </span>
                  </td>
                  <td className={`px-3 py-2 text-right hidden md:table-cell tabular-nums text-[10px] ${
                    (item.fundingRate || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {item.fundingRate != null ? (item.fundingRate * 100).toFixed(4) + '%' : '--'}
                  </td>
                  <td className="px-3 py-2 text-right text-slate-400 hidden md:table-cell tabular-nums text-[10px]">
                    {item.oi ? '$' + fmtVol(item.oi) : '--'}
                  </td>
                  <td className="px-3 py-2 text-left hidden lg:table-cell">
                    <span className={`text-[9px] font-bold px-2 py-0.5 rounded ${
                      item.direction?.includes('上涨') ? 'bg-emerald-500/10 text-emerald-400' :
                      item.direction?.includes('下跌') ? 'bg-red-500/10 text-red-400' :
                      'bg-slate-700/20 text-slate-500'
                    }`}>
                      {item.direction || '--'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="text-center py-8 text-slate-500 text-xs">无匹配结果</div>
        )}
      </div>

      {cg?.liquidation_coins?.length > 0 && (
        <div className="shield-glass rounded-2xl p-4">
          <div className="text-[9px] text-red-400 font-black uppercase mb-3">24H清算排行</div>
          <div className="space-y-1.5 max-h-[250px] overflow-y-auto">
            {cg.liquidation_coins.slice(0, 15).map((liq, i) => {
              const total = (liq.long_vol || 0) + (liq.short_vol || 0);
              const longPct = total > 0 ? (liq.long_vol / total) * 100 : 50;
              return (
                <div key={i} className="flex items-center gap-2 text-[10px] bg-slate-950/30 rounded-lg px-3 py-1.5">
                  <span className="text-slate-600 w-4">{i + 1}</span>
                  <span className="text-white font-bold w-12">{liq.symbol}</span>
                  <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden flex">
                    <div className="bg-emerald-500/60 h-full" style={{ width: `${longPct}%` }} />
                    <div className="bg-red-500/60 h-full" style={{ width: `${100 - longPct}%` }} />
                  </div>
                  <span className="text-emerald-400 w-16 text-right">${fmtVol(liq.long_vol)}</span>
                  <span className="text-red-400 w-16 text-right">${fmtVol(liq.short_vol)}</span>
                  <span className="text-slate-400 w-16 text-right">${fmtVol(total)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
