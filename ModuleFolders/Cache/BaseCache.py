# AiNiee/ModuleFolders/Cache/BaseCache.py
import copy
import inspect
import threading
import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass, field, fields, is_dataclass
from reprlib import Repr
from typing import Any, ClassVar, Type, Union, get_args, get_origin, Optional, TypeVar, _GenericAlias
import types # 用于检查 UnionType

# 定义原子类型集合
_ATOMIC_TYPES = frozenset([
    bool,
    int,
    float,
    str,
])

# 定义 TypeVar 用于泛型
T = TypeVar('T')

class DictMixin:
    """提供 to_dict 和 from_dict 方法的 Mixin 类"""

    def _to_dict_part(self, obj: Any, keep_none: bool = False) -> Any:
        """递归地将对象部分转换为字典友好的格式"""
        if obj is None:
            # 根据 keep_none 决定是否保留 None 值
            return None if keep_none else obj #<-- 修正：keep_none 为 True 时应返回 None
        obj_type = type(obj)

        if obj_type in _ATOMIC_TYPES:
            # 基本数据类型直接返回
            return obj
        elif isinstance(obj, DictMixin):
            # 递归调用 to_dict
            return obj.to_dict(keep_none)
        elif isinstance(obj, tuple) and hasattr(obj, '_fields'):
            # NamedTuple: 递归处理每个字段，并转换为普通 tuple
            # 注意：NamedTuple 本身不是 DictMixin，所以按普通 tuple 处理
            return tuple(self._to_dict_part(item, keep_none) for item in obj)
        elif isinstance(obj, (list, tuple, set, frozenset)):
            # 集合类型：递归处理每个元素
            # 使用列表推导式或生成器表达式以提高效率
            return obj_type(self._to_dict_part(item, keep_none) for item in obj)
        elif isinstance(obj, dict):
            # 字典类型：递归处理键和值
            new_dict = {}
            for k, v in obj.items():
                # 假设键总是可以安全转换或已经是目标类型
                # JSON key 必须是 str，但这里保持灵活性
                key_part = self._to_dict_part(k, keep_none)
                value_part = self._to_dict_part(v, keep_none)
                # 仅当值不为 None 或需要保留 None 时添加
                if value_part is not None or keep_none:
                    new_dict[key_part] = value_part
            return new_dict
        else:
            # 其他类型，尝试深拷贝
            try:
                return copy.deepcopy(obj)
            except TypeError:
                # 对于无法深拷贝的对象，返回其字符串表示
                return str(obj)

    def to_dict(self, keep_none: bool = False) -> dict[str, Any]:
        """将 dataclass 实例转换为字典，处理 None 值"""
        result = {}
        # 确保只处理 dataclass 定义的字段
        defined_fields = {f.name for f in fields(self)}

        for name in defined_fields:
            if name.startswith("_"): # 跳过私有属性
                continue
            # 使用 getattr 安全获取属性值
            value = getattr(self, name, None)
            # 如果值为 None 且不保留 None，则跳过
            if value is None and not keep_none:
                continue

            # 递归转换属性值
            result[name] = self._to_dict_part(value, keep_none)
        return result

    @classmethod
    def _from_define(cls, type_: Type, data: Any) -> Any:
        """
        核心的反序列化方法，根据类型注解 type_ 将数据 data 转换为目标类型。
        增强了对 None、Optional、泛型容器和 dataclass 的处理。
        """
        origin = get_origin(type_)
        args = get_args(type_)

        # 1. 处理 None 数据
        if data is None:
            # 检查类型是否允许 None (Optional[T] or Union[T, None] or Any or NoneType)
            is_optional = (origin is Union or origin is types.UnionType) and type(None) in args
            is_any = type_ is Any
            is_none_type = type_ is type(None)

            if is_optional or is_any or is_none_type:
                return None
            else:
                # 如果目标类型严格不允许 None，则抛出错误
                raise TypeError(f"Type '{type_}' does not allow None, but received None data.")

        # 2. 处理泛型类型
        if origin is not None:
            if origin is Union or origin is types.UnionType: # Union 和 Optional
                possible_types = [arg for arg in args if arg is not type(None)]
                if len(possible_types) == 1 and type_ is Optional[possible_types[0]]:
                    # 特殊处理 Optional[T]，直接用 T 类型尝试解析
                    return cls._from_define(possible_types[0], data)
                else: # 处理普通的 Union[T1, T2, ...]
                    # 尝试用 Union 中的每种类型解析，返回第一个成功的
                    errors = []
                    for possible_type in possible_types:
                        try:
                            return cls._from_define(possible_type, data)
                        except (TypeError, ValueError) as e:
                            # 记录尝试失败的错误信息
                            errors.append(f"  - Tried '{possible_type}': {e}")
                    # 如果所有类型都尝试失败，抛出错误
                    raise TypeError(f"Data '{data}' (type: {type(data)}) did not match any type in Union '{type_}'. Errors:\n" + "\n".join(errors))

            elif issubclass(origin, list) and isinstance(data, list):
                if not args: raise TypeError(f"List type hint is missing argument: {type_}")
                item_type = args[0]
                # 列表推导式处理列表项
                return [cls._from_define(item_type, item) for item in data]

            elif issubclass(origin, set) and isinstance(data, (list, set)): # 允许从 list 初始化 set
                if not args: raise TypeError(f"Set type hint is missing argument: {type_}")
                item_type = args[0]
                # 集合推导式处理集合项
                return {cls._from_define(item_type, item) for item in data}

            elif issubclass(origin, frozenset) and isinstance(data, (list, set, frozenset)): # 允许从 list/set 初始化 frozenset
                if not args: raise TypeError(f"Frozenset type hint is missing argument: {type_}")
                item_type = args[0]
                return frozenset(cls._from_define(item_type, item) for item in data)

            elif issubclass(origin, tuple):
                if not args: raise TypeError(f"Tuple type hint is missing argument: {type_}")
                if not isinstance(data, (list, tuple)):
                     raise TypeError(f"Expected list or tuple for Tuple type '{type_}', got '{type(data)}'.")

                if len(args) == 2 and args[1] is Ellipsis: # tuple[T, ...]
                     item_type = args[0]
                     # 处理可变长度元组
                     return tuple(cls._from_define(item_type, item) for item in data)
                else: # tuple[T1, T2, ...]
                     if len(args) != len(data):
                          raise ValueError(f"Tuple type '{type_}' expects {len(args)} items, but data has {len(data)} items.")
                     # 处理固定长度元组
                     return tuple(cls._from_define(arg, item) for arg, item in zip(args, data))

            elif issubclass(origin, dict) and isinstance(data, dict):
                if len(args) != 2: raise TypeError(f"Dict type hint needs two arguments (Key, Value): {type_}")
                key_type, value_type = args
                new_dict = {}
                for k, v in data.items():
                    try:
                         # 递归处理键和值
                         new_key = cls._from_define(key_type, k)
                         new_value = cls._from_define(value_type, v)
                         new_dict[new_key] = new_value
                    except (TypeError, ValueError) as e:
                         # 包装错误信息
                         raise TypeError(f"Error processing dictionary item ('{k}': '{v}') for type '{type_}': {e}") from e
                return new_dict
            else:
                 # 不支持的泛型类型
                 raise TypeError(f"Unsupported generic type origin: {origin} in type hint '{type_}'.")

        # 3. 处理非泛型类型 (包括 dataclasses, NamedTuple, Any 等)
        elif inspect.isclass(type_):
            if type_ in _ATOMIC_TYPES:
                if not isinstance(data, type_):
                    # 尝试进行类型转换
                    try:
                        return type_(data)
                    except (ValueError, TypeError) as e:
                         raise TypeError(f"Failed to convert data '{data}' (type: {type(data)}) to atomic type '{type_.__name__}'. Original error: {e}") from e
                return data # 类型匹配，直接返回
            elif is_dataclass(type_) and issubclass(type_, DictMixin):
                 if not isinstance(data, dict):
                      raise TypeError(f"Expected a dictionary to instantiate dataclass '{type_.__name__}', but got '{type(data)}'.")
                 # 递归调用 from_dict 创建 dataclass 实例
                 return type_.from_dict(data)
            elif hasattr(type_, '_fields') and issubclass(type_, tuple): # NamedTuple
                if not isinstance(data, (list, tuple)):
                    raise TypeError(f"Expected list or tuple for NamedTuple '{type_.__name__}', got '{type(data)}'.")
                try:
                     # 创建 NamedTuple 实例
                     return type_(*data)
                except TypeError as e:
                     raise TypeError(f"Error creating NamedTuple '{type_.__name__}': {e}") from e
            elif type_ is Any:
                # 对于 Any 类型，进行深拷贝
                return copy.deepcopy(data)
            else:
                # 不支持的类类型
                raise TypeError(f"Unsupported class type '{type_.__name__}' for deserialization.")
        else:
            # 不支持的类型提示 (如 TypeVar 本身)
            raise TypeError(f"Unsupported type hint for deserialization: {type_}")

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """
        从字典创建 dataclass 实例。增强了错误处理和字段映射。
        """
        if not isinstance(data, dict):
            raise TypeError(f"Input must be a dictionary, but got {type(data)}.")

        init_vars = {}
        # 创建字段名到字段对象的映射，方便查找
        field_map = {f.name: f for f in fields(cls)}

        # 迭代输入字典的数据
        for field_name, field_data in data.items():
            if field_name in field_map: # 只处理 dataclass 中定义的字段
                field_ = field_map[field_name]
                try:
                    # 使用 _from_define 进行核心转换
                    init_vars[field_name] = cls._from_define(field_.type, field_data)
                except (TypeError, ValueError) as e:
                    # 包装错误，提供字段上下文
                    raise TypeError(f"Error processing field '{cls.__name__}.{field_name}' with data '{field_data}': {e}") from e
            # else:
            #     # 忽略 data 中未在 dataclass 定义的字段
            #     pass

        # 实例化 dataclass，依赖其 __init__ 处理默认值和缺失字段
        try:
            instance = cls(**init_vars)
            return instance
        except TypeError as e:
            # 捕获实例化错误，提供更详细的信息
            defined_field_names = {f.name for f in fields(cls)}
            provided_field_names = set(init_vars.keys())
            # 计算必需但未提供的字段
            required_fields = {
                f.name for f in fields(cls)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            }
            missing_required = required_fields - provided_field_names

            if missing_required:
                # 如果缺少必需字段，抛出带有字段名的错误
                raise TypeError(f"Missing required fields for '{cls.__name__}': {', '.join(missing_required)}. Provided: {list(provided_field_names)}. Original error: {e}") from e
            else:
                # 如果没有明显缺失的必需字段，可能是其他类型不匹配等问题
                raise TypeError(f"Error instantiating '{cls.__name__}'. Check field types and provided data: {init_vars}. Original error: {e}") from e


    # 使用 reprlib 来限制输出长度
    _repr: ClassVar[Repr] = Repr(maxlevel=2, maxdict=3, maxlist=3, maxother=100)

    def __repr__(self) -> str:
        """提供更简洁且有用的对象表示"""
        fields_str = []
        # 确保只处理 dataclass 定义的字段
        field_names = {f.name for f in fields(self)}

        for name in sorted(field_names): # 按字母顺序排列字段
            if name.startswith("_"): # 跳过私有字段
                continue
            # 使用 getattr 安全获取值
            value = getattr(self, name, '<Attribute missing>')
            # 使用 reprlib 限制输出
            fields_str.append(f"{name}={self._repr.repr(value)}")

        # 返回类名和字段表示
        return f"{self.__class__.__name__}({', '.join(fields_str)})"


