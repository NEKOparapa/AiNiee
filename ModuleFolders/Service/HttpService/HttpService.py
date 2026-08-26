import threading
import json
import re
import urllib.request
import urllib.error
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType
from ModuleFolders.Service.Cache.CacheItem import TranslationStatus


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """支持多线程处理的 HTTP Server"""
    daemon_threads = True


class RequestHandler(BaseHTTPRequestHandler):
    """处理 HTTP 请求：薄分发层，所有业务逻辑在 HttpService 的 handler 方法里。

    handler 签名: (params: dict, client_ip: str) -> tuple[dict, int]
    """

    def log_message(self, format, *args):
        # 屏蔽默认的控制台日志，避免刷屏
        pass

    def _write(self, body: dict, code: int) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch(self, method: str) -> None:
        service = self.server.service_instance
        raw_path = self.path.split("?", 1)[0]
        path = raw_path.lower().rstrip("/") or "/"
        table = service._get_routes if method == "GET" else service._post_routes
        handler = table.get(path)
        if handler is None:
            self._write({"status": "error", "message": f"Unknown command: {raw_path}"}, 404)
            return

        params = {}
        if method == "POST":
            try:
                length = int(self.headers.get("Content-Length", 0) or 0)
                if length > 0:
                    params = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(params, dict):
                    self._write({"status": "error", "message": "JSON body must be an object"}, 400)
                    return
            except (ValueError, json.JSONDecodeError) as e:
                self._write({"status": "error", "message": f"Invalid JSON: {e}"}, 400)
                return

        try:
            body, code = handler(params, self.client_address[0])
        except Exception as e:
            service.error(f"处理请求时发生错误: {e}")
            body, code = {"status": "error", "message": str(e)}, 500
        self._write(body, code)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


