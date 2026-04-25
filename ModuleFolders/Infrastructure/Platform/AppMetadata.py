import re


APP_DISPLAY_NAME = "AiNiee"
APP_ORGANIZATION = "NEKOparapa"
APP_ORGANIZATION_DOMAIN = "github.com/NEKOparapa"


def semantic_version(raw_version: str) -> str:
    # Qt 的应用版本只接受纯数字版本号，这里从展示版本中提取语义化部分。
    match = re.search(r"\d+(?:\.\d+){1,3}", raw_version)
    return match.group(0) if match else "0.0.0"


def configure_application_metadata(app, version: str) -> None:
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setApplicationVersion(semantic_version(version))
    app.setOrganizationName(APP_ORGANIZATION)
    app.setOrganizationDomain(APP_ORGANIZATION_DOMAIN)
    if hasattr(app, "setApplicationDisplayName"):
        app.setApplicationDisplayName(APP_DISPLAY_NAME)
