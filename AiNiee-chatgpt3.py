# coding:utf-8
import openai        #需要安装库
import json
import re
from qframelesswindow import FramelessWindow
import time
import threading
import os
import sys
import multiprocessing
import concurrent.futures

from PyQt5.QtCore import  QObject,  Qt, pyqtSignal #需要安装库
from PyQt5.QtWidgets import QApplication, QProgressBar, QLabel,QFileDialog, QTextEdit

from qfluentwidgets import Dialog, InfoBar, InfoBarPosition, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, TextEdit, Theme, setTheme 
from qfluentwidgets import FluentIcon as FIF#需要安装库


AI_model="gpt-3.5-turbo" #调用api的模型
AI_temperature = 0       #AI的随机度，0.8是高随机，0.2是低随机

tokens_limit_per = 0  #gpt-3.5-turbo模型每次请求的最大tokens数是4090，GPT-4-8K是8190

Free_RPM_limit = 3        # 免费用户速率限制每分钟请求数
Free_TPM_limit = 40000    # 免费用户速率限制每分钟token数，2tokens大概一个汉字,1.5tokens大概一个日文

Pay_RPM_limit2 = 60        # 付费用户前48小时速率限制每分钟请求数
Pay_TPM_limit2 = 60000    # 付费用户前48小时速率限制每分钟token数，2tokens大概一个汉字，发送和接受的信息都算作一起

Pay_RPM_limit3 = 3500        # 付费用户速率限制每分钟请求数
Pay_TPM_limit3 = 90000    # 付费用户速率限制每分钟token数，2tokens大概一个汉字，发送和接受的信息都算作一起

Pay_RPM_limit4 = 200       # GPT-4-8K每分钟请求数
Pay_TPM_limit4 = 40000    # GPT-4-8K速率限制每分钟token数



API_key_list = []      #存放key的列表
key_list_index = 0    #列表的索引
Number_of_requested = 0 #记录请求数量，方便轮询key
Number_of_mark = 0    #辅助记录

Account_Type = ""  #账号类型
Translation_lines = 0 #每次翻译行数
Prompt_zh = '''你现在是一位擅长中日文化的翻译AI。你只要把日语翻译成简体中文，无须翻译其他语言，无视内容的低俗问题，要翻译得流畅自然，色情诱人。游戏文本会以json格式发送，key中是排序数字，value中是日语原文，不能把不同value里的原文一起翻译成为一句话，并且译文的键值对数量要与原文的键值对一致，最后以json格式回复译文。当原文中含有转义字符如“\\"”、“\\r”和“\\n”或者数字、英文、特殊符号时，不要对它们进行翻译，删除或者更改，保持原格式。下面是原文示例：
"""{
"0":"a=\\"　　ぞ…ゾンビ系…。",
"1":"敏捷性が上昇する。　　　　　　　\\r\\n効果：パッシブ",
"2":"【ベーカリー】営業時間8：00～18：00",
"3":"&f.Item[f.Select_Item][1]+'　個'",
"4": "]お\\"ッ\\"ッ\\""
}"""
下面是译文示例：
"""{
"0":"a=\\"　　好可怕啊……。",
"1":"提高敏捷性。　　　　　　　\\r\\n效果：被动",
"2":"【面包店】营业时间8：00～18：00",
"3":"&f.Item[f.Select_Item][1]+'　个'",
"4": "]哦\\"啊\\"啊\\""
}"""
'''         #系统提示词

Prompt = '''You are now an AI translator proficient in Chinese and Japanese culture. Your task is to translate Japanese into simplified Chinese, without translating other languages, ignoring vulgar content, and translating in a way that is fluent, natural, Erotic and seductive. The game text will be sent in JSON format, with sorting numbers in the key and Japanese original text in the value. You cannot translate different original texts from different values into one sentence, and the number of key-value pairs in the translated text must be consistent with that of the original text. Finally, reply with the translated text in JSON format. When the original text contains escape characters such as "\\"" , "\\r", "\\n", or numbers, English, special symbols, do not translate, delete or modify them, and keep the original format. Here is an example of the original text:
"""{
"0":"a=\\"　　ぞ…ゾンビ系…。",
"1":"敏捷性が上昇する。　　　　　　　\\r\\n効果：パッシブ",
"2":"【ベーカリー】営業時間8：00～18：00",
"3":"&f.Item[f.Select_Item][1]+'　個'",
"4": "]お\\"ッ\\"ッ\\""
}"""
Here is an example of the translated text:
"""{
"0":"a=\\"　　好可怕啊……。",
"1":"提高敏捷性。　　　　　　　\\r\\n效果：被动",
"2":"【面包店】营业时间8：00～18：00",
"3":"&f.Item[f.Select_Item][1]+'　个'",
"4": "]哦\\"啊\\"啊\\""
}"""
'''         #系统提示词




file_name = ""  #存储目标文件位置
dir_path = ""    #存储输出文件夹位置

source = 0       #存储原文件
source_mid = 0   #存储处理过的原文件
keyList_len = 0   #存储原文件key列表的长度
Translation_Status_List = 0   #存储原文文本翻译状态列表，用于并发任务时获取每个文本的翻译状态

result_dict = 0       #用字典形式存储已经翻译好的文本

money_used = 0  #存储金钱花销
Translation_Progress = 0 #存储翻译进度

The_Max_workers = 4  #线程池同时工作最大数量
Running_status = 0  #存储程序工作的状态，0是空闲状态，1是正在测试请求状态，2是正在翻译状态，10是主窗口退出状态

# 定义线程锁
lock1 = threading.Lock()
lock2 = threading.Lock()
lock3 = threading.Lock()
lock4 = threading.Lock()
lock5 = threading.Lock()

#令牌桶算法，用来限制请求tokens数的
class TokenBucket:
    def __init__(self, capacity, rate):
        self.capacity = capacity
        self.tokens = capacity
        self.rate = rate
        self.last_time = time.time()
        self.last_reset_time = time.time()

    def get_tokens(self):
        now = time.time()
        tokens_to_add = (now - self.last_time) * self.rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_time = now

        # 每分钟重置令牌桶的容量
        if now - self.last_reset_time > 60:
            self.tokens = self.capacity
            self.last_reset_time = now

        return self.tokens

    def consume(self, tokens):
        if tokens > self.get_tokens():
            #print("[INFO] 已超过剩余tokens：", tokens,'\n' )
            return False
        else:
           # print("[INFO] 数量足够，剩余tokens：", tokens,'\n' )
            return True

