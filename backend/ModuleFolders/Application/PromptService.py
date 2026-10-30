"""UI-independent prompt configuration, retaining desktop storage keys."""

from copy import deepcopy
from uuid import uuid4

from ModuleFolders.Application.Errors import ApplicationError
from ModuleFolders.Application.JsonValidation import validate_finite_json
from ModuleFolders.Application.OperationGuard import exclusive_operation
from ModuleFolders.Application.SettingsDefaults import fill_setting_defaults
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Base.Base import Base
from ModuleFolders.Domain.PromptBuilder.CharacterHelper import CharacterHelper
from ModuleFolders.Domain.PromptBuilder.PromptBuilder import PromptBuilder
from ModuleFolders.Domain.PromptBuilder.PromptBuilderEnum import PromptBuilderEnum
from ModuleFolders.Domain.PromptBuilder.PromptBuilderExtraction import PromptBuilderExtraction
from ModuleFolders.Domain.PromptBuilder.PromptBuilderPolishing import PromptBuilderPolishing


class PromptService(ConfigMixin):
    LIBRARIES = {
        "system": ("translation_prompt_selection", "translation_user_prompt_data"),
        "polish": ("polishing_prompt_selection", "polishing_user_prompt_data"),
        "analysis_basic": ("extract_prompt_selection", "extract_user_prompt_data"),
        "analysis_judgment": ("extract_judgment_prompt_selection", "extract_judgment_user_prompt_data"),
    }
    TEXTS = {
        "world": ("world_building", "故事发生在魔法世界，到三十岁还保持童贞，就可以学会大火球魔法，成为魔法师。"),
        "style": ("writing_style", "根据原文语境，可以适当调整，使表达更生动形象，提升译文的冲击力与张力。"),
    }
    ROWS = {"characters": "characterization", "examples": "translation_example"}

    def _presets(self, kind, config):
        if kind == "system":
            return [{"id": value, "name": name, "content": PromptBuilder.get_system_default(config, value), "type": "system"}
                    for value, name in ((PromptBuilderEnum.COMMON, "通用"), (PromptBuilderEnum.COT, "思维链"), (PromptBuilderEnum.LOCAL, "本地模型"))]
        if kind == "polish":
            return [{"id": PromptBuilderEnum.POLISH_COMMON, "name": "通用", "content": PromptBuilderPolishing.get_system_default(config), "type": "system"}]
        stage = "basic" if kind == "analysis_basic" else "judgment"
        return [{"id": PromptBuilderExtraction.STAGES[stage]["preset_id"], "name": "通用", "content": PromptBuilderExtraction.get_system_default(stage), "type": "system"}]

    def _library(self, kind, config):
        if kind not in self.LIBRARIES:
            raise ApplicationError("prompt_kind_invalid", 404)
        selection_key, custom_key = self.LIBRARIES[kind]
        presets = self._presets(kind, config)
        custom = deepcopy(config.get(custom_key, []))
        custom = [row for row in custom if isinstance(row, dict) and all(key in row for key in ("id", "name", "content"))]
        selection = config.get(selection_key, {})
        selected_id = selection.get("last_selected_id")
        if not any(str(row["id"]) == str(selected_id) for row in presets + custom):
            selected_id = presets[0]["id"]
        return {"presets": presets, "custom": custom, "selected_id": selected_id}

    def get_library(self, kind):
        return self._library(kind, fill_setting_defaults(self.load_config()))

    def _document(self, kind, config):
        if kind in self.LIBRARIES:
            library = self._library(kind, config)
            selected = next(row for row in library["presets"] + library["custom"] if str(row["id"]) == str(library["selected_id"]))
            selection = config.get(self.LIBRARIES[kind][0], {})
            content = selection.get("prompt_content", selected["content"]) if str(selection.get("last_selected_id")) == str(selected["id"]) else selected["content"]
            return {"enabled": True, "content": content, "selected_id": selected["id"], "rows": []}
        if kind in self.TEXTS:
            key, default = self.TEXTS[kind]
            return {"enabled": bool(config.get(key + "_switch", False)), "content": config.get(key + "_content", default), "rows": [], "selected_id": None}
        if kind in self.ROWS:
            key = self.ROWS[kind]
            rows = deepcopy(config.get(key + "_data", []))
            if kind == "characters":
                rows = CharacterHelper.normalize_rows(rows)
            return {"enabled": bool(config.get(key + "_switch", False)), "rows": rows, "content": "", "selected_id": None}
        raise ApplicationError("prompt_kind_invalid", 404)

    def get(self, kind):
        return self._document(kind, fill_setting_defaults(self.load_config()))

    def put(self, kind, document):
        try:
            validate_finite_json(document)
        except ValueError as error:
            raise ApplicationError("prompt_invalid") from error
        def update(config):
            if kind in self.TEXTS:
                key, _ = self.TEXTS[kind]
                config[key + "_switch"] = document.get("enabled", False)
                config[key + "_content"] = document.get("content", "")
            elif kind in self.ROWS:
                key = self.ROWS[kind]
                rows = deepcopy(document.get("rows", []))
                if kind == "characters":
                    rows = [row for row in CharacterHelper.normalize_rows(rows) if row.get("original_name")]
                else:
                    rows = [{**row, "src": str(row.get("src", "")).strip(), "dst": str(row.get("dst", "")).strip()} for row in rows if str(row.get("src", "")).strip()]
                config[key + "_switch"] = document.get("enabled", False)
                config[key + "_data"] = rows
            elif kind in self.LIBRARIES:
                library = self._library(kind, fill_setting_defaults(config))
                selected = next((row for row in library["presets"] + library["custom"] if str(row["id"]) == str(document.get("selected_id"))), None)
                if selected is None:
                    raise ApplicationError("prompt_not_found", 404)
                selection_key = self.LIBRARIES[kind][0]
                config[selection_key] = {**config.get(selection_key, {}), "last_selected_id": selected["id"], "prompt_content": selected["content"]}
            else:
                raise ApplicationError("prompt_kind_invalid", 404)
        with exclusive_operation():
            config = self.update_config(update)
        Base().emit(Base.EVENT.PROMPTS_CHANGED, {"kind": kind})
        return self._document(kind, fill_setting_defaults(config))

    def upsert(self, kind, document):
        try:
            validate_finite_json(document)
        except ValueError as error:
            raise ApplicationError("prompt_invalid") from error
        if kind not in self.LIBRARIES:
            raise ApplicationError("prompt_kind_invalid", 404)
        if not document.get("name", "").strip() or not document.get("content", "").strip():
            raise ApplicationError("prompt_invalid")
        def update(config):
            library = self._library(kind, fill_setting_defaults(config))
            selection_key, custom_key = self.LIBRARIES[kind]
            identifier = document.get("id")
            if any(str(preset["id"]) == str(identifier) for preset in library["presets"]):
                raise ApplicationError("prompt_readonly", 409)
            prompts = deepcopy(config.get(custom_key, []))
            position = next((index for index, prompt in enumerate(prompts) if str(prompt.get("id")) == str(identifier)), None) if identifier else None
            if identifier and position is None:
                raise ApplicationError("prompt_not_found", 404)
            prior = prompts[position] if position is not None else {}
            prompt = {**prior, **{key: value for key, value in document.items() if key != "select"}, "id": identifier or str(uuid4()), "name": document["name"].strip(), "content": document["content"], "type": "user"}
            if position is None:
                prompts.append(prompt)
            else:
                prompts[position] = prompt
            config[custom_key] = prompts
            selection = config.get(selection_key, {})
            if document.get("select", True) or str(selection.get("last_selected_id")) == str(prompt["id"]):
                config[selection_key] = {**selection, "last_selected_id": prompt["id"], "prompt_content": prompt["content"]}
        with exclusive_operation():
            config = self.update_config(update)
        Base().emit(Base.EVENT.PROMPTS_CHANGED, {"kind": kind})
        return self._library(kind, fill_setting_defaults(config))

    def delete(self, kind, identifier):
        def update(config):
            library = self._library(kind, fill_setting_defaults(config))
            if any(str(preset["id"]) == str(identifier) for preset in library["presets"]):
                raise ApplicationError("prompt_readonly", 409)
            selection_key, custom_key = self.LIBRARIES[kind]
            prompts = config.get(custom_key, [])
            if not any(str(prompt.get("id")) == str(identifier) for prompt in prompts):
                raise ApplicationError("prompt_not_found", 404)
            config[custom_key] = [prompt for prompt in prompts if str(prompt.get("id")) != str(identifier)]
            selection = config.get(selection_key, {})
            if str(selection.get("last_selected_id")) == str(identifier):
                preset = library["presets"][0]
                config[selection_key] = {**selection, "last_selected_id": preset["id"], "prompt_content": preset["content"]}
        with exclusive_operation():
            config = self.update_config(update)
        Base().emit(Base.EVENT.PROMPTS_CHANGED, {"kind": kind})
        return self._library(kind, fill_setting_defaults(config))
