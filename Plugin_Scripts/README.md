
# 插件系统编写指南
欢迎来到插件系统编写指南！本文档将帮助您了解如何为项目编写插件


## 目录
1. [插件编写步骤](#插件编写步骤)
2. [继承插件基类](#继承插件基类)
3. [事件触发说明](#事件触发说明)
4. [传入参数介绍](#传入参数介绍)
5. [示例代码](#示例代码)
6. [贡献指南](#贡献指南)



## 插件编写步骤
1. **环境准备**
   确保您的开发环境满足以下要求：
   - Python 3.9
   - 相关依赖库（请查看`requirements.txt`）
2. **创建插件文件**
   在项目的`Plugin_Scripts`目录下创建新的子文件夹，并创建新的Python文件，例如`my_plugin.py`。
3. **编写插件代码**
   按照以下模板编写您的插件代码，并确保继承自`PluginBase`类。


## 继承插件基类
所有插件必须继承自`PluginBase`类。以下是`PluginBase`类的简化定义：
```python
class PluginBase:
    def __init__(self):
        self.name = "Unnamed Plugin"
        self.description = "No description provided."

    def load(self):
        """加载插件时调用"""
        pass

    def on_event(self, event_name, configuration_information, event_data):
        """处理事件"""
        pass

```
在编写插件时，您需要创建一个继承自`PluginBase`的新类，并实现必要的方法。



## 事件触发说明
插件可以通过重写`on_event`方法来监听和响应事件。以下是事件触发的基本流程：

1. **重写事件处理方法**
   在您的插件类中重写`on_event`方法，该方法将接收事件名称和数据。

2. **监听事件**
   在`on_event`方法内部，根据事件名称执行相应的逻辑。

以下是一些可能的事件示例：
- `preproces_text`: 读取原文文件到缓存中，开始请求前触发。
- `postprocess_text`: 翻译完成，输出文件前触发。


## 传入参数介绍

- `configuration_information`: 全局配置类，用于获取和设置应用程序的配置信息。

- `event_data`: 当前事件数据，目前是传入缓存文本信息。
```python
    """
    缓存数据以列表来存储，分文件头（第一个元素）和文本单元(后续元素)，文件头数据结构如下:
    1.项目类型： "project_type"
    2.项目ID： "project_id"

    文本单元的部分数据结构如下:
    1.翻译状态： "translation_status"   未翻译状态为0，已翻译为1，正在翻译为2，不需要翻译为7
    2.文本索引： "text_index"
    3.名字： "name"
    4.原文： "source_text"
    5.译文： "translated_text"
    6.存储路径： "storage_path"
    7.存储文件名： "storage_file_name"
    8.翻译模型： "model"                         
    等等

    """

```


## 示例代码
以下是一个简单的插件示例，它继承自`PluginBase`并监听了`preproces_text`事件：
```python
from ..Plugin_Base.Plugin_Base import PluginBase
class GreetingPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "example_Plugin"
        self.description = "This is an example plugin."

    def load(self):
        print(f"[INFO]  {self.name} loaded!")

    def on_event(self, event_name, configuration_information, event_data):
        # 事件触发
        if event_name == "preproces_text":

            # 如果翻译日语或者韩语文本时，则去除非中日韩文本
            if  configuration_information.source_language == "日语" or  configuration_information.source_language == "韩语":
                
                # 过滤文本
                self.preproces_text(event_data)

                print(f"[INFO]  Non-Japanese/Korean text has been filtered.")
```



## 贡献指南
1. Fork本项目
2. 创建您的特性分支 (`git checkout -b my-new-feature`)
3. 提交您的改动 (`git commit -am 'Add some feature'`)
4. 将您的分支推送到GitHub (`git push origin my-new-feature`)
5. 创建新的Pull Request
