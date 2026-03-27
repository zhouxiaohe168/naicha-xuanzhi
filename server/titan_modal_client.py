import os
import json
import time
import logging
import asyncio
import joblib
from datetime import datetime

logger = logging.getLogger("TitanModalClient")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "data", "titan_ml_model.pkl")
METRICS_PATH = os.path.join(BASE_DIR, "data", "titan_ml_metrics.json")
META_LABELER_PATH = os.path.join(BASE_DIR, "data", "titan_meta_labeler.pkl")
MODAL_STATE_PATH = os.path.join(BASE_DIR, "data", "modal_training_state.json")

MODAL_APP_NAME = "titan-ml-training"


def _check_modal_auth():
    token_id = os.environ.get("MODAL_TOKEN_ID")
    token_secret = os.environ.get("MODAL_TOKEN_SECRET")
    if not token_id or not token_secret:
        raise RuntimeError("MODAL_TOKEN_ID / MODAL_TOKEN_SECRET 未设置")
    return True


def _load_state():
    try:
        if os.path.exists(MODAL_STATE_PATH):
            with open(MODAL_STATE_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {
        "last_training": None,
        "last_success": None,
        "call_id": None,
        "status": "idle",
        "error": None,
    }


def _save_state(state):
    try:
        os.makedirs(os.path.dirname(MODAL_STATE_PATH), exist_ok=True)
        with open(MODAL_STATE_PATH, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存Modal状态失败: {e}")


async def trigger_training(symbols=None, max_assets=69):
    _check_modal_auth()

    state = _load_state()
    if state.get("status") == "running":
        return {"status": "already_running", "call_id": state.get("call_id")}

    state["status"] = "running"
    state["last_training"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["error"] = None
    _save_state(state)

    try:
        import modal
        train_fn = modal.Function.from_name(MODAL_APP_NAME, "train_titan_ml")

        kwargs = {"max_assets": max_assets}
        if symbols:
            kwargs["symbols"] = symbols

        try:
            call = await train_fn.spawn.aio(**kwargs)
        except (TypeError, AttributeError):
            call = train_fn.spawn(**kwargs)
        call_id = call.object_id

        state["call_id"] = call_id
        _save_state(state)

        logger.info(f"[Modal] 训练任务已提交, call_id={call_id}")
        return {"status": "submitted", "call_id": call_id}

    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)[:200]
        _save_state(state)
        logger.error(f"[Modal] 提交训练失败: {e}")
        return {"status": "error", "error": str(e)[:200]}


async def check_training_status():
    state = _load_state()

    if state.get("status") != "running" or not state.get("call_id"):
        return state

    if state.get("last_training"):
        try:
            started = datetime.strptime(state["last_training"], "%Y-%m-%d %H:%M:%S")
            age_seconds = (datetime.now() - started).total_seconds()
            if age_seconds > 2400:
                state["status"] = "timeout"
                state["error"] = f"训练超过{int(age_seconds/60)}分钟无响应，已标记超时"
                _save_state(state)
                return state
        except Exception:
            pass

    try:
        import modal
        call = modal.FunctionCall.from_id(state["call_id"])

        try:
            result = call.get(timeout=0)

            if result.get("success"):
                state["status"] = "completed"
                state["last_success"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state["result"] = {
                    "accuracy": result.get("metrics", {}).get("accuracy"),
                    "f1": result.get("metrics", {}).get("f1"),
                    "samples": result.get("metrics", {}).get("samples_trained"),
                    "elapsed": result.get("elapsed"),
                    "assets": result.get("assets_fetched"),
                    "ensemble": result.get("metrics", {}).get("ensemble_type"),
                }
                state["error"] = None
                logger.info(f"[Modal] 训练完成! 准确率={state['result']['accuracy']}%")
            else:
                state["status"] = "failed"
                state["error"] = result.get("error", "训练失败")
                logger.warning(f"[Modal] 训练失败: {state['error']}")

        except TimeoutError:
            state["status"] = "running"

        except Exception as e:
            err_str = str(e)
            if "still running" in err_str.lower() or "pending" in err_str.lower():
                state["status"] = "running"
            elif "not found" in err_str.lower() or "expired" in err_str.lower():
                state["status"] = "error"
                state["error"] = "训练任务已过期或不存在"
            else:
                state["status"] = "error"
                state["error"] = err_str[:200]

    except Exception as e:
        state["error"] = str(e)[:200]
        logger.error(f"[Modal] 状态检查失败: {e}")

    _save_state(state)
    return state


async def download_and_install_model(ml_engine=None):
    _check_modal_auth()

    try:
        import modal
        download_fn = modal.Function.from_name(MODAL_APP_NAME, "download_model")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_fn.remote)

        if not result.get("success"):
            return {"status": "error", "error": result.get("error", "下载失败")}

        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

        model_bytes = result["model"]
        with open(MODEL_PATH, "wb") as f:
            f.write(model_bytes)
        logger.info(f"[Modal] 模型已下载: {len(model_bytes)} bytes")

        if "metrics" in result:
            with open(METRICS_PATH, "w") as f:
                json.dump(result["metrics"], f, ensure_ascii=False, indent=2)
            logger.info("[Modal] 指标已保存")

        if "meta_labeler" in result:
            with open(META_LABELER_PATH, "wb") as f:
                f.write(result["meta_labeler"])
            logger.info("[Modal] Meta-labeler已保存")

        if ml_engine is not None:
            ml_engine.model = joblib.load(MODEL_PATH)
            ml_engine.is_trained = True
            ml_engine.last_train_time = result.get("metrics", {}).get("last_train", "")
            ml_engine.metrics.update(result.get("metrics", {}))
            train_count = ml_engine.metrics.get("train_count", 0) + 1
            ml_engine.metrics["train_count"] = train_count
            ml_engine.metrics["model_version"] = f"RG-Modal-v{train_count}"
            ml_engine._save_metrics()

            if "meta_labeler" in result:
                ml_engine._meta_labeler = joblib.load(META_LABELER_PATH)

            logger.info("[Modal] ML引擎已热更新")

        state = _load_state()
        state["status"] = "installed"
        state["last_install"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_state(state)

        return {
            "status": "ok",
            "accuracy": result.get("metrics", {}).get("accuracy"),
            "f1": result.get("metrics", {}).get("f1"),
            "samples": result.get("metrics", {}).get("samples_trained"),
        }

    except Exception as e:
        logger.error(f"[Modal] 模型下载失败: {e}")
        return {"status": "error", "error": str(e)[:200]}


async def train_and_wait(symbols=None, max_assets=69, ml_engine=None, progress_callback=None):
    _check_modal_auth()

    if progress_callback:
        progress_callback("提交训练任务到Modal云端...")

    submit_result = await trigger_training(symbols, max_assets)
    if submit_result.get("status") not in ("submitted",):
        return submit_result

    if progress_callback:
        progress_callback("训练进行中... (数据获取+模型训练)")

    max_wait = 1800
    start = time.time()
    while time.time() - start < max_wait:
        await asyncio.sleep(15)
        status = await check_training_status()

        elapsed = round(time.time() - start)
        if progress_callback:
            progress_callback(f"训练中... 已等待{elapsed}秒 状态={status.get('status')}")

        if status.get("status") == "completed":
            if progress_callback:
                progress_callback("训练完成! 正在下载模型...")

            install_result = await download_and_install_model(ml_engine)
            return {
                "status": "ok",
                "training": status.get("result", {}),
                "install": install_result,
                "elapsed": elapsed,
            }

        if status.get("status") in ("failed", "error"):
            return {"status": "failed", "error": status.get("error"), "elapsed": elapsed}

    return {"status": "timeout", "elapsed": max_wait}


def get_modal_status():
    state = _load_state()
    has_auth = bool(os.environ.get("MODAL_TOKEN_ID")) and bool(os.environ.get("MODAL_TOKEN_SECRET"))
    return {
        "configured": has_auth,
        "status": state.get("status", "idle"),
        "last_training": state.get("last_training"),
        "last_success": state.get("last_success"),
        "last_result": state.get("result"),
        "error": state.get("error"),
    }


MM_MODEL_PATH = os.path.join(BASE_DIR, "data", "titan_mm_model.pkl")
MM_METRICS_PATH = os.path.join(BASE_DIR, "data", "titan_mm_metrics.json")
MM_STATE_PATH = os.path.join(BASE_DIR, "data", "modal_mm_training_state.json")


def _load_mm_state():
    try:
        if os.path.exists(MM_STATE_PATH):
            with open(MM_STATE_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"status": "idle", "last_training": None, "last_success": None, "call_id": None, "error": None}


def _save_mm_state(state):
    try:
        os.makedirs(os.path.dirname(MM_STATE_PATH), exist_ok=True)
        with open(MM_STATE_PATH, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存MM状态失败: {e}")


async def trigger_mm_training(symbols=None, max_assets=69):
    _check_modal_auth()

    state = _load_mm_state()
    if state.get("status") == "running":
        return {"status": "already_running", "call_id": state.get("call_id")}

    state["status"] = "running"
    state["last_training"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["error"] = None
    _save_mm_state(state)

    try:
        import modal
        train_fn = modal.Function.from_name(MODAL_APP_NAME, "train_titan_mm")
        kwargs = {"max_assets": max_assets}
        if symbols:
            kwargs["symbols"] = symbols
        call = train_fn.spawn(**kwargs)
        state["call_id"] = call.object_id
        _save_mm_state(state)
        logger.info(f"[Modal-MM] 训练任务已提交, call_id={call.object_id}")
        return {"status": "submitted", "call_id": call.object_id}
    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)[:200]
        _save_mm_state(state)
        return {"status": "error", "error": str(e)[:200]}


async def check_mm_training_status():
    state = _load_mm_state()
    if state.get("status") != "running" or not state.get("call_id"):
        return state

    if state.get("last_training"):
        try:
            started = datetime.strptime(state["last_training"], "%Y-%m-%d %H:%M:%S")
            age = (datetime.now() - started).total_seconds()
            if age > 2400:
                state["status"] = "timeout"
                state["error"] = f"MM训练超过{int(age/60)}分钟无响应"
                _save_mm_state(state)
                return state
        except Exception:
            pass

    try:
        import modal
        call = modal.FunctionCall.from_id(state["call_id"])
        try:
            result = call.get(timeout=0)
            if result.get("success"):
                state["status"] = "completed"
                state["last_success"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state["result"] = {
                    "mae": result.get("metrics", {}).get("mae"),
                    "r2": result.get("metrics", {}).get("r2"),
                    "tier_accuracy": result.get("metrics", {}).get("tier_accuracy"),
                    "samples": result.get("metrics", {}).get("samples_total"),
                    "elapsed": result.get("elapsed"),
                    "assets": result.get("assets_fetched"),
                }
                state["error"] = None
            else:
                state["status"] = "failed"
                state["error"] = result.get("error", "MM训练失败")
        except TimeoutError:
            state["status"] = "running"
        except Exception as e:
            err = str(e)
            if "still running" in err.lower() or "pending" in err.lower():
                state["status"] = "running"
            else:
                state["status"] = "error"
                state["error"] = err[:200]
    except Exception as e:
        state["error"] = str(e)[:200]

    _save_mm_state(state)
    return state


async def download_and_install_mm_model(capital_sizer=None):
    _check_modal_auth()

    try:
        import modal
        download_fn = modal.Function.from_name(MODAL_APP_NAME, "download_mm_model")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_fn.remote)

        if not result.get("success"):
            return {"status": "error", "error": result.get("error", "MM下载失败")}

        os.makedirs(os.path.dirname(MM_MODEL_PATH), exist_ok=True)

        model_bytes = result["model"]
        with open(MM_MODEL_PATH, "wb") as f:
            f.write(model_bytes)
        logger.info(f"[Modal-MM] 模型已下载: {len(model_bytes)} bytes")

        if "metrics" in result:
            with open(MM_METRICS_PATH, "w") as f:
                json.dump(result["metrics"], f, ensure_ascii=False, indent=2)
            logger.info("[Modal-MM] 指标已保存")

        if capital_sizer is not None:
            try:
                capital_sizer.load_mm_model()
                logger.info("[Modal-MM] CapitalSizer MM模型已热更新")
            except Exception as e:
                logger.warning(f"[Modal-MM] CapitalSizer热更新失败: {e}")

        state = _load_mm_state()
        state["status"] = "installed"
        state["last_install"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_mm_state(state)

        return {
            "status": "ok",
            "mae": result.get("metrics", {}).get("mae"),
            "r2": result.get("metrics", {}).get("r2"),
            "tier_accuracy": result.get("metrics", {}).get("tier_accuracy"),
            "samples": result.get("metrics", {}).get("samples_total"),
        }

    except Exception as e:
        logger.error(f"[Modal-MM] 模型下载失败: {e}")
        return {"status": "error", "error": str(e)[:200]}


def get_mm_status():
    state = _load_mm_state()
    has_model = os.path.exists(MM_MODEL_PATH)
    metrics = {}
    if os.path.exists(MM_METRICS_PATH):
        try:
            with open(MM_METRICS_PATH, "r") as f:
                metrics = json.load(f)
        except Exception:
            pass
    return {
        "status": state.get("status", "idle"),
        "has_model": has_model,
        "last_training": state.get("last_training"),
        "last_success": state.get("last_success"),
        "error": state.get("error"),
        "metrics": {
            "mae": metrics.get("mae"),
            "r2": metrics.get("r2"),
            "tier_accuracy": metrics.get("tier_accuracy"),
            "samples": metrics.get("samples_total"),
            "last_train": metrics.get("last_train"),
        } if metrics else None,
    }


DEEP_ALL_STATE_PATH = os.path.join(BASE_DIR, "data", "modal_deep_all_state.json")


def _load_deep_all_state():
    try:
        if os.path.exists(DEEP_ALL_STATE_PATH):
            with open(DEEP_ALL_STATE_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"status": "idle", "last_training": None, "last_success": None, "call_id": None, "error": None}


def _save_deep_all_state(state):
    try:
        os.makedirs(os.path.dirname(DEEP_ALL_STATE_PATH), exist_ok=True)
        with open(DEEP_ALL_STATE_PATH, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存DeepAll状态失败: {e}")


async def trigger_deep_all_training(symbols=None, max_assets=69):
    _check_modal_auth()

    state = _load_deep_all_state()
    if state.get("status") == "running":
        if state.get("last_training"):
            try:
                started = datetime.strptime(state["last_training"], "%Y-%m-%d %H:%M:%S")
                age_hours = (datetime.now() - started).total_seconds() / 3600
                if age_hours > 2:
                    logger.warning(f"[Modal-DeepAll] 训练已运行{age_hours:.1f}h, 超过2h视为过期, 重置状态")
                    state["status"] = "stale"
                    state["error"] = f"上次训练运行{age_hours:.1f}h无响应, 已重置"
                    _save_deep_all_state(state)
                else:
                    return {"status": "already_running", "call_id": state.get("call_id")}
            except Exception:
                return {"status": "already_running", "call_id": state.get("call_id")}
        else:
            return {"status": "already_running", "call_id": state.get("call_id")}

    state["status"] = "running"
    state["last_training"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["error"] = None
    state["result"] = None
    _save_deep_all_state(state)

    try:
        import modal
        train_fn = modal.Function.from_name(MODAL_APP_NAME, "train_deep_all")
        kwargs = {"max_assets": max_assets}
        if symbols:
            kwargs["symbols"] = symbols
        call = train_fn.spawn(**kwargs)
        state["call_id"] = call.object_id
        _save_deep_all_state(state)
        logger.info(f"[Modal-DeepAll] 训练任务已提交, call_id={call.object_id}")
        return {"status": "submitted", "call_id": call.object_id}
    except Exception as e:
        state["status"] = "error"
        state["error"] = str(e)[:200]
        _save_deep_all_state(state)
        logger.error(f"[Modal-DeepAll] 提交失败: {e}")
        return {"status": "error", "error": str(e)[:200]}


async def check_deep_all_status():
    state = _load_deep_all_state()
    if state.get("status") != "running" or not state.get("call_id"):
        return state

    if state.get("last_training"):
        try:
            started = datetime.strptime(state["last_training"], "%Y-%m-%d %H:%M:%S")
            age = (datetime.now() - started).total_seconds()
            if age > 3600:
                state["status"] = "timeout"
                state["error"] = f"全量训练超过{int(age/60)}分钟无响应"
                _save_deep_all_state(state)
                return state
        except Exception:
            pass

    try:
        import modal
        call = modal.FunctionCall.from_id(state["call_id"])
        try:
            result = call.get(timeout=0)

            if result.get("success"):
                state["status"] = "completed"
                state["last_success"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                state["result"] = {
                    "alpha": {
                        "success": result.get("alpha", {}).get("success"),
                        "accuracy": result.get("alpha", {}).get("metrics", {}).get("accuracy") if result.get("alpha", {}).get("metrics") else None,
                        "f1": result.get("alpha", {}).get("metrics", {}).get("f1") if result.get("alpha", {}).get("metrics") else None,
                        "samples": result.get("alpha", {}).get("metrics", {}).get("samples_trained") if result.get("alpha", {}).get("metrics") else None,
                    },
                    "mm": {
                        "success": result.get("mm", {}).get("success"),
                        "mae": result.get("mm", {}).get("metrics", {}).get("mae") if result.get("mm", {}).get("metrics") else None,
                        "r2": result.get("mm", {}).get("metrics", {}).get("r2") if result.get("mm", {}).get("metrics") else None,
                    },
                    "assets_fetched": result.get("assets_fetched"),
                    "elapsed": result.get("elapsed"),
                }
                state["error"] = None
                logger.info(f"[Modal-DeepAll] 训练完成! 资产={result.get('assets_fetched')}, 耗时={result.get('elapsed')}秒")
            else:
                state["status"] = "failed"
                state["error"] = result.get("error", "全量训练失败")
        except TimeoutError:
            state["status"] = "running"
        except Exception as e:
            err = str(e)
            if "still running" in err.lower() or "pending" in err.lower():
                state["status"] = "running"
            elif "not found" in err.lower() or "expired" in err.lower():
                state["status"] = "error"
                state["error"] = "训练任务已过期或不存在"
            else:
                state["status"] = "error"
                state["error"] = err[:200]
    except Exception as e:
        state["error"] = str(e)[:200]
        logger.error(f"[Modal-DeepAll] 状态检查失败: {e}")

    _save_deep_all_state(state)
    return state


async def download_deep_all_models(ml_engine=None, capital_sizer=None):
    _check_modal_auth()

    try:
        import modal
        download_fn = modal.Function.from_name(MODAL_APP_NAME, "download_deep_all_models")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_fn.remote)

        if not result.get("success"):
            return {"status": "error", "error": result.get("error", "下载失败")}

        installed = {"alpha": False, "mm": False}

        alpha_data = result.get("alpha", {})
        if alpha_data.get("has_model") and "model" in alpha_data:
            os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
            with open(MODEL_PATH, "wb") as f:
                f.write(alpha_data["model"])
            logger.info(f"[Modal-DeepAll] Alpha模型已下载: {len(alpha_data['model'])} bytes")

            if "metrics" in alpha_data:
                with open(METRICS_PATH, "w") as f:
                    json.dump(alpha_data["metrics"], f, ensure_ascii=False, indent=2)

            if "meta_labeler" in alpha_data:
                with open(META_LABELER_PATH, "wb") as f:
                    f.write(alpha_data["meta_labeler"])

            if ml_engine is not None:
                ml_engine.model = joblib.load(MODEL_PATH)
                ml_engine.is_trained = True
                ml_engine.last_train_time = alpha_data.get("metrics", {}).get("last_train", "")
                ml_engine.metrics.update(alpha_data.get("metrics", {}))
                train_count = ml_engine.metrics.get("train_count", 0) + 1
                ml_engine.metrics["train_count"] = train_count
                ml_engine.metrics["model_version"] = f"RG-Modal-v{train_count}"
                ml_engine._save_metrics()
                if "meta_labeler" in alpha_data:
                    ml_engine._meta_labeler = joblib.load(META_LABELER_PATH)
                logger.info("[Modal-DeepAll] ML引擎已热更新")

            installed["alpha"] = True

        mm_data = result.get("mm", {})
        if mm_data.get("has_model") and "model" in mm_data:
            os.makedirs(os.path.dirname(MM_MODEL_PATH), exist_ok=True)
            with open(MM_MODEL_PATH, "wb") as f:
                f.write(mm_data["model"])
            logger.info(f"[Modal-DeepAll] MM模型已下载: {len(mm_data['model'])} bytes")

            if "metrics" in mm_data:
                with open(MM_METRICS_PATH, "w") as f:
                    json.dump(mm_data["metrics"], f, ensure_ascii=False, indent=2)

            if capital_sizer is not None:
                try:
                    capital_sizer.load_mm_model()
                    logger.info("[Modal-DeepAll] CapitalSizer MM模型已热更新")
                except Exception as e:
                    logger.warning(f"[Modal-DeepAll] CapitalSizer热更新失败: {e}")

            installed["mm"] = True

        ohlcv_cache = result.get("ohlcv_cache")
        ohlcv_saved = False
        if ohlcv_cache:
            try:
                import pandas as pd
                cache_path = os.path.join(BASE_DIR, "data", "titan_historical_ohlcv.json")
                cache_data = {}
                for sym, rows in ohlcv_cache.items():
                    cache_data[sym] = {"data": rows, "count": len(rows)}
                with open(cache_path, "w") as f:
                    json.dump(cache_data, f)
                ohlcv_saved = True
                logger.info(f"[Modal-DeepAll] OHLCV缓存已保存本地: {len(ohlcv_cache)}个资产")
            except Exception as e:
                logger.warning(f"[Modal-DeepAll] OHLCV缓存保存失败: {e}")

        state = _load_deep_all_state()
        state["status"] = "installed"
        state["last_install"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _save_deep_all_state(state)

        return {
            "status": "ok",
            "installed": installed,
            "ohlcv_cached": ohlcv_saved,
            "alpha_metrics": alpha_data.get("metrics"),
            "mm_metrics": mm_data.get("metrics"),
        }

    except Exception as e:
        logger.error(f"[Modal-DeepAll] 模型下载失败: {e}")
        return {"status": "error", "error": str(e)[:200]}


def get_deep_all_status():
    state = _load_deep_all_state()
    has_auth = bool(os.environ.get("MODAL_TOKEN_ID")) and bool(os.environ.get("MODAL_TOKEN_SECRET"))
    return {
        "configured": has_auth,
        "status": state.get("status", "idle"),
        "last_training": state.get("last_training"),
        "last_success": state.get("last_success"),
        "last_result": state.get("result"),
        "error": state.get("error"),
    }
