# Codebase Concerns

**Analysis Date:** 2026-04-14

## Tech Debt

**Language Hardcoding in ASR:**
- Issue: `src/speech/asr.py` line 170 hardcodes `language="English"` regardless of user settings
- Files: `src/speech/asr.py`
- Impact: User's language preference is ignored; non-English audio transcribes poorly
- Fix approach: Use the `language` parameter passed to `transcribe_audio()` method

**Inaccurate Time Estimation:**
- Issue: `src/gui/main_window.py` line 755 calculates `end_time = start_time + len(result.text.split()) * 0.5` - assumes 500ms per word
- Files: `src/gui/main_window.py`
- Impact: Speaker diarization receives incorrect timestamps, causing misaligned speaker assignments
- Fix approach: Use actual audio duration from the captured samples instead of text-based estimation

**Hardcoded Audio Buffer Durations:**
- Issue: `src/speech/asr.py` lines 310-311 hardcode `min_process_duration=3.0` and `max_process_duration=8.0` seconds
- Files: `src/speech/asr.py`
- Impact: Cannot adapt to different ASR model requirements; may process suboptimal chunk sizes
- Fix approach: Move to configuration with sensible defaults

**Subprocess Dependency on pactl/parec:**
- Issue: `src/audio/capture.py` assumes `pactl` and `parec` are available with no validation
- Files: `src/audio/capture.py`
- Impact: Application fails silently or crashes if PulseAudio/PipeWire is not installed
- Fix approach: Check for command availability at startup and provide clear error message

**Brittle pactl Output Parsing:**
- Issue: `src/audio/capture.py` parses pactl output using string matching (e.g., `startswith("Source #")`, `split(": ", 1)[1]`)
- Files: `src/audio/capture.py` lines 159-212, 251-270
- Impact: Parsing breaks if pactl output format changes across versions
- Fix approach: Add version-aware parsing with fallback and validation

**Settings Dialog API Key Stored in Plain Text:**
- Issue: `src/utils/config.py` saves API key to `config.json` without encryption
- Files: `src/utils/config.py`, `src/gui/settings_dialog.py`
- Impact: API key readable by anyone with file access
- Fix approach: Use system keyring (e.g., `keyring` package) for API key storage

**Global Singletons with Lazy Initialization:**
- Issue: `src/database/manager.py` line 306-316 and `src/utils/config.py` line 186-195 use global singletons initialized on first use
- Files: `src/database/manager.py`, `src/utils/config.py`
- Impact: Potential race conditions in multi-threaded access; testing difficult
- Fix approach: Use dependency injection or thread-safe initialization pattern

## Known Bugs

**Model Fetch Thread Resource Leak:**
- Issue: `src/gui/settings_dialog.py` lines 886-894 creates new `ModelFetchThread` without properly cleaning up previous one
- Files: `src/gui/settings_dialog.py`
- Trigger: Rapidly changing API key causes multiple threads to run concurrently
- Workaround: Wait for thread completion before creating new one (already partially addressed with `isRunning()` check)

**Audio Processing Thread Not Guaranteed to Stop:**
- Issue: `src/audio/capture.py` `AudioCaptureThread.stop()` calls `terminate()` then `wait(timeout=2)` - may not fully clean up
- Files: `src/audio/capture.py` lines 109-130
- Trigger: Stopping capture during active recording
- Workaround: Application typically restarts cleanly, but repeated stop/start may accumulate zombie processes

**Temp File Leak in Diarization:**
- Issue: `src/speech/diarization.py` line 114 creates temp WAV files, deleted in `finally` block but error path may skip deletion
- Files: `src/speech/diarization.py` lines 114-131
- Trigger: Exception during `preprocess_wav()` call
- Workaround: System temp file cleanup handles orphaned files eventually

**ASR Model Not Validated Before Use:**
- Issue: `src/speech/asr.py` checks `QWEN_ASR_AVAILABLE` flag but model loading can still fail later
- Files: `src/speech/asr.py`
- Trigger: Corrupted model cache or incompatible CUDA version
- Workaround: Model reload on next startup

## Security Considerations

**Plain Text API Key Storage:**
- Risk: API keys stored in `~/.config/recorder-python/config.json` readable by other users
- Files: `src/utils/config.py`
- Current mitigation: None - config file has standard filesystem permissions
- Recommendations: Use system keyring (see Tech Debt section)

