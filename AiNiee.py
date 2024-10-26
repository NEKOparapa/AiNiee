
# 
#                        _oo0oo_
#                       o8888888o
#                       88" . "88
#                       (| -_- |)
#                       0\  =  /0
#                     ___/`---'\___
#                   .' \\|     |// '.
#                  / \\|||  :  |||// \
#                 / _||||| -:- |||||- \
#                |   | \\\  -  /// |   |
#                | \_|  ''\---/''  |_/ |
#                \  .-\__  '-'  ___/-. /
#              ___'. .'  /--.--\  `. .'___
#           ."" '<  `.___\_<|>_/___.' >' "".
#          | | :  `- \`.;`\ _ /`;.`/ - ` : | |
#          \  \ `_.   \_ __\ /__ _/   .-` /  /
#      =====`-.____`.___ \_____/___.-`___.-'=====
#                        `=---='
# 
# 
#      ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# 
#             赛博佛祖光耀照，程序运行永无忧。
#             翻译之路顺畅通，字字珠玑无误漏。



# coding:utf-8               
import copy
import datetime
import json
import time
import threading
import os
import sys
import multiprocessing
import concurrent.futures
from rich import print


import cohere  # 需要安装库pip install cohere
import anthropic # 需要安装库pip install anthropic
import google.generativeai as genai # 需要安装库pip install -U google-generativeai
from openai import OpenAI # 需要安装库pip install openai


from PyQt5.QtGui import QFont
from PyQt5.QtCore import  QObject,  Qt, pyqtSignal
from PyQt5.QtWidgets import QApplication
from qfluentwidgets import InfoBar, InfoBarPosition, StateToolTip

from Base.AiNieeBase import AiNieeBase
from StevExtraction import jtpp  # type: ignore #导入文本提取工具
from Module_Folders.Cache_Manager.Cache import Cache_Manager  
from Module_Folders.File_Reader.File1 import File_Reader 
from Module_Folders.File_Outputer.File2 import File_Outputter 
from Module_Folders.Response_Parser.Response import Response_Parser
from Module_Folders.Request_Tester.Request import Request_Tester
from Module_Folders.Configurator.Config import Configurator
from Module_Folders.Request_Limiter.Request_limit import Request_Limiter
from Plugin_Scripts.Plugin_Manager import Plugin_Manager
from User_Interface.AppFluentWindow import AppFluentWindow


# 翻译器
class Translator(AiNieeBase):
    
    def __init__(self):
        super().__init__()
    
    # 翻译器主逻辑
    def Main(self):
        # ——————————————————————————————————————————配置信息初始化—————————————————————————————————————————

        configurator.load_config_file() # 读取配置文件

        # 根据混合翻译设置更换翻译平台
        if configurator.mix_translation_enable:
            configurator.target_platform = configurator.mix_translation_settings["translation_platform_1"]

        configurator.configure_translation_platform(configurator.target_platform,None)  # 配置翻译平台信息
        request_limiter.set_limit(configurator.max_tokens,configurator.TPM_limit,configurator.RPM_limit) # 配置请求限制器，依赖前面的配置信息


        # ——————————————————————————————————————————读取原文到缓存—————————————————————————————————————————


        #如果是从头开始翻译
        if configurator.Running_status == 6:
            # 读取文件
            try:
                configurator.cache_list = File_Reader.read_files(self,configurator.translation_project, configurator.label_input_path)

            except Exception as e:
                print(e)
                print("[[red]Error[/]] 读取原文文件失败，请检查项目类型是否设置正确，输入文件夹是否混杂其他非必要文件！")
                return


        # ——————————————————————————————————————————插件预处理—————————————————————————————————————————
        


        # 调用插件，进行文本过滤
        plugin_manager.broadcast_event("text_filter", configurator,configurator.cache_list)

        # 调用插件，进行文本预处理
        plugin_manager.broadcast_event("preproces_text", configurator,configurator.cache_list)



        # ——————————————————————————————————————————构建并发任务池子—————————————————————————————————————————


        # 计算待翻译的文本总行数，tokens总数
        untranslated_text_line_count,untranslated_text_tokens_count = Cache_Manager.count_and_update_translation_status_0_2(self, configurator.cache_list) #获取需要翻译的文本总行数
        # 计算剩余任务数
        tasks_Num = Translator.calculate_total_tasks(self,untranslated_text_line_count,untranslated_text_tokens_count,configurator.lines_limit,configurator.tokens_limit,configurator.tokens_limit_switch)


        # 更新界面UI信息
        if configurator.Running_status == 10: # 如果是继续翻译
            user_interface_prompter.signal.emit("翻译状态提示","开始翻译",0)

            # 更新翻译状态日志
            configurator.update_translation_status("继续翻译", None ,None,None)

            #最后改一下运行状态，为正常翻译状态
            configurator.Running_status = 6

        else:#如果是从头开始翻译
            project_id = configurator.cache_list[0]["project_id"]
            user_interface_prompter.signal.emit("初始化翻译界面数据",project_id,untranslated_text_line_count) #需要输入够当初设定的参数个数
            user_interface_prompter.signal.emit("翻译状态提示","开始翻译",0)

            # 更新翻译状态日志
            configurator.update_translation_status("开始翻译", configurator.translation_project, untranslated_text_line_count,None)


        # 输出开始翻译的日志
        self.print("")
        self.print("")
        self.info(f"项目类型 - {configurator.translation_project}")
        self.info(f"原文语言 - {configurator.source_language}")
        self.info(f"译文语言 - {configurator.target_language}")
        self.print("")
        self.info(f"接口名称 - {configurator.platforms.get(configurator.target_platform, {}).get("name", "未知")}")
        self.info(f"接口地址 - {configurator.base_url}")
        self.info(f"模型名称 - {configurator.model}")
        self.print("")
        self.info(f"生效中的 RPM 限额 - {configurator.RPM_limit}")
        self.info(f"生效中的 TPM 限额 - {configurator.TPM_limit}")
        self.info(f"生效中的 MAX_TOKENS 限额 - {configurator.max_tokens}")
        self.print("")
        if configurator.target_platform != "sakura":
            self.info(f"本次任务使用以下基础指令：\n{configurator.get_system_prompt()}")
            self.print("")
        self.info(f"即将开始执行翻译任务，预计子任务总数为 {tasks_Num}, 同时执行的子任务数量为 {configurator.actual_thread_counts}，请注意保持网络通畅，余额充足。")
        self.print("")
        self.print("")
        time.sleep(3)

        # 创建线程池
        The_Max_workers = configurator.actual_thread_counts # 获取线程数配置
        with concurrent.futures.ThreadPoolExecutor (The_Max_workers) as executor:
            # 创建实例
            api_requester_instance = Api_Requester()
            # 向线程池提交任务
            for i in range(tasks_Num):
                # 根据不同平台调用不同接口
                executor.submit(api_requester_instance.concurrent_request)
                    
            # 等待线程池任务完成
            executor.shutdown(wait=True)


        # 检查翻译任务是否已经暂停或者取消
        if configurator.Running_status in (9, 11):
            return


        # ——————————————————————————————————————————检查没能成功翻译的文本，循环拆分翻译————————————————————————————————————————


        #计算未翻译文本的数量
        untranslated_text_line_count,untranslated_text_tokens_count = Cache_Manager.count_and_update_translation_status_0_2(self,configurator.cache_list)

        #存储重新翻译的次数
        retry_translation_count = 1

        while untranslated_text_line_count != 0 :
            print("[[salmon1]Warning[/]] 仍然有部分未翻译，将进行拆分后重新翻译，-----------------------------------")
            print("[[green]INFO[/]] 当前拆分翻译轮次：",retry_translation_count ," 到达最大轮次：",configurator.round_limit," 时，将停止翻译")
            user_interface_prompter.signal.emit("运行状态改变","正在拆分翻译",0)

            # 根据混合翻译设置更换翻译平台,并重新初始化部分配置信息
            if configurator.mix_translation_enable:

                configurator.load_config_file() # 重新获取配置信息

                # 更换翻译平台
                if retry_translation_count == 1:
                    configurator.target_platform = configurator.mix_translation_settings["translation_platform_2"]
                    print("[[green]INFO[/]] 已开启混合翻译功能，正在进行次轮翻译，翻译平台更换为：",configurator.target_platform, '\n')
                elif retry_translation_count >= 2:
                    configurator.target_platform = configurator.mix_translation_settings["translation_platform_3"]
                    print("[[green]INFO[/]] 已开启混合翻译功能，正在进行末轮翻译，翻译平台更换为：",configurator.target_platform, '\n')

                # 更换模型选择
                model = None
                if (retry_translation_count == 1) and (configurator.mix_translation_settings["customModel_siwtch_2"]):
                    model = configurator.mix_translation_settings["model_type_2"]
                    print("[[green]INFO[/]] 模型更换为：",model, '\n')

                elif (retry_translation_count >= 2) and (configurator.mix_translation_settings["customModel_siwtch_3"]):
                    model = configurator.mix_translation_settings["model_type_3"]
                    print("[[green]INFO[/]] 模型更换为：",model, '\n')

                configurator.configure_translation_platform(configurator.target_platform,model)  # 重新配置翻译平台信息
                request_limiter.set_limit(configurator.max_tokens,configurator.TPM_limit,configurator.RPM_limit)# 重新配置请求限制器


            # 拆分文本行数或者tokens数
            if (configurator.mix_translation_enable) and (retry_translation_count == 1) and (not configurator.mix_translation_settings["split_switch_2"]):
                print("[[green]INFO[/]] 检测到不进行拆分设置，发送行数/tokens数将继续保持不变")

            if (configurator.mix_translation_enable) and (retry_translation_count >= 2) and (not configurator.mix_translation_settings["split_switch_3"]):
                print("[[green]INFO[/]] 检测到不进行拆分设置，发送行数/tokens数将继续保持不变")

            else:
                configurator.lines_limit,configurator.tokens_limit = Translator.update_lines_or_tokens(self,configurator.lines_limit,configurator.tokens_limit) # 更换配置中的文本行数
            

            # 显示日志
            if configurator.tokens_limit_switch:
                print("[[green]INFO[/]] 未翻译文本总tokens为：",untranslated_text_tokens_count,"  每次发送tokens为：",configurator.tokens_limit, '\n')
            else:
                print("[[green]INFO[/]] 未翻译文本总行数为：",untranslated_text_line_count,"  每次发送行数为：",configurator.lines_limit, '\n')


            # 更新翻译状态日志
            configurator.update_translation_status("拆分翻译", configurator.translation_project, None,retry_translation_count)


            # 计算剩余任务数
            tasks_Num = Translator.calculate_total_tasks(self,untranslated_text_line_count,untranslated_text_tokens_count,configurator.lines_limit,configurator.tokens_limit,configurator.tokens_limit_switch)



            # 创建线程池
            The_Max_workers = configurator.actual_thread_counts # 获取线程数配置
            with concurrent.futures.ThreadPoolExecutor (The_Max_workers) as executor:
                # 创建实例
                api_requester_instance = Api_Requester()
                # 向线程池提交任务
                for i in range(tasks_Num):
                    # 根据不同平台调用不同接口
                    executor.submit(api_requester_instance.concurrent_request)

                # 等待线程池任务完成
                executor.shutdown(wait=True)

            
            # 检查翻译任务是否已经暂停或者取消
            if configurator.Running_status == 9 or configurator.Running_status == 11 :
                return


            #检查是否已经达到重翻次数限制
            retry_translation_count  = retry_translation_count + 1
            if retry_translation_count > configurator.round_limit :
                print ("[[salmon1]Warning[/]] 已经达到拆分翻译轮次限制，但仍然有部分文本未翻译，不影响使用，可手动翻译", '\n')
                break

            #重新计算未翻译文本的数量
            untranslated_text_line_count,untranslated_text_tokens_count = Cache_Manager.count_and_update_translation_status_0_2(self,configurator.cache_list)

        print ("[[green]Success[/]] 翻译阶段已完成，正在处理数据-----------------------------------", '\n')


        # ——————————————————————————————————————————插件后处理—————————————————————————————————————————
            
        # 调用插件，进行文本后处理
        plugin_manager.broadcast_event("postprocess_text", configurator,configurator.cache_list)


        #如果开启了转换简繁开关功能，则进行文本转换
        if configurator.response_conversion_toggle:
            try:
                configurator.cache_list = Cache_Manager.simplified_and_traditional_conversion(self,configurator.cache_list, configurator.opencc_preset)
                print(f"[[green]Success[/]] 文本转化{configurator.target_language}完成-----------------------------------", '\n')   

            except Exception as e:
                print("[[salmon1]Warning[/]] 文本转换出现问题！！将跳过该步，错误信息如下")
                print(f"Error: {e}\n")


        # ——————————————————————————————————————————将数据处理并保存为文件—————————————————————————————————————————


        # 将翻译结果写为对应文件
        File_Outputter.output_translated_content(self,configurator.cache_list,configurator.label_output_path,configurator.label_input_path)



        # —————————————————————————————————————#全部翻译完成——————————————————————————————————————————


        print("[[green]Success[/]] 译文文件写入完成-----------------------------------", '\n')  
        user_interface_prompter.signal.emit("翻译状态提示","翻译完成",0)
        print("\n--------------------------------------------------------------------------------------")
        print("\n[[green]Success[/]] 已完成全部翻译任务，程序已经停止")   
        print("\n[[green]Success[/]] 请检查译文文件，格式是否错误，存在错行，空行等问题")
        print("\n-------------------------------------------------------------------------------------\n")

        # 更新翻译状态日志
        configurator.update_translation_status("翻译完成", None, None,None)


        # ——————————————————————————————————————————完成后插件—————————————————————————————————————————
            
        plugin_manager.broadcast_event("translation_completed", configurator,None)



    # 重新设置发送的文本行数
    def update_lines_or_tokens(self,lines_limit,tokens_limit):
        # 重新计算文本行数限制
        if lines_limit % 2 == 0:
            new_lines_limit = lines_limit // 2
        elif lines_limit % 3 == 0:
            new_lines_limit = lines_limit // 3
        elif lines_limit % 4 == 0:
            new_lines_limit = lines_limit // 4
        elif lines_limit % 5 == 0:
            new_lines_limit = lines_limit // 5
        else:
            new_lines_limit = 1 # 保底一行

        # 重新计算tokens限制
        new_tokens_limit = tokens_limit // 2
        if new_tokens_limit < 2:
            new_tokens_limit = 2 # 保底非零

        return new_lines_limit,new_tokens_limit


    # 计算剩余任务总数
    def calculate_total_tasks(self,total_lines,total_tokens,lines_limit,tokens_limit,switch = False):
        
        if switch:

            if total_tokens  <= tokens_limit:  # 防止负数计算
                return  1

            if total_tokens % tokens_limit == 0:
                tasks_Num = total_tokens // tokens_limit 
            else:
                tasks_Num = total_tokens // tokens_limit + 1

        else:

            if total_lines % lines_limit == 0:
                tasks_Num = total_lines // lines_limit 
            else:
                tasks_Num = total_lines // lines_limit + 1

        return tasks_Num


