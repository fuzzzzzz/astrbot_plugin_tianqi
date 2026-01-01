"""
数据模型测试
"""

import pytest
import json
from datetime import datetime, date
from weather_plugin.models import (
    WeatherData, ForecastDay, ForecastData, UserPrefs, 
    WeatherCommand, Coordinates, LocationInfo,
    CommandType, AlertType
)


class TestCoordinates:
    """坐标测试"""
    
    def test_valid_coordinates(self):
        """测试有效坐标"""
        coords = Coordinates(39.9042, 116.4074)  # 北京
        assert coords.latitude == 39.9042
        assert coords.longitude == 116.4074
    
    def test_invalid_latitude(self):
        """测试无效纬度"""
        with pytest.raises(ValueError, match="纬度必须在 -90 到 90 之间"):
            Coordinates(91.0, 0.0)
        
        with pytest.raises(ValueError, match="纬度必须在 -90 到 90 之间"):
            Coordinates(-91.0, 0.0)
    
    def test_invalid_longitude(self):
        """测试无效经度"""
        with pytest.raises(ValueError, match="经度必须在 -180 到 180 之间"):
            Coordinates(0.0, 181.0)
        
        with pytest.raises(ValueError, match="经度必须在 -180 到 180 之间"):
            Coordinates(0.0, -181.0)


