# optimax-haswell

Reproducible experiments with `llama.cpp`'s Vulkan backend on Intel Haswell integrated graphics using Mesa `hasvk`.

This repository is intentionally narrow: it records the hardware and software environment, the observed failure in stock `llama.cpp`, the experimental patch used during testing, exact benchmark commands/results, and unresolved technical questions.

It does **not** claim that removing or weakening `llama.cpp`'s 16-bit-storage requirement is generally correct.

## What is verified

Test system:

- CPU: Intel Core i5-4590S, 4 cores / 4 threads
- iGPU: Intel HD Graphics 4600 (Haswell GT2 / HSW GT2)
- RAM: 8 GB DDR3, shared-memory/UMA graphics
- OS: Ubuntu 24.04
- Final validation Mesa version: 26.1.7 (`hasvk`)
- Observed Vulkan device heap available to the workload: approximately 1.5 GiB

Observed stock-backend failure on this device:

```text
ggml_vulkan: device Vulkan0 does not support 16-bit storage.
E llama_model_load: error loading model: Unsupported device
```

An experimental patch changes the Vulkan initialization guard so that lack of advertised 16-bit storage is fatal only when `device->fp16` is enabled, and only requests `VK_KHR_16bit_storage` in that case.

With that patch applied, the following configuration was observed to load and run a Gemma 3 1B Q4_0 model with full GPU layer offload:

```bash
llama-bench \
  -m gemma-3-1b-q4_0.gguf \
  -ngl 99 \
  -fa off \
  -ub 64 \
  -p 512 \
  -n 128
```

Final recorded result on Mesa 26.1.7:

- prompt processing (`pp512`): approximately **44.7 t/s**
- token generation (`tg128`): approximately **7.85 t/s**
- three consecutive stability probes completed with no recorded i915 GPU hang events

A 3.09B Q4_K_S model was also observed with partial Vulkan offload, but CPU inference was faster on this hardware. Larger/full-offload attempts were constrained by the approximately 1.5 GiB device heap.

See [`docs/observations.md`](docs/observations.md) and [`docs/benchmarks.md`](docs/benchmarks.md).

## What is not established

`llama.cpp` maintainers have correctly pointed out that the Vulkan backend historically requires 16-bit storage support and that model data may include fp16 tensors.

Therefore, the successful run above does **not** by itself prove that the backend's 16-bit-storage requirement can be removed generally.

The unresolved question is:

> Why did this particular quantized model execute successfully after the initialization guard was relaxed, despite the device not advertising the expected 16-bit storage feature?

Possible explanations must be tested rather than assumed: tensor placement, conversion behavior, code paths not exercised by the model, or other implementation details.

## Repository layout

- `patches/0001-hasvk-relax-16bit-storage-init-guard.patch` — experimental patch used in testing
- `scripts/build-llama-vulkan.sh` — sanitized reproducible build helper
- `scripts/probe-vulkan.sh` — records Vulkan/driver capabilities without machine-specific configuration
- `scripts/run-benchmark.sh` — benchmark wrapper matching the documented test
- `docs/observations.md` — fact-only technical record
- `docs/benchmarks.md` — recorded performance data and limitations
- `docs/open-questions.md` — unresolved correctness questions and proposed validation work

## Upstream context

The corresponding draft `llama.cpp` pull request is:

- ggml-org/llama.cpp#27723 — `ggml-vulkan: allow fp32-only devices (Haswell hasvk)`

The PR title and original interpretation are broader than what is currently proven. This repository intentionally uses more conservative language while the behavior is investigated.

## Privacy / scope

This repository was created with fresh history from a private experimental environment. It intentionally excludes private hostnames, IP addresses, mount paths, credentials, fleet topology, service configuration, and unrelated deployment material.
