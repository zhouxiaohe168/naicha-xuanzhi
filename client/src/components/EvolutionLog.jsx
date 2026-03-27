import { useState, useEffect } from 'react';
import {
  AlertTriangle, Clock, CheckCircle, XCircle, Loader2,
  RefreshCw, GitBranch, Eye, Shield, Zap, Brain,
  ChevronDown, ChevronUp, Pause
} from 'lucide-react';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const statusBadge = (status) => {
  const map = {
    pending: { cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30', label: '待审核' },
    adopted: { cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', label: '已采纳' },
    rejected: { cls: 'bg-red-500/15 text-red-400 border-red-500/30', label: '已拒绝' },
    hold_pending_data: { cls: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30', label: '观望中' },
    auto_adopted: { cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30', label: '🤖 自动采纳' },
    verified_effective: { cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', label: '✅ 已验证有效' },
    rolled_back: { cls: 'bg-orange-500/15 text-orange-400 border-orange-500/30', label: '↩️ 已回滚' },
    hold_phase1: { cls: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30', label: '观望中' },
  };
  const m = map[status] || { cls: 'bg-slate-700/30 text-slate-400 border-slate-700/40', label: status || '未知' };
  return <span className={`text-[8px] font-black px-1.5 py-0.5 rounded border ${m.cls}`}>{m.label}</span>;
};

const severityBadge = (severity) => {
  if (severity === 'critical') return <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/30">严重</span>;
  if (severity === 'warning') return <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">警告</span>;
  return <span className="text-[8px] font-black px-1.5 py-0.5 rounded bg-slate-700/30 text-slate-400 border border-slate-700/40">信息</span>;
};

export default function EvolutionLog() {
  const [watchdog, setWatchdog] = useState(null);
  const [reviews, setReviews] = useState(null);
  const [darwin, setDarwin] = useState(null);
  const [evolutionLog, setEvolutionLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(null);
  const [expandedEvo, setExpandedEvo] = useState(null);

  const fetchAll = async () => {
    setLoading(true);
    const fetches = [
      fetch('/api/ai/watchdog').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/ai/reviews').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/darwin').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/evolution-log').then(r => r.ok ? r.json() : null).catch(() => null),
    ];
    const [wd, rv, dw, el] = await Promise.all(fetches);
    setWatchdog(wd);
    setReviews(rv);
    setDarwin(dw);
    setEvolutionLog(el?.data || el);
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const handleProposalAction = async (id, action) => {
    setActing(id);
    try {
      const res = await fetch(`/api/evolution-proposals/${id}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, reason: '' }),
      });
      if (res.ok) {
        fetchAll();
      }
    } catch (e) {
      console.error('Proposal action failed:', e);
    } finally {
      setActing(null);
    }
  };

  if (loading) {
    return (
      <div className="shield-glass rounded-xl p-6 border border-slate-800 text-center">
        <Loader2 className="w-5 h-5 animate-spin text-cyan-400 mx-auto mb-2" />
        <div className="text-[10px] text-slate-500">加载进化日志...</div>
      </div>
    );
  }

  const alerts = watchdog?.alerts || watchdog?.active_alerts || [];
  const reviewList = reviews?.reviews || reviews?.recent_reviews || [];
  const deepEvo = evolutionLog?.deep_evolution || [];
  const proposals = evolutionLog?.proposals || [];
  const pendingProposals = proposals.filter(p => p.status === 'pending');
  const decidedProposals = proposals.filter(p => p.status !== 'pending');

  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4 text-violet-400" />
          <span className="text-[11px] font-black text-white uppercase tracking-wider">进化日志</span>
        </div>
        <button
          onClick={fetchAll}
          className="flex items-center gap-1 text-[8px] font-bold px-2 py-1 rounded bg-slate-800/50 text-slate-400 border border-slate-700 hover:text-cyan-400 hover:border-cyan-500/30 transition-all"
        >
          <RefreshCw className="w-2.5 h-2.5" /> 刷新
        </button>
      </div>

      <div className="shield-glass rounded-2xl p-4">
        <div className="text-[9px] text-red-400 font-black uppercase mb-3 flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5" /> 看门狗告警
          {alerts.length > 0 && (
            <span className="text-[8px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full font-bold">{alerts.length}</span>
          )}
        </div>
        {alerts.length === 0 ? (
          <div className="text-center py-4">
            <Shield className="w-6 h-6 text-emerald-500/40 mx-auto mb-1" />
            <div className="text-[10px] text-slate-500">系统运行正常，无活跃告警</div>
          </div>
        ) : (
          <div className="space-y-2 max-h-[30vh] overflow-y-auto">
            {alerts.map((alert, i) => (
              <div key={alert.id || i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-bold text-white">{safe(alert.message || alert.title || alert.type)}</span>
                  {severityBadge(alert.severity)}
                </div>
                <div className="flex items-center gap-3 text-[8px] text-slate-600 mt-1">
                  {alert.timestamp && (
                    <span className="flex items-center gap-0.5">
                      <Clock className="w-2.5 h-2.5" />
                      {new Date(alert.timestamp).toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </span>
                  )}
                  {alert.component && <span>模块: {alert.component}</span>}
                </div>
                {alert.details && (
                  <div className="text-[9px] text-slate-400 mt-1.5 leading-relaxed">{safe(alert.details)}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="shield-glass rounded-2xl p-4">
        <div className="text-[9px] text-violet-400 font-black uppercase mb-3 flex items-center gap-2">
          <Brain className="w-3.5 h-3.5" /> 深度进化时间线
        </div>
        {deepEvo.length === 0 ? (
          <div className="text-center py-4">
            <GitBranch className="w-6 h-6 text-slate-600 mx-auto mb-1" />
            <div className="text-[10px] text-slate-500">暂无深度进化记录</div>
          </div>
        ) : (
          <div className="space-y-2 max-h-[40vh] overflow-y-auto">
            {[...deepEvo].reverse().map((entry, i) => {
              const isExpanded = expandedEvo === i;
              return (
                <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedEvo(isExpanded ? null : i)}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-violet-500 shrink-0" />
                      <span className="text-[10px] font-bold text-white">
                        {entry.summary_text || `进化 #${deepEvo.length - i}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {entry.trades_processed != null && (
                        <span className="text-[8px] text-slate-500">{entry.trades_processed} 笔交易</span>
                      )}
                      {entry.insights_generated != null && (
                        <span className="text-[8px] text-amber-400">{entry.insights_generated} 洞察</span>
                      )}
                      {isExpanded ? <ChevronUp className="w-3 h-3 text-slate-500" /> : <ChevronDown className="w-3 h-3 text-slate-500" />}
                    </div>
                  </div>
                  {entry.timestamp && (
                    <div className="text-[8px] text-slate-600 mt-1 flex items-center gap-1">
                      <Clock className="w-2.5 h-2.5" />
                      {new Date(entry.timestamp).toLocaleString('zh-CN')}
                    </div>
                  )}
                  {isExpanded && entry.ai_analysis_summary && (
                    <div className="mt-2 text-[9px] text-slate-300 leading-relaxed bg-slate-900/50 rounded-lg p-2.5 border border-slate-800/50">
                      {safe(entry.ai_analysis_summary)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="shield-glass rounded-2xl p-4">
        <div className="text-[9px] text-amber-400 font-black uppercase mb-3 flex items-center gap-2">
          <Zap className="w-3.5 h-3.5" /> 优化提案
          {pendingProposals.length > 0 && (
            <span className="text-[8px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded-full font-bold">{pendingProposals.length} 待审</span>
          )}
        </div>
        {proposals.length === 0 ? (
          <div className="text-center py-4">
            <Zap className="w-6 h-6 text-slate-600 mx-auto mb-1" />
            <div className="text-[10px] text-slate-500">暂无优化提案</div>
          </div>
        ) : (
          <div className="space-y-2 max-h-[50vh] overflow-y-auto">
            {pendingProposals.map((p) => (
              <div key={p.id} className="bg-slate-950/60 border border-amber-500/20 rounded-xl p-3">
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      {statusBadge(p.status)}
                      {p.category && <span className="text-[8px] text-slate-500">{p.category}</span>}
                    </div>
                    <div className="text-[10px] font-bold text-white leading-relaxed">{safe(p.title || p.description || p.proposal_text)}</div>
                  </div>
                </div>
                {p.evidence && (
                  <div className="text-[9px] text-slate-400 mt-1 leading-relaxed">{safe(p.evidence)}</div>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <button
                    onClick={() => handleProposalAction(p.id, 'adopt')}
                    disabled={acting === p.id}
                    className="flex items-center gap-1 text-[8px] font-bold px-2.5 py-1.5 rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50 transition-all"
                  >
                    <CheckCircle className="w-2.5 h-2.5" /> 采纳
                  </button>
                  <button
                    onClick={() => handleProposalAction(p.id, 'reject')}
                    disabled={acting === p.id}
                    className="flex items-center gap-1 text-[8px] font-bold px-2.5 py-1.5 rounded-lg bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25 disabled:opacity-50 transition-all"
                  >
                    <XCircle className="w-2.5 h-2.5" /> 拒绝
                  </button>
                  <button
                    onClick={() => handleProposalAction(p.id, 'hold')}
                    disabled={acting === p.id}
                    className="flex items-center gap-1 text-[8px] font-bold px-2.5 py-1.5 rounded-lg bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/25 disabled:opacity-50 transition-all"
                  >
                    <Pause className="w-2.5 h-2.5" /> 观望
                  </button>
                  {acting === p.id && <Loader2 className="w-3 h-3 animate-spin text-slate-400" />}
                </div>
                {p.created_at && (
                  <div className="text-[8px] text-slate-600 mt-1.5 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    {new Date(p.created_at).toLocaleString('zh-CN')}
                  </div>
                )}
                {p.source && p.source.startsWith('memory_bank') && (
                  <span className="text-[7px] font-bold px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-400 border border-purple-500/30 mt-1 inline-block">🧠 记忆衍生</span>
                )}
              </div>
            ))}
            {decidedProposals.length > 0 && (
              <>
                <div className="text-[8px] text-slate-600 font-bold uppercase mt-3 mb-1">已处理</div>
                {decidedProposals.slice(0, 10).map((p) => (
                  <div key={p.id} className={`bg-slate-950/60 border rounded-xl p-3 opacity-70 ${p.status === 'rolled_back' ? 'border-orange-500/20' : p.status === 'verified_effective' ? 'border-emerald-500/20' : 'border-slate-800'}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {statusBadge(p.status)}
                        <span className="text-[10px] text-slate-300">{safe(p.title || p.description || p.proposal_text)}</span>
                      </div>
                      {p.created_at && (
                        <span className="text-[8px] text-slate-600">{new Date(p.created_at).toLocaleDateString('zh-CN')}</span>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 mt-1.5 text-[8px]">
                      {p.baseline_win_rate != null && (
                        <span className="text-slate-500">基准胜率: <span className="text-cyan-400 font-bold">{(p.baseline_win_rate * 100).toFixed(1)}%</span></span>
                      )}
                      {p.result_7d != null && (
                        <span className="text-slate-500">7天效果: <span className={`font-bold ${p.result_7d >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{p.result_7d > 0 ? '+' : ''}{(p.result_7d * 100).toFixed(1)}%</span></span>
                      )}
                      {p.review_due_at && p.status === 'auto_adopted' && (
                        <span className="text-slate-500">效果验证: <span className="text-amber-400 font-bold">{Math.max(0, Math.ceil((new Date(p.review_due_at) - new Date()) / 86400000))}天后</span></span>
                      )}
                    </div>
                    {p.notes && (
                      <div className="text-[8px] text-slate-500 mt-1">{safe(p.notes)}</div>
                    )}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      <div className="shield-glass rounded-2xl p-4">
        <div className="text-[9px] text-cyan-400 font-black uppercase mb-3 flex items-center gap-2">
          <Eye className="w-3.5 h-3.5" /> AI 审查记录
        </div>
        {(!reviewList || reviewList.length === 0) ? (
          <div className="text-center py-4">
            <Eye className="w-6 h-6 text-slate-600 mx-auto mb-1" />
            <div className="text-[10px] text-slate-500">暂无 AI 审查记录</div>
          </div>
        ) : (
          <div className="space-y-2 max-h-[30vh] overflow-y-auto">
            {reviewList.slice(0, 10).map((review, i) => (
              <div key={i} className="bg-slate-950/60 border border-slate-800 rounded-xl p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-bold text-white">
                    {safe(review.summary || review.title || `审查 #${i + 1}`)}
                  </span>
                  {review.score != null && (
                    <span className={`text-[9px] font-black ${review.score >= 70 ? 'text-emerald-400' : review.score >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                      {review.score}分
                    </span>
                  )}
                </div>
                {review.timestamp && (
                  <div className="text-[8px] text-slate-600 flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    {new Date(review.timestamp).toLocaleString('zh-CN')}
                  </div>
                )}
                {review.recommendations && Array.isArray(review.recommendations) && review.recommendations.length > 0 && (
                  <div className="mt-1.5 space-y-0.5">
                    {review.recommendations.slice(0, 3).map((rec, j) => (
                      <div key={j} className="text-[8px] text-slate-400 flex items-start gap-1">
                        <span className="text-amber-500 shrink-0">•</span>
                        <span>{safe(rec)}</span>
                      </div>
                    ))}
                  </div>
                )}
                {typeof review.analysis === 'string' && (
                  <div className="text-[9px] text-slate-400 mt-1 leading-relaxed">{review.analysis}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {darwin && (
        <div className="shield-glass rounded-2xl p-4">
          <div className="text-[9px] text-emerald-400 font-black uppercase mb-3 flex items-center gap-2">
            <GitBranch className="w-3.5 h-3.5" /> 达尔文进化状态
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">状态</div>
              <div className={`text-sm font-black ${darwin.running ? 'text-amber-400' : darwin.enabled ? 'text-emerald-400' : 'text-slate-500'}`}>
                {darwin.running ? '运行中' : darwin.enabled ? '已启用' : '已禁用'}
              </div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">总代数</div>
              <div className="text-sm font-black text-cyan-400">{darwin.total_generations ?? darwin.generations ?? '--'}</div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">最佳适应度</div>
              <div className="text-sm font-black text-violet-400">{darwin.best_fitness?.toFixed(4) ?? '--'}</div>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
              <div className="text-[9px] text-slate-500 font-black uppercase">突变率</div>
              <div className="text-sm font-black text-amber-400">{darwin.mutation_rate ? `${(darwin.mutation_rate * 100).toFixed(1)}%` : '--'}</div>
            </div>
          </div>
          {darwin.best_params && (
            <div className="mt-3 bg-slate-950/60 border border-slate-800 rounded-xl p-3">
              <div className="text-[8px] text-slate-500 font-bold mb-1.5">最优参数</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 text-[9px]">
                {Object.entries(darwin.best_params).map(([k, v]) => (
                  <div key={k} className="flex justify-between">
                    <span className="text-slate-500">{k}</span>
                    <span className="text-white font-mono">{typeof v === 'number' ? v.toFixed(4) : safe(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}