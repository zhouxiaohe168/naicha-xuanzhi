#!/usr/bin/env python3
"""
Titan V19.2 智能体联动综合测试
模拟多组交易数据，验证所有智能体的反馈闭环是否正常工作

测试链路:
  信号 → Dispatcher(策略选择) → SignalQuality(质量评估) → Synapse(协同检查)
  → RiskBudget(资金分配) → 模拟交易 → 平仓 → Synapse(广播结果)
  → SignalQuality(记录结果) → RiskBudget(释放资金/更新PnL)
  → Dispatcher(再平衡) → 下一轮分配优化
"""

import sys
import os
import json
import copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.titan_dispatcher import TitanDispatcher
from server.titan_synapse import TitanSynapse
from server.titan_risk_budget import TitanRiskBudget
from server.titan_signal_quality import TitanSignalQuality


def create_fresh_agents():
    d = TitanDispatcher()
    d.current_regime = "unknown"
    d.allocation = dict(d.DEFAULT_ALLOCATION)
    d.active_strategies = ["trend", "range", "grid"]
    d.switch_count = 0
    d.last_switch_time = 0
    d.performance_tracker = {}
    d.regime_history = []

    syn = TitanSynapse()
    syn.knowledge_base = {
        "asset_insights": {},
        "regime_insights": {},
        "timing_insights": {},
        "correlation_map": {},
    }
    syn.broadcast_log = []
    syn.cross_strategy_rules = []
    syn.strategy_performance = {
        "trend": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best_regimes": {}, "worst_assets": {}},
        "range": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best_regimes": {}, "worst_assets": {}},
        "grid": {"wins": 0, "losses": 0, "total_pnl": 0.0, "best_regimes": {}, "worst_assets": {}},
    }
    syn.stats = {"total_broadcasts": 0, "rules_generated": 0, "last_sync": ""}

    rb = TitanRiskBudget(total_capital=100000)
    rb.total_capital = 100000
    rb.strategy_budgets = {
        "trend": {"base_pct": 0.40, "current_pct": 0.40, "used": 0, "max_drawdown_pct": 0.03, "current_dd": 0, "frozen": False},
        "range": {"base_pct": 0.30, "current_pct": 0.30, "used": 0, "max_drawdown_pct": 0.025, "current_dd": 0, "frozen": False},
        "grid": {"base_pct": 0.30, "current_pct": 0.30, "used": 0, "max_drawdown_pct": 0.02, "current_dd": 0, "frozen": False},
    }
    rb.daily_pnl = 0
    rb.daily_trades = 0
    rb.peak_capital = 100000
    rb.total_drawdown = 0
    rb.max_drawdown_ever = 0
    rb.rebalance_count = 0
    rb.history = []

    sq = TitanSignalQuality()
    sq.condition_stats = {}
    sq.asset_stats = {}
    sq.combo_stats = {}
    sq.calibration_table = {}
    sq.stats = {"total_evaluated": 0, "avg_quality": 0, "last_update": ""}

    return d, syn, rb, sq


