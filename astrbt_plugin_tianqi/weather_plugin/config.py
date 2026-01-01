"""
配置管理模块

处理插件配置的加载、验证和管理。
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from .models import ConfigurationError


@dataclass
class APIProviderConfig:
    """API 提供商配置"""
    name: str
    base_url: str
    api_key_required: bool = True
    supported_features: List[str] = field(default_factory=list)
    rate_limits: Dict[str, int] = field(default_factory=dict)


@dataclass
class WeatherConfig:
    """天气插件配置"""
    # API 配置
    api_provider: str = "openweathermap"
    api_key: str = ""
    api_base_url: str = ""
    
    # 缓存配置
    cache_enabled: bool = True
    cache_db_path: str = "weather_cache.db"
    cache_ttl_current: int = 600  # 10分钟
    cache_ttl_forecast: int = 3600  # 1小时
    cache_ttl_hourly: int = 1800  # 30分钟
    
    # 用户偏好配置
    default_units: str = "metric"
    default_language: str = "zh"
    
    # API 限制配置
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 1000
    
    # 插件配置
    plugin_name: str = "智能天气助手"
    plugin_version: str = "1.0.0"
    
    # 支持的 API 提供商配置
    supported_providers: Dict[str, APIProviderConfig] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.supported_providers:
            self._init_default_providers()
    
    def _init_default_providers(self):
        """初始化默认 API 提供商"""
        self.supported_providers = {
            "openweathermap": APIProviderConfig(
                name="OpenWeatherMap",
                base_url="https://api.openweathermap.org/data/2.5",
                api_key_required=True,
                supported_features=["current", "forecast", "hourly", "alerts"],
                rate_limits={"per_minute": 60, "per_day": 1000}
            ),
            "weatherapi": APIProviderConfig(
                name="WeatherAPI",
                base_url="https://api.weatherapi.com/v1",
                api_key_required=True,
                supported_features=["current", "forecast", "hourly", "alerts", "history"],
                rate_limits={"per_minute": 100, "per_day": 1000000}
            )
        }
    
    def validate(self) -> None:
        """验证配置有效性"""
        if not self.api_key:
            raise ConfigurationError("API 密钥不能为空")
        
        if self.api_provider not in self.supported_providers:
            supported = ", ".join(self.supported_providers.keys())
            raise ConfigurationError(f"不支持的 API 提供商: {self.api_provider}。支持的提供商: {supported}")
        
        # 验证 API 密钥要求
        provider_config = self.supported_providers[self.api_provider]
        if provider_config.api_key_required and not self.api_key:
            raise ConfigurationError(f"API 提供商 {self.api_provider} 需要 API 密钥")
        
        if self.default_units not in ["metric", "imperial"]:
            raise ConfigurationError(f"无效的默认单位: {self.default_units}")
        
        if self.cache_ttl_current <= 0:
            raise ConfigurationError("当前天气缓存 TTL 必须大于 0")
        
        if self.cache_ttl_forecast <= 0:
            raise ConfigurationError("预报缓存 TTL 必须大于 0")
        
        if self.cache_ttl_hourly <= 0:
            raise ConfigurationError("小时预报缓存 TTL 必须大于 0")
    
    def get_provider_config(self) -> APIProviderConfig:
        """获取当前 API 提供商配置"""
        return self.supported_providers.get(self.api_provider)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: Optional[str] = None, metadata_path: Optional[str] = None):
        self.config_path = config_path or "config.yaml"
        self.metadata_path = metadata_path or "metadata.yaml"
        self._config: Optional[WeatherConfig] = None
        self._metadata: Optional[Dict[str, Any]] = None
    
    def load_config(self) -> WeatherConfig:
        """加载配置"""
        try:
            # 首先加载元数据
            metadata = self._load_metadata()
            
            # 从配置文件加载
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            else:
                config_data = {}
            
            # 从元数据合并默认配置
            self._merge_metadata_config(config_data, metadata)
            
            # 从环境变量覆盖配置
            self._load_from_env(config_data)
            
            # 创建配置对象
            self._config = WeatherConfig(**config_data)
            self._config.validate()
            
            return self._config
            
        except Exception as e:
            raise ConfigurationError(f"加载配置失败: {e}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """加载元数据文件"""
        if self._metadata is not None:
            return self._metadata
            
        try:
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    self._metadata = yaml.safe_load(f) or {}
            else:
                self._metadata = {}
            return self._metadata
        except Exception as e:
            raise ConfigurationError(f"加载元数据失败: {e}")
    
    def _merge_metadata_config(self, config_data: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """从元数据合并配置"""
        # 从元数据获取插件信息
        if 'name' in metadata:
            config_data.setdefault('plugin_name', metadata['name'])
        if 'version' in metadata:
            config_data.setdefault('plugin_version', metadata['version'])
        
        # 从元数据的配置模板合并默认值
        config_template = metadata.get('config_template', {})
        for key, value in config_template.items():
            config_data.setdefault(key, value)
    
    def _load_from_env(self, config_data: Dict[str, Any]) -> None:
        """从环境变量加载配置"""
        env_mappings = {
            'WEATHER_API_KEY': 'api_key',
            'WEATHER_API_PROVIDER': 'api_provider',
            'WEATHER_API_BASE_URL': 'api_base_url',
            'WEATHER_CACHE_ENABLED': 'cache_enabled',
            'WEATHER_CACHE_DB_PATH': 'cache_db_path',
            'WEATHER_DEFAULT_UNITS': 'default_units',
            'WEATHER_DEFAULT_LANGUAGE': 'default_language',
            'WEATHER_RATE_LIMIT_PER_MINUTE': 'rate_limit_per_minute',
            'WEATHER_RATE_LIMIT_PER_DAY': 'rate_limit_per_day',
        }
        
        for env_key, config_key in env_mappings.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                # 处理布尔值
                if config_key == 'cache_enabled':
                    config_data[config_key] = env_value.lower() in ('true', '1', 'yes')
                # 处理整数值
                elif config_key in ['rate_limit_per_minute', 'rate_limit_per_day']:
                    try:
                        config_data[config_key] = int(env_value)
                    except ValueError:
                        raise ConfigurationError(f"环境变量 {env_key} 必须是整数")
                else:
                    config_data[config_key] = env_value
    
    def get_config(self) -> WeatherConfig:
        """获取当前配置"""
        if self._config is None:
            return self.load_config()
        return self._config
    
    def reload_config(self) -> WeatherConfig:
        """重新加载配置"""
        self._config = None
        self._metadata = None
        return self.load_config()
    
    def save_config(self, config: WeatherConfig) -> None:
        """保存配置到文件"""
        try:
            config_dict = {
                'api_provider': config.api_provider,
                'api_key': config.api_key,
                'api_base_url': config.api_base_url,
                'cache_enabled': config.cache_enabled,
                'cache_db_path': config.cache_db_path,
                'cache_ttl_current': config.cache_ttl_current,
                'cache_ttl_forecast': config.cache_ttl_forecast,
                'cache_ttl_hourly': config.cache_ttl_hourly,
                'default_units': config.default_units,
                'default_language': config.default_language,
                'rate_limit_per_minute': config.rate_limit_per_minute,
                'rate_limit_per_day': config.rate_limit_per_day,
            }
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
                
            self._config = config
            
        except Exception as e:
            raise ConfigurationError(f"保存配置失败: {e}")
    
    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据"""
        return self._load_metadata()
    
    def validate_api_key(self, api_key: str, provider: str) -> bool:
        """验证 API 密钥格式"""
        if not api_key:
            return False
        
        # 基本格式验证
        if provider == "openweathermap":
            # OpenWeatherMap API 密钥通常是32位十六进制字符串
            return len(api_key) == 32 and all(c in '0123456789abcdefABCDEF' for c in api_key)
        elif provider == "weatherapi":
            # WeatherAPI 密钥格式较为灵活，基本长度检查
            return len(api_key) >= 16
        
        return True  # 对于未知提供商，只检查非空
    
    def get_supported_providers(self) -> List[str]:
        """获取支持的 API 提供商列表"""
        config = self.get_config()
        return list(config.supported_providers.keys())


# 全局配置管理器实例
config_manager = ConfigManager()