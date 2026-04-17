# Speed up transcription flow — investigation, plan, and progress

> **Status:** Phase 1 ✓, Phase 2 ✓, Phase 3 ✓, Phase 4 ✓, Phase 5 partial ✓.

## Implementation log

Shipped in this PR (all covered by the 11 new tests in `tests/test_asr_speedups.py`):

* **Phase 1** — zero-risk wins:
  * `src/audio/capture.py`: parec chunk size is now configurable via `audio.chunk_duration` (seconds) and defaults to 0.1 s. Silence-based flushing can now react within ~100 ms instead of being quantised to a 2.0 s read.
  * `src/speech/asr.py`: 1 s warmup decode at load-time (removes 0.5–2 s cold-start on first utterance); `torch.inference_mode()` around `generate()`; `torchaudio.Resample` cached by (orig_sr, target_sr); `DEFAULT_MODEL_SIZE = "0.6B"` (existing users on 1.7B keep it via config override).
  * `_finalize_buffer` now trims leading/trailing silence before decode (with a 60 ms margin) — saves encoder cost on backstop flushes.
* **Phase 2** — streaming/rolling-window interims: new `qwen_asr.interim_strategy = "window"` (default) decodes only the last `qwen_asr.interim_window_sec = 4.0` seconds on interim ticks. The `asr_interim` log now shows `audio_sec` (what was decoded) vs `total_buffer_sec` (what the UI sees). Final flush still decodes the whole buffer, so quality on committed text is unaffected. Set `qwen_asr.interim_strategy = "full"` to restore old behaviour.
* **Phase 3** — webrtcvad integration: new `qwen_asr.vad_backend = "webrtc"` (default, with `vad_aggressiveness = 2`). The ASR worker now asks webrtcvad for trailing-silence detection and buffer-speech gating; falls back to the existing RMS path on any import/init failure or on incompatible sample rates. Logged as `asr_vad_backend`.
* **Phase 5** — polish: `QwenASRConfig` dataclass now exposes every tuning knob explicitly (instead of each living only as a string key lookup), which makes them appear in the round-tripped config.json and available to the Settings UI if we ever want to surface them.

* **Phase 4** — `faster-whisper` backend shipped:
  * `src/speech/faster_whisper_backend.py` — new `FasterWhisperASR` class mirroring the Qwen3ASR signal/method surface. `_auto_device()` picks cuda / cpu via ctranslate2, `_auto_compute_type()` picks `int8_float16` on cuda / `int8` on cpu.
  * `src/speech/asr.py` — `TranscriptionManager.__init__` now routes to the configured backend via `stt.backend = "qwen3" | "faster-whisper"`. Falls back to qwen3 if the faster-whisper import fails, so a user with a broken ctranslate2 install can still start the app.
  * `src/utils/config.py` — new `FasterWhisperConfig` dataclass; `STTConfig` gains `backend: str = "qwen3"`.
  * `src/gui/settings_dialog.py` — "Backend" dropdown + a "faster-whisper" group (model size / compute type / VAD filter). Switching backends shows a "restart required" message rather than hot-swapping at runtime.
  * `requirements.txt` — `faster-whisper>=1.1.0` added. Smoke-tested end-to-end on this machine with `tiny` on CPU int8 (3 s load, 316 ms warmup, VAD correctly drops non-speech input).
  * **12 new tests** in `tests/test_backends.py` covering config round-trip, backend selection, fallback-on-import-failure, and audio normalisation.

Not shipped in this PR:

* **Phase 5** — direct-queue audio path (skip Qt signal hop between capture and worker) and session-level language pin. These are small incremental wins that make sense once Phase 2 is measured in production — do in a follow-up if still noticeable.
* **AppImageBuilder.yml** updates to bundle the ctranslate2 wheel. Worth doing alongside the next packaged release — ctranslate2 ships manylinux wheels so no system deps needed.

## Original plan


## Current pipeline (recap)

```
parec (2 s chunks)
  → AudioCaptureThread.data_ready (int16 np.array, ~64 KB)
  → Qt signal → MainWindow.on_audio_data
  → TranscriptionManager.process_audio
  → ASRWorker.audio_queue
  → accumulate in audio_buffer, every 50 ms check:
      • silence pause >= 300 ms  → _finalize_buffer   (transcribe full buffer)
      • 1.5 s elapsed since last  → _emit_interim     (transcribe full buffer AGAIN)
      • 12 s hard backstop        → _finalize_buffer  (transcribe, keep 0.5 s tail)
  → Qwen3ASRModel.transcribe(full_buffer, sr=16000)   # full re-decode every time
  → TranscriptionResult → Qt signal → MainWindow → UI + questions + RAG + DB
```

