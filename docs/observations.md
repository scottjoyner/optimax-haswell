# Observations

This document separates directly observed behavior from interpretation.

## Test platform

Recorded test platform:

| Component | Value |
|---|---|
| CPU | Intel Core i5-4590S |
| CPU topology | 4 cores / 4 threads |
| iGPU | Intel HD Graphics 4600 |
| GPU generation | Haswell GT2 / HSW GT2 |
| RAM | 8 GB DDR3, shared/UMA |
| OS | Ubuntu 24.04 |
| Vulkan driver | Mesa hasvk |
| Final validation Mesa version | 26.1.7 |
| Observed device heap | ~1.5 GiB |

Earlier experiments also used Mesa 25.2.8. Performance and stability claims labeled "final" refer to Mesa 26.1.7.

## Stock llama.cpp behavior

On the test device, the stock Vulkan backend rejected the device during initialization because 16-bit storage support was not advertised.

Observed error text:

```text
ggml_vulkan: device Vulkan0 does not support 16-bit storage.
E llama_model_load: error loading model: Unsupported device
```

The failure occurred before useful inference could begin.

## Experimental change

The experimental patch modifies the Vulkan device initialization logic in `ggml/src/ggml-vulkan/ggml-vulkan.cpp`.

The original code unconditionally rejected a device when `storageBuffer16BitAccess` was false and unconditionally requested `VK_KHR_16bit_storage`.

The experiment changed this behavior to:

1. treat either `storageBuffer16BitAccess` or `uniformAndStorageBuffer16BitAccess` as evidence of 16-bit storage support;
2. reject missing 16-bit storage only when `device->fp16` is true; and
3. request `VK_KHR_16bit_storage` only when `device->fp16` is true.

The exact patch is preserved in `patches/`.

## Successful 1B observation

With the experimental patch applied, a Gemma 3 1B Q4_0 model was observed running with:

```bash
-ngl 99 -fa off -ub 64
```

Final Mesa 26.1.7 benchmark:

```text
pp512 ~= 44.7 t/s
tg128 ~= 7.85 t/s
```

Three consecutive stability probes completed without a recorded i915 GPU hang event.

This proves only that this tested workload executed under the patched initialization behavior on this machine.

It does not establish that all tensor types, all models, or all Vulkan operations are safe without the advertised feature.

## 3B observation

A 3.09B parameter Q4_K_S model was observed with partial Vulkan offload.

Recorded representative results before the final tuning round:

| Backend | Configuration | pp512 | tg128 | Observation |
|---|---|---:|---:|---|
| CPU | 4 threads, flash attention off | ~36.9 t/s | ~7.8 t/s | baseline |
| Vulkan | partial/auto-fit | ~36.7 t/s | ~7.4 t/s | executed, not faster |

A later tuned CPU result reached approximately 10.1 t/s generation with 3 CPU threads.

Attempts to push larger fractions of the 3B model onto the GPU encountered device-memory limits. The available Vulkan heap observed by the workload was approximately 1.5 GiB.

## Stability observations

During experimentation:

- disabling i915 hangcheck allowed larger kernels to run but also allowed at least one real GPU wedge to surface as `DeviceLost` rather than a clean reset;
- the final documented configuration restored i915 hangcheck;
- Mesa 26.1.7 with hangcheck enabled and `-fa off -ub 64` produced the final 1B result above;
- three consecutive final stability probes recorded no GPU hang events.

The public reproduction does not recommend disabling hangcheck.

## Performance interpretation

The measurements do **not** show Haswell iGPU inference broadly outperforming CPU inference.

The useful observation is narrower:

> A Haswell HD 4600 device rejected by stock llama.cpp Vulkan initialization was able to execute at least one quantized 1B workload after the 16-bit-storage initialization guard was relaxed.

For the tested 3B workload, CPU inference was faster.

## Maintainer feedback that constrains interpretation

Maintainers of `llama.cpp` have stated that the Vulkan backend requires f16 storage support because parts of model data are stored in fp16.

That feedback creates an unresolved correctness question. The fact that one workload executed does not demonstrate that the initialization requirement is unnecessary in the general case.

See `open-questions.md`.
