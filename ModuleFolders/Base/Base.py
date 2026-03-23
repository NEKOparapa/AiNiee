from ModuleFolders.Base.EventManager import EventManager

# 事件列表
class Event():

    API_TEST_DONE = 100                             # API 测试完成
    API_TEST_START = 101                            # API 测试开始
    TASK_START = 210                         # 翻译开始
    TASK_UPDATE = 220                        # 翻译状态更新
    TASK_STOP = 230                          # 翻译停止
    TASK_STOP_DONE = 231                     # 翻译停止完成
    TASK_COMPLETED = 232                          # 翻译完成

    TASK_CONTINUE_CHECK = 240                # 继续翻译状态检查
    TASK_CONTINUE_CHECK_DONE = 241           # 继续翻译状态检查完成
    TASK_MANUAL_EXPORT = 250                 # 翻译结果手动导出
    TASK_MANUAL_SAVE_CACHE = 251             # 手动保存缓存文件
    CACHE_FILE_AUTO_SAVE = 300                      # 缓存文件自动保存


    APP_UPDATE_CHECK: int = 600                             # 检查更新
    APP_UPDATE_CHECK_DONE: int = 610                        # 检查更新完成
    APP_UPDATE_DOWNLOAD: int = 620                          # 下载应用
    APP_UPDATE_DOWNLOAD_UPDATE: int = 630                   # 下载应用更新

    GLOSS_TASK_START = 700                           # 术语表翻译 开始
    GLOSS_TASK_DONE = 701                            # 术语表翻译 完成

    TABLE_TRANSLATE_START = 800                      # 表格翻译 开始
    TABLE_TRANSLATE_DONE = 801                       # 表格翻译 完成
    TABLE_POLISH_START = 810                      # 表格润色 开始
    TABLE_POLISH_DONE = 811                      # 表格润色 完成    

    TERM_EXTRACTION_START = 830                  # 术语提取开始
    TERM_EXTRACTION_DONE = 831                     

    TERM_TRANSLATE_SAVE_START = 832              # 实体提取开始
    TERM_TRANSLATE_SAVE_DONE = 833 

    TRANSLATION_CHECK_START = 840                # 语言检查开始    

    TABLE_UPDATE = 898                             # 表格更新
    TABLE_FORMAT = 899                             # 表格重排

    APP_SHUT_DOWN = 99999                          # 应用关闭

# 软件运行状态列表
class Status():

    IDLE = 1000                                     # 无任务
    TASKING = 1001                                  # 任务中
    STOPING = 1002                                  # 停止中
    TASKSTOPPED = 1003                              # 任务已停止
    
    API_TEST = 2000                                 # 接口测试中
    GLOSS_TASK = 3000                               # 术语表翻译中
    TABLE_TASK = 4001                               # 表格任务中

class Base():

    # 事件列表
    EVENT = Event()
    STATUS = Status()
    work_status = STATUS.IDLE

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.default = {}
        self.event_manager_singleton = EventManager.get_singleton()

    # 触发事件
    def emit(self, event: int, data: dict) -> None:
        EventManager.get_singleton().emit(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable) -> None:
        EventManager.get_singleton().subscribe(event, hanlder)

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable) -> None:
        EventManager.get_singleton().unsubscribe(event, hanlder)
