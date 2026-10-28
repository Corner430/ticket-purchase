#!/bin/bash
# 大麦抢票 - Appium启动脚本
# 使用方法: ./start_appium.sh

echo "🚀 启动大麦抢票环境..."

# 项目根目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 加载环境变量（单一来源 env.sh）
source "$PROJECT_DIR/env.sh"

echo "✅ 环境变量已设置"
echo "   ANDROID_HOME: $ANDROID_HOME"
echo "   ANDROID_SDK_ROOT: $ANDROID_SDK_ROOT"

# 检查Node.js版本
NODE_VERSION=$(node --version | cut -d'v' -f2)
echo "📦 Node.js版本: $NODE_VERSION"

# 检查Appium是否安装
if ! command -v appium &> /dev/null; then
    echo "❌ Appium未安装，请先安装Appium"
    echo "   运行: npm install -g appium"
    exit 1
fi

# 检查Android设备
echo "📱 检查Android设备..."
DEVICES=$(adb devices | grep -c "device$")
if [ $DEVICES -eq 0 ]; then
    echo "⚠️  未检测到Android设备"
    echo "   请启动模拟器或连接真机"
    echo "   启动模拟器: emulator -avd damai_test"
    exit 1
else
    echo "✅ 检测到 $DEVICES 个Android设备"
fi

# 锁定目标设备（取第一台），后续命令都 -s 指定，避免多设备 "more than one device" 报错
SERIAL=$(adb devices | awk 'NR>1 && $2=="device"{print $1; exit}')
ADB="adb -s $SERIAL"
echo "🎯 目标设备: $SERIAL"

# 检查大麦APP是否安装
if ! $ADB shell pm list packages | grep -q "cn.damai"; then
    echo "⚠️  大麦APP未安装"
    echo "   请在设备上安装大麦APP"
    exit 1
else
    echo "✅ 大麦APP已安装"
fi

# 确保 Appium uiautomator2 辅助包已装（一次性就绪；有就跳过，不卡华为安装弹窗）
APK_BASE="$PROJECT_DIR/node_modules/appium-uiautomator2-driver/node_modules"
ensure_pkg() {  # $1=包名  $2=apk 路径(可含通配符)
    if $ADB shell pm list packages 2>/dev/null | tr -d '\r' | grep -qx "package:$1"; then
        echo "✅ 辅助包已安装: $1"
    else
        local apk
        apk=$(ls $2 2>/dev/null | head -1)
        if [ -z "$apk" ]; then
            echo "❌ 找不到 apk: $2（请确认已 npm install appium + 装好 uiautomator2 驱动）"
            exit 1
        fi
        echo "📦 安装辅助包 $1（华为机请在手机上点【继续安装】）..."
        if ! $ADB install -r -t "$apk"; then
            echo "❌ 安装失败: $1"
            echo "   华为机建议：开发者选项关闭「监控 ADB 安装应用」后重试"
            exit 1
        fi
    fi
}
echo "🔧 检查 Appium 辅助包..."
ensure_pkg io.appium.uiautomator2.server "$APK_BASE/appium-uiautomator2-server/apks/appium-uiautomator2-server-v*.apk"
ensure_pkg io.appium.uiautomator2.server.test "$APK_BASE/appium-uiautomator2-server/apks/appium-uiautomator2-server-debug-androidTest.apk"
ensure_pkg io.appium.settings "$APK_BASE/io.appium.settings/apks/settings_apk-debug.apk"

# 启动Appium服务器
echo "🚀 启动Appium服务器..."
echo "   服务器地址: http://127.0.0.1:4723"
echo "   按 Ctrl+C 停止服务器"
echo ""

appium --port 4723