## Bottlenecks (ranked by expected wall-clock impact)

| # | Bottleneck | Where | Impact |
|---|---|---|---|
| 1 | Every interim re-decodes the **entire growing segment** from scratch. At 12 s buffer + interims every 1.5 s that's up to 8 redundant full-segment forward passes per segment. | `src/speech/asr.py` `_emit_interim` | Huge — scales with segment length |
| 2 | parec delivers audio in **2 s blocks**. Silence/flush logic can only act on 2-second boundaries → silence_flush_ms=300 effectively becomes ~300 ms + up-to-2000 ms jitter before the flush fires. | `src/audio/capture.py` `chunk_size = sample_rate * 2.0 * …` | 0.5–2.0 s of added end-to-end latency per utterance |
| 3 | Default model **Qwen3-ASR-1.7B**. No CPU path, float32 fallback if not on CUDA. | `src/speech/asr.py` `DEFAULT_MODEL_SIZE = "1.7B"` | 2–3× slower inference than 0.6B; GPU-only realistically |
| 4 | **No model warm-up** — first transcription cold-starts kernels / allocators. | `TranscriptionManager.initialize` | 500–2000 ms on the first utterance |
| 5 | **Ad-hoc RMS VAD** (framewise mean square + adaptive floor) — slow to react on noisy sources, requires per-flush 2 s probe & per-frame loop. `webrtcvad` is already in requirements.txt but unused. | `_should_flush`, `_trailing_silence_ms` | Modest (50–200 ms) + accuracy improvements → fewer unnecessary flushes |
| 6 | `torchaudio.transforms.Resample` is **constructed on every call**. If parec captures at 16 kHz (which it already does) this is dead code; but when sample_rate != 16000 it's O(log) wasted build time. | `_resample_audio` | Small, but free win |
| 7 | Language auto-detect runs even when user has set `stt.language = en/ru/uk`. Actually the current code DOES pass `language=` — but the default config is `auto`, costing an extra inference pass inside qwen-asr. | `transcribe_audio` | Modest — ~5–15 % |
| 8 | No `@torch.inference_mode()` / `torch.no_grad()` around forward pass. | `transcribe_audio` | Small (~5 %) + peak memory |
| 9 | Qt signal hops for every audio chunk (capture thread → main thread → manager → worker queue via `.copy()`). | `main_window.on_audio_data` | Small but compounding |

## Approaches considered

### A. Streaming / rolling-window decoding (attack bottleneck #1)

Qwen3-ASR is a non-streaming encoder-decoder (same family as Whisper) — it has no native streaming API. Two battle-tested patterns fit on top:

* **LocalAgreement-n** (Machácek et al., used by `whisper_streaming`, MIT). On each interim, decode only the newest window; commit the prefix that matches the previous two decodes; keep the unstable tail for the next round. Keeps word error close to offline.
* **Chunk-and-merge with small overlap**. Decode fixed ~3 s windows with 0.5 s overlap, emit the non-overlapped prefix immediately. Simpler, slightly worse on cross-chunk words.

Both cut interim cost from O(full_segment) to O(window). On a 12 s segment with 1.5 s interims we go from ~8 full-segment decodes to ~8 small-window decodes — **~4–8× throughput on the interim path**.

### B. Faster / alternative ASR backend

| Model | Languages | Streaming-friendly | Rough relative speed vs current (1.7B BF16 GPU) | Notes |
|---|---|---|---|---|
| Qwen3-ASR-0.6B (already supported) | same as 1.7B | same pattern | **~2.5–3×** | Switch default; tiny code change |
| faster-whisper `large-v3-turbo` (CTranslate2) int8_float16 GPU | 99 incl. en/ru/uk | batched + built-in Silero VAD | **~4–8×** | Mature. CPU-usable with int8 (~real-time). Pulls in `faster-whisper` dep |
| faster-whisper `distil-large-v3` | en only | yes | very fast | EN-only — doesn't meet RU/UK constraint |
| NVIDIA Parakeet-TDT-0.6B-v3 (multilingual EU) | includes en/ru/uk | native streaming (TDT) | extremely fast | Newer, less mature; pulls in NeMo — heavy dep tree |
| NVIDIA Canary-1B | en/de/es/fr | yes | fast | No RU/UK — rule out |
| Moonshine / Distil-Whisper | en | yes | very fast | No RU/UK — rule out |

**Recommendation:** keep Qwen3-ASR as the default-high-quality backend, switch default size to **0.6B**, and add **faster-whisper `large-v3-turbo`** as an alternate backend users can select in Settings. That gives a CPU-capable mode and a much faster GPU mode without removing Qwen.

