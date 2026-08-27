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

With that patch applied, the following configuration was observed to load and run small Q4_0/Q5_K_M models with full GPU layer offload on the Haswell iGPU. The showcased example uses `LFM2.5-1.2B-Instruct-Q5_K_M` (open-weight, fetchable without gated access, ~804 MB); `LFM2.5-1.2B-Instruct-Q4_0` (~696 MB) also runs. Measured numbers for both are in `docs/benchmarks.md`.

```bash
llama-bench \
  -m LFM2.5-1.2B-Instruct-Q5_K_M.gguf \
  -ngl 99 \
  -fa off \
  -ub 64 \
  -p 512 \
  -n 128
```

Final recorded result for the showcased model on Mesa 26.1.7:

- `LFM2.5-1.2B-Instruct-Q5_K_M` prompt processing (`pp512`): **32.36 t/s**
- token generation (`tg128`): **6.05 t/s** (Vulkan, full offload)
- CPU generation for the same model: 4.04 t/s, so Vulkan is ~1.5x faster at generation

A Gemma 3 1B Q4_0 run recorded pp512 ~44.7 t/s / tg128 ~7.85 t/s (see `docs/benchmarks.md`). A 3.09B Q4_K_S model was observed with partial Vulkan offload, but CPU inference was faster on this hardware. Larger/full-offload attempts were constrained by the approximately 1.5 GiB device heap.

See [`docs/observations.md`](docs/observations.md), [`docs/benchmarks.md`](docs/benchmarks.md), and the separate [`docs/ling-lenovo-pr27723.md`](docs/ling-lenovo-pr27723.md) evidence note for the Intel UHD 620 Ling A/B test.

## What is not established

`llama.cpp` maintainers have correctly pointed out that the Vulkan backend historically requires 16-bit storage support and that model data may include fp16 tensors.

Therefore, the successful run above does **not** by itself prove that the backend's 16-bit-storage requirement can be removed generally.

The unresolved question is:

> Why did this particular quantized model execute successfully after the initialization guard was relaxed, despite the device not advertising the expected 16-bit storage feature?

Possible explanations must be tested rather than assumed: tensor placement, conversion behavior, code paths not exercised by the model, or other implementation details.

## Repository layout

- `patches/0001-hasvk-relax-16bit-storage-init-guard.patch` — experimental patch used in testing
- `scripts/build-llama-vulkan.sh` — sanitized reproducible build helper (builds with `GGML_NATIVE=OFF` so the binary runs on Haswell; also builds `llama-perplexity`)
- `scripts/probe-vulkan.sh` — records Vulkan/driver capabilities without machine-specific configuration
- `scripts/run-benchmark.sh` — benchmark wrapper running both CPU and Vulkan backends
- `scripts/verify-correctness.sh` — CPU-vs-Vulkan perplexity comparison for numerical-correctness validation
- `docs/observations.md` — fact-only technical record
- `docs/benchmarks.md` — recorded performance data and limitations
- `docs/open-questions.md` — unresolved correctness questions and proposed validation work

## Upstream context

The corresponding draft `llama.cpp` pull request is:

- ggml-org/llama.cpp#27723 — `ggml-vulkan: allow fp32-only devices (Haswell hasvk)`

The carried patch in `patches/` is synchronized from the private `optiplex-optimax`
benchmarking repository, which is the source of the hasvk bring-up work documented here.

The PR title and original interpretation are broader than what is currently proven. This repository intentionally uses more conservative language while the behavior is investigated.

## Privacy / scope

This repository was created with fresh history from a private experimental environment. It intentionally excludes private hostnames, IP addresses, mount paths, credentials, fleet topology, service configuration, and unrelated deployment material.
