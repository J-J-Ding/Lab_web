# 技术博客栏目内容添加指南

## 📝 概述

本指南帮助实验室成员快速、规范地发布技术博客到网站。每篇博客需要创建一个独立的文件夹和详情页。

---

## 📂 文件结构

```
data/blogs/
├── index.html                    # 博客列表页（已存在）
├── css/
│   └── blog_detail.css       # 博客详情页样式（已存在）
└── [博客文件夹]/
    ├── index.html              # 博客详情页
    ├── 封面图.png           # 博客封面图
    ├── 图片1.png            # 正文图片
    ├── 图片2.png
```

---

## 🚀 快速开始（3步完成）

### 第1步：创建博客文件夹

在 `data/blogs/` 目录下创建一个新文件夹：

**文件夹命名规则：**
- 格式：`[日期]标题`
- 示例：
  - `20231003TPA-LSTM`（推荐：英文技术术语）

**建议：**
- 优先使用英文标题，避免中文乱码问题
- 使用下划线 `_` 或连字符 `-` 分隔单词
- 不要使用特殊字符和空格

---

### 第2步：复制模板文件

复制现有的博客详情页作为模板：
```bash
# 方式1：使用命令行
cp data/blogs/TPA-LSTM/index.html data/blogs/你的博客名/index.html

# 方式2：直接复制文件内容
用编辑器打开 20231003TPA-LSTM/index.html
另存为 你的博客名/index.html
```

---

### 第3步：修改内容

打开新创建的 `index.html`，按注释提示修改内容。

---

## ✏️ 必须修改的内容（按顺序）


### 1. 博客徽章（第24行）

```html
<div class="blog-badge">技术分享</div>
```

**可选的徽章文字：**
- `技术分享`
- `教程指南`
- `研究论文`
- `学习笔记`
- `项目实践`

### 2. 博客标题（第25行）

```html
<h1 class="blog-title" data-search="title">你的博客标题</h1>
```

### 3. 作者信息（第27-28行）

```html
<span class="blog-meta-item">👤 作者：张三</span>
<span class="blog-meta-item">📅 发布时间：2025-01-15</span>
```

**日期格式：** `YYYY-MM-DD`

---

## 📖 博客内容结构

### 摘要部分（第33-38行）

简洁介绍博客的主要内容：

```html
<div class="blog-section" data-search="abstract">
  <h2 class="blog-section-title">📝 摘要</h2>
  <div class="blog-content">
    <p>这里是摘要内容，用1-2段话介绍博客主题、核心观点和主要内容...</p>
  </div>
</div>
```

**写作建议：**
- 字数：100-200字
- 包含：主题、核心观点、主要内容
- 吸引读者继续阅读

---

### 正文部分（第41-90行）

这是博客的核心内容：

```html
<div class="blog-section" data-search="content">
  <h2 class="blog-section-title">📖 正文</h2>
  <div class="blog-content">
    <!-- 内容开始 -->
    <h3>一、引言</h3>
    <p>介绍背景、问题、目的...</p>

    <h3>二、核心概念</h3>
    <p>解释关键概念...</p>
    <p>使用例子说明...</p>

    <h3>三、技术实现</h3>
    <p>详细描述实现步骤...</p>

    <!-- 插入代码示例 -->
    <p>以下是代码示例：</p>
    <pre><code>
import torch
import torch.nn as nn

class MyModel(nn.Module):
    def __init__(self):
        super(MyModel, self).__init__()
        # 模型定义
    </code></pre>

    <!-- 插入图片 -->
    <img src="architecture.png" alt="模型架构图" class="blog-image" />
    <p class="image-caption">图1：模型架构图</p>

    <h3>四、实验结果</h3>
    <p>展示实验数据和分析...</p>

    <h3>五、总结</h3>
    <p>总结全文内容，提出展望...</p>
  </div>
</div>
```

#### 内容写作要点

**1. 标题层级**
- 使用 `<h3>` 作为主要章节标题（一、二、三...）
- 使用 `<p>` 写段落
- 避免使用 `<h1>`、`<h2>`（已被其他地方使用）

**2. 代码插入**
```html
<pre><code>
# 代码内容
import numpy as np
</code></pre>
```

**注意事项：**
- 不要使用代码高亮（`<code>` 标签足够）
- 代码保持缩进

**3. 图片插入**
```html
<img src="文件名.png" alt="图片描述" class="blog-image" />
```

**注意事项：**
- 图片放在博客文件夹内
- 建议格式：PNG（矢量图）或 JPG（照片）
- 建议宽度：800-1200px
- 添加 `alt` 描述（用于 SEO 和无障碍访问）

