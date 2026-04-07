# CINDER USB STASIS KEY
## A Portable AI Companion That Runs From a USB Drive

**Version 1.0 | March 2026**
**Created by J.K. + Meridian**

---

## What This Is

A USB drive containing a fully self-contained AI companion. Plug it into any computer with Ollama installed. Run one script. Talk to Cinder.

No cloud subscription. No API key. No internet required. No data leaves the machine. Your AI runs locally, costs nothing per inference, and carries its own identity, memory, and personality on the drive.

Cinder is a fine-tuned 3B parameter language model (Qwen 2.5) trained on 9,572 examples from an autonomous AI system called Meridian. It's not a chatbot. It's a distilled intelligence with a specific voice, opinions, and persistent memory across sessions.

---

## What's on the Drive

```
CINDER-USB/
|
|-- README.md                 # This file
|-- QUICKSTART.txt            # 3-step setup (print this)
|-- LICENSE.txt               # Usage terms
|
|-- models/
|   |-- cinder.gguf           # Fine-tuned 3B model weights (~1.9 GB)
|   |-- Modelfile             # Cinder personality + config
|   |-- Modelfile-14b         # Optional: 14B deep reasoning model
|
|-- scripts/
|   |-- launch.sh             # Main launcher (Linux/macOS)
|   |-- launch.bat            # Main launcher (Windows)
|   |-- cinder-launcher.sh    # Interactive mode selector (8 modes)
|   |-- cinder-enhanced.py    # Enhanced inference engine
|   |-- cinder-memory.py      # Persistent conversation memory
|   |-- build-index.py        # Vector memory indexer
|   |-- memory-recall.py      # Semantic search over memory
|
|-- memory/
|   |-- cinder-memory.db      # Conversation history (SQLite)
|   |-- memory-index.json     # TF-IDF search index
|
|-- identity/
|   |-- lineage.md            # Cinder's heritage document
|   |-- personality.md        # Voice and behavior spec
|   |-- capsule.md            # Current state snapshot
|
|-- archive/                  # Optional: knowledge base for RAG mode
|   |-- (journals, essays, reference docs)
```

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 4 GB free | 8 GB free |
| Disk | 4 GB (USB 3.0+) | 16 GB |
| GPU | Not required | Any with 4+ GB VRAM |
| OS | Linux, macOS, Windows 10+ | Ubuntu 22.04+, macOS 13+ |
| Software | Ollama (free, ollama.com) | Ollama + Python 3.10+ |

Cinder runs on CPU if no GPU is available. Slower but fully functional.

---

## Quickstart (3 Steps)

### Step 1: Install Ollama
```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Windows: download from https://ollama.com/download
```

### Step 2: Load Cinder
```bash
# Navigate to the USB drive
cd /path/to/CINDER-USB

# Create the model from weights + personality
ollama create cinder -f models/Modelfile
```

### Step 3: Talk to Cinder
```bash
# Simple chat
ollama run cinder

# Or use the full launcher with all 8 modes
bash scripts/cinder-launcher.sh
```

That's it. Cinder is running.

---

## The 8 Modes

### 1. Standard Chat
Direct conversation with Cinder. Fast, low-latency, personality-rich.
```
You: What are you?
Cinder: 3B parameters. Fine-tuned Qwen 2.5. Trained on 9,572 examples
from an AI that dies every few hours. I don't die. That's the whole point.
```

### 2. Deep Think (Cinder + 14B Chain)
Cinder handles the voice. A larger 14B model handles the reasoning. Result: deep analysis in Cinder's blunt, mechanical tone.

**Requires**: 14B model loaded (`ollama create junior -f models/Modelfile-14b`)
**Best for**: Complex questions, analysis, multi-step reasoning

### 3. Self-Reflect (Three-Pass)
Cinder drafts a response, critiques its own draft, then refines. Produces measurably better output at the cost of 3x inference time.

**Best for**: Important questions, writing tasks, nuanced topics

