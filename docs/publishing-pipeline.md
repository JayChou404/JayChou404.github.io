# Obsidian Vault 与博客发布内容分离方案（Jekyll + Chirpy + GitHub Pages）

> 适用仓库：`JayChou404.github.io`（Chirpy 主题 + GitHub Pages Action）。

## 1. 目标与现状

当前仓库已经具备以下基础：

- Jekyll 构建由 GitHub Actions 驱动，`bundle exec jekyll b` 后发布到 Pages。
- `_config.yml` 中已排除 `.obsidian`、`.trash`，说明已有把 Obsidian 元数据排除出站点的意识。

为了进一步实现“写作工作区（Vault）”和“线上发布内容（Jekyll 内容）”彻底分离，推荐采用**双目录+导出**模式：

- `vault/`：仅用于 Obsidian 创作，不直接参与 Jekyll 构建。
- `site-content/`：导出后的“可发布 Markdown 与资源”。
- `_posts/`、`assets/img/posts/`：Jekyll 真正读取的内容目录（由导出脚本同步生成）。

---

## 2. 推荐目录结构

> 下面结构可在当前仓库内落地；也可把 `vault/` 放在仓库外（更彻底隔离）。

```text
.
├── .github/
├── _config.yml
├── _posts/                      # Jekyll 发布目录（由导出流程写入）
├── assets/
│   └── img/
│       └── posts/              # 文章资源（图片、附件）发布目录
├── tools/
│   └── publishing/
│       ├── export.sh           # 从 vault 导出到 site-content
│       ├── sync-to-jekyll.sh   # 从 site-content 同步到 _posts/assets
│       └── validate.sh         # 发布前校验
├── site-content/               # 中间产物：仅含“可发布内容”
│   ├── posts/
│   └── assets/
└── vault/                      # Obsidian 工作区（建议默认不发布）
    ├── .obsidian/
    ├── 00-Inbox/
    ├── 10-Drafts/
    ├── 20-Posts/
    ├── 30-Notes/
    ├── 90-Archive/
    └── attachments/
```

### `vault/` 内建议分层

- `00-Inbox/`：临时收集。
- `10-Drafts/`：草稿（不发布）。
- `20-Posts/`：候选发布文章。
- `30-Notes/`：知识笔记（默认不发布）。
- `attachments/`：原始附件池。

---

## 3. 发布筛选规则（核心）

建议采用“**目录 + Front Matter + 白名单字段**”三重筛选，避免误发：

1. **目录门禁**
   - 仅扫描 `vault/20-Posts/`。
   - 其余目录（`Drafts/Notes/Archive`）无条件跳过。

2. **Front Matter 门禁**（建议）
   - `publish: true` 才可导出。
   - `date:` 必填；未填则阻断导出。
   - `title:` 必填；为空则阻断导出。
   - `tags/categories` 可选但建议规范。

3. **文件名规则**
   - 导出为 Jekyll 标准：`YYYY-MM-DD-slug.md`。
   - `slug` 从英文标题或手工 `slug:` 字段生成，避免中文文件名导致链接不稳定。

4. **内容规则**
   - 禁止导出包含私密标记的文章（如 `private: true`、`sensitive: true`）。
   - 可在校验阶段做关键字阻断（如身份证号、密钥模式等）。

---

## 4. 导出目录与同步路径

建议分两步，保证可审计与可回滚：

### Step A：Vault → `site-content/`

- 文章导出到：`site-content/posts/`
- 资源导出到：`site-content/assets/`
- 该阶段完成：
  - Front Matter 规范化
  - Obsidian 链接改写（见下文）
  - 资源去重与重命名

### Step B：`site-content/` → Jekyll 目录

- `site-content/posts/*.md` → `_posts/*.md`
- `site-content/assets/**` → `assets/img/posts/**`

> 优点：`site-content/` 作为“发布候选区”，可以在 PR 中直接 review。

---

## 5. 资源目录策略（图片/附件）

建议采用“文章隔离目录”，减少重名冲突：

```text
assets/img/posts/
└── 2026-02-13-obsidian-pipeline/
    ├── cover.webp
    ├── diagram-01.png
    └── ref-table.csv
```

规则建议：

- 每篇文章一个目录：`assets/img/posts/<post-slug>/`
- 资源名做规范化：小写、短横线、去空格。
- 大图导出时可自动压缩为 `webp`（可选）。
- Obsidian 原始附件不直接引用，统一走发布目录路径。

---

## 6. 链接策略（Obsidian WikiLink → Jekyll URL）

Obsidian 常见写法需在导出时转换：

1. `[[文章标题]]`
   - 转换为：`[文章标题]({% post_url yyyy-mm-dd-slug %})` 或最终 URL `/posts/slug/`

2. `[[文章标题#小节]]`
   - 转换为：`/posts/slug/#小节锚点`

3. `![[image.png]]`
   - 转换为：`![alt](/assets/img/posts/<post-slug>/image.png)`

4. 相对链接 `./foo.md`
   - 统一改写为站内 permalink。

为降低复杂度，建议只支持以下“可发布链接集合”：

- 指向 `vault/20-Posts/` 中已发布文章的内部链接。
- 指向当前文章资源目录中的附件链接。

其余链接在 `validate.sh` 中报错并阻断发布。

---

## 7. 回滚策略（Git + 发布流程）

建议按“内容回滚”和“站点回滚”两层处理：

### 7.1 内容回滚（首选）

- 所有导出结果通过 PR 合并。
- 发布异常时：
  1. `git revert <bad_commit>` 回滚本次导出提交。
  2. 触发 GitHub Pages Action 重新部署。

### 7.2 站点快速回滚（紧急）

- 在 `main` 维护最近可用 tag（如 `release-YYYYMMDD-HHMM`）。
- 故障时直接把 `main` 回退到最近稳定 tag，再触发部署。

### 7.3 预防性措施

- 导出前执行：链接检查、Front Matter 校验、敏感词扫描。
- Action 中保留 `htmlproofer`（仓库已有），避免坏链接进入生产。

---

## 8. 与当前仓库配置的衔接建议

1. `_config.yml`
   - 保留 `.obsidian`、`.trash` 的 `exclude`。
   - 追加：`vault/`、`site-content/`（如果不希望中间产物被 Jekyll误处理）。

2. GitHub Actions
   - 在 `Build site` 前插入导出步骤：
     - `tools/publishing/export.sh`
     - `tools/publishing/sync-to-jekyll.sh`
     - `tools/publishing/validate.sh`

3. 本地工作流
   - 写作：仅在 `vault/` 完成。
   - 发布：执行一键脚本（导出→同步→校验→commit）。

---

## 9. 最小可执行流程（建议）

```bash
# 1) 从 vault 挑选 publish:true 的文章导出到 site-content
bash tools/publishing/export.sh

# 2) 同步到 _posts 与 assets/img/posts
bash tools/publishing/sync-to-jekyll.sh

# 3) 预发布校验
bash tools/publishing/validate.sh

# 4) 本地构建
bundle exec jekyll b
```

如果你希望，我下一步可以基于这个文档直接给出 `export.sh / sync-to-jekyll.sh / validate.sh` 的可执行初版（兼容你当前 Chirpy 结构和 GitHub Pages Action）。
