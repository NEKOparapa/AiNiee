import tiktoken  # 需要安装库pip install tiktoken
import tiktoken_ext  # 必须导入这两个库，否则打包后无法运行
from tiktoken_ext import openai_public


class Tokener:

    def __init__(self) -> None:
        pass

    # 计算消息列表内容的tokens的函数
    def num_tokens_from_messages(self, messages) -> int:
        """Return the number of tokens used by a list of messages."""
        encoding = tiktoken.get_encoding("o200k_base")

        tokens_per_message = 3
        tokens_per_name = 1
        num_tokens = 0
        for message in messages:
            num_tokens += tokens_per_message
            for key, value in message.items():
                # 如果value是字符串类型才计算tokens，否则跳过，因为AI在调用函数时，会在content中回复null，导致报错
                if isinstance(value, str):
                    num_tokens += len(encoding.encode(value))
                if key == "name":
                    num_tokens += tokens_per_name
        num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
        return num_tokens


    # 计算字符串内容的tokens的函数
    def num_tokens_from_str(self, text) -> int:
        """Return the number of tokens used by a list of messages."""
        encoding = tiktoken.get_encoding("o200k_base")

        if isinstance(text, str):
            num_tokens = len(encoding.encode(text))
        else:
            num_tokens = 0

        return num_tokens

    def calculate_tokens(self, message1, text1,):
        """
        根据输入的消息和文本，计算tokens消耗并返回。

        """
        if message1 and text1:
            tokens1 = Tokener.num_tokens_from_messages(self,message1)
            tokens_text1 = Tokener.num_tokens_from_str(self,text1)
            return tokens1 + tokens_text1
