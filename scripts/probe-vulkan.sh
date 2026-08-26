#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-vulkan-probe.txt}"

{
  echo '# optimax-haswell Vulkan probe'
  echo
  date -u '+utc: %Y-%m-%dT%H:%M:%SZ'
  echo "kernel: $(uname -srmo)"
  if command -v lscpu >/dev/null 2>&1; then
    echo
    echo '## lscpu'
    lscpu
  fi
  if command -v lspci >/dev/null 2>&1; then
    echo
    echo '## display devices'
    lspci -nnk | grep -A4 -Ei 'VGA|3D|Display' || true
  fi
  if command -v vulkaninfo >/dev/null 2>&1; then
    echo
    echo '## vulkaninfo --summary'
    vulkaninfo --summary || true
    echo
    echo '## relevant Vulkan 16-bit / float16 features'
    vulkaninfo 2>/dev/null | grep -Ei \
      'storageBuffer16BitAccess|uniformAndStorageBuffer16BitAccess|storagePushConstant16|storageInputOutput16|shaderFloat16|VK_KHR_16bit_storage' || true
  else
    echo
    echo 'vulkaninfo: not installed'
  fi
} | tee "$OUT"

echo "wrote $OUT"
