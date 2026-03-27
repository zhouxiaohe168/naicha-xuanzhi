import React, { useState, useEffect } from 'react';
import { Target, RefreshCw, TrendingUp, TrendingDown, Grid3x3, Shield, Brain, Layers, ChevronDown, ChevronUp, Crosshair, AlertTriangle } from 'lucide-react';
import { useShield } from '../hooks/useShieldData';

const safe = (v) => v == null ? '--' : typeof v === 'object' ? JSON.stringify(v) : v;

const gradeColors = {
  A: 'text-emerald-400 bg-emerald-500/15 border-emerald-500/30',
  B: 'text-blue-400 bg-blue-500/15 border-blue-500/30',
  C: 'text-amber-400 bg-amber-500/15 border-amber-500/30',
  D: 'text-orange-400 bg-orange-500/15 border-orange-500/30',
  F: 'text-red-400 bg-red-500/15 border-red-500/30',
};

const TradeModal = () => {
  const { tradeModal, setTradeModal, tradePreview, setTradePreview, previewLoading, confirmTrade } = useShield();

  const [editPrice, setEditPrice] = useState('');
  const [editTp, setEditTp] = useState('');
  const [editSl, setEditSl] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [showChain, setShowChain] = useState(false);
  const [showPartialPlan, setShowPartialPlan] = useState(false);

  useEffect(() => {
    if (tradePreview) {
      setEditPrice(tradePreview.price ?? '');
      setEditTp(tradePreview.tp_price ?? '');
      setEditSl(tradePreview.sl_price ?? '');
      setEditAmount(tradePreview.recommended_amount ?? '');
    }
  }, [tradePreview]);

  if (!tradeModal) return null;

  const close = () => { setTradeModal(null); setTradePreview(null); };

  const handleConfirm = () => {
    confirmTrade({
      entry_price: parseFloat(editPrice) || tradePreview.price,
      tp_price: parseFloat(editTp) || tradePreview.tp_price,
      sl_price: parseFloat(editSl) || tradePreview.sl_price,
      amount: parseFloat(editAmount) || tradePreview.recommended_amount,
    });
  };

  const opScores = tradePreview?.operation_scores || {};
  const recOp = tradePreview?.recommended_operation || '';
  const opConf = tradePreview?.operation_confidence || 0;
  const riskGrade = tradePreview?.risk_grade || {};
  const decisionChain = tradePreview?.decision_chain || [];
  const partialPlan = tradePreview?.partial_tp_plan || {};
  const entryStrategy = tradePreview?.entry_strategy || {};
  const aiReview = tradePreview?.ai_risk_review || {};
  const mlProbs = tradePreview?.ml_probabilities || {};

  const opIcons = {
    "做多": <TrendingUp className="w-4 h-4" />,
    "做空": <TrendingDown className="w-4 h-4" />,
    "网格": <Grid3x3 className="w-4 h-4" />,
  };
  const opColors = {
    "做多": "text-emerald-400 border-emerald-500/30 bg-emerald-500/10",
    "做空": "text-red-400 border-red-500/30 bg-red-500/10",
    "网格": "text-blue-400 border-blue-500/30 bg-blue-500/10",
  };

  const inputClass = "w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm font-mono text-white focus:border-amber-500 focus:outline-none transition-colors";

  const computedRR = editPrice && editTp && editSl
    ? (Math.abs(parseFloat(editTp) - parseFloat(editPrice)) / (Math.abs(parseFloat(editSl) - parseFloat(editPrice)) || 1)).toFixed(2)
    : tradePreview?.risk_reward || 0;

  const computedRisk = editAmount && editPrice && editSl
    ? (parseFloat(editAmount) * Math.abs(parseFloat(editSl) - parseFloat(editPrice)) / (parseFloat(editPrice) || 1)).toFixed(2)
    : tradePreview?.risk_amount || 0;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fadeIn"
        onClick={close}
      >
        <div
          className="shield-glass border border-slate-700 rounded-3xl p-5 max-w-lg w-full max-h-[90vh] overflow-y-auto"
          onClick={e => e.stopPropagation()}
        >
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-black flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-500" />
              {tradeModal.symbol} 一键{tradeModal.direction === 'long' ? '做多' : '做空'}
            </h3>
            <button onClick={close} className="text-slate-500 hover:text-white text-xl">&times;</button>
          </div>

          {previewLoading && (
            <div className="text-center py-10">
              <RefreshCw className="w-8 h-8 text-amber-500 animate-spin mx-auto mb-3" />
              <p className="text-slate-400 text-sm">AI 5层决策引擎分析中...</p>
              <p className="text-slate-600 text-[10px] mt-1">信号评估 → ML研判 → 环境匹配 → 智能定价 → 风控审查</p>
            </div>
          )}

          {tradePreview && !previewLoading && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <div className={`flex-1 p-3 rounded-2xl border text-center ${
                  tradePreview.verdict === 'BUY' ? 'bg-emerald-500/10 border-emerald-500/30' :
                  tradePreview.verdict === 'CAUTION' ? 'bg-amber-500/10 border-amber-500/30' :
                  'bg-red-500/10 border-red-500/30'
                }`}>
                  <div className="text-xl font-black mb-0.5">{safe(tradePreview.verdict_text)}</div>
                  <div className="text-[9px] text-slate-400">5层决策引擎研判</div>
                </div>
                {riskGrade.grade && (
                  <div className={`w-20 p-3 rounded-2xl border text-center ${gradeColors[riskGrade.grade] || gradeColors.C}`}>
                    <div className="text-2xl font-black">{riskGrade.grade}</div>
                    <div className="text-[8px]">风险评级</div>
                  </div>
                )}
              </div>

              {mlProbs && Object.keys(mlProbs).length > 0 && (
                <div className="p-2.5 rounded-xl border border-slate-700 bg-slate-950">
                  <div className="text-[9px] text-violet-400 font-bold mb-2 flex items-center gap-1">
                    <Brain className="w-3 h-3" /> ML概率分布
                  </div>
                  <div className="flex gap-1">
                    {[
                      { label: '涨', prob: mlProbs['涨'] || 0, color: 'bg-emerald-500' },
                      { label: '横盘', prob: mlProbs['横盘'] || 0, color: 'bg-slate-500' },
                      { label: '跌', prob: mlProbs['跌'] || 0, color: 'bg-red-500' },
                    ].map(item => (
                      <div key={item.label} className="flex-1">
                        <div className="flex justify-between text-[9px] mb-0.5">
                          <span className="text-slate-400">{item.label}</span>
                          <span className="text-white font-mono">{item.prob.toFixed(0)}%</span>
                        </div>
                        <div className="w-full bg-slate-800 rounded-full h-1.5">
                          <div className={`h-1.5 rounded-full ${item.color}`}
                            style={{ width: `${Math.min(item.prob, 100)}%` }}></div>
                        </div>
                      </div>
                    ))}
                  </div>
                  {tradePreview.direction_prob > 0 && (
                    <div className="text-center text-[9px] text-slate-400 mt-1.5">
                      方向概率 <span className="text-white font-bold">{tradePreview.direction_prob.toFixed(0)}%</span>
                      {tradePreview.meta_trade === false && (
                        <span className="text-red-400 ml-2">Meta-Labeler: 不建议交易</span>
                      )}
                    </div>
                  )}
                </div>
              )}

              {recOp && (
                <div className="p-2.5 rounded-xl border border-slate-700 bg-slate-950">
                  <div className="text-[9px] text-slate-500 font-bold mb-2">AI操作建议</div>
                  <div className="grid grid-cols-3 gap-2">
                    {["做多", "做空", "网格"].map(op => {
                      const isRec = op === recOp;
                      const score = opScores[op] || 0;
                      const maxScore = Math.max(...Object.values(opScores), 1);
                      return (
                        <div key={op} className={`relative p-2 rounded-lg border text-center transition-all ${
                          isRec ? opColors[op] + ' ring-1 ring-offset-1 ring-offset-slate-950' : 'border-slate-800 bg-slate-900/50'
                        }`}>
                          <div className="flex items-center justify-center gap-1 mb-1">
                            {opIcons[op]}
                            <span className={`text-xs font-bold ${isRec ? '' : 'text-slate-400'}`}>{op}</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5 mb-1">
                            <div className={`h-1.5 rounded-full transition-all ${
                              op === "做多" ? 'bg-emerald-500' : op === "做空" ? 'bg-red-500' : 'bg-blue-500'
                            }`} style={{ width: `${(score / maxScore) * 100}%` }}></div>
                          </div>
                          <div className={`text-[10px] font-mono ${isRec ? 'font-bold' : 'text-slate-500'}`}>
                            {score.toFixed(0)}分
                          </div>
                          {isRec && (
                            <div className="absolute -top-1.5 -right-1.5 bg-amber-500 text-black text-[8px] font-black px-1.5 py-0.5 rounded-full">
                              推荐
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <div className="text-center text-[10px] text-slate-400 mt-1.5">
                    推荐 <span className="text-white font-bold">{recOp}</span> · 置信度 <span className="text-amber-400 font-bold">{opConf.toFixed(0)}%</span>
                  </div>
                </div>
              )}

              <div className="p-2.5 rounded-xl border border-slate-700 bg-slate-950">
                <div className="text-[9px] text-amber-500 font-bold mb-2 flex items-center gap-1">
                  <Crosshair className="w-3 h-3" /> 交易参数
                  {entryStrategy.type && (
                    <span className={`ml-auto text-[8px] px-1.5 py-0.5 rounded ${
                      entryStrategy.type === 'market' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-blue-500/20 text-blue-400'
                    }`}>
                      {entryStrategy.type === 'market' ? '市价入场' : '限价入场'}
                    </span>
                  )}
                </div>
                {entryStrategy.description && (
                  <div className="text-[9px] text-slate-400 mb-2 bg-slate-800/50 rounded px-2 py-1">
                    {entryStrategy.description}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[9px] text-slate-500 font-bold block mb-0.5">入场价格</label>
                    <input type="number" step="any" value={editPrice}
                      onChange={e => setEditPrice(e.target.value)} className={inputClass} />
                  </div>
                  <div>
                    <label className="text-[9px] text-slate-500 font-bold block mb-0.5">买入金额 ($)</label>
                    <input type="number" step="any" value={editAmount}
                      onChange={e => setEditAmount(e.target.value)} className={inputClass} />
                  </div>
                  <div>
                    <label className="text-[9px] text-emerald-500 font-bold block mb-0.5">
                      止盈价格
                      {tradePreview.tp_distance_pct > 0 && (
                        <span className="text-slate-500 ml-1">+{tradePreview.tp_distance_pct}%</span>
                      )}
                    </label>
                    <input type="number" step="any" value={editTp}
                      onChange={e => setEditTp(e.target.value)}
                      className={`${inputClass} focus:border-emerald-500`} />
                  </div>
                  <div>
                    <label className="text-[9px] text-red-500 font-bold block mb-0.5">
                      止损价格
                      {tradePreview.sl_distance_pct > 0 && (
                        <span className="text-slate-500 ml-1">-{tradePreview.sl_distance_pct}%</span>
                      )}
                    </label>
                    <input type="number" step="any" value={editSl}
                      onChange={e => setEditSl(e.target.value)}
                      className={`${inputClass} focus:border-red-500`} />
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 mt-2">
                  <div className="bg-slate-800/50 rounded-lg p-1.5 text-center">
                    <div className="text-[8px] text-slate-500">盈亏比</div>
                    <div className={`text-sm font-black ${
                      parseFloat(computedRR) >= 2 ? 'text-emerald-400' :
                      parseFloat(computedRR) >= 1.5 ? 'text-blue-400' : 'text-amber-400'
                    }`}>{computedRR}:1</div>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-1.5 text-center">
                    <div className="text-[8px] text-slate-500">风险金额</div>
                    <div className="text-sm font-black text-red-400">${computedRisk}</div>
                  </div>
                  <div className="bg-slate-800/50 rounded-lg p-1.5 text-center">
                    <div className="text-[8px] text-slate-500">方向概率</div>
                    <div className={`text-sm font-black ${
                      (tradePreview.direction_prob || 0) >= 60 ? 'text-emerald-400' :
                      (tradePreview.direction_prob || 0) >= 45 ? 'text-amber-400' : 'text-red-400'
                    }`}>{(tradePreview.direction_prob || 0).toFixed(0)}%</div>
                  </div>
                </div>
              </div>

              {partialPlan.stage1 && (
                <div className="rounded-xl border border-slate-700 bg-slate-950 overflow-hidden">
                  <button onClick={() => setShowPartialPlan(!showPartialPlan)}
                    className="w-full p-2 flex items-center justify-between text-[9px] text-cyan-400 font-bold hover:bg-slate-800/50">
                    <span className="flex items-center gap-1">
                      <Layers className="w-3 h-3" /> 分段止盈计划
                    </span>
                    {showPartialPlan ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  {showPartialPlan && (
                    <div className="px-2.5 pb-2.5 space-y-1.5">
                      <div className="flex items-center gap-2 text-[9px]">
                        <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[8px] font-bold">1</span>
                        <div className="flex-1">
                          <span className="text-white">{partialPlan.stage1.description}</span>
                          <span className="text-slate-500 ml-1">@ {partialPlan.stage1.trigger_price}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-[9px]">
                        <span className="w-5 h-5 rounded-full bg-cyan-500/20 text-cyan-400 flex items-center justify-center text-[8px] font-bold">2</span>
                        <div className="flex-1">
                          <span className="text-white">{partialPlan.stage2.description}</span>
                          <span className="text-slate-500 ml-1">@ {partialPlan.stage2.trigger_price}</span>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 text-[9px]">
                        <span className="w-5 h-5 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center text-[8px] font-bold">3</span>
                        <div className="flex-1 text-white">{partialPlan.remaining?.description}</div>
                      </div>
                      <div className="text-[8px] text-slate-500 mt-1">
                        保本触发: 价格到达 {partialPlan.breakeven_trigger} 后止损移至入场价
                      </div>
                    </div>
                  )}
                </div>
              )}

              {aiReview.approval_score != null && (
                <div className={`p-2.5 rounded-xl border ${
                  aiReview.approval_score >= 60 ? 'bg-emerald-500/5 border-emerald-500/20' :
                  aiReview.approval_score >= 30 ? 'bg-amber-500/5 border-amber-500/20' :
                  'bg-red-500/5 border-red-500/20'
                }`}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="text-[9px] font-bold flex items-center gap-1">
                      <Shield className="w-3 h-3 text-amber-500" />
                      <span className="text-amber-500">AI首席风控官审查</span>
                    </div>
                    <div className={`text-xs font-black px-2 py-0.5 rounded-full ${
                      aiReview.approval_score >= 60 ? 'bg-emerald-500/20 text-emerald-400' :
                      aiReview.approval_score >= 30 ? 'bg-amber-500/20 text-amber-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      {aiReview.approval_score}分
                    </div>
                  </div>
                  {aiReview.suggestion && (
                    <div className="text-xs text-white font-bold mb-1">{aiReview.suggestion}</div>
                  )}
                  {aiReview.review_points && (
                    <div className="space-y-0.5">
                      {aiReview.review_points.slice(0, 3).map((pt, i) => (
                        <div key={i} className="text-[9px] text-slate-300">• {pt}</div>
                      ))}
                    </div>
                  )}
                  {aiReview.risk_level && (
                    <div className="text-[8px] text-slate-500 mt-1">
                      风险级别: <span className={`font-bold ${
                        aiReview.risk_level === 'low' ? 'text-emerald-400' :
                        aiReview.risk_level === 'medium' ? 'text-amber-400' :
                        aiReview.risk_level === 'high' ? 'text-orange-400' : 'text-red-400'
                      }`}>{aiReview.risk_level}</span>
                    </div>
                  )}
                </div>
              )}

              <div className="space-y-1">
                {tradePreview.reasons?.map((r, i) => (
                  <div key={i} className="text-[10px] text-slate-300 bg-slate-950 px-2.5 py-1.5 rounded-lg">{safe(r)}</div>
                ))}
              </div>

              {decisionChain.length > 0 && (
                <div className="rounded-xl border border-slate-700 bg-slate-950 overflow-hidden">
                  <button onClick={() => setShowChain(!showChain)}
                    className="w-full p-2 flex items-center justify-between text-[9px] text-indigo-400 font-bold hover:bg-slate-800/50">
                    <span className="flex items-center gap-1">
                      <Layers className="w-3 h-3" /> 5层决策链路 ({decisionChain.length}步)
                    </span>
                    {showChain ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  {showChain && (
                    <div className="px-2.5 pb-2.5 space-y-1">
                      {decisionChain.map((step, i) => (
                        <div key={i} className="text-[9px] text-slate-400 flex gap-1.5">
                          <span className="text-indigo-500 font-mono min-w-[14px]">{i + 1}.</span>
                          <span>{step}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="grid grid-cols-4 gap-1.5 text-center text-[9px]">
                <div className="bg-slate-950 p-1.5 rounded-lg">
                  <div className="text-slate-600">评分</div>
                  <div className={`font-black ${tradePreview.signal_score >= 80 ? 'text-emerald-400' : 'text-amber-400'}`}>{safe(tradePreview.signal_score)}</div>
                </div>
                <div className="bg-slate-950 p-1.5 rounded-lg">
                  <div className="text-slate-600">ML置信</div>
                  <div className="font-black text-violet-400">{safe(tradePreview.ml_confidence)}%</div>
                </div>
                <div className="bg-slate-950 p-1.5 rounded-lg">
                  <div className="text-slate-600">FNG</div>
                  <div className="font-black">{safe(tradePreview.fng)}</div>
                </div>
                <div className="bg-slate-950 p-1.5 rounded-lg">
                  <div className="text-slate-600">环境</div>
                  <div className="font-black text-cyan-400">{safe(tradePreview.regime)}</div>
                </div>
              </div>

              <div className="flex gap-2 pt-1">
                <button onClick={close} className="flex-1 bg-slate-800 text-slate-300 font-bold text-sm py-3 rounded-xl hover:bg-slate-700 transition-all">
                  取消
                </button>
                {tradePreview.verdict !== 'SKIP' && parseFloat(editAmount) > 0 && (
                  <button
                    onClick={handleConfirm}
                    className={`flex-1 font-black text-sm py-3 rounded-xl transition-all ${
                      tradePreview.verdict === 'BUY'
                        ? 'bg-emerald-500 text-black hover:bg-emerald-400'
                        : 'bg-amber-500 text-black hover:bg-amber-400'
                    }`}
                  >
                    确认{tradeModal.direction === 'long' ? '做多' : '做空'} ${parseFloat(editAmount).toFixed(2)}
                  </button>
                )}
                {tradePreview.verdict === 'SKIP' && (
                  <button disabled className="flex-1 bg-red-500/20 text-red-400 font-bold text-sm py-3 rounded-xl cursor-not-allowed">
                    AI不建议交易
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default TradeModal;