# 接口请求器
class Api_Requester():

    def __init__(self):
        pass

    # 并发接口请求分发
    def concurrent_request(self):
        target_platform = configurator.target_platform
        api_format = configurator.platforms.get(target_platform).get("api_format")

        if target_platform == "sakura":
            self.concurrent_request_sakura()
        elif target_platform  == "cohere":
            self.concurrent_request_cohere()
        elif target_platform  == "google":
            self.concurrent_request_google()
        elif target_platform  == "anthropic":
            self.concurrent_request_anthropic()
        elif target_platform.startswith("custom_platform_") and api_format == "Anthropic":
            self.concurrent_request_anthropic()
        else:
            self.concurrent_request_openai()

    # 整理发送内容（Openai）
    def organize_send_content_openai(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        #如果开启指令词典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[[green]INFO[/]] 已添加术语表：\n",glossary_prompt)


        #如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[[green]INFO[/]] 已添加角色介绍：\n",characterization)

        #如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[[green]INFO[/]] 已添加背景设定：\n",world_building)

        #如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[[green]INFO[/]] 已添加文风要求：\n",writing_style)



        # 添加系统提示词信息
        messages.append({"role": "system","content": system_prompt })



        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        #构建默认示例
        original_exmaple,translation_example_content =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example_content:

            the_original_exmaple =  {"role": "user","content":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "assistant", "content": (f'{fol_prompt}```json\n{translation_example_content}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[[green]INFO[/]] 已添加格式原文示例：\n",original_exmaple)
            print("[[green]INFO[/]] 已添加格式译文示例：\n",translation_example_content, '\n')


        #如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "user","content":original_exmaple_3 }
                the_translation_example = {"role": "assistant", "content": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[[green]INFO[/]] 已添加用户原文示例：\n",original_exmaple_3)
                print("[[green]INFO[/]] 已添加用户译文示例：\n",translation_example_3, '\n')


        # 调用插件，进行处理
        plugin_manager.broadcast_event("normalize_text", configurator,source_text_dict)


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[[green]INFO[/]] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        #如果开启译前文本替换功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[[green]INFO[/]] 你开启了译前文本替换功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果加上文
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                pass
                #print("[[green]INFO[/]] 已添加上文：\n",previous)



        #获取提问时的前置文本
        pre_prompt = configurator.build_userQueryPrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelResponsePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)


        # 构建用户信息
        source_text_str = json.dumps(source_text_dict, ensure_ascii=False)  
        source_text_str = f'{previous}\n{pre_prompt}```json\n{source_text_str}\n```'
        messages.append({"role":"user","content":source_text_str })


        # 构建模型信息
        if( "claude" in configurator.model or "gpt" in configurator.model or "moonshot" in configurator.model or "deepseek" in configurator.model) :
            messages.append({"role": "assistant", "content":fol_prompt })

        return messages,source_text_str


    # 并发接口请求（Openai）
    def concurrent_request_openai(self):

        # 检查翻译任务是否已经暂停或者退出
        if configurator.Running_status == 9 or configurator.Running_status == 11 :
            return

        try:#方便排查子线程bug

            # ——————————————————————————————————————————截取需要翻译的原文本——————————————————————————————————————————
            configurator.lock1.acquire()  # 获取锁
            # 获取设定行数的文本，并修改缓存文件里的翻译状态为2，表示正在翻译中
            if configurator.tokens_limit_switch:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(self,configurator.tokens_limit, configurator.cache_list,configurator.pre_line_counts)  
            else:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(self,configurator.lines_limit, configurator.cache_list,configurator.pre_line_counts)   
            configurator.lock1.release()  # 释放锁

            # 检查一下是否有发送内容
            if source_text_list == []:
                print("[[salmon1]Warning[/]] 未能获取文本，该线程为多余线程，取消任务")
                return
            # ——————————————————————————————————————————处理原文本的内容与格式——————————————————————————————————————————
            # 将原文本列表改变为请求格式
            source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self,source_text_list)  

            # 如果原文是日语，清除文本首尾中的代码文本，并记录清除信息
            if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                source_text_dict,process_info_list = Cache_Manager.process_dictionary(self,source_text_dict)
                row_count = len(source_text_dict)

            # ——————————————————————————————————————————整合发送内容——————————————————————————————————————————        
            messages,source_text_str = Api_Requester.organize_send_content_openai(self,source_text_dict, previous_list)



            #——————————————————————————————————————————检查tokens发送限制——————————————————————————————————————————
            #计算请求的tokens预计花费
            request_tokens_consume = Request_Limiter.num_tokens_from_messages(self,messages) 
            #计算回复的tokens预计花费，只计算发送的文本，不计算提示词与示例，可以大致得出
            Original_text = [{"role":"user","content":source_text_str }] # 需要拿列表来包一层，不然计算时会出错 
            completion_tokens_consume = Request_Limiter.num_tokens_from_messages(self,Original_text)
 
            if request_tokens_consume >= request_limiter.max_tokens :
                print("[[red]Error[/]] 该条消息总tokens数大于单条消息最大数量" )
                print("[[red]Error[/]] 该条消息取消任务，进行拆分翻译" )
                return
            # ——————————————————————————————————————————开始循环请求，直至成功或失败——————————————————————————————————————————
            start_time = time.time()
            timeout = 220  # 设置超时时间为x秒
            request_errors_count = 0 # 请求错误次数
            Wrong_answer_count = 0   # 错误回复次数
            model_degradation = False # 模型退化检测

            while 1 :
                # 检查翻译任务是否已经暂停或者退出---------------------------------
                if configurator.Running_status == 9 or configurator.Running_status == 11 :
                    return

                #检查子线程运行是否超时---------------------------------
                if time.time() - start_time > timeout:
                    print("[[red]Error[/]] 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print("[[green]INFO[/]] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[[green]INFO[/]] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取接口的请求参数
                    temperature, top_p, presence_penalty, frequency_penalty = configurator.get_platform_request_args()

                    # 如果上一次请求出现模型退化，更改参数
                    if model_degradation:
                        frequency_penalty = 0.2

                    # 获取apikey
                    openai_apikey =  configurator.get_apikey()
                    # 创建openai客户端
                    openaiclient = OpenAI(api_key=openai_apikey,
                                            base_url= configurator.base_url)
                    # 发送对话请求
                    try:
                        response = openaiclient.chat.completions.create(
                            model= configurator.model,
                            messages = messages ,
                            temperature=temperature,
                            top_p = top_p,                        
                            presence_penalty=presence_penalty,
                            frequency_penalty=frequency_penalty
                            )
                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 进行请求时出现问题！！！错误信息如下")
                        print(f"[[red]Error[/]] {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break

                        #处理完毕，再次进行请求
                        continue


                    # 检查翻译任务是否已经暂停或者退出，不进行接下来的处理了
                    if configurator.Running_status == 9 or configurator.Running_status == 11 :
                        return
                    

                    #——————————————————————————————————————————收到回复，获取返回的信息 ————————————————————————————————————————  
                    # 计算AI回复花费的时间
                    response_time = time.time()
                    Request_consumption_time = round(response_time - Start_request_time, 2)


                    # 计算本次请求的花费的tokens
                    try: # 因为有些中转网站不返回tokens消耗
                        prompt_tokens_used = int(response.usage.prompt_tokens) #本次请求花费的tokens
                    except Exception:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception:
                        completion_tokens_used = 0



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.choices[0].message.content 
                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 提取文本时出现问题！！！运行错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[[green]INFO[/]] 已成功接受到AI的回复-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[[green]INFO[/]] AI回复的文本内容：\n",response_content ,'\n','\n')

                    # ———————————————————————————————————对回复内容处理,检查—————————————————————————————————————————————————

                    # 调用插件，进行处理
                    plugin_manager.broadcast_event("complete_text_process", configurator,response_content)

                    # 提取回复内容
                    response_dict = Response_Parser.text_extraction(self,response_content)

                    # 检查回复内容
                    check_result,error_content =  Response_Parser.check_response_content(self,configurator.reply_check_switch,response_content,response_dict,source_text_dict,configurator.source_language)


                    # ———————————————————————————————————回复内容结果录入—————————————————————————————————————————————————
                    # 如果没有出现错误
                    if check_result :

                        # 如果开启了保留换行符功能
                        if configurator.preserve_line_breaks_toggle:
                            response_dict = Cache_Manager.replace_special_characters(self,response_dict, "还原")


                        # 如果开启译后文本替换功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[[green]INFO[/]] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.label_output_path, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(1, row_count, prompt_tokens_used, completion_tokens_used)
                        
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print("\n--------------------------------------------------------------------------------------")
                        print(f"\n[[green]Success[/]] AI回复内容检查通过！！！已翻译完成{progress}%")
                        print("\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:
                        print("[[salmon1]Warning[/]] AI回复内容存在问题:",error_content,"\n")


                        configurator.lock2.acquire()  # 获取锁

                        # 如果是进行平时的翻译任务
                        if configurator.Running_status == 6 :

                            # 更新运行日志数据
                            configurator.update_running_params(0, row_count, prompt_tokens_used, completion_tokens_used)

                            # 更新翻译界面数据
                            user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                            # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                            user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁


                        # 检查一下是不是模型退化
                        if error_content == "AI回复内容出现高频词,并重新翻译":
                            print("[[salmon1]Warning[/]] 下次请求将修改参数，回避高频词输出","\n")
                            model_degradation = True

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("[[salmon1]Warning[/]] 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("[[salmon1]Warning[/]] 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("[[red]Error[/]] 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（Google）
    def organize_send_content_google(self,source_text_dict, previous_list):
        # 创建message列表，用于发送
        messages = []

        # 获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        # #如果开启指令词典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[[green]INFO[/]] 已添加术语表：\n",glossary_prompt)


        # 如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[[green]INFO[/]] 已添加角色介绍：\n",characterization)

        # 如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[[green]INFO[/]] 已添加背景设定：\n",world_building)

        # 如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[[green]INFO[/]] 已添加文风要求：\n",writing_style)

        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        # 构建默认示例
        original_exmaple,translation_example_content =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example_content:
            
            the_original_exmaple =  {"role": "user","parts":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "model", "parts": (f'{fol_prompt}```json\n{translation_example_content}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[[green]INFO[/]] 已添加格式原文示例：\n",original_exmaple)
            print("[[green]INFO[/]] 已添加格式译文示例：\n",translation_example_content, '\n')


        # 如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "user","parts":original_exmaple_3 }
                the_translation_example = {"role": "model", "parts": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[[green]INFO[/]] 已添加用户原文示例：\n",original_exmaple_3)
                print("[[green]INFO[/]] 已添加用户译文示例：\n",translation_example_3, '\n')


        # 调用插件，进行处理
        plugin_manager.broadcast_event("normalize_text", configurator,source_text_dict)


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[[green]INFO[/]] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        # 如果开启译前文本替换功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[[green]INFO[/]] 你开启了译前文本替换功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        # 如果加上文
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                pass
                #print("[[green]INFO[/]] 已添加上文：\n",previous)


        # 获取提问时的前置文本
        pre_prompt = configurator.build_userQueryPrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelResponsePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)


        # 构建用户信息
        source_text_str = json.dumps(source_text_dict, ensure_ascii=False)
        source_text_str = f'{previous}\n{pre_prompt}```json\n{source_text_str}\n```'     
        messages.append({"role":"user","parts":source_text_str })


        # 构建模型信息
        messages.append({"role": "model", "parts":fol_prompt })


        return messages,source_text_str,system_prompt


    # 并发接口请求（Google）
    def concurrent_request_google(self):
        # 检查翻译任务是否已经暂停或者退出
        if configurator.Running_status == 9 or configurator.Running_status == 11 :
            return

        try:#方便排查子线程bug

            # ——————————————————————————————————————————截取需要翻译的原文本——————————————————————————————————————————
            configurator.lock1.acquire()  # 获取锁
            # 获取设定行数的文本，并修改缓存文件里的翻译状态为2，表示正在翻译中
            if configurator.tokens_limit_switch:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(self,configurator.tokens_limit, configurator.cache_list,configurator.pre_line_counts)  
            else:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(self,configurator.lines_limit, configurator.cache_list,configurator.pre_line_counts)     
            configurator.lock1.release()  # 释放锁

            # 检查一下是否有发送内容
            if source_text_list == []:
                print("[[salmon1]Warning[/]] 未能获取文本，该线程为多余线程，取消任务")
                return
            # ——————————————————————————————————————————处理原文本的内容与格式——————————————————————————————————————————
            # 将原文本列表改变为请求格式
            source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self,source_text_list)  

            # 如果原文是日语，清除文本首尾中的代码文本，并记录清除信息
            if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                source_text_dict,process_info_list = Cache_Manager.process_dictionary(self,source_text_dict)
                row_count = len(source_text_dict)


            # ——————————————————————————————————————————整合发送内容——————————————————————————————————————————        
            messages,source_text_str,system_prompt = Api_Requester.organize_send_content_google(self,source_text_dict, previous_list)



            #——————————————————————————————————————————检查tokens发送限制——————————————————————————————————————————
            # 计算请求的tokens预计花费
            prompt_tokens ={"role": "system","content": system_prompt }
            messages_tokens= messages.copy()
            messages_tokens.append(prompt_tokens)
            request_tokens_consume = Request_Limiter.num_tokens_from_messages(self,messages_tokens) 

            #计算回复的tokens预计花费，只计算发送的文本，不计算提示词与示例，可以大致得出
            Original_text = [{"role":"user","content":source_text_str}] # 需要拿列表来包一层，不然计算时会出错 
            completion_tokens_consume = Request_Limiter.num_tokens_from_messages(self,Original_text)
 
            if request_tokens_consume >= request_limiter.max_tokens :
                print("[[salmon1]Warning[/]] 该条消息总tokens数大于单条消息最大数量" )
                print("[[salmon1]Warning[/]] 该条消息取消任务，进行拆分翻译" )
                return

            # ——————————————————————————————————————————开始循环请求，直至成功或失败——————————————————————————————————————————
            start_time = time.time()
            timeout = 220   # 设置超时时间为x秒
            request_errors_count = 0 # 设置请求错误次数限制
            Wrong_answer_count = 0   # 设置错误回复次数限制

            while 1 :
                # 检查翻译任务是否已经暂停或者退出
                if configurator.Running_status == 9 or configurator.Running_status == 11 :
                    return

                #检查子线程运行是否超时---------------------------------
                if time.time() - start_time > timeout:
                    print("[[red]Error[/]] 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print("[[green]INFO[/]] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[[green]INFO[/]] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取接口的请求参数
                    temperature, top_p, presence_penalty, frequency_penalty = configurator.get_platform_request_args()

                    # 设置AI的参数
                    generation_config = {
                    "temperature": temperature,
                    "top_p": 1,
                    "top_k": 1,
                    "max_output_tokens": 8000, 
                    }

                    #调整安全限制
                    safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                    ]

                    # 获取apikey
                    apikey =  configurator.get_apikey()
                    genai.configure(api_key=apikey,transport='rest')

                    #设置对话模型及参数
                    model = genai.GenerativeModel(model_name=configurator.model,
                                    generation_config=generation_config,
                                    safety_settings=safety_settings,
                                    system_instruction = system_prompt)


                    # 发送对话请求
                    try:
                        response = model.generate_content(messages)

                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break

                        #处理完毕，再次进行请求
                        continue


                    # 检查翻译任务是否已经暂停或者退出，不进行接下来的处理了
                    if configurator.Running_status == 9 or configurator.Running_status == 11 :
                        return
                    

                    #——————————————————————————————————————————收到回复，获取返回的信息 ————————————————————————————————————————  
                    # 计算AI回复花费的时间
                    response_time = time.time()
                    Request_consumption_time = round(response_time - Start_request_time, 2)


                    # 计算本次请求的花费的tokens
                    prompt_tokens_used = int(request_tokens_consume)
                    completion_tokens_used = int(completion_tokens_consume)



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.text
                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 提取文本时出现错误！！！运行的错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response.prompt_feedback)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[[green]INFO[/]] 已成功接受到AI的回复-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[[green]INFO[/]] AI回复的文本内容：\n",response_content ,'\n','\n')

                    # ——————————————————————————————————————————对回复内容处理,检查和录入——————————————————————————————————————————
                    # 调用插件，进行处理
                    plugin_manager.broadcast_event("complete_text_process", configurator,response_content)

                    # 提取回复内容
                    response_dict = Response_Parser.text_extraction(self,response_content)

                    # 检查回复内容
                    check_result,error_content =  Response_Parser.check_response_content(self,configurator.reply_check_switch,response_content,response_dict,source_text_dict,configurator.source_language)

                    # ———————————————————————————————————回复内容结果录入—————————————————————————————————————————————————

                    # 如果没有出现错误
                    if check_result :

                        # 如果开启了保留换行符功能
                        if configurator.preserve_line_breaks_toggle:
                            response_dict = Cache_Manager.replace_special_characters(self,response_dict, "还原")

                        #如果开启译后文本替换功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[[green]INFO[/]] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.label_output_path, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁


                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(1, row_count, prompt_tokens_used, completion_tokens_used)
                        
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print("\n--------------------------------------------------------------------------------------")
                        print(f"\n[[green]Success[/]] AI回复内容检查通过！！！已翻译完成{progress}%")
                        print("\n--------------------------------------------------------------------------------------\n")

                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:
                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(0, row_count, prompt_tokens_used, completion_tokens_used)
                        
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("[[salmon1]Warning[/]] AI回复内容存在问题:",error_content,"\n")

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("[[salmon1]Warning[/]] 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("[[salmon1]Warning[/]] 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("[[red]Error[/]] 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（Anthropic）
    def organize_send_content_anthropic(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        # 如果开启指令词典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[[green]INFO[/]] 已添加术语表：\n",glossary_prompt)


        #如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[[green]INFO[/]] 已添加角色介绍：\n",characterization)

        #如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[[green]INFO[/]] 已添加背景设定：\n",world_building)

        #如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[[green]INFO[/]] 已添加文风要求：\n",writing_style)

        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        #构建默认示例
        original_exmaple,translation_example_content =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example_content:

            the_original_exmaple =  {"role": "user","content":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "assistant", "content": (f'{fol_prompt}```json\n{translation_example_content}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[[green]INFO[/]] 已添加格式原文示例：\n",original_exmaple)
            print("[[green]INFO[/]] 已添加格式译文示例：\n",translation_example_content, '\n')


        #如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "user","content":original_exmaple_3 }
                the_translation_example = {"role": "assistant", "content": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[[green]INFO[/]] 已添加用户原文示例：\n",original_exmaple_3)
                print("[[green]INFO[/]] 已添加用户译文示例：\n",translation_example_3, '\n')



        # 调用插件，进行处理
        plugin_manager.broadcast_event("normalize_text", configurator,source_text_dict)


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[[green]INFO[/]] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        #如果开启译前文本替换功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[[green]INFO[/]] 你开启了译前文本替换功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果加上文
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                pass
                #print("[[green]INFO[/]] 已添加上文：\n",previous)


        # 获取提问时的前置文本
        pre_prompt = configurator.build_userQueryPrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelResponsePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)


        # 构建用户信息
        source_text_str = json.dumps(source_text_dict, ensure_ascii=False) 
        source_text_str = f'{previous}\n{pre_prompt}```json\n{source_text_str}\n```'
        messages.append({"role":"user","content":source_text_str })


        # 构建模型信息
        messages.append({"role": "assistant", "content":fol_prompt })


        return messages,source_text_str,system_prompt


    # 并发接口请求（Anthropic）
    def concurrent_request_anthropic(self):

        # 检查翻译任务是否已经暂停或者退出
        if configurator.Running_status == 9 or configurator.Running_status == 11 :
            return

        try:#方便排查子线程bug

            # ——————————————————————————————————————————截取需要翻译的原文本——————————————————————————————————————————
            configurator.lock1.acquire()  # 获取锁
            # 获取设定行数的文本，并修改缓存文件里的翻译状态为2，表示正在翻译中
            if configurator.tokens_limit_switch:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(self,configurator.tokens_limit, configurator.cache_list,configurator.pre_line_counts)  
            else:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(self,configurator.lines_limit, configurator.cache_list,configurator.pre_line_counts)    
            configurator.lock1.release()  # 释放锁

            # 检查一下是否有发送内容
            if source_text_list == []:
                print("[[salmon1]Warning[/]] 未能获取文本，该线程为多余线程，取消任务")
                return
            # ——————————————————————————————————————————处理原文本的内容与格式——————————————————————————————————————————
            # 将原文本列表改变为请求格式
            source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self,source_text_list)  

            # 如果原文是日语，清除文本首位中的代码文本，并记录清除信息
            if configurator.source_language == "日语"and configurator.text_clear_toggle:
                source_text_dict,process_info_list = Cache_Manager.process_dictionary(self,source_text_dict)
                row_count = len(source_text_dict)


            # ——————————————————————————————————————————整合发送内容——————————————————————————————————————————        
            messages,source_text_str,system_prompt = Api_Requester.organize_send_content_anthropic(self,source_text_dict, previous_list)

            #——————————————————————————————————————————检查tokens发送限制——————————————————————————————————————————
            # 计算请求的tokens预计花费
            prompt_tokens ={"role": "system","content": system_prompt }
            messages_tokens= messages.copy()
            messages_tokens.append(prompt_tokens)
            request_tokens_consume = Request_Limiter.num_tokens_from_messages(self,messages_tokens) 

            # 计算回复的tokens预计花费，只计算发送的文本，不计算提示词与示例，可以大致得出
            Original_text = [{"role":"user","content":source_text_str }] # 需要拿列表来包一层，不然计算时会出错 
            completion_tokens_consume = Request_Limiter.num_tokens_from_messages(self,Original_text)
 
            if request_tokens_consume >= request_limiter.max_tokens :
                print("[[red]Error[/]] 该条消息总tokens数大于单条消息最大数量" )
                print("[[red]Error[/]] 该条消息取消任务，进行拆分翻译" )
                return
            
            # ——————————————————————————————————————————开始循环请求，直至成功或失败——————————————————————————————————————————
            start_time = time.time()
            timeout = 220   # 设置超时时间为x秒
            request_errors_count = 0 # 请求错误计数
            Wrong_answer_count = 0   # 错误回复计数

            while 1 :
                # 检查翻译任务是否已经暂停或者退出
                if configurator.Running_status == 9 or configurator.Running_status == 11 :
                    return

                #检查子线程运行是否超时---------------------------------
                if time.time() - start_time > timeout:
                    print("[[red]Error[/]] 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print("[[green]INFO[/]] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[[green]INFO[/]] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取接口的请求参数
                    temperature, top_p, presence_penalty, frequency_penalty = configurator.get_platform_request_args()
                    
                    # 获取apikey
                    anthropic_apikey =  configurator.get_apikey()
                    # 创建anthropic客户端
                    client = anthropic.Anthropic(api_key=anthropic_apikey,base_url=configurator.base_url)
                    # 发送对话请求
                    try:
                        response = client.messages.create(
                            model= configurator.model,
                            max_tokens=4000,
                            system= system_prompt,
                            messages = messages ,
                            temperature=temperature
                            )



                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break

                        #处理完毕，再次进行请求
                        continue


                    # 检查翻译任务是否已经暂停或者退出，不进行接下来的处理了
                    if configurator.Running_status == 9 or configurator.Running_status == 11 :
                        return
                    

                    #——————————————————————————————————————————收到回复，获取返回的信息 ————————————————————————————————————————  
                    # 计算AI回复花费的时间
                    response_time = time.time()
                    Request_consumption_time = round(response_time - Start_request_time, 2)


                    # 计算本次请求的花费的tokens
                    try: # 因为有些中转网站不返回tokens消耗
                        prompt_tokens_used = int(response.usage.prompt_tokens) #本次请求花费的tokens
                    except Exception:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception:
                        completion_tokens_used = 0



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.content[0].text 
                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 提取文本时出现问题！！！运行错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[[green]INFO[/]] 已成功接受到AI的回复-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[[green]INFO[/]] AI回复的文本内容：\n",response_content ,'\n','\n')

                    # ——————————————————————————————————————————对回复内容处理,检查和录入——————————————————————————————————————————
                    # 调用插件，进行处理
                    plugin_manager.broadcast_event("complete_text_process", configurator,response_content)

                    # 提取回复内容
                    response_dict = Response_Parser.text_extraction(self,response_content)

                    # 检查回复内容
                    check_result,error_content =  Response_Parser.check_response_content(self,configurator.reply_check_switch,response_content,response_dict,source_text_dict,configurator.source_language)

                    # ———————————————————————————————————回复内容结果录入—————————————————————————————————————————————————

                    # 如果没有出现错误
                    if check_result :

                        # 如果开启了保留换行符功能
                        if configurator.preserve_line_breaks_toggle:
                            response_dict = Cache_Manager.replace_special_characters(self,response_dict, "还原")

                        #如果开启译后文本替换功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[[green]INFO[/]] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.label_output_path, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(1, row_count, prompt_tokens_used, completion_tokens_used)

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print("\n--------------------------------------------------------------------------------------")
                        print(f"\n[[green]Success[/]] AI回复内容检查通过！！！已翻译完成{progress}%")
                        print("\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:

                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(0, row_count, prompt_tokens_used, completion_tokens_used)

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("[[salmon1]Warning[/]] AI回复内容存在问题:",error_content,"\n")

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("[[salmon1]Warning[/]] 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("[[salmon1]Warning[/]] 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("[[red]Error[/]] 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（Cohere）
    def organize_send_content_cohere(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        # 如果开启指令词典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[[green]INFO[/]] 已添加术语表：\n",glossary_prompt)


        # 如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[[green]INFO[/]] 已添加角色介绍：\n",characterization)

        #如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[[green]INFO[/]] 已添加背景设定：\n",world_building)

        #如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[[green]INFO[/]] 已添加文风要求：\n",writing_style)

        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        #构建默认示例
        original_exmaple,translation_example_content =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example_content:
                
            the_original_exmaple =  {"role": "USER","message":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "CHATBOT", "message": (f'{fol_prompt}```json\n{translation_example_content}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[[green]INFO[/]] 已添加格式原文示例：\n",original_exmaple)
            print("[[green]INFO[/]] 已添加格式译文示例：\n",translation_example_content, '\n')


        #如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "USER","message":original_exmaple_3 }
                the_translation_example = {"role": "CHATBOT", "message": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[[green]INFO[/]] 已添加用户原文示例：\n",original_exmaple_3)
                print("[[green]INFO[/]] 已添加用户译文示例：\n",translation_example_3, '\n')


        # 调用插件，进行处理
        plugin_manager.broadcast_event("normalize_text", configurator,source_text_dict)


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[[green]INFO[/]] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        #如果开启译前文本替换功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[[green]INFO[/]] 你开启了译前文本替换功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果加上文(cohere的模型注意力更多会注意在最新的消息，而导致过分关注最新消息的格式)
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                #system_prompt += previous
                pass 
                #print("[[green]INFO[/]] 已添加上文：\n",previous)


        # 获取提问时的前置文本
        pre_prompt = configurator.build_userQueryPrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)


        #构建用户信息
        source_text_str = json.dumps(source_text_dict, ensure_ascii=False)   
        source_text_str = f'{previous}\n{pre_prompt}```json\n{source_text_str}\n```'


        return messages,source_text_str,system_prompt


    # 并发接口请求（Cohere）
    def concurrent_request_cohere(self):

        # 检查翻译任务是否已经暂停或者退出
        if configurator.Running_status == 9 or configurator.Running_status == 11 :
            return

        try:#方便排查子线程bug

            # ——————————————————————————————————————————截取需要翻译的原文本——————————————————————————————————————————
            configurator.lock1.acquire()  # 获取锁
            # 获取设定行数的文本，并修改缓存文件里的翻译状态为2，表示正在翻译中
            if configurator.tokens_limit_switch:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(self,configurator.tokens_limit, configurator.cache_list,configurator.pre_line_counts)  
            else:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(self,configurator.lines_limit, configurator.cache_list,configurator.pre_line_counts)    
            configurator.lock1.release()  # 释放锁

            # 检查一下是否有发送内容
            if source_text_list == []:
                print("[[salmon1]Warning[/]] 未能获取文本，该线程为多余线程，取消任务")
                return
            # ——————————————————————————————————————————处理原文本的内容与格式——————————————————————————————————————————
            # 将原文本列表改变为请求格式
            source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self,source_text_list)  

            # 如果原文是日语，清除文本首位中的代码文本，并记录清除信息
            if configurator.source_language == "日语"and configurator.text_clear_toggle:
                source_text_dict,process_info_list = Cache_Manager.process_dictionary(self,source_text_dict)
                row_count = len(source_text_dict)


            # ——————————————————————————————————————————整合发送内容——————————————————————————————————————————        
            messages,source_text_str,system_prompt = Api_Requester.organize_send_content_cohere(self,source_text_dict, previous_list)

            #——————————————————————————————————————————检查tokens发送限制——————————————————————————————————————————
            # 计算请求的tokens预计花费
            prompt_tokens ={"role": "system","content": system_prompt }
            srt_tokens ={"role": "user","content": source_text_str }
            messages_tokens= messages.copy()
            messages_tokens.append(prompt_tokens)
            messages_tokens.append(srt_tokens)
            request_tokens_consume = Request_Limiter.num_tokens_from_messages(self,messages_tokens) 

            # 计算回复的tokens预计花费，只计算发送的文本，不计算提示词与示例，可以大致得出
            Original_text = [{"role":"user","content":source_text_str }] # 需要拿列表来包一层，不然计算时会出错 
            completion_tokens_consume = Request_Limiter.num_tokens_from_messages(self,Original_text)
 
            if request_tokens_consume >= request_limiter.max_tokens :
                print("[[red]Error[/]] 该条消息总tokens数大于单条消息最大数量" )
                print("[[red]Error[/]] 该条消息取消任务，进行拆分翻译" )
                return
            
            # ——————————————————————————————————————————开始循环请求，直至成功或失败——————————————————————————————————————————
            start_time = time.time()
            timeout = 220   # 设置超时时间为x秒
            request_errors_count = 0 # 请求错误计数
            Wrong_answer_count = 0   # 错误回复计数

            while 1 :
                # 检查翻译任务是否已经暂停或者退出
                if configurator.Running_status == 9 or configurator.Running_status == 11 :
                    return

                #检查子线程运行是否超时---------------------------------
                if time.time() - start_time > timeout:
                    print("[[red]Error[/]] 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print("[[green]INFO[/]] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[[green]INFO[/]] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取apikey
                    cohere_apikey =  configurator.get_apikey()
                    
                    # 获取接口的请求参数
                    temperature, top_p, presence_penalty, frequency_penalty = configurator.get_platform_request_args()
                    
                    # 创建anthropic客户端
                    client = cohere.Client(api_key=cohere_apikey,base_url=configurator.base_url)
                    
                    # 发送对话请求
                    try:
                        response = client.chat(
                            model= configurator.model,
                            preamble= system_prompt,
                            message = source_text_str ,
                            chat_history = messages,
                            temperature=temperature
                            )



                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break

                        #处理完毕，再次进行请求
                        continue


                    # 检查翻译任务是否已经暂停或者退出，不进行接下来的处理了
                    if configurator.Running_status == 9 or configurator.Running_status == 11 :
                        return
                    

                    #——————————————————————————————————————————收到回复，获取返回的信息 ————————————————————————————————————————  
                    # 计算AI回复花费的时间
                    response_time = time.time()
                    Request_consumption_time = round(response_time - Start_request_time, 2)


                    # 计算本次请求的花费的tokens
                    try: # 因为有些中转网站不返回tokens消耗
                        prompt_tokens_used = 0
                        #prompt_tokens_used = int(response.usage.prompt_tokens) #本次请求花费的tokens
                    except Exception:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = 0
                        #completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception:
                        completion_tokens_used = 0



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.text 
                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 提取文本时出现问题！！！运行错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[[green]INFO[/]] 已成功接受到AI的回复-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[[green]INFO[/]] AI回复的文本内容：\n",response_content ,'\n','\n')

                    # ——————————————————————————————————————————对回复内容处理,检查和录入——————————————————————————————————————————
                    # 调用插件，进行处理
                    plugin_manager.broadcast_event("complete_text_process", configurator,response_content)

                    # 提取回复内容
                    response_dict = Response_Parser.text_extraction(self,response_content)

                    # 检查回复内容
                    check_result,error_content =  Response_Parser.check_response_content(self,configurator.reply_check_switch,response_content,response_dict,source_text_dict,configurator.source_language)

                    # ———————————————————————————————————回复内容结果录入—————————————————————————————————————————————————

                    # 如果没有出现错误
                    if check_result :

                        # 如果开启了保留换行符功能
                        if configurator.preserve_line_breaks_toggle:
                            response_dict = Cache_Manager.replace_special_characters(self,response_dict, "还原")

                        #如果开启译后文本替换功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[[green]INFO[/]] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.label_output_path, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(1, row_count, prompt_tokens_used, completion_tokens_used)
                        
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print("\n--------------------------------------------------------------------------------------")
                        print(f"\n[[green]Success[/]] AI回复内容检查通过！！！已翻译完成{progress}%")
                        print("\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:

                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(0, row_count, prompt_tokens_used, completion_tokens_used)
                        
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("[[salmon1]Warning[/]] AI回复内容存在问题:",error_content,"\n")

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("[[salmon1]Warning[/]] 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("[[salmon1]Warning[/]] 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("[[red]Error[/]] 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（sakura）
    def organize_send_content_sakura(self, source_text_dict, previous_list):
        # 局部引用
        from rich import print

        # 创建message列表，用于发送
        messages = []


        # 构建系统提示词
        system_prompt = {
            "role": "system",
            "content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"
        }
        messages.append(system_prompt)


        # 调用插件，进行处理
        plugin_manager.broadcast_event("normalize_text", configurator,source_text_dict)


        # 如果开启译前替换功能
        if configurator.pre_translation_switch :
            print("[[green]INFO[/green]] 译前替换功能已开启，正在进行替换 ...")
            source_text_dict = configurator.replace_before_translation(source_text_dict)

        # 如果开启了携带上文功能，v0.9 版本跳过
        if configurator.model != "Sakura-v0.9" and configurator.pre_line_counts and previous_list:
            print(f"[[green]INFO[/green]] 携带上文功能已开启，实际携带 {len(previous_list)} 行上文 ...")
            messages.append(
                {
                    "role": "user",
                    "content": "将下面的日文文本翻译成中文：" + "\n".join(previous_list),
                }
            )

        # 如果开启了保留句内换行符功能
        print("[[green]INFO[/green]] 保留句内换行符功能已开启，将替换句内换行符为特殊符号 ...")
        source_text_dict = Cache_Manager.replace_special_characters(self, source_text_dict, "替换")

        # 如果开启了指令词典功能
        gpt_dict_raw_text = "" # 空变量
        if configurator.model != "Sakura-v0.9" and configurator.prompt_dictionary_switch: # v0.9 版本或功能未启用时跳过
            glossary_prompt = configurator.build_glossary_prompt_sakura(source_text_dict)
            if glossary_prompt:
                gpt_dict_text_list = []
                for gpt in glossary_prompt:
                    src = gpt["src"]
                    dst = gpt["dst"]
                    info = gpt["info"] if "info" in gpt.keys() else None
                    if info:
                        single = f"{src}->{dst} #{info}"
                    else:
                        single = f"{src}->{dst}"
                    gpt_dict_text_list.append(single)

                gpt_dict_raw_text = "\n".join(gpt_dict_text_list)
                print(f"[[green]INFO[/green]] 指令词典功能已开启，本次请求的原文中包含 {len(gpt_dict_text_list)} 条指令词典条目 ...")
                print(f"{gpt_dict_raw_text}")
                print("\n")

        # 将原文本字典转换成raw格式的字符串
        source_text_str_raw = self.convert_dict_to_raw_str(source_text_dict)

        # 构建主要提示词
        if gpt_dict_raw_text == "": 
            user_prompt = "将下面的日文文本翻译成中文：\n" + source_text_str_raw
        else:
            user_prompt = "根据以下术语表（可以为空）：\n" + gpt_dict_raw_text + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：\n" + source_text_str_raw

        messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        return messages, source_text_str_raw

    # 并发接口请求（sakura）
    def concurrent_request_sakura(self):

        # 检查翻译任务是否已经暂停或者退出
        if configurator.Running_status == 9 or configurator.Running_status == 11 :
            return

        try:#方便排查子线程bug

            # ——————————————————————————————————————————截取需要翻译的原文本——————————————————————————————————————————
            configurator.lock1.acquire()  # 获取锁
            # 获取设定行数的文本，并修改缓存文件里的翻译状态为2，表示正在翻译中
            if configurator.tokens_limit_switch:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(self,configurator.tokens_limit, configurator.cache_list,configurator.pre_line_counts)  
            else:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(self,configurator.lines_limit, configurator.cache_list,configurator.pre_line_counts)    
            configurator.lock1.release()  # 释放锁

            # 检查一下是否有发送内容
            if source_text_list == []:
                print("[[salmon1]Warning[/]] 未能获取文本，该线程为多余线程，取消任务")
                return

            # ——————————————————————————————————————————处理原文本的内容与格式——————————————————————————————————————————
            # 将原文本列表改变为请求格式
            source_text_dict, row_count = Cache_Manager.create_dictionary_from_list(self,source_text_list)  

            # 如果原文是日语，清除文本首位中的代码文本，并记录清除信息
            if configurator.source_language == "日语" and configurator.text_clear_toggle:
                source_text_dict,process_info_list = Cache_Manager.process_dictionary(self,source_text_dict)
                row_count = len(source_text_dict)


            # ——————————————————————————————————————————整合发送内容——————————————————————————————————————————        
            messages,source_text_str = Api_Requester.organize_send_content_sakura(self,source_text_dict, previous_list)



            #——————————————————————————————————————————检查tokens发送限制——————————————————————————————————————————
            #计算请求的tokens预计花费
            request_tokens_consume = Request_Limiter.num_tokens_from_messages(self,messages)  #加上2%的修正系数
            #计算回复的tokens预计花费，只计算发送的文本，不计算提示词与示例，可以大致得出
            Original_text = [{"role":"user","content":source_text_str}] # 需要拿列表来包一层，不然计算时会出错 
            completion_tokens_consume = Request_Limiter.num_tokens_from_messages(self,Original_text) #加上2%的修正系数
 
            if request_tokens_consume >= request_limiter.max_tokens :
                print("[[salmon1]Warning[/]] 该条消息总tokens数大于单条消息最大数量" )
                print("[[salmon1]Warning[/]] 该条消息取消任务，进行拆分翻译" )
                return
            
            # ——————————————————————————————————————————开始循环请求，直至成功或失败——————————————————————————————————————————
            start_time = time.time()
            timeout = 220   # 设置超时时间为x秒
            request_errors_count = 0 # 设置请求错误次数限制
            Wrong_answer_count = 0   # 设置错误回复次数限制
            model_degradation = False # 模型退化检测

            while 1 :
                # 检查翻译任务是否已经暂停或者退出
                if configurator.Running_status == 9 or configurator.Running_status == 11 :
                    return

                #检查子线程运行是否超时---------------------------------
                if time.time() - start_time > timeout:
                    print("[[red]Error[/]] 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print("[[green]INFO[/]] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[[green]INFO[/]] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取接口的请求参数
                    temperature, top_p, presence_penalty, frequency_penalty = configurator.get_platform_request_args()
                    
                    # 如果上一次请求出现模型退化，更改参数
                    if model_degradation:
                        frequency_penalty = 0.2


                    extra_query = {
                        'do_sample': True,
                        'num_beams': 1,
                        'repetition_penalty': 1.0
                    }

                    # 获取apikey
                    openai_apikey =  configurator.get_apikey()
                    # 获取请求地址
                    openai_base_url = configurator.base_url
                    # 创建openai客户端
                    openaiclient = OpenAI(api_key = openai_apikey, base_url = openai_base_url)

                    # Token限制模式下，请求的最大tokens数应该与设置保持一致
                    if configurator.tokens_limit_switch:
                        sakura_max_tokens = configurator.tokens_limit
                    else:
                        sakura_max_tokens = 512
                    
                    # 发送对话请求
                    try:
                        response = openaiclient.chat.completions.create(
                            model = configurator.model,
                            messages = messages,
                            temperature = temperature,
                            top_p = top_p,                        
                            frequency_penalty = frequency_penalty,
                            max_tokens = sakura_max_tokens,
                            seed = -1,
                            extra_query = extra_query,
                        )

                    #抛出错误信息
                    except Exception as e:
                        print("[[red]Error[/]] 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("[[red]Error[/]] 请求发生错误次数过多，该线程取消任务！")
                            break

                        #处理完毕，再次进行请求
                        continue


                    # 检查翻译任务是否已经暂停或者退出，不进行接下来的处理了
                    if configurator.Running_status == 9 or configurator.Running_status == 11 :
                        return
                    
                    
                    #——————————————————————————————————————————收到回复，获取返回的信息 ————————————————————————————————————————  
                    # 计算AI回复花费的时间
                    response_time = time.time()
                    Request_consumption_time = round(response_time - Start_request_time, 2)


                    # 计算本次请求的花费的tokens
                    try: # 因为有些中转网站不返回tokens消耗
                        prompt_tokens_used = int(response.usage.prompt_tokens) #本次请求花费的tokens
                    except Exception:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception:
                        completion_tokens_used = 0



                    # 提取回复的文本内容
                    response_content = response.choices[0].message.content 


                    print('\n' )
                    print("[[green]INFO[/]] 已成功接受到AI的回复-----------------------")
                    print(f"[[green]INFO[/]] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[[green]INFO[/]] AI回复的文本内容：\n",response_content ,'\n','\n')

                    # ——————————————————————————————————————————对回复内容处理,检查——————————————————————————————————————————

                    # 调用插件，进行处理
                    plugin_manager.broadcast_event("sakura_complete_text_process", configurator,response_content)

                    # 见raw格式转换为josn格式字符串
                    response_content = Response_Parser.convert_str_to_json_str(self, row_count, response_content)

                    # 提取回复内容
                    response_dict = Response_Parser.text_extraction(self,response_content)

                    # 检查回复内容
                    check_result,error_content =  Response_Parser.check_response_content(self,configurator.reply_check_switch,response_content,response_dict,source_text_dict,configurator.source_language)

                    # ——————————————————————————————————————————回复内容结果录入——————————————————————————————————————————

                    # 如果没有出现错误
                    if check_result :

                        # 强制开启换行符还原功能
                        response_dict = Cache_Manager.replace_special_characters(self,response_dict, "还原")

                        #如果开启译后文本替换功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[[green]INFO[/]] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.label_output_path, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁


                        # 更新运行日志数据
                        configurator.update_running_params(1, row_count, prompt_tokens_used, completion_tokens_used)

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress                    

                        print("\n--------------------------------------------------------------------------------------")
                        print(f"\n[[green]Success[/]] AI回复内容检查通过！！！已翻译完成{progress}%")
                        print("\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:

                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新运行日志数据
                        configurator.update_running_params(0, row_count, prompt_tokens_used, completion_tokens_used)
                        
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("[[salmon1]Warning[/]] AI回复内容存在问题:",error_content,"\n")

                        # 检查一下是不是模型退化
                        if error_content == "AI回复内容出现高频词,并重新翻译":
                            print("[[salmon1]Warning[/]] 下次请求将修改参数，回避高频词输出","\n")
                            model_degradation = True

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("[[salmon1]Warning[/]] 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("[[salmon1]Warning[/]] 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("[[red]Error[/]] 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return


    # 将json文本改为纯文本
    def convert_dict_to_raw_str(self,source_text_dict):
        str_list = []
        for idx in range(len(source_text_dict.keys())):
            # str_list.append(s['source_text'])
            str_list.append(source_text_dict[f"{idx}"])
        raw_str = "\n".join(str_list)
        return raw_str

# UI交互器
class User_Interface_Prompter(QObject):
    signal = pyqtSignal(str,str,int) #创建信号,并确定发送参数类型

    def __init__(self, app_fluent_window):
       super().__init__()  # 调用父类的构造函数
       self.stateTooltip = None # 存储翻译状态控件
       self.total_text_line_count = 0 # 存储总文本行数
       self.translated_line_count = 0 # 存储已经翻译文本行数
       self.progress = 0.0           # 存储翻译进度
       self.tokens_spent = 0  # 存储已经花费的tokens
       self.amount_spent = 0  # 存储已经花费的金钱
       self.num_worker_threads = 0 # 存储子线程数
       self.translated_token_count_this_run = 0  # 存储本次已经翻译文本 tokens 数
       self.translated_line_count_this_run = 0  # 存储本次已经翻译文本行数
       self.translation_start_time = 0

    # 槽函数，用于接收子线程发出的信号，更新界面UI的状态，因为子线程不能更改父线程的QT的UI控件的值
    def on_update_ui(self,input_str1,input_str2,iunput_int1):

        if input_str1 == "翻译状态提示":
            if input_str2 == "开始翻译":
                self.translation_start_time = time.time()
                self.translated_token_count_this_run = 0
                self.translated_line_count_this_run = 0
                self.stateTooltip = StateToolTip(" 正在进行翻译中，客官请耐心等待哦~~", "　　　当前任务开始于 " + datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S"), app_fluent_window)
                self.stateTooltip.move(510, 30) # 设定控件的出现位置，该位置是传入的Window窗口的位置
                self.stateTooltip.show()
                # 翻译状态改变
                app_fluent_window.Widget_start_translation.A_settings.running_status.setText("正在翻译中")


            elif input_str2 == "翻译暂停":
                print("[[salmon1]Warning[/]] 翻译任务已被暂停-----------------------","\n")
                self.stateTooltip.setContent('翻译已暂停')
                self.stateTooltip.setState(True)
                self.stateTooltip = None
                # 翻译状态改变
                app_fluent_window.Widget_start_translation.A_settings.running_status.setText("已暂停翻译")
                app_fluent_window.Widget_start_translation.A_settings.thread_count.setText("0")
                # 界面提示
                self.createSuccessInfoBar("翻译任务已全部暂停")

            elif input_str2 == "翻译取消":
                print("[[salmon1]Warning[/]] 翻译任务已被取消-----------------------","\n")
                self.stateTooltip.setContent('翻译已取消')
                self.stateTooltip.setState(True)
                self.stateTooltip = None
                # 界面提示
                self.createSuccessInfoBar("翻译任务已全部取消")

                # 翻译状态改变
                app_fluent_window.Widget_start_translation.A_settings.running_status.setText("已取消翻译")
                #重置翻译界面数据
                app_fluent_window.Widget_start_translation.A_settings.translation_project.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.project_id.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.total_text_line_count.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.translated_line_count.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.tokens_spent.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.amount_spent.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.thread_count.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.translation_speed_token.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.translation_speed_line.setText("无")
                app_fluent_window.Widget_start_translation.A_settings.progressRing.setValue(0)


            elif input_str2 == "翻译完成":
                self.stateTooltip.setContent('已经翻译完成啦 😆')
                self.stateTooltip.setState(True)
                self.stateTooltip = None

                # 翻译状态改变
                app_fluent_window.Widget_start_translation.A_settings.running_status.setText("翻译已完成")
                # 子线程数为0
                app_fluent_window.Widget_start_translation.A_settings.thread_count.setText("0")
                #隐藏继续翻译按钮
                app_fluent_window.Widget_start_translation.A_settings.primaryButton_continue_translation.hide()
                #隐藏暂停翻译按钮
                app_fluent_window.Widget_start_translation.A_settings.primaryButton_pause_translation.hide()
                #显示开始翻译按钮
                app_fluent_window.Widget_start_translation.A_settings.primaryButton_start_translation.show()

        elif input_str1 == "运行状态改变":
            # 运行状态改变
            app_fluent_window.Widget_start_translation.A_settings.running_status.setText(input_str2)


        elif input_str1 == "接口测试结果":
            if self.on_api_test_done:
                self.on_api_test_done(input_str2 == "测试成功")

        elif input_str1 == "初始化翻译界面数据":
            # 更新翻译项目信息
            translation_project = configurator.translation_project
            app_fluent_window.Widget_start_translation.A_settings.translation_project.setText(translation_project)

            # 更新项目ID信息
            app_fluent_window.Widget_start_translation.A_settings.project_id.setText(input_str2)

            # 更新需要翻译的文本行数信息
            self.total_text_line_count = iunput_int1 #存储总文本行数
            app_fluent_window.Widget_start_translation.A_settings.total_text_line_count.setText(str(self.total_text_line_count))

            # 翻译状态改变
            app_fluent_window.Widget_start_translation.A_settings.running_status.setText("正在翻译中")

            # 获取当前所有存活的线程
            alive_threads = threading.enumerate()
            self.num_worker_threads = len(alive_threads) - 2  # 减去主线程与一个子线程
            app_fluent_window.Widget_start_translation.A_settings.thread_count.setText(str(self.num_worker_threads))

            # 其他信息设置为0
            app_fluent_window.Widget_start_translation.A_settings.translated_line_count.setText("0")
            app_fluent_window.Widget_start_translation.A_settings.tokens_spent.setText("0")
            app_fluent_window.Widget_start_translation.A_settings.amount_spent.setText("0")
            app_fluent_window.Widget_start_translation.A_settings.translation_speed_token.setText("0")
            app_fluent_window.Widget_start_translation.A_settings.translation_speed_line.setText("0")
            app_fluent_window.Widget_start_translation.A_settings.progressRing.setValue(0)

            # 初始化存储的数值
            self.translated_line_count = 0 
            self.tokens_spent = 0  
            self.amount_spent = 0  
            self.progress = 0.0 
            self.translated_token_count_this_run = 0
            self.translated_line_count_this_run = 0
            self.translation_start_time = time.time()


        elif input_str1 == "重置界面数据":

            #重置翻译界面数据
            app_fluent_window.Widget_start_translation.A_settings.translation_project.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.project_id.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.total_text_line_count.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.translated_line_count.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.translation_speed_token.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.translation_speed_line.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.tokens_spent.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.amount_spent.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.thread_count.setText("无")
            app_fluent_window.Widget_start_translation.A_settings.progressRing.setValue(0)


        elif input_str1 == "更新翻译界面数据":
            elapsed_time_this_run = time.time() - self.translation_start_time

            app_fluent_window.Widget_start_translation.A_settings.translated_line_count.setText(str(self.translated_line_count))

            app_fluent_window.Widget_start_translation.A_settings.translation_speed_token.setText(f"{self.translated_token_count_this_run / elapsed_time_this_run:.2f}")
            app_fluent_window.Widget_start_translation.A_settings.translation_speed_line.setText(f"{self.translated_line_count_this_run / elapsed_time_this_run:.2f}")

            app_fluent_window.Widget_start_translation.A_settings.tokens_spent.setText(str(self.tokens_spent))

            app_fluent_window.Widget_start_translation.A_settings.amount_spent.setText(str(self.amount_spent))

            app_fluent_window.Widget_start_translation.A_settings.thread_count.setText(str(self.num_worker_threads))

            progress = int(round(self.progress, 0))
            app_fluent_window.Widget_start_translation.A_settings.progressRing.setValue(progress)

    
    # 更新翻译进度数据
    def update_data(self, state, translated_line_count, prompt_tokens_used, completion_tokens_used):

        input_price = configurator.model_input_price               #获取输入价格
        output_price = configurator.model_output_price               #获取输出价格

        #计算已经翻译的文本数
        if state == 1:
            # 更新已经翻译的文本数
            self.translated_line_count = self.translated_line_count + translated_line_count   
            self.translated_line_count_this_run += translated_line_count
            self.translated_token_count_this_run += completion_tokens_used

        #计算tokens花销
        self.tokens_spent = self.tokens_spent + prompt_tokens_used + completion_tokens_used

        #计算金额花销
        self.amount_spent = self.amount_spent + (input_price/1000 * prompt_tokens_used)  + (output_price/1000 * completion_tokens_used) 
        self.amount_spent = round(self.amount_spent, 4)

        #计算进度条
        result = self.translated_line_count / self.total_text_line_count * 100
        self.progress = round(result, 2)

        # 获取当前所有存活的线程
        alive_threads = threading.enumerate()
        # 计算子线程数量
        if (len(alive_threads) - 2) <= 0: # 减去主线程与一个子线程，和一个滞后线程
            counts = 1
        else:
            counts = len(alive_threads) - 2

        self.num_worker_threads = counts
        #print("[DEBUG] 子线程数：",num_worker_threads)




    #成功信息居中弹出框函数
    def createSuccessInfoBar(self,str):
        InfoBar.success(
            title='[Success]',
            content=str,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=app_fluent_window
            )

    #错误信息右下方弹出框函数
    def createErrorInfoBar(self,str):
        InfoBar.error(
            title='[Error]',
            content=str,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=-1,    # won't disappear automatically
            parent=app_fluent_window
            )

    #提醒信息左上角弹出框函数
    def createWarningInfoBar(self,str):
        InfoBar.warning(
            title='[Warning]',
            content=str,
            orient=Qt.Horizontal,
            isClosable=False,   # disable close button
            position=InfoBarPosition.TOP_LEFT,
            duration=2000,
            parent=app_fluent_window
            )

# 任务执行器
class background_executor(threading.Thread, AiNieeBase): 
    def __init__(
        self,
        task_id = None,
        input_folder = None,
        output_folder = None,
        tag = None,
        api_url = None,
        api_key = None,
        api_format = None,
        model = None,
        auto_complete = None,
        proxy_url = None,
        proxy_enable = None,
        callback = None,
    ):
        super().__init__() # 调用父类构造
        self.task_id = task_id
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.tag = tag
        self.api_url = api_url
        self.api_key = api_key
        self.api_format = api_format
        self.model = model
        self.auto_complete = auto_complete
        self.proxy_url = proxy_url
        self.proxy_enable = proxy_enable
        self.callback = callback

    def run(self):
        # 执行翻译
        if self.task_id == "开始翻译":
            # 如果是空闲状态进入翻译
            if configurator.Running_status  == 0:
                configurator.Running_status = 6

            # 如果是暂停状态进入翻译
            if configurator.Running_status  == 10:
                pass


            # 执行翻译主函数
            Translator.Main(self)


            # 如果正常完成了翻译任务
            if configurator.Running_status == 6:
                configurator.Running_status = 0

            # 如果中途暂停了翻译任务
            if configurator.Running_status == 9:
                configurator.Running_status = 10 # 已完成暂停状态
                user_interface_prompter.signal.emit("翻译状态提示","翻译暂停",0)

            # 如果中途取消了翻译任务
            if configurator.Running_status == 11:
                configurator.Running_status = 0  # 已完成取消状态，变成空闲状态
                user_interface_prompter.signal.emit("翻译状态提示","翻译取消",0)


        # 执行接口测试
        elif self.task_id == "接口测试":
            configurator.Running_status = 1
            user_interface_prompter.on_api_test_done = self.callback # 设置回调函数
            Request_Tester.request_test(
                self,
                user_interface_prompter,
                tag = self.tag,
                api_url = self.api_url,
                api_key = self.api_key,
                api_format = self.api_format,
                model = self.model,
                auto_complete = self.auto_complete,
                proxy_url = self.proxy_url,
                proxy_enable = self.proxy_enable,
            )
            configurator.Running_status = 0

        # 输出缓存文件实现函数
        elif self.task_id == "输出缓存文件":
            File_Outputter.output_cache_file(self,configurator.cache_list,self.output_folder)
            print('[[green]Success[/]] 已输出缓存文件到文件夹')

        # 输出已翻译文件实现函数
        elif self.task_id == "输出已翻译文件":

            # 复制缓存文本数据，避免手动导出被插件处理
            try:
                new_cache_data = copy.deepcopy(configurator.cache_list)
            except:
                print("[[green]INFO[/]]: 无法正常进行深层复制,改为浅复制")
                new_cache_data = configurator.cache_list.copy()

            # 调用插件
            plugin_manager.broadcast_event("manual_export", configurator,new_cache_data)

            File_Outputter.output_translated_content(self,new_cache_data,self.output_folder,self.input_folder)
            print('[[green]Success[/]] 已输出已翻译文件到文件夹')


    # 开始翻译判断函数
    def Start_translation_switch(self):
        if configurator.Running_status == 0:
            return True

        else :
            user_interface_prompter.createWarningInfoBar("正在进行任务中，请等待任务结束后再操作~")
            return False


    # 继续翻译判断函数
    def Continue_translation_switch(self):
        if configurator.Running_status == 10:
            return True

        else :
            user_interface_prompter.createWarningInfoBar("正在清理线程中，请耐心等待一会")
            print("[[salmon1]Warning[/]] 多线程任务正清理中，请耐心等待一会","\n")
            return False


    # 暂停翻译判断+实现函数
    def Pause_translation(self):
        configurator.Running_status = 9
        user_interface_prompter.createWarningInfoBar("软件的多线程任务正在逐一取消中，请等待全部任务释放完成！！！")
        user_interface_prompter.signal.emit("运行状态改变","正在取消线程任务中",0)
        print("[[salmon1]Warning[/]] 软件的多线程任务正在逐一取消中，请等待全部任务释放完成！！！-----------------------","\n")


    # 取消翻译判断+实现函数
    def Cancel_translation(self):

        # 如果正在翻译中或者取消线程任务中
        if configurator.Running_status in (6,9):
            configurator.Running_status = 11
            user_interface_prompter.createWarningInfoBar("软件的多线程任务正在逐一取消中，请等待全部任务释放完成！！！")
            user_interface_prompter.signal.emit("运行状态改变","正在取消线程任务中",0)
            print("[[salmon1]Warning[/]] 软件的多线程任务正在逐一取消中，请等待全部翻译任务释放完成！！！-----------------------","\n")

        # 如果已经暂停翻译
        elif configurator.Running_status == 10:

            configurator.Running_status = 0
            print("[[salmon1]Warning[/]] 翻译任务已取消-----------------------","\n")
            # 界面提示
            user_interface_prompter.createWarningInfoBar("翻译已取消")
            user_interface_prompter.signal.emit("重置界面数据","翻译取消",0)
            user_interface_prompter.signal.emit("运行状态改变","已取消翻译",0)

        # 如果正在空闲中
        elif configurator.Running_status == 0:

            configurator.Running_status = 0
            print("[[salmon1]Warning[/]] 当前无翻译任务-----------------------","\n")
            # 界面提示
            user_interface_prompter.createWarningInfoBar("当前无翻译任务")
            user_interface_prompter.signal.emit("重置界面数据","翻译取消",0)


    # 接口测试判断函数
    def Request_test_switch(self):
        if configurator.Running_status == 0:
            return True
        else:
            return False



if __name__ == '__main__':
    #开启子进程支持
    multiprocessing.freeze_support() 

    # 启用了高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    Software_Version = "AiNiee v5.0"  #软件版本号

    # 工作目录改为python源代码所在的目录
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0])) # 获取当前工作目录
    sys.path.append(script_dir)
    print("[[green]INFO[/]] 当前工作目录是:",script_dir,'\n')

    # 创建全局配置器
    configurator = Configurator(script_dir)

    # 创建全局限制器
    request_limiter = Request_Limiter(configurator)

    # 创建全局插件管理器
    plugin_manager = Plugin_Manager()
    plugin_manager.load_plugins_from_directory(configurator.plugin_dir)

    # 创建全局应用对象
    app = QApplication(sys.argv)
    
    # 载入配置文件
    config = {}
    if os.path.exists("./Resource/config.json"):
        with open("./Resource/config.json", "r", encoding = "utf-8") as reader:
            config = json.load(reader)
    else:
        print("[[red]ERROR[/]] 配置文件不存在 ...")

    # 设置全局字体属性，解决狗牙问题
    font = QFont()
    font.setHintingPreference(QFont.PreferFullHinting if config.get("font_hinting", True) else QFont.PreferNoHinting)
    app.setFont(font)

    # 创建全局窗口对象
    app_fluent_window = AppFluentWindow(Software_Version)

    # 创建测试器对象
    request_tester = Request_Tester()

    # 创建全局UI通讯器
    user_interface_prompter = User_Interface_Prompter(app_fluent_window)

    # 创建信号与槽函数的绑定，使用方法为 user_interface_prompter.signal.emit("str", "str"....)
    user_interface_prompter.signal.connect(user_interface_prompter.on_update_ui)

    # 显示全局窗口
    app_fluent_window.add_pages(configurator, plugin_manager, background_executor, user_interface_prompter, jtpp)
    app_fluent_window.show()

    #进入事件循环，等待用户操作
    sys.exit(app.exec_())