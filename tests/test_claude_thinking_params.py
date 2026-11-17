import unittest

from Backend.infrastructure.llm.model_config_helper import ModelConfigHelper


class ClaudeThinkingOffParamsTest(unittest.TestCase):
    def test_thinking_off_params_per_model(self):
        off = ModelConfigHelper.get_claude_thinking_off_params
        self.assertEqual(off("claude-fable-5-2"), {})
        self.assertEqual(off("claude-mythos-5-2"), {})
        self.assertEqual(off("claude-opus-5-5"), {"output_config": {"effort": "low"}})
        self.assertEqual(off("anthropic.claude-opus-5-5"), {"output_config": {"effort": "low"}})
        self.assertEqual(off("claude-sonnet-5-5"), {"thinking": {"type": "between_tools"}})
        for model in ("claude-opus-5", "claude-sonnet-5", "claude-haiku-5-5"):
            self.assertEqual(off(model), {"thinking": {"type": "disabled"}}, model)

    def test_haiku_5_is_supported(self):
        self.assertEqual(ModelConfigHelper.get_claude_max_output_tokens("claude-haiku-5-5"), 128000)
        with self.assertRaises(ValueError):
            ModelConfigHelper.get_claude_max_output_tokens("claude-haiku-4-5")


if __name__ == "__main__":
    unittest.main()
