import os
import re
import threading

import cohere                       # 需要安装库pip install cohere
import anthropic                    # 需要安装库pip install anthropic
import google.generativeai as genai # 需要安装库pip install -U google-generativeai
from openai import OpenAI           # 需要安装库pip install openai

from Base.Base import Base

# 接口测试器
class Request_Tester(Base):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 注册事件
        self.subscribe(Base.EVENT.API_TEST_START, self.api_test_start)

    # 响应接口测试开始事件
    def api_test_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.api_test, args = (event, data))
        thread.start()

    # 接口测试分发
    def api_test(self, event, data: dict):
        # 获取参数
        tag = data.get("tag")
        name = data.get("name")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model = data.get("model")
        auto_complete = data.get("auto_complete")
        proxy_url = data.get("proxy_url")
        proxy_enable = data.get("proxy_enable")

        # 获取接口地址并补齐，v3 结尾是火山，v4 结尾是智谱
        if tag == "sakura" and not api_url.endswith("/v1"):
            api_url = api_url + "/v1"
        elif auto_complete == True and not api_url.endswith("/v1") and not api_url.endswith("/v3") and not api_url.endswith("/v4"):
            api_url = api_url + "/v1"
        else:
            api_url = api_url

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

        # 解析密钥字符串
        # 即使字符中没有逗号，split(",") 方法仍然会返回只包含一个完整字符串的列表
        api_keys = re.sub(r"\s+","", api_key).split(",")

        for api_key in api_keys:
            # 构建 Prompt
            messages = self.generate_messages(tag, api_format)

            # 打印日志
            self.print("")
            self.info("正在进行接口测试 ...")
            self.info(f"接口名称 - {name}")
            self.info(f"接口地址 - {api_url}")
            self.info(f"接口密钥 - {api_key}")
            self.info(f"模型名称 - {model}")
            self.info("测试指令 - ")
            self.print(f"{messages}")

            #尝试请求，并设置各种参数
            try:
                # 获取回复内容
                content = self.request_for_content(tag, api_url, api_key, api_format, model, messages)

                # 打印日志
                self.info("接口测试成功 ...")
                self.info(f"接口返回信息 - {content}")

                # 储存结果
                success.append(api_key)
            except Exception as e:
                # 打印日志
                self.error(f"接口测试失败 ... {e}")

                # 储存结果
                failure.append(api_key)
            finally:
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

    # 根据 tag 生成测试消息
    def generate_messages(self, tag: str, api_format: str):
        messages = []

        if tag == "sakura":
            messages = [
                {
                    "role": "system",
                    "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。",
                },
                {
                    "role": "user",
                    "content": "将下面的日文文本翻译成中文：サポートキャスト",
                },
            ]
        elif tag == "anthropic" or (tag.startswith("custom_platform_") and api_format == "Anthropic"):
            messages = [
                {
                    "role": "user",
                    "content": "小可爱，你在干嘛"
                },
            ]
        else:
            messages = [
                {
                    "role": "system",
                    "content": "你不是AI助手，你是我的女朋友欣雨，接下来你必须以女朋友的方式回复我。",
                },
                {
                    "role": "user",
                    "content": "小可爱，你在干嘛"
                },
            ]

        return messages

    # 请求测试
    def request_for_content(self, tag: str, api_url: str, api_key: str, api_format: str, model: str, messages: list):
        if tag == "cohere":
            client = cohere.Client(
                api_key = api_key if api_key != "" else "no_key_required",
                base_url = api_url
            )

            response = client.chat(
                model = model,
                preamble = "你不是AI助手，你是我的女朋友欣雨，接下来你必须以女朋友的方式回复我。",
                message = "小可爱，你在干嘛",
            )

            return response.text.strip()
        elif tag == "google":
            genai.configure(
                api_key = api_key if api_key != "" else "no_key_required",
                transport = "rest"
            )

            requester = genai.GenerativeModel(
                model_name = model,
                safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                ],
                generation_config = {
                    "temperature": 0,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 2048, # 最大输出，Pro 最大输出是 2048
                },
                system_instruction = "你不是AI助手，你是我的女朋友欣雨，接下来你必须以女朋友的方式回复我。"
            )

            return requester.generate_content("小可爱，你在干嘛").text.strip()
        elif tag == "anthropic" or (tag.startswith("custom_platform_") and api_format == "Anthropic"):
            client = anthropic.Anthropic(
                api_key = api_key if api_key != "" else "no_key_required",
                base_url = api_url,
            )

            response = client.messages.create(
                model = model,
                max_tokens = 2048,
                messages = messages,
                system = "你不是AI助手，你是我的女朋友欣雨，接下来你必须以女朋友的方式回复我。",
            )

            return response.content[0].text.strip()
        else:
            client = OpenAI(
                api_key = api_key if api_key != "" else "no_key_required",
                base_url = api_url,
            )

            response = client.chat.completions.create(
                model = model,
                messages = messages,
            )

            return response.choices[0].message.content.strip()