import copy
import inspect
import threading
import dataclasses
from contextlib import contextmanager
from dataclasses import dataclass, field, fields, is_dataclass
from reprlib import Repr
from typing import Any, ClassVar, Type, Union, get_args, get_origin, Optional, TypeVar, Dict, GenericAlias as TypingGenericAlias
import types

# 定义原子类型集合，这些类型在序列化/反序列化时通常直接处理或有简单转换
_ATOMIC_TYPES = frozenset([
    bool,
    int,
    float,
    str,
    type(None) # NoneType is considered atomic for some checks, though None values have special handling.
])

# 定义 TypeVar 用于泛型类型提示
T = TypeVar('T')

class DictMixin:
    """
    提供 to_dict 和 from_dict 方法的 Mixin 类，
    用于将 dataclass 实例与字典相互转换。
    """

    def _to_dict_part(self, obj: Any, keep_none: bool = False) -> Any:
        """
        递归地将对象的各个部分转换为字典友好的格式。
        这个方法是 to_dict 的核心辅助函数。

        Args:
            obj: 要转换的对象部分。
            keep_none: 如果为 True，即使值为 None，也会在结果中保留（返回 None）。
                       如果为 False，None 值可能会被调用者忽略。

        Returns:
            转换后的对象部分。
        """
        if obj is None:
            # 如果对象是 None，则返回 None。
            # 调用 to_dict 方法会根据 keep_none 决定是否将这个 None 值加入最终的字典。
            # Fix分支的注释指出: keep_none 为 True 时应返回 None。
            # 原代码 `return None if keep_none else obj` 当 obj is None 时, 结果总是 None。
            return None
        
        obj_type = type(obj)

        if obj_type in _ATOMIC_TYPES and obj_type is not type(None): # 确保 obj 不是 None
            # 基本数据类型直接返回其值。
            return obj
        elif isinstance(obj, DictMixin):
            # 如果对象是 DictMixin 的实例，递归调用其 to_dict 方法。
            return obj.to_dict(keep_none)
        elif isinstance(obj, tuple) and hasattr(obj, '_fields'): # 处理 NamedTuple
            # NamedTuple 被转换为普通元组，其每个元素都经过递归处理。
            return tuple(self._to_dict_part(item, keep_none) for item in obj)
        elif isinstance(obj, (list, tuple, set, frozenset)):
            # 对于列表、元组、集合等序列类型，递归处理其每个元素。
            return obj_type(self._to_dict_part(item, keep_none) for item in obj)
        elif isinstance(obj, dict):
            # 对于字典类型，递归处理其键和值。
            new_dict = {}
            for k, v in obj.items():
                key_part = self._to_dict_part(k, keep_none) # 键也需要处理
                value_part = self._to_dict_part(v, keep_none)
                # 仅当值不为 None 或明确指示保留 None 时，才将键值对添加到新字典中。
                if value_part is not None or keep_none:
                    new_dict[key_part] = value_part
            return new_dict
        else:
            # 对于其他未知类型，尝试进行深拷贝。
            try:
                return copy.deepcopy(obj)
            except TypeError:
                # 如果深拷贝失败（例如对象不可拷贝），则返回其字符串表示作为后备。
                return str(obj)

    def to_dict(self, keep_none: bool = False) -> dict[str, Any]:
        """
        将 dataclass 实例转换为字典。

        Args:
            keep_none: 如果为 True，则在字典中保留值为 None 的字段。
                       如果为 False（默认），则忽略值为 None 的字段。

        Returns:
            表示 dataclass 实例的字典。
        """
        result = {}
        # 获取 dataclass 定义的所有字段名。
        # fields(self) 会考虑继承链（如果父类也是 dataclass）。
        defined_fields = {f.name for f in fields(self)}

        for name in defined_fields:
            if name.startswith("_"): # 按照约定，跳过以下划线开头的“私有”属性。
                continue
            
            value = getattr(self, name, None) # 安全地获取属性值，如果属性不存在则默认为 None。

            # 如果值为 None 且不要求保留 None，则跳过此字段。
            if value is None and not keep_none:
                continue

            # 使用 _to_dict_part 递归转换属性值。
            result[name] = self._to_dict_part(value, keep_none)
        return result

    @classmethod
    def _from_define(cls, type_: Type, data: Any) -> Any:
        """
        核心的反序列化方法。根据类型注解 `type_` 将数据 `data` 转换为目标类型。
        此方法增强了对 None、Optional、各种泛型容器（List, Dict, Tuple, Set）以及
        自定义 dataclass（继承自 DictMixin）和 NamedTuple 的处理。
        此实现主要基于 'Fix' 分支的逻辑，该逻辑更为全面和健壮。
        """
        origin = get_origin(type_) # 获取泛型类型的原始类型 (例如 list for List[int])
        args = get_args(type_)     # 获取泛型类型的参数 (例如 (int,) for List[int])

        # 步骤 1: 处理 `data` 为 None 的情况
        if data is None:
            # 检查类型注解 `type_` 是否允许 None 值。
            # 这包括 Optional[T], Union[T, None], Any, 或 type_ 本身就是 NoneType。
            is_explicit_union_with_none = (origin is Union or origin is types.UnionType) and type(None) in args
            # `_GenericAlias` (Python < 3.9) or `types.GenericAlias` (Python 3.9+) for subscripted generics like Optional[T]
            # `typing.Optional` is an alias for `Union[T, NoneType]`
            is_optional_syntax = isinstance(type_, TypingGenericAlias) and \
                                 hasattr(type_, '_name') and type_._name == 'Optional' and \
                                 type(None) in get_args(type_.__origin__ if hasattr(type_, '__origin__') else type_)


            if type_ is Any or type_ is type(None) or is_explicit_union_with_none or is_optional_syntax:
                return None # 类型允许 None，直接返回 None
            else:
                # 如果数据是 None，但类型注解不允许 None（且非 Any），则抛出类型错误。
                raise TypeError(f"Type '{type_}' does not allow None, but received None data.")

        # 步骤 2: 处理泛型类型 (例如 List[T], Dict[K, V], Union[X, Y])
        if origin is not None: # `origin` 非 None 表示 `type_` 是一个泛型类型
            if origin is Union or origin is types.UnionType: # 处理 Union 类型 (包括 Optional)
                # `types.UnionType` 用于检查 Python 3.10+ 的 X | Y 语法创建的联合类型。
                
                # 从 Union 参数中排除 NoneType，因为它已在上面的 `data is None` 逻辑中处理。
                possible_types = [arg for arg in args if arg is not type(None)]
                
                # 特殊情况: 如果 `type_` 是 Optional[T] (即 Union[T, NoneType]) 且 `data` 不是 None,
                # 那么我们应该尝试将 `data` 解析为类型 T。
                if len(possible_types) == 1 and type(None) in args: 
                     # 这表明原始类型是 Optional[possible_types[0]]
                     try:
                         return cls._from_define(possible_types[0], data)
                     except (TypeError, ValueError) as e:
                         # 如果作为 T 类型解析失败，则抛出错误，因为 Optional 只允许 T 或 None。
                         raise TypeError(f"Data '{data}' (type: {type(data)}) failed to parse as type '{possible_types[0]}' from Optional form '{type_}'. Error: {e}")

                # 对于一般的 Union[T1, T2, ...] (非 Optional 或已处理完 Optional 的 T 部分)，
                # 尝试用 Union 中的每种（非 None）类型来解析 `data`。
                errors = [] # 记录尝试解析失败的错误信息
                for pt in possible_types:
                    try:
                        return cls._from_define(pt, data) # 返回第一个成功解析的结果
                    except (TypeError, ValueError) as e:
                        errors.append(f"  - Tried '{pt}': {e}")
                # 如果所有可能的类型都尝试失败，则抛出错误。
                raise TypeError(f"Data '{data}' (type: {type(data)}) did not match any type in Union '{type_}'. Errors:\n" + "\n".join(errors))

            elif issubclass(origin, list) and isinstance(data, list):
                # 处理 List[T]: `data` 必须是列表。
                if not args: raise TypeError(f"List type hint '{type_}' is missing item type argument.")
                item_type = args[0] # 获取列表项的类型 T
                # 递归地将列表中的每个项目转换为 `item_type`。
                return [cls._from_define(item_type, item) for item in data]

            elif issubclass(origin, set) and isinstance(data, (list, set)): # 允许从列表初始化集合
                # 处理 Set[T]: `data` 可以是列表或集合。
                if not args: raise TypeError(f"Set type hint '{type_}' is missing item type argument.")
                item_type = args[0] # 获取集合项的类型 T
                return {cls._from_define(item_type, item) for item in data}

            elif issubclass(origin, frozenset) and isinstance(data, (list, set, frozenset)):
                # 处理 Frozenset[T]: `data` 可以是列表、集合或冻结集合。
                if not args: raise TypeError(f"Frozenset type hint '{type_}' is missing item type argument.")
                item_type = args[0]
                return frozenset(cls._from_define(item_type, item) for item in data)

            elif issubclass(origin, tuple):
                # 处理 Tuple 类型。
                if not args: raise TypeError(f"Tuple type hint '{type_}' is missing item type arguments.")
                if not isinstance(data, (list, tuple)): # `data` 必须是序列类型。
                    raise TypeError(f"Expected list or tuple to construct Tuple type '{type_}', got '{type(data)}'.")

                if len(args) == 2 and args[1] is Ellipsis:  # 处理可变长度元组: tuple[T, ...]
                    item_type = args[0] # 类型 T
                    return tuple(cls._from_define(item_type, item) for item in data)
                else:  # 处理固定长度元组: tuple[T1, T2, ...]
                    if len(args) != len(data):
                        raise ValueError(f"Tuple type '{type_}' expects {len(args)} items, but data has {len(data)} items.")
                    return tuple(cls._from_define(arg_type, item_data) for arg_type, item_data in zip(args, data))

            elif issubclass(origin, dict) and isinstance(data, dict):
                # 处理 Dict[K, V]: `data` 必须是字典。
                if len(args) != 2: raise TypeError(f"Dict type hint '{type_}' must have two arguments (KeyType, ValueType).")
                key_type, value_type = args # 类型 K 和 V
                new_dict = {}
                for k, v in data.items():
                    try:
                        new_key = cls._from_define(key_type, k)
                        new_value = cls._from_define(value_type, v)
                        new_dict[new_key] = new_value
                    except (TypeError, ValueError) as e:
                        # 包装错误信息，提供更多上下文。
                        raise TypeError(f"Error processing dictionary item ('{k}': '{v}') for type '{type_}': {e}") from e
                return new_dict
            else:
                # 不支持的泛型原始类型。
                raise TypeError(f"Unsupported generic type origin: '{origin}' in type hint '{type_}'.")

        # 步骤 3: 处理非泛型类型 (例如 dataclasses, NamedTuple, Any, 原子类型)
        elif inspect.isclass(type_): # 确保 `type_` 是一个类
            if type_ in _ATOMIC_TYPES and type_ is not type(None): # 处理原子类型 (已处理 `data is None` 的情况)
                if not isinstance(data, type_):
                    # 如果 `data` 不是目标原子类型，尝试进行类型转换 (例如，str "123" to int 123)。
                    try:
                        return type_(data)
                    except (ValueError, TypeError) as e:
                         raise TypeError(f"Failed to convert data '{data}' (type: {type(data)}) to atomic type '{type_.__name__}': {e}") from e
                return data # 类型匹配或成功转换，直接返回

            elif is_dataclass(type_) and issubclass(type_, DictMixin): # 处理继承自 DictMixin 的 dataclass
                 if not isinstance(data, dict):
                      raise TypeError(f"Expected a dictionary to instantiate dataclass '{type_.__name__}', but got type '{type(data)}'.")
                 # 递归调用 from_dict 方法创建 dataclass 实例。
                 return type_.from_dict(data) # type: ignore # 假设 from_dict 存在，因为 issubclass(type_, DictMixin)

            elif hasattr(type_, '_fields') and issubclass(type_, tuple):  # 处理 NamedTuple
                if not isinstance(data, (list, tuple)):
                    raise TypeError(f"Expected list or tuple to instantiate NamedTuple '{type_.__name__}', got type '{type(data)}'.")
                try:
                     # 创建 NamedTuple 实例。
                     return type_(*data)
                except TypeError as e: # 捕获参数数量不匹配等错误
                     raise TypeError(f"Error creating NamedTuple '{type_.__name__}' from data '{data}': {e}") from e
            
            elif type_ is Any:
                # 对于 Any 类型，进行深拷贝以避免意外的共享引用。
                return copy.deepcopy(data)

            else:
                # 如果 `type_` 是一个类，但不是上述任何一种已知类型，
                # 检查 `data` 是否已经是 `type_` 的实例。
                if isinstance(data, type_):
                    return data # `data` 已经是目标类型，直接返回。
                # 否则，这是一个不支持的类类型，无法从当前 `data` 类型进行反序列化。
                raise TypeError(f"Unsupported class type '{type_.__name__}' for deserialization from data of type '{type(data)}'.")
        
        # 如果 `type_` 不是类 (例如，直接传递了 TypeVar 实例或其他非类型对象)，
        # 或者属于其他未处理的类型提示结构。
        else:
            raise TypeError(f"Unsupported type hint for deserialization: {type_}")


    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """
        从字典创建 dataclass 实例。
        此方法会使用字段的类型注解来递归地转换字典中的值。

        Args:
            cls: 要创建实例的 dataclass 类型。
            data: 包含字段数据的字典。

        Returns:
            `cls` 类型的一个新实例。

        Raises:
            TypeError: 如果 `cls` 不是 dataclass，或者 `data` 不是字典，
                       或者在处理字段或实例化过程中发生类型不匹配或缺少必需字段。
        """
        if not is_dataclass(cls): # 确保 `cls` 是一个 dataclass
            raise TypeError(f"from_dict can only be called on dataclass types. '{cls.__name__}' is not a dataclass.")
        if not isinstance(data, dict):
            raise TypeError(f"Input to from_dict must be a dictionary, got {type(data)}.")

        init_kwargs = {} # 用于存储传递给 dataclass构造函数 的参数
        # 创建字段名到 `dataclasses.Field` 对象的映射，方便查找字段类型等信息。
        cls_fields_map = {f.name: f for f in fields(cls)}

        # 迭代输入字典 `data` 中的键值对
        for field_name, field_value in data.items():
            if field_name in cls_fields_map: # 只处理在 dataclass 中定义的字段
                target_field = cls_fields_map[field_name] # 获取字段对象
                try:
                    # 使用 `_from_define` 方法根据字段的类型注解转换 `field_value`。
                    init_kwargs[field_name] = cls._from_define(target_field.type, field_value)
                except (TypeError, ValueError) as e:
                    # 如果转换失败，包装错误信息，提供字段上下文。
                    raise TypeError(f"Error processing field '{cls.__name__}.{field_name}' with value '{field_value}' (type: {type(field_value)}): {e}") from e
            # else:
            #   （可选）可以添加逻辑来处理 `data` 中存在但 dataclass 中未定义的字段，
            #   例如记录警告或根据策略抛出错误。当前实现是忽略这些额外字段。

        # 使用收集到的参数实例化 dataclass。
        # dataclass 的 `__init__` 方法会自动处理默认值和检查必需参数。
        try:
            instance = cls(**init_kwargs) # type: ignore # 假设 init_kwargs 包含了正确的参数
            return instance
        except TypeError as e:
            # 如果 `cls(**init_kwargs)` 抛出 TypeError (例如，缺少必需参数，或类型仍然不匹配)，
            # 提供更详细的错误信息。
            defined_field_names = {f.name for f in fields(cls)}
            provided_field_names = set(init_kwargs.keys())
            # 计算哪些必需字段（没有默认值）没有被提供
            required_fields_without_default = {
                f.name for f in fields(cls)
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING
            }
            missing_required = required_fields_without_default - provided_field_names
            
            if missing_required:
                 # 如果确实缺少必需字段，在错误信息中列出它们。
                 raise TypeError(f"Missing required fields for '{cls.__name__}': {', '.join(sorted(list(missing_required)))}. Provided: {sorted(list(provided_field_names))}. Original error: {e}") from e
            # 如果没有明显缺失的必需字段，错误可能是由于其他原因（例如，`__post_init__` 中的问题，
            # 或者传递了 `init=False` 的字段等）。
            raise TypeError(f"Error instantiating '{cls.__name__}' with arguments {init_kwargs}. Check field types, defaults, and __post_init__ if applicable. Original error: {e}") from e


    # 使用 reprlib 来生成对象的简洁字符串表示，避免过长的输出。
    _repr_instance: ClassVar[Repr] = Repr() # 创建一个 Repr 实例作为类变量
    _repr_instance.maxlevel = 2      # 限制嵌套对象的递归深度
    _repr_instance.maxdict = 3       # 限制字典显示的最大条目数
    _repr_instance.maxlist = 3       # 限制列表显示的最大条目数
    _repr_instance.maxstring = 50    # 限制字符串显示的最大长度
    _repr_instance.maxother = 50     # 限制其他类型对象显示的最大长度

    def __repr__(self) -> str:
        """提供一个比默认 dataclass repr 更简洁且有用的对象字符串表示。"""
        if not is_dataclass(self): # 防御性检查，尽管通常由 @dataclass 保证
            return super().__repr__()

        field_parts = []
        # 迭代 dataclass 的字段对象，以确保只处理定义的字段，并可以访问 repr=False 等元数据。
        # fields(self) 默认按定义顺序返回。
        for f_obj in fields(self):
            if not f_obj.repr: # 尊重 dataclass 字段定义的 `repr=False`。
                continue
            # 按照约定，不显示以下划线开头的“私有”字段在 repr 中（除非其 repr=True 被明确设置）。
            # 此处简单地跳过所有以下划线开头的字段，可以根据需要调整此策略。
            if f_obj.name.startswith("_"):
                continue
            
            try:
                value = getattr(self, f_obj.name)
                # 使用类配置的 Repr 实例来格式化字段值。
                value_repr = self._repr_instance.repr(value)
            except AttributeError:
                value_repr = "<Attribute missing>" # 如果由于某种原因属性不存在
            field_parts.append(f"{f_obj.name}={value_repr}")
        
        return f"{self.__class__.__name__}({', '.join(field_parts)})"


