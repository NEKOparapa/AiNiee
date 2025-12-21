import threading
import json
import urllib.request
import urllib.error
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

from ModuleFolders.Base.Base import Base
from ModuleFolders.Infrastructure.TaskConfig.TaskType import TaskType

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """支持多线程处理的 HTTP Server"""
    daemon_threads = True

class RequestHandler(BaseHTTPRequestHandler):
    """处理 HTTP 请求"""
    
    def log_message(self, format, *args):
        # 屏蔽默认的控制台日志，避免刷屏
        pass

    def do_POST(self):
        """处理 POST 请求（支持传参）"""
        service = self.server.service_instance
        
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
            status_str = "IDLE"
            if Base.work_status == Base.STATUS.TASKING:
                status_str = "TASKING"
            elif Base.work_status == Base.STATUS.STOPING:
                status_str = "STOPPING"
            elif Base.work_status == Base.STATUS.TASKSTOPPED:
                status_str = "STOPPED"
        
            response_data = {
                "status": "success", 
                "app_status": status_str,
                "work_status_code": Base.work_status,
            }
            status_code = 200

        # 发送响应
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))


class HttpService(Base):
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