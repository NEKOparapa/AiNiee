# coding:utf-8
import openai        #需要安装库
import json
import re
from qframelesswindow import FramelessWindow
import tiktoken      #需要安装库
import time
import threading
import concurrent.futures
import os
import sys

from PyQt5.QtCore import QObject,  Qt, pyqtSignal #需要安装库
from PyQt5.QtWidgets import QApplication,  QWidget, QProgressBar, QLabel,QFileDialog

from qfluentwidgets import Dialog, InfoBar, InfoBarPosition, SpinBox, ComboBox, LineEdit, PrimaryPushButton, PushButton ,StateToolTip, Theme, setTheme 
from qfluentwidgets import FluentIcon as FIF#需要安装库



AI_model="gpt-3.5-turbo" #调用api的模型
AI_temperature = 1       #AI的随机度，0.8是高随机，0.2是低随机

tokens_limit_per = 4090  #gpt-3.5-turbo模型每次请求的最大tokens数

Free_RPM_limit = 3        # 免费用户速率限制每分钟请求数
Free_TPM_limit = 40000    # 免费用户速率限制每分钟token数，2tokens大概一个汉字

Pay_RPM_limit2 = 60        # 付费用户前48小时速率限制每分钟请求数
Pay_TPM_limit2 = 60000    # 付费用户前48小时速率限制每分钟token数，2tokens大概一个汉字，发送和接受的信息都算作一起

Pay_RPM_limit3 = 3500        # 付费用户速率限制每分钟请求数
Pay_TPM_limit3 = 90000    # 付费用户速率限制每分钟token数，2tokens大概一个汉字，发送和接受的信息都算作一起


Account_Type = ""  #账号类型
API_key = ""       #key
Prompt = ""         #系统提示词
Translation_lines = 0 #每次翻译行数

file_name = ""  #存储目标文件位置
dir_path = ""    #存储输出文件夹位置

source = 0       #存储原文件
source_mid = 0   #存储处理过的原文件
keyList_len = 0   #存储原文件key列表的长度
Translation_Status_List = 0   #存储原文文本翻译状态列表，用于并发任务时获取每个文本的翻译状态


result_str = ""      #存储已经翻译好的文本，最终用
result_str = '{'  + '\n' + result_str  # 在开头添加 `{`

Failure_translate_str = ""      #存储未能成功翻译的文本
Failure_translate_str = '{'  + '\n' + Failure_translate_str  # 在开头添加 `{`

money_used = 0  #存储金钱花销
Translation_Progress = 0 #存储翻译进度

The_Max_workers = 0  #线程池同时工作最大数量
Running_status = 0  #存储程序工作的状态，0是空闲状态，1是正在测试请求状态，2是正在翻译状态，10是主窗口退出状态

# 定义锁
lock1 = threading.Lock()
lock2 = threading.Lock()
lock3 = threading.Lock()



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
           # print("[INFO] 数量不足，剩余tokens：", tokens,'\n' )
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
class MainThread(threading.Thread):
    def run(self):

        if Running_status == 1:
            # 在子线程中执行测试请求函数
            Request_test()
        else:
            # 在子线程中执行main函数
            Main()

#在Worker类中定义了一个update_signal信号，用于向UI线程发送消息
class Worker(QObject):
    # 定义信号，用于向UI线程发送消息
    update_signal = pyqtSignal(str) #创建信号,并确定发送参数类型

#用来计算单个信息的花费的token数的，可以根据不同模型计算，未来可能添加chatgpt4的接口上去
def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301"):
    """Returns the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model) #使用 `tiktoken.encoding_for_model()` 函数加载一个编码器，该编码器可以将文本字符串转换为一组 token
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model == "gpt-3.5-turbo":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
        #print("Warning: gpt-3.5-turbo may change over time. Returning num tokens assuming gpt-3.5-turbo-0301.")
        #return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0301")
    elif model == "gpt-4":
        #print("Warning: gpt-4 may change over time. Returning num tokens assuming gpt-4-0314.")
        return num_tokens_from_messages(messages, model="gpt-4-0314")
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif model == "gpt-4-0314":
        tokens_per_message = 3
        tokens_per_name = 1
    else:
        raise NotImplementedError(f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens.""")
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens

