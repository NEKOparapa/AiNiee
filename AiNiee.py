
# ═══════════════════════════════════════════════════════
# ████ 警告：擅自进入，后果自负                         ████
# ████ 恭喜你，你已经发现了我的杰作                     ████
# ████ 一座万行意大利面条式代码的屎山                   ████
# ████ 请谨慎前行，阅读这段代码可能会。                 ████
# ████ 立刻让你感到不幸和绝望                          ████
# ═══════════════════════════════════════════════════════

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

from openai import OpenAI #需要安装库pip install openai
import google.generativeai as genai #需要安装库pip install -U google-generativeai
import anthropic #需要安装库pip install anthropic
import cohere  #需要安装库pip install cohere

from PyQt5.QtCore import  QObject,  Qt, pyqtSignal 
from PyQt5.QtWidgets import QApplication, QTableWidgetItem
from qfluentwidgets import InfoBar, InfoBarPosition, StateToolTip

from StevExtraction import jtpp  # type: ignore #导入文本提取工具
from Module_Folders.Cache_Manager.Cache import Cache_Manager  
from Module_Folders.File_Reader.File1 import File_Reader 
from Module_Folders.File_Outputer.File2 import File_Outputter 
from Module_Folders.Response_Parser.Response import Response_Parser
from Module_Folders.Request_Tester.Request import Request_Tester
from Module_Folders.Configurator.Config import Configurator
from Module_Folders.Request_Limiter.Request_limit import Request_Limiter
from User_Interface.MainWindows import window  # 导入界面
from User_Interface.MainWindows import Widget_New_proxy
from Plugin_Scripts.Plugin_Manager import Plugin_Manager


