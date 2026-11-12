# 学习通自动助手 · Linux 版

只处理老师布置的虚拟题库作业 / 课程任务点；正式计分考试、补考、竞赛卷一律不代答。
不代签到；不绕过人脸识别、弹题、拖动验证、验证码；不索要、不保存账号密码。

## 铁律（违反就停手）

1. 只处理老师布置的虚拟题库作业 / 课程任务点；正式计分考试、补考、竞赛卷一律不代答。
2. **提交门**：只有一份作业全部题目都有把握答案（不确定数 = 0）时才自动点提交；
   只要有 1 道不确定，就只点「暂时保存」，并在报告里列出不确定题号，绝不提交半份作业。
   提交前必须重载页面核对答案已保留。
3. 不代签到；不绕过人脸识别、弹题、拖动验证、验证码；平台要求人工确认时立刻停下。
4. 不索要、不保存账号密码，登录由用户本人在浏览器里完成。
5. 电话、邮箱、密码、cookie、登录态绝不进仓库；任何凭证只放本机数据目录。

## 五分钟上手

1. 装系统依赖（Debian / Ubuntu）：

   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip chromium-browser
   ```

   其它发行版换包管理器：Fedora 用 `sudo dnf install -y python3-pip chromium`；
   Arch 用 `sudo pacman -S python-pip chromium`。`chromium-browser` 是系统 Chromium；
   不装也行，脚本会回退到 Playwright 自带 Chromium（见「浏览器怎么选」）。

2. 跑 `./00_安装依赖.sh`（装 playwright Python 库 + Chromium + 跑自测）。
3. 跑 `./6_自测.sh`（00 脚本最后已跑过一次；想单独验证再跑）。
4. 跑 `./1_登录.sh`，自己扫码登录学习通，勾「下次自动登录」。
5. 跑 `./2_巡检.sh`，确认三门课的作业和任务点能读到。
6. 准备答案（见「答案从哪里来」），跑 `./3_填答.sh --answers ~/.cxauto/answers.json`；
   不带 `--answers` 时只巡检、不填题。
7. 需要长期值守：装 systemd timer（见「定时」），每小时跑一轮。

先建 `config.py`：把仓库根的 `config.example.py` 复制为 `config.py`，
再把里面的三门课换成你自己的课程号（courseid/clazzid/cpi 在学习通课程页
URL 里找，见仓库根 README「填你自己的课程信息」）；有同名假班要跳过时，
把它的 clazzid 写进 `SKIP_CLAZZIDS`。

## 答案从哪里来（重要）

脚本只做机械层：巡检、填题、保存、提交门、视频播放、报告、定时。
**脚本本身不管模型、不调用任何模型、不猜题。**

答案由操作者用的智能体提供：比如用仓库 `doubao/` 下的豆包提示词让豆包来答
（豆包没有 Linux 桌面客户端，用网页版 doubao.com），再把答案写进 JSON 文件交给脚本。

答案 JSON 格式（题号作键）：

```json
{
  "1": "B",
  "2": {"answer": "AC", "certain": true},
  "3": {"answer": "A", "certain": false}
}
```

- `"1": "B"`：第 1 题有把握选 B；
- `{"answer": ..., "certain": true}`：同上，显式写法；
- `certain: false` 的题、文件里没有的题：脚本留空，绝不猜；
- 文件放 `~/.cxauto/answers.json`，跑 `./3_填答.sh --answers ~/.cxauto/answers.json`；
  相对路径先在当前目录找，找不到再到 `~/.cxauto/` 下找；
- **不给 `--answers` 时**：只巡检、只写报告，不填题、不保存、不提交，
  报告里 action 记为 `awaiting_answers`，并写明「待外部提供答案」。

接线位置：`common/answer_provider.py`（`AnswerProvider.lookup(qnum, stem, qtype)` 协议、
`DictAnswerProvider`、`JsonFileAnswerProvider`）；`common/homework.py` 的
`answer_assignment(page, assignment, provider)`；`linux/do_homework.py` 的
`--answers` 选项与 `load_provider()`。

## 每个启动器的作用

| 启动器 | 作用 |
| --- | --- |
| `00_安装依赖.sh` | 检查 python3/pip → `pip install playwright` → 装 Chromium → 跑自测 |
| `1_登录.sh` | 扫码登录（有头模式，勾「下次自动登录」），登录态进 `~/.cxauto/browser_profile` |
| `2_巡检.sh` | 只读巡检三门课 + 心理课任务点，不作答、不提交 |
| `3_填答.sh` | 巡检 → 按 `--answers` 的答案填答 → 提交门 → 报告；不带 `--answers` 只巡检 |
| `4_心理课视频.sh` | 心理课视频：原速、页面静音，96% 停，复核任务点 |
| `5_值守.sh` | 值守循环：每小时一轮巡检 → 填答 → 播放 |
| `6_自测.sh` | 不登录、不联网，mock 自测（提交门 / 外部答案接口 / 状态去重 / Linux 配置） |

## 浏览器怎么选（三种情况）

脚本按顺序选 Chromium（见 `linux/config.py` 的 `resolve_chromium()`）：

1. **`/usr/bin/chromium` 或 `/usr/bin/chromium-browser` 存在**（可执行）
   → 直接用它（`executable_path` 指向存在的那个）；
2. **上面两个路径都没有，但 PATH 里能找到 `chromium` / `chromium-browser`**
   → 用 `channel="chromium"` 让 Playwright 找系统 Chromium；
3. **都没有** → 回退 Playwright 自带 Chromium，
   需先跑 `python3 -m playwright install chromium`（`00_安装依赖.sh` 会装）。

环境变量 `CX_CHROMIUM_PATH` 可强制指定一个 Chromium 二进制路径
（如 `/snap/bin/chromium`）。当前会用哪种，可跑：

```bash
python3 -c "import config; print(config.chromium_launch_kwargs())"
```

## 数据目录

默认 `~/.cxauto`；`$XDG_DATA_HOME` 已设置时用 `$XDG_DATA_HOME/cxauto`；
环境变量 `CX_DATA_DIR` 可改：

| 位置 | 内容 |
| --- | --- |
| `browser_profile/` | profile 模式浏览器档案（登录态在这里） |
| `state.json` | 已完成作业 / 视频状态（四个列表） |
| `scan.json` | 最近一次巡检结果 |
| `answers.json` | 自己放的答案文件（不进仓库） |
| `reports/` | 每轮 CSV 明细 |
| `logs/run.log`、`logs/summary.jsonl` | 运行日志 / 每轮结论 |
| `每日检查记录.md` | 有新增 / 异常时才追加的检查记录 |
| `shots/` | 异常截图 |

电话、邮箱、密码、cookie、登录态绝不进仓库；`config.py` 只放本机，
绝不提交（已被仓库根 `.gitignore` 覆盖）。

## 无头运行说明

- `HEADLESS` 默认 1（无头）；登录（`login.py`）默认有头，扫码要用。
- 环境变量 `CX_HEADLESS=0` 可强制有头（调试页面时用）。
- 值守 / 定时任务跑无头即可；登录态已保存就不需要显示器。

## 服务器无显示器首次登录

二选一：

1. **本机跑 login.py**：把仓库复制到有显示器的 Linux 桌面，跑 `./1_登录.sh`
   扫码登录，再把 `~/.cxauto/browser_profile` 整个目录拷回服务器的 `~/.cxauto/` 下；
2. **X 转发**：`ssh -X user@服务器` 登录后跑 `python3 login.py --headless 0`
   （有头模式，DISPLAY 经 X 转发）。

登录态拷回服务器后，服务器上跑 `2_巡检.sh` 应能直接读到课程，不用再登录。

## 定时

### systemd（推荐，用户级服务，不用 root）

```bash
mkdir -p ~/.config/systemd/user
cp linux/systemd/cxauto-watch.service linux/systemd/cxauto-watch.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now cxauto-watch.timer
systemctl --user list-timers | grep cxauto
```

每小时跑 `watch.py --once`。注意：

- 用户级服务只在登录会话存活时跑；服务器长期在请开 lingering：
  `loginctl enable-linger $USER`；
- 仓库不在 `~/chaoxing-auto` 时，改 service 里的 `%h/chaoxing-auto` 两处路径；
- 停用：`systemctl --user disable --now cxauto-watch.timer`。

### crontab（一行示例）

```cron
0 * * * * /usr/bin/python3 /home/你的用户名/chaoxing-auto/linux/watch.py --once >> ~/.cxauto/logs/cron.log 2>&1
```

把 `/home/你的用户名/chaoxing-auto` 换成仓库实际路径；cron 里要用绝对路径。

## FAQ

**登录失效（提示请先跑 1_登录.sh）**
重新跑 `./1_登录.sh` 扫码登录，勾「下次自动登录」。登录态过期是正常的，
不要把账号密码告诉任何人、不要写进任何文件。

**Chromium 未找到**
按「浏览器怎么选」三步查：先 `which chromium chromium-browser` 看 PATH 里有没有；
没有就 `sudo apt install chromium-browser`，或跑 `python3 -m playwright install chromium`
装 Playwright 自带 Chromium；Snap 装的 Chromium 可用 `CX_CHROMIUM_PATH=/snap/bin/chromium` 指定。

**没有答案文件 / 答案文件找不到**
不给 `--answers` 时脚本只巡检、不填题，这是正常的（报告里 action 为 `awaiting_answers`）。
给了 `--answers` 但文件不存在或不是合法 JSON 时，脚本直接停下并报错，不会静默跳过：
检查路径是否写对（绝对路径，或放 `~/.cxauto/` 下用文件名）。

**服务器无显示器首次登录**
见「服务器无显示器首次登录」：本机跑 login.py 再拷 `browser_profile` 回来，
或 `ssh -X` 后跑 `python3 login.py --headless 0`。

**保存后重载答案丢失**
程序会在重载后逐题核对，答案没保留就只暂时保存、不提交，并在报告里写明题号。
处理：先手动打开那份作业看答案在不在；如果页面本身就没保存住，重跑一次
`3_填答.sh --answers ~/.cxauto/answers.json`（按同一份答案重新填答再保存）；
仍丢失就手动在浏览器里填好再保存。

**视频 d/t 未 +1（报告「第 x.x 章播放未计入」）**
程序不会重播（重播大概率也不计入）。处理：手动打开那一章看任务点状态；
如果是平台判定问题，手动看完该章；确认计入后，下次巡检任务点会正常 +1。
