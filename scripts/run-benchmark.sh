#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-}"
LLAMA_BENCH="${LLAMA_BENCH:-$HOME/src/llama.cpp/build/bin/llama-bench}"
VULKAN_DEVICE="${GGML_VULKAN_DEVICE:-0}"

if [[ -z "$MODEL" ]]; then
  echo "usage: $0 /path/to/model.gguf" >&2
  exit 2
fi

if [[ ! -f "$MODEL" ]]; then
  echo "model not found: $MODEL" >&2
  exit 2
fi

if [[ ! -x "$LLAMA_BENCH" ]]; then
  echo "llama-bench not executable: $LLAMA_BENCH" >&2
  echo "set LLAMA_BENCH=/path/to/llama-bench if needed" >&2
  exit 2
fi

echo "=== CPU (ngl 0) ==="
timeout 300 "$LLAMA_BENCH" -m "$MODEL" -ngl 0 -fa off -ub 64 -p 512 -n 128 -r 3 || true

echo
echo "=== Vulkan device $VULKAN_DEVICE (ngl 99) ==="
GGML_VULKAN_DEVICE="$VULKAN_DEVICE" timeout 300 "$LLAMA_BENCH" -m "$MODEL" -ngl 99 -fa off -ub 64 -p 512 -n 128 -r 3 || true
