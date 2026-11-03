#!/usr/bin/env bash
# Build native, self-contained CLI tools; no GPL/nonfree or third-party libraries.
# Run Tools/prepare_ffmpeg.py first. Windows uses an MSYS2 MINGW64 shell.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TARGET="${1:?Expected windows or macos}"
ARCH="${2:?Expected x86_64 or arm64}"
VERSION="$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' "$ROOT/Tools/ffmpeg-source.json")"
SOURCE="$ROOT/build/ffmpeg-source/ffmpeg-$VERSION"
STAGE="$ROOT/build/media-tools/$TARGET-$ARCH"
WORK="$ROOT/build/ffmpeg-work/$TARGET-$ARCH"
test -f "$SOURCE/configure" || { echo "Run python Tools/prepare_ffmpeg.py first" >&2; exit 1; }
mkdir -p "$STAGE" "$WORK"
cd "$WORK"
FLAGS=(--disable-autodetect --disable-network --disable-doc --disable-debug
       --disable-ffplay --disable-avdevice --disable-hwaccels --disable-x86asm
       --enable-static --disable-shared --disable-gpl --disable-nonfree)
case "$TARGET-$ARCH" in
    windows-x86_64)
        FLAGS+=(--target-os=mingw32 --arch=x86_64 --cc=gcc --disable-pthreads --extra-ldflags=-static)
        SUFFIX=.exe
        ;;
    macos-arm64|macos-x86_64)
        CPU="$ARCH"
        [[ "$ARCH" != arm64 ]] || CPU=aarch64
        FLAGS+=(--target-os=darwin "--arch=$CPU" --cc=clang
                --extra-cflags=-mmacosx-version-min=13.0 --extra-ldflags=-mmacosx-version-min=13.0)
        SUFFIX=
        ;;
    *) echo "Unsupported FFmpeg target: $TARGET-$ARCH" >&2; exit 1 ;;
esac
bash "$SOURCE/configure" "${FLAGS[@]}"
make -j "${FFMPEG_BUILD_JOBS:-4}" "ffmpeg$SUFFIX" "ffprobe$SUFFIX"
cp "ffmpeg$SUFFIX" "ffprobe$SUFFIX" "$STAGE/"
chmod +x "$STAGE/ffmpeg$SUFFIX" "$STAGE/ffprobe$SUFFIX"
cp "$SOURCE/COPYING.LGPLv2.1" "$SOURCE/LICENSE.md" "$STAGE/"
cp "$ROOT/build/ffmpeg-source/ffmpeg-$VERSION.tar.xz" "$STAGE/"
cp "$ROOT/Tools/ffmpeg-source.json" "$ROOT/Tools/prepare_ffmpeg.py" "$ROOT/Tools/scripts/build_ffmpeg.sh" "$STAGE/"
{
    printf 'FFmpeg %s, unmodified upstream source, built for %s-%s\n' "$VERSION" "$TARGET" "$ARCH"
    printf 'Source: https://ffmpeg.org/releases/ffmpeg-%s.tar.xz\n' "$VERSION"
    printf 'Configure:'
    printf ' %q' "${FLAGS[@]}"
    printf '\nCompiler: '
    "${CC:-cc}" --version | head -n 1
    printf '\nThese standalone tools are used as subprocesses by AiNiee.\n'
    printf 'The corresponding source archive, license and build script are included here.\n'
} > "$STAGE/BUILD-INFO.txt"
"$STAGE/ffmpeg$SUFFIX" -version
"$STAGE/ffprobe$SUFFIX" -version
