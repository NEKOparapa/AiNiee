import unittest
from types import SimpleNamespace

from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderLocal import PromptBuilderLocal


class PromptBuilderLocalTests(unittest.TestCase):
    def setUp(self):
        self.source_lang = "japanese"
        self.source_text_dict = {"0": "远坂凛今天会去教会。"}

    def make_config(self, **overrides):
        config = {
            "target_language": "chinese_simplified",
            "prompt_dictionary_switch": False,
            "prompt_dictionary_data": [],
            "characterization_switch": False,
            "characterization_data": [
                {
                    "original_name": "远坂[Separator]凛",
                    "translated_name": "远坂凛",
                    "gender": "女",
                    "age": "少女",
                    "personality": "高傲",
                    "speech_style": "大小姐",
                    "additional_info": "魔术师",
                }
            ],
            "world_building_switch": False,
            "world_building_content": "故事发生在有魔术协会的现代世界。",
            "writing_style_switch": False,
            "writing_style_content": "保持冷静、克制、文学化的表达。",
            "translation_example_switch": False,
            "translation_example_data": [
                {"src": "こんにちは。", "dst": "你好。"},
                {"src": "さようなら。", "dst": "再见。"},
            ],
        }
        config.update(overrides)
        return SimpleNamespace(**config)

    def test_single_sections_are_appended_when_enabled(self):
        cases = [
            (
                "characterization_switch",
                lambda config: PromptBuilder.build_characterization(config, self.source_text_dict),
            ),
            (
                "world_building_switch",
                lambda config: PromptBuilder.build_world_building(config),
            ),
            (
                "writing_style_switch",
                lambda config: PromptBuilder.build_writing_style(config),
            ),
            (
                "translation_example_switch",
                lambda config: PromptBuilder.build_translation_example(config),
            ),
        ]

        for switch_name, build_section in cases:
            with self.subTest(switch=switch_name):
                config = self.make_config(**{switch_name: True})

                messages, system, extra_log = PromptBuilderLocal.generate_prompt_LocalLLM(
                    config,
                    self.source_text_dict,
                    [],
                    self.source_lang,
                )

                expected_section = build_section(config)
                self.assertTrue(expected_section)
                self.assertIn(expected_section, system)
                self.assertEqual(extra_log, [expected_section])
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0]["role"], "user")

    def test_all_sections_follow_expected_order(self):
        config = self.make_config(
            characterization_switch=True,
            world_building_switch=True,
            writing_style_switch=True,
            translation_example_switch=True,
        )

        _, system, extra_log = PromptBuilderLocal.generate_prompt_LocalLLM(
            config,
            self.source_text_dict,
            [],
            self.source_lang,
        )

        expected_sections = [
            PromptBuilder.build_characterization(config, self.source_text_dict),
            PromptBuilder.build_world_building(config),
            PromptBuilder.build_writing_style(config),
            PromptBuilder.build_translation_example(config),
        ]

        self.assertEqual(extra_log, expected_sections)

        section_positions = [system.index(section) for section in expected_sections]
        self.assertEqual(section_positions, sorted(section_positions))

    def test_disabled_sections_do_not_change_baseline_local_prompt(self):
        config = self.make_config()

        messages, system, extra_log = PromptBuilderLocal.generate_prompt_LocalLLM(
            config,
            self.source_text_dict,
            [],
            self.source_lang,
        )

        self.assertEqual(system, PromptBuilderLocal.build_system(config, self.source_lang))
        self.assertEqual(extra_log, [])
        self.assertEqual(len(messages), 1)
        self.assertNotIn("###角色介绍", system)
        self.assertNotIn("###背景设定", system)
        self.assertNotIn("###翻译风格", system)
        self.assertNotIn("###翻译示例", system)

    def test_empty_manual_translation_examples_do_not_add_section(self):
        config = self.make_config(
            translation_example_switch=True,
            translation_example_data=[],
        )

        _, system, extra_log = PromptBuilderLocal.generate_prompt_LocalLLM(
            config,
            self.source_text_dict,
            [],
            self.source_lang,
        )

        self.assertNotIn("###翻译示例", system)
        self.assertEqual(extra_log, [])


if __name__ == "__main__":
    unittest.main()
