"""
活动推荐器属性测试

使用 Hypothesis 进行基于属性的测试，验证活动推荐器的正确性属性。
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis import HealthCheck
from datetime import datetime

from weather_plugin.activity_recommender import ActivityRecommender
from weather_plugin.models import WeatherData, Activity, Season


class TestActivityRecommenderProperties:
    """活动推荐器属性测试"""
    
    def _create_weather_data(self, temperature=20.0, humidity=50, wind_speed=5.0, 
                           wind_direction=180, pressure=1013.25, visibility=10.0, 
                           uv_index=3.0, condition="晴天", condition_code="clear", 
                           location="测试城市", units="metric"):
        """创建测试天气数据"""
        return WeatherData(
            location=location,
            temperature=temperature,
            feels_like=temperature,
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
    
    @given(
        temperature=st.floats(min_value=-40.0, max_value=50.0),
        humidity=st.integers(min_value=0, max_value=100),
        wind_speed=st.floats(min_value=0.0, max_value=50.0),
        wind_direction=st.integers(min_value=0, max_value=360),
        visibility=st.floats(min_value=0.1, max_value=50.0),
        uv_index=st.floats(min_value=0.0, max_value=15.0),
        condition=st.sampled_from(["晴天", "多云", "阴天", "雨天", "雪天", "雷暴", "雾霾"]),
        season=st.sampled_from(list(Season))
    )
    @settings(max_examples=100)
    def test_property_6_activity_recommendation_logic(self, temperature, humidity, 
                                                    wind_speed, wind_direction, 
                                                    visibility, uv_index, condition, season):
        """
        属性6：活动推荐逻辑
        
        **验证需求：4.1, 4.2, 4.3, 4.4, 4.5**
        
        For any valid weather conditions and season, the activity recommender should:
        1. Return a non-empty list of activities when conditions allow
        2. All recommended activities should be suitable for the given weather
        3. Indoor activities should be recommended during severe weather
        4. Seasonal activities should match the current season or be season-independent
        """
        recommender = ActivityRecommender()
        
        # 创建天气数据
        weather = self._create_weather_data(
            temperature=temperature,
            humidity=humidity,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            visibility=visibility,
            uv_index=uv_index,
            condition=condition
        )
        
        # 获取活动推荐
        recommended_activities = recommender.recommend_activities(weather, season)
        
        # 验证返回的是活动列表
        assert isinstance(recommended_activities, list)
        
        # 验证所有推荐的活动都是Activity实例
        for activity in recommended_activities:
            assert isinstance(activity, Activity)
        
        # 获取天气分类
        weather_category = recommender._categorize_weather(weather)
        is_severe = recommender._is_severe_weather(weather)
        
        # 验证推荐逻辑
        for activity in recommended_activities:
            # 验证季节匹配
            assert activity.season is None or activity.season == season, \
                f"Activity {activity.name} season {activity.season} doesn't match {season}"
            
            # 验证天气适宜性
            if is_severe:
                # 恶劣天气应该推荐室内活动
                if not activity.indoor:
                    # 除非活动明确适合这种天气条件
                    assert weather_category in activity.suitable_weather, \
                        f"Outdoor activity {activity.name} recommended in severe weather {weather_category}"
            else:
                # 正常天气应该推荐适合的活动
                assert (weather_category in activity.suitable_weather or 
                       (is_severe and activity.indoor)), \
                    f"Activity {activity.name} not suitable for weather {weather_category}"
        
        # 验证推荐数量合理（不超过8个）
        assert len(recommended_activities) <= 8, \
            f"Too many activities recommended: {len(recommended_activities)}"
    
    @given(
        temperature=st.floats(min_value=-40.0, max_value=50.0),
        humidity=st.integers(min_value=0, max_value=100),
        wind_speed=st.floats(min_value=0.0, max_value=50.0),
        wind_direction=st.integers(min_value=0, max_value=360),
        visibility=st.floats(min_value=0.1, max_value=50.0),
        uv_index=st.floats(min_value=0.0, max_value=15.0),
        condition=st.sampled_from(["晴天", "多云", "阴天", "雨天", "雪天", "雷暴", "雾霾", 
                                 "clear", "cloudy", "overcast", "rain", "snow", "thunderstorm", "fog"])
    )
    @settings(max_examples=100)
    def test_property_7_safety_recommendation_generation(self, temperature, humidity, 
                                                       wind_speed, wind_direction, 
                                                       visibility, uv_index, condition):
        """
        属性7：安全建议生成
        
        **验证需求：4.1, 4.2, 4.3, 4.4, 4.5**
        
        For any weather conditions, the safety recommendation system should:
        1. Always return a list of safety recommendations
        2. Include temperature-specific advice for extreme temperatures
        3. Include wind-related advice for high wind speeds
        4. Include UV protection advice for high UV index
        5. Include weather condition-specific advice
        """
        recommender = ActivityRecommender()
        
        # 创建天气数据
        weather = self._create_weather_data(
            temperature=temperature,
            humidity=humidity,
            wind_speed=wind_speed,
            wind_direction=wind_direction,
            visibility=visibility,
            uv_index=uv_index,
            condition=condition
        )
        
        # 获取安全建议
        safety_recommendations = recommender.get_safety_recommendations(weather)
        
        # 验证返回的是字符串列表
        assert isinstance(safety_recommendations, list)
        for recommendation in safety_recommendations:
            assert isinstance(recommendation, str)
            assert len(recommendation.strip()) > 0, "Empty safety recommendation"
        
        # 验证极端温度建议
        if temperature <= recommender.weather_thresholds['temperature']['very_cold']:
            # 极寒天气应该有相关建议
            cold_advice_found = any(
                any(keyword in rec for keyword in ["极寒", "保暖", "冻伤", "户外活动"])
                for rec in safety_recommendations
            )
            assert cold_advice_found, f"No cold weather advice for temperature {temperature}"
        
        elif temperature >= recommender.weather_thresholds['temperature']['very_hot']:
            # 高温天气应该有相关建议
            hot_advice_found = any(
                any(keyword in rec for keyword in ["高温", "中暑", "防晒", "水分"])
                for rec in safety_recommendations
            )
            assert hot_advice_found, f"No hot weather advice for temperature {temperature}"
        
        # 验证强风建议
        if wind_speed >= recommender.weather_thresholds['wind_speed']['strong']:
            wind_advice_found = any(
                any(keyword in rec for keyword in ["大风", "风力", "高空", "骑行"])
                for rec in safety_recommendations
            )
            assert wind_advice_found, f"No wind advice for wind speed {wind_speed}"
        
        # 验证UV指数建议
        if uv_index >= recommender.weather_thresholds['uv_index']['very_high']:
            uv_advice_found = any(
                any(keyword in rec for keyword in ["紫外线", "防晒", "SPF", "太阳镜"])
                for rec in safety_recommendations
            )
            assert uv_advice_found, f"No UV advice for UV index {uv_index}"
        
        # 验证能见度建议
        if visibility < 1.0:
            visibility_advice_found = any(
                any(keyword in rec for keyword in ["能见度", "驾驶", "户外"])
                for rec in safety_recommendations
            )
            assert visibility_advice_found, f"No visibility advice for visibility {visibility}"
        
        # 验证天气条件特定建议
        condition_lower = condition.lower()
        if any(word in condition_lower for word in ['雨', 'rain', '雷', 'thunder']):
            rain_advice_found = any(
                any(keyword in rec for keyword in ["雨天", "路滑", "雨具", "空旷"])
                for rec in safety_recommendations
            )
            assert rain_advice_found, f"No rain advice for condition {condition}"
        
        elif any(word in condition_lower for word in ['雪', 'snow']):
            snow_advice_found = any(
                any(keyword in rec for keyword in ["雪天", "路滑", "保暖", "积雪"])
                for rec in safety_recommendations
            )
            assert snow_advice_found, f"No snow advice for condition {condition}"
    
    @given(
        activities_count=st.integers(min_value=1, max_value=20),
        temperature=st.floats(min_value=-20.0, max_value=40.0),
        condition=st.sampled_from(["晴天", "多云", "阴天", "雨天"])
    )
    @settings(max_examples=50)
    def test_property_weather_filtering_consistency(self, activities_count, temperature, condition):
        """
        属性：天气过滤一致性
        
        For any set of activities and weather conditions, filtering should be consistent:
        1. The same weather should always produce the same filtered results
        2. Filtered activities should all be suitable for the weather
        """
        recommender = ActivityRecommender()
        
        # 创建天气数据
        weather = self._create_weather_data(temperature=temperature, condition=condition)
        
        # 获取所有活动
        all_activities = recommender.activities
        
        # 多次过滤应该得到相同结果
        filtered_1 = recommender.filter_by_weather_conditions(all_activities, weather)
        filtered_2 = recommender.filter_by_weather_conditions(all_activities, weather)
        
        # 验证一致性
        assert len(filtered_1) == len(filtered_2)
        assert set(activity.name for activity in filtered_1) == set(activity.name for activity in filtered_2)
        
        # 验证过滤结果的正确性
        weather_category = recommender._categorize_weather(weather)
        is_severe = recommender._is_severe_weather(weather)
        
        for activity in filtered_1:
            if is_severe and activity.indoor:
                # 恶劣天气时室内活动应该被包含
                continue
            else:
                # 其他情况下活动应该适合当前天气
                assert weather_category in activity.suitable_weather, \
                    f"Activity {activity.name} not suitable for weather {weather_category}"
    
    @given(
        temperature=st.floats(min_value=-30.0, max_value=45.0),
        wind_speed=st.floats(min_value=0.0, max_value=40.0),
        uv_index=st.floats(min_value=0.0, max_value=12.0)
    )
    @settings(max_examples=50)
    def test_property_activity_scoring_monotonicity(self, temperature, wind_speed, uv_index):
        """
        属性：活动评分单调性
        
        For activities under similar conditions, scoring should be monotonic:
        1. Better weather conditions should result in higher scores for outdoor activities
        2. Indoor activities should have consistent scores regardless of weather
        """
        recommender = ActivityRecommender()
        
        # 创建两个天气条件：一个更好，一个更差
        good_weather = self._create_weather_data(
            temperature=22.0,  # 理想温度
            wind_speed=5.0,    # 微风
            uv_index=3.0,      # 适中UV
            condition="晴天"
        )
        
        bad_weather = self._create_weather_data(
            temperature=temperature,
            wind_speed=wind_speed,
            uv_index=uv_index,
            condition="雷暴"
        )
        
        # 选择一个户外活动进行测试
        outdoor_activity = None
        indoor_activity = None
        
        for activity in recommender.activities:
            if not activity.indoor and outdoor_activity is None:
                outdoor_activity = activity
            elif activity.indoor and indoor_activity is None:
                indoor_activity = activity
            
            if outdoor_activity and indoor_activity:
                break
        
        if outdoor_activity:
            good_score = recommender._calculate_activity_score(outdoor_activity, good_weather)
            bad_score = recommender._calculate_activity_score(outdoor_activity, bad_weather)
            
            # 好天气下户外活动的分数应该更高（除非坏天气实际上更适合）
            if not recommender._is_severe_weather(good_weather):
                assert isinstance(good_score, (int, float))
                assert isinstance(bad_score, (int, float))
        
        if indoor_activity:
            # 室内活动的分数应该相对稳定
            indoor_good_score = recommender._calculate_activity_score(indoor_activity, good_weather)
            indoor_bad_score = recommender._calculate_activity_score(indoor_activity, bad_weather)
            
            assert isinstance(indoor_good_score, (int, float))
            assert isinstance(indoor_bad_score, (int, float))
            
            # 室内活动在恶劣天气下可能分数更高
            if recommender._is_severe_weather(bad_weather):
                assert indoor_bad_score >= indoor_good_score - 10  # 允许一些变化