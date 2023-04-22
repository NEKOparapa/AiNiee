import openai        #需要安装库
import json
import re
import tiktoken      #需要安装库
import time
import threading
import concurrent.futures
import os

model="gpt-3.5-turbo" #调用api的模型
temperature = 1       #AI的随机度，0.8是高随机，0.2是低随机

tokens_limit_per = 4090  #gpt-3.5-turbo模型每次请求的最大tokens数

Free_RPM_limit = 3        # 免费用户速率限制每分钟请求数
Free_TPM_limit = 40000    # 免费用户速率限制每分钟token数，2tokens大概一个汉字

Pay_RPM_limit2 = 60        # 付费用户前48小时速率限制每分钟请求数
Pay_TPM_limit2 = 60000    # 付费用户前48小时速率限制每分钟token数，2tokens大概一个汉字，发送和接受的信息都算作一起

Pay_RPM_limit3 = 3500        # 付费用户速率限制每分钟请求数
Pay_TPM_limit3 = 90000    # 付费用户速率限制每分钟token数，2tokens大概一个汉字，发送和接受的信息都算作一起




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




#—————————————————————————————————————————— 读取配置文件——————————————————————————————————————————
#工作目录改为python源代码所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__)) #使用 `__file__` 变量获取当前 Python 脚本的文件名（包括路径），然后使用 `os.path.abspath()` 函数将其转换为绝对路径，最后使用 `os.path.dirname()` 函数获取该文件所在的目录
os.chdir(script_dir)#使用 `os.chdir()` 函数将当前工作目录改为程序所在的目录。
print("[INFO] 当前工作目录是:",script_dir,'\n') 

#打开配置文件
with open("config.txt", "r",encoding="utf-8") as f:   #以阅读模式和特定编码模式，读取目标文件，并缓存为f1，程序结束则自动关闭文件
    lines = f.readlines()                             #使用 readlines() 函数读取config.txt文件中的所有行


    params = {}                                       #注册空字典
    for line in lines:
        line = line.strip()                           #使用 strip() 方法去除行末的空格，并检查行是否为空
        if line:
            key, value = line.split("=")              #使用 split() 方法将行分割为键和值，并将它们添加到 params 字典中
            params[key.strip()] = value.strip()       #构建字典键值对

        
    API_key = params["API_key"]                        #设定api
    Prompt = params["Prompt"]                         #设定AI提示词
    Account_Type = int(params["Account_Type"])        #设定账号类型
    Number_of_lines_per_translation = int(params["Number_of_lines_per_translation"])      #设定截取原文文本行数

#检查是否正确填写配置
if (not API_key) or (not Prompt) or (not Account_Type) or (not Number_of_lines_per_translation) :
    print("\033[1;31mError:\033[0m 请请正确填写配置格式，并放到程序根目录下!")
    exit()

#输出配置信息
print("[INFO] 你的账号类型是:",Account_Type,'\n') 
print("[INFO] 你的API_key是:",API_key,'\n',) 
print("[INFO] 每次翻译文本行数是:",Number_of_lines_per_translation,'\n') 
print("[INFO] 你的Prompt是:",Prompt,'\n') 


#—————————————————————————————————————————— 设定相关系统参数——————————————————————————————————————————
#注册api
openai.api_key = API_key                            

#设定账号类型
if Account_Type == 2 :
    The_RPM_limit =  60 / Pay_RPM_limit2           
    The_TPM_limit =  Pay_TPM_limit2 / 60
    The_Max_workers = 20


elif Account_Type == 3 :
    The_RPM_limit =  60 / Pay_RPM_limit3           
    The_TPM_limit =  Pay_TPM_limit3 / 60
    The_Max_workers = 30

else :
    The_RPM_limit =  60 / Free_RPM_limit             #计算请求时间间隔
    The_TPM_limit =  Free_TPM_limit / 60             #计算请求每秒可请求的tokens流量
    The_Max_workers = 4                              #设定最大并行任务数


#根据账号类型，设定请求限制
api_request = APIRequest(The_RPM_limit)
api_tokens = TokenBucket((tokens_limit_per * 1.9), The_TPM_limit)

# 定义两个锁
lock1 = threading.Lock()
lock2 = threading.Lock()
lock3 = threading.Lock()


# ——————————————————————————————————————————读取需要翻译的文件——————————————————————————————————————————
try:
    with open("ManualTransFile.json", "r",encoding="utf-8") as f:               
        source_str = f.read()       #一次性读取文本中全部的内容，以字符串的形式返回结果


        source = json.loads(source_str) #转换为json格式，当作最后翻译文件的原文源
        source_mid = json.loads(source_str) #转换为json格式，当作中间文件的原文源
  



        keyList=list(source_mid.keys())         #通过keys方法，获取所有的key，返回值为一个可迭代对象，并转换为list变量
        keyList_len = len(keyList)              #获取原文件key列表的长度
        print("[INFO] 你的原文长度是",keyList_len,"-----------------------")



        for i in range(keyList_len):  #将原始字典source_mid中的键设为从0开始的数字序号 str(i)
            source_mid[str(i)] = source_mid.pop(keyList[i])        


        Translation_Status_List =  [0] * keyList_len   #创建文本翻译状态列表，用于并发时获取每个文本的翻译状态


        result_str = ""      #存储已经翻译好的文本，最终用
        result_str = '{'  + '\n' + result_str  # 在开头添加 `{`

        money_used = 0  #存储金钱花销

