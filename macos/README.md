# 学习通自动助手 · macOS 版

只处理老师布置的虚拟题库作业 / 课程任务点；正式计分考试、补考、竞赛卷一律不代答。
不代签到；不绕过人脸识别、弹题、拖动验证、验证码；不索要、不保存账号密码。

本脚本只做机械层：巡检、按外部传入的答案填表、提交门判定、视频任务点播放、
去重状态、报告、定时、登录态检查。脚本本身不解题、不调用任何外部解题服务，
答案由操作者用的智能体另外提供（见下面「答案从哪里来」）。

## 铁律（违反就停手）

1. 只处理老师布置的虚拟题库作业 / 课程任务点；正式计分考试、补考、竞赛卷一律不代答。
2. **提交门**：只有一份作业全部题目都有把握答案（不确定数 = 0）时才自动点提交；
   只要有 1 道不确定，就只点「暂时保存」，并在报告里列出不确定题号，绝不提交半份作业。
   提交前必须重载页面核对答案已保留。
3. 不代签到；不绕过人脸识别、弹题、拖动验证、验证码；平台要求人工确认时立刻停下。
4. 不索要、不保存账号密码，登录由用户本人在浏览器里完成。

## 五分钟上手

1. 双击 `00_安装依赖.command`（找 Python3 → 装 playwright → 装浏览器驱动 → 跑自测）。
   首次双击 `.command` 若提示「无法打开，因为无法验证开发者」，右键点它 →「打开」即可；
   或在终端跑 `chmod +x *.command *.sh`（权限说明见下面「启动器」）。
2. 把仓库根的 `config.example.py` 复制为 `config.py`，填入你自己的课程号
   （courseid/clazzid/cpi 在学习通课程页 URL 里找，见仓库根 README「填你自己的课程信息」）。
3. 双击 `1_登录.command`，自己扫码登录学习通，勾「下次自动登录」。
4. 双击 `2_巡检.command`，确认三门课的作业和任务点能读到。
5. 按下面「答案从哪里来」准备好答案文件（`~/.cxauto/answers.json`），
   再双击 `3_填答.command`：全部有把握才提交，有不确定只暂时保存。
6. 需要长期值守：用 launchd 每小时跑一轮（见下面「定时方法」），或双击 `5_值守.command` 前台跑。

## 答案从哪里来（必读）

脚本不管解题，答案要你先准备好，再交给脚本。做法：

1. 用你用的智能体答题：比如用仓库 `doubao/` 下的豆包提示词，让豆包按题做答；
   也可以用你自己的其他答题办法。答题这一步完全在脚本之外。
2. 把答案写进 JSON 文件，格式（题号为键）：
   ```json
   {
     "1": "B",
     "2": {"answer": "AB", "certain": true},
     "3": {"answer": "对", "certain": true}
   }
   ```
   - `"1": "B"`：第 1 题有把握，答案 B。
   - `certain: true`：有把握；没把握的题不要写进文件，或写 `"certain": false`。
   - 没写进文件的题脚本判不确定、留空，不猜。
3. 把文件放到 `~/.cxauto/answers.json`（默认位置），再双击 `3_填答.command`，
   它检测到这个文件会自动用它填答；或在终端指定别的路径：
   ```bash
   python3 do_homework.py --answers /path/to/answers.json
   ```
4. 不给 `--answers`（且默认文件不存在）时，脚本只做巡检与报告，不填题、不提交，
   每份作业在报告里记 `awaiting_answers`（「待外部提供答案」）。

答案文件放在本机数据目录（`~/.cxauto/answers.json`），不在仓库里，不进 git。

## 每个启动器的作用

| 启动器 | 作用 |
| --- | --- |
| `00_安装依赖.command` / `.sh` | 找 Python3 → `pip install playwright` → 装 Chromium / msedge 驱动 → 跑自测 |
| `1_登录.command` | 扫码登录（勾「下次自动登录」），登录态进 `~/.cxauto/browser_profile` |
| `2_巡检.command` | 只读巡检三门课 + 心理课任务点，不作答、不提交 |
| `3_填答.command` | 巡检 → 按答案文件填答 → 提交门 → 报告；无答案文件时只巡检与报告 |
| `4_心理课视频.command` | 心理课视频：原速、页面静音，96% 停，复核任务点 |
| `5_值守.command` | 值守循环：每小时一轮巡检 → 填答 → 播放（前台跑，Ctrl+C 停） |
| `6_自测.command` | 不登录、不联网，mock 自测（提交门 / 答案提供方 / 状态去重 / macOS 配置） |

`.command` 是双击入口（转调同名 `.sh`，逻辑只在 `.sh` 里一份）；
`.sh` 可在终端直接跑。刚拷到 Mac 上双击没反应时，先在终端进本目录跑：

```bash
chmod +x *.command *.sh
```

若 macOS 提示「无法验证开发者」，右键点击 `.command` →「打开」；
仍被拦时可跑 `xattr -d com.apple.quarantine *.command` 再双击。

## 数据目录

默认 `~/.cxauto`（即 `/Users/<用户名>/.cxauto`，可用环境变量 `CX_DATA_DIR` 改）：

