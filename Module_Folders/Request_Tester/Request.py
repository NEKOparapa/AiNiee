import os

import cohere  # 需要安装库pip install cohere
import anthropic # 需要安装库pip install anthropic
import google.generativeai as genai # 需要安装库pip install -U google-generativeai

from rich import print
from openai import OpenAI # 需要安装库pip install openai

# 接口测试器
class Request_Tester():

    def __init__(self):
        pass

    # 接口测试分发
    def request_test(self, user_interface_prompter, tag, api_url, api_key, api_format, model, auto_complete, proxy_url, proxy_enable):
        # 获取接口地址并补齐，v3 结尾是火山，v4 结尾是智谱
        if tag == "sakura" and not api_url.endswith("/v1"):
            api_url = api_url + "/v1"
        elif auto_complete == True and not api_url.endswith("/v1") and not api_url.endswith("/v3") and not api_url.endswith("/v4"):
            api_url = api_url + "/v1"
        else:
            api_url = api_url

        # 获取并设置网络代理
        if proxy_enable == False or proxy_url == "":
            os.environ.pop("http_proxy", None)
            os.environ.pop("https_proxy", None)
        else:
            os.environ["http_proxy"] = proxy_url
            os.environ["https_proxy"] = proxy_url
            print(f"[[green]INFO[/]] 系统代理已启用，代理地址：{proxy_url}")

        if tag == "sakura":
            Request_Tester.sakura_request_test(self, user_interface_prompter, api_url, api_key, model)
        elif tag == "cohere":
            Request_Tester.cohere_request_test(self, user_interface_prompter, api_url, api_key, model)
        elif tag == "google":
            Request_Tester.google_request_test(self, user_interface_prompter, api_url, api_key, model)
        elif tag == "anthropic":
            Request_Tester.anthropic_request_test(self, user_interface_prompter, api_url, api_key, model)
        elif tag.startswith("custom_platform_") and api_format == "Anthropic":
            Request_Tester.anthropic_request_test(self, user_interface_prompter, api_url, api_key, model)
        else:
            Request_Tester.openai_request_test(self, user_interface_prompter, api_url, api_key, model)

    # openai接口测试
    def openai_request_test(self, user_interface_prompter, base_url, api_key, model):
        
        print("[INFO] 正在测试openai类接口",'\n')

        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        #创建openai客户端
        client = OpenAI(api_key=API_key_list[0],
                base_url= base_url)


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model,'\n')

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
                model= model,
                messages = messages_test ,
                ) 

                #如果回复成功，显示成功信息
                response_test = response_test.choices[0].message.content
                print("[INFO] 已成功接受到AI的回复")
                print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

                test_results[i] = 1 #记录成功结果

            #如果回复失败，抛出错误信息，并测试下一个key
            except Exception as e:
                print("[[red]Error[/]] key：",API_key_list[i],"请求出现问题！错误信息如下")
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
    def google_request_test(self, user_interface_prompter, base_url, api_key, model):

        print("[INFO] 正在测试Google接口",'\n')

        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model,'\n')

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
            model = genai.GenerativeModel(model_name=model,
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
                print("[[red]Error[/]] key：",API_key_list[i],"请求出现问题！错误信息如下")
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
    def anthropic_request_test(self, user_interface_prompter, base_url, api_key, model):
        
        print("[INFO] 正在测试Anthropic接口",'\n')

        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        #创建客户端
        client = anthropic.Anthropic(
            base_url=base_url,
            api_key=API_key_list[0]
        )



        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model,'\n')


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
                model= model,
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
                print("[[red]Error[/]] key：",API_key_list[i],"请求出现问题！错误信息如下")
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
    def cohere_request_test(self, user_interface_prompter, base_url, api_key, model):
        
        print("[INFO] 正在测试Cohere接口",'\n')

        #分割KEY字符串并存储进列表里,如果API_key_str中没有逗号，split(",")方法仍然返回一个只包含一个元素的列表
        API_key_list = api_key_str.replace('\n','').replace(" ", "").split(",")


        #创建openai客户端
        client = cohere.Client(api_key=API_key_list[0],
                base_url= base_url)


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model,'\n')

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
                model= model,
                message = "小可爱，你在干嘛" ,
                ) 

                #如果回复成功，显示成功信息
                response_test = response_test.text
                print("[INFO] 已成功接受到AI的回复")
                print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')

                test_results[i] = 1 #记录成功结果

            #如果回复失败，抛出错误信息，并测试下一个key
            except Exception as e:
                print("[[red]Error[/]] key：",API_key_list[i],"请求出现问题！错误信息如下")
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
    def sakura_request_test(self, user_interface_prompter, base_url, api_key, model):

        print("[INFO] 正在测试Sakura接口",'\n')

        #检查一下请求地址尾部是否为/v1，自动补全
        if base_url[-3:] != "/v1":
            base_url = base_url + "/v1"

        #创建openai客户端
        openaiclient = OpenAI(api_key="sakura",
                base_url= base_url)


        print("[INFO] 请求地址是:",base_url,'\n')
        print("[INFO] 模型选择是:",model,'\n')



        #构建发送内容
        messages_test = [{"role": "system","content":"你是一个轻小说翻译模型，可以流畅通顺地以日本轻小说的风格将日文翻译成简体中文，并联系上下文正确使用人称代词，不擅自添加原文中没有的代词。"},
                         {"role":"user","content":"将下面的日文文本翻译成中文：サポートキャスト"}]
        print("[INFO] 当前发送内容：\n", messages_test ,'\n')

        #尝试请求，并设置各种参数
        try:
            response_test = openaiclient.chat.completions.create( 
            model= model,
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
            print("[[red]Error[/]] 请求出现问题！错误信息如下")
            print(f"Error: {e}\n\n")
            print("[INFO] 模型通讯测试失败！！！！")
            user_interface_prompter.signal.emit("接口测试结果","测试失败",0)
