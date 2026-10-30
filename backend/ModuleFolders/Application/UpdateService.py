"""从旧版本管理页面提取的更新检查，不下载或安装更新。"""

import os
import platform
import re
from collections.abc import Callable

import requests

from ModuleFolders.Application.SystemService import SystemService
from ModuleFolders.Base.Base import Base
from ModuleFolders.Base.EventManager import EventManager
from ModuleFolders.Infrastructure.Platform.PlatformPaths import is_macos, release_api_url


class UpdateCheckError(RuntimeError):
    """更新源不可用或返回了无效的发布数据。"""


class UpdateService:
    def __init__(
        self,
        current_version: str | None = None,
        http_get: Callable | None = None,
    ) -> None:
        version = current_version if current_version is not None else SystemService().get_version()["version"]
        self.current_version = self._release_version(version)
        self._http_get = http_get or requests.get

    @staticmethod
    def _release_version(tag_name: str) -> str:
        match = re.search(r"\d+(?:\.\d+)*", tag_name)
        return match.group(0) if match else "0.0.0"

    @staticmethod
    def _compare_versions(first: str, second: str) -> int:
        # 保留旧比较规则：逐段数值比较，缺失的尾段补零。
        first_parts = [int(part) for part in first.split(".")]
        second_parts = [int(part) for part in second.split(".")]
        width = max(len(first_parts), len(second_parts))
        first_parts += [0] * (width - len(first_parts))
        second_parts += [0] * (width - len(second_parts))
        return (first_parts > second_parts) - (first_parts < second_parts)

    @staticmethod
    def _asset_suffix() -> str:
        if not is_macos():
            return ".zip"
        arch = (os.environ.get("AINIEE_MACOS_ARCH") or platform.machine()).strip().lower()
        arch = {"aarch64": "arm64", "amd64": "x86_64", "x64": "x86_64"}.get(arch, arch)
        return f"-{arch}.dmg"

    def _compatible_release(self, releases: list) -> tuple[dict | None, str]:
        selected = None
        selected_version = self.current_version
        for release in releases:
            if not isinstance(release, dict):
                raise UpdateCheckError("Update source returned an invalid release")
            if release.get("draft") or release.get("prerelease"):
                continue
            version = self._release_version(str(release.get("tag_name", "")))
            if self._compare_versions(version, selected_version) <= 0:
                continue
            assets = release.get("assets", [])
            if not isinstance(assets, list):
                raise UpdateCheckError("Update source returned invalid assets")
            if any(
                isinstance(asset, dict)
                and str(asset.get("name", "")).endswith(self._asset_suffix())
                and isinstance(asset.get("browser_download_url"), str)
                and asset["browser_download_url"]
                for asset in assets
            ):
                selected, selected_version = release, version
        return selected, selected_version

    def _get_response(self, url: str, **kwargs):
        try:
            return self._http_get(url, timeout=10, **kwargs)
        except requests.RequestException as error:
            raise UpdateCheckError("Unable to reach the update source") from error

    @staticmethod
    def _read_json(response):
        if response.status_code != 200:
            raise UpdateCheckError(f"Update source returned HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as error:
            raise UpdateCheckError("Update source returned invalid JSON") from error

    def _result(self, version: str, release_url: str | None, available: bool) -> dict:
        return {
            "current_version": self.current_version,
            "latest_version": version,
            "update_available": available,
            "release_url": release_url,
        }

    def check(self) -> dict:
        try:
            result = self._check()
        except UpdateCheckError:
            EventManager.get_singleton().emit(
                Base.EVENT.APP_UPDATE_CHECK_DONE,
                {"status": "error", "message": "Unable to check for updates"},
            )
            raise
        EventManager.get_singleton().emit(Base.EVENT.APP_UPDATE_CHECK_DONE, dict(result))
        return result

    def _check(self) -> dict:
        api_url = release_api_url()
        response = self._get_response(api_url)
        # 沿用旧版 macOS 更新源尚未发布版本时的行为。
        if response.status_code == 404 and is_macos():
            return self._result(
                self.current_version, "https://github.com/NEKOparapa/AiNiee/releases", False
            )
        latest = self._read_json(response)
        if not isinstance(latest, dict):
            raise UpdateCheckError("Update source returned an invalid latest release")
        release_url = latest.get("html_url")
        if not isinstance(release_url, str):
            release_url = None
        release, version = self._compatible_release([latest])
        if release is not None:
            return self._result(version, release_url, True)

        latest_version = self._release_version(str(latest.get("tag_name", "")))
        if self._compare_versions(latest_version, self.current_version) <= 0:
            return self._result(self.current_version, release_url, False)

        # latest 可能只有其他平台的资产；按旧流程继续查找兼容发布。
        releases_url = api_url.removesuffix("/latest")
        page = 1
        while True:
            response = self._get_response(releases_url, params={"per_page": 100, "page": page})
            releases = self._read_json(response)
            if not isinstance(releases, list):
                raise UpdateCheckError("Update source returned an invalid release list")
            release, version = self._compatible_release(releases)
            if release is not None:
                selected_url = release.get("html_url")
                return self._result(version, selected_url if isinstance(selected_url, str) else None, True)
            if len(releases) < 100:
                return self._result(self.current_version, release_url, False)
            page += 1
