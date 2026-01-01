#!/usr/bin/env python3
"""
天气服务验证脚本

验证WeatherService的基本功能是否正常工作。
"""

import asyncio
import sys
from weather_plugin.weather_service import WeatherService, CircuitBreaker
from weather_plugin.config import WeatherConfig
from weather_plugin.api_client import MockWeatherAPIClient
from weather_plugin.cache import CacheManager
from weather_plugin.location_service import LocationService
from weather_plugin.user_preferences import UserPreferences


async def main():
    """主验证函数"""
    print("🌤️  验证天气服务...")
    
    try:
        # 创建测试配置
        config = WeatherConfig(
            api_provider="openweathermap",
            api_key="test_key",
            cache_enabled=False,  # 禁用缓存避免数据库问题
            default_units="metric",
            default_language="zh",
            cache_ttl_current=600,
            cache_ttl_forecast=3600,
            cache_ttl_hourly=1800
        )
        
        print("✅ 配置创建成功")
        
        # 创建组件
        api_client = MockWeatherAPIClient(config)
        cache_manager = CacheManager(config)
        location_service = LocationService(config)
        user_preferences = UserPreferences(db_path=":memory:")
        
        print("✅ 组件创建成功")
        
        # 创建天气服务
        weather_service = WeatherService(
            config=config,
            api_client=api_client,
            cache_manager=cache_manager,
            location_service=location_service,
            user_preferences=user_preferences
        )
        
        print("✅ 天气服务创建成功")
        
        # 测试断路器
        circuit_breaker = CircuitBreaker()
        assert circuit_breaker.state.value == "closed"
        print("✅ 断路器工作正常")
        
        # 测试数据验证
        from weather_plugin.models import WeatherData
        from datetime import datetime
        
        test_weather = WeatherData(
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
        
        assert weather_service._validate_weather_data(test_weather) is True
        print("✅ 数据验证功能正常")
        
        # 测试错误消息
        error_msg = weather_service._get_friendly_error_message("api_unavailable", "北京")
        assert "暂时不可用" in error_msg
        print("✅ 错误处理功能正常")
        
        # 测试数据清理
        test_weather.temperature = 100.0  # 设置异常值
        sanitized = weather_service._sanitize_weather_data(test_weather)
        assert sanitized.temperature == 60.0  # 应该被修正
        print("✅ 数据清理功能正常")
        
        print("\n🎉 所有验证通过！天气服务核心功能正常工作。")
        return True
        
    except Exception as e:
        print(f"\n❌ 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # 清理资源
        try:
            if 'cache_manager' in locals():
                cache_manager.close()
            if 'api_client' in locals() and hasattr(api_client, 'close'):
                await api_client.close()
        except:
            pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)