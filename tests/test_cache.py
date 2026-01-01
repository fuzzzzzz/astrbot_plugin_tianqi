"""
缓存管理器测试

测试CacheManager类的基本功能和缓存清理机制。
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

from weather_plugin.cache import CacheManager
from weather_plugin.config import WeatherConfig
from weather_plugin.models import WeatherData, ForecastData, ForecastDay, CacheError


@pytest.fixture
def temp_config():
    """创建临时配置用于测试"""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test_cache.db")
        config = WeatherConfig(
            api_key="test_key",
            cache_enabled=True,
            cache_db_path=db_path,
            cache_ttl_current=600,
            cache_ttl_forecast=3600
        )
        yield config


@pytest.fixture
def cache_manager(temp_config):
    """创建缓存管理器实例"""
    manager = CacheManager(temp_config)
    yield manager
    # 确保所有连接都关闭
    manager.close()
    # 强制垃圾回收以释放SQLite连接
    import gc
    gc.collect()
    # 给Windows一点时间释放文件句柄
    import time
    time.sleep(0.1)


@pytest.fixture
def sample_weather_data():
    """创建示例天气数据"""
    return WeatherData(
        location="北京",
        temperature=25.0,
        feels_like=27.0,
        humidity=60,
        wind_speed=5.0,
        wind_direction=180,
        pressure=1013.25,
        visibility=10.0,
        uv_index=5.0,
        condition="晴天",
        condition_code="clear",
        timestamp=datetime.now(),
        units="metric"
    )


@pytest.fixture
def sample_forecast_data():
    """创建示例预报数据"""
    days = [
        ForecastDay(
            date=datetime.now().date(),
            high_temp=28.0,
            low_temp=18.0,
            condition="晴天",
            precipitation_chance=10,
            wind_speed=5.0,
            humidity=55
        )
    ]
    return ForecastData(
        location="北京",
        days=days,
        units="metric",
        generated_at=datetime.now()
    )


class TestCacheManager:
    """缓存管理器测试类"""
    
    def test_cache_manager_initialization(self, cache_manager):
        """测试缓存管理器初始化"""
        assert cache_manager.config.cache_enabled is True
        assert Path(cache_manager.db_path).parent.exists()
    
    def test_generate_cache_key(self, cache_manager):
        """测试缓存键生成"""
        key1 = cache_manager.generate_cache_key("北京", "weather")
        key2 = cache_manager.generate_cache_key("北京", "weather")
        key3 = cache_manager.generate_cache_key("上海", "weather")
        
        # 相同参数应生成相同键
        assert key1 == key2
        # 不同参数应生成不同键
        assert key1 != key3
        # 键应包含前缀
        assert key1.startswith("weather_cache:")
    
    def test_generate_cache_key_with_kwargs(self, cache_manager):
        """测试带额外参数的缓存键生成"""
        key1 = cache_manager.generate_cache_key("北京", "forecast", days=5, units="metric")
        key2 = cache_manager.generate_cache_key("北京", "forecast", days=3, units="metric")
        
        assert key1 != key2
    
    @pytest.mark.asyncio
    async def test_cache_weather_data(self, cache_manager, sample_weather_data):
        """测试缓存天气数据"""
        cache_key = cache_manager.generate_cache_key("北京", "weather")
        
        # 缓存数据
        await cache_manager.cache_weather_data(cache_key, sample_weather_data, 600)
        
        # 获取缓存数据
        cached_data = await cache_manager.get_cached_weather(cache_key)
        
        assert cached_data is not None
        assert cached_data.location == sample_weather_data.location
        assert cached_data.temperature == sample_weather_data.temperature
    
    @pytest.mark.asyncio
    async def test_cache_forecast_data(self, cache_manager, sample_forecast_data):
        """测试缓存预报数据"""
        cache_key = cache_manager.generate_cache_key("北京", "forecast")
        
        # 缓存数据
        await cache_manager.cache_forecast_data(cache_key, sample_forecast_data, 3600)
        
        # 获取缓存数据
        cached_data = await cache_manager.get_cached_forecast(cache_key)
        
        assert cached_data is not None
        assert cached_data.location == sample_forecast_data.location
        assert len(cached_data.days) == len(sample_forecast_data.days)
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, cache_manager, sample_weather_data):
        """测试缓存过期"""
        cache_key = cache_manager.generate_cache_key("北京", "weather")
        
        # 缓存数据，设置很短的TTL
        await cache_manager.cache_weather_data(cache_key, sample_weather_data, 1)
        
        # 立即获取应该成功
        cached_data = await cache_manager.get_cached_weather(cache_key)
        assert cached_data is not None
        
        # 等待过期
        await asyncio.sleep(2)
        
        # 再次获取应该返回None
        cached_data = await cache_manager.get_cached_weather(cache_key)
        assert cached_data is None
    
    def test_cleanup_expired_cache(self, cache_manager):
        """测试清理过期缓存"""
        # 先获取初始统计
        initial_stats = cache_manager.get_cache_stats()
        
        # 执行清理
        cache_manager.cleanup_expired_cache()
        
        # 清理后统计应该正常
        final_stats = cache_manager.get_cache_stats()
        assert isinstance(final_stats, dict)
        assert 'total_records' in final_stats
    
    def test_cache_stats(self, cache_manager):
        """测试缓存统计"""
        stats = cache_manager.get_cache_stats()
        
        assert isinstance(stats, dict)
        assert 'total_records' in stats
        assert 'expired_records' in stats
        assert 'active_records' in stats
        assert 'type_distribution' in stats
        assert 'access_stats' in stats
    
    def test_cache_health(self, cache_manager):
        """测试缓存健康检查"""
        health = cache_manager.get_cache_health()
        
        assert isinstance(health, dict)
        assert 'health_score' in health
        assert 'health_status' in health
        assert 'recommendations' in health
        assert 0 <= health['health_score'] <= 100
    
    def test_force_cleanup(self, cache_manager):
        """测试强制清理"""
        cleanup_result = cache_manager.force_cleanup()
        
        assert isinstance(cleanup_result, dict)
        assert 'cleanup_time' in cleanup_result
        assert 'records_before' in cleanup_result
        assert 'records_after' in cleanup_result
        assert 'records_cleaned' in cleanup_result
    
    def test_clear_all_cache(self, cache_manager):
        """测试清空所有缓存"""
        # 清空缓存
        cache_manager.clear_all_cache()
        
        # 验证缓存已清空
        stats = cache_manager.get_cache_stats()
        assert stats['total_records'] == 0
    
    def test_auto_cleanup_control(self, cache_manager):
        """测试自动清理控制"""
        # 停止自动清理
        cache_manager.stop_auto_cleanup()
        
        # 重新启动
        cache_manager.start_auto_cleanup()
        
        # 设置清理间隔
        cache_manager.set_cleanup_interval(3600)
        
        # 测试无效间隔
        with pytest.raises(ValueError):
            cache_manager.set_cleanup_interval(30)
    
    def test_cleanup_callback(self, cache_manager):
        """测试清理回调"""
        callback_called = False
        callback_data = None
        
        def cleanup_callback(stats):
            nonlocal callback_called, callback_data
            callback_called = True
            callback_data = stats
        
        cache_manager.set_cleanup_callback(cleanup_callback)
        cache_manager.cleanup_expired_cache()
        
        assert callback_called
        assert callback_data is not None
        assert isinstance(callback_data, dict)
    
    def test_disabled_cache(self, temp_config):
        """测试禁用缓存时的行为"""
        temp_config.cache_enabled = False
        cache_manager = CacheManager(temp_config)
        
        try:
            # 创建测试数据
            weather_data = WeatherData(
                location="北京",
                temperature=25.0,
                feels_like=27.0,
                humidity=60,
                wind_speed=5.0,
                wind_direction=180,
                pressure=1013.25,
                visibility=10.0,
                uv_index=5.0,
                condition="晴天",
                condition_code="clear",
                timestamp=datetime.now(),
                units="metric"
            )
            
            cache_key = cache_manager.generate_cache_key("北京", "weather")
            
            # 缓存操作应该被忽略
            asyncio.run(cache_manager.cache_weather_data(cache_key, weather_data, 600))
            cached_data = asyncio.run(cache_manager.get_cached_weather(cache_key))
            
            assert cached_data is None
            
        finally:
            cache_manager.close()