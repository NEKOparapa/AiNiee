import copy
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, fields, MISSING # 增加 MISSING 导入
from reprlib import Repr
from typing import Any, ClassVar, get_args, get_origin, Union # 增加 Union
from types import UnionType # 增加 UnionType 导入 (Python 3.10+)
import functools # 导入 functools 用于 lru_cache

_ATOMIC_TYPES = frozenset([
    bool,
    int,
    float,
    str,
])


class DictMixin:

    def _to_dict_part(self, obj, keep_none=False) -> Any:
        if type(obj) in _ATOMIC_TYPES:
            # 基本数据类型
            return obj
        elif isinstance(obj, DictMixin):
            return obj.to_dict(keep_none)
        elif isinstance(obj, tuple) and hasattr(obj, '_fields'):
            # namedtuple
            return type(obj)(*map(self._to_dict_part, obj))
        elif isinstance(obj, (list, tuple, set, frozenset)):
            # 集合
            return type(obj)(map(self._to_dict_part, obj))
        elif isinstance(obj, dict):
            if hasattr(type(obj), 'default_factory'):
                # defaltdict
                result = type(obj)(getattr(obj, 'default_factory'))
                for k, v in obj.items():
                    result[self._to_dict_part(k)] = self._to_dict_part(v)
                return result
            return type(obj)(
                (self._to_dict_part(k), self._to_dict_part(v))
                for k, v in obj.items()
            )
        else:
            return copy.deepcopy(obj)

    def to_dict(self, keep_none=False) -> dict[str, Any]:
        result = {}
        for f in fields(self):
            name = f.name
            value = object.__getattribute__(self, name)
            # 默认None不参与dict转换
            if name.startswith("_") or (value is None and not keep_none):
                continue
            else:
                result[name] = self._to_dict_part(value, keep_none)
        return result

    @classmethod
    def _from_define(cls, type_, data) -> Any:
        # --- 添加调试打印 ---
        # print(f"[DEBUG] _from_define called with type_: {type_} (actual type: {type(type_)}) | data type: {type(data)}")
        # --- 调试打印 End ---

        # --- 提前处理 None 数据 ---
        if data is None:
            # 如果类型允许 None (Optional 或 Union 包含 NoneType)，则返回 None
            origin_type_for_none = get_origin(type_)
            args_for_none = get_args(type_)
            is_optional_for_none = (origin_type_for_none is Union or origin_type_for_none is UnionType) and type(None) in args_for_none
            if type_ is Any or type_ is type(None) or is_optional_for_none:
                return None
            else:
                # 如果类型不允许 None 但数据是 None，可能表示数据缺失或错误
                # 可以选择抛出错误或返回类型的默认值（如果可能）
                # 这里选择抛出错误，因为无法确定合适的默认值
                raise ValueError(f"类型 {type_} 不允许 None 值，但接收到 None 数据")
        # --- None 数据处理结束 ---


        # 检查 type_ 是否是有效的类型或 typing 别名
        # isinstance(type_, type) 检查是否是普通类
        # hasattr(type_, '__origin__') 检查是否是 typing 模块的泛型别名 (如 list[int])
        # hasattr(type_, '_special') 在某些旧版本 typing 中可能需要
        # isinstance(type_, UnionType) 检查是否是 Python 3.10+ 的 Union 类型 (e.g., int | None)
        is_valid_type_hint = isinstance(type_, type) or hasattr(type_, '__origin__') or isinstance(type_, UnionType) # or hasattr(type_, '_special')
        if not is_valid_type_hint and type_ is not Any:
             # print(f"[ERROR] _from_define received non-type/non-alias: {type_} ({type(type_)})")
             raise TypeError(f"期望一个类或类型别名，但得到 {type_} (类型: {type(type_)})")


        # --- 处理 Optional[T] (即 Union[T, None]) ---
        origin_type = get_origin(type_)
        args = get_args(type_)
        is_optional = (origin_type is Union or origin_type is UnionType) and type(None) in args

        if is_optional:
            # Optional 类型不能直接用于 issubclass 等检查，需要提取实际类型
            actual_type = next((t for t in args if t is not type(None)), None)
            if actual_type is None:
                 # 这种情况理论上不应该发生 (Optional[None]?)
                 raise ValueError(f"无法从 Optional 类型 {type_} 中提取非 None 类型")
            # print(f"[DEBUG] Handling Optional, using actual type: {actual_type}") # 调试信息
            # 使用实际类型递归调用，并将结果返回
            # 注意：这里直接返回递归调用的结果，避免重复处理下面的逻辑
            return cls._from_define(actual_type, data)
        # --- Optional 处理结束 ---


        # --- 正式处理各种类型 ---
        if type_ in _ATOMIC_TYPES:
             # 检查数据类型是否匹配（或是否可以安全转换）
             if type(data) in _ATOMIC_TYPES:
                 try:
                     # 尝试进行类型转换（例如，从 int 到 float，或 str 到 int/float）
                     # 注意：这可能不是严格需要的，取决于你的数据源和期望
                     # 如果数据源保证类型正确，可以直接返回 data
                     return type_(data) # 尝试转换，失败会抛出 ValueError 或 TypeError
                 except (ValueError, TypeError):
                      raise TypeError(f"数据类型 {type(data)} 与期望的基本类型 {type_} 不匹配且无法转换: {data}")
             else:
                  raise TypeError(f"数据类型 {type(data)} 与期望的基本类型 {type_} 不匹配: {data}")

        elif type_ is Any:
            # print("[DEBUG] Processing Any type") # 调试信息
            return copy.deepcopy(data) # Any 类型直接深拷贝返回

        # --- 处理 DictMixin 子类 ---
        # 必须在检查泛型之前，因为 DictMixin 子类本身也是 type
        elif isinstance(type_, type) and issubclass(type_, DictMixin):
            if isinstance(data, dict):
                # print(f"[DEBUG] Processing DictMixin subclass: {type_}") # 调试信息
                return type_.from_dict(data)
            else:
                 raise TypeError(f"期望字典数据来创建 {type_} 实例，但得到 {type(data)}")

        # --- 处理 typing 泛型 ---
        elif origin_type is not None: # 确认是泛型类型
            # 集合 (List, Set, FrozenSet)
            if origin_type in (list, set, frozenset):
                if not isinstance(data, list): # JSON 反序列化通常得到 list
                    raise TypeError(f"期望列表数据来创建 {origin_type}，但得到 {type(data)}")
                if not args: raise ValueError(f"泛型容器 {origin_type} 缺少类型参数")
                element_type = args[0]
                # print(f"[DEBUG] Processing List/Set with element type: {element_type}") # 调试信息
                return origin_type(cls._from_define(element_type, x) for x in data)

            # 元组 (Tuple)
            elif origin_type is tuple:
                 if not isinstance(data, (list, tuple)):
                      raise TypeError(f"期望列表或元组数据来创建 {origin_type}，但得到 {type(data)}")
                 if not args: raise ValueError(f"泛型容器 {origin_type} 缺少类型参数")
                 # tuple[T, ...]
                 if len(args) == 2 and args[1] is Ellipsis:
                     element_type = args[0]
                     # print(f"[DEBUG] Processing Tuple[T, ...] with element type: {element_type}") # 调试信息
                     return tuple(cls._from_define(element_type, x) for x in data) # 返回 tuple
                 # tuple[T1, T2, ...] (固定长度)
                 else:
                     if len(args) != len(data):
                         raise ValueError(f"元组定义 {type_} (长度 {len(args)}) 与数据长度 {len(data)} 不匹配")
                     # print(f"[DEBUG] Processing fixed-length Tuple with types: {args}") # 调试信息
                     return tuple(cls._from_define(arg, dat) for arg, dat in zip(args, data)) # 返回 tuple

            # 字典 (Dict)
            elif origin_type is dict:
                if not isinstance(data, dict):
                     raise TypeError(f"期望字典数据来创建 {origin_type}，但得到 {type(data)}")
                if len(args) != 2: raise ValueError(f"泛型容器 {origin_type} 需要两个类型参数")
                key_type, value_type = args
                # print(f"[DEBUG] Processing Dict with key type: {key_type}, value type: {value_type}") # 调试信息
                # 注意：JSON 的 key 必须是字符串，如果 key_type 不是 str，需要特殊处理或报错
                if key_type is not str:
                    # 警告或引发错误，因为 JSON key 总是 str
                    print(f"[WARN] Dict key type is {key_type}, but JSON keys are always strings. Attempting conversion.")
                    # 可以尝试转换，或者直接报错
                    # raise TypeError("Dictionary keys must be strings when deserializing from JSON")
                return { # 返回普通 dict
                         cls._from_define(key_type, k): cls._from_define(value_type, v)
                         for k, v in data.items()
                     }
            # namedtuple (通常通过 hasattr(_fields) 在前面处理，这里可能多余)
            elif hasattr(origin_type, "_fields") and issubclass(origin_type, tuple):
                 if isinstance(data, (list, tuple)):
                      # print(f"[DEBUG] Processing namedtuple (via origin): {origin_type}") # 调试信息
                      return origin_type(*(cls._from_define(Any, x) for x in data))
                 else:
                      raise TypeError(f"期望列表或元组数据来创建 {origin_type}，但得到 {type(data)}")
            else:
                raise ValueError(f"不支持的泛型容器 {origin_type}")

        # --- 处理普通类（非 DictMixin，非泛型） ---
        elif isinstance(type_, type):
             # print(f"[WARN] Unsupported non-generic, non-DictMixin class type: {type_}") # 调试信息
             # 对于无法自动处理的类型，可以选择：
             # 1. 尝试直接赋值（如果数据类型匹配）
             # 2. 返回深拷贝
             # 3. 抛出错误
             # 这里选择抛出错误，因为不知道如何构造实例
             raise ValueError(f"不支持的类型自动转换: {type_}")

        # --- 未知情况 ---
        else:
            raise ValueError(f"无法处理的类型: {type_}")


    @classmethod
    def from_dict[T: DictMixin](cls: type[T], data: dict[str, Any]) -> T:
        # dacite 会覆盖__post_init__的属性，所以不用
        init_vars = {}
        field_map = {f.name: f for f in fields(cls)} # 预先创建字段映射

        # 处理 data 中的键，确保它们是有效的字段名
        for field_name, value in data.items():
             if field_name in field_map:
                 field_ = field_map[field_name]
                 field_type = field_.type
                 try:
                     # print(f"[DEBUG] from_dict processing field: {field_name}, type: {field_type}") # 调试信息
                     init_vars[field_name] = cls._from_define(field_type, value)
                 except Exception as e:
                      # 增加错误上下文信息
                      print(f"[ERROR] 处理字段 '{field_name}' (类型: {field_type}) 出错，数据: {repr(value)[:100]}...")
                      raise e # 重新抛出异常以便看到完整 traceback
             # else: # 选择性地忽略不在 dataclass 定义中的字段
             #    print(f"[WARN] 忽略未知字段 '{field_name}' (类: {cls.__name__})")

        # 处理 dataclass 中定义但 data 中没有提供的字段
        for field_name, field_ in field_map.items():
            if field_name not in init_vars:
                # 如果字段有默认值或默认工厂，dataclass 的 __init__ 会处理
                # 如果字段没有默认值且在 data 中缺失，__init__ 会抛出 TypeError，这是预期的
                pass
                 # if field_.default is MISSING and field_.default_factory is MISSING:
                 #     print(f"[WARN] Field '{field_name}' missing in data and has no default value for class {cls.__name__}")


        try:
            # print(f"[DEBUG] Instantiating {cls.__name__} with vars: {list(init_vars.keys())}") # 调试信息
            instance = cls(**init_vars)
            # print(f"[DEBUG] Successfully created instance of {cls.__name__}") # 调试信息
            return instance
        except Exception as e:
            print(f"[ERROR] 实例化 {cls.__name__} 失败，参数: {init_vars}")
            raise e


    _repr: ClassVar[Repr] = Repr(maxdict=1, maxother=256)

    def __repr__(self) -> str:
        fields_str = []
        for name, value in vars(self).items():
            if name.startswith("_"):
                continue
            fields_str.append(f"{name}={self._repr.repr(value)}")
        return f"{self.__class__.__name__}({', '.join(fields_str)})"


