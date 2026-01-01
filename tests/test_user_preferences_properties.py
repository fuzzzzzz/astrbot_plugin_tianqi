"""
用户偏好管理属性测试

使用 Hypothesis 进行基于属性的测试，验证用户偏好管理的正确性属性。
"""

import pytest
import tempfile
import os
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings
from hypothesis import HealthCheck
from datetime import datetime

from weather_plugin.user_preferences import UserPreferences
from weather_plugin.models import UserPrefs, AlertType


class TestUserPreferencesProperties:
    """用户偏好管理属性测试"""
    
    def _create_temp_manager(self):
        """创建临时用户偏好管理器"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        manager = UserPreferences(db_path)
        return manager, db_path
    
    def _cleanup_temp_db(self, db_path):
        """清理临时数据库"""
        try:
            if os.path.exists(db_path):
                os.unlink(db_path)
        except PermissionError:
            # Windows上SQLite文件可能被锁定，忽略删除错误
            pass
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        location=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        units=st.sampled_from(['metric', 'imperial']),
        language=st.sampled_from(['zh', 'en'])
    )
    @settings(max_examples=100)
    def test_property_4_user_preference_persistence(self, user_id, location, units, language):
        """
        属性4：用户偏好持久化
        
        **验证需求：3.1, 3.2, 3.3, 3.4, 3.5**
        
        For any valid user preferences, storing them and then retrieving them 
        should return equivalent preferences.
        """
        user_prefs_manager, db_path = self._create_temp_manager()
        
        try:
            # 设置用户偏好
            user_prefs_manager.set_default_location(user_id, location)
            user_prefs_manager.set_units(user_id, units)
            user_prefs_manager.set_language(user_id, language)
            
            # 添加一些警报订阅
            alert_types = [AlertType.SEVERE_WEATHER, AlertType.TEMPERATURE_CHANGE]
            user_prefs_manager.update_alert_subscriptions(user_id, alert_types)
            
            # 获取偏好
            retrieved_prefs = user_prefs_manager.get_user_preferences(user_id)
            
            # 验证持久化
            assert retrieved_prefs.user_id == user_id
            assert retrieved_prefs.default_location == location
            assert retrieved_prefs.units == units
            assert retrieved_prefs.language == language
            assert set(retrieved_prefs.alert_subscriptions) == set(alert_types)
            
            # 创建新的管理器实例（模拟重启）
            new_manager = UserPreferences(db_path)
            persisted_prefs = new_manager.get_user_preferences(user_id)
            
            # 验证数据在重启后仍然存在
            assert persisted_prefs.user_id == retrieved_prefs.user_id
            assert persisted_prefs.default_location == retrieved_prefs.default_location
            assert persisted_prefs.units == retrieved_prefs.units
            assert persisted_prefs.language == retrieved_prefs.language
            assert set(persisted_prefs.alert_subscriptions) == set(retrieved_prefs.alert_subscriptions)
        
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        initial_location=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        new_location=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        initial_units=st.sampled_from(['metric', 'imperial']),
        new_units=st.sampled_from(['metric', 'imperial'])
    )
    @settings(max_examples=100)
    def test_property_5_preference_update_confirmation(self, user_id, 
                                                     initial_location, new_location, 
                                                     initial_units, new_units):
        """
        属性5：偏好更新确认
        
        **验证需求：3.1, 3.2, 3.3, 3.4, 3.5**
        
        For any user preferences, updating a preference should result in the 
        updated value being retrievable and the updated_at timestamp being newer.
        """
        user_prefs_manager, db_path = self._create_temp_manager()
        
        try:
            # 设置初始偏好
            user_prefs_manager.set_default_location(user_id, initial_location)
            user_prefs_manager.set_units(user_id, initial_units)
            
            initial_prefs = user_prefs_manager.get_user_preferences(user_id)
            initial_updated_at = initial_prefs.updated_at
            
            # 等待一小段时间确保时间戳不同
            import time
            time.sleep(0.001)
            
            # 更新位置
            user_prefs_manager.set_default_location(user_id, new_location)
            updated_prefs = user_prefs_manager.get_user_preferences(user_id)
            
            # 验证位置更新
            assert updated_prefs.default_location == new_location
            assert updated_prefs.updated_at >= initial_updated_at
            
            # 更新单位
            user_prefs_manager.set_units(user_id, new_units)
            final_prefs = user_prefs_manager.get_user_preferences(user_id)
            
            # 验证单位更新
            assert final_prefs.units == new_units
            assert final_prefs.updated_at >= updated_prefs.updated_at
            
            # 验证其他字段保持不变
            assert final_prefs.user_id == user_id
            assert final_prefs.default_location == new_location
        
        finally:
            self._cleanup_temp_db(db_path)
    
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
    def test_property_alert_subscription_consistency(self, user_id, alert_types_list):
        """
        属性：警报订阅一致性
        
        For any list of alert types, setting them as subscriptions should result 
        in exactly those alert types being retrievable.
        """
        user_prefs_manager, db_path = self._create_temp_manager()
        
        try:
            # 设置警报订阅
            user_prefs_manager.update_alert_subscriptions(user_id, alert_types_list)
            
            # 获取订阅
            retrieved_subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
            
            # 验证一致性
            assert set(retrieved_subscriptions) == set(alert_types_list)
            assert len(retrieved_subscriptions) == len(alert_types_list)
        
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        alert_type=st.sampled_from(list(AlertType))
    )
    @settings(max_examples=100)
    def test_property_alert_subscription_idempotence(self, user_id, alert_type):
        """
        属性：警报订阅幂等性
        
        For any alert type, adding it multiple times should result in it appearing 
        only once in the subscription list.
        """
        user_prefs_manager, db_path = self._create_temp_manager()
        
        try:
            # 多次添加同一个警报类型
            user_prefs_manager.add_alert_subscription(user_id, alert_type)
            user_prefs_manager.add_alert_subscription(user_id, alert_type)
            user_prefs_manager.add_alert_subscription(user_id, alert_type)
            
            # 获取订阅
            subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
            
            # 验证只出现一次
            assert subscriptions.count(alert_type) == 1
        
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        user_id=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        alert_type=st.sampled_from(list(AlertType))
    )
    @settings(max_examples=100)
    def test_property_alert_subscription_removal(self, user_id, alert_type):
        """
        属性：警报订阅移除
        
        For any alert type, adding it and then removing it should result in 
        it not being in the subscription list.
        """
        user_prefs_manager, db_path = self._create_temp_manager()
        
        try:
            # 添加警报订阅
            user_prefs_manager.add_alert_subscription(user_id, alert_type)
            
            # 验证存在
            subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
            assert alert_type in subscriptions
            
            # 移除订阅
            user_prefs_manager.remove_alert_subscription(user_id, alert_type)
            
            # 验证不存在
            subscriptions = user_prefs_manager.get_alert_subscriptions(user_id)
            assert alert_type not in subscriptions
        
        finally:
            self._cleanup_temp_db(db_path)
    
    @given(
        user_ids=st.lists(
            st.text(min_size=1, max_size=50).filter(lambda x: x.strip()), 
            min_size=1, 
            max_size=10, 
            unique=True
        )
    )
    @settings(max_examples=50, deadline=None)
    def test_property_user_isolation(self, user_ids):
        """
        属性：用户隔离
        
        For any set of users, preferences set for one user should not affect 
        the preferences of other users.
        """
        user_prefs_manager, db_path = self._create_temp_manager()
        
        try:
            # 为每个用户设置不同的偏好
            user_preferences = {}
            for i, user_id in enumerate(user_ids):
                location = f"Location_{i}"
                units = "metric" if i % 2 == 0 else "imperial"
                language = "zh" if i % 2 == 0 else "en"
                
                user_prefs_manager.set_default_location(user_id, location)
                user_prefs_manager.set_units(user_id, units)
                user_prefs_manager.set_language(user_id, language)
                
                user_preferences[user_id] = {
                    'location': location,
                    'units': units,
                    'language': language
                }
            
            # 验证每个用户的偏好都是独立的
            for user_id, expected_prefs in user_preferences.items():
                actual_prefs = user_prefs_manager.get_user_preferences(user_id)
                
                assert actual_prefs.default_location == expected_prefs['location']
                assert actual_prefs.units == expected_prefs['units']
                assert actual_prefs.language == expected_prefs['language']
        
        finally:
            self._cleanup_temp_db(db_path)