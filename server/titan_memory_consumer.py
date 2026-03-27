import json
import os
import logging
from datetime import datetime

from server.titan_db import db_connection, TitanDB
from server.titan_external_data import TitanMemoryBank

logger = logging.getLogger("TitanMemoryConsumer")

LOW_RISK_KEYWORDS = [
    '减少', '降低', '避免', '减少交易频率',
    '暂时', '短期', '限制', '监控', '关注',
    '减少此类', '暂停', '收紧',
]
HIGH_CONFIDENCE_KEYWORDS = [
    '重复亏损', '持续亏损', '连续亏损',
    '短持仓', '0-1小时', '短期交易',
    '胜率低', '亏损币种',
]
HIGH_RISK_KEYWORDS = [
    '增加', '提高频率', '更激进',
    '修改止损', '修改止盈', '放宽', '加大',
]


class TitanMemoryConsumer:

    def __init__(self):
        self.memory_bank = TitanMemoryBank()

    def consume_insights(self):
        all_unconsumed = self._get_unconsumed_insights()
        if not all_unconsumed:
            logger.info("[记忆消费] 无新洞察需要处理")
            return {'processed': 0, 'rules': 0, 'patterns': 0, 'insights': 0, 'snapshots': 0, 'events': 0}

        counts = {'processed': 0, 'rules': 0, 'patterns': 0, 'insights': 0, 'snapshots': 0, 'events': 0}

        for insight in all_unconsumed:
            insight_type = insight.get('type', '')

            try:
                if insight_type == 'rule':
                    self._rule_to_proposal(insight)
                    counts['rules'] += 1
                elif insight_type == 'pattern':
                    self._pattern_to_strength(insight)
                    self._pattern_to_proposal(insight)
                    counts['patterns'] += 1
                elif insight_type == 'insight':
                    self._insight_to_journal(insight)
                    counts['insights'] += 1
                elif insight_type == 'snapshot':
                    self._snapshot_to_context(insight)
                    counts['snapshots'] += 1
                elif insight_type == 'event':
                    self._event_to_journal(insight)
                    counts['events'] += 1

                self._mark_consumed(insight)
                counts['processed'] += 1
            except Exception as e:
                logger.error(f"[记忆消费] 处理洞察失败 #{insight.get('id', '?')}: {e}")

        logger.info(
            f"[记忆消费] 完成: 处理{counts['processed']}条 "
            f"(规则{counts['rules']}/模式{counts['patterns']}/洞察{counts['insights']}"
            f"/快照{counts['snapshots']}/事件{counts['events']})"
        )
        return counts

    def _get_unconsumed_insights(self):
        memories = self.memory_bank.memories
        unconsumed = []
        idx = 0

        category_type_map = {
            'rules': 'rule',
            'insights': 'insight',
            'trade_patterns': 'pattern',
            'performance_snapshots': 'snapshot',
            'market_events': 'event',
            'regime_history': 'event',
        }

        for category, insight_type in category_type_map.items():
            items = memories.get(category, [])
            for list_idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                if item.get('_consumed'):
                    continue

                content = ''
                if category == 'rules':
                    content = item.get('condition', '') or item.get('action', '') or item.get('content', '') or item.get('rule', '')
                elif category == 'insights':
                    content = item.get('insight', '') or item.get('content', '')
                elif category == 'trade_patterns':
                    content = json.dumps(item, ensure_ascii=False)[:300]
                elif category == 'performance_snapshots':
                    parts = []
                    if item.get('win_rate') is not None:
                        parts.append(f"胜率{item['win_rate']}%")
                    if item.get('equity') is not None:
                        parts.append(f"权益{item['equity']}")
                    if item.get('max_drawdown') is not None:
                        parts.append(f"最大回撤{item['max_drawdown']}%")
                    if item.get('regime'):
                        parts.append(f"行情{item['regime']}")
                    ts = item.get('timestamp', '')
                    content = f"[{ts}] " + ' | '.join(parts) if parts else json.dumps(item, ensure_ascii=False)[:200]
                elif category == 'market_events':
                    content = item.get('description', '') or item.get('content', '')
                elif category == 'regime_history':
                    content = f"行情切换: {item.get('from','')} → {item.get('to','')} | {item.get('context','')}"

                unconsumed.append({
                    'id': f"{category}_{idx}",
                    'type': insight_type,
                    'content': content,
                    'symbol': item.get('symbol', ''),
                    'pnl': item.get('pnl_pct', 0),
                    'win_rate': item.get('win_rate'),
                    'result': item.get('result', ''),
                    'strategy': item.get('strategy', ''),
                    'holding_hours': item.get('holding_hours'),
                    '_category': category,
                    '_index': list_idx,
                    '_raw': item,
                })
                idx += 1

        priority_order = {'rule': 0, 'pattern': 1, 'insight': 2, 'event': 3, 'snapshot': 4}
        unconsumed.sort(key=lambda x: priority_order.get(x['type'], 5))
        return unconsumed[:200]

    def _rule_to_proposal(self, insight):
        content = str(insight.get('content', ''))
        if len(content) < 10:
            return

        risk_level = 'medium'
        confidence = 0.60

        if any(kw in content for kw in LOW_RISK_KEYWORDS):
            risk_level = 'low'
            confidence = 0.70

        if any(kw in content for kw in HIGH_CONFIDENCE_KEYWORDS):
            confidence = min(0.85, confidence + 0.15)

        if any(kw in content for kw in HIGH_RISK_KEYWORDS):
            risk_level = 'high'
            confidence = 0.55

        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT id FROM evolution_proposals
                    WHERE evidence LIKE %s
                      AND created_at > NOW() - INTERVAL '30 days'
                    LIMIT 1
                """, (f"%{content[:50]}%",))
                if cur.fetchone():
                    return

                cur.execute("""
                    INSERT INTO evolution_proposals
                    (proposal_type, target, evidence, confidence, risk_level, source, status, created_at, auto_adopted)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', NOW(), false)
                """, (
                    'memory_derived',
                    'signal_filter',
                    content[:500],
                    confidence,
                    risk_level,
                    f"memory_bank:{insight.get('id', '')}",
                ))
                conn.commit()
                logger.info(f"[记忆消费] 规则→proposal [{risk_level}/{confidence:.0%}]: {content[:60]}...")
        except Exception as e:
            logger.error(f"[记忆消费] 规则转proposal失败: {e}")

    def _pattern_to_strength(self, insight):
        symbol = insight.get('symbol', '')
        if not symbol:
            return

        pattern_key = f"symbol:{symbol}:deep_evolution"
        pnl = float(insight.get('pnl', 0) or 0)
        outcome = 1 if pnl > 0 else -1

        TitanDB.update_memory_strength(
            pattern_key=pattern_key,
            outcome=outcome,
            importance=1.2
        )

    def _pattern_to_proposal(self, insight):
        raw = insight.get('_raw', {})
        symbol = insight.get('symbol', '')
        result = raw.get('result', '')
        pnl = float(insight.get('pnl', 0) or 0)
        holding_hours = raw.get('holding_hours')
        strategy = raw.get('strategy', '')

        if not symbol:
            return

        if result == 'loss' and pnl < -1.0:
            evidence = f"{symbol} 亏损{pnl:.2f}%"
            if holding_hours is not None:
                evidence += f" 持仓{holding_hours:.1f}h"
            if strategy:
                evidence += f" 策略{strategy}"

            try:
                with db_connection(dict_cursor=True) as (conn, cur):
                    cur.execute("""
                        SELECT COUNT(*) as cnt FROM evolution_proposals
                        WHERE target = %s AND created_at > NOW() - INTERVAL '7 days'
                    """, (f"symbol_filter:{symbol}",))
                    if cur.fetchone()['cnt'] > 0:
                        return

                    cur.execute("""
                        SELECT COUNT(*) as total,
                               SUM(CASE WHEN pnl_value > 0 THEN 1 ELSE 0 END) as wins
                        FROM trades WHERE symbol = %s AND result IN ('win', 'loss')
                    """, (symbol,))
                    row = cur.fetchone()
                    total = row['total'] or 0
                    wins = row['wins'] or 0

                    if total < 3:
                        return

                    wr = wins / total
                    if wr >= 0.30:
                        return

                    conf = min(0.90, 0.50 + total * 0.05)

                    cur.execute("""
                        INSERT INTO evolution_proposals
                        (proposal_type, target, current_value, suggested_value, evidence,
                         confidence, risk_level, source, status, created_at, auto_adopted)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW(), false)
                    """, (
                        'pattern_derived',
                        f"symbol_filter:{symbol}",
                        'active',
                        'reduce_frequency',
                        f"{symbol}胜率{wr:.0%}(n={total}) | {evidence}",
                        conf,
                        'low',
                        f"trade_pattern:{insight.get('id', '')}",
                    ))
                    conn.commit()
                    logger.info(f"[记忆消费] 模式→proposal: {symbol} 胜率{wr:.0%} n={total}")
            except Exception as e:
                logger.error(f"[记忆消费] 模式转proposal失败: {e}")

    def _insight_to_journal(self, insight):
        content = insight.get('content', '')
        if len(content) < 20:
            return

        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO learning_journal
                    (source, content, priority, consumed_by_cto, created_at)
                    VALUES (%s, %s, %s, false, NOW())
                """, (
                    'memory_consumer',
                    content[:1000],
                    'medium',
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[记忆消费] 写入学习日志失败: {e}")

    def _snapshot_to_context(self, insight):
        content = insight.get('content', '')
        if len(content) < 10:
            return

        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO learning_journal
                    (source, content, priority, consumed_by_cto, created_at)
                    VALUES (%s, %s, %s, false, NOW())
                """, (
                    'performance_snapshot',
                    content[:500],
                    'low',
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[记忆消费] 快照写入学习日志失败: {e}")

    def _event_to_journal(self, insight):
        content = insight.get('content', '')
        if len(content) < 10:
            return

        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO learning_journal
                    (source, content, priority, consumed_by_cto, created_at)
                    VALUES (%s, %s, %s, false, NOW())
                """, (
                    'market_event',
                    content[:500],
                    'medium',
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"[记忆消费] 事件写入学习日志失败: {e}")

    def _mark_consumed(self, insight):
        try:
            category = insight.get('_category', '')
            idx = insight.get('_index', -1)
            items = self.memory_bank.memories.get(category, [])
            if 0 <= idx < len(items):
                if isinstance(items[idx], dict):
                    items[idx]['_consumed'] = True
        except Exception as e:
            logger.warning(f"[记忆消费] 标记已消费失败: {e}")

    def save_all(self):
        self.memory_bank._save()

    def get_status(self):
        memories = self.memory_bank.memories
        total = sum(len(v) for v in memories.values() if isinstance(v, list))
        consumed = 0
        by_category = {}
        for cat_name, cat in memories.items():
            if isinstance(cat, list):
                cat_consumed = sum(1 for item in cat if isinstance(item, dict) and item.get('_consumed'))
                consumed += cat_consumed
                by_category[cat_name] = {'total': len(cat), 'consumed': cat_consumed}

        journal_count = 0
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("SELECT COUNT(*) as cnt FROM learning_journal")
                journal_count = cur.fetchone()['cnt']
        except Exception:
            pass

        return {
            'total_memories': total,
            'consumed': consumed,
            'unconsumed': total - consumed,
            'journal_entries': journal_count,
            'by_category': by_category,
        }