class TestWeatherData:
    """天气数据测试"""
    
    def test_valid_weather_data(self):
        """测试有效天气数据"""
        weather = WeatherData(
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
        assert weather.location == "北京"
        assert weather.temperature == 25.0
    
    def test_invalid_humidity(self):
        """测试无效湿度"""
        with pytest.raises(ValueError, match="湿度必须在 0-100 之间"):
            WeatherData(
                location="北京", temperature=25.0, feels_like=27.0,
                humidity=101, wind_speed=5.0, wind_direction=180,
                pressure=1013.25, visibility=10.0, uv_index=5.0,
                condition="晴天", condition_code="clear",
                timestamp=datetime.now(), units="metric"
            )
    
    def test_invalid_wind_speed(self):
        """测试无效风速"""
        with pytest.raises(ValueError, match="风速不能为负数"):
            WeatherData(
                location="北京", temperature=25.0, feels_like=27.0,
                humidity=60, wind_speed=-1.0, wind_direction=180,
                pressure=1013.25, visibility=10.0, uv_index=5.0,
                condition="晴天", condition_code="clear",
                timestamp=datetime.now(), units="metric"
            )
    
    def test_serialization(self):
        """测试序列化和反序列化"""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        weather = WeatherData(
            location="北京", temperature=25.0, feels_like=27.0,
            humidity=60, wind_speed=5.0, wind_direction=180,
            pressure=1013.25, visibility=10.0, uv_index=5.0,
            condition="晴天", condition_code="clear",
            timestamp=timestamp, units="metric"
        )
        
        # 测试 to_dict
        data_dict = weather.to_dict()
        assert data_dict['location'] == "北京"
        assert data_dict['timestamp'] == timestamp.isoformat()
        
        # 测试 from_dict
        restored_weather = WeatherData.from_dict(data_dict)
        assert restored_weather.location == weather.location
        assert restored_weather.timestamp == weather.timestamp
        
        # 测试 to_json
        json_str = weather.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json['location'] == "北京"


class TestForecastDay:
    """预报日测试"""
    
    def test_valid_forecast_day(self):
        """测试有效预报日"""
        forecast_day = ForecastDay(
            date=date.today(),
            high_temp=30.0,
            low_temp=20.0,
            condition="晴天",
            precipitation_chance=10,
            wind_speed=5.0,
            humidity=60
        )
        assert forecast_day.high_temp == 30.0
        assert forecast_day.low_temp == 20.0
    
    def test_invalid_temperature_range(self):
        """测试无效温度范围"""
        with pytest.raises(ValueError, match="最高温度不能低于最低温度"):
            ForecastDay(
                date=date.today(),
                high_temp=15.0,
                low_temp=20.0,
                condition="晴天",
                precipitation_chance=10,
                wind_speed=5.0,
                humidity=60
            )
    
    def test_serialization(self):
        """测试序列化和反序列化"""
        test_date = date(2024, 1, 1)
        forecast_day = ForecastDay(
            date=test_date,
            high_temp=30.0,
            low_temp=20.0,
            condition="晴天",
            precipitation_chance=10,
            wind_speed=5.0,
            humidity=60
        )
        
        # 测试 to_dict
        data_dict = forecast_day.to_dict()
        assert data_dict['date'] == test_date.isoformat()
        assert data_dict['high_temp'] == 30.0
        
        # 测试 from_dict
        restored_day = ForecastDay.from_dict(data_dict)
        assert restored_day.date == forecast_day.date
        assert restored_day.high_temp == forecast_day.high_temp


class TestUserPrefs:
    """用户偏好测试"""
    
    def test_default_user_prefs(self):
        """测试默认用户偏好"""
        prefs = UserPrefs(user_id="test_user")
        assert prefs.user_id == "test_user"
        assert prefs.units == "metric"
        assert prefs.language == "zh"
        assert prefs.alert_subscriptions == []
        assert prefs.created_at is not None
    
    def test_invalid_units(self):
        """测试无效单位"""
        with pytest.raises(ValueError, match="单位必须是 'metric' 或 'imperial'"):
            UserPrefs(user_id="test_user", units="invalid")
    
    def test_custom_user_prefs(self):
        """测试自定义用户偏好"""
        prefs = UserPrefs(
            user_id="test_user",
            default_location="北京",
            units="imperial",
            alert_subscriptions=[AlertType.SEVERE_WEATHER],
            language="en"
        )
        assert prefs.default_location == "北京"
        assert prefs.units == "imperial"
        assert AlertType.SEVERE_WEATHER in prefs.alert_subscriptions
    
    def test_serialization(self):
        """测试序列化和反序列化"""
        prefs = UserPrefs(
            user_id="test_user",
            default_location="北京",
            units="imperial",
            alert_subscriptions=[AlertType.SEVERE_WEATHER],
            language="en"
        )
        
        # 测试 to_dict
        data_dict = prefs.to_dict()
        assert data_dict['user_id'] == "test_user"
        assert data_dict['alert_subscriptions'] == ['severe']
        
        # 测试 from_dict
        restored_prefs = UserPrefs.from_dict(data_dict)
        assert restored_prefs.user_id == prefs.user_id
        assert restored_prefs.alert_subscriptions == prefs.alert_subscriptions
        
        # 测试 to_json
        json_str = prefs.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json['user_id'] == "test_user"
    
    def test_preference_updates(self):
        """测试偏好更新方法"""
        import time
        prefs = UserPrefs(user_id="test_user")
        original_updated_at = prefs.updated_at
        
        # 添加小延迟确保时间戳不同
        time.sleep(0.001)
        
        # 测试位置更新
        prefs.update_location("上海")
        assert prefs.default_location == "上海"
        assert prefs.updated_at >= original_updated_at
        
        # 测试单位更新
        prefs.update_units("imperial")
        assert prefs.units == "imperial"
        
        # 测试警报订阅
        prefs.add_alert_subscription(AlertType.SEVERE_WEATHER)
        assert AlertType.SEVERE_WEATHER in prefs.alert_subscriptions
        
        prefs.remove_alert_subscription(AlertType.SEVERE_WEATHER)
        assert AlertType.SEVERE_WEATHER not in prefs.alert_subscriptions


class TestWeatherCommand:
    """天气命令测试"""
    
    def test_basic_weather_command(self):
        """测试基本天气命令"""
        command = WeatherCommand(
            command_type=CommandType.CURRENT_WEATHER,
            location="北京"
        )
        assert command.command_type == CommandType.CURRENT_WEATHER
        assert command.location == "北京"
        assert command.additional_params == {}
    
    def test_command_with_params(self):
        """测试带参数的命令"""
        command = WeatherCommand(
            command_type=CommandType.FORECAST,
            location="上海",
            time_period="7天",
            additional_params={"days": 7}
        )
        assert command.additional_params["days"] == 7


class TestForecastData:
    """预报数据测试"""
    
    def test_serialization(self):
        """测试预报数据序列化和反序列化"""
        test_date = date(2024, 1, 1)
        generated_at = datetime(2024, 1, 1, 12, 0, 0)
        
        forecast_day = ForecastDay(
            date=test_date,
            high_temp=30.0,
            low_temp=20.0,
            condition="晴天",
            precipitation_chance=10,
            wind_speed=5.0,
            humidity=60
        )
        
        forecast_data = ForecastData(
            location="北京",
            days=[forecast_day],
            units="metric",
            generated_at=generated_at
        )
        
        # 测试 to_dict
        data_dict = forecast_data.to_dict()
        assert data_dict['location'] == "北京"
        assert len(data_dict['days']) == 1
        assert data_dict['generated_at'] == generated_at.isoformat()
        
        # 测试 from_dict
        restored_forecast = ForecastData.from_dict(data_dict)
        assert restored_forecast.location == forecast_data.location
        assert len(restored_forecast.days) == 1
        assert restored_forecast.generated_at == forecast_data.generated_at
        
        # 测试 to_json
        json_str = forecast_data.to_json()
        parsed_json = json.loads(json_str)
        assert parsed_json['location'] == "北京"