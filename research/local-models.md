# Local open-weight VLMs for Parts Pile — September 2026

Research date: 2026-09-06. Target hardware: Apple M4 Max MacBook Pro, 36GB and 64–128GB unified
memory configs. Target workload: 1–4 photos of a bin of hobbyist electronics → strict-JSON parts
list, with tiny-text OCR (chip markings, silkscreen, resistor codes) as the make-or-break skill.
Serving must speak OpenAI `/chat/completions` with `response_format: json_schema` (our
`openai_compat` provider, `partspile/providers/openai_compat.py`).

---

## 1. Recommendations

### The short version

The Qwen family owns local OCR in 2026 — every tier, every leaderboard, and every community
thread agrees ("for OCR specifically, Qwen wins at every tier" —
[BestLLMfor Gemma 4 guide](https://bestllmfor.com/guides/gemma-4-local-ollama-benchmarks/)).
The big 2026 shift: **Qwen3.5 (Feb 2026) and Qwen3.6 (Apr 2026) are natively multimodal** —
early-fusion vision-language models that replaced the separate Qwen3-VL line and beat it on
visual-understanding benchmarks ([Qwen3.5 overview](https://www.digitalocean.com/community/tutorials/qwen35),
[Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)). All Apache 2.0.

### #1 for the 36GB M4 Max: **Qwen3.6-35B-A3B** (4-bit, ~23GB)

MoE with 35B total / only **3B active** parameters — near-flagship OCR quality at small-model
speed. Its Qwen3.5 sibling scores **OCRBench 91.0, CC-OCR 80.7, OmniDocBench1.5 89.3**
([HF card](https://huggingface.co/Qwen/Qwen3.5-35B-A3B)); Qwen3.6 improves on it
(CC-OCR 81.9, OmniDocBench 89.9, [HF card](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)).
Community M4 Max numbers for this architecture class: **~60–68 tok/s decode at 4-bit**
([codersera](https://codersera.com/blog/run-qwen3-vl-30b-a3b-thinking-on-macos-installation-guide/),
[techie007 Qwen3.5 guide](https://techie007.substack.com/p/qwen-35-the-complete-guide-benchmarks)).

**Setup (Ollama, simplest — GGUF tag, NOT the `-mlx` tag, see caveat below):**

```bash
ollama pull qwen3.6:35b          # 23GB GGUF, vision + tools + 256K ctx
# https://ollama.com/library/qwen3.6

export PARTS_PILE_PROVIDER=openai_compat
export PARTS_PILE_BASE_URL=http://localhost:11434/v1
export PARTS_PILE_MODEL=qwen3.6:35b
```

Ollama's `/v1/chat/completions` accepts multiple `image_url` parts per message and enforces
`response_format: json_schema` via grammar-constrained decoding
([Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)) — exactly
what our provider already sends. 23GB model + KV cache + vision encoder fits a 36GB machine with
room for the OS; keep other apps light during a scan.

**Alternative runtime (LM Studio, MLX engine — usually faster prefill on Apple Silicon):**
download `qwen/qwen3.5-35b-a3b` (MLX 4-bit) in LM Studio ([catalog](https://lmstudio.ai/models/qwen3.5)),
start the server, then `PARTS_PILE_BASE_URL=http://localhost:1234/v1`,
`PARTS_PILE_MODEL=qwen/qwen3.5-35b-a3b`. LM Studio's OpenAI-compat endpoint supports
json_schema structured output and multi-image content arrays
([docs](https://lmstudio.ai/docs/developer/openai-compat/structured-output),
[unified MLX engine](https://lmstudio.ai/blog/unified-mlx-engine)).

### #1 for 64GB: same model, higher precision — **Qwen3.6-35B-A3B at 8-bit (~35GB)**

Quantization measurably hurts fine-text vision; with 64GB, spend the headroom on precision, not
parameters. Pull an 8-bit tag (`ollama pull qwen3.6:35b-a3b-q8_0` or the LM Studio MLX 8-bit
build). Decode stays fast (still 3B active). This is the best accuracy-per-second option for
the scan loop.

### #1 for 128GB: **Qwen3.5-122B-A10B** (4-bit, ~81GB)

The strongest open-weight OCR model that fits a laptop: **OCRBench 92.1, CC-OCR 81.8,
OmniDocBench 89.8, MMMU 83.9** ([HF card](https://huggingface.co/Qwen/Qwen3.5-122B-A10B)).
10B active → still interactive: ~38 tok/s decode and ~1,460 tok/s prefill measured on an
M5 Max 128GB (M4 Max will be somewhat lower)
([oMLX benchmark](https://omlx.ai/benchmarks/hmt0s3pi),
[Silicon Score](https://siliconscore.com/models/qwen3-5-122b-a10b/)).

```bash
ollama pull qwen3.5:122b         # ~81GB — 128GB machines only
export PARTS_PILE_BASE_URL=http://localhost:11434/v1
export PARTS_PILE_MODEL=qwen3.5:122b
```

(Do **not** try the 2–3-bit MLX mixed quants of the 122B to squeeze it into 64GB — 2-bit
vision quality is a known lottery; the 35B at 8-bit is better than the 122B at 2-bit for OCR.)

---

## 2. Comparison table — top candidates, September 2026

| Model | Params (act.) | Quant / RAM | OCR ability | Multi-image | JSON schema | License | Apple Silicon runtime |
|---|---|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B** (Apr 2026) | 35B (3B) | Q4 ~23GB / Q8 ~35GB | Best-in-class tier: CC-OCR 81.9, OmniDoc 89.9 (3.5 sibling: OCRBench 91.0) | Yes | Yes (Ollama/LM Studio/vLLM) | Apache 2.0 | Ollama GGUF ✅, LM Studio MLX ✅ (~60-68 tok/s M4 Max @Q4) |
| **Qwen3.5-122B-A10B** (Feb 2026) | 122B (10B) | Q4 ~81GB | **OCRBench 92.1** — best laptop-fit open model | Yes | Yes | Apache 2.0 | Ollama / MLX; ~38 tok/s on M5 Max 128GB |
| **Qwen3.5-27B / Qwen3.6-27B** (dense) | 27B | Q4 ~18GB | OCRBench 89.4, CC-OCR 81.0 | Yes | Yes | Apache 2.0 | Ollama/LM Studio; dense → ~15-25 tok/s (slower than the MoE, slightly below it on OCR too) |
| **Qwen3-VL-8B** (Oct 2025) | 8B | Q4 ~6-8GB | DocVQA 96.1 — best tiny option ([tinyweights](https://tinyweights.dev/posts/best-local-vision-language-models-2026/)) | Yes | Yes | Apache 2.0 | `ollama pull qwen3-vl:8b`, very fast; fallback if RAM is contended |
| **Gemma 4 26B/31B** (Apr 2026) | 26/31B | Q4 ~16-19GB | Good general vision, but loses to Qwen on OCR at every size ([BestLLMfor](https://bestllmfor.com/guides/gemma-4-local-ollama-benchmarks/)) | Yes | Yes | Apache 2.0 ([model card](https://ai.google.dev/gemma/docs/core/model_card_4)) | Ollama 0.31+ ✅, strong Mac support (~50-95 tok/s) |
| **GLM-5.3-Flash** (Aug 2026) | 321B (18B) | Q4 ~170GB+ | Strong, natively multimodal, MIT | Yes | Yes (vLLM) | MIT | **Doesn't fit a laptop** — needs 256-512GB Mac Studio ([specs](https://www.mindstudio.ai/blog/run-glm-5-3-flash-locally)) |
| MiniCPM-V 4.6 (2026) | 1.2B | ~2GB | Mobile-tier; not enough for tiny chip markings | Yes | Partial | Apache 2.0-ish | mlx-vlm; too weak for this workload |

Not recommended: **Llama 3.2/4 Vision** (behind Qwen on OCR, Llama license restrictions),
**InternVL3.5** (good but no Qwen-level Mac tooling; strongest at UI/code screenshots, not
fine text — [InternVL3.5 paper](https://arxiv.org/pdf/2508.18265)), **Pixtral** (stale by 2026),
**Moondream** (too small for dense-pile OCR).

---

## 3. Runtime notes and gotchas (Apple Silicon, Sept 2026)

- **Ollama's new MLX backend had vision + structured-output bugs in mid-2026**: `-mlx` model
  tags silently dropped image input ([#17065](https://github.com/ollama/ollama/issues/17065))
  and ignored `format` schemas ([#16563](https://github.com/ollama/ollama/issues/16563)). Both
  are closed/fixed, but the GGUF tags (`qwen3.6:35b`, no `-mlx` suffix) are the battle-tested
  path. **Smoke-test before trusting**: send one fixture photo with the schema via `curl` and
  confirm the reply is schema-valid JSON that mentions actual image content.
- **Quantization hurts vision more than text.** Keep the vision projector (mmproj) at FP16/BF16;
  community reports show measurable OCR degradation from quantized projectors and even
  F16-GGUF-vs-transformers gaps on Qwen VL OCR
  ([llama.cpp #16334](https://github.com/ggml-org/llama.cpp/issues/16334),
  [MindStudio llama.cpp guide](https://www.mindstudio.ai/blog/how-to-run-qwen-vision-models-locally)).
  On 64GB+, run Q8 for this reason.
- **Latency budget**: high-res photos become 1–3K visual tokens each under Qwen's dynamic
  resolution. Expect roughly 5–15s prefill per photo + decode on M4 Max — a 4-photo bin scan in
  the ~30–90s range at Q4. Downscale to ~1500px longest edge per photo to control this (but
  test against OCR recall on fixtures first — resolution is what reads "B103").
- **Multi-image**: 1–4 images per request works across Ollama, LM Studio, and mlx-based servers
  via standard `content: [{image_url}, ...]` arrays — exactly what our provider sends.
- **Pure-MLX server alternatives** if Ollama/LM Studio disappoint:
  [mlx-openai-server](https://github.com/cubist38/mlx-openai-server) (has a `qwen3_vl` parser) or
  [vllm-mlx](https://github.com/waybarrios/vllm-mlx) (continuous batching, OpenAI + Anthropic
  endpoints). Both are OpenAI-compatible → just change `PARTS_PILE_BASE_URL`.

---

## 4. Honest caveats: where local will fall short of Claude

1. **Photographed tiny text ≠ document OCR.** OCRBench ~91 is measured mostly on flat scans and
   screenshots. Laser-etched gray-on-black IC markings, curved TO-92 bodies, glare, and 4-point
   SMD codes are much harder; expect real recall on the smallest markings to be far below the
   benchmark numbers, and below Claude's.
2. **Hallucinated part numbers.** OCR-tuned VLMs autocomplete plausible strings from partial
   strokes — a half-visible "74HC…" will confidently become a specific full canonical. This is a
   documented failure mode of learned OCR on ambiguous markings
   ([Basler chip-marking inspection](https://www.baslerweb.com/en/use-cases/semicon-chip-marking-inspection-recognition/)).
   Mitigation: lean hard on `confidence` + `needs_reshoot` in the prompt, and treat low-frequency
   exotic canonicals from the local model with suspicion.
3. **World-knowledge mapping is the bigger gap.** Reading "1AM" is OCR; knowing 1AM ⇒ MMBT3904 is
   knowledge. Claude's marking-code → canonical-part mapping (and its restraint when unsure) is
   noticeably stronger than a 3B-active local MoE. Expect the local model to read text about as
   well but *identify* less well.
4. **Expected accuracy drop** (estimate — validate with `python eval.py` on fixtures, never the
   holdout): roughly **10–25% fewer exact canonical matches** vs Claude on the same bins at Q4,
   closer to the low end at Q8/122B; plus more `needs_reshoot` flags. Resistor color-band decoding
   is likely the weakest category for any current local model.
5. **Constrained decoding + vision quantization stack their penalties.** If output quality looks
   oddly clipped, A/B test with `response_format` off (parse leniently) — grammar constraints
   occasionally fight long OCR transcriptions.

## 5. Sources

- Qwen3.5/3.6 model cards: [Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B) ·
  [Qwen3.5-35B-A3B](https://huggingface.co/Qwen/Qwen3.5-35B-A3B) ·
  [Qwen3.5-122B-A10B](https://huggingface.co/Qwen/Qwen3.5-122B-A10B) ·
  [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) ·
  [QwenLM/Qwen3.6](https://github.com/QwenLM/Qwen3.6) · [Qwen3-VL report](https://arxiv.org/abs/2511.21631)
- Ollama: [qwen3.6 library](https://ollama.com/library/qwen3.6) ·
  [qwen3.5 library](https://ollama.com/library/qwen3.5) ·
  [qwen3-vl:8b](https://ollama.com/library/qwen3-vl:8b) ·
  [structured outputs](https://docs.ollama.com/capabilities/structured-outputs) ·
  bugs [#17065](https://github.com/ollama/ollama/issues/17065), [#16563](https://github.com/ollama/ollama/issues/16563)
- LM Studio: [Qwen3.5 catalog](https://lmstudio.ai/models/qwen3.5) ·
  [structured output](https://lmstudio.ai/docs/developer/openai-compat/structured-output) ·
  [unified MLX engine](https://lmstudio.ai/blog/unified-mlx-engine)
- Apple Silicon perf: [Qwen3-VL-30B on macOS](https://codersera.com/blog/run-qwen3-vl-30b-a3b-thinking-on-macos-installation-guide/) ·
  [oMLX 122B benchmark](https://omlx.ai/benchmarks/hmt0s3pi) ·
  [Silicon Score 122B](https://siliconscore.com/models/qwen3-5-122b-a10b/) ·
  [Qwen 3.5 complete guide](https://techie007.substack.com/p/qwen-35-the-complete-guide-benchmarks)
- Competitors: [Gemma 4 model card](https://ai.google.dev/gemma/docs/core/model_card_4) ·
  [Gemma 4 local benchmarks](https://bestllmfor.com/guides/gemma-4-local-ollama-benchmarks/) ·
  [GLM-5.3-Flash locally](https://www.mindstudio.ai/blog/run-glm-5-3-flash-locally) ·
  [GLM-5.3-Flash guide](https://linas.substack.com/p/glm-5-3-flash-guide) ·
  [InternVL3.5](https://arxiv.org/pdf/2508.18265) ·
  [best small VLMs 2026](https://tinyweights.dev/posts/best-local-vision-language-models-2026/)
- OCR leaderboards: [OCRBench v2](https://99franklin.github.io/ocrbench_v2/) ·
  [OCRBench GitHub](https://github.com/yuliang-liu/multimodalocr)
