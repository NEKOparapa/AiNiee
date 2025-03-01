import os
import re
import threading
import urllib
import copy

import rapidjson as json

from Base.Base import Base

# 接口请求器
class TranslatorConfig(Base):

    # 打印时的类型过滤器
    TYPE_FILTER = (int, str, bool, float, list, dict, tuple)

    def __init__(self) -> None:
        super().__init__()
        
        # 初始化实例级线程锁和密钥索引
        self._config_lock = threading.Lock()

        self._api_key_lock = threading.Lock()
        self.apikey_index = 0
        self.apikey_list = []
        self.apikey_index_a = 0
        self.apikey_list_a = []
        self.apikey_index_b = 0
        self.apikey_list_b = []

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

    def get_next_apikey_a(self) -> str:
        """
        线程安全的轮询获取 API Key
        """
        with self._api_key_lock:
            if not self.apikey_list_a:
                return "no_key_required"
            
            # 边界检查
            if self.apikey_index_a >= len(self.apikey_list_a):
                self.apikey_index_a = 0

            key = self.apikey_list_a[self.apikey_index_a]

            # 更新索引（如果还有下一个 key，则递增，否则归零）
            if len(self.apikey_list_a) > 1:
                self.apikey_index_a = (self.apikey_index_a + 1) % len(self.apikey_list_a)

            return key

    def get_next_apikey_b(self) -> str:
        """
        线程安全的轮询获取 API Key
        """
        with self._api_key_lock:
            if not self.apikey_list_b:
                return "no_key_required"
            
            # 边界检查
            if self.apikey_index_b >= len(self.apikey_list_b):
                self.apikey_index_b = 0

            key = self.apikey_list_b[self.apikey_index_b]

            # 更新索引（如果还有下一个 key，则递增，否则归零）
            if len(self.apikey_list_b) > 1:
                self.apikey_index_b = (self.apikey_index_b + 1) % len(self.apikey_list_b)

            return key

    # 读取配置文件
    def initialize(self) -> None:
        # 读取配置文件
        config = self.load_config()

        # 将字典中的每一项赋值到类中的同名属性
        for key, value in config.items():
            setattr(self, key, value)

    # 请求线程数
    def thread_counts_setting(self) -> None:
        # 如果用户指定了线程数，则使用用户指定的线程数
        if self.user_thread_counts > 0:
            self.actual_thread_counts = self.user_thread_counts
        # 如果用户没有指定线程数，且目标平台不为 Sakura,本地小模型 或 自定义平台，则使用默认值
        elif self.user_thread_counts == 0 and not ("sakura" in self.target_platform or "LocalLLM" in self.target_platform  or "custom_platform_" in self.target_platform):
            self.actual_thread_counts = 8
        # 如果用户没有指定线程数，且目标平台为 Sakura 或 自定义平台，则尝试自动获取
        else:
            num = self.get_llama_cpp_slots_num(self.platforms.get(self.target_platform).get("api_url"))
            self.actual_thread_counts = num if num > 0 else 4
            self.info(f"根据 llama.cpp 接口信息，自动设置同时执行的翻译任务数量为 {self.actual_thread_counts} 个 ...")

    # 准备翻译
    def prepare_for_translation(self) -> None:

        if self.double_request_switch_settings == False:
            # 获取目标平台
            target_platform = self.target_platform

            # 获取模型类型
            self.model = self.platforms.get(target_platform).get("model")

            # 解析密钥字符串
            # 即使字符中没有逗号，split(",") 方法仍然会返回只包含一个完整字符串的列表
            api_key = self.platforms.get(target_platform).get("api_key")
            if api_key == "":
                self.apikey_list = ["no_key_required"]
                self.apikey_index = 0
            else:
                self.apikey_list = re.sub(r"\s+","", api_key).split(",")
                self.apikey_index = 0

            # 获取接口地址并补齐
            api_url = self.platforms.get(target_platform).get("api_url")
            auto_complete = self.platforms.get(target_platform).get("auto_complete")
            if target_platform == "sakura" and not api_url.endswith("/v1"):
                self.base_url = api_url + "/v1"
            elif auto_complete == True and not api_url.endswith("/v1") and not api_url.endswith("/v2") and not api_url.endswith("/v3") and not api_url.endswith("/v4"):
                self.base_url = api_url + "/v1"
            else:
                self.base_url = api_url



            # 获取接口限额
            a = self.platforms.get(target_platform).get("account")
            m = self.platforms.get(target_platform).get("model")

            self.rpm_limit = self.platforms.get(target_platform).get("account_datas").get(a, {}).get(m, {}).get("RPM", 0)
            if self.rpm_limit == 0:
                self.rpm_limit = self.platforms.get(target_platform).get("rpm_limit", 4096)    # 当取不到账号类型对应的预设值，则使用该值

            self.tpm_limit = self.platforms.get(target_platform).get("account_datas").get(a, {}).get(m, {}).get("TPM", 0)
            if self.tpm_limit == 0:
                self.tpm_limit = self.platforms.get(target_platform).get("tpm_limit", 10000000)    # 当取不到账号类型对应的预设值，则使用该值


            # 根据密钥数量给 RPM 和 TPM 限额翻倍
            self.rpm_limit = self.rpm_limit * len(self.apikey_list)
            self.tpm_limit = self.tpm_limit * len(self.apikey_list)


        else:
            target_platform_a = self.request_a_platform_settings

            # 获取模型类型
            self.model_a = self.platforms.get(target_platform_a).get("model")

            # 解析密钥字符串
            # 即使字符中没有逗号，split(",") 方法仍然会返回只包含一个完整字符串的列表
            api_key_a = self.platforms.get(target_platform_a).get("api_key")
            if api_key_a == "":
                self.apikey_list_a = ["no_key_required"]
                self.apikey_index_a = 0
            else:
                self.apikey_list_a = re.sub(r"\s+","", api_key_a).split(",")
                self.apikey_index_a = 0

            # 获取接口地址并补齐
            api_url_a = self.platforms.get(target_platform_a).get("api_url")
            auto_complete_a = self.platforms.get(target_platform_a).get("auto_complete")
            if target_platform_a == "sakura" and not api_url_a.endswith("/v1"):
                self.base_url_a = api_url_a + "/v1"
            elif auto_complete_a == True and not api_url_a.endswith("/v1") and not api_url_a.endswith("/v2") and not api_url_a.endswith("/v3") and not api_url_a.endswith("/v4"):
                self.base_url_a = api_url_a + "/v1"
            else:
                self.base_url_a = api_url_a



            # 获取接口限额
            a = self.platforms.get(target_platform_a).get("account")
            m = self.platforms.get(target_platform_a).get("model")

            self.rpm_limit_a = self.platforms.get(target_platform_a).get("account_datas").get(a, {}).get(m, {}).get("RPM", 0)
            if self.rpm_limit_a == 0:
                self.rpm_limit_a= self.platforms.get(target_platform_a).get("rpm_limit", 4096)    # 当取不到账号类型对应的预设值，则使用该值

            self.tpm_limit_a = self.platforms.get(target_platform_a).get("account_datas").get(a, {}).get(m, {}).get("TPM", 0)
            if self.tpm_limit_a == 0:
                self.tpm_limit_a = self.platforms.get(target_platform_a).get("tpm_limit", 10000000)    # 当取不到账号类型对应的预设值，则使用该值


            # 根据密钥数量给 RPM 和 TPM 限额翻倍
            self.rpm_limit_a = self.rpm_limit_a * len(self.apikey_list_a)
            self.tpm_limit_a = self.tpm_limit_a * len(self.apikey_list_a)




            target_platform_b = self.request_b_platform_settings

            # 获取模型类型
            self.model_b = self.platforms.get(target_platform_b).get("model")

            # 解析密钥字符串
            # 即使字符中没有逗号，split(",") 方法仍然会返回只包含一个完整字符串的列表
            api_key_b = self.platforms.get(target_platform_b).get("api_key")
            if api_key_b == "":
                self.apikey_list_b = ["no_key_required"]
                self.apikey_index_b = 0
            else:
                self.apikey_list_b = re.sub(r"\s+","", api_key_b).split(",")
                self.apikey_index_b = 0

            # 获取接口地址并补齐
            api_url_b = self.platforms.get(target_platform_b).get("api_url")
            auto_complete_b = self.platforms.get(target_platform_b).get("auto_complete")
            if target_platform_b == "sakura" and not api_url_b.endswith("/v1"):
                self.base_url_b = api_url_b + "/v1"
            elif auto_complete_b == True and not api_url_b.endswith("/v1") and not api_url_b.endswith("/v2") and not api_url_b.endswith("/v3") and not api_url_b.endswith("/v4"):
                self.base_url_b = api_url_b + "/v1"
            else:
                self.base_url_b = api_url_b



            # 获取接口限额
            a = self.platforms.get(target_platform_b).get("account")
            m = self.platforms.get(target_platform_b).get("model")

            self.rpm_limit_b = self.platforms.get(target_platform_b).get("account_datas").get(a, {}).get(m, {}).get("RPM", 0)
            if self.rpm_limit_b == 0:
                self.rpm_limit_b= self.platforms.get(target_platform_b).get("rpm_limit", 4096)    # 当取不到账号类型对应的预设值，则使用该值

            self.tpm_limit_b = self.platforms.get(target_platform_b).get("account_datas").get(a, {}).get(m, {}).get("TPM", 0)
            if self.tpm_limit_b == 0:
                self.tpm_limit_b = self.platforms.get(target_platform_b).get("tpm_limit", 10000000)    # 当取不到账号类型对应的预设值，则使用该值


            # 根据密钥数量给 RPM 和 TPM 限额翻倍
            self.rpm_limit_b = self.rpm_limit_b * len(self.apikey_list_b)
            self.tpm_limit_b = self.tpm_limit_b * len(self.apikey_list_b)



            # 取两者最低速
            self.rpm_limit = min(self.rpm_limit_a,self.rpm_limit_b)
            self.tpm_limit = min(self.tpm_limit_a,self.tpm_limit_b)






        # 设置网络代理(共用设置)
        if self.proxy_enable == False or self.proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = self.proxy_url
            os.environ["https_proxy"] = self.proxy_url


    def update_glossary_ntl_config(self, glossary_entries, ntl_entries):
        
        # 检测一下是不是空，免得浪费性能
        if (not glossary_entries) and (not ntl_entries):
            return ""

        with self._config_lock:
            # 更新术语表
            self.prompt_dictionary_data = self.update_glossary_2_dict(self.prompt_dictionary_data, glossary_entries)

            # 更新禁翻表
            self.exclusion_list_data = self.update_ntl_2_dict(self.exclusion_list_data,  ntl_entries)

            # 保存新配置
            config = self.load_config()

            config["prompt_dictionary_data"] = self.prompt_dictionary_data
            config["exclusion_list_data"] = self.exclusion_list_data

            self.save_config(config)


    def update_glossary_2_dict(self,original_data, glossary_entries):
        """
        将术语表内容合并到现有数据列表中
        
        参数：
            original_data (list): 原始数据列表，元素为包含src/dst/info的字典
            glossary_entries (list): 需要合并的术语表，元素为(原文,译文,备注)元组
            
        返回：
            list: 合并后的新列表数据（深拷贝）
        """
        # 深拷贝原始数据避免修改原对象
        new_data = copy.deepcopy(original_data)
        
        # 空值快速返回
        if not glossary_entries:
            return new_data
        
        # 构建源词存在集合
        existing_src = {item["src"] for item in new_data}
        
        # 转换术语表为字典格式
        for entry in glossary_entries:
            # 跳过格式不规范的条目
            if len(entry) < 2:
                continue
            
            src = entry[0].strip()
            dst = entry[1].strip()
            info = entry[2].strip() if len(entry) > 2 and entry[2] else ""
            
            # 重复检查
            if src not in existing_src:
                new_data.append({
                    "src": src,
                    "dst": dst,
                    "info": info
                })
                existing_src.add(src)  # 更新存在集合
        
        return new_data

    def update_ntl_2_dict(self,original_data, ntl_entries):

        # 深拷贝原始数据避免修改原对象
        new_data = copy.deepcopy(original_data)
        
        # 空值快速返回
        if not ntl_entries:
            return new_data
        
        # 构建源词存在集合
        existing_src = {item["markers"] for item in new_data}
        
        # 转换术语表为字典格式
        for entry in ntl_entries:
            # 跳过格式不规范的条目
            if len(entry) < 1:
                continue
            
            src = entry[0].strip()
            info = entry[1].strip() if len(entry) > 1 and entry[1] else ""
            
            # 重复检查
            if src not in existing_src:
                new_data.append({
                    "markers": src,
                    "info": info,
                    "regex": ""
                })
                existing_src.add(src)  # 更新存在集合
        
        return new_data

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
        
    # 获取配置信息包
    def get_platform_configuration(self,platform_type):

        if platform_type == "singleReq":
            target_platform = self.target_platform
            api_url = self.base_url
            api_key = self.get_next_apikey()
            api_format = self.platforms.get(target_platform).get("api_format")
            model_name = self.model
            request_timeout = self.request_timeout
            temperature = self.platforms.get(target_platform).get("temperature")
            top_p = self.platforms.get(target_platform).get("top_p")
            presence_penalty = self.platforms.get(target_platform).get("presence_penalty")
            frequency_penalty = self.platforms.get(target_platform).get("frequency_penalty")

        elif platform_type == "doubleReqA":
            target_platform = self.request_a_platform_settings
            api_url = self.base_url_a
            api_key = self.get_next_apikey_a()
            api_format = self.platforms.get(target_platform).get("api_format")
            model_name = self.model_a
            request_timeout = self.request_timeout
            temperature = self.platforms.get(target_platform).get("temperature")
            top_p = self.platforms.get(target_platform).get("top_p")
            presence_penalty = self.platforms.get(target_platform).get("presence_penalty")
            frequency_penalty = self.platforms.get(target_platform).get("frequency_penalty")

        elif platform_type == "doubleReqB":
            target_platform = self.request_b_platform_settings
            api_url = self.base_url_b
            api_key = self.get_next_apikey_b()
            api_format = self.platforms.get(target_platform).get("api_format")
            model_name = self.model_b
            request_timeout = self.request_timeout
            temperature = self.platforms.get(target_platform).get("temperature")
            top_p = self.platforms.get(target_platform).get("top_p")
            presence_penalty = self.platforms.get(target_platform).get("presence_penalty")
            frequency_penalty = self.platforms.get(target_platform).get("frequency_penalty")


        params = {
            "target_platform": target_platform,
            "api_url": api_url,
            "api_key": api_key,
            "api_format": api_format,
            "model_name": model_name,
            "request_timeout": request_timeout,
            "temperature": temperature,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty
        }



        return params