@dataclass(repr=False) # repr=False 因为我们通过 DictMixin 提供了自定义的 __repr__
class ThreadSafeCache(DictMixin):
    """
    为 dataclass 提供线程安全的属性访问。
    它使用一个可重入锁（RLock）来同步对实例属性的访问。
    这个 Mixin 应该与 `@dataclass` 一起使用。
    """
    # `_lock` 属性不在 dataclass 的 `field` 中定义，
    # 而是在 `__post_init__` 中初始化，以避免与 dataclass 字段生成过程冲突。

    def __post_init__(self):
        """在 dataclass 完全初始化后，创建并设置 RLock。"""
        # 使用 `object.__setattr__` 来设置 `_lock`，
        # 这样可以绕过我们自己定义的 `__setattr__` 方法，避免在初始化锁时发生递归或死锁。
        object.__setattr__(self, "_lock", threading.RLock())

        # 如果父类（或同一继承链上的其他 Mixin）也有 `__post_init__` 方法，确保调用它。
        if hasattr(super(), "__post_init__"):
            super().__post_init__() # type: ignore # super() 调用可能需要特定类型注解上下文

    def __setattr__(self, name: str, value: Any) -> None:
        """线程安全地设置属性值。"""
        # 首先，尝试获取 `_lock`。
        # 必须使用 `object.__getattribute__` 来获取 `_lock`，以避免触发我们自己定义的 `__getattribute__`。
        try:
            lock = object.__getattribute__(self, "_lock")
        except AttributeError:
            # 如果 `_lock` 不存在（例如，在 `__post_init__` 完成之前，dataclass 正在初始化其字段），
            # 则直接设置属性，不加锁。这是 dataclass 初始化过程所必需的。
            object.__setattr__(self, name, value)
            return

        # 对于以下划线开头的“私有”属性或 `_lock` 属性本身，不进行加锁，直接设置。
        # 这是为了允许内部操作或避免死锁。
        if name.startswith("_") or name == "_lock":
            object.__setattr__(self, name, value)
        else:
            # 对于所有其他“公共”属性，在锁的保护下设置值。
            with lock:
                object.__setattr__(self, name, value)

    def __getattribute__(self, name: str) -> Any:
        """线程安全地获取属性值。"""
        try:
            # 尝试获取锁。如果锁还未在 __post_init__ 中创建，会触发 AttributeError
            lock = object.__getattribute__(self, "_lock")

            # 如果锁存在，则继续原有的逻辑
            initial_value = object.__getattribute__(self, name)

            # 对于“公共”属性（非私有、非锁本身），并且该属性不是可调用对象（即不是方法），
            # 则在锁的保护下重新获取该值。
            if not name.startswith("_") and name != "_lock" and not callable(initial_value):
                with lock:
                    # 在锁内重新获取并返回
                    return object.__getattribute__(self, name)
            
            # 对于私有属性、锁本身、或可调用属性（方法），直接返回初始获取的值。
            return initial_value

        except AttributeError:
            # 如果捕获到 AttributeError，说明 _lock 属性还不存在（对象正在初始化早期）
            # 在这种情况下，直接获取并返回请求的属性，不加锁。
            return object.__getattribute__(self, name)

    @contextmanager
    def atomic_scope(self):
        """
        提供一个上下文管理器，用于执行一系列操作的原子块。
        在此块内的所有属性访问（通过此类的实例）都将受到同一个锁的保护。
        """
        lock = object.__getattribute__(self, "_lock") # 获取锁
        with lock: # 进入锁
            yield # 执行上下文块中的代码

    # `to_dict` 方法继承自 `DictMixin`。
    # 为了确保 `to_dict` 操作的线程安全性（如果其内部逻辑或访问的属性需要同步），
    # 我们在这里覆盖它，以在锁的保护下调用父类的实现。
    def to_dict(self, keep_none: bool = False) -> dict[str, Any]:
        """线程安全地将对象转换为字典。"""
        lock = object.__getattribute__(self, "_lock") # 获取锁
        with lock: # 进入锁
            # 调用 `DictMixin` 中的 `to_dict` 实现。
            return super().to_dict(keep_none=keep_none)