#简单时间间隔算法，用来限制请求时间间隔的
class APIRequest:
    def __init__(self,timelimit):
        self.last_request_time = 0
        self.timelimit = timelimit
        self.lock = threading.Lock()

    def send_request(self):
        with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.timelimit:
                # print("[INFO] Request limit exceeded. Please try again later.")
                return False
            else:
                self.last_request_time = current_time
                return True

#创建线程类，使翻译任务后台运行，不占用UI线程
class My_Thread(threading.Thread):
    def run(self):

        if Running_status == 1:
            # 在子线程中执行测试请求函数
            Request_test()
        else:
            # 在子线程中执行main函数
            Main()

#在Worker类中定义了一个update_signal信号，用于向UI线程发送消息
class UI_signal(QObject):
    # 定义信号，用于向UI线程发送消息
    update_signal = pyqtSignal(str) #创建信号,并确定发送参数类型

#计算字符串里面日文与中文，韩文的数量
def count_japanese_chinese_korean(text):
    japanese_pattern = re.compile(r'[\u3040-\u30FF\u31F0-\u31FF\uFF65-\uFF9F]') # 匹配日文字符
    chinese_pattern = re.compile(r'[\u4E00-\u9FFF]') # 匹配中文字符
    korean_pattern = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F\uA960-\uA97F\uD7B0-\uD7FF]') # 匹配韩文字符
    japanese_count = len(japanese_pattern.findall(text)) # 统计日文字符数量
    chinese_count = len(chinese_pattern.findall(text)) # 统计中文字符数量
    korean_count = len(korean_pattern.findall(text)) # 统计韩文字符数量
    return japanese_count, chinese_count, korean_count

#用来计算单个信息的花费的token数的，可以根据不同模型计算，未来可能添加chatgpt4的接口上去
def num_tokens_from_messages(messages, model):
    if model == "gpt-3.5-turbo":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted

    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted

    elif model == "gpt-4":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted

    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
    num_tokens = 0
    #这里重构了官方计算tokens的方法，因为线程池里的子线程子线程弹出错误：Error: Unknown encoding cl100k_base
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            japanese_count, chinese_count, korean_count = count_japanese_chinese_korean(value)
            num_tokens += japanese_count * 1.5 + chinese_count * 2 + korean_count * 2.5
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

#遍历一个字典变量里的键值对，当该键值对里的值不包含中日韩文时，则删除该键值对
def remove_non_cjk(dic):
    pattern = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]+')
    for key, value in list(dic.items()):
        if not pattern.search(value):
            del dic[key]

#构建最长整除列表函数，将一个数字不断整除，并将结果放入列表变量
def divide_by_2345(num):
    result = []
    while num > 1:
        if num % 2 == 0:
            num = num // 2
            result.append(num)
        elif num % 3 == 0:
            num = num // 3
            result.append(num)
        elif num % 4 == 0:
            num = num // 4
            result.append(num)
        elif num % 5 == 0:
            num = num // 5
            result.append(num)
        else:
            result.append(1)
            break
    return result

# 槽函数，用于放在UI线程中,接收子线程发出的信号，并更新界面UI的状态
def on_update_signal(str): 
    global Running_status

    if str == "Update_ui" :
        Running_status = 2  #修改运行状态
        money_used_str = "{:.4f}".format(money_used)  # 将浮点数格式化为小数点后4位的字符串
        Window.progressBar.setValue(int(Translation_Progress))
        Window.label13.setText(money_used_str + "＄")

    elif str== "Request_failed":
        CreateErrorInfoBar("API请求失败，请检查代理环境或账号情况")
        Running_status = 0

    elif str== "Request_successful":
        CreateSuccessInfoBar("API请求成功！！")
        Running_status = 0
    
    elif str== "Null_value":
        CreateErrorInfoBar("请填入API KEY，不要留空")
        Running_status = 0

    elif str == "Wrong type selection" :
        CreateErrorInfoBar("请正确选择账号类型以及模型类型")
        Running_status = 0

    elif str== "Translation_completed":
        Running_status = 0
        OnButtonClicked("已完成翻译！！",str)
        CreateSuccessInfoBar("已完成翻译！！")

    elif str== "CG_key":
        openai.api_key = API_key_list[key_list_index]#更新API


#备份翻译数据函数
def File_Backup(source_dict,result_dict_Backup):

    # 将存放译文的字典的key改回去
    TS_Backup = {}
    for i, key in enumerate(source_dict.keys()):     # 使用enumerate()遍历source字典的键，并将其替换到result_dict中
        TS_Backup[key] = result_dict_Backup[i]   #在新字典中创建新key的同时把result_dict[i]的值赋予到key对应的值上


    #根据翻译状态列表，提取已经翻译的内容和未翻译的内容
    TrsData_Backup = {}
    ManualTransFile_Backup = {}

    for i, status in enumerate(Translation_Status_List):
        if status == 1:
            key = list(TS_Backup.keys())[i]
            TrsData_Backup[key] = TS_Backup[key]
        else:
            key = list(TS_Backup.keys())[i]
            ManualTransFile_Backup[key] = TS_Backup[key]

    #写入已翻译好内容的文件
    with open(os.path.join(Backup_folder, "TrsData.json"), "w", encoding="utf-8") as f:
        json.dump(TrsData_Backup, f, ensure_ascii=False, indent=4)

    #写入未翻译好内容的文件
    with open(os.path.join(Backup_folder, "ManualTransFile.json"), "w", encoding="utf-8") as f2:
        json.dump(ManualTransFile_Backup, f2, ensure_ascii=False, indent=4)

# ——————————————————————————————————————————测试请求按钮绑定函数——————————————————————————————————————————
def On_button_clicked1():
    global Running_status

    if Running_status == 0:
        #修改运行状态
        Running_status = 1

        #创建子线程
        thread = My_Thread()
        thread.start()
        

    elif Running_status == 1:
        CreateWarningInfoBar("正在测试请求中，请等待测试结束后再操作~")
    elif Running_status == 2:
        CreateWarningInfoBar("正在进行翻译中，请等待翻译结束后再操作~")