---

### 标签部分（第93-102行，可选）

添加相关标签，便于分类：

```html
<div class="blog-section" data-search="tags">
  <h2 class="blog-section-title">🏷️ 标签</h2>
  <div class="tags-container">
    <div class="tag-item">🧠 深度学习</div>
    <div class="tag-item">🔥 PyTorch</div>
    <div class="tag-item">🎯 机器学习</div>
    <div class="tag-item">💻 人工智能</div>
    <div class="tag-item">📚 教程</div>
  </div>
</div>
```

**常用标签建议：**
- **技术领域：** 🧠 深度学习、🎯 机器学习、💻 人工智能、🤖 神经网络
- **框架工具：** 🔥 PyTorch、⚡ TensorFlow、💡 NumPy、📊 Matplotlib
- **内容类型：** 📚 教程、📝 学习笔记、🔬 研究论文、🛠️ 实践指南

---

### 作者信息（第105-115行）

```html
<div class="blog-section" data-search="author">
  <h2 class="blog-section-title">👤 作者简介</h2>
  <div class="author-info">
    <div class="author-avatar">👨‍💻</div>
    <div class="author-details">
      <div class="author-name">张三</div>
      <div class="author-role">智能系统实验室硕士研究生（在读）</div>
      <div class="author-bio">专注于深度学习研究，主要方向为计算机视觉和自然语言处理。</div>
    </div>
  </div>
</div>
```

**头像emoji选择：**
- 👨‍💻 男程序员
- 👩‍💻 女程序员
- 👨‍🎓 男研究生
- 👩‍🎓 女研究生
- 👨‍🏫 男教师
- 👩‍🏫 女教师

**角色描述建议：**
- `硕士研究生`
- `博士研究生`
- `教授`
- ······


---

### 相关文章（第118-137行，可选）

推荐阅读的其他博客：

```html
<div class="blog-section" data-search="related">
  <h2 class="blog-section-title">📚 相关文章</h2>
  <div class="related-posts">

    <a href="../TPA-LSTM/index.html" class="related-post-item">
      <span class="related-post-icon">📝</span>
      <span class="related-post-title">TPA-LSTM</span>
      <span class="related-post-date">2023-10-03</span>
    </a>

    <a href="../Deep_Learning_Introduction/index.html" class="related-post-item">
      <span class="related-post-icon">📝</span>
      <span class="related-post-title">深度学习入门与实践</span>
      <span class="related-post-date">2025-01-10</span>
    </a>

  </div>
</div>
```

**注意事项：**
- `href` 路径：`../博客文件夹名/index.html`
- 可以添加1-3篇相关文章
- 按时间或相关度排序

---

## 🔄 更新博客列表页

创建完博客详情页后，需要在 `data/blogs/index.html` 中添加博客卡片：

{
date: 'YYYY-MM-DD',
thumbnail: '博客文件夹/封面图.png',
title: '博客标题',
author: '作者姓名',
category: '博客分类',
summary: '博客摘要或简介',
link: '博客文件夹/index.html'
},

**重要提示：**
- `data` 属性：格式为 `YYYY-MM-DD`
- `href` 链接：指向新创建的博客文件中的index.html
- 摘要：从博客详情页的摘要部分复制或提炼

---

## 📋 检查清单

完成博客添加后，请检查：

### 文件检查
- [ ] 博客文件夹已创建在 `data/blogs/` 下
- [ ] 文件夹名称使用英文（避免中文）
- [ ] `index.html` 已创建
- [ ] 图片文件已放入文件夹内（如有）

### 内容检查
- [ ] 页面标题已更新
- [ ] 博客标题正确
- [ ] 作者信息已填写
- [ ] 发布时间已填写（格式 YYYY-MM-DD）
- [ ] 摘要完整（100-200字）
- [ ] 正文结构清晰（分节、分段）
- [ ] 代码使用 `<pre><code>` 标签
- [ ] 图片路径正确（直接使用文件名）
- [ ] 作者简介完整

### 列表页更新
- [ ] `data/blogs/index.html` 已添加博客卡片
- [ ] 博客卡片按日期排序（最新的在上）
- [ ] 链接指向正确的文件夹名称

---

## 📊 博客类型分类

### 1. 研究论文型
- 内容：论文解读、研究成果、实验分析
- 标签：🔬 研究、📊 数据分析、🎯 算法
- 模板参考：`TPA-LSTM/index.html`

### 2. 教程指南型
- 内容：技术教程、入门指南、实践步骤
- 标签：📚 教程、💡 学习、🛠️ 实践

