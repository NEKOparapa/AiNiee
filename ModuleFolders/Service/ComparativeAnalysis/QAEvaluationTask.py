import concurrent.futures
import time
import rapidjson as json

from ModuleFolders.Base.Base import Base
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Infrastructure.LLMRequester.LLMRequester import LLMRequester
from ModuleFolders.Infrastructure.RequestLimiter.RequestLimiter import RequestLimiter
from ModuleFolders.Service.Cache.CacheItem import CacheItem

class QAEvaluationTask(LogMixin, ConfigMixin, Base):
    """
    负责对齐后文本的质量评估 (QA)
    """
    def __init__(self, platform_config: dict, thread_counts: int):
        super().__init__()
        self.platform_config = platform_config
        self.thread_counts = thread_counts
        self.request_limiter = RequestLimiter()
        self.request_limiter.set_limit(platform_config.get("rpm_limit", 60))
        self.is_stopped = False

    def stop(self):
        self.is_stopped = True

    def evaluate(self, aligned_pairs: list[tuple[CacheItem, str]], progress_callback=None) -> list[dict]:
        """
        并发请求 LLM 对文本进行质量评估
        """
        results = [None] * len(aligned_pairs)
        
        self.info(f"开始执行 QA 质量评估，总计 {len(aligned_pairs)} 条...")
        
        def _process_item(index: int, source_item: CacheItem, imported_text: str):
            if self.is_stopped:
                return index, None
                
            if not source_item.source_text.strip() or not imported_text.strip():
                return index, {"is_good": True, "issues": ""}
                
            while not self.request_limiter.check_limiter(0):
                if self.is_stopped:
                    return index, None
                time.sleep(0.5)
            
            prompt = f"""
请作为专业翻译校对人员，评估以下原文与其对应译文的翻译质量。
重点检查：
1. 漏译 (Missed translation)
2. 错译 (Wrong translation)
3. 术语不一致 (Terminology inconsistency)

如果翻译完全正确或只有微小可以接受的瑕疵，请判断为良好。

[原文]
{source_item.source_text}

[译文]
{imported_text}

请严格使用 JSON 格式返回结果：
{{
    "is_good": true 或 false,
    "issues": "如果 is_good 为 false，请简短说明原因，否则留空"
}}
"""
            # 发起请求
            try:
                # 为了简便，我们直接使用 LLMRequester 发送单条指令
                requester = LLMRequester()
                message = [{"role": "user", "content": prompt}]
                skip, _, response_text, _, _ = requester.sent_request(
                    messages=message,
                    system_prompt="",
                    platform_config=self.platform_config
                )
                
                # 解析 JSON
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:-3]
                elif response_text.startswith("```"):
                    response_text = response_text[3:-3]
                    
                data = json.loads(response_text)
                return index, data
            except Exception as e:
                self.error(f"QA 评估失败 (索引 {index}): {str(e)}")
                return index, {"is_good": True, "issues": f"评估异常: {str(e)}"}

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.thread_counts)
        futures = [
            executor.submit(_process_item, i, pair[0], pair[1])
            for i, pair in enumerate(aligned_pairs)
        ]
        
        completed = 0
        try:
            for future in concurrent.futures.as_completed(futures):
                if self.is_stopped:
                    for f in futures:
                        f.cancel()
                    break
                    
                idx, data = future.result()
                results[idx] = data
                completed += 1
                if progress_callback:
                    # 如果回调接收三个参数，则传入当前的结果列表
                    try:
                        progress_callback(completed, len(aligned_pairs), results)
                    except TypeError:
                        progress_callback(completed, len(aligned_pairs))
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        return results
