import { useState, useEffect } from 'react';
import {
  TrendingUp, Newspaper, Brain, Database, Loader2,
  BarChart3, ArrowUpRight, ArrowDownRight, Clock,
  Zap, Shield, RefreshCw, Sparkles, Eye, AlertTriangle,
  ExternalLink, GitBranch
} from 'lucide-react';
import DebateCard from '../components/DebateCard';
import CounterfactualPanel from '../components/CounterfactualPanel';
import MemoryStrengthMap from '../components/MemoryStrengthMap';
import BacktestReport from '../components/BacktestReport';
import SignalQualityPanel from '../components/SignalQualityPanel';
import EvolutionLog from '../components/EvolutionLog';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { useShield } from '../hooks/useShieldData';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const pctColor = (v) => {
  const n = parseFloat(v);
  if (!n && n !== 0) return 'text-slate-400';
  return n >= 0 ? 'text-emerald-400' : 'text-red-400';
};

const PctArrow = ({ val }) => {
  const n = parseFloat(val);
  if (!n && n !== 0) return null;
  return n >= 0
    ? <ArrowUpRight className="w-3 h-3 text-emerald-400 inline" />
    : <ArrowDownRight className="w-3 h-3 text-red-400 inline" />;
};

const fmtUsd = (v, decimals = 1) => {
  if (v == null) return '--';
  const abs = Math.abs(v);
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(decimals)}B`;
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(decimals)}M`;
  if (abs >= 1e3) return `$${(v / 1e3).toFixed(decimals)}K`;
  return `$${v.toFixed(decimals)}`;
};

const tabs = [
  { key: 'derivatives', label: '衍生品全景', icon: TrendingUp },
  { key: 'rankings', label: '市场排行', icon: BarChart3 },
  { key: 'news', label: '新闻情报', icon: Newspaper },
  { key: 'synapse', label: '跨策略洞察', icon: Brain },
  { key: 'decisions', label: '决策透视', icon: GitBranch },
  { key: 'evolution', label: '进化日志', icon: Zap },
  { key: 'memory', label: '统一记忆', icon: Database },
];