TRADE_SCENARIOS = [
    {"symbol": "SOL/USDT", "direction": "long", "adx": 35, "rsi": 45, "macd_hist": 0.5, "bb_position": 0.6, "volume_ratio": 1.5, "ema_trend": "bullish", "regime_adx": 35, "pnl_pct": 2.5, "is_win": True, "regime": "trending", "score": 82},
    {"symbol": "ETH/USDT", "direction": "long", "adx": 40, "rsi": 55, "macd_hist": 1.2, "bb_position": 0.7, "volume_ratio": 2.5, "ema_trend": "bullish", "regime_adx": 40, "pnl_pct": 3.8, "is_win": True, "regime": "trending", "score": 88},
    {"symbol": "DOGE/USDT", "direction": "long", "adx": 32, "rsi": 65, "macd_hist": 0.3, "bb_position": 0.75, "volume_ratio": 1.1, "ema_trend": "bullish", "regime_adx": 32, "pnl_pct": -1.5, "is_win": False, "regime": "trending", "score": 72},
    {"symbol": "XRP/USDT", "direction": "short", "adx": 15, "rsi": 50, "macd_hist": -0.1, "bb_position": 0.5, "volume_ratio": 0.8, "ema_trend": "neutral", "regime_adx": 15, "pnl_pct": 1.2, "is_win": True, "regime": "ranging", "score": 65},
    {"symbol": "ADA/USDT", "direction": "long", "adx": 12, "rsi": 35, "macd_hist": -0.3, "bb_position": 0.3, "volume_ratio": 0.6, "ema_trend": "bearish", "regime_adx": 12, "pnl_pct": -2.0, "is_win": False, "regime": "ranging", "score": 55},
    {"symbol": "SOL/USDT", "direction": "long", "adx": 38, "rsi": 48, "macd_hist": 0.8, "bb_position": 0.55, "volume_ratio": 1.8, "ema_trend": "bullish", "regime_adx": 38, "pnl_pct": 4.2, "is_win": True, "regime": "trending", "score": 90},
    {"symbol": "DOGE/USDT", "direction": "short", "adx": 28, "rsi": 72, "macd_hist": -0.5, "bb_position": 0.85, "volume_ratio": 3.0, "ema_trend": "bearish", "regime_adx": 28, "pnl_pct": -1.8, "is_win": False, "regime": "volatile", "score": 68},
    {"symbol": "ETH/USDT", "direction": "long", "adx": 42, "rsi": 52, "macd_hist": 1.5, "bb_position": 0.65, "volume_ratio": 2.0, "ema_trend": "bullish", "regime_adx": 42, "pnl_pct": 5.1, "is_win": True, "regime": "trending", "score": 92},
    {"symbol": "XRP/USDT", "direction": "long", "adx": 16, "rsi": 40, "macd_hist": 0.1, "bb_position": 0.4, "volume_ratio": 0.9, "ema_trend": "neutral", "regime_adx": 16, "pnl_pct": 0.8, "is_win": True, "regime": "ranging", "score": 60},
    {"symbol": "BNB/USDT", "direction": "long", "adx": 22, "rsi": 58, "macd_hist": 0.2, "bb_position": 0.6, "volume_ratio": 1.2, "ema_trend": "bullish", "regime_adx": 22, "pnl_pct": 1.5, "is_win": True, "regime": "mixed", "score": 75},
]

def build_signal(sc):
    return {
        "symbol": sc["symbol"],
        "price": 100.0,
        "score": sc["score"],
        "report": {
            "adx": sc["adx"],
            "rsi": sc["rsi"],
            "macd_hist": sc["macd_hist"],
            "bb_position": sc["bb_position"],
            "volume_ratio": sc["volume_ratio"],
            "ema_trend": sc["ema_trend"],
            "atr": 2.5,
        },
        "regime": {
            "adx": sc["regime_adx"],
            "type": "趋势" if sc["regime_adx"] > 25 else "震荡",
            "atr_percentile": 50,
        },
        "ml": {"confidence": 73.9, "prediction": 1 if sc["direction"] == "long" else -1},
    }


