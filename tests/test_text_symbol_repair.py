# -*- coding: utf-8 -*-
"""符号修复引擎与检查器测试（零第三方依赖，直接运行）。

用法：
    python tests/test_text_symbol_repair.py

覆盖：
    - TextSymbolRepair 引擎：引号还原 / 批注删除（收窄规则）/ 条件标点 / 保护段 / 空白保留
    - SymbolRepairChecker 检查器：空项目 / 无翻译 / 正常扫描 / 润色状态透传

批注删除规则说明（收窄后）：
    仅当原文完全没有括号，且译文括号段内部文本命中 _ANNOTATION_PATTERNS
    （如（译者注：…）、【补充说明】、(TL: …) 等）时才删除整个括号段；
    普通括号内容（（笑）、（注意）、(上午) 等）与孤立括号一律保留。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ModuleFolders.Domain.TextSymbolRepair.TextSymbolRepair import TextSymbolRepair
from ModuleFolders.Service.Cache.CacheFile import CacheFile
from ModuleFolders.Service.Cache.CacheItem import CacheItem, TranslationStatus
from ModuleFolders.Service.Cache.CacheProject import CacheProject
from ModuleFolders.Service.TranslationChecker.CheckResult import CheckResult
from ModuleFolders.Service.TranslationChecker.SymbolRepairChecker import SymbolRepairChecker


class Harness:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name, got, expected):
        if got == expected:
            self.passed += 1
            print(f"  [OK ] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}\n    got     : {got!r}\n    expected: {expected!r}")


def test_engine_quotes(h, r):
    print("== 引擎：引号还原 ==")
    h.check("首尾「」", r.repair_text_symbols('「こんにちは」', '"你好"'), '「你好」')
    h.check("首尾『』", r.repair_text_symbols('『銀河鉄道の夜』', '"银河铁道之夜"'), '『银河铁道之夜』')
    h.check("首尾“”", r.repair_text_symbols('“そうだ”', '"是啊"'), '“是啊”')
    h.check("内部「」多对", r.repair_text_symbols('「a」と「b」', '"a"和"b"'), '「a」和「b」')
    h.check("内部“”", r.repair_text_symbols('彼は「行こう」と言った。', '他说“走吧”。'), '他说「走吧」。')

    print("== 引擎：嵌套/重复引号 ==")
    h.check("嵌套「「」」→ ““””", r.repair_text_symbols('「彼は「行こう」と言った。」', '“他说“走吧”。”'), '「他说「走吧」。」')
    h.check("嵌套「「」」→ \"\"\"\"", r.repair_text_symbols('「彼は「行こう」と言った。」', '"他说"走吧"。"'), '「他说「走吧」。」')
    h.check("重复引号「「」」→ “”", r.repair_text_symbols('「「こんにちは」」', '““你好””'), '「「你好」」')
    h.check("多对混合“”", r.repair_text_symbols('「a」と「b」', '“a”和“b”'), '「a」和「b」')
    h.check("内部英文引号嵌套", r.repair_text_symbols('「A」と「B」と「C」', '"A"、"B"和"C"'), '「A」、「B」和「C」')

    print("== 引擎：单边引号 ==")
    h.check("单边开引号", r.repair_text_symbols('「こんにちは」', '“你好'), '「你好」')
    h.check("单边闭引号", r.repair_text_symbols('「こんにちは」', '你好”'), '「你好」')
    h.check("单边ASCII开引号", r.repair_text_symbols('「こんにちは」', '"你好'), '「你好」')
    h.check("单边ASCII闭引号", r.repair_text_symbols('「こんにちは」', '你好"'), '「你好」')

    print("== 引擎：无中生有引号 ==")
    h.check("无中生有「」", r.repair_text_symbols('こんにちは', '「你好」'), '你好')
    h.check("无中生有“”", r.repair_text_symbols('こんにちは', '“你好”'), '你好')
    h.check("无中生有ASCII", r.repair_text_symbols('こんにちは', '"你好"'), '你好')
    h.check("原文无引号译文正常", r.repair_text_symbols('こんにちは', '你好'), '你好')
    h.check("撇号保留", r.repair_text_symbols('それはdon\'tです。', "那是don't。"), "那是don't。")
    h.check("原文有“”译文“”不删", r.repair_text_symbols('“そうだ”', '“是啊”'), '“是啊”')


def test_engine_annotations(h, r):
    print("== 引擎：批注删除（收窄规则：仅删除命中批注关键词的括号段） ==")
    # --- 命中批注模式 → 删除 ---
    h.check("全角（注释：…）删除", r.repair_text_symbols('彼は学校に行った。', '他去了学校（注释：上午去的）。'), '他去了学校。')
    h.check("全角（注：…）删除", r.repair_text_symbols('彼は学校に行った。', '他去了学校（注：上午去的）。'), '他去了学校。')
    h.check("【补充说明：…】删除", r.repair_text_symbols('こんにちは。', '你好【补充说明：下午好】。'), '你好。')
    h.check("（译者注）无冒号删除", r.repair_text_symbols('彼は行った。', '他走了（译者注）。'), '他走了。')
    h.check("（作者注）删除", r.repair_text_symbols('彼は行った。', '他走了（作者注）。'), '他走了。')
    h.check("嵌套括号内批注整段删除", r.repair_text_symbols('こんにちは。', '（译者注：详见【附录】）你好。'), '你好。')
    h.check("半角(注：…)删除", r.repair_text_symbols('彼は学校に行った。', '他去了学校(注：上午)。'), '他去了学校。')
    h.check("英文(TL: …)删除", r.repair_text_symbols('彼は行った。', '他走了(TL: see above)。'), '他走了。')
    h.check("英文(Note: …)删除", r.repair_text_symbols('こんにちは。', '你好(Note: 你好)。'), '你好。')
    h.check("书名号保留+批注删除", r.repair_text_symbols('《銀河鉄道の夜》を読んだ。', '读了《银河铁道之夜》（译者注）。'), '读了《银河铁道之夜》。')
    h.check("URL内括号保护+批注删除", r.repair_text_symbols(
        '詳細はhttps://a.jp/item(a)をご覧ください。',
        '详情见https://a.jp/item(a)（译者注）。'),
        '详情见https://a.jp/item(a)。')
    h.check("批注删除幂等", r.repair_text_symbols('彼は学校に行った。', '他去了学校（注释）。'), '他去了学校。')

    # --- 未命中批注模式 → 一律保留（收窄的核心） ---
    h.check("【重要】保留", r.repair_text_symbols('彼は学校に行った。', '【重要】他来了。'), '【重要】他来了。')
    h.check("半角普通括号保留", r.repair_text_symbols('彼は学校に行った。', '他去了学校(上午)。'), '他去了学校(上午)。')
    h.check("嵌套普通括号保留", r.repair_text_symbols('こんにちは。', '（嵌套（测试）内容）你好。'), '（嵌套（测试）内容）你好。')
    h.check("孤立左括号保留", r.repair_text_symbols('こんにちは。', '他走了（'), '他走了（')
    h.check("孤立右括号保留", r.repair_text_symbols('こんにちは。', '他走了）'), '他走了）')
    h.check("括号内引号按引号规则处理", r.repair_text_symbols('彼は行った。', '他说（“走吧”）。'), '他说（走吧）。')
    h.check("（笑）保留", r.repair_text_symbols('彼は笑った。', '他笑了（笑）。'), '他笑了（笑）。')
    h.check("（注意）保留", r.repair_text_symbols('これは危険です。', '这很危险（注意）。'), '这很危险（注意）。')
    h.check("普通括号+批注并存", r.repair_text_symbols('彼は学校に行った。', '他去了学校（上午）（译者注：译名修正）。'), '他去了学校（上午）。')
    h.check("原文有括号不删", r.repair_text_symbols('（原文）内容です。', '内容（译文批注）。'), '内容（译文批注）。')
    h.check("无括号无批注原样", r.repair_text_symbols('こんにちは。', '你好。'), '你好。')


def test_engine_punctuation_and_protection(h, r):
    print("== 引擎：条件标点替换 ==")
    h.check("原文？→ 译文?转？", r.repair_text_symbols('本当ですか？', '真的吗?'), '真的吗？')
    h.check("原文无？→ 保持", r.repair_text_symbols('本当ですか。', '真的吗?'), '真的吗?')
    h.check("原文！→ 译文!转！", r.repair_text_symbols('すごい！', '好厉害!'), '好厉害！')
    h.check("原文无！→ 保持", r.repair_text_symbols('すごい。', '好厉害!'), '好厉害!')
    h.check("省略号", r.repair_text_symbols('それは…秘密です。', '那是...秘密。'), '那是…秘密。')
    h.check("省略号日式", r.repair_text_symbols('それは…秘密です。', '那是。。。秘密。'), '那是…秘密。')
    h.check("破折号", r.repair_text_symbols('彼は——言った。', '他说--'), '他说——')
    h.check("短破折号", r.repair_text_symbols('彼は—言った。', '他说--'), '他说—')

    print("== 引擎：保护段 ==")
    h.check("URL问号保护", r.repair_text_symbols(
        '最終更新：https://a.jp/r/?u=1&is_lid=0 です？',
        '最终更新：https://a.jp/r/?u=1&is_lid=0 是吗?'),
        '最终更新：https://a.jp/r/?u=1&is_lid=0 是吗？')
    h.check("Markdown链接保护", r.repair_text_symbols(
        '見て[ここ](https://e.com/a?x=1)ください！',
        '请看[这里](https://e.com/a?x=1)!'),
        '请看[这里](https://e.com/a?x=1)！')
    h.check("占位符保护", r.repair_text_symbols('これは{P0}ですか？', '这是{P0}吗?'), '这是{P0}吗？')
    h.check("HTML标签保护", r.repair_text_symbols('<b>大事</b>です？', '<b>重要</b>吗?'), '<b>重要</b>吗？')

    print("== 引擎：空白保留 ==")
    h.check("首尾空白", r.repair_text_symbols('  「こんにちは」  ', '  "你好"  '), '  「你好」  ')


def test_checker(h):
    print("== 检查器 ==")

    class FakeCacheManager:
        def __init__(self, project):
            self.project = project

    def make_project(items):
        file = CacheFile(storage_path='a.txt')
        for i, (src, dst, status) in enumerate(items):
            file.items.append(CacheItem(
                text_index=i,
                source_text=src,
                translated_text=dst,
                translation_status=status,
            ))
        project = CacheProject(project_id='t', project_type='Txt', project_name='t')
        project.files['a.txt'] = file
        return FakeCacheManager(project)

    # 空项目
    cm = FakeCacheManager(CacheProject(project_id='t'))
    code, data = SymbolRepairChecker(cm).run_repair({})
    h.check("空项目返回缓存错误", code, CheckResult.ERROR_CACHE)

    # 无翻译
    cm = make_project([('こんにちは', None, TranslationStatus.UNTRANSLATED)])
    code, data = SymbolRepairChecker(cm).run_repair({})
    h.check("无翻译返回错误", code, CheckResult.ERROR_NO_TRANSLATION)

    # 正常：2条需要修复，1条无需；普通括号不触发修复（收窄规则）
    cm = make_project([
        ('「こんにちは」', '"你好"', TranslationStatus.TRANSLATED),
        ('本当ですか？', '真的吗?', TranslationStatus.TRANSLATED),
        ('彼は学校に行った。', '他去了学校（上午）。', TranslationStatus.TRANSLATED),
    ])
    code, data = SymbolRepairChecker(cm).run_repair({})
    h.check("检查结果码", code, CheckResult.SUCCESS_SYMBOL_REPAIR_RESULT)
    rows = data["repair_rows"]
    h.check("待修复条数", len(rows), 2)
    h.check("扫描条数", data["total_scanned"], 3)
    by_src = {row["source"]: row for row in rows}
    h.check("行1修复后", by_src['「こんにちは」']["check_text"], '「你好」')
    h.check("行2修复后", by_src['本当ですか？']["check_text"], '真的吗？')
    h.check("行2修复前", by_src['本当ですか？']["before_text"], '真的吗?')
    h.check("row_number", by_src['本当ですか？']["row_number"], 2)
    h.check("普通括号行不标记", '彼は学校に行った。' not in by_src, True)

    # 润色状态保留
    cm = make_project([
        ('本当ですか？', '真的吗?', TranslationStatus.POLISHED),
    ])
    code, data = SymbolRepairChecker(cm).run_repair({})
    h.check("润色状态透传", data["repair_rows"][0]["translation_status"], TranslationStatus.POLISHED)


def main():
    h = Harness()
    r = TextSymbolRepair()
    test_engine_quotes(h, r)
    test_engine_annotations(h, r)
    test_engine_punctuation_and_protection(h, r)
    test_checker(h)
    print(f"\n结果: {h.passed} 通过, {h.failed} 失败")
    return 1 if h.failed else 0


if __name__ == "__main__":
    sys.exit(main())
