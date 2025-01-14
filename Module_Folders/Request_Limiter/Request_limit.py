import time
import threading
import tiktoken  # 需要安装库pip install tiktoken
import tiktoken_ext  # 必须导入这两个库，否则打包后无法运行
from tiktoken_ext import openai_public


class Request_Limiter:

    def __init__(self) -> None:
        # TPM相关参数
        self.max_tokens = 0  # 令牌桶最大容量
        self.remaining_tokens = 0  # 令牌桶剩余容量
        self.tokens_rate = 0  # 令牌每秒的恢复速率
        self.last_time = time.time()  # 上次记录时间

        # RPM相关参数
        self.last_request_time = 0  # 上次记录时间
        self.request_interval = 0  # 请求的最小时间间隔（s）
        self.lock = threading.Lock()

    # 设置限制器的参数
    def set_limit(self, max_tokens: int, tpm_limit: int, rpm_limit: int) -> None:
        # 设置限制器的TPM参数
        self.max_tokens = max_tokens  # 令牌桶最大容量
        self.tokens_rate = tpm_limit / 60  # 令牌每秒的恢复速率
        self.remaining_tokens = max_tokens  # 令牌桶剩余容量

        # 设置限制器的RPM参数
        self.request_interval = 60 / rpm_limit  # 请求的最小时间间隔（s）

    def rpm_limiter(self) -> bool:
        current_time = time.time()  # 获取现在的时间
        time_since_last_request = current_time - self.last_request_time  # 计算当前时间与上次记录时间的间隔
        if time_since_last_request < self.request_interval:
            # print("[DEBUG] Request limit exceeded. Please try again later.")
            return False
        else:
            self.last_request_time = current_time
            return True

    def tpm_limiter(self, tokens: int) -> bool:
        now = time.time()  # 获取现在的时间
        tokens_to_add = (now - self.last_time) * self.tokens_rate  # 现在时间减去上一次记录的时间，乘以恢复速率，得出这段时间恢复的tokens数量
        self.remaining_tokens = min(self.max_tokens, self.remaining_tokens + tokens_to_add)  # 计算新的剩余容量，与最大容量比较，谁小取谁值，避免发送信息超过最大容量
        self.last_time = now  # 改变上次记录时间

        # 检查是否超过模型最大输入限制
        if tokens >= self.max_tokens:
            print("[Warning INFO] 该次任务总tokens量已经超过模型最大输入限制，将进入下次拆分轮次")
            return False
        
        # 检查是否超过余量
        elif tokens >= self.remaining_tokens:
            return False
        
        else:
            # print("[DEBUG] 数量足够，剩余tokens：", tokens,'\n' )
            return True

    def check_limiter(self, tokens: int) -> bool:
        # 如果能够发送请求，则扣除令牌桶里的令牌数
        with self.lock:
            if self.rpm_limiter() and self.tpm_limiter(tokens):
                self.remaining_tokens = self.remaining_tokens - tokens
                return True
            else:
                return False

    # 计算消息列表内容的tokens的函数
    def num_tokens_from_messages(self, messages) -> int:
        """Return the number of tokens used by a list of messages."""
        try:
            encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except KeyError:
            print("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")

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