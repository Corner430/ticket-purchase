# TODO —— 大麦抢票(逐条推进)

> 可执行待办 + 已知约束(findings)。
> 原则:极简、不过度设计、就绪由用户自己保证、不绕过风控。
> 最后更新:2026-10-28

---

## A. "代码优化"回退评估

- [x] **A1. 回退 `driver_factory.py` + `_setup_driver` 的 create_driver 改造** —— 已完全回退
  - `_setup_driver` 恢复为原始裸 `webdriver.Remote` + `update_settings`;删除 `driver_factory.py`。
- [x] **A2. 删除 `connectivity_check.py`** —— 已删除
- [x] **A3. 恢复 `webdriver` / `AppiumOptions` 导入** —— 已随 A1 恢复
- [x] **A4. 设备识别改为运行时自动探测**:`platform_version` 删除(UiAutomator2 不需要);`device_name` 默认 `"auto"`,启动时经 `adb devices` 探测唯一设备(多设备才需在 config 指定)。彻底消除设备相关的配置过期问题。

> 回退后主程序先回到原作者形态;其后又做了设备运行时自动探测(_resolve_udid/_adb_path、appium:udid、删除 platformVersion),故现已不完全等同原版。

## B. 正确性修正(待办)

- [ ] **B1. 去掉 `run_with_retry` 的"热路径重连"反模式**
  - 现状:失败后 `driver.quit()` + `_setup_driver()` 重建 + `sleep(2)` 整体重来 3 次——抢票语境近乎放弃。
  - 目标:连接在预备期一次建好;抢票热路径**只前进、不重连、不 sleep**。
  - 建议:拆 `prepare()`(建会话,用户保证页面就绪)/ `grab()`(纯点击序列)。
  - 原则:**准备 ≠ 抢**。预备期可慢/可重试;抢票热路径必须零重连、零退避、零 sleep——那一刻 session 必须已是热的,此刻才需重连=本单已输。

## B2. Appium 辅助包安装:每会话重装 → 一次就绪(已解决)

- [x] **根因**:Appium 在每次 `webdriver.Remote()` 建会话时检查/重装其 uiautomator2 辅助服务端(io.appium.uiautomator2.server/.server.test/.settings)。华为 EMUI 读不到已装 server 版本号(`Cannot read version codes`)→ 判定 unknown → 卸载重装 → 撞 EMUI 安装弹窗 120s 超时。安装被错误地放进了抢票热路径。
- [x] **方案**:`damai_app_v2.py` 设 `skipServerInstallation: True`(热路径不装);安装挪到就绪阶段——`start_appium.sh` 幂等 `ensure_pkg`(先查 pm list,有就跳过,缺才 `adb install -r -t`)。新设备首次跑一次 start_appium.sh 即就绪。
- [x] 华为备注:安装时手机点「继续安装」;建议关开发者选项「监控 ADB 安装应用」。

## B3. 选择器已随大麦改版大面积失效(待办,脚本可用前必须修)

- [ ] **真机实测(2026-10-28,理查德·克莱德曼音乐会详情页)核对结果**:
  - ✅ `trade_project_detail_purchase_status_bar_container_fl`(底部购买栏)仍匹配
  - ❌ `project_detail_perform_price_flowlayout`(票价容器)失效(0 匹配)
  - ❌ `layout_num`(数量)、`img_jia`(加号)、`btn_buy_view`(确定购买)全部失效
- [ ] **结论**:`damai_app_v2.py` 第 3~5 步(选票价/加数量/确定购买)的选择器已过时,真机上点不到,必须重抓更新;第 1/2/6/7 步(城市/购买按钮/观演人/提交)也需在真实购买流程上复核。
- [ ] **怎么抓**:需要一个**当前可购买(按钮"立即购买"亮着)**的演出,点进购买流程后用 Appium 读出真实的票价面板/数量/确定/提交控件 id;理查德这场是预约制/未开售、按钮灰,展不开购买面板,不适合。
- [ ] 顺带在真实票价列表上定出目标票档的 `price_index`。
- [ ] 备注:这是"选择器随 App 版本失效"的通病,本次真机实锤;更新后建议在注释标注抓取日期与大麦版本。

## C. 配置 / 启动脚本(待办)

- [x] **C1. 启动脚本硬编码路径 —— 已修**
  - `start_appium.sh` / `start_ticket_grabbing.sh` / `check_environment.sh` 的 `/Users/shengwang/...` 改为 `${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}`;抢票脚本 python 改用项目 `.venv`;模拟器提示改 `damai_test`。

## D. 本期明确"不做"(决策记录)

- [x] **D1. 业务门控 preflight —— 不做**。就绪(已登录/停详情页/观演人配好)由用户自己保证。
- [x] **D2. 蹲守(poll-until-clickable)—— 不做**。采用"手动掐点"(模式 A)。
  - 备注:**v2 无蹲守**(运行即跑一遍 + 失败重试 3 次);**v1 有**(while 循环轮询按钮文字 + 下拉刷新)。未来若需要,可借鉴 v1 或在 `grab()` 开头加几行 poll 循环。
