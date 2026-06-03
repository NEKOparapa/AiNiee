import threading
import json
import hmac
import urllib.request
import urllib.error
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from ModuleFolders.Base.Base import Base
from ModuleFolders.Config.Config import ConfigMixin
from ModuleFolders.Config.FilePathConfig import default_input_dir
from ModuleFolders.Log.Log import LogMixin
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType

def _is_loopback(addr: str) -> bool:
    a = (addr or "").strip().lower()
    if a.startswith("::ffff:"):
        a = a[7:]
    return a in ("127.0.0.1", "::1", "localhost") or a.startswith("127.")


def _host_only(host_header: str) -> str:
    h = (host_header or "").strip().lower()
    if not h:
        return ""
    if h[0] == "[":
        end = h.find("]")
        return h[1:end] if end > 0 else h.strip("[]")
    if h.count(":") == 1:
        return h.rsplit(":", 1)[0]
    return h


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """支持多线程处理的 HTTP Server"""
    daemon_threads = True

class RequestHandler(BaseHTTPRequestHandler):
    """处理 HTTP 请求"""
    
    def log_message(self, format, *args):
        # 屏蔽默认的控制台日志，避免刷屏
        pass

    def _authorized(self) -> bool:
        config = self.server.service_instance.load_config()
        token = str(config.get("http_auth_token", "")).strip()
        if token:
            provided = self.headers.get("X-Auth-Token", "").strip()
            if not provided:
                auth = self.headers.get("Authorization", "")
                if auth[:7].lower() == "bearer ":
                    provided = auth[7:].strip()
            return hmac.compare_digest(provided.encode("utf-8"), token.encode("utf-8"))
        if not _is_loopback(self.client_address[0]):
            return False
        return _host_only(self.headers.get("Host", "")) in ("127.0.0.1", "localhost", "::1")

    def _reject_unauthorized(self):
        service = getattr(self.server, "service_instance", None)
        if service is not None:
            service.warning(f"HTTP 鉴权失败，已拒绝 (Client: {self.client_address[0]})")
        self.send_response(401)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": "Unauthorized"}).encode('utf-8'))

    def do_POST(self):
        """处理 POST 请求（支持传参）"""
        service = self.server.service_instance

        if not self._authorized():
            self._reject_unauthorized()
            return

        response_data = {"status": "error", "message": "Unknown command"}
        status_code = 404
        path = self.path.lower()

        # 1. 开始翻译（支持可选参数）
        if path == '/api/translate':
            if Base.work_status == Base.STATUS.IDLE or Base.work_status == Base.STATUS.TASKSTOPPED:
                try:
                    # 读取请求体
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length)
                    params = {}
                    
                    if content_length > 0:
                        params = json.loads(post_data.decode('utf-8'))
                    
                    service.info(f"收到 HTTP 指令: 开始翻译 (Client: {self.client_address[0]})")
                    if params:
                        service.info(f"请求参数: {params}")
                    
                    # 提取可选参数
                    input_folder = params.get("input_folder")
                    output_folder = params.get("output_folder")
                    
                    # 如果提供了自定义路径，先更新配置
                    if input_folder or output_folder:
                        config = service.load_config()
                        if input_folder:
                            config["label_input_path"] = input_folder
                            service.info(f"使用自定义输入路径: {input_folder}")
                        if output_folder:
                            config["label_output_path"] = output_folder
                            service.info(f"使用自定义输出路径: {output_folder}")
                        service.save_config(config)
                    
                    # 检查项目是否已加载
                    if not service.check_project_loaded():
                        service.info("项目未加载，正在加载项目文件...")
                        if not service.load_project():
                            response_data = {"status": "error", "message": "Failed to load project files"}
                            status_code = 500
                            self.send_response(status_code)
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps(response_data).encode('utf-8'))
                            return
                    
                    # 触发翻译任务
                    service.emit(Base.EVENT.TASK_START, {
                        "continue_status": False,
                        "current_mode": TaskType.TRANSLATION
                    })
                    
                    # 返回当前使用的路径配置
                    current_config = service.load_config()
                    response_data = {
                        "status": "success", 
                        "message": "Translation task started",
                        "input_folder": current_config.get("label_input_path", ""),
                        "output_folder": current_config.get("label_output_path", "")
                    }
                    status_code = 200
                    
                except json.JSONDecodeError as e:
                    response_data = {"status": "error", "message": f"Invalid JSON: {str(e)}"}
                    status_code = 400
                except Exception as e:
                    service.error(f"处理请求时发生错误: {e}")
                    response_data = {"status": "error", "message": str(e)}
                    status_code = 500
            else:
                response_data = {"status": "error", "message": "App is busy (Task running or stopping)"}
                status_code = 409

        # 发送响应
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def do_GET(self):
        """处理 GET 请求（保持向后兼容）"""
        service = self.server.service_instance

        if not self._authorized():
            self._reject_unauthorized()
            return

        response_data = {"status": "error", "message": "Unknown command"}
        status_code = 404
        path = self.path.lower()

        # 1. 开始翻译（使用配置文件中的路径）
        if path == '/api/translate':
            if Base.work_status == Base.STATUS.IDLE or Base.work_status == Base.STATUS.TASKSTOPPED:
                service.info(f"收到 HTTP 指令: 开始翻译 (Client: {self.client_address[0]})")
                
                # 检查项目是否已加载
                if not service.check_project_loaded():
                    service.info("项目未加载，正在加载项目文件...")
                    if not service.load_project():
                        response_data = {"status": "error", "message": "Failed to load project files"}
                        status_code = 500
                        self.send_response(status_code)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(response_data).encode('utf-8'))
                        return
                
                service.emit(Base.EVENT.TASK_START, {
                    "continue_status": False,
                    "current_mode": TaskType.TRANSLATION
                })
                response_data = {"status": "success", "message": "Translation task started"}
                status_code = 200
            else:
                response_data = {"status": "error", "message": "App is busy (Task running or stopping)"}
                status_code = 409

        # 2. 停止任务
        elif path == '/api/stop':
            service.info(f"收到 HTTP 指令: 停止任务 (Client: {self.client_address[0]})")
            service.emit(Base.EVENT.TASK_STOP, {})
            response_data = {"status": "success", "message": "Stop signal sent"}
            status_code = 200
            
        # 3. 获取状态
        elif path == '/api/status':
            response_data = service.build_status_response()
            status_code = 200

        # 发送响应
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))


