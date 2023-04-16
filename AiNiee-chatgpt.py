import openai
import json
import time
import re


def main():

#——————————————————————————————————————————定义常量——————————————————————————————————————————


    result_str = ""      #存储已经翻译好的文本，最终用
    result_str = '{' + '\n'   # 在开头添加 `{`

    l = 0                #请求失败计数
#—————————————————————————————————————————— 读取配置文件——————————————————————————————————————————
    with open("config.txt", "r",encoding="utf-8") as f:   #以阅读模式和特定编码模式，读取目标文件，并缓存为f1，程序结束则自动关闭文件
        lines = f.readlines()                             #使用 readlines() 函数读取config.txt文件中的所有行


        params = {}                                       #注册空字典
        for line in lines:
            line = line.strip()                           #使用 strip() 方法去除行末的空格，并检查行是否为空
            if line:
                key, value = line.split("=")              #使用 split() 方法将行分割为键和值，并将它们添加到 params 字典中
                params[key.strip()] = value.strip()       #构建字典键值对

        
        API_key = params["API_key"]                        #设定api
        API_access_cycle = int(params["API_access_cycle"]) #设定api访问速度
        system_settings_word = params["Prompt"]            #设定AI提示词
        Number_of_lines_per_translation = int(params["Number_of_lines_per_translation"])      #设定截取原文文本行数

        start = -Number_of_lines_per_translation          # 截取的起始位置
        end =  start + Number_of_lines_per_translation     # 截取结束的位置（不包含）
  
        print("--------------API_key是:",API_key,'\n',) 
        print("--------------API_access_cycle是:",API_access_cycle,'\n') 
        print("--------------Prompt是:",system_settings_word,'\n') 
        print("--------------Number_of_lines_per_translation是:",Number_of_lines_per_translation,'\n') 

        openai.api_key = API_key                              #注册api

    if (not API_key) or (not API_access_cycle) or (not system_settings_word) or ( not Number_of_lines_per_translation):
        print("--------------------------请请正确填写配置格式，并放到程序根目录下!-----------------------------")
        exit()



# ——————————————————————————————————————————读取需要翻译的文件——————————————————————————————————————————
    try:
        with open("ManualTransFile.json", "r",encoding="utf-8") as f:               
            source_str = f.read()       #一次性读取文本中全部的内容，以字符串的形式返回结果
            source = json.loads(source_str) #转换为json格式，当作最后翻译文件的原文源
            source_mid = json.loads(source_str) #转换为json格式，当作中间文件的原文源



            keyList=list(source_mid.keys())         #通过keys方法，获取所有的key，返回值为一个可迭代对象，并转换为list变量
            keyList_len = len(keyList)              #获取原文件key列表的长度
            print("--------------你的原文长度是",keyList_len,"-----------------------"'\n','\n')



            for i in range(keyList_len):  #将原始字典 `source_mid` 中的键 `keyList[i]` 对应的值作为新的键值对的值，并将新的键设为从 0 开始的数字序号 `str(i)`
                source_mid[str(i)] = source_mid.pop(keyList[i])        
            # print("替换后的结果为：\n", source_mid,'\n')

            



    except FileNotFoundError:
        print("--------------请将包含需要翻译内容的ManualTransFile.json放到程序根目录下!-------------------------")
        exit()



