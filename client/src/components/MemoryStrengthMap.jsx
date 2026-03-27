import { useState, useEffect } from 'react';
import { Database, Loader2 } from 'lucide-react';

const strengthColor = (s) => {
  if (s >= 0.6) return 'bg-emerald-500';
  if (s >= 0.3) return 'bg-amber-500';
  return 'bg-red-500';
};

const strengthLabel = (s) => {
  if (s >= 0.7) return { text: '强', cls: 'text-emerald-400' };
  if (s >= 0.4) return { text: '中', cls: 'text-amber-400' };
  return { text: '弱', cls: 'text-red-400' };
};

export default function MemoryStrengthMap() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/memory-strengths?limit=50')
      .then(r => r.json())
      .then(d => {
        const sorted = (d.data || []).sort((a, b) => (b.importance || 0) - (a.importance || 0));
        setRecords(sorted);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-4 border border-slate-800">
        <div className="flex items-center gap-2 text-slate-500 text-[10px]">
          <Loader2 className="w-3 h-3 animate-spin" /> 加载记忆强度...
        </div>
      </div>
    );
  }

  return (
    <div className="shield-glass rounded-xl p-4 border border-slate-800">
      <div className="flex items-center gap-2 mb-3">
        <Database className="w-4 h-4 text-cyan-400" />
        <span className="text-[11px] font-black text-white uppercase tracking-wider">记忆强度</span>
        <span className="text-[9px] text-slate-500 ml-auto">{records.length} 条模式</span>
      </div>

      {records.length === 0 ? (
        <div className="text-[10px] text-slate-600 text-center py-6">暂无记忆强度数据 — 等待交易积累模式</div>
      ) : (
        <div className="space-y-1.5 max-h-[400px] overflow-y-auto scrollbar-hide">
          <div className="grid grid-cols-[1fr_80px_50px_60px] gap-2 text-[8px] text-slate-600 font-bold px-2 pb-1 border-b border-slate-800">
            <span>模式</span>
            <span className="text-center">强度</span>
            <span className="text-center">重要性</span>
            <span className="text-center">正确/错误</span>
          </div>
          {records.map((r, i) => {
            const s = Number(r.strength || 0);
            const lbl = strengthLabel(s);
            const patternShort = (r.pattern_key || '').length > 30
              ? (r.pattern_key || '').slice(0, 28) + '…'
              : (r.pattern_key || '');

            return (
              <div key={r.pattern_key || i} className="grid grid-cols-[1fr_80px_50px_60px] gap-2 items-center px-2 py-1.5 rounded bg-slate-900/30 hover:bg-slate-900/60 transition-colors">
                <span className="text-[8px] text-slate-300 font-mono truncate" title={r.pattern_key}>
                  {patternShort}
                </span>
                <div className="flex items-center gap-1.5">
                  <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full transition-all ${strengthColor(s)}`}
                      style={{ width: `${Math.min(100, s * 100)}%` }} />
                  </div>
                  <span className={`text-[7px] font-bold ${lbl.cls}`}>{lbl.text}</span>
                </div>
                <span className="text-[8px] text-amber-400 text-center font-bold">
                  {Number(r.importance || 0).toFixed(1)}
                </span>
                <div className="flex items-center justify-center gap-1 text-[8px]">
                  <span className="text-emerald-400 font-bold">{r.correct_predictions || 0}</span>
                  <span className="text-slate-600">/</span>
                  <span className="text-red-400 font-bold">{r.wrong_predictions || 0}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
