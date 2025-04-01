import os
import threading

import httpx

from base.Base import Base

class VersionManager(Base):

    class Status():

        NONE: str = "NONE"
        NEW_VERSION: str = "NEW_VERSION"
        UPDATING: str = "UPDATING"
        DOWNLOADED: str = "DOWNLOADED"

    # 版本号
    VERSION: str = "v0.0.0"

    # 更新状态
    STATUS: str = Status.NONE

    # 更新时的临时文件
    UPDATE_TEMP_PATH: str = "./resource/update.temp"

    def __init__(self, version: str) -> None:
        super().__init__()

        # 注册事件
        self.subscribe(Base.Event.APP_UPDATE_CHECK, self.app_update_check)
        self.subscribe(Base.Event.APP_UPDATE_DOWNLOAD, self.app_update_download)

        # 初始化
        VersionManager.VERSION = version

    # 检查更新事件
    def app_update_check(self, event: int, data: dict) -> None:
        thread = threading.Thread(target = self.app_update_check_task, args = (event, data))
        thread.start()

    # 下载更新事件
    def app_update_download(self, event: int, data: dict) -> None:
        thread = threading.Thread(target = self.app_update_download_task, args = (event, data))
        thread.start()

    # 检查更新开始
    def app_update_check_task(self, event: int, data: dict) -> None:
        try:
            # 获取更新信息
            response = httpx.get("https://api.github.com/repos/NEKOparapa/AiNiee/releases/latest", timeout = 60)
            response.raise_for_status()

            # 发送完成事件
            self.emit(Base.Event.APP_UPDATE_CHECK_DONE, {
                "result": response.json()
            })
        except Exception as e:
            pass

    # 检查更新开始
    def app_update_download_task(self, event: int, data: dict) -> None:
        try:
            # 获取更新信息
            response = httpx.get("https://api.github.com/repos/NEKOparapa/AiNiee/releases/latest", timeout = 60)
            response.raise_for_status()

            # 开始下载
            browser_download_url = response.json().get("assets", [])[0].get("browser_download_url", "")
            with httpx.stream("GET", browser_download_url, timeout = 60, follow_redirects = True) as response:
                response.raise_for_status()

                # 获取文件总大小
                total_size: int = int(response.headers.get("Content-Length", 0))
                downloaded_size: int = 0

                # 有效性检查
                if total_size == 0:
                    raise Exception("Content-Length is 0 ...")

                # 写入文件并更新进度
                os.remove(VersionManager.UPDATE_TEMP_PATH) if os.path.isfile(VersionManager.UPDATE_TEMP_PATH) else None
                os.makedirs(os.path.dirname(VersionManager.UPDATE_TEMP_PATH), exist_ok = True)
                with open(VersionManager.UPDATE_TEMP_PATH, "wb") as writer:
                    for chunk in response.iter_bytes(chunk_size = 1024 * 1024):
                        if chunk is not None:
                            writer.write(chunk)
                            downloaded_size = downloaded_size + len(chunk)

                            self.emit(Base.Event.APP_UPDATE_DOWNLOAD_UPDATE, {
                                "error": None,
                                "total_size": total_size,
                                "downloaded_size": downloaded_size,
                            })
        except Exception as e:
            self.emit(Base.Event.APP_UPDATE_DOWNLOAD_UPDATE, {
                "error": e,
                "total_size": 0,
                "downloaded_size": 0,
            })