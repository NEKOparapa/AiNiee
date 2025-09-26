import json
from pathlib import Path

from ModuleFolders.Cache.CacheFile import CacheFile
from ModuleFolders.Cache.CacheProject import ProjectType
from ModuleFolders.FileOutputer.BaseWriter import (
    BaseTranslatedWriter,
    OutputConfig,
    PreWriteMetadata
)


class TransWriter(BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def on_write_translated(
        self, translation_file_path: Path, cache_file: CacheFile,
        pre_write_metadata: PreWriteMetadata,
        source_file_path: Path = None,
    ):
        trans_content = json.loads(source_file_path.read_text(encoding="utf-8"))
        for item in cache_file.items:
            file_category = item.get_extra("file_category", "")
            data_index = item.get_extra("data_index", "")
            tags = item.get_extra("tags", None)
            new_translation = item.final_text
            name = item.get_extra("name", "")

            # 导航并更新，带有检查
            if file_category not in trans_content["project"]["files"]:
                print(f"[警告] 文件类别 '{file_category}' 在目标文件中不存在，跳过该项目。")
                continue
            
            category_data = trans_content["project"]["files"][file_category]
            data_list = category_data["data"]
            tags_list = category_data.get("tags") # 如果 "tags" 不存在，返回 None

            # 检查 data_index 是否为有效整数且在 data_list 的范围内
            if not isinstance(data_index, int) or not (0 <= data_index < len(data_list)):
                print(f"[警告] 检测到无效或越界的 data_index ({data_index})，将跳过此项目。")
                print(f"       文件类别: {file_category}, 列表长度: {len(data_list)}")
                # 尝试输出上一个索引的文本
                try:
                    if data_index > 0:
                        print(f"       上一个索引的文本: {data_list[data_index - 1]}")
                except IndexError:
                    pass  
                
                continue # 跳过当前循环，处理下一个 item

            # 补充或者创建一样长度的tags列表，与文本列表长度一致
            tags_list = self.align_lists(data_list, tags_list)
            # 将更新后的 tags_list 写回 category_data，以防 align_lists 创建了新的列表
            category_data["tags"] = tags_list

            # 如果有人名信息
            if name:
                # 分割人名与文本
                name, new_translation = self.extract_strings(name, new_translation)

            # 仅当翻译实际改变时才写入，译文文本在第二个元素
            if len(data_list[data_index]) > 1:  # 检查长度是否至少为2,保证有译文位置
                if data_list[data_index][1] != new_translation:
                    data_list[data_index][1] = new_translation
            else:
                # 处理列表只有一个元素或没有元素的情况
                data_list[data_index].append(new_translation)

            # 写回颜色标签
            tags_list[data_index] = tags

        # 写回修改后的内容
        json_content = json.dumps(trans_content, ensure_ascii=False, indent=4)
        translation_file_path.write_text(json_content, encoding="utf-8")

    def extract_strings(self, name, dialogue):
        # 验证数据类型
        if not isinstance(dialogue, str) or not isinstance(name, str):
            return name, dialogue

        # 仅当对话以"["开头时才处理
        if not dialogue.startswith("["):
            return name, dialogue

        end_pos = -1  # 初始化结束位置为-1（表示未找到）

        # 优先策略：尝试匹配与原name嵌套层级一致的"]"
        # 这种策略可以正确处理 [[英雄]惊讶] 这样的情况
        count_in_name = name.count("]")
        required_closing_brackets = count_in_name + 1
        
        search_start_pos = 0
        temp_end_pos = -1
        found_brackets = 0
        for _ in range(required_closing_brackets):
            # 从上一个找到的位置之后开始搜索
            pos = dialogue.find("]", search_start_pos)
            if pos == -1:
                # 如果找不到足够数量的"]"，说明优先策略失败
                found_brackets = -1  # 标记为失败
                break
            temp_end_pos = pos
            found_brackets += 1
            search_start_pos = pos + 1
        
        # 如果优先策略成功，则使用其结果
        if found_brackets == required_closing_brackets:
            end_pos = temp_end_pos

        # 回退策略：如果优先策略失败 (end_pos 仍然是 -1)，则回退为查找第一个 "]"
        if end_pos == -1:
            end_pos = dialogue.find("]")

        # 如果最终找到了一个有效的结束位置（无论是通过优先策略还是回退策略）
        # end_pos > 0 确保了不是空名字，如 "[]text"
        if end_pos > 0:
            extracted_name = dialogue[1:end_pos]
            remaining_dialogue = dialogue[end_pos + 1:].lstrip()
            return extracted_name, remaining_dialogue

        # 如果两种策略都失败了（例如，对话是"["但没有"]"），则返回原值
        return name, dialogue


    def align_lists(self, data_list, tags_list):
        # 如果 tags_list 是 None，初始化为空列表
        if tags_list is None:
            tags_list = []
        
        # 计算需要补充的 None 的个数
        diff = len(data_list) - len(tags_list)
        if diff > 0:
            # 如果 data_list 更长，补充 None 到 tags_list
            tags_list.extend([None] * diff)
        return tags_list

    @classmethod
    def get_project_type(self):
        return ProjectType.TRANS