export default function IntelCenter() {
  const {
    externalData, synapseData, data,
    memoryStats, memoryAnalysis, memoryAnalyzing,
    fetchMemoryStats, runMemoryAnalysis, generateAutoRules,
    coordinatorData, coinglassData,
  } = useShield();

  const [activeSection, setActiveSection] = useState('derivatives');
  const [unifiedMem, setUnifiedMem] = useState(null);

  const fetchUnifiedMem = async () => {
    try {
      const res = await fetch('/api/unified-memory');
      if (res.ok) setUnifiedMem(await res.json());
    } catch (err) { console.error('Unified memory fetch failed:', err); }
  };

  useEffect(() => { fetchMemoryStats(); fetchUnifiedMem(); }, []);

  const cg = coinglassData || externalData?.coinglass;
  const newsRaw = externalData?.news;
  const news = newsRaw?.articles || (Array.isArray(newsRaw) ? newsRaw : []);

  const sentimentStyle = (s) => {
    if (s === '正面' || s === 'positive') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (s === '负面' || s === 'negative') return 'bg-red-500/20 text-red-400 border-red-500/30';
    return 'bg-slate-700/30 text-slate-400 border-slate-700/40';
  };

  const sentimentLabel = (s) => {
    if (s === '正面' || s === 'positive') return '正面';
    if (s === '负面' || s === 'negative') return '负面';
    return '中性';
  };

  const renderDerivatives = () => {
    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">BTC 持仓量</div>
            <div className="text-sm font-black text-orange-400">
              {cg?.btc_oi ? fmtUsd(cg.btc_oi) : '--'}
            </div>
            <div className={`text-[9px] font-bold ${pctColor(cg?.btc_oi_change_24h)}`}>
              <PctArrow val={cg?.btc_oi_change_24h} /> {cg?.btc_oi_change_24h != null ? `${cg.btc_oi_change_24h > 0 ? '+' : ''}${cg.btc_oi_change_24h.toFixed(1)}%` : '--'}
            </div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">资金费率</div>
            <div className={`text-sm font-black ${
              (cg?.btc_funding_rate || 0) > 0.0003 ? 'text-red-400' :
              (cg?.btc_funding_rate || 0) < -0.0001 ? 'text-emerald-400' : 'text-amber-400'
            }`}>
              {cg?.btc_funding_rate != null ? `${(cg.btc_funding_rate * 100).toFixed(4)}%` : '--'}
            </div>
            <div className="text-[9px] text-slate-500">
              {(cg?.btc_funding_rate || 0) > 0.0005 ? '多头过热' :
               (cg?.btc_funding_rate || 0) < -0.0003 ? '空头付费' : '正常'}
            </div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">多空账户比</div>
            <div className={`text-sm font-black ${
              (cg?.btc_long_short_ratio || 1) > 1.2 ? 'text-emerald-400' :
              (cg?.btc_long_short_ratio || 1) < 0.8 ? 'text-red-400' : 'text-white'
            }`}>
              {cg?.btc_long_short_ratio?.toFixed(2) ?? '--'}
            </div>
            {cg?.long_short_accounts?.long_ratio != null && (
              <div className="text-[9px] text-slate-500">
                多{cg.long_short_accounts.long_ratio}% / 空{cg.long_short_accounts.short_ratio}%
              </div>
            )}
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">24h 清算</div>
            <div className="text-sm font-black text-white">
              {cg?.btc_liquidation_24h?.total ? fmtUsd(cg.btc_liquidation_24h.total) : '--'}
            </div>
            <div className="flex justify-center gap-2 text-[9px]">
              <span className="text-emerald-400">多:{cg?.btc_liquidation_24h?.long ? fmtUsd(cg.btc_liquidation_24h.long) : '--'}</span>
              <span className="text-red-400">空:{cg?.btc_liquidation_24h?.short ? fmtUsd(cg.btc_liquidation_24h.short) : '--'}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {cg?.top_trader_sentiment?.ratio != null && (
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">顶级交易员多空比</div>
              <div className={`text-lg font-black ${cg.top_trader_sentiment.ratio > 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                {cg.top_trader_sentiment.ratio.toFixed(2)}
              </div>
              <div className="text-[9px] text-slate-500">
                多{cg.top_trader_sentiment.long_ratio}% / 空{cg.top_trader_sentiment.short_ratio}%
              </div>
            </div>
          )}
          {cg?.taker_buy_sell?.ratio != null && (
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">主动买卖比</div>
              <div className={`text-lg font-black ${cg.taker_buy_sell.ratio > 1 ? 'text-emerald-400' : 'text-red-400'}`}>
                {cg.taker_buy_sell.ratio.toFixed(4)}
              </div>
              <div className="flex justify-center gap-2 text-[9px]">
                <span className="text-emerald-400">买: {fmtUsd(cg.taker_buy_sell.buy_vol)}</span>
                <span className="text-red-400">卖: {fmtUsd(cg.taker_buy_sell.sell_vol)}</span>
              </div>
            </div>
          )}
          {cg?.coinbase_premium != null && (
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">Coinbase 溢价</div>
              <div className={`text-lg font-black ${cg.coinbase_premium > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {cg.coinbase_premium > 0 ? '+' : ''}{cg.coinbase_premium.toFixed(2)}%
              </div>
              <div className="text-[9px] text-slate-500">
                {cg.coinbase_premium > 0.5 ? '美国买盘强劲' : cg.coinbase_premium < -0.5 ? '美国卖压' : '正常'}
              </div>
            </div>
          )}
        </div>

        {cg?.ahr999 != null && (
          <div className="bg-slate-950/60 border border-amber-500/20 rounded-xl p-3 flex items-center justify-between">
            <div>
              <div className="text-[9px] text-amber-400 font-black uppercase">AHR999 指标</div>
              <div className="text-[10px] text-slate-400 mt-0.5">
                {cg.ahr999 < 0.45 ? '抄底区间' : cg.ahr999 < 1.2 ? '定投区间' : '过热区间'}
              </div>
            </div>
            <div className={`text-xl font-black ${cg.ahr999 < 0.45 ? 'text-emerald-400' : cg.ahr999 < 1.2 ? 'text-amber-400' : 'text-red-400'}`}>
              {cg.ahr999.toFixed(2)}
            </div>
          </div>
        )}

        {cg?.liquidation_coins && cg.liquidation_coins.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-red-400 font-black uppercase mb-3">清算排行</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {cg.liquidation_coins.slice(0, 8).map((item, i) => (
                <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-lg p-2 text-center">
                  <div className="text-[10px] font-black text-white">{safe(item.symbol)}</div>
                  <div className="text-[9px] text-white font-bold">
                    {item.total ? fmtUsd(item.total) : '--'}
                  </div>
                  {item.long_vol != null && item.total != null && (
                    <div className="flex justify-center gap-1 text-[8px]">
                      <span className="text-emerald-400">{((item.long_vol / (item.total || 1)) * 100).toFixed(0)}%多</span>
                      <span className="text-red-400">{((item.short_vol / (item.total || 1)) * 100).toFixed(0)}%空</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {cg?.etf_flows?.history?.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="text-[9px] text-amber-400 font-black uppercase">BTC ETF 资金流</div>
              <div className="flex gap-3">
                <span className={`text-[9px] font-bold ${(cg.etf_flows.latest_flow || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  最新: {(cg.etf_flows.latest_flow || 0) >= 0 ? '+' : ''}{fmtUsd(cg.etf_flows.latest_flow || 0)}
                </span>
                <span className={`text-[9px] font-bold ${(cg.etf_flows.net_7d || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  7日: {(cg.etf_flows.net_7d || 0) >= 0 ? '+' : ''}{fmtUsd(cg.etf_flows.net_7d || 0)}
                </span>
              </div>
            </div>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={[...cg.etf_flows.history].reverse()} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                  <XAxis dataKey="date" tick={{ fontSize: 7, fill: '#64748b' }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 7, fill: '#64748b' }} axisLine={false} tickLine={false} tickFormatter={v => `${(v / 1e6).toFixed(0)}M`} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} formatter={(v) => [fmtUsd(v), '净流入']} />
                  <Bar dataKey="total_net_flow" radius={[3, 3, 0, 0]}>
                    {[...cg.etf_flows.history].reverse().map((entry, i) => (
                      <Cell key={i} fill={entry.total_net_flow >= 0 ? '#10b981' : '#ef4444'} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {(() => {
              const history = cg.etf_flows.history || [];
              const latestEntry = history.length > 0 ? history[0] : null;
              const latestDate = latestEntry?.date || null;
              return latestDate ? (
                <div className="text-slate-500 text-xs mt-2">
                  数据截止：{latestDate}（T+1延迟）
                </div>
              ) : null;
            })()}
          </div>
        )}

        {cg?.funding_heatmap?.BTC?.exchanges?.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-cyan-400 font-black uppercase mb-3">BTC 各交易所资金费率</div>
            <div className="overflow-x-auto">
              <table className="w-full text-[10px]">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left py-2 px-2 font-black">交易所</th>
                    <th className="text-right py-2 px-2 font-black">费率</th>
                    <th className="text-right py-2 px-2 font-black">方向</th>
                  </tr>
                </thead>
                <tbody>
                  {cg.funding_heatmap.BTC.exchanges.map((item, i) => (
                    <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                      <td className="py-1.5 px-2 font-bold text-white">{safe(item.exchange)}</td>
                      <td className={`py-1.5 px-2 text-right font-bold ${
                        (item.rate || 0) > 0.0003 ? 'text-red-400' :
                        (item.rate || 0) < -0.0001 ? 'text-emerald-400' : 'text-slate-300'
                      }`}>
                        {item.rate != null ? `${(item.rate * 100).toFixed(4)}%` : '--'}
                      </td>
                      <td className="py-1.5 px-2 text-right">
                        <span className={`text-[8px] font-black px-1.5 py-0.5 rounded ${
                          (item.rate || 0) > 0 ? 'bg-red-500/15 text-red-400' : 'bg-emerald-500/15 text-emerald-400'
                        }`}>
                          {(item.rate || 0) > 0 ? '多付空' : '空付多'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {!cg && (
          <div className="shield-glass rounded-2xl p-8 text-center">
            <AlertTriangle className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <div className="text-xs text-slate-500">暂无衍生品数据</div>
          </div>
        )}
      </div>
    );
  };

  const renderRankings = () => {
    const coins = cg?.top_oi_coins || [];
    const liqCoins = cg?.liquidation_coins || [];

    if (coins.length === 0 && liqCoins.length === 0) {
      return (
        <div className="shield-glass rounded-2xl p-8 text-center animate-fadeIn">
          <BarChart3 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <div className="text-xs text-slate-500">暂无市场排行数据</div>
        </div>
      );
    }

    return (
      <div className="space-y-4 animate-fadeIn">
        {coins.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-orange-400 font-black uppercase mb-3 flex items-center gap-2">
              <TrendingUp className="w-3.5 h-3.5" /> 衍生品持仓排行
            </div>
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-[10px] min-w-[600px]">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left py-2 px-2 font-black">#</th>
                    <th className="text-left py-2 px-2 font-black">币种</th>
                    <th className="text-right py-2 px-2 font-black">价格</th>
                    <th className="text-right py-2 px-2 font-black">持仓量</th>
                    <th className="text-right py-2 px-2 font-black">持仓变化(24h)</th>
                    <th className="text-right py-2 px-2 font-black">24h成交额</th>
                  </tr>
                </thead>
                <tbody>
                  {coins.map((coin, i) => (
                    <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                      <td className="py-2 px-2 text-slate-500 font-bold">{i + 1}</td>
                      <td className="py-2 px-2 font-black text-white">{safe(coin.symbol)}</td>
                      <td className="py-2 px-2 text-right text-slate-300 font-mono tabular-nums">
                        ${coin.price != null ? Number(coin.price).toLocaleString(undefined, { maximumFractionDigits: 2 }) : '--'}
                      </td>
                      <td className="py-2 px-2 text-right font-bold text-orange-400 tabular-nums">
                        {fmtUsd(coin.oi)}
                      </td>
                      <td className={`py-2 px-2 text-right font-bold tabular-nums ${pctColor(coin.oi_change_24h)}`}>
                        {coin.oi_change_24h != null ? (
                          <>
                            <PctArrow val={coin.oi_change_24h} />
                            {coin.oi_change_24h > 0 ? '+' : ''}{coin.oi_change_24h.toFixed(2)}%
                          </>
                        ) : '--'}
                      </td>
                      <td className="py-2 px-2 text-right text-slate-300 tabular-nums">
                        {fmtUsd(coin.volume_24h)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {coins.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-cyan-400 font-black uppercase mb-3">持仓量分布</div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={coins.slice(0, 10)} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
                  <XAxis dataKey="symbol" tick={{ fontSize: 8, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 8, fill: '#64748b' }} axisLine={false} tickLine={false} tickFormatter={v => fmtUsd(v, 0)} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 10 }} formatter={(v) => [fmtUsd(v), '持仓量']} />
                  <Bar dataKey="oi" radius={[4, 4, 0, 0]}>
                    {coins.slice(0, 10).map((_, i) => (
                      <Cell key={i} fill={i === 0 ? '#f97316' : '#3b82f6'} fillOpacity={0.7} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {liqCoins.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-red-400 font-black uppercase mb-3 flex items-center gap-2">
              <Zap className="w-3.5 h-3.5" /> 24h清算排行
            </div>
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-[10px] min-w-[500px]">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left py-2 px-2 font-black">#</th>
                    <th className="text-left py-2 px-2 font-black">币种</th>
                    <th className="text-right py-2 px-2 font-black">总清算</th>
                    <th className="text-right py-2 px-2 font-black">多头清算</th>
                    <th className="text-right py-2 px-2 font-black">空头清算</th>
                    <th className="text-right py-2 px-2 font-black">多/空比</th>
                  </tr>
                </thead>
                <tbody>
                  {liqCoins.map((coin, i) => {
                    const longPct = coin.total ? ((coin.long_vol / coin.total) * 100) : 0;
                    return (
                      <tr key={i} className="border-b border-slate-800/50 hover:bg-slate-800/20 transition-colors">
                        <td className="py-2 px-2 text-slate-500 font-bold">{i + 1}</td>
                        <td className="py-2 px-2 font-black text-white">{safe(coin.symbol)}</td>
                        <td className="py-2 px-2 text-right font-bold text-white tabular-nums">{fmtUsd(coin.total)}</td>
                        <td className="py-2 px-2 text-right text-emerald-400 tabular-nums">{fmtUsd(coin.long_vol)}</td>
                        <td className="py-2 px-2 text-right text-red-400 tabular-nums">{fmtUsd(coin.short_vol)}</td>
                        <td className="py-2 px-2 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <div className="w-16 h-1.5 bg-slate-800 rounded-full overflow-hidden flex">
                              <div className="h-full bg-emerald-500" style={{ width: `${longPct}%` }} />
                              <div className="h-full bg-red-500 flex-1" />
                            </div>
                            <span className="text-[8px] text-slate-400 tabular-nums w-8 text-right">{longPct.toFixed(0)}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>
    );
  };

  const renderNews = () => {
    const items = Array.isArray(news) ? news : [];
    if (items.length === 0) {
      return (
        <div className="shield-glass rounded-2xl p-8 text-center animate-fadeIn">
          <Newspaper className="w-8 h-8 text-slate-600 mx-auto mb-2" />
          <div className="text-xs text-slate-500">暂无新闻情报</div>
        </div>
      );
    }

    return (
      <div className="space-y-3 animate-fadeIn">
        {items.map((item, i) => (
          <div key={i} className="shield-glass rounded-xl p-4 hover:border-slate-700 transition-colors">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1.5">
                  <span className={`text-[8px] font-black px-2 py-0.5 rounded-lg border ${sentimentStyle(item.sentiment)}`}>
                    {sentimentLabel(item.sentiment)}
                  </span>
                  {item.source && (
                    <span className="text-[8px] text-slate-500 font-bold">{safe(item.source)}</span>
                  )}
                  {item.published_at && (
                    <span className="text-[8px] text-slate-600 flex items-center gap-0.5">
                      <Clock className="w-2.5 h-2.5" />
                      {new Date(item.published_at).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                </div>
                <h4 className="text-xs font-bold text-white leading-relaxed">{safe(item.title)}</h4>
              </div>
              {item.url && (
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-slate-500 hover:text-cyan-400 transition-colors shrink-0">
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderSynapse = () => {
    const syn = synapseData || data?.synapse;
    if (!syn) return (
      <div className="shield-glass rounded-2xl p-8 text-center animate-fadeIn">
        <Brain className="w-8 h-8 text-slate-600 mx-auto mb-2" />
        <div className="text-xs text-slate-500">系统启动后将自动收集跨策略数据</div>
      </div>
    );

    const totalBroadcasts = syn.total_broadcasts ?? 0;
    const activeRules = syn.active_rules ?? 0;
    const rulesGenerated = syn.rules_generated ?? 0;
    const crossRules = syn.cross_rules || [];
    const stratPerf = syn.strategy_performance || {};
    const regimeInsights = syn.regime_insights || {};
    const timingInsights = syn.timing_insights || {};
    const broadcasts = syn.recent_broadcasts || [];
    const aiInsights = syn.ai_insights;
    const stratMap = { trend: '趋势跟踪', grid: '网格交易', range: '区间收割' };
    const regimeMap = { trending: '趋势', volatile: '震荡', ranging: '横盘', mixed: '混合', unknown: '未知' };

    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">总广播</div>
            <div className="text-lg font-black text-cyan-400">{totalBroadcasts.toLocaleString()}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">活跃规则</div>
            <div className="text-lg font-black text-emerald-400">{activeRules}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">已生成规则</div>
            <div className="text-lg font-black text-amber-400">{rulesGenerated}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">最后同步</div>
            <div className="text-xs font-bold text-indigo-400">{syn.last_sync ? syn.last_sync.split(' ')[1] || syn.last_sync : '--'}</div>
          </div>
        </div>

        {Object.keys(stratPerf).length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-cyan-400 font-black uppercase mb-3">策略表现对比</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {Object.entries(stratPerf).map(([key, perf]) => (
                <div key={key} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                  <div className="text-[10px] font-bold text-white mb-2">{stratMap[key] || key}</div>
                  <div className="space-y-1.5 text-[9px]">
                    <div className="flex justify-between"><span className="text-slate-500">交易数</span><span className="text-white font-mono">{perf.total_trades}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">胜率</span><span className={perf.win_rate >= 50 ? 'text-emerald-400' : perf.win_rate >= 35 ? 'text-amber-400' : 'text-red-400'}>{perf.win_rate}%</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">总盈亏</span><span className={perf.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>{perf.total_pnl >= 0 ? '+' : ''}{perf.total_pnl?.toFixed(2)}%</span></div>
                    {perf.worst_assets && Object.keys(perf.worst_assets).length > 0 && (
                      <div className="pt-1 border-t border-slate-800">
                        <div className="text-[8px] text-slate-600 mb-1">高频交易资产</div>
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(perf.worst_assets).slice(0, 3).map(([asset, count]) => (
                            <span key={asset} className="text-[8px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">{asset} ({count})</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.keys(regimeInsights).length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-violet-400 font-black uppercase mb-3">市场环境洞察</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(regimeInsights).map(([regime, info]) => (
                <div key={regime} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                  <div className="text-[10px] font-bold text-white mb-1.5">{regimeMap[regime] || regime}</div>
                  <div className="text-[9px] space-y-1">
                    <div className="flex justify-between"><span className="text-slate-500">交易</span><span className="text-white font-mono">{info.total_trades}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">胜率</span><span className={info.win_rate >= 50 ? 'text-emerald-400' : info.win_rate >= 35 ? 'text-amber-400' : 'text-red-400'}>{info.win_rate}%</span></div>
                    {info.best_strategy && <div className="text-[8px] text-slate-600 pt-1">最佳: {info.best_strategy}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.keys(timingInsights).length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-amber-400 font-black uppercase mb-3">交易时段分析</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(timingInsights).map(([session, info]) => (
                <div key={session} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
                  <div className="text-[10px] font-bold text-white mb-1">{session}</div>
                  <div className="text-[8px] text-slate-500">{info.total} 笔</div>
                  <div className={`text-sm font-black ${info.win_rate >= 50 ? 'text-emerald-400' : info.win_rate >= 35 ? 'text-amber-400' : 'text-red-400'}`}>{info.win_rate}%</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {crossRules.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-red-400 font-black uppercase mb-3">跨策略规则 (最近{crossRules.length}条)</div>
            <div className="space-y-2 max-h-[40vh] overflow-y-auto">
              {crossRules.slice(-15).reverse().map((rule, i) => (
                <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold text-white">{safe(rule.description || rule.reason || rule.asset || `规则 #${i + 1}`)}</span>
                    <div className="flex items-center gap-2">
                      {rule.type && (
                        <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${
                          rule.type === 'asset_avoid' ? 'bg-red-500/15 text-red-400 border-red-500/30' :
                          rule.type === 'strategy_preference' ? 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30' :
                          'bg-indigo-500/15 text-indigo-400 border-indigo-500/30'
                        }`}>
                          {rule.type === 'asset_avoid' ? '避开资产' : rule.type === 'strategy_preference' ? '策略偏好' : safe(rule.type)}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-[8px] text-slate-600 mt-1">
                    {rule.asset && <span>资产: {rule.asset}</span>}
                    {rule.created && <span>{rule.created}</span>}
                    {rule.source && <span>来源: {rule.source}</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {aiInsights && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-emerald-400 font-black uppercase mb-3">AI 跨策略分析</div>
            <div className="text-[10px] text-slate-300 leading-relaxed bg-slate-950/60 border border-slate-800 rounded-lg p-3 whitespace-pre-wrap">
              {typeof aiInsights === 'object' ? JSON.stringify(aiInsights, null, 2) : safe(aiInsights)}
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderMemory = () => {
    const stats = memoryStats;

    const totalTrades = stats?.total ?? 0;
    const symbolPerf = stats?.symbol_performance || {};
    const stratPerf = stats?.strategy_performance || {};
    const regimePerf = stats?.regime_performance || {};
    const scoreBuckets = stats?.signal_score_buckets || {};
    const dirStats = stats?.direction_stats || {};
    const timeDist = stats?.time_distribution || {};
    const holdingAnalysis = stats?.holding_analysis || {};

    const um = unifiedMem;
    const agentMem = um?.agent_memory || {};
    const topPatterns = agentMem.top_patterns || [];
    const recentInsights = agentMem.recent_insights || [];

    const sortedSymbols = Object.entries(symbolPerf).sort((a, b) => b[1].total_pnl - a[1].total_pnl);

    return (
      <div className="space-y-4 animate-fadeIn">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">总交易数</div>
            <div className="text-lg font-black text-cyan-400">{totalTrades}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">识别模式</div>
            <div className="text-lg font-black text-violet-400">{agentMem.patterns_tracked ?? topPatterns.length ?? '--'}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">累积洞察</div>
            <div className="text-lg font-black text-amber-400">{agentMem.insights_count ?? '--'}</div>
          </div>
          <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
            <div className="text-[9px] text-slate-500 font-black uppercase">禁用规则</div>
            <div className="text-lg font-black text-red-400">{agentMem.ban_rules ?? '--'}</div>
          </div>
        </div>

        <div className="shield-glass rounded-2xl p-4">
          <div className="text-[9px] text-slate-500 font-black uppercase mb-3">记忆操作</div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => { fetchMemoryStats(30); fetchUnifiedMem(); }}
              className="flex items-center gap-1.5 text-[10px] font-bold px-3 py-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 hover:bg-cyan-500/20 transition-colors"
            >
              <RefreshCw className="w-3 h-3" /> 刷新统计
            </button>
            <button
              onClick={runMemoryAnalysis}
              disabled={memoryAnalyzing}
              className="flex items-center gap-1.5 text-[10px] font-bold px-3 py-2 rounded-lg bg-violet-500/10 text-violet-400 border border-violet-500/20 hover:bg-violet-500/20 transition-colors disabled:opacity-50"
            >
              {memoryAnalyzing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
              {memoryAnalyzing ? '分析中...' : '运行分析'}
            </button>
            <button
              onClick={generateAutoRules}
              className="flex items-center gap-1.5 text-[10px] font-bold px-3 py-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 transition-colors"
            >
              <Sparkles className="w-3 h-3" /> 生成自动规则
            </button>
          </div>
        </div>

        {recentInsights.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-amber-400 font-black uppercase mb-3">最新洞察</div>
            <div className="space-y-2 max-h-[30vh] overflow-y-auto">
              {recentInsights.map((ins, i) => (
                <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-lg p-2.5">
                  <div className="text-[8px] text-slate-600 mb-1">{ins.time}</div>
                  <div className="text-[10px] text-slate-300 leading-relaxed">{safe(ins.insight)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {topPatterns.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-violet-400 font-black uppercase mb-3">交易模式识别</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {topPatterns.map((pat, i) => (
                <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold text-white">{safe(pat.pattern)}</span>
                    <span className={`text-[8px] font-black px-1.5 py-0.5 rounded ${pat.win_rate >= 60 ? 'bg-emerald-500/15 text-emerald-400' : pat.win_rate >= 40 ? 'bg-amber-500/15 text-amber-400' : 'bg-red-500/15 text-red-400'}`}>
                      胜率 {pat.win_rate}%
                    </span>
                  </div>
                  <div className="flex gap-3 text-[8px] text-slate-500 mt-1">
                    <span>总计 {pat.total} 笔</span>
                    <span className="text-emerald-500">胜 {pat.wins}</span>
                    <span className="text-red-500">负 {pat.losses}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {sortedSymbols.length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-cyan-400 font-black uppercase mb-3">资产表现排行 (Top 10)</div>
            <div className="space-y-1.5">
              {sortedSymbols.slice(0, 10).map(([symbol, perf]) => (
                <div key={symbol} className="flex items-center justify-between bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-white w-14">{symbol}</span>
                    <span className="text-[8px] text-slate-500">{perf.trades} 笔</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-[9px] font-bold ${perf.win_rate >= 60 ? 'text-emerald-400' : perf.win_rate >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                      胜率 {perf.win_rate}%
                    </span>
                    <span className={`text-[9px] font-mono font-bold w-20 text-right ${perf.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {perf.total_pnl >= 0 ? '+' : ''}{perf.total_pnl.toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.keys(dirStats).length > 0 && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-indigo-400 font-black uppercase mb-3">方向分析</div>
            <div className="grid grid-cols-2 gap-3">
              {Object.entries(dirStats).map(([dir, info]) => (
                <div key={dir} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
                  <div className={`text-sm font-bold mb-1 ${dir === 'long' ? 'text-emerald-400' : 'text-red-400'}`}>{dir === 'long' ? '做多' : '做空'}</div>
                  <div className="text-[9px] text-slate-500">{info.trades} 笔 | 胜率 {info.win_rate}%</div>
                  <div className={`text-xs font-black mt-1 ${info.total_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {info.total_pnl >= 0 ? '+' : ''}{info.total_pnl.toFixed(2)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {memoryAnalysis && (
          <div className="shield-glass rounded-2xl p-4">
            <div className="text-[9px] text-violet-400 font-black uppercase mb-3">AI 分析结果</div>
            {typeof memoryAnalysis === 'object' ? (
              <div className="space-y-2">
                {memoryAnalysis.summary && (
                  <div className="text-[10px] text-white leading-relaxed bg-slate-950/60 border border-slate-800 rounded-lg p-3">
                    {safe(memoryAnalysis.summary)}
                  </div>
                )}
                {memoryAnalysis.insights && Array.isArray(memoryAnalysis.insights) && memoryAnalysis.insights.map((insight, i) => (
                  <div key={i} className="text-[10px] text-slate-300 bg-slate-950/40 border border-slate-800 rounded-lg p-2.5">
                    {safe(insight)}
                  </div>
                ))}
                {memoryAnalysis.recommendations && Array.isArray(memoryAnalysis.recommendations) && memoryAnalysis.recommendations.map((rec, i) => (
                  <div key={i} className="text-[10px] text-amber-300 bg-amber-500/5 border border-amber-500/15 rounded-lg p-2.5 flex items-start gap-1.5">
                    <Zap className="w-3 h-3 shrink-0 mt-0.5" />
                    <span>{safe(rec)}</span>
                  </div>
                ))}
                {!memoryAnalysis.summary && !memoryAnalysis.insights && !memoryAnalysis.recommendations && (
                  <div className="text-[10px] text-slate-300 bg-slate-950/60 border border-slate-800 rounded-lg p-3 whitespace-pre-wrap">
                    {JSON.stringify(memoryAnalysis, null, 2)}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-[10px] text-slate-300 bg-slate-950/60 border border-slate-800 rounded-lg p-3">
                {safe(memoryAnalysis)}
              </div>
            )}
          </div>
        )}

        {!stats && !um && (
          <div className="shield-glass rounded-2xl p-8 text-center">
            <Database className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <div className="text-xs text-slate-500">点击"刷新统计"加载记忆数据</div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-400" /> 情报中心
        </h2>
      </div>

      <div className="flex gap-1.5 overflow-x-auto pb-1 scrollbar-hide">
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeSection === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveSection(tab.key)}
              className={`flex items-center gap-1.5 text-[10px] font-bold px-3 py-2 rounded-lg whitespace-nowrap transition-all ${
                isActive
                  ? 'bg-cyan-500/15 text-cyan-400 border border-cyan-500/30'
                  : 'bg-slate-800/30 text-slate-500 border border-slate-800 hover:text-slate-300 hover:border-slate-700'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {activeSection === 'derivatives' && renderDerivatives()}
      {activeSection === 'rankings' && renderRankings()}
      {activeSection === 'news' && renderNews()}
      {activeSection === 'synapse' && renderSynapse()}
      {activeSection === 'decisions' && (
        <div className="space-y-4">
          <SignalQualityPanel />
          <BacktestReport />
          <DebateCard />
          <CounterfactualPanel />
          <MemoryStrengthMap />
        </div>
      )}
      {activeSection === 'evolution' && <EvolutionLog />}
      {activeSection === 'memory' && renderMemory()}
    </div>
  );
}