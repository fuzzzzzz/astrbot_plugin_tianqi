"""
命令解析器

实现自然语言天气查询解析，命令类型检测和参数提取。
"""

import re
from typing import Optional, Dict, List, Tuple, Pattern
from .interfaces import ICommandParser
from .models import WeatherCommand, CommandType


class CommandParser(ICommandParser):
    """天气命令解析器"""
    
    def __init__(self):
        """初始化命令解析器"""
        self._init_patterns()
        self._init_location_patterns()
        self._init_time_patterns()
    
    def _init_patterns(self):
        """初始化命令匹配模式"""
        # 当前天气查询模式
        self.weather_patterns = [
            # 直接询问天气
            r'(?:今天|现在)(.*)(?:天气|气温|温度)(?:怎么样|如何|多少)',
            r'(.*)(?:的天气|天气怎么样|天气如何|气温多少)',
            r'(?:天气|weather)\s*(.+)',
            r'(.+)(?:天气|weather)',
            # 英文模式
            r'(?:what\'?s\s+the\s+)?weather\s+(?:in\s+|at\s+|for\s+)?(.+)',
            r'(?:how\'?s\s+the\s+)?weather\s+(?:in\s+|at\s+|for\s+)?(.+)',
            r'current\s+weather\s+(?:in\s+|at\s+|for\s+)?(.+)',
        ]
        
        # 预报查询模式
        self.forecast_patterns = [
            # 中文预报模式 - 明确的时间指示词
            r'(?:明天|后天|大后天)(.*)(?:天气|气温|温度|预报)(?:怎么样|如何|多少|$)',
            r'(.*)(?:明天|后天|大后天)(?:天气|预报)',
            r'(.*)(?:的预报|预报怎么样)',
            r'(?:预报|forecast)\s*(.+)',
            # 英文预报模式
            r'(?:weather\s+)?forecast\s+(?:for\s+|in\s+|at\s+)?(.+)',
            r'(?:what\'?s\s+the\s+)?forecast\s+(?:for\s+|in\s+|at\s+)?(.+)',
            r'(?:will\s+it\s+rain|will\s+it\s+snow)\s+(?:in\s+|at\s+)?(.+)',
            r'tomorrow\'?s?\s+weather\s+(?:in\s+|at\s+|for\s+)?(.+)',
        ]
        
        # 小时预报模式
        self.hourly_patterns = [
            r'(?:小时|hourly)\s*(?:预报|forecast)\s*(.+)',
            r'(.+)(?:的小时预报|小时预报)',
            r'hourly\s+(?:weather\s+)?(?:for\s+|in\s+|at\s+)?(.+)',
        ]
        
        # 帮助命令模式
        self.help_patterns = [
            r'(?:帮助|help|使用说明|命令列表)',
            r'(?:天气|weather)(?:帮助|help)',
            r'(?:how\s+to\s+use|usage|commands)',
        ]
        
        # 设置命令模式
        self.set_location_patterns = [
            r'(?:设置|set)\s*(?:位置|location)\s*(.+)',
            r'(?:默认|default)\s*(?:位置|location)\s*(.+)',
            r'set\s+(?:my\s+)?(?:default\s+)?location\s+(?:to\s+)?(.+)',
        ]
        
        self.set_units_patterns = [
            r'(?:设置|set)\s*(?:单位|units)\s*(.+)',
            r'(?:使用|use)\s*(.+)\s*(?:单位|units)',
            r'set\s+units\s+(?:to\s+)?(.+)',
        ]
        
        # 警报相关模式
        self.alert_patterns = [
            r'(?:警报|alert|通知|notification)(.+)',
            r'(.+)(?:警报|alert)',
            r'weather\s+(?:alert|warning)s?\s*(?:for\s+)?(.+)',
        ]
        
        # 活动推荐模式
        self.activity_patterns = [
            r'(?:活动|activity|activities)\s*(?:推荐|recommendation)(.+)',
            r'(.+)(?:适合什么活动|能做什么)',
            r'what\s+(?:can\s+i\s+do|activities)\s+(?:in\s+|at\s+)?(.+)',
            r'(?:outdoor\s+)?activities\s+(?:for\s+|in\s+|at\s+)?(.+)',
        ]
        
        # 编译正则表达式
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则表达式模式"""
        self.compiled_weather_patterns = [re.compile(p, re.IGNORECASE) for p in self.weather_patterns]
        self.compiled_forecast_patterns = [re.compile(p, re.IGNORECASE) for p in self.forecast_patterns]
        self.compiled_hourly_patterns = [re.compile(p, re.IGNORECASE) for p in self.hourly_patterns]
        self.compiled_help_patterns = [re.compile(p, re.IGNORECASE) for p in self.help_patterns]
        self.compiled_set_location_patterns = [re.compile(p, re.IGNORECASE) for p in self.set_location_patterns]
        self.compiled_set_units_patterns = [re.compile(p, re.IGNORECASE) for p in self.set_units_patterns]
        self.compiled_alert_patterns = [re.compile(p, re.IGNORECASE) for p in self.alert_patterns]
        self.compiled_activity_patterns = [re.compile(p, re.IGNORECASE) for p in self.activity_patterns]
    
    def _init_location_patterns(self):
        """初始化位置提取模式"""
        self.location_extraction_patterns = [
            # 中文位置模式 - 更精确的匹配
            r'(?:今天|明天|后天)\s*([^的天气预报]+?)(?:的天气|天气|预报|$)',
            r'([^，,。.！!？?]+?)(?:的天气|天气怎么样|天气如何|的预报|的小时预报|小时预报)',
            r'(?:天气|预报|小时预报|weather|forecast|hourly)\s+([^，,。.！!？?]+?)(?:$|[，,。.！!？?])',
            r'(?:在|去|到|位于)\s*([^的]+?)(?:的|$)',
            # 英文位置模式
            r'(?:weather|forecast|hourly)\s+(?:in\s+|at\s+|for\s+)?([a-zA-Z\s]+?)(?:$|[,.])',
            r'(?:in|at|for)\s+([a-zA-Z\s]+?)(?:\s+weather|\s+forecast|$)',
        ]
        
        self.compiled_location_patterns = [re.compile(p, re.IGNORECASE) for p in self.location_extraction_patterns]
    
    def _init_time_patterns(self):
        """初始化时间模式"""
        self.time_patterns = {
            'today': [r'今天', r'现在', r'当前', r'today', r'now', r'current'],
            'tomorrow': [r'明天', r'tomorrow'],
            'day_after_tomorrow': [r'后天', r'day\s+after\s+tomorrow'],
            'this_week': [r'这周', r'本周', r'this\s+week'],
            'next_week': [r'下周', r'next\s+week'],
        }
        
        self.compiled_time_patterns = {}
        for time_key, patterns in self.time_patterns.items():
            self.compiled_time_patterns[time_key] = [re.compile(p, re.IGNORECASE) for p in patterns]
    
    def parse_command(self, message: str) -> Optional[WeatherCommand]:
        """
        解析天气命令
        
        Args:
            message: 用户输入的消息
            
        Returns:
            Optional[WeatherCommand]: 解析出的命令对象，如果无法解析则返回 None
        """
        if not message or not message.strip():
            return None
        
        message = message.strip()
        
        # 检测命令类型
        command_type = self.detect_command_type(message)
        
        if command_type == CommandType.HELP:
            return WeatherCommand(command_type=command_type)
        
        # 提取位置信息
        location = self.extract_location(message)
        
        # 提取时间信息
        time_period = self._extract_time_period(message)
        
        # 提取其他参数
        additional_params = self._extract_additional_params(message, command_type)
        
        return WeatherCommand(
            command_type=command_type,
            location=location,
            time_period=time_period,
            additional_params=additional_params
        )
    
    def extract_location(self, text: str) -> Optional[str]:
        """
        提取位置信息
        
        Args:
            text: 输入文本
            
        Returns:
            Optional[str]: 提取出的位置，如果没有找到则返回 None
        """
        if not text:
            return None
        
        # 尝试使用各种位置提取模式
        for pattern in self.compiled_location_patterns:
            match = pattern.search(text)
            if match:
                location = match.group(1).strip()
                # 清理位置字符串
                location = self._clean_location_string(location)
                if location and self._is_valid_location(location):
                    return location
        
        # 如果没有匹配到模式，尝试简单的词汇提取
        return self._extract_location_fallback(text)
    
    def detect_command_type(self, text: str) -> CommandType:
        """
        检测命令类型
        
        Args:
            text: 输入文本
            
        Returns:
            CommandType: 检测到的命令类型
        """
        if not text:
            return CommandType.CURRENT_WEATHER
        
        text = text.strip()
        
        # 检查帮助命令
        for pattern in self.compiled_help_patterns:
            if pattern.search(text):
                return CommandType.HELP
        
        # 检查设置位置命令
        for pattern in self.compiled_set_location_patterns:
            if pattern.search(text):
                return CommandType.SET_LOCATION
        
        # 检查设置单位命令
        for pattern in self.compiled_set_units_patterns:
            if pattern.search(text):
                return CommandType.SET_UNITS
        
        # 检查警报命令
        for pattern in self.compiled_alert_patterns:
            if pattern.search(text):
                return CommandType.ALERTS
        
        # 检查活动推荐命令
        for pattern in self.compiled_activity_patterns:
            if pattern.search(text):
                return CommandType.ACTIVITIES
        
        # 检查小时预报命令
        for pattern in self.compiled_hourly_patterns:
            if pattern.search(text):
                return CommandType.HOURLY_FORECAST
        
        # 检查预报命令
        for pattern in self.compiled_forecast_patterns:
            if pattern.search(text):
                return CommandType.FORECAST
        
        # 检查当前天气命令
        for pattern in self.compiled_weather_patterns:
            if pattern.search(text):
                return CommandType.CURRENT_WEATHER
        
        # 默认返回当前天气
        return CommandType.CURRENT_WEATHER
    
    def _extract_time_period(self, text: str) -> Optional[str]:
        """提取时间段信息"""
        for time_key, patterns in self.compiled_time_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    return time_key
        return None
    
    def _extract_additional_params(self, text: str, command_type: CommandType) -> Dict[str, any]:
        """提取额外参数"""
        params = {}
        
        # 根据命令类型提取特定参数
        if command_type == CommandType.SET_UNITS:
            units = self._extract_units(text)
            if units:
                params['units'] = units
        
        elif command_type == CommandType.FORECAST:
            days = self._extract_forecast_days(text)
            if days:
                params['days'] = days
        
        elif command_type == CommandType.HOURLY_FORECAST:
            hours = self._extract_forecast_hours(text)
            if hours:
                params['hours'] = hours
        
        return params
    
    def _clean_location_string(self, location: str) -> str:
        """清理位置字符串"""
        if not location:
            return ""
        
        # 移除常见的无用词汇
        stop_words = [
            '的', '在', '去', '到', '位于', '地方', '城市', '地区', '今天', '明天', '后天',
            'the', 'in', 'at', 'for', 'of', 'city', 'area', 'place', 'today', 'tomorrow'
        ]
        
        # 移除标点符号
        location = re.sub(r'[，,。.！!？?；;：:]', '', location)
        
        # 移除停用词
        words = location.split()
        filtered_words = []
        
        for word in words:
            # 跳过时间词汇
            if word.lower() in ['今天', '明天', '后天', 'today', 'tomorrow']:
                continue
            # 跳过停用词
            if word.lower() not in stop_words:
                filtered_words.append(word)
        
        return ' '.join(filtered_words).strip()
    
    def _is_valid_location(self, location: str) -> bool:
        """验证位置是否有效"""
        if not location or len(location.strip()) < 2:
            return False
        
        # 过滤掉一些明显无效的词汇
        invalid_words = [
            '今天', '明天', '后天', '现在', '当前', '天气', '预报',
            'today', 'tomorrow', 'now', 'current', 'weather', 'forecast',
            '怎么样', '如何', '多少', 'how', 'what', 'when', 'where'
        ]
        
        location_lower = location.lower().strip()
        return location_lower not in invalid_words
    
    def _extract_location_fallback(self, text: str) -> Optional[str]:
        """备用位置提取方法"""
        # 简单的词汇提取，寻找可能的地名
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        
        for word in words:
            if len(word) >= 2 and self._is_valid_location(word):
                # 简单的地名判断
                if self._looks_like_location(word):
                    return word
        
        return None
    
    def _looks_like_location(self, word: str) -> bool:
        """判断词汇是否像地名"""
        # 简单的启发式规则
        if len(word) < 2:
            return False
        
        # 中文地名通常包含这些字符
        location_indicators = ['市', '省', '县', '区', '镇', '村', '州', '港', '岛']
        if any(indicator in word for indicator in location_indicators):
            return True
        
        # 英文地名通常首字母大写
        if word[0].isupper() and word.isalpha():
            return True
        
        # 常见城市名称
        common_cities = [
            '北京', '上海', '广州', '深圳', '杭州', '南京', '武汉', '成都', '西安', '重庆',
            'beijing', 'shanghai', 'guangzhou', 'shenzhen', 'hangzhou', 'nanjing',
            'wuhan', 'chengdu', 'xian', 'chongqing', 'london', 'paris', 'tokyo',
            'newyork', 'losangeles', 'chicago', 'houston', 'philadelphia'
        ]
        
        return word.lower() in common_cities
    
    def _extract_units(self, text: str) -> Optional[str]:
        """提取单位设置"""
        metric_keywords = ['摄氏度', '公制', 'metric', 'celsius', 'c']
        imperial_keywords = ['华氏度', '英制', 'imperial', 'fahrenheit', 'f']
        
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in metric_keywords):
            return 'metric'
        elif any(keyword in text_lower for keyword in imperial_keywords):
            return 'imperial'
        
        return None
    
    def _extract_forecast_days(self, text: str) -> Optional[int]:
        """提取预报天数"""
        # 寻找数字
        numbers = re.findall(r'\d+', text)
        
        # 检查特定的时间词汇
        if '明天' in text or 'tomorrow' in text.lower():
            return 1
        elif '后天' in text or 'day after tomorrow' in text.lower():
            return 2
        elif '三天' in text or '3天' in text or '3 day' in text.lower():
            return 3
        elif '一周' in text or '7天' in text or 'week' in text.lower():
            return 7
        
        # 如果找到数字，取第一个合理的数字
        for num_str in numbers:
            num = int(num_str)
            if 1 <= num <= 14:  # 限制在合理范围内
                return num
        
        return None
    
    def _extract_forecast_hours(self, text: str) -> Optional[int]:
        """提取预报小时数"""
        # 寻找数字
        numbers = re.findall(r'\d+', text)
        
        # 检查特定的时间词汇
        if '小时' in text or 'hour' in text.lower():
            for num_str in numbers:
                num = int(num_str)
                if 1 <= num <= 48:  # 限制在合理范围内
                    return num
        
        # 默认返回24小时
        return 24