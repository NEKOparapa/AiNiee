from ModuleFolders.Base.Base import Base
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.LLMRequester.ModelConfigHelper import ModelConfigHelper
from ModuleFolders.Infrastructure.LLMRequester.LLMClientFactory import LLMClientFactory


# 接口请求器
class AmazonbedrockRequester(LogMixin, Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_amazonbedrock(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        model_name = platform_config.get("model_name")
        if "anthropic" in model_name:
            return self.request_amazonbedrock_anthropic(messages, system_prompt, platform_config)
        else:
            return self.request_amazonbedrock_boto3(messages, system_prompt, platform_config)

    # 发起请求
    def request_amazonbedrock_anthropic(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name:str = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)

            # 从工厂获取客户端
            client = LLMClientFactory().get_anthropic_bedrock(platform_config)

            max_tokens = ModelConfigHelper.get_claude_max_output_tokens(model_name)
            think_switch = bool(platform_config.get("think_switch"))
            think_depth = platform_config.get("think_depth") or "medium"

            if (
                messages
                and isinstance(messages[-1], dict)
                and messages[-1].get("role") == "assistant"
            ):
                messages = messages[:-1]

            request_params = {
                "model": model_name,
                "system": system_prompt,
                "messages": messages,
                "timeout": request_timeout,
                "max_tokens": max_tokens,
            }

            if think_switch:
                request_params["thinking"] = {
                    "type": "adaptive",
                    "display": "summarized",
                }
                request_params["output_config"] = {
                    "effort": think_depth
                    if think_depth in {"low", "medium", "high", "xhigh", "max"}
                    else "medium"
                }
            elif not ModelConfigHelper.is_claude_always_thinking_model(model_name):
                request_params["thinking"] = {"type": "disabled"}

            response = client.messages.create(**request_params)

            thinking_parts = []
            content_parts = []
            for block in response.content:
                block_type = getattr(block, "type", "")
                if block_type == "thinking":
                    thinking_text = getattr(block, "thinking", "")
                    if thinking_text:
                        thinking_parts.append(thinking_text)
                elif block_type == "text":
                    content_parts.append(block.text)

            response_think = "".join(thinking_parts)
            response_content = "".join(content_parts)
        except Exception as e:
            if Base.work_status == Base.STATUS.STOPING:
                return True, None, None, None, None
            self.error(f"翻译任务错误 ... {e}", e)
            return True, None, None, None, None

        # 获取指令消耗
        try:
            prompt_tokens = int(response.usage.input_tokens)
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗
        try:
            completion_tokens = int(response.usage.output_tokens)
        except Exception:
            completion_tokens = 0

        return False, response_think, response_content, prompt_tokens, completion_tokens

    # 发起请求
    def request_amazonbedrock_boto3(self, messages, system_prompt, platform_config) -> tuple[bool, str, str, int, int]:
        try:
            model_name = platform_config.get("model_name")
            temperature = platform_config.get("temperature")

            # 从工厂获取客户端
            client = LLMClientFactory().get_boto3_bedrock(platform_config)

            # 使用boto3 converse api 调用,
            # 需要把"context":{"text":"message"} 转换为 "content":["text":"message"]
            # 如果messages最后一个元素是assistant，则需要添加{"role":"user","content":[{"text":"continue"}]}
            new_messages = []
            for message in messages:
                new_messages.append({"role": message["role"], "content": [{"text": message["content"]}]})
            if messages[-1]["role"] == "assistant":
                new_messages.append({"role": "user", "content": [{"text": "continue"}]})
            is_nova_2 = "amazon.nova-2" in model_name.lower()
            inference_config = {
                "maxTokens": 65536 if is_nova_2 else 4096,
            }
            if temperature is not None:
                inference_config["temperature"] = temperature

            request_params = {
                "modelId": model_name,
                "messages": new_messages,
                "inferenceConfig": inference_config,
            }
            if system_prompt:
                request_params["system"] = [{"text": system_prompt}]

            if is_nova_2:
                think_switch = bool(platform_config.get("think_switch"))
                think_depth = platform_config.get("think_depth") or "medium"
                nova_effort = think_depth if think_depth in {"low", "medium", "high"} else "high"
                reasoning_config = {"type": "enabled" if think_switch else "disabled"}
                if think_switch:
                    reasoning_config["maxReasoningEffort"] = nova_effort
                request_params["additionalModelRequestFields"] = {
                    "reasoningConfig": reasoning_config
                }

            response = client.converse(**request_params)

            thinking_parts = []
            content_parts = []
            for block in response["output"]["message"]["content"]:
                if "text" in block:
                    content_parts.append(block["text"])
                reasoning_content = block.get("reasoningContent")
                if isinstance(reasoning_content, dict):
                    reasoning_text = reasoning_content.get("reasoningText", {})
                    if isinstance(reasoning_text, dict) and reasoning_text.get("text"):
                        thinking_parts.append(reasoning_text["text"])

            response_think = "".join(thinking_parts)
            response_content = "".join(content_parts)
        except Exception as e:
            if Base.work_status == Base.STATUS.STOPING:
                return True, None, None, None, None
            self.error(f"请求任务错误 ... {e}", e)
            return True, None, None, None, None

        # 获取指令消耗
        try:
            prompt_tokens = int(response["usage"]["inputTokens"])
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗
        try:
            completion_tokens = int(response["usage"]["outputTokens"])
        except Exception:
            completion_tokens = 0

        return False, response_think, response_content, prompt_tokens, completion_tokens
