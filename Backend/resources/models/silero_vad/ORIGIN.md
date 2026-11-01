# Silero VAD ONNX

This directory bundles the unmodified `silero_vad.onnx` model from the official
[Silero VAD v5.1.2 release](https://github.com/snakers4/silero-vad/releases/tag/v5.1.2).

- Upstream repository: https://github.com/snakers4/silero-vad
- Fixed commit: `6478567951ae5c9979ad7b234185b5515f4be7a1`
- Model source: https://raw.githubusercontent.com/snakers4/silero-vad/6478567951ae5c9979ad7b234185b5515f4be7a1/src/silero_vad/data/silero_vad.onnx
- SHA-256: `2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f`
- Size: 2,327,524 bytes
- License: MIT, copyright 2020-present Silero Team; the upstream license is
  included verbatim in `LICENSE`.
- Inference reference: https://github.com/snakers4/silero-vad/blob/6478567951ae5c9979ad7b234185b5515f4be7a1/src/silero_vad/utils_vad.py

AiNiee uses ONNX Runtime and NumPy directly: 16 kHz mono, 512 new samples per
frame, 64 prior context samples, and recurrent state shaped `(2, 1, 128)`.
No Torch dependency or runtime download is required. VAD is used only to prefer
quiet chunk boundaries; audio is never removed based on the detector's result.
