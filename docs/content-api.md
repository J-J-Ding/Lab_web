# V5 协同 API

与既有 [认证 API](auth-api.md)、[成员 API](member-api.md) 配合使用。所有路径同源；不配置公网数据库或第二个 Nginx。

## 认证和错误

使用 Django Session Cookie。先按认证文档获取 CSRF Cookie，所有写请求发送 `X-CSRFToken`，登录后重新读取轮换后的 Cookie。Fetch 使用 `credentials: 'same-origin'`；不在 localStorage 保存密码或 Session。业务字段不能传入 role、is_staff、is_superuser、reviewer 等身份字段。

业务错误包含 `code`、`detail`、`fields`。400 输入不合法，403 身份/权限/CSRF 拒绝，404 对象不存在或不可见，409 版本或状态冲突，429 限流，503 数据库/审计暂不可用。不要自动重放写请求。分页列表使用返回的 next/previous；筛选只接受白名单字段。响应不包含密码哈希、Session 密钥或裸文件存储路径。

## 内容与审核

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/content/capabilities/` | 当前提交/管理能力 |
| GET | `/api/content/projects/` | 可安全选择的项目，支持 q |
| GET/POST | `/api/content/contributors/` | 可见贡献者 / 创建外部署名，不自动绑定账号 |
| GET/POST | `/api/content/items/` | 可见列表 / 创建；列表支持 kind、state、scope |
| GET | `/api/content/items/{id}/` | 对象和版本概览 |
| POST | `/api/content/items/{id}/revisions/` | 克隆新稿，lock_version，可选 source_revision |
| PATCH | `/api/content/revisions/{id}/` | 保存 DRAFT，必须携带当前 lock_version |
| POST | `/api/content/revisions/{id}/submit/`、`withdraw/`、`discard/` | 提交、撤回、放弃；携带 lock_version |
| GET | `/api/content/items/{id}/history/`、`moderation-history/` | 版本审核历史 / 管理动作理由历史 |
| POST | `/api/content/items/{id}/grants/` | lock_version、user_id、can_edit、revoke |
| POST | `/api/content/items/{id}/archive/`、`unarchive/`、`unpublish/` | lock_version、reason；独立动作 |
| POST | `/api/content/items/{id}/corrections/` | reason，发起纠错 |
| GET | `/api/content/confirmations/` | 本人的待确认署名摘要，不授予整篇私稿阅读权 |
| POST | `/api/content/contributions/{id}/confirm/` | decision=CONFIRMED/DISPUTED；争议必须 reason |
| GET | `/api/review/tasks/` | 审核任务，包含 can_review |
| POST | `/api/review/revisions/{id}/decision/` | decision=APPROVE/REJECT、reason、lock_version |
| POST | `/api/review/contributions/{id}/confirm/` | 管理者证据代确认，必须提供理由 |
| GET | `/api/review/corrections/` | 纠错任务 |
| POST | `/api/review/corrections/{id}/resolve/` | reason，处理纠错 |

创建技术博客请求体示例：

```json
{"kind":"BLOG","title":"实验记录","summary":"实验方法说明","detail":{"body":"正文","category":"实验"},"contributions":[]}
```

根据响应取得对象、工作版本 ID 和 lock_version，再保存版本：

```json
{"lock_version":1,"title":"实验记录修订","summary":"更新摘要","detail":{"body":"修订正文","category":"实验"}}
```

数字仅作格式示例，实际必须使用最新响应中的版本。保存成功后，以新的 lock_version 提交；合格审核者（包括允许自审的本人）读取任务和快照后发送：

```json
{"decision":"APPROVE","reason":"已核对正文和署名","lock_version":3}
```

CUSTOMER 不具备内容投稿资格；符合条件的正式成员或管理者可投稿。ROOT、ADMIN、TEACHER 均可审核自己提交或编辑的版本，仍需正常提交和填写审核理由。参与署名不自动获得协作编辑权。公开版本 A 的新稿 B 未获批前，公开选择器仍返回 A。

## 身份申请和成员资料

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET/POST | `/api/members/applications/` | 本人申请；application_kind=STUDENT/TEACHER、statement，可选 target_profile/proof_asset |
| POST | `/api/members/applications/{id}/withdraw/` | lock_version，撤回 |
| GET | `/api/review/member-applications/` | 有权审核的身份申请 |
| POST | `/api/review/member-applications/{id}/decision/` | decision、reason、lock_version，可选 use_applicant_fields |
| GET/POST/PATCH | `/api/members/me/draft/` | 读取、创建、保存本人资料草稿，沿用 V4 契约 |
| POST | `/api/members/me/draft/submit/` | lock_version、public_visible、contact_visible、education_visible、alumni_visible |
| POST | `/api/members/me/draft/withdraw/` | lock_version，撤回资料稿 |
| POST | `/api/members/me/privacy/restrict/` | scopes 数组：public/contact/education/alumni，即时收紧 |
| GET | `/api/review/member-revisions/` | 合法范围内的资料候选及公开授权 |
| POST | `/api/review/member-revisions/{id}/decision/` | decision、reason、lock_version |
| GET/POST | `/api/admin/members/` | 管理档案；创建 display_name、member_kind，不自动公开 |
| POST | `/api/admin/members/{id}/bind/` | user_id，显式绑定，不改变角色或自动发布 |

认领只处理未绑定目标；已有成果/贡献者关联等冲突须人工处理，不自动搬迁署名。教师档案类型不自动授予 TEACHER。CUSTOMER 通过身份审批获得 STUDENT 投稿资格。独立角色管理继续遵守用户明确要求的 V2 规则：ADMIN/TEACHER 可在 CUSTOMER、STUDENT、TEACHER 之间管理普通账号，不能接管或提升 ADMIN、ROOT；ROOT 可管理 ADMIN。ROOT 仅由服务器命令创建。

ROOT 可管理全部档案并自审；ADMIN 可审核本人资料/申请，但不能查看或接管其他 ADMIN/ROOT 私密档案；TEACHER 可自审本人资料，其他账号范围不变。公开授权随隐私版本记录，收紧之后旧待审授权作废，恢复需重新提交并由有权管理者审核。

## 私有文件

`POST /api/assets/` 使用 multipart：purpose 为 avatar 或 proof，file 为文件。头像 JPEG/PNG/WebP ≤5MiB；证明 PDF ≤10MiB。必须携带最新 CSRF。每账户默认 900 秒内限制 20 次上传尝试，并检查每小时成功存储数量。清洗失败不入可用资产库。

`GET /api/assets/{id}/download/` 仅本人或有权处理相关申请/档案的审核者可下载；不提供裸媒体目录。文件默认私有，未获保留的文件默认 30 天过期；获批引用头像保留。清理命令默认 dry-run。解析、清洗及资源限制详见 [工作流说明](workflow.md)，不等同完整防病毒扫描。公共头像与官网数据渲染留到 V6。

## V6 附件扩展

内容版本 PATCH 增加 `assets: [UUID,…]`，最多 30 项。新增文件要求当前编辑者所有权，协作者可保留版本已有合法引用；不能通过 UUID 偷加其他人的资产。`revision_data.assets` 返回引用 ID，编辑/审核界面提供受控私有下载。内容批准时复核 CLEAN/用途/到期/删除请求并转 PUBLIC，但匿名下载仍须当前公开版本引用。新增 owner 的 `POST /api/assets/{id}/delete/` 只请求删除，不破坏历史引用。详见 [媒体存储](media-storage.md) 与 [公共 API](public-api.md)。
