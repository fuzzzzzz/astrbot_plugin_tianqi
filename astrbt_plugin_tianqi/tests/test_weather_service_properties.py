"""
天气服务属性测试

使用属性测试验证天气服务的正确性属性。
"""

import pytest
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from unittest.mock import Mock, AsyncMock
from datetime import datetime, date, timedelta
import asyncio

from weather_plugin.weather_service import WeatherService
from weather_plugin.config import WeatherConfig
from weather_plugin.models import (
    WeatherData, ForecastData, ForecastDay, HourlyForecastData,
    LocationInfo, UserPrefs, APIError, LocationError
)


class TestWeatherServiceProperties:
    """天气服务属性测试"""
    
    def create_weather_service(self):
        """创建模拟的天气服务实例"""
        config = WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key",
            cache_enabled=False,  # 禁用缓存简化测试
            default_units="metric",
            default_language="zh",
            cache_ttl_current=600,
            cache_ttl_forecast=3600,
            cache_ttl_hourly=1800
        )
        
        mock_api_client = Mock()
        mock_cache_manager = Mock()
        mock_location_service = Mock()
        mock_user_preferences = Mock()
        
        # 配置基本模拟行为
        mock_cache_manager.get_cached_weather = AsyncMock(return_value=None)
        mock_cache_manager.get_cached_forecast = AsyncMock(return_value=None)
        mock_cache_manager.cache_weather_data = AsyncMock()
        mock_cache_manager.cache_forecast_data = AsyncMock()
        mock_cache_manager.generate_cache_key.return_value = "test_cache_key"
        
        return WeatherService(
            config=config,
            api_client=mock_api_client,
            cache_manager=mock_cache_manager,
            location_service=mock_location_service,
            user_preferences=mock_user_preferences
        )
    
    # 生成策略
    @st.composite
    def valid_location_strategy(draw):
        """生成有效的位置名称"""
        cities = ["北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "成都", "西安", "重庆"]
        return draw(st.sampled_from(cities))
    
    @st.composite
    def valid_forecast_days_strategy(draw):
        """生成有效的预报天数"""
        return draw(st.integers(min_value=1, max_value=16))
    
    @st.composite
    def valid_weather_data_strategy(draw):
        """生成有效的天气数据"""
        location = draw(st.text(min_size=1, max_size=50))
        temperature = draw(st.floats(min_value=-50.0, max_value=50.0))
        feels_like = draw(st.floats(min_value=-50.0, max_value=50.0))
        humidity = draw(st.integers(min_value=0, max_value=100))
        wind_speed = draw(st.floats(min_value=0.0, max_value=200.0))
        wind_direction = draw(st.integers(min_value=0, max_value=360))
        pressure = draw(st.floats(min_value=800.0, max_value=1100.0))
        visibility = draw(st.floats(min_value=0.0, max_value=50.0))
        uv_index = draw(st.floats(min_value=0.0, max_value=15.0))
        condition = draw(st.text(min_size=1, max_size=100))
        condition_code = draw(st.text(min_size=1, max_size=10))
        units = draw(st.sampled_from(["metric", "imperial"]))
        
        return WeatherData(
            location=location,
            temperature=temperature,
            feels_like=feels_like,
            humidity=humidity,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            pressure=pressure,
            visibility=visibility,
            uv_index=uv_index,
            condition=condition,
            condition_code=condition_code,
            timestamp=datetime.now(),
            units=units
        )
    
    @st.composite
    def valid_forecast_day_strategy(draw):
        """生成有效的预报日数据"""
        forecast_date = draw(st.dates(
            min_value=date.today(),
            max_value=date.today() + timedelta(days=16)
        ))
        low_temp = draw(st.floats(min_value=-50.0, max_value=40.0))
        high_temp = draw(st.floats(min_value=low_temp, max_value=50.0))
        condition = draw(st.text(min_size=1, max_size=100))
        precipitation_chance = draw(st.integers(min_value=0, max_value=100))
        wind_speed = draw(st.floats(min_value=0.0, max_value=200.0))
        humidity = draw(st.integers(min_value=0, max_value=100))
        
        return ForecastDay(
            date=forecast_date,
            high_temp=high_temp,
            low_temp=low_temp,
            condition=condition,
            precipitation_chance=precipitation_chance,
            wind_speed=wind_speed,
            humidity=humidity
        )
    
    @st.composite
    def openweathermap_api_response_strategy(draw):
        """生成OpenWeatherMap API响应格式的数据"""
        temp = draw(st.floats(min_value=-50.0, max_value=50.0))
        feels_like = draw(st.floats(min_value=-50.0, max_value=50.0))
        humidity = draw(st.integers(min_value=0, max_value=100))
        pressure = draw(st.floats(min_value=800.0, max_value=1100.0))
        wind_speed = draw(st.floats(min_value=0.0, max_value=200.0))
        wind_deg = draw(st.integers(min_value=0, max_value=360))
        visibility = draw(st.integers(min_value=0, max_value=50000))
        description = draw(st.text(min_size=1, max_size=100))
        icon = draw(st.text(min_size=1, max_size=10))
        
        return {
            "main": {
                "temp": temp,
                "feels_like": feels_like,
                "humidity": humidity,
                "pressure": pressure
            },
            "weather": [{"description": description, "icon": icon}],
            "wind": {"speed": wind_speed, "deg": wind_deg},
            "visibility": visibility
        }
    
    @st.composite
    def openweathermap_forecast_response_strategy(draw):
        """生成OpenWeatherMap预报API响应格式的数据"""
        list_size = draw(st.integers(min_value=1, max_value=40))
        forecast_list = []
        
        base_time = int(datetime.now().timestamp())
        for i in range(list_size):
            temp = draw(st.floats(min_value=-50.0, max_value=50.0))
            humidity = draw(st.integers(min_value=0, max_value=100))
            pressure = draw(st.floats(min_value=800.0, max_value=1100.0))
            wind_speed = draw(st.floats(min_value=0.0, max_value=200.0))
            wind_deg = draw(st.integers(min_value=0, max_value=360))
            description = draw(st.text(min_size=1, max_size=100))
            icon = draw(st.text(min_size=1, max_size=10))
            pop = draw(st.floats(min_value=0.0, max_value=1.0))
            
            forecast_list.append({
                "dt": base_time + (i * 3 * 3600),  # 每3小时
                "main": {
                    "temp": temp,
                    "humidity": humidity,
                    "pressure": pressure
                },
                "weather": [{"description": description, "icon": icon}],
                "wind": {"speed": wind_speed, "deg": wind_deg},
                "pop": pop
            })
        
        return {
            "cod": "200",
            "message": 0,
            "cnt": len(forecast_list),
            "list": forecast_list
        }
    
    # 属性测试
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(valid_weather_data_strategy())
    def test_property_weather_data_validation_consistency(self, weather_data):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：天气数据验证的一致性
        对于任何有效的天气数据，验证函数应该返回一致的结果
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        service = self.create_weather_service()
        
        # 验证应该是确定性的
        result1 = service._validate_weather_data(weather_data)
        result2 = service._validate_weather_data(weather_data)
        
        assert result1 == result2, "天气数据验证结果应该是一致的"
    
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(valid_weather_data_strategy())
    def test_property_weather_data_sanitization_idempotence(self, weather_data):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：天气数据清理的幂等性
        对于任何天气数据，多次清理应该产生相同的结果
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        service = self.create_weather_service()
        
        # 第一次清理
        sanitized1 = service._sanitize_weather_data(weather_data)
        # 第二次清理
        sanitized2 = service._sanitize_weather_data(sanitized1)
        
        # 清理操作应该是幂等的
        assert sanitized1.temperature == sanitized2.temperature
        assert sanitized1.humidity == sanitized2.humidity
        assert sanitized1.wind_speed == sanitized2.wind_speed
        assert sanitized1.pressure == sanitized2.pressure
        assert sanitized1.wind_direction == sanitized2.wind_direction
    
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(openweathermap_api_response_strategy(), valid_location_strategy(), st.sampled_from(["metric", "imperial"]))
    def test_property_api_data_conversion_preserves_structure(self, api_response, location, units):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：API数据转换保持结构完整性
        对于任何有效的API响应，转换后的数据应该包含所有必要字段
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        service = self.create_weather_service()
        
        try:
            weather_data = service._convert_current_weather_data(api_response, location, units)
            
            # 验证所有必要字段都存在且类型正确
            assert isinstance(weather_data.location, str)
            assert isinstance(weather_data.temperature, (int, float))
            assert isinstance(weather_data.feels_like, (int, float))
            assert isinstance(weather_data.humidity, int)
            assert isinstance(weather_data.wind_speed, (int, float))
            assert isinstance(weather_data.wind_direction, int)
            assert isinstance(weather_data.pressure, (int, float))
            assert isinstance(weather_data.visibility, (int, float))
            assert isinstance(weather_data.condition, str)
            assert isinstance(weather_data.condition_code, str)
            assert isinstance(weather_data.units, str)
            assert isinstance(weather_data.timestamp, datetime)
            
            # 验证位置和单位正确设置
            assert weather_data.location == location
            assert weather_data.units == units
            
        except Exception as e:
            # 如果转换失败，应该是由于数据格式问题，而不是程序错误
            assert "格式错误" in str(e) or "缺少字段" in str(e)
    
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(openweathermap_forecast_response_strategy(), valid_location_strategy(), 
           valid_forecast_days_strategy(), st.sampled_from(["metric", "imperial"]))
    def test_property_forecast_data_conversion_integrity(self, api_response, location, days, units):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：预报数据转换的完整性
        对于任何有效的预报API响应，转换后的数据应该保持逻辑一致性
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        service = self.create_weather_service()
        
        try:
            forecast_data = service._convert_forecast_data(api_response, location, days, units)
            
            # 验证基本结构
            assert isinstance(forecast_data, ForecastData)
            assert forecast_data.location == location
            assert forecast_data.units == units
            assert isinstance(forecast_data.days, list)
            assert len(forecast_data.days) <= days  # 不应超过请求的天数
            
            # 验证每日数据的完整性
            for day in forecast_data.days:
                assert isinstance(day, ForecastDay)
                assert isinstance(day.date, date)
                assert isinstance(day.high_temp, (int, float))
                assert isinstance(day.low_temp, (int, float))
                assert isinstance(day.condition, str)
                assert isinstance(day.precipitation_chance, int)
                assert isinstance(day.wind_speed, (int, float))
                assert isinstance(day.humidity, int)
                
                # 验证逻辑约束
                assert day.high_temp >= day.low_temp, "最高温度应该不低于最低温度"
                assert 0 <= day.precipitation_chance <= 100, "降水概率应该在0-100之间"
                assert 0 <= day.humidity <= 100, "湿度应该在0-100之间"
                assert day.wind_speed >= 0, "风速不应该为负数"
            
            # 验证日期顺序
            if len(forecast_data.days) > 1:
                for i in range(1, len(forecast_data.days)):
                    assert forecast_data.days[i].date >= forecast_data.days[i-1].date, "预报日期应该按顺序排列"
                    
        except Exception as e:
            # 如果转换失败，应该是由于数据格式问题
            assert "格式错误" in str(e) or "缺少字段" in str(e) or "转换失败" in str(e)
    
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(st.lists(valid_forecast_day_strategy(), min_size=1, max_size=16))
    def test_property_forecast_data_serialization_roundtrip(self, forecast_days):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：预报数据序列化往返一致性
        对于任何预报数据，序列化后再反序列化应该得到等价的数据
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        # 创建预报数据
        forecast_data = ForecastData(
            location="测试城市",
            days=forecast_days,
            units="metric",
            generated_at=datetime.now()
        )
        
        # 序列化往返测试
        serialized = forecast_data.to_json()
        deserialized = ForecastData.from_dict(forecast_data.to_dict())
        
        # 验证关键字段保持一致
        assert deserialized.location == forecast_data.location
        assert deserialized.units == forecast_data.units
        assert len(deserialized.days) == len(forecast_data.days)
        
        # 验证每日数据
        for original_day, deserialized_day in zip(forecast_data.days, deserialized.days):
            assert deserialized_day.date == original_day.date
            assert deserialized_day.high_temp == original_day.high_temp
            assert deserialized_day.low_temp == original_day.low_temp
            assert deserialized_day.condition == original_day.condition
            assert deserialized_day.precipitation_chance == original_day.precipitation_chance
            assert deserialized_day.wind_speed == original_day.wind_speed
            assert deserialized_day.humidity == original_day.humidity
    
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(st.text(min_size=1, max_size=100))
    def test_property_error_message_consistency(self, location):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：错误消息的一致性
        对于相同的错误类型和位置，应该生成一致的错误消息
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        service = self.create_weather_service()
        
        error_types = ["api_unavailable", "location_not_found", "rate_limit", "network_error"]
        
        for error_type in error_types:
            # 多次调用应该返回相同的消息
            msg1 = service._get_friendly_error_message(error_type, location)
            msg2 = service._get_friendly_error_message(error_type, location)
            
            assert msg1 == msg2, f"错误类型 {error_type} 的消息应该一致"
            assert isinstance(msg1, str), "错误消息应该是字符串"
            assert len(msg1) > 0, "错误消息不应该为空"
    
    @settings(max_examples=50, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])  # 减少测试数量以提高速度
    @given(st.integers(min_value=-1000, max_value=1000))
    def test_property_invalid_forecast_days_handling(self, days):
        """
        **Feature: smart-weather-assistant, Property 3: 预报数据完整性**
        
        属性：无效预报天数的处理
        对于任何超出有效范围的天数，应该抛出适当的异常
        **Validates: Requirements 2.1, 2.2, 2.3**
        """
        service = self.create_weather_service()
        
        # 配置模拟
        service.location_service.parse_location.return_value = LocationInfo(name="北京")
        service.user_preferences.get_user_preferences.return_value = UserPrefs(
            user_id="test_user", units="metric"
        )
        
        async def run_test():
            if days <= 0 or days > 16:
                # 无效天数应该抛出异常
                with pytest.raises(Exception):  # 可能是ValueError或WeatherError
                    await service.get_forecast("北京", days, "test_user")
            else:
                # 有效天数不应该因为天数验证而失败
                # 注意：可能因为其他原因失败（如API调用），但不应该是天数验证
                try:
                    await service.get_forecast("北京", days, "test_user")
                except Exception as e:
                    # 如果失败，不应该是因为天数验证
                    assert "预报天数必须在 1-16 之间" not in str(e)
        
        # 运行异步测试
        asyncio.run(run_test())


# 运行属性测试的辅助函数
def run_property_tests():
    """运行所有属性测试"""
    import subprocess
    import sys
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_weather_service_properties.py", 
        "-v", "--tb=short"
    ], capture_output=True, text=True)
    
    return result.returncode == 0, result.stdout, result.stderr


if __name__ == "__main__":
    # 直接运行时执行属性测试
    success, stdout, stderr = run_property_tests()
    print(stdout)
    if stderr:
        print("STDERR:", stderr)
    exit(0 if success else 1)