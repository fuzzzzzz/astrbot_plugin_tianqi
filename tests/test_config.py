"""
配置管理测试
"""

import pytest
import tempfile
import os
import yaml
from hypothesis import given, strategies as st
from weather_plugin.config import WeatherConfig, ConfigManager, APIProviderConfig
from weather_plugin.models import ConfigurationError


class TestWeatherConfig:
    """天气配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = WeatherConfig(api_key="test_key")
        assert config.api_provider == "openweathermap"
        assert config.api_key == "test_key"
        assert config.cache_enabled is True
        assert config.default_units == "metric"
    
    def test_config_validation_success(self):
        """测试配置验证成功"""
        config = WeatherConfig(
            api_key="valid_key",
            api_provider="openweathermap",
            default_units="metric"
        )
        # 不应该抛出异常
        config.validate()
    
    def test_config_validation_empty_api_key(self):
        """测试空 API 密钥验证"""
        config = WeatherConfig(api_key="")
        with pytest.raises(ConfigurationError, match="API 密钥不能为空"):
            config.validate()
    
    def test_config_validation_invalid_provider(self):
        """测试无效 API 提供商"""
        config = WeatherConfig(api_key="test_key", api_provider="invalid")
        with pytest.raises(ConfigurationError, match="不支持的 API 提供商"):
            config.validate()
    
    def test_config_validation_invalid_units(self):
        """测试无效单位"""
        config = WeatherConfig(api_key="test_key", default_units="invalid")
        with pytest.raises(ConfigurationError, match="无效的默认单位"):
            config.validate()
    
    def test_config_validation_invalid_ttl(self):
        """测试无效 TTL"""
        config = WeatherConfig(api_key="test_key", cache_ttl_current=0)
        with pytest.raises(ConfigurationError, match="当前天气缓存 TTL 必须大于 0"):
            config.validate()


class TestConfigManager:
    """配置管理器测试"""
    
    def test_load_config_from_file(self, temp_config_file):
        """测试从文件加载配置"""
        manager = ConfigManager(temp_config_file)
        config = manager.load_config()
        
        assert config.api_key == "test_api_key"
        assert config.api_provider == "openweathermap"
        assert config.cache_enabled is True
    
    def test_load_config_nonexistent_file(self):
        """测试加载不存在的配置文件"""
        manager = ConfigManager("nonexistent.yaml")
        
        # 应该抛出配置错误，因为没有 API 密钥
        with pytest.raises(ConfigurationError, match="加载配置失败"):
            manager.load_config()
    
    def test_save_and_load_config(self):
        """测试保存和加载配置"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            manager = ConfigManager(temp_path)
            
            # 创建配置
            config = WeatherConfig(
                api_key="test_key",
                api_provider="weatherapi",
                default_units="imperial"
            )
            
            # 保存配置
            manager.save_config(config)
            
            # 重新加载
            loaded_config = manager.load_config()
            
            assert loaded_config.api_key == "test_key"
            assert loaded_config.api_provider == "weatherapi"
            assert loaded_config.default_units == "imperial"
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_reload_config(self, temp_config_file):
        """测试重新加载配置"""
        manager = ConfigManager(temp_config_file)
        
        # 首次加载
        config1 = manager.load_config()
        assert config1.api_key == "test_api_key"
        
        # 修改文件
        with open(temp_config_file, 'w') as f:
            yaml.dump({
                'api_key': 'new_test_key',
                'api_provider': 'weatherapi'
            }, f)
        
        # 重新加载
        config2 = manager.reload_config()
        assert config2.api_key == "new_test_key"
        assert config2.api_provider == "weatherapi"
    
    def test_get_config_caching(self, temp_config_file):
        """测试配置缓存"""
        manager = ConfigManager(temp_config_file)
        
        # 首次获取会加载
        config1 = manager.get_config()
        # 再次获取应该返回缓存的配置
        config2 = manager.get_config()
        
        assert config1 is config2  # 应该是同一个对象


