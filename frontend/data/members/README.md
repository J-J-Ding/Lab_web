# 团队成员栏目使用文档

## 📋 目录结构

```
members/
├── index.html                          # 成员列表页（主入口）
├── css/
│   └── member_detail.css              # 成员详情页样式
├── teachers/                          # 教师目录
│   ├── Jiangwen_Xiao/               # 教师个人文件夹（姓名拼音）
│   │   ├── index.html               # 教师个人详情页
│   │   └── 肖江文.png                # 教师头像
│   ├── Xiaokang_Liu/
│   ├── Yanwu_Wang/
│   └── ...
└── students/                          # 学生目录
    ├── Junjie_Ding/
    │   ├── index.html
    │   └── 丁俊杰.jpg
    └── ...
```

## 🎯 功能概述

本栏目实现了团队成员的集中管理，支持：
- 📝 成员列表展示（支持教师/学生分类筛选）
- 👤 成员个人详情页
- 🔗 自动关联论文列表
- 📚 论文引用格式展示

---

## 📝 添加新成员

### 步骤 1: 创建成员文件夹

1. 在 `teachers/` 或 `students/` 目录下创建新文件夹
2. **文件夹命名规则**：使用成员姓名的拼音，首字母大写，用下划线分隔
   - 例如：`Jiangwen_Xiao`、`Junjie_Ding`

### 步骤 2: 准备成员资料

- 头像图片：建议尺寸 200x200px，支持 png/jpg 格式
- 命名规则：中文姓名.png 或中文姓名.jpg

### 步骤 3: 创建成员详情页

在成员文件夹中创建 `index.html`，复制已有模板 `teachers/Jiangwen_Xiao/index.html` 或 `students/Junjie_Ding/index.html`。

---

## 📤 添加成员到列表

### 步骤 1: 编辑 members/index.html

在 `membersData` 数组中添加新成员信息：

```javascript
const membersData = [
    // 现有成员...

    // 添加新成员（教师）
    {
        type: 'teacher',                      // 成员类型：teacher 或 student
        name: '姓名',                         // 中文姓名
        role: '教授/职位',                    // 职位或年级
        email: 'email@hust.edu.cn',          // 邮箱地址
        avatar: 'teachers/文件夹名/头像.png', // 头像路径
        link: 'teachers/文件夹名/index.html', // 详情页链接
        research: [                          // 研究方向数组
            '研究方向1',
            '研究方向2'
        ]
    },

    // 添加新成员（学生）
    {
        type: 'student',
        name: '姓名',
        role: '2024级硕士研究生',
        email: 'email@hust.edu.cn',
        avatar: 'students/文件夹名/头像.jpg',
        link: 'students/文件夹名/index.html',
        research: [
            '研究方向'
        ]
    }
];
```

### 步骤 2: 更新成员数量统计

系统会自动根据 `membersData` 数组统计成员数量，无需手动修改。

---

## 📚 关联论文

### 论文关联方式

在成员详情页的「发表论文」部分，每篇论文通过以下方式展示：

```html
<!-- --------------------- -->
<a href="../../../papers/A new deep clustering method with application to customer selection for demand response program/index.html" class="reference-link" style="color: #ffffff !important; text-decoration: none !important;">  <!-- 需要修改 -->
    <div class="project-item">
        [1] Xiao J W, Xie Y, Fang H, et al. A new deep clustering method with application to customer selection for demand response program[J]. International Journal of Electrical Power & Energy Systems, 2023, 150: 109072.  <!-- 需要修改 -->
    </div>
</a>
<!-- --------------------- -->
```

### 引用格式说明

推荐使用标准的学术引用格式

---

## 🎨 样式定制

### 成员详情页样式

样式文件：`css/member_detail.css`

主要样式类：

- `.member-header.teacher` - 教师头部样式（紫色渐变）
- `.member-header.student` - 学生头部样式（粉色渐变）
- `.info-section` - 信息区块
- `.project-item` - 项目条目
- `.publication-item` - 出版物条目

### 自定义颜色

可在 CSS 中修改以下变量：

```css
:root {
  --member-gradient-teacher: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --member-gradient-student: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}
```

---

## 📱 页面导航

### 左侧导航栏

成员列表页提供三个视图：
- **所有成员**：显示教师和学生
- **教师列表**：仅显示教师
- **学生列表**：仅显示学生

### URL 锚点

可以直接通过 URL 锚点跳转到特定分类：
- `members/index.html#all-members` - 所有成员
- `members/index.html#teachers` - 教师列表
- `members/index.html#students` - 学生列表

---

## 📌 注意事项

1. **文件夹命名**：严格使用拼音命名，首字母大写，用下划线分隔
2. **图片格式**：建议使用 png 或 jpg 格式，避免使用特殊字符
3. **路径问题**：确保所有相对路径正确，特别是论文链接
4. **数据一致性**：`membersData` 中的数据与实际成员文件夹保持一致
5. **响应式设计**：页面已适配移动端，无需额外处理

---

## 🚀 快速开始

1. 复制现有成员文件夹作为模板
2. 修改文件夹名称和个人信息
3. 在 `members/index.html` 中添加成员数据
4. 完成！

---

## 📞 技术支持

如有问题，请联系技术负责人或提交 Issue。