class ExtraMixin:
    """
    一个 Mixin 类，用于统一管理实例上的 `extra` 字典属性。
    `extra` 字典用于存储任意的附加数据。
    这个 Mixin 假定宿主类可能也使用了 `ThreadSafeCache` 或有自己的 `_lock` 属性以实现线程安全。
    它会尝试使用这个 `_lock`（如果存在）来同步对 `extra` 字典的访问。
    """
    # `extra` 字典本身应该在宿主 dataclass 中定义，例如：
    # extra: Dict[str, Any] = field(default_factory=dict, repr=False)

    def _get_extra_dict(self, create_if_missing: bool = False) -> Optional[Dict[str, Any]]:
        """
        辅助方法，用于安全地获取 `extra` 字典。
        如果 `extra` 不存在或不是字典，并且 `create_if_missing` 为 True，则会创建它。
        """
        try:
            # 使用 object.__getattribute__ 访问 `extra` 以避免触发宿主类可能的自定义行为。
            current_extra = object.__getattribute__(self, "extra")
            if not isinstance(current_extra, dict):
                # 如果 `extra` 存在但不是字典
                if create_if_missing:
                    current_extra = {} # 创建新的空字典
                    object.__setattr__(self, "extra", current_extra) # 并设置回实例
                else:
                    return None # 不创建，返回 None 表示 `extra` 无效
            return current_extra
        except AttributeError:
            # 如果 `extra` 属性根本不存在
            if create_if_missing:
                current_extra = {} # 创建新的空字典
                object.__setattr__(self, "extra", current_extra) # 并设置回实例
                return current_extra
            return None # 不创建，返回 None

    def set_extra(self, key: str, value: Any):
        """
        线程安全地在 `extra` 字典中设置一个键值对。
        如果 `value` 为 None，则根据策略可以不设置或移除该键（当前策略是不设置）。
        """
        if value is None: # 策略：不在 `extra` 中存储 None 值。
            return

        lock = None
        try: # 尝试获取宿主类的 `_lock`（如果存在，例如来自 ThreadSafeCache）
            lock = object.__getattribute__(self, "_lock")
        except AttributeError:
            pass # 没有锁，将以非线程安全模式继续

        if lock: # 如果有锁，在锁的保护下操作
            with lock:
                extra_dict = self._get_extra_dict(create_if_missing=True)
                if extra_dict is not None: # `_get_extra_dict` 确保在 create_if_missing=True 时返回字典
                    extra_dict[key] = value
        else: # 没有锁，直接操作
            extra_dict = self._get_extra_dict(create_if_missing=True)
            if extra_dict is not None:
                extra_dict[key] = value


    def get_extra(self, key: str, default: Any = None) -> Any:
        """
        线程安全地从 `extra` 字典中获取一个值。
        如果键不存在，或 `extra` 字典本身无效，则返回 `default` 值。
        """
        lock = None
        try:
            lock = object.__getattribute__(self, "_lock")
        except AttributeError:
            pass

        if lock:
            with lock:
                extra_dict = self._get_extra_dict(create_if_missing=False) # 不创建，如果不存在或无效则返回 None
                return extra_dict.get(key, default) if extra_dict is not None else default
        else:
            extra_dict = self._get_extra_dict(create_if_missing=False)
            return extra_dict.get(key, default) if extra_dict is not None else default

    def require_extra(self, key: str) -> Any:
        """
        线程安全地从 `extra` 字典中获取一个值。
        如果键不存在，或 `extra` 字典本身无效，则抛出 `KeyError`。
        """
        lock = None
        try:
            lock = object.__getattribute__(self, "_lock")
        except AttributeError:
            pass

        op = lambda d: d[key] # 操作：从字典 d 中获取键 key 的值

        if lock:
            with lock:
                extra_dict = self._get_extra_dict(create_if_missing=False)
                if extra_dict is None:
                    raise KeyError(f"Attribute 'extra' is missing or not a dictionary. Cannot find required key '{key}'.")
                try:
                    return op(extra_dict)
                except KeyError: # 明确捕获并重新抛出 KeyError，以确保 from None 来清除原始 Traceback (如果需要)
                    raise KeyError(f"Required key '{key}' not found in 'extra' dictionary.") from None
        else:
            extra_dict = self._get_extra_dict(create_if_missing=False)
            if extra_dict is None:
                raise KeyError(f"Attribute 'extra' is missing or not a dictionary. Cannot find required key '{key}'.")
            try:
                return op(extra_dict)
            except KeyError:
                raise KeyError(f"Required key '{key}' not found in 'extra' dictionary.") from None