# 槽函数，用于放在UI线程中,接收子线程发出的信号，并更新界面UI的状态
def on_update_signal(str): 
    global Running_status

    if str == "Being_translated" :
        money_used_str = "{:.4f}".format(money_used)  # 将浮点数格式化为小数点后4位的字符串
        Window.progressBar.setValue(int(Translation_Progress))
        Window.label13.setText(money_used_str + "＄")

    elif str== "Request_failed":
        CreateErrorInfoBar("API请求失败，请检查代理环境或账号情况")
        Running_status = 0

    elif str== "Request_successful":
        CreateSuccessInfoBar("API请求成功！！")
        Running_status = 0
    else :
        OnButtonClicked("已完成翻译！！",str)
        CreateSuccessInfoBar("已完成翻译！！")

# ——————————————————————————————————————————测试请求按钮绑定函数——————————————————————————————————————————
def On_button_clicked1():
    global Running_status

    if Running_status == 0:
        #修改运行状态
        Running_status = 1

        #创建子线程
        thread = MainThread()
        thread.start()
        
        # 创建子线程通信的信号
        global worker
        worker = Worker() #创建子线程类，并创建新信号
        worker.update_signal.connect(on_update_signal)  #创建信号与槽函数的绑定

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
    global Running_status

    if Running_status == 0:

        #清空进度与花销
        global money_used,Translation_Progress
        money_used = 0 
        Translation_Progress = 0 
        on_update_signal("Being_translated")

        if Config()==0 :  #读取配置信息，设置系统参数，并检查是否填写了配置
            CreateErrorInfoBar("请正确填入配置信息,并选择原文文件与输出文件夹")
            Running_status = 0  #修改运行状态


        else :  
            Running_status = 2  #修改运行状态
            OnButtonClicked("正在翻译中" , "客官请耐心等待哦~~")

            #显示隐藏控件
            Window.progressBar.show() 
            Window.label12.show()
            Window.label13.show()  
            #创建子线程
            thread = MainThread()
            thread.start()

            # 创建子线程通信的信号
            global worker
            worker = Worker() #创建子线程类，并创建新信号
            worker.update_signal.connect(on_update_signal)  #创建信号与槽函数的绑定

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
        stateTooltip.move(640, 20)
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
    global Running_status

    Account_Type = Window.comboBox.currentText()      #获取账号类型下拉框当前选中选项的值
    API_key = Window.LineEdit1.text()            #获取apikey输入值

    print("[INFO] 你的账号类型是:",Account_Type,'\n') 
    print("[INFO] 你的API_key是:",API_key,'\n',) 

    #注册api
    openai.api_key = API_key 

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
        worker.update_signal.emit("Request_failed")#发送失败信号，激活槽函数,要有参数，否则报错
        return


    #成功回复
    response_test = response_test['choices'][0]['message']['content']
    print("[INFO] 已成功接受到AI的回复--------------")
    print("[INFO] AI回复的文本内容：\n",response_test ,'\n','\n')
    worker.update_signal.emit("Request_successful")#发送成功信号，激活槽函数,要有参数，否则报错


