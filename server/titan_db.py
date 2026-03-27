import os
import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor, Json

logger = logging.getLogger("TitanDB")

DATABASE_URL = os.environ.get("DATABASE_URL")

_db_healthy = True
_db_fail_count = 0
_MAX_FAIL_BEFORE_SUPPRESS = 5


@contextmanager
def db_connection(dict_cursor=False):
    global _db_healthy, _db_fail_count
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        if dict_cursor:
            cur = conn.cursor(cursor_factory=RealDictCursor)
        else:
            cur = conn.cursor()
        yield conn, cur
        _db_fail_count = 0
        _db_healthy = True
    except Exception as e:
        _db_fail_count += 1
        if _db_fail_count >= _MAX_FAIL_BEFORE_SUPPRESS:
            _db_healthy = False
        raise
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def is_db_healthy():
    return _db_healthy


def init_db():
    with db_connection() as (conn, cur):
        cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            strategy_type TEXT NOT NULL DEFAULT 'unknown',
            entry_price DOUBLE PRECISION,
            exit_price DOUBLE PRECISION,
            tp_price DOUBLE PRECISION,
            sl_price DOUBLE PRECISION,
            position_value DOUBLE PRECISION,
            pnl_pct DOUBLE PRECISION,
            pnl_value DOUBLE PRECISION,
            result TEXT,
            reason TEXT,
            signal_score DOUBLE PRECISION,
            ml_confidence DOUBLE PRECISION,
            ai_verdict TEXT,
            mtf_alignment INTEGER DEFAULT 0,
            open_time TIMESTAMPTZ,
            close_time TIMESTAMPTZ,
            hold_hours DOUBLE PRECISION,
            regime TEXT,
            signal_direction_4h_result TEXT,
            btc_macro_trend_at_entry TEXT,
            extra JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            strategy_type TEXT NOT NULL DEFAULT 'unknown',
            entry_price DOUBLE PRECISION,
            current_price DOUBLE PRECISION,
            tp_price DOUBLE PRECISION,
            sl_price DOUBLE PRECISION,
            position_value DOUBLE PRECISION,
            remaining_value DOUBLE PRECISION,
            signal_score DOUBLE PRECISION,
            ml_confidence DOUBLE PRECISION,
            ai_verdict TEXT,
            mtf_alignment INTEGER DEFAULT 0,
            open_time TIMESTAMPTZ,
            regime TEXT,
            extra JSONB DEFAULT '{}',
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS grid_activities (
            id SERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            action TEXT NOT NULL,
            spacing_mode TEXT,
            grid_count INTEGER,
            range_pct DOUBLE PRECISION,
            bias TEXT,
            capital DOUBLE PRECISION,
            pnl DOUBLE PRECISION DEFAULT 0,
            regime TEXT,
            extra JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS signals (
            id SERIAL PRIMARY KEY,
            symbol TEXT NOT NULL,
            direction TEXT,
            signal_score DOUBLE PRECISION,
            ml_confidence DOUBLE PRECISION,
            ml_direction TEXT,
            strategy_type TEXT,
            regime TEXT,
            passed_gate BOOLEAN DEFAULT FALSE,
            blocked_reason TEXT,
            extra JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS strategy_snapshots (
            id SERIAL PRIMARY KEY,
            strategy TEXT NOT NULL,
            trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            win_rate DOUBLE PRECISION DEFAULT 0,
            total_pnl DOUBLE PRECISION DEFAULT 0,
            avg_pnl DOUBLE PRECISION DEFAULT 0,
            regime TEXT,
            equity DOUBLE PRECISION,
            extra JSONB DEFAULT '{}',
            snapshot_time TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS system_snapshots (
            id SERIAL PRIMARY KEY,
            equity DOUBLE PRECISION,
            capital DOUBLE PRECISION,
            total_trades INTEGER,
            win_rate DOUBLE PRECISION,
            max_drawdown DOUBLE PRECISION,
            regime TEXT,
            fng INTEGER,
            btc_price DOUBLE PRECISION,
            ml_accuracy DOUBLE PRECISION,
            health_score INTEGER,
            active_positions INTEGER,
            active_grids INTEGER,
            extra JSONB DEFAULT '{}',
            snapshot_time TIMESTAMPTZ DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_type);
        CREATE INDEX IF NOT EXISTS idx_trades_close_time ON trades(close_time);
        CREATE INDEX IF NOT EXISTS idx_trades_result ON trades(result);
        CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
        CREATE INDEX IF NOT EXISTS idx_grid_symbol ON grid_activities(symbol);
        CREATE INDEX IF NOT EXISTS idx_grid_created ON grid_activities(created_at);
        CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);
        CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
        CREATE INDEX IF NOT EXISTS idx_snapshots_time ON system_snapshots(snapshot_time);
        CREATE INDEX IF NOT EXISTS idx_strategy_snap_time ON strategy_snapshots(snapshot_time);
    """)
        conn.commit()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS rejected_signals (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            symbol VARCHAR(20),
            direction VARCHAR(10),
            signal_score INTEGER,
            ml_confidence DOUBLE PRECISION,
            rejected_by VARCHAR(50),
            rejection_reason TEXT,
            rejection_detail JSONB,
            btc_macro_trend VARCHAR(20),
            fng_value INTEGER,
            regime VARCHAR(20),
            price_at_rejection DOUBLE PRECISION,
            price_24h_later DOUBLE PRECISION,
            price_change_pct DOUBLE PRECISION,
            rejection_was_correct BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS position_events (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            trade_id TEXT,
            symbol VARCHAR(20),
            event_type VARCHAR(50),
            old_value TEXT,
            new_value TEXT,
            reason TEXT,
            current_pnl_pct DOUBLE PRECISION,
            current_price DOUBLE PRECISION,
            holding_hours DOUBLE PRECISION
        );

        CREATE TABLE IF NOT EXISTS scan_summaries (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            total_scanned INTEGER,
            long_signals INTEGER,
            short_signals INTEGER,
            passed_long_prescan INTEGER,
            passed_short_prescan INTEGER,
            passed_all_gates INTEGER,
            trades_opened INTEGER,
            top5_scores INTEGER[],
            long_threshold INTEGER,
            short_threshold INTEGER,
            fng_value INTEGER,
            btc_price DOUBLE PRECISION,
            btc_macro_trend VARCHAR(20),
            regime VARCHAR(20),
            market_breadth_long_pct DOUBLE PRECISION
        );

        CREATE INDEX IF NOT EXISTS idx_rejected_signals_created ON rejected_signals(created_at);
        CREATE INDEX IF NOT EXISTS idx_rejected_signals_by ON rejected_signals(rejected_by);
        CREATE INDEX IF NOT EXISTS idx_rejected_signals_unverified ON rejected_signals(created_at) WHERE rejection_was_correct IS NULL;
        CREATE INDEX IF NOT EXISTS idx_position_events_trade ON position_events(trade_id);
        CREATE INDEX IF NOT EXISTS idx_position_events_created ON position_events(created_at);
        CREATE INDEX IF NOT EXISTS idx_scan_summaries_created ON scan_summaries(created_at);

        CREATE TABLE IF NOT EXISTS market_pulses (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            symbol VARCHAR(20),
            trade_id INTEGER,
            kline_prediction NUMERIC,
            momentum NUMERIC,
            volatility VARCHAR(20),
            reversal_risk NUMERIC,
            session_bias VARCHAR(10),
            breadth_score NUMERIC,
            composite_score NUMERIC
        );

        CREATE TABLE IF NOT EXISTS strategy_weights (
            id SERIAL PRIMARY KEY,
            updated_at TIMESTAMP DEFAULT NOW(),
            rsi_weight NUMERIC DEFAULT 1.0,
            adx_weight NUMERIC DEFAULT 1.0,
            bb_weight NUMERIC DEFAULT 1.0,
            volume_weight NUMERIC DEFAULT 1.0,
            fng_weight NUMERIC DEFAULT 1.0,
            hold_time_weight NUMERIC DEFAULT 1.0,
            funding_weight NUMERIC DEFAULT 1.0,
            session_weight NUMERIC DEFAULT 1.0,
            sample_size INTEGER,
            prediction_accuracy NUMERIC
        );

        CREATE TABLE IF NOT EXISTS evolution_proposals (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            proposal_type VARCHAR(50),
            target VARCHAR(100),
            current_value TEXT,
            suggested_value TEXT,
            evidence TEXT,
            confidence NUMERIC,
            risk_level VARCHAR(20),
            status VARCHAR(20) DEFAULT 'pending',
            auto_adopted BOOLEAN DEFAULT FALSE,
            adopted_at TIMESTAMP,
            result_7d NUMERIC,
            result_30d NUMERIC,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS debate_records (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            symbol VARCHAR(20),
            signal_score INTEGER,
            bull_score NUMERIC,
            bear_score NUMERIC,
            risk_level VARCHAR(20),
            historical_wr NUMERIC,
            verdict VARCHAR(20),
            verdict_reason TEXT,
            confidence NUMERIC,
            trade_id INTEGER,
            verdict_correct BOOLEAN
        );

        CREATE TABLE IF NOT EXISTS counterfactuals (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            trade_id INTEGER,
            early_tp_better BOOLEAN,
            wider_sl_survives BOOLEAN,
            was_correct_to_trade BOOLEAN,
            peak_giveback_pct NUMERIC,
            primary_lessons TEXT[],
            analysis_json JSONB
        );

        CREATE TABLE IF NOT EXISTS memory_strengths (
            id SERIAL PRIMARY KEY,
            pattern_key VARCHAR(200),
            strength NUMERIC DEFAULT 0.5,
            importance NUMERIC DEFAULT 1.0,
            correct_predictions INTEGER DEFAULT 0,
            wrong_predictions INTEGER DEFAULT 0,
            last_updated TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS backtest_reports (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT NOW(),
            backtest_days INTEGER,
            signal_accuracy JSONB,
            debate_accuracy NUMERIC,
            strategy_performance JSONB,
            auto_optimizations INTEGER DEFAULT 0,
            pending_proposals INTEGER DEFAULT 0,
            summary TEXT
        );

        CREATE TABLE IF NOT EXISTS learning_journal (
            id SERIAL PRIMARY KEY,
            source VARCHAR(50),
            content TEXT,
            priority VARCHAR(20) DEFAULT 'medium',
            consumed_by_cto BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        );

        ALTER TABLE evolution_proposals ADD COLUMN IF NOT EXISTS baseline_win_rate NUMERIC;
        ALTER TABLE evolution_proposals ADD COLUMN IF NOT EXISTS review_due_at TIMESTAMP;
        ALTER TABLE evolution_proposals ADD COLUMN IF NOT EXISTS source VARCHAR(100);

        CREATE INDEX IF NOT EXISTS idx_market_pulses_created ON market_pulses(created_at);
        CREATE INDEX IF NOT EXISTS idx_market_pulses_symbol ON market_pulses(symbol);
        CREATE INDEX IF NOT EXISTS idx_evolution_proposals_status ON evolution_proposals(status);
        CREATE INDEX IF NOT EXISTS idx_debate_records_created ON debate_records(created_at);
        CREATE INDEX IF NOT EXISTS idx_counterfactuals_trade ON counterfactuals(trade_id);
        CREATE INDEX IF NOT EXISTS idx_memory_strengths_key ON memory_strengths(pattern_key);
        CREATE INDEX IF NOT EXISTS idx_backtest_reports_created ON backtest_reports(created_at);
        """)
        conn.commit()

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='trades' AND column_name='signal_direction_4h_result'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE trades ADD COLUMN signal_direction_4h_result TEXT")
            conn.commit()
            logger.info("迁移: 添加signal_direction_4h_result列")

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='trades' AND column_name='btc_macro_trend_at_entry'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE trades ADD COLUMN btc_macro_trend_at_entry TEXT")
            conn.commit()
            logger.info("迁移: 添加btc_macro_trend_at_entry列")

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='trades' AND column_name='position_advisor_suggestion'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE trades ADD COLUMN position_advisor_suggestion VARCHAR(20)")
            cur.execute("ALTER TABLE trades ADD COLUMN position_advisor_followed BOOLEAN")
            conn.commit()
            logger.info("迁移: 添加position_advisor_suggestion/followed列")

        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name='trades' AND column_name='sub_strategy'
        """)
        if not cur.fetchone():
            cur.execute("ALTER TABLE trades ADD COLUMN sub_strategy VARCHAR(50)")
            cur.execute("ALTER TABLE trades ADD COLUMN direction_bias VARCHAR(20)")
            conn.commit()
            logger.info("迁移: 添加sub_strategy/direction_bias列")

    logger.info("数据库初始化完成")


_TRADE_FIELDS = frozenset((
    'id', 'symbol', 'direction', 'strategy_type', 'entry_price',
    'exit_price', 'tp_price', 'sl_price', 'position_value',
    'pnl_pct', 'pnl_value', 'result', 'reason', 'signal_score',
    'ml_confidence', 'ai_verdict', 'mtf_alignment', 'open_time',
    'close_time', 'hold_hours', 'regime', 'signal_direction_4h_result',
    'btc_macro_trend_at_entry', 'sub_strategy', 'direction_bias'
))
_POS_FIELDS = frozenset((
    'id', 'symbol', 'direction', 'strategy_type', 'entry_price',
    'current_price', 'tp_price', 'sl_price', 'position_value',
    'remaining_value', 'signal_score', 'ml_confidence', 'ai_verdict',
    'mtf_alignment', 'open_time', 'regime'
))
_GRID_FIELDS = frozenset((
    'symbol', 'action', 'spacing_mode', 'grid_count', 'range_pct',
    'bias', 'capital', 'pnl', 'regime'
))
_SIGNAL_FIELDS = frozenset((
    'symbol', 'direction', 'signal_score', 'ml_confidence',
    'ml_direction', 'strategy_type', 'regime', 'passed_gate', 'blocked_reason'
))


class TitanDB:

    @staticmethod
    def save_trade(trade: dict):
        if not _db_healthy:
            return
        try:
            extra = {k: v for k, v in trade.items() if k not in _TRADE_FIELDS}
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO trades (id, symbol, direction, strategy_type, entry_price,
                        exit_price, tp_price, sl_price, position_value, pnl_pct, pnl_value,
                        result, reason, signal_score, ml_confidence, ai_verdict,
                        mtf_alignment, open_time, close_time, hold_hours, regime,
                        signal_direction_4h_result, btc_macro_trend_at_entry, extra)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        exit_price=EXCLUDED.exit_price, pnl_pct=EXCLUDED.pnl_pct,
                        pnl_value=EXCLUDED.pnl_value, result=EXCLUDED.result,
                        reason=EXCLUDED.reason, close_time=EXCLUDED.close_time,
                        hold_hours=EXCLUDED.hold_hours, extra=EXCLUDED.extra
                """, (
                    trade.get('id'), trade.get('symbol'), trade.get('direction'),
                    trade.get('strategy_type', 'unknown'), trade.get('entry_price'),
                    trade.get('exit_price'), trade.get('tp_price'), trade.get('sl_price'),
                    trade.get('position_value'), trade.get('pnl_pct'), trade.get('pnl_value'),
                    trade.get('result'), trade.get('reason'), trade.get('signal_score'),
                    trade.get('ml_confidence'), trade.get('ai_verdict'),
                    trade.get('mtf_alignment', 0), trade.get('open_time'),
                    trade.get('close_time'), trade.get('hold_hours'),
                    trade.get('regime'), trade.get('signal_direction_4h_result'),
                    trade.get('btc_macro_trend_at_entry'),
                    Json(extra)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存交易失败: {e}")

    @staticmethod
    def save_position(pos: dict):
        if not _db_healthy:
            return
        try:
            extra = {k: v for k, v in pos.items() if k not in _POS_FIELDS}
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO positions (id, symbol, direction, strategy_type, entry_price,
                        current_price, tp_price, sl_price, position_value, remaining_value,
                        signal_score, ml_confidence, ai_verdict, mtf_alignment, open_time, regime, extra)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        current_price=EXCLUDED.current_price, sl_price=EXCLUDED.sl_price,
                        remaining_value=EXCLUDED.remaining_value, extra=EXCLUDED.extra,
                        updated_at=NOW()
                """, (
                    pos.get('id'), pos.get('symbol'), pos.get('direction'),
                    pos.get('strategy_type', 'unknown'), pos.get('entry_price'),
                    pos.get('current_price', pos.get('entry_price')),
                    pos.get('tp_price'), pos.get('sl_price'),
                    pos.get('position_value'), pos.get('remaining_value', pos.get('position_value')),
                    pos.get('signal_score'), pos.get('ml_confidence'),
                    pos.get('ai_verdict'), pos.get('mtf_alignment', 0),
                    pos.get('open_time'), pos.get('regime'), Json(extra)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存持仓失败: {e}")

    @staticmethod
    def remove_position(pid: str):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("DELETE FROM positions WHERE id=%s", (pid,))
                conn.commit()
        except Exception as e:
            logger.error(f"删除持仓失败: {e}")

    @staticmethod
    def save_grid_activity(activity: dict):
        if not _db_healthy:
            return
        try:
            extra = {k: v for k, v in activity.items() if k not in _GRID_FIELDS}
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO grid_activities (symbol, action, spacing_mode, grid_count,
                        range_pct, bias, capital, pnl, regime, extra)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    activity.get('symbol'), activity.get('action'),
                    activity.get('spacing_mode'), activity.get('grid_count'),
                    activity.get('range_pct'), activity.get('bias'),
                    activity.get('capital'), activity.get('pnl', 0),
                    activity.get('regime'), Json(extra)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存网格活动失败: {e}")

    @staticmethod
    def save_signal(signal: dict):
        if not _db_healthy:
            return
        try:
            extra = {k: v for k, v in signal.items() if k not in _SIGNAL_FIELDS}
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO signals (symbol, direction, signal_score, ml_confidence,
                        ml_direction, strategy_type, regime, passed_gate, blocked_reason, extra)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    signal.get('symbol'), signal.get('direction'),
                    signal.get('signal_score'), signal.get('ml_confidence'),
                    signal.get('ml_direction'), signal.get('strategy_type'),
                    signal.get('regime'), signal.get('passed_gate', False),
                    signal.get('blocked_reason'), Json(extra)
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存信号失败: {e}")

    @staticmethod
    def save_strategy_snapshot(snapshots: list):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                for s in snapshots:
                    cur.execute("""
                        INSERT INTO strategy_snapshots (strategy, trades, wins, losses,
                            win_rate, total_pnl, avg_pnl, regime, equity, extra)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        s.get('strategy'), s.get('trades', 0), s.get('wins', 0),
                        s.get('losses', 0), s.get('win_rate', 0), s.get('total_pnl', 0),
                        s.get('avg_pnl', 0), s.get('regime'), s.get('equity'),
                        Json(s.get('extra', {}))
                    ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存策略快照失败: {e}")

    @staticmethod
    def save_system_snapshot(snap: dict):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO system_snapshots (equity, capital, total_trades, win_rate,
                        max_drawdown, regime, fng, btc_price, ml_accuracy, health_score,
                        active_positions, active_grids, extra)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    snap.get('equity'), snap.get('capital'), snap.get('total_trades'),
                    snap.get('win_rate'), snap.get('max_drawdown'), snap.get('regime'),
                    snap.get('fng'), snap.get('btc_price'), snap.get('ml_accuracy'),
                    snap.get('health_score'), snap.get('active_positions'),
                    snap.get('active_grids'), Json(snap.get('extra', {}))
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存系统快照失败: {e}")

    @staticmethod
    def query_trades(strategy=None, symbol=None, result=None, limit=100, offset=0):
        limit = min(limit, 500)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                conditions = []
                params = []
                if strategy:
                    conditions.append("strategy_type=%s")
                    params.append(strategy)
                if symbol:
                    conditions.append("symbol=%s")
                    params.append(symbol)
                if result:
                    conditions.append("result=%s")
                    params.append(result)
                where = " AND ".join(conditions)
                if where:
                    where = "WHERE " + where
                cur.execute(f"""
                    SELECT * FROM trades {where}
                    ORDER BY close_time DESC NULLS LAST
                    LIMIT %s OFFSET %s
                """, params + [limit, offset])
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询交易失败: {e}")
            return []

    @staticmethod
    def get_strategy_stats():
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT strategy_type,
                        COUNT(*) as trades,
                        SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                        SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) as losses,
                        ROUND(AVG(CASE WHEN result='win' THEN 1.0 ELSE 0.0 END)*100, 1) as win_rate,
                        ROUND(SUM(pnl_value)::numeric, 2) as total_pnl,
                        ROUND(AVG(pnl_value)::numeric, 2) as avg_pnl,
                        ROUND(AVG(hold_hours)::numeric, 1) as avg_hold_hours
                    FROM trades
                    GROUP BY strategy_type
                    ORDER BY trades DESC
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询策略统计失败: {e}")
            return []

    @staticmethod
    def get_asset_stats(limit=20):
        limit = min(limit, 200)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT symbol,
                        COUNT(*) as trades,
                        SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                        ROUND(AVG(CASE WHEN result='win' THEN 1.0 ELSE 0.0 END)*100, 1) as win_rate,
                        ROUND(SUM(pnl_value)::numeric, 2) as total_pnl,
                        ROUND(AVG(pnl_value)::numeric, 2) as avg_pnl
                    FROM trades
                    GROUP BY symbol
                    ORDER BY total_pnl ASC
                    LIMIT %s
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询资产统计失败: {e}")
            return []

    @staticmethod
    def get_recent_signals(limit=50):
        limit = min(limit, 200)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM signals
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询信号失败: {e}")
            return []

    @staticmethod
    def get_grid_history(limit=50):
        limit = min(limit, 200)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM grid_activities
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询网格历史失败: {e}")
            return []

    @staticmethod
    def get_equity_curve(hours=72):
        hours = min(hours, 720)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT equity, regime, fng, btc_price, total_trades, win_rate,
                           health_score, snapshot_time
                    FROM system_snapshots
                    WHERE snapshot_time > NOW() - INTERVAL '%s hours'
                    ORDER BY snapshot_time ASC
                """, (hours,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询净值曲线失败: {e}")
            return []

    @staticmethod
    def get_dashboard_summary():
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        (SELECT COUNT(*) FROM trades) as total_trades,
                        (SELECT COUNT(*) FROM trades WHERE result='win') as total_wins,
                        (SELECT ROUND(SUM(pnl_value)::numeric, 2) FROM trades) as total_pnl,
                        (SELECT COUNT(*) FROM positions) as open_positions,
                        (SELECT COUNT(*) FROM grid_activities WHERE action='activate'
                            AND created_at > NOW() - INTERVAL '24 hours') as grids_24h,
                        (SELECT COUNT(*) FROM signals WHERE created_at > NOW() - INTERVAL '1 hour') as signals_1h,
                        (SELECT COUNT(*) FROM signals WHERE passed_gate=true
                            AND created_at > NOW() - INTERVAL '1 hour') as passed_signals_1h
                """)
                row = cur.fetchone()
                return dict(row) if row else {}
        except Exception as e:
            logger.error(f"查询仪表盘摘要失败: {e}")
            return {}

    @staticmethod
    def record_rejection(symbol, direction, signal_score, ml_confidence,
                         rejected_by, rejection_reason, rejection_detail=None,
                         btc_macro_trend=None, fng_value=None, regime=None, price=None):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO rejected_signals
                    (symbol, direction, signal_score, ml_confidence,
                     rejected_by, rejection_reason, rejection_detail,
                     btc_macro_trend, fng_value, regime, price_at_rejection)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (symbol, direction, signal_score, ml_confidence,
                      rejected_by, rejection_reason,
                      Json(rejection_detail) if rejection_detail else None,
                      btc_macro_trend, fng_value, regime, price))
                conn.commit()
        except Exception as e:
            logger.error(f"记录拒绝信号失败: {e}")

    @staticmethod
    def record_position_event(trade_id, symbol, event_type,
                              old_value=None, new_value=None, reason=None,
                              current_pnl_pct=None, current_price=None, holding_hours=None):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO position_events
                    (trade_id, symbol, event_type, old_value, new_value,
                     reason, current_pnl_pct, current_price, holding_hours)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (trade_id, symbol, event_type, old_value, new_value,
                      reason, current_pnl_pct, current_price, holding_hours))
                conn.commit()
        except Exception as e:
            logger.error(f"记录持仓事件失败: {e}")

    @staticmethod
    def verify_rejections():
        if not _db_healthy:
            return []
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id, symbol, direction, price_at_rejection
                    FROM rejected_signals
                    WHERE rejection_was_correct IS NULL
                    AND created_at < NOW() - INTERVAL '24 hours'
                    AND created_at > NOW() - INTERVAL '7 days'
                    AND price_at_rejection IS NOT NULL
                    AND price_at_rejection > 0
                    LIMIT 500
                """)
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询待验证拒绝信号失败: {e}")
            return []

    @staticmethod
    def update_rejection_verification(rejection_id, price_24h_later, price_change_pct, was_correct):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    UPDATE rejected_signals
                    SET price_24h_later = %s,
                        price_change_pct = %s,
                        rejection_was_correct = %s
                    WHERE id = %s
                """, (price_24h_later, price_change_pct, was_correct, rejection_id))
                conn.commit()
        except Exception as e:
            logger.error(f"更新拒绝验证失败: {e}")

    @staticmethod
    def get_rejection_stats(days=30):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT
                        rejected_by,
                        COUNT(*) as total,
                        SUM(CASE WHEN rejection_was_correct THEN 1 ELSE 0 END) as correct,
                        SUM(CASE WHEN rejection_was_correct = false THEN 1 ELSE 0 END) as incorrect,
                        SUM(CASE WHEN rejection_was_correct IS NULL THEN 1 ELSE 0 END) as pending,
                        ROUND(AVG(CASE WHEN rejection_was_correct IS NOT NULL
                            THEN (CASE WHEN rejection_was_correct THEN 100.0 ELSE 0 END)
                            END)::numeric, 1) as accuracy_pct
                    FROM rejected_signals
                    WHERE created_at > NOW() - INTERVAL '%s days'
                    GROUP BY rejected_by
                    ORDER BY total DESC
                """, (days,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询拒绝统计失败: {e}")
            return []

    @staticmethod
    def save_scan_summary(summary: dict):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO scan_summaries (
                        total_scanned, long_signals, short_signals,
                        passed_long_prescan, passed_short_prescan,
                        passed_all_gates, trades_opened, top5_scores,
                        long_threshold, short_threshold,
                        fng_value, btc_price, btc_macro_trend,
                        regime, market_breadth_long_pct
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    summary.get("total_scanned", 0),
                    summary.get("long_signals", 0),
                    summary.get("short_signals", 0),
                    summary.get("passed_long_prescan", 0),
                    summary.get("passed_short_prescan", 0),
                    summary.get("passed_all_gates", 0),
                    summary.get("trades_opened", 0),
                    summary.get("top5_scores", []),
                    summary.get("long_threshold", 0),
                    summary.get("short_threshold", 0),
                    summary.get("fng_value", 0),
                    summary.get("btc_price", 0),
                    summary.get("btc_macro_trend", ""),
                    summary.get("regime", ""),
                    summary.get("market_breadth_long_pct", 0),
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"保存扫描汇总失败: {e}")

    @staticmethod
    def get_scan_summaries(limit=50):
        if not _db_healthy:
            return []
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM scan_summaries
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (min(limit, 200),))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询扫描汇总失败: {e}")
            return []

    @staticmethod
    def update_memory_strength(pattern_key, outcome, importance=1.0):
        if not _db_healthy:
            return
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("SELECT * FROM memory_strengths WHERE pattern_key = %s", (pattern_key,))
                existing = cur.fetchone()

                if existing:
                    from datetime import datetime, timezone
                    last_updated = existing["last_updated"]
                    if hasattr(last_updated, "timestamp"):
                        days_old = max(0, (datetime.now(timezone.utc) - last_updated.replace(tzinfo=timezone.utc)).days)
                    else:
                        days_old = 0
                    decay = 0.95 ** days_old
                    old_strength = float(existing["strength"] or 0.5)

                    if outcome > 0:
                        new_strength = min(1.0, old_strength + 0.1 * importance)
                        cur.execute("UPDATE memory_strengths SET strength = %s, correct_predictions = correct_predictions + 1, importance = %s, last_updated = NOW() WHERE pattern_key = %s",
                                    (round(new_strength * decay, 4), importance, pattern_key))
                    else:
                        new_strength = max(0.0, old_strength - 0.15 * importance)
                        cur.execute("UPDATE memory_strengths SET strength = %s, wrong_predictions = wrong_predictions + 1, importance = %s, last_updated = NOW() WHERE pattern_key = %s",
                                    (round(new_strength * decay, 4), importance, pattern_key))

                    cur.execute("DELETE FROM memory_strengths WHERE strength < 0.1 AND pattern_key = %s", (pattern_key,))
                else:
                    cur.execute("""
                        INSERT INTO memory_strengths (pattern_key, strength, importance, correct_predictions, wrong_predictions)
                        VALUES (%s, 0.5, %s, %s, %s)
                    """, (pattern_key, importance, 1 if outcome > 0 else 0, 0 if outcome > 0 else 1))

                conn.commit()
        except Exception as e:
            logger.error(f"更新记忆强度失败: {e}")

    @staticmethod
    def get_memory_strengths(limit=100):
        if not _db_healthy:
            return []
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM memory_strengths
                    ORDER BY importance DESC, strength DESC
                    LIMIT %s
                """, (min(limit, 500),))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询记忆强度失败: {e}")
            return []

    @staticmethod
    def get_recent_rejections(limit=50):
        limit = min(limit, 200)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM rejected_signals
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询最近拒绝信号失败: {e}")
            return []

    @staticmethod
    def get_position_events(trade_id=None, limit=50):
        limit = min(limit, 200)
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                if trade_id:
                    cur.execute("""
                        SELECT * FROM position_events
                        WHERE trade_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (trade_id, limit))
                else:
                    cur.execute("""
                        SELECT * FROM position_events
                        ORDER BY created_at DESC
                        LIMIT %s
                    """, (limit,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询持仓事件失败: {e}")
            return []

    @staticmethod
    def update_advisor_suggestion(trade_id, suggestion):
        if not _db_healthy:
            return
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    UPDATE trades
                    SET position_advisor_suggestion = %s
                    WHERE id = %s
                """, (suggestion, trade_id))
                conn.commit()
        except Exception as e:
            logger.error(f"更新顾问建议失败: {e}")

    @staticmethod
    def get_trades_pending_4h_backfill(limit=50):
        if not _db_healthy:
            return []
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id, symbol, direction, entry_price, open_time
                    FROM trades
                    WHERE signal_direction_4h_result IS NULL
                    AND open_time < NOW() - INTERVAL '4 hours'
                    AND open_time > NOW() - INTERVAL '72 hours'
                    ORDER BY open_time ASC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"查询待回填交易失败: {e}")
            return []

    @staticmethod
    def update_signal_direction_4h(trade_id: str, direction: str):
        if not _db_healthy:
            return False
        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    UPDATE trades
                    SET signal_direction_4h_result = %s
                    WHERE id = %s
                """, (direction, trade_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"回填4h方向失败 trade={trade_id}: {e}")
            return False
