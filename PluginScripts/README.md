
# 插件系统编写指南
欢迎来到插件系统编写指南！本文档将帮助您了解如何为项目编写插件


## 目录
1. [插件编写步骤](#插件编写步骤)
2. [继承插件基类](#继承插件基类)
3. [事件触发说明](#事件触发说明)
4. [示例代码](#示例代码)
5. [插件事件介绍](#插件事件介绍)
6. [贡献指南](#贡献指南)



## 插件编写步骤
1. **环境准备**
   确保您的开发环境满足以下要求：
   - Python 3.12
   - 相关依赖库（请查看`requirements.txt`）
2. **创建插件文件**
   在项目的`Plugin_Scripts`目录下创建新的子文件夹，并创建新的Python文件，例如`my_plugin.py`。
3. **编写插件代码**
   按照以下模板编写您的插件代码，并确保继承自`PluginBase`类。


## 继承插件基类
所有插件必须继承自`PluginBase`类。以下是`PluginBase`类的简化定义：
```python
class Priority():

    HIGHEST    = 700
    HIGHER     = 600
    HIGH       = 500
    NORMAL     = 400
    LOW        = 300
    LOWER      = 200
    LOWEST     = 100

class PluginBase:

    def __init__(self) -> None:
        self.name = "Unnamed Plugin"
        self.description = "No description provided."

        self.visibility = True      # 是否在插件设置中显示
        self.default_enable = True  # 默认启用状态

        self.events = []            # 插件感兴趣的事件列表，使用字典存储事件名和优先级

    # 加载插件时调用
    def load(self) -> None:
        pass

    # 处理事件
    def on_event(self, event: str, config: TranslatorConfig, event_data: any) -> None:
        pass

    # 添加事件
    def add_event(self, event: str, priority: int) -> None:
        self.events.append(
            {
                "event": event,
                "priority": priority,
            }
        )
```
在编写插件时，您需要创建一个继承自`PluginBase`的新类，并实现必要的方法。


## 事件触发说明
插件可以通过重写 `on_event` 方法来监听和响应事件。以下是事件触发的基本流程：

1. **添加监听事件**
   使用 `add_event` 方法，添加监听的事件及该事件触发的优先级；
   优先级为枚举值，从 `LOWEST` 到 `HIGHEST`，默认为 `NORMAL`；

3. **重写事件处理方法**
   在您的插件类中重写 `on_event` 方法，该方法将接收事件名称和数据。

4. **监听事件**
   在 `on_event` 方法内部，根据事件名称执行相应的逻辑。

## 示例代码
以下是一个简单的插件示例，它继承自 `PluginBase` 并监听了 `manual_export` 、 `preproces_text` 、 `postprocess_text` 事件：
```python
from Plugin_Scripts.PluginBase import PluginBase

class ExamplePlugin(PluginBase):

    def __init__(self) -> None:
        super().__init__()
        self.name = "ExamplePlugin"
        self.description = "This is a Example Plugin ..."

        self.visibility = True          # 是否在插件设置中显示
        self.default_enable = False     # 默认启用状态

        self.add_event("manual_export", PluginBase.PRIORITY.NORMAL)
        self.add_event("preproces_text", PluginBase.PRIORITY.NORMAL)
        self.add_event("postprocess_text", PluginBase.PRIORITY.NORMAL)

    def on_event(self, event: str, config: TranslatorConfig, event_data: list[dict]) -> None:
        if event == "preproces_text":
            self.on_preproces_text(event, config, event_data)

        if event in ("manual_export", "postprocess_text"):
            self.on_postprocess_text(event, config, event_data)

    # 文本预处理事件
    def on_preproces_text(self, event: str, config: TranslatorConfig, event_data: list[dict]) -> None:
        pass

    # 文本后处理事件
    def on_postprocess_text(self, event: str, config: TranslatorConfig, event_data: list[dict]) -> None:
        pass
```


## 插件事件介绍
翻译任务执行过程中会触发以下事件，并提供相应的参数供其他插件或功能模块使用，下面事件触发顺序大致由上到下。


### 文本预过滤事件：text_filter

1. **触发位置**

    在读取原文文件后，在文本预处理事件前触发

2. **传入参数**

    | 参数名 | 类型 | 描述 |
    | ------ | ---- | ---- |
    | event_name | string | text_filter |
    | config | TranslatorConfig | 全局类，包含了在整个应用范围内共享的的配置信息 |
    | event_data | list | 全局缓存文本数据，格式与导出的缓存文件一致 |



### 文本预处理事件：preproces_text

1. **触发位置**

    在文本预过滤事件后，开始请求前触发。

2. **传入参数**

    | 参数名 | 类型 | 描述 |
    | ------ | ---- | ---- |
    | event_name | string | preproces_text |
    | config | TranslatorConfig | 全局类，包含了在整个应用范围内共享的的配置信息 |
    | event_data | list | 全局缓存文本数据，格式与导出的缓存文件一致 |


    - `event_data`: 全局缓存文本数据，格式与导出的缓存文件一致。
    ```json
   [
       {
           "row_index": 0,                                                # 在原始文件中的行号
           "text_index": 3,                                               # 在整个翻译任务中的索引号
           "translation_status": 1,                                       # 翻译状态，枚举值：0 - 待翻译，1 - 已翻译，2 - 翻译中，7 - 已排除
           "model": "gpt-4o",                                             # 翻译使用的模型
           "source_text": "「すまない、ダリヤ。婚約を破棄させてほしい」",     # 原文
           "translated_text": "「对不起，达莉亚。请允许我解除婚约」",        # 译文
           "file_name": "sample.txt",                                     # 原始文件名
           "storage_path": "sample.txt",                                  # 原始路径
       },
       {},
   ]
    ```


### 发送前文本规范事件：normalize_text

1. **触发位置**

    每次获取到待翻译文本，发送请求前触发。

2. **传入参数**

    | 参数名 | 类型 | 描述 |
    | ------ | ---- | ---- |
    | event_name | string | normalize_text |
    | config | TranslatorConfig | 全局类，包含了在整个应用范围内共享的的配置信息 |
    | event_data | dict | 本次任务的待翻译的原文文本 |


    因为没有返回参数，需要直接处理输入的参数event_data


    - `event_data`: 本次任务的待翻译的原文文本，json格式，key值是从0开始的数字序号
    ```json
    {
        "0": "弾：ゾンビ攻撃",
        "1": "敵：タイムボム",
        "2": "敵：スコーピオン",
        "3": "敵：プチデビル：リ",
        "4": "プチデビルのリスポーン用です。"
    }
    ```

### 文本后处理事件：postprocess_text

1. **触发位置**

    翻译完成，翻译文件输出前。

2. **传入参数**

    | 参数名 | 类型 | 描述 |
    | ------ | ---- | ---- |
    | event_name | string | postprocess_text |
    | config | TranslatorConfig | 全局类，包含了在整个应用范围内共享的的配置信息 |
    | event_data | list | 全局缓存文本数据，格式与导出的缓存文件一致 |


### 手动导出事件：manual_export

1. **触发位置**

    用户使用“手动导出翻译文件功能”，在翻译文件导出前触发。

2. **传入参数**

    | 参数名 | 类型 | 描述 |
    | ------ | ---- | ---- |
    | event_name | string | manual_export |
    | config | TranslatorConfig | 全局类，包含了在整个应用范围内共享的的配置信息 |
    | event_data | list | 全局缓存文本数据，格式与导出的缓存文件一致 |


### 翻译完成事件：translation_completed

1. **触发位置**

    翻译完成，写出翻译文件后，任务即将退出前。

2. **传入参数**

    | 参数名 | 类型 | 描述 |
    | ------ | ---- | ---- |
    | event_name | string | translation_completed |
    | config | TranslatorConfig | 全局类，包含了在整个应用范围内共享的的配置信息 |
    | event_data | list | 全局缓存文本数据，格式与导出的缓存文件一致 |

## 贡献指南
1. Fork本项目
2. 创建您的特性分支 (`git checkout -b my-new-feature`)
3. 提交您的改动 (`git commit -am 'Add some feature'`)
4. 将您的分支推送到 GitHub (`git push origin my-new-feature`)
5. 创建新的Pull Request