| 位置 | 内容 |
| --- | --- |
| `browser_profile/` | 浏览器档案（登录态在这里；Windows 版叫 `edge_profile`） |
| `answers.json` | 答案文件（默认位置，见「答案从哪里来」） |
| `state.json` | 已完成作业 / 视频状态（四个列表） |
| `scan.json` | 最近一次巡检结果 |
| `reports/` | 每轮 CSV 明细 |
| `logs/run.log`、`logs/summary.jsonl` | 运行日志 / 每轮结论 |
| `每日检查记录.md` | 有新增 / 异常时才追加的检查记录 |
| `shots/` | 异常截图 |

电话、邮箱、密码、cookie、登录态绝不进仓库；任何凭证只放本机数据目录。
`config.py` 只放本机，绝不提交（已被仓库根 `.gitignore` 覆盖）。

## 浏览器：Edge 优先，未装回退自带 Chromium

- 本机装了 Microsoft Edge for Mac（`/Applications/Microsoft Edge.app`）时，
  用 Edge（`channel="msedge"`）跑，登录态与你在用的 Edge 习惯一致。
- 没装 Edge 时自动回退到 Playwright 自带 Chromium（不装 Edge 也能跑），
  启动时会打印一行提示；想用 Edge 请先安装 Edge for Mac 再跑。
- `config.py` 里 `HEADLESS` 默认 `1`（无头）；登录那一步固定有头，方便扫码。

## 定时方法

### 方法一：launchd（推荐，macOS 原生）

```bash
cp ~/workspace/your_files/chaoxing-auto/macos/launchd/com.cxauto.watch.plist \
   ~/Library/LaunchAgents/com.cxauto.watch.plist
launchctl load ~/Library/LaunchAgents/com.cxauto.watch.plist
```

每小时跑一轮 `watch.py --once`。停止：

```bash
launchctl unload ~/Library/LaunchAgents/com.cxauto.watch.plist
```

查看是否在跑：`launchctl list | grep cxauto`；日志在 `~/.cxauto/logs/run.log`。
如仓库不在 `~/workspace/your_files/chaoxing-auto`，改 plist 里 `cd` 的路径。
要在定时轮里自动填答，把 plist 的命令改成：

```bash
cd ~/workspace/your_files/chaoxing-auto/macos && python3 watch.py --once --answers ~/.cxauto/answers.json
```

### 方法二：crontab（一行）

```cron
0 * * * * cd ~/workspace/your_files/chaoxing-auto/macos && /usr/bin/python3 watch.py --once >> ~/.cxauto/logs/cron.log 2>&1
```

加答案透传：`watch.py --once --answers ~/.cxauto/answers.json`。
注意 cron 环境变量极少，`python3` 请写绝对路径（`which python3` 查；
Homebrew 装的一般是 `/opt/homebrew/bin/python3`，不是 `/usr/bin/python3`）。

## 通知

关键异常才弹 macOS 通知（`osascript`）：登录失效、提交状态无法确认、
视频未计入、单轮超时。正常轮次静默，只写日志（`~/.cxauto/logs/run.log`）。

## FAQ

**登录失效（提示请先跑 1_登录.command）**
重新双击 `1_登录.command` 扫码登录，勾「下次自动登录」。登录态过期是正常的，
不要把账号密码告诉任何人、不要写进任何文件。

**没装 Edge，提示回退 Chromium**
正常：没装 Edge for Mac 时自动用 Playwright 自带 Chromium，不影响使用。
想用 Edge 就先安装 Edge for Mac，再跑（登录态要重新扫一次）。

**没有答案文件（报告里全是 awaiting_answers）**
脚本没拿到答案：按「答案从哪里来」准备好 `~/.cxauto/answers.json` 再跑
`3_填答.command`；或终端跑 `python3 do_homework.py --answers <你的答案文件路径>`。
答案文件不存在、JSON 写坏了，程序会在启动前就报错停下，不会进浏览器乱填。

**保存后重载答案丢失**
程序会在重载后逐题核对，答案没保留就只暂时保存、不提交，并在报告里写明题号。
处理：先手动打开那份作业看答案在不在；如果页面本身就没保存住，确认答案文件
无误后重跑一次 `3_填答.command`；仍丢失就手动在浏览器里填好再保存。

**视频 d/t 未 +1（报告「第 x.x 章播放未计入」）**
程序不会重播（重播大概率也不计入）。处理：手动打开那一章看任务点状态；
如果是平台判定问题，手动看完该章；确认计入后，下次巡检任务点会正常 +1。
同时会弹一次 macOS 通知提醒你复核。

**9222 端口被占（attach 模式）**
先完全退出 Edge 再跑；还被占就查是谁在用 9222（`lsof -i :9222`），
或在 `settings.json` 里把 `edge_port` 改成别的端口（如 9223）。

**单轮超时**
`watch.py` 每步最长 15 分钟（`ROUND_TIMEOUT`），超时会杀掉子进程、记日志、
弹通知，等下一轮。常超时先看 `~/.cxauto/logs/run.log` 是哪一步卡住
（一般是视频太长或页面加载慢），再决定要不要手动处理。
