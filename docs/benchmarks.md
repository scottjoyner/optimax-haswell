# Benchmarks

These are recorded observations from the Haswell test system. They are not intended as generalized performance claims.

## Environment

- Intel Core i5-4590S
- Intel HD Graphics 4600 (Haswell GT2)
- 8 GB DDR3 UMA
- Ubuntu 24.04
- Mesa hasvk
- final validation: Mesa 26.1.7
- observed Vulkan device heap: ~1.5 GiB

Unless otherwise noted, the benchmark shape was:

```bash
llama-bench -p 512 -n 128
```

## Gemma 3 1B Q4_0

Final recorded configuration:

```bash
llama-bench \
  -m gemma-3-1b-q4_0.gguf \
  -ngl 99 \
  -fa off \
  -ub 64 \
  -p 512 \
  -n 128
```

Final Mesa 26.1.7 result:

| Metric | Result |
|---|---:|
| pp512 | ~44.7 t/s |
| tg128 | ~7.85 t/s |

Three consecutive stability probes completed without a recorded i915 GPU hang event.

Earlier tuning runs produced values in roughly the following range:

| Configuration | pp512 | tg128 | Notes |
|---|---:|---:|---|
| `ngl99 fa off ub64` | ~34.9 t/s | ~7.6 t/s | earlier, before final clock/driver tuning |
| `ngl99 fa off ub64`, clocks pinned | ~45.5 t/s | ~8.0 t/s | tuned run |
| `ngl99 fa off ub512`, clocks pinned | ~48.7–49.4 t/s | ~8.2 t/s | larger ubatch; not selected as conservative final config |

The final public reproduction uses `-ub 64` because it was the safer documented configuration.

## 3.09B Q4_K_S

Representative measurements:

| Backend | Configuration | pp512 | tg128 | Result |
|---|---|---:|---:|---|
| CPU | 4 threads, `-fa off` | ~36.9 t/s | ~7.8 t/s | baseline |
| Vulkan | partial/auto-fit | ~36.7 t/s | ~7.4 t/s | executed, slightly slower |
| Vulkan | `-ngl 32` hybrid | load failure | — | exceeded available device memory in recorded run |

Later CPU tuning reached approximately:

| CPU configuration | pp512 | tg128 |
|---|---:|---:|
| 4 threads | ~40.1 t/s | ~8.8 t/s |
| 3 threads | ~33.3 t/s | ~10.1 t/s |

For this tested 3B workload, CPU generation was faster than Vulkan offload on the HD 4600.

## LFM2.5 1.2B (Q4_0 / Q5_K_M)

Measured on the target device (Haswell HD 4600 / hasvk, Mesa 26.1.7) with the
patched build (`-fa off -ub 64`). Vulkan uses the Intel device selected via
`GGML_VULKAN_DEVICE=0`; CPU is `-ngl 0`.

| Model | Backend | ngl | pp512 | tg128 |
|---|---|---:|---:|---:|
| LFM2.5-1.2B-Instruct-Q4_0 | CPU | 0 | 31.42 t/s | 4.95 t/s |
| LFM2.5-1.2B-Instruct-Q4_0 | Vulkan (hasvk) | 99 | 34.88 t/s | 7.20 t/s |
| LFM2.5-1.2B-Instruct-Q5_K_M | CPU | 0 | 28.85 t/s | 4.04 t/s |
| LFM2.5-1.2B-Instruct-Q5_K_M | Vulkan (hasvk) | 99 | 32.36 t/s | 6.05 t/s |

For both quantizations, full GPU offload on the Haswell iGPU is faster than CPU:
generation (tg128) is ~1.45x (Q4_0) to ~1.5x (Q5_K_M) faster, and prompt
processing (pp512) is slightly faster. Q4_0 is the faster quant overall.

Sustained generation: a longer Q5_K_M run (`-n 512`) measured tg512 = 7.78 t/s
on Vulkan. This is higher than the 128-token average (6.05 t/s) because
startup/scheduling overhead is amortized over more tokens; there was no sign of
throughput degradation across the longer run, so no thermal throttling was
observed on this hardware within the tested window.

## Qwen2.5 0.5B (Q4_0)

Measured on the target device (Haswell HD 4600 / hasvk, Mesa 26.1.7), patched
build, `-fa off -ub 64`.

| Model | Backend | ngl | pp512 | tg128 |
|---|---|---:|---:|---:|
| Qwen2.5-0.5B-Instruct-Q4_0 | CPU | 0 | 82.84 t/s | 12.65 t/s |
| Qwen2.5-0.5B-Instruct-Q4_0 | Vulkan (hasvk) | 99 | 89.06 t/s | 10.98 t/s |

(The model is ≈630M params; `llama-bench` mislabels it "qwen2 1B" in its table,
but the filename and reported param count identify it as the 0.5B variant.)

For this small model, Vulkan prompt processing is slightly faster, but **CPU
generation is faster than Vulkan** (12.65 vs 10.98 t/s). The Vulkan speedup seen
at 1.2B does not generalize to very small models on this iGPU; the limited
compute/bandwidth only pays off above a certain model size.

## Correctness validation (perplexity)

Text generation can degenerate into a greedy loop on a bare prompt with hybrid
models, which confounds a naive CPU-vs-Vulkan token comparison. To test numerical
correctness directly, perplexity was computed on a fixed ~960-word corpus with
`llama-perplexity`, comparing CPU (`-ngl 0`) and Vulkan (`-ngl 99`) backends.

| Model | CPU PPL | Vulkan PPL |
|---|---:|---:|
| LFM2.5-1.2B-Instruct-Q5_K_M | 6.2488 ± 0.63738 | 6.2488 ± 0.63739 |
| LFM2.5-1.2B-Instruct-Q4_0 | 6.4569 ± 0.64130 | 6.4569 ± 0.64129 |

The reported perplexity values are identical between backends (6.2488 and 6.4569
respectively). The two runs differ only in the fifth decimal of the reported
standard error (±0.63738 vs ±0.63739; ±0.64130 vs ±0.64129), which is floating-point
noise. This demonstrates the patched Vulkan fp32 fallback path is numerically
correct versus CPU for these workloads. A reproducible script is provided as
`scripts/verify-correctness.sh`.

## What these numbers do and do not mean

They show that the patched backend executed the tested workloads and provide a performance reference for this machine.

They do not establish:

- general llama.cpp support for Haswell;
- correctness for all GGUF tensor types;
- correctness for all model architectures;
- that missing advertised 16-bit storage support can safely be ignored;
- that Haswell iGPU offload is generally faster than CPU inference.
