import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, CrosshairMode, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

const TIMEFRAMES = [
  { label: '15m', value: '15m' },
  { label: '1H', value: '1h' },
  { label: '4H', value: '4h' },
  { label: '1D', value: '1d' },
  { label: '1W', value: '1w' },
];

export default function KLineChart({ symbol, onClose }) {
  const chartRef = useRef(null);
  const containerRef = useRef(null);
  const [timeframe, setTimeframe] = useState('4h');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastPrice, setLastPrice] = useState(null);
  const [priceChange, setPriceChange] = useState(null);

  const sym = symbol?.replace('/USDT', '').replace('_USDT', '') || 'BTC';

  const fetchAndRender = useCallback(async (tf) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/kline/${sym}?timeframe=${tf}&limit=300`);
      if (!res.ok) throw new Error('数据获取失败');
      const data = await res.json();
      const candles = data.candles || [];
      if (candles.length === 0) throw new Error('暂无数据');

      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }

      const container = containerRef.current;
      if (!container) return;

      const chart = createChart(container, {
        width: container.clientWidth,
        height: container.clientHeight,
        layout: {
          background: { type: ColorType.Solid, color: 'transparent' },
          textColor: '#94a3b8',
          fontSize: 10,
          fontFamily: 'JetBrains Mono, monospace',
        },
        grid: {
          vertLines: { color: 'rgba(51, 65, 85, 0.3)' },
          horzLines: { color: 'rgba(51, 65, 85, 0.3)' },
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: 'rgba(251, 191, 36, 0.4)', width: 1, style: 2 },
          horzLine: { color: 'rgba(251, 191, 36, 0.4)', width: 1, style: 2 },
        },
        timeScale: {
          borderColor: 'rgba(51, 65, 85, 0.5)',
          timeVisible: true,
          secondsVisible: false,
        },
        rightPriceScale: {
          borderColor: 'rgba(51, 65, 85, 0.5)',
        },
        handleScroll: { vertTouchDrag: false },
      });

      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#10b981',
        downColor: '#ef4444',
        borderUpColor: '#10b981',
        borderDownColor: '#ef4444',
        wickUpColor: '#10b981',
        wickDownColor: '#ef4444',
      });
      candleSeries.setData(candles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })));

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });
      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });
      volumeSeries.setData(candles.map(c => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)',
      })));

      chart.timeScale().fitContent();
      chartRef.current = chart;

      const last = candles[candles.length - 1];
      const first = candles[0];
      setLastPrice(last.close);
      const change = ((last.close - first.open) / first.open) * 100;
      setPriceChange(change);

      const handleResize = () => {
        if (container && chart) {
          chart.applyOptions({ width: container.clientWidth });
        }
      };
      const ro = new ResizeObserver(handleResize);
      ro.observe(container);

      chart._ro = ro;
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sym]);

  useEffect(() => {
    fetchAndRender(timeframe);
    return () => {
      if (chartRef.current) {
        if (chartRef.current._ro) chartRef.current._ro.disconnect();
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [timeframe, fetchAndRender]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fadeIn" onClick={onClose}>
      <div className="w-[95vw] max-w-5xl h-[80vh] max-h-[600px] bg-slate-950 border border-slate-800 rounded-2xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-black text-white">{sym}/USDT</h3>
            {lastPrice != null && (
              <span className="text-sm font-bold text-slate-300 font-mono tabular-nums">${lastPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}</span>
            )}
            {priceChange != null && (
              <span className={`text-xs font-bold px-2 py-0.5 rounded ${priceChange >= 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <div className="flex bg-slate-900 rounded-lg p-0.5 gap-0.5">
              {TIMEFRAMES.map(tf => (
                <button
                  key={tf.value}
                  onClick={() => setTimeframe(tf.value)}
                  className={`px-2.5 py-1 rounded-md text-[10px] font-bold transition-all ${
                    timeframe === tf.value
                      ? 'bg-amber-500 text-black shadow-lg shadow-amber-500/20'
                      : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  {tf.label}
                </button>
              ))}
            </div>
            <button onClick={onClose} className="ml-2 w-7 h-7 flex items-center justify-center rounded-lg bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-all text-sm font-bold">
              ✕
            </button>
          </div>
        </div>

        <div className="flex-1 relative">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center z-10 bg-slate-950/80">
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <div className="w-4 h-4 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                加载中...
              </div>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center z-10">
              <div className="text-red-400 text-sm">{error}</div>
            </div>
          )}
          <div ref={containerRef} className="w-full h-full" />
        </div>
      </div>
    </div>
  );
}
