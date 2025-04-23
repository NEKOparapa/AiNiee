import re 
from ..PluginBase import PluginBase

class TextLayoutRepairPlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.name = "TextLayoutRepairPlugin"
        self.description = "文本排版修复插件"+ "\n"+ "根据原文恢复译文中改变的标点符号和排版格式"

        self.visibility = True  # 是否在插件设置中显示
        self.default_enable = False  # 默认启用状态

        self.add_event("postprocess_text", PluginBase.PRIORITY.LOWEST)  # 添加感兴趣的事件和优先级
        self.add_event("manual_export", PluginBase.PRIORITY.LOWEST)


    def load(self):
        pass

    def on_event(self, event_name, config, event_data):
        if event_name in ("manual_export", "postprocess_text"):
            self.process_dictionary_list(event_data)

    def process_dictionary_list(self, cache_list):
        for entry in cache_list:
            storage_path = entry.get("storage_path")

            if storage_path:
                source_text = entry.get("source_text")
                translated_text = entry.get("translated_text")
                translation_status = entry.get("translation_status")

                # 仅处理已翻译的条目
                if source_text and translated_text and translation_status == 1:
                    entry["translated_text"] = self.fix_typography(source_text, translated_text)


    def fix_typography(self, original_text: str, translated_text: str) -> str:
        """
        修复译文的排版，分阶段处理首尾和内部标点。

        Args:
            original_text: 原始文本字符串。
            translated_text: 需要修复排版的译文文本字符串。

        Returns:
            修复排版后的译文文本字符串。
        """
        if not isinstance(original_text, str) or not isinstance(translated_text, str):
            return translated_text

        # --- 阶段 0: 处理前后缀空白 ---
        leading_whitespace_match = re.match(r"^(\s*)", original_text)
        trailing_whitespace_match = re.search(r"(\s*)$", original_text)
        leading_whitespace = leading_whitespace_match.group(1) if leading_whitespace_match else ""
        trailing_whitespace = trailing_whitespace_match.group(1) if trailing_whitespace_match else ""

        # 处理原文与译文的首尾空白
        original_stripped = original_text.strip()
        translated_stripped = translated_text.strip()

        # 如果原文或译文为空，则直接返回译文
        if not original_stripped or not translated_stripped:
            return translated_text

        # 平常内容是:说话文本
        # 或者是:说话文本+其他文本
        # 或者是:其他文本+说话文本       
        # 但有些内容是:说话文本+说话文本+说话文本
        # 也有些内容是:说话文本+其他文本+说话文本
        # 也有些内容是:其他文本+说话文本+其他文本
        # 例如：
        # "source_text": '「文句を言う前に、俺に謝るのが筋じゃないか」と少年は砂を払いながら、掠れて大人びた声でいきなり言った。「人様の楽しみを無茶苦茶にしておいて、貴方は謝罪もできないのか」',
        # "translated_text": '"在抱怨之前，先向我道歉才是道理吧"少年一边拍打身上的沙子，突然用沙哑而老成的语气说道。"把别人的快乐搅得一团糟，你连道歉都不会吗"',

        #"source_text": "「息子さんが結婚したの。それはおめでとうございます」乾杯。「めでたいものか、ちくしょう」「まあまあ」乾杯。「俺が育てたのに自分で勝手に育ったようなツラをする」「親はなくても子は育つ」「俺は居ても居なくても一緒かい」「そんなわけないでしょう社長さん」乾杯。",
        #"translated_text": '"儿子结婚了啊。那可要恭喜""干杯。""有什么好恭喜的，混蛋""好啦好啦"干杯。"明明是我养大的，却摆出一副自己长大的嘴脸""没有父母孩子照样能长大""我在不在都一样是吧""怎么会呢社长"干杯。',

        #"source_text": "「東堂さん」と私は叫び、続いて「お父さん」と呟いたのは新婦でした。",
        #"translated_text": '"东堂先生"我喊道，接着轻声说出"爸爸"的是新娘。',

        #"source_text": "その日は銀閣寺交番の前で待ち合わせをしました。哲学の道沿いの桜並木もすっかり冬の風に葉を散らしてしまって、あの砂糖菓子のような満開の桜を想像することもできない淋しい風景です。ぴうぴう吹く風に私の髪も散ってしまいそう。寒い寒いようと思いながら大文字山を見上げ、「北風小僧の寒太郎」を口ずさんでいると、やがて紀子さんと元パンツ総番長が二人でやって来ました。彼らはお見舞いの品をたくさん持っています。「やあ、その後いかがですか」と、元パンツ総番長が晴れ晴れとした顔で言いました。彼は宿願であった紀子さんとの再会を果たし、パンツを決して穿き替えないという荒行から足を洗った身、下半身の病気ともサヨナラして、ずいぶんと御機嫌でした。まことに喜ばしいことです。",
        #"translated_text": '那天我们在银阁寺派出所前碰头。哲学之道两旁的樱花树早已被冬风吹落叶子，完全想象不出那些像糖果般盛开的樱花，只剩一片萧瑟景象。寒风呼啸，我的头发都快被吹散了。我一边想着"好冷好冷"，一边仰望着大文字山，哼着《北风小子寒太郎》的调子，不久纪子小姐和前内裤总长就一起来了。他们带了很多慰问品。"哟，最近怎么样啊？"前内裤总长神清气爽地说道。他实现了与纪子小姐重逢的心愿，也告别了"绝不换内裤"的苦行，连下半身的疾病都痊愈了，显得特别高兴。真是可喜可贺。',

        #"source_text": "“하악…! 허윽, 하악!”",
        #"translated_text": '"哈啊…! 呃啊，哈啊!"',


        # --- 阶段 1: 处理仅首尾有符号的说话文本 --
        # 成对型标点检查映射
        # 格式: (原文开始符, 原文结束符, [译文可能替代开始符], [译文可能替代结束符])
        boundary_punctuation_pairs = [
            ('「', '」', ['“', '‘', '"'], ['”', '’', '"']),
            ('『', '』', ['“', '‘', '"'], ['”', '’', '"']),
            ('“', '”', ['‘', '"'], ['’', '"']),
            ('‘', '’', ['“', '"'], ['”', '"']),
            # 可以添加更多首尾标点对，例如 ('(', ')', ['（'], ['）']) 等
        ]

        for orig_start, orig_end, alt_starts, alt_ends in boundary_punctuation_pairs:
            # 检查原文的开头与结尾标点，且只有一个成对标点
            if original_stripped.startswith(orig_start) and original_stripped.endswith(orig_end) and original_stripped.count(orig_start) == 1 and original_stripped.count(orig_end) == 1:
                matched_alt = False
                for i, alt_start in enumerate(alt_starts):

                    alt_end = alt_ends[i]
                    # 检查译文是否以对应的替代标点开头和结尾
                    if translated_stripped.startswith(alt_start) and translated_stripped.endswith(alt_end):

                        # 替换译文的首尾标点为原文的标点
                        inner_text = translated_stripped[len(alt_start):-len(alt_end)]    # 截取掉译文的首尾标点
                        translated_stripped = orig_start + inner_text + orig_end  # 用原文标点包裹

                        # 处理完当前原文标点对后，跳出循环
                        matched_alt = True
                        break # 找到匹配的替代项后，不再尝试其他替代项

                if matched_alt:
                    break # 处理完当前原文标点对后，不再尝试其他原文标点对


        # --- 阶段2: 处理其他类型文本 ---
        # 1. 定义原文和译文的内部引号
        orig_internal_start = '「'
        orig_internal_end = '」'
        trans_internal_quote = '"' # 英文双引号，开始和结束相同

        # 2. 检查原文中是否有成对的「 和 」，并计算对数
        orig_start_count = original_stripped.count(orig_internal_start)
        orig_end_count = original_stripped.count(orig_internal_end)

        # 3. 检查译文中是否有成对的英文双引号，并计算数量
        trans_quote_count = translated_stripped.count(trans_internal_quote)

        # 4. 条件判断：
        #    - 原文中「 和 」数量相等且大于0
        #    - 译文中 " 数量是偶数且大于0
        #    - 原文中的对数 == 译文中的对数 
        if ((orig_start_count > 0 and orig_start_count == orig_end_count) and (trans_quote_count > 0 and trans_quote_count % 2 == 0) and (orig_start_count == trans_quote_count // 2)):

            # 5. 执行替换：从左到右，依次将 " 替换为 「 和 」
            temp_translated_list = list(translated_stripped) # 转为列表方便修改
            quote_indices = [i for i, char in enumerate(temp_translated_list) if char == trans_internal_quote]

            open_quote = True # 标记下一个应该是开引号还是闭引号
            replacements_done = 0
            
            # 确保找到的引号数量和预期一致
            if len(quote_indices) == trans_quote_count:

                for index in quote_indices:
                    if open_quote:
                        temp_translated_list[index] = orig_internal_start # 直接修改列表
                    else:
                        temp_translated_list[index] = orig_internal_end # 直接修改列表
                        replacements_done += 1
                    open_quote = not open_quote # 切换状态

                translated_stripped = "".join(temp_translated_list) # 转换回字符串




        # --- 阶段3: 处理内部可以全局替换的标点符号 ---
        # 定义标点替换映射：key 是原文期望的标点，value 是译文中可能出现的需要被替换的标点列表
        punctuation_map = {
            '…': ['...', '。。。'], # 中文省略号 替换 英文省略号 或 多个句号
            '—': ['--', '-', '——'],   # 中文破折号 替换 两个连字符、单个连字符 或 加长破折号
            '！': ['!'],          # 中文感叹号 替换 英文感叹号
            '？': ['?'],          # 中文问号 替换 英文问号
        }

        # 遍历标点映射表
        for original_punc, alternative_puncs in punctuation_map.items():
            # 遍历该原文标点对应的所有可能替代标点
            for alt_punc in alternative_puncs:
                # 在译文中全局替换替代标点为原文标点
                translated_stripped = translated_stripped.replace(alt_punc, original_punc)


        # --- 最终处理: 还原前后空白 ---
        # 将处理过的核心文本与原文的前后空白结合
        result = leading_whitespace + translated_stripped + trailing_whitespace
        return result