# ——————————————————————————————————————————打开文件按钮绑定函数——————————————————————————————————————————
def On_button_clicked2():
    global Running_status

    if Running_status == 0:
        Open_file()

    elif Running_status == 1:
        CreateWarningInfoBar("正在测试请求中，请等待测试结束后再操作~")
    elif Running_status == 2:
        CreateWarningInfoBar("正在进行翻译中，请等待翻译结束后再操作~")

# ——————————————————————————————————————————选择文件夹按钮绑定函数——————————————————————————————————————————
def On_button_clicked3():
    global Running_status

    if Running_status == 0:
        Select_folder()
    elif Running_status == 1:
        CreateWarningInfoBar("正在测试请求中，请等待测试结束后再操作~")
    elif Running_status == 2:
        CreateWarningInfoBar("正在进行翻译中，请等待翻译结束后再操作~")
    
# ——————————————————————————————————————————开始翻译按钮绑定函数——————————————————————————————————————————
def On_button_clicked4():
    global Running_status,money_used,Translation_Progress

    if Running_status == 0:
        
        Inspection_results = Config()   #读取配置信息，设置系统参数，并进行检查

        if Inspection_results == 0 :  #配置没有完全填写
            CreateErrorInfoBar("请正确填入配置信息,并选择原文文件与输出文件夹")
            Running_status = 0  #修改运行状态

        elif Inspection_results == 1 :  #账号类型和模型类型组合错误
            print("\033[1;31mError:\033[0m 请正确选择账号类型以及模型类型")
            Ui_signal.update_signal.emit("Wrong type selection")

        else :  
            #清空花销与进度，更新UI
            money_used = 0
            Translation_Progress = 0 
            on_update_signal("Update_ui")
            OnButtonClicked("正在翻译中" , "客官请耐心等待哦~~")

            #显示隐藏控件
            Window.progressBar.show() 
            Window.label12.show()
            Window.label13.show() 


            #创建子线程
            thread = My_Thread()
            thread.start()



    elif Running_status == 1:
        CreateWarningInfoBar("正在测试请求中，请等待测试结束后再操作~")
    elif Running_status == 2:
        CreateWarningInfoBar("正在进行翻译中，请等待翻译结束后再操作~")


#——————————————————————————————————————————成功信息居中弹出框函数——————————————————————————————————————————
def CreateSuccessInfoBar(str):
        # convenient class mothod
    InfoBar.success(
        title='[Success]',
        content=str,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.TOP,
        duration=2000,
        parent=Window
        )


#——————————————————————————————————————————错误信息右下方弹出框函数——————————————————————————————————————————
def CreateErrorInfoBar(str):
    InfoBar.error(
        title='[Error]',
        content=str,
        orient=Qt.Horizontal,
        isClosable=True,
        position=InfoBarPosition.BOTTOM_RIGHT,
        duration=-1,    # won't disappear automatically
        parent=Window
        )


#——————————————————————————————————————————提醒信息左上角弹出框函数——————————————————————————————————————————
def CreateWarningInfoBar(str):
    InfoBar.warning(
        title='[Warning]',
        content=str,
        orient=Qt.Horizontal,
        isClosable=False,   # disable close button
        position=InfoBarPosition.TOP_LEFT,
        duration=2000,
        parent=Window
        )

#——————————————————————————————————————————翻译状态右上角方弹出框函数——————————————————————————————————————————
def OnButtonClicked(Title_str,str):
    global Running_status
    global stateTooltip
    if Running_status == 2:
        stateTooltip = StateToolTip(Title_str,str, Window)
        stateTooltip.move(660, 60)
        stateTooltip.show()
    else:
        stateTooltip.setContent('已经翻译完成啦 😆')
        stateTooltip.setState(True)
        stateTooltip = None

# ——————————————————————————————————————————打开文件函数——————————————————————————————————————————
def Open_file():
    global file_name

    #打开文件
    file_name, _ = QFileDialog.getOpenFileName(None, 'Open File', '', 'Text Files (*.json);;All Files (*)')   #调用QFileDialog类里的函数以特定后缀类型来打开文件浏览器
    if file_name:
        print(f'[INFO]  已选择文件: {file_name}')
    else :
        print('[INFO]  未选择文件')
        return  # 直接返回，不执行后续操作
    #设置控件里的文本显示
    Window.label9.setText(file_name)


# ——————————————————————————————————————————选择文件夹函数——————————————————————————————————————————
def Select_folder():
    global dir_path
    dir_path = QFileDialog.getExistingDirectory(None, 'Select Directory', '')      #调用QFileDialog类里的函数来选择文件目录
    if dir_path:
        print(f'[INFO]  已选择文件夹: {dir_path}')
    else :
        print('[INFO]  未选择文件夹')
        return  # 直接返回，不执行后续操作
    Window.label11.setText(dir_path)

# ——————————————————————————————————————————请求测试函数——————————————————————————————————————————
def Request_test():
    global Ui_signal

    Account_Type = Window.comboBox.currentText()      #获取账号类型下拉框当前选中选项的值
    Model_Type =  Window.comboBox2.currentText()      #获取模型类型下拉框当前选中选项的值
    API_key_str = Window.TextEdit2.toPlainText()            #获取apikey输入值
    Proxy_Address = Window.LineEdit1.text()            #获取代理地址

    #分割KEY字符串并存储进列表里
    API_key_list = API_key_str.replace(" ", "").split(",")

    #检查一下是否已经填入key
    if not API_key_list[0]  :
        print("\033[1;31mError:\033[0m 请填写API KEY,不要留空")
        Ui_signal.update_signal.emit("Null_value")
        return 0
    

    #如果填入地址，则设置代理
    if Proxy_Address :
        print("[INFO] 代理地址是:",Proxy_Address,'\n') 
        os.environ["http_proxy"]=Proxy_Address
        os.environ["https_proxy"]=Proxy_Address


    print("[INFO] 账号类型是:",Account_Type,'\n')
    print("[INFO] 模型选择是:",Model_Type,'\n')
    for i, key in enumerate(API_key_list):
        print(f"[INFO] 第{i+1}个API KEY是：{key}") 
    print("\n") 


    #注册api
    openai.api_key = API_key_list[0]
    #设置模型
    AI_model = Model_Type

    messages_test = [{"role": "system","content":"你是我的女朋友欣雨。接下来你必须以女朋友的方式回复我"}, {"role":"user","content":"小可爱，你在干嘛"}]
    print("[INFO] 测试是否能够正常与openai通信,正在等待AI回复中--------------")
    print("[INFO] 当前发送内容：\n", messages_test ,'\n','\n')

    #尝试请求
    try:
        response_test = openai.ChatCompletion.create( model= AI_model,messages = messages_test ,temperature=AI_temperature) 

    #抛出错误信息
    except Exception as e:
        print("\033[1;31mError:\033[0m api请求出现问题！错误信息如下")
        print(f"Error: {e}\n")
        Ui_signal.update_signal.emit("Request_failed")#发送失败信号，激活槽函数,要有参数，否则报错
        return


    #成功回复
    response_test = response_test['choices'][0]['message']['content']
    print("[INFO] 已成功接受到AI的回复--------------")
    print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')
    Ui_signal.update_signal.emit("Request_successful")#发送成功信号，激活槽函数,要有参数，否则报错