# ——————————————————————————————————————————将原文文本分段，并循环进行翻译——————————————————————————————————————————

    
    while end < keyList_len :

        messages = [{"role": "system","content":system_settings_word}]

        # 用来改变截取原文位置
        if ((end + Number_of_lines_per_translation) >= keyList_len):
            end = keyList_len
            start = start + Number_of_lines_per_translation
        else:
            end = end + Number_of_lines_per_translation
            start = start + Number_of_lines_per_translation


        #读取source_mid源文件中特定起始位置到结束位置的数据
        keys = list(source_mid.keys())[start:end]         #将`source_mid`的所有键转换为列表变量，然后使用切片语法`[start:end]`选取指定范围内的键，存储到`keys`变量中
        subset_mid = {k: source_mid[k] for k in keys}          #`k: source_mid[k]`是一个字典键值对，其中`k`表示键，`source_mid[k]`表示该键对应的值。`for k in keys`是一个for循环，它遍历了`keys`列表中的每个键，并将其用作字典键。
                                                           #因此，`{k: source_mid[k] for k in keys}`是一个字典推导式，它使用`keys`列表中的每个键创建一个新的字典。该字典的键是`keys`列表中的键，对应的值是`source_mid`字典中该键对应的值。 

        #改键为从0到截取长度结束的数字序号，因为AI酱对一万以上的数字排列不是很理解，回复又慢又容易出错
        subset_mid = {j: subset_mid[k] for j, k in enumerate(subset_mid)} #使用`enumerate()`函数遍历`subset_mid`字典中的键值对，将键值对的索引值存储到`i`变量中，将键存储到`k`变量中。
        subset_mid = {j: subset_mid[j] for j in range( 0, (end - start) )}  #使用一个for循环遍历从0开始到`(end - start)`结束的数字，并将数字作为新的键，将`subset_mid`字典中对应的值存储到新的字典中。
    




        subset_str = json.dumps(subset_mid, ensure_ascii=False)    #转换字典变量为json格式，返回值是一个字符串
        print("--------------当前翻译起始位置是：",start,"------当前翻译结束位置是：", end ,'\n') 
        A = subset_str.count('"')         #记录字符串的双引号数量
        B = subset_str.count(':')         #记录字符串的冒号数量
        print("--------------提取的字符串的双引号数量是",A,'\n') 
        print("--------------提取的字符串的冒号数量是",B,'\n') 
        print("--------------提取的字符串内容是",subset_str,'\n','\n') 


            
        subset_str = subset_str[1:-1] + ","                     #去除头和尾的大括号，带一个逗号，做成json内格式，方便chatgpt识别
        d = {"role":"user","content":subset_str}                #将文本整合进字典，符合会话请求格式   
        messages.append(d)
        print("--------------当前发送内容：\n", messages ,'\n','\n')

        #调试用
        # response = openai.ChatCompletion.create( model="gpt-3.5-turbo",messages = messages ,temperature=1)


        try:
            response = openai.ChatCompletion.create(                #发送翻译会话请求
                model="gpt-3.5-turbo",
                messages = messages ,
                temperature=1)
        except :
            print("--------------------------------api请求出现问题！！！！！！！！------------------\n")
            print("--------------------------------api请求出现问题！！！！！！！！------------------\n")
            print("--------------------------------api请求出现问题！！！！！！！！------------------\n")
            print("--------------------------------尝试五次后自动退出程序！！！！！！！！------------\n")
            end = end - Number_of_lines_per_translation            #回滚截取原文位置
            start = start - Number_of_lines_per_translation  
            time.sleep(API_access_cycle * 2)                       # 暂停时间

            l = l + 1                                              #失败太多次就退出循环
            if (l >= 5  ):
                break
            continue

        
        response = response['choices'][0]['message']['content']  #截取回复内容中的文本内容
        print("--------------AI回复的文本内容：\n",response ,'\n','\n')



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
            json.loads("{" + response + "}")             #给来两个括号，变成json格式看看
        except :                                              #如果出现错误
            print("-------------AI回复内容不符合json格式要求！！！！！！！！------------------\n")
            end = end - Number_of_lines_per_translation        #回滚翻译位置
            start = start - Number_of_lines_per_translation
            time.sleep(API_access_cycle   )                     # 暂停周期，会比较久
            continue
        #如果没有出现错误
        print("--------------AI回复内容字符串符合JSON 格式------------------------------")



        #主要检查AI回复时，双引号和冒号数量对不对------------------------------------------------------
        print("--------------AI回复内容的双引号数量是：",response.count('"') , "双引号数量应该是为：", A )
        print("--------------AI回复内容的冒号数量是：",response.count(':') , "双引号数量应该是为：", B )
        if((response.count('"')  !=  A) or (response.count(':')  !=  B) ):    #AI回复内容不符合格式的话，则回滚位置，结束该循环，再翻译
            print("--------------AI回复内容双引号或冒号数量不符合格式要求！！！！！！！！------------------\n")
            end = end - Number_of_lines_per_translation
            start = start - Number_of_lines_per_translation
            time.sleep(API_access_cycle  )  # 暂停周期
            continue

        

        #将AI酱回复的内容数字序号进行修改，方便后面进行读写json文件------------------------------------------------------
        new_response = re.sub(r'"(\d+)"', lambda x: '"' + str(int(x.group(1))+start) + '"', response)
        # 我们使用re.sub()函数来进行字符串替换。该函数的第一个参数是正则表达式，用于匹配需要替换的字符串。第二个参数是替换函数，用于对匹配到的字符串进行处理。第三个参数是需要进行替换的字符串。
        # 正则表达式是'"(\d+)"'，其中\d+表示匹配一个或多个数字，而前后的双引号表示匹配前后都是双引号的数字
        # lambda函数是缩写函数，来对匹配到的数字进行加法操作，具体操作为将数字转换为整型，加上start的值后再转换为字符串
 
        print("--------------AI回复的文本内容改变左边键序后：\n",new_response ,'\n','\n')