except FileNotFoundError:
    print("\033[1;31mError:\033[0m 请将包含需要翻译内容的ManualTransFile.json放到程序根目录下!")
    exit()




# ——————————————————————————————————————————并发请求任务函数——————————————————————————————————————————

def make_request():

    global result_str  # 声明全局变量
    global Translation_Status_List  
    global money_used

    Wrong_answer_count = 0 #错误回答计数，用于错误回答到达一定次数后，取消该任务。

    #遍历翻译状态列表，找到还没翻译的值和对应的索引位置
    lock1.acquire()  # 获取锁
    for i, status in enumerate(Translation_Status_List):
        if status  == 0:

            start = i     #确定切割开始位置

            if (start + Number_of_lines_per_translation >= keyList_len) :  #确定切割结束位置，注意最后位置是不固定的
                end = keyList_len  
            else :
                end = start + Number_of_lines_per_translation
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

    tokens_consume = num_tokens_from_messages(messages, model)  #计算该信息在openai那里的tokens花费


    while 1 :
        # 如果符合速率限制，则可以发送请求
        if api_tokens.consume(tokens_consume * 2 ) and api_request.send_request():

            #如果能够发送请求，则扣除令牌桶里的令牌数
            api_tokens.tokens = api_tokens.tokens - (tokens_consume * 2 )
            print("[INFO] 已发送请求,正在等待AI回复中--------------")
            print("[INFO] 花费tokens数预计值是：",tokens_consume * 2) 
            print("[INFO] 桶中剩余tokens数是：",api_tokens.tokens ,'\n') 

            # 开始发送会话请求，如果出现错误则会输出错误日志
            try:
            #Make your OpenAI API request here
                response = openai.ChatCompletion.create( model,messages = messages ,temperature=temperature)
                print("[INFO] 当前发送内容：\n", messages ,'\n','\n')
                # print("[INFO] 已发送请求,正在等待AI回复中--------------",'\n','\n')

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
            response = response['choices'][0]['message']['content']  
            print("[INFO] AI回复的文本内容：\n",response )

            #截取回复内容中返回的tonkens花费，并计算金钱花费
            lock3.acquire()  # 获取锁
            total_tokens_used = int (response["usage"]["total_tokens"])
            money_used = money_used + (total_tokens_used *  (0.002 / 1000) )
            lock3.release()  # 释放锁
            print("[INFO] 此次请求花费的tokens：",total_tokens_used ,'\n','\n')

    # ——————————————————————————————————————————对AI回复内容进行各种处理和检查——————————————————————————————————————————

            #预处理AI回复内容------------------------------------------------------         
            if response[-1]  ==  ',':                      # 检查 response_check 的最后一个字符是不是逗号
                response = response[:-1]             # 如果最后一个字符是逗号，则在末尾删除逗号

            elif response[-1]  ==  '"':                   # 再检查 response_check 的最后一个字符是不是双引号
                pass

            elif response[-1]  ==  '。':                   # 再检查 response_check 的最后一个字符是不是句号
                pos = response.rfind('"')                  # 从后往前查找最后一个双引号的位置
                response = response[:pos]           # 删除双引号及其后面的所有字符
                response = response+ '"'


            #检查回复内容的json格式------------------------------------------------------        
            try:
                json.loads("{" + response + "}")             
            except :                                            
                print("\033[1;31mError:\033[0m AI回复内容不符合json格式要求！！！！！！！！------------------\n")
                #检查回答错误次数，如果达到限制，则跳过该句翻译。
                Wrong_answer_count = Wrong_answer_count + 1
                if Wrong_answer_count >= 20 :
                    lock2.acquire()  # 获取锁
                    result_str = result_str + '\n' + subset_mid_str #将原文拼接回去      
                    lock2.release()  # 释放锁
                    print("\033[1;31mError:\033[0m AI回复内容错误次数已经达限制,跳过该任务！！！\n")    
                    break

                time.sleep(1)                 
                continue
            #如果没有出现错误
            print("[INFO] AI回复内容字符串符合JSON 格式------------------------------")


            #主要检查AI回复时，双引号和冒号数量对不对------------------------------------------------------
            print("[INFO] AI回复内容的双引号数量是：",response.count('"') , "双引号数量应该是为：", A )
            print("[INFO] AI回复内容的冒号数量是：",response.count(':') , "双引号数量应该是为：", B )
            if((response.count('"')  !=  A) or (response.count(':')  !=  B) ):    
                print("\033[1;31mError:\033[0m AI回复内容双引号或冒号数量不符合格式要求！！！！！！！！------------------\n")
                #检查回答错误次数，如果达到限制，则跳过该句翻译。
                Wrong_answer_count = Wrong_answer_count + 1
                if Wrong_answer_count >= 20 :
                    lock2.acquire()  # 获取锁
                    result_str = result_str + '\n' + subset_mid_str #将原文拼接回去      
                    lock2.release()  # 释放锁
                    print("\033[1;31mError:\033[0m AI回复内容错误次数已经达限制,跳过该任务！！！\n")    
                    break

                time.sleep(1)
                continue

            #将AI酱回复的内容数字序号进行修改，方便后面进行读写json文件------------------------------------------------------
            new_response = re.sub(r'"(\d+)"', lambda x: '"' + str(int(x.group(1))+start) + '"', response)

            lock2.acquire()  # 获取锁
            #变成非完全json格式，循环存储到最终翻译文本字符串变量中
            result_str = result_str + '\n' + new_response+ ','       
            lock2.release()  # 释放锁    

            break




    #修改翻译状态列表位置状态为翻译完成
    lock1.acquire()  # 获取锁
    Translation_Status_List[start:end] = [1] * (end - start)
    lock1.release()  # 释放锁

    #计算翻译进度
    percent = Translation_Status_List.count(1) / keyList_len  * 100 
    print(f"\n--------------------------------------------------------------------------------------")
    print(f"\n\033[1;32mSuccess:\033[0m 翻译已完成：{percent:.2f}%               已花费费用：{money_used:.2f}＄")
    print(f"\n--------------------------------------------------------------------------------------\n")
    # print("文本翻译状态列表：" ,  Translation_Status_List )