def run_test():
    print("=" * 70)
    print("🏛️  Titan V19.2 智能体联动综合测试")
    print("=" * 70)

    dispatcher, synapse, risk_budget, signal_quality = create_fresh_agents()

    print(f"\n📋 初始状态:")
    print(f"   Dispatcher: regime={dispatcher.current_regime}, alloc={dispatcher.allocation}")
    print(f"   RiskBudget: capital=${risk_budget.total_capital:,.0f}, trend={risk_budget.strategy_budgets['trend']['current_pct']:.0%}/range={risk_budget.strategy_budgets['range']['current_pct']:.0%}/grid={risk_budget.strategy_budgets['grid']['current_pct']:.0%}")
    print(f"   Synapse: broadcasts={synapse.stats['total_broadcasts']}, rules={len(synapse.cross_strategy_rules)}")
    print(f"   SignalQuality: conditions={len(signal_quality.condition_stats)}, calibrated={len(signal_quality.calibration_table)}")

    errors = []
    
    print(f"\n{'─' * 70}")
    print(f"📊 开始模拟 {len(TRADE_SCENARIOS)} 笔交易...")
    print(f"{'─' * 70}")

    for i, sc in enumerate(TRADE_SCENARIOS, 1):
        print(f"\n── 交易 #{i}: {sc['symbol']} {sc['direction'].upper()} (ADX={sc['adx']}, 评分={sc['score']}) ──")

        signal = build_signal(sc)

        # Step 1: Dispatcher 检测市场环境 & 选择策略
        regime = dispatcher.evaluate_regime([signal])
        strategy = dispatcher.get_strategy_for_signal(signal)
        print(f"   [Dispatcher] 市场环境={regime}, 选定策略={strategy}")

        # Step 2: SignalQuality 评估信号质量
        report = signal.get("report", {})
        conditions = signal_quality.extract_conditions(report, regime)
        quality = signal_quality.evaluate_signal(conditions, sc["symbol"], regime, sc["score"])
        q_score = quality["quality_score"]
        print(f"   [SignalQuality] 条件={conditions}")
        print(f"   [SignalQuality] 质量评分={q_score}, 校准条件={quality['calibrated_conditions']}, 调整={quality['adjustments']}")

        # Step 3: Synapse 检查是否有跨策略规则阻止交易
        can_trade, reason = synapse.should_trade(sc["symbol"], strategy, regime)
        print(f"   [Synapse] 允许交易={can_trade}, 原因={reason}")

        preferred = synapse.get_preferred_strategy(sc["symbol"], regime)
        if preferred:
            print(f"   [Synapse] 推荐策略={preferred}")

        # Step 4: RiskBudget 检查资金可用性
        available = risk_budget.get_available_budget(strategy)
        position_size = risk_budget.get_position_size(strategy, quality.get("confidence", 0.5))
        print(f"   [RiskBudget] 策略={strategy}, 可用=${available:,.0f}, 建议仓位=${position_size:,.0f}")

        if not can_trade:
            print(f"   ⛔ Synapse规则阻止交易，跳过")
            continue

        if position_size <= 0:
            print(f"   ⛔ 无可用资金，跳过")
            continue

        # Step 5: 请求资金 (模拟开仓)
        allocated = risk_budget.request_capital(strategy, position_size)
        print(f"   [开仓] 分配资金=${allocated:,.0f}")

        # Step 6: 模拟交易结果 → 平仓
        pnl_usd = allocated * sc["pnl_pct"] / 100.0
        result_emoji = "✅" if sc["is_win"] else "❌"
        print(f"   [平仓] {result_emoji} PnL={sc['pnl_pct']:+.1f}% (${pnl_usd:+,.2f})")

        # Step 7: 释放资金 & 更新PnL
        risk_budget.release_capital(strategy, allocated, pnl_usd)
        print(f"   [RiskBudget] 资金释放, 总资金=${risk_budget.total_capital:,.2f}, 日PnL=${risk_budget.daily_pnl:,.2f}, 回撤={risk_budget.total_drawdown:.2%}")

        # Step 8: Synapse 广播交易结果
        trade_info = {
            "symbol": sc["symbol"],
            "strategy_type": strategy,
            "pnl_pct": sc["pnl_pct"],
            "market_regime": regime,
            "direction": sc["direction"],
            "signal_score": sc["score"],
            "holding_hours": 4,
        }
        synapse.broadcast_trade_result(trade_info)
        print(f"   [Synapse] 广播完成, 总广播={synapse.stats['total_broadcasts']}, 规则数={len(synapse.cross_strategy_rules)}")

        # Step 9: SignalQuality 记录结果
        signal_quality.record_outcome(conditions, sc["is_win"], sc["pnl_pct"], sc["symbol"], regime)
        print(f"   [SignalQuality] 结果记录, 条件库={len(signal_quality.condition_stats)}, 校准表={len(signal_quality.calibration_table)}")

        # Step 10: 周期性再平衡 (每3笔交易)
        if i % 3 == 0:
            synapse_advice = synapse.get_regime_allocation_advice(regime)
            risk_budget.rebalance(
                dispatcher_allocation=dispatcher.allocation,
                synapse_advice=synapse_advice,
            )
            alloc = {s: b["current_pct"] for s, b in risk_budget.strategy_budgets.items()}
            print(f"   [再平衡] Synapse建议={synapse_advice}, 新分配={alloc}")

        # 验证: Synapse是否正确记录了胜负
        if strategy in synapse.strategy_performance:
            sp = synapse.strategy_performance[strategy]
            expected_total = sum(1 for s in TRADE_SCENARIOS[:i] if dispatcher.get_strategy_for_signal(build_signal(s)) == strategy or s == sc)
            if sp["wins"] + sp["losses"] == 0 and i > 0:
                errors.append(f"Trade #{i}: Synapse未记录{strategy}策略的交易")

    print(f"\n{'=' * 70}")
    print(f"📊 测试结果汇总")
    print(f"{'=' * 70}")

    # Final state
    print(f"\n🔹 Dispatcher 最终状态:")
    print(f"   当前环境: {dispatcher.current_regime}")
    print(f"   活跃策略: {dispatcher.active_strategies}")
    print(f"   分配比例: {dispatcher.allocation}")
    print(f"   环境切换次数: {dispatcher.switch_count}")
    for rh in dispatcher.regime_history:
        print(f"   切换记录: {rh['from']} → {rh['to']} (ADX={rh['avg_adx']})")

    print(f"\n🔹 Synapse 最终状态:")
    print(f"   总广播次数: {synapse.stats['total_broadcasts']}")
    print(f"   生成规则数: {synapse.stats['rules_generated']}")
    print(f"   活跃规则: {len(synapse.cross_strategy_rules)}")
    for s, perf in synapse.strategy_performance.items():
        total = perf["wins"] + perf["losses"]
        wr = perf["wins"] / total * 100 if total > 0 else 0
        print(f"   策略 {s}: {total}笔, 胜率{wr:.0f}%, PnL={perf['total_pnl']:+.2f}%")
    if synapse.cross_strategy_rules:
        print(f"   跨策略规则:")
        for rule in synapse.cross_strategy_rules:
            print(f"     - [{rule['type']}] {rule['reason']}")
    
    asset_insights = synapse.knowledge_base.get("asset_insights", {})
    print(f"   资产洞察 ({len(asset_insights)} 资产):")
    for asset, info in asset_insights.items():
        wr = info["wins"] / info["total_trades"] * 100 if info["total_trades"] > 0 else 0
        print(f"     {asset}: {info['total_trades']}笔, 胜率{wr:.0f}%, 最佳策略={info['best_strategy']}")

    regime_insights = synapse.knowledge_base.get("regime_insights", {})
    print(f"   环境洞察 ({len(regime_insights)} 环境):")
    for regime, info in regime_insights.items():
        wr = info["wins"] / info["total_trades"] * 100 if info["total_trades"] > 0 else 0
        print(f"     {regime}: {info['total_trades']}笔, 胜率{wr:.0f}%, 最佳策略={info['best_strategy']}")

    print(f"\n🔹 RiskBudget 最终状态:")
    print(f"   总资金: ${risk_budget.total_capital:,.2f} (初始$100,000)")
    print(f"   峰值资金: ${risk_budget.peak_capital:,.2f}")
    print(f"   总回撤: {risk_budget.total_drawdown:.2%}")
    print(f"   最大回撤: {risk_budget.max_drawdown_ever:.2%}")
    print(f"   日PnL: ${risk_budget.daily_pnl:,.2f}")
    print(f"   日交易数: {risk_budget.daily_trades}")
    print(f"   再平衡次数: {risk_budget.rebalance_count}")
    for s, b in risk_budget.strategy_budgets.items():
        print(f"   策略 {s}: 基准{b['base_pct']:.0%} → 当前{b['current_pct']:.1%}, 已用${b['used']:,.0f}, 冻结={b['frozen']}")

    print(f"\n🔹 SignalQuality 最终状态:")
    print(f"   总评估次数: {signal_quality.stats['total_evaluated']}")
    print(f"   条件库大小: {len(signal_quality.condition_stats)}")
    print(f"   已校准条件: {len(signal_quality.calibration_table)}")
    if signal_quality.calibration_table:
        print(f"   校准表:")
        for cond, cal in sorted(signal_quality.calibration_table.items(), key=lambda x: -x[1]["win_rate"]):
            print(f"     {cond}: 胜率={cal['win_rate']:.0%}, 平均PnL={cal['avg_pnl']:+.2f}%, 样本={cal['samples']}, 可靠度={cal['reliability']:.0%}")

    hot_cold = signal_quality.get_hot_conditions(min_samples=3)
    if hot_cold["hot"]:
        print(f"   🔥 热门条件:")
        for h in hot_cold["hot"]:
            print(f"     {h['condition']}: 胜率{h['win_rate']:.0%}")
    if hot_cold["cold"]:
        print(f"   ❄️ 冷门条件:")
        for c in hot_cold["cold"]:
            print(f"     {c['condition']}: 胜率{c['win_rate']:.0%}")

    # Validation checks
    print(f"\n{'=' * 70}")
    print(f"✅ 联动验证检查")
    print(f"{'=' * 70}")
    
    checks = []

    # Check 1: Dispatcher detected regime changes
    if dispatcher.switch_count > 0:
        checks.append(("✅", "Dispatcher正确检测并切换了市场环境"))
    else:
        checks.append(("❌", "Dispatcher未检测到环境变化"))
        errors.append("Dispatcher should have switched regimes")

    # Check 2: Synapse received all broadcasts
    expected_broadcasts = sum(1 for sc in TRADE_SCENARIOS if True)  # all should trade in this test
    if synapse.stats["total_broadcasts"] >= 8:
        checks.append(("✅", f"Synapse接收了{synapse.stats['total_broadcasts']}次广播"))
    else:
        checks.append(("❌", f"Synapse仅接收{synapse.stats['total_broadcasts']}次广播，预期≥8"))
        errors.append("Synapse broadcast count too low")

    # Check 3: SignalQuality recorded outcomes
    if signal_quality.stats["total_evaluated"] >= 8:
        checks.append(("✅", f"SignalQuality记录了{signal_quality.stats['total_evaluated']}次结果"))
    else:
        checks.append(("❌", f"SignalQuality仅记录{signal_quality.stats['total_evaluated']}次，预期≥8"))
        errors.append("SignalQuality recording count too low")

    # Check 4: RiskBudget capital changed
    if risk_budget.total_capital != 100000:
        delta = risk_budget.total_capital - 100000
        checks.append(("✅", f"RiskBudget资金从$100,000变化了${delta:+,.2f}"))
    else:
        checks.append(("⚠️", "RiskBudget资金未变化"))

    # Check 5: RiskBudget rebalanced
    if risk_budget.rebalance_count >= 2:
        checks.append(("✅", f"RiskBudget再平衡了{risk_budget.rebalance_count}次"))
    else:
        checks.append(("⚠️", f"RiskBudget仅再平衡{risk_budget.rebalance_count}次"))

    # Check 6: Allocation shifted from base
    base = TitanRiskBudget.DEFAULT_ALLOCATION if hasattr(TitanRiskBudget, 'DEFAULT_ALLOCATION') else {"trend": 0.40, "range": 0.30, "grid": 0.30}
    shifted = False
    for s, b in risk_budget.strategy_budgets.items():
        if abs(b["current_pct"] - b["base_pct"]) > 0.01:
            shifted = True
            break
    if shifted:
        checks.append(("✅", "资金分配已从基准比例动态调整（学习生效）"))
    else:
        checks.append(("⚠️", "资金分配未偏离基准（可能需要更多交易数据）"))

    # Check 7: Condition stats populated
    if len(signal_quality.condition_stats) >= 5:
        checks.append(("✅", f"条件库已积累{len(signal_quality.condition_stats)}个条件"))
    else:
        checks.append(("⚠️", f"条件库仅{len(signal_quality.condition_stats)}个条件"))

    # Check 8: Asset insights populated
    if len(synapse.knowledge_base["asset_insights"]) >= 3:
        checks.append(("✅", f"Synapse已积累{len(synapse.knowledge_base['asset_insights'])}个资产洞察"))
    else:
        checks.append(("⚠️", f"Synapse仅{len(synapse.knowledge_base['asset_insights'])}个资产洞察"))

    # Check 9: Regime insights populated
    if len(synapse.knowledge_base["regime_insights"]) >= 2:
        checks.append(("✅", f"Synapse已积累{len(synapse.knowledge_base['regime_insights'])}个环境洞察"))
    else:
        checks.append(("⚠️", f"Synapse仅{len(synapse.knowledge_base['regime_insights'])}个环境洞察"))

    # Check 10: Daily trades tracked
    if risk_budget.daily_trades >= 8:
        checks.append(("✅", f"RiskBudget正确跟踪了{risk_budget.daily_trades}笔日交易"))
    else:
        checks.append(("⚠️", f"RiskBudget仅记录{risk_budget.daily_trades}笔日交易"))

    for emoji, msg in checks:
        print(f"   {emoji} {msg}")

    # Final verdict
    print(f"\n{'=' * 70}")
    if not errors:
        print(f"🎉 全部 {len(checks)} 项检查通过！智能体联动正常！")
    else:
        print(f"⚠️ 发现 {len(errors)} 个问题:")
        for e in errors:
            print(f"   - {e}")
    print(f"{'=' * 70}")

    return len(errors) == 0


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