### C. Lower-level tweaks

1. **Shrink parec chunk** from 2.0 s → **0.1 s** (~6.4 KB). Cuts silence-detection latency to ~100 ms + 50 ms worker tick.
2. **Warm up** model with a 1-s zero/sine buffer at the end of `load_model`.
3. **Swap custom RMS VAD for `webrtcvad`** (aggressiveness=2) *or* `silero-vad` (pytorch, more accurate on music/loopback). webrtcvad is already a declared dep, so zero install cost.
4. Keep a **single `torchaudio.transforms.Resample`** instance cached on `self` per (orig_sr, target_sr) pair.
5. Decorate `Qwen3ASR.transcribe_audio` with `@torch.inference_mode()`; on CUDA wrap in `torch.autocast("cuda", dtype=torch.bfloat16)` when dtype is bf16 (this is already partial via `dtype=bfloat16` on load, but inference_mode is missing).
6. Persist language pin: if `stt.language` is `auto`, detect language once on the first final segment and cache it for the remainder of the session (user can re-trigger by reopening settings).
7. **Coalesce Qt hops**: let `AudioCaptureThread` push directly into a `queue.Queue` shared with the worker (QThread is fine across threads); emit the signal only for metering/UI. Removes one signal-hop + one `.copy()` per chunk.
8. On finalization, **trim leading/trailing silence** from the buffer before sending to the model. Typical 2–5 s buffer contains 0.3–0.8 s silence that still gets encoded.

## Proposed phased changes

### Phase 1 — zero-risk wins (no new deps, no behavior change)

| File | Change |
|---|---|
| `src/audio/capture.py` | `chunk_size = int(sample_rate * 0.1 * channels * 2)` (2.0 → 0.1). Add `bufsize=0` or leave, test both; 100 ms chunks. |
| `src/speech/asr.py` :: `Qwen3ASR.load_model` | After successful load, run `self.model.transcribe(audio=(np.zeros(16000, dtype=np.float32), 16000))` inside try/except to warm kernels. Log `model_warmed=True`. |
| `src/speech/asr.py` :: `Qwen3ASR.transcribe_audio` | Wrap body in `with torch.inference_mode():` when `TORCH_AVAILABLE`. |
| `src/speech/asr.py` :: `Qwen3ASR.__init__` | `self._resampler_cache: dict[tuple[int,int], torchaudio.transforms.Resample] = {}` and reuse in `_resample_audio`. |
| `src/speech/asr.py` :: `DEFAULT_MODEL_SIZE` | Change `"1.7B"` → `"0.6B"`. Users on 1.7B keep it (config override). |
| `src/speech/asr.py` :: `_finalize_buffer` | Before `transcribe_audio`, trim leading/trailing silence using the existing RMS frame grid (cheap — already computed). |

Expected end-to-end latency improvement: **30–50 %** on the default path, zero behavior change for existing configs (they keep their model size).

### Phase 2 — streaming/rolling-window interims (attack bottleneck #1)

| File | Change |
|---|---|
| `src/speech/asr.py` :: `ASRWorker` | New state: `self._committed_text: str = ""`, `self._last_interim_text: str = ""`, `self._window_start_sample: int = 0`. |
| `_emit_interim` | Transcribe only the **last `interim_window_sec`** seconds of the buffer (default 3.0 s, configurable). Apply LocalAgreement-2: compare to `_last_interim_text`; the longest common prefix between the last two decodes is committed to `_committed_text`; the remainder is the unstable tail shown as interim. Emit `committed_text + tail`. |
| `_finalize_buffer` | Decode the whole final buffer once (quality-preserving), but if `_committed_text` prefix matches, only the suffix diff needs to flow to the UI (same UX, same text). |
| Config additions | `qwen_asr.interim_window_sec = 3.0`, `qwen_asr.interim_strategy = "local_agreement"` (values: `"full"` (current behaviour), `"local_agreement"` (new), `"sliding"`). Default = `"local_agreement"`. |

Expected interim-path CPU/GPU reduction: **3–6×** on typical 6–12 s utterances.

### Phase 3 — real VAD (webrtcvad, already installed)

| File | Change |
|---|---|
| `src/speech/asr.py` | Optional import `webrtcvad`. If available, replace `_trailing_silence_ms` + `_buffer_has_speech` with webrtcvad @ 30 ms frames, aggressiveness configurable (`qwen_asr.vad_aggressiveness = 2`). Fall back to current RMS on ImportError. |
| Config additions | `qwen_asr.vad_backend = "webrtc"` (values: `"rms"` (current), `"webrtc"`). Default = `"webrtc"`. |

