# chaoxing-auto（学习通自动助手）

11 月 12 日，豆包工作正式接入第三方模型，DeepSeek V4.1 Flash 限时 0.01x 额度消耗——做同样的活，额度只扣原来的百分之一。趁着这波，顺手把这套学习通自动化做了出来：Windows、macOS、Linux 三个版本，外加三份能直接贴给豆包的提示词。豆包负责读题答题，脚本只做巡检、填表、播视频这些机械活。

只处理老师布置的虚拟题库作业 / 课程任务点；正式计分考试、补考、竞赛卷一律不代答。
不代签到；不绕过人脸识别、弹题、拖动验证、验证码；不索要、不保存账号密码。
仓库公开，许可证见 `LICENSE`（MIT）。

## 铁律（违反就停手）

1. 只处理老师布置的虚拟题库作业 / 课程任务点；正式计分考试、补考、竞赛卷一律不代答。
2. **提交门**：只有一份作业全部题目都有把握答案（不确定数 = 0）时才自动点提交；
   只要有 1 道不确定，就只点「暂时保存」，并在报告里列出不确定题号，绝不提交半份作业。
   提交前必须重载页面核对答案已保留。
3. 不代签到；不绕过人脸识别、弹题、拖动验证、验证码；平台要求人工确认时立刻停下。
4. 不索要、不保存账号密码，登录由用户本人在浏览器里完成。
5. 电话、邮箱、密码、cookie、登录态绝不进仓库；
   任何 token、cookie、会话凭证只放本机数据目录（DATA_DIR 下）。

## 填你自己的课程信息

仓库里不写任何人的课程号，三门课只是示例：

1. 把仓库根的 `config.example.py` 复制为 `config.py`（已被 `.gitignore` 覆盖，不会提交）；
2. 把 `config.py` 里的三门课换成你自己的：`courseid`、`clazzid`、`cpi` 都在学习通课程页 URL 里找——打开一门课，地址栏形如 `https://mooc1.chaoxing.com/visit/stucoursemiddle?courseid=<你的 courseid>&clazzid=<你的 clazzid>&cpi=<你的 cpi>&...`；三门课的 `cpi` 是同一个值；
3. 有同名假班要跳过时，把它的 `clazzid` 写进 `config.py` 的 `SKIP_CLAZZIDS`；
4. 示例值（`000000001` 这类）只是占位，直接跑会提示「课程 ID 还是占位符」。

找不到 `config.py` 时脚本会直接报错，告诉你去复制 `config.example.py`。
学号、电话、邮箱、密码、cookie、登录态不在仓库里，也永远不要往里放。

## 新架构：脚本只做机械层，答案由外部传入

脚本不含任何模型调用配置，也不调任何模型接口，只做机械活：

- 巡检（读作业列表、任务点状态）、视频播放（心理课，96% 停）
- 按外部给的答案填表、点「暂时保存」、重载核对、提交门判定、去重、写报告、定时巡检

答案由操作者用的智能体提供：比如用仓库 `doubao/` 下的豆包提示词让豆包来答题，
再把答案写进 JSON 文件，跑填答时传给脚本：

```
python do_homework.py --answers answers.json
```

答案 JSON 的格式见 `answers/README.md`（`{"<题号>": "B"}` 表示有把握的答案，
或 `{"<题号>": {"answer": "B", "certain": true}}`；文件里没有的题、
`certain` 为 `false` 的题一律判不确定、留空）。接线在
`common/answer_provider.py`（`AnswerProvider` 协议、`DictAnswerProvider`、
`JsonFileAnswerProvider`），填答入口是 `common/homework.py` 的
`answer_assignment(page, assignment, provider)`。

**后果（请注意）：没有答案清单、也不接模型之后，脚本版不能再无人值守自动答题。**
答题必须靠智能体在场：智能体先答题、给出答案 JSON，脚本再按答案机械填答。
不给 `--answers` 时，`do_homework.py` 只做巡检与报告，不填题、不保存、不提交，
每份作业在报告里记为 `awaiting_answers`，并写明「待外部提供答案」。
定时值守（每小时一轮）同样只巡检，不会自动答题。

## 三平台对照

