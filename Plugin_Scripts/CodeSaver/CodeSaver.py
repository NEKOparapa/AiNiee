import re
import json

from tqdm import tqdm
from rich import print

from Plugin_Scripts.Plugin_Base.Plugin_Base import PluginBase

class MTool_Optimizer(PluginBase):

    CODE_PATTERN = (
        r"[/\\][A-Z]{1,5}<[\d]{0,10}>",         # /C<y> /C<1> \FS<xy> \FS<12>
        r"[/\\][A-Z]{1,5}\[[\d]{0,10}\]",       # /C[x] /C[1] \FS[xy] \FS[12]
        r"[/\\][A-Z]{1,5}(?=<.{0,10}>)",        # /C<非数字> /C<非数字> \FS<非数字> \FS<非数字> 中的前半部分
        r"[/\\][A-Z]{1,5}(?=\[.{0,10}\])",      # /C[非数字] /C[非数字] \FS[非数字] \FS[非数字] 中的前半部分
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
        r"<.{0,10}?>",
        r"\[.{0,10}?\]",
    )



    def __init__(self):
        super().__init__()
        self.name = "CodeSaver"
        self.description = (
            "代码救星，尝试保留文本中的各种代码段（例如 \FS[29]）以方便进行文本内嵌"
            + "\n" + "兼容性：支持全部语言；仅支持 Sakura 系列模型；仅支持 T++ 文本；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", 5)
        self.add_event("preproces_text", 5)
        self.add_event("postprocess_text", 5)

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
        if "sakura" not in configurator.target_platform.lower():
            return

        # 限制文本格式
        if "t++" not in project.get("project_type", "").lower():
            return

        # 关闭内置的 保留句内换行符 和 保留首位非文本字符 功能
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

        # 查找代码段
        pattern = rf"(?:{"|".join(self.CODE_PATTERN)})+"
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
        failed_items = {
            "failed": {},
            "code_lost": {},
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
                failed_items["failed"][item.get("source_text", "")] = item.get("translated_text", "")
            elif code_lost == True:
                failed_items["code_lost"][item.get("source_text", "")] = item.get("translated_text", "")

        # 将还原失败的条目写入文件
        with open(f"{configurator.label_output_path}/code_saver_failed_items.json", "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(failed_items, indent = 4, ensure_ascii = False))

        print("")
        print(
            f"[CodeSaver] 已将 {len(failed_items.get("failed")) + len(failed_items.get("code_lost"))} 条未通过检查的条目写入 [green]{configurator.label_output_path}/code_saver_failed_items.json[/] 文件，请手工修正 ..."
        )

    # 检查翻译结果是否丢失代码段
    def check_code_lost(self, source: str, translated: str) -> bool:
        result = False

        for pattern in self.CODE_LOST_PATTERN:
            if len(re.findall(pattern, source)) != len(re.findall(pattern, translated)):
                result = True
                break

        return result