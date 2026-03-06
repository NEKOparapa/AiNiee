# LLMClientFactory.py
import threading
from typing import Dict, Any
import urllib.request
import httpx
from openai import OpenAI
import anthropic
import boto3
import cohere
from google import genai
import json
from curl_cffi import requests as curl_requests


class CurlHTTPXTransport(httpx.BaseTransport):
    """
    使用curl_cffi的HTTPX Transport，用于绕过JA3/TLS指纹检测
    """
    def __init__(self, impersonate="chrome136", timeout=300, **kwargs):
        self.impersonate = impersonate
        self.default_timeout = timeout

        # 检测系统代理
        if "proxies" not in kwargs:
            kwargs["proxies"] = urllib.request.getproxies()

        self.session = curl_requests.Session(impersonate=impersonate, **kwargs)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # 处理超时
        timeout = self.default_timeout
        if 'timeout' in request.extensions:
            t = request.extensions['timeout']
            if isinstance(t, dict):
                read_t = t.get('read')
                if read_t is not None:
                    timeout = read_t
            elif isinstance(t, (int, float)):
                timeout = t

        content = request.read()
        try:
            # 过滤掉可能与impersonate冲突的header
            headers = dict(request.headers)
            headers_to_remove = [
                "user-agent",
                "accept-encoding",
                "connection",
                "keep-alive",
                "accept",
                "cookie",
                "content-length"
            ]
            for key in headers_to_remove:
                if key in headers:
                    del headers[key]
                # 处理大写开头header
                capitalized_key = key.title()
                if capitalized_key in headers:
                    del headers[capitalized_key]

            response = self.session.request(
                method=request.method,
                url=str(request.url),
                headers=headers,
                data=content,
                timeout=timeout,
                allow_redirects=True
            )

            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=response.content,
                extensions={"http_version": b"HTTP/2"}
            )
        except Exception as e:
            raise httpx.RequestError(f"CurlCffi Error: {str(e)}", request=request) from e

    def close(self):
        self.session.close()


def create_curl_client(impersonate="chrome136", timeout=300):
    return httpx.Client(
        transport=CurlHTTPXTransport(impersonate=impersonate, timeout=timeout),
        timeout=timeout
    )


def create_httpx_client(
        http2=True,
        max_connections=256,
        max_keepalive_connections=128,
        keepalive_expiry=30,
        **kwargs
):
    """
    创建配置好的HTTP客户端

    参数:
        http2: 是否启用HTTP/2
        max_connections: 最大并发连接数
        max_keepalive_connections: 最大保持活跃的连接数
        keepalive_expiry: 连接保持活跃的秒数
        **kwargs: 传递给httpx.Client的其他参数

    返回:
        配置好的httpx.Client实例
    """
    return httpx.Client(
        http2=http2,
        limits=httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry
        ),
        **kwargs
    )


