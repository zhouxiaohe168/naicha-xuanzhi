-- 3月15日检查点完整查询

-- 1. 市场状态（最新）
SELECT
    fng_value,
    btc_trend,
    regime,
    top5_scores,
    long_signal_count,
    short_signal_count,
    created_at
FROM scan_summaries
ORDER BY created_at DESC
LIMIT 1;

-- 2. 新交易（3月10日后）
SELECT
    COUNT(*) as new_trades,
    SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
    ROUND(AVG(sl_distance_pct)::numeric, 2) as avg_sl_pct,
    ROUND(AVG(
        tp_distance_pct / NULLIF(sl_distance_pct, 0)
    )::numeric, 1) as avg_tp_sl_ratio,
    ROUND(AVG(
        EXTRACT(EPOCH FROM (closed_at - created_at)) / 3600
    )::numeric, 1) as avg_hold_hours,
    STRING_AGG(
        symbol || '(' || ROUND(pnl_pct::numeric, 1) || '%)',
        ', ' ORDER BY created_at DESC
    ) as trade_list
FROM trades
WHERE created_at > '2026-03-10';

-- 3. Shadow系统数据积累
SELECT
    (SELECT COUNT(*) FROM market_pulses) as pulses,
    (SELECT COUNT(*) FROM debate_records) as debates,
    (SELECT COUNT(*) FROM counterfactuals) as counterfactuals,
    (SELECT COUNT(*) FROM memory_strengths) as strengths,
    (SELECT COUNT(*) FROM strategy_weights) as weight_updates;

-- 4. 进化系统状态
SELECT
    status,
    risk_level,
    COUNT(*) as count
FROM evolution_proposals
GROUP BY status, risk_level
ORDER BY status, risk_level;

-- 5. 自动采纳历史
SELECT
    target,
    current_value,
    suggested_value,
    baseline_win_rate,
    result_7d,
    status,
    adopted_at
FROM evolution_proposals
WHERE auto_adopted = true
ORDER BY adopted_at DESC;

-- 6. Learning journal消费情况
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN consumed_by_cto THEN 1 ELSE 0 END) as cto_read,
    COUNT(DISTINCT source) as sources
FROM learning_journal;

-- 7. ML实战表现（3月10日后）
SELECT
    ROUND(AVG(
        (extra->>'ml_confidence')::numeric
    ), 1) as avg_ml_confidence,
    COUNT(CASE WHEN
        (extra->>'ml_signal') = 'bullish'
        AND pnl_usd > 0
        THEN 1 END) as ml_correct,
    COUNT(CASE WHEN
        (extra->>'ml_signal') IS NOT NULL
        THEN 1 END) as ml_total
FROM trades
WHERE created_at > '2026-03-10';

-- 8. 记忆消费进度
SELECT
    type,
    COUNT(*) as total,
    SUM(CASE WHEN consumed THEN 1 ELSE 0 END) as consumed,
    ROUND(100.0 * SUM(
        CASE WHEN consumed THEN 1 ELSE 0 END
    ) / COUNT(*), 0) as pct
FROM memory_bank
GROUP BY type
ORDER BY total DESC;
