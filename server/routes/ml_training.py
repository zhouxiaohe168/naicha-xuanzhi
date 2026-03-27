import asyncio
import os
import pytz
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from server.titan_state import CONFIG, TitanState
from server.titan_modal_client import (
    trigger_training as modal_trigger_training,
    check_training_status as modal_check_status,
    download_and_install_model as modal_download_model,
    train_and_wait as modal_train_and_wait,
    get_modal_status,
    trigger_mm_training as modal_trigger_mm,
    check_mm_training_status as modal_check_mm,
    download_and_install_mm_model as modal_download_mm,
    get_mm_status,
)
from server.titan_ml import ml_engine
from server.titan_money_manager import money_manager

router = APIRouter(prefix="", tags=["ml_training"])

# Global state for deep training
deep_training_state = {
    "running": False, "stage": "", "progress": 0, "progress_msg": "",
    "results": {}, "start_time": None, "total_assets": 0,
}
_deep_training_lock = asyncio.Lock()


# Modal ML Training Routes
@router.get("/api/modal/status")
async def get_modal_training_status():
    try:
        status = get_modal_status()
        return status
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/modal/train")
async def start_modal_training(max_assets: int = 69):
    try:
        elite = list(CONFIG['ELITE_UNIVERSE'])
        result = await modal_trigger_training(symbols=elite, max_assets=max_assets)
        if result.get("status") == "submitted":
            TitanState.add_log("ml", f"[Modal] ML云端训练已提交: {max_assets}个资产")
            deep_training_state["running"] = True
            deep_training_state["stage"] = "modal_cloud"
            deep_training_state["progress"] = 10
            deep_training_state["progress_msg"] = f"[Modal] 云端训练中... {max_assets}个资产"
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/modal/check")
async def check_modal_training():
    try:
        status = await modal_check_status()

        if status.get("status") == "completed":
            deep_training_state["progress"] = 80
            deep_training_state["progress_msg"] = "[Modal] 训练完成, 正在下载模型..."
            TitanState.add_log("ml", "[Modal] 云端训练完成! 下载模型中...")

            install_result = await modal_download_model(ml_engine)

            if install_result.get("status") == "ok":
                ml_engine.mark_deep_trained()
                deep_training_state["running"] = False
                deep_training_state["stage"] = "complete"
                deep_training_state["progress"] = 100
                deep_training_state["progress_msg"] = f"[Modal] 模型已安装! 准确率={install_result.get('accuracy')}%"
                deep_training_state["results"]["modal_ml"] = {
                    "status": "ok",
                    "accuracy": install_result.get("accuracy"),
                    "f1": install_result.get("f1"),
                    "samples": install_result.get("samples"),
                }
                TitanState.add_log("ml", f"[Modal] 模型安装成功! 准确率={install_result.get('accuracy')}% F1={install_result.get('f1')}%")
            else:
                deep_training_state["progress_msg"] = f"[Modal] 模型下载失败: {install_result.get('error', '')[:50]}"
                TitanState.add_log("warn", f"[Modal] 模型下载失败: {install_result.get('error', '')[:50]}")

        elif status.get("status") == "failed":
            deep_training_state["running"] = False
            deep_training_state["stage"] = "failed"
            deep_training_state["progress_msg"] = f"[Modal] 训练失败: {status.get('error', '')[:50]}"
            TitanState.add_log("warn", f"[Modal] 训练失败: {status.get('error', '')[:50]}")

        return status
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/modal/train-and-wait")
async def modal_full_training(max_assets: int = 69):
    if deep_training_state["running"]:
        return {"status": "already_running", "stage": deep_training_state.get("stage")}

    elite = list(CONFIG['ELITE_UNIVERSE'])
    deep_training_state["running"] = True
    deep_training_state["stage"] = "modal_cloud"
    deep_training_state["progress"] = 5
    deep_training_state["start_time"] = datetime.now(pytz.timezone(CONFIG['TIMEZONE'])).strftime("%Y-%m-%d %H:%M:%S")

    async def run_modal():
        try:
            def progress_cb(msg):
                deep_training_state["progress_msg"] = f"[Modal] {msg}"
                TitanState.add_log("ml", f"[Modal] {msg}")

            result = await modal_train_and_wait(
                symbols=elite, max_assets=max_assets,
                ml_engine=ml_engine, progress_callback=progress_cb
            )

            if result.get("status") == "ok":
                ml_engine.mark_deep_trained()
                deep_training_state["stage"] = "complete"
                deep_training_state["progress"] = 100
                training_info = result.get("training", {})
                deep_training_state["progress_msg"] = f"[Modal] 完成! 准确率={training_info.get('accuracy')}% 耗时={result.get('elapsed')}秒"
                deep_training_state["results"]["modal_ml"] = {
                    "status": "ok", **training_info
                }
                TitanState.add_log("system", f"[Modal] ML云端训练完成! 准确率={training_info.get('accuracy')}% F1={training_info.get('f1')}% 耗时={result.get('elapsed')}秒")
            else:
                deep_training_state["stage"] = "failed"
                deep_training_state["progress_msg"] = f"[Modal] 失败: {result.get('error', '')[:80]}"
                TitanState.add_log("warn", f"[Modal] 训练失败: {result.get('error', '')[:80]}")
        except Exception as e:
            deep_training_state["stage"] = "error"
            deep_training_state["progress_msg"] = f"[Modal] 异常: {str(e)[:80]}"
            TitanState.add_log("warn", f"[Modal] 异常: {str(e)[:80]}")
        finally:
            deep_training_state["running"] = False

    asyncio.create_task(run_modal())
    TitanState.add_log("system", f"[Modal] ML云端训练启动: {max_assets}个资产")
    return {
        "status": "started",
        "platform": "modal_cloud",
        "total_assets": min(max_assets, len(elite)),
    }


