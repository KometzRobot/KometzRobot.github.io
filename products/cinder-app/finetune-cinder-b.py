#!/usr/bin/env python3
"""
Cinder Option B — Fresh Fine-Tune Script
Uses Unsloth + QLoRA to fine-tune qwen2.5-3b on fresh training data.
No Meridian data. No recycled conversations. Clean build.

Usage:
    /mnt/data1/venv-finetune/bin/python3 finetune-cinder-b.py

Requirements:
    - Unsloth installed in venv-finetune
    - RTX 2070+ (8GB VRAM)
    - training-data-fresh.jsonl in same directory
"""

import json
import os
import sys
from pathlib import Path

# Configuration
BASE_MODEL = "unsloth/Qwen2.5-3B-Instruct"
TRAINING_DATA = Path(__file__).parent / "training-data-fresh.jsonl"
OUTPUT_DIR = Path(__file__).parent / "cinder-b-output"
LORA_DIR = OUTPUT_DIR / "lora"
GGUF_DIR = OUTPUT_DIR / "gguf"

# Training hyperparameters
MAX_SEQ_LENGTH = 4096
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
EPOCHS = 3
BATCH_SIZE = 1
GRAD_ACCUM = 4
LEARNING_RATE = 2e-4
WARMUP_STEPS = 10

def load_training_data():
    """Load and validate training data from JSONL."""
    examples = []
    with open(TRAINING_DATA, 'r') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                convs = data.get('conversations', [])
                if len(convs) < 2:
                    print(f"  Warning: Line {i} has fewer than 2 conversation turns, skipping")
                    continue
                examples.append(data)
            except json.JSONDecodeError as e:
                print(f"  Error parsing line {i}: {e}")
                continue
    return examples

def format_for_training(examples):
    """Convert conversation format to ChatML training format."""
    formatted = []
    for ex in examples:
        convs = ex['conversations']
        text = ""
        for turn in convs:
            role = turn['from']
            value = turn['value']
            if role == 'system':
                text += f"<|im_start|>system\n{value}<|im_end|>\n"
            elif role == 'human':
                text += f"<|im_start|>user\n{value}<|im_end|>\n"
            elif role == 'gpt':
                text += f"<|im_start|>assistant\n{value}<|im_end|>\n"
        formatted.append({"text": text})
    return formatted

def main():
    print("=" * 60)
    print("CINDER OPTION B — Fresh Fine-Tune")
    print("=" * 60)

    # Step 1: Load data
    print(f"\n[1/5] Loading training data from {TRAINING_DATA}")
    examples = load_training_data()
    print(f"  Loaded {len(examples)} examples")

    if len(examples) < 10:
        print("  WARNING: Very few examples. Fine-tune quality may be poor.")
        print("  Recommended: 100+ examples for personality alignment.")

    # Step 2: Format data
    print("\n[2/5] Formatting for ChatML training")
    formatted = format_for_training(examples)
    print(f"  Formatted {len(formatted)} training examples")

    # Step 3: Load model with Unsloth
    print(f"\n[3/5] Loading base model: {BASE_MODEL}")
    from unsloth import FastLanguageModel
    from datasets import Dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # auto-detect
        load_in_4bit=True,
    )

    # Apply LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                         "gate_proj", "up_proj", "down_proj"],
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    print(f"  Model loaded. LoRA rank={LORA_R}, alpha={LORA_ALPHA}")

    # Step 4: Train
    print(f"\n[4/5] Training — {EPOCHS} epochs, batch={BATCH_SIZE}, lr={LEARNING_RATE}")

    dataset = Dataset.from_list(formatted)

    os.makedirs(LORA_DIR, exist_ok=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=TrainingArguments(
            output_dir=str(LORA_DIR),
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRAD_ACCUM,
            warmup_steps=WARMUP_STEPS,
            num_train_epochs=EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=True,
            logging_steps=1,
            save_strategy="epoch",
            seed=42,
        ),
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
    )

    trainer.train()

    # Save LoRA adapter
    model.save_pretrained(str(LORA_DIR))
    tokenizer.save_pretrained(str(LORA_DIR))
    print(f"  LoRA saved to {LORA_DIR}")

    # Step 5: Export to GGUF
    print(f"\n[5/5] Exporting to GGUF (Q4_K_M quantization)")
    os.makedirs(GGUF_DIR, exist_ok=True)

    model.save_pretrained_gguf(
        str(GGUF_DIR),
        tokenizer,
        quantization_method="q4_k_m",
    )

    gguf_files = list(GGUF_DIR.glob("*.gguf"))
    if gguf_files:
        final_path = gguf_files[0]
        target = Path(__file__).parent / "models" / "cinder-b.gguf"
        os.makedirs(target.parent, exist_ok=True)
        os.rename(str(final_path), str(target))
        print(f"  GGUF exported to {target}")
        print(f"  Size: {target.stat().st_size / (1024**3):.2f} GB")
    else:
        print("  WARNING: No GGUF file produced")

    print("\n" + "=" * 60)
    print("DONE — Cinder Option B model ready")
    print(f"  Model: {target if gguf_files else 'check ' + str(GGUF_DIR)}")
    print(f"  Modelfile: Modelfile-optionB")
    print(f"  To install: ollama create cinder-b -f Modelfile-optionB")
    print("=" * 60)

if __name__ == "__main__":
    main()
