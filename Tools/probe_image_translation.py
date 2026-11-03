"""One-page DashScope image translation experiment; no OCR or text translator.

Requires the project's httpx and Pillow dependencies. Credentials come from
DASHSCOPE_API_KEY or an existing DashScope image-generation profile.
No automatic generation retries. --download-only reuses a saved response.
Example: python Tools/probe_image_translation.py --output-dir Data/ImageGenerationQA/new-run
Protocol: https://help.aliyun.com/zh/model-studio/qwen-image-generation-and-editing-api-reference
"""
import argparse
import base64
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.parse import urlsplit

import httpx
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
PROMPT = """把这张日语漫画里的所有日文对白、旁白、注释和手写文字翻译成简体中文，并直接把中文译文写在原图里，替换掉对应的日文。输出中文版漫画图片。
最重要的是完成文字翻译：输出图中的气泡和对白必须是清晰可读的简体中文，不要保留日文对白，不要只复制原图。完整保留每段话的含义，不漏译。
保留人物、分镜、气泡和黑白漫画画风，英文 Ubuntu 标志保持原样。
"""


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def scrub(text, key=""):
    text = str(text).replace(key, "[REDACTED]") if key else str(text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    text = re.sub(r"https?://\S+", "[URL]", text)
    return text[:1200]


def credentials(args):
    config = json.loads(args.config.read_text(encoding="utf-8-sig")) if args.config.is_file() else {}
    name = args.provider or config.get("active_image_generation_platform", "bailian_image")
    profile = config.get("image_generation_platforms", {}).get(name, {})
    if profile and profile.get("api_format", "DashScope") != "DashScope":
        raise ValueError("Select a DashScope image-generation profile with --provider")
    endpoint = args.endpoint or profile.get("api_url") or DEFAULT_ENDPOINT
    host = urlsplit(endpoint)
    if host.scheme != "https" or host.username or host.password or host.query or host.fragment:
        raise ValueError("Use an HTTPS DashScope endpoint without credentials or query parameters")
    if host.hostname not in ("dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com", "dashscope-us.aliyuncs.com") and not (host.hostname or "").endswith(".maas.aliyuncs.com"):
        raise ValueError("This experiment only sends credentials to official DashScope endpoints")
    if host.path != "/api/v1/services/aigc/multimodal-generation/generation":
        raise ValueError("Expected the native DashScope multimodal generation endpoint")
    key = os.environ.get("DASHSCOPE_API_KEY") or profile.get("api_key", "")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("Set DASHSCOPE_API_KEY or select a configured DashScope image-generation profile")
    return endpoint, key.strip(), "environment" if os.environ.get("DASHSCOPE_API_KEY") else f"image_generation_platforms.{name}"


def prepare(args):
    source = args.input.resolve()
    data = source.read_bytes()
    if len(data) > 10 * 1024 * 1024:
        raise ValueError("Input exceeds the provider's 10 MiB image limit")
    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image)
        image.load()
        width, height = image.size
        if min(width, height) < 1 or max(width, height) > 8000 or max(width, height) / min(width, height) > 10:
            raise ValueError("Input dimensions exceed the provider's limits")
        normalized = io.BytesIO()
        image.convert("RGB").save(normalized, format="PNG")
    if normalized.tell() > 10 * 1024 * 1024:
        raise ValueError("Normalized PNG exceeds 10 MiB")
    size = args.size or f"{round(width / 16) * 16}*{round(height / 16) * 16}"
    if not re.fullmatch(r"[1-9][0-9]*\*[1-9][0-9]*", size):
        raise ValueError("Size must be WIDTH*HEIGHT")
    out_width, out_height = map(int, size.split("*"))
    if not 512 ** 2 <= out_width * out_height <= 2048 ** 2 or max(out_width, out_height) / min(out_width, out_height) > 8:
        raise ValueError("Output dimensions exceed provider limits; pass --size WIDTH*HEIGHT")
    prompt = args.prompt_file.read_text(encoding="utf-8-sig") if args.prompt_file else PROMPT
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    parameters = {"n": 1, "size": size, "seed": args.seed, "prompt_extend": args.prompt_extend, "watermark": False}
    body = {"model": args.model, "input": {"messages": [{"role": "user", "content": [
        {"image": "data:image/png;base64," + base64.b64encode(normalized.getvalue()).decode("ascii")},
        {"text": prompt}]}]}, "parameters": parameters}
    metadata = {"source_path": str(source), "source_sha256": sha256(data), "input_size": [width, height],
                "submitted_sha256": sha256(normalized.getvalue()), "model": args.model,
                "parameters": parameters, "prompt": prompt, "ocr_used": False, "text_translator_used": False}
    return normalized.getvalue(), body, metadata


