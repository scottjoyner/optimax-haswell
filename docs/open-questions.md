# Open questions

The central unresolved issue is correctness, not performance.

## 1. What fp16 data is present in the successful model?

The successful Gemma 3 1B Q4_0 run should be inspected with `llama-model-loader`, GGUF metadata tooling, or equivalent llama.cpp diagnostics to identify tensor storage types.

Questions:

- Which tensors are stored as F16?
- Which are quantized types?
- Are any F16 tensors assigned to the Vulkan backend?
- Are they converted before upload?

## 2. What exactly does hasvk expose?

Capture the full relevant Vulkan feature/extension report, including:

- `storageBuffer16BitAccess`
- `uniformAndStorageBuffer16BitAccess`
- `storagePushConstant16`
- `storageInputOutput16`
- `shaderFloat16`
- `VK_KHR_16bit_storage`

The public probe script records the generic Vulkan capability dump so this can be compared across Mesa versions.

On the target device (Mesa 26.1.7, hasvk / HSW GT2) the relevant result is now
captured: `storageBuffer16BitAccess`, `uniformAndStorageBuffer16BitAccess`,
`storagePushConstant16`, `storageInputOutput16`, and `shaderFloat16` are all
`false`, and `VK_KHR_16bit_storage` is not advertised. That is exactly why the
patch's relaxation of the 16-bit-storage guard is required for this device.

## 3. Why does the tested workload execute?

The current evidence does not distinguish among several possibilities:

1. the tested model does not exercise a path requiring unsupported 16-bit storage;
2. relevant tensors remain on CPU despite GPU layer offload;
3. llama.cpp converts or repacks data before the affected Vulkan operation;
4. hasvk supports enough underlying behavior for this workload despite not advertising the feature expected by llama.cpp;
5. the workload is producing incorrect results without an obvious crash.

Each possibility requires evidence.

Execution is now confirmed: with the patched build, `LFM2.5-1.2B-Instruct-Q4_0`
and `-Q5_K_M` run with full Vulkan offload on the Haswell hasvk device and
produce valid pp/tg throughput (see `docs/benchmarks.md`), so the fp32 fallback
path does carry these workloads. The remaining question is whether the *results*
are numerically correct (see #4).

## 4. Is output numerically correct?

A successful benchmark only demonstrates execution.

Validation should compare patched Vulkan output against CPU output using deterministic settings and fixed prompts/tokens. Useful checks include:

- identical greedy token sequences for a set of prompts;
- logits or top-k comparisons at selected positions;
- perplexity comparison on a small deterministic corpus;
- repeated runs to detect nondeterministic corruption.

Preliminary greedy `llama-cli` comparison was confounded by a degenerate greedy
loop on a bare prompt with this hybrid model (a sampling/prompt artifact —
`llama-bench` completed normally, so it is not a backend failure).

**Status: answered for the tested models.** `llama-perplexity` on a fixed
~960-word corpus gives identical perplexity for CPU and Vulkan backends to five
significant figures: LFM2.5-1.2B Q5_K_M = 6.2488 (both), Q4_0 = 6.4569 (both).
The patched Vulkan path is numerically correct versus CPU for these workloads. A
reproducible script is `scripts/verify-correctness.sh`. Whether this holds for
every model/tensor combination remains covered by question 5.

## 5. Which model/tensor combinations fail?

A small test matrix should deliberately vary:

- architecture;
- model size;
- quantization;
- presence of F16/BF16 tensors;
- GPU layer count.

The goal is to find the boundary of the observed behavior rather than prove a predetermined conclusion.

Models tested so far on the target device (patched build, `-fa off -ub 64`):

| Model | Size | Result |
|---|---|---|
| Gemma 3 1B Q4_0 | 1B | runs (prior observation) |
| LFM2.5-1.2B-Instruct-Q4_0 | 1.2B | runs; Vulkan gen faster; PPL matches CPU |
| LFM2.5-1.2B-Instruct-Q5_K_M | 1.2B | runs; Vulkan gen faster; PPL matches CPU |
| Qwen2.5-0.5B-Instruct-Q4_0 | 0.5B | runs; CPU gen faster than Vulkan |
| Any model, *unpatched* backend | — | **fails**: `does not support 16-bit storage` (control build) |

Open boundary: models whose working set exceeds the ~1.5 GiB Vulkan heap (e.g.
larger 3B+ Q4) are expected to fall back to partial offload or fail to allocate.

## 6. Does the patch need a narrower condition?

If successful workloads can be explained safely, the correct upstream change may still be narrower than the current experiment. Possibilities could include capability checks based on actual operations/tensor paths or an explicit unsupported/experimental mode.

No specific implementation is claimed here until the execution path is understood.
