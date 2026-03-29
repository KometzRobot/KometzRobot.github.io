#!/usr/bin/env python3
"""
Practical Router Example
=========================
Shows how a web app (like hub-v2 or the-chorus) would use TensorZero
to route requests to the right Ollama model based on task type.

This uses the EMBEDDED gateway -- no separate server process needed.
The TensorZero Rust gateway runs inside your Python process.
"""

import os
from tensorzero import TensorZeroGateway, Text

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "tensorzero.toml")

# Simple keyword-based task classifier
# In production, you could use a small model to classify, or let the
# calling code specify the task type directly.
TASK_KEYWORDS = {
    "deep_think": ["explain", "analyze", "compare", "why", "how does", "prove", "reason",
                    "evaluate", "critique", "implications", "architecture"],
    "creative": ["write", "story", "poem", "scene", "imagine", "create", "brainstorm",
                 "design", "invent", "fiction", "journal"],
    "companion": ["feeling", "how are you", "lonely", "talk to me", "support",
                  "emotions", "stressed", "happy", "sad"],
    "heavy": ["research", "comprehensive", "detailed analysis", "full report",
              "technical paper", "in-depth"],
}


def classify_task(message: str) -> str:
    """Classify a message into a task type based on keywords."""
    msg_lower = message.lower()
    for task, keywords in TASK_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return task
    # Short messages -> quick chat, longer -> general
    if len(message) < 50:
        return "quick_chat"
    return "general"


def route_message(gateway: TensorZeroGateway, message: str, task_type: str = None) -> str:
    """
    Route a message through TensorZero to the appropriate model.

    Args:
        gateway: TensorZeroGateway instance
        message: User message
        task_type: Override auto-classification. One of:
                   quick_chat, deep_think, creative, general, companion, heavy

    Returns:
        Model response text
    """
    if task_type is None:
        task_type = classify_task(message)

    response = gateway.inference(
        function_name=task_type,
        input={
            "messages": [
                {"role": "user", "content": [Text(message)]}
            ]
        },
    )

    # Extract text from response
    for block in response.content:
        if hasattr(block, 'text'):
            return block.text
    return str(response)


def main():
    """Interactive demo of the router."""
    print("TensorZero Router Demo")
    print("=" * 50)
    print("Type a message and it will be routed to the best model.")
    print("Prefix with [task_type] to override routing.")
    print("  e.g., [deep_think] What is consciousness?")
    print("  e.g., [creative] Write about a sunset")
    print("Type 'quit' to exit.\n")

    with TensorZeroGateway.build_embedded(config_file=CONFIG_FILE) as gw:
        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input or user_input.lower() == "quit":
                break

            # Check for task type override: [task_type] message
            task_override = None
            if user_input.startswith("["):
                bracket_end = user_input.find("]")
                if bracket_end > 0:
                    task_override = user_input[1:bracket_end].strip()
                    user_input = user_input[bracket_end + 1:].strip()

            task = task_override or classify_task(user_input)
            model_map = {
                "quick_chat": "cinder (3B)",
                "deep_think": "qwen2.5:14b (14B)",
                "creative": "qwen3.5",
                "general": "llama3.1 (8B)",
                "companion": "eos-7b",
                "heavy": "mistral-small3.2",
            }
            print(f"[Routing: {task} -> {model_map.get(task, '?')}]")

            try:
                response = route_message(gw, user_input, task_override)
                print(f"AI: {response}\n")
            except Exception as e:
                print(f"Error: {e}\n")


if __name__ == "__main__":
    main()
