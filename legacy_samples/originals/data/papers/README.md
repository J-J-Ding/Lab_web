# 论文栏目操作手册

## 📁 目录结构

```
papers/
├── index.html                  # 论文列表页
├── css/
│   └── paper_detail.css      # 论文详情页样式
└── 论文文件夹/               # 每篇论文一个文件夹
    ├── 封面图.png            # 论文封面图
    ├── paper.pdf             # 论文全文（可选）
    ├── framework1.png         # 技术路线图1
    ├── framework2.png         # 技术路线图2
    └── index.html            # 论文详情页
```

---

## 📝 添加新论文

### 步骤 1：创建论文文件夹

1. 在 `papers/` 目录下创建新文件夹
2. **命名规则**：`日期_论文标题`（不含特殊字符）
   - 示例：`202308_A new deep clustering method with application to customer selection for demand response program`

### 步骤 2：准备论文资料

- **封面图**：命名为 `封面图.png`，建议尺寸 800x400px
- **论文PDF**：命名为 `paper.pdf`
- **技术路线图**：命名为 `framework1.png`、`framework2.png`...

### 步骤 3：修改论文列表页

在 `papers/index.html` 中添加论文卡片，找到 `<div id="contentList">` 部分，添加如下内容：

```html
<!-- ---------------------------------- -->
<div class="item-card" data-date="2023-08">  <!-- 需要修改 -->
  <div class="item-thumbnail">
    <img src="202308_A new deep clustering method with application to customer selection for demand response program/封面图.png" alt="paper photo" onerror="this.onerror=null; this.src='../../lab-logo.png'" />  <!-- 需要修改 -->
  </div>
  <div class="item-content-wrapper">
    <div class="item-title">论文标题</div>  <!-- 需要修改 -->
    <div class="item-meta">
      <span>📄 期刊/会议名称</span>  <!-- 需要修改 -->
      <span>📅 2023-08</span>  <!-- 需要修改 -->
    </div>
    <div class="item-content">  <!-- 需要修改 -->
      论文摘要或简介...
    </div>
    <div class="item-footer">
      <div class="item-author">
        <span>👤</span>
        <a href="../members/index.html#teachers" class="item-link">作者1, 作者2, 作者3</a>  <!-- 需要修改 -->
      </div>
      <a href="202308_A new deep clustering method with application to customer selection for demand response program/index.html" class="btn btn-sm">查看详情</a>  <!-- 需要修改 -->
    </div>
  </div>
</div>
<!-- ---------------------------------- -->
```

**需要修改的地方（标注了 `<!-- 需要修改 -->`）：**
1. `data-date`：论文发表日期（YYYY-MM格式）
2. 图片 `src`：论文文件夹路径 + 封面图.png
3. `item-title`：论文标题
4. 期刊/会议名称
5. 发表年份月份
6. 论文摘要或简介
7. 作者信息（可链接到成员列表）
8. 详情页链接路径

### 步骤 4：创建论文详情页

在论文文件夹中创建 `index.html`，复制已有模板（只需修改标注了 `<!-- 需要修改 -->` 的部分）

---

## 🔗 关联作者

### 链接到成员列表

```html
<a href="../../members/index.html" class="paper-author-link">👤 作者1, 作者2, 作者3</a>
```

---

## 🎨 添加技术路线图

### 图片要求

- **命名**：`framework1.png`、`framework2.png`...
- **尺寸**：建议 800x500px 或更大
- **格式**：PNG（推荐）或 JPG

### 使用方式

```html
<div class="paper-section" data-search="framework">
  <h2 class="paper-section-title">🎨 技术路线</h2>
  <div class="paper-framework">
    <img src="framework1.png" alt="Framework" class="paper-framework-image" />
    <p class="paper-framework-caption">图片说明文字</p>
  </div>
</div>
```

---

## 📄 上传论文PDF

### 文件要求

- **文件名**：必须为 `paper.pdf`
- **格式**：PDF
- **大小**：建议小于 10MB

### 下载链接

```html
<a href="paper.pdf" download class="btn-download">
  <span class="btn-icon">📄</span>
  <span class="btn-text">下载论文全文</span>
</a>
```

---

## 🚀 快速开始

1. 创建论文文件夹（日期+标题）
2. 准备封面图和PDF
3. 修改 `papers/index.html` 添加论文卡片
4. 创建论文详情页 `index.html`
5. 完成！

---

## ⚠️ 注意事项

1. **文件夹命名**：使用 `日期_标题` 格式，便于排序
2. **封面图**：必须命名为 `封面图.png`
3. **论文PDF**：必须命名为 `paper.pdf`（如果提供）
4. **作者链接**：确保成员文件夹存在
5. **相对路径**：CSS 路径为 `../css/paper_detail.css`
6. **只需修改标注**：只有标注 `<!-- 需要修改 -->` 的地方才需要改

---
