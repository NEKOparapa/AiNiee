
import os
from openai import OpenAI #需要安装库pip install openai
import google.generativeai as genai #需要安装库pip install -U google-generativeai
import anthropic #需要安装库pip install anthropic
import cohere  #需要安装库pip install cohere



# 接口测试器
class Request_Tester():
    def __init__(self):
        pass

    # 接口测试分发
    def request_test(self,user_interface_prompter,platform,base_url,model_type,api_key_str,proxy_port):

        # 执行openai接口测试
        if platform == "OpenAI":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行google接口测试
        elif platform == "Google":
            Request_Tester.google_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行anthropic接口测试
        elif platform == "Anthropic":
            Request_Tester.anthropic_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行cohere接口测试
        elif platform == "Cohere":
            Request_Tester.cohere_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行智谱接口测试
        elif platform == "Zhipu":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行零一万物接口测试
        elif platform == "Yi":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行月之暗面接口测试
        elif platform == "Moonshot":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行Deepseek接口测试
        elif platform == "Deepseek":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行Dashscope接口测试
        elif platform == "Dashscope":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行Volcengine接口测试
        elif platform == "Volcengine":
            Request_Tester.openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)

        # 执行Sakura接口测试
        elif platform == "Sakura":
            Request_Tester.sakura_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port)


    # openai接口测试
    def openai_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port):
        
        print("[INFO] 正在测试openai类接口",'\n')

        #如果填入地址，则设置系统代理
        if proxy_port :
            print("[INFO] 系统代理端口是:",proxy_port,'\n') 
            os.environ["http_proxy"]=proxy_port
            os.environ["https_proxy"]=proxy_port

        
        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")

        #检查一下请求地址尾部是否为/v1，自动补全,如果是/v4，则是在调用智谱接口，如果是/v3，则是豆包
        if base_url[-3:] != "/v1" and base_url[-3:] != "/v4" and base_url[-3:] != "/v3" :
            base_url = base_url + "/v1"

        #创建openai客户端
        client = OpenAI(api_key=API_key_list[0],
                base_url= base_url)


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model_type,'\n')

        #创建存储每个key测试结果的列表
        test_results = [None] * len(API_key_list)


        #循环测试每一个apikey情况
        for i, key in enumerate(API_key_list):
            print(f"[INFO] 正在测试第{i+1}个API KEY：{key}",'\n') 

            #更换key
            client.api_key = API_key_list[i]

            #构建发送内容
            messages_test = [{"role": "system","content":"你不是AI助手之类，你是我的女朋友欣雨。接下来你必须以女朋友的方式回复我"}, {"role":"user","content":"小可爱，你在干嘛"}]
            print("[INFO] 当前发送内容：\n", messages_test ,'\n')

            #尝试请求，并设置各种参数
            try:
                response_test = client.chat.completions.create( 
                model= model_type,
                messages = messages_test ,
                ) 

                #如果回复成功，显示成功信息
                response_test = response_test.choices[0].message.content
                print("[INFO] 已成功接受到AI的回复")
                print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

                test_results[i] = 1 #记录成功结果

            #如果回复失败，抛出错误信息，并测试下一个key
            except Exception as e:
                print("\033[1;31mError:\033[0m key：",API_key_list[i],"请求出现问题！错误信息如下")
                print(f"Error: {e}\n\n")
                test_results[i] = 0 #记录错误结果
                continue


        # 输出每个API密钥测试的结果
        print("[INFO] 全部API KEY测试结果--------------")
        for i, key in enumerate(API_key_list):
            result = "成功" if test_results[i] == 1 else "失败"
            print(f"第{i+1}个 API KEY：{key} 测试结果：{result}")

        # 检查测试结果是否全部成功
        all_successful = all(result == 1 for result in test_results)
        # 输出总结信息
        if all_successful:
            print("[INFO] 所有API KEY测试成功！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试成功",0)
        else:
            print("[INFO] 存在API KEY测试失败！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试失败",0)


    # google接口测试
    def google_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port):

        print("[INFO] 正在测试Google接口",'\n')

        #如果填入地址，则设置系统代理
        if proxy_port :
            print("[INFO] 系统代理端口是:",proxy_port,'\n') 
            os.environ["http_proxy"]=proxy_port
            os.environ["https_proxy"]=proxy_port


        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model_type,'\n')

        # 设置ai参数
        generation_config = {
        "temperature": 0,
        "top_p": 1,
        "top_k": 1,
        "max_output_tokens": 2048, #最大输出，pro最大输出是2048
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


        #创建存储每个key测试结果的列表
        test_results = [None] * len(API_key_list)


        #循环测试每一个apikey情况
        for i, key in enumerate(API_key_list):
            print(f"[INFO] 正在测试第{i+1}个API KEY：{key}",'\n') 

            #更换key
            genai.configure(api_key= API_key_list[i],transport='rest') 

            #构建发送内容
            system_prompt = "你是我的女朋友欣雨。接下来你必须以女朋友的方式向我问好"
            messages_test = ["你在干嘛呢？",]
            print("[INFO] 当前发送内容：\n", messages_test ,'\n')


            #设置对话模型
            model = genai.GenerativeModel(model_name=model_type,
                            generation_config=generation_config,
                            safety_settings=safety_settings,
                            system_instruction = system_prompt
                            )


            #尝试请求，并设置各种参数
            try:
                response_test =  model.generate_content(messages_test)

                #如果回复成功，显示成功信息
                response_test = response_test.text
                print("[INFO] 已成功接受到AI的回复")
                print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

                test_results[i] = 1 #记录成功结果

            #如果回复失败，抛出错误信息，并测试下一个key
            except Exception as e:
                print("\033[1;31mError:\033[0m key：",API_key_list[i],"请求出现问题！错误信息如下")
                print(f"Error: {e}\n\n")
                test_results[i] = 0 #记录错误结果
                continue


        # 输出每个API密钥测试的结果
        print("[INFO] 全部API KEY测试结果--------------")
        for i, key in enumerate(API_key_list):
            result = "成功" if test_results[i] == 1 else "失败"
            print(f"第{i+1}个 API KEY：{key} 测试结果：{result}")

        # 检查测试结果是否全部成功
        all_successful = all(result == 1 for result in test_results)
        # 输出总结信息
        if all_successful:
            print("[INFO] 所有API KEY测试成功！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试成功",0)
        else:
            print("[INFO] 存在API KEY测试失败！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试失败",0)


    # anthropic接口测试
    def anthropic_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port):
        
        print("[INFO] 正在测试Anthropic接口",'\n')

        #如果填入地址，则设置系统代理
        if proxy_port :
            print("[INFO] 系统代理端口是:",proxy_port,'\n') 
            os.environ["http_proxy"]=proxy_port
            os.environ["https_proxy"]=proxy_port


        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        #创建客户端
        client = anthropic.Anthropic(
            base_url=base_url,
            api_key=API_key_list[0]
        )



        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model_type,'\n')


        #创建存储每个key测试结果的列表
        test_results = [None] * len(API_key_list)


        #循环测试每一个apikey情况
        for i, key in enumerate(API_key_list):
            print(f"[INFO] 正在测试第{i+1}个API KEY：{key}",'\n') 

            #更换key
            client.api_key = API_key_list[i]

            #构建发送内容
            messages_test = [ {"role":"user","content":"小可爱，你在干嘛"}]
            print("[INFO] 当前发送内容：\n", messages_test ,'\n')


            #尝试请求，并设置各种参数
            try:
                response_test = client.messages.create(
                model= model_type,
                max_tokens=1000,
                system="你是我的女朋友欣雨。接下来你必须以女朋友的方式回复我",
                messages = messages_test ,
                ) 

            #    #如果回复成功，显示成功信息
                response_test = response_test.content[0].text


                print("[INFO] 已成功接受到AI的回复")
                print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

                test_results[i] = 1 #记录成功结果

            #如果回复失败，抛出错误信息，并测试下一个key
            except Exception as e:
                print("\033[1;31mError:\033[0m key：",API_key_list[i],"请求出现问题！错误信息如下")
                print(f"Error: {e}\n\n")
                test_results[i] = 0 #记录错误结果
                continue


        # 输出每个API密钥测试的结果
        print("[INFO] 全部API KEY测试结果--------------")
        for i, key in enumerate(API_key_list):
            result = "成功" if test_results[i] == 1 else "失败"
            print(f"第{i+1}个 API KEY：{key} 测试结果：{result}")

        # 检查测试结果是否全部成功
        all_successful = all(result == 1 for result in test_results)
        # 输出总结信息
        if all_successful:
            print("[INFO] 所有API KEY测试成功！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试成功",0)
        else:
            print("[INFO] 存在API KEY测试失败！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试失败",0)


    # cohere接口测试
    def cohere_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port):
        
        print("[INFO] 正在测试Cohere接口",'\n')

        #如果填入地址，则设置系统代理
        if proxy_port :
            print("[INFO] 系统代理端口是:",proxy_port,'\n') 
            os.environ["http_proxy"]=proxy_port
            os.environ["https_proxy"]=proxy_port

        
        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        #创建openai客户端
        client = cohere.Client(api_key=API_key_list[0],
                base_url= base_url)


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model_type,'\n')

        #创建存储每个key测试结果的列表
        test_results = [None] * len(API_key_list)


        #循环测试每一个apikey情况
        for i, key in enumerate(API_key_list):
            print(f"[INFO] 正在测试第{i+1}个API KEY：{key}",'\n') 

            #更换key
            client.api_key = API_key_list[i]

            #构建发送内容
            messages_test = "小可爱，你在干嘛"
            print("[INFO] 当前发送内容：\n", messages_test ,'\n')

            #尝试请求，并设置各种参数
            try:
                response_test = client.chat( 
                preamble= "你不是AI助手之类，你是我的女朋友欣雨。接下来你必须以女朋友的方式回复我",
                model= model_type,
                message = "小可爱，你在干嘛" ,
                ) 

                #如果回复成功，显示成功信息
                response_test = response_test.text
                print("[INFO] 已成功接受到AI的回复")
                print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

                test_results[i] = 1 #记录成功结果

            #如果回复失败，抛出错误信息，并测试下一个key
            except Exception as e:
                print("\033[1;31mError:\033[0m key：",API_key_list[i],"请求出现问题！错误信息如下")
                print(f"Error: {e}\n\n")
                test_results[i] = 0 #记录错误结果
                continue


        # 输出每个API密钥测试的结果
        print("[INFO] 全部API KEY测试结果--------------")
        for i, key in enumerate(API_key_list):
            result = "成功" if test_results[i] == 1 else "失败"
            print(f"第{i+1}个 API KEY：{key} 测试结果：{result}")

        # 检查测试结果是否全部成功
        all_successful = all(result == 1 for result in test_results)
        # 输出总结信息
        if all_successful:
            print("[INFO] 所有API KEY测试成功！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试成功",0)
        else:
            print("[INFO] 存在API KEY测试失败！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试失败",0)


    # sakura接口测试
    def sakura_request_test(self,user_interface_prompter,base_url,model_type,api_key_str,proxy_port):

        print("[INFO] 正在测试Sakura接口",'\n')

        #如果填入地址，则设置系统代理
        if proxy_port :
            print("[INFO] 系统代理端口是:",proxy_port,'\n') 
            os.environ["http_proxy"]=proxy_port
            os.environ["https_proxy"]=proxy_port

        

        #检查一下请求地址尾部是否为/v1，自动补全
        if base_url[-3:] != "/v1":
            base_url = base_url + "/v1"

        #创建openai客户端
        openaiclient = OpenAI(api_key="sakura",
                base_url= base_url)


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model_type,'\n')



        #构建发送内容
        messages_test = [{"role": "system","content":"你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"},
                         {"role":"user","content":"将下面的日文文本翻译成中文：サポートキャスト"}]
        print("[INFO] 当前发送内容：\n", messages_test ,'\n')

        #尝试请求，并设置各种参数
        try:
            response_test = openaiclient.chat.completions.create( 
            model= model_type,
            messages = messages_test ,
            ) 

            #如果回复成功，显示成功信息
            response_test = response_test.choices[0].message.content
            print("[INFO] 已成功接受到AI的回复")
            print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

            print("[INFO] 模型通讯测试成功！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试成功",0)

        #如果回复失败，抛出错误信息，并测试下一个key
        except Exception as e:
            print("\033[1;31mError:\033[0m 请求出现问题！错误信息如下")
            print(f"Error: {e}\n\n")
            print("[INFO] 模型通讯测试失败！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试失败",0)
