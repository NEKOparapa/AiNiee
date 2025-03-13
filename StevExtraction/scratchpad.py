# scratchpad.py
# 这个文件用于存放一些临时的、草稿性质的代码片段，可能用于测试、调试或未来的功能开发。

from jtpp import Jr_Tpp

# 示例配置（请根据实际情况修改）
config = {
    'game_path': '/path/to/your/game',  # 替换为你的游戏路径
    'save_path': '/path/to/save/project',  # 替换为保存翻译工程的路径
    'data_path': '/path/to/save/data',  # 替换为保存数据的路径
}

# 以下是从 jtpp.py 文件中移过来的测试代码

# 示例 1：读取游戏、显示、获取名称、从 JSON 导入、保存
# test = Jr_Tpp(config)
# test.ReadGame(config['game_path'])
# test.Display(namelist=['Map122.json'])
# print('\n{}'.format(test.ProgramData['Map122.json'].loc['虚ろな目をした女性','地址']))
# test.GetName()
# test.InputFromJson(path=r'res/TrsData.json')
# test.Save('data')

# 示例 2：加载翻译工程、从 xlsx 导入、保存、搜索、导出、注入游戏、保存、处理 Note
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