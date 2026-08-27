#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${LLAMA_CPP_SRC:-$HOME/src/llama.cpp}"
JOBS="${JOBS:-$(nproc)}"

if [[ ! -d "$SRC/.git" ]]; then
  mkdir -p "$(dirname "$SRC")"
  git clone https://github.com/ggml-org/llama.cpp.git "$SRC"
fi

cd "$SRC"

echo "llama.cpp commit: $(git rev-parse HEAD)"

PATCH="$ROOT/patches/0001-hasvk-relax-16bit-storage-init-guard.patch"
if git apply --check "$PATCH" 2>/dev/null; then
  git apply "$PATCH"
  echo "applied experimental patch"
elif git apply --reverse --check "$PATCH" 2>/dev/null; then
  echo "experimental patch already applied"
else
  echo "patch does not apply cleanly to $(git rev-parse HEAD)" >&2
  echo "Use a compatible llama.cpp revision or inspect the upstream code before proceeding." >&2
  exit 1
fi

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_VULKAN=ON \
  -DGGML_NATIVE=OFF \
  -DLLAMA_CURL=OFF

cmake --build build --config Release -j"$JOBS" --target llama-cli llama-bench llama-perplexity

printf '\nBuilt:\n  %s\n  %s\n' \
  "$SRC/build/bin/llama-cli" \
  "$SRC/build/bin/llama-bench"
