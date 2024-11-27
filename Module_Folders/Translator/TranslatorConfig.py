import os
import re
import urllib

import rapidjson as json

from Base.Base import Base

# 接口请求器
class TranslatorConfig(Base):

    # 打印时的类型过滤器
    TYPE_FILTER = (int, str, bool, float, list, dict, tuple)

    def __init__(self) -> None:
        super().__init__()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}({self.get_vars()})"
        )

    def get_vars(self) -> dict:
        return {
            k:v
            for k, v in vars(self).items()
            if isinstance(v, __class__.TYPE_FILTER)
        }

    # 初始化
    def initialize(self) -> None:
        # 读取配置文件
        config = self.load_config()

        # 将字典中的每一项赋值到类中的同名属性
        for key, value in config.items():
            setattr(self, key, value)

    # 请求线程数
    def request_thread_counts(self) -> None:
        # 如果用户指定了线程数，则使用用户指定的线程数
        if self.user_thread_counts > 0:
            self.actual_thread_counts = self.user_thread_counts
        # 如果用户没有指定线程数，且目标平台不为 Sakura 或 自定义平台，则使用默认值
        elif self.user_thread_counts == 0 and not ("sakura" in self.target_platform or "custom_platform_" in self.target_platform):
            self.actual_thread_counts = 4
        # 如果用户没有指定线程数，且目标平台为 Sakura 或 自定义平台，则尝试自动获取
        else:
            num = self.get_llama_cpp_slots_num(self.platforms.get(self.target_platform).get("api_url"))
            self.actual_thread_counts = num if num > 0 else 4
            self.info(f"根据 llama.cpp 接口信息，自动设置同时执行的翻译任务数量为 {self.actual_thread_counts} 个 ...")

    # 准备翻译
    def prepare_for_translation(self, model = None) -> None:
        # 获取模型类型
        if model:
            self.model = model
        else:
            self.model = self.platforms.get(self.target_platform).get("model")

        # 解析密钥字符串
        # 即使字符中没有逗号，split(",") 方法仍然会返回只包含一个完整字符串的列表
        api_key = self.platforms.get(self.target_platform).get("api_key")
        if api_key == "":
            self.apikey_list = ["no_key_required"]
            self.apikey_index = 0
        else:
            self.apikey_list = re.sub(r"\s+","", api_key).split(",")
            self.apikey_index = 0

        # 获取接口地址并补齐，v3 结尾是火山，v4 结尾是智谱
        api_url = self.platforms.get(self.target_platform).get("api_url")
        auto_complete = self.platforms.get(self.target_platform).get("auto_complete")
        if self.target_platform == "sakura" and not api_url.endswith("/v1"):
            self.base_url = api_url + "/v1"
        elif auto_complete == True and not api_url.endswith("/v1") and not api_url.endswith("/v3") and not api_url.endswith("/v4"):
            self.base_url = api_url + "/v1"
        else:
            self.base_url = api_url

        # 设置网络代理
        if self.proxy_enable == False or self.proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = self.proxy_url
            os.environ["https_proxy"] = self.proxy_url

        # 获取接口限额
        a = self.platforms.get(self.target_platform).get("account")
        m = self.platforms.get(self.target_platform).get("model")

        self.rpm_limit = self.platforms.get(self.target_platform).get("account_datas").get(a, {}).get(m, {}).get("RPM", 0)
        if self.rpm_limit == 0:
            self.rpm_limit = self.platforms.get(self.target_platform).get("rpm_limit", 4096)

        self.tpm_limit = self.platforms.get(self.target_platform).get("account_datas").get(a, {}).get(m, {}).get("TPM", 0)
        if self.tpm_limit == 0:
            self.tpm_limit = self.platforms.get(self.target_platform).get("tpm_limit", 4096000)

        self.max_tokens = self.platforms.get(self.target_platform).get("account_datas").get(a, {}).get(m, {}).get("max_tokens", 0)
        if self.max_tokens == 0:
            self.max_tokens = self.platforms.get(self.target_platform).get("token_limit", 4096)

        # 根据密钥数量给 RPM 和 TPM 限额翻倍
        self.rpm_limit = self.rpm_limit * len(self.apikey_list)
        self.tpm_limit = self.tpm_limit * len(self.apikey_list)

    # 获取 llama.cpp 的 slots 数量，获取失败则返回 -1
    def get_llama_cpp_slots_num(self,url: str) -> int:
        try:
            num = -1
            url = url.replace("/v1", "") if url.endswith("/v1") else url
            with urllib.request.urlopen(f"{url}/slots") as response:
                data = json.loads(response.read().decode("utf-8"))
                num = len(data) if data != None and len(data) > 0 else num
        except Exception:
            pass
        finally:
            return num

