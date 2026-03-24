import copy
import threading
from contextlib import contextmanager
from dataclasses import dataclass, fields
from functools import cache
from reprlib import Repr
from types import UnionType
from typing import Any, ClassVar, Union, get_args, get_origin

_ATOMIC_TYPES = frozenset([
    bool,
    int,
    float,
    str,
])


@cache
def _get_fields(cls):
    return fields(cls)


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
        for f in _get_fields(self.__class__):
            name = f.name
            value = getattr(self, name)
            # 默认None不参与dict转换
            if name.startswith("_") or (value is None and not keep_none):
                continue
            else:
                result[name] = self._to_dict_part(value, keep_none)
        return result

    @classmethod
    def _from_define(cls, type_, data) -> Any:
        if type(type_) is type:
            if type_ in _ATOMIC_TYPES and type(data) in _ATOMIC_TYPES:
                # 基本数据类型
                return data
            elif issubclass(type_, DictMixin) and isinstance(data, dict):
                return type_.from_dict(data)
            elif hasattr(type_, "_fields") and issubclass(type_, tuple) and isinstance(data, (list, tuple)):
                return type_(*(cls._from_define(Any, x) for x in data))
            elif data is None:
                return None
            raise ValueError(f"不能从定义 {type_} 加载数据 {data}")
        elif type_ is Any:
            return copy.deepcopy(data)
        elif data is None:
            return None

        type_origin = get_origin(type_)
        args = get_args(type_)

        # 容器类型必须定义泛型
        if type_origin is None or args is None:
            raise ValueError(f"不支持的类型 {type_} {data} {args}")
        elif type_origin in [Union, UnionType]:  # Union类型的处理
            # 尝试使用能够匹配的第一个类型
            for arg in args:
                if arg is type(None) and data is None:
                    return None
                try:
                    return cls._from_define(arg, data)
                except (ValueError, TypeError):
                    continue
            # 如果都不匹配，直接返回数据
            return data
        elif issubclass(type_origin, tuple) and isinstance(data, (list, tuple)):
            # 元组
            if len(args) == 2 and args[1] is Ellipsis:
                # tuple[int, ...]
                return type_(cls._from_define(args[0], x) for x in data)
            else:
                # tuple[int, str, float, int]
                if len(args) != len(data):
                    raise ValueError(f"元组的定义 {type_} 不符合数据 {data}")
                return type_(cls._from_define(arg, dat) for arg, dat in zip(args, data))
        elif issubclass(type_origin, (list, set, frozenset)) and isinstance(data, (list, set, frozenset)):
            # 集合
            return type_origin(cls._from_define(args[0], x) for x in data)
        elif issubclass(type_origin, dict) and isinstance(data, dict):
            # 字典
            key_type, value_type = args
            if hasattr(type_origin, 'default_factory'):
                # defaultdict
                return type_origin(value_type, (
                    (cls._from_define(key_type, k), cls._from_define(value_type, v))
                    for k, v in data.items()
                ))
            else:
                return type_origin(
                    (cls._from_define(key_type, k), cls._from_define(value_type, v))
                    for k, v in data.items()
                )
        else:
            raise ValueError(f"不能从定义 {type_} 加载数据 {data}")

    @classmethod
    def from_dict[T: DictMixin](cls: type[T], data: dict[str, Any]) -> T:
        # dacite 会覆盖__post_init__的属性，所以不用
        init_vars = {}
        for field_ in _get_fields(cls):
            field_name = field_.name
            field_type = field_.type
            if field_name in data:
                init_vars[field_name] = cls._from_define(field_type, data[field_name])
        return cls(**init_vars)

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

    @property
    def _lock(self):
        return self._LOCK_POOL[id(self) % self._LOCK_POOL_SIZE]

    @contextmanager
    def atomic_scope(self):
        """一次读/写多个属性"""
        with self._lock:
            yield

    def to_dict(self, keep_none=False) -> dict[str, Any]:
        with self._lock:
            return super().to_dict(keep_none)

    # 质数减少取模后的碰撞
    _LOCK_POOL_SIZE: ClassVar[int] = 997
    _LOCK_POOL: ClassVar[tuple[threading.RLock]] = tuple(threading.RLock() for _ in range(_LOCK_POOL_SIZE))


class ExtraMixin:
    """统一管理extra属性的方法"""

    def _extra(self) -> dict[str, Any]:
        raise NotImplementedError

    def set_extra(self, key, value):
        if value is not None:
            self._extra()[key] = value

    def get_extra(self, key, default=None):
        return self._extra().get(key, default)

    def require_extra(self, key):
        return self._extra()[key]
