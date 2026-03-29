#!/usr/bin/env python3
"""
TensorZero Gateway for Meridian
================================
Runs an embedded TensorZero gateway that routes requests to local Ollama models.
No Docker, no ClickHouse, no Postgres required.

Usage:
    python3 tensorzero-gateway.py

The gateway listens on port 3000 and proxies to Ollama at localhost:11434.
Web apps hit this gateway using the OpenAI SDK format.

Task routing (call the function name that matches your task):
    quick_chat  -> cinder (3B, fast)
    deep_think  -> qwen2.5:14b (14B, reasoning)
    creative    -> qwen3.5 (creative/general)
    general     -> llama3.1 (8B, general)
    companion   -> eos-7b (companion)
    heavy       -> mistral-small3.2 (most capable)

API format (OpenAI-compatible):
    POST http://localhost:3000/openai/v1/chat/completions
    {
        "model": "tensorzero::function_name::quick_chat",
        "messages": [{"role": "user", "content": "Hello!"}]
    }
"""

import os
import sys
import signal

# Path to config file
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "tensorzero.toml")


def main():
    print("=" * 60)
    print("TensorZero Gateway for Meridian")
    print("=" * 60)
    print(f"Config: {CONFIG_FILE}")
    print(f"Gateway: http://localhost:3000")
    print(f"Ollama:  http://localhost:11434")
    print()
    print("Task routing:")
    print("  quick_chat  -> cinder (3B)")
    print("  deep_think  -> qwen2.5:14b (14B)")
    print("  creative    -> qwen3.5")
    print("  general     -> llama3.1 (8B)")
    print("  companion   -> eos-7b")
    print("  heavy       -> mistral-small3.2")
    print()
    print("API endpoint:")
    print('  POST http://localhost:3000/openai/v1/chat/completions')
    print('  {"model": "tensorzero::function_name::quick_chat", ...}')
    print("=" * 60)

    # Verify config exists
    if not os.path.exists(CONFIG_FILE):
        print(f"ERROR: Config not found at {CONFIG_FILE}")
        sys.exit(1)

    # Import and start gateway
    from tensorzero.tensorzero import _start_http_gateway

    # _start_http_gateway blocks and runs the Rust gateway server
    # Pass None for optional services we don't need
    _start_http_gateway(
        config_file=CONFIG_FILE,
        clickhouse_url=None,
        postgres_url=None,
        valkey_url=None,
        async_setup=False,
    )


if __name__ == "__main__":
    main()
