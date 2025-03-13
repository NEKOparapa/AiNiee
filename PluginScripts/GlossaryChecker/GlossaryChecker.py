import os
import re
import json

from tqdm import tqdm
from rich import print

from PluginScripts.PluginBase import PluginBase
from ModuleFolders.Translator.TranslatorConfig import TranslatorConfig

class GlossaryChecker(PluginBase):

    ACTORS_PATH = "Actors.json"

    def __init__(self) -> None:
        super().__init__()

        self.name = "GlossaryChecker"
        self.description = (
            "术语表检查器，在翻译完成后，检查术语表中的各个条目是否正确的生效"
            + "\n"
            + "兼容性：支持全部语言；支持全部模型；支持全部文本格式；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False      # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.LOW)
        self.add_event("postprocess_text", PluginBase.PRIORITY.LOW)

    def on_event(self, event: str, config: TranslatorConfig, data: list[dict]) -> None:
        # 检查数据有效性
        if isinstance(data, list) == False or len(data) < 2:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 如果指令词典未启用或者无内容，则跳过
        if (
            config.prompt_dictionary_switch == False
            or config.prompt_dictionary_data == None
            or len(config.prompt_dictionary_data) == 0
        ):
            return

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(event, config, data, items, project)

    # 文本后处理事件
    def on_postprocess_text(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        print("")
        print("[GlossaryChecker] 开始执行后处理 ...")
        print("")

        # 根据是否为 RPGMaker MV/MZ 文本来决定是否启用 角色代码还原 步骤
        names = []
        nicknames = []
        if any(re.search(r"\\n{1,2}\[\d+\]", v.get("source_text", ""), flags = re.IGNORECASE) for v in items):
            names, nicknames = self.load_names(f"{config.label_input_path}/{self.ACTORS_PATH}")

        # 生成词典
        glossary = {}
        for v in config.prompt_dictionary_data:
            glossary[v.get("src", "")] = v.get("dst", "")

        # 查找不匹配项目，查找范围限定在翻译状态为 已翻译 的条目内
        result = {}
        for item in tqdm([v for v in items if v.get("translation_status", 0) == 1]):
            source_text = item.get("source_text", "")
            translated_text = item.get("translated_text", "")

            # 还原角色代码
            source_text_replaced = self.replace_name_code(source_text, names, nicknames)

            # 依次检查每一个词典条目
            for k, v in glossary.items():
                if k in source_text_replaced and v not in translated_text:
                    result.setdefault(f"{k} -> {v}", {})[source_text] = translated_text

        # 写入文件
        result_path = f"{config.label_output_path}/指令词典检查_结果.json"
        with open(result_path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(result, indent = 4, ensure_ascii = False))

        # 输出结果
        print(f"")
        print(f"[GlossaryChecker] 指令词典检查已完成 ...")
        print(f"[GlossaryChecker] 检查结果已写入 [green]{result_path}[/] 文件，请检查结果并进行手工修正 ...")
        print(f"")

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