**OpenRouter API Key in Memory:**
- Risk: `src/ai/openrouter.py` stores API key in `self.api_key` which may be exposed in crash dumps or logs
- Files: `src/ai/openrouter.py`
- Current mitigation: Headers set to not log content
- Recommendations: Consider API key masking in logs

**External URL Opens Without Confirmation:**
- Risk: `src/gui/settings_dialog.py` line 500 opens `openrouter.ai/keys` via `setOpenExternalLinks(True)`
- Files: `src/gui/settings_dialog.py`
- Current mitigation: User must click link explicitly
- Recommendations: Add confirmation dialog before opening external URLs

**No HTTPS Enforcement for API Calls:**
- Risk: `src/ai/openrouter.py` uses `https://` but doesn't verify certificates strictly
- Files: `src/ai/openrouter.py`
- Current mitigation: httpx default behavior
- Recommendations: Add explicit certificate verification

**Subprocess Injection Risk:**
- Risk: `src/audio/capture.py` constructs shell commands from audio source names
- Files: `src/audio/capture.py` lines 75-88, 313-316
- Current mitigation: Source names come from pactl parsing, not user input directly
- Recommendations: Validate source names against allowlist pattern

## Performance Bottlenecks

**Diarization Temp File I/O:**
- Problem: Each 10-second audio chunk writes to temporary WAV file, processes, then deletes
- Files: `src/speech/diarization.py` lines 114-131
- Cause: Resemblyzer requires file-based input; no in-memory processing
- Improvement path: Use in-memory audio buffer with scipy/io.wavfile or memory-based WAV processing

**Large Audio Buffer Accumulation:**
- Problem: `src/speech/diarization.py` accumulates `_audio_chunks` list without size limit
- Files: `src/speech/diarization.py` lines 239, 282-308
- Cause: Audio is accumulated until 10-second threshold reached
- Improvement path: Implement bounded queue with max memory limit

**No Concurrent Request Batching for AI:**
- Problem: Each question generates a separate OpenRouter API call with no batching
- Files: `src/ai/openrouter.py`, `src/gui/main_window.py`
- Cause: Questions detected individually
- Improvement path: Batch multiple questions per API request within time window

**SQLite Single-Writer Limitation:**
- Problem: `src/database/manager.py` uses SQLite without write batching
- Files: `src/database/manager.py`
- Cause: Each `add_message()` commits immediately
- Improvement path: Implement write queuing with periodic commits

**Model Loading on Every Startup:**
- Problem: Qwen3-ASR model loads from HuggingFace on each application start
- Files: `src/speech/asr.py` lines 85-129
- Cause: No persistent model caching with model registry
- Improvement path: Implement model caching with checksum verification

## Fragile Areas

**pactl Output Format Dependency:**
- Why fragile: Parsing logic in `src/audio/capture.py` assumes specific output format from `pactl list sources`
- Files: `src/audio/capture.py` lines 149-270
- Safe modification: Add output format version detection and schema validation
- Test coverage: No tests for pactl parsing - requires manual testing with different PulseAudio versions

**Resemblyzer Preprocessing Requirements:**
- Why fragile: `src/speech/diarization.py` preprocess_wav() expects specific audio format and sample rate
- Files: `src/speech/diarization.py` lines 124-129
- Safe modification: Add audio format validation before processing
- Test coverage: No automated tests for audio preprocessing edge cases

**Qwen ASR Model Availability:**
- Why fragile: Downloads depend on HuggingFace Hub availability and network connectivity
- Files: `src/speech/asr.py`, `scripts/download_models.py`
- Safe modification: Implement offline mode with local model validation
- Test coverage: No fallback testing for network failures

**Audio Source Name Parsing:**
- Why fragile: `src/audio/capture.py` uses regex `app-pid-(\d+)` to match application sources
- Files: `src/audio/capture.py` line 313
- Safe modification: Add validation that PID exists before creating loopback
- Test coverage: Only works with specific PulseAudio/PipeWire configurations

**ASR Language Parameter Ignored:**
- Why fragile: `src/speech/asr.py` line 170 ignores `language` parameter, always using "English"
- Files: `src/speech/asr.py`
- Safe modification: Pass language parameter to model.transcribe()
- Test coverage: Functionality works but doesn't respect user configuration

## Scaling Limits