def download_result(response, output):
    urls = [part["image"] for choice in response.get("output", {}).get("choices", [])
            for part in choice.get("message", {}).get("content", []) if isinstance(part, dict) and part.get("image")]
    if not urls:
        raise ValueError("Provider returned no image; inspect response.json")
    url = urls[0]
    if urlsplit(url).scheme != "https":
        raise ValueError("Expected an HTTPS result URL")
    # Do not forward the API Authorization header to the image storage host.
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        data = bytearray()
        with client.stream("GET", url) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                data.extend(chunk)
                if len(data) > 64 * 1024 * 1024:
                    raise ValueError("Generated image exceeds the download limit")
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.format != "PNG":
            raise ValueError("Expected PNG from DashScope; received another format")
        dimensions = list(image.size)
    target = output / "translated.png"
    temporary = output / "translated.download"
    temporary.write_bytes(data)
    temporary.replace(target)
    return {"path": str(target), "size": dimensions, "sha256": sha256(data), "bytes": len(data)}


def comparison_page(output, report):
    title = html.escape(report["model"])
    (output / "comparison.html").write_text(f"""<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>漫画生图直译对照</title><style>body{{font-family:system-ui;background:#202020;color:#eee;margin:24px}}
.pages{{display:flex;gap:20px;align-items:start}}figure{{margin:0;flex:1;min-width:0}}img{{width:100%;background:white}}
figcaption{{margin:12px 0}}a{{color:#9cf}}</style><h1>原图与生图直译</h1>
<p>{title} · 无 OCR / 无 DeepSeek · <a href="report.json">运行记录</a></p>
<div class="pages"><figure><figcaption>日语原图</figcaption><a href="source.png"><img src="source.png"></a></figure>
<figure><figcaption>模型生成的简体中文译图</figcaption><a href="translated.png"><img src="translated.png"></a></figure></div>
<p>点击图片查看原尺寸。请对照检查漏译、错字、气泡归属及人物和线稿变化。</p></html>""", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "Data/MangaPipelineQA/inputs/ubunchu01_02.png")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", default="qwen-image-3.0-pro")
    parser.add_argument("--config", type=Path, default=ROOT / "Data/config.json")
    parser.add_argument("--provider", help="Existing DashScope image-generation profile")
    parser.add_argument("--endpoint")
    parser.add_argument("--size", help="DashScope format, e.g. 1248*1632")
    parser.add_argument("--seed", type=int, default=20261102)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--prompt-extend", action=argparse.BooleanOptionalAction, default=True,
                        help="Provider instruction rewriting; enabled by default after the live comparison")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--download-only", action="store_true", help="Reuse response.json; never generate again")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    report, key, owns_report = {}, "", False
    started = time.monotonic()
    try:
        if args.download_only:
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            response = json.loads((output / "response.json").read_text(encoding="utf-8"))
            owns_report = True
        else:
            if not args.dry_run and (output / "request.json").exists():
                raise FileExistsError("Request already exists")
            source, body, report = prepare(args)
            endpoint, key, key_source = credentials(args)
            report.update(endpoint=endpoint, credential_source=key_source, status="prepared")
            if args.dry_run:
                print(json.dumps({k:v for k,v in report.items() if k != "prompt"}, ensure_ascii=False, indent=2))
                return 0
            output.mkdir(parents=True, exist_ok=True)
            # Exclusive marker prevents accidental repeat billing in the same run.
            with (output / "request.json").open("x", encoding="utf-8") as handle:
                json.dump(report, handle, ensure_ascii=False, indent=2)
            owns_report = True
            (output / "source.png").write_bytes(source)
            attribution = ROOT / "Data/MangaPipelineQA/ATTRIBUTION.txt"
            if args.input.resolve().is_relative_to(ROOT / "Data/MangaPipelineQA") and attribution.exists():
                shutil.copyfile(attribution, output / "ATTRIBUTION.txt")
            report["status"] = "request_in_flight"
            write_json(output / "report.json", report)
            print(f"Submitting one image to {args.model}; no automatic retries", flush=True)
            with httpx.Client(timeout=httpx.Timeout(600, connect=30)) as client:
                result = client.post(endpoint, json=body, headers={"Authorization": f"Bearer {key}"})
            report.update(http_status=result.status_code, generation_seconds=round(time.monotonic()-started, 2))
            response = result.json()
            # Provider response is retained locally for download recovery, including its temporary result URL.
            serialized = json.dumps(response, ensure_ascii=False, indent=2).replace(key, "[REDACTED]")
            write_json(output / "response.json", json.loads(serialized))
            report.update(request_id=response.get("request_id"), usage=response.get("usage"))
            if result.is_error or response.get("code"):
                report.update(status="provider_error", error=scrub(f"{response.get('code', '')}: {response.get('message', '')}", key))
                write_json(output / "report.json", report)
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 1
            report["status"] = "generated_pending_download"
            write_json(output / "report.json", report)
        report["artifact"] = download_result(response, output)
        report.update(status="success", last_attempt_seconds=round(time.monotonic()-started, 2))
        comparison_page(output, report)
        write_json(output / "report.json", report)
        print(json.dumps({k:v for k,v in report.items() if k != "prompt"}, ensure_ascii=False, indent=2))
        return 0
    except FileExistsError:
        print("This output directory already has a request. Use --download-only to recover its image, or a new directory for a deliberate new generation.", file=sys.stderr)
        return 2
    except Exception as error:
        message = scrub(f"{type(error).__name__}: {error}", key)
        if owns_report and report:
            report.update(error=message, last_attempt_seconds=round(time.monotonic()-started, 2))
            write_json(output / "report.json", report)
        print(message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
