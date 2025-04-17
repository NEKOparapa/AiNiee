import os
import re
import threading

from Base.Base import Base
from ModuleFolders.LLMRequester.LLMRequester import LLMRequester


# 接口测试器(后面改造成通用请求器，用来承担UI触发的各种额外的请求任务，接口测试可以和流程测试合并)
class RequestTester(Base):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 订阅接口测试开始事件
        self.subscribe(Base.EVENT.API_TEST_START, self.api_test_start)

        # 订阅术语表翻译开始事件
        self.subscribe(Base.EVENT.GLOSS_TRANSLATION_START, self.glossary_translation_start)

    # 响应接口测试开始事件
    def api_test_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.api_test, args = (event, data))
        thread.start()

    # 接口测试
    def api_test(self, event, data: dict):
        # 获取参数
        platform_tag = data.get("tag")
        platform_name = data.get("name")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        proxy_url = data.get("proxy_url")
        proxy_enable = data.get("proxy_enable")
        extra_body = data.get("extra_body",{})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")

        # 自动补全API地址
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"

        # 获取并设置网络代理
        if proxy_enable == False or proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            self.info(f"系统代理已启用，代理地址：{proxy_url}")

        # 测试结果
        failure = []
        success = []

        # 解析并分割密钥字符串
        api_keys = re.sub(r"\s+","", api_key).split(",")

        # 轮询所有密钥进行测试
        for api_key in api_keys:

            # 构建 Prompt
            messages = [
                {
                    "role": "user",
                    "content": "小可爱，你在干嘛"
                }
            ]
            system_prompt = "你接下来要扮演我的女朋友，名字叫欣雨，请你以女朋友的方式回复我。"

            # 打印日志
            self.print("")
            self.info("正在进行接口测试 ...")
            self.info(f"接口名称 - {platform_name}")
            self.info(f"接口地址 - {api_url}")
            self.info(f"接口密钥 - {'*'*(len(api_key)-8)}{api_key[-8:]}") # 隐藏敏感信息
            self.info(f"模型名称 - {model_name}")
            if extra_body:
                self.info(f"额外参数 - {extra_body}")
            self.print(f"系统提示词 - {system_prompt}")
            self.print(f"信息内容 - {messages}")

            # 构建配置包
            platform_config = {
                "target_platform": platform_tag,
                "api_url": api_url,
                "api_key": api_key,
                "api_format": api_format,
                "model_name": model_name,
                "region":  region,
                "access_key":  access_key,
                "secret_key": secret_key,
                "extra_body": extra_body
            }

            #尝试请求
            requester = LLMRequester()
            skip, response_think, response_content, prompt_tokens, completion_tokens = requester.sent_request(
                messages,
                system_prompt,
                platform_config
            )

            # 测试成功
            if skip == False:
                self.info("接口测试成功 ...")
                self.info(f"接口返回信息 - {response_content}")
                # 储存结果
                success.append(api_key)

            # 测试失败
            else:
                self.error(f"接口测试失败 ... ")
                # 储存结果
                failure.append(api_key)

            self.print("")

        # 打印结果
        self.print("")
        self.info(f"接口测试结果：共测试 {len(api_keys)} 个接口，成功 {len(success)} 个，失败 {len(failure)} 个 ...")
        if len(failure) >0:
            self.error(f"失败的接口密钥 - {", ".join(failure)}")
        self.print("")

        # 发送完成事件
        self.emit(Base.EVENT.API_TEST_DONE, {
            "failure": failure,
            "success": success,
        })


    # 响应术语表翻译开始事件
    def glossary_translation_start(self, event: int, data: dict):
        thread = threading.Thread(target = self.glossary_translation, args = (event, data))
        thread.start()

    # 术语表翻译
    def glossary_translation(self, event, data: dict):
        # 获取参数
        platform_tag = data.get("tag")
        platform_name = data.get("name")
        api_url = data.get("api_url")
        api_key = data.get("api_key")
        api_format = data.get("api_format")
        model_name = data.get("model")
        auto_complete = data.get("auto_complete")
        proxy_url = data.get("proxy_url")
        proxy_enable = data.get("proxy_enable")
        extra_body = data.get("extra_body",{})
        region = data.get("region")
        access_key = data.get("access_key")
        secret_key = data.get("secret_key")
        target_language = data.get("target_language")

        prompt_dictionary_data = data.get("prompt_dictionary_data")
        if not prompt_dictionary_data:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TRANSLATION_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 自动补全API地址
        if platform_tag == "sakura" and not api_url.endswith("/v1"):
            api_url += "/v1"
        elif auto_complete:
            version_suffixes = ["/v1", "/v2", "/v3", "/v4"]
            if not any(api_url.endswith(suffix) for suffix in version_suffixes):
                api_url += "/v1"

        # 获取并设置网络代理
        if proxy_enable == False or proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            self.info(f"系统代理已启用，代理地址：{proxy_url}")

        # 解析并分割密钥字符串，并只取第一个密钥进行测试
        api_keys = re.sub(r"\s+","", api_key).split(",")
        api_key = api_keys[0]


        # 获取未翻译术语
        untranslated_items = [item for item in prompt_dictionary_data if not item.get("dst")]
        if not untranslated_items:
            self.info("没有需要翻译的术语")
            self.emit(Base.EVENT.GLOSS_TRANSLATION_DONE, {
                "status": "null",
                "updated_data": prompt_dictionary_data
            })
            return

        # 分组处理（每组最多50个）
        group_size = 50
        translated_count = 0
        total_groups = (len(untranslated_items) + group_size - 1) // group_size

        # 输出整体进度信息
        print("")
        self.info(f" 开始术语表循环翻译 \n"
                f"├ 未翻译术语总数: {len(untranslated_items)}\n"
                f"├ 分组数量: {total_groups}\n"
                f"└ 每组上限: {group_size}术语")
        print("")

        # 构建平台配置
        platform_config = {
            "target_platform": platform_tag,
            "api_url": api_url,
            "api_key": api_key,
            "api_format": api_format,
            "model_name": model_name,
            "region": region,
            "access_key": access_key,
            "secret_key": secret_key,
            "extra_body": extra_body
        }

        # 分组翻译处理
        for group_idx in range(total_groups):
            start_idx = group_idx * group_size
            end_idx = start_idx + group_size
            current_group = untranslated_items[start_idx:end_idx]
            
            # 组处理开始日志
            print("")
            self.info(f" 正在处理第 {group_idx+1}/{total_groups} 组 \n"
                    f"├ 本组术语范围: {start_idx+1}-{min(end_idx, len(untranslated_items))}\n"
                    f"└ 实际处理数量: {len(current_group)}术语")
            print("")

            # 构造系统提示词
            system_prompt = (
                f"Translate the source text from the glossary into {target_language} line by line, maintaining accuracy and naturalness, and output the translation wrapped in a textarea tag:\n"
                "<textarea>\n"
                f"1.{target_language}text\n"
                "</textarea>\n"
            )

            # 构造消息内容，按行排列，并添加序号
            src_terms = [f"{idx+1}.{item['src']}" for idx, item in enumerate(current_group)]
            src_terms_text = "\n".join(src_terms)
            messages = [
                {
                    "role": "user",
                    "content": src_terms_text
                }
            ]

            # 请求发送日志
            print("")
            self.info(
                    f" 正在发送API请求...\n"
                    f"│ 平台类型: {platform_tag}\n"
                    f"│ 模型名称: {model_name}\n"
                    f"└ 目标语言: {target_language}")
            print("")

            # 发送翻译请求
            requester = LLMRequester()
            skip, _, response_content, _, _ = requester.sent_request(
                messages,
                system_prompt,
                platform_config
            )

            # 如果请求失败，返回失败信息
            if skip:
                self.error(f"第 {group_idx+1}/{total_groups} 组翻译失败")
                self.emit(Base.EVENT.GLOSS_TRANSLATION_DONE, {
                    "status": "error",
                    "message": f"第 {group_idx+1} 组翻译请求失败",
                    "updated_data": None
                })
                return

            # 如果请求成功，解析翻译结果
            try:
                # 提取译文结果
                textarea_contents = re.findall(r'<textarea.*?>(.*?)</textarea>', response_content, re.DOTALL)
                last_content = textarea_contents[-1]

                # 分行
                translated_terms = last_content.strip().split("\n")
                
                # 去除序号
                translated_terms = [re.sub(r'^\d+\.', '', term).strip() for term in translated_terms]

                # 检查翻译结果数量是否匹配
                if len(translated_terms) != len(current_group):
                    raise ValueError("翻译结果数量不匹配")
                    
            except Exception as e:
                self.error(f"翻译结果解析失败: {str(e)}")
                self.emit(Base.EVENT.GLOSS_TRANSLATION_DONE, {
                    "status": "error",
                    "message": f"第 {group_idx+1} 组结果解析失败",
                    "updated_data": None
                })
                return

            # 更新翻译结果
            for idx, item in enumerate(current_group):
                item["dst"] = translated_terms[idx]
            translated_count += len(current_group)

            # 进度更新日志
            print("")
            self.info(
                    f"├ 本组完成数量: {len(current_group)}\n"
                    f"├ 累计完成进度: {translated_count}/{len(untranslated_items)}\n"
                    f"└ 进度百分比: {translated_count/len(untranslated_items):.0%}")
            print("")

        # 全部完成
        self.info(f" 术语表翻译全部完成 \n"
                f"├ 总处理组数: {total_groups}\n"
                f"├ 总翻译术语: {translated_count}\n"
                f"└ 最终状态: {'成功' if translated_count == len(untranslated_items) else '失败'}")
        
        # 发送完成事件
        self.emit(Base.EVENT.GLOSS_TRANSLATION_DONE, {
            "status": "success",
            "updated_data": prompt_dictionary_data
        })