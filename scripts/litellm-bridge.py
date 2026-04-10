#!/usr/bin/env python3
"""
LiteLLM Bridge — Unified inference API for all local models.
Replaces direct Ollama calls with a unified interface that can:
- Route to any local model (Cinder, Eos, Sentinel, Junior, etc.)
- Fall back between models if one fails
- Track usage/performance for optimization

Usage:
    from tools.litellm_bridge import ask, ask_cinder, ask_multi

    # Single model (default: sentinel — main stack model)
    response = ask("What time is it?", model="sentinel")

    # Multi-model consensus
    responses = ask_multi("What should I work on?", models=["sentinel", "eos", "qwen-7b"])

    # Quick shortcut
    response = ask_default("Hello")
"""

import litellm
import json
import os
import time
from datetime import datetime, timezone

OLLAMA_BASE = "http://localhost:11434"

# Model aliases — friendly names to Ollama model names
MODEL_MAP = {
    "cinder": "ollama/cinder",
    "cinder-fresh": "ollama/cinder-fresh",
    "cinder-q4": "ollama/cinder-q4",
    "eos": "ollama/eos-7b",
    "junior": "ollama/junior-v2",
    "sentinel": "ollama/sentinel",
    "qwen-14b": "ollama/qwen2.5:14b",
    "qwen-7b": "ollama/qwen2.5:7b",
    "qwen-3b": "ollama/qwen2.5:3b",
    "llama": "ollama/llama3.1",
    "mistral": "ollama/mistral-small3.2",
    "qwen3": "ollama/qwen3.5",
}

# Suppress litellm verbose logging
litellm.suppress_debug_info = True

def ask(prompt, model="sentinel", system=None, temperature=0.7, max_tokens=500, timeout=60):
    """Ask a single model a question. Returns response text."""
    ollama_model = MODEL_MAP.get(model, f"ollama/{model}")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        start = time.time()
        response = litellm.completion(
            model=ollama_model,
            messages=messages,
            api_base=OLLAMA_BASE,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        elapsed = time.time() - start
        content = response.choices[0].message.content

        # Log inference
        _log_inference(model, prompt[:80], len(content), elapsed)

        return content
    except Exception as e:
        return f"[ERROR: {model}] {e}"


def ask_default(prompt, system=None, **kwargs):
    """Shortcut for default (Sentinel) inference."""
    return ask(prompt, model="sentinel", system=system, **kwargs)


def ask_cinder(prompt, system=None, **kwargs):
    """Cinder inference — USB product testing only."""
    return ask(prompt, model="cinder", system=system, **kwargs)


def ask_multi(prompt, models=None, system=None, **kwargs):
    """Ask multiple models and return all responses. For consensus/comparison."""
    if models is None:
        models = ["sentinel", "eos", "qwen-7b"]

    results = {}
    for model in models:
        results[model] = ask(prompt, model=model, system=system, **kwargs)

    return results


def list_models():
    """List available local models."""
    try:
        import requests
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        return [m["name"] for m in r.json().get("models", [])]
    except:
        return []


def _log_inference(model, prompt_preview, response_len, elapsed):
    """Log inference to a JSONL file for performance tracking."""
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    log_file = os.path.join(log_dir, "litellm-usage.jsonl")

    try:
        os.makedirs(log_dir, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "prompt": prompt_preview,
            "response_len": response_len,
            "elapsed_s": round(elapsed, 2),
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except:
        pass


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(ask_cinder(prompt))
    else:
        print("Available models:")
        for alias, ollama_name in MODEL_MAP.items():
            print(f"  {alias:15s} -> {ollama_name}")
        print(f"\nOllama models online: {list_models()}")
