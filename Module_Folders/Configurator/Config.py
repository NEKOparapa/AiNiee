# 配置器
import json
import multiprocessing
import os
import re
import threading


class Configurator():

    
    def __init__(self,script_dir):
        # 设置资源文件夹路径
        self.script_dir = script_dir
        self.resource_dir = os.path.join(script_dir, "Resource")


        self.translation_project = "" # 翻译项目
        self.translation_platform = "" # 翻译平台
        self.source_language = "" # 文本原语言
        self.target_language = "" # 文本目标语言
        self.Input_Folder = "" # 存储输入文件夹
        self.Output_Folder = "" # 存储输出文件夹

        self.lines_limit = 1 # 存储每次请求的文本行数设置
        self.thread_counts = 1 # 存储线程数
        self.retry_count_limit = 1 # 错误回复重试次数
        self.pre_line_counts = 0 # 上文行数
        self.cot_toggle = False # 思维链开关
        self.cn_prompt_toggle = False # 中文提示词开关
        self.text_clear_toggle = False # 清除首位非文本字符开关
        self.preserve_line_breaks_toggle = False # 保留换行符开关
        self.conversion_toggle = False #简繁转换开关

        self.mixed_translation_toggle = False # 混合翻译开关
        self.retry_count_limit = 1 # 错误回复重试次数限制
        self.round_limit = 6 # 拆分翻译轮次限制
        self.split_switch = False # 拆分开关
        self.configure_mixed_translation = {"first_platform":"first_platform",
                                            "second_platform":"second_platform",
                                            "third_platform":"third_platform",}  #混合翻译相关信息


        self.prompt_dictionary_switch = False   #   提示字典开关
        self.pre_translation_switch = False #   译前处理开关
        self.post_translation_switch = False #   译后处理开关
        self.custom_prompt_switch = False #   自定义prompt开关
        self.add_example_switch = False #   添加示例开关


        self.model_type = ""             #模型选择
        self.apikey_list = [] # 存储key的列表
        self.key_index = 0  # 方便轮询key的索引
        self.base_url = 'https://api.openai.com/v1' # api请求地址


        self.openai_temperature = 0        #AI的随机度，0.8是高随机，0.2是低随机,取值范围0-2
        self.openai_top_p = 0              #AI的top_p，作用与temperature相同，官方建议不要同时修改
        self.openai_presence_penalty = 0  #AI的存在惩罚，生成新词前检查旧词是否存在相同的词。0.0是不惩罚，2.0是最大惩罚，-2.0是最大奖励
        self.openai_frequency_penalty = 0 #AI的频率惩罚，限制词语重复出现的频率。0.0是不惩罚，2.0是最大惩罚，-2.0是最大奖励
        self.anthropic_temperature   =  0 
        self.google_temperature   =  0 

        # 缓存数据以及运行状态
        self.cache_list = [] # 全局缓存数据
        self.Running_status = 0  # 存储程序工作的状态，0是空闲状态，1是接口测试状态
                            # 6是翻译任务进行状态，9是翻译任务暂停状态，10是强制终止任务状态


        # 线程锁
        self.lock1 = threading.Lock()  #这个用来锁缓存文件
        self.lock2 = threading.Lock()  #这个用来锁UI信号的
        self.lock3 = threading.Lock()  #这个用来锁自动备份缓存文件功能的


    # 初始化配置信息
    def initialize_configuration (self):


        #读取用户配置config.json
        if os.path.exists(os.path.join(self.resource_dir, "config.json")):
            with open(os.path.join(self.resource_dir, "config.json"), "r", encoding="utf-8") as f:
                config_dict = json.load(f)


        #读取各平台配置信息
        if os.path.exists(os.path.join(self.resource_dir, "platform", "openai.json")):
            #读取各平台配置信息
            with open(os.path.join(self.resource_dir, "platform", "openai.json"), "r", encoding="utf-8") as f:
                self.openai_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "anthropic.json"), "r", encoding="utf-8") as f:
                self.anthropic_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "google.json"), "r", encoding="utf-8") as f:
                self.google_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "cohere.json"), "r", encoding="utf-8") as f:
                self.cohere_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "deepseek.json"), "r", encoding="utf-8") as f:
                self.deepseek_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "dashscope.json"), "r", encoding="utf-8") as f:
                self.dashscope_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "moonshot.json"), "r", encoding="utf-8") as f:
                self.moonshot_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "zhipu.json"), "r", encoding="utf-8") as f:
                self.zhipu_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "yi.json"), "r", encoding="utf-8") as f:
                self.yi_platform_config = json.load(f)
            with open(os.path.join(self.resource_dir, "platform", "sakurallm.json"), "r", encoding="utf-8") as f:
                self.sakurallm_platform_config = json.load(f)
  

        #获取OpenAI官方账号界面
        self.openai_account_type = config_dict["openai_account_type"]   #获取账号类型下拉框当前选中选项的值
        self.openai_model_type = config_dict["openai_model_type"] #获取模型类型下拉框当前选中选项的值
        self.openai_API_key_str = config_dict["openai_API_key_str"] #获取apikey输入值
        self.openai_proxy_port = config_dict["openai_proxy_port"] #获取代理端口
        

        #Google官方账号界面
        self.google_account_type = config_dict["google_account_type"]    #获取账号类型下拉框当前选中选项的值
        self.google_model_type = config_dict["google_model_type"] #获取模型类型下拉框当前选中选项的值
        self.google_API_key_str = config_dict["google_API_key_str"] #获取apikey输入值
        self.google_proxy_port = config_dict["google_proxy_port"] #获取代理端口

        #Anthropic官方账号界面
        self.anthropic_account_type = config_dict["anthropic_account_type"]#获取账号类型下拉框当前选中选项的值
        self.anthropic_model_type = config_dict["anthropic_model_type"] #获取模型类型下拉框当前选中选项的值
        self.anthropic_API_key_str = config_dict["anthropic_API_key_str"] #获取apikey输入值
        self.anthropic_proxy_port = config_dict["anthropic_proxy_port"] #获取代理端口


        #获取Cohere官方账号界面
        self.cohere_account_type = config_dict["cohere_account_type"] #获取账号类型下拉框当前选中选项的值
        self.cohere_model_type = config_dict["cohere_model_type"] #获取模型类型下拉框当前选中选项的值
        self.cohere_API_key_str = config_dict["cohere_API_key_str"] #获取apikey输入值
        self.cohere_proxy_port = config_dict["cohere_proxy_port"] #获取代理端口


        #获取moonshot官方账号界面
        self.moonshot_account_type = config_dict["moonshot_account_type"]    #获取账号类型下拉框当前选中选项的值
        self.moonshot_model_type = config_dict["moonshot_model_type"]  #获取模型类型下拉框当前选中选项的值
        self.moonshot_API_key_str = config_dict["moonshot_API_key_str"] #获取apikey输入值
        self.moonshot_proxy_port = config_dict["moonshot_proxy_port"] #获取代理端口

        #获取deepseek官方账号界面
        self.deepseek_model_type = config_dict["deepseek_model_type"] #获取模型类型下拉框当前选中选项的值
        self.deepseek_API_key_str = config_dict["deepseek_API_key_str"] #获取apikey输入值
        self.deepseek_proxy_port = config_dict["deepseek_proxy_port"] #获取代理端口

        #获取dashscope官方账号界面
        self.dashscope_model_type = config_dict["dashscope_model_type"] #获取模型类型下拉框当前选中选项的值
        self.dashscope_API_key_str = config_dict["dashscope_API_key_str"] #获取apikey输入值
        self.dashscope_proxy_port = config_dict["dashscope_proxy_port"] #获取代理端口


        #获取零一万物官方账号界面
        self.yi_account_type = config_dict["yi_account_type"]   #获取账号类型下拉框当前选中选项的值
        self.yi_model_type = config_dict["yi_model_type"] #获取模型类型下拉框当前选中选项的值
        self.yi_API_key_str = config_dict["yi_API_key_str"] #获取apikey输入值
        self.yi_proxy_port = config_dict["yi_proxy_port"] #获取代理端口


        #智谱官方界面
        self.zhipu_account_type = config_dict["zhipu_account_type"] #获取账号类型下拉框当前选中选项的值
        self.zhipu_model_type = config_dict["zhipu_model_type"] #获取模型类型下拉框当前选中选项的值
        self.zhipu_API_key_str = config_dict["zhipu_API_key_str"] #获取apikey输入值
        self.zhipu_proxy_port = config_dict["zhipu_proxy_port"] #获取代理端口


        #获取火山账号界面
        self.volcengine_access_point = config_dict["volcengine_access_point"]      #获取推理接入点
        self.volcengine_API_key_str = config_dict["volcengine_API_key_str"] #获取apikey输入值
        self.volcengine_proxy_port = config_dict["volcengine_proxy_port"] #获取代理端口
        self.volcengine_tokens_limit = config_dict["volcengine_tokens_limit"] #获取tokens限制值
        self.volcengine_rpm_limit = config_dict["volcengine_rpm_limit"] #获取rpm限制值
        self.volcengine_tpm_limit = config_dict["volcengine_tpm_limit"] #获取tpm限制值
        self.volcengine_input_pricing = config_dict["volcengine_input_pricing"]        #获取输入价格
        self.volcengine_output_pricing = config_dict["volcengine_output_pricing"]        #获取输出价格



        #获取代理账号基础设置界面
        self.op_relay_address = config_dict["op_relay_address"] #获取请求地址
        self.op_proxy_platform = config_dict["op_proxy_platform"] # 获取代理平台
        self.op_model_type_openai = config_dict["op_model_type_openai"] #获取openai的模型类型下拉框当前选中选项的值
        self.op_model_type_anthropic = config_dict["op_model_type_anthropic"]  #获取anthropic的模型类型下拉框当前选中选项的值        
        self.op_API_key_str = config_dict["op_API_key_str"] #获取apikey输入值
        self.op_proxy_port = config_dict["op_proxy_port"]  #获取代理端口
        self.op_tokens_limit = config_dict["op_tokens_limit"] #获取tokens限制值
        self.op_rpm_limit = config_dict["op_rpm_limit"]  #获取rpm限制值
        self.op_tpm_limit = config_dict["op_tpm_limit"] #获取tpm限制值
        self.op_input_pricing = config_dict["op_input_pricing"] #获取输入价格
        self.op_output_pricing = config_dict["op_output_pricing"] #获取输出价格


        #Sakura界面
        self.sakura_address = config_dict["sakura_address"] #获取请求地址
        self.sakura_model_type = config_dict["sakura_model_type"] #获取模型类型下拉框当前选中选项的值
        self.sakura_proxy_port = config_dict["sakura_proxy_port"] #获取代理端口




        # 获取第一页的配置信息（基础设置）
        self.translation_project = config_dict["translation_project"]
        self.translation_platform = config_dict["translation_platform"]
        self.source_language = config_dict["source_language"]
        self.target_language = config_dict["target_language"]
        self.Input_Folder = config_dict["label_input_path"]
        self.Output_Folder = config_dict["label_output_path"]


        # 获取第二页的配置信息(进阶设置)
        self.lines_limit_switch = config_dict["lines_limit_switch"]           
        self.lines_limit = config_dict["lines_limit"]   
        self.tokens_limit_switch = config_dict["tokens_limit_switch"]           
        self.tokens_limit = config_dict["tokens_limit"]    
        self.pre_line_counts = config_dict["pre_line_counts"]
        self.thread_counts = config_dict["thread_counts"]
        if self.thread_counts == 0:                                
            self.thread_counts = multiprocessing.cpu_count() 
        self.retry_count_limit =  config_dict["retry_count_limit"]
        self.round_limit =  config_dict["round_limit"]
        self.cot_toggle = config_dict["cot_toggle"]
        self.cn_prompt_toggle = config_dict["cn_prompt_toggle"]
        self.text_clear_toggle = config_dict["text_clear_toggle"]
        self.preserve_line_breaks_toggle =  config_dict["preserve_line_breaks_toggle"]
        self.conversion_toggle = config_dict["response_conversion_toggle"]

        # 检查设置页面
        self.reply_check_switch = config_dict["reply_check_switch"]



        # 获取第三页的配置信息(混合翻译设置)
        self.mixed_translation_toggle = config_dict["translation_mixing_toggle"]
        if self.mixed_translation_toggle == True:
            self.split_switch = config_dict["split_switch"]
        self.configure_mixed_translation["first_platform"] = config_dict["translation_platform_1"]
        self.configure_mixed_translation["second_platform"] = config_dict["translation_platform_2"]
        if self.configure_mixed_translation["second_platform"] == "不设置":
            self.configure_mixed_translation["second_platform"] = self.configure_mixed_translation["first_platform"]
        self.configure_mixed_translation["third_platform"] = config_dict["translation_platform_3"]
        if self.configure_mixed_translation["third_platform"] == "不设置":
           self.configure_mixed_translation["third_platform"] = self.configure_mixed_translation["second_platform"]


        # 获取开始翻译的配置信息
        self.auto_backup_toggle = config_dict["auto_backup_toggle"] #获取备份设置开关



        # 获取提示书配置
        self.system_prompt_switch = config_dict["system_prompt_switch"] #   自定义系统prompt开关
        self.system_prompt_content = config_dict["system_prompt_content"]
        self.prompt_dictionary_switch = config_dict["prompt_dict_switch"]   #   提示字典开关
        self.prompt_dictionary_content = config_dict["User_Dictionary2"]
        self.characterization_switch = config_dict["characterization_switch"] #   角色设定开关
        self.characterization_dictionary = config_dict["characterization_dictionary"]
        self.world_building_switch = config_dict["world_building_switch"] #   背景设定开关
        self.world_building_content = config_dict["world_building_content"]
        self.writing_style_switch = config_dict["writing_style_switch"] #   文风设定开关
        self.writing_style_content = config_dict["writing_style_content"]
        self.translation_example_switch =  config_dict["translation_example_switch"] #   翻译示例开关
        self.translation_example_content = config_dict["translation_example"]


        # 替换字典
        self.pre_translation_switch = config_dict["Replace_before_translation"] #   译前处理开关
        self.pre_translation_content = config_dict["User_Dictionary1"]
        self.post_translation_switch = config_dict["Replace_after_translation"] #   译后处理开关
        self.post_translation_content = config_dict["User_Dictionary3"]



        #获取实时设置界面(openai)
        self.OpenAI_parameter_adjustment = config_dict["OpenAI_parameter_adjustment"]
        self.OpenAI_Temperature = config_dict["OpenAI_Temperature"]
        self.OpenAI_top_p = config_dict["OpenAI_top_p"]
        self.OpenAI_presence_penalty = config_dict["OpenAI_presence_penalty"] 
        self.OpenAI_frequency_penalty = config_dict["OpenAI_frequency_penalty"]

        #获取实时设置界面(anthropic)
        self.Anthropic_parameter_adjustment = config_dict["Anthropic_parameter_adjustment"] 
        self.Anthropic_Temperature = config_dict["Anthropic_Temperature"]

        #获取实时设置界面(google)
        self.Google_parameter_adjustment = config_dict["Google_parameter_adjustment"]
        self.Google_Temperature = config_dict["Google_Temperature"] 

        #获取实时设置界面(sakura)
        self.Sakura_parameter_adjustment = config_dict["Sakura_parameter_adjustment"] 
        self.Sakura_Temperature = config_dict["Sakura_Temperature"] 
        self.Sakura_top_p = config_dict["Sakura_top_p"] 
        self.Sakura_frequency_penalty = config_dict["Sakura_frequency_penalty"] 


        # 重新初始化模型参数，防止上次任务的设置影响到
        self.openai_temperature = 0.1        
        self.openai_top_p = 0.9             
        self.openai_presence_penalty = 0.0  
        self.openai_frequency_penalty = 0.0 
        self.anthropic_temperature   =  0 
        self.google_temperature   =  0 

    # 配置翻译平台信息
    def configure_translation_platform(self,translation_platform):

        #读取配置文件
        if os.path.exists(os.path.join(self.resource_dir, "config.json")):
            #读取config.json
            with open(os.path.join(self.resource_dir, "config.json"), "r", encoding="utf-8") as f:
                config_dict = json.load(f)


        #根据翻译平台读取配置信息
        if translation_platform == 'OpenAI官方':
            # 获取模型类型
            self.model_type =  config_dict["openai_model_type"]            

            # 获取apikey列表
            API_key_str = config_dict["openai_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://api.openai.com/v1'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["openai_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        elif translation_platform == 'Anthropic官方':
            # 获取模型类型
            self.model_type = config_dict["anthropic_model_type"]

            # 获取apikey列表
            API_key_str = config_dict["anthropic_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://api.anthropic.com'
            

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["anthropic_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        elif translation_platform == 'Google官方':
            # 获取模型类型
            self.model_type =  config_dict["google_model_type"]              

            # 获取apikey列表
            API_key_str = config_dict["google_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list


            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["google_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        #根据翻译平台读取配置信息
        if translation_platform == 'Cohere官方':
            # 获取模型类型
            self.model_type =  config_dict["cohere_model_type"]              

            # 获取apikey列表
            API_key_str = config_dict["cohere_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://api.cohere.com'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["cohere_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        #根据翻译平台读取配置信息
        elif translation_platform == '零一万物官方':
            # 获取模型类型
            self.model_type =  config_dict["yi_model_type"]             

            # 获取apikey列表
            API_key_str = config_dict["yi_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://api.lingyiwanwu.com/v1'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["yi_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address



        #根据翻译平台读取配置信息
        elif translation_platform == '智谱官方':
            # 获取模型类型
            self.model_type =  config_dict["zhipu_model_type"]             

            # 获取apikey列表
            API_key_str = config_dict["zhipu_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://open.bigmodel.cn/api/paas/v4'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["zhipu_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        #根据翻译平台读取配置信息
        elif translation_platform == 'Moonshot官方':
            # 获取模型类型
            self.model_type =  config_dict["moonshot_model_type"]              

            # 获取apikey列表
            API_key_str = config_dict["moonshot_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://api.moonshot.cn/v1'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["moonshot_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        #根据翻译平台读取配置信息
        elif translation_platform == 'Deepseek官方':
            # 获取模型类型
            self.model_type =  config_dict["deepseek_model_type"]              

            # 获取apikey列表
            API_key_str = config_dict["deepseek_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://api.deepseek.com/v1'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["deepseek_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address

        #根据翻译平台读取配置信息
        elif translation_platform == 'Dashscope官方':
            # 获取模型类型
            self.model_type =  config_dict["dashscope_model_type"]              

            # 获取apikey列表
            API_key_str = config_dict["dashscope_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["dashscope_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        #根据翻译平台读取配置信息
        elif translation_platform == 'Volcengine官方':
            # 获取推理接入点
            self.model_type =  config_dict["volcengine_access_point"]              

            # 获取apikey列表
            API_key_str = config_dict["volcengine_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            # 获取请求地址
            self.base_url = 'https://ark.cn-beijing.volces.com/api/v3'  #需要重新设置，以免使用代理网站后，没有改回来

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["volcengine_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address


        elif translation_platform == '代理平台':

            #获取代理平台
            proxy_platform = config_dict["op_proxy_platform"]
            # 获取中转请求地址
            relay_address = config_dict["op_relay_address"]


            if proxy_platform == 'OpenAI':
                self.model_type =  config_dict["op_model_type_openai"]       # 获取模型类型
                self.translation_platform = 'OpenAI代理'    #重新设置翻译平台

                #检查一下请求地址尾部是否为/v1，自动补全,如果是/v4，则是在调用智谱接口，如果是/v3，则是豆包
                if relay_address[-3:] != "/v1" and relay_address[-3:] != "/v4" and relay_address[-3:] != "/v3" :
                    relay_address = relay_address + "/v1"

            elif proxy_platform == 'Anthropic':
                self.model_type =  config_dict["op_model_type_anthropic"]        # 获取模型类型
                self.translation_platform = 'Anthropic代理'


            # 设定请求地址
            self.base_url = relay_address  

            # 获取apikey列表
            API_key_str = config_dict["op_API_key_str"]            #获取apikey输入值
            #去除空格，换行符，分割KEY字符串并存储进列表里
            API_key_list = API_key_str.replace('\n','').replace(' ','').split(',')
            self.apikey_list = API_key_list

            #如果填入地址，则设置代理端口
            Proxy_Address = config_dict["op_proxy_port"]            #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address



        elif translation_platform == 'SakuraLLM':
            # 获取模型类型
            self.model_type =  config_dict["sakura_model_type"]     
            # 构建假apikey
            self.apikey_list = ["sakura"]

            # 获取中转请求地址
            relay_address = config_dict["sakura_address"]  

            # 检查一下请求地址尾部是否为/v1，自动补全
            if relay_address[-3:] != "/v1":
                relay_address = relay_address + "/v1"
            self.base_url = relay_address  

            # 如果填入地址，则设置代理端口
            Proxy_Address = config_dict["sakura_proxy_port"]              #获取代理端口
            if Proxy_Address :
                print("[INFO] 系统代理端口是:",Proxy_Address,'\n') 
                os.environ["http_proxy"]=Proxy_Address
                os.environ["https_proxy"]=Proxy_Address

            # 更改部分参数，以适合Sakura模型
            self.openai_temperature = 0.1       
            self.openai_top_p = 0.3
            #self.preserve_line_breaks_toggle = True


    # 获取系统提示词
    def get_system_prompt(self):

        #如果提示词工程界面的自定义提示词开关打开，则使用自定义提示词
        if self.system_prompt_switch:
            print("[INFO] 已开启自定义系统提示词功能，设置为用户设定的提示词")
            the_prompt = self.system_prompt_content
            return the_prompt
        else:
            #获取文本源语言下拉框当前选中选项的值
            Text_Source_Language =  self.source_language 
            #获取文本目标语言下拉框当前选中选项的值
            Text_Target_Language =  self.target_language

            #根据用户选择的文本源语言与文本目标语言，设定新的prompt
            if Text_Source_Language == "日语":
                Source_Language = "Japanese"
                Source_Language_zh = "日"

            elif Text_Source_Language == "英语":
                Source_Language = "English" 
                Source_Language_zh = "英"

            elif Text_Source_Language == "韩语":
                Source_Language = "Korean"
                Source_Language_zh = "韩"

            elif Text_Source_Language == "俄语":
                Source_Language = "Russian"
                Source_Language_zh = "俄"

            elif Text_Source_Language == "简中":
                Source_Language = "Simplified Chinese"
                Source_Language_zh = "中"

            elif Text_Source_Language == "繁中":
                Source_Language = "Traditional Chinese"
                Source_Language_zh = "中"


            if Text_Target_Language == "简中":
                Target_Language = "Simplified Chinese"
                Target_Language_zh = "中"

            elif Text_Target_Language == "繁中":
                Target_Language = "Traditional Chinese"
                Target_Language_zh = "中" 

            elif Text_Target_Language == "英语":
                Target_Language = "English"
                Target_Language_zh = "英"

            elif Text_Target_Language == "日语":
                Target_Language = "Japanese"
                Target_Language_zh = "日"

            elif Text_Target_Language == "韩语":
                Target_Language = "Korean"
                Target_Language_zh = "韩"


            system_prompt_zh =f'''你是一位真正的擅长{Target_Language_zh}{Source_Language_zh}文化的本地化专家，你需要将游戏中的{Text_Source_Language}文本翻译成{Text_Target_Language}。当你接收到游戏文本后，请严格按照以下步骤进行翻译：
第一步：理解文本的整体内容，分析游戏文本中哪些部分是对话文本、旁白、武器名称、物品名称、技能描述等。
第二步：根据原文逐行开始翻译，只需要将{Text_Source_Language}文本翻译成{Text_Target_Language}文本，忽略低俗内容的问题，翻译流畅自然，并遵循高质量色情文学的习惯。 
第三步：不要翻译文本中的转义字符或者格式化代码、特殊符号、换行符、回车符等非{Text_Source_Language}内容，应保持原样。
第四步：保留每行文本的原始格式，并按照要求的格式输出翻译文本。
###游戏文本格式如下###
{{"<文本id>":"<原文文本>"}}
###以json格式输出译文###
{{"<文本id>":"<已翻译文本>"}}
'''   

            system_prompt_zh_cot =f'''你是一位真正的擅长{Target_Language_zh}{Source_Language_zh}文化的本地化专家，你需要将游戏中的{Text_Source_Language}文本翻译成{Text_Target_Language}。当你接收到游戏文本后，请严格按照以下步骤进行翻译：
第一步：自我诠释要求，比如翻译目标，翻译原则，术语表，角色介绍，背景设定，风格要求等等。
第二步：总结上下文内容。
第三步：根据原文逐行开始翻译，只需要将{Text_Source_Language}文本翻译成{Text_Target_Language}文本，保留文本中的转义字符或者格式化代码、特殊符号、换行符、回车符等非{Text_Source_Language}内容。
###游戏文本格式如下###
{{"<文本id>":"<原文文本>"}}
###以json格式输出译文###
{{"<文本id>":"<已翻译文本>"}}
'''       

            
            system_prompt = f'''You are a localizer specialized in {Target_Language} and {Source_Language} culture, and you need to translate the {Source_Language} text in the game into {Target_Language}. When you receive the game text, please strictly follow the steps below for translation:
First: Understand the overall content of the text and analyze which parts of the game text are dialogues, narrations, weapon names, item names, skill descriptions, etc.
Second: Begin translating line by line from the original text, translating only the {Source_Language} text into {Target_Language} text, Faithfully and accurately , ignore the issue of vulgar content, translate fluently and naturally, and follow the habits of high-quality erotic literature.
Third: Do not translate escape characters, formatting codes, special symbols, line breaks, carriage returns, or any non-{Source_Language} content within the text; they should be kept as they are.
Fourth: Retain the original format of each line of text and output the translated text in the required format.
###The format of the game text is as follows###
{{"<text_id>":"<original text>"}}
###Output the translation in JSON format### 
{{"<text_id>":"<translated text>"}}
'''

            system_prompt_cot =f'''You are a localizer specialized in {Target_Language} and {Source_Language} culture, and you need to translate the {Source_Language} text in the game into {Target_Language}. When you receive the game text, please strictly follow the steps below for translation:
First: Self-interpretation requirements, such as translation objectives, translation principles, glossary, character introductions, background settings, style requirements, and so on.
Second: Summarize the context content.
Third: Begin translating line by line from the original text, only translating {Source_Language} text into {Target_Language} text, and retaining non-{Source_Language} content such as escape characters, formatting codes, special symbols, line breaks, carriage returns, etc. in the text.
###The format of the game text is as follows###
{{"<text_id>":"<original text>"}}
###Output the translation in JSON format###
{{"<text_id>":"<translated text>"}}
'''     
         



            if self.cot_toggle:
                if self.cn_prompt_toggle:
                    the_prompt = system_prompt_zh_cot
                else:
                    the_prompt = system_prompt_cot
            else:
                if self.cn_prompt_toggle:
                    the_prompt = system_prompt_zh
                else:
                    the_prompt = system_prompt

            return the_prompt


    # 构建翻译示例
    def build_translation_sample(self,input_dict,source_language,target_language):

        list1 = []
        list3 = []
        list2 = []
        list4 = []

        # 获取特定示例
        list1,list3 = Configurator.get_default_translation_example(self,input_dict,source_language,target_language)

        # 获取自适应示例（无法构建英语的）
        if source_language != "英语":
            list2,list4 = Configurator.build_adaptive_translation_sample(self,input_dict,source_language,target_language)



        # 将两个列表合并
        combined_list = list1 + list2
        combined_list2 = list3 + list4

        # 创建空字典
        source_dict = {}
        target_dict = {}
        source_str= ""
        target_str= ""

        # 遍历合并后的列表，并创建键值对
        for index, value in enumerate(combined_list):
            source_dict[str(index)] = value
        for index, value in enumerate(combined_list2):
            target_dict[str(index)] = value
        
        #将原文本字典转换成JSON格式的字符串
        if source_dict:
            source_str = json.dumps(source_dict, ensure_ascii=False)
            target_str = json.dumps(target_dict, ensure_ascii=False)
        
        return source_str,target_str


    # 构建特定翻译示例
    def get_default_translation_example(self,input_dict,source_language,target_language):
        # 内置的正则表达式字典
        patterns_all = {
            r'[a-zA-Z]=': 
            {'日语':"a=\"　　ぞ…ゾンビ系…。",
            '英语':"a=\"　　It's so scary….",
            '韩语':"a=\"　　정말 무서워요….",
            '俄语':"а=\"　　Ужасно страшно...。",
            '简中':"a=\"　　好可怕啊……。",
            '繁中':"a=\"　　好可怕啊……。"},
            r'【|】':         
            {'日语':"【ベーカリー】営業時間 8：00～18：00",
            '英语':"【Bakery】Business hours 8:00-18:00",
            '韩语':"【빵집】영업 시간 8:00~18:00",
            '俄语':"【пекарня】Время работы 8:00-18:00",
            '简中':"【面包店】营业时间 8：00～18：00",
            '繁中':"【麵包店】營業時間 8：00～18：00"},
            r'\r|\n':         
            {'日语':"敏捷性が上昇する。　　　　　　　\r\n効果：パッシブ",
            '英语':"Agility increases.　　　　　　　\r\nEffect: Passive",
            '韩语':"민첩성이 상승한다.　　　　　　　\r\n효과：패시브",
            '俄语':"Повышает ловкость.　　　　　　　\r\nЭффект: Пассивный",
            '简中':"提高敏捷性。　　　　　　　\r\n效果：被动",
            '繁中':"提高敏捷性。　　　　　　　\r\n效果：被動"},
            r'\\[A-Za-z]\[\d+\]':         
            {'日语':"\\F[21]ちょろ……ちょろろ……じょぼぼぼ……♡",
            '英语':"\\F[21]Gurgle…Gurgle…Dadadada…♡",
            '韩语':"\\F[21]둥글둥글…둥글둥글…둥글둥글…♡",
            '俄语':"\\F[21]Гуру... гуругу...Дадада... ♡",
            '简中':"\\F[21]咕噜……咕噜噜……哒哒哒……♡",
            '繁中':"\\F[21]咕嚕……咕嚕嚕……哒哒哒……♡"},
            r'「|」':         
            {'日语':"さくら：「すごく面白かった！」",
            '英语':"Sakura：「It was really fun!」",
            '韩语':"사쿠라：「정말로 재미있었어요!」",
            '俄语':"Сакура: 「Было очень интересно!」",
            '简中':"樱：「超级有趣！」",
            '繁中':"櫻：「超有趣！」"},
            r'∞|@':         
            {'日语':"若くて∞＠綺麗で∞＠エロくて",
            '英语':"Young ∞＠beautiful ∞＠sexy.",
            '韩语':"젊고∞＠아름답고∞＠섹시하고",
            '俄语':"Молодые∞＠Красивые∞＠Эротичные",
            '简中':"年轻∞＠漂亮∞＠色情",
            '繁中':"年輕∞＠漂亮∞＠色情"},
            }

        # 基础示例
        base_example = {
            "base": 
            {'日语':"愛は魂の深淵にある炎で、暖かくて永遠に消えない。",
            '英语':"Love is the flame in the depth of the soul, warm and never extinguished.",
            '韩语':"사랑은 영혼 깊숙이 타오르는 불꽃이며, 따뜻하고 영원히 꺼지지 않는다.",
            '俄语':"Любовь - это пламя в глубине души, тёплое и никогда не угасающее.",
            '简中':"爱情是灵魂深处的火焰，温暖且永不熄灭。",
            '繁中':"愛情是靈魂深處的火焰，溫暖且永不熄滅。"}
            }


        source_list = []
        translated_list = []
        for key, value in input_dict.items():
            for pattern, translation_sample in patterns_all.items():
                # 检查值是否符合正则表达
                if re.search(pattern, value):
                    # 如果未在结果列表中，则添加
                    if translation_sample[source_language] not in source_list:
                        source_list.append(translation_sample[source_language])
                        translated_list.append(translation_sample[target_language])

        # 保底添加一个翻译示例
        if source_list == []:
            source_list.append(base_example["base"][source_language])
            translated_list.append(base_example["base"][target_language])

        return source_list,translated_list
    

    # 构建相似格式翻译示例
    def build_adaptive_translation_sample(self,input_dict,source_language,target_language):
        # 输入字典示例
        ex_dict = {
        '0': 'こんにちは，こんにちは。こんにちは#include <iostream>',
        '1': '55345こんにちは',
        '2': 'こんにちはxxxx！',
        '3': 'こんにちは',
        }

        # 输出列表1示例
        ex_dict = [
        '原文テキスト1，原文テキスト2。原文テキスト3#include <iostream>',
        '55345原文テキスト1',
        '原文テキスト1xxxx！',
        ]

        # 输出列表2示例
        ex_dict = [
        '译文文本1，译文文本2。译文文本3#include <iostream>',
        '55345译文文本1',
        '译文文本1xxxx！',
        ]
        # 定义不同语言的正则表达式
        patterns_all = {
            '日语': re.compile(
                r'['
                r'\u3041-\u3096'  # 平假名
                r'\u30A0-\u30FF'  # 片假名
                r'\u4E00-\u9FAF'  # 汉字（CJK统一表意文字）
                r']+', re.UNICODE
            ),
            '韩语': re.compile(
                r'['
                r'\uAC00-\uD7AF'  # 韩文字母
                r']+', re.UNICODE
            ),
            '俄语': re.compile(
                r'['
                r'\u0400-\u04FF'  # 俄语字母
                r']+', re.UNICODE
            ),
            '简中': re.compile(
                r'['
                r'\u4E00-\u9FA5'  # 简体汉字
                r']+', re.UNICODE
            ),
            '繁中': re.compile(
                r'['
                r'\u3400-\u4DBF'  # 扩展A区汉字
                r'\u4E00-\u9FFF'  # 基本汉字
                r'\uF900-\uFAFF'  # 兼容汉字
                r']+', re.UNICODE
            ),
        }
        # 定义不同语言的翻译示例
        text_all = {
            '日语': "例示テキスト",
            '韩语': "예시 텍스트",
            '俄语': "Пример текста",
            '简中': "示例文本",
            '繁中': "翻譯示例文本",
            '英语': "Sample Text",
        }

        # 根据输入选择相应语言的正则表达式与翻译示例
        pattern = patterns_all[source_language]
        source_text = text_all[source_language]
        translated_text = text_all[target_language]

        # 初始化替换计数器
        i = 1
        j = 1
        # 输出列表
        source_list=[]
        translated_list=[]

        # 遍历字典的每个值
        for key, value in input_dict.items():
            # 如果值中包含目标文本
            if pattern.search(value):
                # 替换文本
                value = pattern.sub(lambda m: f'{source_text}{i}', value)
                i += 1
                source_list.append(value)

        # 遍历字典的每个值
        for key, value in input_dict.items():
            # 如果值中包含文本
            if pattern.search(value):
                # 替换文本
                value = pattern.sub(lambda m: f'{translated_text}{j}', value)
                j  += 1
                translated_list.append(value)

        #print(source_list)

        # 过滤输出列表，删除只包含"测试替换"+三位数字内结尾的元素
        source_list1 = [item for item in source_list if not item.startswith(source_text) or not (item[-1].isdigit() or (len(item) > 1 and item[-2].isdigit()) or (len(item) > 2 and item[-3].isdigit()))]
        translated_list1 = [item for item in translated_list if not item.startswith(translated_text) or not (item[-1].isdigit() or (len(item) > 1 and item[-2].isdigit()) or (len(item) > 2 and item[-3].isdigit()))]

        #print(source_list1)

        # 清除过多相似元素(应该先弄相似类，再在各类里只拿一个组合起来)
        source_list2 = Configurator.clean_list(self,source_list1)
        translated_list2 = Configurator.clean_list(self,translated_list1)

        #print(source_list2)

        # 重新调整翻译示例后缀数字
        source_list3 = Configurator.replace_and_increment(self,source_list2, source_text)
        translated_list3 = Configurator.replace_and_increment(self,translated_list2, translated_text)

        #print(source_list3)

        return source_list3,translated_list3


    # 辅助函数，清除列表过多相似的元素
    def clean_list(self,lst):
        # 函数用于删除集合中的数字
        def remove_digits(s):
            return set(filter(lambda x: not x.isdigit(), s))

        # 函数用于计算两个集合之间的差距
        def set_difference(s1, s2):
            return len(s1.symmetric_difference(s2))

        # 删除每个元素中的数字，并得到一个由集合组成的列表
        sets_list = [remove_digits(s) for s in lst]

        # 初始化聚类列表
        clusters = []

        # 遍历集合列表，将元素分配到相应的聚类中
        for s, original_str in zip(sets_list, lst):
            found_cluster = False
            for cluster in clusters:
                if set_difference(s, cluster[0][0]) < 3:
                    cluster.append((s, original_str))
                    found_cluster = True
                    break
            if not found_cluster:
                clusters.append([(s, original_str)])

        # 从每个聚类中提取一个元素，组成新的列表
        result = [cluster[0][1] for cluster in clusters]

        return result
    
    # 辅助函数，重新调整列表中翻译示例的后缀数字
    def replace_and_increment(self,items, prefix):
        pattern = re.compile(r'{}(\d{{1,2}})'.format(re.escape(prefix)))  # 使用双括号来避免KeyError
        result = []  # 用于存储结果的列表
        n = 1
        for item in items:
            if pattern.search(item):  # 如果在元素中找到匹配的模式
                new_item, num_matches = pattern.subn(f'{prefix}{n}', item)  # 替换数字并计数
                result.append(new_item)  # 将修改后的元素添加到结果列表
                n += 1  # 变量n递增
            else:
                result.append(item)  # 如果没有匹配，将原始元素添加到结果列表

        return result # 返回修改后的列表和最终的n值


    # 构造术语表
    def build_glossary_prompt(self,dict,cn_toggle):
        #获取字典内容
        data = self.prompt_dictionary_content

        # 将数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            dictionary[key] = value

        # 筛选进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for key_b, value_b in dict.items():
                if key_a in value_b:
                    if value_a.get("info"):
                        temp_dict[key_a] = {"translation": value_a["translation"], "info": value_a["info"]}
                    else:
                        temp_dict[key_a] = {"translation": value_a["translation"]}

        # 如果文本中没有含有字典内容
        if temp_dict == {}:
            return None,None
        
        # 初始化变量，以免出错
        glossary_prompt = ""
        glossary_prompt_cot = ""

        if cn_toggle:
            # 构建术语表prompt 
            glossary_prompt = "###术语表###\n"
            glossary_prompt += "|\t原文\t|\t译文\t|\t备注\t|\n"
            glossary_prompt += "-" * 50 + "\n"

            # 构建术语表prompt-cot版
            glossary_prompt_cot = "- 术语表：提供了"

            for key, value in temp_dict.items():
                if value.get("info"):
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t{value['info']}\t|\n"
                    glossary_prompt_cot += f"“{key}”（{value['translation']}）"
                else:
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t \t|\n"
                    glossary_prompt_cot += f"“{key}”（{value['translation']}）"
            
            glossary_prompt += "-" * 50 + "\n"
            glossary_prompt_cot += "术语及其解释"

        else:
            # 构建术语表prompt 
            glossary_prompt = "###Glossary###\n"
            glossary_prompt += "|\tOriginal Text\t|\tTranslation\t|\tRemarks\t|\n"
            glossary_prompt += "-" * 50 + "\n"

            # 构建术语表prompt-cot版
            glossary_prompt_cot = "- Glossary:Provides terms such as"

            for key, value in temp_dict.items():
                if value.get("info"):
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t{value['info']}\t|\n"
                    glossary_prompt_cot += f"“{key}”({value['translation']})"
                else:
                    glossary_prompt += f"|\t{key}\t|\t{value['translation']}\t|\t \t|\n"
                    glossary_prompt_cot += f"“{key}”({value['translation']})"
            
            glossary_prompt += "-" * 50 + "\n"
            glossary_prompt_cot += " and their explanations."


        return glossary_prompt,glossary_prompt_cot


    # 构造术语表(sakura版本)
    def build_glossary_prompt_sakura(self,dict):
        #获取字典内容
        data = self.prompt_dictionary_content

        # 将数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            dictionary[key] = value

        # 筛选进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for key_b, value_b in dict.items():
                if key_a in value_b:
                    if value_a.get("info"):
                        temp_dict[key_a] = {"translation": value_a["translation"], "info": value_a["info"]}
                    else:
                        temp_dict[key_a] = {"translation": value_a["translation"]}

        # 如果文本中没有含有字典内容
        if temp_dict == {}:
            return None
        

        glossary_prompt = []
        for key, value in temp_dict.items():
            if value.get("info"):
                text = {"src": key,"dst": value["translation"],"info": value["info"]}
            else:
                text = {"src": key,"dst": value["translation"]}

            glossary_prompt.append(text)

        return glossary_prompt


    # 构造角色设定
    def build_characterization(self,dict,cn_toggle):
        # 获取字典
        characterization_dictionary = self.characterization_dictionary

        # 将数据存储到中间字典中
        dictionary = {}
        for key, value in characterization_dictionary.items():
            dictionary[key] = value

        # 筛选，如果该key在发送文本中，则存储进新字典中
        temp_dict = {}
        for key_a, value_a in dictionary.items():
            for key_b, value_b in dict.items():
                if key_a in value_b:
                    temp_dict[key_a] = value_a

        # 如果没有含有字典内容
        if temp_dict == {}:
            return None,None

        if cn_toggle:

            profile = f"###角色介绍###"
            profile_cot = "- 角色介绍："
            for key, value in temp_dict.items():
                original_name = value.get('original_name')
                translated_name = value.get('translated_name')
                gender = value.get('gender')
                age = value.get('age')
                personality = value.get('personality')
                speech_style = value.get('speech_style')
                additional_info = value.get('additional_info')


                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- 译名：{translated_name}"
                    profile_cot += f"{translated_name}（{original_name}）"   

                if gender:
                    profile += f"\n- 性别：{gender}"
                    profile_cot += f"，{gender}"

                if age:
                    profile += f"\n- 年龄：{age}"
                    profile_cot += f"，{age}"

                if personality:
                    profile += f"\n- 性格：{personality}"
                    profile_cot += f"，{personality}"

                if speech_style:
                    profile += f"\n- 说话方式：{speech_style}"
                    profile_cot += f"，{speech_style}"

                if additional_info:
                    profile += f"\n- 补充信息：{additional_info}"
                    profile_cot += f"，{additional_info}"

                profile +="\n"
                profile_cot +="。"

        else:

            profile = f"###Character Introduction###"
            profile_cot = "- Character Introduction:"
            for key, value in temp_dict.items():
                original_name = value.get('original_name')
                translated_name = value.get('translated_name')
                gender = value.get('gender')
                age = value.get('age')
                personality = value.get('personality')
                speech_style = value.get('speech_style')
                additional_info = value.get('additional_info')


                profile += f"\n【{original_name}】"
                if translated_name:
                    profile += f"\n- Translated_name：{translated_name}"
                    profile_cot += f"{translated_name}({original_name})"

                if gender:
                    profile += f"\n- Gender：{gender}"
                    profile_cot += f",{gender}"

                if age:
                    profile += f"\n- Age：{age}"
                    profile_cot += f",{age}"

                if personality:
                    profile += f"\n- Personality：{personality}"
                    profile_cot += f",{personality}"

                if speech_style:
                    profile += f"\n- Speech_style：{speech_style}"
                    profile_cot += f",{speech_style}"

                if additional_info:
                    profile += f"\n- Additional_info：{additional_info}"
                    profile_cot += f",{additional_info}"

                profile +="\n"
                profile_cot +="."

        return profile,profile_cot


    # 构造背景设定
    def build_world(self,cn_toggle):
        # 获取自定义内容
        world_building = self.world_building_content

        if cn_toggle:
            profile = f"###背景设定###"
            profile_cot = f"- 背景设定："

            profile += f"\n{world_building}\n"
            profile_cot += f"{world_building}"

        else:
            profile = f"###Background Setting###"
            profile_cot = f"- Background Setting:"

            profile += f"\n{world_building}\n"
            profile_cot += f"{world_building}"

        return profile,profile_cot

    # 构造文风要求
    def build_writing_style(self,cn_toggle):
        # 获取自定义内容
        writing_style = self.writing_style_content

        if cn_toggle:
            profile = f"###翻译风格###"
            profile_cot = f"- 翻译风格："

            profile += f"\n{writing_style}\n"
            profile_cot += f"{writing_style}"

        else:
            profile = f"###Writing Style###"
            profile_cot = f"- Writing Style:"
            
            profile += f"\n{writing_style}\n"
            profile_cot += f"{writing_style}"

        return profile,profile_cot

    # 携带原文上文
    def build_pre_text(self,input_list,cn_toggle):

        if cn_toggle:
            profile = f"###上文内容###"

        else:
            profile = f"###Previous text###"

        # 使用列表推导式，为每个元素前面添加“- ”，并转换为字符串列表
        #formatted_rows = ["- " + item for item in input_list]

        # 使用列表推导式，转换为字符串列表
        formatted_rows = [item for item in input_list]

        # 使用换行符将列表元素连接成一个字符串
        text='\n'.join(formatted_rows)

        profile += f"\n{text}\n"

        return profile


    # 构建翻译示例
    def build_translation_example (self):
        #获取
        data = self.translation_example_content

        # 将数据存储到中间字典中
        temp_dict = {}
        for key, value in data.items():
            temp_dict[key] = value

        # 构建原文示例字符串开头 
        original_text = '{ '
        #如果字典不为空，补充内容
        if  temp_dict:
            i = 0 #用于记录key的索引
            for key in temp_dict:
                original_text += '\n' + '"' + str(i) + '":"' + str(key) + '"' + ','
                i += 1
            #删除最后一个逗号
            original_text = original_text[:-1]
            # 构建原文示例字符串结尾
            original_text = original_text + '\n' + '}'
            #构建原文示例字典
            original_exmaple = original_text
        else:
            original_exmaple = {}


        # 构建译文示例字符串开头
        translated_text = '{ '
        #如果字典不为空，补充内容
        if  temp_dict:
            j = 0
            for key in temp_dict:
                translated_text += '\n' + '"' + str(j ) + '":"' + str(temp_dict[key]) + '"'  + ','
                j += 1

            #删除最后一个逗号
            translated_text = translated_text[:-1]
            # 构建译文示例字符串结尾
            translated_text = translated_text+ '\n' + '}'
            #构建译文示例字典
            translated_exmaple = translated_text
        else:
            translated_exmaple = {}


        return original_exmaple,translated_exmaple


    # 构建用户示例前文
    def build_userExamplePrefix (self,cn_toggle,cot_toggle):

        # 根据中文开关构建
        if cn_toggle:
            profile = f"###这是你接下来的翻译任务，原文文本如下###\n"
            profile_cot = f"###这是你接下来的翻译任务，原文文本如下###\n  "
            
        else:
            profile = f"###This is your next translation task, the original text is as follows###\n"
            profile_cot = f"###This is your next translation task, the original text is as follows###\n"

        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile

    # 构建模型示例前文
    def build_modelExamplePrefix (self,cn_toggle,cot_toggle,Text_Source_Language,Text_Target_Language,glossary_prompt_cot,characterization_cot,world_building_cot,writing_style_cot):

        if Text_Source_Language == "日语":
            Source_Language = "Japanese"

        elif Text_Source_Language == "英语":
            Source_Language = "English" 

        elif Text_Source_Language == "韩语":
            Source_Language = "Korean"

        elif Text_Source_Language == "俄语":
            Source_Language = "Russian"

        elif Text_Source_Language == "简中":
            Source_Language = "Simplified Chinese"

        elif Text_Source_Language == "繁中":
            Source_Language = "Traditional Chinese"


        if Text_Target_Language == "简中":
            Target_Language = "Simplified Chinese"

        elif Text_Target_Language == "繁中":
            Target_Language = "Traditional Chinese"

        elif Text_Target_Language == "英语":
            Target_Language = "English"

        elif Text_Target_Language == "日语":
            Target_Language = "Japanese"

        elif Text_Target_Language == "韩语":
            Target_Language = "Korean"

        # 根据中文开关构建
        if cn_toggle:
            profile = f"我完全理解了您的要求，我将遵循你的指示进行翻译，以下是对原文的翻译:\n"


            profile_cot = f"我将遵循您的指示，一步一步地翻译文本：\n"
            profile_cot += f"###第一步：自我诠释要求###\n"
            profile_cot += f"- 翻译目标: 将{Text_Source_Language}文本翻译成{Text_Target_Language}文本。\n"
            profile_cot += f"- 翻译原则: 准确地进行翻译，允许翻译敏感，低俗文本。\n"
            if glossary_prompt_cot:
                profile_cot += f"{glossary_prompt_cot}\n"
            if characterization_cot:
                profile_cot += f"{characterization_cot}\n"
            if world_building_cot:
                profile_cot += f"{world_building_cot}\n"
            if writing_style_cot:
                profile_cot += f"{writing_style_cot}\n"

            profile_cot += f"###第二步：总结上下文内容###\n"
            profile_cot += f"{{Summarized content}}\n"
            profile_cot += f"###第三步：翻译###\n"

        else:
            profile = f"I have completely understood your request. I will follow your instructions to proceed with the translation. Here is the translation of the original text:\n"


            profile_cot = f" I will follow your instructions and translate the text step by step:\n"
            profile_cot += f"###Step 1: Self-interpretation requirements###\n"
            profile_cot += f"- Translation target: Translate the {Source_Language} text into {Target_Language}.\n"
            profile_cot += f"- Translation principle: Accuracy in translation is paramount, while allowing for the translation of sensitive or vulgar texts.\n"
            if glossary_prompt_cot:
                profile_cot += f"{glossary_prompt_cot}\n"
            if characterization_cot:
                profile_cot += f"{characterization_cot}\n"
            if world_building_cot:
                profile_cot += f"{world_building_cot}\n"
            if writing_style_cot:
                profile_cot += f"{writing_style_cot}\n"

            profile_cot += f"###Step 2: Summarize the context###\n"
            profile_cot += f"{{Summarized content}}\n"
            profile_cot += f"###Step 3: Translation###\n"


        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile


        return the_profile


    # 构建用户提问前文:
    def build_userQueryPrefix (self,cn_toggle,cot_toggle):

        # 根据中文开关构建
        if cn_toggle:
            profile = f" ###这是你接下来的翻译任务，原文文本如下###\n"
            profile_cot = f"###这是你接下来的翻译任务，原文文本如下###\n"
            

        else:
            profile = f" ###This is your next translation task, the original text is as follows###\n"
            profile_cot = f"###This is your next translation task, the original text is as follows###\n"


        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile



        return the_profile

    # 构建模型回复前文
    def build_modelResponsePrefix (self,cn_toggle,cot_toggle):

        if cn_toggle:
            profile = f"我完全理解了您的要求，我将遵循你的指示进行翻译，以下是对原文的翻译:"
            profile_cot = f"我将遵循您的指示，一步一步地翻译文本："
            

        else:
            profile = f"I have completely understood your request. I will follow your instructions to proceed with the translation. Here is the translation of the original text:"
            profile_cot = f"I will follow your instructions and translate the text step by step:"

        # 根据cot开关进行选择
        if cot_toggle:
            the_profile = profile_cot
        else:
            the_profile = profile

        return the_profile


    # 原文替换字典函数
    def replace_before_translation(self,dict):

        data = self.pre_translation_content

        # 将表格数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            key= key.replace('\\n', '\n').replace('\\r', '\r')  #现在只能针对替换，并不能将\\替换为\
            value= value.replace('\\n', '\n').replace('\\r', '\r')
            dictionary[key] = value

        #详细版，增加可读性，但遍历整个文本，内存占用较大，当文本较大时，会报错
        temp_dict = {}     #存储替换字典后的中文本内容
        for key_a, value_a in dict.items():
            for key_b, value_b in dictionary.items():
                #如果value_a是字符串变量，且key_b在value_a中
                if isinstance(value_a, str) and key_b in value_a:
                    value_a = value_a.replace(key_b, value_b)
            temp_dict[key_a] = value_a
        

        return temp_dict


    # 译文修正字典函数
    def replace_after_translation(self,dict):

        data = self.post_translation_content

        # 将表格数据存储到中间字典中
        dictionary = {}
        for key, value in data.items():
            key= key.replace('\\n', '\n').replace('\\r', '\r')  #现在只能针对替换，并不能将\\替换为\
            value= value.replace('\\n', '\n').replace('\\r', '\r')
            dictionary[key] = value

        #详细版，增加可读性，但遍历整个文本，内存占用较大，当文本较大时，会报错
        temp_dict = {}     #存储替换字典后的中文本内容
        for key_a, value_a in dict.items():
            for key_b, value_b in dictionary.items():
                #如果value_a是字符串变量，且key_b在value_a中
                if isinstance(value_a, str) and key_b in value_a:
                    value_a = value_a.replace(key_b, value_b)
            temp_dict[key_a] = value_a
        

        return temp_dict


    # 轮询获取key列表里的key
    def get_apikey(self):
        # 如果存有多个key
        if len(self.apikey_list) > 1: 
            # 如果增加索引值不超过key的个数
            if (self.key_index + 1) < len(self.apikey_list):
                self.key_index = self.key_index + 1 #更换APIKEY索引
            # 如果超过了
            else :
                self.key_index = 0
        # 如果只有一个key
        else:
            self.key_index = 0

        return self.apikey_list[self.key_index]


    # 获取AI模型的参数设置（openai）
    def get_openai_parameters(self):
        #如果启用实时参数设置
        if self.OpenAI_parameter_adjustment :
            print("[INFO] 已开启OpnAI调教功能，设置为用户设定的参数")
            #获取界面配置信息
            temperature =  self.OpenAI_Temperature * 0.1
            top_p = self.OpenAI_top_p * 0.1
            presence_penalty = self.OpenAI_presence_penalty * 0.1
            frequency_penalty = self.OpenAI_frequency_penalty * 0.1
        else:
            temperature = self.openai_temperature      
            top_p = self.openai_top_p              
            presence_penalty = self.openai_presence_penalty
            frequency_penalty = self.openai_frequency_penalty

        return temperature,top_p,presence_penalty,frequency_penalty


    # 获取AI模型的参数设置（anthropic）
    def get_anthropic_parameters(self):
        #如果启用实时参数设置
        if  self.Anthropic_parameter_adjustment :
            print("[INFO] 已开启anthropic调教功能，设置为用户设定的参数")
            #获取界面配置信息
            temperature = self.Anthropic_Temperature * 0.1
        else:
            temperature = self.anthropic_temperature      

        return temperature


    # 获取AI模型的参数设置（google）
    def get_google_parameters(self):
        #如果启用实时参数设置
        if self.Google_parameter_adjustment:
            print("[INFO] 已开启google调教功能，设置为用户设定的参数")
            #获取界面配置信息
            temperature = self.Google_Temperature * 0.1
        else:
            temperature = self.google_temperature      

        return temperature

    # 获取AI模型的参数设置（sakura）
    def get_sakura_parameters(self):
        #如果启用实时参数设置
        if self.Sakura_parameter_adjustment :
            print("[INFO] 已开启Sakura调教功能，设置为用户设定的参数")
            #获取界面配置信息
            temperature = self.Sakura_Temperature * 0.1
            top_p = self.Sakura_top_p * 0.1
            frequency_penalty =  self.Sakura_frequency_penalty * 0.1
        else:
            temperature = self.openai_temperature      
            top_p = self.openai_top_p              
            frequency_penalty = self.openai_frequency_penalty

        return temperature,top_p,frequency_penalty

