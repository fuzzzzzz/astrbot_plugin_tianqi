"""
警报管理器属性测试

使用 Hypothesis 进行基于属性的测试，验证警报管理器的正确性属性。
"""

import pytest
import tempfile
import os
import asyncio
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from hypothesis import HealthCheck
from datetime import datetime, timedelta

from weather_plugin.alert_manager import AlertManager
from weather_plugin.models import (
    WeatherAlert, AlertType, UserPrefs, WeatherData,
    WeatherError, ConfigurationError
)


class TestAlertManagerProperties:
    """警报管理器属性测试"""
    
    def _create_temp_manager(self):
        """创建临时警报管理器"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        manager = AlertManager(db_path)
        return manager, db_path
    
    def _cleanup_temp_db(self, db_path):
        """清理临时数据库"""
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except PermissionError:
            # Windows上SQLite文件可能被锁定，忽略删除错误
            pass
    
    def _create_test_weather_alert(self, alert_type: AlertType, location: str) -> WeatherAlert:
        """创建测试用的天气警报"""
        return WeatherAlert(
            alert_type=alert_type,
            title=f"Test {alert_type.value} Alert",
            description=f"Test alert for {location}",
            severity="medium",
            location=location,
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            advice=["Stay safe", "Monitor conditions"]
        )
    
    def _create_test_user_prefs(self, user_id: str, alert_subscriptions: list) -> UserPrefs:
        """创建测试用的用户偏好"""
        return UserPrefs(
            user_id=user_id,
            default_location="Test Location",
            units="metric",
            alert_subscriptions=alert_subscriptions,
            language="zh"
        )
    
    def _create_test_weather_data(self, **kwargs) -> WeatherData:
        """创建测试用的天气数据"""
        defaults = {
            'location': 'Test Location',
            'temperature': 20.0,
            'feels_like': 22.0,
            'humidity': 60,
            'wind_speed': 5.0,
            'wind_direction': 180,
            'pressure': 1013.25,
            'visibility': 10.0,
            'uv_index': 5.0,
            'condition': 'clear',
            'condition_code': '800',
            'timestamp': datetime.now(),
            'units': 'metric'
        }
        defaults.update(kwargs)
        return WeatherData(**defaults)
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        alert_types_list=st.lists(
            st.sampled_from(list(AlertType)), 
            min_size=0, 
            max_size=len(AlertType), 
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_property_8_alert_system_integrity(self, user_id, alert_types_list):
        """
        属性8：警报系统完整性
        
        **验证需求：5.1, 5.2, 5.3, 5.4, 5.5**
        
        For any user and list of alert types, subscribing to those alert types
        and then retrieving subscriptions should return exactly those types.
        The alert history should accurately record all sent alerts.
        """
        alert_manager, db_path = self._create_temp_manager()
        
        try:
            # 订阅警报类型
            alert_manager.subscribe_user(user_id, alert_types_list)
            
            # 验证订阅一致性
            retrieved_subscriptions = alert_manager.get_user_subscriptions(user_id)
            assert set(retrieved_subscriptions) == set(alert_types_list)
            assert len(retrieved_subscriptions) == len(alert_types_list)
            
            # 测试警报发送和历史记录
            initial_history = alert_manager.get_alert_history(user_id)
            initial_count = len(initial_history)
            
            # 为每个订阅的警报类型创建并发送警报
            sent_alerts = []
            for alert_type in alert_types_list:
                alert = self._create_test_weather_alert(alert_type, f"Location_{alert_type.value}")
                
                # 使用asyncio运行异步方法
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(alert_manager.send_alert(user_id, alert))
                finally:
                    loop.close()
                
                sent_alerts.append(alert)
            
            # 验证警报历史记录完整性
            final_history = alert_manager.get_alert_history(user_id)
            assert len(final_history) == initial_count + len(alert_types_list)
            
            # 验证每个发送的警报都在历史记录中
            history_alert_types = [record['alert_type'] for record in final_history[-len(alert_types_list):]]
            expected_alert_types = [alert.alert_type.value for alert in sent_alerts]
            assert set(history_alert_types) == set(expected_alert_types)
            
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        initial_alert_types=st.lists(
            st.sampled_from(list(AlertType)), 
            min_size=0, 
            max_size=len(AlertType), 
            unique=True
        ),
        new_alert_types=st.lists(
            st.sampled_from(list(AlertType)), 
            min_size=0, 
            max_size=len(AlertType), 
            unique=True
        )
    )
    @settings(max_examples=100)
    def test_property_9_subscription_management(self, user_id, initial_alert_types, new_alert_types):
        """
        属性9：订阅管理
        
        **验证需求：5.1, 5.2, 5.3, 5.4, 5.5**
        
        For any user, updating alert subscriptions should completely replace
        the previous subscriptions with the new ones. Multiple subscription
        updates should be idempotent and maintain consistency.
        """
        alert_manager, db_path = self._create_temp_manager()
        
        try:
            # 设置初始订阅
            alert_manager.subscribe_user(user_id, initial_alert_types)
            
            # 验证初始订阅
            initial_subscriptions = alert_manager.get_user_subscriptions(user_id)
            assert set(initial_subscriptions) == set(initial_alert_types)
            
            # 更新订阅
            alert_manager.subscribe_user(user_id, new_alert_types)
            
            # 验证订阅已完全替换
            updated_subscriptions = alert_manager.get_user_subscriptions(user_id)
            assert set(updated_subscriptions) == set(new_alert_types)
            assert len(updated_subscriptions) == len(new_alert_types)
            
            # 验证旧订阅不再存在（除非也在新订阅中）
            old_only_types = set(initial_alert_types) - set(new_alert_types)
            for old_type in old_only_types:
                assert old_type not in updated_subscriptions
            
            # 测试幂等性：重复相同的订阅操作
            alert_manager.subscribe_user(user_id, new_alert_types)
            repeated_subscriptions = alert_manager.get_user_subscriptions(user_id)
            
            # 验证结果保持一致
            assert set(repeated_subscriptions) == set(new_alert_types)
            assert len(repeated_subscriptions) == len(new_alert_types)
            
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        alert_type=st.sampled_from(list(AlertType)),
        location=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        subscribed_types=st.lists(
            st.sampled_from(list(AlertType)), 
            min_size=1, 
            max_size=len(AlertType), 
            unique=True
        ),
        severity=st.sampled_from(['low', 'medium', 'high', '低', '中', '高'])
    )
    @settings(max_examples=100)
    def test_property_alert_filtering_logic(self, alert_type, location, subscribed_types, severity):
        """
        属性：警报过滤逻辑
        
        For any alert and user preferences, the should_send_alert method
        should correctly determine whether to send the alert based on
        subscription status and severity level.
        """
        alert_manager, db_path = self._create_temp_manager()
        
        try:
            # 创建测试警报
            alert = WeatherAlert(
                alert_type=alert_type,
                title="Test Alert",
                description="Test Description",
                severity=severity,
                location=location,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1)
            )
            
            # 创建用户偏好
            user_prefs = self._create_test_user_prefs("test_user", subscribed_types)
            
            # 测试过滤逻辑
            should_send = alert_manager.should_send_alert(alert, user_prefs)
            
            # 验证过滤逻辑
            is_subscribed = alert_type in subscribed_types
            is_not_low_severity = severity.lower() not in ['low', '低']
            is_not_expired = alert.end_time is None or alert.end_time >= datetime.now()
            
            expected_should_send = is_subscribed and is_not_low_severity and is_not_expired
            assert should_send == expected_should_send
            
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        location=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        alert_type=st.sampled_from(list(AlertType))
    )
    @settings(max_examples=50)
    def test_property_alert_suppression(self, user_id, location, alert_type):
        """
        属性：警报抑制
        
        For any user, location, and alert type, sending the same type of alert
        multiple times within a short period should be suppressed to prevent spam.
        """
        alert_manager, db_path = self._create_temp_manager()
        
        try:
            # 创建测试警报
            alert = self._create_test_weather_alert(alert_type, location)
            
            # 第一次发送警报
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(alert_manager.send_alert(user_id, alert))
                
                # 立即再次发送相同类型的警报
                # 由于抑制机制，第二次发送应该被跳过
                initial_history_count = len(alert_manager.get_alert_history(user_id))
                
                # 创建另一个相同类型的警报
                second_alert = self._create_test_weather_alert(alert_type, location)
                loop.run_until_complete(alert_manager.send_alert(user_id, second_alert))
                
                # 验证历史记录没有增加（被抑制了）
                final_history_count = len(alert_manager.get_alert_history(user_id))
                
                # 由于抑制机制，历史记录应该只增加1（第一次发送）
                assert final_history_count == initial_history_count
                
            finally:
                loop.close()
            
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        location=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        temperature=st.floats(min_value=-50.0, max_value=60.0),
        wind_speed=st.floats(min_value=0.0, max_value=50.0),
        uv_index=st.floats(min_value=0.0, max_value=15.0),
        visibility=st.floats(min_value=0.0, max_value=50.0)
    )
    @settings(max_examples=100)
    def test_property_weather_alert_creation(self, location, temperature, wind_speed, uv_index, visibility):
        """
        属性：天气警报创建
        
        For any weather conditions, creating alerts should follow consistent
        threshold rules and produce valid alert objects when thresholds are exceeded.
        """
        alert_manager, db_path = self._create_temp_manager()
        
        try:
            # 创建天气数据
            weather_data = self._create_test_weather_data(
                location=location,
                temperature=temperature,
                wind_speed=wind_speed,
                uv_index=uv_index,
                visibility=visibility
            )
            
            # 测试不同类型的警报创建
            alert_types_to_test = [
                AlertType.SEVERE_WEATHER,
                AlertType.TEMPERATURE_CHANGE,
                AlertType.WIND,
                AlertType.UV_INDEX
            ]
            
            for alert_type in alert_types_to_test:
                alert = alert_manager.create_weather_alert(alert_type, location, weather_data)
                
                # 验证警报创建逻辑
                if alert is not None:
                    # 如果创建了警报，验证其有效性
                    assert alert.alert_type == alert_type
                    assert alert.location == location
                    assert alert.title is not None and len(alert.title) > 0
                    assert alert.description is not None and len(alert.description) > 0
                    assert alert.severity in ['low', 'medium', 'high', '低', '中', '高']
                    assert alert.start_time is not None
                    assert isinstance(alert.advice, list)
                    
                    # 验证警报是基于实际阈值创建的
                    thresholds = alert_manager.alert_thresholds[alert_type]
                    
                    if alert_type == AlertType.SEVERE_WEATHER:
                        # 恶劣天气警报应该基于风速或能见度阈值
                        wind_threshold_exceeded = wind_speed >= thresholds['wind_speed_ms']
                        visibility_threshold_exceeded = visibility <= thresholds['visibility_km']
                        assert wind_threshold_exceeded or visibility_threshold_exceeded
                    
                    elif alert_type == AlertType.TEMPERATURE_CHANGE:
                        # 温度警报应该基于极端温度阈值
                        high_temp_exceeded = temperature >= thresholds['extreme_high_celsius']
                        low_temp_exceeded = temperature <= thresholds['extreme_low_celsius']
                        assert high_temp_exceeded or low_temp_exceeded
                    
                    elif alert_type == AlertType.WIND:
                        # 风力警报应该基于风速阈值
                        assert wind_speed >= thresholds['strong_wind_ms']
                    
                    elif alert_type == AlertType.UV_INDEX:
                        # 紫外线警报应该基于UV指数阈值
                        assert uv_index >= thresholds['high_uv']
            
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        days_to_keep=st.integers(min_value=1, max_value=365)
    )
    @settings(max_examples=50)
    def test_property_alert_cleanup(self, days_to_keep):
        """
        属性：警报清理
        
        For any cleanup period, the cleanup operation should remove only
        records older than the specified number of days while preserving
        recent records.
        """
        alert_manager, db_path = self._create_temp_manager()
        
        try:
            user_id = "test_user"
            location = "test_location"
            
            # 创建一些旧的和新的警报记录
            old_alert = self._create_test_weather_alert(AlertType.SEVERE_WEATHER, location)
            recent_alert = self._create_test_weather_alert(AlertType.TEMPERATURE_CHANGE, location)
            
            # 发送警报以创建历史记录
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(alert_manager.send_alert(user_id, old_alert))
                loop.run_until_complete(alert_manager.send_alert(user_id, recent_alert))
            finally:
                loop.close()
            
            # 获取清理前的记录数
            initial_history = alert_manager.get_alert_history(user_id)
            initial_count = len(initial_history)
            
            # 执行清理操作
            alert_manager.cleanup_old_alerts(days_to_keep)
            
            # 获取清理后的记录数
            final_history = alert_manager.get_alert_history(user_id)
            final_count = len(final_history)
            
            # 验证清理操作的一致性
            # 由于我们刚刚创建的记录都是最近的，它们不应该被清理
            # 除非days_to_keep非常小（接近0）
            if days_to_keep >= 1:
                assert final_count == initial_count
            else:
                # 如果保留天数很小，可能会清理一些记录
                assert final_count <= initial_count
            
        finally:
            self._cleanup_temp_db(db_path)