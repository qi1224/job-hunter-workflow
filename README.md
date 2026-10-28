# Job Hunter Workflow

让 AI 根据你的 CV 推荐职位关键词，确认关键词后再确认搜索国家。配置完成后，每次执行职位搜索、评分、去重，并追加到本地 HTML 求职记录及完整 JD 报告。支持 Windows、macOS 和 Linux。

## 交给 AI 部署

下载或 clone 本仓库到本地，把下面的话交给能读取文件、运行 Python 的 AI 助手：

> 请阅读这个仓库的 SKILL.md，按照其中的流程部署到本地。我会提供一份 CV。先分析 CV，推荐职位方向、关键词和评分资料，等我确认后，再列出搜索国家让我确认。保存配置后检查安装。后续按已保存的配置搜索并更新记录。

如果助手没有自动发现 skill，让它直接读取本仓库的 `SKILL.md`。这是文件与 Python 脚本驱动的工作流，不依赖某个助手专有的 slash command。AI 负责推荐和引导，脚本负责提取、保存和执行；确认前不会自动搜索。

## 安装

需要 Python 3.10+、网络连接和可运行命令的 AI 助手。从仓库根目录执行：

```text
python scripts/bootstrap.py
```

Windows 可用 `py -3` 替代 `python`。安装器会创建本仓库 `.venv` 并安装 requirements，不修改全局 Python。成功后使用以下解释器，无需激活环境：

| 系统 | Python 路径 |
|---|---|
| Windows | `.venv/Scripts/python.exe` |
| macOS / Linux | `.venv/bin/python` |

下文 `PYTHON` 表示该解释器，请替换为实际路径。PowerShell 调用带引号的路径时，在前面加 `&`。

```text
PYTHON scripts/setup_config.py scan --resume "/path/to/cv.pdf"
```

AI 根据提取文本生成提案，展示依据，等用户确认。提案格式见 [onboarding.md](references/onboarding.md)。支持含文本的 PDF、DOCX、TXT、Markdown；扫描版 PDF 需要先 OCR。

```text
PYTHON scripts/setup_config.py profile --resume "/path/to/cv.pdf" --proposal "/private/proposal.json" --confirmed
```

再展示国家列表并等待用户确认。下面只是命令格式，国家由用户决定：

```text
PYTHON scripts/setup_config.py countries --countries Belgium Netherlands "United Kingdom" --tracker "/private/job-hunter/Job Tracker.html" --confirmed
PYTHON scripts/daily_job_hunt.py --check
PYTHON scripts/daily_job_hunt.py
```

默认配置在 `~/.config/job-hunter/config.json`。如已有安装，用 `setup_config.py --config <新路径> <子命令>` 创建独立配置，运行时也传相同 `--config`。安装器不会修改已有配置、CV 或正在使用的 skill。

## 每次搜索

告诉 AI“按已保存的配置找工作并更新记录”。默认搜索最近一周，JobSpy 无需 API key；JSearch 为可选补充，成功后至少间隔 14 天。价格、配额及各站点可用性以实际服务为准。没有配置定时任务。

运行结束列出新职位编号、分数、公司和地点。选择如“1、3”后，AI 才生成对应求职信；脚本先生成模板，完整文稿由 AI 用 CV/JD 证据填写。不会自动申请或联系雇主。

| 产物 | 位置 |
|---|---|
| 累计 HTML 职位记录 | 配置的 `html_tracker` |
| 完整 JD 和 CV 分析报告 | HTML 旁的 `JD Reports/` |
| 当前评分和新职位编号 | 用户目录下 `.job-hunter-last-*.json` |
| 选择后生成的求职信 | HTML 旁的 `Cover Letters/日期/` |

HTML 保留已有行，提供 Applied、Interview、Rejected 等状态。**按钮状态保存在同一浏览器的 localStorage 中，不写回 HTML，不跨设备同步；移动 HTML 或清除浏览器数据可能丢失状态。** 备份 HTML 不能备份浏览器状态。

## 隐私和限制

CV 提取在本地，AI 助手会读取文本；是否发送到模型服务取决于你使用的助手。职位服务只接收关键词和地点，不上传 CV。JD 报告包含完整 CV，应保存在私人目录。不要把真实 CV、配置、API key、报告或申请记录上传 GitHub。`.gitignore` 不能保护放在任意位置或已被 git 跟踪的敏感文件；提交前检查文件列表。

分数是可解释的关键词匹配，不能证明录用资格、语言或签证条件。招聘源可能限流、返回空结果或失败；AI 应报告这些情况。检索遵守各服务的使用条件，不自动绕过访问限制。

## 验证与来源

```text
PYTHON -m unittest discover -s tests -v
PYTHON scripts/daily_job_hunt.py --config /private/config.json --input /private/jobs.json --output-dir /private/test-output
```

测试使用虚构 CV 和职位，不发出职位搜索请求。审核与行为变化见 [AUDIT.md](AUDIT.md)。

本项目由 qi1224 在 [Donzhu2020/job-tracker](https://github.com/Donzhu2020/job-tracker) 基础上二次开发，使用 GitHub fork 保留上游关系及提交历史。新增 CV 引导及分阶段确认、通用评分、本地 HTML 与 JD 报告工作流和跨平台部署说明。上游未看到许可证文件，本项目没有替原作者授予新许可证；第三方依赖遵循各自许可证。当前文件仅包含本工作流使用的代码与文档，未上传个人 CV、配置和运行记录。
