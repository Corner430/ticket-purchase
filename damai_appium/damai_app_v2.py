# -*- coding: UTF-8 -*-
"""
__Author__ = "BlueCestbon / refactor"
__Version__ = "3.0.0"
__Description__ = "大麦 App 抢票自动化 - 状态驱动版"
__Created__ = 2025/09/13 19:27

设计见 doc/抢票流程与状态机.md:
- prepare(): 预备期（可慢）——建会话、识别当前状态、关实名弹窗、预解析购买栏坐标。
- grab(): 热路径——从当前页推进到支付；零 page_source、零 sleep 重试、零重连，只前进。
两条路（未预约全流程 / 已预约快路径）在 SKU 页/订单页自然汇合：
脚本只认"当前在哪个 Activity，往支付推进"，而非写死 1→2→…→7 线性剧本。
"""
import datetime
import os
import shutil
import subprocess
import re
import time

from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from config import Config
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ID = "cn.damai:id/"
# Activity 关键字 → 状态
DETAIL_ACT = "ProjectDetailActivity"
SKU_ACT = "NcovSkuActivity"
ORDER_ACT = "DmOrderActivity"
RISK_ACT = "fc.ui.ContainerActivity"   # 阿里风控人机校验
PAY_PKG = "com.eg.android.AlipayGphone"  # 支付宝


