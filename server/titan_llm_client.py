import os
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

logger = logging.getLogger("TitanLLM")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_PATH = os.path.join(BASE_DIR, "data", "titan_llm_telemetry.json")

LLM_PROVIDER_CONFIG = {
    "default": "openai",

    "cto_briefings": "openai",
    "cto_report": "openai",
    "cto_coordination": "openai",
    "trade_judge": "openai",
    "signal_quality": "openai",
    "position_advisor": "openai",
    "ai_reviewer": "openai",
    "ai_diagnostic": "openai",
    "agi_reflection": "openai",
    "synapse": "openai",
    "deep_evolution": "openai",
    "return_rate_agent": "openai",
    "analyst": "openai",
    "scoring_engine": "openai",
    "watchdog": "openai",
    "external_data": "openai",
    "dispatcher": "openai",
    "regime_detector": "openai",
    "ml_engine": "openai",
    "api_ceo_report": "openai",
    "api_signal_analysis": "openai",
    "api_ai_coordination": "openai",
    "self_inspector": "openai",
    "portfolio_correlation": "openai",
    "regime_transition": "openai",
}

MODAL_LLM_CONFIG = {
    "app_name": "titan-llm-service",
    "function_name": "chat_completion",
    "model_id": "Qwen/Qwen2.5-7B-Instruct",
    "max_retries": 2,
    "timeout_seconds": 30,
}


class LLMTelemetry:
    def __init__(self):
        self.stats = {
            "openai": {"calls": 0, "successes": 0, "failures": 0, "total_latency": 0, "fallbacks_from_modal": 0},
            "modal": {"calls": 0, "successes": 0, "failures": 0, "total_latency": 0},
        }
        self.module_stats = {}
        self.recent_calls = []
        self._last_save_time = 0
        self._load()

    def record(self, provider: str, module: str, latency: float, success: bool, fallback: bool = False):
        if provider not in self.stats:
            self.stats[provider] = {"calls": 0, "successes": 0, "failures": 0, "total_latency": 0}
        self.stats[provider]["calls"] += 1
        self.stats[provider]["total_latency"] += latency
        if success:
            self.stats[provider]["successes"] += 1
        else:
            self.stats[provider]["failures"] += 1
        if fallback:
            self.stats["openai"]["fallbacks_from_modal"] += 1

        if module not in self.module_stats:
            self.module_stats[module] = {"openai": 0, "modal": 0, "total_calls": 0, "avg_latency": 0, "total_latency": 0}
        ms = self.module_stats[module]
        ms["total_calls"] += 1
        ms[provider] = ms.get(provider, 0) + 1
        ms["total_latency"] += latency
        ms["avg_latency"] = round(ms["total_latency"] / ms["total_calls"], 2)

        self.recent_calls.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "module": module,
            "provider": provider,
            "latency": round(latency, 2),
            "success": success,
            "fallback": fallback,
        })
        if len(self.recent_calls) > 100:
            self.recent_calls = self.recent_calls[-100:]
        
        self._save()

    def _load(self):
        try:
            if os.path.exists(TELEMETRY_PATH):
                with open(TELEMETRY_PATH, 'r') as f:
                    data = json.load(f)
                if "stats" in data:
                    self.stats = data["stats"]
                if "module_stats" in data:
                    self.module_stats = data["module_stats"]
        except Exception:
            pass

    def _save(self):
        current_time = time.time()
        if current_time - self._last_save_time < 30:
            return
        
        self._last_save_time = current_time
        try:
            from server.titan_utils import atomic_json_save
            data = {
                "stats": self.stats,
                "module_stats": self.module_stats,
            }
            atomic_json_save(TELEMETRY_PATH, data)
        except Exception:
            pass

    def force_save(self):
        try:
            from server.titan_utils import atomic_json_save
            data = {
                "stats": self.stats,
                "module_stats": self.module_stats,
            }
            atomic_json_save(TELEMETRY_PATH, data)
            self._last_save_time = time.time()
        except Exception:
            pass

    def get_summary(self):
        summary = {}
        for provider, s in self.stats.items():
            avg_lat = round(s["total_latency"] / max(s["calls"], 1), 2)
            success_rate = round(s["successes"] / max(s["calls"], 1) * 100, 1)
            summary[provider] = {
                "calls": s["calls"],
                "success_rate": f"{success_rate}%",
                "avg_latency": f"{avg_lat}s",
                "failures": s["failures"],
            }
        summary["openai"]["fallbacks_from_modal"] = self.stats["openai"].get("fallbacks_from_modal", 0)
        return summary

    def get_status(self):
        return {
            "provider_summary": self.get_summary(),
            "module_stats": dict(self.module_stats),
            "recent_calls": self.recent_calls[-20:],
        }


telemetry = LLMTelemetry()


def _get_provider_for_module(module: str) -> str:
    override = os.environ.get("TITAN_LLM_PROVIDER_OVERRIDE")
    if override and override in ("openai", "modal"):
        return override

    module_override = os.environ.get(f"TITAN_LLM_{module.upper()}")
    if module_override and module_override in ("openai", "modal"):
        return module_override

    return LLM_PROVIDER_CONFIG.get(module, LLM_PROVIDER_CONFIG.get("default", "openai"))