| 项目 | Windows | macOS | Linux |
| --- | --- | --- | --- |
| 目录 | `windows/` | `macos/` | `linux/` |
| 浏览器 | 本机 Edge（channel="msedge"），不下载浏览器 | Edge for Mac 优先，未装回退 Playwright 自带 Chromium | 系统 Chromium 优先，未装回退 Playwright 自带 Chromium |
| 数据目录 | `%LOCALAPPDATA%/cxauto` | `~/.cxauto`（`/Users/duzou/.cxauto`） | `~/.cxauto`（遵循 XDG） |
| 启动器 | `.bat` 双击 | `.command` 双击（转调同名 `.sh`） | `.sh`（`chmod +x`） |
| 定时 | 计划任务（`7_装成每小时计划任务.bat`） | launchd plist / crontab | systemd timer / cron |
| 通知 | 写日志 + 每日检查记录 | osascript 弹通知（关键异常才弹） | 写日志 |
| 单轮超时 | subprocess timeout | signal.alarm + 进程组 | signal.alarm + 进程组 |
| 浏览器模式 | profile / attach（可复用你自己的 Edge 档案） | profile | profile |

三版共用 `common/` 核心：配置、答案提供方、提交门、选择器、浏览器、状态、
报告、作业、视频、日志。平台差异只在启动、路径、浏览器定位、定时与通知。

## 目录结构

| 目录 / 文件 | 说明 |
| --- | --- |
| `common/` | 共享核心包：配置、答案提供方、提交门、选择器、浏览器、状态、报告、作业、视频、日志 |
| `windows/` | Windows 版：扫码登录、巡检、填答、心理课视频、值守循环、启动器 .bat、自测 |
| `macos/` | macOS 版：同上，启动器 .command/.sh、launchd 示例、osascript 通知 |
| `linux/` | Linux 版：同上，启动器 .sh、systemd 示例、无头运行说明 |
| `doubao/` | 豆包提示词（三份，每系统一份）：让豆包用内置浏览器答题，答完把答案写进 JSON 交给脚本 |
| `answers/` | 答案 JSON 文件的格式说明（答案由外部传入，见上） |
| `config.example.py` | 配置示例：复制为 `config.py` 再填你自己的课程号（只有课程、路径、浏览器与行为参数） |
| `LICENSE` | MIT |
| `.gitignore` | 覆盖 config.py、会话凭证、浏览器档案、运行数据，一律不进 git |

## 五分钟上手

### Windows

1. 双击 `windows/00_安装依赖.bat`（装 Playwright 依赖 + 自测）。
2. 把仓库根的 `config.example.py` 复制为 `config.py`，填入你自己的课程号（见上面「填你自己的课程信息」）。
3. 双击 `windows/1_登录.bat`，自己扫码登录，勾「下次自动登录」。
4. 双击 `windows/2_巡检.bat`，看到三门课状态就说明链路通了。
5. 让智能体答题（用 `doubao/doubao-windows.md` 的提示词），把答案写进 JSON。
6. 双击 `windows/3_填答.bat`（或 `python do_homework.py --answers <答案 JSON>`）。
7. 需要每小时自动巡检：双击 `windows/7_装成每小时计划任务.bat`。

### macOS

1. 双击 `macos/00_安装依赖.command`。
2. 把仓库根的 `config.example.py` 复制为 `config.py`，填入你自己的课程号（见上面「填你自己的课程信息」）。
3. 双击 `macos/1_登录.command`，自己扫码登录，勾「下次自动登录」。
4. 双击 `macos/2_巡检.command`。
5. 让智能体答题（用 `doubao/doubao-macos.md`），答案写进 JSON（默认放 `~/.cxauto/answers.json`）。
6. 双击 `macos/3_填答.command`。
7. 定时：按 `macos/README.md` 装 `launchd/com.cxauto.watch.plist`，或 crontab 加一行。

### Linux

1. `bash linux/00_安装依赖.sh`（检查 python3/pip，装 Playwright；Chromium 按 README 用 apt 装）。
2. 把仓库根的 `config.example.py` 复制为 `config.py`，填入你自己的课程号（见上面「填你自己的课程信息」）。
3. `bash linux/1_登录.sh`，自己扫码登录（服务器无显示器的做法见 `linux/README.md`）。
4. `bash linux/2_巡检.sh`。
5. 让智能体答题（用 `doubao/doubao-linux.md`，豆包无 Linux 桌面客户端，用网页版 doubao.com），答案写进 JSON。
6. `bash linux/3_填答.sh --answers <答案 JSON>`。
7. 定时：按 `linux/README.md` 启用 systemd timer，或 crontab 加一行。

