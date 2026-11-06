# 学科竞赛栏目内容添加指南

## 📝 概述

本指南帮助实验室成员快速、规范地添加学科竞赛获奖信息到网站。每个竞赛需要创建一个独立的文件夹和详情页。

---

## 📂 文件结构

```
data/competitions/
├── index.html                          # 竞赛列表页（已存在）
├── css/
│   └── competition_detail.css      # 竞赛详情页样式（已存在）
└── [竞赛文件夹]/
    ├── index.html                   # 竞赛详情页
    ├── 封面图.jpg                   # 竞赛封面图（建议尺寸：1200×630px）
    ├── 获奖证书.png                 # 获奖证书
    ├── 项目截图.png                 # 项目相关截图（可选）
    ├── 团队合影.jpg                 # 团队合影（可选）
    └── 其他材料...                  # 其他相关材料（可选）
```

---

## 🚀 快速开始（3步完成）

### 第1步：创建竞赛文件夹

在 `data/competitions/` 目录下创建一个新文件夹：

**文件夹命名规则：**
- 格式：`[日期][竞赛名称]` 或 `[竞赛名称]`
- 示例：
  - `20261228金融科技竞赛`（推荐：日期+名称）

**建议：**
- 使用日期前缀便于排序和管理
- 日期格式：`YYYYMMDD`（如 20251228）
- 可以使用中文，但建议使用英文避免乱码

---

### 第2步：复制模板文件

复制现有的竞赛详情页作为模板：
```bash
# 方式1：使用命令行
cp data/competitions/20261228金融科技竞赛/index.html data/competitions/你的竞赛/index.html

# 方式2：直接复制文件内容
用编辑器打开 20261228金融科技竞赛/index.html
另存为 你的竞赛/index.html
```

---

### 第3步：修改内容

打开新创建的 `index.html`，按注释提示修改内容。

---

## ✏️ 必须修改的内容（按顺序）

### 1. 竞赛标题（第24行）

```html
<h1 class="competition-title" data-search="title">你的竞赛名称</h1>
```

**标题示例：**
- `第X届中国研究生金融科技创新大赛`
- `2025年全国大学生数学建模竞赛`
- `ACM-ICPC国际大学生程序设计竞赛`
- `全国大学生智能汽车竞赛`

---

## 📋 内容结构详解

### 赛事简介（第28-33行）

简要介绍竞赛的基本信息：

```html
<div class="competition-section" data-search="intro">
  <h2 class="competition-section-title">📋 赛事简介</h2>
  <div class="competition-content">
    <p>这里是赛事简介内容，包括竞赛的主办单位、参赛对象、竞赛目的、影响力等...</p>
  </div>
</div>
```

---

### 作品简介（第36-41行）

详细介绍参赛项目的内容：

```html
<div class="competition-section" data-search="project">
  <h2 class="competition-section-title">💡 作品简介</h2>
  <div class="competition-content">
    <p>这里是项目简介内容，包括项目背景、核心技术、创新点、应用价值等...</p>
  </div>
</div>
```

---

### 获奖信息（第45-61行）

填写获奖的详细信息：

```html
<div class="competition-section" data-search="award">
  <h2 class="competition-section-title">🏆 获奖信息</h2>
  <div class="award-info">
    <div class="award-item">
      <span class="award-label">获奖等级</span>
      <span class="award-value">国家级特等奖</span>
    </div>
    <div class="award-item">
      <span class="award-label">获奖时间</span>
      <span class="award-value">2025年12月28日</span>
    </div>
    <div class="award-item">
      <span class="award-label">主办单位</span>
      <span class="award-value">中国学位与研究生教育学会</span>
    </div>
  </div>
</div>
```

**可以添加的奖项信息：**
- **获奖等级**：国家级特等奖、一等奖、二等奖、三等奖，省一等奖等
- **获奖时间**：格式：`YYYY年MM月DD日`
- **主办单位**：竞赛的主办方
- **承办单位**：（可选）
- **参与成员**：（可选）

**获奖等级示例：**
- 国家级特等奖、一等奖、二等奖、三等奖
- 省级一等奖、二等奖、三等奖
- 校级一等奖、二等奖、三等奖
- 冠军、亚军、季军、全国第三名
- 金奖、银奖、铜奖

---

### 相关链接（第64-82行）

添加竞赛相关的链接：