class HttpService(ConfigMixin, LogMixin, Base):
    def __init__(self):
        super().__init__()
        self.httpd = None
        self.server_thread = None

        # 依赖对象
        self.cache_manager = None
        self.file_reader = None

        # 异步任务结果暂存（emit 是发射即返回，*_DONE 事件晚到，这里订阅并暂存供轮询）
        self._result_lock = threading.Lock()
        self._latest = {
            key: {"seq": 0, "running": False, "payload": None, "received_at": 0}
            for key in ("analysis", "glossary", "apitest")
        }

        # 订阅事件
        self.subscribe(Base.EVENT.TASK_COMPLETED, self.on_task_completed)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.on_app_shutdown)
        self.subscribe(Base.EVENT.ANALYSIS_TASK_DONE, self._on_analysis_done)
        self.subscribe(Base.EVENT.GLOSS_TASK_DONE, self._on_gloss_done)
        self.subscribe(Base.EVENT.API_TEST_DONE, self._on_apitest_done)

        self._build_routes()

    def _build_routes(self) -> None:
        self._get_routes = {
            "/api/status": self._h_status,
            "/api/stop": self._h_stop,
            "/api/translate": self._h_translate_get,          # 旧别名，向后兼容
            "/api/analysis/result": lambda p, ip: self._result_response("analysis"),
            "/api/analysis/data": self._h_analysis_data,
            "/api/glossary/result": lambda p, ip: self._result_response("glossary"),
            "/api/apitest/result": lambda p, ip: self._result_response("apitest"),
            "/api/cache/stats": self._h_cache_stats,
        }
        self._post_routes = {
            "/api/task/start": self._h_task_start,
            "/api/translate": self._h_translate_post,         # 旧别名，向后兼容
            "/api/project/load": self._h_project_load,
            "/api/analysis/start": self._h_analysis_start,
            "/api/glossary/translate": self._h_glossary_translate,
            "/api/apitest": self._h_apitest,
            "/api/export": self._h_export,
            "/api/cache/save": self._h_cache_save,
            "/api/cache/search": self._h_cache_search,
            "/api/cache/update": self._h_cache_update,
            "/api/cache/replace": self._h_cache_replace,
        }

    def set_dependencies(self, cache_manager, file_reader):
        """设置依赖对象（在主程序中调用）"""
        self.cache_manager = cache_manager
        self.file_reader = file_reader

    def check_project_loaded(self) -> bool:
        """检查项目是否已加载"""
        if not self.cache_manager:
            return False
        return self.cache_manager.get_item_count() > 0

    def get_app_status(self) -> str:
        """获取当前应用任务状态字符串。"""
        if Base.work_status == Base.STATUS.TASKING:
            return "TASKING"
        if Base.work_status == Base.STATUS.STOPING:
            return "STOPPING"
        if Base.work_status == Base.STATUS.TASKSTOPPED:
            return "STOPPED"
        return "IDLE"

    @staticmethod
    def _parse_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    # ----------------------------- 通用守卫 -----------------------------
    def _deps_ready(self):
        if not self.cache_manager or not self.file_reader:
            return ({"status": "error", "message": "服务未就绪（依赖未注入）"}, 503)
        return None

    def _require_project(self):
        if not self.check_project_loaded():
            return ({"status": "error", "code": "no_project",
                     "message": "AiNiee 当前没有已加载的项目，请先加载项目"}, 409)
        return None

    def _require_idle(self):
        if Base.work_status != Base.STATUS.IDLE:
            return ({"status": "error", "code": "busy",
                     "message": "需要 AiNiee 处于空闲(IDLE)状态才能开始该任务"}, 409)
        return None

    def _require_idle_or_stopped(self):
        if Base.work_status not in (Base.STATUS.IDLE, Base.STATUS.TASKSTOPPED):
            return ({"status": "error", "code": "busy",
                     "message": "翻译任务进行中，请停止或等待完成后再修改缓存"}, 409)
        return None

    # ----------------------------- 异步结果暂存 -----------------------------
    def _stash_reset(self, key: str) -> None:
        with self._result_lock:
            slot = self._latest[key]
            slot["running"] = True
            slot["payload"] = None
            slot["seq"] += 1

    def _stash_done(self, key: str, payload: dict) -> None:
        with self._result_lock:
            slot = self._latest[key]
            slot["payload"] = payload
            slot["running"] = False
            slot["received_at"] = time.time()

    def _on_analysis_done(self, event: int, data: dict) -> None:
        self._stash_done("analysis", data)

    def _on_gloss_done(self, event: int, data: dict) -> None:
        self._stash_done("glossary", data)

    def _on_apitest_done(self, event: int, data: dict) -> None:
        self._stash_done("apitest", data)

    def _result_response(self, key: str):
        with self._result_lock:
            slot = dict(self._latest[key])
        if slot["payload"] is not None:
            return ({"status": "success", "running": False, "has_result": True,
                     "result": slot["payload"], "seq": slot["seq"],
                     "received_at": slot.get("received_at", 0)}, 200)
        if slot["running"]:
            return ({"status": "pending", "running": True, "has_result": False,
                     "seq": slot["seq"]}, 202)
        return ({"status": "empty", "running": False, "has_result": False,
                 "seq": slot["seq"]}, 200)

    # ----------------------------- 状态 -----------------------------
    def build_status_response(self) -> dict:
        """构建当前应用状态与翻译任务进度响应。"""
        project = getattr(self.cache_manager, "project", None) if self.cache_manager else None
        has_project = project is not None
        project_id = getattr(project, "project_id", "") if has_project else ""
        project_name = getattr(project, "project_name", "") if has_project else ""

        stats = {}
        stats_data = getattr(project, "stats_data", None) if has_project else None
        if stats_data is not None:
            if hasattr(stats_data, "to_dict"):
                stats = stats_data.to_dict()
            elif isinstance(stats_data, dict):
                stats = stats_data

        total_line = self._parse_int(stats.get("total_line", 0))
        line = self._parse_int(stats.get("line", 0))
        remaining_line = max(0, total_line - line)
        percent = round(line / total_line * 100, 2) if total_line > 0 else 0.0
        is_complete = total_line > 0 and line >= total_line

        start_time = self._parse_float(stats.get("start_time", 0))
        recorded_time = self._parse_float(stats.get("time", 0))
        if Base.work_status in (Base.STATUS.TASKING, Base.STATUS.STOPING) and start_time > 0:
            elapsed_seconds = int(max(0, time.time() - start_time))
        else:
            elapsed_seconds = int(max(0, recorded_time))

        return {
            "status": "success",
            "app_status": self.get_app_status(),
            "work_status_code": Base.work_status,
            "has_project": has_project,
            "project_id": project_id,
            "project_name": project_name,
            "progress": {
                "total_line": total_line,
                "line": line,
                "remaining_line": remaining_line,
                "percent": percent,
                "is_complete": is_complete,
                "total_requests": self._parse_int(stats.get("total_requests", 0)),
                "error_requests": self._parse_int(stats.get("error_requests", 0)),
                "token": self._parse_int(stats.get("token", 0)),
                "total_completion_tokens": self._parse_int(stats.get("total_completion_tokens", 0)),
                "elapsed_seconds": elapsed_seconds,
            },
        }

    def _h_status(self, params, ip):
        resp = self.build_status_response()
        with self._result_lock:
            resp["async"] = {
                k: {"running": v["running"], "seq": v["seq"], "has_result": v["payload"] is not None}
                for k, v in self._latest.items()
            }
        return (resp, 200)

    # ----------------------------- 项目加载 -----------------------------
    def load_project(self) -> bool:
        """直接加载新项目（不检查缓存）"""
        try:
            config = self.load_config()
            translation_project = config.get("translation_project", "AutoType")
            label_input_path = config.get("label_input_path", "./input")
            label_input_exclude_rule = config.get("label_input_exclude_rule", "")

            self.info(f"开始加载项目文件...")
            self.info(f"项目类型: {translation_project}")
            self.info(f"输入路径: {label_input_path}")

            # 直接读取文件并加载到缓存
            CacheProject = self.file_reader.read_files(
                translation_project,
                label_input_path,
                label_input_exclude_rule
            )
            self.cache_manager.load_from_project(CacheProject)

            item_count = self.cache_manager.get_item_count()
            if item_count == 0:
                raise ValueError("项目数据为空，请检查项目类型和输入文件夹设置")

            self.info(f"项目加载成功，共 {item_count} 条数据")

            # 打印文件信息
            for _, file in self.cache_manager.project.files.items():
                self.info(f"  - {file.storage_path} ({file.file_project_type})")

            return True

        except Exception as e:
            self.error(f"加载项目失败: {e}")
            return False

    def _h_project_load(self, params, ip):
        guard = self._deps_ready() or self._require_idle_or_stopped()
        if guard:
            return guard
        updates = {}
        if params.get("translation_project"):
            updates["translation_project"] = params["translation_project"]
        if params.get("input_folder"):
            updates["label_input_path"] = params["input_folder"]
        if "exclude_rule" in params:
            updates["label_input_exclude_rule"] = params["exclude_rule"]
        if updates:
            config = self.load_config()
            config.update(updates)
            self.save_config(config)
        self.info(f"收到 HTTP 指令: 加载项目 (Client: {ip})")
        if not self.load_project():
            return ({"status": "error", "message": "加载项目失败，请检查项目类型与输入路径"}, 500)
        return ({"status": "success", "message": "项目已加载",
                 "item_count": self.cache_manager.get_item_count(),
                 "project_id": getattr(self.cache_manager.project, "project_id", "")}, 200)

    # ----------------------------- 任务控制 -----------------------------
    def _h_task_start(self, params, ip):
        guard = self._deps_ready()
        if guard:
            return guard
        if Base.work_status not in (Base.STATUS.IDLE, Base.STATUS.TASKSTOPPED):
            return ({"status": "error", "code": "busy",
                     "message": "AiNiee 正在执行任务（运行或停止中）"}, 409)

        mode = (params.get("mode") or "translate").lower()
        if mode not in ("translate", "polish"):
            return ({"status": "error", "message": "mode 必须为 'translate' 或 'polish'"}, 400)
        continue_status = bool(params.get("continue", False))
        input_folder = params.get("input_folder")
        output_folder = params.get("output_folder")

        self.info(f"收到 HTTP 指令: 开始{mode} (Client: {ip}), continue={continue_status}")

        if input_folder or output_folder:
            config = self.load_config()
            if input_folder:
                config["label_input_path"] = input_folder
                self.info(f"使用自定义输入路径: {input_folder}")
            if output_folder:
                config["label_output_path"] = output_folder
                self.info(f"使用自定义输出路径: {output_folder}")
            self.save_config(config)

        if not continue_status and not self.check_project_loaded():
            self.info("项目未加载，正在加载项目文件...")
            if not self.load_project():
                return ({"status": "error", "message": "加载项目文件失败"}, 500)

        task_type = TaskType.TRANSLATION if mode == "translate" else TaskType.POLISH
        self.emit(Base.EVENT.TASK_START, {
            "continue_status": continue_status,
            "current_mode": task_type,
        })

        config = self.load_config()
        return ({"status": "success", "message": f"{mode} task started",
                 "mode": mode, "continue": continue_status,
                 "input_folder": config.get("label_input_path", ""),
                 "output_folder": config.get("label_output_path", "")}, 200)

    def _h_translate_post(self, params, ip):
        merged = dict(params)
        merged["mode"] = "translate"
        return self._h_task_start(merged, ip)

    def _h_translate_get(self, params, ip):
        return self._h_task_start({"mode": "translate"}, ip)

    def _h_stop(self, params, ip):
        self.info(f"收到 HTTP 指令: 停止任务 (Client: {ip})")
        self.emit(Base.EVENT.TASK_STOP, {})
        return ({"status": "success", "message": "Stop signal sent"}, 200)

    def _h_export(self, params, ip):
        export_path = params.get("export_path")
        if not export_path:
            return ({"status": "error", "message": "需要 export_path 参数"}, 400)
        guard = self._require_project()
        if guard:
            return guard
        self.emit(Base.EVENT.TASK_MANUAL_EXPORT, {"export_path": export_path})
        return ({"status": "success", "message": "导出已触发", "export_path": export_path}, 200)

    def _h_cache_save(self, params, ip):
        guard = self._require_project()
        if guard:
            return guard
        self.emit(Base.EVENT.TASK_MANUAL_SAVE_CACHE, {})
        return ({"status": "success", "message": "缓存保存已触发"}, 200)

    # ----------------------------- 扩展任务 -----------------------------
    def _h_analysis_start(self, params, ip):
        guard = self._require_project() or self._require_idle()
        if guard:
            return guard
        self._stash_reset("analysis")
        self.emit(Base.EVENT.ANALYSIS_TASK_START, {})
        return ({"status": "success", "message": "分析任务已开始，请轮询 /api/analysis/result"}, 202)

    def _h_analysis_data(self, params, ip):
        """读取当前已加载项目里已保存的分析结果(角色/术语/禁翻表)，无需重跑分析。"""
        guard = self._require_project()
        if guard:
            return guard
        data = self.cache_manager.get_analysis_data() or {}
        return ({"status": "success", "has_analysis": bool(data),
                 "analysis_data": data}, 200)

    def _h_glossary_translate(self, params, ip):
        guard = self._require_idle()
        if guard:
            return guard
        config = self.load_config()
        data = config.get("prompt_dictionary_data", []) or []
        if not data:
            return ({"status": "error", "message": "config.prompt_dictionary_data 为空，无可翻译术语"}, 400)
        self._stash_reset("glossary")
        self.emit(Base.EVENT.GLOSS_TASK_START, {"prompt_dictionary_data": data})
        return ({"status": "success", "message": "术语表翻译已开始，请轮询 /api/glossary/result",
                 "term_count": len(data)}, 202)

    def _h_apitest(self, params, ip):
        guard = self._require_idle()
        if guard:
            return guard
        tag = params.get("tag")
        config = self.load_config()
        platforms = config.get("platforms", {}) or {}
        if not tag or tag not in platforms:
            return ({"status": "error", "message": f"未知接口 tag: {tag}",
                     "available_tags": list(platforms.keys())}, 400)
        p = platforms[tag]
        payload = {
            "tag": tag, "name": p.get("name"), "api_url": p.get("api_url", ""),
            "api_key": p.get("api_key"), "api_format": p.get("api_format", ""),
            "model": p.get("model"), "auto_complete": p.get("auto_complete"),
            "extra_body": p.get("extra_body", {}), "region": p.get("region"),
            "access_key": p.get("access_key"), "secret_key": p.get("secret_key"),
            "tls_switch": p.get("tls_switch", False), "think_switch": p.get("think_switch"),
            "think_depth": p.get("think_depth"), "thinking_level": p.get("thinking_level"),
            "temperature": p.get("temperature"),
        }
        self._stash_reset("apitest")
        self.emit(Base.EVENT.API_TEST_START, payload)
        return ({"status": "success", "message": "接口测试已开始，请轮询 /api/apitest/result"}, 202)

    # ----------------------------- 通用译文检查/修正（内存缓存） -----------------------------
    def _h_cache_stats(self, params, ip):
        guard = self._require_project()
        if guard:
            return guard
        cm = self.cache_manager
        return ({"status": "success", "has_project": True,
                 "total": cm.get_item_count(),
                 "untranslated": cm.get_item_count_by_status(TranslationStatus.UNTRANSLATED),
                 "translated": cm.get_item_count_by_status(TranslationStatus.TRANSLATED),
                 "polished": cm.get_item_count_by_status(TranslationStatus.POLISHED),
                 "excluded": cm.get_item_count_by_status(TranslationStatus.EXCLUDED)}, 200)

    def _h_cache_search(self, params, ip):
        guard = self._require_project()
        if guard:
            return guard
        query = params.get("query", "") or ""
        scope = params.get("scope", "all") or "all"
        if scope not in ("all", "source_text", "translated_text"):
            return ({"status": "error", "message": "scope 必须为 all/source_text/translated_text"}, 400)
        is_regex = bool(params.get("regex", False))
        flagged = bool(params.get("flagged_only", False))
        limit = self._parse_int(params.get("limit", 200)) or 200

        try:
            results = self.cache_manager.search_items(query, scope, is_regex, flagged)
        except Exception as e:
            return ({"status": "error", "message": f"搜索失败: {e}"}, 400)

        items = []
        for storage_path, _row, item in results[:limit]:
            items.append({
                "storage_path": storage_path,
                "text_index": item.text_index,
                "source_text": item.source_text,
                "translated_text": item.translated_text,
                "status": item.translation_status,
            })
        return ({"status": "success", "count": len(items),
                 "total_matches": len(results), "items": items}, 200)

    def _h_cache_update(self, params, ip):
        guard = self._require_project() or self._require_idle_or_stopped()
        if guard:
            return guard
        edits = params.get("edits", []) or []
        if not isinstance(edits, list):
            return ({"status": "error", "message": "edits 必须为数组"}, 400)

        updated, failed = 0, []
        for edit in edits:
            sp = edit.get("storage_path")
            ti = edit.get("text_index")
            field = edit.get("field", "translated_text")
            new_text = edit.get("new_text", "")
            if field not in ("translated_text", "source_text"):
                failed.append({"text_index": ti, "reason": "field 必须为 translated_text/source_text"})
                continue
            cache_file = self.cache_manager.project.get_file(sp) if self.cache_manager.project else None
            if not cache_file:
                failed.append({"text_index": ti, "reason": f"找不到文件 {sp}"})
                continue
            try:
                self.cache_manager.update_item_text(sp, int(ti), field, new_text)
                updated += 1
            except Exception as e:
                failed.append({"text_index": ti, "reason": str(e)})

        if updated:
            self.cache_manager.save_to_file()
        return ({"status": "success", "updated": updated, "failed": failed}, 200)

    @staticmethod
    def _compile_source_guards(value):
        """source_requires / source_excludes accept a regex string or a list of them."""
        if not value:
            return []
        if isinstance(value, str):
            value = [value]
        return [re.compile(v) for v in value]

    def _compile_replace_rule(self, rule: dict):
        find = rule.get("find", "")
        if not find:
            return None
        is_regex = bool(rule.get("regex", False))
        pattern = find if is_regex else re.escape(find)
        skip = rule.get("skip_if_followed_by") or []
        if skip:
            neg = "|".join(re.escape(s) for s in skip)
            pattern = f"(?:{pattern})(?!{neg})"
        scope = rule.get("scope", "translated_text") or "translated_text"
        if scope not in ("all", "source_text", "translated_text"):
            raise ValueError("scope 必须为 all/source_text/translated_text")
        return {
            "regex": re.compile(pattern),
            "replace": rule.get("replace", ""),
            "is_regex_replace": is_regex,
            # which field(s) to rewrite: translated_text (default) / source_text / all.
            "scope": scope,
            # source_requires: at least one must match (OR). source_excludes: skip if any matches.
            "source_requires": self._compile_source_guards(rule.get("source_requires")),
            "source_excludes": self._compile_source_guards(rule.get("source_excludes")),
        }

    @staticmethod
    def _apply_replace(cr, text):
        """Apply one compiled rule to a single field's text."""
        if cr["is_regex_replace"]:
            return cr["regex"].sub(cr["replace"], text)
        replacement = cr["replace"]
        return cr["regex"].sub(lambda m, r=replacement: r, text)

    def _h_cache_replace(self, params, ip):
        guard = self._require_project() or self._require_idle_or_stopped()
        if guard:
            return guard
        rules = params.get("rules", []) or []
        dry_run = bool(params.get("dry_run", True))
        if not isinstance(rules, list) or not rules:
            return ({"status": "error", "message": "rules 必须为非空数组"}, 400)

        try:
            compiled = [c for c in (self._compile_replace_rule(r) for r in rules) if c]
        except re.error as e:
            return ({"status": "error", "message": f"正则表达式错误: {e}"}, 400)
        except ValueError as e:
            return ({"status": "error", "message": str(e)}, 400)
        if not compiled:
            return ({"status": "error", "message": "没有有效规则（每条规则需包含非空 find）"}, 400)

        PREVIEW_CAP = 200
        match_count = 0
        applied = 0
        preview = []

        for storage_path, cache_file in self.cache_manager.project.files.items():
            for item in cache_file.items:
                orig_src = item.source_text or ""
                orig_tr = item.translated_text or ""
                new_src, new_tr = orig_src, orig_tr
                for cr in compiled:
                    # source guards always test the original source, independent of rule order.
                    if cr["source_requires"] and not any(p.search(orig_src) for p in cr["source_requires"]):
                        continue
                    if cr["source_excludes"] and any(p.search(orig_src) for p in cr["source_excludes"]):
                        continue
                    if cr["scope"] in ("translated_text", "all"):
                        new_tr = self._apply_replace(cr, new_tr)
                    if cr["scope"] in ("source_text", "all"):
                        new_src = self._apply_replace(cr, new_src)
                # one change record per rewritten field
                for field, before, after in (("translated_text", orig_tr, new_tr),
                                             ("source_text", orig_src, new_src)):
                    if after != before:
                        match_count += 1
                        if len(preview) < PREVIEW_CAP:
                            preview.append({"storage_path": storage_path, "text_index": item.text_index,
                                            "field": field, "before": before, "after": after})
                        if not dry_run:
                            self.cache_manager.update_item_text(
                                storage_path, item.text_index, field, after)
                            applied += 1

        if not dry_run and applied:
            self.cache_manager.save_to_file()

        return ({"status": "success", "dry_run": dry_run,
                 "matched_items": match_count, "applied": applied,
                 "changed_preview": preview,
                 "preview_truncated": match_count > len(preview)}, 200)

    # ----------------------------- 服务生命周期 -----------------------------
    def start(self):
        """启动 HTTP 服务"""
        config = self.load_config()

        # 检查开关
        if not config.get("http_server_enable", False):
            return

        # 解析合并后的地址配置 "IP:PORT"
        address_config = config.get("http_listen_address", "127.0.0.1:3388")

        try:
            if ":" in address_config:
                host, port_str = address_config.split(":")
                port = int(port_str)
            else:
                # 如果用户只填了端口，默认监听 127.0.0.1
                host = "127.0.0.1"
                port = int(address_config)
        except ValueError:
            self.error(f"HTTP 监听地址格式错误: {address_config}。请使用 'IP:PORT' 格式 (如 127.0.0.1:3388)")
            return

        try:
            self.httpd = ThreadingHTTPServer((host, port), RequestHandler)
            # 将 self 注入到 server 中
            self.httpd.service_instance = self

            self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            self.server_thread.start()

            self.info(f"HTTP 服务已启动，监听地址: http://{host}:{port}")
            self.info("可用接口:")
            self.info("  - POST /api/task/start       开始翻译/润色 (mode, continue, input_folder, output_folder)")
            self.info("  - GET/POST /api/translate    开始翻译 (兼容旧接口)")
            self.info("  - GET  /api/stop             停止任务")
            self.info("  - GET  /api/status           查看状态与进度")
            self.info("  - POST /api/project/load     加载项目")
            self.info("  - POST /api/analysis/start   开始分析  | GET /api/analysis/result")
            self.info("  - GET  /api/analysis/data    读取已保存的分析结果(角色/术语/禁翻表)")
            self.info("  - POST /api/glossary/translate 术语表翻译 | GET /api/glossary/result")
            self.info("  - POST /api/apitest          接口测试 | GET /api/apitest/result")
            self.info("  - POST /api/export           导出结果")
            self.info("  - POST /api/cache/save       保存缓存")
            self.info("  - POST /api/cache/search     搜索译文  | GET /api/cache/stats")
            self.info("  - POST /api/cache/update     按条目修改译文")
            self.info("  - POST /api/cache/replace    通用查找替换 (dry_run 预览)")

        except OSError as e:
            self.error(f"HTTP 服务启动失败，端口可能被占用: {e}")
        except Exception as e:
            self.error(f"HTTP 服务启动发生未知错误: {e}")

    def on_task_completed(self, event: int, data: dict):
        """任务完成回调"""
        config = self.load_config()
        callback_url = config.get("http_callback_url", "")

        if not callback_url or not callback_url.startswith("http"):
            return

        self.info(f"任务完成,正在发送回调通知至: {callback_url}")

        def send_request():
            try:
                payload = {
                    "event": "task_completed",
                    "timestamp": int(time.time()),
                    "output_folder": config.get("label_output_path", ""),  # 输出文件夹信息
                    "input_folder": config.get("label_input_path", "")     # 输入文件夹信息
                }
                json_data = json.dumps(payload).encode('utf-8')

                req = urllib.request.Request(
                    callback_url,
                    data=json_data,
                    headers={'Content-Type': 'application/json', 'User-Agent': 'AiNiee-Client'}
                )

                with urllib.request.urlopen(req, timeout=10) as response:
                    if 200 <= response.status < 300:
                        self.info(f"回调通知发送成功 (Status: {response.status})")
                    else:
                        self.warning(f"回调通知发送异常 (Status: {response.status})")

            except urllib.error.URLError as e:
                self.error(f"回调请求连接失败: {e.reason}")
            except Exception as e:
                self.error(f"发送回调时发生错误: {e}")

        threading.Thread(target=send_request, daemon=True).start()

    def on_app_shutdown(self, event: int, data: dict):
        """关闭服务"""
        if self.httpd:
            self.info("正在关闭 HTTP 服务...")
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except:
                pass
