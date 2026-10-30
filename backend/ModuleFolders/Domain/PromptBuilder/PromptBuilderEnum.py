from ModuleFolders.Base.Base import Base

class PromptBuilderEnum(Base):

    COMMON = 100
    COT = 200
    LOCAL = 400
    CUSTOM = 1000

    POLISH_COMMON = 10001

    FORMAT_COMMON = 20001

    EXTRACT_COMMON = 30001
    EXTRACT_JUDGMENT = 30002

    @classmethod
    def normalize_translation_preset(cls, preset_id):
        # 300 was the removed reasoning-model preset in older configurations.
        return cls.COMMON if preset_id in (300, "300") else preset_id
