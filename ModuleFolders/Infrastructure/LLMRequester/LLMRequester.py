from ModuleFolders.Infrastructure.LLMRequester.SakuraRequester import SakuraRequester
from ModuleFolders.Infrastructure.LLMRequester.LocalLLMRequester import LocalLLMRequester
from ModuleFolders.Infrastructure.LLMRequester.CohereRequester import CohereRequester
from ModuleFolders.Infrastructure.LLMRequester.GoogleRequester import GoogleRequester
from ModuleFolders.Infrastructure.LLMRequester.AnthropicRequester import AnthropicRequester
from ModuleFolders.Infrastructure.LLMRequester.AmazonbedrockRequester import AmazonbedrockRequester
from ModuleFolders.Infrastructure.LLMRequester.OpenaiRequester import OpenaiRequester
from ModuleFolders.Infrastructure.LLMRequester.DashscopeRequester import DashscopeRequester

# 接口请求器
class LLMRequester():
    def __init__(self) -> None:
        pass

    # 分发请求
    def sent_request(self, messages: list[dict], system_prompt: str, platform_config: dict) -> tuple[bool, str, str, int, int]:
        # 获取平台参数
        target_platform = platform_config.get("target_platform")
        api_format = platform_config.get("api_format")

        # 发起请求（sakura/LocalLLM 用 startswith，兼容新增平台 key 如 sakura_123456、LocalLLM_456789）
        if target_platform.startswith("sakura"):
            sakura_requester = SakuraRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = sakura_requester.request_sakura(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform.startswith("LocalLLM"):
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
        elif target_platform == "google" or (
            (target_platform.startswith("custom_platform_") or target_platform.startswith("custom_"))
            and api_format == "Google"
        ):
            google_requester = GoogleRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = google_requester.request_google(
                messages,
                system_prompt,
                platform_config,
            )
        elif target_platform == "anthropic" or (
            (target_platform.startswith("custom_platform_") or target_platform.startswith("custom_"))
            and api_format == "Anthropic"
        ):
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
