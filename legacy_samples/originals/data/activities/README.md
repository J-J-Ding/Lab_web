# 团建活动栏目内容添加指南

## 📝 概述

本指南帮助实验室成员快速、规范地添加团建活动内容到网站。每个活动需要创建一个独立的文件夹和详情页。

---

## 📂 文件结构

```
data/activities/
├── index.html                    # 活动列表页（已存在）
├── css/
│   └── activity_detail.css   # 详情页样式（已存在）
└── [活动文件夹]/
    ├── index.html              # 活动详情页
    ├── 活动照片1.jpg         # 活动照片（推荐4-8张）
    ├── 活动照片2.jpg
    ├── 活动照片3.jpg
    └── 活动照片4.jpg
```

---

## 🚀 快速开始（3步完成）

### 第1步：创建活动文件夹

在 `data/activities/` 目录下创建一个新文件夹：

**文件夹命名规则：**
- 格式：`[日期][活动名称]` 或 `[活动名称]`
- 示例：
  - `20251211羽毛球赛`
  - `2025年春游`
  - `十周年庆典`
  - `202501新年聚餐`

**建议：** 使用日期前缀便于排序和管理

---

### 第2步：复制模板文件

复制现有的活动详情页作为模板：
```bash
# 方式1：使用命令行
cp data/activities/20251211羽毛球赛/index.html data/activities/你的活动/index.html

# 方式2：直接复制文件内容
# 用编辑器打开 20251211羽毛球赛/index.html
# 另存为 你的活动/index.html
```

---

### 第3步：修改内容

打开新创建的 `index.html`，修改以下内容：

#### ✅ 必须修改的内容

| 位置 | 说明 | 示例 |
|-----|------|------|
| **第6行** | 页面标题（`<title>`） | `<title>智能系统实验室2025年春游</title>` |
| **第24行** | 活动徽章文字 | `<div class="activity-badge">户外活动</div>` |
| **第24行** | 活动徽章样式（可选类型） | 添加以下类名之一：<br>`sports`、`outdoor` |
| **第25行** | 活动标题 | `<h1>智能系统实验室2025年春游</h1>` |
| **第27-29行** | 活动元数据（时间、地点、人数） | <br>`<span class="activity-meta-item">📅 活动时间：2025年4月20日</span>`<br>`<span class="activity-meta-item">📍 活动地点：郊野公园</span>`<br>`<span class="activity-meta-item">👥 参与人数：25人</span>` |
| **第34-42行** | 活动简介 | 使用多个 `<p>` 标签分段描述 |
| **第51-73行** | 活动照片 | 修改图片文件名和描述 |

---

## 🎨 活动徽章类型

在 HTML 第25行的 `activity-badge` 中添加以下类名之一：

| 类名 | 显示效果 | 适用场景 |
|-----|---------|---------|
| `sports` | 🏸 体育运动 | 羽毛球、篮球、足球等 |
| `outdoor` | 🌲 户外活动 | 春游、秋游等 |

**使用示例：**
```html
<!-- 体育运动 -->
<div class="activity-badge sports">🏸 体育运动</div>

<!-- 庆典活动 -->
<div class="activity-badge celebration">🎉 庆典活动</div>
```

---

## 📷 活动照片设置

### 准备照片

1. **照片要求：**
   - 格式：JPG、PNG（推荐 JPG）
   - 尺寸：建议 1920×1080 像素或更高
   - 数量：建议 4-8 张照片
   - 内容：活动场景、合影、精彩瞬间

2. **命名规则：**
   - 格式：`活动照片1.jpg`、`活动照片2.jpg`...
   - 从数字 1 开始递增

3. **放置位置：**
   - 将所有照片放入活动文件夹内 data/activities/你的活动/活动照片1.jpg
   - 例如：`data/activities/2025春游/活动照片1.jpg`

### 修改照片描述

在 HTML 第51-73行的 `activity-gallery` 部分修改：

