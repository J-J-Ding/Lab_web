# 出版刊物管理操作手册

本指南介绍如何在 Lab_test/data/publications 目录下添加和管理出版刊物内容。

## 目录结构

```
Lab_test/data/publications/
├── index.html          # 刊物列表页（自动排序）
├── README.md           # 本操作手册
└── [刊物文件夹]/
    ├── 封面图.png      # 刊物封面图
    └── index.html      # 刊物详情页
```

## 添加新刊物步骤

### 步骤 1：创建刊物文件夹

在 `publications/` 目录下创建新刊物文件夹，命名格式建议：`YYYYMM_刊物名称`

```
publications/
└── 202506Deep_Learning_Book/
```

### 步骤 2：准备封面图

将刊物封面图命名为 `封面图.png`，放置在刊物文件夹中：

```
publications/202506Deep_Learning_Book/
└── 封面图.png
```

**封面图建议**：
- 尺寸：200x200 像素或相近比例
- 格式：PNG
- 文件大小：建议小于 500KB

### 步骤 3：创建刊物详情页

在刊物文件夹中创建 `index.html`，可参考现有模板：

```html
<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <title>刊物名称 - 智能系统实验室</title>
  <link rel="stylesheet" href="../../../css/style.css" />
</head>
<body>
  <div id="navbar-container"></div>
  <main class="main-content">
    <!-- 刊物详情内容 -->
  </main>
  <script src="../../../js/navbar-loader.js"></script>
</body>
</html>
```

### 步骤 4：修改 publications/index.html

**重要**：只需修改 `publicationsData` 数组，其他部分无需改动！

找到 `publicationsData` 数组并添加新刊物信息：

```javascript
const publicationsData = [
  {
    date: '2025-06',                    // 出版日期
    thumbnail: '刊物文件夹/封面图.png',    // 封面图路径
    title: '刊物标题',                   // 刊物名称
    type: '学术专著',                    // 刊物类型
    pages: '456页',                     // 页数
    summary: '刊物简介...',             // 简短描述（1-2句话）
    authors: '作者姓名',                 // 作者
    link: '刊物文件夹/index.html'        // 详情页链接
  },
  // 添加更多刊物...
];
```

**自动排序**：系统会根据 `date` 字段自动从新到旧排序，无需手动调整顺序。

## 字段说明

| 字段 | 必填 | 说明 | 示例 |
|------|------|------|------|
| date | ✅ | 出版日期（YYYY-MM） | '2025-06' |
| thumbnail | ✅ | 封面图相对路径 | '202506Deep_Learning_Book/封面图.png' |
| title | ✅ | 刊物名称 | '深度学习原理与应用' |
| type | ✅ | 刊物类型 | '学术专著', '教材', '译著' |
| pages | ✅ | 页数 | '456页' |
| summary | ✅ | 刊物简介 | '本书系统介绍了...' |
| authors | ✅ | 作者 | '王燕舞, 肖江文' |
| link | ✅ | 详情页链接 | '202506Deep_Learning_Book/index.html' |

## 删除刊物

1. 删除对应的刊物文件夹
2. 从 `publicationsData` 数组中删除对应的刊物对象

## 修改刊物信息

直接在 `publicationsData` 数组中修改对应刊物的字段值即可。

## 注意事项

1. **文件路径**：确保所有路径（thumbnail、link）相对于 `publications/index.html` 正确
2. **封面图**：如果封面图加载失败，会自动显示实验室 Logo 作为备用
3. **排序规则**：按 `date` 字段日期从大到小排序
4. **HTML 标注**：index.html 中标注了 `<!-- 需要修改 -->` 的部分才是需要修改的，其他代码请勿改动
5. **空状态**：如果 `publicationsData` 为空，页面会显示"暂无刊物"提示
6. **日期格式**：使用 `YYYY-MM` 格式，如 '2025-06'，页面会自动显示为 "2025年6月"

## 常见问题

**Q: 刊物顺序不对？**
A: 检查 `date` 字段是否正确，系统会自动按出版日期从新到旧排序。

**Q: 封面图显示不出来？**
A: 确认封面图路径正确，文件存在，且格式为 PNG。如果图片加载失败会自动使用实验室 Logo。

