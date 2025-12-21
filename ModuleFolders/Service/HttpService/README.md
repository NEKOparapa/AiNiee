# AiNiee HTTP API 接口文档

## 概述

AiNiee 提供 HTTP API 接口，允许外部程序远程控制翻译任务。

**基础信息：**
- 协议：HTTP/1.1
- 默认地址：`http://127.0.0.1:3388`
- 数据格式：JSON
- 字符编码：UTF-8

---

## 配置说明

### 在 `Resource/config.json` 中添加以下配置：


```json
{
  "http_server_enable": true,
  "http_listen_address": "127.0.0.1:3388",
  "http_callback_url": "http://your-server.com/callback"
}
```

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `http_server_enable` | boolean | 是否启用 HTTP 服务 |
| `http_listen_address` | string | 监听地址，格式 `IP:端口` |
| `http_callback_url` | string | 任务完成回调地址（可选） |


### 或者手动在应用设置中启用和配置 HTTP 服务。

- 打开Http服务选项
- 设置监听地址和端口
- 可选：设置任务完成回调 URL


---


### 1. 开始翻译任务

**接口地址：** `POST /api/translate`

**功能说明：**
- 启动新的翻译任务
- 支持传入可选的输入/输出文件夹路径
- 如果不传参数，使用配置文件中的默认路径

**请求示例：**

```bash
# 方式1：使用默认路径（空请求体）
curl -X POST http://127.0.0.1:3388/api/translate \
  -H "Content-Type: application/json" \
  -d '{}'

# 方式2：自定义输入路径
curl -X POST http://127.0.0.1:3388/api/translate \
  -H "Content-Type: application/json" \
  -d '{
    "input_folder": "/path/to/input"
  }'

# 方式3：自定义输入和输出路径
curl -X POST http://127.0.0.1:3388/api/translate \
  -H "Content-Type: application/json" \
  -d '{
    "input_folder": "/path/to/input",
    "output_folder": "/path/to/output"
  }'
```

**请求参数：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| input_folder | string | 否 | 输入文件夹路径 |
| output_folder | string | 否 | 输出文件夹路径 |

**响应示例：**

成功（200）：
```json
{
  "status": "success",
  "message": "Translation task started",
  "input_folder": "/path/to/input",
  "output_folder": "/path/to/output"
}
```

### 2. 任务完成回调、

**回调请求体示例：**

```json
{
  "event": "task_completed",
  "timestamp": 1703001234,
  "output_folder": "/path/to/output",
  "input_folder": "/path/to/input"
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| event | string | 事件类型，固定为 `task_completed` |
| timestamp | integer | Unix 时间戳（秒） |
| output_folder | string | 输出文件夹路径 |
| input_folder | string | 输入文件夹路径 |

## Python 使用示例

```python
import requests
import time

BASE_URL = "http://127.0.0.1:3388"

# 示例1：使用自定义路径启动翻译
response = requests.post(
    f"{BASE_URL}/api/translate",
    json={
        "input_folder": "./my_input",
        "output_folder": "./my_output"
    }
)
result = response.json()
print(f"启动结果: {result}")
print(f"输入路径: {result.get('input_folder')}")
print(f"输出路径: {result.get('output_folder')}")

# 示例2：轮询状态直到完成
while True:
    time.sleep(5)
    status_response = requests.get(f"{BASE_URL}/api/status")
    status_data = status_response.json()
    print(f"任务状态: {status_data['app_status']}")
    
    if status_data['app_status'] in ['IDLE', 'STOPPED']:
        print("任务已完成")
        break
```