**Memory: Audio Buffer Growth:**
- Current capacity: Unbounded `self._audio_buffer` in diarization; ~8 seconds max in ASR worker
- Limit: RAM exhaustion for recordings longer than ~30 minutes without processing
- Scaling path: Implement streaming architecture with processed chunk cleanup

**Memory: Resemblyzer Embedding Cache:**
- Current capacity: No limit on `_speaker_embeddings` dict in `src/speech/diarization.py` line 58
- Limit: Number of unique speaker clusters = unbounded
- Scaling path: Implement speaker ID consolidation after session end

**Disk: Temp File Accumulation:**
- Current capacity: Temp WAV files deleted immediately unless error occurs
- Limit: Crash scenarios may leave temp files in system temp directory
- Scaling path: Use named pipes or memory buffers instead of temp files

**Database: Session Size:**
- Current capacity: SQLite with no pagination for message retrieval
- Limit: Sessions with >10,000 messages may cause UI slowdown
- Scaling path: Implement message pagination and virtual scrolling

**API: OpenRouter Rate Limits:**
- Current capacity: No rate limiting or retry logic in `src/ai/openrouter.py`
- Limit: OpenRouter free tier limits (~100 requests/day typical)
- Scaling path: Implement request queuing with exponential backoff

## Dependencies at Risk

**qwen-asr Package:**
- Risk: External package with limited community; may not support latest transformers
- Impact: Transcription breaks if package API changes or drops Python 3.10+ support
- Migration plan: Wrap in abstraction layer to swap to alternative ASR (Whisper, etc.)

**resemblyzer Package:**
- Risk: Low maintenance package; may have compatibility issues with newer numpy/scipy
- Impact: Speaker diarization fails with import errors
- Migration plan: Use alternative (pyannote.audio) or implement custom voice embedding

**PySide6:**
- Risk: Heavy Qt dependency; may have installation issues on non-GUI systems
- Impact: Cannot run in headless mode even for processing stored recordings
- Migration plan: Add optional GUI dependency with CLI-only mode

**pyaudio/pulsectl:**
- Risk: Platform-specific audio handling; may fail on Wayland-only systems
- Impact: Audio capture fails without PulseAudio/PipeWire
- Migration plan: Add support for other audio backends (PulseAudio, PipeWire, ALSA detection)

## Missing Critical Features

**Error Recovery:**
- Problem: No retry logic for transient failures (network, audio device disconnect)
- Blocks: Reliable long-running recording sessions

**Configuration Validation:**
- Problem: No schema validation on config.json load
- Blocks: Debugging config-related issues; corrupted config can crash app

**Audio Device Hotplug:**
- Problem: Audio source list is only refreshed on user action or app start
- Blocks: Detecting new microphones without app restart

**Session Persistence Across Crashes:**
- Problem: In-progress recording lost if app crashes
- Blocks: Reliable recording for important meetings

**Progress Indicators:**
- Problem: No progress feedback for model downloads or long operations
- Blocks: User confidence during wait times

## Test Coverage Gaps

**Untested: Audio Capture Parsing:**
- What's not tested: `pactl` output parsing for different PulseAudio versions
- Files: `src/audio/capture.py` lines 149-270
- Risk: UI shows no sources or wrong sources on system configuration changes

**Untested: Model Download Scripts:**
- What's not tested: Network failure handling, disk space checks, partial downloads
- Files: `scripts/download_models.py`, `scripts/download_qwen_asr.py`
- Risk: Corrupted model files or incomplete downloads go undetected

**Untested: ASR Worker Queue Processing:**
- What's not tested: Queue overflow handling, worker thread shutdown during processing
- Files: `src/speech/asr.py` lines 298-363
- Risk: Memory leak or hang on stop during transcription

**Untested: Database Migration:**
- What's not tested: Schema migrations, upgrade from previous versions
- Files: `src/database/manager.py`
- Risk: Data loss or corruption when upgrading application

**Untested: Settings Dialog Thread Safety:**
- What's not tested: Concurrent settings saves, thread cleanup on dialog close
- Files: `src/gui/settings_dialog.py` lines 200-206
- Risk: Resource leak when rapidly opening/closing settings

**Untested: Audio Format Conversion:**
- What's not tested: Resampling with different sample rates, channel conversion
- Files: `src/speech/asr.py` lines 194-218
- Risk: Poor transcription quality with non-16kHz audio sources

---

*Concerns audit: 2026-04-14*
