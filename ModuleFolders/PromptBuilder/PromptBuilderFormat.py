import re
from types import SimpleNamespace

from Base.Base import Base
from ModuleFolders.TaskConfig.TaskConfig import TaskConfig
from ModuleFolders.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
class PromptBuilderFormat(Base):

    def __init__(self) -> None:
        super().__init__()

    # 获取提示词文本
    def get_system_default(config: TaskConfig) -> str:
        if getattr(PromptBuilderFormat, "format_system_zh", None) == None:
            with open("./Resource/Prompt/Format/format_system_zh.txt", "r", encoding = "utf-8") as reader:
                PromptBuilderFormat.format_system_zh = reader.read().strip()


        # 如果输入的是字典，则转换为命名空间
        if isinstance(config, dict):
            namespace = SimpleNamespace()
            for key, value in config.items():
                setattr(namespace, key, value)
            config = namespace


        # 构造结果
        result = PromptBuilderFormat.format_system_zh

        return result

    # 获取系统提示词
    def build_system(config: TaskConfig) -> str:
        PromptBuilderFormat.get_system_default(config)

        # 构造结果
        result = PromptBuilderFormat.format_system_zh


        return result

    # 构建原文
    def build_source_text(config: TaskConfig, source_text_dict: dict) -> str:

        source_text_str = "\n".join(source_text_dict.values())
        
        return source_text_str

    # 生成信息结构 - 通用
    def generate_prompt(config, source_text_dict: dict):
        # 储存指令
        messages = []
        # 储存额外日志
        extra_log = []


        # 基础系统提示词
        if config.format_prompt_selection["last_selected_id"]  == PromptBuilderEnum.FORMAT_COMMON:
            system = PromptBuilderFormat.build_system(config)
        else:
            system = config.polishing_prompt_selection["prompt_content"]  # 自定义提示词


        # 待排序原文
        source_text = PromptBuilderFormat.build_source_text(config,source_text_dict)


        # 用户提示词
        pre_prompt = "这是你接下来的排版任务，文本如下:\n"

        source_text_str = f"{pre_prompt}<textarea>\n{source_text}\n</textarea>"


        # 构建用户信息
        messages.append(
            {
                "role": "user",
                "content": source_text_str,
            }
        )

        return messages, system, extra_log
