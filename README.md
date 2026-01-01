# 智能天气助手 AstrBot 插件

一个为 AstrBot 平台设计的全功能天气插件，提供智能天气信息服务。

## 功能特性

- 🌤️ 实时天气查询
- 📊 多日天气预报
- 🎯 个性化用户偏好
- 🚨 天气警报通知
- 🏃 基于天气的活动推荐
- 💾 智能缓存管理
- 🌍 多种位置输入格式支持

## 项目结构

```
weather_plugin/
├── __init__.py          # 插件包初始化
├── plugin.py            # 主插件类
├── models.py            # 数据模型定义
├── interfaces.py        # 接口定义
└── config.py            # 配置管理

tests/
├── __init__.py          # 测试包初始化
├── conftest.py          # pytest 配置和 fixtures
├── test_models.py       # 数据模型测试
├── test_config.py       # 配置管理测试
└── test_plugin.py       # 插件主类测试

metadata.yaml            # AstrBot 插件元数据
config.yaml              # 插件配置文件
requirements.txt         # Python 依赖项
pytest.ini              # pytest 配置
README.md               # 项目说明文档
```

## 安装和配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

编辑 `config.yaml` 文件，填入您的天气 API 密钥：

```yaml
api_provider: "openweathermap"
api_key: "YOUR_API_KEY_HERE"
```

### 3. 部署到 AstrBot

将插件目录复制到 AstrBot 的插件目录中，然后重启 AstrBot。

## 使用方法

### 基本命令

- `weather 北京` - 查询北京当前天气
- `forecast 上海` - 查询上海天气预报
- `help` - 显示帮助信息

### 自然语言查询

- "今天天气怎么样？"
- "明天会下雨吗？"
- "这周末适合出门吗？"

## 开发

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_models.py

# 运行带覆盖率的测试
pytest --cov=weather_plugin
```

### 代码结构

插件采用分层架构设计：

1. **插件层** (`plugin.py`) - AstrBot 接口和消息路由
2. **服务层** - 业务逻辑处理（待实现）
3. **数据层** - 缓存和持久化存储（待实现）
4. **接口层** (`interfaces.py`) - 抽象接口定义

## 配置选项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `api_provider` | `openweathermap` | API 提供商 |
| `api_key` | - | API 密钥（必填） |
| `cache_enabled` | `true` | 是否启用缓存 |
| `default_units` | `metric` | 默认单位制 |
| `default_language` | `zh` | 默认语言 |

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！