# -*- coding: UTF-8 -*-
"""
__Author__ = "BlueCestbon"
__Version__ = "2.0.0"
__Description__ = "大麦app抢票自动化 - 优化版"
__Created__ = 2025/09/13 19:27
"""

import os
import shutil
import subprocess
import time

from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from config import Config
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class DamaiBot:
    def __init__(self):
        self.config = Config.load_config()
        self.driver = None
        self.wait = None
        self._setup_driver()

    @staticmethod
    def _adb_path():
        """定位 adb：优先 PATH，其次 ANDROID_HOME/ANDROID_SDK_ROOT。"""
        found = shutil.which("adb")
        if found:
            return found
        for root in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT")):
            if root:
                candidate = os.path.join(root, "platform-tools", "adb")
                if os.path.isfile(candidate):
                    return candidate
        raise RuntimeError("找不到 adb，请设置 ANDROID_HOME 或把 platform-tools 加入 PATH")

    def _resolve_udid(self):
        """解析目标设备 udid：config 指定则用之，否则（auto/空）自动探测唯一连接设备。"""
        name = (self.config.device_name or "").strip()
        if name and name.lower() != "auto":
            return name
        out = subprocess.run([self._adb_path(), "devices"],
                             capture_output=True, text=True).stdout
        serials = [ln.split("\t")[0] for ln in out.splitlines()[1:]
                   if ln.strip().endswith("device")]
        if not serials:
            raise RuntimeError("未检测到已连接设备，请先用 `adb devices` 确认设备在线")
        if len(serials) > 1:
            raise RuntimeError(f"检测到多台设备 {serials}，请在 config.jsonc 的 device_name 指定其中一个")
        return serials[0]

    def _setup_driver(self):
        """初始化驱动配置"""
        udid = self._resolve_udid()
        print(f"目标设备: {udid}")
        capabilities = {
            "platformName": "Android",  # 操作系统
            "appium:udid": udid,  # 目标设备（auto 自动探测 / config 指定）
            "deviceName": udid,  # 信息性字段
            "appPackage": "cn.damai",  # app 包名
            "appActivity": ".launcher.splash.SplashMainActivity",  # app 启动 Activity
            "unicodeKeyboard": True,  # 支持 Unicode 输入
            "resetKeyboard": True,  # 隐藏键盘
            "noReset": True,  # 不重置 app
            "newCommandTimeout": 6000,  # 超时时间
            "automationName": "UiAutomator2",  # 使用 uiautomator2
            # 跳过每次建会话时对 uiautomator2 辅助服务端的检查/重装：
            # ① 抢票热路径不该做卸载重装（慢；且华为 EMUI 读不到已装版本号会反复卸载重装、卡安装弹窗）；
            # ② 辅助 apk 安装属"环境就绪"的一次性动作，由 start_appium.sh 幂等完成。
            # 前提：新设备首次使用前先跑一次 ./start_appium.sh（按需安装这三个辅助包）。
            "skipServerInstallation": True,
            "ignoreHiddenApiPolicyError": True,  # 忽略隐藏 API 策略错误
            "disableWindowAnimation": True,  # 禁用窗口动画
            # 优化性能配置
            "mjpegServerFramerate": 1,  # 降低截图帧率
            "shouldTerminateApp": False,
            "adbExecTimeout": 20000,
        }

        device_app_info = AppiumOptions()
        device_app_info.load_capabilities(capabilities)
        self.driver = webdriver.Remote(self.config.server_url, options=device_app_info)

        # 更激进的性能优化设置
        self.driver.update_settings({
            "waitForIdleTimeout": 0,  # 空闲时间，0 表示不等待，让 UIAutomator2 不等页面“空闲”再返回
            "actionAcknowledgmentTimeout": 0,  # 禁止等待动作确认
            "keyInjectionDelay": 0,  # 禁止输入延迟
            "waitForSelectorTimeout": 300,  # 从500减少到300ms
            "ignoreUnimportantViews": False,  # 保持false避免元素丢失
            "allowInvisibleElements": True,
            "enableNotificationListener": False,  # 禁用通知监听
        })

        # 极短的显式等待，抢票场景下速度优先
        self.wait = WebDriverWait(self.driver, 2)  # 从5秒减少到2秒

    def ultra_fast_click(self, by, value, timeout=1.5):
        """超快速点击 - 适合抢票场景"""
        try:
            # 直接查找并点击，不等待可点击状态
            el = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            # 使用坐标点击更快
            rect = el.rect
            x = rect['x'] + rect['width'] // 2
            y = rect['y'] + rect['height'] // 2
            self.driver.execute_script("mobile: clickGesture", {
                "x": x,
                "y": y,
                "duration": 50  # 极短点击时间
            })
            return True
        except TimeoutException:
            return False

    def ultra_batch_click(self, elements_info, timeout=2):
        """超快批量点击 - 带等待机制"""
        coordinates = []
        # 批量收集坐标，带超时等待
        for by, value in elements_info:
            try:
                # 等待元素出现
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                rect = el.rect
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                coordinates.append((x, y, value))
            except TimeoutException:
                print(f"超时未找到用户: {value}")
            except Exception as e:
                print(f"查找用户失败 {value}: {e}")
        print(f"成功找到 {len(coordinates)} 个用户")
        # 快速连续点击
        for i, (x, y, value) in enumerate(coordinates):
            self.driver.execute_script("mobile: clickGesture", {
                "x": x,
                "y": y,
                "duration": 30
            })
            if i < len(coordinates) - 1:
                time.sleep(0.01)
            print(f"点击用户: {value}")

    def smart_wait_and_click(self, by, value, backup_selectors=None, timeout=1.5):
        """智能等待和点击 - 支持备用选择器"""
        selectors = [(by, value)]
        if backup_selectors:
            selectors.extend(backup_selectors)

        for selector_by, selector_value in selectors:
            try:
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((selector_by, selector_value))
                )
                rect = el.rect
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y, "duration": 50})
                return True
            except TimeoutException:
                continue
        return False

    def run_ticket_grabbing(self):
        """执行抢票主流程"""
        try:
            print("开始抢票流程...")
            start_time = time.time()

            # 1. 城市选择 - 准备多个备选方案
            print("选择城市...")
            city_selectors = [
                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{self.config.city}")'),
                (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{self.config.city}")'),
                (By.XPATH, f'//*[@text="{self.config.city}"]')
            ]
            if not self.smart_wait_and_click(*city_selectors[0], city_selectors[1:]):
                print("城市选择失败")
                return False

            # 2. 点击预约按钮 - 多种可能的按钮文本
            print("点击预约按钮...")
            book_selectors = [
                (By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*预约.*|.*购买.*|.*立即.*")'),
                (By.XPATH, '//*[contains(@text,"预约") or contains(@text,"购买")]')
            ]
            if not self.smart_wait_and_click(*book_selectors[0], book_selectors[1:]):
                print("预约按钮点击失败")
                return False

            # 3. 票价选择 - 优化查找逻辑
            print("选择票价...")
            try:
                # 直接尝试点击，不等待容器，实际每次都失败，只能等待
                price_container = self.driver.find_element(By.ID, 'cn.damai:id/project_detail_perform_price_flowlayout')
                # 在容器内找第 price_index 个可点击的 FrameLayout（票价 text 为空被隐藏，只能靠索引）
                target_price = price_container.find_element(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    f'new UiSelector().className("android.widget.FrameLayout").index({self.config.price_index}).clickable(true)'
                )
                self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})
            except Exception as e:
                print(f"票价选择失败，启动备用方案: {e}")
                # 备用方案
                # 先找到大容器
                price_container = self.wait.until(
                    EC.presence_of_element_located((By.ID, 'cn.damai:id/project_detail_perform_price_flowlayout')))
                # 在容器内找 index=1 且 clickable="true" 的 FrameLayout【因为799元的票价是排在第二的，但是page里text是空的被隐藏了】
                target_price = price_container.find_element(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    f'new UiSelector().className("android.widget.FrameLayout").index({self.config.price_index}).clickable(true)'
                )
                self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})

            # 4. 数量选择
            print("选择数量...")
            if self.driver.find_elements(by=By.ID, value='layout_num'):
                clicks_needed = len(self.config.users) - 1
                if clicks_needed > 0:
                    try:
                        plus_button = self.driver.find_element(By.ID, 'img_jia')
                        for i in range(clicks_needed):
                            rect = plus_button.rect
                            x = rect['x'] + rect['width'] // 2
                            y = rect['y'] + rect['height'] // 2
                            self.driver.execute_script("mobile: clickGesture", {
                                "x": x,
                                "y": y,
                                "duration": 50
                            })
                            time.sleep(0.02)
                    except Exception as e:
                        print(f"快速点击加号失败: {e}")

            # 5. 确定购买
            print("确定购买...")
            if not self.ultra_fast_click(By.ID, "btn_buy_view"):
                # 备用按钮文本
                self.ultra_fast_click(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*确定.*|.*购买.*")')

            # 6. 批量选择用户
            print("选择用户...")
            user_clicks = [(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{user}")') for user in
                           self.config.users]
            self.ultra_batch_click(user_clicks)

            # 7. 提交订单（受 if_commit_order 开关控制：默认 False，调试时不真实下单）
            if self.config.if_commit_order:
                print("提交订单...")
                submit_selectors = [
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*提交.*|.*确认.*")'),
                    (By.XPATH, '//*[contains(@text,"提交")]')
                ]
                self.smart_wait_and_click(*submit_selectors[0], submit_selectors[1:])
            else:
                print("已跳过提交（if_commit_order=False，未真实下单）")

            end_time = time.time()
            print(f"抢票流程完成，耗时: {end_time - start_time:.2f}秒")
            return True

        except Exception as e:
            print(f"抢票过程发生错误: {e}")
            return False
        finally:
            time.sleep(1)  # 给最后的操作一点时间
            self.driver.quit()

    def run_with_retry(self, max_retries=3):
        """带重试机制的抢票"""
        for attempt in range(max_retries):
            print(f"第 {attempt + 1} 次尝试...")
            if self.run_ticket_grabbing():
                print("抢票成功！")
                return True
            else:
                print(f"第 {attempt + 1} 次尝试失败")
                if attempt < max_retries - 1:
                    print("2秒后重试...")
                    time.sleep(2)
                    # 重新初始化驱动
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self._setup_driver()

        print("所有尝试均失败")
        return False


# 使用示例
if __name__ == "__main__":
    bot = DamaiBot()
    bot.run_with_retry(max_retries=3)
