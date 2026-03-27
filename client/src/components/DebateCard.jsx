import { useState, useEffect } from 'react';
import { Brain, ThumbsUp, ThumbsDown, Loader2 } from 'lucide-react';

export default function DebateCard() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/debate-records?limit=20')
      .then(r => r.json())
      .then(d => setRecords(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const verdictStyle = (v) => {
    if (v === 'execute') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
    if (v === 'reduce_size') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
    return 'bg-red-500/20 text-red-400 border-red-500/30';
  };

  const verdictLabel = (v) => {
    if (v === 'execute') return '执行';
    if (v === 'reduce_size') return '减仓';
    return '拒绝';
  };

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-4 border border-slate-800">
        <div className="flex items-center gap-2 text-slate-500 text-[10px]">
          <Loader2 className="w-3 h-3 animate-spin" /> 加载辩论记录...
        </div>
      </div>
    );
  }

  return (
    <div className="shield-glass rounded-xl p-4 border border-slate-800">
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-purple-400" />
        <span className="text-[11px] font-black text-white uppercase tracking-wider">辩论记录</span>
        <span className="text-[9px] text-slate-500 ml-auto">{records.length} 条</span>
      </div>

      {records.length === 0 ? (
        <div className="text-[10px] text-slate-600 text-center py-6">暂无辩论记录 — 等待下一次开仓触发</div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto scrollbar-hide">
          {records.map((r, i) => (
            <div key={r.id || i} className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold text-cyan-400">{r.symbol || r.trade_symbol || '--'}</span>
                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full border ${verdictStyle(r.verdict)}`}>
                  {verdictLabel(r.verdict)}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 mb-2">
                <div>
                  <div className="text-[8px] text-slate-600 mb-0.5 flex items-center gap-1">
                    <ThumbsUp className="w-2.5 h-2.5 text-emerald-500" /> 多头
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500/70 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (r.bull_score || 0))}%` }} />
                  </div>
                  <span className="text-[8px] text-emerald-400">{(r.bull_score || 0).toFixed(0)}</span>
                </div>
                <div>
                  <div className="text-[8px] text-slate-600 mb-0.5 flex items-center gap-1">
                    <ThumbsDown className="w-2.5 h-2.5 text-red-500" /> 空头
                  </div>
                  <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-red-500/70 rounded-full transition-all"
                      style={{ width: `${Math.min(100, (r.bear_score || 0))}%` }} />
                  </div>
                  <span className="text-[8px] text-red-400">{(r.bear_score || 0).toFixed(0)}</span>
                </div>
              </div>

              <div className="flex items-center gap-3 text-[8px]">
                <span className="text-slate-500">置信度: <span className="text-amber-400 font-bold">{((r.confidence || 0) * 100).toFixed(0)}%</span></span>
                {r.risk_level && (
                  <span className={`px-1.5 py-0.5 rounded text-[7px] font-bold ${
                    r.risk_level === 'low' ? 'bg-emerald-500/15 text-emerald-400' :
                    r.risk_level === 'medium' ? 'bg-amber-500/15 text-amber-400' :
                    'bg-red-500/15 text-red-400'
                  }`}>风险:{r.risk_level === 'low' ? '低' : r.risk_level === 'medium' ? '中' : r.risk_level === 'high' ? '高' : r.risk_level}</span>
                )}
                {r.pnl_pct != null && (
                  <span className={`font-bold ${r.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    盈亏: {r.pnl_pct > 0 ? '+' : ''}{Number(r.pnl_pct).toFixed(2)}%
                  </span>
                )}
              </div>

              <div className="text-[7px] text-slate-600 mt-1">
                {r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
