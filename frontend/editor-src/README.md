# 本地图文编辑器

本目录是官网图文编辑器的构建源码；运行网站只使用已提交的 `frontend/vendor/lab-editor.js`，无需Node、CDN或外部编辑服务。

- Tiptap core / StarterKit / Table / TextAlign：3.33.0（MIT），完整依赖由package-lock.json固定。
- esbuild：0.25.12，仅构建使用。
- 自定义图片节点只保存系统资产ID；官网展示用 `../js/rich-content.js` 的白名单DOM渲染器。
- 表格限定基础行列，不支持合并与自由列宽；从网页粘贴表格时简化这些属性。

重新构建（在本目录、有Node/npm的开发环境）：

```sh
npm ci
npm run build
python3 licenses.py
```

提交构建产物、lockfile及许可证；不要提交node_modules。更新依赖后收集各运行依赖LICENSE到 `../vendor/lab-editor.LICENSE.txt`，并更新引用资源的缓存键。修改编辑器／文档结构时同时验证后端校验器，防止前端可编辑但服务端无法保存。

现有线上后端未返回 `rich_content` 能力时，新前端保留旧文字编辑栏；部署必须先备份、执行0012迁移并更新后端，再开放图文编辑能力。