# 翻译器
class Translator():
    def __init__(self):
        pass
    
    # 翻译器主逻辑
    def Main(self):
        # ——————————————————————————————————————————配置信息初始化—————————————————————————————————————————


        user_interface_prompter.read_write_config("write",configurator.resource_dir) # 将界面信息写入配置文件中

        configurator.Read_Configuration_File() # 读取配置文件

        # 根据混合翻译设置更换翻译平台
        if configurator.mixed_translation_toggle:
            configurator.translation_platform = configurator.mixed_translation_settings["translation_platform_1"]

        configurator.configure_translation_platform(configurator.translation_platform,None)  # 配置翻译平台信息
        request_limiter.set_limit(configurator.max_tokens,configurator.TPM_limit,configurator.RPM_limit) # 配置请求限制器，依赖前面的配置信息，必需在最后面初始化


        # ——————————————————————————————————————————读取原文到缓存—————————————————————————————————————————


        #如果是从头开始翻译
        if configurator.Running_status == 6:
            # 读取文件
            try:
                configurator.cache_list = File_Reader.read_files(self,configurator.translation_project, configurator.Input_Folder)

            except Exception as e:
                print(e)
                print("\033[1;31mError:\033[0m 读取原文文件失败，请检查项目类型是否设置正确，输入文件夹是否混杂其他非必要文件！")
                return


        # ——————————————————————————————————————————插件预处理—————————————————————————————————————————
        
        # 加载插件
        plugin_manager.load_plugins_from_directory(configurator.plugin_dir)


        # 调用插件，进行文本过滤
        plugin_manager.broadcast_event("text_filter", configurator,configurator.cache_list)

        # 调用插件，进行文本预处理
        plugin_manager.broadcast_event("preproces_text", configurator,configurator.cache_list)



        # ——————————————————————————————————————————构建并发任务池子—————————————————————————————————————————


        # 计算待翻译的文本总行数，tokens总数
        untranslated_text_line_count,untranslated_text_tokens_count = Cache_Manager.count_and_update_translation_status_0_2(self, configurator.cache_list) #获取需要翻译的文本总行数
        # 计算剩余任务数
        tasks_Num = Translator.calculate_total_tasks(self,untranslated_text_line_count,untranslated_text_tokens_count,configurator.lines_limit,configurator.tokens_limit,configurator.tokens_limit_switch,configurator.translation_platform)


        # 更新界面UI信息
        if configurator.Running_status == 10: # 如果是继续翻译
            total_text_line_count = user_interface_prompter.total_text_line_count # 与上一个翻译任务的总行数一致
            user_interface_prompter.signal.emit("翻译状态提示","开始翻译",0)

            #最后改一下运行状态，为正常翻译状态
            configurator.Running_status = 6

        else:#如果是从头开始翻译
            total_text_line_count = untranslated_text_line_count
            project_id = configurator.cache_list[0]["project_id"]
            user_interface_prompter.signal.emit("初始化翻译界面数据",project_id,untranslated_text_line_count) #需要输入够当初设定的参数个数
            user_interface_prompter.signal.emit("翻译状态提示","开始翻译",0)


        # 输出开始翻译的日志
        print("\n")
        print("[INFO]  翻译项目为",configurator.translation_project, '\n')
        print("[INFO]  翻译平台为",configurator.translation_platform, '\n')
        print("[INFO]  请求地址为",configurator.base_url, '\n')
        print("[INFO]  翻译模型为",configurator.model_type, '\n')

        if configurator.translation_platform != "SakuraLLM":
            print("[INFO]  当前设定的系统提示词为:\n", configurator.get_system_prompt(), '\n')

        print("[INFO]  游戏文本从",configurator.source_language, '翻译到', configurator.target_language,'\n')
        print("[INFO]  文本总行数为：",total_text_line_count,"  需要翻译的行数为：",untranslated_text_line_count)
        if configurator.tokens_limit_switch:
            print("[INFO]  每次发送tokens为：",configurator.tokens_limit,"  计划的翻译任务总数是：", tasks_Num,'\n') 
        else:    
            print("[INFO]  每次发送行数为：",configurator.lines_limit,"  计划的翻译任务总数是：", tasks_Num,'\n') 
        print("\033[1;32m[INFO] \033[0m 五秒后开始进行翻译，请注意保持网络通畅，余额充足。", '\n')
        time.sleep(5)  


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
            print("\033[1;33mWarning:\033[0m 仍然有部分未翻译，将进行拆分后重新翻译，-----------------------------------")
            print("[INFO] 当前拆分翻译轮次：",retry_translation_count ," 到达最大轮次：",configurator.round_limit," 时，将停止翻译")
            user_interface_prompter.signal.emit("运行状态改变",f"正在拆分翻译",0)

            # 根据混合翻译设置更换翻译平台,并重新初始化部分配置信息
            if configurator.mixed_translation_toggle:

                configurator.Read_Configuration_File() # 重新获取配置信息

                # 更换翻译平台
                if retry_translation_count == 1:
                    configurator.translation_platform = configurator.mixed_translation_settings["translation_platform_2"]
                    print("[INFO]  已开启混合翻译功能，正在进行次轮翻译，翻译平台更换为：",configurator.translation_platform, '\n')
                elif retry_translation_count >= 2:
                    configurator.translation_platform = configurator.mixed_translation_settings["translation_platform_3"]
                    print("[INFO]  已开启混合翻译功能，正在进行末轮翻译，翻译平台更换为：",configurator.translation_platform, '\n')

                # 更换模型选择
                model_type = None
                if (retry_translation_count == 1) and (configurator.mixed_translation_settings["customModel_siwtch_2"]):
                    model_type = configurator.mixed_translation_settings["model_type_2"]
                    print("[INFO]  模型更换为：",model_type, '\n')

                elif (retry_translation_count >= 2) and (configurator.mixed_translation_settings["customModel_siwtch_3"]):
                    model_type = configurator.mixed_translation_settings["model_type_3"]
                    print("[INFO]  模型更换为：",model_type, '\n')

                configurator.configure_translation_platform(configurator.translation_platform,model_type)  # 重新配置翻译平台信息
                request_limiter.set_limit(configurator.max_tokens,configurator.TPM_limit,configurator.RPM_limit)# 重新配置请求限制器


            # 拆分文本行数或者tokens数
            if (configurator.mixed_translation_toggle) and (retry_translation_count == 1) and (not configurator.mixed_translation_settings["split_switch_2"]):
                print("[INFO] 检测到不进行拆分设置，发送行数/tokens数将继续保持不变")

            if (configurator.mixed_translation_toggle) and (retry_translation_count >= 2) and (not configurator.mixed_translation_settings["split_switch_3"]):
                print("[INFO] 检测到不进行拆分设置，发送行数/tokens数将继续保持不变")

            else:
                configurator.lines_limit,configurator.tokens_limit = Translator.update_lines_or_tokens(self,configurator.lines_limit,configurator.tokens_limit) # 更换配置中的文本行数
            

            # 显示日志
            if configurator.tokens_limit_switch:
                print("[INFO] 未翻译文本总tokens为：",untranslated_text_tokens_count,"  每次发送tokens为：",configurator.tokens_limit, '\n')
            else:
                print("[INFO] 未翻译文本总行数为：",untranslated_text_line_count,"  每次发送行数为：",configurator.lines_limit, '\n')


            # 计算剩余任务数
            tasks_Num = Translator.calculate_total_tasks(self,untranslated_text_line_count,untranslated_text_tokens_count,configurator.lines_limit,configurator.tokens_limit,configurator.tokens_limit_switch,configurator.translation_platform)



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
                print ("\033[1;33mWarning:\033[0m 已经达到拆分翻译轮次限制，但仍然有部分文本未翻译，不影响使用，可手动翻译", '\n')
                break

            #重新计算未翻译文本的数量
            untranslated_text_line_count,untranslated_text_tokens_count = Cache_Manager.count_and_update_translation_status_0_2(self,configurator.cache_list)

        print ("\033[1;32mSuccess:\033[0m  翻译阶段已完成，正在处理数据-----------------------------------", '\n')


        # ——————————————————————————————————————————插件后处理—————————————————————————————————————————
            
        # 调用插件，进行文本后处理
        plugin_manager.broadcast_event("postprocess_text", configurator,configurator.cache_list)


        # 调用插件，进行文本后处理
        plugin_manager.broadcast_event("optimize_text", configurator,configurator.cache_list)

        #如果开启了转换简繁开关功能，则进行文本转换
        if configurator.conversion_toggle:
            try:
                configurator.cache_list = Cache_Manager.simplified_and_traditional_conversion(self,configurator.cache_list, configurator.opencc_preset)
                print(f"\033[1;32mSuccess:\033[0m  文本转化{configurator.target_language}完成-----------------------------------", '\n')   

            except Exception as e:
                print("\033[1;33mWarning:\033[0m 文本转换出现问题！！将跳过该步，错误信息如下")
                print(f"Error: {e}\n")


        # ——————————————————————————————————————————将数据处理并保存为文件—————————————————————————————————————————


        # 将翻译结果写为对应文件
        File_Outputter.output_translated_content(self,configurator.cache_list,configurator.Output_Folder,configurator.Input_Folder)



        # —————————————————————————————————————#全部翻译完成——————————————————————————————————————————


        print("\033[1;32mSuccess:\033[0m  译文文件写入完成-----------------------------------", '\n')  
        user_interface_prompter.signal.emit("翻译状态提示","翻译完成",0)
        print("\n--------------------------------------------------------------------------------------")
        print("\n\033[1;32mSuccess:\033[0m 已完成全部翻译任务，程序已经停止")   
        print("\n\033[1;32mSuccess:\033[0m 请检查译文文件，格式是否错误，存在错行，空行等问题")
        print("\n-------------------------------------------------------------------------------------\n")


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
        if new_tokens_limit < 20:
            new_tokens_limit = 20 # 保底非零

        return new_lines_limit,new_tokens_limit


    # 计算剩余任务总数
    def calculate_total_tasks(self,total_lines,total_tokens,lines_limit,tokens_limit,switch = False,translation_platform = None):
        
        if switch:

            if translation_platform == "SakuraLLM":

                tokens_limit_sakura = tokens_limit - 95 # 减去系统提示词的消耗
                if total_tokens  <= tokens_limit_sakura:  # 防止无法产出任务数
                    return  2

                if  tokens_limit_sakura <= 20: # 防止任务数过多
                    tokens_limit_sakura = 20

                if total_tokens % tokens_limit_sakura == 0:
                    tasks_Num = total_tokens // tokens_limit_sakura 
                else:
                    tasks_Num = total_tokens // tokens_limit_sakura + 1
            
            else:

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
    def concurrent_request (self):

        if configurator.translation_platform == "OpenAI" or configurator.translation_platform == "OpenAI_proxy":
            self.concurrent_request_openai()
        
        elif configurator.translation_platform == "Google":
            self.concurrent_request_google()

        elif configurator.translation_platform == "Cohere":
            self.Concurrent_Request_cohere()

        elif configurator.translation_platform == "Anthropic" or configurator.translation_platform == "Anthropic_proxy":
            self.concurrent_request_anthropic()

        elif configurator.translation_platform == "Moonshot":
            self.concurrent_request_openai()

        elif configurator.translation_platform == "Deepseek":
            self.concurrent_request_openai()

        elif configurator.translation_platform == "Dashscope":
            self.concurrent_request_openai()

        elif configurator.translation_platform == "Volcengine":
            self.concurrent_request_openai()

        elif configurator.translation_platform == "零一万物":
            self.concurrent_request_openai()

        elif configurator.translation_platform == "智谱":
            self.concurrent_request_openai()

        elif configurator.translation_platform == "SakuraLLM":
            self.concurrent_request_sakura()


    # 整理发送内容（Openai）
    def organize_send_content_openai(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        #如果开启提示字典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[INFO]  已添加术语表：\n",glossary_prompt)


        #如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[INFO]  已添加角色介绍：\n",characterization)

        #如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[INFO]  已添加背景设定：\n",world_building)

        #如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[INFO]  已添加文风要求：\n",writing_style)



        # 添加系统提示词信息
        messages.append({"role": "system","content": system_prompt })



        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        #构建默认示例
        original_exmaple,translation_example =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example:

            the_original_exmaple =  {"role": "user","content":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "assistant", "content": (f'{fol_prompt}```json\n{translation_example}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[INFO]  已添加格式原文示例：\n",original_exmaple)
            print("[INFO]  已添加格式译文示例：\n",translation_example, '\n')


        #如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "user","content":original_exmaple_3 }
                the_translation_example = {"role": "assistant", "content": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[INFO]  已添加用户原文示例：\n",original_exmaple_3)
                print("[INFO]  已添加用户译文示例：\n",translation_example_3, '\n')


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[INFO] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        #如果开启译前替换字典功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[INFO] 你开启了译前替换字典功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果加上文
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                pass
                #print("[INFO]  已添加上文：\n",previous)



        #获取提问时的前置文本
        pre_prompt = configurator.build_userQueryPrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelResponsePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)


        # 构建用户信息
        source_text_str = json.dumps(source_text_dict, ensure_ascii=False)  
        source_text_str = f'{previous}\n{pre_prompt}```json\n{source_text_str}\n```'
        messages.append({"role":"user","content":source_text_str })


        # 构建模型信息
        if( "claude" in configurator.model_type or "gpt" in configurator.model_type or "moonshot" in configurator.model_type or "deepseek" in configurator.model_type) :
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
                print("\033[1;33mWarning:\033[0m 未能获取文本，该线程为多余线程，取消任务")
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
                print("\033[1;31mError:\033[0m 该条消息总tokens数大于单条消息最大数量" )
                print("\033[1;31mError:\033[0m 该条消息取消任务，进行拆分翻译" )
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
                    print("\033[1;31mError:\033[0m 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print(f"[INFO] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[INFO] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取AI的参数设置
                    temperature,top_p,presence_penalty,frequency_penalty= configurator.get_openai_parameters()
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
                            model= configurator.model_type,
                            messages = messages ,
                            temperature=temperature,
                            top_p = top_p,                        
                            presence_penalty=presence_penalty,
                            frequency_penalty=frequency_penalty
                            )
                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
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
                    except Exception as e:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception as e:
                        completion_tokens_used = 0



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.choices[0].message.content 
                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 提取文本时出现问题！！！运行错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[INFO] 已成功接受到AI的回复-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

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


                        # 如果开启译后替换字典功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[INFO] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model_type)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.Output_Folder, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁
                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print(f"\n--------------------------------------------------------------------------------------")
                        print(f"\n\033[1;32mSuccess:\033[0m AI回复内容检查通过！！！已翻译完成{progress}%")
                        print(f"\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:
                        print("\033[1;33mWarning:\033[0m AI回复内容存在问题:",error_content,"\n")


                        configurator.lock2.acquire()  # 获取锁

                        # 如果是进行平时的翻译任务
                        if configurator.Running_status == 6 :

                            # 更新翻译界面数据
                            user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                            # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                            user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁


                        # 检查一下是不是模型退化
                        if error_content == "AI回复内容出现高频词,并重新翻译":
                            print("\033[1;33mWarning:\033[0m 下次请求将修改参数，回避高频词输出","\n")
                            model_degradation = True

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("\033[1;33mWarning:\033[0m 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("\033[1;33mWarning:\033[0m 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("\033[1;31mError:\033[0m 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（Google）
    def organize_send_content_google(self,source_text_dict, previous_list):
        # 创建message列表，用于发送
        messages = []

        # 获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        # #如果开启提示字典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[INFO]  已添加术语表：\n",glossary_prompt)


        # 如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[INFO]  已添加角色介绍：\n",characterization)

        # 如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[INFO]  已添加背景设定：\n",world_building)

        # 如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[INFO]  已添加文风要求：\n",writing_style)

        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        # 构建默认示例
        original_exmaple,translation_example =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example:
            
            the_original_exmaple =  {"role": "user","parts":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "model", "parts": (f'{fol_prompt}```json\n{translation_example}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[INFO]  已添加格式原文示例：\n",original_exmaple)
            print("[INFO]  已添加格式译文示例：\n",translation_example, '\n')


        # 如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "user","parts":original_exmaple_3 }
                the_translation_example = {"role": "model", "parts": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[INFO]  已添加用户原文示例：\n",original_exmaple_3)
                print("[INFO]  已添加用户译文示例：\n",translation_example_3, '\n')


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[INFO] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        # 如果开启译前替换字典功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[INFO] 你开启了译前替换字典功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        # 如果加上文
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                pass
                #print("[INFO]  已添加上文：\n",previous)


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
                print("\033[1;33mWarning:\033[0m 未能获取文本，该线程为多余线程，取消任务")
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
                print("\033[1;33mWarning:\033[0m 该条消息总tokens数大于单条消息最大数量" )
                print("\033[1;33mWarning:\033[0m 该条消息取消任务，进行拆分翻译" )
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
                    print("\033[1;31mError:\033[0m 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print(f"[INFO] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[INFO] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取AI的参数设置
                    temperature= configurator.get_google_parameters()

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
                    model = genai.GenerativeModel(model_name=configurator.model_type,
                                    generation_config=generation_config,
                                    safety_settings=safety_settings,
                                    system_instruction = system_prompt)


                    # 发送对话请求
                    try:
                        response = model.generate_content(messages)

                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
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
                        print("\033[1;31mError:\033[0m 提取文本时出现错误！！！运行的错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response.prompt_feedback)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[INFO] 已成功接受到AI的回复-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

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

                        #如果开启译后替换字典功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[INFO] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model_type)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.Output_Folder, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁


                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print(f"\n--------------------------------------------------------------------------------------")
                        print(f"\n\033[1;32mSuccess:\033[0m AI回复内容检查通过！！！已翻译完成{progress}%")
                        print(f"\n--------------------------------------------------------------------------------------\n")

                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:
                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("\033[1;33mWarning:\033[0m AI回复内容存在问题:",error_content,"\n")

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("\033[1;33mWarning:\033[0m 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("\033[1;33mWarning:\033[0m 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("\033[1;31mError:\033[0m 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（Anthropic）
    def organize_send_content_anthropic(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        # 如果开启提示字典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[INFO]  已添加术语表：\n",glossary_prompt)


        #如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[INFO]  已添加角色介绍：\n",characterization)

        #如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[INFO]  已添加背景设定：\n",world_building)

        #如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[INFO]  已添加文风要求：\n",writing_style)

        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        #构建默认示例
        original_exmaple,translation_example =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example:

            the_original_exmaple =  {"role": "user","content":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "assistant", "content": (f'{fol_prompt}```json\n{translation_example}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[INFO]  已添加格式原文示例：\n",original_exmaple)
            print("[INFO]  已添加格式译文示例：\n",translation_example, '\n')


        #如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "user","content":original_exmaple_3 }
                the_translation_example = {"role": "assistant", "content": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[INFO]  已添加用户原文示例：\n",original_exmaple_3)
                print("[INFO]  已添加用户译文示例：\n",translation_example_3, '\n')


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[INFO] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        #如果开启译前替换字典功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[INFO] 你开启了译前替换字典功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果加上文
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                pass
                #print("[INFO]  已添加上文：\n",previous)


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
                print("\033[1;33mWarning:\033[0m 未能获取文本，该线程为多余线程，取消任务")
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
                print("\033[1;31mError:\033[0m 该条消息总tokens数大于单条消息最大数量" )
                print("\033[1;31mError:\033[0m 该条消息取消任务，进行拆分翻译" )
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
                    print("\033[1;31mError:\033[0m 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print(f"[INFO] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[INFO] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()
                    # 获取AI的参数设置
                    temperature= configurator.get_anthropic_parameters()
                    # 获取apikey
                    anthropic_apikey =  configurator.get_apikey()
                    # 创建anthropic客户端
                    client = anthropic.Anthropic(api_key=anthropic_apikey,base_url=configurator.base_url)
                    # 发送对话请求
                    try:
                        response = client.messages.create(
                            model= configurator.model_type,
                            max_tokens=4000,
                            system= system_prompt,
                            messages = messages ,
                            temperature=temperature
                            )



                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
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
                    except Exception as e:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception as e:
                        completion_tokens_used = 0



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.content[0].text 
                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 提取文本时出现问题！！！运行错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[INFO] 已成功接受到AI的回复-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

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

                        #如果开启译后替换字典功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[INFO] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model_type)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.Output_Folder, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print(f"\n--------------------------------------------------------------------------------------")
                        print(f"\n\033[1;32mSuccess:\033[0m AI回复内容检查通过！！！已翻译完成{progress}%")
                        print(f"\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:

                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("\033[1;33mWarning:\033[0m AI回复内容存在问题:",error_content,"\n")

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("\033[1;33mWarning:\033[0m 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("\033[1;33mWarning:\033[0m 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("\033[1;31mError:\033[0m 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（Cohere）
    def organize_send_content_cohere(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #获取基础系统提示词
        system_prompt = configurator.get_system_prompt()


        # 如果开启提示字典
        glossary_prompt = ""
        glossary_prompt_cot = ""
        if configurator.prompt_dictionary_switch :
            glossary_prompt,glossary_prompt_cot = configurator.build_glossary_prompt(source_text_dict,configurator.cn_prompt_toggle)
            if glossary_prompt :
                system_prompt += glossary_prompt 
                print("[INFO]  已添加术语表：\n",glossary_prompt)


        # 如果角色介绍开关打开
        characterization = ""
        characterization_cot = ""
        if configurator.characterization_switch :
            characterization,characterization_cot = configurator.build_characterization(source_text_dict,configurator.cn_prompt_toggle)
            if characterization:
                system_prompt += characterization 
                print("[INFO]  已添加角色介绍：\n",characterization)

        #如果背景设定开关打开
        world_building = ""
        world_building_cot = ""
        if configurator.world_building_switch :
            world_building,world_building_cot = configurator.build_world(configurator.cn_prompt_toggle)
            if world_building:
                system_prompt += world_building 
                print("[INFO]  已添加背景设定：\n",world_building)

        #如果文风要求开关打开
        writing_style = ""
        writing_style_cot = ""
        if configurator.writing_style_switch :
            writing_style,writing_style_cot = configurator.build_writing_style(configurator.cn_prompt_toggle)
            if writing_style:
                system_prompt += writing_style 
                print("[INFO]  已添加文风要求：\n",writing_style)

        # 获取默认示例前置文本
        pre_prompt = configurator.build_userExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)
        fol_prompt = configurator.build_modelExamplePrefix (configurator.cn_prompt_toggle,configurator.cot_toggle,configurator.source_language,configurator.target_language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot)

        #构建默认示例
        original_exmaple,translation_example =  configurator.build_translation_sample(source_text_dict,configurator.source_language,configurator.target_language)
        if original_exmaple and translation_example:
                
            the_original_exmaple =  {"role": "USER","message":(f'{pre_prompt}```json\n{original_exmaple}\n```') }
            the_translation_example = {"role": "CHATBOT", "message": (f'{fol_prompt}```json\n{translation_example}\n```') }

            messages.append(the_original_exmaple)
            messages.append(the_translation_example)
            print("[INFO]  已添加格式原文示例：\n",original_exmaple)
            print("[INFO]  已添加格式译文示例：\n",translation_example, '\n')


        #如果翻译示例开关打开
        if configurator.translation_example_switch :
            original_exmaple_3,translation_example_3 = configurator.build_translation_example ()
            if original_exmaple_3 and translation_example_3:
                the_original_exmaple =  {"role": "USER","message":original_exmaple_3 }
                the_translation_example = {"role": "CHATBOT", "message": translation_example_3}
                messages.append(the_original_exmaple)
                messages.append(the_translation_example)
                print("[INFO]  已添加用户原文示例：\n",original_exmaple_3)
                print("[INFO]  已添加用户译文示例：\n",translation_example_3, '\n')


        # 如果开启了保留换行符功能
        if configurator.preserve_line_breaks_toggle:
            print("[INFO] 你开启了保留换行符功能，正在进行替换", '\n')
            source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")


        #如果开启译前替换字典功能，则根据用户字典进行替换
        if configurator.pre_translation_switch :
            print("[INFO] 你开启了译前替换字典功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果加上文(cohere的模型注意力更多会注意在最新的消息，而导致过分关注最新消息的格式)
        previous = ""
        if configurator.pre_line_counts and previous_list :
            previous = configurator.build_pre_text(previous_list,configurator.cn_prompt_toggle)
            if previous:
                #system_prompt += previous
                pass 
                #print("[INFO]  已添加上文：\n",previous)


        # 获取提问时的前置文本
        pre_prompt = configurator.build_userQueryPrefix (configurator.cn_prompt_toggle,configurator.cot_toggle)


        #构建用户信息
        source_text_str = json.dumps(source_text_dict, ensure_ascii=False)   
        source_text_str = f'{previous}\n{pre_prompt}```json\n{source_text_str}\n```'


        return messages,source_text_str,system_prompt


    # 并发接口请求（Cohere）
    def Concurrent_Request_cohere(self):

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
                print("\033[1;33mWarning:\033[0m 未能获取文本，该线程为多余线程，取消任务")
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
                print("\033[1;31mError:\033[0m 该条消息总tokens数大于单条消息最大数量" )
                print("\033[1;31mError:\033[0m 该条消息取消任务，进行拆分翻译" )
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
                    print("\033[1;31mError:\033[0m 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print(f"[INFO] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[INFO] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取apikey
                    cohere_apikey =  configurator.get_apikey()
                    # 获取AI的参数设置
                    temperature= configurator.get_cohere_parameters()
                    # 创建anthropic客户端
                    client = cohere.Client(api_key=cohere_apikey,base_url=configurator.base_url)
                    # 发送对话请求
                    try:
                        response = client.chat(
                            model= configurator.model_type,
                            preamble= system_prompt,
                            message = source_text_str ,
                            chat_history = messages,
                            temperature=temperature
                            )



                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
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
                    except Exception as e:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = 0
                        #completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception as e:
                        completion_tokens_used = 0



                    # 尝试提取回复的文本内容
                    try:
                        response_content = response.text 
                    #抛出错误信息
                    except Exception as e:
                        print("\033[1;31mError:\033[0m 提取文本时出现问题！！！运行错误信息如下")
                        print(f"Error: {e}\n")
                        print("接口返回的错误信息如下")
                        print(response)
                        #处理完毕，再次进行请求
                        
                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
                            break
                        continue


                    print('\n' )
                    print("[INFO] 已成功接受到AI的回复-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

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

                        #如果开启译后替换字典功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[INFO] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model_type)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.Output_Folder, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress

                        print(f"\n--------------------------------------------------------------------------------------")
                        print(f"\n\033[1;32mSuccess:\033[0m AI回复内容检查通过！！！已翻译完成{progress}%")
                        print(f"\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:

                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("\033[1;33mWarning:\033[0m AI回复内容存在问题:",error_content,"\n")

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("\033[1;33mWarning:\033[0m 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("\033[1;33mWarning:\033[0m 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("\033[1;31mError:\033[0m 子线程运行出现问题！错误信息如下")
            print(f"Error: {e}\n")
            return



    # 整理发送内容（sakura）
    def organize_send_content_sakura(self,source_text_dict, previous_list):
        #创建message列表，用于发送
        messages = []

        #构建系统提示词
        if configurator.model_type != "Sakura-v0.9":
            system_prompt ={"role": "system","content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。" }
        else:
            system_prompt ={"role": "system","content": "你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。" }
        messages.append(system_prompt)


        # 开启了保留换行符功能
        print("[INFO] 正在使用SakuraLLM，将替换换行符为特殊符号", '\n')
        source_text_dict = Cache_Manager.replace_special_characters(self,source_text_dict, "替换")

        #如果开启译前替换字典功能
        if configurator.pre_translation_switch :
            print("[INFO] 你开启了译前替换字典功能，正在进行替换", '\n')
            source_text_dict = configurator.replace_before_translation(source_text_dict)



        #如果开启了译时提示字典功能
        gpt_dict_raw_text = "" # 空变量
        if (configurator.prompt_dictionary_switch) and (configurator.model_type != "Sakura-v0.9"):
            glossary_prompt = configurator.build_glossary_prompt_sakura(source_text_dict)
            if glossary_prompt:
                gpt_dict_text_list = []
                for gpt in glossary_prompt:
                    src = gpt['src']
                    dst = gpt['dst']
                    info = gpt['info'] if "info" in gpt.keys() else None
                    if info:
                        single = f"{src}->{dst} #{info}"
                    else:
                        single = f"{src}->{dst}"
                    gpt_dict_text_list.append(single)

                gpt_dict_raw_text = "\n".join(gpt_dict_text_list)
                print("[INFO]  检测到请求的原文中含有提示字典内容")
                print("[INFO]  术语表:\n",gpt_dict_raw_text,"\n")

 
        #将原文本字典转换成raw格式的字符串
        source_text_str_raw = self.convert_dict_to_raw_str(source_text_dict)

        # 处理全角数字
        source_text_str_raw = self.convert_fullwidth_to_halfwidth(source_text_str_raw)

        #构建user_prompt
        if gpt_dict_raw_text: # 有字典时
            user_prompt = "根据以下术语表（可以为空）：\n" + gpt_dict_raw_text + "\n" + "将下面的日文文本根据对应关系和备注翻译成中文：" + source_text_str_raw

        else: # 空字典时
            if configurator.model_type != "Sakura-v0.9": 
                user_prompt = "将下面的日文文本翻译成中文：" + source_text_str_raw
            else:
                user_prompt = "将下面的日文文本翻译成中文：" + source_text_str_raw

        Original_text = {"role":"user","content": user_prompt}


        messages.append(Original_text)



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
                # 减去系统提示词预计的tokens
                if configurator.tokens_limit - 90 > 0:
                    tokens_limit = configurator.tokens_limit - 90
                else:
                    tokens_limit = configurator.tokens_limit

                source_text_list, previous_list = Cache_Manager.process_dictionary_data_tokens(self,tokens_limit, configurator.cache_list,configurator.pre_line_counts)  
            else:
                source_text_list, previous_list = Cache_Manager.process_dictionary_data_lines(self,configurator.lines_limit, configurator.cache_list,configurator.pre_line_counts)    
            configurator.lock1.release()  # 释放锁

            # 检查一下是否有发送内容
            if source_text_list == []:
                print("\033[1;33mWarning:\033[0m 未能获取文本，该线程为多余线程，取消任务")
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
                print("\033[1;33mWarning:\033[0m 该条消息总tokens数大于单条消息最大数量" )
                print("\033[1;33mWarning:\033[0m 该条消息取消任务，进行拆分翻译" )
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
                    print("\033[1;31mError:\033[0m 子线程执行任务已经超时，将暂时取消本次任务")
                    break


                # 检查是否符合速率限制---------------------------------
                if request_limiter.RPM_and_TPM_limit(request_tokens_consume):


                    # 获取当前线程的ID
                    thread_id = threading.get_ident()
                    # 将线程ID简化为4个数字，这里使用对10000取模的方式
                    simplified_thread_id = thread_id % 10000
                    print(f"[INFO] 已发送请求,正在等待AI回复中-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 文本行数: {row_count}, tokens数: {request_tokens_consume}" )
                    print(f"[INFO] 当前发送的原文文本: \n{source_text_str}")

                    # ——————————————————————————————————————————发送会话请求——————————————————————————————————————————
                    # 记录开始请求时间
                    Start_request_time = time.time()

                    # 获取AI的参数设置
                    temperature,top_p,frequency_penalty= configurator.get_sakura_parameters()
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
                            model = configurator.model_type,
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
                        print("\033[1;31mError:\033[0m 进行请求时出现问题！！！错误信息如下")
                        print(f"Error: {e}\n")

                        #请求错误计次
                        request_errors_count = request_errors_count + 1
                        #如果错误次数过多，就取消任务
                        if request_errors_count >= 4 :
                            print("\033[1;31m[ERROR]\033[0m 请求发生错误次数过多，该线程取消任务！")
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
                    except Exception as e:
                        prompt_tokens_used = 0
                    try:
                        completion_tokens_used = int(response.usage.completion_tokens) #本次回复花费的tokens
                    except Exception as e:
                        completion_tokens_used = 0



                    # 提取回复的文本内容
                    response_content = response.choices[0].message.content 


                    print('\n' )
                    print("[INFO] 已成功接受到AI的回复-----------------------")
                    print(f"[INFO] 线程 ID: {simplified_thread_id:04d}, 等待时间: {Request_consumption_time} 秒")
                    print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

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

                        #如果开启译后替换字典功能，则根据用户字典进行替换
                        if configurator.post_translation_switch :
                            print("[INFO] 你开启了译后修正功能，正在进行替换", '\n')
                            response_dict = configurator.replace_after_translation(response_dict)

                        # 如果原文是日语，则还原文本的首尾代码字符
                        if (configurator.source_language == "日语" and configurator.text_clear_toggle):
                            response_dict = Cache_Manager.update_dictionary(self,response_dict, process_info_list)

                        # 录入缓存文件
                        configurator.lock1.acquire()  # 获取锁
                        Cache_Manager.update_cache_data(self,configurator.cache_list, source_text_list, response_dict,configurator.model_type)
                        configurator.lock1.release()  # 释放锁


                        # 如果开启自动备份,则自动备份缓存文件
                        if configurator.auto_backup_toggle:
                            configurator.lock3.acquire()  # 获取锁

                            # 创建存储缓存文件的文件夹，如果路径不存在，创建文件夹
                            output_path = os.path.join(configurator.Output_Folder, "cache")
                            os.makedirs(output_path, exist_ok=True)
                            # 输出备份
                            File_Outputter.output_cache_file(self,configurator.cache_list,output_path)
                            configurator.lock3.release()  # 释放锁

                        
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(1,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译成功",1)

                        # 获取翻译进度
                        progress = user_interface_prompter.progress                    

                        print(f"\n--------------------------------------------------------------------------------------")
                        print(f"\n\033[1;32mSuccess:\033[0m AI回复内容检查通过！！！已翻译完成{progress}%")
                        print(f"\n--------------------------------------------------------------------------------------\n")
                        configurator.lock2.release()  # 释放锁


                        break
                

                    # 如果出现回复错误
                    else:

                        # 更改UI界面信息
                        configurator.lock2.acquire()  # 获取锁

                        # 更新翻译界面数据
                        user_interface_prompter.update_data(0,row_count,prompt_tokens_used,completion_tokens_used)

                        # 更改UI界面信息,注意，传入的数值类型分布是字符型与整数型，小心浮点型混入
                        user_interface_prompter.signal.emit("更新翻译界面数据","翻译失败",1)

                        configurator.lock2.release()  # 释放锁

                        print("\033[1;33mWarning:\033[0m AI回复内容存在问题:",error_content,"\n")

                        # 检查一下是不是模型退化
                        if error_content == "AI回复内容出现高频词,并重新翻译":
                            print("\033[1;33mWarning:\033[0m 下次请求将修改参数，回避高频词输出","\n")
                            model_degradation = True

                        #错误回复计次
                        Wrong_answer_count = Wrong_answer_count + 1
                        print("\033[1;33mWarning:\033[0m 错误重新翻译最大次数限制:",configurator.retry_count_limit,"剩余可重试次数:",(configurator.retry_count_limit + 1 - Wrong_answer_count),"到达次数限制后，该段文本将进行拆分翻译\n")
                        #检查回答错误次数，如果达到限制，则跳过该句翻译。
                        if Wrong_answer_count > configurator.retry_count_limit :
                            print("\033[1;33mWarning:\033[0m 错误回复重翻次数已经达限制,将该段文本进行拆分翻译！\n")    
                            break


                        #进行下一次循环              
                        continue

    #子线程抛出错误信息
        except Exception as e:
            print("\033[1;31mError:\033[0m 子线程运行出现问题！错误信息如下")
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


    # 将列表中的字符串中的全角数字转换为半角数字
    def convert_fullwidth_to_halfwidth(self,input_string):
        modified_string = ""
        for char in input_string:
            if '０' <= char <= '９':  # 判断是否为全角数字
                modified_string += chr(ord(char) - ord('０') + ord('0'))  # 转换为半角数字
            else:
                modified_string += char

        return modified_string


# UI交互器
class User_Interface_Prompter(QObject):
    signal = pyqtSignal(str,str,int) #创建信号,并确定发送参数类型

    def __init__(self):
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
                self.stateTooltip = StateToolTip(" 正在进行翻译中，客官请耐心等待哦~~", "　　　当前任务开始于 " + datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S"), Main_Window)
                self.stateTooltip.move(510, 30) # 设定控件的出现位置，该位置是传入的Window窗口的位置
                self.stateTooltip.show()
                # 翻译状态改变
                Main_Window.Widget_start_translation.A_settings.running_status.setText("正在翻译中")


            elif input_str2 == "翻译暂停":
                print("\033[1;33mWarning:\033[0m 翻译任务已被暂停-----------------------","\n")
                self.stateTooltip.setContent('翻译已暂停')
                self.stateTooltip.setState(True)
                self.stateTooltip = None
                # 翻译状态改变
                Main_Window.Widget_start_translation.A_settings.running_status.setText("已暂停翻译")
                Main_Window.Widget_start_translation.A_settings.thread_count.setText("0")
                # 界面提示
                self.createSuccessInfoBar("翻译任务已全部暂停")

            elif input_str2 == "翻译取消":
                print("\033[1;33mWarning:\033[0m 翻译任务已被取消-----------------------","\n")
                self.stateTooltip.setContent('翻译已取消')
                self.stateTooltip.setState(True)
                self.stateTooltip = None
                # 界面提示
                self.createSuccessInfoBar("翻译任务已全部取消")

                # 翻译状态改变
                Main_Window.Widget_start_translation.A_settings.running_status.setText("已取消翻译")
                #重置翻译界面数据
                Main_Window.Widget_start_translation.A_settings.translation_project.setText("无")
                Main_Window.Widget_start_translation.A_settings.project_id.setText("无")
                Main_Window.Widget_start_translation.A_settings.total_text_line_count.setText("无")
                Main_Window.Widget_start_translation.A_settings.translated_line_count.setText("无")
                Main_Window.Widget_start_translation.A_settings.tokens_spent.setText("无")
                Main_Window.Widget_start_translation.A_settings.amount_spent.setText("无")
                Main_Window.Widget_start_translation.A_settings.thread_count.setText("无")
                Main_Window.Widget_start_translation.A_settings.translation_speed_token.setText("无")
                Main_Window.Widget_start_translation.A_settings.translation_speed_line.setText("无")
                Main_Window.Widget_start_translation.A_settings.progressRing.setValue(0)


            elif input_str2 == "翻译完成":
                self.stateTooltip.setContent('已经翻译完成啦 😆')
                self.stateTooltip.setState(True)
                self.stateTooltip = None

                # 翻译状态改变
                Main_Window.Widget_start_translation.A_settings.running_status.setText("翻译已完成")
                # 子线程数为0
                Main_Window.Widget_start_translation.A_settings.thread_count.setText("0")
                #隐藏继续翻译按钮
                Main_Window.Widget_start_translation.A_settings.primaryButton_continue_translation.hide()
                #隐藏暂停翻译按钮
                Main_Window.Widget_start_translation.A_settings.primaryButton_pause_translation.hide()
                #显示开始翻译按钮
                Main_Window.Widget_start_translation.A_settings.primaryButton_start_translation.show()

        elif input_str1 == "运行状态改变":
            # 运行状态改变
            Main_Window.Widget_start_translation.A_settings.running_status.setText(input_str2)


        elif input_str1 == "接口测试结果":
            if input_str2 == "测试成功":
                self.createSuccessInfoBar("全部Apikey请求测试成功")
            else:
                self.createErrorInfoBar("存在Apikey请求测试失败")


        elif input_str1 == "初始化翻译界面数据":
            # 更新翻译项目信息
            translation_project = configurator.translation_project
            Main_Window.Widget_start_translation.A_settings.translation_project.setText(translation_project)

            # 更新项目ID信息
            Main_Window.Widget_start_translation.A_settings.project_id.setText(input_str2)

            # 更新需要翻译的文本行数信息
            self.total_text_line_count = iunput_int1 #存储总文本行数
            Main_Window.Widget_start_translation.A_settings.total_text_line_count.setText(str(self.total_text_line_count))

            # 翻译状态改变
            Main_Window.Widget_start_translation.A_settings.running_status.setText("正在翻译中")

            # 获取当前所有存活的线程
            alive_threads = threading.enumerate()
            self.num_worker_threads = len(alive_threads) - 2  # 减去主线程与一个子线程
            Main_Window.Widget_start_translation.A_settings.thread_count.setText(str(self.num_worker_threads))

            # 其他信息设置为0
            Main_Window.Widget_start_translation.A_settings.translated_line_count.setText("0")
            Main_Window.Widget_start_translation.A_settings.tokens_spent.setText("0")
            Main_Window.Widget_start_translation.A_settings.amount_spent.setText("0")
            Main_Window.Widget_start_translation.A_settings.translation_speed_token.setText("0")
            Main_Window.Widget_start_translation.A_settings.translation_speed_line.setText("0")
            Main_Window.Widget_start_translation.A_settings.progressRing.setValue(0)

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
            Main_Window.Widget_start_translation.A_settings.translation_project.setText("无")
            Main_Window.Widget_start_translation.A_settings.project_id.setText("无")
            Main_Window.Widget_start_translation.A_settings.total_text_line_count.setText("无")
            Main_Window.Widget_start_translation.A_settings.translated_line_count.setText("无")
            Main_Window.Widget_start_translation.A_settings.translation_speed_token.setText("无")
            Main_Window.Widget_start_translation.A_settings.translation_speed_line.setText("无")
            Main_Window.Widget_start_translation.A_settings.tokens_spent.setText("无")
            Main_Window.Widget_start_translation.A_settings.amount_spent.setText("无")
            Main_Window.Widget_start_translation.A_settings.thread_count.setText("无")
            Main_Window.Widget_start_translation.A_settings.progressRing.setValue(0)


        elif input_str1 == "更新翻译界面数据":
            elapsed_time_this_run = time.time() - self.translation_start_time

            Main_Window.Widget_start_translation.A_settings.translated_line_count.setText(str(self.translated_line_count))

            Main_Window.Widget_start_translation.A_settings.translation_speed_token.setText(f"{self.translated_token_count_this_run / elapsed_time_this_run:.2f}")
            Main_Window.Widget_start_translation.A_settings.translation_speed_line.setText(f"{self.translated_line_count_this_run / elapsed_time_this_run:.2f}")

            Main_Window.Widget_start_translation.A_settings.tokens_spent.setText(str(self.tokens_spent))

            Main_Window.Widget_start_translation.A_settings.amount_spent.setText(str(self.amount_spent))

            Main_Window.Widget_start_translation.A_settings.thread_count.setText(str(self.num_worker_threads))

            progress = int(round(self.progress, 0))
            Main_Window.Widget_start_translation.A_settings.progressRing.setValue(progress)

    
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
            parent=Main_Window
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
            parent=Main_Window
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
            parent=Main_Window
            )


    #读写配置文件config.json函数
    def read_write_config(self,mode,resource_dir):

        if mode == "write":
            # 存储配置信息的字典
            config_dict = {}
            
            #获取OpenAI官方账号界面
            config_dict["openai_account_type"] = Main_Window.Widget_Openai.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["openai_model_type"] =  Main_Window.Widget_Openai.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["openai_API_key_str"] = Main_Window.Widget_Openai.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["openai_proxy_port"] = Main_Window.Widget_Openai.LineEdit_proxy_port.text()            #获取代理端口
            

            #Google官方账号界面
            config_dict["google_account_type"] = Main_Window.Widget_Google.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["google_model_type"] =  Main_Window.Widget_Google.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["google_API_key_str"] = Main_Window.Widget_Google.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["google_proxy_port"] = Main_Window.Widget_Google.LineEdit_proxy_port.text()            #获取代理端口

            #Anthropic官方账号界面
            config_dict["anthropic_account_type"] = Main_Window.Widget_Anthropic.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["anthropic_model_type"] =  Main_Window.Widget_Anthropic.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["anthropic_API_key_str"] = Main_Window.Widget_Anthropic.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["anthropic_proxy_port"] = Main_Window.Widget_Anthropic.LineEdit_proxy_port.text()            #获取代理端口


            #获取Cohere官方账号界面
            config_dict["cohere_account_type"] = Main_Window.Widget_Cohere.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["cohere_model_type"] =  Main_Window.Widget_Cohere.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["cohere_API_key_str"] = Main_Window.Widget_Cohere.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["cohere_proxy_port"] = Main_Window.Widget_Cohere.LineEdit_proxy_port.text()            #获取代理端口


            #获取moonshot官方账号界面
            config_dict["moonshot_account_type"] = Main_Window.Widget_Moonshot.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["moonshot_model_type"] =  Main_Window.Widget_Moonshot.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["moonshot_API_key_str"] = Main_Window.Widget_Moonshot.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["moonshot_proxy_port"] = Main_Window.Widget_Moonshot.LineEdit_proxy_port.text()            #获取代理端口

            #获取deepseek官方账号界面
            config_dict["deepseek_model_type"] =  Main_Window.Widget_Deepseek.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["deepseek_API_key_str"] = Main_Window.Widget_Deepseek.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["deepseek_proxy_port"] = Main_Window.Widget_Deepseek.LineEdit_proxy_port.text()            #获取代理端口

            #获取dashscope官方账号界面
            config_dict["dashscope_model_type"] =  Main_Window.Widget_Dashscope.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["dashscope_API_key_str"] = Main_Window.Widget_Dashscope.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["dashscope_proxy_port"] = Main_Window.Widget_Dashscope.LineEdit_proxy_port.text()            #获取代理端口

            
            #获取零一万物官方账号界面
            config_dict["yi_account_type"] = Main_Window.Widget_Yi.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["yi_model_type"] =  Main_Window.Widget_Yi.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["yi_API_key_str"] = Main_Window.Widget_Yi.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["yi_proxy_port"] = Main_Window.Widget_Yi.LineEdit_proxy_port.text()            #获取代理端口
            


            #智谱官方界面
            config_dict["zhipu_account_type"] = Main_Window.Widget_ZhiPu.comboBox_account_type.currentText()      #获取账号类型下拉框当前选中选项的值
            config_dict["zhipu_model_type"] =  Main_Window.Widget_ZhiPu.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["zhipu_API_key_str"] = Main_Window.Widget_ZhiPu.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["zhipu_proxy_port"] = Main_Window.Widget_ZhiPu.LineEdit_proxy_port.text()            #获取代理端口


            #获取火山账号界面
            config_dict["volcengine_access_point"] = Main_Window.Widget_Volcengine.A_settings.LineEdit_access_point.text()                  #获取推理接入点
            config_dict["volcengine_API_key_str"] = Main_Window.Widget_Volcengine.A_settings.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["volcengine_proxy_port"] = Main_Window.Widget_Volcengine.A_settings.LineEdit_proxy_port.text()            #获取代理端口
            config_dict["volcengine_tokens_limit"] = Main_Window.Widget_Volcengine.B_settings.spinBox_tokens.value()               #获取tokens限制值
            config_dict["volcengine_rpm_limit"] = Main_Window.Widget_Volcengine.B_settings.spinBox_RPM.value()               #获取rpm限制值
            config_dict["volcengine_tpm_limit"] = Main_Window.Widget_Volcengine.B_settings.spinBox_TPM.value()               #获取tpm限制值
            config_dict["volcengine_input_pricing"] = Main_Window.Widget_Volcengine.B_settings.spinBox_input_pricing.value()               #获取输入价格
            config_dict["volcengine_output_pricing"] = Main_Window.Widget_Volcengine.B_settings.spinBox_output_pricing.value()               #获取输出价格



            #获取代理账号设置界面
            config_dict["op_relay_address"] = Main_Window.Widget_Proxy.A_settings.LineEdit_relay_address.text()                  #获取请求地址
            config_dict["op_proxy_platform"] = Main_Window.Widget_Proxy.A_settings.comboBox_proxy_platform.currentText()       # 获取代理平台
            config_dict["op_model_type_openai"] =  Main_Window.Widget_Proxy.A_settings.comboBox_model_openai.currentText()      #获取openai的模型类型下拉框当前选中选项的值
            config_dict["op_model_type_anthropic"] =  Main_Window.Widget_Proxy.A_settings.comboBox_model_anthropic.currentText()      #获取anthropic的模型类型下拉框当前选中选项的值        
            config_dict["op_API_key_str"] = Main_Window.Widget_Proxy.A_settings.TextEdit_apikey.toPlainText()        #获取apikey输入值
            config_dict["op_proxy_port"]  = Main_Window.Widget_Proxy.A_settings.LineEdit_proxy_port.text()               #获取代理端口
            config_dict["op_auto_complete"]  = Main_Window.Widget_Proxy.A_settings.SwitchButton_auto_complete.isChecked()              #获取自动补全开关
            config_dict["op_tokens_limit"] = Main_Window.Widget_Proxy.B_settings.spinBox_tokens.value()               #获取tokens限制值
            config_dict["op_rpm_limit"] = Main_Window.Widget_Proxy.B_settings.spinBox_RPM.value()               #获取rpm限制值
            config_dict["op_tpm_limit"] = Main_Window.Widget_Proxy.B_settings.spinBox_TPM.value()               #获取tpm限制值
            config_dict["op_input_pricing"] = Main_Window.Widget_Proxy.B_settings.spinBox_input_pricing.value()               #获取输入价格
            config_dict["op_output_pricing"] = Main_Window.Widget_Proxy.B_settings.spinBox_output_pricing.value()               #获取输出价格


            # 获取额外代理平台配置信息
            config_dict["additional_platform_count"] = configurator.additional_platform_count
            config_dict["additional_platform_dict"] = configurator.additional_platform_dict
            for key, value in configurator.additional_platform_dict.items():
                object_Name = key
                config_dict[object_Name] = {} # 创建次级字典
                config_dict[object_Name]["op_platform_name"] = value 
                config_dict[object_Name]["op_relay_address"] = configurator.instances_information[object_Name].A_settings.LineEdit_relay_address.text()                  #获取请求地址
                config_dict[object_Name]["op_proxy_platform"] = configurator.instances_information[object_Name].A_settings.comboBox_proxy_platform.currentText()       # 获取代理平台
                config_dict[object_Name]["op_model_type_openai"] =  configurator.instances_information[object_Name].A_settings.comboBox_model_openai.currentText()      #获取openai的模型类型下拉框当前选中选项的值
                config_dict[object_Name]["op_model_type_anthropic"] =  configurator.instances_information[object_Name].A_settings.comboBox_model_anthropic.currentText()      #获取anthropic的模型类型下拉框当前选中选项的值        
                config_dict[object_Name]["op_API_key_str"] = configurator.instances_information[object_Name].A_settings.TextEdit_apikey.toPlainText()        #获取apikey输入值
                config_dict[object_Name]["op_proxy_port"]  = configurator.instances_information[object_Name].A_settings.LineEdit_proxy_port.text()               #获取代理端口
                config_dict[object_Name]["op_auto_complete"] = configurator.instances_information[object_Name].A_settings.SwitchButton_auto_complete.isChecked()               #获取自动补全开关
                config_dict[object_Name]["op_tokens_limit"] = configurator.instances_information[object_Name].B_settings.spinBox_tokens.value()               #获取tokens限制值
                config_dict[object_Name]["op_rpm_limit"] = configurator.instances_information[object_Name].B_settings.spinBox_RPM.value()               #获取rpm限制值
                config_dict[object_Name]["op_tpm_limit"] = configurator.instances_information[object_Name].B_settings.spinBox_TPM.value()               #获取tpm限制值
                config_dict[object_Name]["op_input_pricing"] = configurator.instances_information[object_Name].B_settings.spinBox_input_pricing.value()               #获取输入价格
                config_dict[object_Name]["op_output_pricing"] = configurator.instances_information[object_Name].B_settings.spinBox_output_pricing.value()               #获取输出价格


            #Sakura界面
            config_dict["sakura_address"] = Main_Window.Widget_SakuraLLM.LineEdit_address.text()                  #获取请求地址
            config_dict["sakura_model_type"] =  Main_Window.Widget_SakuraLLM.comboBox_model.currentText()      #获取模型类型下拉框当前选中选项的值
            config_dict["sakura_proxy_port"] = Main_Window.Widget_SakuraLLM.LineEdit_proxy_port.text()            #获取代理端口


            #翻译设置基础设置界面
            config_dict["translation_project"] = Main_Window.Widget_translation_settings_A.comboBox_translation_project.currentText()
            config_dict["translation_platform"] = Main_Window.Widget_translation_settings_A.comboBox_translation_platform.currentText()
            config_dict["source_language"] = Main_Window.Widget_translation_settings_A.comboBox_source_text.currentText()
            config_dict["target_language"] = Main_Window.Widget_translation_settings_A.comboBox_translated_text.currentText()
            config_dict["label_input_path"] = Main_Window.Widget_translation_settings_A.label_input_path.text()
            config_dict["label_output_path"] = Main_Window.Widget_translation_settings_A.label_output_path.text()

            #翻译设置进阶设置界面
            config_dict["lines_limit_switch"] = Main_Window.Widget_translation_settings_B1.checkBox_lines_limit_switch.isChecked()            
            config_dict["lines_limit"] = Main_Window.Widget_translation_settings_B1.spinBox_lines_limit.value()          
            config_dict["tokens_limit_switch"] = Main_Window.Widget_translation_settings_B1.checkBox_tokens_limit_switch.isChecked()           
            config_dict["tokens_limit"] = Main_Window.Widget_translation_settings_B1.spinBox_tokens_limit.value()            #获取tokens限制
            config_dict["pre_line_counts"] = Main_Window.Widget_translation_settings_B1.spinBox_pre_lines.value()     # 获取上文文本行数设置
            config_dict["user_thread_counts"] = Main_Window.Widget_translation_settings_B1.spinBox_thread_count.value() # 获取线程数设置
            config_dict["retry_count_limit"] =  Main_Window.Widget_translation_settings_B1.spinBox_retry_count_limit.value()     # 获取重翻次数限制  
            config_dict["round_limit"] =  Main_Window.Widget_translation_settings_B1.spinBox_round_limit.value() # 获取轮数限制
            config_dict["cot_toggle"] =  Main_Window.Widget_translation_settings_B2.SwitchButton_cot_toggle.isChecked()   # 获取cot开关
            config_dict["cn_prompt_toggle"] =  Main_Window.Widget_translation_settings_B2.SwitchButton_cn_prompt_toggle.isChecked()   # 获取中文提示词开关
            config_dict["preserve_line_breaks_toggle"] =  Main_Window.Widget_translation_settings_B2.SwitchButton_line_breaks.isChecked() # 获取保留换行符开关  
            config_dict["response_conversion_toggle"] =  Main_Window.Widget_translation_settings_B2.SwitchButton_conversion_toggle.isChecked()   # 获取简繁转换开关
            config_dict["opencc_preset"] = Main_Window.Widget_translation_settings_B2.comboBox_opencc_preset.currentText()
            config_dict["text_clear_toggle"] =  Main_Window.Widget_translation_settings_B2.SwitchButton_clear.isChecked() # 获取文本处理开关

            #翻译设置的检查设置页面
            Model_Degradation_Check =  Main_Window.Widget_translation_settings_B3.SwitchButton_check1.isChecked() 
            Residual_Original_Text_Check =  Main_Window.Widget_translation_settings_B3.SwitchButton_check2.isChecked()   
            Return_to_Original_Text_Check =  Main_Window.Widget_translation_settings_B3.SwitchButton_check3.isChecked() 
            config_dict["reply_check_switch"] = {"Model Degradation Check":Model_Degradation_Check,"Residual Original Text Check":Residual_Original_Text_Check,"Return to Original Text Check":Return_to_Original_Text_Check}


            #翻译设置混合反应设置界面
            config_dict["translation_mixing_toggle"] =  Main_Window.Widget_translation_settings_C.SwitchButton_mixed_translation.isChecked() # 获取混合翻译开关
            config_dict["mixed_translation_settings"] = {}
            config_dict["mixed_translation_settings"]["translation_platform_1"] = Main_Window.Widget_translation_settings_C.SettingCard_A.translationPlatform_comboBox.currentText()  # 获取首轮翻译平台设置


            config_dict["mixed_translation_settings"]["translation_platform_2"] = Main_Window.Widget_translation_settings_C.SettingCard_B.translationPlatform_comboBox.currentText()  # 获取首轮翻译平台设置
            config_dict["mixed_translation_settings"]["customModel_siwtch_2"] = Main_Window.Widget_translation_settings_C.SettingCard_B.customModel_Button.isChecked()  
            config_dict["mixed_translation_settings"]["model_type_2"] = Main_Window.Widget_translation_settings_C.SettingCard_B.model_type.text()
            config_dict["mixed_translation_settings"]["split_switch_2"] = Main_Window.Widget_translation_settings_C.SettingCard_B.textSplitting_Button.isChecked()   

            config_dict["mixed_translation_settings"]["translation_platform_3"] = Main_Window.Widget_translation_settings_C.SettingCard_C.translationPlatform_comboBox.currentText()  # 获取首轮翻译平台设置
            config_dict["mixed_translation_settings"]["customModel_siwtch_3"] = Main_Window.Widget_translation_settings_C.SettingCard_C.customModel_Button.isChecked()  
            config_dict["mixed_translation_settings"]["model_type_3"] = Main_Window.Widget_translation_settings_C.SettingCard_C.model_type.text()  
            config_dict["mixed_translation_settings"]["split_switch_3"] = Main_Window.Widget_translation_settings_C.SettingCard_C.textSplitting_Button.isChecked()  


            #开始翻译的备份设置界面
            config_dict["auto_backup_toggle"] =  Main_Window.Widget_start_translation.B_settings.checkBox_switch.isChecked() # 获取备份设置开关




            #获取提示字典界面
            config_dict["prompt_dict_switch"] = Main_Window.Widget_prompt_dict.checkBox2.isChecked() #获取译时提示开关状态
            User_Dictionary2 = {}
            for row in range(Main_Window.Widget_prompt_dict.tableView.rowCount() - 1):
                key_item = Main_Window.Widget_prompt_dict.tableView.item(row, 0)
                value_item = Main_Window.Widget_prompt_dict.tableView.item(row, 1)
                info_item = Main_Window.Widget_prompt_dict.tableView.item(row, 2)
                if key_item and value_item:
                    key = key_item.data(Qt.DisplayRole)
                    value = value_item.data(Qt.DisplayRole)
                    # 检查一下是不是空值
                    if info_item:
                        info = info_item.data(Qt.DisplayRole)
                        User_Dictionary2[key] = {"translation": value, "info": info}
                    else:
                        # 如果info项为None，可以选择不添加到字典中或者添加一个默认值
                        User_Dictionary2[key] = {"translation": value, "info": None}
            config_dict["User_Dictionary2"] = User_Dictionary2



            #获取译前替换字典界面
            config_dict["Replace_before_translation"] =  Main_Window.Widget_replace_dict.A_settings.checkBox1.isChecked()#获取译前替换开关状态
            User_Dictionary1 = {}
            for row in range(Main_Window.Widget_replace_dict.A_settings.tableView.rowCount() - 1):
                key_item = Main_Window.Widget_replace_dict.A_settings.tableView.item(row, 0)
                value_item = Main_Window.Widget_replace_dict.A_settings.tableView.item(row, 1)
                if key_item and value_item:
                    key = key_item.data(Qt.DisplayRole)
                    value = value_item.data(Qt.DisplayRole)
                    User_Dictionary1[key] = value
            config_dict["User_Dictionary1"] = User_Dictionary1


            #获取译后替换字典界面
            config_dict["Replace_after_translation"] =  Main_Window.Widget_replace_dict.B_settings.checkBox1.isChecked()#获取译后替换开关状态
            User_Dictionary3 = {}
            for row in range(Main_Window.Widget_replace_dict.B_settings.tableView.rowCount() - 1):
                key_item = Main_Window.Widget_replace_dict.B_settings.tableView.item(row, 0)
                value_item = Main_Window.Widget_replace_dict.B_settings.tableView.item(row, 1)
                if key_item and value_item:
                    key = key_item.data(Qt.DisplayRole)
                    value = value_item.data(Qt.DisplayRole)
                    User_Dictionary3[key] = value
            config_dict["User_Dictionary3"] = User_Dictionary3




            #获取实时设置界面(openai)
            config_dict["OpenAI_parameter_adjustment"] = Main_Window.Widget_tune_openai.checkBox.isChecked()           #获取开关设置
            config_dict["OpenAI_Temperature"] = Main_Window.Widget_tune_openai.slider1.value()           #获取OpenAI温度
            config_dict["OpenAI_top_p"] = Main_Window.Widget_tune_openai.slider2.value()                 #获取OpenAI top_p
            config_dict["OpenAI_presence_penalty"] = Main_Window.Widget_tune_openai.slider3.value()      #获取OpenAI top_k
            config_dict["OpenAI_frequency_penalty"] = Main_Window.Widget_tune_openai.slider4.value()    #获取OpenAI repetition_penalty

            #获取实时设置界面(anthropic)
            config_dict["Anthropic_parameter_adjustment"] = Main_Window.Widget_tune_anthropic.checkBox.isChecked()           #获取开关设置
            config_dict["Anthropic_Temperature"] = Main_Window.Widget_tune_anthropic.slider1.value()           #获取anthropic 温度

            #获取实时设置界面(google)
            config_dict["Google_parameter_adjustment"] = Main_Window.Widget_tune_google.checkBox.isChecked()           #获取开关设置
            config_dict["Google_Temperature"] = Main_Window.Widget_tune_google.slider1.value()           #获取google 温度

            #获取实时设置界面(cohere)
            config_dict["Cohere_parameter_adjustment"] = Main_Window.Widget_tune_cohere.checkBox.isChecked()           #获取开关设置
            config_dict["Cohere_Temperature"] = Main_Window.Widget_tune_cohere.slider1.value()           #获取cohere 温度

            #获取实时设置界面(sakura)
            config_dict["Sakura_parameter_adjustment"] = Main_Window.Widget_tune_sakura.checkBox.isChecked()           #获取开关设置
            config_dict["Sakura_Temperature"] = Main_Window.Widget_tune_sakura.slider1.value()           #获取sakura温度
            config_dict["Sakura_top_p"] = Main_Window.Widget_tune_sakura.slider2.value()
            config_dict["Sakura_frequency_penalty"] = Main_Window.Widget_tune_sakura.slider4.value()



            #获取提示书界面
            config_dict["system_prompt_switch"] = Main_Window.Widget_system_prompt.checkBox1.isChecked()   #获取自定义提示词开关状态
            config_dict["system_prompt_content"] = Main_Window.Widget_system_prompt.TextEdit1.toPlainText()        #获取自定义提示词输入值 
            config_dict["characterization_switch"] = Main_Window.Widget_characterization.checkBox1.isChecked() #获取角色设定开关状态
            characterization_dictionary = {}
            for row in range(Main_Window.Widget_characterization.tableView.rowCount() - 1):
                original_name = Main_Window.Widget_characterization.tableView.item(row, 0)
                translated_name = Main_Window.Widget_characterization.tableView.item(row, 1)
                character_attributes1 = Main_Window.Widget_characterization.tableView.item(row, 2)
                character_attributes2 = Main_Window.Widget_characterization.tableView.item(row, 3)
                character_attributes3 = Main_Window.Widget_characterization.tableView.item(row, 4)
                character_attributes4 = Main_Window.Widget_characterization.tableView.item(row, 5)
                character_attributes5 = Main_Window.Widget_characterization.tableView.item(row, 6)
                if original_name and translated_name:
                    original_name = original_name.data(Qt.DisplayRole)
                    translated_name = translated_name.data(Qt.DisplayRole)
                    base_dictionary = {"original_name": original_name, "translated_name": translated_name}
                    if character_attributes1:
                        base_dictionary["gender"] = character_attributes1.data(Qt.DisplayRole)
                    if character_attributes2:
                        base_dictionary["age"] = character_attributes2.data(Qt.DisplayRole)
                    if character_attributes3:
                        base_dictionary["personality"] = character_attributes3.data(Qt.DisplayRole)
                    if character_attributes4:
                        base_dictionary["speech_style"] = character_attributes4.data(Qt.DisplayRole)
                    if character_attributes5:
                        base_dictionary["additional_info"] = character_attributes5.data(Qt.DisplayRole)
                    characterization_dictionary[original_name] = base_dictionary
            config_dict["characterization_dictionary"] = characterization_dictionary

            config_dict["world_building_switch"] = Main_Window.Widget_world_building.checkBox1.isChecked()   #获取背景设定开关状态
            config_dict["world_building_content"] = Main_Window.Widget_world_building.TextEdit1.toPlainText()        #获取背景设定文本 
            config_dict["writing_style_switch"] = Main_Window.Widget_writing_style.checkBox1.isChecked()   #获取文风要求开关状态
            config_dict["writing_style_content"] = Main_Window.Widget_writing_style.TextEdit1.toPlainText()        #获取文风要求开关 

            config_dict["translation_example_switch"]= Main_Window.Widget_translation_example.checkBox1.isChecked()#获取添加翻译示例开关状态
            translation_example = {}
            for row in range(Main_Window.Widget_translation_example.tableView.rowCount() - 1):
                key_item = Main_Window.Widget_translation_example.tableView.item(row, 0)
                value_item = Main_Window.Widget_translation_example.tableView.item(row, 1)
                if key_item and value_item:
                    key = key_item.data(Qt.DisplayRole)
                    value = value_item.data(Qt.DisplayRole)
                    translation_example[key] = value
            config_dict["translation_example"] = translation_example



            #将所有的配置信息写入config.json文件中
            with open(os.path.join(resource_dir, "config.json"), "w", encoding="utf-8") as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=4)


        if mode == "read":
            #如果config.json在子文件夹resource中存在
            if os.path.exists(os.path.join(resource_dir, "config.json")):
                #读取config.json
                with open(os.path.join(resource_dir, "config.json"), "r", encoding="utf-8") as f:
                    config_dict = json.load(f)

                #将config.json中的值赋予到变量中,并set到界面上
                #OpenAI官方账号界面
                if "openai_account_type" in config_dict:
                    Main_Window.Widget_Openai.comboBox_account_type.setCurrentText(config_dict["openai_account_type"])
                if "openai_model_type" in config_dict:
                    # 获取配置文件中指定的模型类型
                    model_type = config_dict["openai_model_type"]
                    # 检查模型类型是否已经存在于下拉列表中
                    existing_index = Main_Window.Widget_Openai.comboBox_model.findText(model_type)
                    # 如果模型类型不存在，则添加到下拉列表中
                    if existing_index == -1:
                        Main_Window.Widget_Openai.comboBox_model.addItem(model_type)
                    # 设置当前文本为配置文件中指定的模型类型
                    Main_Window.Widget_Openai.comboBox_model.setCurrentText(model_type)
                if "openai_API_key_str" in config_dict:
                    Main_Window.Widget_Openai.TextEdit_apikey.setText(config_dict["openai_API_key_str"])
                if "openai_proxy_port" in config_dict:
                    Main_Window.Widget_Openai.LineEdit_proxy_port.setText(config_dict["openai_proxy_port"])

                #anthropic官方账号界面
                if "anthropic_account_type" in config_dict:
                    Main_Window.Widget_Anthropic.comboBox_account_type.setCurrentText(config_dict["anthropic_account_type"])
                if "anthropic_model_type" in config_dict:
                    model_type = config_dict["anthropic_model_type"]
                    existing_index = Main_Window.Widget_Anthropic.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Anthropic.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Anthropic.comboBox_model.setCurrentText(model_type)
                if "anthropic_API_key_str" in config_dict:
                    Main_Window.Widget_Anthropic.TextEdit_apikey.setText(config_dict["anthropic_API_key_str"])
                if "anthropic_proxy_port" in config_dict:
                    Main_Window.Widget_Anthropic.LineEdit_proxy_port.setText(config_dict["anthropic_proxy_port"])


                #google官方账号界面
                if "google_account_type" in config_dict:
                    Main_Window.Widget_Google.comboBox_account_type.setCurrentText(config_dict["google_account_type"])
                if "google_model_type" in config_dict:
                    model_type = config_dict["google_model_type"]
                    existing_index = Main_Window.Widget_Google.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Google.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Google.comboBox_model.setCurrentText(model_type)
                if "google_API_key_str" in config_dict:
                    Main_Window.Widget_Google.TextEdit_apikey.setText(config_dict["google_API_key_str"])
                if "google_proxy_port" in config_dict:
                    Main_Window.Widget_Google.LineEdit_proxy_port.setText(config_dict["google_proxy_port"])


                #Cohere官方账号界面
                if "cohere_account_type" in config_dict:
                    Main_Window.Widget_Cohere.comboBox_account_type.setCurrentText(config_dict["cohere_account_type"])
                if "cohere_model_type" in config_dict:
                    model_type = config_dict["cohere_model_type"]
                    existing_index = Main_Window.Widget_Cohere.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Cohere.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Cohere.comboBox_model.setCurrentText(model_type)
                if "cohere_API_key_str" in config_dict:
                    Main_Window.Widget_Cohere.TextEdit_apikey.setText(config_dict["cohere_API_key_str"])
                if "cohere_proxy_port" in config_dict:
                    Main_Window.Widget_Cohere.LineEdit_proxy_port.setText(config_dict["cohere_proxy_port"])

                #moonshot官方账号界面
                if "moonshot_account_type" in config_dict:
                    Main_Window.Widget_Moonshot.comboBox_account_type.setCurrentText(config_dict["moonshot_account_type"])
                if "moonshot_model_type" in config_dict:
                    model_type = config_dict["moonshot_model_type"]
                    existing_index = Main_Window.Widget_Moonshot.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Moonshot.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Moonshot.comboBox_model.setCurrentText(model_type)
                if "moonshot_API_key_str" in config_dict:
                    Main_Window.Widget_Moonshot.TextEdit_apikey.setText(config_dict["moonshot_API_key_str"])
                if "moonshot_proxy_port" in config_dict:
                    Main_Window.Widget_Moonshot.LineEdit_proxy_port.setText(config_dict["moonshot_proxy_port"])

                #deepseek官方账号界面
                if "deepseek_model_type" in config_dict:
                    model_type = config_dict["deepseek_model_type"]
                    existing_index = Main_Window.Widget_Deepseek.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Deepseek.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Deepseek.comboBox_model.setCurrentText(model_type)
                if "deepseek_API_key_str" in config_dict:
                    Main_Window.Widget_Deepseek.TextEdit_apikey.setText(config_dict["deepseek_API_key_str"])
                if "deepseek_proxy_port" in config_dict:
                    Main_Window.Widget_Deepseek.LineEdit_proxy_port.setText(config_dict["deepseek_proxy_port"])

                #dashscope官方账号界面
                if "dashscope_model_type" in config_dict:
                    model_type = config_dict["dashscope_model_type"]
                    existing_index = Main_Window.Widget_Dashscope.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Dashscope.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Dashscope.comboBox_model.setCurrentText(model_type)
                if "dashscope_API_key_str" in config_dict:
                    Main_Window.Widget_Dashscope.TextEdit_apikey.setText(config_dict["dashscope_API_key_str"])
                if "dashscope_proxy_port" in config_dict:
                    Main_Window.Widget_Dashscope.LineEdit_proxy_port.setText(config_dict["dashscope_proxy_port"])


                #火山官方账号界面
                if "volcengine_access_point" in config_dict:
                    Main_Window.Widget_Volcengine.A_settings.LineEdit_access_point.setText(config_dict["volcengine_access_point"])
                if "volcengine_API_key_str" in config_dict:
                    Main_Window.Widget_Volcengine.A_settings.TextEdit_apikey.setText(config_dict["volcengine_API_key_str"])
                if "volcengine_proxy_port" in config_dict:
                    Main_Window.Widget_Volcengine.A_settings.LineEdit_proxy_port.setText(config_dict["volcengine_proxy_port"])
                if "volcengine_tokens_limit" in config_dict:
                    Main_Window.Widget_Volcengine.B_settings.spinBox_tokens.setValue(config_dict["volcengine_tokens_limit"])
                if "volcengine_rpm_limit" in config_dict:
                    Main_Window.Widget_Volcengine.B_settings.spinBox_RPM.setValue(config_dict["volcengine_rpm_limit"])
                if "volcengine_tpm_limit" in config_dict:
                    Main_Window.Widget_Volcengine.B_settings.spinBox_TPM.setValue(config_dict["volcengine_tpm_limit"])
                if "volcengine_input_pricing" in config_dict:
                    Main_Window.Widget_Volcengine.B_settings.spinBox_input_pricing.setValue(config_dict["volcengine_input_pricing"])
                if "volcengine_output_pricing" in config_dict:
                    Main_Window.Widget_Volcengine.B_settings.spinBox_output_pricing.setValue(config_dict["volcengine_output_pricing"])


                #零一万物官方账号界面
                if "yi_account_type" in config_dict:
                    Main_Window.Widget_Yi.comboBox_account_type.setCurrentText(config_dict["yi_account_type"])
                if "yi_model_type" in config_dict:
                    model_type = config_dict["yi_model_type"]
                    existing_index = Main_Window.Widget_Yi.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_Yi.comboBox_model.addItem(model_type)
                    Main_Window.Widget_Yi.comboBox_model.setCurrentText(model_type)
                if "yi_API_key_str" in config_dict:
                    Main_Window.Widget_Yi.TextEdit_apikey.setText(config_dict["yi_API_key_str"])
                if "yi_proxy_port" in config_dict:
                    Main_Window.Widget_Yi.LineEdit_proxy_port.setText(config_dict["yi_proxy_port"])


                #智谱官方界面
                if "zhipu_account_type" in config_dict:
                    Main_Window.Widget_ZhiPu.comboBox_account_type.setCurrentText(config_dict["zhipu_account_type"])
                if "zhipu_model_type" in config_dict:
                    model_type = config_dict["zhipu_model_type"]
                    existing_index = Main_Window.Widget_ZhiPu.comboBox_model.findText(model_type)
                    if existing_index == -1:
                        Main_Window.Widget_ZhiPu.comboBox_model.addItem(model_type)
                    Main_Window.Widget_ZhiPu.comboBox_model.setCurrentText(model_type)
                if "zhipu_API_key_str" in config_dict:
                    Main_Window.Widget_ZhiPu.TextEdit_apikey.setText(config_dict["zhipu_API_key_str"])
                if "zhipu_proxy_port" in config_dict:
                    Main_Window.Widget_ZhiPu.LineEdit_proxy_port.setText(config_dict["zhipu_proxy_port"])

                #sakura界面
                if "sakura_address" in config_dict:
                    Main_Window.Widget_SakuraLLM.LineEdit_address.setText(config_dict["sakura_address"])
                if "sakura_model_type" in config_dict:
                    Main_Window.Widget_SakuraLLM.comboBox_model.setCurrentText(config_dict["sakura_model_type"])
                if "sakura_proxy_port" in config_dict:
                    Main_Window.Widget_SakuraLLM.LineEdit_proxy_port.setText(config_dict["sakura_proxy_port"])


                #代理账号基础界面
                if "op_relay_address" in config_dict:
                    Main_Window.Widget_Proxy.A_settings.LineEdit_relay_address.setText(config_dict["op_relay_address"])
                if "op_proxy_platform" in config_dict:
                    Main_Window.Widget_Proxy.A_settings.comboBox_proxy_platform.setCurrentText(config_dict["op_proxy_platform"])
                    # 根据下拉框的索引调用不同的函数
                    if config_dict["op_proxy_platform"] =="OpenAI":
                        Main_Window.Widget_Proxy.A_settings.comboBox_model_openai.show()
                        Main_Window.Widget_Proxy.A_settings.comboBox_model_anthropic.hide()
                    elif config_dict["op_proxy_platform"] == 'Anthropic':
                        Main_Window.Widget_Proxy.A_settings.comboBox_model_openai.hide()
                        Main_Window.Widget_Proxy.A_settings.comboBox_model_anthropic.show()
                if "op_model_type_openai" in config_dict:

                    # 获取配置文件中指定的模型类型
                    model_type = config_dict["op_model_type_openai"]
                    # 检查模型类型是否已经存在于下拉列表中
                    existing_index = Main_Window.Widget_Proxy.A_settings.comboBox_model_openai.findText(model_type)
                    # 如果模型类型不存在，则添加到下拉列表中
                    if existing_index == -1:
                        Main_Window.Widget_Proxy.A_settings.comboBox_model_openai.addItem(model_type)
                    # 设置当前文本为配置文件中指定的模型类型
                    Main_Window.Widget_Proxy.A_settings.comboBox_model_openai.setCurrentText(model_type)

                if "op_model_type_anthropic" in config_dict:
                    # 获取配置文件中指定的模型类型
                    model_type = config_dict["op_model_type_anthropic"]
                    # 检查模型类型是否已经存在于下拉列表中
                    existing_index = Main_Window.Widget_Proxy.A_settings.comboBox_model_anthropic.findText(model_type)
                    # 如果模型类型不存在，则添加到下拉列表中
                    if existing_index == -1:
                        Main_Window.Widget_Proxy.A_settings.comboBox_model_anthropic.addItem(model_type)
                    # 设置当前文本为配置文件中指定的模型类型
                    Main_Window.Widget_Proxy.A_settings.comboBox_model_anthropic.setCurrentText(model_type)

                if "op_auto_complete" in config_dict:
                    Main_Window.Widget_Proxy.A_settings.SwitchButton_auto_complete.setChecked(config_dict["op_auto_complete"])
                if "op_API_key_str" in config_dict:
                    Main_Window.Widget_Proxy.A_settings.TextEdit_apikey.setText(config_dict["op_API_key_str"])
                if "op_proxy_port" in config_dict:
                    Main_Window.Widget_Proxy.A_settings.LineEdit_proxy_port.setText(config_dict["op_proxy_port"])


                #代理账号进阶界面
                if "op_tokens_limit" in config_dict:
                    Main_Window.Widget_Proxy.B_settings.spinBox_tokens.setValue(config_dict["op_tokens_limit"])
                if "op_rpm_limit" in config_dict:
                    Main_Window.Widget_Proxy.B_settings.spinBox_RPM.setValue(config_dict["op_rpm_limit"])
                if "op_tpm_limit" in config_dict:
                    Main_Window.Widget_Proxy.B_settings.spinBox_TPM.setValue(config_dict["op_tpm_limit"])
                if "op_input_pricing" in config_dict:
                    Main_Window.Widget_Proxy.B_settings.spinBox_input_pricing.setValue(config_dict["op_input_pricing"])
                if "op_output_pricing" in config_dict:
                    Main_Window.Widget_Proxy.B_settings.spinBox_output_pricing.setValue(config_dict["op_output_pricing"])


                if "additional_platform_dict" in config_dict:
                    configurator.additional_platform_count = config_dict["additional_platform_count"]
                    configurator.additional_platform_dict = config_dict["additional_platform_dict"]
                    for key, value in configurator.additional_platform_dict.items():
                        # 获取索引对象名
                        object_name = key

                        # 创建动态名实例,并存入字典里
                        Widget_New = configurator.instances_information[object_name] = Widget_New_proxy(object_name, None,configurator,user_interface_prompter,background_executor)

                        # 获取平台显示名
                        object_name_cn = value

                        # 添加新导航项(这里使用子函数，是因为lambda不能循环使用，会导致指向同一个页面)
                        Main_Window.add_sub_interface(Widget_New,object_name,object_name_cn)

                        # 添加新选项到UI选项中
                        user_interface_prompter.add_new_proxy_option(object_name_cn)


                        #代理账号基础界面
                        Widget_New.A_settings.LineEdit_relay_address.setText(config_dict[object_name]["op_relay_address"])
                        Widget_New.A_settings.comboBox_proxy_platform.setCurrentText(config_dict[object_name]["op_proxy_platform"])
                        # 根据下拉框的索引调用不同的函数
                        if config_dict[object_name]["op_proxy_platform"] =="OpenAI":
                            Widget_New.A_settings.comboBox_model_openai.show()
                            Widget_New.A_settings.comboBox_model_anthropic.hide()
                        elif config_dict[object_name]["op_proxy_platform"] == 'Anthropic':
                            Widget_New.A_settings.comboBox_model_openai.hide()
                            Widget_New.A_settings.comboBox_model_anthropic.show()

                        # 获取配置文件中指定的模型类型
                        model_type = config_dict[object_name]["op_model_type_openai"]
                        # 检查模型类型是否已经存在于下拉列表中
                        existing_index = Widget_New.A_settings.comboBox_model_openai.findText(model_type)
                        # 如果模型类型不存在，则添加到下拉列表中
                        if existing_index == -1:
                            Widget_New.A_settings.comboBox_model_openai.addItem(model_type)
                        # 设置当前文本为配置文件中指定的模型类型
                        Widget_New.A_settings.comboBox_model_openai.setCurrentText(model_type)

                        # 获取配置文件中指定的模型类型
                        model_type = config_dict[object_name]["op_model_type_anthropic"]
                        # 检查模型类型是否已经存在于下拉列表中
                        existing_index = Widget_New.A_settings.comboBox_model_anthropic.findText(model_type)
                        # 如果模型类型不存在，则添加到下拉列表中
                        if existing_index == -1:
                            Widget_New.A_settings.comboBox_model_anthropic.addItem(model_type)
                        # 设置当前文本为配置文件中指定的模型类型
                        Widget_New.A_settings.comboBox_model_anthropic.setCurrentText(model_type)

                            
                        Widget_New.A_settings.TextEdit_apikey.setText(config_dict[object_name]["op_API_key_str"])
                        Widget_New.A_settings.LineEdit_proxy_port.setText(config_dict[object_name]["op_proxy_port"])
                        Widget_New.A_settings.SwitchButton_auto_complete.setChecked(config_dict[object_name]["op_auto_complete"])

                        Widget_New.B_settings.spinBox_tokens.setValue(config_dict[object_name]["op_tokens_limit"])
                        Widget_New.B_settings.spinBox_RPM.setValue(config_dict[object_name]["op_rpm_limit"])
                        Widget_New.B_settings.spinBox_TPM.setValue(config_dict[object_name]["op_tpm_limit"])
                        Widget_New.B_settings.spinBox_input_pricing.setValue(config_dict[object_name]["op_input_pricing"])
                        Widget_New.B_settings.spinBox_output_pricing.setValue(config_dict[object_name]["op_output_pricing"])




                #翻译设置基础界面
                if "translation_project" in config_dict:
                    Main_Window.Widget_translation_settings_A.comboBox_translation_project.setCurrentText(config_dict["translation_project"])
                if "translation_platform" in config_dict:
                    Main_Window.Widget_translation_settings_A.comboBox_translation_platform.setCurrentText(config_dict["translation_platform"])
                if "source_language" in config_dict:
                    Main_Window.Widget_translation_settings_A.comboBox_source_text.setCurrentText(config_dict["source_language"])
                if "target_language" in config_dict:
                    Main_Window.Widget_translation_settings_A.comboBox_translated_text.setCurrentText(config_dict["target_language"])
                if "label_input_path" in config_dict:
                    Main_Window.Widget_translation_settings_A.label_input_path.setText(config_dict["label_input_path"])
                if "label_output_path" in config_dict:
                    Main_Window.Widget_translation_settings_A.label_output_path.setText(config_dict["label_output_path"])



                #翻译设置进阶界面
                if "lines_limit_switch" in config_dict:
                    Main_Window.Widget_translation_settings_B1.checkBox_lines_limit_switch.setChecked(config_dict["lines_limit_switch"])
                if "lines_limit" in config_dict:
                    Main_Window.Widget_translation_settings_B1.spinBox_lines_limit.setValue(config_dict["lines_limit"])
                if "tokens_limit_switch" in config_dict:
                    Main_Window.Widget_translation_settings_B1.checkBox_tokens_limit_switch.setChecked(config_dict["tokens_limit_switch"])
                if "tokens_limit" in config_dict:
                    Main_Window.Widget_translation_settings_B1.spinBox_tokens_limit.setValue(config_dict["tokens_limit"])
                if "pre_line_counts" in config_dict:
                    Main_Window.Widget_translation_settings_B1.spinBox_pre_lines.setValue(config_dict["pre_line_counts"])
                if "user_thread_counts" in config_dict:
                    Main_Window.Widget_translation_settings_B1.spinBox_thread_count.setValue(config_dict["user_thread_counts"])
                if "retry_count_limit" in config_dict:
                    Main_Window.Widget_translation_settings_B1.spinBox_retry_count_limit.setValue(config_dict["retry_count_limit"])
                if "round_limit" in config_dict:
                     Main_Window.Widget_translation_settings_B1.spinBox_round_limit.setValue(config_dict["round_limit"]) 
                if "cot_toggle" in config_dict:
                    Main_Window.Widget_translation_settings_B2.SwitchButton_cot_toggle.setChecked(config_dict["cot_toggle"])
                if "cn_prompt_toggle" in config_dict:
                    Main_Window.Widget_translation_settings_B2.SwitchButton_cn_prompt_toggle.setChecked(config_dict["cn_prompt_toggle"])
                if "preserve_line_breaks_toggle" in config_dict:
                    Main_Window.Widget_translation_settings_B2.SwitchButton_line_breaks.setChecked(config_dict["preserve_line_breaks_toggle"])
                if "response_conversion_toggle" in config_dict:
                    Main_Window.Widget_translation_settings_B2.SwitchButton_conversion_toggle.setChecked(config_dict["response_conversion_toggle"])
                if "opencc_preset" in config_dict:
                    Main_Window.Widget_translation_settings_B2.comboBox_opencc_preset.setCurrentText(config_dict["opencc_preset"])
                if "text_clear_toggle" in config_dict:
                    Main_Window.Widget_translation_settings_B2.SwitchButton_clear.setChecked(config_dict["text_clear_toggle"])

                #翻译设置的检查设置
                if "reply_check_switch" in config_dict:
                    if "Model Degradation Check" in config_dict["reply_check_switch"]:
                        Main_Window.Widget_translation_settings_B3.SwitchButton_check1.setChecked(config_dict["reply_check_switch"]["Model Degradation Check"])
                    if "Residual Original Text Check" in config_dict["reply_check_switch"]:
                        Main_Window.Widget_translation_settings_B3.SwitchButton_check2.setChecked(config_dict["reply_check_switch"]["Residual Original Text Check"])
                    if "Return to Original Text Check" in config_dict["reply_check_switch"]:
                        Main_Window.Widget_translation_settings_B3.SwitchButton_check3.setChecked(config_dict["reply_check_switch"]["Return to Original Text Check"])

                #翻译设置混合翻译界面
                if "translation_mixing_toggle" in config_dict:
                    Main_Window.Widget_translation_settings_C.SwitchButton_mixed_translation.setChecked(config_dict["translation_mixing_toggle"])
                if "mixed_translation_settings" in config_dict:
                    Main_Window.Widget_translation_settings_C.SettingCard_A.translationPlatform_comboBox.setCurrentText(config_dict["mixed_translation_settings"]["translation_platform_1"])

                    Main_Window.Widget_translation_settings_C.SettingCard_B.translationPlatform_comboBox.setCurrentText(config_dict["mixed_translation_settings"]["translation_platform_2"])
                    Main_Window.Widget_translation_settings_C.SettingCard_B.customModel_Button.setChecked(config_dict["mixed_translation_settings"]["customModel_siwtch_2"])
                    Main_Window.Widget_translation_settings_C.SettingCard_B.model_type.setText(config_dict["mixed_translation_settings"]["model_type_2"])
                    Main_Window.Widget_translation_settings_C.SettingCard_B.textSplitting_Button.setChecked(config_dict["mixed_translation_settings"]["split_switch_2"] )

                    Main_Window.Widget_translation_settings_C.SettingCard_C.translationPlatform_comboBox.setCurrentText(config_dict["mixed_translation_settings"]["translation_platform_3"])
                    Main_Window.Widget_translation_settings_C.SettingCard_C.customModel_Button.setChecked(config_dict["mixed_translation_settings"]["customModel_siwtch_3"])
                    Main_Window.Widget_translation_settings_C.SettingCard_C.model_type.setText(config_dict["mixed_translation_settings"]["model_type_3"])
                    Main_Window.Widget_translation_settings_C.SettingCard_C.textSplitting_Button.setChecked(config_dict["mixed_translation_settings"]["split_switch_3"] )


                #开始翻译的备份设置界面
                if "auto_backup_toggle" in config_dict:
                    Main_Window.Widget_start_translation.B_settings.checkBox_switch.setChecked(config_dict["auto_backup_toggle"])



                #提示字典界面
                if "User_Dictionary2" in config_dict:
                    User_Dictionary2 = config_dict["User_Dictionary2"]
                    if User_Dictionary2:
                        for key, value in User_Dictionary2.items():
                            row = Main_Window.Widget_prompt_dict.tableView.rowCount() - 1
                            Main_Window.Widget_prompt_dict.tableView.insertRow(row)
                            key_item = QTableWidgetItem(key)
                            # 兼容旧版本存储格式
                            if isinstance(value, dict):
                                value_item = QTableWidgetItem(value["translation"])
                                info_item = QTableWidgetItem(value["info"])
                                Main_Window.Widget_prompt_dict.tableView.setItem(row, 0, key_item)
                                Main_Window.Widget_prompt_dict.tableView.setItem(row, 1, value_item)
                                Main_Window.Widget_prompt_dict.tableView.setItem(row, 2, info_item)
                            else:
                                value_item = QTableWidgetItem(value)
                                Main_Window.Widget_prompt_dict.tableView.setItem(row, 0, key_item)
                                Main_Window.Widget_prompt_dict.tableView.setItem(row, 1, value_item)                                  
                        #删除第一行
                        Main_Window.Widget_prompt_dict.tableView.removeRow(0)
                if "prompt_dict_switch" in config_dict:
                    Change_translation_prompt = config_dict["prompt_dict_switch"]
                    Main_Window.Widget_prompt_dict.checkBox2.setChecked(Change_translation_prompt)


                #译前替换字典界面
                if "User_Dictionary1" in config_dict:
                    User_Dictionary1 = config_dict["User_Dictionary1"]
                    if User_Dictionary1:
                        for key, value in User_Dictionary1.items():
                            row = Main_Window.Widget_replace_dict.A_settings.tableView.rowCount() - 1
                            Main_Window.Widget_replace_dict.A_settings.tableView.insertRow(row)
                            key_item = QTableWidgetItem(key)
                            value_item = QTableWidgetItem(value)
                            Main_Window.Widget_replace_dict.A_settings.tableView.setItem(row, 0, key_item)
                            Main_Window.Widget_replace_dict.A_settings.tableView.setItem(row, 1, value_item)        
                        #删除第一行
                        Main_Window.Widget_replace_dict.A_settings.tableView.removeRow(0)
                if "Replace_before_translation" in config_dict:
                    Replace_before_translation = config_dict["Replace_before_translation"]
                    Main_Window.Widget_replace_dict.A_settings.checkBox1.setChecked(Replace_before_translation)


                #译后替换字典界面
                if "User_Dictionary3" in config_dict:
                    User_Dictionary3 = config_dict["User_Dictionary3"]
                    if User_Dictionary3:
                        for key, value in User_Dictionary3.items():
                            row = Main_Window.Widget_replace_dict.B_settings.tableView.rowCount() - 1
                            Main_Window.Widget_replace_dict.B_settings.tableView.insertRow(row)
                            key_item = QTableWidgetItem(key)
                            value_item = QTableWidgetItem(value)
                            Main_Window.Widget_replace_dict.B_settings.tableView.setItem(row, 0, key_item)
                            Main_Window.Widget_replace_dict.B_settings.tableView.setItem(row, 1, value_item)
                        #删除第一行
                        Main_Window.Widget_replace_dict.B_settings.tableView.removeRow(0)
                if "Replace_after_translation" in config_dict:
                    Replace_after_translation = config_dict["Replace_after_translation"]
                    Main_Window.Widget_replace_dict.B_settings.checkBox1.setChecked(Replace_after_translation)



                #实时设置界面(openai)
                if "OpenAI_parameter_adjustment" in config_dict:
                    OpenAI_parameter_adjustment = config_dict["OpenAI_parameter_adjustment"]
                    Main_Window.Widget_tune_openai.checkBox.setChecked(OpenAI_parameter_adjustment)
                if "OpenAI_Temperature" in config_dict:
                    OpenAI_Temperature = config_dict["OpenAI_Temperature"]
                    Main_Window.Widget_tune_openai.slider1.setValue(OpenAI_Temperature)
                if "OpenAI_top_p" in config_dict:
                    OpenAI_top_p = config_dict["OpenAI_top_p"]
                    Main_Window.Widget_tune_openai.slider2.setValue(OpenAI_top_p)
                if "OpenAI_presence_penalty" in config_dict:
                    OpenAI_presence_penalty = config_dict["OpenAI_presence_penalty"]
                    Main_Window.Widget_tune_openai.slider3.setValue(OpenAI_presence_penalty)
                if "OpenAI_frequency_penalty" in config_dict:
                    OpenAI_frequency_penalty = config_dict["OpenAI_frequency_penalty"]
                    Main_Window.Widget_tune_openai.slider4.setValue(OpenAI_frequency_penalty)

                #实时设置界面(anthropic)
                if "Anthropic_parameter_adjustment" in config_dict:
                    Anthropic_parameter_adjustment = config_dict["Anthropic_parameter_adjustment"]
                    Main_Window.Widget_tune_anthropic.checkBox.setChecked(Anthropic_parameter_adjustment)
                if "Anthropic_Temperature" in config_dict:
                    Anthropic_Temperature = config_dict["Anthropic_Temperature"]
                    Main_Window.Widget_tune_anthropic.slider1.setValue(Anthropic_Temperature)

                #实时设置界面(google)
                if "Google_parameter_adjustment" in config_dict:
                    Google_parameter_adjustment = config_dict["Google_parameter_adjustment"]
                    Main_Window.Widget_tune_google.checkBox.setChecked(Google_parameter_adjustment)
                if "Google_Temperature" in config_dict:
                    Google_Temperature = config_dict["Google_Temperature"]
                    Main_Window.Widget_tune_google.slider1.setValue(Google_Temperature)

                #实时设置界面(cohere)
                if "Cohere_parameter_adjustment" in config_dict:
                    Cohere_parameter_adjustment = config_dict["Cohere_parameter_adjustment"]
                    Main_Window.Widget_tune_cohere.checkBox.setChecked(Cohere_parameter_adjustment)
                if "Cohere_Temperature" in config_dict:
                    Cohere_Temperature = config_dict["Cohere_Temperature"]
                    Main_Window.Widget_tune_cohere.slider1.setValue(Cohere_Temperature)

                #实时设置界面(sakura)
                if "Sakura_parameter_adjustment" in config_dict:
                    Sakura_parameter_adjustment = config_dict["Sakura_parameter_adjustment"]
                    Main_Window.Widget_tune_sakura.checkBox.setChecked(Sakura_parameter_adjustment)
                if "Sakura_Temperature" in config_dict:
                    Sakura_Temperature = config_dict["Sakura_Temperature"]
                    Main_Window.Widget_tune_sakura.slider1.setValue(Sakura_Temperature)
                if "Sakura_top_p" in config_dict:
                    Sakura_top_p = config_dict["Sakura_top_p"]
                    Main_Window.Widget_tune_sakura.slider2.setValue(Sakura_top_p)
                if  "Sakura_frequency_penalty" in config_dict:
                    Sakura_frequency_penalty = config_dict["Sakura_frequency_penalty"]
                    Main_Window.Widget_tune_sakura.slider4.setValue(Sakura_frequency_penalty)


                #提示书界面
                if "system_prompt_switch" in config_dict:
                    system_prompt_switch = config_dict["system_prompt_switch"]
                    Main_Window.Widget_system_prompt.checkBox1.setChecked(system_prompt_switch)
                if "system_prompt_content" in config_dict:
                    system_prompt_content = config_dict["system_prompt_content"]
                    Main_Window.Widget_system_prompt.TextEdit1.setText(system_prompt_content)

                if "characterization_switch" in config_dict:
                    characterization_switch = config_dict["characterization_switch"]
                    Main_Window.Widget_characterization.checkBox1.setChecked(characterization_switch)
                if "characterization_dictionary" in config_dict:
                    characterization_dictionary = config_dict["characterization_dictionary"]
                    if characterization_dictionary:
                        for key, value in characterization_dictionary.items():
                            row = Main_Window.Widget_characterization.tableView.rowCount() - 1
                            Main_Window.Widget_characterization.tableView.insertRow(row)

                            original_name = QTableWidgetItem(value["original_name"])
                            translated_name = QTableWidgetItem(value["translated_name"])
                            Main_Window.Widget_characterization.tableView.setItem(row, 0, original_name)
                            Main_Window.Widget_characterization.tableView.setItem(row, 1, translated_name)

                            if (value.get('gender')):
                                character_attributes1 = QTableWidgetItem(value["gender"])
                                Main_Window.Widget_characterization.tableView.setItem(row, 2, character_attributes1)
                            if (value.get('age')):
                                character_attributes2 = QTableWidgetItem(value["age"])
                                Main_Window.Widget_characterization.tableView.setItem(row, 3, character_attributes2)
                            if (value.get('personality')):
                                character_attributes3 = QTableWidgetItem(value["personality"])
                                Main_Window.Widget_characterization.tableView.setItem(row, 4, character_attributes3)
                            if (value.get('speech_style')):
                                character_attributes4 = QTableWidgetItem(value["speech_style"])
                                Main_Window.Widget_characterization.tableView.setItem(row, 5, character_attributes4)
                            if (value.get('additional_info')):
                                character_attributes5 = QTableWidgetItem(value["additional_info"])
                                Main_Window.Widget_characterization.tableView.setItem(row, 6, character_attributes5)
                        #删除第一行
                        Main_Window.Widget_characterization.tableView.removeRow(0)

                if "world_building_switch" in config_dict:
                    world_building_switch = config_dict["world_building_switch"]
                    Main_Window.Widget_world_building.checkBox1.setChecked(world_building_switch)
                if "world_building_content" in config_dict:
                    world_building_content = config_dict["world_building_content"]
                    Main_Window.Widget_world_building.TextEdit1.setText(world_building_content)

                if "writing_style_switch" in config_dict:
                    writing_style_switch = config_dict["writing_style_switch"]
                    Main_Window.Widget_writing_style.checkBox1.setChecked(writing_style_switch)
                if "writing_style_content" in config_dict:
                    writing_style_content = config_dict["writing_style_content"]
                    Main_Window.Widget_writing_style.TextEdit1.setText(writing_style_content)

                if "translation_example_switch" in config_dict:
                    translation_example_switch = config_dict["translation_example_switch"]
                    Main_Window.Widget_translation_example.checkBox1.setChecked(translation_example_switch)
                if "translation_example" in config_dict:
                    translation_example = config_dict["translation_example"]
                    if translation_example:
                        for key, value in translation_example.items():
                            row = Main_Window.Widget_translation_example.tableView.rowCount() - 1
                            Main_Window.Widget_translation_example.tableView.insertRow(row)
                            key_item = QTableWidgetItem(key)
                            value_item = QTableWidgetItem(value)
                            Main_Window.Widget_translation_example.tableView.setItem(row, 0, key_item)
                            Main_Window.Widget_translation_example.tableView.setItem(row, 1, value_item)        
                        #删除第一行
                        Main_Window.Widget_translation_example.tableView.removeRow(0)

    # 添加新的平台选项
    def add_new_proxy_option(self,item_name):

        # 给基础设置添加代理选项
        existing_index = Main_Window.Widget_translation_settings_A.comboBox_translation_platform.findText(item_name)
        # 如果模型类型不存在，则添加到下拉列表中
        if existing_index == -1:
            Main_Window.Widget_translation_settings_A.comboBox_translation_platform.addItem(item_name)

        # 给混合设置添加代理选项
        existing_index = Main_Window.Widget_translation_settings_C.SettingCard_A.translationPlatform_comboBox.findText(item_name)
        if existing_index == -1:
            Main_Window.Widget_translation_settings_C.SettingCard_A.translationPlatform_comboBox.addItem(item_name)

        existing_index = Main_Window.Widget_translation_settings_C.SettingCard_B.translationPlatform_comboBox.findText(item_name)
        if existing_index == -1:
            Main_Window.Widget_translation_settings_C.SettingCard_B.translationPlatform_comboBox.addItem(item_name)

        existing_index = Main_Window.Widget_translation_settings_C.SettingCard_C.translationPlatform_comboBox.findText(item_name)
        if existing_index == -1:
            Main_Window.Widget_translation_settings_C.SettingCard_C.translationPlatform_comboBox.addItem(item_name)


    # 删除导航项及平台选项及配置信息
    def del_proxy_option(self,object_name):

        # 删除导航项
        Main_Window.del_Interface(object_name)


        # 删除平台选项
        if object_name in configurator.additional_platform_dict:
            platform_name = configurator.additional_platform_dict[object_name]
        else:
            return 0
        
        
        # 获取项目在组合框中的索引
        index = Main_Window.Widget_translation_settings_A.comboBox_translation_platform.findText(platform_name)
        # 如果找到了该项目，移除它
        if index != -1:
            Main_Window.Widget_translation_settings_A.comboBox_translation_platform.removeItem(index)


        index = Main_Window.Widget_translation_settings_C.SettingCard_A.translationPlatform_comboBox.findText(platform_name)
        if index != -1:
            Main_Window.Widget_translation_settings_C.SettingCard_A.translationPlatform_comboBox.removeItem(index)

        index = Main_Window.Widget_translation_settings_C.SettingCard_B.translationPlatform_comboBox.findText(platform_name)
        if index != -1:
            Main_Window.Widget_translation_settings_C.SettingCard_B.translationPlatform_comboBox.removeItem(index)
                
        index = Main_Window.Widget_translation_settings_C.SettingCard_C.translationPlatform_comboBox.findText(platform_name)
        if index != -1:
            Main_Window.Widget_translation_settings_C.SettingCard_C.translationPlatform_comboBox.removeItem(index)


        # 删除配置信息
        configurator.additional_platform_count = configurator.additional_platform_count - 1
        configurator.additional_platform_dict.pop(object_name)


# 任务执行器
class background_executor(threading.Thread): 
    def __init__(self, task_id = None,input_folder = None,output_folder= None,platform= None,base_url= None,model= None,api_key= None,proxy_port= None):
        super().__init__() # 调用父类构造
        self.task_id = task_id
        self.input_folder = input_folder
        self.output_folder = output_folder
        self.platform = platform
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.proxy_port = proxy_port

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
            Request_Tester.request_test(self,user_interface_prompter,self.platform,self.base_url,self.model,self.api_key,self.proxy_port)
            configurator.Running_status = 0

        # 输出缓存文件实现函数
        elif self.task_id == "输出缓存文件":
            File_Outputter.output_cache_file(self,configurator.cache_list,self.output_folder)
            print('\033[1;32mSuccess:\033[0m 已输出缓存文件到文件夹')

        # 输出已翻译文件实现函数
        elif self.task_id == "输出已翻译文件":

            # 复制缓存文本数据，避免手动导出被插件处理
            try:
                new_cache_data = copy.deepcopy(configurator.cache_list)
            except:
                print("[INFO]: 无法正常进行深层复制,改为浅复制")
                new_cache_data = configurator.cache_list.copy()

            # 调用插件
            plugin_manager.broadcast_event("manual_export", configurator,new_cache_data)

            File_Outputter.output_translated_content(self,new_cache_data,self.output_folder,self.input_folder)
            print('\033[1;32mSuccess:\033[0m 已输出已翻译文件到文件夹')


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
            print("\033[1;33mWarning:\033[0m 多线程任务正清理中，请耐心等待一会","\n")
            return False


    # 暂停翻译判断+实现函数
    def Pause_translation(self):
        configurator.Running_status = 9
        user_interface_prompter.createWarningInfoBar("软件的多线程任务正在逐一取消中，请等待全部任务释放完成！！！")
        user_interface_prompter.signal.emit("运行状态改变","正在取消线程任务中",0)
        print("\033[1;33mWarning:\033[0m 软件的多线程任务正在逐一取消中，请等待全部任务释放完成！！！-----------------------","\n")


    # 取消翻译判断+实现函数
    def Cancel_translation(self):

        # 如果正在翻译中或者取消线程任务中
        if configurator.Running_status in (6,9):
            configurator.Running_status = 11
            user_interface_prompter.createWarningInfoBar("软件的多线程任务正在逐一取消中，请等待全部任务释放完成！！！")
            user_interface_prompter.signal.emit("运行状态改变","正在取消线程任务中",0)
            print("\033[1;33mWarning:\033[0m 软件的多线程任务正在逐一取消中，请等待全部翻译任务释放完成！！！-----------------------","\n")

        # 如果已经暂停翻译
        elif configurator.Running_status == 10:

            configurator.Running_status = 0
            print("\033[1;33mWarning:\033[0m 翻译任务已取消-----------------------","\n")
            # 界面提示
            user_interface_prompter.createWarningInfoBar("翻译已取消")
            user_interface_prompter.signal.emit("重置界面数据","翻译取消",0)
            user_interface_prompter.signal.emit("运行状态改变",f"已取消翻译",0)

        # 如果正在空闲中
        elif configurator.Running_status == 0:

            configurator.Running_status = 0
            print("\033[1;33mWarning:\033[0m 当前无翻译任务-----------------------","\n")
            # 界面提示
            user_interface_prompter.createWarningInfoBar("当前无翻译任务")
            user_interface_prompter.signal.emit("重置界面数据","翻译取消",0)


    # 接口测试判断函数
    def Request_test_switch(self):
        if configurator.Running_status == 0:
            return True
        else:
            self.user_interface_prompter.createWarningInfoBar("正在进行任务中，请等待任务结束后再操作~")
            return False



if __name__ == '__main__':

    #开启子进程支持
    multiprocessing.freeze_support() 

    # 启用了高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)


    Software_Version = "AiNiee4.75"  #软件版本号


    # 工作目录改为python源代码所在的目录
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0])) # 获取当前工作目录
    sys.path.append(script_dir)
    print("[INFO] 当前工作目录是:",script_dir,'\n') 



    # 创建全局UI通讯器
    user_interface_prompter = User_Interface_Prompter() 
    user_interface_prompter.signal.connect(user_interface_prompter.on_update_ui)  #创建信号与槽函数的绑定，使用方法为：user_interface_prompter.signal.emit("str","str"....)

    # 创建全局配置器
    configurator = Configurator(script_dir)

    # 创建全局限制器
    request_limiter = Request_Limiter(configurator)

    # 创建全局插件管理器
    plugin_manager = Plugin_Manager()
   


    #创建全局窗口对象
    app = QApplication(sys.argv)
    Main_Window = window(Software_Version,configurator,user_interface_prompter,background_executor,jtpp)
    
    #窗口对象显示
    Main_Window.show()


    # 读取配置文件
    user_interface_prompter.read_write_config("read",configurator.resource_dir)

    #进入事件循环，等待用户操作   
    sys.exit(app.exec_())



