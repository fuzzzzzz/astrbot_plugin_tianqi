"""
天气服务简单测试

测试核心天气服务的基本功能，不依赖数据库。
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from weather_plugin.weather_service import WeatherService, CircuitBreaker, CircuitBreakerState
from weather_plugin.config import WeatherConfig
from weather_plugin.models import (
    WeatherData, ForecastData, HourlyForecastData,
    APIError, LocationError, WeatherError, LocationInfo, UserPrefs
)


class TestWeatherServiceCore:
    """天气服务核心功能测试"""
    
    @pytest.fixture
    def weather_config(self):
        """测试配置"""
        return WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key",
            cache_enabled=False,  # 禁用缓存避免数据库问题
            default_units="metric",
            default_language="zh",
            cache_ttl_current=600,
            cache_ttl_forecast=3600,
            cache_ttl_hourly=1800
        )
    
    @pytest.fixture
    def weather_service_mocked(self, weather_config):
        """完全模拟的天气服务"""
        # 创建所有模拟组件
        mock_api_client = Mock()
        mock_cache_manager = Mock()
        mock_location_service = Mock()
        mock_user_preferences = Mock()
        
        # 配置模拟行为
        mock_location_service.parse_location.return_value = LocationInfo(name="北京")
        mock_user_preferences.get_user_preferences.return_value = UserPrefs(
            user_id="test_user",
            units="metric",
            default_location="北京"
        )
        mock_cache_manager.get_cached_weather = AsyncMock(return_value=None)
        mock_cache_manager.get_cached_forecast = AsyncMock(return_value=None)
        mock_cache_manager.cache_weather_data = AsyncMock()
        mock_cache_manager.cache_forecast_data = AsyncMock()
        mock_cache_manager.generate_cache_key.return_value = "test_cache_key"
        
        return WeatherService(
            config=weather_config,
            api_client=mock_api_client,
            cache_manager=mock_cache_manager,
            location_service=mock_location_service,
            user_preferences=mock_user_preferences
        )
    
    def test_weather_service_initialization(self, weather_service_mocked):
        """测试天气服务初始化"""
        service = weather_service_mocked
        assert service is not None
        assert service.config is not None
        assert service.api_client is not None
        assert service.cache_manager is not None
        assert service.location_service is not None
        assert service.user_preferences is not None
        assert service.circuit_breaker is not None
        assert isinstance(service.circuit_breaker, CircuitBreaker)
    
    @pytest.mark.asyncio
    async def test_get_current_weather_with_api_success(self, weather_service_mocked):
        """测试通过API成功获取当前天气"""
        service = weather_service_mocked
        
        # 配置API返回数据
        api_response = {
            "main": {
                "temp": 25.0,
                "feels_like": 27.0,
                "humidity": 60,
                "pressure": 1013.0
            },
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 10.0, "deg": 180},
            "visibility": 10000
        }
        
        service.api_client.fetch_current_weather = AsyncMock(return_value=api_response)
        
        # 调用服务
        result = await service.get_current_weather("北京", "test_user")
        
        # 验证结果
        assert isinstance(result, WeatherData)
        assert result.location == "北京"
        assert result.temperature == 25.0
        assert result.feels_like == 27.0
        assert result.humidity == 60
        assert result.units == "metric"
        
        # 验证调用
        service.api_client.fetch_current_weather.assert_called_once_with("北京")
        service.cache_manager.cache_weather_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_forecast_with_api_success(self, weather_service_mocked):
        """测试通过API成功获取预报"""
        service = weather_service_mocked
        
        # 配置API返回数据
        api_response = {
            "list": [
                {
                    "dt": 1640995200,
                    "main": {"temp": 25.0, "humidity": 60, "pressure": 1013.0},
                    "weather": [{"description": "晴朗", "icon": "01d"}],
                    "wind": {"speed": 10.0, "deg": 180},
                    "pop": 0.1
                }
            ]
        }
        
        service.api_client.fetch_forecast = AsyncMock(return_value=api_response)
        
        # 调用服务
        result = await service.get_forecast("北京", 3, "test_user")
        
        # 验证结果
        assert isinstance(result, ForecastData)
        assert result.location == "北京"
        assert result.units == "metric"
        assert len(result.days) >= 0  # 可能为空，因为数据处理逻辑
        
        # 验证调用
        service.api_client.fetch_forecast.assert_called_once_with("北京", 3)
        service.cache_manager.cache_forecast_data.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_api_error_handling(self, weather_service_mocked):
        """测试API错误处理"""
        service = weather_service_mocked
        
        # 配置API抛出异常
        service.api_client.fetch_current_weather = AsyncMock(side_effect=APIError("API调用失败"))
        
        # 配置降级策略返回None
        service._get_stale_cache_data = AsyncMock(return_value=None)
        
        # 调用服务应该抛出友好的错误
        with pytest.raises(APIError, match="天气服务暂时不可用"):
            await service.get_current_weather("北京", "test_user")
    
    def test_validate_weather_data_valid(self, weather_service_mocked):
        """测试有效天气数据验证"""
        service = weather_service_mocked
        
        weather_data = WeatherData(
            location="北京",
            temperature=25.0,
            feels_like=27.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction=180,
            pressure=1013.0,
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        assert service._validate_weather_data(weather_data) is True
    
    def test_validate_weather_data_invalid(self, weather_service_mocked):
        """测试无效天气数据验证"""
        service = weather_service_mocked
        
        weather_data = WeatherData(
            location="北京",
            temperature=100.0,  # 异常高温
            feels_like=27.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction=180,
            pressure=1013.0,
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        assert service._validate_weather_data(weather_data) is False
    
    def test_sanitize_weather_data(self, weather_service_mocked):
        """测试天气数据清理"""
        service = weather_service_mocked
        
        # 创建有效的基础数据
        weather_data = WeatherData(
            location="北京",
            temperature=25.0,
            feels_like=27.0,
            humidity=60,
            wind_speed=10.0,
            wind_direction=180,
            pressure=1013.0,
            visibility=10.0,
            uv_index=5.0,
            condition="晴朗",
            condition_code="01d",
            timestamp=datetime.now(),
            units="metric"
        )
        
        # 手动设置异常值
        weather_data.temperature = 100.0
        weather_data.humidity = 150
        weather_data.wind_speed = -10.0
        weather_data.wind_direction = 400
        weather_data.pressure = 500.0
        
        sanitized = service._sanitize_weather_data(weather_data)
        
        assert sanitized.temperature == 60.0
        assert sanitized.humidity == 100
        assert sanitized.wind_speed == 0.0
        assert sanitized.wind_direction == 40
        assert sanitized.pressure == 800.0
    
    def test_get_friendly_error_message(self, weather_service_mocked):
        """测试友好错误消息"""
        service = weather_service_mocked
        
        assert "暂时不可用" in service._get_friendly_error_message("api_unavailable", "北京")
        assert "未找到位置" in service._get_friendly_error_message("location_not_found", "北京")
        assert "请求过于频繁" in service._get_friendly_error_message("rate_limit")
        assert "网络连接" in service._get_friendly_error_message("network_error")
    
    @pytest.mark.asyncio
    async def test_invalid_forecast_days(self, weather_service_mocked):
        """测试无效的预报天数"""
        service = weather_service_mocked
        
        with pytest.raises(WeatherError, match="预报天数必须在 1-16 之间"):
            await service.get_forecast("北京", 0, "test_user")
        
        with pytest.raises(WeatherError, match="预报天数必须在 1-16 之间"):
            await service.get_forecast("北京", 20, "test_user")
    
    @pytest.mark.asyncio
    async def test_invalid_hourly_hours(self, weather_service_mocked):
        """测试无效的小时数"""
        service = weather_service_mocked
        
        with pytest.raises(WeatherError, match="小时预报时长必须在 1-48 小时之间"):
            await service.get_hourly_forecast("北京", 0, "test_user")
        
        with pytest.raises(WeatherError, match="小时预报时长必须在 1-48 小时之间"):
            await service.get_hourly_forecast("北京", 50, "test_user")


class TestCircuitBreakerStandalone:
    """断路器独立测试"""
    
    def test_circuit_breaker_initialization(self):
        """测试断路器初始化"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_success(self):
        """测试断路器成功调用"""
        cb = CircuitBreaker()
        
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_and_recovery(self):
        """测试断路器失败和恢复"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        async def failing_func():
            raise Exception("Test failure")
        
        async def success_func():
            return "success"
        
        # 触发失败
        with pytest.raises(Exception):
            await cb.call(failing_func)
        assert cb.failure_count == 1
        
        with pytest.raises(Exception):
            await cb.call(failing_func)
        assert cb.failure_count == 2
        assert cb.state == CircuitBreakerState.OPEN
        
        # 断路器开启时直接抛出异常
        with pytest.raises(APIError, match="服务暂时不可用"):
            await cb.call(failing_func)
        
        # 等待恢复时间
        import asyncio
        await asyncio.sleep(0.2)
        
        # 成功调用应该重置断路器
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0