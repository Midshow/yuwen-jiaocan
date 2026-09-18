# 高中语文教参库 · 查询引擎 + Skill（yuwen-jiaocan）

统编版高中语文五册《教师教学用书》结构化数据库 + 命令行查询引擎 + Hermes Agent Skill。
面向高二考生：课文解读、文言标准翻译、单元任务、写作方法、评分标准——一条命令即得。

## 这是什么

| 组件 | 说明 |
|---|---|
| `flowus_data/高中语文教参.db` | 五册教参 SQLite 结构化库：282 节点 / 116 篇课文解说 / 约 161 万字 |
| `flowus_query.py` | 查询引擎（六命令：search / book / unit / get / text / list-ke） |
| `flowus_build_db.py` | 由原始 tree JSON 重建数据库的脚本 |
| `SKILL.md` | Hermes Agent skill（评分标准 / 答题协议 / 题型映射） |
| `references/` | 课标学业质量水平五级全文、116 篇课文索引 |
| `scripts/flowus_query.py` | skill 内置引擎副本（自动定位数据目录） |

## 快速开始（无需任何依赖）

```bash
# 查课文解说（文言文含教参标准译文，译文在同单元"资料链接"）
python flowus_query.py text 必修上册 劝学

# 查单元栏目（目标意图/课文解说/单元学习任务/教学设计/资料链接）
python flowus_query.py unit 必修上册 第一单元

# 全库搜索（写作方法 / 文学短评 / 意象…）
python flowus_query.py search 文学短评

# 全量课文解说清单（116 篇）
python flowus_query.py list-ke

# 取任意节点全文
python flowus_query.py get 必修下册 关于单元学习任务
```

册名：`必修上册 / 必修下册 / 选择性必修上册 / 选择性必修中册 / 选择性必修下册`

## 作为 Hermes / Claude 系 Agent 的 Skill 使用

将 `SKILL.md` + `references/` + `scripts/` 装入 Agent 的 skills 目录
（Hermes: `skills/education/gaozhong-yuwen-jiaocan/`），Agent 即可在对话中查库答题：
"《赤壁赋》怎么翻译？" → 自动查库返回教参标准译文 + 实词表 + 应试要点。
SKILL.md 内含应答协议、类别→命令决策树、执行期红线（不凭记忆翻译、答必注出处）。

## 目录结构

```
├── SKILL.md                 # Hermes skill 规则
├── flowus_query.py          # 查询引擎（主）
├── flowus_build_db.py       # 建库脚本
├── flowus_data/
│   ├── 高中语文教参.db      # 结构化数据库（4.8MB）
│   └── 课文索引.md          # 116 篇课文解说清单
├── references/
│   ├── 课文索引.md
│   └── 课标学业质量水平.md  # 教育部课标学业质量五级全文
└── scripts/flowus_query.py  # skill 内置引擎副本
```

## 构建/依赖

- 查询引擎：**纯 Python 标准库**（sqlite3），无需 pip 安装，Windows/macOS/Linux 皆可
- 建库脚本：依赖原始 FlowUs tree JSON（不随仓分发，116MB）；普通用户直接用现成 .db 即可
- 编码：UTF-8；中文 Windows 控制台若乱码，先执行 `chcp 65001`

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
