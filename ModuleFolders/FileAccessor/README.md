
# 读写器 (Reader / Writer) 系统编写指南

欢迎来到读写器系统编写指南！本文档将帮助您了解如何为项目编写读写器

## 目录

- [读写器 (Reader / Writer) 系统编写指南](#读写器-reader--writer-系统编写指南)
  - [目录](#目录)
  - [读写器编写步骤](#读写器编写步骤)
  - [Reader介绍](#reader介绍)
    - [Reader基类](#reader基类)
    - [Reader生命周期](#reader生命周期)
    - [Reader示例代码](#reader示例代码)
  - [Writer介绍](#writer介绍)
    - [Writer基类](#writer基类)
    - [Writer生命周期](#writer生命周期)
    - [Writer示例代码](#writer示例代码)
  - [Accessor介绍（可选）](#accessor介绍可选)
  - [贡献指南](#贡献指南)

## 读写器编写步骤

1. **环境准备**
   确保您的开发环境满足以下要求：
   - Python 3.12
   - 相关依赖库（请查看 `requirements.txt` ）
2. **读写器文件**
   在项目的 `ModuleFolders/FileReader` 和 `ModuleFolders/FileOutputer` 目录下创建新的 `.py` 文件， 例如 `XXXReader.py, XXXWriter.py` 。
3. **编写读写器代码** 按照以下模板编写您的读写器代码，并确保继承自对应的基类。
4. **复杂文件访问（可选）** 部分文件的读写逻辑比较复杂，可以把文件本身的读写逻辑抽取出来，参考 `DocxAccessor` 。

## Reader介绍

### Reader基类

在编写Reader时，您需要创建一个继承自 `BaseSourceReader` 的新类，并实现 `get_project_type`、`support_file`和`read_source_file` 方法。

以下是 `BaseSourceReader` 类的简化定义：

```python
class BaseSourceReader(ABC):
    """Reader基类，在其生命周期内可以输入多个文件"""
    def __init__(self, input_config: InputConfig) -> None:
        self.input_config = input_config

    def __enter__(self):
        """申请整个Reader生命周期用到的耗时资源，单个文件的资源则在read_source_file方法中申请释放"""
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """释放耗时资源"""
        pass

    @classmethod
    @abstractmethod
    def get_project_type(cls) -> str:
        """获取Reader对应的项目类型标识符（用于动态实例化），如 Mtool"""
        pass

    @property
    @abstractmethod
    def support_file(self) -> str:
        """该读取器支持处理的文件扩展名（不带点），如 json"""
        pass

    @abstractmethod
    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        """读取文件内容，并返回原文(译文)片段"""
        pass

    def can_read(self, file_path: Path) -> bool:
        """验证文件兼容性，返回False则不会读取该文件"""
        if file_path.suffix.replace('.', '', 1) != self.support_file:
            return False
        return True
```

### Reader生命周期

1. **Reader注册**
   - 所有的Reader都通过 `FileReader` 的 `register_reader` 方法注册
   - 为保证通用性，注册的内容为 Reader工厂，可以简单理解为一个创建 Reader 的函数

2. **Reader实例化**

   - `FileReader` 结合用户选择的 项目设置 -> 项目类型 和 `get_project_type` 中声明的项目类型，实例化对应的Reader
   - 每个Reader都被包装在 `DirectoryReader` 中，在读取目录前执行 `__enter__` 申请耗时资源
   - `DirectoryReader` 会把目录下的文件**一个一个**的传给Reader

3. **文件读取**

    Reader接收的文件满足 `can_read` 则执行 `read_source_file` 方法

4. **Reader销毁**

    当 `DirectoryReader` 读取完目录后，Reader 销毁，执行 `__exit__` 释放资源

### Reader示例代码

以下是 `TxtReader` 的示例

1. 用户界面的 Txt小说文件 对应 `get_project_type` 里声明的 `Txt`
2. 该Reader只支持 `support_file` 中声明的 `txt` 类型文件类型
3. 在 `read_source_file` 读取源文件，把源文档会被分拆成多个片段，并返回原文片段列表 `list[CacheItem]`
4. `CacheItem` 中只定义了通用的属性，若实在有需要可直接给 `CacheItem` 赋值，如 `item.sentence_indent = spaces`
5. 为保持可读性和可维护性，一些复杂的计算逻辑可提取成函数如 `_count_next_empty_line`

```python
class TxtReader(BaseSourceReader):
    def __init__(self, input_config: InputConfig, max_empty_line_check=2):
        super().__init__(input_config)
        self.max_empty_line_check = max_empty_line_check

    @classmethod
    def get_project_type(cls):
        return "Txt"

    @property
    def support_file(self):
        return "txt"

    def read_source_file(self, file_path: Path) -> list[CacheItem]:
        items = []
        # 切行
        lines = file_path.read_text(encoding='utf-8').split('\n')
        for j, line in enumerate(lines):
            if line.strip() == '':  # 跳过空行
                continue
            spaces = len(line) - len(line.lstrip())  # 获取行开头的空格数
            item = text_to_cache_item(line)
            item.sentence_indent = spaces
            item.line_break = self._count_next_empty_line(lines, j)
            items.append(item)
        return items

    def _count_next_empty_line(self, lines, line_index):
        """检查后续行是否连续空行，最多检查 max_empty_line_check 行"""
        max_empty_line_check = self.max_empty_line_check if self.max_empty_line_check is not None else len(lines)
        empty_line_index = line_index
        for empty_line_index in range(line_index + 1, min(len(lines), line_index + 1 + max_empty_line_check)):
            if lines[empty_line_index].strip() != '':
                empty_line_index -= 1
                break
        return empty_line_index - line_index
```

## Writer介绍

### Writer基类

Writer可能有多份输出，比如既要输出译文文件又要输出双语文件

1. 所有Writer必须间接继承自 `BaseTranslationWriter` 类且实现 `get_project_type` 方法
2. 如果只做译文输出则继承 `BaseTranslatedWriter` 类且实现 `write_translated_file` 方法
3. 如果要同时做译文输出和双语输出，则要同时继承 `BaseTranslatedWriter` 和 `BaseBilingualWriter` 类且实现对应的方法

以下是这些类的简化定义

```python
class BaseTranslationWriter(ABC):
    """Writer基类，在其生命周期内可以输出多个文件"""
    def __init__(self, output_config: OutputConfig) -> None:
        self.output_config = output_config

    NOT_TRANSLATED_STATUS = (CacheItem.STATUS.UNTRANSLATED, CacheItem.STATUS.TRANSLATING)

    def __enter__(self):
        """申请整个Writer生命周期用到的耗时资源，单个文件的资源则在write_xxx_file方法中申请释放"""
        return self

    def __exit__(self, exc_type, exc, exc_tb):
        """释放耗时资源"""
        pass

    @classmethod
    @abstractmethod
    def get_project_type(self) -> str:
        """获取Writer对应的项目类型标识符（用于动态实例化），如 Mtool"""
        pass


class BaseTranslatedWriter(BaseTranslationWriter):
    """译文输出基类"""

    @abstractmethod
    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        """输出译文文件"""
        pass


class BaseBilingualWriter(BaseTranslationWriter):
    """双语输出基类"""

    @abstractmethod
    def write_bilingual_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        """输出双语文件"""
        pass
```

### Writer生命周期

1. **Writer注册**
   - 所有的Writer都在 `FileOutputer` 实例化的时候通过 `_register_system_Writer` 方法注册
   - 为保证通用性，注册的内容为 Writer工厂，可以简单理解为一个创建 Writer 的函数

2. **Writer实例化**

   - `FileOutputer` 结合用户选择的 项目设置 -> 项目类型 和 `get_project_type` 中声明的项目类型，实例化对应的Writer
   - 每个Writer都被包装在 `DirectoryWriter` 中，在写入目录前执行 `__enter__` 申请耗时资源
   - `DirectoryWriter` 会把目录下的文件**一个一个**的传给Writer

3. **文件输出**

    1. 当Writer的 `output_config` 中 `enable` 了对应的输出方式
    2. 正确的继承了对应的输出基类
    3. 则执行具体的 `write_xxx_file` 方法，如译文输出就是 `write_translated_file`
    4. 部分文档需要保留原文的复杂样式，此时可使用方法参数中的 `source_file_path` 读取到源文档，再结合译文做文档重构，参考 `RenpyWriter`

4. **Writer销毁**

    当 `DirectoryWriter` 读取完目录后，Writer 销毁，执行 `__exit__` 释放资源

### Writer示例代码

以下是 `TxtWriter` 的配置

1. `TxtWriter` 要同时支持译文输出和双语输出，所以 `bilingual_config.enable` 也是 `True`
2. `name_suffix` 代表输出文件的后缀，如果后缀是 `_translated`，那么 `aaa.txt` 的译文文件名是 `aaa_translated.txt`
3. `output_root` 代表输出的根目录，也就是用户界面 项目配置 -> 输出文件夹，此处译文文件直接在 输出文件夹 下输出，而双语文件在 输出文件夹的子文件夹`bilingual_txt` 下输出

```python
OutputConfig(
    translated_config=TranslationOutputConfig(
        enabled=True, name_suffix="_translated", output_root=output_path
    ),
    bilingual_config=TranslationOutputConfig(
        enabled=True, name_suffix="_bilingual", output_root=output_path / "bilingual_txt"
    ),
)
```

以下是 `TxtWriter` 的示例

1. 用户界面的 Txt小说文件 对应 `get_project_type` 里声明的 `Txt`
2. 该Writer要支持译文输出和双语输出，于是继承了 `BaseBilingualWriter` 和 `BaseTranslatedWriter`
3. 在 `write_bilingual_file` 方法中输出双语文件，在 `write_translated_file` 方法中输出译文文件
4. 译文和双语的区别在于怎么替换原文片段，建议抽出公共方法如 `_write_translation_file`，把替换原文片段的逻辑作为参数传入
5. 此处用到了 `CacheItem` 中未定义的属性 `item.sentence_indent` ，如果不保证属性存在请使用 `getattr`

```python
class TxtWriter(BaseBilingualWriter, BaseTranslatedWriter):
    def __init__(self, output_config: OutputConfig):
        super().__init__(output_config)

    def write_bilingual_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None,
    ):
        self._write_translation_file(translation_file_path, items, self._item_to_bilingual_line)

    def write_translated_file(
        self, translation_file_path: Path, items: list[CacheItem],
        source_file_path: Path = None
    ):
        self._write_translation_file(translation_file_path, items, self._item_to_translated_line)

    def _write_translation_file(
        self, translation_file_path: Path, items: list[CacheItem],
        item_to_line: Callable[[CacheItem], str],
    ):
        lines = list(map(item_to_line, items))
        translation_file_path.write_text("".join(lines), encoding="utf-8")

    def _item_to_bilingual_line(self, item: CacheItem):
        indent = "　" * item.sentence_indent
        # 至少2个换行，让双语排版不那么紧凑
        line_break = "\n" * max(item.line_break + 1, 2)
        return (
            f"{indent}{item.get_source_text().lstrip()}\n"
            f"{indent}{item.get_translated_text().lstrip()}{line_break}"
        )

    def _item_to_translated_line(self, item: CacheItem):
        indent = "　" * item.sentence_indent
        line_break = "\n" * (item.line_break + 1)
        return f"{indent}{item.get_translated_text().lstrip()}{line_break}"

    @classmethod
    def get_project_type(self):
        return "Txt"
```

## Accessor介绍（可选）

1. Accessor主要是把复杂的文件读写逻辑从 Reader/Writer 中剥离，通过 `content` 与 Reader/Writer 交互
2. Reader/Writer 只用关心如何读取/修改 `content`，而具体怎么从文件中读取 `content` 还是把 `content` 写入到文件则由Accessor负责
3. 参考`DocxReader` 和 `DocxWriter` 读取和写入都用到了 `DocxAccessor` 的 `read_content` 方法

## 贡献指南

1. Fork本项目
2. 创建您的特性分支 (`git checkout -b my-new-feature`)
3. 提交您的改动 (`git commit -am 'Add some feature'`)
4. 将您的分支推送到 GitHub (`git push origin my-new-feature`)
5. 创建新的Pull Request
