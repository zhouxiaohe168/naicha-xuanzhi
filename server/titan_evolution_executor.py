import json
import os
import logging
from datetime import datetime

from server.titan_db import db_connection, TitanDB
from server.titan_utils import atomic_json_save

logger = logging.getLogger("TitanEvolutionExecutor")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "titan_config.json")


class TitanEvolutionExecutor:

    SAFE_AUTO_PARAMS = {
        'asia_session_bonus': (-10, 0),
        'europe_session_bonus': (0, 10),
        'us_session_bonus': (0, 10),
        'fng_extreme_penalty': (-20, -5),
        'min_signal_score': (70, 78),
        'hold_time_protection_enabled': (False, True),
        'scan_interval_seconds': (600, 1800),
        'signal_gate_4h_filter': (False, True),
        'min_sl_distance': (0.02, 0.05),
        'volatile_long_ban': (False, True),
    }

    SAFE_CRITIC_BANS = {
        'critic_ban_',
    }

    def run_auto_adopt(self):
        adopted = []
        skipped = []

        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM evolution_proposals
                    WHERE status = 'pending'
                      AND risk_level IN ('low', 'medium')
                      AND confidence >= 0.75
                      AND (auto_adopted = false OR auto_adopted IS NULL)
                    ORDER BY confidence DESC
                """)
                pending = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询pending proposals失败: {e}")
            return {'adopted': adopted, 'skipped': skipped}

        for proposal in pending:
            target = proposal.get('target', '')
            suggested = proposal.get('suggested_value', '')

            is_critic_ban = any(target.startswith(prefix) for prefix in self.SAFE_CRITIC_BANS)

            if is_critic_ban:
                confidence = float(proposal.get('confidence', 0))
                if confidence < 0.80:
                    skipped.append({
                        'id': proposal['id'],
                        'reason': f'Critic ban置信度{confidence}<0.80'
                    })
                    continue
                success = self._apply_critic_ban(proposal)
            elif target in self.SAFE_AUTO_PARAMS:
                bounds = self.SAFE_AUTO_PARAMS[target]
                if isinstance(bounds[0], bool):
                    if str(suggested).lower() not in ('true', 'false', '0', '1'):
                        skipped.append({
                            'id': proposal['id'],
                            'reason': f'布尔参数值无效: {suggested}'
                        })
                        continue
                else:
                    try:
                        val = float(suggested)
                        if not (bounds[0] <= val <= bounds[1]):
                            skipped.append({
                                'id': proposal['id'],
                                'reason': f'值{val}超出安全范围{bounds}'
                            })
                            continue
                    except (ValueError, TypeError):
                        skipped.append({
                            'id': proposal['id'],
                            'reason': f'值{suggested}无法转换为数字'
                        })
                        continue
                success = self._apply_config_change(
                    target,
                    proposal.get('current_value'),
                    suggested
                )
            else:
                skipped.append({
                    'id': proposal['id'],
                    'reason': f'{target}不在安全白名单'
                })
                continue

            if success:
                try:
                    with db_connection() as (conn, cur):
                        cur.execute("""
                            UPDATE evolution_proposals
                            SET status = 'auto_adopted',
                                auto_adopted = true,
                                adopted_at = NOW()
                            WHERE id = %s
                        """, (proposal['id'],))
                        conn.commit()
                except Exception as e:
                    logger.error(f"更新proposal状态失败: {e}")
                    continue

                self._record_baseline(proposal['id'])
                adopted.append(proposal)
                logger.info(
                    f"[进化] 自动采纳: {target} "
                    f"{proposal.get('current_value')} → {suggested} "
                    f"(置信度{float(proposal.get('confidence', 0)):.0%})"
                )

        return {'adopted': adopted, 'skipped': skipped}

    def _apply_config_change(self, key, old_val, new_val):
        try:
            config = {}
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)

            if 'evolution_backups' not in config:
                config['evolution_backups'] = {}
            config['evolution_backups'][key] = {
                'original': old_val,
                'changed_at': datetime.now().isoformat()
            }

            try:
                new_val_parsed = json.loads(str(new_val))
            except (json.JSONDecodeError, TypeError):
                new_val_parsed = new_val

            config[key] = new_val_parsed
            config['last_evolution_update'] = datetime.now().isoformat()

            atomic_json_save(CONFIG_PATH, config)
            logger.info(f"[进化] 配置已更新: {key} = {new_val_parsed}")
            return True
        except Exception as e:
            logger.error(f"配置修改失败: {e}")
            return False

    def _apply_critic_ban(self, proposal):
        try:
            target = proposal.get('target', '')
            notes = proposal.get('notes', '')
            confidence = float(proposal.get('confidence', 0))

            config = {}
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)

            if 'critic_bans' not in config:
                config['critic_bans'] = []

            ban_entry = {
                'rule': target,
                'confidence': confidence,
                'notes': notes[:200] if notes else '',
                'adopted_at': datetime.now().isoformat(),
                'proposal_id': proposal.get('id'),
            }

            existing = [b.get('rule') for b in config['critic_bans']]
            if target in existing:
                logger.info(f"[进化] Critic ban已存在: {target}")
                return True

            config['critic_bans'].append(ban_entry)
            config['last_evolution_update'] = datetime.now().isoformat()
            atomic_json_save(CONFIG_PATH, config)

            try:
                with db_connection() as (conn, cur):
                    cur.execute("""
                        INSERT INTO learning_journal (source, content, priority, consumed_by_cto)
                        VALUES (%s, %s, %s, false)
                    """, ("config_change", f"Critic ban自动采纳: {target} (置信度{confidence})", "high"))
                    conn.commit()
            except Exception:
                pass

            logger.info(f"[进化] Critic ban已采纳: {target} (置信度{confidence:.0%})")
            return True
        except Exception as e:
            logger.error(f"Critic ban应用失败: {e}")
            return False

    def _record_baseline(self, proposal_id):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN pnl_value > 0 THEN 1 ELSE 0 END) as wins
                    FROM trades
                    WHERE created_at > NOW() - INTERVAL '7 days'
                      AND result IN ('win', 'loss')
                """)
                row = cur.fetchone()
                total = row['total'] or 0
                wins = row['wins'] or 0
                baseline_wr = wins / total if total > 0 else None

                cur.execute("""
                    UPDATE evolution_proposals
                    SET baseline_win_rate = %s,
                        review_due_at = NOW() + INTERVAL '7 days'
                    WHERE id = %s
                """, (baseline_wr, proposal_id))
                conn.commit()
        except Exception as e:
            logger.error(f"记录基准胜率失败: {e}")

    def check_effects(self):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM evolution_proposals
                    WHERE status = 'auto_adopted'
                      AND review_due_at <= NOW()
                      AND result_7d IS NULL
                """)
                due_reviews = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"查询待验证proposals失败: {e}")
            return

        for proposal in due_reviews:
            current_wr = self._get_win_rate_since(proposal.get('adopted_at'))
            baseline_wr = proposal.get('baseline_win_rate')

            if baseline_wr is None or current_wr is None:
                try:
                    with db_connection() as (conn, cur):
                        cur.execute("""
                            UPDATE evolution_proposals
                            SET review_due_at = NOW() + INTERVAL '7 days',
                                notes = COALESCE(notes, '') || '数据不足，延期7天; '
                            WHERE id = %s
                        """, (proposal['id'],))
                        conn.commit()
                    logger.info(f"[进化] 效果验证延期: {proposal.get('target')} (数据不足)")
                except Exception as e:
                    logger.error(f"延期验证失败: {e}")
                continue

            improvement = current_wr - float(baseline_wr)

            if improvement >= -0.02:
                try:
                    with db_connection() as (conn, cur):
                        cur.execute("""
                            UPDATE evolution_proposals
                            SET result_7d = %s,
                                status = 'verified_effective'
                            WHERE id = %s
                        """, (round(improvement, 4), proposal['id']))
                        conn.commit()
                except Exception as e:
                    logger.error(f"标记验证有效失败: {e}")

                logger.info(
                    f"[进化] 效果验证通过: "
                    f"{proposal.get('target')} "
                    f"胜率变化{improvement:+.1%} ✅"
                )
            else:
                self._rollback(proposal)
                logger.warning(
                    f"[进化] 效果不佳，已回滚: "
                    f"{proposal.get('target')} "
                    f"胜率变化{improvement:+.1%} ⚠️"
                )

    def _rollback(self, proposal):
        self._apply_config_change(
            proposal.get('target', ''),
            proposal.get('suggested_value'),
            proposal.get('current_value')
        )

        improvement = None
        current_wr = self._get_win_rate_since(proposal.get('adopted_at'))
        baseline_wr = proposal.get('baseline_win_rate')
        if current_wr is not None and baseline_wr is not None:
            improvement = round(current_wr - float(baseline_wr), 4)

        try:
            with db_connection() as (conn, cur):
                cur.execute("""
                    UPDATE evolution_proposals
                    SET status = 'rolled_back',
                        result_7d = %s
                    WHERE id = %s
                """, (improvement, proposal['id']))
                conn.commit()
        except Exception as e:
            logger.error(f"回滚状态更新失败: {e}")

    def _get_win_rate_since(self, since_time):
        if since_time is None:
            return None
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN pnl_value > 0 THEN 1 ELSE 0 END) as wins
                    FROM trades
                    WHERE created_at > %s
                      AND result IN ('win', 'loss')
                """, (since_time,))
                row = cur.fetchone()
                total = row['total'] or 0
                wins = row['wins'] or 0
                if total < 5:
                    return None
                return wins / total
        except Exception as e:
            logger.error(f"查询胜率失败: {e}")
            return None

    def get_status(self):
        try:
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT status, COUNT(*) as cnt
                    FROM evolution_proposals
                    GROUP BY status
                """)
                status_counts = {r['status']: r['cnt'] for r in cur.fetchall()}

                cur.execute("""
                    SELECT id, target, status, result_7d, baseline_win_rate, review_due_at, adopted_at
                    FROM evolution_proposals
                    WHERE status IN ('auto_adopted', 'verified_effective', 'rolled_back')
                    ORDER BY adopted_at DESC NULLS LAST
                    LIMIT 10
                """)
                recent_auto = [dict(r) for r in cur.fetchall()]

            return {
                'status_counts': status_counts,
                'recent_auto_actions': recent_auto,
                'safe_params': list(self.SAFE_AUTO_PARAMS.keys()),
            }
        except Exception as e:
            logger.error(f"获取进化执行器状态失败: {e}")
            return {'status_counts': {}, 'recent_auto_actions': [], 'safe_params': []}