class HttpService(ConfigMixin, LogMixin, Base):
    def __init__(self):
        super().__init__()
        self.httpd = None
        self.server_thread = None
        
        # 依赖对象
        self.cache_manager = None
        self.file_reader = None
        
        # 订阅任务完成事件
        self.subscribe(Base.EVENT.TASK_COMPLETED, self.on_task_completed)
        self.subscribe(Base.EVENT.APP_SHUT_DOWN, self.on_app_shutdown)

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

    def load_project(self) -> bool:
        """直接加载新项目（不检查缓存）"""
        try:
            config = self.load_config()
            translation_project = config.get("translation_project", "AutoType")
            label_input_path = config.get("label_input_path", str(default_input_dir()))
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

    def start(self):
        """启动 HTTP 服务"""
        config = self.load_config()
        
        # 检查开关
        if not config.get("http_server_enable", False):
            return

        # 解析合并后的地址配置 "IP:PORT"
        address_config = config.get("http_listen_address", "127.0.0.1:3388")
        
        try:
            addr = address_config.strip()
            if addr.startswith("["):
                host, _, rest = addr[1:].partition("]")
                port = int(rest.lstrip(":"))
            elif addr.count(":") == 1:
                host, port_str = addr.split(":")
                port = int(port_str)
            else:
                # 如果用户只填了端口，默认监听 127.0.0.1
                host = "127.0.0.1"
                port = int(addr)
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
            self.info("  - GET  /api/translate  开始翻译 (使用配置文件路径)")
            self.info("  - POST /api/translate  开始翻译 (可传入自定义路径)")
            self.info("  - GET  /api/stop       停止任务")
            self.info("  - GET  /api/status     查看状态")
            
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
