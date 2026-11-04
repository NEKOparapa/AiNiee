"""Request error diagnostics shared with routes that sanitize validation errors."""
import logging
import traceback

from Backend.core.log_system import redact


def log_request_error(request, code, message, *, error=None):
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    text = f"后端请求错误：{request.method} {path} [{code}] {message}"
    if error is not None:
        text += "\n" + "".join(traceback.format_exception(type(error), error, error.__traceback__))
    # Never include headers, query strings, request bodies, or validation input.
    logging.getLogger("AiNiee.backend").error(redact(text))


def validation_details(error):
    return [{"loc": [redact(part) for part in issue["loc"]],
             "type": issue["type"], "msg": redact(issue["msg"])} for issue in error.errors()]


def log_validation_error(request, details):
    message = "；".join(f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}" for issue in details)
    log_request_error(request, "VALIDATION_ERROR", message)
