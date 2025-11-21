# Deribit BTC 期权和 DVOL 监控系统

## 📖 项目简介

这是一个基于 Python 的量化监控系统，用于实时监控 Deribit 交易所上的：

1. **账户 BTC 期权合约**的 **IV（隐含波动率）** 和 **Gamma** 指标
2. **BTC Volatility Index (DVOL)**，包括绝对数值和 IV 百分位

当上述指标在**最近 5 分钟内**出现异动（百分比变化或绝对数值变化超过设定阈值）时，系统会通过**飞书 Webhook 机器人**自动发送告警消息。

## ✨ 功能列表

- ✅ **实时监控** Deribit 账户中的 BTC 期权持仓及其 Greeks（IV、Gamma 等）
- ✅ **实时监控** Deribit 公共 BTC DVOL 指数
- ✅ **自动计算** DVOL 在历史数据中的 IV 百分位
- ✅ **智能告警** 当指标在 5 分钟内变化超过阈值时自动发送飞书告警
- ✅ **告警去重** 支持告警冷却时间，避免重复告警
- ✅ **数据持久化** 使用 JSON 文件存储历史数据，支持滚动窗口
- ✅ **错误重试** 内置 HTTP 请求重试机制（指数退避）
- ✅ **详细日志** 使用 loguru 提供清晰的日志输出

## 🛠️ 环境依赖

- Python 3.10+
- Deribit API 账户（需要开通读取期权持仓和 Greeks 的权限）
- 飞书 Webhook 机器人（可选，用于接收告警）

## 📦 安装步骤

### 1. 克隆或下载项目

```bash
cd /path/to/derbit
```

### 2. 创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `env_example.txt` 为 `.env` 并填写你的凭证：

```bash
# Windows
copy env_example.txt .env

# Linux / macOS
cp env_example.txt .env
```

编辑 `.env` 文件，填写你的实际凭证：

```env
DERIBIT_CLIENT_ID=your_client_id_here
DERIBIT_CLIENT_SECRET=your_client_secret_here
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_webhook_token_here
```

### 5. 配置监控阈值

编辑 `config.yaml` 文件，根据你的需求调整监控阈值：

- `option_greeks_thresholds`: 期权 IV 和 Gamma 的异动阈值
- `dvol_thresholds`: DVOL 数值和 IV 百分位的异动阈值
- `poll_interval_seconds`: 轮询间隔（默认 60 秒）
- `cooldown_seconds`: 告警冷却时间（默认 300 秒）

## 🚀 启动说明

### 基本启动

```bash
python main.py
```

### 指定配置文件

```bash
python main.py --config custom_config.yaml
```

### Linux 后台运行示例

#### 方式 1: 使用 nohup

```bash
nohup python main.py > monitor.log 2>&1 &
```

#### 方式 2: 使用 screen

```bash
# 创建一个新的 screen 会话
screen -S deribit_monitor

# 在 screen 中运行程序
python main.py

# 按 Ctrl+A 然后 D 来分离会话

# 重新连接到会话
screen -r deribit_monitor
```

#### 方式 3: 使用 systemd（推荐用于生产环境）

创建 `/etc/systemd/system/deribit-monitor.service`：

```ini
[Unit]
Description=Deribit BTC Option and DVOL Monitor
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/derbit
Environment="PATH=/path/to/derbit/venv/bin"
ExecStart=/path/to/derbit/venv/bin/python /path/to/derbit/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable deribit-monitor
sudo systemctl start deribit-monitor

# 查看日志
sudo journalctl -u deribit-monitor -f
```

## ⚙️ 配置说明

### 环境变量 (.env)

| 变量名 | 说明 | 是否必需 |
|--------|------|----------|
| `DERIBIT_CLIENT_ID` | Deribit API Client ID | ✅ 是 |
| `DERIBIT_CLIENT_SECRET` | Deribit API Client Secret | ✅ 是 |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook URL | ✅ 是（如需告警） |
| `DERIBIT_BASE_URL` | Deribit API 基础 URL（可选） | ❌ 否 |

### 配置文件 (config.yaml)

#### 通用配置

```yaml
general:
  poll_interval_seconds: 60  # 轮询间隔（秒）
  log_level: INFO            # 日志级别
```

#### Deribit 配置

```yaml
deribit:
  base_url: https://www.deribit.com  # API 基础 URL
  underlying: BTC                     # 监控标的
  option_filters:
    currency: BTC
    kind: option
    only_active_positions: true       # 只监控有效持仓
```

#### 监控阈值