@dataclass(repr=False)
class ThreadSafeCache(DictMixin):
    """
    提供线程安全的属性访问和字典转换的 Mixin 类。
    使用 RLock 保证同一线程可以重入。
    修正了 __getattribute__ 和 __setattr__ 的递归问题。
    """
    # _lock 不应在 field 中初始化，推迟到 __post_init__
    # _lock: threading.RLock = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self):
        """在 dataclass 初始化后创建锁，避免递归"""
        # 使用 object.__getattribute__ 检查 _lock 是否已存在或被初始化
        try:
            # 尝试使用 object.__getattribute__ 安全地访问 _lock
            object.__getattribute__(self, "_lock")
            lock_exists = True
        except AttributeError:
            lock_exists = False

        if not lock_exists:
            # 使用 object.__setattr__ 绕过自定义的 __setattr__ 来初始化锁
            object.__setattr__(self, "_lock", threading.RLock())

        # 调用父类的 __post_init__ (如果存在)
        if hasattr(super(), "__post_init__"):
             super().__post_init__()

    def __setattr__(self, name: str, value: Any) -> None:
        """线程安全地设置属性，使用 object.__getattribute__ 访问锁"""
        # 使用 object.__getattribute__ 获取锁以避免递归
        try:
             lock = object.__getattribute__(self, "_lock")
        except AttributeError:
             lock = None # 锁还未初始化

        # 只对非私有属性且锁已初始化时加锁
        if not name.startswith("_") and lock:
            with lock:
                # 使用 object.__setattr__ 设置属性，绕过自定义的 __setattr__
                object.__setattr__(self, name, value)
        else:
            # 对于私有属性或锁未初始化的情况，直接设置
            object.__setattr__(self, name, value)

    def __getattribute__(self, name: str) -> Any:
        """线程安全地获取属性，使用 object.__getattribute__ 访问锁和属性"""
        # 使用 object.__getattribute__ 获取锁以避免递归
        try:
             lock = object.__getattribute__(self, "_lock")
        except AttributeError:
             lock = None # 锁还未初始化

        # 使用 object.__getattribute__ 获取原始属性值，避免递归
        attr = object.__getattribute__(self, name)

        # 对非私有、非可调用属性，且锁已初始化时，加锁后重新获取
        if not name.startswith("_") and not callable(attr) and lock:
            with lock:
                # 在锁内，必须再次使用 object.__getattribute__ 重新获取
                # 以确保获取到的是加锁期间的最新值
                return object.__getattribute__(self, name)
        else:
            # 对于私有属性、方法或锁未初始化的情况，直接返回第一次获取的值
            return attr

    @contextmanager
    def atomic_scope(self):
        """提供一个上下文管理器，用于原子性地读/写多个属性"""
        # 直接获取锁，如果不存在则会抛出 AttributeError
        lock = object.__getattribute__(self, "_lock")
        with lock:
            yield

    def to_dict(self, keep_none=False) -> dict[str, Any]:
        """线程安全地将对象转换为字典"""
        # 直接获取锁，如果不存在则会抛出 AttributeError
        lock = object.__getattribute__(self, "_lock")
        with lock:
            # 调用 DictMixin 的 to_dict 方法
            # 使用 super() 调用父类方法以确保正确性
            return super(ThreadSafeCache, self).to_dict(keep_none)


