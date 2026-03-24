import json
import os
import re
import time

from ModuleFolders.Service.Cache.CacheItem import TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import CacheProject
from ..PluginBase import PluginBase

class TranslationCheckPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "TranslationCheckPlugin"
        self.description = "翻译流程检查插件，用于翻译结果与功能运行评估，包括术语表、禁翻表、换行符和自动处理等。\n错误信息文件将输出到 output 文件夹。"
        self.visibility = True
        self.default_enable = False
        self.add_event("translation_completed", PluginBase.PRIORITY.LOWEST)

    def load(self):
        pass

    def on_event(self, event_name, config, event_data: CacheProject):
        if event_name == "translation_completed":
            self.check_cache(config, event_data)

    def prepare_regex_patterns(self, exclusion_list_data):
        """准备所有需要使用的正则表达式模式"""
        patterns = []
        regex_file_path = os.path.join(".", "Resource", "Regex", "check_regex.json") # 修正路径拼接

        # 从正则库加载基础正则
        if os.path.exists(regex_file_path):
            try:
                with open(regex_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    file_patterns = [item["regex"] for item in data if isinstance(item, dict) and "regex" in item]
                    patterns.extend(file_patterns)
            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                print(f"[WARNING][TranslationCheckPlugin] 加载正则文件 '{regex_file_path}' 失败: {e}")
        else:
             print(f"[WARNING][TranslationCheckPlugin] 正则文件未找到: '{regex_file_path}'")


        # 合并禁翻表数据
        if exclusion_list_data: # 检查 exclusion_list_data 是否存在且非空
            exclusion_patterns = []
            for item in exclusion_list_data:
                if isinstance(item, dict): # 确保 item 是字典
                    if regex := item.get("regex"):
                        try:
                            re.compile(regex) # 尝试编译，验证正则有效性
                            exclusion_patterns.append(regex)
                        except re.error as e:
                            print(f"[WARNING][TranslationCheckPlugin] 禁翻表中的无效正则表达式: '{regex}', 错误: {e}")
                    elif markers := item.get("markers"): # 使用 markers 字段
                        exclusion_patterns.append(re.escape(markers)) # 转义 markers 并添加
            patterns.extend(exclusion_patterns)
        return patterns

    def check_cache(self, config, cache_data: CacheProject):
        error_entries = [] # 存储结构化错误信息
        output_path = config.label_output_path
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        json_error_filename = f"translation_check_errors_{timestamp}.json" # 错误信息单独json文件
        json_error_filepath = os.path.join(output_path, json_error_filename)


        if not os.path.exists(output_path):
            os.makedirs(output_path, exist_ok=True)

        # 获取配置项
        prompt_dictionary_switch = config.prompt_dictionary_switch
        prompt_dictionary_data = config.prompt_dictionary_data if prompt_dictionary_switch else [] # 仅在开关打开时获取
        exclusion_list_switch = config.exclusion_list_switch
        exclusion_list_data = config.exclusion_list_data if exclusion_list_switch else [] # 仅在开关打开时获取
        auto_process_text_code_segment = config.auto_process_text_code_segment

        # 仅在需要时准备正则模式
        patterns = []
        if exclusion_list_switch or auto_process_text_code_segment:
            patterns = self.prepare_regex_patterns(exclusion_list_data if exclusion_list_switch else [])

        project_report_logged = False # 标记项目报告是否已输出

        total_error_count = 0 # 统计总错误数
        check_summary = {
            "prompt_dictionary_errors": 0,
            "exclusion_list_errors": 0,
            "auto_process_errors": 0,
            "newline_errors": 0,
            "placeholder_errors": 0,
            "numbered_prefix_errors": 0,
            "example_text_errors": 0
        }
        
        # 初始化项目报告相关变量
        project_type = ""
        start_time = None
        total_completion_tokens = 0
        total_requests = 0
        error_requests = 0
        total_line = 0
        translated_line = 0

        project_type = cache_data.project_type
        data = cache_data.stats_data
        start_time = data.start_time
        total_completion_tokens = data.total_completion_tokens
        total_requests = data.total_requests
        error_requests = data.error_requests
        total_line = data.total_line
        translated_line = data.line
        end_time = time.time()

        if start_time: # 确保 start_time 有效
            elapsed_time = end_time - start_time
            tokens_per_second = total_completion_tokens / elapsed_time if elapsed_time > 0 else 0
            performance_level = self.map_performance_level(tokens_per_second) # 使用新的映射函数

            project_report = [
                "=" * 60,
                "          💻 项目运行报告 💻          ",
                "─" * 60,
                f"  📌 项目类型: {project_type}",
                f"  ⏱ 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}",
                f"  🏁 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}",
                f"  ⏳ 运行时长: {elapsed_time:.2f} 秒",
                f"  📨 总请求数: {total_requests}",
                f"  ❌ 错误请求数: {error_requests}",
                f"  📝 总行数: {total_line}",
                f"  ✅ 翻译行数: {translated_line}",
                f"  ⚡ Tokens速度: {tokens_per_second:.2f} t/s",
                "─" * 60,
                "          📊 性能评估报告 📊          ",
                f"{performance_level}",
                "=" * 60 + "\n"
            ]
            print("\n".join(project_report)) # 项目报告直接输出到控制台
            project_report_logged = True # 标记已输出
        else:
            print("[WARNING][TranslationCheckPlugin] 项目报告条目缺少有效的 'start_time'。")

        # 再处理文本检查条目
        for file in cache_data.files.values():
            for entry in file.items:

                # 文本条目检查逻辑...
                source_text = entry.source_text
                translated_text = entry.translated_text
                translation_status = entry.translation_status
                storage_path = file.storage_path
                file_name = file.file_name if file.file_name else "Unknown File"
                text_index = entry.text_index

                # 安全获取文本，避免 None 导致后续检查出错
                source_text = source_text if source_text is not None else ""
                translated_text = translated_text if translated_text is not None else ""

                if translation_status == TranslationStatus.EXCLUDED:  # 已被过滤
                    continue # 跳过被过滤的条目

                current_entry_errors = [] # 存储当前条目的错误信息

                if translation_status == 0: # 未翻译
                    error_msg = "🚧 [WARNING] 条目未翻译 "
                    current_entry_errors.append(error_msg) # 记录错误

                elif translation_status == 1: # 已翻译条目
                    # 各项检查，并将错误信息添加到 current_entry_errors
                    # 术语表检查
                    if prompt_dictionary_switch and prompt_dictionary_data:
                        errors = self.check_prompt_dictionary(source_text, translated_text, prompt_dictionary_data)
                        if errors:
                            check_summary["prompt_dictionary_errors"] += len(errors)
                            current_entry_errors.extend(errors)
                    # 禁翻表功能检查
                    if exclusion_list_switch and exclusion_list_data:
                        errors = self.check_exclusion_list(source_text, translated_text, exclusion_list_data)
                        if errors:
                            check_summary["exclusion_list_errors"] += len(errors)
                            current_entry_errors.extend(errors)
                    # 自动处理检查
                    if auto_process_text_code_segment and patterns:
                        errors = self.check_auto_process(source_text, translated_text, patterns)
                        if errors:
                            check_summary["auto_process_errors"] += len(errors)
                            current_entry_errors.extend(errors)
                    # 占位符检查
                    if auto_process_text_code_segment:
                        errors = self.check_placeholder_residue( translated_text)
                        if errors:
                            check_summary["placeholder_errors"] += len(errors)
                            current_entry_errors.extend(errors)

                    # 数字序号检查
                    errors = self.check_numbered_prefix( translated_text)
                    if errors:
                        check_summary["numbered_prefix_errors"] += len(errors)
                        current_entry_errors.extend(errors)

                    # 示例文本复读检查
                    errors = self.check_example_text( translated_text)
                    if errors:
                        check_summary["example_text_errors"] += len(errors)
                        current_entry_errors.extend(errors)

                    # 换行符检查
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


        # 输出检查总结到控制台 (仅当有文本条目被检查过才输出总结)
        # 通过检查 total_error_count 或 check_summary 的值是否非零判断
        if any(v > 0 for v in check_summary.values()) or total_error_count > 0 or not project_report_logged:
             # 如果没有项目报告，或者有错误，或者总结非零，则输出总结
            summary_messages = ["\n"+"=" * 60, "          ✨ 检查总结 ✨          ", "─" * 60]
            if total_error_count > 0:
                summary_messages.append(f"          ❌ 共发现 {total_error_count} 个潜在问题 ❌")
                if check_summary["prompt_dictionary_errors"] > 0:
                    summary_messages.append(f"  - 📚 术语表检查: {check_summary['prompt_dictionary_errors']} 个错误 ⚠️")
                if check_summary["exclusion_list_errors"] > 0:
                    summary_messages.append(f"  - 🚫 禁翻表检查: {check_summary['exclusion_list_errors']} 个错误 ⚠️")
                if check_summary["auto_process_errors"] > 0:
                    summary_messages.append(f"  - ⚙️ 自动处理检查: {check_summary['auto_process_errors']} 个错误 ⚠️")
                if check_summary["placeholder_errors"] > 0:
                    summary_messages.append(f"  - 🍩 占位符残留检查: {check_summary['placeholder_errors']} 个错误 ⚠️")
                if check_summary["numbered_prefix_errors"] > 0:
                    summary_messages.append(f"  - 🔢 数字序号检查: {check_summary['numbered_prefix_errors']} 个错误 ⚠️")
                if check_summary["example_text_errors"] > 0:
                    summary_messages.append(f"  - 💦 示例文本复读检查: {check_summary['example_text_errors']} 个错误 ⚠️")
                if check_summary["newline_errors"] > 0:
                    summary_messages.append(f"  - 📃 换行符检查: {check_summary['newline_errors']} 个错误 ⚠️")

                if any(e['errors'][0] == "🚧 [WARNING] 条目未翻译 " for e in error_entries if e['errors']):
                    untranslated_count = sum(1 for e in error_entries if e['errors'] and e['errors'][0] == "🚧 [WARNING] 条目未翻译 ")
                    summary_messages.append(f"  - 🚧 未翻译条目: {untranslated_count} 个 ⚠️")

            elif any(cache_data.items_iter()):  # 上面遍历了所有items，所以只要items不为空就能确保有文本条目被检查过
                summary_messages.append("✅ 恭喜！所有已翻译条目的检查项均未发现明显错误 🎉🎉🎉")
            else: # 如果 cache_list 为空或只有项目报告
                 summary_messages.append("ℹ️ 未检查任何文本条目。")

            summary_messages.append("=" * 60 + "\n")
            print("\n".join(summary_messages)) # 控制台输出总结信息


        # 写入结构化错误信息到 JSON 文件
        if error_entries:
            try:
                with open(json_error_filepath, 'w', encoding='utf-8') as json_file:
                    json.dump(error_entries, json_file, indent=4, ensure_ascii=False) # 缩进和中文支持
                print(f"[INFO][TranslationCheckPlugin] {len(error_entries)} 个错误条目的详细信息已保存到: {json_error_filepath}")
            except IOError as e:
                print(f"[ERROR][TranslationCheckPlugin] 无法写入错误日志文件 '{json_error_filepath}': {e}")

        elif total_error_count == 0 and any(cache_data.items_iter()):  # 上面遍历了所有items，所以只要items不为空就能确保有文本条目被检查过
            print("[INFO][TranslationCheckPlugin] 所有已检查条目均无错误，未生成错误日志文件。")
        # 如果没有文本条目被检查，则不输出此信息


    def map_performance_level(self, tokens_per_second):
        """
        根据 tokens/s 速度进行性能评级，并计算超越用户百分比。
        百分比在每个速度等级区间内线性增长。
        """
        # 性能等级定义: (速度上限, 等级名称, 描述, 在该速度上限时达到的超越百分比)
        # 百分比应单调递增，且介于 0 到 100 之间。
        levels = [
            # (Max Speed, Level Name, Description, Percentile Target AT this Max Speed)
            (20,   "          🐌 蜗牛速",      "需要加油哦",   10.0),  # 在 20 t/s 时，超越 10.0%
            (100,   "          🚲 自行车速",    "正常起步",    30.0),  # 在 50 t/s 时，超越 30.0%
            (300,  "          🚗 汽车速度",    "流畅运行",     60.0),  # 在 100 t/s 时，超越 60.0%
            (500,  "          🚄 高铁速度",    "效率惊人",     85.0),  # 在 200 t/s 时，超越 85.0%
            (700,  "          ✈️ 飞机速度",    "专业级表现",   95.0),  # 在 350 t/s 时，超越 95.0%
            (800,  "          🚀 火箭速度",    "顶尖水平",     99.0),  # 在 600 t/s 时，超越 99.0%
            (1000, "          ⚡ 光子速度",    "超越物理极限", 99.9)   # 在 1000 t/s 时，超越 99.9%
            # 对于超过 1000 t/s 的速度，我们将百分比限制在 99.9%
        ]

        # 处理 tokens_per_second <= 0 的情况
        if tokens_per_second <= 0:
            level_name = levels[0][1]
            level_desc = levels[0][2]
            display_percent = 0.0
            return f"{level_name} {level_desc} \n  🎉恭喜你，超越全宇宙 {display_percent:.1f}% 的翻译用户！！！"

        level_name = levels[-1][1] # 默认名称为最高等级
        level_desc = levels[-1][2] # 默认描述为最高等级
        display_percent = levels[-1][3] # 默认百分比为最高等级目标

        prev_max_speed = 0.0
        prev_percentile = 0.0

        for max_speed, name, desc, target_percentile in levels:
            if tokens_per_second <= max_speed:
                level_name = name
                level_desc = desc

                # 在当前区间 [prev_max_speed, max_speed] 内进行线性插值
                speed_range = max_speed - prev_max_speed
                percentile_range = target_percentile - prev_percentile

                if speed_range > 0:
                    # 计算当前速度在速度区间内的比例
                    ratio = (tokens_per_second - prev_max_speed) / speed_range
                    # 根据比例计算插值后的百分比
                    display_percent = prev_percentile + ratio * percentile_range
                else: # 处理 speed_range 为 0 或负数（理论上不应发生，除非 levels 定义错误）
                      # 或者 tokens_per_second 恰好等于 prev_max_speed
                    display_percent = prev_percentile # 直接使用上一级的百分比

                # 确保百分比不会超过当前等级的目标值（防止浮点误差）
                # 同时确保百分比不低于上一等级的目标值
                display_percent = max(prev_percentile, min(display_percent, target_percentile))
                
                # 对最终结果应用一个全局上限，例如 99.9%
                display_percent = min(display_percent, 99.9)
                break # 找到对应的等级区间，停止循环

            # 更新上一等级的信息，为下一次迭代或超出最高等级时使用
            prev_max_speed = max_speed
            prev_percentile = target_percentile
        else:
            # 如果循环正常结束（未 break），说明 tokens_per_second 大于最后一个 max_speed
            # 使用最高等级的名称和描述，并将百分比限制在最终目标值（或全局上限）
            level_name = levels[-1][1]
            level_desc = levels[-1][2]
            display_percent = levels[-1][3]
            display_percent = min(display_percent, 99.9) # 再次确保上限

        # 确保百分比不为负（虽然理论上不会，但作为保险）
        display_percent = max(0.0, display_percent)

        return f"{level_name} {level_desc} \n  🎉恭喜你，翻译速度超越全宇宙 {display_percent:.1f}% 的用户！！！"


    def check_prompt_dictionary(self, source_text, translated_text, prompt_dictionary_data):
        """检查术语表功能, 返回错误信息列表"""
        errors = []
        # prompt_dictionary_data 已在调用前检查过非空
        for term in prompt_dictionary_data:
           if isinstance(term, dict): # 确保 term 是字典
                src_term = term.get("src")
                dst_term = term.get("dst")
                # 确保 src_term 和 dst_term 都存在且非空
                if src_term and dst_term:
                    # 简单的包含检查，可能需要更复杂的逻辑（如大小写、词形变化）
                    if src_term in source_text:
                        if dst_term not in translated_text:
                            error_msg = f"📚[术语表错误] 原文含 '{src_term}'，译文未找到对应术语 '{dst_term}'"
                            errors.append(error_msg)
        return errors


    def check_exclusion_list(self, source_text, translated_text, exclusion_list_data):
        """检查禁翻表功能, 返回错误信息列表"""
        errors = []
        # exclusion_list_data 已在调用前检查过非空
        for item in exclusion_list_data:
            pattern_to_check = None
            original_marker = None # 用于错误信息展示

            if isinstance(item, dict): # 确保 item 是字典
                regex = item.get("regex")
                markers = item.get("markers")

                if regex:
                    try:
                        re.compile(regex) # 再次验证（虽然 prepare_regex_patterns 可能已做）
                        pattern_to_check = regex
                        original_marker = f"正则 '{regex}'"
                    except re.error:
                        # 忽略无效正则，或记录一个警告
                        continue # 跳过这个无效项
                elif markers:
                    pattern_to_check = re.escape(markers)
                    original_marker = f"标记符 '{markers}'"

            if pattern_to_check and original_marker:
                try:
                     # 使用 finditer 获取所有匹配及其位置，更精确
                    for match in re.finditer(pattern_to_check, source_text):
                        matched_text = match.group(0) # 获取匹配到的具体文本
                        # 检查译文中是否“原样”包含这个匹配到的文本
                        if matched_text not in translated_text:
                            error_msg = f"🚫[禁翻表错误] 原文含 {original_marker} 匹配到的 '{matched_text}'，但译文缺少此内容"
                            # 避免重复添加完全相同的错误信息
                            if error_msg not in errors:
                                 errors.append(error_msg)
                except re.error:
                     # 处理 pattern_to_check 编译失败的情况（理论上不应发生）
                     continue
        return errors
    

    def check_auto_process(self, source_text, translated_text, patterns):
        """检查自动处理功能 (基于 patterns 列表), 返回错误信息列表"""
        errors = []

        # 确保输入是字符串，如果不是则视为空字符串处理或保持原样以便后续处理
        _source_text = source_text if isinstance(source_text, str) else ""
        _translated_text = translated_text if isinstance(translated_text, str) else ""

        # --- 去除尾部所有换行符 ---
        _source_text = _source_text.rstrip('\n')
        _translated_text = _translated_text.rstrip('\n')

        # patterns 已在调用前检查过非空 
        for pattern in patterns:
            try:
                # 使用 finditer 获取所有匹配
                for match in re.finditer(pattern, _source_text):
                    matched_text = match.group(0)
                    # 检查处理过的译文中是否“原样”包含这个匹配到的文本
                    if matched_text not in _translated_text:
                        # 对 pattern 做截断，防止过长
                        pattern_display = pattern[:50] + '...' if len(pattern) > 50 else pattern
                        error_msg = f"⚙️[自动处理错误] 规则 '{pattern_display}' 匹配到 '{matched_text}'，但译文缺少此内容"
                        if error_msg not in errors:
                             errors.append(error_msg)
            except re.error:
                 continue
        return errors


    def check_newline(self, source_text, translated_text):
        """检查换行符数量一致性, 返回错误信息列表"""
        errors = []

        # 确保输入是字符串，如果不是则视为空字符串处理或保持原样以便后续处理
        _source_text = source_text if isinstance(source_text, str) else ""
        _translated_text = translated_text if isinstance(translated_text, str) else ""

        # 去除头尾的空格和换行符
        trimmed_source_text = _source_text.strip()
        trimmed_translated_text = _translated_text.strip()

        # 在处理过的文本上计算文本内的换行符数量
        source_newlines = trimmed_source_text.count('\n')
        # 检查原文中的转义换行符
        source_newlines += trimmed_source_text.count('\\n')

        translated_newlines = trimmed_translated_text.count('\n')
        translated_newlines += trimmed_translated_text.count('\\n')

        if source_newlines != translated_newlines:
            error_msg = f"📃[换行符错误] 原文有 {source_newlines} 个换行符，译文有 {translated_newlines} 个"
            errors.append(error_msg)
        return errors


    def check_placeholder_residue(self,  translated_text):
        """检查占位符残留, 返回错误信息列表"""
        errors = []
        
        # 确保输入是字符串，如果不是则视为空字符串处理或保持原样以便后续处理
        translated_text = translated_text if isinstance(translated_text, str) else ""
        
        # 正则表达式匹配 [P+数字] 格式的占位符
        pattern = r'\[P\d+\]'  # 匹配示例：[P3]、[P25]、[P999]
        
        if re.search(pattern, translated_text):
            error_msg = f"🍩[占位符残留] 译文中残留有类似[P数字]的占位符，未能还原成功（示例：{re.findall(pattern, translated_text)[0]}）"
            errors.append(error_msg)
        return errors

    def check_numbered_prefix(self,  translated_text):
        """检查数字序号残留, 返回错误信息列表"""
        errors = []
        
        # 确保输入是字符串，如果不是则视为空字符串处理或保持原样以便后续处理
        translated_text = translated_text if isinstance(translated_text, str) else ""
        
        # 正则表达式匹配 1.2. 格式的占位符
        pattern = r'\d+\.\d+\.'  # 匹配示例：1.2.
        
        if re.search(pattern, translated_text):
            error_msg = f"🔢[数字序号残留] 译文中残留数字子序号，未能清除成功（示例：{re.findall(pattern, translated_text)[0]}）"
            errors.append(error_msg)
        return errors
    
    # 针对“示例文本[随机字母]-[随机数字]”的残留检查，目前只针对中文进行检查
    def check_example_text(self, translated_text):
        """检查示例文本复读, 返回错误信息列表"""
        errors = []
        
        # 确保输入是字符串，如果不是则视为空字符串处理或保持原样以便后续处理
        translated_text = translated_text if isinstance(translated_text, str) else ""
        
        # 正则表达式匹配 示例文本B-1 格式的示例复读文本
        # 匹配示例：示例文本B-1
        pattern = r'示例文本[A-Z]-\d+'
        
        if re.search(pattern, translated_text):
            error_msg = f"🔢[示例文本复读] 译文中出现示例文本复读问题，未能正确翻译（示例：{re.findall(pattern, translated_text)[0]}）"
            errors.append(error_msg)
        return errors

