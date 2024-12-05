import os
import re
import json

from tqdm import tqdm
from rich import print

from Plugin_Scripts.PluginBase import PluginBase
from Module_Folders.Translator.TranslatorConfig import TranslatorConfig

class CodeSaver(PluginBase):

    # 可能存在的空字符
    SPACE_PATTERN = r"\s*"

    # 用于英文的代码段规则
    CODE_PATTERN_EN = (
        SPACE_PATTERN + r"if\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # if(!s[982]) if(s[1623]) if(v[982] >= 1)
        SPACE_PATTERN + r"en\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # en(!s[982]) en(v[982] >= 1)
        SPACE_PATTERN + r"[/\\][a-z]{1,5}<[\d]{0,10}>" + SPACE_PATTERN,               # /C<1> \FS<12>
        SPACE_PATTERN + r"[/\\][a-z]{1,5}\[[\d]{0,10}\]" + SPACE_PATTERN,             # /C[1] \FS[12]
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=<.{0,10}>)" + SPACE_PATTERN,              # /C<非数字> /C<非数字> \FS<非数字> \FS<非数字> 中的前半部分
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=\[.{0,10}\])" + SPACE_PATTERN,            # /C[非数字] /C[非数字] \FS[非数字] \FS[非数字] 中的前半部分
    )

    # 用于非英文的代码段规则
    CODE_PATTERN_NON_EN = (
        SPACE_PATTERN + r"if\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # if(!s[982]) if(v[982] >= 1)
        SPACE_PATTERN + r"en\(.{0,5}[vs]\[\d+\].{0,10}\)" + SPACE_PATTERN,            # en(!s[982]) en(v[982] >= 1)
        SPACE_PATTERN + r"[/\\][a-z]{1,5}<[a-z\d]{0,10}>" + SPACE_PATTERN,            # /C<y> /C<1> \FS<xy> \FS<12>
        SPACE_PATTERN + r"[/\\][a-z]{1,5}\[[a-z\d]{0,10}\]" + SPACE_PATTERN,          # /C[x] /C[1] \FS[xy] \FS[12]
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=<.{0,10}>)" + SPACE_PATTERN,              # /C<非数字非字母> /C<非数字非字母> \FS<非数字非字母> \FS<非数字非字母> 中的前半部分
        SPACE_PATTERN + r"[/\\][a-z]{1,5}(?=\[.{0,10}\])" + SPACE_PATTERN,            # /C[非数字非字母] /C[非数字非字母] \FS[非数字非字母] \FS[非数字非字母] 中的前半部分
    )

    # 同时作用于英文于非英文的代码段规则
    CODE_PATTERN_COMMON = (
        SPACE_PATTERN + r"\\fr" + SPACE_PATTERN,                                      # 重置文本的改变
        SPACE_PATTERN + r"\\fb" + SPACE_PATTERN,                                      # 加粗
        SPACE_PATTERN + r"\\fi" + SPACE_PATTERN,                                      # 倾斜
        SPACE_PATTERN + r"\\\{" + SPACE_PATTERN,                                      # 放大字体 \{
        SPACE_PATTERN + r"\\\}" + SPACE_PATTERN,                                      # 缩小字体 \}
        SPACE_PATTERN + r"\\g" + SPACE_PATTERN,                                       # 显示货币 \G
        SPACE_PATTERN + r"\\\$" + SPACE_PATTERN,                                      # 打开金币框 \$
        SPACE_PATTERN + r"\\\." + SPACE_PATTERN,                                      # 等待0.25秒 \.
        SPACE_PATTERN + r"\\\|" + SPACE_PATTERN,                                      # 等待1秒 \|
        SPACE_PATTERN + r"\\!" + SPACE_PATTERN,                                       # 等待按钮按下 \!
        SPACE_PATTERN + r"\\>" + SPACE_PATTERN,                                       # 在同一行显示文字 \>
        # SPACE_PATTERN + r"\\<" + SPACE_PATTERN,                                     # 取消显示所有文字 \<
        SPACE_PATTERN + r"\\\^" + SPACE_PATTERN,                                      # 显示文本后不需要等待 \^
        # SPACE_PATTERN + r"\\n" + SPACE_PATTERN,                                     # 换行符 \\n
        SPACE_PATTERN + r"\r\n" + SPACE_PATTERN,                                      # 换行符 \r\n
        SPACE_PATTERN + r"\n" + SPACE_PATTERN,                                        # 换行符 \n
        SPACE_PATTERN + r"\\\\<br>" + SPACE_PATTERN,                                  # 换行符 \\<br>
        SPACE_PATTERN + r"<br>" + SPACE_PATTERN,                                      # 换行符 <br>
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
            + "兼容性：支持全部语言；支持全部模型，但在 Sakura 模型上效果最佳；仅支持 T++ 文本；"
        )

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.NORMAL)
        self.add_event("preproces_text", PluginBase.PRIORITY.NORMAL)
        self.add_event("postprocess_text", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TranslatorConfig, data: list[dict]) -> None:
        # 检查数据有效性
        if isinstance(data, list) == False or len(data) < 2:
            return

        # 初始化
        items = data[1:]
        project = data[0]

        # 限制文本格式
        if "t++" not in project.get("project_type", "").lower():
            return

        # 关闭内置的 保留句内换行符、保留首位非文本字符 功能
        config.preserve_line_breaks_toggle = False
        config.preserve_prefix_and_suffix_codes = False

        if event == "preproces_text":
            self.on_preproces_text(event, config, data, items, project)

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(event, config, data, items, project)

    # 文本预处理事件
    def on_preproces_text(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        # 检查数据是否已经被插件处理过
        if project.get("code_saver_processed", False) == True:
            return

        print("")
        print("[CodeSaver] 开始执行预处理 ...")
        print("")

        # 根据是否为 RPGMaker MV/MZ 文本来决定是否启用 角色代码还原 步骤
        names = []
        nicknames = []
        if any(re.search(r"\\n{1,2}\[\d+\]", v.get("source_text", ""), flags = re.IGNORECASE) for v in items):
            print("[CodeSaver] 判断为 [green]RPGMaker MV/MZ[/] 游戏文本 ...")
            names, nicknames = self.load_names(f"{config.label_input_path}/Actors.json")
            if len(names) + len(nicknames) > 0:
                print(f"[CodeSaver] [green]Actors.json[/] 文件加载成功，共加载 {len(names) + len(nicknames)} 条数据，稍后将执行 [green]角色代码还原[/] 步骤 ...")
                print("")
            else:
                print("[CodeSaver] 未在 [green]输入目录[/] 下找到 [green]Actors.json[/] 文件，将跳过 [green]角色代码还原[/] 步骤 ...")
                print("[CodeSaver] [green]角色代码还原[/] 步骤可以显著提升质量，建议添加 [green]Actors.json[/] 后重新开始 ...")
                print("[CodeSaver] [green]Actors.json[/] 文件一般可以在游戏目录的 [green]data[/] 或者 [green]www\\data[/] 文件夹内找到 ...")
                print("")

        # 根据原文语言生成正则表达式
        if "英语" in config.source_language:
            code_pattern = CodeSaver.CODE_PATTERN_EN
        else:
            code_pattern = CodeSaver.CODE_PATTERN_NON_EN
            
        agg_pattern = code_pattern + CodeSaver.CODE_PATTERN_COMMON
        
        common_pattern = re.compile(rf"(?:{"|".join(CodeSaver.CODE_PATTERN_COMMON)})+", re.IGNORECASE)
        
        pattern = re.compile(rf"(?:{"|".join(code_pattern)})+", re.IGNORECASE)
        
        prefix_pattern = re.compile(rf"^(?:{"|".join(agg_pattern)})+", re.IGNORECASE)
        suffix_pattern = re.compile(rf"(?:{"|".join(agg_pattern)})+$", re.IGNORECASE)

        # 查找代码段
        for item in tqdm(items):
            # 备份原文
            item["source_backup"] = item.get("source_text", "")

            # 还原角色代码
            item["source_text"] = self.replace_name_code(item.get("source_text"), names, nicknames)

            # 查找与替换前缀代码段
            item["code_saver_prefix_codes"] = prefix_pattern.findall(item.get("source_text"))
            item["source_text"] = prefix_pattern.sub("", item.get("source_text"))

            # 查找与替换后缀代码段
            item["code_saver_suffix_codes"] = suffix_pattern.findall(item.get("source_text"))
            item["source_text"] = suffix_pattern.sub("", item.get("source_text"))

            # 查找与替换主体代码段
            item["code_saver_codes"] = pattern.findall(item.get("source_text"))
            item["source_text"] = pattern.sub("↓↓", item.get("source_text"))
            
            item["code_saver_common_codes"] = common_pattern.findall(item.get("source_text"))
            item["source_text"] = common_pattern.sub("→→", item.get("source_text"))

        # 设置处理标志
        project["code_saver_processed"] = True

    # 文本后处理事件
    def on_postprocess_text(self, event: str, config: TranslatorConfig, data: list[dict], items: list[dict], project: dict) -> None:
        # 检查数据是否已经被插件处理过
        if project.get("code_saver_processed", False) == False:
            return

        print("")
        print("[CodeSaver] 开始执行后处理 ...")
        print("")

        # 筛选出需要处理的条目
        target_items = [v for v in items if v.get("translation_status", 0) == 1]

        # 还原文本
        result = {"占位符部分丢失":{}, "占位符全部丢失":{}, "代码数量不匹配":{}}
        for item in tqdm(target_items):
            # 还原原文
            item["source_text"] = item.get("source_backup", "")

            # 有时候模型会增加 ↓ 的数量，分别判断
            success = False
            cnt = 0
            success_common = False
            cnt_common = 0
            
            pattern = r"(?<!↓)(↓+)(?!↓)"  # 匹配孤立的箭头序列
            arrow_matches = re.findall(pattern, item.get("translated_text", ""))
            
            # 如果没有匹配的孤立箭头，跳过
            if arrow_matches:
                code_codes = item.get("code_saver_codes", [])
                code_len = len(code_codes)

                # 对比数量
                if len(arrow_matches) == code_len:
                    # 数量一致，逐个替换
                    
                    # 匹配成功标记
                    success = True
                    
                    for arrow, code in zip(arrow_matches, code_codes):
                        item["translated_text"] = item.get("translated_text", "").replace(arrow, code, 1)
                else:
                    # 数量不一致，尽可能多替换
                    cnt = min(len(arrow_matches), code_len)
                    for i in range(cnt):
                        item["translated_text"] = item.get("translated_text", "").replace(arrow_matches[i], code_codes[i], 1)
                # 可能会有残留，清理一下        
                item["translated_text"] = item.get("translated_text", "").replace("↓", "")
                
            common_pattern = r"(?<!→)(→+)(?!→)"  # 匹配孤立的箭头序列
            common_arrow_matches = re.findall(common_pattern, item.get("translated_text", ""))
            
            # 如果没有匹配的孤立箭头，跳过
            if common_arrow_matches:
                # 提取 code_saver_common_codes
                common_codes = item.get("code_saver_common_codes", [])
                common_len = len(common_codes)

                # 对比数量
                if len(common_arrow_matches) == common_len:
                    # 数量一致，逐个替换
                    
                    # 匹配成功标记
                    success_common = True
                    
                    for arrow, code in zip(common_arrow_matches, common_codes):
                        item["translated_text"] = item.get("translated_text", "").replace(arrow, code, 1)
                else:
                    # 数量不一致，尽可能多替换
                    cnt_common = min(len(common_arrow_matches), common_len)
                    for i in range(cnt_common):
                        item["translated_text"] = item.get("translated_text", "").replace(common_arrow_matches[i], common_codes[i], 1)
                # 可能会有残留，清理一下        
                item["translated_text"] = item.get("translated_text", "").replace("→", "")

            # 还原前缀和后缀代码段
            item["translated_text"] = (
                "".join(item.get("code_saver_prefix_codes", []))
                + item.get("translated_text", "")
                + "".join(item.get("code_saver_suffix_codes", []))
            )

            # 检查是否存在代码段丢失
            if not success or not success_common:
                if not success:
                    if len(item.get("code_saver_codes", [])) == 0:
                        pass
                    elif cnt == 0:
                        result["占位符全部丢失"][item.get("source_text", "")] = item.get("translated_text", "")
                    elif cnt > 0:
                        result["占位符部分丢失"][item.get("source_text", "")] = item.get("translated_text", "")
                        
                if not success_common:
                    if len(item.get("code_saver_codes", [])) == 0:
                        pass
                    elif cnt_common == 0:
                        result["占位符全部丢失"][item.get("source_text", "")] = item.get("translated_text", "")
                    elif cnt_common > 0:
                        result["占位符部分丢失"][item.get("source_text", "")] = item.get("translated_text", "")
            else:
                source_text = re.sub(r"\\N{1,2}\[\d+\]", " ", item.get("source_text", ""), flags = re.IGNORECASE)
                translated_text = item.get("translated_text", "")
                for code in CodeSaver.CODE_PATTERN_NUM_MATCH:
                    if source_text.count(code) != translated_text.count(code):
                        result["代码数量不匹配"].setdefault(f"{code}", {})[item.get("source_text", "")] = item.get("translated_text", "")

        # 将还原失败的条目写入文件
        for k, v in result.items():
            result_path = f"{config.label_output_path}/代码救星_结果_{k}.json"
            with open(result_path, "w", encoding = "utf-8") as writer:
                writer.write(json.dumps(v, indent = 4, ensure_ascii = False))

        # 计算数量
        failure_count = sum(len(v) for k,v in result.items() if "占位符" in k)
        success_count = len(target_items) - failure_count

        print("")
        print(
            "[CodeSaver] 代码还原已完成，"
            + f"成功 [green]{success_count}[/] 条，"
            + f"失败 [green]{failure_count}[/] 条，"
            + f"成功率 [green]{(success_count / max(1, len(target_items)) * 100):.2f}[/] % ..."
            + "\n"
            + f"[CodeSaver] 代码还原结果已写入 [green]{config.label_output_path}[/] 目录，请检查结果并进行手工修正 ..."
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
