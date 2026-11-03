"""Offline release smoke check, also runnable inside the frozen backend."""
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import wave

from Backend.core.media_tools import bundled_media_tools_dir, find_media_tool


def check_media_tools(ffmpeg, ffprobe):
    # An absolute executable path and empty PATH detect accidental dependencies
    # on the build machine's FFmpeg installation or extra runtime DLLs.
    environment = {**os.environ, "PATH": ""}
    for name in ("LD_LIBRARY_PATH", "LD_LIBRARY_PATH_ORIG", "DYLD_LIBRARY_PATH"):
        environment.pop(name, None)

    def run(tool, *arguments):
        result = subprocess.run([str(tool), *map(str, arguments)], env=environment,
                                stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=45,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if result.returncode:
            raise RuntimeError(f"Bundled media tool failed: {tool}\n{result.stderr[-2000:]}")
        return result.stdout

    versions = {name: run(tool, "-version").splitlines()[0]
                for name, tool in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))}
    with TemporaryDirectory(prefix="ainiee media check ") as temporary:
        video = Path(temporary) / "sample video.mp4"
        audio = Path(temporary) / "audio.wav"
        # File inputs also work in builds without capture devices/lavfi input.
        frames = Path(temporary) / "frames.rgb"
        frames.write_bytes(bytes((0, 0, 255)) * 32 * 32 * 5)
        original_audio = Path(temporary) / "original.wav"
        with wave.open(str(original_audio), "wb") as stream:
            stream.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
            stream.writeframes(b"\0\0" * 44100)
        run(ffmpeg, "-hide_banner", "-v", "error", "-nostdin", "-y",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "32x32",
            "-framerate", "5", "-i", frames, "-i", original_audio,
            "-c:v", "mpeg4", "-c:a", "aac", "-shortest", video)
        probe = json.loads(run(ffprobe, "-v", "error", "-show_streams", "-of", "json", video))
        if {stream["codec_type"] for stream in probe["streams"]} != {"audio", "video"}:
            raise RuntimeError("Bundled ffprobe did not detect the generated video/audio streams")
        run(ffmpeg, "-v", "error", "-nostdin", "-y", "-i", video,
            "-map", "0:a:0", "-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", audio)
        with wave.open(str(audio), "rb") as stream:
            if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (16000, 1, 2):
                raise RuntimeError("Bundled ffmpeg generated invalid PCM audio")
            if stream.getnframes() < 15000:
                raise RuntimeError("Bundled ffmpeg generated incomplete PCM audio")
    return {"status": "ok", "versions": versions}


def check_bundled_media_tools():
    directory = bundled_media_tools_dir()
    if directory is None:
        raise RuntimeError("This check must run inside the packaged backend")
    tools = [find_media_tool(name) for name in ("ffmpeg", "ffprobe")]
    if any(path is None or not Path(path).is_relative_to(directory.resolve()) for path in tools):
        raise RuntimeError("The release is missing its bundled FFmpeg/ffprobe")
    return check_media_tools(*tools)
