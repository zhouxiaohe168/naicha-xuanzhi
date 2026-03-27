import React, { useState, useRef, useEffect } from 'react';
import { TrendingUp, Gauge, BarChart3, Shield, Zap, Grid3X3, Wifi, WifiOff, RefreshCw, Bell } from 'lucide-react';
import { useShield } from '../hooks/useShieldData';
import { GaugeRing, StatusDot, AnimatedNumber } from './ProUI';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const CommandBar = () => {
  const { btcPulse, fngVal, fngDetail, highAlpha, scanMode, totalScanned, aiSummary, data, totalPnL, isConnected, dataAge, fetchData, notifications } = useShield();
  const [showNotifications, setShowNotifications] = useState(false);
  const notifRef = useRef(null);
  const alertCount = (notifications || []).filter(n => n.type === 'warn' || n.type === 'alert').length;

  useEffect(() => {
    const handleClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setShowNotifications(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const fngColor = fngVal <= 25 ? '#ef4444' : fngVal <= 45 ? '#f59e0b' : fngVal <= 55 ? '#94a3b8' : fngVal <= 75 ? '#10b981' : '#10b981';
  const fngLabel = fngDetail.label === 'Extreme Fear' ? '极度恐惧' : fngDetail.label === 'Fear' ? '恐惧' : fngDetail.label === 'Neutral' ? '中性' : fngDetail.label === 'Greed' ? '贪婪' : fngDetail.label === 'Extreme Greed' ? '极度贪婪' : fngDetail.label || '中性';

  const regimeVal = (() => { const r = data?.dispatcher?.current_regime; return r === 'trending' ? '趋势' : r === 'ranging' ? '震荡' : r === 'volatile' ? '剧烈' : r === 'mixed' ? '混合' : '检测'; })();
  const regimeColor = (() => { const r = data?.dispatcher?.current_regime; return r === 'trending' ? '#10b981' : r === 'ranging' ? '#06b6d4' : r === 'volatile' ? '#ef4444' : '#f59e0b'; })();
  const decisionVal = (() => { const m = data?.unified_decision?.last_decision?.mode; return m === 'full' ? '全开' : m === 'long_only' ? '做多' : m === 'defensive' ? '防御' : m === 'grid_focus' ? '网格' : m === 'no_trade' ? '停止' : '待机'; })();
  const decisionColor = (() => { const m = data?.unified_decision?.last_decision?.mode; return m === 'full' ? '#10b981' : m === 'no_trade' ? '#ef4444' : m === 'defensive' ? '#f59e0b' : '#06b6d4'; })();

  const btcChange = parseFloat(btcPulse.change) || 0;
  const annualizedReturn = data?.return_target?.annualized_return_pct;

  return (
    <div className="shield-glass-elevated rounded-2xl p-2 md:p-3 mb-3 md:mb-4 animate-fadeIn">

      <div className="md:hidden">
        <div className="flex items-center gap-2 flex-nowrap">
          <div className="flex items-center gap-1.5 flex-shrink-0">
            <div className={`p-1 rounded-lg ${btcChange >= 0 ? 'bg-emerald-500/10' : 'bg-red-500/10'}`}>
              <TrendingUp className={`w-3.5 h-3.5 ${btcChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`} />
            </div>
            <div className="flex-shrink-0">
              <div className="text-[8px] text-slate-500 font-bold flex items-center gap-0.5">
                BTC <StatusDot status={isConnected ? 'healthy' : 'offline'} />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-xs font-black tabular-nums">
                  ${btcPulse.price ? btcPulse.price.toLocaleString() : '---'}
                </span>
                <span className={`text-[8px] font-bold px-1 py-0.5 rounded ${btcChange >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                  {safe(btcPulse.change) || '0%'}
                </span>
                {btcPulse.is_crash && (
                  <span className="text-[7px] font-black bg-red-500/20 text-red-400 border border-red-500/30 px-0.5 rounded animate-pulse">熔断</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex-shrink-0 text-right border-l border-slate-700/40 pl-2">
            <div className="text-[7px] text-slate-600 font-bold">盈亏</div>
            <div className={`text-[10px] font-black tabular-nums ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
              <AnimatedNumber value={totalPnL} decimals={2} prefix={totalPnL >= 0 ? '+' : ''} />
            </div>
          </div>

          <div className="ml-auto flex items-center gap-1.5 flex-shrink-0">
            <div className="relative" ref={notifRef}>
              <button onClick={() => setShowNotifications(!showNotifications)} className="relative p-1 rounded-lg">
                <Bell className="w-3 h-3 text-slate-500" />
                {alertCount > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[12px] h-3 flex items-center justify-center text-[7px] font-black rounded-full bg-red-500 text-white px-0.5 animate-pulse">
                    {alertCount}
                  </span>
                )}
              </button>
              {showNotifications && (
                <div className="absolute right-0 top-7 w-64 shield-glass-elevated rounded-xl border border-slate-700 shadow-2xl z-50 max-h-80 overflow-y-auto animate-scaleIn">
                  <div className="p-2 border-b border-slate-700/50 flex items-center justify-between">
                    <span className="text-[9px] font-black text-slate-400 uppercase">通知中心</span>
                    <span className="text-[8px] text-slate-600">{(notifications || []).length} 条</span>
                  </div>
                  {(notifications || []).length === 0 ? (
                    <div className="p-4 text-[10px] text-slate-500 text-center">暂无通知</div>
                  ) : (
                    (notifications || []).slice(0, 10).map((n, i) => {
                      const typeColor = n.type === 'alert' ? 'border-l-red-500' : n.type === 'warn' ? 'border-l-amber-500' : 'border-l-cyan-500';
                      const textColor = n.type === 'alert' ? 'text-red-400' : n.type === 'warn' ? 'text-amber-400' : 'text-cyan-400';
                      return (
                        <div key={i} className={`p-2 border-b border-slate-800/50 border-l-2 ${typeColor}`}>
                          <div className={`text-[9px] font-bold ${textColor}`}>{n.message || n.msg || '--'}</div>
                          <div className="text-[7px] text-slate-600 mt-0.5 font-mono">{n.timestamp || n.time || '--'}</div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
            </div>
            <div className="flex items-center gap-1">
              {isConnected ? <Wifi className="w-2.5 h-2.5 text-emerald-400" /> : <WifiOff className="w-2.5 h-2.5 text-red-500" />}
              <span className={`text-[7px] font-bold tabular-nums ${dataAge > 30 ? 'text-amber-400' : 'text-slate-500'}`}>{dataAge}s</span>
            </div>
            <button onClick={fetchData} className="p-0.5 hover:bg-slate-800/60 rounded">
              <RefreshCw className="w-2.5 h-2.5 text-slate-500" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-0 mt-1.5 pt-1.5 border-t border-slate-700/30 overflow-x-auto scrollbar-hide flex-nowrap">
          <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5 border-r border-slate-700/30">
            <span className="text-[7px] text-slate-500 font-bold">FNG</span>
            <span className="text-[10px] font-black" style={{ color: fngColor }}>{fngVal}</span>
          </div>
          <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5 border-r border-slate-700/30">
            <span className="text-[7px] text-slate-500 font-bold">信号</span>
            <span className={`text-[10px] font-black ${highAlpha.length > 0 ? 'text-emerald-400' : 'text-slate-500'}`}>{highAlpha.length}</span>
          </div>
          <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5 border-r border-slate-700/30">
            <span className="text-[7px] text-slate-500 font-bold">扫描</span>
            <span className="text-[10px] font-black text-cyan-400">{totalScanned}</span>
          </div>
          <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5 border-r border-slate-700/30">
            <span className="text-[7px] text-slate-500 font-bold">调度</span>
            <span className="text-[10px] font-black" style={{ color: regimeColor }}>{regimeVal}</span>
          </div>
          <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5 border-r border-slate-700/30">
            <span className="text-[7px] text-slate-500 font-bold">决策</span>
            <span className="text-[10px] font-black" style={{ color: decisionColor }}>{decisionVal}</span>
          </div>
          {annualizedReturn != null && (
            <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5 border-r border-slate-700/30">
              <span className="text-[7px] text-slate-500 font-bold">年化</span>
              <span className={`text-[10px] font-black ${annualizedReturn >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{annualizedReturn}%</span>
            </div>
          )}
          {aiSummary.summary && aiSummary.summary.length > 1 && (
            <div className="flex items-center gap-0.5 flex-shrink-0 px-1.5">
              <Zap className={`w-2.5 h-2.5 flex-shrink-0 ${aiSummary.is_agent ? 'text-cyan-400' : 'text-slate-500'}`} />
              <span className={`text-[9px] font-bold truncate max-w-[120px] ${aiSummary.is_agent ? 'text-cyan-400' : 'text-slate-400'}`}>
                {safe(aiSummary.summary)}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="hidden md:flex items-center gap-3 overflow-x-auto scrollbar-hide flex-nowrap">
        <div className="flex items-center gap-3 flex-shrink-0 pr-3 border-r border-slate-700/50">
          <div className="flex items-center gap-2">
            <div className={`p-2 rounded-xl ${btcChange >= 0 ? 'bg-emerald-500/10 glow-emerald' : 'bg-red-500/10 glow-red'}`}>
              <TrendingUp className={`w-5 h-5 ${btcChange >= 0 ? 'text-emerald-400' : 'text-red-400'}`} />
            </div>
            <div>
              <div className="text-[9px] text-slate-500 font-bold flex items-center gap-1">
                BTC <StatusDot status={isConnected ? 'healthy' : 'offline'} />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="text-base font-black tabular-nums">
                  ${btcPulse.price ? btcPulse.price.toLocaleString() : '---'}
                </span>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${btcChange >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'}`}>
                  {safe(btcPulse.change) || '0%'}
                </span>
                {btcPulse.is_crash && (
                  <span className="text-[8px] font-black bg-red-500/20 text-red-400 border border-red-500/30 px-1 py-0.5 rounded animate-pulse glow-red">熔断</span>
                )}
              </div>
            </div>
          </div>
          <div className="text-right pl-2">
            <div className="text-[8px] text-slate-600 font-bold uppercase">盈亏</div>
            <div className={`text-xs font-black tabular-nums ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-500'}`}>
              <AnimatedNumber value={totalPnL} decimals={2} prefix={totalPnL >= 0 ? '+' : ''} />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-shrink-0 px-1">
          <GaugeRing value={fngVal} max={100} size={44} strokeWidth={4} color={fngColor} label="FNG" sublabel={fngLabel} />
        </div>

        <div className="flex items-center gap-3 flex-shrink-0 px-2 border-l border-slate-700/30">
          <div className="flex items-center gap-1.5">
            <BarChart3 className="w-3.5 h-3.5 text-slate-600" />
            <div>
              <div className="text-[8px] text-slate-600 font-bold">信号</div>
              <span className={`text-xs font-black ${highAlpha.length > 0 ? 'text-emerald-400' : 'text-slate-500'}`}>{highAlpha.length}</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-slate-600" />
            <div>
              <div className="text-[8px] text-slate-600 font-bold">扫描</div>
              <span className="text-xs font-black text-cyan-400 tabular-nums">{totalScanned}</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Grid3X3 className="w-3.5 h-3.5 text-slate-600" />
            <div>
              <div className="text-[8px] text-slate-600 font-bold">调度</div>
              <span className="text-xs font-black" style={{ color: regimeColor }}>{regimeVal}</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-slate-600" />
            <div>
              <div className="text-[8px] text-slate-600 font-bold">决策</div>
              <span className="text-xs font-black" style={{ color: decisionColor }}>{decisionVal}</span>
              {annualizedReturn != null && (
                <div className="text-[7px] text-slate-600 tabular-nums">年化{annualizedReturn}%</div>
              )}
            </div>
          </div>
        </div>

        {aiSummary.summary && aiSummary.summary.length > 1 && (
          <div className="flex items-center gap-2 flex-shrink-0 px-2 border-l border-slate-700/50">
            <Zap className={`w-3.5 h-3.5 ${aiSummary.is_agent ? 'text-cyan-400' : 'text-slate-500'}`} />
            <div className="max-w-[200px]">
              <div className="text-[8px] text-slate-600 font-bold">AI</div>
              <div className={`text-[10px] font-bold truncate ${aiSummary.is_agent ? 'text-cyan-400' : 'text-slate-400'}`}>
                {safe(aiSummary.summary)}
              </div>
            </div>
          </div>
        )}

        <div className="ml-auto flex items-center gap-2 flex-shrink-0 pl-3 border-l border-slate-700/50">
          <div className="relative" ref={notifRef}>
            <button onClick={() => setShowNotifications(!showNotifications)} className="relative p-1.5 hover:bg-slate-800/60 rounded-lg transition-all">
              <Bell className="w-3.5 h-3.5 text-slate-500" />
              {alertCount > 0 && (
                <span className="absolute -top-1 -right-1 min-w-[14px] h-3.5 flex items-center justify-center text-[8px] font-black rounded-full bg-red-500 text-white px-0.5 animate-pulse">
                  {alertCount}
                </span>
              )}
            </button>
            {showNotifications && (
              <div className="absolute right-0 top-8 w-80 shield-glass-elevated rounded-xl border border-slate-700 shadow-2xl z-50 max-h-96 overflow-y-auto animate-scaleIn">
                <div className="p-3 border-b border-slate-700/50 flex items-center justify-between">
                  <span className="text-[9px] font-black text-slate-400 uppercase">通知中心</span>
                  <span className="text-[8px] text-slate-600">{(notifications || []).length} 条</span>
                </div>
                {(notifications || []).length === 0 ? (
                  <div className="p-6 text-[10px] text-slate-500 text-center">暂无通知</div>
                ) : (
                  (notifications || []).slice(0, 15).map((n, i) => {
                    const typeColor = n.type === 'alert' ? 'border-l-red-500' : n.type === 'warn' ? 'border-l-amber-500' : 'border-l-cyan-500';
                    const textColor = n.type === 'alert' ? 'text-red-400' : n.type === 'warn' ? 'text-amber-400' : 'text-cyan-400';
                    return (
                      <div key={i} className={`p-3 border-b border-slate-800/50 border-l-2 ${typeColor} hover:bg-slate-800/30 transition-colors`}>
                        <div className={`text-[10px] font-bold ${textColor}`}>{n.message || n.msg || '--'}</div>
                        <div className="text-[8px] text-slate-600 mt-0.5 font-mono">{n.timestamp || n.time || '--'}</div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            {isConnected ? <Wifi className="w-3 h-3 text-emerald-400" /> : <WifiOff className="w-3 h-3 text-red-500" />}
            <span className={`text-[9px] font-bold tabular-nums ${dataAge > 30 ? 'text-amber-400' : 'text-slate-500'}`}>{dataAge}s</span>
          </div>
          <button onClick={fetchData} className="hover:rotate-180 transition-transform duration-500 p-1 hover:bg-slate-800/60 rounded-lg">
            <RefreshCw className="w-3 h-3 text-slate-500" />
          </button>
        </div>
      </div>

    </div>
  );
};

export default CommandBar;
