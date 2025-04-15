import anthropic                        # pip install anthropic
import boto3 

from Base.Base import Base

# 接口请求器
class AmazonbedrockRequester(Base):
    def __init__(self) -> None:
        pass

    # 发起请求
    def request_amazonbedrock(self, messages, system_prompt,platform_config) -> tuple[bool, str, str, int, int]:
        model_name = platform_config.get("model_name")
        if "anthropic" in model_name:
            return self.request_amazonbedrock_anthropic(messages, system_prompt,platform_config)
        else:
            return self.request_amazonbedrock_boto3(messages, system_prompt,platform_config)

    # 发起请求
    def request_amazonbedrock_anthropic(self, messages, system_prompt,platform_config) -> tuple[bool, str, str, int, int]:
        try:
            
            region = platform_config.get("region")
            access_key = platform_config.get("access_key")
            secret_key = platform_config.get("secret_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout", 60)
            temperature = platform_config.get("temperature", 1.0)
            top_p = platform_config.get("top_p", 1.0)


            client = anthropic.AnthropicBedrock(
                aws_region = region,
                aws_access_key = access_key,
                aws_secret_key = secret_key,
            )
            
            response = client.messages.create(
                model = model_name,
                system = system_prompt,
                messages = messages,
                temperature = temperature,
                top_p = top_p,
                timeout = request_timeout,
                max_tokens = 4096,
            )

            # 提取回复的文本内容
            response_content = response.content[0].text
        except Exception as e:
            self.error(f"翻译任务错误 ... {e}", e if self.is_debug() else None)
            return True, None, None, None, None

        # 获取指令消耗
        try:
            prompt_tokens = int(response.usage.prompt_tokens)
        except Exception:
            prompt_tokens = 0

        # 获取回复消耗
        try:
            completion_tokens = int(response.usage.completion_tokens)
        except Exception:
            completion_tokens = 0

        return False, "", response_content, prompt_tokens, completion_tokens
    
    # 发起请求
    def request_amazonbedrock_boto3(self, messages, system_prompt,platform_config) -> tuple[bool, str, str, int, int]:
        try:
            region = platform_config.get("region")
            access_key = platform_config.get("access_key")
            secret_key = platform_config.get("secret_key")
            model_name = platform_config.get("model_name")
            request_timeout = platform_config.get("request_timeout")
            temperature = platform_config.get("temperature")
            top_p = platform_config.get("top_p")

            client = boto3.client("bedrock-runtime",
                                  region_name=region,
                                  aws_access_key_id=access_key,
                                  aws_secret_access_key=secret_key)

            # 使用boto3 converse api 调用,
            # 需要把"context":{"text":"message"} 转换为 "content":["text":"message"]
            # 如果messages最后一个元素是assistant，则需要添加{"role":"user","content":[{"text":"continue"}]}
            new_messages = []
            for message in messages:
                new_messages.append({"role":message["role"],"content":[{"text":message["content"]}]})
            if messages[-1]["role"] == "assistant":
                new_messages.append({"role":"user","content":[{"text":"continue"}]})
            response = client.converse(
                modelId=model_name,
                system=[{"text":system_prompt}],
                messages=new_messages,
                inferenceConfig={"maxTokens": 4096, "temperature": temperature, "topP": top_p},
            )
            

            # 提取回复的文本内容
            response_content = response["output"]["message"]["content"][0]["text"]
        except Exception as e:
            self.error(f"请求任务错误 ... {e}", e if self.is_debug() else None)
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

        return False, "", response_content, prompt_tokens, completion_tokens
    