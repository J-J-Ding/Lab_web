# 课题项目管理操作手册

本指南介绍如何在 Lab_test/data/projects 目录下添加和管理课题项目内容。

## 目录结构

```
Lab_test/data/projects/
├── index.html          # 项目列表页（自动排序）
├── README.md           # 本操作手册
├── css/                # 项目详情页样式
│   └── project_detail.css
└── [项目文件夹]/
    ├── 封面图.png      # 项目封面图
    └── index.html      # 项目详情页
```

## 添加新项目步骤

### 步骤 1：创建项目文件夹

在 `projects/` 目录下创建新项目文件夹，命名格式建议：`YYYY_项目名称`（年份前缀便于管理）

```
projects/
└── 2025_Grid_Distributed_Control/
```

### 步骤 2：准备封面图

将项目封面图命名为 `封面图.png`，放置在项目文件夹中：

```
projects/2025_Grid_Distributed_Control/
└── 封面图.png
```

**封面图建议**：
- 尺寸：200x200 像素或相近比例
- 格式：PNG
- 文件大小：建议小于 500KB

### 步骤 3：创建项目详情页

在项目文件夹中创建 `index.html`，可参考现有模板：

```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>项目名称 - 智能系统实验室</title>
  <link rel="stylesheet" href="../../../css/style.css" />
  <link rel="stylesheet" href="../css/project_detail.css" />
</head>
<body>
  <div id="navbar-container"></div>
  <main class="main-content">
    <!-- 项目详情内容 -->
  </main>
  <script src="../../../js/navbar-loader.js"></script>
</body>
</html>
```

### 步骤 4：修改 projects/index.html

**重要**：只需修改 `projectsData` 数组，其他部分无需改动！

找到 `projectsData` 数组并添加新项目信息：

```javascript
const projectsData = [
  {
    date: '2025',                    // 项目开始年份
    thumbnail: '项目文件夹/封面图.png',  // 封面图路径
    title: '项目标题',                // 项目名称
    category: '项目类别',              // 例如：国家自然科学重点项目
    period: '2025-2027',             // 项目周期
    summary: '项目简介...',          // 简短描述（1-2句话）
    authors: '负责人姓名',            // 项目负责人
    link: '项目文件夹/index.html'     // 详情页链接
  },
  // 添加更多项目...
];
```

**自动排序**：系统会根据 `date` 字段自动从新到旧排序，无需手动调整顺序。

## 字段说明

| 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|
| date | ✅ | 项目开始年份 | '2025' |
| thumbnail | ✅ | 封面图相对路径 | 'Grid_Distributed_Control/封面图.png' |
| title | ✅ | 项目名称 | '网格分布式控制系统研究' |
| category | ✅ | 项目类别 | '国家自然科学重点项目' |
| period | ✅ | 项目周期 | '2025-2027' |
| summary | ✅ | 项目简介 | '本项目聚焦分布式控制系统...' |
| authors | ✅ | 项目负责人 | '王燕舞, 肖江文' |
| link | ✅ | 详情页链接 | 'Grid_Distributed_Control/index.html' |

## 删除项目

1. 删除对应的项目文件夹
2. 从 `projectsData` 数组中删除对应的项目对象

## 修改项目信息

直接在 `projectsData` 数组中修改对应项目的字段值即可。

## 注意事项

1. **文件路径**：确保所有路径（thumbnail、link）相对于 `projects/index.html` 正确
2. **封面图**：如果封面图加载失败，会自动显示实验室 Logo 作为备用
3. **排序规则**：按 `date` 字段年份从大到小排序
