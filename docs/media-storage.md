# V6 私有存储与受控媒体

沿用 private_media 卷、随机存储键与 0600 文件权限。数据库新增 AssetFile.purpose 和 deletion_requested_at；purpose 区分 avatar/proof/image/attachment。上传始终先存 PRIVATE，响应不含实际路径。V5 已有图片在迁移时识别为 avatar，证明仍为 proof；只有当前已批准、公开且未到期的清洁头像回填为 PUBLIC，其余保持原有可见性。

## 上传与检查

`POST /api/assets/` 仍使用 Session、multipart 和最新 X-CSRFToken。avatar/image 接受 JPEG/PNG/WebP ≤5MiB；proof 接受 PDF ≤10MiB；attachment 接受 PDF/DOCX ≤20MiB。文件后缀、MIME、魔数、大小须一致，拒绝 SVG/HTML/脚本。原有按账号上传尝试及每小时存储数量限制继续生效。

图片由 Pillow 解码，限制单帧及一千万像素，重编码为 PNG 去除元数据和附带字节。PDF 由 pypdf 严格解析、限制 1–100 页和对象遍历，拒绝脚本/动作/表单/嵌入内容等再重写。DOCX 限 2000 个 ZIP 条目、50MiB 总展开量、20MiB 单条目、100 倍压缩比；禁止绝对/穿越路径、重复名、加密、宏、ActiveX、OLE/嵌入二进制、外部关系、DTD/实体。XML 仅接受 UTF-8；媒体限受检栅格图并重编码。普通内部关系不执行、不解压到宿主机目录。

检查子进程限制 256MiB 内存、5 秒 CPU、8 秒超时以及 20MiB 输入输出；不传 Django/数据库凭据。该机制是结构校验与清洗，不宣称完整杀毒或操作系统沙箱。更完整扫描/生产文件策略留后续阶段。

## 引用与下载

内容草稿 PATCH 的 `assets: [UUID,…]` 最多 30 项：新增资产须属于当前编辑者且已检验；协作者可以保留本稿已有合法引用，不能凭 UUID 偷加他人文件。编辑器支持上传、移除引用与私有下载。独立审核者及有效协作授权者按内容对象可见性下载待审附件；授权撤销后失效。证明/高权限成员私密档案保护继续沿用 V5。

V5 独立审批发布内容时，事务内复核所引用资产，才将图片/附件转 PUBLIC 并保留；成员头像同样经本人授权、独立审批后公开。公共下载额外检查当前公开指针与即时 gate；历史发布引用、DRAFT、撤下对象或收紧的成员均不能单独使文件公开。下载不提供裸 media alias，不修改系统 Nginx 路由。

`POST /api/assets/{id}/delete/` 仅 owner 可请求删除，记录时间与审计，不立即破坏引用。历史、当前、草稿、成员/申请中的任何引用均阻止物理清理。`python manage.py cleanup_private_assets` 默认 dry-run，`--apply` 才处理过期私有孤立文件；V6 未启用自动定时删除。已公开资产和历史引用保留，不承诺一键物理删除。导入单条记录失败会回滚数据库并清除本条新写入字节。

Nginx 默认请求上限可能低于附件大小。正式部署经批准后，在原 `/api/` location 设置 `client_max_body_size 21m;`，保留现有反代及静态配置，先 nginx -t 再 reload。不得给 legacy_samples/originals 或 private_media 配置 alias。


### 简历删除（V14追加）

`POST /api/members/me/resumes/{id}/delete/`携带`lock_version`，仅当前账号可删除自己的简历。删除标记使列表、编辑、重新投递和收件箱访问立即不可用，并撤回有效投递。事务提交后删除不再被其他有效简历/业务引用的当前及投递文件；被其他简历共用时保留到最后一个引用删除。不可变投递元数据与审计保留，已删除简历不提供恢复。文件删除失败可用`cleanup_private_assets --apply`重试；资产一旦标记删除，受控下载即拒绝，不以是否仍留存字节为依据。此特例不改变其他业务历史附件的引用保留规则。