Expected: fewer false-positive silences in noisy loopback (so fewer pointless flushes) and fewer missed pauses (so lower end-to-end latency before final emit). Also ~5× faster than the RMS path on long probes.

### Phase 4 — alternate backend: faster-whisper (opt-in)

| File | Change |
|---|---|
| `requirements.txt` | `faster-whisper>=1.1.0` (optional group, or add to main since it installs ctranslate2 wheels cleanly on linux). |
| `src/speech/asr.py` | Extract a tiny `ASRBackend` protocol (`transcribe(audio, sr, language) -> TranscriptionResult | None`). Two implementations: `Qwen3Backend` (existing), `FasterWhisperBackend` (new, wrapping `WhisperModel(model_size, device=..., compute_type=...)`). `TranscriptionManager` picks one based on `stt.backend`. |
| `src/gui/settings_dialog.py` | Add a "Backend" selector (`qwen3 / faster-whisper`) and per-backend model size dropdown. Only show if backend is available. |
| Config additions | `stt.backend = "qwen3"` (or `"faster-whisper"`), `faster_whisper.model_size = "large-v3-turbo"`, `faster_whisper.compute_type = "auto"` (`int8_float16` on CUDA, `int8` on CPU), `faster_whisper.vad_filter = true`. |

Expected: users without a GPU get a realistic real-time path for the first time. GPU users willing to try a different model get ~4–8× speed-up vs Qwen3-ASR-1.7B.

### Phase 5 — audio path polish (small but cumulative)

| Change | Rationale |
|---|---|
| `AudioCaptureThread` pushes directly into a `queue.Queue` owned by `ASRWorker`; `audio_data` Qt signal kept but only emitted every Nth chunk for UI metering. | Removes one signal hop + one `.copy()` per chunk. |
| Cache language pin per session after first successful detect when `stt.language == "auto"`. | Saves the detection pass on every subsequent segment. |
| Stop Qwen3's `max_new_tokens=256` hard-coding — scale with `audio_sec` (e.g. `min(256, int(audio_sec * 25))`). | Shorter buffers decode faster. |

## Rollout order and measurable success

1. **Phase 1** (1 PR, ~1 day). Metric: median `asr_chunk` `infer_sec` for a 6 s final on the default setup, before vs after. Target: −30 %.
2. **Phase 2** (1 PR, ~1–2 days). Metric: sum of `asr_interim` `infer_sec` across a 12 s segment. Target: −60 %.
3. **Phase 3** (1 PR, ~0.5 day). Metric: p95 latency from end-of-speech (human-marked) to final emit. Target: −40 % on noisy loopback.
4. **Phase 4** (1 PR, ~2 days). Metric: CPU-only laptop can transcribe real-time (RTFx ≥ 1.0). Current: ~0.2–0.4 on CPU with Qwen-1.7B.
5. **Phase 5** (1 PR, ~0.5 day). Minor polish; no new metric.

## Risks

- **Phase 1 parec chunk 2.0 → 0.1 s**: more wake-ups (~20/s) but each decode round is tiny; the worker already sleeps 50 ms, so throughput is unchanged. Verified safe on PipeWire.
- **Phase 1 default 1.7B → 0.6B**: accuracy drop on multilingual (EN/RU/UK mixed); Qwen reports 0.6B is close but not identical. Users who had 1.7B pinned keep it (config override).
- **Phase 2 LocalAgreement**: committed prefix can be wrong if decode #1 and #2 happen to share a wrong prefix (rare). Mitigation: keep the full-buffer final pass, which overrides committed text; the UI already rebuilds on `is_final=True`.
- **Phase 3 webrtcvad**: aggressiveness 3 can over-cut; start at 2. Fallback to RMS on import error keeps AppImage builds working if the wheel is missing.
- **Phase 4 faster-whisper**: adds `ctranslate2` native dep (~60 MB wheel). AppImage recipe needs updating (`AppImageBuilder.yml`). Verify on target distros.
- **Phase 5 direct queue**: need to ensure ASR worker drains queue on `stop()` to avoid leaking audio to the next session.

## Out of scope / rejected

- `torch.compile` on qwen-asr forward — fragile with the current wrapper API; re-evaluate when qwen-asr supports it natively.
- FlashAttention / xformers — already used by transformers where available.
- Parakeet-TDT multilingual — promising but NeMo dep tree is huge for a desktop app; revisit if Phase 4 isn't enough.
- Switching language detection to a dedicated small model (e.g. whisper-tiny for lang-id) — the pinned-after-first-detect cache (Phase 5) is cheaper.