class ExtraMixin:
    """
    统一管理 extra 属性的方法，增强了健壮性。
    假定宿主类有 `extra` 属性 (通常是 dict) 和 `_lock` 属性 (可能来自 ThreadSafeCache)。
    使用 object.__getattribute__ 和 object.__setattr__ 来安全访问内部状态。
    """
    # 类型提示，实际的 extra 字典需要在宿主类中通过 field 定义
    # extra: dict[str, Any] = field(default_factory=dict, repr=False) # 宿主类应这样定义

    def set_extra(self, key: str, value: Any):
        """线程安全地设置 extra 字典中的键值对。如果 value 为 None，则不设置。"""
        if value is None:
            return

        # 安全地获取锁
        try:
             lock = object.__getattribute__(self, "_lock")
        except AttributeError:
             lock = None

        # 安全地获取或初始化 extra 字典
        try:
             current_extra = object.__getattribute__(self, "extra")
             if not isinstance(current_extra, dict):
                  # 如果 extra 不是字典，重新初始化为空字典
                  current_extra = {}
                  object.__setattr__(self, "extra", current_extra)
        except AttributeError:
             # 如果 extra 不存在，初始化为空字典
             current_extra = {}
             object.__setattr__(self, "extra", current_extra)

        # 在锁内或直接设置值
        if lock:
            with lock:
                 current_extra[key] = value
        else: # 非线程安全模式
            current_extra[key] = value

    def get_extra(self, key: str, default: Any = None) -> Any:
        """线程安全地获取 extra 字典中的值，如果键不存在或 extra 不可用，则返回默认值。"""
        # 安全地获取锁
        try:
             lock = object.__getattribute__(self, "_lock")
        except AttributeError:
             lock = None

        # 安全地获取 extra 字典
        try:
             current_extra = object.__getattribute__(self, "extra")
             if not isinstance(current_extra, dict):
                  return default
        except AttributeError:
             return default

        # 在锁内或直接获取值
        if lock:
            with lock:
                 return current_extra.get(key, default)
        else: # 非线程安全模式
            return current_extra.get(key, default)

    def require_extra(self, key: str) -> Any:
        """线程安全地获取 extra 字典中的值，如果键不存在或 extra 不可用，则抛出 KeyError。"""
        # 安全地获取锁
        try:
             lock = object.__getattribute__(self, "_lock")
        except AttributeError:
             lock = None

        # 安全地获取 extra 字典
        try:
             current_extra = object.__getattribute__(self, "extra")
             if not isinstance(current_extra, dict):
                 raise KeyError(f"Attribute 'extra' is not a dictionary. Cannot require key '{key}'.")
        except AttributeError:
             raise KeyError(f"Attribute 'extra' does not exist. Cannot require key '{key}'.")

        # 在锁内或直接获取值
        if lock:
            with lock:
                try:
                     return current_extra[key]
                except KeyError:
                     # 抛出更具体的错误
                     raise KeyError(f"Required key '{key}' not found in extra dictionary.") from None
        else: # 非线程安全模式
            try:
                 return current_extra[key]
            except KeyError:
                 # 抛出更具体的错误
                 raise KeyError(f"Required key '{key}' not found in extra dictionary.") from None