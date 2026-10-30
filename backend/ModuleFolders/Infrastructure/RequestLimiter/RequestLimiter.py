import time
import threading


class RequestLimiter:
    MAX_TOKENS = 600000

    def __init__(self) -> None:
        # 单次请求 token 上限
        self.max_tokens = self.MAX_TOKENS

        # RPM相关参数
        self.last_request_time = 0  # 上次记录时间
        self.request_interval = 0  # 请求的最小时间间隔（s）
        self.lock = threading.Lock()

    # 设置限制器的参数
    def set_limit(self, rpm_limit: int) -> None:
        self.max_tokens = self.MAX_TOKENS
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

    def token_limiter(self, tokens: int) -> bool:
        # 检查是否超过单次请求最大输入限制
        if tokens >= self.max_tokens:
            print("[Warning INFO] 该次任务的文本总tokens量已经超过最大输入限制(60w tokens)，请检查原文文件是否有问题或者文本切分量设置过大！！！")
            print("[Warning INFO] 该次任务将进行拆分处理，并进入下一轮任务中....")
            return False
        return True

    def check_limiter(self, tokens: int) -> bool:
        with self.lock:
            return self.rpm_limiter() and self.token_limiter(tokens)

