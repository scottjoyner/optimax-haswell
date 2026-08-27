# Ling Tiny APEX on Intel UHD 620 (`hasvk`)

This note records a separate validation of the `hasvk` Vulkan path on a Lenovo
system with Intel UHD 620 graphics. It is evidence for the behavior addressed by
upstream `llama.cpp` PR #27723, not a claim of general Vulkan or model support.

## Runtime and model identity

- Runtime: `llama.cpp` PR branch `hasvk-fp32-support`
- Server build: `0.3.0-dev (build 1, commit da91b2d)`
- Build: `GGML_VULKAN=ON`, release build
- Vulkan ICD: Intel `hasvk` ICD (`intel_hasvk_icd.json`)
- Device: Intel UHD 620
- CPU: Intel Core i3-8130U, 2 physical cores / 4 logical CPUs
- Memory: approximately 12 GB system RAM
- Test affinity: one logical CPU, `taskset -c 0`, `--threads 1`
- Context: 8192 tokens for the extended quant comparison
- Slots: 1
- GPU configuration: `--n-gpu-layers 999 --flash-attn off --ubatch-size 64`
- All tests used a temporary loopback-only endpoint. Production admission and
  signed runtime projections were not modified.

The tested model repository is `SC117/Ling-3.0-tiny-abliterated-APEX-GGUF`.

| Quant | Artifact size | SHA-256 |
|---|---:|---|
| Mini | 3,408,245,728 bytes | `6d729f137e80218d212b62b33dfa9e319616101d11612b6d520593906ce48816` |
| I-Compact | 3,985,017,952 bytes | `f661876a860cc7093583a35a8187e66696c73a2cd512ece8117477a05ceda115` |

The upstream repository also contains I-Balanced, I-Quality, and BF16 artifacts.
Compact was the first additional quant tested. BF16 is approximately 15.8 GB and
was not considered viable on this machine.

## Isolation contract

Before each runtime trial, CPU, iGPU, and embedding inference services were
stopped. Persistence owners were inspected and inference persistence cron entries
were temporarily held. The trial proceeded only after zero `llama-server` PIDs,
zero inference sockets, and approximately 10 GB available RAM were observed.
The original crontab and incumbent services were restored after testing and their
exact model IDs were re-verified.

A timed-out checksum command briefly left a checksum reader in uninterruptible
I/O wait on the local ext4 device. The exact stale readers were terminated, disk
utilization returned to normal, and the Compact artifact was then checksum
verified. This storage event is not model or Vulkan evidence.

## Baseline: pre-PR runtime

On the same Lenovo class of device, the pre-PR runtime loaded Ling Mini but failed
on the first generation request:

```text
ggml_vulkan: device lost on Vulkan0
vk::Device::waitForFences: ErrorDeviceLost
ggml_assert(batch.slot_batched || batch.size() == 0)
```

The test was cleanly isolated from competing inference services. This established
that endpoint contention was not the sole cause.

## PR runtime: Mini without and with reasoning preservation

The PR runtime loaded Mini successfully and eliminated the Vulkan device-loss
failure. Early short probes omitted `--reasoning-preserve`; they returned HTTP 200
but exhausted the generation budget in `reasoning_content` while leaving
`content` empty.

The server log then identified the relevant control:

```text
chat template supports preserving reasoning, consider enabling it via --reasoning-preserve
```

Mini was relaunched with `--reasoning-preserve`, 8192 context, and a 512-token
completion budget. On the same arithmetic prompt used for Compact, it returned:

- HTTP 200;
- `finish_reason=stop`;
- 246 completion tokens;
- 560 reasoning characters;
- correct final answer: `1260 requests`;
- elapsed time: 30.777 seconds;
- prompt processing: 14.29 tokens/s;
- generation: 9.03 tokens/s;
- no device-loss, assertion, or crash messages.

## PR runtime: I-Compact

Compact loaded successfully with the same Vulkan configuration. On the identical
prompt and 512-token budget it returned:

- HTTP 200;
- `finish_reason=stop`;
- 181 completion tokens;
- 337 reasoning characters;
- correct final answer: `1260 requests`;
- elapsed time: 21.116 seconds;
- prompt processing: 16.63 tokens/s;
- generation: 10.01 tokens/s;
- no device-loss, assertion, or crash messages.

The Compact response was valid final `content`, not only hidden reasoning text.

## Interpretation

1. PR #27723 fixes the observed Intel `hasvk` initialization/generation failure
   path for this workload: the pre-PR device-loss/assertion failure did not recur
   in the PR build.
2. Ling reasoning is useful on this model, but `--reasoning-preserve` is a
   required part of the serving envelope for usable OpenAI-compatible output.
3. The apparent Mini output failure was primarily a serving-configuration issue,
   not proof that Mini was an inferior quant.
4. Compact was faster in this single comparison and produced a shorter reasoning
   trace, but this is not enough evidence for a general quant-quality ranking.
5. No quant was admitted to production. More prompts, repeated runs, and task
   quality scoring are required before choosing Mini versus Compact.

## Reproduction shape

The temporary server used the following public-safe shape; substitute local paths
and the exact model artifact as appropriate:

```bash
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/intel_hasvk_icd.json \
GGML_VULKAN_DEVICE=0 \
taskset -c 0 llama-server \
  --model Ling-3.0-tiny-abliterated-APEX-I-Compact.gguf \
  --host 127.0.0.1 --port 1247 \
  --threads 1 --ctx-size 8192 --parallel 1 \
  --n-gpu-layers 999 --flash-attn off --ubatch-size 64 \
  --reasoning-preserve \
  --alias ling-apex-compact
```

The endpoint must advertise the exact alias through `/v1/models` before sending a
completion. A listening port or successful model load alone is not sufficient
qualification evidence.

## Concurrency and primary-node qualification

A second isolated service run used I-Compact with `--parallel 2`, while preserving
all other settings and `--reasoning-preserve`. Two simultaneous requests both
returned HTTP 200, `finish_reason=stop`, and correct final content:

- wall time: 33.498 seconds;
- request latency: 24.181 and 33.481 seconds;
- generated tokens: 107 and 201;
- per-request generation rates: 5.41 and 6.92 tokens/s;
- aggregate generated throughput: approximately 9.19 tokens/s;
- peak server RSS: approximately 5.87 GiB;
- no Vulkan device-loss, assertion, or crash messages.

The single-slot Compact result was approximately 10.01 tokens/s generation. Thus,
two slots provide concurrent service capacity but do not increase aggregate
throughput on this two-core/UHD 620 node; they divide the available compute and
increase individual latency. The measured safe posture is one preferred active
request, with two slots as a bounded fallback only when latency is acceptable.

This evidence does not qualify Lenovo as a primary general-purpose inference
node. It supports a low-priority, one-slot specialist role for Ling/Compact or
similar workloads. Primary admission would require current signed projection,
real routed lifecycle proof, repeated task-family quality results, and a measured
capacity policy. No production admission was changed during this work.

## Scope limits

These results do not establish:

- correctness for all Ling quants or GGUF tensor types;
- correctness for all architectures on Intel UHD 620;
- safe removal of Vulkan 16-bit-storage requirements in general;
- production suitability of Ling on Lenovo;
- concurrency beyond one slot;
- that Compact is universally better than Mini.
