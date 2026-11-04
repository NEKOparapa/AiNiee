import copy
import re
import threading
import urllib.request
from urllib.parse import urlsplit, urlunsplit

import rapidjson as json

from Backend.core.base import Base
from Backend.core.config import ConfigMixin, get_config_snapshot
from Backend.core.headers import normalize_extra_headers
from Backend.domain.config.tables import TableConfigHelper
from Backend.domain.config.request_defaults import normalize_request_timeouts
from Backend.domain.config.platform_concurrency import normalize_platform_concurrency, validate_thread_count
from Backend.core.paths import auto_output_dir
from Backend.core.log import LogMixin
from Backend.infrastructure.llm.auto_concurrency import (
    AutoConcurrency, MAX_AUTO_CONCURRENCY, initial_concurrency, validate_rpm,
)


# 接口请求器
class TaskConfig(ConfigMixin, LogMixin, Base):
    # 打印时的类型过滤器
    TYPE_FILTER = (int, str, bool, float, list, dict, tuple)
    # 支持按不同功能角色绑定接口，未命中时统一回退到 active
    SUPPORTED_INTERFACE_ROLES = {"active", "extract", "translate", "polish", "proofread"}
    API_ROLE_KEYS = ("extract", "translate", "polish", "proofread")
    API_SETTINGS_MIGRATION_KEY = "_active_follow_migration_done"

    def __init__(self) -> None:
        super().__init__()

        # 初始化实例级线程锁、接口角色和密钥索引
        self._config_lock = threading.Lock()
        self._api_key_lock = threading.Lock()
        self.interface_role = "active"
        self.prepared_interface_role = None
        self.apikey_index = 0
        self.apikey_list = []
        self._auto_concurrency = None
        self.project_characters_data = []
        self.project_terms_data = []
        self.project_non_translate_data = []

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.get_vars()})"

    def get_vars(self) -> dict:
        return {
            key: value
            for key, value in vars(self).items()
            if isinstance(value, __class__.TYPE_FILTER)
        }

    def _normalize_project_table_rows(
        self,
        rows,
        key_field: str,
        fields_to_keep: tuple[str, ...],
    ) -> list[dict]:
        normalized_rows = []

        if not isinstance(rows, list):
            return normalized_rows

        for row in rows:
            if not isinstance(row, dict):
                continue

            identity_value = str(row.get(key_field, "")).strip()
            if not identity_value:
                continue

            normalized_row = {}
            for field_name in fields_to_keep:
                normalized_row[field_name] = str(row.get(field_name, "") or "").strip()

            normalized_rows.append(normalized_row)

        return normalized_rows

    # 载入项目表数据（角色表、术语表、禁翻表）到内存，供 PromptBuilder 构建提示词时使用
    def load_project_table_data(self, cache_manager) -> None:
        self.project_characters_data = []
        self.project_terms_data = []
        self.project_non_translate_data = []

        if cache_manager is None or not hasattr(cache_manager, "get_analysis_data"):
            return

        analysis_data = cache_manager.get_analysis_data() or {}
        if not isinstance(analysis_data, dict):
            return

        self.project_characters_data = self._normalize_project_table_rows(
            analysis_data.get("characters", []),
            "source",
            ("source", "recommended_translation", "gender", "note"),
        )
        self.project_terms_data = self._normalize_project_table_rows(
            analysis_data.get("terms", []),
            "source",
            ("source", "recommended_translation", "category_path", "note"),
        )
        self.project_non_translate_data = self._normalize_project_table_rows(
            analysis_data.get("non_translate", []),
            "marker",
            ("marker", "category", "note"),
        )

    # 规范化接口角色名称，非法值统一回退到 active
    def _normalize_interface_role(self, interface_role: str | None) -> str:
        role = str(interface_role or "").strip().lower()
        if role in self.SUPPORTED_INTERFACE_ROLES:
            return role
        return "active"

    # 检查平台标签是否存在于当前平台配置中
    def _is_valid_platform_tag(self, tag, platforms: dict) -> bool:
        return bool(tag) and tag in platforms

    # 规范化接口角色绑定配置，同时兼容旧版 translate / polish 双接口配置
    def _normalize_api_settings(self, config: dict, persist: bool = False) -> dict:
        platforms = config.get("platforms", {}) or {}
        api_settings = config.setdefault("api_settings", {})
        original_api_settings = dict(api_settings)

        active_tag = api_settings.get("active")
        if not self._is_valid_platform_tag(active_tag, platforms):
            active_tag = None
            for role in self.API_ROLE_KEYS:
                role_tag = api_settings.get(role)
                if self._is_valid_platform_tag(role_tag, platforms):
                    active_tag = role_tag
                    break

        api_settings["active"] = active_tag

        if not api_settings.get(self.API_SETTINGS_MIGRATION_KEY):
            if active_tag is not None and all(api_settings.get(role) == active_tag for role in self.API_ROLE_KEYS):
                for role in self.API_ROLE_KEYS:
                    api_settings[role] = None
            api_settings[self.API_SETTINGS_MIGRATION_KEY] = True

        for role in self.API_ROLE_KEYS:
            role_tag = api_settings.get(role)
            if not self._is_valid_platform_tag(role_tag, platforms):
                api_settings[role] = None

        if persist and not getattr(self, "_snapshot_mode", False) and original_api_settings != api_settings:
            return self.save_config(config)

        return config

    # 根据功能角色解析目标接口：优先取角色绑定，取不到则回退到 active
    def resolve_platform_tag_for_role(self, interface_role: str | None = None) -> str | None:
        role = self._normalize_interface_role(interface_role or getattr(self, "interface_role", "active"))
        api_settings = getattr(self, "api_settings", {}) or {}
        platforms = getattr(self, "platforms", {}) or {}

        active_tag = api_settings.get("active")
        if not self._is_valid_platform_tag(active_tag, platforms):
            active_tag = None

        if role == "active":
            return active_tag

        role_tag = api_settings.get(role)
        if self._is_valid_platform_tag(role_tag, platforms):
            return role_tag

        return active_tag

    # 线程安全地轮询获取 API Key
    def get_next_apikey(self) -> str:
        with self._api_key_lock:
            if not self.apikey_list:
                return "no_key_required"

            # 边界检查
            if self.apikey_index >= len(self.apikey_list):
                self.apikey_index = 0

            key = self.apikey_list[self.apikey_index]

            # 更新索引（如果还有下一个 key，则递增，否则归零）
            if len(self.apikey_list) > 1:
                self.apikey_index = (self.apikey_index + 1) % len(self.apikey_list)

            return key

    # 读取配置文件，并记录当前任务要使用的接口角色
    def initialize(self, interface_role: str = "active") -> None:
        self._snapshot_mode = get_config_snapshot() is not None
        self.interface_role = self._normalize_interface_role(interface_role)
        self.prepared_interface_role = None
        self.target_platform = None
        self.model = None
        self.base_url = ""
        self.apikey_index = 0
        self.apikey_list = []

        config = self._normalize_api_settings(self.load_config(), persist=True)
        normalize_request_timeouts(config)
        normalize_platform_concurrency(config)
        if self._snapshot_mode:
            self._source_snapshot = copy.deepcopy(config)

        # 将字典中的每一项赋值到类中的同名属性
        for key, value in config.items():
            setattr(self, key, value)

        TableConfigHelper.apply_runtime_snapshot(self)

    @classmethod
    def read_snapshot(cls) -> dict:
        """Read configuration without migration, normalization writes or backups."""
        snapshot = get_config_snapshot()
        if snapshot is not None:
            normalize_request_timeouts(snapshot)
            normalize_platform_concurrency(snapshot)
            return snapshot

        from Backend.core.paths import config_path
        from Backend.infrastructure.config.defaults import get_defaults
        from Backend.infrastructure.config.store import ConfigStore

        result = get_defaults()
        with ConfigStore.CONFIG_FILE_LOCK:
            path = config_path()
            if path.exists():
                with path.open("r", encoding="utf-8") as reader:
                    saved = json.load(reader)
                if not isinstance(saved, dict):
                    raise ValueError("配置根节点必须是对象")
                result.update(saved)
        normalize_request_timeouts(result)
        normalize_platform_concurrency(result)
        return copy.deepcopy(result)

    @classmethod
    def from_snapshot(cls, snapshot: dict, interface_role: str = "translate", provider_id: str | None = None,
                      *, user_thread_counts: int | None = None):
        """Resolve an operation-owned configuration; never save global settings."""
        from Backend.infrastructure.config.defaults import get_defaults
        from Backend.domain.config.prompt_selection import TranslationPromptConfigHelper
        from Backend.domain.text.regex import RegexSwitchHelper

        instance = cls()
        instance._snapshot_mode = True
        instance.interface_role = instance._normalize_interface_role(interface_role)
        instance.prepared_interface_role = None
        values = get_defaults()
        values.update(copy.deepcopy(snapshot))
        normalize_platform_concurrency(values)
        RegexSwitchHelper.normalize_config(values)
        TableConfigHelper.normalize_config(values)
        TranslationPromptConfigHelper.normalize_config(values)
        values = instance._normalize_api_settings(values, persist=False)
        if provider_id is not None:
            if provider_id not in values.get("platforms", {}):
                raise ValueError("指定的 provider_id 不存在")
            values["api_settings"][instance.interface_role] = provider_id
        if user_thread_counts is not None:
            # Explicit REST/MCP overrides apply only to this operation's selected
            # provider copy; saved provider settings and other roles stay intact.
            validate_thread_count(user_thread_counts)
            target = values["api_settings"].get(instance.interface_role) or values["api_settings"].get("active")
            if target is not None:
                values["platforms"][target]["user_thread_counts"] = user_thread_counts
        instance._source_snapshot = copy.deepcopy(values)
        for key, value in values.items():
            if not key.startswith("_"):
                setattr(instance, key, value)
        TableConfigHelper.apply_runtime_snapshot(instance)
        instance.prepare_for_active_platform(instance.interface_role)
        return instance

    # API_URL 自动处理方法
    def process_api_url(self, raw_url: str, target_platform: str, auto_complete: bool, api_format: str = "") -> str:
        if not raw_url:
            return ""

        # 1. 基础清洗
        url = raw_url.strip().rstrip("/")

        # 2. 裁剪冗余后缀
        # 允许输入如: http://127.0.0.1:5000/v1/chat/completions -> 裁剪为 -> http://127.0.0.1:5000/v1
        redundant_suffixes = ["/chat/completions", "/completions", "/chat"]
        for suffix in redundant_suffixes:
            if url.endswith(suffix):
                url = url[:-len(suffix)]
                url = url.rstrip("/")  # 再次去除可能暴露出来的斜杠
                break

        # 3. 判断是否为 Anthropic 格式（平台名称或接口格式）
        is_anthropic = (
            target_platform.lower() == "anthropic"
            or api_format.lower() == "anthropic"
        )

        # 4. 版本号后缀列表
        version_suffixes = ["/v1", "/v2", "/v3", "/v4", "/v5", "/v6"]

        # 5. Anthropic 格式特殊处理
        # Anthropic SDK 会自动拼接 /v1/messages，所以需要去掉用户输入的版本号
        if is_anthropic and auto_complete:
            for suffix in version_suffixes:
                if url.endswith(suffix):
                    url = url[:-len(suffix)]
                    url = url.rstrip("/")
                    break

            # Anthropic 不需要补全 /v1，直接返回
            return url

        # 6. 非 Anthropic 的自动补全 /v1 逻辑
        # 某些平台强制补全，或者配置开启了 auto_complete
        is_local_or_sakura = target_platform.startswith("sakura") or target_platform.startswith("LocalLLM")
        should_auto_complete = is_local_or_sakura or auto_complete
        if should_auto_complete and not any(url.endswith(suffix) for suffix in version_suffixes):
            url += "/v1"

        # 7. 返回处理后的 URL
        return url

    # 获取当前角色对应的接口标签，默认返回当前激活接口
    def get_active_platform_tag(self, interface_role: str | None = None) -> str | None:
        return self.resolve_platform_tag_for_role(interface_role)

    # 将接口绑定配置与平台列表重新同步，并在需要时回写到配置文件
    def sync_active_platform_settings(self) -> None:
        config = self._normalize_api_settings(self.load_config(), persist=True)
        self.api_settings = config.get("api_settings", {})
        self.platforms = config.get("platforms", {})

    # 准备当前角色对应的接口配置
    def prepare_for_active_platform(self, interface_role: str | None = None) -> None:
        self.interface_role = self._normalize_interface_role(interface_role or getattr(self, "interface_role", "active"))
        if not getattr(self, "_snapshot_mode", False):
            self.sync_active_platform_settings()

        # 获取目标平台
        self.target_platform = self.get_active_platform_tag(self.interface_role)
        self.prepared_interface_role = self.interface_role

        # 增加获取不到内容时的异常处理
        if self.target_platform is None:
            raise ValueError("当前配置文件中未设置可用接口，请到接口管理页面激活或绑定接口。")

        platform_data = self.platforms.get(self.target_platform, {})

        # 获取模型类型
        self.model = platform_data.get("model")

        # 分割密钥字符串
        api_key = platform_data.get("api_key")
        self.apikey_list = list(dict.fromkeys(
            key for key in re.sub(r"\s+", "", api_key or "").split(",") if key
        )) or ["no_key_required"]
        self.apikey_index = 0

        # 处理 API URL 和限额
        raw_url = platform_data.get("api_url", "")
        auto_complete_setting = platform_data.get("auto_complete", False)
        api_format = platform_data.get("api_format", "")
        self.base_url = self.process_api_url(raw_url, self.target_platform, auto_complete_setting, api_format)

        # 获取接口限额
        self.rpm_limit = validate_rpm(platform_data.get("rpm_limit", 4096))

        # 根据密钥数量给 RPM 限额翻倍
        self.rpm_limit = validate_rpm(self.rpm_limit * len(self.apikey_list))

        # 如果开启自动设置输出文件夹功能，设置为输入文件夹的平级目录
        if self.auto_set_output_path is True:
            self.label_output_path = auto_output_dir(self.label_input_path)

        # 保存新配置
        if not getattr(self, "_snapshot_mode", False):
            config = self.load_config()
            config["label_output_path"] = self.label_output_path
            self.save_config(config)

        # 按实际选中的接口计算并发，旧全局值不再参与任务设置。
        self.user_thread_counts = validate_thread_count(platform_data.get("user_thread_counts", 0))
        self.actual_thread_counts = self.thread_counts_setting(
            self.user_thread_counts,
            self.target_platform,
            self.rpm_limit,
        )

    # 自动计算实际请求线程数
    def thread_counts_setting(self, user_thread_counts, target_platform, rpm_limit) -> int:
        self._auto_concurrency = None
        # 如果用户指定了线程数，则使用用户指定的线程数
        if user_thread_counts > 0:
            return user_thread_counts

        # 如果是本地类接口，尝试访问 slots 数
        elif target_platform.startswith("sakura") or target_platform.startswith("LocalLLM"):
            num = self.get_llama_cpp_slots_num(self.platforms.get(target_platform).get("api_url"))
            slots = min(MAX_AUTO_CONCURRENCY, num) if num > 0 else 2
            self._auto_concurrency = AutoConcurrency(rpm_limit, self.request_timeout, fixed_limit=slots)
            source = "本地模型槽位" if num > 0 else "本地槽位探测失败，使用保守默认值"
            self.info(f"{source}：自动并发 {slots} 个 ...")

        # 如果用户没有指定线程数，则自动计算
        else:
            self._auto_concurrency = AutoConcurrency(rpm_limit, self.request_timeout)
            self.info(f"自动并发从 {self._auto_concurrency.initial_limit} 个开始，根据响应耗时调整，"
                      f"最多 {self._auto_concurrency.max_concurrency} 个，连续请求失败时降低并发 ...")

        return self._auto_concurrency.initial_limit

    @property
    def worker_thread_counts(self):
        """Pool capacity; automatic mode admits requests through its own gate."""
        return self._auto_concurrency.max_concurrency if self._auto_concurrency else self.actual_thread_counts

    def copy_prepared_concurrency(self, original):
        """Keep a prepared snapshot's policy without sharing live request state."""
        self.user_thread_counts = original.user_thread_counts
        self.actual_thread_counts = original.actual_thread_counts
        self.platforms[self.target_platform]["user_thread_counts"] = original.user_thread_counts
        self._source_snapshot["platforms"][self.target_platform]["user_thread_counts"] = original.user_thread_counts
        self._auto_concurrency = original._auto_concurrency.fresh() if original._auto_concurrency else None

    # 获取 llama.cpp 的 slots 数量，获取失败则返回 -1
    def get_llama_cpp_slots_num(self, url: str) -> int:
        try:
            parts = urlsplit(url)
            path = parts.path.rstrip("/").removesuffix("/v1") + "/slots"
            endpoint = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
            with urllib.request.urlopen(endpoint, timeout=2) as response:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, list) and data and all(isinstance(slot, dict) for slot in data):
                    return len(data)
        except Exception:
            pass
        return -1

    # 先按短请求估算初始并发，再由请求控制器根据实际耗时调整。
    def calculate_thread_count(self, rpm_limit):
        return initial_concurrency(rpm_limit)

    # 获取当前角色对应接口的配置信息包
    def get_active_platform_configuration(self, interface_role: str | None = None):
        role = self._normalize_interface_role(interface_role or getattr(self, "interface_role", "active"))
        target_platform = self.get_active_platform_tag(role)
        if target_platform is None:
            raise ValueError("当前配置文件中未设置可用接口，请到接口管理页面激活或绑定接口。")

        if (
            getattr(self, "target_platform", None) != target_platform
            or getattr(self, "prepared_interface_role", None) != role
        ):
            self.prepare_for_active_platform(role)

        platform_data = self.platforms.get(target_platform, {})

        params = {
            "target_platform": target_platform,
            "api_url": self.base_url,
            "api_key": self.get_next_apikey(),
            "api_format": platform_data.get("api_format"),
            "model_name": self.model,
            "region": platform_data.get("region", ""),
            "access_key": platform_data.get("access_key", ""),
            "secret_key": platform_data.get("secret_key", ""),
            "request_timeout": self.request_timeout,
            "temperature": platform_data.get("temperature"),
            "extra_body": platform_data.get("extra_body", {}),
            "extra_headers": normalize_extra_headers(platform_data.get("extra_headers")),
            "tls_switch": platform_data.get("tls_switch", False),
            "think_switch": platform_data.get("think_switch"),
            "think_depth": platform_data.get("think_depth"),
            "thinking_budget": platform_data.get("thinking_budget", -1),
            "thinking_level": platform_data.get("thinking_level", "high"),
        }

        if self._auto_concurrency is not None:
            params["_auto_concurrency"] = self._auto_concurrency
        return params
