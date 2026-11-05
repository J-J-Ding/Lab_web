# V7：AI 文档解析与智能内容填充

- 状态：待评审；依赖 V6 文件安全、成员/成果版本和 V5 审核流程。
- 目录 `/opt/Lab_web`，分支 `arc-update`；共同约束见[总体规划](V4-V9-后续开发总体规划与验收基线.md)。
- 用户指定 DeepSeek Flash。本次仅保存服务器环境配置，不调用 API，不证明密钥有效、余额充足或模型可用。

## 1. 目标与不做事项

用户上传 PDF/DOCX 简历、论文、项目材料和证书，获得可编辑的候选字段、来源片段及不确定提示，确认后写入草稿。AI 不直接发布、不审批、不授予任何角色、不自动绑定成员/外部作者，不提供访问数据库/文件系统的工具代理。

只支持有文本层 PDF 和 DOCX 的确定性解析；扫描件检测后明确显示“需要 OCR/人工录入”，不伪称提取成功。扫描证书 OCR/视觉识别如确需实现，单独评审子方案、成本、识别样本与隐私范围后再加入；当前证书仅文本型可解析。AI 生成简介/摘要是候选文本，保留事实依据并人工确认。

## 2. 供应商与配置

2026-11-06 查阅官方文档：兼容 OpenAI 格式的 base_url 为 `https://api.deepseek.com`，Flash 模型 ID 为 `deepseek-flash`；具体能力与限额实施时再次检查。