# ——————————————————————————————————————————将翻译文本改变格式写入中间件——————————————————————————————————————————
        result_str = result_str + '\n' + new_response+ ','        #变成非完全json格式，循环存储到最终翻译文本字符串变量中    
        
        result_str_mid = result_str[:-1] + '\n' + '}'             #变成json格式，准备写入中间件

        with open("translation_mid.json", "w", encoding="utf-8") as f:
            f.write(result_str_mid)



    # ——————————————————————————————————————将翻译文本修改key，再写入最后的译文保存文件——————————————————————————————————————————

        with open("translation_mid.json", "r",encoding="utf-8") as f:               
            source_last_str = f.read()                  #一次性读取json文本中全部的内容，以字符串的形式返回结果
            source_last = json.loads(source_last_str)    #字符串转换为json格式，当作最后翻译文件的原文源

        
        source_last_values = list(source_last.values())         # 获取 source_last 的所有值,转换为列表变量存储
        source_last_values_len = len(source_last_values)        #获取source_last值列表的长度


        # 遍历 source 和 source_mid 的键值对，将 source_last_values列表变量的值按索引顺序赋给source，改变原文的右边文本。
        n = 0
        for key, value in source.items():
            if (key in source) and (n < source_last_values_len ):
                source[key] = source_last_values[n]
                n = n + 1


        # 将更新后的 source字典 写入json文件
        with open("TrsData.json", "w", encoding="utf-8") as f:
            json.dump(source, f, ensure_ascii=False, indent=4)


# —————————————————————————————————————#单次翻译完成——————————————————————————————————————————

   
        percent = end / keyList_len * 100  #计算翻译进度
        print(f"\n--------------------------------------------------------------------------------------")
        print(f"\n----------------------------翻译已完成 {percent:.2f}%---------------------------------------")
        print(f"\n--------------------------------------------------------------------------------------\n")
        time.sleep(API_access_cycle)       # 暂停周期



# —————————————————————————————————————#全部翻译完成——————————————————————————————————————————
    print("\n--------------------------------------------------------------------------------------")
    print(f"\n-------------------------翻译已完成 {percent:.2f}%-------------------------------------------")   
    print("\n-------------------翻译已停止,请检查末尾是否缺失,格式是否错误------------------------------------")
    print("\n-------------------------------------------------------------------------------------\n")

main()





