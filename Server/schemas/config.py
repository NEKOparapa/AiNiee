from pydantic import ConfigDict, JsonValue, RootModel


class ConfigDocument(RootModel[dict[str, JsonValue]]):
    """Existing config.json object, including preserved extension keys."""

    model_config = ConfigDict(allow_inf_nan=False)


class ConfigPatch(ConfigDocument):
    """Provided top-level keys replace their values; omitted keys are preserved."""
