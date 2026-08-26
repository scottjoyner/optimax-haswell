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

## What these numbers do and do not mean

They show that the patched backend executed the tested workloads and provide a performance reference for this machine.

They do not establish:

- general llama.cpp support for Haswell;
- correctness for all GGUF tensor types;
- correctness for all model architectures;
- that missing advertised 16-bit storage support can safely be ignored;
- that Haswell iGPU offload is generally faster than CPU inference.