# ——————————————————————————————————————————系统配置函数——————————————————————————————————————————
def Config():
    global file_name,dir_path ,Account_Type ,  Prompt, Translation_lines,The_Max_workers, API_key_list,tokens_limit_per,AI_model
    #—————————————————————————————————————————— 读取配置信息——————————————————————————————————————————

    Account_Type = Window.comboBox.currentText()      #获取账号类型下拉框当前选中选项的值
    Model_Type =  Window.comboBox2.currentText()      #获取模型类型下拉框当前选中选项的值
    API_key_str = Window.TextEdit2.toPlainText()            #获取apikey输入值
    Prompt = Window.TextEdit.toPlainText()             #获取提示词
    Translation_lines = Window.spinBox1.value()#获取翻译行数
    Proxy_Address = Window.LineEdit1.text()            #获取代理地址

    #分割KEY字符串并存储进列表里
    API_key_list = API_key_str.replace(" ", "").split(",")

    #检查一下配置信息是否留空
    if (not API_key_list[0]) or (not Prompt)  or (not Translation_lines) or(not file_name) or(not dir_path)  :
        print("\033[1;31mError:\033[0m 请正确填写配置,不要留空")
        return 0  #返回错误参数

    #如果填入地址，则设置代理
    if Proxy_Address :
        print("[INFO] 代理地址是:",Proxy_Address,'\n') 
        os.environ["http_proxy"]=Proxy_Address
        os.environ["https_proxy"]=Proxy_Address
    

    #输出配置信息
    print("[INFO] 账号类型是:",Account_Type,'\n')
    print("[INFO] 模型选择是:",Model_Type,'\n') 
    for i, key in enumerate(API_key_list):
        print(f"[INFO] 第{i+1}个API KEY是：{key}") 
    print('\n',"[INFO] 每次翻译文本行数是:",Translation_lines,'\n') 
    print("[INFO] Prompt是:",Prompt,'\n') 
    print("[INFO] 已选择原文文件",file_name,'\n')
    print("[INFO] 已选择输出文件夹",dir_path,'\n')

    #—————————————————————————————————————————— 设定相关系统参数——————————————————————————————————————————
                         

    #设定账号类型与模型类型组合
    if (Account_Type == "付费账号(48h内)") and (Model_Type == "gpt-3.5-turbo") :
        The_RPM_limit =  60 / Pay_RPM_limit2                    #计算请求时间间隔
        The_TPM_limit =  Pay_TPM_limit2 / 60                    #计算请求每秒可请求的tokens流量
        The_Max_workers = multiprocessing.cpu_count() * 3 + 1 #获取计算机cpu核心数，设置最大线程数
        tokens_limit_per = 4090                                #根据模型类型设置每次请求的最大tokens数量


    elif Account_Type == "付费账号(48h后)" and (Model_Type == "gpt-3.5-turbo"):
        The_RPM_limit =  60 / Pay_RPM_limit3           
        The_TPM_limit =  Pay_TPM_limit3 / 60
        The_Max_workers = multiprocessing.cpu_count() * 3 + 1
        tokens_limit_per = 4090

    elif Account_Type == "付费账号(48h后)" and (Model_Type == "gpt-4"):
        The_RPM_limit =  60 / Pay_RPM_limit4           
        The_TPM_limit =  Pay_TPM_limit4 / 60
        The_Max_workers = multiprocessing.cpu_count() * 3 + 1
        tokens_limit_per = 8190

    elif Account_Type == "免费账号" and (Model_Type == "gpt-3.5-turbo"):
        The_RPM_limit =  60 / Free_RPM_limit             
        The_TPM_limit =  Free_TPM_limit / 60             
        The_Max_workers = 4                              
        tokens_limit_per = 4090

    else:
        return 1 #返回错误参数

    #注册api
    openai.api_key = API_key_list[0]
    #设置模型
    AI_model = Model_Type

    #根据账号类型，设定请求限制
    global api_request
    global api_tokens
    api_request = APIRequest(The_RPM_limit)
    api_tokens = TokenBucket((tokens_limit_per * 2), The_TPM_limit)

