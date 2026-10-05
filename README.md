# 高中语文教参库 · 查询引擎 + 离线阅读器 + Skill

统编版高中语文五册教参的本地查询工具。随仓数据库包含 282 个节点、116 篇课文解说；所有查询和网页阅读均可离线使用。

## 给同学：直接打开阅读器

下载仓库的 **[yuwen-jiaocan.html](yuwen-jiaocan.html)**，用浏览器打开，无需 Python、账户或服务器。

- 打开“目录与搜索”，按册目展开单元。
- 搜索篇名或关键词，可选择全库或某册。结果优先显示精确篇名，再显示标题包含、正文命中，并附摘要。
- 点击结果自动高亮正文命中词，可用“上一个 / 下一个”跳转。
- 在课文页面点击“参考译文 / 单元任务 / 相关资料”。译文支持查看来源节点、行号及返回原文位置。
- 调整字号；浏览器允许本地存储时，自动记住上次阅读内容、位置与字号。禁用存储时仍可正常阅读。

译文入口只显示原文明确标记并匹配到该课文的小节。当前数据识别到 35 个译文来源小节，关联到 32 个不同的册内篇名；同篇不同来源分别保留。这不代表 116 篇课文均有译文。

## 命令行与 Agent

需要 **Python 3.10 或更新版本**，运行时只用标准库，无需 pip 安装。先下载整个仓库并进入目录：

```bash
python flowus_query.py search 劝学
python flowus_query.py search 文学短评 --book 必修上册 --limit 5 --page 1
python flowus_query.py text 必修上册 赤壁赋
python flowus_query.py translation 必修上册 赤壁赋 --json
python flowus_query.py unit 必修上册 第七单元
python flowus_query.py get 必修上册 第七单元/资料链接
python flowus_query.py book 必修上册
python flowus_query.py list-ke
```

册名：必修上册、必修下册、选择性必修上册、选择性必修中册、选择性必修下册。

- 多个关键词用空格分隔，须全部命中；`%`、`_` 按字面搜索。
- 搜索与正文查询默认每页 8 条，目录默认全部；`--limit` / `--page` 控制分页。总命中数与本页条数分别显示。
- 指定册无结果时不会自动换册；如需跨册，明确增加 `--all-books`（适用于 get / text / translation）。
- `--json` 返回 `total、returned、page、limit、notice、results`。每项包含 `doc_id、book、unit、section、subsection、path`；搜索返回 `snippet` 和 `content_length`，正文命令返回 `content`。译文另含 `translation_id、start_line、end_line`。
- 译文行号按源节点正文计算，从 1 开始，范围包含标题；返回正文不含该标题。
- 参数错误、缺库或库格式错误退出码为 2；合法查询无结果返回 0，并明确显示 0 条。

所有查询入口和 HTML 生成器共用路径规则：`--db` > `FLOWUS_DB` > `FLOWUS_DATA_DIR/高中语文教参.db` > 项目内 `flowus_data/高中语文教参.db`。查询以只读模式打开，路径错误不会创建空库。

```bash
python flowus_query.py --db "/path/to/高中语文教参.db" translation 必修上册 赤壁赋
python gen_html_reader.py --db "/path/to/高中语文教参.db" --output dist/yuwen-jiaocan.html
```

中文终端输出异常时可用 `python -X utf8 ...`。

## 安装完整 Skill

生成可搬迁的完整安装包：

```bash
python scripts/build_skill.py
# 输出 dist/gaozhong-yuwen-jiaocan.zip；也支持 --db 和 --output
```

将 ZIP 中的 `gaozhong-yuwen-jiaocan/` 整个文件夹解压到 Agent 的 skills 目录（例如 Hermes 的 `skills/education/`）。不要只复制 SKILL.md 和 scripts：数据库与 jiaocan 包也必须保留。

安装后可从任意工作目录验证：

```bash
python "/安装位置/gaozhong-yuwen-jiaocan/scripts/flowus_query.py" translation 必修上册 赤壁赋 --json
```

包内 `manifest.json` 记录各文件 SHA-256，便于核验安装文件。Skill 规则要求先检索再回答，并标注原文来源；年级、地区、考试要求按实际用户信息确定。课标参考文件明确标注 2020 修订版和核验范围，不能直接替代某年某省考试细则。

## 数据校验与重建

检查随仓数据库并保存报告：

```bash
python flowus_build_db.py --check --report dist/data-report.json
```

从原始 FlowUs tree JSON 重建（原始文件不随仓分发）：

```bash
python flowus_build_db.py --data-dir /path/to/tree-json --db dist/高中语文教参.db --report dist/build-report.json
```

输入文件为五册各自的 `<册名>_tree.json`。构建遍历容器内嵌套子页，并保持同级顺序；报告节点数、空正文、冲突节点、缺失块、未遍历页面、未知块类型、孤立节点和重复路径。空正文可能是合法目录节点，单独列出供检查。缺失块、冲突节点、未遍历页面或最终校验失败会停止构建；先构建临时库，全部通过后替换目标，失败保留原库。

## 开发与验证

```bash
python -m unittest discover -s tests -v
python gen_html_reader.py
python scripts/build_skill.py
```

浏览器回归测试是开发依赖，普通用户不需要安装：

```bash
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
node tests/reader.cjs
```

可设置 `BROWSER_PATH` 使用本机 Chromium 系浏览器；`SCREENSHOT_DIR` 指定已存在的截图目录。测试直接使用 file://，覆盖桌面和手机视口、搜索、译文跳转、目录折叠、字号和阅读进度恢复、禁用本地存储。

GitHub Actions 在 Windows / Linux、Python 3.10 / 3.13 上运行回归与数据校验，并在 Chromium 上运行离线阅读测试。

## 目录

```text
jiaocan/                 共享查询、译文提取、排序及 CLI 实现
flowus_query.py          根目录兼容入口
scripts/flowus_query.py  Skill 兼容入口（不维护第二套实现）
scripts/build_skill.py   完整 Skill 打包
flowus_build_db.py       原始树建库及校验
gen_html_reader.py      生成单文件 HTML
reader/                 阅读器 HTML / CSS / JavaScript 源码
flowus_data/             SQLite 数据库及原始篇目索引
references/             Skill 篇目索引、课标版本与来源说明
tests/                  数据、查询、打包、浏览器回归
SKILL.md                Agent 使用规则
yuwen-jiaocan.html       生成的离线阅读器
```

## 数据来源与版权声明 ⚠️

- 数据库内容整理自**人民教育出版社《普通高中语文教师教学用书》**（统编版 2019 年版），
  版权归人教社及原作者所有；原始数据经付费知识库（FlowUs）数字化整理。
- 本仓库**仅供个人学习、教学研究、非商业用途**。不得用于商业牟利、不得再传播用于商业用途。
- 如涉侵权请联系仓库维护者删除对应内容。
- `references/课标学业质量水平.md` 摘自教育部《普通高中语文课程标准（2017 年版 2020 年修订）》（教育部公开文件），已注明出处。

## License

代码（查询引擎/建库脚本/skill 规则）：MIT License。
数据（`flowus_data/高中语文教参.db` 及教参衍生内容）：**学习用途授权，非商业，版权归原作者**——见上文版权声明。

---

Made with 开源精神 by 陈厚亦（高二 · 江苏南通）· 若对你有帮助，点个 Star ✨