```html
<div class="competition-section" data-search="links">
  <h2 class="competition-section-title">🔗 相关链接</h2>
  <div class="competition-links">

    <!-- 竞赛官网 -->
    <a href="https://example.com" target="_blank" class="competition-link-card">
      <div class="competition-link-icon">🌐</div>
      <div class="competition-link-info">
        <div class="competition-link-title">竞赛官网</div>
        <div class="competition-link-desc">访问官方网站了解更多信息</div>
      </div>
    </a>

    <!-- 获奖证书 -->
    <a href="获奖证书.png" target="_blank" class="competition-link-card">
      <div class="competition-link-icon">📄</div>
      <div class="competition-link-info">
        <div class="competition-link-title">获奖证书</div>
        <div class="competition-link-desc">查看获奖证书</div>
      </div>
    </a>

  </div>
</div>
```

**可以添加的链接类型：**

| 图标 | 标题 | 链接类型 | 说明 |
|-----|------|---------|------|
| 🌐 | 竞赛官网 | 外部链接 | `https://...` |
| 📄 | 获奖证书 | 本地文件 | `获奖证书.png` |
| 📁 | 项目代码 | 外部链接 | GitHub、Gitee |
| 📊 | 项目报告 | 本地文件 | `报告.pdf` |
| 🎬 | 项目演示 | 外部链接 | B站、YouTube |
| 📸 | 团队合影 | 本地文件 | `合影.jpg` |

**注意事项：**
- 外部链接使用 `target="_blank"` 在新标签页打开
- 本地文件放在竞赛文件夹内
- 确保链接可访问

---

## 🔄 更新竞赛列表页

创建完竞赛详情页后，需要在 `data/competitions/index.html` 中添加竞赛卡片：

{
        date: 'YYYY-MM-DD',
        thumbnail: '竞赛文件夹/封面图.jpg',
        title: '竞赛名称',
        award: '获奖等级',
        summary: '竞赛简介或获奖情况',
        members: '获奖成员',
        link: '竞赛文件夹/index.html'
      },
      
**重要提示：**
- `data-date` 属性：格式为 `YYYY-MM-DD`（获奖日期）
- `src` 路径：`竞赛文件夹名/封面图.jpg`
- `href` 链接：`竞赛文件夹名/index.html`
- 参与成员：列出所有获奖学生姓名，用英文逗号+空格(, )分隔

---

## 📸 图片管理

### 封面图

- **建议尺寸：** 1200×630px（16:9比例）
- **建议格式：** JPG（照片类）或 PNG（图表类）
- **文件名：** `封面图.jpg`
- **内容：** 竞赛Logo、获奖照片、项目截图等

### 获奖证书

- **建议尺寸：** 原始尺寸
- **建议格式：** JPG 或 PNG
- **文件名：** `获奖证书.png`或`获奖证书.jpg`
- **内容：** 获奖证书扫描件或照片

### 其他图片（可选）

- **项目截图：** 展示项目界面、实验结果等
- **团队合影：** 参赛团队与奖杯的合影
- **现场照片：** 比赛现场、答辩现场等

**图片命名规则：**
- 使用中文或英文
- 不要使用特殊字符
- 使用下划线 `_` 或连字符 `-` 分隔
- 示例：
  - `封面图.jpg`
  - `获奖证书.png`
  - `项目截图.png`
  - `团队合影.jpg`

---

## 📋 检查清单

完成竞赛添加后，请检查：

### 文件检查
- [ ] 竞赛文件夹已创建在 `data/competitions/` 下
- [ ] 文件夹名称使用日期+名称或纯名称
- [ ] `index.html` 已创建
- [ ] 封面图已添加（推荐）
- [ ] 获奖证书已添加（如需要）

### 内容检查
- [ ] 页面标题已更新
- [ ] 竞赛标题正确
- [ ] 赛事简介完整（100-200字）
- [ ] 项目简介详细（200-400字）
- [ ] 获奖等级、时间、主办单位已填写
- [ ] 相关链接已添加（官网、证书等）

### 列表页更新
- [ ] `data/competitions/index.html` 已添加竞赛卡片
- [ ] 竞赛卡片按日期排序（最新的在上）
- [ ] 封面图路径正确
- [ ] 链接指向正确的文件夹名称
- [ ] 参与成员已列出

---
