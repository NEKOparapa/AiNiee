import os
import traceback
import logging

from jtpp import Jr_Tpp, version
from ruamel.yaml import YAML


class MainApp:
    def __init__(self):
        """初始化主应用程序类."""
        self.config = self.read_config()  # 读取配置
        self.pj = None  # 初始化 Jr_Tpp 对象
        self.logger = self.setup_logger()  # 设置日志记录器
        self.print_version()  # 打印版本信息

    def print_version(self):
        """打印版本信息."""
        print(f"jtpp_{version}")
        print("main_v2.00")

    def setup_logger(self):
        """设置日志记录器."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        return logger

    def read_config(self):
        """读取配置文件 config.yaml."""
        config_path = "config.yaml"
        try:
            yaml = YAML(typ="safe")
            with open(config_path, "r", encoding="utf8") as f:
                config = yaml.load(f)

            # 规范化路径
            for key in [
                "game_path",
                "save_path",
                "translation_path",
                "output_path",
                "data_path",
            ]:
                config[key] = os.path.normpath(config.get(key, ""))

            # 确保配置项存在并提供默认值
            defaults = {
                "mark": 0,
                "NameWithout": [],
                "ReadCode": [],
                "BlackDir": [],
                "BlackCode": [],
                "BlackFiles": [],
                "codewithnames": [],
                "line_length": 40,
                "sumcode": [],
                "note_percent": 0.2,
                "ja": 1,
                "sptext": {},
                "auto_linefeed_js": "自动换行.js",
                "need2check_filename": "need2check.json",
                "project_data_dir": "data",
                "project_dir_name": "翻译工程文件",
            }
            for key, value in defaults.items():
                config.setdefault(key, value)

            return config

        except FileNotFoundError:
            print(f"错误：未找到配置文件 '{config_path}'。请确保文件存在。")
            exit(1)
        except Exception as e:
            print(f"读取配置文件时发生未知错误：{e}")
            print(traceback.format_exc())
            exit(1)

    def get_user_choice(self, prompt, valid_choices):
        """获取用户输入的选择，并验证选择是否有效."""
        while True:
            choice = input(prompt)
            if choice in valid_choices:
                return choice
            print("无效选择，请重试。")

    def run(self):
        """运行主程序."""
        start_page = (
            "1. 一键读取游戏数据并保存\n"
            "2. 加载翻译工程\n"
            "3. 游戏版本更新\n"
            "0. 退出\n"
        )
        start_keys = ["1", "2", "3", "0"]

        main_page = (
            "1. 一键注入翻译\n"
            "2. 保存翻译工程\n"
            "3. 加载翻译工程\n"
            "4. 导出翻译xlsx文件\n"
            "5. 重新加载配置文件\n"
            "0. 退出\n"
        )
        main_keys = ["1", "2", "3", "4", "5", "0"]

        try:
            while True:  # 初始菜单循环
                res = self.get_user_choice(start_page, start_keys)
                if res == "1":
                    self.one_click_read_and_save()
                    break  # 进入主菜单
                elif res == "3":
                    self.update_game_version()
                    break  # 进入主菜单
                elif res == "2":
                    self.load_project()
                    break  # 进入主菜单
                elif res == "0":
                    exit(0)

            while True:  # 主菜单循环
                res = self.get_user_choice(main_page, main_keys)
                if res == "1":
                    self.one_click_inject()
                elif res == "2":
                    self.save_project()
                elif res == "3":
                    self.load_project()
                elif res == "4":
                    self.export_translation()
                elif res == "5":
                    self.reload_config()
                elif res == "0":
                    break

        except Exception as e:
            print(traceback.format_exc())
            print(e)
            input("发生错误，请上报bug")

    def one_click_read_and_save(self):
        """一键读取游戏数据并保存."""
        self.pj = Jr_Tpp(self.config)
        self.pj.FromGame(
            self.config["game_path"], self.config["save_path"], self.config["data_path"]
        )
        input(
            "已成功读取游戏数据，提取到的名字保存在Name.json中\n"
            "请在翻译完名字以后，将其导入到ainiee的术语表中\n"
            f'然后翻译{os.path.join(self.config["save_path"], "data")}中的xlsx文件\n'
        )

    def update_game_version(self):
        """游戏版本更新."""
        self.pj = Jr_Tpp(self.config)
        self.pj.Update(
            self.config["game_path"],
            self.config["translation_path"],
            self.config["save_path"],
            self.config["data_path"],
        )

    def load_project(self):
        """加载翻译工程."""
        self.pj = Jr_Tpp(self.config, self.config["save_path"])

    def one_click_inject(self):
        """一键注入翻译."""
        if self.pj is None:
            print("请先加载翻译工程或读取游戏数据。")
            return
        self.pj.ToGame(
            self.config["game_path"],
            self.config["translation_path"],
            self.config["output_path"],
            self.config["mark"],
        )

    def save_project(self):
        """保存翻译工程."""
        if self.pj is None:
            print("请先加载翻译工程或读取游戏数据。")
            return
        self.pj.Save(self.config["save_path"])

    def export_translation(self):
        """导出翻译 xlsx 文件."""
        if self.pj is None:
            print("请先加载翻译工程或读取游戏数据。")
            return
        self.pj.Output(self.config["save_path"])

    def reload_config(self):
        """重新加载配置文件."""
        self.config = self.read_config()
        if self.pj:
            self.pj.ApplyConfig(self.config)
        print("已重新加载配置文件")


if __name__ == "__main__":
    app = MainApp()
    app.run()