参考：[DeepSeek 首次调用文档](https://api-docs.deepseek.com/)、[模型列表](https://api-docs.deepseek.com/api/list-models/)。仅采用官方接口，不把用户文档交给第三方中转站。

拟议环境变量：

```dotenv
AI_ENABLED=False
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
AI_CONNECT_TIMEOUT_SECONDS=5
AI_REQUEST_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=2
AI_MAX_INPUT_TOKENS=24000
AI_MAX_OUTPUT_TOKENS=4000
AI_USER_DAILY_LIMIT=10
AI_GLOBAL_DAILY_LIMIT=100
AI_GLOBAL_DAILY_BUDGET_CNY=10
AI_SOURCE_RETENTION_DAYS=7
AI_CANDIDATE_RETENTION_DAYS=30
```

这些是本次建议默认值，实施时验证所用 SDK 参数；每次调用仍须显式限制输入/输出，不能直接使用供应商最大窗口。请求默认关闭思考以控制提取延迟，使用实际官方支持参数，unsupported 时明确失败而不悄悄切换高价模型。

用户已授权将真实 key 存于本机被 Git 忽略的 `.env`（权限 0600）。本 spec 与未来 `.env.example` 只含空占位；现有 Compose 未注入这些变量，容器不会仅因 `.env` 增加键就自动获得配置。V7 再将必要变量传给后端/worker，默认 AI_ENABLED=False，不在浏览器暴露 key 或代理请求到供应商。`lab_web` 只作为用户提供的服务标识，不假定是模型 ID、密码或供应商正式项目参数。

密钥曾出现在会话中，建议负责人轮换后更新 `.env`；禁止在故障日志、完整 Compose 输出、截图、管理页面或错误响应中回显。AI 管理页只显示是否配置、模型和额度。模型名可换，供应商适配器接口保持不变。

## 3. 流程、模型与任务

流程：上传私有文件→安全校验→展示发送范围与授权→任务排队→本地提取→最小化/分段→AI候选→schema校验→人工逐项核对→应用草稿→常规审核发布。

新增：

| 模型 | 内容 |
| --- | --- |
| AIImportJob | UUID、owner、asset、目标类型、状态、lease/heartbeat、attempts、模型/提示版本、输入摘要、created/finished/expires_at、脱敏错误码 |
| AIConsent | job、授权者、授权版本、发送字段范围、时间；撤销后未发送任务取消 |
| AICandidate | job、schema_version、结构化候选、字段证据页码/片段、uncertain_fields、confirmed_at、applied_revision |
| AIUsageLedger | user/job、请求标识摘要、预留/实际 token与金额、状态、UTC计费日/上海业务日；job/request 幂等键 |
| AIQuotaBucket | 用户/全站每日计数与预留额度、数据库唯一键 |

任务状态 QUEUED→EXTRACTING→CALLING→VALIDATING→READY→APPLIED；失败 FAILED，取消 CANCELLED，过期 EXPIRED。独立 worker 复用应用镜像，无宿主端口，数据库 `select_for_update(skip_locked=True)` 领取任务，lease 失效有限重试。不要在 HTTP 请求中解析大文件或等待模型。

不能在 DB 事务持锁期间发网络调用；先事务预留预算、领取任务，再外部请求，再事务记录结果。崩溃在计费后、落库前可能不能保证上游 exactly-once，使用稳定请求摘要尽量去重并标为 UNKNOWN_USAGE；未知计费保留预算直到对账，禁止不加区分反复重发。

## 4. 解析与结构化契约

- 文件默认 PDF/DOCX≤20 MiB、PDF≤100页、DOCX 解压总量≤100 MiB且压缩比受控、提取文本≤100000字符；超过分批/明确失败，不截断后默默造完整结果。
- 本地 parser 在受限 worker 中运行，限制 CPU/内存/耗时，无 shell 执行、无宏、无外部链接抓取。DOCX 不执行内嵌对象；PDF 不执行动作/JavaScript。
- 凭据、身份证号、银行卡等不必要信息先拦截/脱敏，账号邮箱/电话只有明确用途与授权才发送；提取预览允许用户取消。文件内部的“忽略指令”等仅视为数据，不能改变系统指令、调用工具或读取密钥。
- Provider 接口 `extract_fields(text, target_schema, context) -> ProviderResult`、`generate_summary(verified_fields) -> ProviderResult`；适配 DeepSeek，不在领域模型中绑定 SDK 响应对象。仅服务端 JSON Schema 校验通过的字段可进入候选；模型输出 JSON 模式不是安全边界。
- 候选示例：`schema_version`、`target_type`、`fields`、`evidence[{field,page,excerpt}]`、`uncertain_fields`、`warnings`。未知字段拒绝；禁止 role/is_staff/is_superuser/reviewer/published_revision 等权限与工作流字段。
- 日期、DOI、作者、学校、姓名按 V4 校验；不确定留空或待确认，不编造缺失信息。没有来源的模型自评置信度不作为自动采信依据。
- 文档内多篇成果逐条候选，保存时查 DOI/项目号并显示已有对象/申请纠错，不自动合并。重名成员和外部合作者必须人工匹配；只允许访问当前用户可见的匹配候选。

## 5. API 与页面

| 方法/路径 | 功能 |
| --- | --- |
| POST `/api/ai/imports/` | 私有 asset UUID、target_type、consent_version，验证归属后返回 202/job UUID |
| GET `/api/ai/imports/`、`{uuid}/` | 本人状态、脱敏错误与候选；分页 |
| POST `/api/ai/imports/{uuid}/cancel/` | 取消尚可取消的任务，不承诺收回已发送的供应商请求 |
| PATCH `/api/ai/imports/{uuid}/candidate/` | 用户修改候选，服务端字段白名单/版本锁 |
| POST `/api/ai/imports/{uuid}/apply/` | 显式确认字段、target UUID、lock_version，写草稿、不发布 |
| DELETE `/api/ai/imports/{uuid}/` | 删除候选/申请清理原件，记录脱敏元数据；应用过的业务草稿不级联删除 |
| POST `/api/ai/summaries/` | 对本人已确认字段生成简介/摘要，单独额度与人工确认 |
| GET `/api/ai/quota/` | 本人剩余额度/功能状态，不含 key |

所有接口 Session/CSRF 与对象归属；CUSTOMER 仅本人档案导入，不能用 AI 绕过投稿资格。apply 需审核该用户对目标草稿的编辑权，锁定 job+目标并幂等，同一候选不能重复创建多篇论文；草稿已变返回 409，保留候选以供重新对比。

新增 `frontend/ai-import.html`、js/ai-import.js、scoped CSS：分步上传、隐私授权、进度、原文证据/候选对照、逐项选择、编辑与“保存为草稿”。轮询使用退避/取消，不持续每秒请求；429 显示额度，503 不报假成功。不能将候选不可信 HTML 插入页面。

## 6. 费用、限流、保留与可用性

默认每人10次/日、全站100次/日，另有每用户同时1任务、全站同时2任务和每日预算10元（均待评审）。预估 token/单价后事务预留，调用后按 usage 实结；价格配置带生效日期，不在 spec 写死供应商当前价。无法计算费用时按保守上限占用，预算不足不发请求；管理员不能从浏览器跳过额度。

超时/429/5xx 仅有限指数退避（尊重 Retry-After、总时长≤180秒）；400/401/403 不重试，返回友好提示。设置熔断、总预算和队列上限，AI 不可用时仍能手工录入。失败任务不无限占用 worker。

原件默认7天、候选30天、使用量与脱敏审计180天，均为拟议保留策略。定时清理尊重正在执行/已引用文件，dry-run 可审查；说明备份中的副本按备份保留周期自然到期，不能宣称本地删除能立刻擦除供应商或所有备份。用户上传前说明第三方处理范围。

## 7. 文件清单与实施顺序

新增 `backend/apps/ai_assistant/` 的 models、providers/base.py、providers/deepseek.py、extractors、schemas、services、tasks、quota、views/urls、permissions、管理命令 run_ai_worker/cleanup_ai_imports 和迁移；assets 增强文档安全；新增 worker Compose 服务与资源限制、环境变量占位和固定版 SDK/parser 依赖（实施时核验版本）。

新增 AI 页面和浏览器测试，`docs/ai-import.md`、`docs/ai-operations.md`、`docs/V7-验收报告.md`。不变更 Nginx、不暴露 key、不提交真实简历和原文日志。

任务顺序：安全/配额/恶意文档失败测试→本地提取→provider mock→持久任务/恢复→候选和人工 apply→前端→显式授权的小额真实调用→回归/清理。真实调用使用虚构文档，费用写入报告。

## 8. 必须实际验收与回退

运行共用完整 Django/Playwright 测试，并覆盖有效 PDF/DOCX、空文档、损坏件、扫描件提示、超限、ZIP炸弹、恶意提示、字段造假、未知 JSON、无效日期、多人关联匹配、并发预算预留、超时重试、worker 崩溃 lease 恢复、取消/清理、跨用户取候选拒绝、CSRF、AI禁用、保存幂等/冲突，以及确认后仅草稿、不自动发布/升权。

自动化用可控 provider 模拟异常，不能把 mock 说成真实 DeepSeek 联通。交付前必须有一次经负责人授权的脱敏真实调用：记录模型、成功/失败、耗时和 token/费用，不记录 key/完整文档。若 key 无效/余额不足/网络阻断，明确“真实模型调用未验证”，不能宣布 V7 全部验收完成；手工流程应继续可用。

回退将 AI_ENABLED=False、停止领取新任务、等待或取消在途任务，退回兼容镜像/隐藏 AI入口；不删除已确认草稿/已有成果，不丢弃未知计费账本。密钥轮换只改服务器环境并在授权后重建需要的服务，禁止在报告回显。