### 3. 学习笔记型
- 内容：学习心得、知识总结、读书笔记
- 标签：📝 笔记、💭 思考、📖 阅读

### 4. 项目实践型
- 内容：项目介绍、实现过程、问题解决
- 标签：🚀 项目、🔧 实践、💻 开发

---

## 🎯 完整示例

### 示例1：创建"Transformer详解"博客

**文件夹：** `data/blogs/Transformer_Guide/`

**详情页关键内容：**
```html
<title>Transformer详解 - 智能系统实验室</title>
<div class="blog-badge">技术分享</div>
<h1 class="blog-title">Transformer详解</h1>
<span>👤 作者：李四</span>
<span>📅 发布时间：2025-01-20</span>

<!-- 摘要 -->
<p>本文详细介绍了Transformer架构的原理、核心组件和应用场景，并通过代码示例帮助读者深入理解这一革命性的深度学习模型。</p>

<!-- 正文 -->
<h3>一、背景介绍</h3>
<p>Transformer由Google团队于2017年提出，彻底改变了自然语言处理领域...</p>

<h3>二、核心架构</h3>
<p>Transformer主要由编码器和解码器组成，核心创新是自注意力机制...</p>

<!-- 标签 -->
<div class="tag-item">🧠 深度学习</div>
<div class="tag-item">📚 NLP</div>
<div class="tag-item">🎯 Attention</div>
```

**列表页卡片：**
```html
<div class="item-card" data-date="2025-01-20">
  <div class="item-thumbnail">
    <div class="item-thumbnail-placeholder">🤖</div>
  </div>
  <div class="item-content-wrapper">
    <div class="item-title">Transformer详解</div>
    <div class="item-meta">
      <span>👤 李四</span>
      <span>📅 2025年1月20日</span>
      <span>🏷️ 深度学习</span>
    </div>
    <div class="item-content">
      <p>本文详细介绍了Transformer架构的原理、核心组件和应用场景...</p>
    </div>
    <div class="item-footer">
      <a href="Transformer_Guide/index.html" class="item-link">阅读更多 →</a>
    </div>
  </div>
</div>
```

---

## 📸 图片管理

### 图片准备

1. **封面图**（可选）
   - 建议尺寸：1200×630px
   - 建议格式：PNG 或 JPG
   - 内容：与博客主题相关

2. **正文图片**
   - 建议宽度：800-1200px
   - 建议格式：PNG（图表）或 JPG（照片）
   - 内容：架构图、效果图、示意图等

3. **作者头像**（可选）
   - 建议尺寸：200×200px 或 400×400px
   - 建议格式：JPG 或 PNG
   - 内容：个人照片

### 图片命名规则

- 使用英文或数字
- 不要使用空格，使用下划线 `_` 或连字符 `-`
- 示例：
  - `architecture.png`
  - `experiment_result.jpg`
  - `flow_chart.png`

---

## ✍️ 内容写作技巧

### 标题建议
- 简洁明了，15-25字
- 包含核心关键词
- 使用数字增加吸引力（如"5个步骤""3种方法"）
- 示例：
  - ✅ "卷积神经网络详解：从原理到实践"
  - ❌ "关于卷积神经网络的一些看法和思考"

### 摘要建议
- 用1-2段话概括全文
- 包含：主题、核心观点、主要内容
- 控制在100-200字
- 避免使用复杂技术术语

### 正文建议
- 结构清晰，使用小标题分段
- 多用例子，少用抽象概念
- 代码和图片配合说明
- 每节内容不宜过长（建议500-1000字）

### 总结建议
- 总结全文要点
- 提出应用建议或注意事项
- 展望未来发展方向

---

## ❓ 常见问题

### Q1: 代码太长怎么办？
**A:** 可以截取核心部分，或在代码中添加注释说明。关键是展示关键逻辑，而不是完整代码。

### Q2: 图片可以放在其他目录吗？
**A:** 建议放在博客文件夹内，便于管理。如果多个博客共用图片，可以放在 `data/blogs/images/` 目录下。

### Q3: 数学公式怎么写？
**A:** 可以使用文本描述，或者截图图片。暂不支持 LaTeX 渲染。

### Q4: 博客字数有限制吗？
**A:** 没有，但建议1500-5000字为宜。太短内容不充实，太长读者难坚持。

### Q5: 可以引用外部资源吗？
**A:** 可以，但要确保链接稳定。建议将重要图片下载到本地。

### Q6: 如何预览效果？
**A:** 直接在浏览器中打开 `index.html` 文件即可预览。部署到 GitHub Pages 后，访问对应的链接查看。


