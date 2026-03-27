import re
import logging
from server.titan_db import db_connection

logger = logging.getLogger("TitanProposalTranslator")


class TitanProposalTranslator:

    def translate_pending_proposals(self):
        translated = 0
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id, proposal_type, target, current_value, suggested_value,
                           evidence, confidence, risk_level, source
                    FROM evolution_proposals
                    WHERE status = 'pending'
                      AND target = 'signal_filter'
                    ORDER BY confidence DESC
                    LIMIT 50
                """)
                pending = cur.fetchall()
        except Exception as e:
            logger.error(f"[转化器] 查询pending提案失败: {e}")
            return 0

        for proposal in pending:
            result = self._translate(proposal)
            if result:
                translated += 1

        logger.info(f"[转化器] {translated}/{len(pending)}条提案已转化")
        return translated

    def _translate(self, proposal):
        evidence = proposal.get('evidence', '') or ''

        if self._match_repeat_loser(evidence):
            symbol = self._extract_symbol(evidence)
            if symbol:
                return self._create_symbol_penalty(symbol, proposal)

        if self._match_short_hold(evidence):
            return self._create_hold_time_param(proposal)

        if self._match_session(evidence, 'asia'):
            return self._create_session_param('asia', -3, proposal)
        if self._match_session(evidence, 'us'):
            return self._create_session_param('us', -2, proposal)

        if self._match_low_winrate_symbol(evidence):
            symbol = self._extract_symbol(evidence)
            if symbol:
                return self._create_symbol_penalty(symbol, proposal)

        return None

    def _match_repeat_loser(self, evidence):
        keywords = ['重复亏损', '连续亏损', 'repeat loser', '反复亏损', '多次亏损']
        return any(k in evidence.lower() for k in keywords)

    def _match_short_hold(self, evidence):
        keywords = ['短持仓', '0-1小时', '1-4小时持仓', '短期持仓', '持仓时间过短']
        return any(k in evidence for k in keywords)

    def _match_session(self, evidence, session):
        if session == 'asia':
            return '亚洲时段' in evidence or '亚盘' in evidence
        if session == 'us':
            return '美盘' in evidence or '美国时段' in evidence
        return False

    def _match_low_winrate_symbol(self, evidence):
        keywords = ['胜率低', '低胜率', '减少交易频率', '暂停或减少', '关注胜率']
        return any(k in evidence for k in keywords)

    def _create_symbol_penalty(self, symbol, proposal):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN pnl_value > 0 THEN 1 ELSE 0 END) as wins
                    FROM trades
                    WHERE symbol = %s AND result IN ('win', 'loss')
                """, (symbol,))
                stats = cur.fetchone()

                total = stats['total'] or 0
                wins = stats['wins'] or 0

                if total < 3:
                    return None

                wr = wins / total

                if wr >= 0.30:
                    return None

                conf = min(0.85, 0.50 + total * 0.05)

                cur.execute("""
                    SELECT id FROM evolution_proposals
                    WHERE target = 'symbol_score_penalty'
                      AND evidence LIKE %s
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 1
                """, (f"%{symbol}%",))
                if cur.fetchone():
                    self._mark_translated(conn, cur, proposal['id'])
                    conn.commit()
                    return True

                cur.execute("""
                    INSERT INTO evolution_proposals
                    (proposal_type, target, current_value, suggested_value,
                     evidence, confidence, risk_level, source, status, created_at, auto_adopted)
                    VALUES ('translated', 'symbol_score_penalty', '0', '-8',
                            %s, %s, 'low', %s, 'pending', NOW(), false)
                """, (
                    f"{symbol}历史胜率{wr:.0%}(n={total})，评分惩罚-8分",
                    conf,
                    f"translated:{proposal['id']}",
                ))

                self._mark_translated(conn, cur, proposal['id'])
                conn.commit()
                logger.info(f"[转化器] symbol_penalty: {symbol} 胜率{wr:.0%} n={total}")
                return True

        except Exception as e:
            logger.error(f"[转化器] symbol_penalty创建失败: {e}")
            return None

    def _create_hold_time_param(self, proposal):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id FROM evolution_proposals
                    WHERE target = 'hold_time_protection_enabled'
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 1
                """)
                if cur.fetchone():
                    self._mark_translated(conn, cur, proposal['id'])
                    conn.commit()
                    return True

                cur.execute("""
                    INSERT INTO evolution_proposals
                    (proposal_type, target, current_value, suggested_value,
                     evidence, confidence, risk_level, source, status, created_at, auto_adopted)
                    VALUES ('translated', 'hold_time_protection_enabled', 'false', 'true',
                            %s, 0.80, 'low', %s, 'pending', NOW(), false)
                """, (
                    '短持仓胜率22.7% vs 长持仓50%，建议启用持仓时间保护',
                    f"translated:{proposal['id']}",
                ))

                self._mark_translated(conn, cur, proposal['id'])
                conn.commit()
                logger.info("[转化器] hold_time_protection: 已创建")
                return True

        except Exception as e:
            logger.error(f"[转化器] hold_time_param创建失败: {e}")
            return None

    def _create_session_param(self, session, penalty, proposal):
        param_key = f'{session}_session_bonus'
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id FROM evolution_proposals
                    WHERE target = %s
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 1
                """, (param_key,))
                if cur.fetchone():
                    self._mark_translated(conn, cur, proposal['id'])
                    conn.commit()
                    return True

                cur.execute("""
                    INSERT INTO evolution_proposals
                    (proposal_type, target, current_value, suggested_value,
                     evidence, confidence, risk_level, source, status, created_at, auto_adopted)
                    VALUES ('translated', %s, '0', %s,
                            %s, 0.72, 'low', %s, 'pending', NOW(), false)
                """, (
                    param_key,
                    str(penalty),
                    (proposal.get('evidence', '') or '')[:200],
                    f"translated:{proposal['id']}",
                ))

                self._mark_translated(conn, cur, proposal['id'])
                conn.commit()
                logger.info(f"[转化器] session_param: {param_key}={penalty}")
                return True

        except Exception as e:
            logger.error(f"[转化器] session_param创建失败: {e}")
            return None

    def _mark_translated(self, conn, cur, proposal_id):
        cur.execute("""
            UPDATE evolution_proposals
            SET status = 'translated'
            WHERE id = %s
        """, (proposal_id,))

    def _extract_symbol(self, text):
        known_symbols = [
            'BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'ADA', 'AVAX', 'DOT', 'LINK',
            'MATIC', 'UNI', 'AAVE', 'FIL', 'ATOM', 'NEAR', 'OP', 'ARB', 'APT',
            'SUI', 'SEI', 'TIA', 'JUP', 'WIF', 'PEPE', 'BONK', 'FLOKI',
            'SHIB', 'LTC', 'BCH', 'ETC', 'ZEC', 'DASH', 'XMR', 'ZEN',
            'STABLE', 'KITE', 'POWER', 'RENDER', 'INJ', 'FET', 'ONDO',
            'PENDLE', 'STX', 'RUNE', 'MKR', 'COMP', 'SNX', 'CRV', 'LDO',
            'DYDX', 'GMX', 'ENS', 'GRT', 'SAND', 'MANA', 'AXS', 'IMX',
        ]

        for sym in known_symbols:
            if sym in text.upper():
                idx = text.upper().index(sym)
                if idx == 0 or not text[idx - 1].isalpha():
                    end_idx = idx + len(sym)
                    if end_idx >= len(text) or not text[end_idx].isalpha():
                        return sym
        return None