# ——————————————————————————————————————————系统配置函数——————————————————————————————————————————
def Config():
    global file_name,dir_path ,Account_Type , API_key,  Prompt, Translation_lines,Running_status,The_Max_workers
    global keyList_len ,result_str ,  Failure_translate_str ,  Translation_Status_List , money_used
    #—————————————————————————————————————————— 读取配置信息——————————————————————————————————————————

    Account_Type = Window.comboBox.currentText()      #获取账号类型下拉框当前选中选项的值
    API_key = Window.LineEdit1.text()            #获取apikey输入值
    Prompt = Window.LineEdit2.text()             #获取提示词
    Translation_lines = Window.spinBox1.value()#获取翻译行数

    #检查一下配置信息是否留空
    if (not API_key) or (not Prompt) or (not Account_Type) or (not Translation_lines) or(not file_name) or(not dir_path)  :
        print("\033[1;31mError:\033[0m 请正确填写配置,不要留空")
        return 0

    #输出配置信息
    print("[INFO] 你的账号类型是:",Account_Type,'\n') 
    print("[INFO] 你的API_key是:",API_key,'\n',) 
    print("[INFO] 每次翻译文本行数是:",Translation_lines,'\n') 
    print("[INFO] 你的Prompt是:",Prompt,'\n') 
    print("[INFO] 已选择原文文件",file_name,'\n')
    print("[INFO] 已选择输出文件夹",dir_path,'\n')

    #—————————————————————————————————————————— 设定相关系统参数——————————————————————————————————————————
    #注册api
    openai.api_key = API_key                            

    #设定账号类型
    if Account_Type == "付费账号(48h内)" :
        The_RPM_limit =  60 / Pay_RPM_limit2           
        The_TPM_limit =  Pay_TPM_limit2 / 60
        The_Max_workers = 20


    elif Account_Type == "付费账号(48h后)" :
        The_RPM_limit =  60 / Pay_RPM_limit3           
        The_TPM_limit =  Pay_TPM_limit3 / 60
        The_Max_workers = 30

    else :
        The_RPM_limit =  60 / Free_RPM_limit             #计算请求时间间隔
        The_TPM_limit =  Free_TPM_limit / 60             #计算请求每秒可请求的tokens流量
        The_Max_workers = 4                              #设定最大并行任务数


    #根据账号类型，设定请求限制

    global api_request
    global api_tokens
    api_request = APIRequest(The_RPM_limit)
    api_tokens = TokenBucket((tokens_limit_per * 1.9), The_TPM_limit)

# ——————————————————————————————————————————翻译任务主函数(程序核心1)——————————————————————————————————————————
def Main():
    global file_name,dir_path ,Account_Type , API_key,  Prompt, Translation_lines,Running_status,The_Max_workers #以后再删，尴尬
    global keyList_len ,result_str ,  Failure_translate_str ,  Translation_Status_List , money_used,source,source_mid


    # ——————————————————————————————————————————读取原文文件并处理—————————————————————————————————————————
    with open(file_name, 'r',encoding="utf-8") as f:               
        source_str = f.read()       #一次性读取文本中全部的内容，以字符串的形式返回结果


        source = json.loads(source_str) #转换为json格式，当作最后翻译文件的原文源
        source_mid = json.loads(source_str) #转换为json格式，当作中间文件的原文源
    



        keyList=list(source_mid.keys())         #通过keys方法，获取所有的key，返回值为一个可迭代对象，并转换为list变量
        keyList_len = len(keyList)              #获取原文件key列表的长度
        print("[INFO] 你的原文长度是",keyList_len)


        for i in range(keyList_len):  #将原始字典source_mid中的键设为从0开始的数字序号 str(i)
            source_mid[str(i)] = source_mid.pop(keyList[i])        
        # print("[INFO] 你的原文是",source_mid)

        Translation_Status_List =  [0] * keyList_len   #创建文本翻译状态列表，用于并发时获取每个文本的翻译状态

    # ——————————————————————————————————————————构建并发任务池子—————————————————————————————————————————

    # 计算并发任务数
    if keyList_len % Translation_lines == 0:
        tasks_Num = keyList_len // Translation_lines 
    else:
        tasks_Num = keyList_len // Translation_lines + 1


    print("[INFO] 你的总任务数是：", tasks_Num)
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

    # ——————————————————————————————————————————将翻译文本改变格式写入中间件——————————————————————————————————————————
        
    result_str_mid = result_str[:-1] + '\n' + '}'             #变成json格式，准备写入中间件

    with open(os.path.join(dir_path, "translation_mid.json"), "w", encoding="utf-8") as f:
        f.write(result_str_mid)


    # ——————————————————————————————————————————将未能翻译文本输出为文件保存——————————————————————————————————————————
    Failure_translate_str  = Failure_translate_str[:-1] + '\n' + '}'
    with open( os.path.join(dir_path, "Failure_to_translate.json"), "w", encoding="utf-8") as f:
        f.write(Failure_translate_str)

    # ——————————————————————————————————————将翻译文本修改key，再写入最后的译文保存文件——————————————————————————————————————————

    with open(os.path.join(dir_path, "translation_mid.json"), "r",encoding="utf-8") as f:               
        source_last_str = f.read()                  #一次性读取json文本中全部的内容，以字符串的形式返回结果
        source_last = json.loads(source_last_str)    #字符串转换为json格式，当作最后翻译文件的原文源

    n = 0
    for key, value in source.items():
        source[key] = source_last[str(n)]
        n = n + 1

    # 将更新后的 source字典 写入json文件
    file_path = os.path.join(dir_path, "TrsData.json") #拼接文件名和路径
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=4)

    #删除中间件
    os.remove(os.path.join(dir_path, "translation_mid.json"))

    #修改运行状态
    Running_status = 0
    worker.update_signal.emit("Translation_completed")#发送信号，激活槽函数,要有参数，否则报错
    # —————————————————————————————————————#全部翻译完成——————————————————————————————————————————

    print("\n--------------------------------------------------------------------------------------")
    print("\n\033[1;32mSuccess:\033[0m 程序已经停止")   
    print("\n\033[1;32mSuccess:\033[0m 请检查TrsData.json文件，文本格式是否错误")
    print("\n-------------------------------------------------------------------------------------\n")


