import json
import re
from pathlib import Path


class NameExtractor:
    def __init__(self):
        # 初始化代码
        pass


    def extract_names_from_trans(self,file_path: Path) -> set:
        """
        从 .trans 文件（实际为JSON）中提取人名。
        """
        names = set()

        content = file_path.read_text(encoding="utf-8")
        trans_content = json.loads(content)

        if not isinstance(trans_content, dict) or "project" not in trans_content:
            return names
            
        project_data = trans_content.get("project", {})
        files_data = project_data.get("files", {})

        if not isinstance(files_data, dict):
            return names

        # 遍历每个文件类别（例如："data/Actors.json"）
        for file_category, category_data in files_data.items():
            if not isinstance(category_data, dict):
                continue # 跳过无效的类别数据

            parameters = category_data.get("parameters", [])  # 如果缺失，默认为空列表

            # 检查 parameters 是否是列表
            if not isinstance(parameters, list):
                continue

            # 遍历 parameters 列表中的每个元素
            for param_item in parameters:
                # 检查元素是否为列表 (根据示例，目标信息在内层列表中)
                if isinstance(param_item, list):
                    # 遍历内层列表中的每个字典
                    for sub_item in param_item:
                            # 检查内层元素是否为字典并包含 rowInfoText
                        if isinstance(sub_item, dict):
                            row_info_text = sub_item.get("rowInfoText", "")
                            if isinstance(row_info_text, str) and row_info_text.strip():
                                names.add(row_info_text.strip())

        return names

    def extract_names_from_rpy(self,file_path: Path) -> set:
        """
        从 .rpy 文件中提取 Character 定义中的人名。
        """
        names = set()
        # 正则表达式匹配 'define variable = Character("Name", ...)' 结构
        # 考虑了可能存在的空格和可选参数
        pattern = re.compile(r'^\s*define\s+\w+\s*=\s*Character\s*\(\s*"([^"]+)"')

        with file_path.open("r", encoding="utf-8-sig") as f: # 小心行头标识
            for line in f:
                match = pattern.match(line)
                if match:
                    name = match.group(1).strip()
                    if name: # 确保提取到的名字不是空字符串
                        names.add(name)
        return names

    def extract_names_from_json(self,file_path: Path) -> set:
        """
        从 .json 文件中提取人名，区分 VNText 和 RPG 两种类型。
        """
        names = set()

        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        # 检查是否为列表类型
        if not isinstance(data, list) or not data:
            return names

        first_valid_element = None
        for element in data:
            if element is not None:
                if isinstance(element, dict):
                    first_valid_element = element
                    break 

        if first_valid_element is None:
            return names

        is_vntext = False
        is_rpg = False

        if "message" in first_valid_element:
            is_vntext = True

        elif "id" in first_valid_element and "traits" in first_valid_element:
            is_rpg = True

        for item in data:
            if not isinstance(item, dict):
                continue

            if is_vntext:

                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    names.add(name.strip())

                names_list = item.get("names")
                if isinstance(names_list, list):
                    for n in names_list:
                        if isinstance(n, str) and n.strip():
                            names.add(n.strip())

            elif is_rpg:
                name = item.get("name")
                if isinstance(name, str) and name.strip():
                    names.add(name.strip())

        return names 




    def deduplicate_names(self,names_set: set) -> set:
        """
        对提取到的人名进行去重，并处理 '人名+数字' vs '人名' 的情况。
        规则：如果同时存在 "Name1" 和 "Name"，则只保留 "Name"。
        """
        final_names = set()
        # 用于快速查找基础名称（无数字后缀）是否存在
        base_names_present = set()

        # 先找出所有不带数字后缀的名字
        for name in names_set:
            match = re.match(r'^(.*?)(\d+)$', name)
            if not match: # 如果名字不以数字结尾
                final_names.add(name)
                base_names_present.add(name) # 记录这个基础名称

        # 再处理带数字后缀的名字
        for name in names_set:
            match = re.match(r'^(.*?)(\d+)$', name)
            if match: # 如果名字以数字结尾
                base_name = match.group(1)
                # 只有当其基础名称（去掉数字后缀的部分）不在集合中时，才添加带后缀的名字
                if base_name not in base_names_present:
                    final_names.add(name) # 添加原始带后缀的名字，例如 "Player1"

        return final_names


    def extract_names_from_folder(self,folder_path_str: str) -> list:
        """
        遍历指定文件夹及其子文件夹，提取所有支持文件类型中的人名信息。

        Args:
            folder_path_str: 文件夹的路径字符串。

        Returns:
            一个列表，每个元素是一个字典，格式为 {"src": name, "dst": "", "info": ""}。
        """
        folder_path = Path(folder_path_str)

        all_names = set()

        # 遍历文件夹中所有文件
        for item in folder_path.rglob('*'): # 递归遍历所有子目录
            if item.is_file():
                file_path = item
                file_extension = file_path.suffix.lower()
                extracted_set = set()

                # 处理单个文件
                try:
                    if file_extension == '.trans':
                        extracted_set = NameExtractor.extract_names_from_trans(self, file_path)

                    elif file_extension == '.rpy':
                        extracted_set = NameExtractor.extract_names_from_rpy(self, file_path)

                    elif file_extension == '.json':
                        extracted_set = NameExtractor.extract_names_from_json(self, file_path)

                    # 将提取到的人名更新进人名集合
                    if extracted_set:
                        all_names.update(extracted_set)

                except json.JSONDecodeError as json_err:
                    # 对无效的 JSON 文件给出更具体的警告
                    print(f"Warning: Skipping invalid JSON file '{file_path}': {json_err}")
                except Exception as e:
                    # 捕获处理单个文件时可能出现的其他错误
                    print(f"Warning: Error processing file '{file_path}': {e}")

        # 进行特殊去重
        deduplicated_names = NameExtractor.deduplicate_names(self, all_names)

        # 格式化输出
        output_list = [
            {"src": name, "dst": "", "info": ""}
            for name in sorted(list(deduplicated_names)) # 按字母排序以获得一致的输出
        ]

        return output_list