import logging
from fastapi import APIRouter, Query
from server.titan_db import TitanDB

logger = logging.getLogger("DecisionRoutes")
router = APIRouter()


@router.get("/api/rejected-signals")
async def get_rejected_signals(limit: int = Query(50, ge=1, le=200)):
    rows = TitanDB.get_recent_rejections(limit=limit)
    for r in rows:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()
    return {"status": "ok", "data": rows}


@router.get("/api/rejection-stats")
async def get_rejection_stats(days: int = Query(30, ge=1, le=90)):
    stats = TitanDB.get_rejection_stats(days=days)
    return {"status": "ok", "data": stats}


@router.get("/api/position-events")
async def get_position_events(trade_id: str = Query(None), limit: int = Query(50, ge=1, le=200)):
    rows = TitanDB.get_position_events(trade_id=trade_id, limit=limit)
    for r in rows:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()
    return {"status": "ok", "data": rows}


@router.get("/api/phase-zero-status")
async def get_phase_zero_status():
    from datetime import datetime, timezone
    import pytz

    phase_zero_start = datetime(2026, 2, 26, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    days_elapsed = (now - phase_zero_start).days
    total_days = 56

    try:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) as losses,
                    ROUND(AVG(CASE WHEN signal_direction_4h_result = 'correct'
                        THEN 100.0
                        WHEN signal_direction_4h_result = 'incorrect'
                        THEN 0.0
                        END)::numeric, 1) as direction_accuracy,
                    COUNT(CASE WHEN signal_direction_4h_result IS NOT NULL THEN 1 END) as verified_trades
                FROM trades
                WHERE open_time >= '2026-02-26T00:00:00Z'
                AND (extra->>'is_test_data')::boolean IS NOT TRUE
            """)
            row = cur.fetchone()
            stats = dict(row) if row else {}
    except Exception as e:
        logger.error(f"查询阶段零状态失败: {e}")
        stats = {}

    return {
        "status": "ok",
        "data": {
            "days_elapsed": max(0, days_elapsed),
            "total_days": total_days,
            "condition_a_deadline": "2026-03-26",
            "condition_b_deadline": "2026-04-23",
            "total_trades": stats.get("total_trades", 0),
            "trade_target": 100,
            "wins": stats.get("wins", 0),
            "losses": stats.get("losses", 0),
            "direction_accuracy": float(stats.get("direction_accuracy") or 0),
            "verified_trades": stats.get("verified_trades", 0),
            "accuracy_target": 45.0,
            "phase": "observing"
        }
    }


@router.get("/api/asset-accuracy")
async def get_asset_accuracy():
    try:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT
                    symbol,
                    COUNT(*) as trades,
                    ROUND(AVG(CASE WHEN signal_direction_4h_result = 'correct'
                        THEN 100.0
                        WHEN signal_direction_4h_result = 'incorrect'
                        THEN 0.0
                        END)::numeric, 1) as direction_accuracy,
                    ROUND(AVG(CASE WHEN result='win' THEN 100.0 ELSE 0 END)::numeric, 1) as win_rate
                FROM trades
                WHERE (extra->>'is_test_data')::boolean IS NOT TRUE
                GROUP BY symbol
                HAVING COUNT(*) >= 1
                ORDER BY COUNT(*) DESC
            """)
            rows = [dict(r) for r in cur.fetchall()]
        return {"status": "ok", "data": {r['symbol']: r for r in rows}}
    except Exception as e:
        logger.error(f"查询资产准确率失败: {e}")
        return {"status": "ok", "data": {}}


@router.get("/api/scan-summaries")
async def get_scan_summaries(limit: int = Query(50, ge=1, le=200)):
    rows = TitanDB.get_scan_summaries(limit=limit)
    for r in rows:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()
    return {"status": "ok", "data": rows}


@router.get("/api/debate-records")
async def get_debate_records(limit: int = Query(20, ge=1, le=100)):
    try:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT * FROM debate_records
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
        return {"status": "ok", "data": rows}
    except Exception as e:
        logger.error(f"查询辩论记录失败: {e}")
        return {"status": "ok", "data": []}