@dataclass(repr=False)
class ThreadSafeCache(DictMixin):
    _lock: threading.RLock = field(default=None, init=False, repr=False, compare=False) # 修改为 RLock

    def __post_init__(self):
        # 把锁的创建放到__init__函数之后，使得初始化不加锁
        # 使用 RLock 允许同一线程多次获取锁
        if getattr(self, "_lock", None) is None: # 确保只初始化一次
             super().__setattr__("_lock", threading.RLock())

    def __setattr__(self, name: str, value: Any) -> None:
        # 每次赋值都加锁
        # object.__getattribute__ # 这行似乎是笔误，移除
        lock = getattr(self, "_lock", None) # 安全地获取锁
        if not name.startswith("_") and lock:
            with lock:
                super().__setattr__(name, value)
        else: # 对于私有属性或锁未初始化时，直接设置
             super().__setattr__(name, value)

    def __getattribute__(self, name: str) -> Any:
        # 每次获取非私有、非 callable 属性都加锁
        # 特殊方法（如 __init__）不加锁
        if name.startswith("_") or name in ("__init__", "__post_init__", "to_dict", "from_dict", "_from_define", "_to_dict_part", "atomic_scope"):
             return super().__getattribute__(name)

        attr = super().__getattribute__(name)

        # callable 通常不需要加锁，除非它们修改了实例状态且需要线程安全
        if callable(attr):
            return attr

        lock = getattr(self, "_lock", None) # 安全地获取锁
        if lock:
            with lock:
                # 在锁内重新获取属性，以防在等待锁时属性被其他线程修改
                # 但对于简单属性读取，直接返回第一次获取的 attr 通常也可以
                # 这里选择重新获取以保证最新值
                return super().__getattribute__(name)
        else: # 锁未初始化
            return attr


    @contextmanager
    def atomic_scope(self):
        """一次读/写多个属性"""
        lock = getattr(self, "_lock", None)
        if not lock:
             # 锁未初始化时，提供一个无操作的上下文
             yield
             return

        with lock:
            yield

    def to_dict(self, keep_none=False) -> dict[str, Any]:
        lock = getattr(self, "_lock", None)
        if not lock:
             # 锁未初始化时，直接调用父类方法
             return super().to_dict(keep_none)

        with lock:
            return super().to_dict(keep_none)


