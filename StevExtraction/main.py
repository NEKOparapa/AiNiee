from jtpp import Jr_Tpp
from jtpp import version
from ruamel.yaml import YAML
import traceback


print('jtpp_{}'.format(version))
print('main_v1.02')


# t++标红标蓝行需要找对应code
# code对应地址
# "Plugin Command": "356","Control Variables": "122","Script": "655",
redcode = ['356', '655', '122']
# "Comment": "108","Comment More": "408",
bluecode = ['108', '408']
bluedir = [r'System.json\switches', r'System.json\variables']
# "Show Choices": "102","Show Text Attributes": "101","Show Text": "401","Show Scrolling Text": "405",
# "Show Scrolling Text Attributes": "105","Change Actor Name": "320","Change Actor Nickname": "324",
# "Choice": "402"应该和102一起来
textcode = ['-1', '401', '101', '102','105','405','320',"324"]  # 需要被翻译的大概只有这些，-1是没有code的
# "Label": "118","Jump to Label": "119","Conditional Branch": "111","Show Picture": "231",
emptycode = ['357', '657', '111', '118', '119'] # t++没有提取的，应该不止
RPG_CODE={
  "Empty": "0",
  "Show Text Attributes": "101",
  "Show Choices": "102",
  "Input Number": "103",
  "Select Key Item": "104",
  "Show Scrolling Text Attributes": "105",
  "Comment": "108",
  "Conditional Branch": "111",
  "Loop": "112",
  "Break Loop": "113",
  "Exit Event Processing": "115",
  "Call Common Event": "117",
  "Label": "118",
  "Jump to Label": "119",
  "Control Switches": "121",
  "Control Variables": "122",
  "Control Self Switch": "123",
  "Control Timer": "124",
  "Change Gold": "125",
  "Change Items": "126",
  "Change Weapons": "127",
  "Change Armor": "128",
  "Change Party Member": "129",
  "Change Battle BGM": "132",
  "Change Battle End ME": "133",
  "Change Save Access": "134",
  "Change Menu Access": "135",
  "Change Encounter": "136",
  "Change Formation Access": "137",
  "Change Window Color": "138",
  "Transfer Player": "201",
  "Set Vehicle Location": "202",
  "Set Event Location": "203",
  "Scroll Map": "204",
  "Set Move Route": "205",
  "Get on/off Vehicle": "206",
  "Change Transparency": "211",
  "Show Animation": "212",
  "Shot Balloon Icon": "213",
  "Erase Event": "214",
  "Change Player Followers": "216",
  "Gather Followers": "217",
  "Fadeout Screen": "221",
  "Fadein Screen": "222",
  "Tint Screen": "223",
  "Flash Screen": "224",
  "Shake Screen": "225",
  "Wait": "230",
  "Show Picture": "231",
  "Move Picture": "232",
  "Rotate Picture": "233",
  "Tint Picture": "234",
  "Erase Picture": "235",
  "Set Weather Effects": "236",
  "Play BGM": "241",
  "Fadeout BGM": "242",
  "Save BGM": "243",
  "Replay BGM": "244",
  "Play BGS": "245",
  "Fadeout BGS": "246",
  "Play ME": "249",
  "Play SE": "250",
  "Stop SE": "251",
  "Play Movie": "261",
  "Change Map Display": "281",
  "Change Tileset": "282",
  "Change Battle Back": "283",
  "Change Parallax Back": "284",
  "Get Location Info": "285",
  "Battle Processing": "301",
  "Shop Processing": "302",
  "Name Input Processing": "303",
  "Change HP": "311",
  "Change MP": "312",
  "Change State": "313",
  "Recover All": "314",
  "Change EXP": "315",
  "Change Level": "316",
  "Change Parameters": "317",
  "Change Skills": "318",
  "Change Equipment": "319",
  "Change Actor Name": "320",
  "Change Actor Class": "321",
  "Change Actor Graphic": "322",
  "Change Vehicle Graphic": "323",
  "Change Actor Nickname": "324",
  "Change Actor Profile": "325",
  "Change Enemy HP": "331",
  "Change Enemy MP": "332",
  "Change Enemy State": "333",
  "Enemy Recover All": "334",
  "Enemy Appear": "335",
  "Enemy Transform": "336",
  "Show Battle Animation": "337",
  "Force Action": "339",
  "Abort Battle": "340",
  "Open Menu Screen": "351",
  "Open Save Screen": "352",
  "Game Over": "353",
  "Return to Title Screen": "354",
  "Script Header": "355",
  "Plugin Command": "356",
  "Show Text": "401",
  "Choice": "402",
  "Choice Cancel": "403",
  "Choices End": "404",
  "Show Scrolling Text": "405",
  "Comment More": "408",
  "Else": "411",
  "Branch End": "412",
  "Repeat Above": "413",
  "If Win": "601",
  "If Escape": "602",
  "If Lose": "603",
  "Battle Processing End": "604",
  "Shop Item": "605",
  "Script": "655"
}

