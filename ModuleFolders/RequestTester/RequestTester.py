import os
import re
import threading

from Base.Base import Base
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester


# 接口测试器(后面改造成通用请求器，用来承担UI触发的各种额外的请求任务，接口测试可以和流程测试合并)
class RequestTester(Base):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 订阅接口测试开始事件
        self.subscribe(Base.EVENT.API_TEST_START, self.api_test_start)

        # 订阅术语表翻译开始事件
        self.subscribe(Base.EVENT.GLOSS_TRANSLATION_START, self.glossary_translation_start)

    # 响应接口测试开始事件
    def api_test_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.api_test, args = (event, data))
        thread.start()

    # 接口测试
    def api_test(self, event, data: dict):
        # 获取参数
        platform_tag = data.get("tag")
        platform_name = data.get("name")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        proxy_url = data.get("proxy_url")
        proxy_enable = data.get("proxy_enable")
        extra_body = data.get("extra_body",{})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")

        # 自动补全API地址
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"

        # 获取并设置网络代理
        if proxy_enable == False or proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            self.info(f"系统代理已启用，代理地址：{proxy_url}")

        # 测试结果
        failure = []
        success = []

        # 解析并分割密钥字符串
        api_keys = re.sub(r"\s+","", api_key).split(",")

        # 轮询所有密钥进行测试
        for api_key in api_keys:

            # 构建 Prompt
            messages = [
                {
                    "role": "user",
                    "content": "小可爱，你在干嘛"
                }
            ]
            system_prompt = "你接下来要扮演我的女朋友，名字叫欣雨，请你以女朋友的方式回复我。"

            # 打印日志
            self.print("")
            self.info("正在进行接口测试 ...")
            self.info(f"接口名称 - {platform_name}")
            self.info(f"接口地址 - {api_url}")
            self.info(f"接口密钥 - {'*'*(len(api_key)-8)}{api_key[-8:]}") # 隐藏敏感信息
            self.info(f"模型名称 - {model_name}")
            if extra_body:
                self.info(f"额外参数 - {extra_body}")
            self.print(f"系统提示词 - {system_prompt}")
            self.print(f"信息内容 - {messages}")

            # 构建配置包
            platform_config = {
                "target_platform": platform_tag,
                "api_url": api_url,
                "api_key": api_key,
                "api_format": api_format,
                "model_name": model_name,
                "region":  region,
                "access_key":  access_key,
                "secret_key": secret_key,
                "extra_body": extra_body
            }

            #尝试请求
            requester = LLMRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
                messages,
                system_prompt,
                platform_config
            )

            # 测试成功
            if skip == False:
                self.info("接口测试成功 ...")
                self.info(f"接口返回信息 - {response_content}")
                # 储存结果
                success.append(api_key)

            # 测试失败
            else:
                self.error(f"接口测试失败 ... ")
                # 储存结果
                failure.append(api_key)

            self.print("")

        # 打印结果
        self.print("")
        self.info(f"接口测试结果：共测试 {len(api_keys)} 个接口，成功 {len(success)} 个，失败 {len(failure)} 个 ...")
        if len(failure) >0:
            self.error(f"失败的接口密钥 - {", ".join(failure)}")
        self.print("")

        # 发送完成事件
        self.emit(Base.EVENT.API_TEST_DONE, {
            "failure": failure,
            "success": success,
        })


    # 响应术语表翻译开始事件
    def glossary_translation_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.glossary_translation, args = (event, data))
        thread.start()

    # 术语表翻译(按固定行数进行拆分翻译，然后合并结果)
    def glossary_translation(self, event, data: dict):
        # 获取参数
        platform_tag = data.get("tag")
        platform_name = data.get("name")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        proxy_url = data.get("proxy_url")
        proxy_enable = data.get("proxy_enable")
        extra_body = data.get("extra_body",{})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")

        # 自动补全API地址
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"

        # 获取并设置网络代理
        if proxy_enable == False or proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            self.info(f"系统代理已启用，代理地址：{proxy_url}")

        # 测试结果
        failure = []
        success = []

        # 解析并分割密钥字符串
        api_keys = re.sub(r"\s+","", api_key).split(",")

        # 轮询所有密钥进行测试
        for api_key in api_keys:

            # 构建 Prompt
            messages = [
                {
                    "role": "user",
                    "content": "小可爱，你在干嘛"
                }
            ]
            system_prompt = "你接下来要扮演我的女朋友，名字叫欣雨，请你以女朋友的方式回复我。"

            # 打印日志
            self.print("")
            self.info("正在进行接口测试 ...")
            self.info(f"接口名称 - {platform_name}")
            self.info(f"接口地址 - {api_url}")
            self.info(f"接口密钥 - {'*'*(len(api_key)-8)}{api_key[-8:]}") # 隐藏敏感信息
            self.info(f"模型名称 - {model_name}")
            if extra_body:
                self.info(f"额外参数 - {extra_body}")
            self.print(f"系统提示词 - {system_prompt}")
            self.print(f"信息内容 - {messages}")

            # 构建配置包
            platform_config = {
                "target_platform": platform_tag,
                "api_url": api_url,
                "api_key": api_key,
                "api_format": api_format,
                "model_name": model_name,
                "region":  region,
                "access_key":  access_key,
                "secret_key": secret_key,
                "extra_body": extra_body
            }

            #尝试请求
            requester = LLMRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
                messages,
                system_prompt,
                platform_config
            )

            # 测试成功
            if skip == False:
                self.info("接口测试成功 ...")
                self.info(f"接口返回信息 - {response_content}")
                # 储存结果
                success.append(api_key)

            # 测试失败
            else:
                self.error(f"接口测试失败 ... ")
                # 储存结果
                failure.append(api_key)

            self.print("")

        # 打印结果
        self.print("")
        self.info(f"接口测试结果：共测试 {len(api_keys)} 个接口，成功 {len(success)} 个，失败 {len(failure)} 个 ...")
        if len(failure) >0:
            self.error(f"失败的接口密钥 - {", ".join(failure)}")
        self.print("")

        # 发送完成事件
        self.emit(Base.GLOSS_TRANSLATION_DONE, {
            "failure": failure,
            "success": success,
        })
