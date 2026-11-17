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



class ClaudeFallbackAndCacheTest(unittest.TestCase):
    def test_fallback_only_on_official_api_and_supported_models(self):
        fb = ModelConfigHelper.get_claude_fallback_params
        expected = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        for model in ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2"):
            self.assertEqual(fb(model, "https://api.anthropic.com"), expected, model)
        self.assertEqual(fb("claude-opus-5-5", None), expected)
        self.assertEqual(fb("claude-haiku-5-5", "https://api.anthropic.com"), {})
        self.assertEqual(fb("claude-sonnet-5", "https://api.anthropic.com"), {})
        self.assertEqual(fb("claude-opus-5-5", "https://proxy.example.com"), {})

    def test_build_claude_system_splits_at_stable_prefix(self):
        build = ModelConfigHelper.build_claude_system
        self.assertEqual(build("abc", 0), "abc")
        self.assertEqual(build("abc", None), "abc")
        self.assertEqual(build("abc", 4), "abc")
        self.assertEqual(build("stable|dynamic", 7), [
            {"type": "text", "text": "stable|", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "dynamic"},
        ])
        self.assertEqual(build("stable", 6), [
            {"type": "text", "text": "stable", "cache_control": {"type": "ephemeral"}},
        ])


if __name__ == "__main__":
    unittest.main()