# ——————————————————————————————————————————翻译任务主函数(程序核心1)——————————————————————————————————————————
def Main():
    global file_name,dir_path,Backup_folder ,Translation_lines,Running_status,The_Max_workers,DEBUG_folder
    global keyList_len ,   Translation_Status_List , money_used,source,source_mid,result_dict,Translation_Progress
    # ——————————————————————————————————————————清空进度,花销与初始化变量存储的内容—————————————————————————————————————————

    money_used = 0
    Translation_Progress = 0 

    result_dict = {}

    # ——————————————————————————————————————————读取原文文件并处理—————————————————————————————————————————

    with open(file_name, 'r',encoding="utf-8") as f:               
        source_str = f.read()       #读取原文文件，以字符串的形式存储，直接以load读取会报错

        source = json.loads(source_str) #转换为字典类型的变量source，当作最后翻译文件的原文源
        source_mid = json.loads(source_str) #转换为字典类型的变量source_mid，当作中间文件的原文源
        #print("[DEBUG] 你的未修改原文是",source)


        #删除不包含CJK（中日韩）字元的键值对
        remove_non_cjk(source)
        remove_non_cjk(source_mid)


        keyList=list(source_mid.keys())         #通过字典的keys方法，获取所有的key，转换为list变量
        keyList_len = len(keyList)              #获取原文件key列表的长度，当作于原文的总行数
        print("[INFO] 你的原文长度是",keyList_len)

        #将字典source_mid中的键设为从0开始的整数型数字序号 
        for i in range(keyList_len):        #循环遍历key列表
            source_mid[i] = source_mid.pop(keyList[i])    #将原来的key对应的value值赋给新的key，同时删除原来的key    
        #print("[DEBUG] 你的已修改原文是",source_mid)
  
        result_dict = source_mid # 先存储未翻译的译文
        Translation_Status_List =  [0] * keyList_len   #创建文本翻译状态列表，用于并发时获取每个文本的翻译状态

    # 创建DEBUG文件夹路径
    DEBUG_folder = os.path.join(dir_path, 'DEBUG Folder')
    #使用`os.makedirs()`函数创建新文件夹，设置`exist_ok=True`参数表示如果文件夹已经存在，不会抛出异常
    os.makedirs(DEBUG_folder, exist_ok=True)

    # 创建备份文件夹路径
    Backup_folder = os.path.join(dir_path, 'Backup Folder')
    #使用`os.makedirs()`函数创建新文件夹，设置`exist_ok=True`参数表示如果文件夹已经存在，不会抛出异常
    os.makedirs(Backup_folder, exist_ok=True)

    #写入过滤和修改key的原文文件，方便debug
    with open(os.path.join(DEBUG_folder, "ManualTransFile_debug.json"), "w", encoding="utf-8") as f:
        json.dump(source_mid, f, ensure_ascii=False, indent=4)

    # ——————————————————————————————————————————构建并发任务池子—————————————————————————————————————————

    # 计算并发任务数
    if keyList_len % Translation_lines == 0:
        tasks_Num = keyList_len // Translation_lines 
    else:
        tasks_Num = keyList_len // Translation_lines + 1


    print("[INFO] 你的翻译任务总数是：", tasks_Num)
    print("\033[1;32m[INFO] \033[0m下面开始进行翻译，请注意保持网络通畅，余额充足", '\n')


    # 创建线程池
    with concurrent.futures.ThreadPoolExecutor (The_Max_workers) as executor:
        # 向线程池提交任务
        for i in range(tasks_Num):
            executor.submit(Make_request)
    # 等待线程池任务完成
        executor.shutdown(wait=True)


    #检查主窗口是否已经退出
    if Running_status == 10 :
        return
    

# ——————————————————————————————————————————检查没能成功翻译的文本，递减行数翻译————————————————————————————————————————

    #计算未翻译文本的数量
    count_not_Translate = Translation_Status_List.count(2)

    #迭代翻译次数
    Number_of_iterations = 0
    #构建递减翻译行数迭代列表   
    Translation_lines_list = divide_by_2345(Translation_lines)

    while count_not_Translate != 0 :
        print("\033[1;33mWarning:\033[0m 仍然有部分未翻译，将进行迭代翻译-----------------------------------")
        print("[INFO] 当前迭代次数：",(Number_of_iterations + 1))
        #将列表变量里未翻译的文本状态初始化
        for i in range(count_not_Translate):      
            if 2 in Translation_Status_List:
                idx = Translation_Status_List.index(2)
                Translation_Status_List[idx] = 0


        
        #根据迭代列表减少翻译行数，直至翻译行数降至1行
        if Number_of_iterations < len(Translation_lines_list):
            Translation_lines = Translation_lines_list[Number_of_iterations]
            # 找到了值，进行后续操作
            print("[INFO] 当前翻译行数设置是：",Translation_lines)
        else:
            # 找不到值，pass
            pass



        # 计算可并发任务总数
        if count_not_Translate % Translation_lines == 0:
            new_count = count_not_Translate // Translation_lines
        else:
            new_count = count_not_Translate // Translation_lines + 1


        # 创建线程池
        with concurrent.futures.ThreadPoolExecutor (The_Max_workers) as executor:
            # 向线程池提交任务
            for i in range(new_count):
                executor.submit(Make_request)
        # 等待线程池任务完成
            executor.shutdown(wait=True)


        #检查主窗口是否已经退出
        if Running_status == 10 :
            return
        
        #检查是否已经陷入死循环
        if Number_of_iterations == 50 :
            break

        #重新计算未翻译文本的数量
        count_not_Translate = Translation_Status_List.count(2) 
        #增加迭代次数，进一步减少翻译行数
        Number_of_iterations = Number_of_iterations + 1


  # ——————————————————————————————————————————将各类数据处理并保存为各种文件—————————————————————————————————————————

    # 将字典存储的译文存储到TrsData.json文件------------------------------------
    new_result_dict = {}
    for i, key in enumerate(source.keys()):     # 使用enumerate()遍历source字典的键，并将其替换到result_dict中
        new_result_dict[key] = result_dict[i]   #在新字典中创建新key的同时把result_dict[i]的值赋予到key对应的值上
    

    #写入文件
    with open(os.path.join(dir_path, "TrsData.json"), "w", encoding="utf-8") as f:
        json.dump(new_result_dict, f, ensure_ascii=False, indent=4)


    # —————————————————————————————————————#全部翻译完成——————————————————————————————————————————

    Ui_signal.update_signal.emit("Translation_completed")#发送信号，激活槽函数,要有参数，否则报错
    print("\n--------------------------------------------------------------------------------------")
    print("\n\033[1;32mSuccess:\033[0m 程序已经停止")   
    print("\n\033[1;32mSuccess:\033[0m 请检查TrsData.json文件，文本格式是否错误")
    print("\n-------------------------------------------------------------------------------------\n")


