# 大麦抢票自动化系统

一个基于 Appium 的大麦网**移动端**抢票自动化工具,通过驱动安卓设备上的大麦 App 完成选城市、选票价、选观演人、提交订单的流程。

## 🚀 功能特性

- **移动端抢票**:基于 Appium + UiAutomator2,驱动安卓真机/模拟器上的大麦 App
- **智能抢票**:自动选择城市、票价、观演人员
- **高性能**:优化的原生坐标点击策略,适合抢票场景
- **可配置**:灵活的配置文件,支持多种演出设置

> 说明:大麦大部分热门票只能在 App 端购买,因此本项目只保留移动端方案。

## 📋 系统要求

### 基础环境
- **Python**: 3.9+
- **Node.js**: 20.19.0+ 或 22.12.0+ 或 24.0.0+
- **操作系统**: macOS / Windows / Linux

### 移动端抢票
- **Android SDK**: 已配置环境变量(含 adb / emulator)
- **Appium**: 3.x + UiAutomator2 驱动
- **Android设备**: 真机或模拟器(实战建议真机)

## 🛠️ 安装指南

### 1. 克隆项目
```bash
git clone <repository-url>
cd ticket-purchase
```

### 2. 安装 Python 依赖
```bash
# 使用 Poetry(推荐)
poetry install

# 或使用 venv + pip
python3 -m venv .venv
.venv/bin/pip install Appium-Python-Client selenium
```

### 3. 安装 Node.js 与 Appium
```bash
# macOS
brew install node
npm install -g appium          # 或装到项目内:npm install appium
appium driver install uiautomator2
appium --version
```

### 4. 配置 Android 环境
```bash
# 设置环境变量(添加到 ~/.zshrc 或 ~/.bashrc),路径换成你自己的 SDK
export ANDROID_HOME=/path/to/your/android/sdk
export ANDROID_SDK_ROOT=/path/to/your/android/sdk
export PATH="\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/emulator:\$PATH"

adb devices   # 验证
```

## ⚙️ 配置说明

### 移动端配置 (damai_appium/config.jsonc)

```json
{
  "server_url": "http://127.0.0.1:4723",
  "device_name": "auto",
  "users": ["观演人1", "观演人2"],
  "city": "泉州",
  "price_index": 1,
  "if_commit_order": false
}
```

#### 配置参数说明

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `server_url` | string | Appium 服务器地址 | `"http://127.0.0.1:4723"` |
| `device_name` | string | 设备序列号。`"auto"`=自动探测唯一设备;多设备时填 `adb devices` 的序列号 | `"auto"` |
| `users` | array | 观演人员名单 | `["张三", "李四"]` |
| `city` | string | 演出城市 | `"泉州"` |
| `price_index` | number | 票价索引(从 0 开始) | `1` |
| `if_commit_order` | boolean | 是否真实提交订单(**默认 false 安全;设 true 才真下单**) | `false` |

## 🚀 使用方法

### 1. 启动 Android 设备
```bash
# 启动模拟器(名称换成你的 AVD)
emulator -avd YourAVDName

# 或连接真机(需开启 USB 调试)
adb devices
```

### 2. 安装并登录大麦 App
在 Android 设备上安装大麦 App 并登录账号。

### 3. 启动 Appium 服务器
```bash
./start_appium.sh
```
> **新设备首次使用**务必用 `./start_appium.sh` 启动:它会检查设备、并**按需一次性安装** Appium 的 uiautomator2 辅助包(华为机需在手机点一次「继续安装」)。装过之后抢票时会跳过安装(`skipServerInstallation: True`),更快更稳。
>
> 也可手动启动:`appium --address 0.0.0.0 --port 4723 --relaxed-security`(但需自行确保辅助包已装)。

### 4. 配置抢票参数
编辑 `damai_appium/config.jsonc`:观演人员(users)、城市(city)、票价索引(price_index)、是否真实下单(if_commit_order,默认 false)。

### 5. 运行抢票脚本
先在设备上把大麦 App 操作到目标演出详情页,然后:
```bash
cd damai_appium
python damai_app_v2.py
```

## 🔧 故障排除

#### 1. Node.js 版本不兼容
```
Error: Node version must be at least ^20.19.0 || ^22.12.0 || >=24.0.0
```
升级 Node.js:`brew upgrade node`

#### 2. Android 环境变量未设置
```
Error: Neither ANDROID_HOME nor ANDROID_SDK_ROOT environment variable was exported
```
按"安装指南第 4 步"设置 `ANDROID_HOME` / `ANDROID_SDK_ROOT`。

#### 3. 设备连接问题 / adb device offline
- 检查连接:`adb devices`
- 瞬时掉线:手动 `adb reconnect offline`,彻底则 `adb kill-server && adb start-server`(代码层当前无自动重连兜底)

#### 4. Appium 连接失败
- 确保 Appium 服务器在运行、端口 4723 未被占用
- `curl http://127.0.0.1:4723/status` 应返回 ready

### 调试技巧
```bash
adb devices                                   # 连接的设备
adb shell getprop ro.build.version.release    # Android 版本
adb shell getprop sys.boot_completed          # 是否完全启动
curl http://127.0.0.1:4723/status             # Appium 状态
adb shell pm list packages | grep damai       # 大麦包名
```

## 📁 项目结构

```
ticket-purchase/
├── damai_appium/             # 移动端抢票
│   ├── damai_app_v2.py      # 主程序
│   ├── config.py            # 配置类
│   ├── config.jsonc         # 配置文件
│   └── app.md               # 应用说明
├── tests/                    # 测试
├── doc/                      # 文档(问题记录、架构设计、流程图)
├── img/                      # 图片资源
└── README.md                 # 说明文档
```

## ⚠️ 注意事项

1. **合法使用**:请遵守大麦网使用条款,合理使用自动化工具
2. **账号安全**:建议使用专门的测试账号
3. **网络环境**:确保网络连接稳定
4. **风控**:大麦/阿里风控会拦截自动化,尤其模拟器环境;本项目不绕过风控
5. **时间设置**:提前起服务、保温会话,在开售时刻触发

## 📄 许可证

本项目仅供学习和研究使用,请勿用于商业用途。
