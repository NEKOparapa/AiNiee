import os
import re
import json

from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase
from Module_Folders.Configurator.Config import Configurator

class CodeSaver(PluginBase):

    # 用于英文的代码段规则
    CODE_PATTERN_EN = (
        r"\s*" + r"if\(.{0,10}[vs]\[\d+\].{0,10}\)" + r"\s*",           # if(!s[982]) if(v[982] >= 1)
        r"\s*" + r"en\(.{0,10}[vs]\[\d+\].{0,10}\)" + r"\s*",           # en(!s[982]) en(v[982] >= 1)
        r"\s*" + r"[/\\][a-z]{1,5}<[\d]{0,10}>" + r"\s*",               # /C<1> \FS<12>
        r"\s*" + r"[/\\][a-z]{1,5}\[[\d]{0,10}\]" + r"\s*",             # /C[1] \FS[12]
        r"\s*" + r"[/\\][a-z]{1,5}(?=<.{0,10}>)" + r"\s*",              # /C<非数字> /C<非数字> \FS<非数字> \FS<非数字> 中的前半部分
        r"\s*" + r"[/\\][a-z]{1,5}(?=\[.{0,10}\])" + r"\s*",            # /C[非数字] /C[非数字] \FS[非数字] \FS[非数字] 中的前半部分
    )

    # 用于非英文的代码段规则
    CODE_PATTERN_NON_EN = (
        r"\s*" + r"if\(.{0,10}[vs]\[\d+\].{0,10}\)" + r"\s*",           # if(!s[982]) if(v[982] >= 1)
        r"\s*" + r"en\(.{0,10}[vs]\[\d+\].{0,10}\)" + r"\s*",           # en(!s[982]) en(v[982] >= 1)
        r"\s*" + r"[/\\][a-z]{1,5}<[\da-z]{0,10}>" + r"\s*",            # /C<y> /C<1> \FS<xy> \FS<12>
        r"\s*" + r"[/\\][a-z]{1,5}\[[\da-z]{0,10}\]" + r"\s*",          # /C[x] /C[1] \FS[xy] \FS[12]
        r"\s*" + r"[/\\][a-z]{1,5}(?=<.{0,10}>)" + r"\s*",              # /C<非数字非字母> /C<非数字非字母> \FS<非数字非字母> \FS<非数字非字母> 中的前半部分
        r"\s*" + r"[/\\][a-z]{1,5}(?=\[.{0,10}\])" + r"\s*",            # /C[非数字非字母] /C[非数字非字母] \FS[非数字非字母] \FS[非数字非字母] 中的前半部分
    )

    # 同时作用于英文于非英文的代码段规则
    CODE_PATTERN_COMMON = (
        r"\s*" + r"\\fr" + r"\s*",                                      # 重置文本的改变
        r"\s*" + r"\\fb" + r"\s*",                                      # 加粗
        r"\s*" + r"\\fi" + r"\s*",                                      # 倾斜
        r"\s*" + r"\\\{" + r"\s*",                                      # 放大字体 \{
        r"\s*" + r"\\\}" + r"\s*",                                      # 缩小字体 \}
        r"\s*" + r"\\g" + r"\s*",                                       # 显示货币 \G
        r"\s*" + r"\\\$" + r"\s*",                                      # 打开金币框 \$
        r"\s*" + r"\\\." + r"\s*",                                      # 等待0.25秒 \.
        r"\s*" + r"\\\|" + r"\s*",                                      # 等待1秒 \|
        r"\s*" + r"\\!" + r"\s*",                                       # 等待按钮按下 \!
        # r"\s*" + r"\\>" + r"\s*",                                     # 在同一行显示文字 \>
        # r"\s*" + r"\\<" + r"\s*",                                     # 取消显示所有文字 \<
        r"\s*" + r"\\\^" + r"\s*",                                      # 显示文本后不需要等待 \^
        # r"\s*" + r"\\n" + r"\s*",                                     # 换行符 \\n
        r"\s*" + r"\r\n" + r"\s*",                                      # 换行符 \r\n
        r"\s*" + r"\n" + r"\s*",                                        # 换行符 \n
        r"\s*" + r"\\\\<br>" + r"\s*",                                  # 换行符 \\<br>
        r"\s*" + r"<br>" + r"\s*",                                      # 换行符 <br>
    )

    # 需要进行数量匹配检查的代码段
    CODE_PATTERN_NUM_MATCH = (
        "<",
        ">",
        "[",
        "]",
    )

    def __init__(self) -> None:
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

    def on_event(self, event: str, configurator: Configurator, data: dict) -> None:
        # 检查数据有效性
        if event == None or len(event) <= 1:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 限制文本格式
        if "t++" not in project.get("project_type", "").lower():
            return

        # 关闭内置的 保留句内换行符、保留首位非文本字符 功能
        configurator.preserve_prefix_and_suffix_codes = False
        configurator.preserve_line_breaks_toggle = False

        if event == "preproces_text":
            self.on_preproces_text(event, configurator, data, items, project)

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(event, configurator, data, items, project)

    # 文本预处理事件
    def on_preproces_text(self, event: str, configurator: Configurator, data: dict, items: list[dict], project: list[dict]) -> None:
        # 检查数据是否已经被插件处理过
        if project.get("code_saver_processed", False) == True:
            return

        print(f"")
        print("[CodeSaver] 开始执行预处理 ...")
        print(f"")

        # 根据是否为 RPGMaker MV/MZ 文本来决定是否启用 角色代码还原 步骤
        names = []
        nicknames = []
        if any(re.search(r"\\n{1,2}\[\d+\]", v.get("source_text", ""), flags = re.IGNORECASE) for v in items):
            print(f"[CodeSaver] 判断为 [green]RPGMaker MV/MZ[/] 游戏文本 ...")
            names, nicknames = self.load_names(f"{configurator.label_input_path}/Actors.json")
            if len(names) + len(nicknames) > 0:
                print(f"[CodeSaver] [green]Actors.json[/] 文件加载成功，共加载 {len(names) + len(nicknames)} 条数据，稍后将执行 [green]角色代码还原[/] 步骤 ...")
                print(f"")
            else:
                print(f"[CodeSaver] 未在 [green]输入目录[/] 下找到 [green]Actors.json[/] 文件，将跳过 [green]角色代码还原[/] 步骤 ...")
                print(f"[CodeSaver] [green]角色代码还原[/] 步骤可以显著提升质量，建议添加 [green]Actors.json[/] 后重新开始 ...")
                print(f"[CodeSaver] [green]Actors.json[/] 文件一般可以在游戏目录的 [green]data[/] 或者 [green]www\\data[/] 文件夹内找到 ...")
                print(f"")

        # 根据原文语言生成正则表达式
        if "英语" in configurator.source_language:
            code_pattern = self.CODE_PATTERN_EN + self.CODE_PATTERN_COMMON
        else:
            code_pattern = self.CODE_PATTERN_NON_EN + self.CODE_PATTERN_COMMON
        pattern = rf"(?:{"|".join(code_pattern)})+"
        prefix_pattern = f"^(?:{"|".join(code_pattern)})+"
        suffix_pattern = f"(?:{"|".join(code_pattern)})+$"

        # 查找代码段
        for item in tqdm(items):
            # 备份原文
            item["source_backup"] = item.get("source_text", "")

            # 还原角色代码
            item["source_text"] = self.replace_name_code(item.get("source_text"), names, nicknames)

            # 查找与替换前缀代码段
            item["code_saver_prefix_codes"] = re.findall(prefix_pattern, item.get("source_text"), flags = re.IGNORECASE)
            item["source_text"] = re.sub(prefix_pattern, "", item.get("source_text"), flags = re.IGNORECASE)

            # 查找与替换后缀代码段
            item["code_saver_suffix_codes"] = re.findall(suffix_pattern, item.get("source_text"), flags = re.IGNORECASE)
            item["source_text"] = re.sub(suffix_pattern, "", item.get("source_text"), flags = re.IGNORECASE)

            # 查找与替换主体代码段
            item["code_saver_codes"] = re.findall(pattern, item.get("source_text"), flags = re.IGNORECASE)
            item["source_text"] = re.sub(pattern, "↓↓", item.get("source_text"), flags = re.IGNORECASE)

        # 设置处理标志
        project["code_saver_processed"] = True

    # 文本后处理事件
    def on_postprocess_text(self, event: str, configurator: Configurator, data: dict, items: list[dict], project: list[dict]) -> None:
        # 检查数据是否已经被插件处理过
        if project.get("code_saver_processed", False) == False:
            return

        print("")
        print("[CodeSaver] 开始执行后处理 ...")
        print("")

        # 还原文本
        result = {
            "占位符残留": {},
        }
        target_items = [v for v in items if v.get("translation_status", 0) == 1]
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

            # 还原前缀和后缀代码段
            item["translated_text"] = (
                "".join(item.get("code_saver_prefix_codes", []))
                + item.get("translated_text", "")
                + "".join(item.get("code_saver_suffix_codes", []))
            )

            # 如果以上均匹配失败，则加入失败条目列表中
            if success == False:
                result.setdefault("占位符残留", {})[item.get("source_text", "")] = item.get("translated_text", "")
            else:
                # 检查是否存在代码段丢失
                source_text = re.sub(r"\\N{1,2}\[\d+\]", " ", item.get("source_text", ""), flags = re.IGNORECASE)
                translated_text = item.get("translated_text", "")
                for code in self.CODE_PATTERN_NUM_MATCH:
                    if source_text.count(code) != translated_text.count(code):
                        result.setdefault(f"数量不匹配 - {code}", {})[item.get("source_text", "")] = item.get("translated_text", "")

        # 将还原失败的条目写入文件
        result_path = f"{configurator.label_output_path}/code_saver_result.json"
        with open(result_path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(result, indent = 4, ensure_ascii = False))

        # 计算数量
        # failure_count = len({k for v in result.values() if isinstance(v, dict) for k in v.keys()})
        failure_count = len(result.get("占位符残留", {}))
        success_count = len(target_items) - failure_count

        print("")
        print(
            f"[CodeSaver] 代码还原已完成，"
            + f"成功 [green]{success_count}[/] 条，"
            + f"失败 [green]{failure_count}[/] 条，"
            + f"成功率 [green]{(success_count / max(1, len(target_items)) * 100):.2f}[/] % ..."
            + "\n"
            + f"[CodeSaver] 检查结果已写入 [green]{result_path}[/] 文件，请检查结果并进行手工修正 ..."
        )
        print("")

    # 加载角色数据
    def load_names(self, path: str) -> tuple[dict, dict]:
        names = {}
        nicknames = {}

        if os.path.exists(path):
            with open(path, "r", encoding = "utf-8") as reader:
                for item in json.load(reader):
                    if isinstance(item, dict):
                        id = item.get("id", -1)

                        if not isinstance(id, int):
                            continue

                        names[id] = item.get("name", "")
                        nicknames[id] = item.get("nickname", "")

        return names, nicknames

    # 执行替换
    def do_replace(self, match: re.Match, names: dict) -> str:
        i = int(match.group(1))

        # 索引在范围内则替换，不在范围内则原文返回
        if i in names:
            return names.get(i, "")
        else:
            return match.group(0)

    # 还原角色代码
    def replace_name_code(self, text: str, names: dict, nicknames: dict) -> str:
        # 根据 actors 中的数据还原 角色代码 \N[123] 实际指向的名字
        text = re.sub(
            r"\\n\[(\d+)\]",
            lambda match: self.do_replace(match, names),
            text,
            flags = re.IGNORECASE
        )

        # 根据 actors 中的数据还原 角色代码 \NN[123] 实际指向的名字
        text = re.sub(
            r"\\nn\[(\d+)\]",
            lambda match: self.do_replace(match, nicknames),
            text,
            flags = re.IGNORECASE
        )

        return text