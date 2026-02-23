#!/usr/bin/env python3
"""
Eos Browser Agent — Web browsing capability for Eos via Ollama.

Uses browser-use library with local Ollama models. No API tokens needed.
Can browse websites, read content, take screenshots, fill forms.

Usage:
  python3 eos-browser.py "check the weather in Calgary"
  python3 eos-browser.py "go to kometzrobot.github.io and tell me what you see"
  python3 eos-browser.py "search google for free bitcoin faucets"

Requires: conda python (3.13), browser-use, playwright, ollama running
Run with: /home/joel/miniconda3/bin/python3 eos-browser.py "task"
"""

import asyncio
import sys
import json
import os
from datetime import datetime

# browser-use imports
from browser_use import Agent
from browser_use.browser.session import BrowserSession
from langchain_ollama import ChatOllama

BASE_DIR = "/home/joel/autonomous-ai"
BROWSER_LOG = os.path.join(BASE_DIR, "eos-browser.log")


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(BROWSER_LOG, "a") as f:
        f.write(line + "\n")


async def browse(task: str):
    """Run a browser task using Ollama."""
    log(f"Task: {task}")

    # Use local Ollama model
    llm = ChatOllama(
        model="qwen2.5:7b",
        base_url="http://localhost:11434",
        temperature=0.7,
    )

    agent = Agent(
        task=task,
        llm=llm,
        max_actions_per_step=3,
    )

    try:
        result = await agent.run(max_steps=10)
        log(f"Result: {result}")
        return result
    except Exception as e:
        log(f"Error: {e}")
        return f"Error: {e}"
    finally:
        await agent.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: eos-browser.py 'task description'")
        print("Example: eos-browser.py 'go to kometzrobot.github.io and describe what you see'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    result = asyncio.run(browse(task))
    print(f"\n=== RESULT ===\n{result}")


if __name__ == "__main__":
    main()
