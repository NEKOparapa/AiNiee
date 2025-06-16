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
from ModuleFolders.LLMRequester.DashscopeRequester import DashscopeRequester

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
            sakura_requester = SakuraRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = sakura_requester.request_sakura(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "LocalLLM":
            local_llm_requester = LocalLLMRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = local_llm_requester.request_LocalLLM(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "cohere":
            cohere_requester = CohereRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = cohere_requester.request_cohere(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "google":
            google_requester = GoogleRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = google_requester.request_google(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "anthropic" or (target_platform.startswith("custom_platform_") and api_format == "Anthropic"):
            anthropic_requester = AnthropicRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = anthropic_requester.request_anthropic(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "amazonbedrock":
            amazonbedrock_requester = AmazonbedrockRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = amazonbedrock_requester.request_amazonbedrock(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "dashscope":
            dashscope_requester = DashscopeRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = dashscope_requester.request_openai(
                messages,
                system_prompt,
                platform_config,
            )
        else:
            openai_requester = OpenaiRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = openai_requester.request_openai(
                messages,
                system_prompt,
                platform_config,
            )

        return skip, response_think, response_content, prompt_tokens, completion_tokens

    # 获取当前设置接口的全部配置信息(草稿)
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
        region = platform_config.get("region", "")
        access_key = platform_config.get("access_key", "")
        secret_key = platform_config.get("secret_key", "")
        model_name = platform_config["model"]
        extra_body = platform_config.get("extra_body", {})

        # 处理API密钥（取第一个有效密钥）
        cleaned_keys = re.sub(r"\s+", "", api_keys)
        api_key = cleaned_keys.split(",")[0] if cleaned_keys else ""

        # 自动补全API地址
        auto_complete = platform_config["auto_complete"]
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"

        # 结构化输出请求参数
        self.info("[接口参数]")
        self.print(f"  → 接口地址: {api_url}")
        self.print(f"  → 模型名称: {model_name}")
        self.print(f"  → 额外参数: {extra_body}")
        self.print(f"  → 接口密钥: {'*' * (len(api_key) - 4)}{api_key[-4:]}")  # 隐藏敏感信息

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

        return platform_config
