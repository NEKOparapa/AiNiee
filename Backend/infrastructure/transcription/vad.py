"""Local Silero VAD hints; detection never decides which audio to discard."""
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import wave

from Backend.application.pipeline_common import PipelineError
from Backend.core.paths import backend_resource_path


SAMPLE_RATE = 16000
FRAME_SAMPLES = 512
CONTEXT_SAMPLES = 64
MODEL_SHA256 = "2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f"
MODEL_VERSION = "5.1.2"


def check_cancelled(context):
    if context is not None and context.is_cancelled():
        raise PipelineError("ASR_CANCELLED", "音频预处理已取消", 409)


class SileroVad:
    """One independent recurrent stream, following the official v5 ONNX inputs."""
    def __init__(self, model_path=None):
        model_path = Path(model_path or backend_resource_path("models", "silero_vad", "silero_vad.onnx"))
        try:
            with model_path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        except OSError as error:
            raise PipelineError("VAD_MODEL_UNAVAILABLE", "本地 Silero VAD 模型缺失或不可读；不会自动下载", 503) from error
        if digest != MODEL_SHA256:
            raise PipelineError("VAD_MODEL_INVALID", "本地 Silero VAD 模型校验失败", 503)
        try:
            import numpy as np
            import onnxruntime as ort
        except ImportError as error:
            raise PipelineError("VAD_DEPENDENCY_UNAVAILABLE", "Silero VAD 需要 numpy 和 onnxruntime；未自动安装", 503) from error
        self.np = np
        try:
            options = ort.SessionOptions()
            options.inter_op_num_threads = 1
            options.intra_op_num_threads = 1
            self.session = ort.InferenceSession(str(model_path), sess_options=options, providers=["CPUExecutionProvider"])
        except Exception as error:
            raise PipelineError("VAD_MODEL_UNAVAILABLE", f"本地 Silero VAD 模型无法加载: {error}", 503) from error
        self.reset()

    def reset(self):
        self._state = self.np.zeros((2, 1, 128), dtype=self.np.float32)
        self._context = self.np.zeros((1, CONTEXT_SAMPLES), dtype=self.np.float32)

    def probability(self, pcm_bytes):
        np = self.np
        if len(pcm_bytes) % 2:
            raise PipelineError("VAD_INPUT_INVALID", "PCM 16bit 输入帧字节数无效")
        samples = np.frombuffer(pcm_bytes, dtype="<i2").astype(np.float32) / 32768.0
        if not 0 < samples.size <= FRAME_SAMPLES:
            raise PipelineError("VAD_INPUT_INVALID", "Silero VAD 输入帧必须为 1 至 512 个 PCM 样本")
        if samples.size < FRAME_SAMPLES:
            samples = np.pad(samples, (0, FRAME_SAMPLES - samples.size))
        inputs = np.concatenate((self._context, samples.reshape(1, FRAME_SAMPLES)), axis=1)
        try:
            output, state = self.session.run(None, {
                "input": inputs, "state": self._state, "sr": np.array(SAMPLE_RATE, dtype=np.int64),
            })
            probability = float(np.asarray(output).reshape(-1)[0])
            if not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ValueError("invalid speech probability")
            self._state = state
            self._context = inputs[:, -CONTEXT_SAMPLES:].copy()
            return probability
        except Exception as error:
            raise PipelineError("VAD_INFERENCE_FAILED", f"本地语音活动检测失败: {error}") from error


@dataclass(frozen=True)
class VadResult:
    total_samples: int
    probabilities: list[float]
    speech_intervals: list[dict[str, int]]


def _speech_intervals(probabilities, total_samples, threshold):
    """Conservative hysteresis; retain short speech and pad its edges by 64 ms."""
    silence_samples, padding = SAMPLE_RATE * 160 // 1000, SAMPLE_RATE * 64 // 1000
    exit_threshold = max(0.01, threshold - 0.15)
    start = silence_start = None
    intervals = []
    for index, probability in enumerate(probabilities):
        position = index * FRAME_SAMPLES
        if start is None:
            if probability >= threshold:
                start = position
            continue
        if probability < exit_threshold:
            if silence_start is None:
                silence_start = position
            if min(total_samples, position + FRAME_SAMPLES) - silence_start >= silence_samples:
                intervals.append((max(0, start - padding), min(total_samples, silence_start + padding)))
                start = silence_start = None
        else:
            silence_start = None
    if start is not None:
        intervals.append((max(0, start - padding), total_samples))
    merged = []
    for start, end in intervals:
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return [{"start_ms": start * 1000 // SAMPLE_RATE,
             "end_ms": (end * 1000 + SAMPLE_RATE - 1) // SAMPLE_RATE} for start, end in merged]


def analyze_wave(path, *, threshold=0.35, context=None) -> VadResult:
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold < 1:
        raise PipelineError("INVALID_VAD_CONFIG", "vad_threshold 必须在 0 和 1 之间", 422)
    check_cancelled(context)
    detector = SileroVad()
    probabilities = []
    try:
        with wave.open(str(path), "rb") as stream:
            if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getcomptype()) != (SAMPLE_RATE, 1, 2, "NONE"):
                raise PipelineError("VAD_INPUT_INVALID", "VAD 需要 16kHz 单声道 16bit PCM WAV")
            total_samples = stream.getnframes()
            if total_samples <= 0:
                raise PipelineError("EMPTY_AUDIO", "音频没有有效采样")
            remaining = total_samples
            while remaining:
                check_cancelled(context)
                count = min(FRAME_SAMPLES, remaining)
                data = stream.readframes(count)
                if len(data) != count * 2:
                    raise PipelineError("VAD_INPUT_INVALID", "规范化音频数据不完整")
                probabilities.append(detector.probability(data))
                remaining -= count
    except (OSError, EOFError, wave.Error) as error:
        raise PipelineError("VAD_INPUT_INVALID", f"无法读取规范化 WAV: {error}") from error
    check_cancelled(context)
    return VadResult(total_samples, probabilities, _speech_intervals(probabilities, total_samples, threshold))
