import json
import os
import re
import time
from ..PluginBase import PluginBase

class TranslationCheckPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "TranslationCheckPlugin"
        self.description = "翻译功能检查插件，用于翻译结果与功能运行评估，包括术语表、禁翻表、换行符和自动处理等。\n错误信息文件将输出到 output 文件夹。"
        self.visibility = True
        self.default_enable = True
        self.add_event("translation_completed", PluginBase.PRIORITY.LOWEST)

    def load(self):
        pass

    def on_event(self, event_name, config, event_data):
        if event_name == "translation_completed":
            self.check_cache(config, event_data)

    def prepare_regex_patterns(self, exclusion_list_data):
        """准备所有需要使用的正则表达式模式"""
        patterns = []

        # 从正则库加载基础正则
        with open(os.path.join(".", "Resource", "Regex", "regex.json"), 'r', encoding='utf-8') as f:
            data = json.load(f)
            file_patterns =  [item["regex"] for item in data if isinstance(item, dict) and "regex" in item]
        patterns.extend(file_patterns)

        # 合并禁翻表数据
        exclusion_patterns = []
        for item in exclusion_list_data:
            if regex := item.get("regex"):
                exclusion_patterns.append(regex)
            elif markers := item.get("markers"): # 使用 markers 字段
                exclusion_patterns.append(re.escape(markers)) # 转义 markers 并添加
        patterns.extend(exclusion_patterns)
        return patterns

    def check_cache(self, config, cache_list):
        error_entries = [] # 存储结构化错误信息
        output_path = config.label_output_path
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        json_error_filename = f"translation_check_errors_{timestamp}.json" # 错误信息单独json文件
        json_error_filepath = os.path.join(output_path, json_error_filename)


        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)

        # 获取配置项
        prompt_dictionary_switch = config.prompt_dictionary_switch
        prompt_dictionary_data = config.prompt_dictionary_data
        exclusion_list_switch = config.exclusion_list_switch
        exclusion_list_data = config.exclusion_list_data
        auto_process_text_code_segment = config.auto_process_text_code_segment

        patterns = self.prepare_regex_patterns(exclusion_list_data) if exclusion_list_data else []

        project_report_logged = False # 标记项目报告是否已输出

        total_error_count = 0 # 统计总错误数
        check_summary = {
            "prompt_dictionary_errors": 0,
            "exclusion_list_errors": 0,
            "auto_process_errors": 0,
            "newline_errors": 0
        }

        for entry in cache_list:
            project_type = entry.get("project_type","")

            if project_type and not project_report_logged: # 项目运行信息，只输出一次
                start_time = entry.get("data").get("start_time")
                total_completion_tokens = entry.get("data").get("total_completion_tokens")
                total_requests = entry.get("data").get("total_requests")
                error_requests = entry.get("data").get("error_requests")
                total_line = entry.get("data").get("total_line")
                translated_line = entry.get("data").get("line")
                end_time = time.time()
                elapsed_time = end_time - start_time
                tokens_per_second = total_completion_tokens / elapsed_time if elapsed_time > 0 else 0
                performance_level = self.map_performance_level(tokens_per_second) # 使用新的映射函数

                project_report = [
                    "=" * 60,
                    "          💻 项目运行报告 💻          ",
                    "=" * 60,
                    f"  📌 项目类型: {project_type}",
                    f"  ⏱ 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}",
                    f"  🏁 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}",
                    f"  ⏳ 运行时长: {elapsed_time:.2f} 秒",
                    f"  📨 总请求数: {total_requests}",
                    f"  ❌ 错误请求数: {error_requests}",
                    f"  📝 总行数: {total_line}",
                    f"  ✅ 翻译行数: {translated_line}",
                    f"  ⚡ Tokens速度: {tokens_per_second:.2f} tokens/s",
                    "─" * 60,
                    "          📊 性能评估报告 📊          ",
                    f"{performance_level}",
                    "=" * 60 + "\n"
                ]
                print("\n".join(project_report)) # 项目报告直接输出到控制台
                project_report_logged = True # 标记已输出

            elif not project_type: # 文本条目检查
                source_text = entry.get("source_text")
                translated_text = entry.get("translated_text")
                translation_status = entry.get("translation_status")
                storage_path = entry.get("storage_path")
                file_name = entry.get("file_name") if entry.get("file_name") else "Unknown File"
                text_index = entry.get("text_index")

                if translation_status == 7: # 已被过滤
                    continue # 跳过被过滤的条目

                current_entry_errors = [] # 存储当前条目的错误信息

                if translation_status == 0: # 未翻译
                    error_msg = "🚧 [WARNING] 条目未翻译 " 
                    current_entry_errors.append(error_msg) # 记录错误

                elif translation_status == 1: # 已翻译条目
                    # 各项检查，并将错误信息添加到 current_entry_errors
                    if prompt_dictionary_switch:
                        errors = self.check_prompt_dictionary(source_text, translated_text, prompt_dictionary_data)
                        if errors:
                            check_summary["prompt_dictionary_errors"] += len(errors)
                            current_entry_errors.extend(errors)
                    if exclusion_list_switch:
                        errors = self.check_exclusion_list(source_text, translated_text, exclusion_list_data)
                        if errors:
                            check_summary["exclusion_list_errors"] += len(errors)
                            current_entry_errors.extend(errors)
                    if auto_process_text_code_segment:
                        errors = self.check_auto_process(source_text, translated_text, patterns)
                        if errors:
                            check_summary["auto_process_errors"] += len(errors)
                            current_entry_errors.extend(errors)
                    errors = self.check_newline(source_text, translated_text)
                    if errors:
                        check_summary["newline_errors"] += len(errors)
                        current_entry_errors.extend(errors)

                if current_entry_errors: # 如果当前条目有错误，则添加到结构化错误日志
                    total_error_count += len(current_entry_errors)
                    error_entries.append({
                        "file_name": file_name,
                        "storage_path": storage_path,
                        "text_index": text_index,
                        "source_text": source_text,
                        "translated_text": translated_text,
                        "errors": current_entry_errors
                    })


        # 输出检查总结到控制台
        summary_messages = ["\n"+"=" * 60, "          ✨ 检查总结 ✨          ", "=" * 60] 
        if total_error_count > 0:
            summary_messages.append(f"❌ 总错误条目数: {total_error_count} ❌") 
            for check_type, error_count in check_summary.items():
                if error_count > 0:
                    summary_messages.append(f"  - {check_type.replace('_', ' ').title()}: 发现 {error_count}个错误 ⚠️") 
        else:
            summary_messages.append("✅ 恭喜！所有检查项均未发现错误 🎉🎉🎉") 
        summary_messages.append("=" * 60 + "\n")
        print("\n".join(summary_messages)) # 控制台输出总结信息


        # 写入结构化错误信息到 JSON 文件
        if error_entries:
            with open(json_error_filepath, 'w', encoding='utf-8') as json_file:
                json.dump(error_entries, json_file, indent=4, ensure_ascii=False) # 缩进和中文支持
            print(f"[INFO][TranslationCheckPlugin] 结构化错误日志已保存到: {json_error_filepath}")

        else:
            print("[INFO][TranslationCheckPlugin] 没有错误条目，未生成结构化错误日志文件。")


    def map_performance_level(self, tokens_per_second):
        """基于对数正态分布的百分比计算模型（假设μ=4.0，σ=0.8）"""
        from math import log, erf
        # 对数正态分布参数（通过调整这些参数可以改变分布形态）
        mu, sigma = 4.0, 0.8  # 约合普通用户场景
        
        def log_normal_cdf(x):
            if x <= 0:
                return 0.0
            return 0.5 * (1 + erf((log(x) - mu) / (sigma * 2**0.5)))
        
        # 计算超越百分比（1 - 累计概率）
        percentile = (1 - log_normal_cdf(tokens_per_second)) * 100
        
        # 性能等级映射表（按速度升序排列）
        levels = [
            (20,  "          🐌 蜗牛速",       "需要加油哦", 0.1),
            (50,  "          🚲 自行车速",     "正常起步", 0.3),
            (100, "          🚗 汽车速度",     "流畅运行", 0.6),
            (200, "          🚄 高铁速度",     "效率惊人", 0.85),
            (350, "          ✈️ 飞机速度",    "专业级表现", 0.95),
            (600, "          🚀 火箭速度",    "顶尖水平", 0.99),
            (1000,"          ⚡ 光子速度",     "超越物理极限", 1.0)
        ]

        # 查找对应的等级描述
        for max_speed, name, desc, _ in levels:
            if tokens_per_second <= max_speed:
                break
                
        # 计算实际超越百分比（用线性插值优化显示效果）
        prev_level = next((l for l in reversed(levels) if l[0] < max_speed), None)
        if prev_level:
            ratio = (tokens_per_second - prev_level[0]) / (max_speed - prev_level[0])
            display_percent = min(prev_level[3] + ratio*(percentile/100 - prev_level[3]), 0.999) * 100
        else:
            display_percent = percentile
            
        return f"{name} {desc} \n  🎉恭喜你，超越全宇宙 {display_percent:.1f}% 的翻译用户！！！"


    def check_prompt_dictionary(self, source_text, translated_text, prompt_dictionary_data):
        """检查术语表功能, 返回错误信息列表"""
        errors = []
        if not prompt_dictionary_data:
            return errors

        for term in prompt_dictionary_data:
            src_term = term.get("src")
            dst_term = term.get("dst")
            if src_term in source_text:
                if dst_term not in translated_text:
                    error_msg = f"📚[术语表错误] 原文 '{src_term}' 存在，但对应译文缺少术语 '{dst_term}' " 
                    errors.append(error_msg)
        return errors


    def check_exclusion_list(self, source_text, translated_text, exclusion_list_data):
        """检查禁翻表功能, 返回错误信息列表"""
        errors = []
        if not exclusion_list_data:
            return errors

        for item in exclusion_list_data:
            markers = item.get("markers")
            regex = item.get("regex")
            pattern_to_check = regex if regex else re.escape(markers) # 优先使用正则，否则转义 markers

            if re.search(pattern_to_check, source_text):
                matches_source = re.findall(pattern_to_check, source_text)
                for match in matches_source: # 遍历所有匹配项进行检查
                    if match not in translated_text:
                        error_msg = f"🚫[禁翻表错误] 标记符 '{match}' ，但译文缺少对应内容 " 
                        errors.append(error_msg)
        return errors


    def check_auto_process(self, source_text, translated_text, patterns):
        """检查自动处理功能 (合并禁翻表和正则库), 返回错误信息列表"""
        errors = []
        if not patterns:
            return errors

        for pattern in patterns:
            if re.search(pattern, source_text):
                matches_source = re.findall(pattern, source_text)
                for match in matches_source:
                    if match not in translated_text:
                        error_msg = f"⚙️[自动处理错误] 标记符 '{match}' 匹配规则 '{pattern}'，但译文缺少对应内容 " 
                        errors.append(error_msg)
        return errors


    def check_newline(self, source_text, translated_text):
        """检查换行符一致性, 返回错误信息列表"""
        errors = []
        source_newlines = source_text.count('\n')
        translated_newlines = translated_text.count('\n')
        if source_newlines != translated_newlines:
            error_msg = f"📃[换行符错误] 原文有 {source_newlines} 个换行符，译文有 {translated_newlines} 个，数量不一致 " 
            errors.append(error_msg)
        return errors