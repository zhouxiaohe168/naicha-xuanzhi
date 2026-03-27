import logging
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List

logger = logging.getLogger("TitanStrategyBrain")


class TitanStrategyBrain:
    """策略脑 - 指标权重自适应学习

    Shadow模式运行：根据历史交易结果学习各技术指标的预测权重，
    结果写入strategy_weights表，不影响任何交易决策。
    Phase 1第2周激活，Phase 2替换硬编码权重。
    """

    DEFAULT_WEIGHTS = {
        "rsi": 1.0,
        "adx": 1.0,
        "bb": 1.0,
        "volume": 1.0,
        "fng": 1.0,
        "hold_time": 1.0,
        "funding": 1.0,
        "session": 1.0,
    }

    def __init__(self):
        self.shadow_mode = True
        self.weights = dict(self.DEFAULT_WEIGHTS)
        self._learning_rate = 0.01
        self._sample_count = 0
        self._prediction_accuracy = 0.0
        logger.info("[StrategyBrain] 初始化完成 (Shadow模式)")

    def learn_from_trade(self, trade: dict, entry_indicators: dict) -> Dict[str, float]:
        """从已完成的交易学习指标权重

        Args:
            trade: 已关闭的交易记录 (含result, pnl_pct等)
            entry_indicators: 开仓时的指标值 (RSI, ADX, BB等)

        Returns:
            更新后的权重字典
        """
        if not entry_indicators:
            return dict(self.weights)

        is_win = trade.get("result") == "win"
        self._update_weights(entry_indicators, is_win)
        self._sample_count += 1

        if self.shadow_mode:
            self._record_weights()

        return dict(self.weights)

    def get_weighted_score(self, indicators: dict) -> float:
        """用当前权重计算加权评分 (Shadow模式下仅记录，不返回给决策)

        Args:
            indicators: 当前指标值

        Returns:
            0~100 加权评分
        """
        return 50.0

    def get_weights(self) -> Dict[str, float]:
        """获取当前指标权重"""
        return dict(self.weights)

    def get_current_weights(self) -> Dict[str, float]:
        """获取当前权重（对外统一接口）"""
        return dict(self.weights)

    def update_weights_daily(self):
        """每日权重更新（从DB中学习最近交易）"""
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT extra, result, pnl_pct
                    FROM trades
                    WHERE close_time IS NOT NULL
                      AND open_time >= NOW() - INTERVAL '7 days'
                    ORDER BY close_time DESC
                    LIMIT 50
                """)
                trades = [dict(r) for r in cur.fetchall()]

            if len(trades) < 5:
                logger.info("[StrategyBrain] 交易数据不足(<5), 跳过权重更新")
                return

            for trade in trades:
                entry_indicators = {}
                extra = trade.get("extra")
                if extra and isinstance(extra, dict):
                    entry_indicators = extra.get("entry_indicators", {})
                self.learn_from_trade(trade, entry_indicators)

            logger.info(f"[StrategyBrain] 日更新完成, {len(trades)}笔交易, 样本总数={self._sample_count}")
        except Exception as e:
            logger.warning(f"[StrategyBrain] 日更新异常: {e}")

    def get_weight_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """从DB获取历史权重变化

        Args:
            days: 回溯天数

        Returns:
            权重历史记录列表
        """
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM strategy_weights
                    WHERE updated_at >= NOW() - INTERVAL '%s days'
                    ORDER BY updated_at DESC
                    LIMIT 100
                """, (days,))
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning(f"[StrategyBrain] 查询权重历史失败: {e}")
            return []

    def _update_weights(self, indicators: dict, is_win: bool):
        """根据交易结果调整权重 (stub: Phase 2实现梯度学习)

        当前实现：简单的赢/亏反馈，后续升级为在线梯度下降
        """
        pass

    def _record_weights(self):
        """写入strategy_weights表 (fire-and-forget)"""
        try:
            from server.titan_db import db_connection
            with db_connection() as (conn, cur):
                cur.execute("""
                    INSERT INTO strategy_weights
                    (rsi_weight, adx_weight, bb_weight, volume_weight,
                     fng_weight, hold_time_weight, funding_weight, session_weight,
                     sample_size, prediction_accuracy)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.weights["rsi"],
                    self.weights["adx"],
                    self.weights["bb"],
                    self.weights["volume"],
                    self.weights["fng"],
                    self.weights["hold_time"],
                    self.weights["funding"],
                    self.weights["session"],
                    self._sample_count,
                    self._prediction_accuracy,
                ))
                conn.commit()
        except Exception as e:
            logger.warning(f"[StrategyBrain] 记录权重失败: {e}")

    def load_latest_weights(self):
        """从DB加载最新权重"""
        try:
            from server.titan_db import db_connection
            with db_connection(dict_cursor=True) as (conn, cur):
                cur.execute("""
                    SELECT * FROM strategy_weights
                    ORDER BY updated_at DESC LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    for key in self.DEFAULT_WEIGHTS:
                        db_key = f"{key}_weight"
                        if db_key in row and row[db_key] is not None:
                            self.weights[key] = float(row[db_key])
                    self._sample_count = row.get("sample_size", 0) or 0
                    self._prediction_accuracy = float(row.get("prediction_accuracy", 0) or 0)
                    logger.info(f"[StrategyBrain] 加载权重成功, 样本数={self._sample_count}")
        except Exception as e:
            logger.warning(f"[StrategyBrain] 加载权重失败: {e}")

    def get_status(self) -> dict:
        """返回模块状态摘要"""
        return {
            "module": "StrategyBrain",
            "shadow_mode": self.shadow_mode,
            "sample_count": self._sample_count,
            "prediction_accuracy": round(self._prediction_accuracy, 2),
            "weights": {k: round(v, 3) for k, v in self.weights.items()},
            "status": "shadow" if self.shadow_mode else "active",
        }