- [x] **D3. DDD —— 否决**。单一用途自动化脚本,无复杂业务领域,上 DDD = 过度设计。回退后结构为 `config.py` + `DamaiBot`(damai_app_v2),已足够。

## E. 操作模式

- **模式 A:手动掐点**。环境(模拟器/Appium)提前起好保温;开售瞬间人工运行 `damai_app_v2.py`。

## F. v1(`damai_app.py`)中值得 v2 借鉴的点(待评估)

> v1 已删除,以下是删除前从中提炼的、v2 缺失或可加固的能力。之后逐条评估是否补进 v2。

- [x] **F1. `if_commit_order` 自动提交开关(安全)—— 已实现**
  - 已加回 `config.if_commit_order`(默认 **false**),v2 第 7 步提交受其控制;false 时跳过提交、不真实下单。
- [ ] **F2. 蹲守循环(到点自动抢)**
  - v1:`while` 轮询底部按钮文字,见"立即购买"才下手,否则 `swipe` 下拉刷新重试。
  - 对应 D2(本期不做手动掐点);若将来要"自动打响",这是现成思路。
- [ ] **F3. App 内搜索导航**
  - v1:点搜索框→输入 `keyword`→点第一个搜索结果→进详情页(用到 `config.keyword`)。
  - v2 移除了此步(需人工导航到详情页)。补回可减少手动准备。
- [ ] **F4. 场次/日期选择**
  - v1:按 `config.date` 在 `tv_tour_time` / `project_detail_perform_flowlayout` 选场次(用到 `config.date`)。
  - v2 未显式选日期。多场次演出需要。
- [ ] **F5. 预约制流程**
  - v1:处理"预约抢票"/"已预约"分支;v2 只做直接购买。预约制演出需要。
- [ ] **F6. 观演人选择的备选策略**
  - v1:定位"身份证"元素→取 parent→再匹配用户名点击;v2 用纯 text 匹配。可作为加固/备选选择器。

> 注:F1/F3/F4 若实现,需把对应 config 字段(if_commit_order / keyword / date)重新加回 `config.py` 与 `config.jsonc`(本次死代码清理时已移除)。

## G. 已清理(死代码)—— 记录

- [x] 删除 `damai_app.py`(v1,已被 v2 取代,无脚本引用)
- [x] 删除 v2 中未调用的 `batch_click()` 方法
- [x] 删除 v2 中未使用的 `NoSuchElementException` 导入
- [x] 删除 v2 中 6 行注释掉的旧代码
- [x] 精简 config:移除 keyword / date / price;if_commit_order 因安全开关(F1)加回;**新增 device_name(默认 auto,运行时经 adb 探测);platformVersion 已删除(UiAutomator2 不需要)**
- [x] 删除死文件 `damai_appium/config.json`(旧 schema、无代码读取)+ 清理 .gitignore 中无意义的 `config.json` 规则

---

# 已知约束 / Findings(原"调试问题记录",合并至此)

> 这些是客观发现与约束,不一定可"解决",作为背景认知。

## 🔴 1. 登录触发阿里风控「访问被拒绝」
模拟器环境被阿里安全 SDK 识别为高风险直接拒绝(非可解滑块)。模拟器无法完成登录。**不绕过**。出路 = 真机 + 已登录。

## 🔴 2. 热门票「秒罄」/ 开售按钮不可点
顶级热票(如凤凰传奇鸟巢)可点窗口极短;模拟器 + 慢网 + 未登录几乎不可能抓到。客观限制,非代码可解。

## 🟡 3. adb「device offline」间歇性掉线
adb server ↔ 模拟器传输层瞬时竞态。**缓解(手动)**:`adb reconnect offline` + 重跑;彻底则 `adb kill-server && adb start-server`。
- 回退后代码层无重试兜底(见 A1)。若后续觉得频繁,可在 `prepare()` 加几行轻量重试(**不要连接池**,adb 单例 server 池化加剧抖动)。

## 🟡 4. FLAG_SECURE 截屏/控件树全黑
登录页/安全验证页/详情页设 FLAG_SECURE,`screencap` 得 0 字节/黑屏。绕行:用 Appium 读 page source / 元素属性;人在模拟器窗口肉眼可见。

## 🟡 5. 详情页 uiautomator dump 拿不到 idle
详情页持续动画,`adb shell uiautomator dump` 报 "could not get idle state"。解法:用 Appium 且设 `waitForIdleTimeout: 0`(脚本本就这么配)。

## 环境基线(供复现)
- SDK:`/opt/homebrew/share/android-commandlinetools`(adb 1.0.41 / emulator 37.2.12 / platform-35 / arm64-v8a)
- 环境变量:`~/.zshrc`(标记 `damai-ticket android env`)
- AVD:`damai_test`(Pixel 6 / Android 15 / API 35)
- Appium 3.9.0(项目 node_modules)+ uiautomator2 8.7.2;Python `.venv`(Appium-Python-Client 6.0.9 + selenium 4.51.0)

## 核心结论
模拟器 = 学流程/练选择器/读脚本;实战需真机 + 已登录 + 稳定网络,热门票仍高度不确定。**不绕过风控。**
客户端点击再快也绕不过服务端瓶颈(风控、排队、库存);自动化只优化"我们可控的客户端延迟"那一小段。
