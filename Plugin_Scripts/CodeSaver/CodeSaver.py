import re
import json

from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase

class CodeSaver(PluginBase):

    CODE_PATTERN_EN = (
        r"[/\\][A-Z]{1,5}<[\d]{0,10}>",         # /C<1> \FS<12>
        r"[/\\][A-Z]{1,5}\[[\d]{0,10}\]",       # /C[1] \FS[12]
        r"[/\\][A-Z]{1,5}(?=<.{0,10}>)",        # /C<非数字> /C<非数字> \FS<非数字> \FS<非数字> 中的前半部分
        r"[/\\][A-Z]{1,5}(?=\[.{0,10}\])",      # /C[非数字] /C[非数字] \FS[非数字] \FS[非数字] 中的前半部分
        r"\\fr",                                # 重置文本的改变
        r"\\fb",                                # 加粗
        r"\\fi",                                # 倾斜
        r"\\\{",                                # 放大字体 \{
        r"\\\}",                                # 缩小字体 \}
        r"\\G",                                 # 显示货币 \G
        r"\\\$",                                # 打开金币框 \$
        r"\\\.",                                # 等待0.25秒 \.
        r"\\\|",                                # 等待1秒 \|
        r"\\!",                                 # 等待按钮按下 \!
        # r"\\>",                               # 在同一行显示文字 \>
        # r"\\<",                               # 取消显示所有文字 \<
        r"\\\^",                                # 显示文本后不需要等待 \^
        # r"\\n",                               # 换行符 \\n
        r"\r\n",                                # 换行符 \r\n
        r"\n",                                  # 换行符 \n
        r"\\\\<br>",                            # 换行符 \\<br>
        r"<br>",                                # 换行符 <br>
    )

    CODE_PATTERN_NON_EN = (
        r"[/\\][A-Z]{1,5}<[\dA-Z]{0,10}>",      # /C<y> /C<1> \FS<xy> \FS<12>
        r"[/\\][A-Z]{1,5}\[[\dA-Z]{0,10}\]",    # /C[x] /C[1] \FS[xy] \FS[12]
        r"[/\\][A-Z]{1,5}(?=<.{0,10}>)",        # /C<非数字非字母> /C<非数字非字母> \FS<非数字非字母> \FS<非数字非字母> 中的前半部分
        r"[/\\][A-Z]{1,5}(?=\[.{0,10}\])",      # /C[非数字非字母] /C[非数字非字母] \FS[非数字非字母] \FS[非数字非字母] 中的前半部分
        r"\\fr",                                # 重置文本的改变
        r"\\fb",                                # 加粗
        r"\\fi",                                # 倾斜
        r"\\\{",                                # 放大字体 \{
        r"\\\}",                                # 缩小字体 \}
        r"\\G",                                 # 显示货币 \G
        r"\\\$",                                # 打开金币框 \$
        r"\\\.",                                # 等待0.25秒 \.
        r"\\\|",                                # 等待1秒 \|
        r"\\!",                                 # 等待按钮按下 \!
        # r"\\>",                               # 在同一行显示文字 \>
        # r"\\<",                               # 取消显示所有文字 \<
        r"\\\^",                                # 显示文本后不需要等待 \^
        # r"\\n",                               # 换行符 \\n
        r"\r\n",                                # 换行符 \r\n
        r"\n",                                  # 换行符 \n
        r"\\\\<br>",                            # 换行符 \\<br>
        r"<br>",                                # 换行符 <br>
    )

    # 匹配 <xyz> [xyz] 形式的代码段，尽可能短的匹配
    CODE_LOST_PATTERN = (
        r"<.+?>",
        r"\[.+?\]",
    )

    def __init__(self):
        super().__init__()
        self.name = "CodeSaver"
        self.description = (
            "代码救星，尝试保留文本中的各种代码段（例如 \\FS[29]）以简化文本内嵌的工作量"
            + "\n"
            + "兼容性：支持全部语言；支持全部模型，但仅在 Sakura 等模型上进行过实际的测试；仅支持 T++ 文本；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.NORMAL)
        self.add_event("preproces_text", PluginBase.PRIORITY.NORMAL)
        self.add_event("postprocess_text", PluginBase.PRIORITY.NORMAL)

    def load(self):
        pass

    def on_event(self, event, configurator, data):
        # 检查数据有效性
        if event == None or len(event) <= 1:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 限制模型
        # if "sakura" not in configurator.target_platform.lower():
        #     return

        # 限制文本格式
        if "t++" not in project.get("project_type", "").lower():
            return

        # 关闭内置的 保留句内换行符、保留首位非文本字符 功能
        configurator.text_clear_toggle = False
        configurator.preserve_line_breaks_toggle = False

        if event == "preproces_text":
            self.on_preproces_text(items, project, event, configurator, data)

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(items, project, event, configurator, data)

    # 文本预处理事件
    def on_preproces_text(self, items, project, event, configurator, data):
        # 检查数据是否已经被插件处理过
        if project.get("code_saver_processed", False) == True:
            return

        print("")
        print("[CodeSaver] 开始执行预处理 ...")
        print("")

        # 构建角色表
        # actors = {}
        # for v in [v for v in items if "actors" in v.get("storage_path", "").lower()]:
        #     actors[f"\\n[{v.get("row_index", 1) - 1}]"] = v.get("source_text", "")

        # 根据原文语言生成正则表达式
        if "英语" in configurator.source_language:
            pattern = rf"(?:{"|".join(self.CODE_PATTERN_EN)})+"
        else:
            pattern = rf"(?:{"|".join(self.CODE_PATTERN_NON_EN)})+"

        # 查找代码段
        for v in tqdm(items):
            source_text = v.get("source_text", "")

            # 备份原文
            v["source_backup"] = source_text

            # 查找
            v["code_saver_codes"] = re.findall(pattern, source_text, flags = re.IGNORECASE)

            # 替换
            v["source_text"] = re.sub(pattern, "↓↓", source_text, flags = re.IGNORECASE)

        # 设置处理标志
        project["code_saver_processed"] = True

    # 文本后处理事件
    def on_postprocess_text(self, items, project, event, configurator, data):
        # 检查数据是否已经被插件处理过
        if project.get("code_saver_processed", False) == False:
            return

        print("")
        print("[CodeSaver] 开始执行后处理 ...")
        print("")

        # 还原文本
        result = {
            "代码段丢失": {},
            "占位符还原失败": {},
        }
        target_items = [v for v in items if v.get("translation_status", 0) == 1 and len(v.get("code_saver_codes", [])) > 0]
        for item in tqdm(target_items):
            # 还原原文
            item["source_text"] = item.get("source_backup", "")

            # 有时候模型会增加 ↓ 的数量，分别判断
            success = False
            for flag in ("↓↓", "↓↓↓↓", "↓↓↓", "↓"):
                # 只有原文与译文代码段数量相同的情况下才进行还原
                if len(item.get("code_saver_codes", [])) == item.get("translated_text", "").count(flag):
                    # 还原代码段，每次都只替换一个匹配项以确保依次替换
                    for code in item.get("code_saver_codes", []):
                        item["translated_text"] = item.get("translated_text", "").replace(flag, code, 1)

                    # 可能会有残留，清理一下
                    item["translated_text"] = item.get("translated_text", "").replace("↓", "")

                    # 匹配成功标记
                    success = True

            # 检查是否存在代码段丢失
            code_lost = self.check_code_lost(item.get("source_text", ""), item.get("translated_text", ""))

            # 如果以上均匹配失败，则加入失败条目列表中
            if success == False:
                result["占位符还原失败"][item.get("source_text", "")] = item.get("translated_text", "")
            elif code_lost == True:
                result["代码段丢失"][item.get("source_text", "")] = item.get("translated_text", "")

        # 将还原失败的条目写入文件
        result_path = f"{configurator.label_output_path}/code_saver_result.json"
        with open(result_path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(result, indent = 4, ensure_ascii = False))

        # 计算数量
        failure_count = len(result.get("代码段丢失", {})) + len(result.get("占位符还原失败", {}))
        success_count = len(target_items) - failure_count

        print("")
        print(
            f"[CodeSaver] 代码还原完成，"
            + f"成功 [green]{success_count}[/] 条，"
            + f"失败 [green]{failure_count}[/] 条，"
            + f"成功率 [green]{(success_count / max(1, len(target_items)) * 100):.2f}[/] % ..."
        )
        print(
            f"[CodeSaver] 检查结果已写入 [green]{result_path}[/] 文件，请检查结果并进行手工修正 ..."
        )
        print("")

    # 检查翻译结果是否丢失代码段
    def check_code_lost(self, source: str, translated: str) -> bool:
        result = False

        for pattern in self.CODE_LOST_PATTERN:
            if len(re.findall(pattern, source)) != len(re.findall(pattern, translated)):
                result = True
                break

        return result