import modal
import os

app = modal.App("titan-llm-service")

llm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.6.0",
        "transformers>=4.44",
        "torch>=2.1",
        "huggingface_hub>=0.24",
    )
)

model_volume = modal.Volume.from_name("titan-llm-models", create_if_missing=True)

MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
MODEL_DIR = "/vol/qwen25-7b"
GPU_TYPE = "A10G"


@app.cls(
    image=llm_image,
    volumes={"/vol": model_volume},
    gpu=GPU_TYPE,
    timeout=120,
    scaledown_window=300,
    memory=32768,
)
class TitanLLMEngine:
    @modal.enter()
    def load_model(self):
        import torch
        from vllm import LLM
        from transformers import AutoTokenizer

        model_path = MODEL_DIR
        if not os.path.exists(os.path.join(model_path, "config.json")):
            from huggingface_hub import snapshot_download
            print(f"[TitanLLM] Downloading {MODEL_ID}...")
            snapshot_download(
                MODEL_ID,
                local_dir=model_path,
                ignore_patterns=["*.md", "*.txt", "LICENSE*"],
            )
            model_volume.commit()
            print(f"[TitanLLM] Model downloaded to {model_path}")

        print(f"[TitanLLM] Loading model {MODEL_ID}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.llm = LLM(
            model=model_path,
            trust_remote_code=True,
            dtype="half",
            max_model_len=8192,
            gpu_memory_utilization=0.85,
        )
        print(f"[TitanLLM] Model loaded successfully!")

    @modal.method()
    def generate(
        self,
        messages: list,
        json_mode: bool = True,
        max_tokens: int = 1500,
        temperature: float = 0.3,
        top_p: float = 0.9,
    ):
        from vllm import SamplingParams

        if json_mode:
            system_json_hint = "\n\nIMPORTANT: You MUST respond with valid JSON only. No markdown, no code blocks, no extra text."
            msgs = [dict(m) for m in messages]
            if msgs and msgs[0].get("role") == "system":
                msgs[0]["content"] += system_json_hint
            else:
                msgs.insert(0, {"role": "system", "content": system_json_hint.strip()})
        else:
            msgs = messages

        prompt = self.tokenizer.apply_chat_template(
            msgs,
            tokenize=False,
            add_generation_prompt=True,
        )

        sampling_params = SamplingParams(
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            stop=["<|endoftext|>", "<|im_end|>"],
        )

        outputs = self.llm.generate([prompt], sampling_params)
        generated = outputs[0].outputs[0].text.strip()

        if json_mode:
            import json
            cleaned = generated
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()

            try:
                parsed = json.loads(cleaned)
                return {"content": json.dumps(parsed, ensure_ascii=False), "model": MODEL_ID, "status": "ok"}
            except json.JSONDecodeError:
                return {"content": generated, "model": MODEL_ID, "status": "ok", "warning": "json_parse_may_fail"}

        return {"content": generated, "model": MODEL_ID, "status": "ok"}


@app.function(
    image=llm_image,
    timeout=120,
)
def chat_completion(
    messages: list,
    json_mode: bool = True,
    max_tokens: int = 1500,
    temperature: float = 0.3,
    top_p: float = 0.9,
):
    engine = TitanLLMEngine()
    return engine.generate.remote(
        messages=messages,
        json_mode=json_mode,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )


@app.function(
    image=llm_image,
    volumes={"/vol": model_volume},
    timeout=30,
)
def health_check():
    model_path = MODEL_DIR
    has_model = os.path.exists(os.path.join(model_path, "config.json"))
    return {
        "status": "ok",
        "model_id": MODEL_ID,
        "model_cached": has_model,
        "gpu": GPU_TYPE,
    }


@app.function(
    image=llm_image,
    timeout=600,
)
def warmup():
    engine = TitanLLMEngine()
    result = engine.generate.remote(
        messages=[
            {"role": "system", "content": "You are a quantitative trading assistant. Respond in JSON."},
            {"role": "user", "content": 'Return {"status": "ok", "message": "warmup complete"}'},
        ],
        json_mode=True,
        max_tokens=50,
    )
    print(f"[TitanLLM] Warmup complete: {result}")
    return {"status": "ok", "model": MODEL_ID, "test_output": str(result)[:200]}
