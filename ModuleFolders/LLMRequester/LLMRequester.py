import os
import re

from Base.Base import Base

from ModuleFolders.LLMRequester.SakuraRequester import SakuraRequester
from ModuleFolders.LLMRequester.LocalLLMRequester import LocalLLMRequester
from ModuleFolders.LLMRequester.CohereRequester import CohereRequester
from ModuleFolders.LLMRequester.GoogleRequester import GoogleRequester
from ModuleFolders.LLMRequester.AnthropicRequester import AnthropicRequester
from ModuleFolders.LLMRequester.AmazonbedrockRequester import AmazonbedrockRequester
from ModuleFolders.LLMRequester.OpenaiRequester import OpenaiRequester


# 接口请求器
class LLMRequester(Base):
    def __init__(self) -> None:
        super().__init__()
        pass

    # 分发请求
    def sent_request(self, messages: list[dict], system_prompt: str, platform_config: dict) -> tuple[bool, str, str, int, int]:
        # 获取平台参数
        target_platform = platform_config.get("target_platform")
        api_format = platform_config.get("api_format")

        # 发起请求
        if target_platform == "sakura":
            skip, response_think, response_content, prompt_tokens, completion_tokens = SakuraRequester.request_sakura(
                self,
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "LocalLLM":
            skip, response_think, response_content, prompt_tokens, completion_tokens = LocalLLMRequester.request_LocalLLM(
                self,
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "cohere":
            skip, response_think, response_content, prompt_tokens, completion_tokens = CohereRequester.request_cohere(
                self,
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "google":
            skip, response_think, response_content, prompt_tokens, completion_tokens = GoogleRequester.request_google(
                self,
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
            skip, response_think, response_content, prompt_tokens, completion_tokens = AnthropicRequester.request_anthropic(
                self,
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "amazonbedrock":
            skip, response_think, response_content, prompt_tokens, completion_tokens = AmazonbedrockRequester.request_amazonbedrock(
                self,
                messages,
                system_prompt,
                platform_config,
            )
        else:
            skip, response_think, response_content, prompt_tokens, completion_tokens = OpenaiRequester.request_openai(
                self,
                messages,
                system_prompt,
                platform_config,
            )

        return skip, response_think, response_content, prompt_tokens, completion_tokens

    # 获取当前设定接口的全部配置信息
    def get_platform_config(self, platform):
        """获取指定平台的配置信息"""
        # 读取配置文件
        user_config = self.load_config()

        # 获取平台配置标识
        platform_tag = user_config.get(f"request_{platform}_platform_settings")

        # 读取平台基础配置
        platform_config = user_config["platforms"][platform_tag]
        api_url = platform_config["api_url"]
        api_keys = platform_config["api_key"]
        api_format = platform_config["api_format"]
        model_name = platform_config["model"]
        auto_complete = platform_config["auto_complete"]
        extra_body = platform_config.get("extra_body", {})

        # 处理API密钥（取第一个有效密钥）
        cleaned_keys = re.sub(r"\s+", "", api_keys)
        api_key = cleaned_keys.split(",")[0] if cleaned_keys else ""

        # 自动补全API地址
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"

        # 网络代理设置
        proxy_url = user_config.get("proxy_url")
        proxy_enable = user_config.get("proxy_enable")

        # 获取并设置网络代理
        if proxy_enable == False or proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            self.info(f"[系统代理]  {proxy_url}")

        return api_key, api_url, model_name, api_format, extra_body
