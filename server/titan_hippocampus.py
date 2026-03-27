import numpy as np
import logging
import time
from collections import defaultdict

logger = logging.getLogger("TitanHippocampus")


class TitanHippocampus:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = TitanHippocampus()
        return cls._instance

    def __init__(self, window_size=30, top_k=7, future_horizon=12):
        self.window_size = window_size
        self.top_k = top_k
        self.future_horizon = future_horizon
        self.memory_banks = defaultdict(lambda: {"vectors": None, "returns": None, "count": 0})
        self.stats = {"total_memories": 0, "assets_loaded": 0, "recalls": 0, "avg_recall_ms": 0}
        TitanHippocampus._instance = self

    def _normalize(self, series):
        mean = np.mean(series)
        std = np.std(series)
        if std < 1e-10:
            return np.zeros_like(series, dtype=np.float32)
        return ((series - mean) / std).astype(np.float32)

    def memorize(self, symbol, closes):
        closes = np.asarray(closes, dtype=np.float64)
        if len(closes) < self.window_size + self.future_horizon + 10:
            return False

        n = len(closes) - self.window_size - self.future_horizon
        if n <= 0:
            return False

        vectors = np.zeros((n, self.window_size), dtype=np.float32)
        returns = np.zeros(n, dtype=np.float32)

        for i in range(n):
            pattern = closes[i: i + self.window_size]
            vectors[i] = self._normalize(pattern)
            current_price = closes[i + self.window_size - 1]
            future_price = closes[i + self.window_size + self.future_horizon - 1]
            if current_price > 0:
                returns[i] = (future_price - current_price) / current_price

        self.memory_banks[symbol] = {"vectors": vectors, "returns": returns, "count": n}
        self.stats["total_memories"] = sum(b["count"] for b in self.memory_banks.values())
        self.stats["assets_loaded"] = len(self.memory_banks)
        return True

    def recall(self, symbol, current_closes):
        if symbol not in self.memory_banks or self.memory_banks[symbol]["vectors"] is None:
            return None

        current_closes = np.asarray(current_closes, dtype=np.float64)
        if len(current_closes) < self.window_size:
            return None

        t0 = time.time()
        current_pattern = self._normalize(current_closes[-self.window_size:])
        bank = self.memory_banks[symbol]
        vectors = bank["vectors"]
        bank_returns = bank["returns"]

        diffs = vectors - current_pattern
        distances = np.sqrt(np.sum(diffs ** 2, axis=1))

        top_k = min(self.top_k, len(distances))
        top_indices = np.argpartition(distances, top_k)[:top_k]
        top_indices = top_indices[np.argsort(distances[top_indices])]

        top_distances = distances[top_indices]
        top_returns = bank_returns[top_indices]

        weights = 1.0 / (1.0 + top_distances)
        weights /= weights.sum()

        weighted_return = float(np.dot(weights, top_returns))
        win_count = int(np.sum(top_returns > 0))
        weighted_win_rate = float(np.sum(weights[top_returns > 0]))

        avg_similarity = float(np.mean(1.0 / (1.0 + top_distances)))
        max_similarity = float(1.0 / (1.0 + top_distances[0]))

        if weighted_return > 0.005:
            signal = "BULLISH"
            confidence = weighted_win_rate
        elif weighted_return < -0.005:
            signal = "BEARISH"
            confidence = 1.0 - weighted_win_rate
        else:
            signal = "NEUTRAL"
            confidence = 0.5

        elapsed_ms = (time.time() - t0) * 1000
        self.stats["recalls"] += 1
        self.stats["avg_recall_ms"] = round(
            (self.stats["avg_recall_ms"] * (self.stats["recalls"] - 1) + elapsed_ms) / self.stats["recalls"], 2
        )

        narrative = []
        for rank, idx in enumerate(top_indices[:3]):
            direction = "涨" if bank_returns[idx] > 0 else "跌"
            sim = 1.0 / (1.0 + distances[idx])
            narrative.append(
                f"#{rank+1} 相似度{sim:.2f} -> 后来{direction}了{bank_returns[idx]*100:.1f}%"
            )

        return {
            "signal": signal,
            "confidence": round(confidence, 3),
            "expected_return": round(weighted_return, 5),
            "avg_similarity": round(avg_similarity, 3),
            "max_similarity": round(max_similarity, 3),
            "win_rate": round(win_count / top_k, 3),
            "narrative": narrative,
        }

    def get_ml_features(self, symbol, current_closes):
        result = self.recall(symbol, current_closes)
        if result is None:
            return {"hip_signal": 0, "hip_confidence": 0, "hip_expected_return": 0, "hip_similarity": 0}
        signal_val = 1 if result["signal"] == "BULLISH" else (-1 if result["signal"] == "BEARISH" else 0)
        return {
            "hip_signal": signal_val,
            "hip_confidence": result["confidence"],
            "hip_expected_return": result["expected_return"],
            "hip_similarity": result["avg_similarity"],
        }

    def get_status(self):
        return {
            "total_memories": self.stats["total_memories"],
            "assets_loaded": self.stats["assets_loaded"],
            "recalls": self.stats["recalls"],
            "avg_recall_ms": self.stats["avg_recall_ms"],
            "memory_details": {
                sym: {"count": b["count"]}
                for sym, b in self.memory_banks.items()
                if b["count"] > 0
            },
        }


hippocampus = TitanHippocampus.get_instance()