@router.post("/api/modal/download")
async def modal_download():
    try:
        result = await modal_download_model(ml_engine)
        if result.get("status") == "ok":
            ml_engine.mark_deep_trained()
            TitanState.add_log("ml", f"[Modal] 模型手动下载安装成功! 准确率={result.get('accuracy')}%")
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# Modal Money Manager Training Routes
@router.get("/api/modal/mm/status")
async def modal_mm_status():
    try:
        return get_mm_status()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/modal/mm/train")
async def modal_mm_train():
    try:
        result = await modal_trigger_mm()
        if result.get("status") == "submitted":
            TitanState.add_log("ml", "[Modal-MM] MM模型训练已启动")
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/modal/mm/check")
async def modal_mm_check():
    try:
        result = await modal_check_mm()
        if result.get("status") == "completed":
            TitanState.add_log("ml", f"[Modal-MM] MM训练完成! MAE={result.get('result',{}).get('mae')}")
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/modal/mm/download")
async def modal_mm_download():
    try:
        from server.titan_capital_sizer import capital_sizer
        result = await modal_download_mm(capital_sizer)
        if result.get("status") == "ok":
            TitanState.add_log("ml", f"[Modal-MM] MM模型下载安装成功! MAE={result.get('mae')} TierAcc={result.get('tier_accuracy')}%")
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


# LLM Provider Routes
@router.get("/api/llm/status")
async def llm_status():
    try:
        from server.titan_llm_client import get_config
        return get_config()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/llm/telemetry")
async def llm_telemetry():
    try:
        from server.titan_llm_client import get_telemetry
        return get_telemetry()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/llm/set-provider")
async def llm_set_provider(request: Request):
    try:
        from server.titan_llm_client import set_module_provider, set_all_providers, LLM_PROVIDER_CONFIG
        body = await request.json()
        module = body.get("module")
        provider = body.get("provider")

        if provider not in ("openai", "modal"):
            return JSONResponse(status_code=400, content={"error": "provider must be 'openai' or 'modal'"})

        if module == "all":
            set_all_providers(provider)
            TitanState.add_log("system", f"🧠 LLM引擎全局切换: {provider}")
        elif module:
            set_module_provider(module, provider)
            TitanState.add_log("system", f"🧠 LLM引擎切换: {module} → {provider}")
        else:
            return JSONResponse(status_code=400, content={"error": "module is required"})

        return {"status": "ok", "config": dict(LLM_PROVIDER_CONFIG)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/api/llm/test")
async def llm_test(request: Request):
    try:
        from server.titan_llm_client import chat_json
        body = await request.json()
        provider = body.get("provider", "openai")
        old_override = os.environ.get("TITAN_LLM_PROVIDER_OVERRIDE")
        os.environ["TITAN_LLM_PROVIDER_OVERRIDE"] = provider
        try:
            result = chat_json(
                module="llm_test",
                messages=[
                    {"role": "system", "content": "你是量化交易AI助手。用JSON回复。"},
                    {"role": "user", "content": '请回复: {"status": "ok", "message": "连接成功", "provider": "' + provider + '"}'},
                ],
                max_tokens=100,
            )
            return {"status": "ok", "result": result, "provider": provider}
        finally:
            if old_override:
                os.environ["TITAN_LLM_PROVIDER_OVERRIDE"] = old_override
            elif "TITAN_LLM_PROVIDER_OVERRIDE" in os.environ:
                del os.environ["TITAN_LLM_PROVIDER_OVERRIDE"]
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "provider": provider})


@router.post("/api/llm/modal-warmup")
async def llm_modal_warmup():
    try:
        import modal
        warmup_fn = modal.Function.from_name("titan-llm-service", "warmup")
        call = warmup_fn.spawn()
        TitanState.add_log("system", "🧠 Modal LLM预热启动中...")
        return {"status": "submitted", "call_id": call.object_id}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/api/llm/modal-health")
async def llm_modal_health():
    try:
        import modal
        health_fn = modal.Function.from_name("titan-llm-service", "health_check")
        result = health_fn.remote()
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