class LLMClientFactory:
    """LLM客户端工厂 - 集中管理和缓存不同类型的LLM客户端"""

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LLMClientFactory, cls).__new__(cls)
                cls._instance._clients = {}
            return cls._instance

    def get_openai_client(self, config: Dict[str, Any]) -> OpenAI:
        """获取OpenAI客户端"""
        # 展示需要到的配置项
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        tls_switch = config.get("tls_switch", False)
        key = ("openai", api_url, api_key, tls_switch)
        return self._get_cached_client(key, lambda: self._create_openai_client(config, api_key, use_curl_cffi=tls_switch))

    def get_openai_client_local(self, config: Dict[str, Any]) -> OpenAI:
        """获取OpenAI客户端"""
        api_key = config.get("api_key")
        if not api_key:
            api_key = "none_api_key"
        api_url = config.get("api_url")
        key = ("openai_local", api_url, api_key)
        return self._get_cached_client(key, lambda: self._create_openai_client(config, api_key, use_curl_cffi=False))

    def get_openai_client_sakura(self, config: Dict[str, Any]) -> OpenAI:
        """获取OpenAI客户端"""
        api_key = config.get("api_key")
        if not api_key:
            api_key = "none_api_key"
        api_url = config.get("api_url")
        key = ("openai_sakura", api_url, api_key)
        return self._get_cached_client(key, lambda: self._create_openai_client(config, api_key, use_curl_cffi=False))

    def get_anthropic_client(self, config: Dict[str, Any]) -> anthropic.Anthropic:
        """获取Anthropic客户端"""
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        key = ("anthropic", api_url, api_key)
        return self._get_cached_client(key, lambda: self._create_anthropic_client(config))

    def get_anthropic_bedrock(self, config: Dict[str, Any]) -> anthropic.AnthropicBedrock:
        """获取AnthropicBedrock客户端"""
        region = config.get("region")
        access_key = config.get("access_key")
        secret_key = config.get("secret_key")
        key = ("anthropic_bedrock", region, access_key, secret_key)
        return self._get_cached_client(key, lambda: self._create_anthropic_bedrock(config))

    def get_boto3_bedrock(self, config: Dict[str, Any]) -> Any:
        """获取boto3 bedrock客户端"""
        region = config.get("region")
        access_key = config.get("access_key")
        secret_key = config.get("secret_key")
        key = ("boto3_bedrock", region, access_key, secret_key)
        return self._get_cached_client(key, lambda: self._create_boto3_bedrock(config))

    def get_cohere_client(self, config: Dict[str, Any]) -> cohere.ClientV2:
        """获取Cohere客户端"""
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        key = ("cohere", api_url, api_key)
        return self._get_cached_client(key, lambda: self._create_cohere_client(config))

    def get_google_client(self, config: Dict[str, Any]) -> genai.Client:
        """获取Google AI客户端"""
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        extra_body = config.get("extra_body", {})
        extra_body_serialized = json.dumps(extra_body, sort_keys=True) if extra_body else None
        key = ("google", api_key, api_url, extra_body_serialized)
        return self._get_cached_client(key, lambda: self._create_google_client(config))

    def _get_cached_client(self, key, factory_func):
        """线程安全地获取或创建客户端"""
        if key not in self._clients:
            with self._lock:
                if key not in self._clients:
                    self._clients[key] = factory_func()
        return self._clients[key]

    # 各种客户端创建函数
    def _create_openai_client(self, config, api_key, use_curl_cffi=False):
        if use_curl_cffi:
            # 使用curl_cffi模拟指纹
            # 获取请求超时时间，默认300秒
            timeout = config.get("request_timeout", 300)
            return OpenAI(
                base_url=config.get("api_url"),
                api_key=api_key,
                http_client=create_curl_client(timeout=timeout)
            )
        else:
            return OpenAI(
                base_url=config.get("api_url"),
                api_key=api_key,
                http_client=create_httpx_client()
            )

    def _create_anthropic_client(self, config):
        return anthropic.Anthropic(
            base_url=config.get("api_url"),
            api_key=config.get("api_key"),
            http_client=create_httpx_client()
        )

    def _create_anthropic_bedrock(self, config):
        return anthropic.AnthropicBedrock(
            aws_region=config.get("region"),
            aws_access_key=config.get("access_key"),
            aws_secret_key=config.get("secret_key"),
            http_client=create_httpx_client()
        )

    def _create_boto3_bedrock(self, config):
        return boto3.client(
            "bedrock-runtime",
            region_name=config.get("region"),
            aws_access_key_id=config.get("access_key"),
            aws_secret_access_key=config.get("secret_key")
        )

    def _create_cohere_client(self, config):
        return cohere.ClientV2(
            base_url=config.get("api_url"),
            api_key=config.get("api_key"),
            timeout=config.get("request_timeout", 60),
            httpx_client=create_httpx_client()
        )

    def _create_google_client(self, config):
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        extra_body = config.get("extra_body")

        http_options = {}
        if api_url:
            http_options["base_url"] = api_url
        if extra_body:
            http_options["extra_body"] = extra_body

        if http_options:
            return genai.Client(api_key=api_key, http_options=http_options)
        else:
            return genai.Client(api_key=api_key)