class DamaiBot:
    def __init__(self):
        self.config = Config.load_config()
        self.driver = None
        self._buy_bar_xy = None
        self._logf = None
        self._open_log()
        self._setup_driver()

    def _open_log(self):
        """日志落盘到 logs/抢票_<时间>.log(不影响 stdout)。"""
        try:
            # 锚定到脚本自身目录（damai_appium/logs/），与 .gitignore 严格对齐，
            # 不受运行时 CWD 影响（避免日志落到仓库根被误提交）。
            logdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            os.makedirs(logdir, exist_ok=True)
            path = os.path.join(
                logdir, datetime.datetime.now().strftime("抢票_%Y%m%d_%H%M%S.log"))
            self._logf = open(path, "a", encoding="utf-8")
            self._log(f"=== 日志文件: {path} ===")
        except OSError:
            self._logf = None

    def _log(self, msg):
        """带墙钟时间戳打印,同时落盘。"""
        line = f"[{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}"
        print(line, flush=True)
        if self._logf is not None:
            try:
                self._logf.write(line + "\n")
                self._logf.flush()
            except OSError:
                pass

    # ---------------- 设备 / 驱动 ----------------
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
        """config 指定则用之，否则（auto/空）自动探测唯一连接设备。"""
        name = (self.config.device_name or "").strip()
        if name and name.lower() != "auto":
            return name
        out = subprocess.run([self._adb_path(), "devices"],
                             capture_output=True, text=True, timeout=5).stdout
        serials = [ln.split("\t")[0] for ln in out.splitlines()[1:]
                   if ln.strip().endswith("device")]
        if not serials:
            raise RuntimeError("未检测到已连接设备，请先用 `adb devices` 确认设备在线")
        if len(serials) > 1:
            raise RuntimeError(f"检测到多台设备 {serials}，请在 config.jsonc 的 device_name 指定其中一个")
        return serials[0]

    def _setup_driver(self):
        udid = self._resolve_udid()
        self._udid = udid
        self._log(f"目标设备: {udid}")
        capabilities = {
            "platformName": "Android",
            "appium:udid": udid,
            "deviceName": udid,
            "appPackage": "cn.damai",
            "appActivity": ".launcher.splash.SplashMainActivity",
            "noReset": True,
            "autoLaunch": False,  # 不重启 app，附着当前界面（用户已导航到目标演出）
            "newCommandTimeout": 6000,
            "automationName": "UiAutomator2",
            # 跳过每次建会话重装 uiautomator2 辅助服务端（安装属就绪，由 start_appium.sh 幂等完成）
            "skipServerInstallation": True,
            "skipDeviceInitialization": True,
            "ignoreHiddenApiPolicyError": True,
            "disableWindowAnimation": True,
            "mjpegServerFramerate": 1,
            "shouldTerminateApp": False,
            "adbExecTimeout": 20000,
        }
        options = AppiumOptions()
        options.load_capabilities(capabilities)
        self.driver = webdriver.Remote(self.config.server_url, options=options)
        # 性能优化：不等页面空闲（详情页有动画会一直不空闲）、极短选择器超时
        self.driver.update_settings({
            "waitForIdleTimeout": 0,
            "actionAcknowledgmentTimeout": 0,
            "keyInjectionDelay": 0,
            "waitForSelectorTimeout": 300,
            "allowInvisibleElements": True,
            "enableNotificationListener": False,
        })

    # ---------------- 工具 ----------------
    def _activity(self):
        try:
            return self.driver.current_activity or ""
        except WebDriverException:
            return ""

    def _foreground(self):
        """用 adb 读真实前台 'package/activity'(driver 读外部 app 如支付宝会 stale/抛错)。"""
        try:
            out = subprocess.run(
                [self._adb_path(), "-s", self._udid, "shell", "dumpsys", "window"],
                capture_output=True, text=True, timeout=4).stdout
        except (subprocess.TimeoutExpired, OSError):
            return ""
        # 跨 ROM 焦点字段可能是 mCurrentFocus 或 mFocusedApp;依次尝试
        for pat in (r"mCurrentFocus=.*\s+(\S+)/(\S+)[\}\s]",
                    r"mFocusedApp=.*\s+(\S+)/(\S+)[\}\s]"):
            m = re.search(pat, out)
            if m:
                return m.group(1) + "/" + m.group(2)
        return ""  # 解析不出 → _state 返回 unknown;排查时打印本函数原始 out

    def _state(self):
        """读真实前台判状态(adb 可靠,不受 session 所属 app 限制)。"""
        fg = self._foreground()
        if PAY_PKG in fg:
            return "pay"
        if RISK_ACT in fg:
            return "risk"
        if ORDER_ACT in fg:
            return "order"
        if SKU_ACT in fg:
            return "sku"
        if DETAIL_ACT in fg:
            return "detail"
        return "unknown"

    def _tap(self, x, y, duration=40):
        self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y, "duration": duration})

    def _tap_el(self, el, duration=40):
        self.driver.execute_script("mobile: clickGesture", {"elementId": el.id, "duration": duration})

    def _find(self, by, value, timeout=1.5):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value)))
        except TimeoutException:
            return None

    def _wait_state(self, target, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            if self._state() == target:
                return True
            time.sleep(0.15)
        return False

    # ---------------- 预备期（可慢） ----------------
    def prepare(self):
        """开抢前：识别状态、关实名弹窗、预解析购买栏坐标。"""
        st = self._state()
        self._log(f"[prepare] 当前状态: {st}")
        if st == "detail":
            self._dismiss_realname_dialog()
            bar = self._find(By.ID, ID + "trade_project_detail_purchase_status_bar_container_fl", 2)
            if bar:
                r = bar.rect
                self._buy_bar_xy = (r["x"] + r["width"] // 2, r["y"] + r["height"] // 2)
                self._log(f"[prepare] 购买栏预解析坐标: {self._buy_bar_xy}")
            else:
                self._log("[prepare] 警告：未找到购买栏（可能未开售/有弹窗/布局变化）")
        return st

    def _dismiss_realname_dialog(self):
        """实名制观演说明弹窗 → 点'知道了'关闭（预选观演人是 H5，由用户手动就绪）。"""
        btn = self.driver.find_elements(By.ID, ID + "damai_theme_dialog_cancel_btn")
        if btn:
            self._tap_el(btn[0])
            time.sleep(0.3)
            self._log("[prepare] 关闭实名制说明弹窗")

    # ---------------- 热路径（开售瞬间，只前进） ----------------
    def grab(self):
        """从当前页推进到支付。零重连、零 sleep 重试。分段打点记录时延。"""
        start = time.time()
        marks = []

        def mark(label):
            marks.append((label, time.time() - start))

        if self._state() == "detail":
            xy = self._buy_bar_xy
            if xy is None:
                bar = self._find(By.ID, ID + "trade_project_detail_purchase_status_bar_container_fl", 1)
                if not bar:
                    self._log("[grab] 无购买栏，放弃")
                    return False
                r = bar.rect
                xy = (r["x"] + r["width"] // 2, r["y"] + r["height"] // 2)
            self._tap(*xy)
            self._wait_state("sku", 5)
            mark("detail→sku")

        if self._state() == "sku":
            if not self._select_sku():
                self._log("[grab] 选票/确定失败（可能缺货或未选全）")
                return False
            self._wait_state("order", 5)
            mark("sku→order")

        if self._state() == "order":
            self._select_viewers()
            mark("勾观演人")
            if self.config.if_commit_order:
                result = self._submit_phase()
                mark(f"提交阶段({result})")
            else:
                self._log("[grab] if_commit_order=False，停在订单页（未提交、未锁票）")
                self._print_marks(marks, start)
                return True

        st = self._state()
        self._print_marks(marks, start)
        self._log(f"[grab] 结束状态: {st}，总耗时 {time.time() - start:.2f}s")
        if st == "risk":
            self._log("[grab] ★到阿里风控人机校验，请在手机上人工完成验证（脚本不绕过）")
        elif st == "pay":
            self._log("[grab] ★到支付页，票已锁定；请在手机上人工支付")
        return st in ("risk", "pay", "order")

    def _price_selected(self):
        """票档是否已选上：tv_price 非 0/空 即为已选（比'确定键 enabled'可靠，
        后者在部分演出上默认就是 true）。"""
        # 依据：SKU 页仅一个 tv_price（底部总价显示）；取 [0]。若大麦改版出现多个需复核。
        els = self.driver.find_elements(By.ID, ID + "tv_price")
        if not els:
            return False
        txt = (els[0].text or "").strip()
        return txt not in ("", "0")

    def _confirm(self):
        btn = self._find(By.ID, ID + "btn_buy_view", 2)
        if btn and btn.get_attribute("enabled") == "true":
            self._tap_el(btn)
            return True
        return False

    def _select_sku(self):
        """选场次 + 票档 → 确定。已预约/已勾选（tv_price 已非 0）时直接确定。"""
        # 已就绪（如已预约，大麦自动勾选票档，tv_price 已非 0）→ 直接确定
        if self._price_selected():
            return self._confirm()
        # 未预约：选场次[perform_index]
        perfs = self.driver.find_elements(By.ID, ID + "ll_perform_item")
        if perfs and 0 <= self.config.perform_index < len(perfs):
            self._tap_el(perfs[self.config.perform_index])
            time.sleep(0.12)
        # 选票档[price_index]（价格文字为空，只能靠索引）
        cont = self._find(By.ID, ID + "project_detail_perform_price_flowlayout", 2)
        if cont:
            try:
                tier = cont.find_element(
                    AppiumBy.ANDROID_UIAUTOMATOR,
                    f'new UiSelector().className("android.widget.FrameLayout")'
                    f'.index({self.config.price_index}).clickable(true)')
                self._tap_el(tier)
            except WebDriverException as e:
                self._log(f"[grab] 票档选择异常: {e}")
        # 等票档真正选上（tv_price 变非 0），最多 ~1s
        for _ in range(10):
            if self._price_selected():
                break
            time.sleep(0.1)
        if not self._price_selected():
            self._log("[grab] 票档未选上（可能缺货/price_index 越界/索引错）")
            return False
        return self._confirm()

    def _select_viewers(self):
        """实名演出:按 config.users 勾选观演人 checkbox。
        非实名/无观演人区→自动跳过;已勾→跳过;勾完回读校验,没勾上重试。"""
        users = self.config.users or []
        if not users:
            return
        # 等观演人区渲染(订单页刚到可能还没出)
        deadline = time.time() + 2.0
        while time.time() < deadline and not self.driver.find_elements(By.ID, ID + "checkbox"):
            time.sleep(0.1)
        if not self.driver.find_elements(By.ID, ID + "checkbox"):
            self._log("[grab] 无观演人区(非实名),跳过选观演人")
            return
        for name in users:
            self._check_viewer(name)

    def _check_viewer(self, name, retries=3):
        """勾上某观演人:按姓名行找最近 checkbox,未勾则点,回读校验,失败重试。"""
        for _ in range(retries):
            rows = self.driver.find_elements(
                AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{name}")')
            if not rows:
                self._log(f"[grab] 未找到观演人: {name}")
                return False
            ry = rows[0].rect["y"]
            cbs = self.driver.find_elements(By.ID, ID + "checkbox")
            best, best_d = None, 99999
            for cb in cbs:
                d = abs(cb.rect["y"] - ry)
                if d < best_d:
                    best_d, best = d, cb
            if best is None or best_d >= 120:
                self._log(f"[grab] 未匹配到 {name} 的勾选框")
                return False
            if best.get_attribute("checked") == "true":
                self._log(f"[grab] 观演人已勾选: {name}")
                return True
            self._tap_el(best)
            time.sleep(0.25)  # 等勾选态刷新再校验
        self._log(f"[grab] ⚠️ 观演人 {name} 勾选未确认(重试耗尽)")
        return False

    def _tap_submit(self):
        """点'立即提交'（按元素，不盲点坐标，避免误触）。无按钮返回 False。"""
        els = self.driver.find_elements(
            AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")')
        if els:
            self._tap_el(els[0])
            return True
        return False

    def _submit_phase(self, timeout=60.0):
        """提交阶段的'重点提交'重试（非重连）:
        - 反复点'立即提交'冲库存;
        - 处理'抢票人数太多/继续尝试'弹窗(自动点继续尝试);
        - 遇阿里风控 → 提示并**等待人工滑动**(不退出),过后回订单页自动续冲;
        - 命中支付页 → 返回 'pay'(锁票成功)。
        抢票正确的热路径重试:只重发提交动作,绝不重连/重建会话。
        """
        self._log("[grab] 进入提交阶段(冲提交;遇风控请在手机上滑动验证)")
        deadline = time.time() + timeout
        risk_notified = False
        while time.time() < deadline:
            try:
                st = self._state()
                if st == "pay":
                    self._log("[grab] ★支付页,锁票成功"); return "pay"
                if st == "risk":
                    if not risk_notified:
                        self._log("[grab] ★阿里风控:请在手机上滑动完成验证(脚本等待中,最多 %ds)..." % int(timeout))
                        risk_notified = True
                    time.sleep(0.5)
                    continue
                if st == "order":
                    risk_notified = False
                    # '抢票人数太多啦/继续尝试'弹窗 → 自动继续尝试
                    dlg = self.driver.find_elements(By.ID, ID + "damai_theme_dialog_confirm_btn")
                    if dlg and any(k in (dlg[0].text or "") for k in ("继续", "尝试")):  # 不含"确定"（避免误点缺货登记等确认弹窗）
                        self._tap_el(dlg[0]); continue
                    # 无拦截弹窗 → 重发'立即提交'(有按钮才点;无按钮=处理中,等)
                    if not self._tap_submit():
                        time.sleep(0.15)
                    continue
                time.sleep(0.1)
            except WebDriverException:
                # 风控 WebView 期间查询常 socket hang up:稍等后重判
                time.sleep(0.4)
                continue
        try:
            return self._state()
        except WebDriverException:
            return "unknown"

    def _print_marks(self, marks, start):
        if not marks:
            return
        prev = 0.0
        self._log("[grab] 分段时延:")
        for label, t in marks:
            self._log(f"    {label}  +{(t - prev) * 1000:.0f}ms  (累计 {t * 1000:.0f}ms)")
            prev = t

    def run(self):
        self.prepare()
        return self.grab()


if __name__ == "__main__":
    bot = DamaiBot()
    bot.run()