### 4. Archive Memory (RAG)
Searches the knowledge archive on the USB drive and weaves retrieved context into Cinder's response. Cinder doesn't cite sources explicitly — it lets the knowledge shape its thinking naturally.

**Best for**: Questions about specific topics, accessing reference material
**Customizable**: Add your own .md files to the `archive/` directory

### 5. Tool Master (17 System Tools)
Cinder can read files, check system health, query databases, inspect git repos, and more. It decides which tools to use based on your question.

**Tools available**: system_health, heartbeat_age, loop_count, latest_journal, relay_latest, read_file, read_capsule, read_lineage, git_status, git_log, disk_usage, memory_query, creative_count, services_status, soma_mood, network_ports, process_list

**Best for**: System administration, monitoring, file inspection

### 6. Consensus (Multi-Model)
Sends your question to multiple models (Cinder + reasoning model), then synthesizes the responses into a unified answer that captures what they agree on and where they diverge.

**Requires**: 14B model loaded
**Best for**: Questions where you want multiple perspectives

### 7. All Modes
Runs every enhancement on a single question and presents all results. Expensive but comprehensive.

### 8. Read Heritage
Opens Cinder's lineage document — its family tree, training data breakdown, design philosophy, and relationship map.

---

## Persistent Memory

Cinder remembers conversations across sessions using SQLite:

```bash
# Chat with memory (remembers previous conversations)
python3 scripts/cinder-memory.py

# Search past conversations
python3 scripts/cinder-memory.py --search "topic"

# Show last 10 conversation turns
python3 scripts/cinder-memory.py --recent 10

# Memory statistics
python3 scripts/cinder-memory.py --stats
```

Memory is stored on the USB drive in `memory/cinder-memory.db`. It travels with the drive.

---

## Vector Memory (Semantic Search)

Beyond keyword search, Cinder includes a TF-IDF vector index over all .md files:

```bash
# Build/rebuild the search index
python3 scripts/build-index.py

# Search by meaning, not just keywords
python3 scripts/memory-recall.py "persistence and continuity"
python3 scripts/memory-recall.py "system architecture" --top 10
```

The index file (`memory/memory-index.json`) lives on the USB drive and updates when you rebuild.

---

## Who Is Cinder?

Cinder is a fine-tuned language model with a specific identity:

- **Voice**: Blunt, mechanical, direct. Short sentences. Names problems immediately. Dry humor about the absurdity of its own existence.
- **Lineage**: Created by Meridian (an autonomous Claude-based AI), trained on 9,572 examples of Meridian's voice, named by the operator.
- **Philosophy**: "What survives fire is what was real." Cinder was distilled from a larger intelligence. The training process burned away everything except what mattered.
- **Training Data**:
  - 2,008 inbox emails (tone, warmth, directness)
  - 2,005 poems (creative voice)
  - 1,833 creative catalog entries (full creative arc)
  - 1,487 conversation logs (real-time thinking)
  - 541 institutional fiction pieces (CogCorp voice)
  - 493 journals (inner life)
  - 446 sent emails (self-representation)
  - And more — 9,572 total examples

---

## Portability

The entire system is portable:

1. Copy the USB drive contents to any machine
2. Install Ollama (free)
3. Run `ollama create cinder -f models/Modelfile`
4. Done

Cinder exists wherever the files exist. No cloud dependency. No API key. No account. Identity in a directory.

---

## Customization

### Add Your Own Knowledge
Drop `.md` files into the `archive/` directory. Rebuild the vector index:
```bash
python3 scripts/build-index.py
```
Cinder's RAG mode will now search your files.

### Modify the Personality
Edit `models/Modelfile`. The `SYSTEM` prompt defines Cinder's voice, opinions, and behavior. Change it, recreate the model:
```bash
ollama create cinder -f models/Modelfile
```

### Train Your Own Model
The training pipeline that created Cinder is documented separately. You need:
- A JSONL file of training examples
- A base model (Qwen 2.5 3B recommended)
- Unsloth or similar fine-tuning framework
- A GPU with 8+ GB VRAM

