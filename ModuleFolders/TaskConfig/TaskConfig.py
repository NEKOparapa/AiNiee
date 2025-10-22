import os
import re
import threading
import urllib

import rapidjson as json

from Base.Base import Base
from ModuleFolders.TaskConfig.TaskType import TaskType


# 接口请求器
class TaskConfig(Base):

    # 打印时的类型过滤器
    TYPE_FILTER = (int, str, bool, float, list, dict, tuple)

    def __init__(self) -> None:
        super().__init__()
        
        # 初始化实例级线程锁和密钥索引
        self._config_lock = threading.Lock()

        self._api_key_lock = threading.Lock()
        self.apikey_index = 0
        self.apikey_list = []


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


    def get_next_apikey(self) -> str:
        """
        线程安全的轮询获取 API Key
        """
        with self._api_key_lock:
            if not self.apikey_list:
                return "no_key_required"
            
            # 边界检查
            if self.apikey_index >= len(self.apikey_list):
                self.apikey_index = 0

            key = self.apikey_list[self.apikey_index]

            # 更新索引（如果还有下一个 key，则递增，否则归零）
            if len(self.apikey_list) > 1:
                self.apikey_index = (self.apikey_index + 1) % len(self.apikey_list)

            return key

    # 读取配置文件
    def initialize(self) -> None:
        # 读取配置文件
        config = self.load_config()

        # 将字典中的每一项赋值到类中的同名属性
        for key, value in config.items():
            setattr(self, key, value)

    # 准备翻译
    def prepare_for_translation(self,mode) -> None:

        # 获取目标平台

        if mode == TaskType.TRANSLATION:
            self.target_platform = self.api_settings["translate"]
        elif mode == TaskType.POLISH:
            self.target_platform = self.api_settings["polish"]

        # 增加获取不到内容时的异常处理
        if self.target_platform is None:
            raise ValueError(f"当前配置文件中未设置 {mode} 的目标平台，请重新检查接口管理页面，是否设置了执行任务的接口。")

        # 获取模型类型
        self.model = self.platforms.get(self.target_platform).get("model")

        # 分割密钥字符串
        api_key = self.platforms.get(self.target_platform).get("api_key")
        if api_key == "":
            self.apikey_list = ["no_key_required"]
            self.apikey_index = 0
        else:
            self.apikey_list = re.sub(r"\s+","", api_key).split(",")
            self.apikey_index = 0

        # 获取接口地址并自动补全
        self.base_url = self.platforms.get(self.target_platform).get("api_url")
        auto_complete = self.platforms.get(self.target_platform).get("auto_complete")

        if (self.target_platform == "sakura" or self.target_platform == "LocalLLM") and not self.base_url.endswith("/v1"):
            self.base_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(self.base_url.endswith(suffix) for suffix in version_suffixes):
                self.base_url += "/v1"

        # 获取接口限额
        self.rpm_limit = self.platforms.get(self.target_platform).get("rpm_limit", 4096)    # 当取不到账号类型对应的预设值，则使用该值
        self.tpm_limit = self.platforms.get(self.target_platform).get("tpm_limit", 10000000)    # 当取不到账号类型对应的预设值，则使用该值

        # 根据密钥数量给 RPM 和 TPM 限额翻倍
        self.rpm_limit = self.rpm_limit * len(self.apikey_list)
        self.tpm_limit = self.tpm_limit * len(self.apikey_list)

        # 如果开启自动设置输出文件夹功能，设置为输入文件夹的平级目录
        if self.auto_set_output_path == True:
            abs_input_path = os.path.abspath(self.label_input_path)
            parent_dir = os.path.dirname(abs_input_path)
            output_folder_name = "AiNieeOutput"
            self.label_output_path = os.path.join(parent_dir, output_folder_name)

            # 润色文本输出路径
            abs_input_path = os.path.abspath(self.label_input_path)
            parent_dir = os.path.dirname(abs_input_path)
            output_folder_name = "PolishingOutput"
            self.polishing_output_path = os.path.join(parent_dir, output_folder_name)

        # 保存新配置
        config = self.load_config()
        config["label_output_path"] = self.label_output_path
        config["polishing_output_path"] = self.polishing_output_path
        self.save_config(config)


        # 计算实际线程数
        self.actual_thread_counts = self.thread_counts_setting(self.user_thread_counts,self.target_platform,self.rpm_limit)


    # 自动计算实际请求线程数
    def thread_counts_setting(self,user_thread_counts,target_platform,rpm_limit) -> None:
        # 如果用户指定了线程数，则使用用户指定的线程数
        if user_thread_counts > 0:
            actual_thread_counts = user_thread_counts

        # 如果是本地类接口，尝试访问slots数
        elif target_platform in ("sakura","LocalLLM"):
            num = self.get_llama_cpp_slots_num(self.platforms.get(target_platform).get("api_url"))
            actual_thread_counts = num if num > 0 else 4
            self.info(f"根据 llama.cpp 接口信息，自动设置同时执行的翻译任务数量为 {actual_thread_counts} 个 ...")

        # 如果用户没有指定线程数，则自动计算
        else :
            actual_thread_counts = self.calculate_thread_count(rpm_limit)
            self.info(f"根据账号类型和接口限额，自动设置同时执行的翻译任务数量为 {actual_thread_counts} 个 ...")

        return actual_thread_counts

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
        
    # 线性计算并发线程数
    def calculate_thread_count(self,rpm_limit):

        min_rpm = 1
        max_rpm = 10000
        min_threads = 1
        max_threads = 100

        if rpm_limit <= min_rpm:
            rpm_threads = min_threads
        elif rpm_limit >= max_rpm:
            rpm_threads = max_threads
        else:
            # 线性插值计算 RPM 对应的线程数
            rpm_threads = min_threads + (rpm_limit - min_rpm) * (max_threads - min_threads) / (max_rpm - min_rpm)

        rpm_threads = int(round(rpm_threads)) # 四舍五入取整

        # 确保线程数在 1-100 范围内，并使用 CPU 核心数作为辅助上限 
        # 更简洁的方式是直接限制在 1-100 范围内，因为 100 通常已经足够高
        actual_thread_counts = max(1, min(100, rpm_threads)) # 限制在 1-100

        return actual_thread_counts


    # 获取接口配置信息包
    def get_platform_configuration(self,platform_type):

        if platform_type == "translationReq":
            target_platform = self.api_settings["translate"]
        elif platform_type == "polishingReq":
            target_platform = self.api_settings["polish"]

        api_url = self.base_url
        api_key = self.get_next_apikey()
        api_format = self.platforms.get(target_platform).get("api_format")
        model_name = self.model
        region = self.platforms.get(target_platform).get("region",'')
        access_key = self.platforms.get(target_platform).get("access_key",'')
        secret_key = self.platforms.get(target_platform).get("secret_key",'')
        request_timeout = self.request_timeout
        temperature = self.platforms.get(target_platform).get("temperature")
        top_p = self.platforms.get(target_platform).get("top_p")
        presence_penalty = self.platforms.get(target_platform).get("presence_penalty")
        frequency_penalty = self.platforms.get(target_platform).get("frequency_penalty")
        extra_body = self.platforms.get(target_platform).get("extra_body",{})
        think_switch = self.platforms.get(target_platform).get("think_switch")
        think_depth = self.platforms.get(target_platform).get("think_depth")
        thinking_budget = self.platforms.get(target_platform).get("thinking_budget", -1)

        params = {
            "target_platform": target_platform,
            "api_url": api_url,
            "api_key": api_key,
            "api_format": api_format,
            "model_name": model_name,
            "region": region,
            "access_key": access_key,
            "secret_key": secret_key,
            "request_timeout": request_timeout,
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "extra_body": extra_body,
            "think_switch": think_switch,
            "think_depth": think_depth,
            "thinking_budget": thinking_budget
        }



        return params