## 提交门逻辑

在 `common/submit_gate.py` 的 `decide()`（第 35 行起）：
题目数 > 0 且全部 `certain` 才 `submit`，否则 `temp_save`。
唯一能点「提交」按钮的路径是 `common/homework.py` 的
`answer_assignment()` 里提交门通过后的分支（第 357 行起）：
先点「暂时保存」→ 重载核对答案已保留 → 提交门判定 → 可提交才点提交并确认弹窗 →
最后核对页面出现「已提交/提交成功」才记为 submitted，否则报告「请人工复核」。

## FAQ

**Q：脚本能自己答题吗？**
不能。脚本只做机械层，答案必须由操作者用的智能体另外提供（见「新架构」一节）。
不给 `--answers` 时只巡检、不填题。

**Q：会不会误点「提交」？**
提交门是唯一路径：不确定数大于 0 时走 `temp_save`，绝不点提交。
`tools/selftest.py` 里有专门断言覆盖这一点（三个平台各有自测）。

**Q：登录失效怎么办？**
重跑各平台的 `1_登录`，记得勾「下次自动登录」。登录态只存在本机数据目录，
仓库里没有，也不要往仓库里放。

**Q：保存后重载答案没了怎么办？**
说明「暂时保存」没点中。看 `logs/run.log` 里有没有「已点暂时保存」，
没有就是没找到按钮（平台结构变了，改 `common/selectors.py` 里的选择器）。

**Q：视频播完任务点没 +1 怎么办？**
平台可能判定挂机。人工打开那章播 1 分钟即可解锁；脚本不会去绕检测，
也不会反复重播。

**Q：作业列表是空的，是没有作业吗？**
不一定。脚本会刷新重试一次，仍为空报「读取失败」，不会把空列表当成没有作业。

**Q：豆包提示词和脚本版会不会打架？**
同一时间只用一个。两边共用的 `monitor_state.json` 是「已做过」的基线，
脚本版会写它；豆包版不写，所以豆包做完的活要手动补进基线，
否则脚本下一轮会再做一次（只是重复暂存，不提交，无实际风险）。

## 参考与致谢

调研了 5 个公开仓库的做法，只借鉴思路，未复制代码：

- [Samueli924/chaoxing](https://github.com/Samueli924/chaoxing) —— 配置模板与模块分层；
  未借鉴其配置存明文账号密码、并发刷课、刷学习次数的做法。
- [chaolucky18/xuexitongScript](https://github.com/chaolucky18/xuexitongScript) ——
  无进度守卫（进度不动即补点、带冷却防抖）。
- [DaRin1403/xuexitong-autostudy](https://github.com/DaRin1403/xuexitong-autostudy) ——
  三级兜底选择器、低于阈值只填不交的门控思想；未借鉴其默认极速模式。
- [Wanbao114514/chaoxing-watch](https://github.com/Wanbao114514/chaoxing-watch) ——
  提交三步回读、视频以页面信号为准、模块互不调用一次只跑一个。
- [zx123-GNF/xuexitong-userscript](https://github.com/zx123-GNF/xuexitong-userscript) ——
  刷课与答题双脚本分离、检测到验证类弹窗自动暂停。

调研结论：这类项目最常见的坑是把「点了播放 / 点了提交」当成完成，
而不回读页面状态确认。本仓库的提交流程（暂存 → 重载核对 → 提交门 →
确认弹窗 → 最终核对「已提交/提交成功」）与视频流程（96% 停 →
回章节页复核任务点 d/t 是否 +1）就是针对这个坑设计的。

## 已知限制

- 题干是图片公式的题（高数常见），脚本按题号向答案提供方查询；
  答案 JSON 里没有就必然「不确定」，留空不猜。
- 学习通改版会换 DOM 结构，选择器集中在 `common/selectors.py`，改一处即可。
- 视频必须真实时长播放，单视频 1.3 小时上限兜底；一次只播一个，播完再进下一章。
- 不处理：签到、考试、需本人附件的实验、人脸/弹题/拖动验证。
- 登录、巡检、填答、视频的真实浏览器路径在本机未实跑（本机无 Playwright、无 Edge），
  首次在各平台跑通请按各平台 README 的顺序走一遍。
