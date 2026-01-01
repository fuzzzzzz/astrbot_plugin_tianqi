"""
活动推荐器实现

基于天气条件和季节提供个性化的活动推荐和安全建议。
"""

from typing import List, Dict, Any
from datetime import datetime
import re

from .interfaces import IActivityRecommender
from .models import WeatherData, Activity, Season


class ActivityRecommender(IActivityRecommender):
    """基于天气条件的活动推荐器"""
    
    def __init__(self):
        """初始化活动推荐器"""
        self._init_activity_database()
        self._init_weather_thresholds()
    
    def _init_activity_database(self) -> None:
        """初始化活动数据库"""
        self.activities = [
            # 户外运动活动
            Activity(
                name="跑步",
                description="户外慢跑或快跑锻炼",
                category="运动",
                suitable_weather=["晴天", "多云", "阴天"],
                season=None,  # 全季节
                indoor=False,
                safety_notes=["注意防晒", "携带水分", "穿着合适的运动鞋"]
            ),
            Activity(
                name="骑行",
                description="自行车骑行运动",
                category="运动",
                suitable_weather=["晴天", "多云"],
                season=None,
                indoor=False,
                safety_notes=["佩戴头盔", "注意交通安全", "检查自行车状况"]
            ),
            Activity(
                name="徒步登山",
                description="山地徒步或登山活动",
                category="运动",
                suitable_weather=["晴天", "多云"],
                season=Season.SPRING,
                indoor=False,
                safety_notes=["穿着防滑鞋", "携带足够水和食物", "告知他人行程"]
            ),
            Activity(
                name="游泳",
                description="游泳锻炼",
                category="运动",
                suitable_weather=["晴天", "多云"],
                season=Season.SUMMER,
                indoor=False,
                safety_notes=["注意水质", "不要独自游泳", "注意防晒"]
            ),
            
            # 休闲娱乐活动
            Activity(
                name="公园散步",
                description="在公园或绿地悠闲散步",
                category="休闲",
                suitable_weather=["晴天", "多云", "阴天"],
                season=None,
                indoor=False,
                safety_notes=["穿着舒适的鞋子", "注意路面状况"]
            ),
            Activity(
                name="野餐",
                description="户外野餐活动",
                category="休闲",
                suitable_weather=["晴天", "多云"],
                season=Season.SPRING,
                indoor=False,
                safety_notes=["选择安全场所", "注意食物保鲜", "清理垃圾"]
            ),
            Activity(
                name="摄影",
                description="户外摄影创作",
                category="艺术",
                suitable_weather=["晴天", "多云", "阴天"],
                season=None,
                indoor=False,
                safety_notes=["保护设备", "注意个人安全", "尊重他人隐私"]
            ),
            
            # 室内活动
            Activity(
                name="健身房锻炼",
                description="室内健身房运动",
                category="运动",
                suitable_weather=["雨天", "雪天", "雷暴"],
                season=None,
                indoor=True,
                safety_notes=["正确使用器械", "适量运动", "注意补水"]
            ),
            Activity(
                name="瑜伽",
                description="室内瑜伽练习",
                category="运动",
                suitable_weather=["雨天", "雪天", "雷暴"],
                season=None,
                indoor=True,
                safety_notes=["使用瑜伽垫", "量力而行", "保持呼吸"]
            ),
            Activity(
                name="读书",
                description="室内阅读",
                category="学习",
                suitable_weather=["雨天", "雪天", "雷暴"],
                season=None,
                indoor=True,
                safety_notes=["保持良好坐姿", "注意光线", "定时休息"]
            ),
            Activity(
                name="看电影",
                description="观看电影",
                category="娱乐",
                suitable_weather=["雨天", "雪天", "雷暴"],
                season=None,
                indoor=True,
                safety_notes=["控制观看时间", "选择合适音量"]
            ),
            
            # 季节性活动
            Activity(
                name="赏花",
                description="观赏春季花卉",
                category="休闲",
                suitable_weather=["晴天", "多云"],
                season=Season.SPRING,
                indoor=False,
                safety_notes=["注意花粉过敏", "不要采摘花朵"]
            ),
            Activity(
                name="海滩活动",
                description="海滩游玩",
                category="休闲",
                suitable_weather=["晴天"],
                season=Season.SUMMER,
                indoor=False,
                safety_notes=["涂抹防晒霜", "注意海浪", "补充水分"]
            ),
            Activity(
                name="赏秋叶",
                description="观赏秋季红叶",
                category="休闲",
                suitable_weather=["晴天", "多云"],
                season=Season.AUTUMN,
                indoor=False,
                safety_notes=["穿着保暖衣物", "注意路面湿滑"]
            ),
            Activity(
                name="滑雪",
                description="滑雪运动",
                category="运动",
                suitable_weather=["雪天"],
                season=Season.WINTER,
                indoor=False,
                safety_notes=["穿戴防护装备", "选择适合难度", "注意保暖"]
            ),
        ]
    
    def _init_weather_thresholds(self) -> None:
        """初始化天气阈值"""
        self.weather_thresholds = {
            'temperature': {
                'very_cold': -10,
                'cold': 5,
                'cool': 15,
                'warm': 25,
                'hot': 30,
                'very_hot': 35
            },
            'wind_speed': {
                'calm': 5,
                'light': 15,
                'moderate': 25,
                'strong': 35
            },
            'humidity': {
                'low': 30,
                'comfortable': 60,
                'high': 80
            },
            'uv_index': {
                'low': 2,
                'moderate': 5,
                'high': 7,
                'very_high': 10
            }
        }
    
    def recommend_activities(self, weather: WeatherData, season: Season) -> List[Activity]:
        """
        基于天气条件和季节推荐活动
        
        Args:
            weather: 当前天气数据
            season: 当前季节
            
        Returns:
            推荐的活动列表
        """
        suitable_activities = []
        
        # 根据天气条件过滤活动
        weather_filtered = self.filter_by_weather_conditions(self.activities, weather)
        
        # 根据季节进一步过滤
        for activity in weather_filtered:
            if activity.season is None or activity.season == season:
                suitable_activities.append(activity)
        
        # 根据天气条件排序推荐优先级
        suitable_activities.sort(key=lambda x: self._calculate_activity_score(x, weather))
        
        return suitable_activities[:8]  # 返回前8个推荐
    
    def get_safety_recommendations(self, weather: WeatherData) -> List[str]:
        """
        基于天气条件生成安全建议
        
        Args:
            weather: 当前天气数据
            
        Returns:
            安全建议列表
        """
        recommendations = []
        
        # 温度相关建议
        temp = weather.temperature
        if temp <= self.weather_thresholds['temperature']['very_cold']:
            recommendations.extend([
                "极寒天气，避免长时间户外活动",
                "穿着多层保暖衣物",
                "注意防止冻伤"
            ])
        elif temp <= self.weather_thresholds['temperature']['cold']:
            recommendations.extend([
                "天气寒冷，注意保暖",
                "户外活动时间不宜过长"
            ])
        elif temp >= self.weather_thresholds['temperature']['very_hot']:
            recommendations.extend([
                "高温天气，避免中午时段户外活动",
                "多补充水分，预防中暑",
                "穿着轻薄透气衣物"
            ])
        elif temp >= self.weather_thresholds['temperature']['hot']:
            recommendations.extend([
                "天气炎热，注意防暑降温",
                "户外活动请做好防晒"
            ])
        
        # 风速相关建议
        if weather.wind_speed >= self.weather_thresholds['wind_speed']['strong']:
            recommendations.extend([
                "大风天气，避免高空作业",
                "注意固定户外物品",
                "骑行时要格外小心"
            ])
        elif weather.wind_speed >= self.weather_thresholds['wind_speed']['moderate']:
            recommendations.append("风力较大，户外活动注意安全")
        
        # 湿度相关建议
        if weather.humidity >= self.weather_thresholds['humidity']['high']:
            recommendations.extend([
                "湿度较高，注意通风",
                "运动时容易出汗，及时补水"
            ])
        elif weather.humidity <= self.weather_thresholds['humidity']['low']:
            recommendations.extend([
                "空气干燥，注意补水",
                "使用润肤霜保护皮肤"
            ])
        
        # UV指数相关建议
        if weather.uv_index >= self.weather_thresholds['uv_index']['very_high']:
            recommendations.extend([
                "紫外线极强，避免长时间暴露在阳光下",
                "使用SPF30+防晒霜",
                "佩戴帽子和太阳镜"
            ])
        elif weather.uv_index >= self.weather_thresholds['uv_index']['high']:
            recommendations.extend([
                "紫外线较强，注意防晒",
                "使用防晒霜"
            ])
        
        # 天气条件相关建议
        condition_lower = weather.condition.lower()
        if any(word in condition_lower for word in ['雨', 'rain', '雷', 'thunder', '暴']):
            recommendations.extend([
                "雨天路滑，注意行走安全",
                "避免在空旷地带活动",
                "携带雨具"
            ])
        elif any(word in condition_lower for word in ['雪', 'snow']):
            recommendations.extend([
                "雪天路滑，小心行走",
                "注意保暖防滑",
                "清理车辆积雪"
            ])
        elif any(word in condition_lower for word in ['雾', 'fog', '霾', 'haze']):
            recommendations.extend([
                "能见度低，注意交通安全",
                "减少户外运动",
                "佩戴口罩"
            ])
        
        # 能见度相关建议
        if weather.visibility < 1.0:  # 能见度小于1公里
            recommendations.extend([
                "能见度极低，避免驾驶",
                "户外活动需格外小心"
            ])
        elif weather.visibility < 5.0:  # 能见度小于5公里
            recommendations.append("能见度较低，注意交通安全")
        
        return recommendations
    
    def filter_by_weather_conditions(self, activities: List[Activity], weather: WeatherData) -> List[Activity]:
        """
        根据天气条件过滤活动
        
        Args:
            activities: 活动列表
            weather: 天气数据
            
        Returns:
            适合当前天气的活动列表
        """
        suitable_activities = []
        weather_category = self._categorize_weather(weather)
        
        for activity in activities:
            # 检查天气条件是否适合
            if weather_category in activity.suitable_weather:
                suitable_activities.append(activity)
            # 如果是恶劣天气，推荐室内活动
            elif self._is_severe_weather(weather) and activity.indoor:
                suitable_activities.append(activity)
        
        return suitable_activities
    
    def _categorize_weather(self, weather: WeatherData) -> str:
        """
        将天气数据分类为简单的天气类型
        
        Args:
            weather: 天气数据
            
        Returns:
            天气类型字符串
        """
        condition_lower = weather.condition.lower()
        
        # 检查恶劣天气
        if any(word in condition_lower for word in ['雷', 'thunder', '暴雨', 'storm']):
            return "雷暴"
        elif any(word in condition_lower for word in ['雨', 'rain', '毛毛雨', 'drizzle']):
            return "雨天"
        elif any(word in condition_lower for word in ['雪', 'snow']):
            return "雪天"
        elif any(word in condition_lower for word in ['雾', 'fog', '霾', 'haze']):
            return "雾霾"
        elif any(word in condition_lower for word in ['晴', 'clear', 'sunny']):
            return "晴天"
        elif any(word in condition_lower for word in ['云', 'cloud', 'overcast']):
            if '多云' in condition_lower or 'partly' in condition_lower:
                return "多云"
            else:
                return "阴天"
        else:
            return "多云"  # 默认分类
    
    def _is_severe_weather(self, weather: WeatherData) -> bool:
        """
        判断是否为恶劣天气
        
        Args:
            weather: 天气数据
            
        Returns:
            是否为恶劣天气
        """
        condition_lower = weather.condition.lower()
        
        # 检查恶劣天气条件
        severe_conditions = [
            '雷', 'thunder', '暴', 'storm', '大雨', 'heavy rain',
            '大雪', 'heavy snow', '冰雹', 'hail'
        ]
        
        if any(word in condition_lower for word in severe_conditions):
            return True
        
        # 检查极端温度
        if (weather.temperature <= self.weather_thresholds['temperature']['very_cold'] or
            weather.temperature >= self.weather_thresholds['temperature']['very_hot']):
            return True
        
        # 检查强风
        if weather.wind_speed >= self.weather_thresholds['wind_speed']['strong']:
            return True
        
        # 检查能见度
        if weather.visibility < 1.0:
            return True
        
        return False
    
    def _calculate_activity_score(self, activity: Activity, weather: WeatherData) -> float:
        """
        计算活动的推荐分数（分数越高越推荐）
        
        Args:
            activity: 活动
            weather: 天气数据
            
        Returns:
            活动分数
        """
        score = 0.0
        
        # 基础分数
        score += 50.0
        
        # 天气适宜性加分
        weather_category = self._categorize_weather(weather)
        if weather_category in activity.suitable_weather:
            score += 30.0
        
        # 温度适宜性加分
        temp = weather.temperature
        if activity.indoor:
            score += 20.0  # 室内活动不受温度影响
        else:
            if self.weather_thresholds['temperature']['cool'] <= temp <= self.weather_thresholds['temperature']['warm']:
                score += 25.0  # 温度适宜
            elif self.weather_thresholds['temperature']['cold'] <= temp <= self.weather_thresholds['temperature']['hot']:
                score += 15.0  # 温度可接受
            else:
                score -= 20.0  # 温度不适宜
        
        # 风速影响
        if not activity.indoor:
            if weather.wind_speed <= self.weather_thresholds['wind_speed']['light']:
                score += 10.0
            elif weather.wind_speed >= self.weather_thresholds['wind_speed']['strong']:
                score -= 15.0
        
        # UV指数影响（对户外活动）
        if not activity.indoor:
            if weather.uv_index <= self.weather_thresholds['uv_index']['moderate']:
                score += 5.0
            elif weather.uv_index >= self.weather_thresholds['uv_index']['very_high']:
                score -= 10.0
        
        # 能见度影响
        if not activity.indoor:
            if weather.visibility >= 10.0:
                score += 5.0
            elif weather.visibility < 1.0:
                score -= 20.0
        
        return score
    
    def get_current_season(self) -> Season:
        """
        根据当前日期获取季节
        
        Returns:
            当前季节
        """
        month = datetime.now().month
        
        if month in [3, 4, 5]:
            return Season.SPRING
        elif month in [6, 7, 8]:
            return Season.SUMMER
        elif month in [9, 10, 11]:
            return Season.AUTUMN
        else:
            return Season.WINTER