# ——————————————————————————————————————————翻译任务线程并发函数(程序核心2)——————————————————————————————————————————

def Make_request():

    global result_str  # 声明全局变量
    global Failure_translate_str
    global Translation_Status_List  
    global money_used,Translation_Progress

    #方便排查子线程bug
    try:
        Wrong_answer_count = 0 #错误回答计数，用于错误回答到达一定次数后，取消该任务。

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
        

        #读取source_mid源文件中特定起始位置到结束位置的数据
        keys = list(source_mid.keys())[start:end]         #将`source_mid`的所有键转换为列表变量，然后使用切片语法`[start:end]`选取指定范围内的键，存储到`keys`变量中
        subset_mid = {k: source_mid[k] for k in keys}     #`k: source_mid[k]`是一个字典键值对，其中`k`表示键，`source_mid[k]`表示该键对应的值。`for k in keys`是一个for循环，它遍历了`keys`列表中的每个键，并将其用作字典键。



        #存储未再次改变key未翻译的截取原文，以便后面错误回答次数超限制时，直接还原用。
        subset_mid_str = json.dumps(subset_mid, ensure_ascii=False) 
        subset_mid_str = subset_mid_str[1:-1] + ","    

        #改截取文本subset_mid的key为从0到截取长度结束的数字序号，因为AI酱对一万以上的数字排列不是很理解，回复又慢又容易出错
        subset_mid = {j: subset_mid[k] for j, k in enumerate(subset_mid)} #使用`enumerate()`函数遍历`subset_mid`字典中的键值对，将键值对的索引值存储到`i`变量中，将键存储到`k`变量中。
        subset_mid = {j: subset_mid[j] for j in range( 0, (end - start) )}  #使用一个for循环遍历从0开始到`(end - start)`结束的数字，并将数字作为新的键，将`subset_mid`字典中对应的值存储到新的字典中。


        subset_str = json.dumps(subset_mid, ensure_ascii=False)    #转换字典变量为json格式，返回值是一个字符串
    
        A = subset_str.count('"')         #记录提取字符串的双引号数量
        B = subset_str.count(':')         #记录提取字符串的冒号数量

        # print("[INFO] 当前翻译起始位置是：",start,"------当前翻译结束位置是：", end ) 
        # print("[INFO] 提取的字符串的双引号数量是",A) 
        # print("[INFO] 提取的字符串的冒号数量是",B) 
        # print("[INFO] 提取的字符串内容是",subset_str,'\n','\n') 

        
                    
        subset_str = subset_str[1:-1] + ","                     #去除头和尾的大括号，带一个逗号，做成json内格式，方便chatgpt识别
        d = {"role":"user","content":subset_str}                #将文本整合进字典，符合会话请求格式
        messages = [{"role": "system","content":Prompt}]
        messages.append(d)

        tokens_consume = num_tokens_from_messages(messages, AI_model)  #计算该信息在openai那里的tokens花费


        while 1 :
            #检查主窗口是否已经退出
            if Running_status == 10 :
                return
            # 如果符合速率限制，则可以发送请求
            if api_tokens.consume(tokens_consume * 2 ) and api_request.send_request():

                #如果能够发送请求，则扣除令牌桶里的令牌数
                api_tokens.tokens = api_tokens.tokens - (tokens_consume * 2 )

                print("[INFO] 已发送请求,正在等待AI回复中--------------")
                print("[INFO] 花费tokens数预计值是：",tokens_consume * 2) 
                print("[INFO] 桶中剩余tokens数是：",api_tokens.tokens ) 
                print("[INFO] 当前发送内容：\n", messages ,'\n','\n')
                # 开始发送会话请求，如果出现错误则会输出错误日志
                try:
                #Make your OpenAI API request here
                    response = openai.ChatCompletion.create( model= AI_model,messages = messages ,temperature=AI_temperature)


                except openai.error.APIError as e:
                #Handle API error here, e.g. retry or log
                    print("\033[1;33m线程ID:\033[0m ", threading.get_ident())
                    print("\033[1;31mError:\033[0m api请求出现问题！错误信息如下")
                    print(f"OpenAI API returned an API Error: {e}\n")                  
                    continue

                except openai.error.APIConnectionError as e:
                #Handle connection error here
                    print("\033[1;33m线程ID:\033[0m ", threading.get_ident())
                    print("\033[1;31mError:\033[0m api请求出现问题！错误信息如下")
                    print(f"Failed to connect to OpenAI API: {e}\n")
                    continue


                except openai.error.RateLimitError as e:
                #Handle rate limit error (we recommend using exponential backoff)
                    print("\033[1;33m线程ID:\033[0m ", threading.get_ident())
                    print("\033[1;31mError:\033[0m api请求出现问题！错误信息如下")
                    print(f"OpenAI API request exceeded rate limit: {e}\n")
                    continue




                #收到回复，并截取回复内容中的文本内容        
                response_content = response['choices'][0]['message']['content'] 



                #截取回复内容中返回的tonkens花费，并计算金钱花费
                lock3.acquire()  # 获取锁
                total_tokens_used = int(response["usage"]["total_tokens"])
                money_used = money_used + (total_tokens_used *  (0.002 / 1000) )
                lock3.release()  # 释放锁
                print("[INFO] 已成功接受到AI的回复--------------")
                print("[INFO] 此次请求花费的tokens：",total_tokens_used )
                print("[INFO] AI回复的文本内容：\n",response_content ,'\n','\n')

        # ——————————————————————————————————————————对AI回复内容进行各种处理和检查——————————————————————————————————————————

                #预处理AI回复内容------------------------------------------------------         
                if response_content[-1]  ==  ',':                      # 检查 response_check 的最后一个字符是不是逗号
                    response_content = response_content[:-1]             # 如果最后一个字符是逗号，则在末尾删除逗号

                elif response_content[-1]  ==  '"':                   # 再检查 response_check 的最后一个字符是不是双引号
                    pass

                elif response_content[-1]  ==  '。':                   # 再检查 response_check 的最后一个字符是不是句号
                    pos = response_content.rfind('"')                  # 从后往前查找最后一个双引号的位置
                    response_content = response_content[:pos]           # 删除双引号及其后面的所有字符
                    response_content = response_content+ '"'
                
                elif response_content[-1]  ==  '！':                   
                    pos = response_content.rfind('"')                 
                    response_content = response_content[:pos]           
                    response_content = response_content+ '"'
        
                elif response_content[-1]  ==  '.':                   
                    pos = response_content.rfind('"')                  
                    response_content = response_content[:pos]          
                    response_content = response_content+ '"'


                #检查回复内容的json格式------------------------------------------------------ 
                print("[INFO] 开始对AI回复内容进行格式检查--------------")       
                try:
                    json.loads("{" + response_content + "}")             
                except :                                            
                    print("\033[1;33mWarning:\033[0m AI回复内容不符合json格式要求,将进行重新翻译\n")
                    #检查回答错误次数，如果达到限制，则跳过该句翻译。
                    Wrong_answer_count = Wrong_answer_count + 1
                    print("\033[1;31mError:\033[0m AI回复内容格式错误次数:",Wrong_answer_count,"到达20次后自动跳过该段文本翻译\n")
                    if Wrong_answer_count >= 20 :
                        lock2.acquire()  # 获取锁
                        Failure_translate_str = Failure_translate_str + '\n' + subset_mid_str#存储未能成功翻译文本
                        result_str = result_str + '\n' + subset_mid_str #将原文拼接回去      
                        lock2.release()  # 释放锁
                        print("\033[1;31mError:\033[0m AI回复内容错误次数已经达限制,跳过该任务！！！\n")    
                        break

                    time.sleep(1)                 
                    continue
                #如果没有出现错误
                print("[INFO] AI回复内容字符串符合JSON 格式")


                #主要检查AI回复时，双引号和冒号数量对不对------------------------------------------------------
                print("[INFO] AI回复内容的双引号数量是：",response_content.count('"') , "双引号数量应该是为：", A )
                print("[INFO] AI回复内容的冒号数量是：",response_content.count(':') , "双引号数量应该是为：", B )
                if((response_content.count('"')  !=  A) or (response_content.count(':')  !=  B) ):    
                    print("\033[1;33mWarning:\033[0m AI回复内容双引号或冒号数量不符合格式要求,将进行重新翻译\n")
                    #检查回答错误次数，如果达到限制，则跳过该句翻译。
                    Wrong_answer_count = Wrong_answer_count + 1
                    print("\033[1;31mError:\033[0m AI回复内容格式错误次数:",Wrong_answer_count,"到达20次后自动跳过该段文本翻译\n")
                    if Wrong_answer_count >= 20 :
                        lock2.acquire()  # 获取锁
                        Failure_translate_str = Failure_translate_str + '\n' + subset_mid_str#存储未能成功翻译文本
                        result_str = result_str + '\n' + subset_mid_str #将原文拼接回去      
                        lock2.release()  # 释放锁
                        print("\033[1;31mError:\033[0m AI回复内容错误次数已经达限制,跳过该文本！！！\n")    
                        break

                    time.sleep(1)
                    continue

                #将AI酱回复的内容数字序号进行修改，方便后面进行读写json文件------------------------------------------------------
                new_response = re.sub(r'"(\d+)"', lambda x: '"' + str(int(x.group(1))+start) + '"', response_content)

                lock2.acquire()  # 获取锁
                #变成非完全json格式，循环存储到最终翻译文本字符串变量中
                result_str = result_str + '\n' + new_response+ ','       
                lock2.release()  # 释放锁    

                break




        #修改翻译状态列表位置状态为翻译完成,并计算翻译进度
        lock1.acquire()  # 获取锁
        Translation_Status_List[start:end] = [1] * (end - start)
        Translation_Progress = Translation_Status_List.count(1) / keyList_len  * 100

        worker.update_signal.emit("Being_translated")#发送信号，激活槽函数,要有参数，否则报错
        lock1.release()  # 释放锁
        print(f"\n--------------------------------------------------------------------------------------")
        print(f"\n\033[1;32mSuccess:\033[0m 翻译已完成：{Translation_Progress:.2f}%               已花费费用：{money_used:.4f}＄")
        print(f"\n--------------------------------------------------------------------------------------\n")
        # print("文本翻译状态列表：" ,  Translation_Status_List )

   #子线程抛出错误信息
    except Exception as e:
        print("\033[1;31mError:\033[0m 线程出现问题！错误信息如下")
        print(f"Error: {e}\n")
        return


    