class ExtraMixin:
    """统一管理extra属性的方法"""
    # 假设子类会继承 ThreadSafeCache 并拥有 _lock 和 extra 属性
    # 或者子类需要自己实现 _lock 和 extra

    def set_extra(self, key, value):
        if value is not None:
             # 确保 extra 属性存在且是字典
             if not hasattr(self, 'extra') or not isinstance(self.extra, dict):
                 self.extra = {} # 如果不存在或类型不对，初始化为空字典

             # 确保 _lock 存在
             lock = getattr(self, "_lock", None)
             if lock:
                 with lock:
                    self.extra[key] = value
             else: # 无锁环境
                 self.extra[key] = value


    def get_extra(self, key, default=None):
         # 确保 extra 属性存在且是字典
         if not hasattr(self, 'extra') or not isinstance(self.extra, dict):
             return default # 如果 extra 不存在或类型不对，返回默认值

         lock = getattr(self, "_lock", None)
         if lock:
             with lock:
                 return self.extra.get(key, default)
         else: # 无锁环境
             return self.extra.get(key, default)

    def require_extra(self, key):
         # 确保 extra 属性存在且是字典
         if not hasattr(self, 'extra') or not isinstance(self.extra, dict):
              raise KeyError(f"属性 'extra' 不存在或类型错误，无法获取键 '{key}'")

         lock = getattr(self, "_lock", None)
         if lock:
             with lock:
                 try:
                     return self.extra[key]
                 except KeyError:
                      raise KeyError(f"在 extra 字典中未找到必需的键 '{key}'")
         else: # 无锁环境
             try:
                 return self.extra[key]
             except KeyError:
                 raise KeyError(f"在 extra 字典中未找到必需的键 '{key}'")