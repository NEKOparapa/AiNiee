# LLMClientFactory.py
import threading
from typing import Dict, Any
import httpx
from openai import OpenAI
import anthropic
import boto3
import cohere
from google import genai


def create_httpx_client(
        http2=True,
        max_connections=128,
        max_keepalive_connections=64,
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
        api_key = config.get("api_key")
        key = ("openai", config.get("api_url"), api_key)
        return self._get_cached_client(key, lambda: self._create_openai_client(config, api_key))

    def get_openai_client_local(self, config: Dict[str, Any]) -> OpenAI:
        """获取OpenAI客户端"""
        api_key = config.get("api_key")
        if not api_key:
            api_key = "none_api_key"
        key = ("openai_local", config.get("api_url"), api_key)
        return self._get_cached_client(key, lambda: self._create_openai_client(config, api_key))

    def get_openai_client_sakura(self, config: Dict[str, Any]) -> OpenAI:
        """获取OpenAI客户端"""
        api_key = config.get("api_key")
        if not api_key:
            api_key = "none_api_key"
        key = ("openai_sakura", config.get("api_url"), api_key)
        return self._get_cached_client(key, lambda: self._create_openai_client(config, api_key))

    def get_anthropic_client(self, config: Dict[str, Any]) -> anthropic.Anthropic:
        """获取Anthropic客户端"""
        key = ("anthropic", config.get("api_url"), config.get("api_key"))
        return self._get_cached_client(key, lambda: self._create_anthropic_client(config))

    def get_anthropic_bedrock(self, config: Dict[str, Any]) -> anthropic.AnthropicBedrock:
        """获取AnthropicBedrock客户端"""
        key = ("anthropic_bedrock", config.get("region"), config.get("access_key"), config.get("secret_key"))
        return self._get_cached_client(key, lambda: self._create_anthropic_bedrock(config))

    def get_boto3_bedrock(self, config: Dict[str, Any]) -> Any:
        """获取boto3 bedrock客户端"""
        key = ("boto3_bedrock", config.get("region"), config.get("access_key"), config.get("secret_key"))
        return self._get_cached_client(key, lambda: self._create_boto3_bedrock(config))

    def get_cohere_client(self, config: Dict[str, Any]) -> cohere.ClientV2:
        """获取Cohere客户端"""
        key = ("cohere", config.get("api_url"), config.get("api_key"))
        return self._get_cached_client(key, lambda: self._create_cohere_client(config))

    def get_google_client(self, config: Dict[str, Any]) -> genai.Client:
        """获取Google AI客户端"""
        key = ("google", config.get("api_key"))
        return self._get_cached_client(key, lambda: self._create_google_client(config))

    def _get_cached_client(self, key, factory_func):
        """线程安全地获取或创建客户端"""
        if key not in self._clients:
            with self._lock:
                if key not in self._clients:
                    self._clients[key] = factory_func()
        return self._clients[key]

    # 各种客户端创建函数
    def _create_openai_client(self, config, api_key):
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
        return genai.Client(api_key=config.get("api_key"))
