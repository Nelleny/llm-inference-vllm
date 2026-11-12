#!/usr/bin/env python3
"""Download model weights once into the mounted persistent volume."""
import os
from pathlib import Path
import sys

try:
    from huggingface_hub import snapshot_download
except ImportError as exc:
    raise SystemExit("huggingface_hub is missing from the pinned vLLM CPU image") from exc

model_id = os.getenv("MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
model_dir = Path(os.getenv("MODEL_DIR", "/models/model"))
marker = model_dir / ".download_complete"

model_dir.mkdir(parents=True, exist_ok=True)
if marker.exists() and (model_dir / "config.json").exists():
    print(f"Model cache is complete; using local files at {model_dir}", flush=True)
    sys.exit(0)

print(f"Downloading {model_id} into persistent volume {model_dir}", flush=True)
token = os.getenv("HF_TOKEN") or None
snapshot_download(
    repo_id=model_id,
    local_dir=str(model_dir),
    token=token,
)
if not (model_dir / "config.json").exists():
    raise RuntimeError("Download finished without config.json; refusing to start")
marker.write_text("ok\n", encoding="utf-8")
print("Model download completed", flush=True)
