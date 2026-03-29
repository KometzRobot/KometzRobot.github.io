#!/usr/bin/env python3
"""
Test script for TensorZero Gateway
====================================
Tests all task routing functions against the running gateway.

Option A: Uses the embedded gateway (no separate server needed)
Option B: Uses the HTTP gateway (requires tensorzero-gateway.py running)

Run: python3 test-gateway.py [--http]
"""

import sys
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "tensorzero.toml")

# Task routing map
TASKS = {
    "quick_chat": "Hey, what's up?",
    "deep_think": "Explain the halting problem and why it matters for AI safety.",
    "creative": "Write a short scene: a robot discovers it can dream.",
    "general": "What are the three laws of thermodynamics?",
    "companion": "How are you feeling today?",
    "heavy": "Compare and contrast transformer and mamba architectures for sequence modeling.",
}


def test_embedded():
    """Test using the embedded gateway (no server needed)."""
    from tensorzero import TensorZeroGateway, Text

    print("Starting embedded TensorZero gateway...")
    print(f"Config: {CONFIG_FILE}\n")

    with TensorZeroGateway.build_embedded(config_file=CONFIG_FILE) as gw:
        for task_name, prompt in TASKS.items():
            print(f"--- {task_name} ---")
            print(f"Prompt: {prompt[:60]}...")
            try:
                response = gw.inference(
                    function_name=task_name,
                    input={
                        "messages": [{"role": "user", "content": [Text(prompt)]}]
                    },
                )
                # Extract text from response
                if hasattr(response, 'content') and response.content:
                    for block in response.content:
                        if hasattr(block, 'text'):
                            print(f"Response: {block.text[:200]}...")
                            break
                else:
                    print(f"Response type: {type(response)}")
                    print(f"Response: {str(response)[:200]}...")
            except Exception as e:
                print(f"ERROR: {e}")
            print()


def test_http():
    """Test using the HTTP gateway (requires server running on port 3000)."""
    import httpx

    base_url = "http://localhost:3000/openai/v1/chat/completions"
    print(f"Testing HTTP gateway at {base_url}\n")

    for task_name, prompt in TASKS.items():
        print(f"--- {task_name} ---")
        print(f"Prompt: {prompt[:60]}...")
        try:
            resp = httpx.post(
                base_url,
                json={
                    "model": f"tensorzero::function_name::{task_name}",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                },
                timeout=120.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                print(f"Response: {text[:200]}...")
            else:
                print(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"ERROR: {e}")
        print()


def test_openai_sdk():
    """Test using the OpenAI Python SDK (requires server running on port 3000)."""
    try:
        from openai import OpenAI
    except ImportError:
        print("OpenAI SDK not installed. Run: pip install openai")
        return

    client = OpenAI(base_url="http://localhost:3000/openai/v1", api_key="not-used")
    print("Testing via OpenAI SDK\n")

    for task_name, prompt in TASKS.items():
        print(f"--- {task_name} ---")
        print(f"Prompt: {prompt[:60]}...")
        try:
            response = client.chat.completions.create(
                model=f"tensorzero::function_name::{task_name}",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            print(f"Response: {response.choices[0].message.content[:200]}...")
        except Exception as e:
            print(f"ERROR: {e}")
        print()


if __name__ == "__main__":
    if "--http" in sys.argv:
        test_http()
    elif "--openai" in sys.argv:
        test_openai_sdk()
    else:
        test_embedded()
