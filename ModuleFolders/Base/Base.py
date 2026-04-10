from ModuleFolders.Base.EventManager import EventManager


# 事件列表
class Event:
    API_TEST_DONE = 100                             # API 测试完成
    API_TEST_START = 101                            # API 测试开始

    TASK_START = 210                                # 翻译开始
    TASK_UPDATE = 220                               # 翻译状态更新
    TASK_STOP = 230                                 # 翻译停止
    TASK_STOP_DONE = 231                            # 翻译停止完成
    TASK_COMPLETED = 232                            # 翻译完成
    TASK_CONTINUE_CHECK = 240                       # 继续翻译状态检查
    TASK_CONTINUE_CHECK_DONE = 241                  # 继续翻译状态检查完成
    TASK_MANUAL_EXPORT = 250                        # 翻译结果手动导出
    TASK_MANUAL_SAVE_CACHE = 251                    # 手动保存缓存文件

    CACHE_FILE_AUTO_SAVE = 300                      # 缓存文件自动保存

    APP_UPDATE_CHECK: int = 600                     # 检查更新
    APP_UPDATE_CHECK_DONE: int = 610                # 检查更新完成
    APP_UPDATE_DOWNLOAD: int = 620                  # 下载应用
    APP_UPDATE_DOWNLOAD_UPDATE: int = 630           # 下载应用更新

    GLOSS_TASK_START = 700                          # 术语表翻译开始
    GLOSS_TASK_DONE = 701                           # 术语表翻译完成

    ANALYSIS_TASK_START = 720                       # 分析任务开始
    ANALYSIS_TASK_UPDATE = 721                      # 分析任务更新
    ANALYSIS_TASK_DONE = 722                        # 分析任务完成

    TABLE_TRANSLATE_START = 800                     # 表格翻译开始
    TABLE_TRANSLATE_DONE = 801                      # 表格翻译完成
    TABLE_POLISH_START = 810                        # 表格润色开始
    TABLE_POLISH_DONE = 811                         # 表格润色完成
    TABLE_PROOFREAD_START = 820                     # 表格校对开始
    TRANSLATION_CHECK_START = 840                   # 语言检查开始

    TABLE_BASIC_DONE = 885                          # 基础表格任务完成
    TABLE_SEARCH_DONE = 886                         # 搜索结果表格任务完成
    TABLE_LANGUAGE_CHECK_DONE = 887                 # 语言检查结果表格任务完成
    TABLE_RULE_CHECK_DONE = 888                     # 规则检查结果表格任务完成
    TABLE_TERMINOLOGY_CHECK_DONE = 889              # 术语检查结果表格任务完成
    TABLE_BASIC_UPDATE = 890                        # 基础表格更新
    TABLE_SEARCH_UPDATE = 891                       # 搜索结果表格更新
    TABLE_LANGUAGE_CHECK_UPDATE = 892               # 语言检查结果表格更新
    TABLE_RULE_CHECK_UPDATE = 893                   # 规则检查结果表格更新
    TABLE_TERMINOLOGY_CHECK_UPDATE = 894            # 术语检查结果表格更新
    TABLE_UPDATE = 898                              # 表格更新（兼容旧事件）
    TABLE_FORMAT = 899                              # 表格重排

    APP_SHUT_DOWN = 99999                           # 应用关闭


# 软件运行状态列表
class Status:
    IDLE = 1000                                     # 无任务
    TASKING = 1001                                  # 任务中
    STOPING = 1002                                  # 停止中
    TASKSTOPPED = 1003                              # 任务已停止

    API_TEST = 2000                                 # 接口测试中
    GLOSS_TASK = 3000                               # 术语表翻译中
    ANALYSIS_TASK = 3500                            # 分析任务中
    TABLE_TASK = 4001                               # 表格任务中


class Base:
    # 事件列表
    EVENT = Event()
    STATUS = Status()
    work_status = STATUS.IDLE

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not hasattr(self, "default"):
            self.default = {}
        self._ensure_event_subscription_state()

    # 触发事件
    def emit(self, event: int, data: dict) -> None:
        self._ensure_event_subscription_state()
        self.event_manager_singleton.emit(event, data)

    # 订阅事件
    def subscribe(self, event: int, hanlder: callable) -> None:
        self._ensure_event_subscription_state()
        self.event_manager_singleton.subscribe(event, hanlder)
        self._event_subscriptions.append((event, hanlder))

    # 取消订阅事件
    def unsubscribe(self, event: int, hanlder: callable) -> None:
        self._ensure_event_subscription_state()
        self.event_manager_singleton.unsubscribe(event, hanlder)
        try:
            self._event_subscriptions.remove((event, hanlder))
        except ValueError:
            pass

    def _cleanup_event_subscriptions(self) -> None:
        if not self._event_subscriptions:
            return

        for event, hanlder in list(self._event_subscriptions):
            self.event_manager_singleton.unsubscribe(event, hanlder)

        self._event_subscriptions.clear()

    def _ensure_event_subscription_state(self) -> None:
        if not hasattr(self, "event_manager_singleton"):
            self.event_manager_singleton = EventManager.get_singleton()

        if not hasattr(self, "_event_subscriptions"):
            self._event_subscriptions = []

        if not hasattr(self, "_destroyed_subscription_cleanup"):
            self._destroyed_subscription_cleanup = None

        if getattr(self, "_destroyed_subscription_connected", False):
            return

        destroyed_signal = getattr(self, "destroyed", None)
        if hasattr(destroyed_signal, "connect"):
            self._destroyed_subscription_cleanup = lambda *_: self._cleanup_event_subscriptions()
            destroyed_signal.connect(self._destroyed_subscription_cleanup)
            self._destroyed_subscription_connected = True