```html
<div class="activity-section" data-search="gallery">
  <h2 class="activity-section-title">📷 活动照片</h2>
  <div class="activity-gallery">

    <!-- 照片1 -->
    <div class="gallery-item">
      <img src="活动照片1.jpg" alt="照片描述" />
      <div class="gallery-caption">
        <h4>照片标题</h4>
        <p>照片描述</p>
      </div>
    </div>

    <!-- 照片2（复制以上结构修改）-->
    <div class="gallery-item">
      <img src="活动照片2.jpg" alt="照片描述" />
      <div class="gallery-caption">
        <h4>照片标题</h4>
        <p>照片描述</p>
      </div>
    </div>

    <!-- 照片3、4... -->

  </div>
</div>
```

---

## 🔄 更新活动列表页

创建完活动详情页后，需要在 `data/activities/index.html` 中添加活动卡片：

### 操作步骤

1. 打开 `data/activities/index.html`
2. 在 `<!-- 活动卡片 - 按活动日期排序 -->` 注释后添加新卡片
3. 按日期降序排列（最新的活动在最上面）
4. <a href="2025春游/index.html" class="item-link">查看详情 →</a> 链接指向新创建的活动文件夹名称

### 活动卡片模板

```html
<!-- 活动名称 - 按活动日期排序 -->
<div class="item-card" data-date="2025-04-20">
  <div class="item-thumbnail">
    <div class="item-thumbnail-placeholder">🎉</div>
  </div>
  <div class="activity-type-badge celebration">🎉 庆典活动</div>
  <div class="item-content-wrapper">
    <div class="item-title">智能系统实验室2025年春游</div>
    <div class="item-meta">
      <span>📅 2025年4月20日</span>
      <span>📍 郊野公园</span>
      <span>👥 25人</span>
    </div>
    <div class="item-content">
      <p>2025年4月20日，智能系统实验室组织了年度春游活动...</p>
    </div>
    <div class="item-footer">
      <div class="item-author">
        <img src="../../lab-logo.png" alt="实验室" />
        <span>智能系统实验室</span>
      </div>
      <a href="2025春游/index.html" class="item-link">查看详情 →</a>
    </div>
  </div>
</div>
```

**重要提示：**
- `data-date` 属性：格式为 `YYYY-MM-DD`
- `href` 链接：指向新创建的活动文件夹名称

---

## 📋 检查清单

完成活动添加后，请检查：

### 文件检查
- [ ] 活动文件夹已创建在 `data/activities/` 下
- [ ] 文件夹名称使用日期或活动名称
- [ ] `index.html` 已创建并包含所有内容
- [ ] 活动照片已放入文件夹内（建议4-8张）
- [ ] 照片按序号命名（活动照片1.jpg、2.jpg...）

### 内容检查
- [ ] 页面标题已更新
- [ ] 活动徽章已设置正确的类型
- [ ] 活动时间、地点、人数已填写
- [ ] 活动简介完整且通顺
- [ ] 照片描述已添加（可选）

### 列表页更新
- [ ] `data/activities/index.html` 已添加活动卡片
- [ ] 活动卡片按日期排序（最新的在上）
- [ ] 链接指向正确的文件夹名称
- [ ] 活动类型徽章选择正确

---

## 🎯 完整示例

### 示例1：创建"2025年中秋聚餐"

**文件夹：** `data/activities/20250917中秋聚餐/`

**详情页内容：**
```html
<div class="activity-badge team">👥 团队建设</div>
<h1>智能系统实验室2025年中秋聚餐</h1>
<span>📅 活动时间：2025年9月17日</span>
<span>📍 活动地点：学校餐厅</span>
<span>👥 参与人数：20人</span>
<p>2025年9月17日中秋佳节，智能系统实验室举办了中秋聚餐活动...</p>
```

**列表页卡片：**
```html
<div class="item-card" data-date="2025-09-17">
  <div class="item-thumbnail">
    <div class="item-thumbnail-placeholder">🌕</div>
  </div>
  <div class="activity-type-badge team">👥 团队建设</div>
  <div class="item-content-wrapper">
    <div class="item-title">智能系统实验室2025年中秋聚餐</div>
    <div class="item-meta">
      <span>📅 2025年9月17日</span>
      <span>📍 学校餐厅</span>
      <span>👥 20人</span>
    </div>
    <div class="item-content">
      <p>2025年9月17日中秋佳节，智能系统实验室举办了中秋聚餐活动...</p>
    </div>
    <div class="item-footer">
      <a href="20250917中秋聚餐/index.html" class="item-link">查看详情 →</a>
    </div>
  </div>
</div>
```