#!/bin/sh
set -eu

MODEL_ID="${MODEL_ID:-Qwen/Qwen2.5-1.5B-Instruct}"
MODEL_DIR="${MODEL_DIR:-/models/model}"
PORT="${PORT:-8000}"

# Download once into the PVC-backed directory; marker prevents network access
# on later pod restarts. HF_TOKEN is optional for this public model.
python /app/scripts/download_model.py

# Do not log request bodies. vLLM's access logs contain request metadata only.
# API key is passed from Kubernetes Secret, never baked into the image.
exec vllm serve "${MODEL_DIR}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --dtype bfloat16 \
  --api-key "${API_ACCESS_TOKEN:?API_ACCESS_TOKEN must be set}" \
  --no-enable-log-requests \
  --gpu-memory-utilization 0.5 \
  --max-model-len "${MAX_MODEL_LEN:-2048}" \
  --max-num-seqs "${MAX_NUM_SEQS:-4}" \
  --max-num-batched-tokens "${MAX_NUM_BATCHED_TOKENS:-1024}" \
  --trust-remote-code