@router.get("/api/counterfactuals")
async def get_counterfactuals(limit: int = Query(10, ge=1, le=50)):
    try:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT cf.*, t.symbol, t.direction, t.pnl_pct, t.result
                FROM counterfactuals cf
                LEFT JOIN trades t ON cf.trade_id::text = t.id
                ORDER BY cf.created_at DESC
                LIMIT %s
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
        return {"status": "ok", "data": rows}
    except Exception as e:
        logger.error(f"查询反事实分析失败: {e}")
        return {"status": "ok", "data": []}


@router.get("/api/memory-strengths")
async def get_memory_strengths(limit: int = Query(100, ge=1, le=500)):
    rows = TitanDB.get_memory_strengths(limit=limit)
    for r in rows:
        for k, v in r.items():
            if hasattr(v, 'isoformat'):
                r[k] = v.isoformat()
    return {"status": "ok", "data": rows}


@router.get("/api/backtest-reports")
async def get_backtest_reports(limit: int = Query(10, ge=1, le=50)):
    try:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("""
                SELECT * FROM backtest_reports
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
        return {"status": "ok", "data": rows}
    except Exception as e:
        logger.error(f"查询回测报告失败: {e}")
        return {"status": "ok", "data": []}


@router.get("/api/evolution-log")
async def get_evolution_log():
    import json, os
    result = {"deep_evolution": [], "proposals": [], "darwin": {}}
    try:
        de_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'deep_evolution_log.json')
        if os.path.exists(de_path):
            with open(de_path, 'r') as f:
                entries = json.load(f)
            if isinstance(entries, list):
                result["deep_evolution"] = entries[-10:]
    except Exception as e:
        logger.warning(f"读取deep_evolution_log失败: {e}")
    try:
        from server.titan_db import db_connection
        with db_connection(dict_cursor=True) as (conn, cur):
            cur.execute("SELECT * FROM evolution_proposals ORDER BY created_at DESC LIMIT 20")
            rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            for k, v in r.items():
                if hasattr(v, 'isoformat'):
                    r[k] = v.isoformat()
        result["proposals"] = rows
    except Exception as e:
        logger.warning(f"查询evolution_proposals失败: {e}")
    return {"status": "ok", "data": result}


@router.post("/api/evolution-proposals/{proposal_id}/decision")
async def decide_evolution_proposal(proposal_id: int, body: dict):
    action = body.get("action", "")
    reason = body.get("reason", "")
    if action not in ("adopt", "reject", "hold"):
        return {"status": "error", "message": "action must be adopt, reject, or hold"}
    status_map = {"adopt": "adopted", "reject": "rejected", "hold": "hold_pending_data"}
    try:
        from server.titan_db import db_connection
        with db_connection() as (conn, cur):
            cur.execute(
                "UPDATE evolution_proposals SET status = %s, notes = %s WHERE id = %s",
                (status_map[action], reason, proposal_id)
            )
            if action == "adopt":
                cur.execute(
                    "UPDATE evolution_proposals SET auto_adopted = TRUE, adopted_at = NOW() WHERE id = %s",
                    (proposal_id,)
                )
            conn.commit()
        return {"status": "ok", "message": f"Proposal #{proposal_id} → {status_map[action]}"}
    except Exception as e:
        logger.error(f"更新proposal失败: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/api/run-backtest")
async def run_backtest_now(days: int = Query(30, ge=7, le=90)):
    try:
        from server.titan_backtester import TitanBacktester
        bt = TitanBacktester()
        report = bt.run_full_backtest(days=days)
        for k, v in report.items():
            if hasattr(v, 'isoformat'):
                report[k] = v.isoformat()
        return {"status": "ok", "data": report}
    except Exception as e:
        logger.error(f"执行回测失败: {e}")
        return {"status": "error", "message": str(e)}
