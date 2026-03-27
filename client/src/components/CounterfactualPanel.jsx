import { useState, useEffect } from 'react';
import { GitBranch, Loader2 } from 'lucide-react';

const lessonConfig = {
  sl_too_tight: { label: 'SL过窄', emoji: '🟠', cls: 'bg-orange-500/20 text-orange-400' },
  trailing_sl_too_late: { label: '止盈太晚', emoji: '🟡', cls: 'bg-amber-500/20 text-amber-400' },
  signal_quality_poor: { label: '信号质量差', emoji: '🔴', cls: 'bg-red-500/20 text-red-400' },
  correct_decision: { label: '决策正确', emoji: '🟢', cls: 'bg-emerald-500/20 text-emerald-400' },
  held_too_short: { label: '持仓太短', emoji: '🔵', cls: 'bg-blue-500/20 text-blue-400' },
};

export default function CounterfactualPanel() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/counterfactuals?limit=10')
      .then(r => r.json())
      .then(d => setRecords(d.data || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-4 border border-slate-800">
        <div className="flex items-center gap-2 text-slate-500 text-[10px]">
          <Loader2 className="w-3 h-3 animate-spin" /> 加载反事实分析...
        </div>
      </div>
    );
  }

  return (
    <div className="shield-glass rounded-xl p-4 border border-slate-800">
      <div className="flex items-center gap-2 mb-3">
        <GitBranch className="w-4 h-4 text-amber-400" />
        <span className="text-[11px] font-black text-white uppercase tracking-wider">反事实推理</span>
        <span className="text-[9px] text-slate-500 ml-auto">{records.length} 笔</span>
      </div>

      {records.length === 0 ? (
        <div className="text-[10px] text-slate-600 text-center py-6">暂无反事实记录 — 等待平仓触发分析</div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto scrollbar-hide">
          {records.map((r, i) => {
            const lessons = r.primary_lessons || [];
            const analysis = r.analysis_json || {};
            const earlyTp = analysis.early_tp || {};

            return (
              <div key={r.id || i} className="bg-slate-900/50 rounded-lg p-3 border border-slate-800/50">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-bold text-cyan-400">{r.symbol || '--'}</span>
                    <span className={`text-[8px] px-1.5 py-0.5 rounded font-bold ${
                      r.direction === 'long' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'
                    }`}>{r.direction === 'long' ? '多' : '空'}</span>
                  </div>
                  <span className={`text-[10px] font-bold ${
                    (r.pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {(r.pnl_pct || 0) > 0 ? '+' : ''}{Number(r.pnl_pct || 0).toFixed(2)}%
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-x-4 gap-y-1 mb-2 text-[8px]">
                  <div className="text-slate-500">
                    实际PnL: <span className={`font-bold ${(earlyTp.actual_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {Number(earlyTp.actual_pnl || 0).toFixed(2)}%
                    </span>
                  </div>
                  <div className="text-slate-500">
                    如果早止盈: <span className={`font-bold ${(earlyTp.could_have || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {Number(earlyTp.could_have || 0).toFixed(2)}%
                    </span>
                    {earlyTp.better && <span className="text-amber-400 ml-1">↑</span>}
                  </div>
                  <div className="text-slate-500">
                    宽SL存活: <span className={`font-bold ${r.wider_sl_survives ? 'text-emerald-400' : 'text-red-400'}`}>
                      {r.wider_sl_survives ? '是' : '否'}
                    </span>
                  </div>
                  <div className="text-slate-500">
                    峰值回吐: <span className="font-bold text-amber-400">
                      {Number(r.peak_giveback_pct || 0).toFixed(2)}%
                    </span>
                  </div>
                </div>

                <div className="flex flex-wrap gap-1">
                  {lessons.map((lesson, j) => {
                    const cfg = lessonConfig[lesson] || { label: lesson, emoji: '⚪', cls: 'bg-slate-500/20 text-slate-400' };
                    return (
                      <span key={j} className={`text-[7px] font-bold px-1.5 py-0.5 rounded ${cfg.cls}`}>
                        {cfg.emoji} {cfg.label}
                      </span>
                    );
                  })}
                </div>

                <div className="text-[7px] text-slate-600 mt-1">
                  {r.created_at ? new Date(r.created_at).toLocaleString('zh-CN') : ''}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