def readconfig():
    try:
        yaml = YAML(typ='safe')
        with open('config.yaml', 'r', encoding='utf8') as f:
            config = yaml.load(f)
        # 确保config中数据齐全
        game_path=config['game_path']
        save_path=config['save_path']
        translation_path=config['translation_path']
        mark=config['mark']
        NameWithout=config['NameWithout']
        ReadCode=config['ReadCode']
        BlackDir=config['BlackDir']
        BlackCode=config['BlackCode']
        BlackFiles=config['BlackFiles']
        codewithnames=config['codewithnames']
        output_path=config['output_path']
        line_length=config['line_length']
        data_path=config['data_path']
        sumcode=config['sumcode']
        note_percent=config['note_percent']
        ja=config['ja']
    except Exception as e:
        print(e)
        input('没有找到格式正确的config.yaml文件，请确保其存在于与exe同级文件夹内')
    return config

config=readconfig()
startpage='1.一键读取游戏数据并保存\n' \
          '2.加载翻译工程\n' \
          '3.游戏版本更新\n'
key=['1','2','3']
try:
    while 1:
        res=0
        while res not in key:
            res = input(startpage)
        if res=='1':
            pj=Jr_Tpp(config)
            pj.FromGame(config['game_path'],config['save_path'],config['data_path'])
            input('已成功读取游戏数据，提取到的名字保存在Name.json中\n'
                  '请在翻译完名字以后，将其导入到ainiee的提示词典中\n'
                  '然后翻译{}\\data中的xlsx文件\n'.format(config['save_path']))
        elif res=='3':
            pj = Jr_Tpp(config)
            pj.Update(config['game_path'],config['translation_path'],config['save_path'],config['data_path'])
        else:
            pj = Jr_Tpp(config,config['save_path'])
        mainpage = '1.一键注入翻译\n' \
                   '2.保存翻译工程\n' \
                   '3.加载翻译工程\n' \
                   '4.导出翻译xlsx文件\n' \
                   '5.重新加载配置文件\n'
        while 1:
            res=0
            while res not in ['1','2','3','4','5']:
                res = input(mainpage)
            if res=='1':
                pj.ToGame(config['game_path'],config['translation_path'],config['output_path'],config['mark'])
            elif res=='2':
                pj.Save(config['save_path'])
            elif res=='3':
                pj = Jr_Tpp(config,config['save_path'])
            elif res=='4':
                pj.Output(config['save_path'])
            elif res=='5':
                config=readconfig()
                pj.ApplyConfig(config)
                print('已重新加载配置文件')
except Exception as e:
    print(traceback.format_exc())
    print(e)
    input('发生错误，请上报bug')
# 读
# test=Jr_Tpp(config)
#
# test.ReadGame(config['game_path'])
# test.Display(namelist=['Map122.json'])
# print('\n{}'.format(test.ProgramData['Map122.json'].loc['虚ろな目をした女性','地址']))
# test.GetName()
# test.InputFromJson(path=r'res/TrsData.json')
# test.Save('data')
# 写
# test=Jr_Tpp_LOAD('data')
# translation_path=r'jt++\ainiee'
# test.InputFromeXlsx(translation_path)
# test.Save('data')
# test.OutputBySearch('自身命中',1)
# outputpath='D:\ggsddu\old\QFT\system\mytrs\jt++\output'
# test.ToGmae(config['GameDir'],translation_path,outputpath,config['mark'])
# test.Save('data')
# test.DNoteB()
# test.Save('data')
# # test.DisplayBySearch('name',2,BigSmall=True)
# print(test.GetFileNames())
# test.Display(namelist=['Actors.json'])
