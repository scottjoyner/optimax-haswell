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

## 3. Why does the tested workload execute?

The current evidence does not distinguish among several possibilities:

1. the tested model does not exercise a path requiring unsupported 16-bit storage;
2. relevant tensors remain on CPU despite GPU layer offload;
3. llama.cpp converts or repacks data before the affected Vulkan operation;
4. hasvk supports enough underlying behavior for this workload despite not advertising the feature expected by llama.cpp;
5. the workload is producing incorrect results without an obvious crash.

Each possibility requires evidence.

## 4. Is output numerically correct?

A successful benchmark only demonstrates execution.

Validation should compare patched Vulkan output against CPU output using deterministic settings and fixed prompts/tokens. Useful checks include:

- identical greedy token sequences for a set of prompts;
- logits or top-k comparisons at selected positions;
- perplexity comparison on a small deterministic corpus;
- repeated runs to detect nondeterministic corruption.

## 5. Which model/tensor combinations fail?

A small test matrix should deliberately vary:

- architecture;
- model size;
- quantization;
- presence of F16/BF16 tensors;
- GPU layer count.

The goal is to find the boundary of the observed behavior rather than prove a predetermined conclusion.

## 6. Does the patch need a narrower condition?

If successful workloads can be explained safely, the correct upstream change may still be narrower than the current experiment. Possibilities could include capability checks based on actual operations/tensor paths or an explicit unsupported/experimental mode.

No specific implementation is claimed here until the execution path is understood.
