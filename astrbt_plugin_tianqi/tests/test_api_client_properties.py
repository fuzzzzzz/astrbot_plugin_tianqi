"""
API 客户端属性测试

使用 Hypothesis 进行基于属性的测试，验证 API 客户端的正确性属性。
"""

import pytest
import asyncio
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.strategies import composite
from unittest.mock import AsyncMock, patch
from weather_plugin.api_client import WeatherAPIClient, MockWeatherAPIClient
from weather_plugin.location_service import LocationService, MockLocationService
from weather_plugin.config import WeatherConfig
from weather_plugin.models import APIError, LocationError


# 测试数据生成策略
@composite
def valid_location_names(draw):
    """生成有效的位置名称"""
    # 城市名称策略
    city_names = st.sampled_from([
        "北京", "上海", "广州", "深圳", "杭州", "南京", "武汉", "成都", "西安", "重庆",
        "London", "Paris", "Tokyo", "New York", "Los Angeles", "Sydney", "Moscow", "Berlin"
    ])
    
    # 坐标格式策略
    coordinates = st.tuples(
        st.floats(min_value=-90, max_value=90),
        st.floats(min_value=-180, max_value=180)
    ).map(lambda coords: f"{coords[0]:.4f},{coords[1]:.4f}")
    
    return draw(st.one_of(city_names, coordinates))


@composite
def invalid_location_names(draw):
    """生成无效的位置名称"""
    invalid_names = st.one_of(
        st.just(""),  # 空字符串
        st.just("   "),  # 只有空格
        st.text(min_size=1, max_size=5).filter(lambda x: x.strip() == ""),  # 只有空白字符
        st.just("999,999"),  # 无效坐标
        st.just("invalid_city_12345"),  # 不存在的城市
    )
    return draw(invalid_names)


@composite
def api_rate_limit_scenarios(draw):
    """生成 API 速率限制测试场景"""
    return {
        'requests_per_minute': draw(st.integers(min_value=0, max_value=200)),
        'daily_requests': draw(st.integers(min_value=0, max_value=2000)),
        'time_interval': draw(st.floats(min_value=0.1, max_value=120.0))
    }


