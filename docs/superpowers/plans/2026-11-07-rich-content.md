# 科研图文正文 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 团队成员可编辑、保存并在官网展示带图片和表格的正文。
**Architecture:** ContentRevision 保存受限 Tiptap JSON；RevisionAsset 保持文件引用。前端本地编辑器，官网白名单 DOM 渲染。
**Tech Stack:** Django/PostgreSQL、原生 JS、MIT Tiptap 开源扩展、本地 esbuild 构建。
**Spec:** specs/V16-科研内容图文编辑与正文图片展示.md

## Global Constraints
- 当前目录、arc-update；不合并main或提前上线。
- 50,000文字、30张图片、表格20×10，所有图片必须有有效资产关联。
- 不依赖CDN或商业服务，旧客户端不得清空新正文。

## Review Focus
- 伪造图片ID和危险协议：后端拒绝，前端不创建不安全资源。
- 历史版本恢复：正文及图片引用一起恢复。
- 旧纯文本尖括号：按文字原样显示。
- 上传未结束及失败：禁止提前保存，保留正文。
- 窄屏表格与长图：页面不溢出、图片保持比例。

### Task 1: 存储、校验与版本接口
Files: content/rich_content.py、models/base.py、direct_services.py、direct_views.py、public_serializers.py、workflow/serializers.py、迁移及test_v16_rich_content.py。
Interfaces: validate_document(value)返回规范文档；image_ids(document)返回资产ID集合；revision.rich_body 可空。
- [x] 添加拒绝非法节点／链接／图片、旧客户端保留、恢复及团队边界测试，先观察失败。
- [x] 实现结构校验、迁移、资产关联、序列化和版本复制。
- [x] 执行新增测试与V12/V14回归、迁移漂移检查。

### Task 2: 编辑器和官网渲染
Files: frontend/editor-src、vendor资源、js/rich-content.js、v10.js、content-detail.js、public-page.js及相关HTML/CSS。
Interfaces: LabRich.mount(parent,{document,text,onChange,upload})；实例getDocument/getText/imageIDs；LabRich.render(document,assets,parent)。
- [x] 编写浏览器编辑、插图、表格、保存重开、团队图片权限及窄屏测试。
- [x] 固定Tiptap及esbuild版本，保留lockfile与许可证；实现本地构建和白名单渲染。
- [x] 接入编辑表单、旧正文回退、AI文字填充、正文展示与去重。
- [x] 将所有用户可见“技术文章”改为“技术博客”。
- [x] 执行浏览器测试、JS语法检查、截图检查及git diff检查。

### Task 3: 交付
- [x] 记录实际命令、结果、限制和回退方法，更新spec实施状态。
- [x] 提交推送arc-update，不修改线上镜像和数据库；部署需验收授权。

## 实施记录

用户已批准实施，直接在当前arc-update执行。采用Tiptap3.33.0替代Quill以满足表格能力；没有付费依赖。35项后端与3项浏览器测试通过；只读审查两处问题已修复并复核。详细证据、部署与回退见docs/V16-科研图文正文实施与验证.md。未部署正式运行环境。
