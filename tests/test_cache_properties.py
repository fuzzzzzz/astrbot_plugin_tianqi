"""
缓存系统属性测试

使用 Hypothesis 进行基于属性的测试，验证缓存系统的正确性属性。
"""

import pytest
import tempfile
import os
import asyncio
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from hypothesis import HealthCheck
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from weather_plugin.cache import CacheManager
from weather_plugin.config import WeatherConfig
from weather_plugin.models import WeatherData, ForecastData, ForecastDay, CacheError


class TestCacheManagerProperties:
    """缓存管理器属性测试"""
    
    def _create_temp_cache_manager(self):
        """创建临时缓存管理器"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        config = WeatherConfig(
            api_key="test_key",
            cache_enabled=True,
            cache_db_path=db_path,
            cache_ttl_current=600,
            cache_ttl_forecast=3600
        )
        
        manager = CacheManager(config)
        return manager, db_path
    
    def _cleanup_temp_db(self, db_path):
        """清理临时数据库"""
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except (PermissionError, OSError):
            # Windows上SQLite文件可能被锁定，忽略删除错误
            pass
    
    @st.composite
    def valid_weather_data_strategy(draw):
        """生成有效的天气数据"""
        location = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
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
    def valid_forecast_data_strategy(draw):
        """生成有效的预报数据"""
        location = draw(st.text(min_size=1, max_size=50).filter(lambda x: x.strip()))
        units = draw(st.sampled_from(["metric", "imperial"]))
        
        # 生成1-7天的预报数据
        num_days = draw(st.integers(min_value=1, max_value=7))
        days = []
        
        for i in range(num_days):
            forecast_date = datetime.now().date() + timedelta(days=i)
            low_temp = draw(st.floats(min_value=-50.0, max_value=40.0))
            high_temp = draw(st.floats(min_value=low_temp, max_value=50.0))
            condition = draw(st.text(min_size=1, max_size=100))
            precipitation_chance = draw(st.integers(min_value=0, max_value=100))
            wind_speed = draw(st.floats(min_value=0.0, max_value=200.0))
            humidity = draw(st.integers(min_value=0, max_value=100))
            
            days.append(ForecastDay(
                date=forecast_date,
                high_temp=high_temp,
                low_temp=low_temp,
                condition=condition,
                precipitation_chance=precipitation_chance,
                wind_speed=wind_speed,
                humidity=humidity
            ))
        
        return ForecastData(
            location=location,
            days=days,
            units=units,
            generated_at=datetime.now()
        )
    
    @given(
        location=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        data_type=st.sampled_from(['weather', 'forecast', 'hourly']),
        units=st.sampled_from(['metric', 'imperial'])
    )
    @settings(max_examples=100)
    def test_property_12_cache_priority_strategy(self, location, data_type, units):
        """
        属性12：缓存优先策略
        
        **验证需求：7.1, 7.2**
        
        For any location and data type, the cache key generation should be 
        deterministic and consistent, enabling proper cache priority strategy.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            # 生成缓存键应该是确定性的
            key1 = cache_manager.generate_cache_key(location, data_type, units=units)
            key2 = cache_manager.generate_cache_key(location, data_type, units=units)
            
            # 相同参数应该生成相同的缓存键
            assert key1 == key2, "相同参数应该生成相同的缓存键"
            
            # 缓存键应该包含所有重要信息
            assert "weather_cache:" in key1, "缓存键应该包含前缀"
            
            # 不同参数应该生成不同的缓存键
            different_key = cache_manager.generate_cache_key(
                location + "_different", data_type, units=units
            )
            assert key1 != different_key, "不同参数应该生成不同的缓存键"
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    @given(valid_weather_data_strategy())
    @settings(max_examples=50)
    def test_property_cache_weather_roundtrip(self, weather_data):
        """
        属性：天气数据缓存往返一致性
        
        **验证需求：7.1, 7.2**
        
        For any valid weather data, caching it and then retrieving it should 
        return equivalent data.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            async def run_test():
                # 生成缓存键
                cache_key = cache_manager.generate_cache_key(
                    weather_data.location, 'weather', units=weather_data.units
                )
                
                # 缓存数据
                await cache_manager.cache_weather_data(cache_key, weather_data, 600)
                
                # 获取缓存数据
                cached_data = await cache_manager.get_cached_weather(cache_key)
                
                # 验证数据一致性
                assert cached_data is not None, "应该能够获取缓存的数据"
                assert cached_data.location == weather_data.location
                assert cached_data.temperature == weather_data.temperature
                assert cached_data.feels_like == weather_data.feels_like
                assert cached_data.humidity == weather_data.humidity
                assert cached_data.wind_speed == weather_data.wind_speed
                assert cached_data.wind_direction == weather_data.wind_direction
                assert cached_data.pressure == weather_data.pressure
                assert cached_data.visibility == weather_data.visibility
                assert cached_data.uv_index == weather_data.uv_index
                assert cached_data.condition == weather_data.condition
                assert cached_data.condition_code == weather_data.condition_code
                assert cached_data.units == weather_data.units
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    @given(valid_forecast_data_strategy())
    @settings(max_examples=50)
    def test_property_cache_forecast_roundtrip(self, forecast_data):
        """
        属性：预报数据缓存往返一致性
        
        **验证需求：7.1, 7.2**
        
        For any valid forecast data, caching it and then retrieving it should 
        return equivalent data.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            async def run_test():
                # 生成缓存键
                cache_key = cache_manager.generate_cache_key(
                    forecast_data.location, 'forecast', 
                    days=len(forecast_data.days), units=forecast_data.units
                )
                
                # 缓存数据
                await cache_manager.cache_forecast_data(cache_key, forecast_data, 3600)
                
                # 获取缓存数据
                cached_data = await cache_manager.get_cached_forecast(cache_key)
                
                # 验证数据一致性
                assert cached_data is not None, "应该能够获取缓存的预报数据"
                assert cached_data.location == forecast_data.location
                assert cached_data.units == forecast_data.units
                assert len(cached_data.days) == len(forecast_data.days)
                
                # 验证每日数据
                for original_day, cached_day in zip(forecast_data.days, cached_data.days):
                    assert cached_day.date == original_day.date
                    assert cached_day.high_temp == original_day.high_temp
                    assert cached_day.low_temp == original_day.low_temp
                    assert cached_day.condition == original_day.condition
                    assert cached_day.precipitation_chance == original_day.precipitation_chance
                    assert cached_day.wind_speed == original_day.wind_speed
                    assert cached_day.humidity == original_day.humidity
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    @given(
        weather_data=valid_weather_data_strategy(),
        ttl=st.integers(min_value=1, max_value=3)  # 很短的TTL用于测试
    )
    @settings(max_examples=10, deadline=5000)  # 增加deadline并减少测试数量
    def test_property_cache_expiration_behavior(self, weather_data, ttl):
        """
        属性：缓存过期行为
        
        **验证需求：7.1, 7.2**
        
        For any cached data with TTL, the data should be available before expiration 
        and unavailable after expiration.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            async def run_test():
                # 生成缓存键
                cache_key = cache_manager.generate_cache_key(
                    weather_data.location, 'weather', units=weather_data.units
                )
                
                # 缓存数据
                await cache_manager.cache_weather_data(cache_key, weather_data, ttl)
                
                # 立即获取应该成功
                cached_data = await cache_manager.get_cached_weather(cache_key)
                assert cached_data is not None, "刚缓存的数据应该立即可用"
                
                # 等待过期（稍微多等一点确保过期）
                await asyncio.sleep(ttl + 0.5)
                
                # 过期后获取应该返回None
                expired_data = await cache_manager.get_cached_weather(cache_key)
                assert expired_data is None, "过期的数据应该不可用"
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    @given(
        locations=st.lists(
            st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
            min_size=2, max_size=5, unique=True
        ),
        data_type=st.sampled_from(['weather', 'forecast']),
        units=st.sampled_from(['metric', 'imperial'])
    )
    @settings(max_examples=50)
    def test_property_cache_isolation(self, locations, data_type, units):
        """
        属性：缓存隔离性
        
        **验证需求：7.1, 7.2**
        
        For any set of different locations, cached data for one location should 
        not interfere with cached data for other locations.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            async def run_test():
                cache_keys = []
                weather_data_list = []
                
                # 为每个位置创建不同的天气数据并缓存
                for i, location in enumerate(locations):
                    weather_data = WeatherData(
                        location=location,
                        temperature=20.0 + i,  # 不同的温度
                        feels_like=22.0 + i,
                        humidity=60 + i,
                        wind_speed=5.0 + i,
                        wind_direction=180,
                        pressure=1013.25,
                        visibility=10.0,
                        uv_index=5.0,
                        condition=f"条件_{i}",
                        condition_code=f"code_{i}",
                        timestamp=datetime.now(),
                        units=units
                    )
                    
                    cache_key = cache_manager.generate_cache_key(location, data_type, units=units)
                    await cache_manager.cache_weather_data(cache_key, weather_data, 600)
                    
                    cache_keys.append(cache_key)
                    weather_data_list.append(weather_data)
                
                # 验证每个位置的数据都是独立的
                for i, (cache_key, original_data) in enumerate(zip(cache_keys, weather_data_list)):
                    cached_data = await cache_manager.get_cached_weather(cache_key)
                    
                    assert cached_data is not None, f"位置 {locations[i]} 的数据应该存在"
                    assert cached_data.location == original_data.location
                    assert cached_data.temperature == original_data.temperature
                    assert cached_data.condition == original_data.condition
                    
                    # 验证与其他位置的数据不同
                    for j, other_data in enumerate(weather_data_list):
                        if i != j:
                            assert cached_data.temperature != other_data.temperature, \
                                f"位置 {locations[i]} 和 {locations[j]} 的数据应该不同"
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    @given(
        location=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        data_type=st.sampled_from(['weather', 'forecast']),
        units=st.sampled_from(['metric', 'imperial']),
        update_count=st.integers(min_value=2, max_value=5)
    )
    @settings(max_examples=30)
    def test_property_cache_update_consistency(self, location, data_type, units, update_count):
        """
        属性：缓存更新一致性
        
        **验证需求：7.1, 7.2**
        
        For any cache key, multiple updates should result in the latest data 
        being retrievable.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            async def run_test():
                cache_key = cache_manager.generate_cache_key(location, data_type, units=units)
                
                # 多次更新缓存
                for i in range(update_count):
                    weather_data = WeatherData(
                        location=location,
                        temperature=20.0 + i,  # 递增的温度
                        feels_like=22.0 + i,
                        humidity=60,
                        wind_speed=5.0,
                        wind_direction=180,
                        pressure=1013.25,
                        visibility=10.0,
                        uv_index=5.0,
                        condition=f"更新_{i}",
                        condition_code=f"code_{i}",
                        timestamp=datetime.now(),
                        units=units
                    )
                    
                    await cache_manager.cache_weather_data(cache_key, weather_data, 600)
                
                # 获取最终数据
                final_data = await cache_manager.get_cached_weather(cache_key)
                
                # 应该是最后一次更新的数据
                assert final_data is not None, "应该能获取到最新的缓存数据"
                assert final_data.temperature == 20.0 + (update_count - 1), "应该是最新的温度值"
                assert final_data.condition == f"更新_{update_count - 1}", "应该是最新的条件"
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    @given(
        location=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        units=st.sampled_from(['metric', 'imperial'])
    )
    @settings(max_examples=50)
    def test_property_cache_miss_behavior(self, location, units):
        """
        属性：缓存未命中行为
        
        **验证需求：7.1, 7.2**
        
        For any cache key that has not been cached, retrieval should return None 
        without raising exceptions.
        """
        cache_manager, db_path = self._create_temp_cache_manager()
        
        try:
            async def run_test():
                # 生成一个未使用的缓存键
                cache_key = cache_manager.generate_cache_key(location, 'weather', units=units)
                
                # 尝试获取不存在的缓存数据
                cached_data = await cache_manager.get_cached_weather(cache_key)
                
                # 应该返回None而不是抛出异常
                assert cached_data is None, "不存在的缓存数据应该返回None"
                
                # 对预报数据也进行相同测试
                forecast_cache_key = cache_manager.generate_cache_key(location, 'forecast', units=units)
                cached_forecast = await cache_manager.get_cached_forecast(forecast_cache_key)
                
                assert cached_forecast is None, "不存在的预报缓存数据应该返回None"
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)
    
    def test_property_disabled_cache_behavior(self):
        """
        属性：禁用缓存行为
        
        **验证需求：7.1, 7.2**
        
        When caching is disabled, all cache operations should be no-ops and 
        retrieval should always return None.
        """
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # 创建禁用缓存的配置
        config = WeatherConfig(
            api_key="test_key",
            cache_enabled=False,  # 禁用缓存
            cache_db_path=db_path,
            cache_ttl_current=600,
            cache_ttl_forecast=3600
        )
        
        cache_manager = CacheManager(config)
        
        try:
            async def run_test():
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
                
                cache_key = cache_manager.generate_cache_key("北京", "weather", units="metric")
                
                # 尝试缓存数据（应该被忽略）
                await cache_manager.cache_weather_data(cache_key, weather_data, 600)
                
                # 尝试获取数据（应该返回None）
                cached_data = await cache_manager.get_cached_weather(cache_key)
                
                assert cached_data is None, "禁用缓存时应该总是返回None"
            
            asyncio.run(run_test())
            
        finally:
            cache_manager.close()
            self._cleanup_temp_db(db_path)