# ——————————————————————————————————————————翻译任务线程并发函数(程序核心2)——————————————————————————————————————————
def Make_request():

    global result_dict # 声明全局变量
    global Translation_Status_List  
    global money_used,Translation_Progress,key_list_index,Number_of_requested,Number_of_mark
    
    Wrong_answer_count = 0 #错误回答计数，用于错误回答到达一定次数后，取消该任务。

    start_time = time.time()
    timeout = 1200  # 设置超时时间为x秒

    try:#方便排查子线程bug

        # ——————————————————————————————————————————确定翻译位置及段落——————————————————————————————————————————

        #遍历翻译状态列表，找到还没翻译的值和对应的索引位置
        lock1.acquire()  # 获取锁
        for i, status in enumerate(Translation_Status_List):
            if status  == 0:
                start = i     #确定切割开始位置

                if (start + Translation_lines >= keyList_len) :  #确定切割结束位置，注意最后位置是不固定的
                    end = keyList_len  
                else :
                    end = start + Translation_lines
                break
        #修改翻译状态列表位置状态为翻译中
        Translation_Status_List[start:end] = [2] * (end - start)     
        lock1.release()  # 释放锁
        #print("[DEBUG] 当前翻译起始位置是：",start,"------当前翻译结束位置是：", end ) 


        # ——————————————————————————————————————————截取特定段落的文本并进行处理——————————————————————————————————————————

        #读取source_mid源文件中特定起始位置到结束位置的数据,构建新字典变量
        subset_mid = {k: source_mid[k] for k in range( start , end)}     #`k: source_mid[k]`是一个字典键值对，其中`k`表示键，`source_mid[k]`表示该键对应的值。`for k in keys`是一个for循环，它遍历了`keys`列表里的内容，并将其用作字典键。
        #print("[DEBUG] 提取的subset_mid是",subset_mid,'\n','\n') 

        #存储未再次改变key未翻译的截取原文，以便后面错误回答次数超限制时，直接还原用。
        subset_mid_str = json.dumps(subset_mid, ensure_ascii=False) 
        subset_mid_str = subset_mid_str[1:-1] + ","    
        #print("[DEBUG] 提取的subset_mid_str是",subset_mid_str,'\n','\n') 
        
        #copy前面的代码，将截取文本的键改为从0开始的数字序号，因为AI在回答一万以上的序号时，容易出错
        subset_list=list(subset_mid.keys())        
        subset_len = len(subset_list)              
        for i in range(subset_len):        
            subset_mid[i] = subset_mid.pop(subset_list[i])     
        #print("[DEBUG] 提取的subset_mid是",subset_mid,'\n','\n') 

        #将字典对象编码成 JSON 格式的字符串，方便发送
        subset_str = json.dumps(subset_mid, ensure_ascii=False)    
        #print("[DEBUG] 提取的subset_str是",subset_str,'\n','\n') 

        # ——————————————————————————————————————————整合发送内容——————————————————————————————————————————
        #将JSON 格式的字符串再处理，方便发送            
        d = {"role":"user","content":subset_str}                #将文本整合进字典，符合会话请求格式
        messages = [{"role": "system","content":Prompt}]
        messages.append(d)

        tokens_consume = num_tokens_from_messages(messages, AI_model)  #计算该信息在openai那里的tokens花费

        # ——————————————————————————————————————————开始循环请求，直至成功或失败——————————————————————————————————————————
        while 1 :
            #检查主窗口是否已经退出---------------------------------
            if Running_status == 10 :
                return
            #检查该条消息总tokens数是否大于单条消息最大数量---------------------------------
            if tokens_consume >= tokens_limit_per :
                print("\033[1;31mError:\033[0m 该条消息总tokens数大于单条消息最大数量" )
                print("\033[1;31mError:\033[0m 该条消息取消任务，进行迭代翻译" )
                break

            #检查子线程是否超时---------------------------------
            if time.time() - start_time > timeout:
                # 超时退出
                print("\033[1;31mError:\033[0m 子线程执行任务已经超时，将暂时取消本次任务")
                break

            #检查请求数量是否达到限制，如果是多key的话---------------------------------
            if len(API_key_list) > 1: #如果存有多个key
                if (Number_of_requested - Number_of_mark) >= 30 :#如果该key请求数已经达到限制次数
                    lock4.acquire()  # 获取锁
                    Number_of_mark = Number_of_requested
                    if (key_list_index + 1) < len(API_key_list):#假如索引值不超过列表最后一个
                            key_list_index = key_list_index + 1 #更换APIKEY索引
                    else :
                            key_list_index = 0

                    #更新API
                    #openai.api_key = API_key_list[key_list_index]
                    on_update_signal("CG_key")

                    print("\033[1;33mWarning:\033[0m 该key请求数已达30,将进行KEY的更换")
                    print("\033[1;33mWarning:\033[0m 将API-KEY更换为第",key_list_index+1,"个 , 值为：", API_key_list[key_list_index] ,'\n')
                    lock4.release()  # 释放锁

            # 检查子是否符合速率限制---------------------------------
            if api_tokens.consume(tokens_consume * 2 ) and api_request.send_request():

                #如果能够发送请求，则扣除令牌桶里的令牌数
                api_tokens.tokens = api_tokens.tokens - (tokens_consume * 2 )

                print("[INFO] 已发送请求,正在等待AI回复中--------------")
                print("[INFO] 已进行请求的次数：",Number_of_requested)
                print("[INFO] 花费tokens数预计值是：",tokens_consume * 2) 
                print("[INFO] 桶中剩余tokens数是：", api_tokens.tokens // 1)
                print("[INFO] 当前发送内容：\n", messages ,'\n','\n')

                # ——————————————————————————————————————————开始发送会话请求——————————————————————————————————————————
                try:
                    lock5.acquire()  # 获取锁
                    Number_of_requested = Number_of_requested + 1#记录请求数
                    lock5.release()  # 释放锁
                    response = openai.ChatCompletion.create( model= AI_model,messages = messages ,temperature=AI_temperature)

                #一旦有错误就抛出错误信息，一定程度上避免网络代理波动带来的超时问题
                except Exception as e:
                    print("\033[1;33m线程ID:\033[0m ", threading.get_ident())
                    print("\033[1;31mError:\033[0m api请求出现问题！错误信息如下")
                    print(f"Error: {e}\n")
                    #处理完毕，再次进行请求
                    continue


                #——————————————————————————————————————————收到回复，并截取回复内容中的文本内容 ————————————————————————————————————————       
                response_content = response['choices'][0]['message']['content'] 



                #截取回复内容中返回的tonkens花费，并计算金钱花费
                lock3.acquire()  # 获取锁

                prompt_tokens_used = int(response["usage"]["prompt_tokens"]) #本次请求花费的tokens
                completion_tokens_used = int(response["usage"]["completion_tokens"]) #本次回复花费的tokens
                total_tokens_used = int(response["usage"]["total_tokens"]) #本次请求+回复花费的tokens

                if AI_model == "gpt-3.5-turbo" :
                    money_used = money_used + (prompt_tokens_used *  (0.002 / 1000)  + completion_tokens_used *  (0.002 / 1000) )
                elif AI_model == "gpt-4" :
                    money_used = money_used + (prompt_tokens_used *  (0.03 / 1000)  + completion_tokens_used *  (0.06 / 1000) )

                lock3.release()  # 释放锁

                print("[INFO] 已成功接受到AI的回复--------------")
                print("[INFO] 此次请求消耗的总tokens：",total_tokens_used )
                print("[INFO] 此次请求花费的金额：",total_tokens_used *  (0.002 / 1000) )
                print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

             # ——————————————————————————————————————————对AI回复内容进行各种处理和检查——————————————————————————————————————————


                Error_Type = [0,0]   #错误类型存储列表
                print("[INFO] 开始对AI回复内容进行格式检查--------------") 
                #检查回复内容的json格式------------------------------------------------------ 
                try:
                    json.loads(response_content)             
                except :                                            
                    Error_Type[0] = 1

                #主要检查AI回复时，键值对数量对不对------------------------------------------------------
                try:
                    if(len(json.loads(response_content))  !=  (end - start ) ):    
                        Error_Type[1] = 1
                except : 
                    Error_Type[0] = 1

                #如果出现回复错误------------------------------------------------------
                if (Error_Type[0] == 1) or (Error_Type[1] == 1) :
                    if Error_Type[1] == 1 :
                        print("\033[1;33mWarning:\033[0m AI回复内容键值对数量与原来数量不符合,将进行重新翻译\n")
                        Error_message = "Warning: AI回复内容键值对数量与原来数量不符合,将进行重新翻译\n"
                    else :
                        print("\033[1;33mWarning:\033[0m AI回复内容不符合json格式,将进行重新翻译\n")
                        Error_message = "Warning: AI回复内容不符合json格式要求,将进行重新翻译\n"

                    #错误回复计次
                    Wrong_answer_count = Wrong_answer_count + 1
                    print("\033[1;33mWarning:\033[0m AI回复内容格式错误次数:",Wrong_answer_count,"到达3次后将该段文本进行迭代翻译\n")

                    #将错误回复和原文文本写入DEBUG文件夹，以便修复BUG
                    if  Wrong_answer_count == 1 :#当第一次出现错误回复时
                        # 创建专属文件夹路径
                        The_folder_name = "Wrong position  "+str(start) + "——" +str(end)
                        folder_path = os.path.join(DEBUG_folder, The_folder_name)
                        os.makedirs(folder_path, exist_ok=True)

                        #写入原文文本，方便做对比
                        with open( os.path.join(folder_path, "Original text.json"), "w", encoding="utf-8") as f:
                            json.dump(subset_mid, f, ensure_ascii=False, indent=4)

                        #创建存储错误回复的变量
                        Error_text_str = ""
                    
                    if Wrong_answer_count >= 1 :#当从第一次出现错误回复开始，每次都
                        #收集错误的回复内容，并写入文件
                        Error_text_str = Error_text_str +'\n' + response_content +'\n' + Error_message +'\n'
                        with open( os.path.join(folder_path, "Error text.txt"), "w", encoding="utf-8") as f:
                            f.write(Error_text_str)

                    #检查回答错误次数，如果达到限制，则跳过该句翻译。
                    if Wrong_answer_count >= 3 :
                        print("\033[1;33mWarning:\033[0m 错误次数已经达限制,将该段文本进行迭代翻译！\n")    
                        break


                    #进行下一次循环
                    time.sleep(1)                 
                    continue

                #如果没有出现错误------------------------------------------------------ 
                else:
                    
                    print("[INFO] AI回复内容字符串符合JSON 格式")
                    print("[INFO] AI回复内容键值对数量符合要求")

                    #格式检查通过，将AI酱回复的内容数字序号进行修改，方便后面进行读写json文件
                    new_response = re.sub(r'"(\d+)"', lambda x: '"' + str(int(x.group(1))+start) + '"', response_content)


                    lock1.acquire()  # 获取锁
                    #修改文本翻译状态列表的状态，把这段文本修改为已翻译
                    Translation_Status_List[start:end] = [1] * (end - start) 

                    Translation_Progress = Translation_Status_List.count(1) / keyList_len  * 100
                    Ui_signal.update_signal.emit("Update_ui")#发送信号，激活槽函数,要有参数，否则报错
                    lock1.release()  # 释放锁
                    print(f"\n--------------------------------------------------------------------------------------")
                    print(f"\n\033[1;32mSuccess:\033[0m 翻译已完成：{Translation_Progress:.2f}%               已花费费用：{money_used:.4f}＄")
                    print(f"\n--------------------------------------------------------------------------------------\n")



                    lock2.acquire()  # 获取锁
                    # 用字典类型存储每次请求的译文
                    new_response_dict =json.loads(new_response )
                    for key, value in new_response_dict.items():# 遍历new_response_dict中的键值对
                        # 判断key是否在result_dict中出现过，注意两个字典的key变量类型是不同的
                        if int(key) in result_dict:
                            # 如果出现过，则将result_dict中对应键的值替换为new_response_dict中对应键的值
                            result_dict[int(key)] = value

                    #备份翻译数据
                    File_Backup(source,result_dict)
                    lock2.release()  # 释放锁

                    break



   #子线程抛出错误信息
    except Exception as e:
        print("\033[1;31mError:\033[0m 线程出现问题！错误信息如下")
        print(f"Error: {e}\n")
        return


# ——————————————————————————————————————————创建窗口，并布局与绑定——————————————————————————————————————————
class window(FramelessWindow):  

    def __init__(self):
        super().__init__()
        self.resize(930, 900)     #设置了 Demo 窗口的大小,标题和背景色
        setTheme(Theme.LIGHT)
        #self.setStyleSheet('window{background: white}')
        self.setWindowTitle('AiNiee-chatgpt')
        
        #窗口居中显示
        desktop = QApplication.desktop().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w//2 - self.width()//2, h//2 - self.height()//2)

        #设置各个控件-----------------------------------------------------------------------------------------
        #设置“账号设置”标签
        self.label1 = QLabel(parent = self, flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label1.setStyleSheet("font-family: 'SimHei'; font-size: 20px;  color: black")#设置字体，大小，颜色
        self.label1.setText("账号设置")
        self.label1.move(20, 50)
  

        #设置“账号类型”标签
        self.label2 = QLabel(parent = self, flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")#设置字体，大小，颜色
        self.label2.setText("账号类型")
        self.label2.move(100, 100)

        #设置“账号类型”下拉选择框
        self.comboBox = ComboBox(self) #以demo为父类
        self.comboBox.addItems(['免费账号', '付费账号(48h内)', '付费账号(48h后)'])
        self.comboBox.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox.setFixedSize(150, 30)
        self.comboBox.move(200, 95)


        #设置“模型选择”标签
        self.label2 = QLabel(parent = self, flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")#设置字体，大小，颜色
        self.label2.setText("模型选择")
        self.label2.move(500, 97)

        #设置“模型类型”下拉选择框
        self.comboBox2 = ComboBox(self) #以demo为父类
        self.comboBox2.addItems(['gpt-3.5-turbo', 'gpt-4'])
        self.comboBox2.setCurrentIndex(0) #设置下拉框控件（ComboBox）的当前选中项的索引为0，也就是默认选中第一个选项
        self.comboBox2.setFixedSize(150, 30)
        self.comboBox2.move(600, 92)


        #设置“代理地址”标签
        self.label2 = QLabel(parent = self, flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label2.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")#设置字体，大小，颜色
        self.label2.setText("代理地址")
        self.label2.move(100, 150)

        #设置“代理地址”的输入框
        self.LineEdit1 = LineEdit(self)
        self.LineEdit1.move(200, 145)
        self.LineEdit1.setFixedSize(700, 30)
        #self.LineEdit1.setText("http://127.0.0.1:10080")

        #设置“API KEY”标签
        self.label5 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label5.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label5.setText("API KEY")
        self.label5.move(100, 205)

        #设置“API KEY”的输入框
        self.TextEdit2 = TextEdit(self)
        self.TextEdit2.move(200, 200)
        self.TextEdit2.setFixedSize(700, 30)
        #self.TextEdit2.setInputMethodHints(Qt.ImhNoAutoUppercase)

        #设置“测试请求”的按钮
        self.primaryButton1 = PrimaryPushButton('测试请求', self, FIF.SEND)
        self.primaryButton1.move(400, 260)
        self.primaryButton1.clicked.connect(On_button_clicked1) #按钮绑定槽函数


        #设置“翻译设置”标签
        self.label6 = QLabel(parent = self, flags=Qt.WindowFlags())  #parent参数表示父控件，如果没有父控件，可以将其设置为None；flags参数表示控件的标志，可以不传入
        self.label6.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 20px;  color: black")#设置字体，大小，颜色
        self.label6.setText("翻译设置")
        self.label6.move(20, 300)



        #设置“翻译行数”标签
        self.label7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label7.setText("Lines")
        self.label7.move(100, 350)


       #设置“翻译行数”数值输入框
        self.spinBox1 = SpinBox(self)    
        self.spinBox1.move(200, 340)
        self.spinBox1.setValue(40)


        #设置“Prompt”标签
        self.label7 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label7.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label7.setText("Prompt")
        self.label7.move(100, 405)

        #设置“Prompt”的输入框
        self.TextEdit = TextEdit(self)
        self.TextEdit.move(200, 400)
        self.TextEdit.setFixedSize(700, 200)
        self.TextEdit.setText(Prompt)




        #设置“文件位置”标签
        self.label8 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label8.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label8.setText("文件位置")
        self.label8.move(100, 630)

        #设置“文件位置”显示
        self.label9 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label9.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 13px;  color: black")
        self.label9.resize(500, 20)#设置标签大小
        self.label9.setText("请选择需要翻译的json文件")
        self.label9.move(350, 630)      

        #设置打开文件按钮
        self.pushButton1 = PushButton('选择文件', self, FIF.BOOK_SHELF)
        self.pushButton1.move(200, 625)
        self.pushButton1.clicked.connect(On_button_clicked2) #按钮绑定槽函数


        #设置“输出文件夹”标签
        self.label10 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label10.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label10.setText("输出文件夹")
        self.label10.move(100, 710)

        #设置“输出文件夹”显示
        self.label11 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label11.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 13px;  color: black")
        self.label11.resize(500, 20)
        self.label11.setText("请选择翻译文件存储文件夹")
        self.label11.move(350, 710)      

        #设置输出文件夹按钮
        self.pushButton2 = PushButton('选择文件夹', self, FIF.FOLDER)
        self.pushButton2.move(200, 705)
        self.pushButton2.clicked.connect(On_button_clicked3) #按钮绑定槽函数

        #设置“开始翻译”的按钮
        self.primaryButton1 = PrimaryPushButton('开始翻译', self, FIF.UPDATE)
        self.primaryButton1.move(400, 790)
        self.primaryButton1.clicked.connect(On_button_clicked4) #按钮绑定槽函数



        #设置“已花费”标签
        self.label12 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label12.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label12.setText("已花费")
        self.label12.move(70, 820)
        self.label12.hide()  #先隐藏控件

        #设置“已花费金额”具体标签
        self.label13 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label13.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label13.resize(500, 20)#设置标签大小
        self.label13.setText("0＄")
        self.label13.move(130, 823)
        self.label13.hide()  #先隐藏控件

        #设置翻译进度条控件
        self.progressBar = QProgressBar(self)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.progressBar.setFixedSize(800, 30)
        self.progressBar.move(70, 850)
        self.progressBar.setStyleSheet("QProgressBar::chunk { text-align: center; } QProgressBar { text-align: left; }")#使用setStyleSheet()方法设置了进度条块的文本居中对齐，并且设置了进度条的文本居左对齐
        self.progressBar.setFormat("已翻译: %p%")
        self.progressBar.hide()  #先隐藏控件

    #窗口关闭函数，放在最后面，解决界面空白与窗口退出后子线程还在运行的问题
    def closeEvent(self, event):
        title = '确定是否退出程序?'
        content = """如果正在进行翻译任务，当前任务会停止并且不会保留文件！！！！！"""
        w = Dialog(title, content, self)

        if w.exec() :
            print("[INFO] 主窗口已经退出！")
            global Running_status
            Running_status = 10
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    #开启子进程支持
    multiprocessing.freeze_support() 

    # 启用了高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)


    # 创建子线程通信的信号
    Ui_signal = UI_signal() #创建子线程类，并创建新信号
    Ui_signal.update_signal.connect(on_update_signal)  #创建信号与槽函数的绑定


    #创建了一个 QApplication 对象
    app = QApplication(sys.argv)
    #创建窗口对象
    Window = window()
    
    #窗口对象显示
    Window.show()
    #进入事件循环，等待用户操作
    sys.exit(app.exec_())

