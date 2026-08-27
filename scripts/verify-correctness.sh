#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:-}"
CORPUS="${2:-/tmp/perplexity-corpus.txt}"
PERP="${LLAMA_PERPLEXITY:-$HOME/src/llama.cpp/build/bin/llama-perplexity}"
VULKAN_DEVICE="${GGML_VULKAN_DEVICE:-0}"

if [[ -z "$MODEL" ]]; then
  echo "usage: $0 /path/to/model.gguf [corpus.txt]" >&2
  exit 2
fi

if [[ ! -f "$MODEL" ]]; then
  echo "model not found: $MODEL" >&2
  exit 2
fi

if [[ ! -f "$CORPUS" ]]; then
  echo "corpus not found: $CORPUS" >&2
  echo "create a fixed text file and pass it as the second argument" >&2
  exit 2
fi

if [[ ! -x "$PERP" ]]; then
  echo "llama-perplexity not executable: $PERP" >&2
  echo "build it with scripts/build-llama-vulkan.sh (target llama-perplexity)" >&2
  exit 2
fi

echo "=== CPU perplexity (ngl 0) ==="
timeout 300 "$PERP" -m "$MODEL" -f "$CORPUS" -ngl 0 -fa off -ub 64 || true

echo
echo "=== Vulkan perplexity (ngl 99, device $VULKAN_DEVICE) ==="
GGML_VULKAN_DEVICE="$VULKAN_DEVICE" timeout 300 "$PERP" -m "$MODEL" -f "$CORPUS" -ngl 99 -fa off -ub 64 || true