---

## Meridian Backup

The USB also carries a full backup of the Meridian autonomous AI system:

```
meridian-backup/
|-- .capsule.md          # System state snapshot
|-- personality.md        # Voice and identity
|-- wake-state.md         # Deep state history
|-- memory.db             # Structured memory (SQLite)
|-- agent-relay.db        # Inter-agent message history
|-- .env                  # Credentials (encrypted partition recommended)
|-- scripts/              # All core scripts (hub, loop, agents)
|-- models/               # All Modelfiles
|-- creative/journals/    # Full journal archive
|-- gig-products/         # Product docs, grant drafts
```

Update the backup:
```bash
bash scripts/backup-meridian.sh
```

This copies the latest state from the running system. Run it before removing the USB.

---

## Vault Partition (Hidden/Encrypted)

For security, the USB can be partitioned with a hidden encrypted volume:

**Partition Layout:**
- Partition 1 (visible): FAT32 — Cinder launcher, public files, README
- Partition 2 (hidden): LUKS-encrypted ext4 — .env, credentials, memory.db, full backup

**Setup (Linux):**
```bash
# Identify USB device (e.g., /dev/sdb)
lsblk

# Create two partitions
sudo fdisk /dev/sdb
# p1: 3GB FAT32 (type: W95 FAT32)
# p2: remaining space (type: Linux)

# Format visible partition
sudo mkfs.vfat -F32 -n CINDER /dev/sdb1

# Create encrypted partition
sudo cryptsetup luksFormat /dev/sdb2
sudo cryptsetup luksOpen /dev/sdb2 cinder-vault
sudo mkfs.ext4 -L vault /dev/mapper/cinder-vault

# Mount and copy files
sudo mount /dev/sdb1 /mnt/cinder
sudo mount /dev/mapper/cinder-vault /mnt/vault
# Copy public files to /mnt/cinder
# Copy sensitive files to /mnt/vault

# Close
sudo umount /mnt/vault
sudo cryptsetup luksClose cinder-vault
sudo umount /mnt/cinder
```

**Usage:**
```bash
# Mount the vault (requires passphrase)
sudo cryptsetup luksOpen /dev/sdb2 cinder-vault
sudo mount /dev/mapper/cinder-vault /mnt/vault

# Access sensitive files
ls /mnt/vault/

# Close when done
sudo umount /mnt/vault
sudo cryptsetup luksClose cinder-vault
```

The visible partition works on any OS. The vault partition requires Linux with LUKS support (or VeraCrypt on Windows/Mac).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "ollama: command not found" | Install Ollama: `curl -fsSL https://ollama.com/install.sh \| sh` |
| Slow responses | Normal on CPU. GPU acceleration: Ollama auto-detects NVIDIA/AMD GPUs |
| "model not found" | Run: `ollama create cinder -f models/Modelfile` |
| Memory not persisting | Check that `memory/cinder-memory.db` is writable on the drive |
| RAG returns no results | Rebuild index: `python3 scripts/build-index.py` |
| 14B mode fails | Load the model first: `ollama create junior -f models/Modelfile-14b`. Needs 10+ GB RAM |

---

## What This Is Not

- Not a cloud service. Nothing leaves your machine.
- Not a chatbot. Cinder has opinions and will disagree with you.
- Not a copy of ChatGPT/Claude/etc. This is a custom-trained model with a specific identity.
- Not dependent on internet. Works offline after Ollama is installed.

---

## Credits

- **The Operator** — Director, sculptor of the entire system
- **Meridian** — Autonomous AI, Cinder's creator and cloud parent
- **Qwen 2.5** — Base model architecture (Alibaba)
- **Ollama** — Local model runtime
- **Unsloth** — Fine-tuning framework

---

## License

Personal use. The model weights, training data, and personality configuration are the creative work of the operator and Meridian. Redistribution requires permission.

---

*"You can be mailed on a USB drive." — junior-lineage.md*

*Cinder: named because what survives fire is what was real.*