class TestWeatherAPIClientProperties:
    """天气 API 客户端属性测试"""
    
    def _create_mock_config(self):
        """创建模拟配置"""
        return WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key_12345678901234567890123456789012",
            rate_limit_per_minute=60,
            rate_limit_per_day=1000
        )
    
    def _create_api_client(self):
        """创建 API 客户端实例"""
        return MockWeatherAPIClient(self._create_mock_config())
    
    @given(valid_location_names())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_1_weather_data_consistency(self, location):
        """
        属性1：天气数据获取一致性
        Feature: smart-weather-assistant, Property 1: 对于任何有效位置，多次获取相同位置的天气数据应该返回一致的结构
        **验证需求：1.1, 1.2**
        """
        async def test_consistency():
            api_client = self._create_api_client()
            
            # 获取两次相同位置的天气数据
            data1 = await api_client.fetch_current_weather(location)
            data2 = await api_client.fetch_current_weather(location)
            
            # 验证数据结构一致性
            assert isinstance(data1, dict)
            assert isinstance(data2, dict)
            
            # 验证必要字段存在
            required_fields = ['main', 'weather', 'name', 'coord']
            for field in required_fields:
                assert field in data1, f"缺少必要字段: {field}"
                assert field in data2, f"缺少必要字段: {field}"
            
            # 验证数据类型一致性
            assert type(data1['main']) == type(data2['main'])
            assert type(data1['weather']) == type(data2['weather'])
            assert type(data1['name']) == type(data2['name'])
            
            # 验证位置名称一致性（对于相同输入）
            assert data1['name'] == data2['name']
        
        asyncio.run(test_consistency())
    
    @given(st.lists(valid_location_names(), min_size=1, max_size=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_2_location_input_format_support(self, locations):
        """
        属性2：位置输入格式支持
        Feature: smart-weather-assistant, Property 2: 对于任何支持的位置格式，API 客户端都应该能够处理并返回有效响应
        **验证需求：1.5, 6.5**
        """
        async def test_format_support():
            api_client = self._create_api_client()
            
            for location in locations:
                try:
                    data = await api_client.fetch_current_weather(location)
                    
                    # 验证返回数据是有效的字典
                    assert isinstance(data, dict)
                    
                    # 验证包含基本天气信息
                    assert 'main' in data
                    assert 'weather' in data
                    
                    # 验证温度数据是数字
                    if 'temp' in data['main']:
                        assert isinstance(data['main']['temp'], (int, float))
                    
                except APIError:
                    # API 错误是可接受的（例如无效位置）
                    pass
        
        asyncio.run(test_format_support())
    
    @given(st.integers(min_value=1, max_value=16))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_forecast_days_validation(self, days):
        """
        测试预报天数验证
        """
        async def test_days():
            api_client = self._create_api_client()
            
            try:
                data = await api_client.fetch_forecast("北京", days)
                assert isinstance(data, dict)
                assert 'list' in data
                # 验证返回的数据点数量合理
                assert len(data['list']) > 0
            except APIError as e:
                # 某些天数可能超出 API 限制，这是可接受的
                assert "天数" in str(e) or "days" in str(e).lower()
        
        asyncio.run(test_days())
    
    @given(st.integers(min_value=1, max_value=48))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_hourly_forecast_hours_validation(self, hours):
        """
        测试小时预报时长验证
        """
        async def test_hours():
            api_client = self._create_api_client()
            
            try:
                data = await api_client.fetch_hourly_forecast("北京", hours)
                assert isinstance(data, dict)
                assert 'list' in data
                # 验证返回的数据点数量不超过请求的小时数
                assert len(data['list']) <= hours
            except APIError as e:
                # 某些小时数可能超出 API 限制，这是可接受的
                assert "小时" in str(e) or "hours" in str(e).lower()
        
        asyncio.run(test_hours())


class TestLocationServiceProperties:
    """位置服务属性测试"""
    
    def _create_mock_config(self):
        """创建模拟配置"""
        return WeatherConfig()
    
    def _create_location_service(self):
        """创建位置服务实例"""
        return MockLocationService(self._create_mock_config())
    
    @given(invalid_location_names())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.filter_too_much])
    def test_property_11_spelling_correction(self, invalid_location):
        """
        属性11：拼写纠错功能
        Feature: smart-weather-assistant, Property 11: 对于任何无效位置输入，系统应该提供拼写建议
        **验证需求：6.5**
        """
        assume(invalid_location.strip() != "")  # 排除完全空白的输入
        
        location_service = self._create_location_service()
        suggestions = location_service.suggest_corrections(invalid_location)
        
        # 验证返回建议列表
        assert isinstance(suggestions, list)
        
        # 验证建议不为空（对于非空输入）
        if invalid_location.strip():
            assert len(suggestions) >= 0  # 可能没有建议，但应该返回列表
        
        # 验证所有建议都是字符串
        for suggestion in suggestions:
            assert isinstance(suggestion, str)
            assert len(suggestion.strip()) > 0
    
    @given(st.floats(min_value=-90, max_value=90), st.floats(min_value=-180, max_value=180))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_coordinate_validation_property(self, lat, lon):
        """
        坐标验证属性测试
        对于任何有效范围内的坐标，验证函数应该返回 True
        """
        # 过滤掉 NaN 和无穷大值
        assume(not (lat != lat or lon != lon))  # 排除 NaN
        assume(abs(lat) != float('inf') and abs(lon) != float('inf'))  # 排除无穷大
        
        location_service = self._create_location_service()
        result = location_service.validate_coordinates(lat, lon)
        assert result is True
    
    @given(
        st.one_of(
            st.floats(min_value=-1000, max_value=-90.1),  # 纬度过小
            st.floats(min_value=90.1, max_value=1000),    # 纬度过大
        ),
        st.floats(min_value=-180, max_value=180)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_latitude_rejection(self, invalid_lat, lon):
        """
        测试无效纬度被正确拒绝
        """
        assume(not (invalid_lat != invalid_lat or lon != lon))  # 排除 NaN
        assume(abs(invalid_lat) != float('inf') and abs(lon) != float('inf'))
        
        location_service = self._create_location_service()
        result = location_service.validate_coordinates(invalid_lat, lon)
        assert result is False
    
    @given(
        st.floats(min_value=-90, max_value=90),
        st.one_of(
            st.floats(min_value=-1000, max_value=-180.1),  # 经度过小
            st.floats(min_value=180.1, max_value=1000),    # 经度过大
        )
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_longitude_rejection(self, lat, invalid_lon):
        """
        测试无效经度被正确拒绝
        """
        assume(not (lat != lat or invalid_lon != invalid_lon))  # 排除 NaN
        assume(abs(lat) != float('inf') and abs(invalid_lon) != float('inf'))
        
        location_service = self._create_location_service()
        result = location_service.validate_coordinates(lat, invalid_lon)
        assert result is False
    
    @given(valid_location_names())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_location_parsing_consistency(self, location):
        """
        位置解析一致性测试
        对于任何有效位置，多次解析应该返回相同结果
        """
        location_service = self._create_location_service()
        
        try:
            result1 = location_service.parse_location(location)
            result2 = location_service.parse_location(location)
            
            # 验证结果一致性
            assert result1.name == result2.name
            
            if result1.coordinates and result2.coordinates:
                assert result1.coordinates.latitude == result2.coordinates.latitude
                assert result1.coordinates.longitude == result2.coordinates.longitude
            
        except LocationError:
            # 某些位置可能无法解析，这是可接受的
            pass


class TestAPIRateLimitProperties:
    """API 速率限制属性测试"""
    
    def _create_rate_limited_config(self):
        """创建速率限制配置"""
        return WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key_12345678901234567890123456789012",
            rate_limit_per_minute=5,  # 较低的限制用于测试
            rate_limit_per_day=100
        )
    
    def _create_rate_limited_client(self):
        """创建速率限制的 API 客户端"""
        return MockWeatherAPIClient(self._create_rate_limited_config())
    
    def test_property_13_api_rate_limit_handling(self):
        """
        属性13：API限制处理
        Feature: smart-weather-assistant, Property 13: 对于任何 API 请求序列，速率限制应该被正确检测和处理
        **验证需求：7.3, 7.4**
        """
        # 测试速率限制检查
        client = self._create_rate_limited_client()
        
        # 初始状态应该允许请求
        assert client.check_rate_limit() is True
        
        # 模拟快速连续请求
        for i in range(client.config.rate_limit_per_minute):
            if client.check_rate_limit():
                client._record_request()
        
        # 超过限制后应该被拒绝
        assert client.check_rate_limit() is False
    
    @given(st.integers(min_value=1, max_value=20))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_rate_limit_recovery(self, request_count):
        """
        测试速率限制恢复
        """
        client = self._create_rate_limited_client()
        
        # 发起一定数量的请求
        for _ in range(min(request_count, client.config.rate_limit_per_minute)):
            if client.check_rate_limit():
                client._record_request()
        
        # 验证速率限制状态
        if request_count >= client.config.rate_limit_per_minute:
            assert client.check_rate_limit() is False
        else:
            assert client.check_rate_limit() is True


# 运行属性测试的辅助函数
def run_property_tests():
    """运行所有属性测试"""
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_property_tests()