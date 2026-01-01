"""
智能天气助手集成测试

测试端到端天气查询流程和组件间的正确交互。
验证需求：1.1, 2.1, 3.3
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date

from weather_plugin.plugin import WeatherPlugin
from weather_plugin.config import WeatherConfig
from weather_plugin.models import (
    WeatherData, ForecastData, ForecastDay, HourlyForecastData,
    UserPrefs, LocationInfo, WeatherAlert, Activity,
    APIError, LocationError, WeatherError
)


class TestWeatherPluginIntegration:
    """天气插件端到端集成测试"""
    
    @pytest.fixture
    def test_config(self):
        """测试配置"""
        return {
            'api_provider': 'openweathermap',
            'api_key': 'test_api_key_12345',
            'cache_enabled': False,  # 禁用缓存避免数据库问题
            'default_units': 'metric',
            'default_language': 'zh',
            'cache_ttl_current': 600,
            'cache_ttl_forecast': 3600,
            'cache_ttl_hourly': 1800,
            'cache_db_path': ':memory:'  # 使用内存数据库
        }
    
    @pytest.fixture
    def weather_plugin(self, test_config):
        """天气插件实例"""
        plugin = WeatherPlugin(test_config)
        yield plugin
        plugin.close()
    
    @pytest.fixture
    def mock_message_event(self):
        """模拟消息事件"""
        class MockEvent:
            def __init__(self, message: str, user_id: str = "test_user"):
                self.message = message
                self.user_id = user_id
        
        return MockEvent
    
    @pytest.mark.asyncio
    async def test_end_to_end_current_weather_query(self, weather_plugin, mock_message_event):
        """
        测试端到端当前天气查询流程
        验证需求：1.1 - 天气数据获取一致性
        """
        # 模拟API响应
        mock_api_response = {
            "main": {
                "temp": 25.0,
                "feels_like": 27.0,
                "humidity": 60,
                "pressure": 1013.0
            },
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 10.0, "deg": 180},
            "visibility": 10000,
            "name": "北京"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather', 
                         new_callable=AsyncMock, return_value=mock_api_response):
            
            # 测试自然语言查询
            event = mock_message_event("北京今天天气怎么样？", "test_user")
            response = await weather_plugin.on_message(event)
            
            # 验证响应包含天气信息
            assert response is not None
            assert "北京" in response
            assert "25.0°C" in response or "25°C" in response
            assert "晴朗" in response
            assert "湿度" in response
            assert "60%" in response
    
    @pytest.mark.asyncio
    async def test_end_to_end_forecast_query(self, weather_plugin, mock_message_event):
        """
        测试端到端预报查询流程
        验证需求：2.1 - 预报数据完整性
        """
        # 模拟预报API响应
        mock_forecast_response = {
            "list": [
                {
                    "dt": int(datetime.now().timestamp()) + 86400,  # 明天
                    "main": {
                        "temp": 28.0,
                        "temp_min": 20.0,
                        "temp_max": 30.0,
                        "humidity": 65,
                        "pressure": 1015.0
                    },
                    "weather": [{"description": "多云", "icon": "02d"}],
                    "wind": {"speed": 8.0, "deg": 200},
                    "pop": 0.3
                },
                {
                    "dt": int(datetime.now().timestamp()) + 172800,  # 后天
                    "main": {
                        "temp": 26.0,
                        "temp_min": 18.0,
                        "temp_max": 28.0,
                        "humidity": 70,
                        "pressure": 1010.0
                    },
                    "weather": [{"description": "小雨", "icon": "10d"}],
                    "wind": {"speed": 12.0, "deg": 220},
                    "pop": 0.8
                }
            ],
            "city": {"name": "上海"}
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_forecast',
                         new_callable=AsyncMock, return_value=mock_forecast_response):
            
            # 测试预报命令（直接命令而不是自然语言）
            response = await weather_plugin.on_command("forecast", ["上海"], "test_user")
            
            # 验证响应包含预报信息
            assert response is not None
            assert "上海" in response
            assert "预报" in response
            # 应该包含多天的信息
            assert "多云" in response or "小雨" in response
            assert "降水概率" in response or "%" in response
    
    @pytest.mark.asyncio
    async def test_component_interaction_with_user_preferences(self, weather_plugin):
        """
        测试组件间交互 - 用户偏好集成
        验证需求：3.3 - 组件间正确交互
        """
        user_id = "test_user_prefs"
        
        # 1. 设置用户偏好
        weather_plugin.user_preferences.set_default_location(user_id, "深圳")
        weather_plugin.user_preferences.set_units(user_id, "imperial")
        
        # 2. 验证偏好已保存
        prefs = weather_plugin.user_preferences.get_user_preferences(user_id)
        assert prefs.default_location == "深圳"
        assert prefs.units == "imperial"
        
        # 3. 模拟API响应（华氏度）
        mock_api_response = {
            "main": {
                "temp": 68.0,  # 华氏度 (约20°C)
                "feels_like": 70.0,
                "humidity": 60,
                "pressure": 1013.0
            },
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 6.2, "deg": 180},  # mph
            "visibility": 6.2,  # miles
            "name": "深圳"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, return_value=mock_api_response):
            
            # 4. 查询天气（不指定位置，应使用默认位置和单位）
            response = await weather_plugin.on_command("weather", [], user_id)
            
            # 5. 验证使用了用户偏好
            assert "深圳" in response
            assert "°F" in response  # 验证使用华氏度单位
            assert "mph" in response  # 验证使用英制单位
    
    @pytest.mark.asyncio
    async def test_basic_integration_flow(self, weather_plugin):
        """
        测试基本集成流程
        验证核心组件的正确交互
        """
        # 模拟API响应
        mock_api_response = {
            "main": {
                "temp": 22.0,
                "feels_like": 24.0,
                "humidity": 55,
                "pressure": 1018.0
            },
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 5.0, "deg": 90},
            "visibility": 10000,
            "name": "广州"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, return_value=mock_api_response) as mock_api:
            
            # 查询天气
            response = await weather_plugin.on_command("weather", ["广州"], "test_user")
            
            # 验证API被调用
            mock_api.assert_called_once()
            assert "广州" in response
            assert "22.0°C" in response or "22°C" in response
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, weather_plugin):
        """
        测试错误处理集成
        验证各组件的错误处理协作
        """
        # 模拟API错误
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, side_effect=APIError("API服务不可用")):
            
            # 使用直接命令而不是自然语言
            response = await weather_plugin.on_command("weather", ["北京"], "test_user")
            
            # 验证返回友好的错误消息
            assert response is not None
            # 错误消息可能是本地化键或实际消息
            assert ("暂时不可用" in response or "服务" in response or "错误" in response or 
                   "失败" in response or "weather_query_failed" in response)
    
    @pytest.mark.asyncio
    async def test_location_service_integration(self, weather_plugin):
        """
        测试位置服务集成
        验证位置解析与天气查询的集成
        """
        # 模拟位置服务返回标准化位置
        mock_location = LocationInfo(name="北京市")
        
        with patch.object(weather_plugin.location_service, 'parse_location',
                         return_value=mock_location):
            
            # 模拟API响应
            mock_api_response = {
                "main": {"temp": 20.0, "feels_like": 22.0, "humidity": 50, "pressure": 1020.0},
                "weather": [{"description": "晴朗", "icon": "01d"}],
                "wind": {"speed": 3.0, "deg": 45},
                "visibility": 10000,
                "name": "北京市"
            }
            
            with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                             new_callable=AsyncMock, return_value=mock_api_response):
                
                # 使用不标准的位置名称
                response = await weather_plugin.on_command("weather", ["beijing"], "test_user")
                
                # 验证位置被正确解析和使用
                assert "北京市" in response
                weather_plugin.location_service.parse_location.assert_called_once_with("beijing")
    
    @pytest.mark.asyncio
    async def test_command_parser_integration(self, weather_plugin, mock_message_event):
        """
        测试命令解析器集成
        验证自然语言解析与天气服务的集成
        """
        # 模拟API响应
        mock_api_response = {
            "main": {"temp": 18.0, "feels_like": 20.0, "humidity": 65, "pressure": 1012.0},
            "weather": [{"description": "阴天", "icon": "04d"}],
            "wind": {"speed": 8.0, "deg": 270},
            "visibility": 8000,
            "name": "杭州"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, return_value=mock_api_response):
            
            # 测试各种自然语言表达
            test_messages = [
                "杭州今天天气怎么样？",
                "杭州的天气",
                "今天杭州天气",
                "杭州天气如何"
            ]
            
            for message in test_messages:
                event = mock_message_event(message, "test_user")
                response = await weather_plugin.on_message(event)
                
                # 验证都能正确解析并返回天气信息
                assert response is not None
                assert "杭州" in response
                assert "18.0°C" in response or "18°C" in response
    
    @pytest.mark.asyncio
    async def test_weather_service_integration(self, weather_plugin):
        """
        测试天气服务集成
        验证天气服务与其他组件的集成
        """
        # 模拟晴朗天气的API响应
        mock_api_response = {
            "main": {"temp": 25.0, "feels_like": 27.0, "humidity": 45, "pressure": 1025.0},
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 5.0, "deg": 180},
            "visibility": 15000,
            "name": "成都"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, return_value=mock_api_response):
            
            # 查询天气
            response = await weather_plugin.on_command("weather", ["成都"], "test_user")
            
            # 验证返回了天气信息
            assert response is not None
            assert "成都" in response
            assert "25.0°C" in response or "25°C" in response
            assert "晴朗" in response
    
    @pytest.mark.asyncio
    async def test_forecast_service_integration(self, weather_plugin):
        """
        测试预报服务集成
        验证预报服务与主系统的集成
        """
        # 模拟预报API响应
        mock_forecast_response = {
            "list": [
                {
                    "dt": int(datetime.now().timestamp()) + 86400,
                    "main": {"temp": 28.0, "temp_min": 20.0, "temp_max": 30.0, "humidity": 65, "pressure": 1015.0},
                    "weather": [{"description": "多云", "icon": "02d"}],
                    "wind": {"speed": 8.0, "deg": 200},
                    "pop": 0.3
                }
            ],
            "city": {"name": "武汉"}
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_forecast',
                         new_callable=AsyncMock, return_value=mock_forecast_response):
            
            # 查询天气预报
            response = await weather_plugin.on_command("forecast", ["武汉"], "test_user")
            
            # 验证返回了预报信息
            assert response is not None
            assert "武汉" in response
            assert "预报" in response
    
    @pytest.mark.asyncio
    async def test_help_system_integration(self, weather_plugin, mock_message_event):
        """
        测试帮助系统集成
        验证帮助系统与主插件的集成
        """
        # 测试帮助命令
        response = await weather_plugin.on_command("help", [], "test_user")
        
        # 验证返回了帮助信息
        assert response is not None
        assert "帮助" in response
        assert "weather" in response or "天气" in response
        assert "forecast" in response or "预报" in response
        
        # 测试自然语言帮助请求
        event = mock_message_event("天气助手怎么用？", "test_user")
        response = await weather_plugin.on_message(event)
        
        # 应该返回帮助信息或建议
        assert response is not None


class TestWeatherPluginErrorScenarios:
    """天气插件错误场景集成测试"""
    
    @pytest.fixture
    def weather_plugin_with_invalid_config(self):
        """使用无效配置的天气插件"""
        invalid_config = {
            'api_provider': 'openweathermap',
            'api_key': '',  # 空API密钥
            'cache_enabled': True,
            'default_units': 'metric',
            'default_language': 'zh'
        }
        
        with pytest.raises(Exception):  # 应该抛出配置错误
            WeatherPlugin(invalid_config)
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, weather_plugin):
        """
        测试网络错误处理
        验证网络问题时的降级策略
        """
        # 模拟网络错误
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, side_effect=Exception("网络连接超时")):
            
            # 使用直接命令
            response = await weather_plugin.on_command("weather", ["天津"], "test_user")
            
            # 验证返回友好的错误消息
            assert response is not None
            assert ("网络" in response or "连接" in response or "暂时不可用" in response or 
                   "失败" in response or "weather_query_failed" in response)
    
    @pytest.mark.asyncio
    async def test_invalid_location_handling(self, weather_plugin):
        """
        测试无效位置处理
        验证位置不存在时的错误处理
        """
        # 模拟位置服务抛出位置错误
        with patch.object(weather_plugin.location_service, 'parse_location',
                         side_effect=LocationError("位置不存在")):
            
            response = await weather_plugin.on_command("weather", ["不存在的城市"], "test_user")
            
            # 验证返回位置错误信息
            assert response is not None
            assert ("位置" in response or "找不到" in response or "不存在" in response or 
                   "weather_query_failed" in response)


class TestWeatherPluginPerformance:
    """天气插件性能集成测试"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self, weather_plugin):
        """
        测试并发请求处理
        验证系统在并发负载下的稳定性
        """
        # 模拟API响应
        mock_api_response = {
            "main": {"temp": 23.0, "feels_like": 25.0, "humidity": 60, "pressure": 1015.0},
            "weather": [{"description": "多云", "icon": "02d"}],
            "wind": {"speed": 7.0, "deg": 200},
            "visibility": 10000,
            "name": "南京"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, return_value=mock_api_response):
            
            # 创建多个并发请求
            tasks = []
            for i in range(5):
                task = weather_plugin.on_command("weather", ["南京"], f"user_{i}")
                tasks.append(task)
            
            # 等待所有请求完成
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 验证所有请求都成功处理
            for response in responses:
                assert not isinstance(response, Exception)
                assert response is not None
                assert "南京" in response
    
    @pytest.mark.asyncio
    async def test_cache_performance_under_load(self, weather_plugin, mock_message_event):
        """
        测试缓存在负载下的性能
        验证缓存系统的并发安全性
        """
        # 模拟API响应
        mock_api_response = {
            "main": {"temp": 21.0, "feels_like": 23.0, "humidity": 55, "pressure": 1020.0},
            "weather": [{"description": "晴朗", "icon": "01d"}],
            "wind": {"speed": 4.0, "deg": 90},
            "visibility": 12000,
            "name": "苏州"
        }
        
        with patch.object(weather_plugin.api_client, 'fetch_current_weather',
                         new_callable=AsyncMock, return_value=mock_api_response) as mock_api:
            
            # 第一次请求建立缓存
            event = mock_message_event("苏州天气", "user_1")
            await weather_plugin.on_message(event)
            
            # 重置API调用计数
            mock_api.reset_mock()
            
            # 创建多个并发的相同请求
            tasks = []
            for i in range(10):
                event = mock_message_event("苏州天气", f"user_{i}")
                task = weather_plugin.on_message(event)
                tasks.append(task)
            
            # 等待所有请求完成
            responses = await asyncio.gather(*tasks)
            
            # 验证所有请求都返回了正确结果
            for response in responses:
                assert response is not None
                assert "苏州" in response
                assert "21.0°C" in response or "21°C" in response
            
            # 验证API没有被重复调用（使用了缓存）
            assert mock_api.call_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])