```yaml
option_greeks_thresholds:
  iv:
    pct_change_5m: 0.10    # IV 5 分钟变动超过 10% 触发
    abs_change_5m: 0.05    # IV 5 分钟绝对变动超过 0.05 触发
  gamma:
    pct_change_5m: 0.20
    abs_change_5m: 0.001

dvol_thresholds:
  dvol_value:
    pct_change_5m: 0.05    # DVOL 5 分钟变动超过 5% 触发
    abs_change_5m: 5.0     # DVOL 5 分钟绝对变动超过 5 点触发
  iv_percentile:
    pct_change_5m: 0.10
    abs_change_5m: 0.10    # IV 百分位 5 分钟变动超过 10 百分点触发
```

#### 告警配置

```yaml
alert:
  enable_alert: true        # 是否启用告警
  cooldown_seconds: 300     # 告警冷却时间（秒）
```

## 📊 工作原理

### 监控流程

1. **数据获取**：每 N 秒（可配置）轮询一次 Deribit API
   - 获取账户期权持仓及其 Greeks（IV、Gamma 等）
   - 获取当前 DVOL 数值

2. **历史数据存储**：将每次获取的数据保存到 `state_store.json`
   - 保留最近 60 分钟的历史数据（可配置）
   - 支持按时间戳查询历史值

3. **异动检测**：每次轮询时，与 5 分钟前的数据对比
   - 计算百分比变化：`(current - previous) / previous`
   - 计算绝对变化：`current - previous`
   - 与配置的阈值对比

4. **告警发送**：当变化超过阈值时
   - 检查冷却时间（避免重复告警）
   - 生成格式化告警消息
   - 通过飞书 Webhook 发送告警

5. **IV 百分位计算**：基于历史 DVOL 数据
   - 维护最近 60 分钟的 DVOL 历史
   - 计算当前 DVOL 在历史分布中的百分位
   - 监控百分位的异常变化

### 数据存储

系统使用 `state_store.json` 文件存储监控数据：

- 期权持仓数据：按 `instrument_name` 索引
- DVOL 数据：按 `dvol` 索引
- IV 百分位数据：按 `dvol_percentile` 索引
- 告警时间戳：存储在 `last_alert_times` 中

## 📝 注意事项

### Deribit API 权限

- 确保你的 Deribit API 密钥具有以下权限：
  - ✅ 读取期权持仓（`get_positions`）
  - ✅ 读取 Greeks 数据
  - ⚠️ 不需要交易权限，本系统只读取数据

### 生产环境建议

1. **测试阈值**：在生产环境部署前，先用较小的阈值测试几次，确认告警逻辑正常

2. **监控日志**：定期检查日志文件，确认系统正常运行

3. **API 限流**：Deribit API 有请求频率限制，建议轮询间隔不要小于 60 秒

4. **错误处理**：系统内置了重试机制，但建议监控系统的运行状态

5. **数据备份**：定期备份 `state_store.json` 文件（如果需要保留历史数据）

### 故障排除

#### 认证失败

```
错误: Deribit 认证失败
解决: 检查 .env 文件中的 DERIBIT_CLIENT_ID 和 DERIBIT_CLIENT_SECRET 是否正确
```

#### 获取持仓失败

```
错误: 获取期权持仓失败
解决: 确保 API 密钥有读取持仓的权限，并且账户中有期权持仓
```

#### 飞书告警发送失败

```
错误: 发送飞书告警失败
解决: 检查 .env 文件中的 FEISHU_WEBHOOK_URL 是否正确，确保机器人未被移除
```

#### 数据格式异常

```
错误: DVOL 数据格式异常
解决: Deribit API 可能更新了数据格式，需要检查 API 文档并更新代码
```

## 📁 项目结构

```
derbit/
├── main.py              # 程序主入口
├── config.py            # 配置加载模块
├── deribit_client.py    # Deribit API 客户端封装
├── monitor.py           # 监控逻辑核心模块
├── notifier.py          # 飞书告警模块
├── state_store.py       # 状态存储模块
├── config.yaml          # 配置文件
├── .env                 # 环境变量（需要自己创建）
├── .env.example         # 环境变量模板
├── requirements.txt     # Python 依赖
├── README.md            # 项目文档
└── state_store.json     # 数据存储文件（运行后自动生成）
```

## 🔗 相关链接

- [Deribit API 文档](https://docs.deribit.com)
- [飞书自定义机器人文档](https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN)

## 📄 许可证

本项目仅供学习和研究使用。使用前请确保遵守 Deribit 的使用条款。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## ⚠️ 免责声明

本项目仅供量化监控使用，不构成任何投资建议。使用本系统进行交易决策的风险由用户自行承担。