# ——————————————————————————————————————————构建并发任务池子—————————————————————————————————————————


# 计算并发任务数
if keyList_len % Number_of_lines_per_translation == 0:
    tasks_Num = keyList_len // Number_of_lines_per_translation 
else:
    tasks_Num = keyList_len // Number_of_lines_per_translation + 1


print("[INFO] 你的总任务数是：", tasks_Num,'\n')

# 创建线程池
with concurrent.futures.ThreadPoolExecutor(The_Max_workers) as executor:
    # 向线程池提交任务
    for i in range(tasks_Num):
        executor.submit(make_request)


# 等待线程池任务完成
executor.shutdown(wait=True)



# ——————————————————————————————————————————检查漏翻的文本，再次翻译————————————————————————————————————————

#计算未翻译文本的数量
count_not_Translate = Translation_Status_List.count(2) + Translation_Status_List.count(0)

while count_not_Translate != 0 :
    

    for i in range(count_not_Translate):      #将列表变量里未翻译的文本状态初始化
        if 2 in Translation_Status_List:
            idx = Translation_Status_List.index(2)
            Translation_Status_List[idx] = 0

    print("\033[1;33mWarning:\033[0m 仍然有部分未翻译，继续翻译-----------------------------------")

    # 计算可并发任务总数
    if count_not_Translate % Number_of_lines_per_translation == 0:
        new_count = count_not_Translate // Number_of_lines_per_translation
    else:
        new_count = count_not_Translate // Number_of_lines_per_translation + 1

    #构建新的线程池
    with concurrent.futures.ThreadPoolExecutor(The_Max_workers) as executor:
    # 向线程池提交任务
        for i in range(new_count):
            executor.submit(make_request)

    # 等待线程池任务完成
    executor.shutdown(wait=True)

    #重新计算未翻译文本的数量
    count_not_Translate = Translation_Status_List.count(2) + Translation_Status_List.count(0)




# ——————————————————————————————————————————将翻译文本改变格式写入中间件——————————————————————————————————————————
    
result_str_mid = result_str[:-1] + '\n' + '}'             #变成json格式，准备写入中间件

with open("translation_mid.json", "w", encoding="utf-8") as f:
    f.write(result_str_mid)



# ——————————————————————————————————————将翻译文本修改key，再写入最后的译文保存文件——————————————————————————————————————————

with open("translation_mid.json", "r",encoding="utf-8") as f:               
    source_last_str = f.read()                  #一次性读取json文本中全部的内容，以字符串的形式返回结果
    source_last = json.loads(source_last_str)    #字符串转换为json格式，当作最后翻译文件的原文源

n = 0
for key, value in source.items():
    source[key] = source_last[str(n)]
    n = n + 1

    # 将更新后的 source字典 写入json文件
with open("TrsData.json", "w", encoding="utf-8") as f:
    json.dump(source, f, ensure_ascii=False, indent=4)

# —————————————————————————————————————#全部翻译完成——————————————————————————————————————————

print("\n--------------------------------------------------------------------------------------")
print("\n\033[1;32mSuccess:\033[0m 程序已经停止")   
print("\n\033[1;32mSuccess:\033[0m 请检查TrsData.json文件，文本格式是否错误")
print("\n-------------------------------------------------------------------------------------\n")