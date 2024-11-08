import json

from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase

class GlossaryChecker(PluginBase):

    def __init__(self):
        super().__init__()

        self.name = "GlossaryChecker"
        self.description = (
            "指令词典检查器，在翻译完成后检查指令词典中的各个条目是否正确的生效"
            + "\n"
            + "兼容性：支持全部语言；支持全部模型；支持全部文本格式；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = True      # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.LOWER)
        self.add_event("postprocess_text", PluginBase.PRIORITY.LOWER)

    def load(self):
        pass

    def on_event(self, event, configurator, data):
        # 检查数据有效性
        if event == None or len(event) <= 1:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 如果指令词典未启用或者无内容，则跳过
        if (
            configurator.prompt_dictionary_switch == False
            or configurator.prompt_dictionary_content == None
            or len(configurator.prompt_dictionary_content) == 0
        ):
            return

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(event, configurator, data, items, project)

    # 文本后处理事件
    def on_postprocess_text(self, event, configurator, data, items, project):
        print("")
        print("[GlossaryChecker] 开始执行后处理 ...")
        print("")

        # 生成词典
        glossary = {}
        for k, v in configurator.prompt_dictionary_content.items():
            glossary[k] = v.get("translation", "")

        # 查找不匹配项目，查找范围限定在翻译状态为 已翻译 的条目内
        result = {}
        for item in tqdm([v for v in items if v.get("translation_status", 0) == 1]):
            source_text = item.get("source_text", "")
            translated_text = item.get("translated_text", "")

            # 依次检查每一个词典条目
            for k, v in glossary.items():
                if k in source_text and v not in translated_text:
                    # 添加结果
                    if result.get(f"{k} -> {v}") == None:
                        result[f"{k} -> {v}"] = {}
                    result[f"{k} -> {v}"][source_text] = translated_text

        # 写入文件
        result_path = f"{configurator.label_output_path}/glossary_checker_result.json"
        with open(result_path, "w", encoding = "utf-8") as writer:
            writer.write(json.dumps(result, indent = 4, ensure_ascii = False))

        # 输出结果
        print("")
        print("[GlossaryChecker] 指令词典检查已完成 ...")
        print(f"[GlossaryChecker] 检查结果已写入 [green]{result_path}[/] 文件，请检查结果并进行手工修正 ...")
        print("")