class TestConfigManagerPropertyBased:
    """配置管理器基于属性的测试"""
    
    @given(
        api_key=st.text(min_size=1, max_size=100),
        api_provider=st.sampled_from(["openweathermap", "weatherapi"]),
        cache_enabled=st.booleans(),
        default_units=st.sampled_from(["metric", "imperial"]),
        cache_ttl_current=st.integers(min_value=1, max_value=86400),
        cache_ttl_forecast=st.integers(min_value=1, max_value=86400),
        cache_ttl_hourly=st.integers(min_value=1, max_value=86400),
    )
    def test_config_multi_provider_support_property(
        self, api_key, api_provider, cache_enabled, default_units, 
        cache_ttl_current, cache_ttl_forecast, cache_ttl_hourly
    ):
        """
        属性14：配置多提供商支持
        验证需求：8.3, 8.4
        
        对于任何有效的配置参数组合，配置系统应该：
        1. 正确支持多个API提供商
        2. 正确验证配置参数
        3. 提供商配置应该包含必要的信息
        """
        # 创建配置
        config = WeatherConfig(
            api_key=api_key,
            api_provider=api_provider,
            cache_enabled=cache_enabled,
            default_units=default_units,
            cache_ttl_current=cache_ttl_current,
            cache_ttl_forecast=cache_ttl_forecast,
            cache_ttl_hourly=cache_ttl_hourly,
        )
        
        # 验证配置应该成功
        config.validate()
        
        # 验证多提供商支持
        assert api_provider in config.supported_providers
        provider_config = config.get_provider_config()
        assert provider_config is not None
        assert isinstance(provider_config, APIProviderConfig)
        assert provider_config.name is not None
        assert provider_config.base_url is not None
        
        # 验证配置参数正确设置
        assert config.api_key == api_key
        assert config.api_provider == api_provider
        assert config.cache_enabled == cache_enabled
        assert config.default_units == default_units
        assert config.cache_ttl_current == cache_ttl_current
        assert config.cache_ttl_forecast == cache_ttl_forecast
        assert config.cache_ttl_hourly == cache_ttl_hourly
    
    @given(
        api_key=st.text(min_size=1, max_size=50),
        api_provider=st.sampled_from(["openweathermap", "weatherapi"]),
        cache_enabled=st.booleans(),
        default_units=st.sampled_from(["metric", "imperial"]),
        cache_ttl_current=st.integers(min_value=1, max_value=86400),
        cache_ttl_forecast=st.integers(min_value=1, max_value=86400),
        cache_ttl_hourly=st.integers(min_value=1, max_value=86400),
    )
    def test_config_save_load_roundtrip_property(
        self, api_key, api_provider, cache_enabled, default_units,
        cache_ttl_current, cache_ttl_forecast, cache_ttl_hourly
    ):
        """
        属性：配置保存加载往返一致性
        
        对于任何有效的配置数据，保存然后加载应该产生相同的配置
        """
        config_data = {
            'api_key': api_key,
            'api_provider': api_provider,
            'cache_enabled': cache_enabled,
            'default_units': default_units,
            'cache_ttl_current': cache_ttl_current,
            'cache_ttl_forecast': cache_ttl_forecast,
            'cache_ttl_hourly': cache_ttl_hourly,
        }
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            manager = ConfigManager(temp_path)
            
            # 创建配置对象
            original_config = WeatherConfig(**config_data)
            original_config.validate()
            
            # 保存配置
            manager.save_config(original_config)
            
            # 重新加载配置
            loaded_config = manager.load_config()
            
            # 验证关键字段一致
            assert loaded_config.api_key == original_config.api_key
            assert loaded_config.api_provider == original_config.api_provider
            assert loaded_config.cache_enabled == original_config.cache_enabled
            assert loaded_config.default_units == original_config.default_units
            assert loaded_config.cache_ttl_current == original_config.cache_ttl_current
            assert loaded_config.cache_ttl_forecast == original_config.cache_ttl_forecast
            assert loaded_config.cache_ttl_hourly == original_config.cache_ttl_hourly
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)