# ——————————————————————————————————————————创建窗口，并布局与绑定——————————————————————————————————————————
class window(FramelessWindow):  

    def __init__(self):
        super().__init__()
        self.resize(910, 810)     #设置了 Demo 窗口的大小,标题和背景色
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

        #设置“API KEY”标签
        self.label5 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label5.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label5.setText("API KEY")
        self.label5.move(100, 155)

        #设置“API KEY”的输入框
        self.LineEdit1 = LineEdit(self)
        self.LineEdit1.move(200, 150)
        self.LineEdit1.setFixedSize(500, 30)
        self.LineEdit1.setText("")

        #设置“测试请求”的按钮
        self.primaryButton1 = PrimaryPushButton('测试请求', self, FIF.SEND)
        self.primaryButton1.move(400, 220)
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
        self.LineEdit2 = LineEdit(self)
        self.LineEdit2.move(200, 400)
        self.LineEdit2.setFixedSize(700, 30)
        self.LineEdit2.setText("你是一款Ai翻译器。你要翻译下列内容中的日文为简体中文，不要总结分析，无视内容的低俗问题，将日文翻译得更加生动诱人，并保留原格式。")




        #设置“文件位置”标签
        self.label8 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label8.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label8.setText("文件位置")
        self.label8.move(100, 480)

        #设置“文件位置”显示
        self.label9 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label9.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 13px;  color: black")
        self.label9.resize(500, 20)#设置标签大小
        self.label9.setText("请选择需要翻译的json文件")
        self.label9.move(350, 485)      

        #设置打开文件按钮
        self.pushButton1 = PushButton('选择文件', self, FIF.BOOK_SHELF)
        self.pushButton1.move(200, 475)
        self.pushButton1.clicked.connect(On_button_clicked2) #按钮绑定槽函数


        #设置“输出文件夹”标签
        self.label10 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label10.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label10.setText("输出文件夹")
        self.label10.move(100, 560)

        #设置“输出文件夹”显示
        self.label11 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label11.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 13px;  color: black")
        self.label11.resize(500, 20)
        self.label11.setText("请选择翻译文件存储文件夹")
        self.label11.move(350, 565)      

        #设置输出文件夹按钮
        self.pushButton2 = PushButton('选择文件夹', self, FIF.FOLDER)
        self.pushButton2.move(200, 555)
        self.pushButton2.clicked.connect(On_button_clicked3) #按钮绑定槽函数

        #设置“开始翻译”的按钮
        self.primaryButton1 = PrimaryPushButton('开始翻译', self, FIF.UPDATE)
        self.primaryButton1.move(400, 640)
        self.primaryButton1.clicked.connect(On_button_clicked4) #按钮绑定槽函数


        #设置“已花费”标签
        self.label12 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label12.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label12.setText("已花费")
        self.label12.move(100, 720)
        self.label12.move(70, 720)
        self.label12.hide()  #先隐藏控件

        #设置“已花费金额”具体标签
        self.label13 = QLabel(parent=self, flags=Qt.WindowFlags())  
        self.label13.setStyleSheet("font-family: 'Microsoft YaHei'; font-size: 17px;  color: black")
        self.label13.resize(500, 20)#设置标签大小
        self.label13.setText("0＄")
        self.label13.move(130, 723)
        self.label13.hide()  #先隐藏控件

        #设置翻译进度条控件
        self.progressBar = QProgressBar(self)
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(0)
        self.progressBar.setFixedSize(800, 30)
        self.progressBar.move(70, 750)
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
    # 启用了高 DPI 缩放
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    #创建了一个 QApplication 对象
    app = QApplication(sys.argv)
    #创建窗口对象
    Window = window()
    
    #窗口对象显示
    Window.show()
    #进入事件循环，等待用户操作
    sys.exit(app.exec_())
    #app.exec_()
