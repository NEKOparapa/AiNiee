"""Server filesystem defaults displayed by path-setting widgets."""
from Frontend.services.editor import call_editor


def default_input_dir():
    return call_editor("paths.input")


def default_output_dir():
    return call_editor("paths.output")


def default_polish_output_dir():
    return call_editor("paths.polish")


def auto_output_dir(path):
    return call_editor("paths.auto_output", path)


def auto_polish_output_dir(path):
    return call_editor("paths.auto_polish", path)