def _call_openai(messages: List[Dict], model: str = "gpt-4o-mini",
                 json_mode: bool = True, max_tokens: int = 1500) -> str:
    from openai import OpenAI
    key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
    url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
    if not key or not url:
        raise RuntimeError("OpenAI credentials not configured (AI_INTEGRATIONS)")

    client = OpenAI(api_key=key, base_url=url)
    kwargs = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned empty response")
    return content.strip()


def _call_modal(messages: List[Dict], model: str = None,
                json_mode: bool = True, max_tokens: int = 1500) -> str:
    import modal

    app_name = MODAL_LLM_CONFIG["app_name"]

    try:
        engine_cls = modal.Cls.from_name(app_name, "TitanLLMEngine")
        engine = engine_cls()
        result = engine.generate.remote(
            messages=messages,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )
    except Exception:
        fn_name = MODAL_LLM_CONFIG["function_name"]
        chat_fn = modal.Function.from_name(app_name, fn_name)
        result = chat_fn.remote(
            messages=messages,
            json_mode=json_mode,
            max_tokens=max_tokens,
        )

    if isinstance(result, dict):
        if result.get("error"):
            raise RuntimeError(f"Modal LLM error: {result['error']}")
        content = result.get("content", "")
    else:
        content = str(result)

    if not content:
        raise RuntimeError("Modal LLM returned empty response")

    return content.strip()


def _validate_json(content: str) -> Optional[Dict]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def chat(module: str, messages: List[Dict],
         json_mode: bool = True,
         max_tokens: int = 1500,
         model: str = "gpt-4o-mini",
         retry_count: int = 1,
         fallback: bool = True) -> str:
    provider = _get_provider_for_module(module)

    for attempt in range(retry_count + 1):
        t0 = time.time()
        try:
            if provider == "modal":
                content = _call_modal(messages, model=model, json_mode=json_mode, max_tokens=max_tokens)
            else:
                content = _call_openai(messages, model=model, json_mode=json_mode, max_tokens=max_tokens)

            if json_mode:
                parsed = _validate_json(content)
                if parsed is None and attempt < retry_count:
                    logger.warning(f"[TitanLLM] {module}/{provider} JSON parse failed, retry {attempt+1}")
                    continue

            latency = time.time() - t0
            telemetry.record(provider, module, latency, success=True)
            logger.debug(f"[TitanLLM] {module}/{provider} OK in {latency:.2f}s")
            return content

        except Exception as e:
            latency = time.time() - t0
            telemetry.record(provider, module, latency, success=False)
            logger.warning(f"[TitanLLM] {module}/{provider} failed: {e}")

            if provider == "modal" and fallback and attempt == retry_count:
                logger.info(f"[TitanLLM] {module} falling back to OpenAI")
                try:
                    t0 = time.time()
                    content = _call_openai(messages, model=model, json_mode=json_mode, max_tokens=max_tokens)
                    latency = time.time() - t0
                    telemetry.record("openai", module, latency, success=True, fallback=True)
                    logger.info(f"[TitanLLM] {module}/openai fallback OK in {latency:.2f}s")
                    return content
                except Exception as fallback_err:
                    latency = time.time() - t0
                    telemetry.record("openai", module, latency, success=False, fallback=True)
                    raise RuntimeError(f"Both Modal and OpenAI failed for {module}: modal={e}, openai={fallback_err}")

            if attempt == retry_count:
                raise

    raise RuntimeError(f"[TitanLLM] {module} exhausted all retries")


def chat_json(module: str, messages: List[Dict],
              max_tokens: int = 1500,
              model: str = "gpt-4o-mini",
              fallback: bool = True) -> Optional[Dict]:
    try:
        content = chat(module, messages, json_mode=True, max_tokens=max_tokens,
                       model=model, fallback=fallback)
        parsed = _validate_json(content)
        return parsed
    except Exception as e:
        logger.warning(f"[TitanLLM] chat_json failed for {module}: {e}")
        return None


def set_module_provider(module: str, provider: str):
    if provider not in ("openai", "modal"):
        raise ValueError(f"Invalid provider: {provider}")
    LLM_PROVIDER_CONFIG[module] = provider
    logger.info(f"[TitanLLM] {module} provider set to {provider}")


def set_all_providers(provider: str):
    if provider not in ("openai", "modal"):
        raise ValueError(f"Invalid provider: {provider}")
    for key in LLM_PROVIDER_CONFIG:
        if key != "default":
            LLM_PROVIDER_CONFIG[key] = provider
    LLM_PROVIDER_CONFIG["default"] = provider
    logger.info(f"[TitanLLM] All providers set to {provider}")


def get_config():
    return {
        "provider_config": dict(LLM_PROVIDER_CONFIG),
        "modal_config": dict(MODAL_LLM_CONFIG),
        "telemetry": telemetry.get_status(),
    }


def get_telemetry():
    return telemetry.get_status()


titan_llm = type("TitanLLM", (), {
    "chat": staticmethod(chat),
    "chat_json": staticmethod(chat_json),
    "set_module_provider": staticmethod(set_module_provider),
    "set_all_providers": staticmethod(set_all_providers),
    "get_config": staticmethod(get_config),
    "get_telemetry": staticmethod(get_telemetry),
    "telemetry": telemetry,
})()
