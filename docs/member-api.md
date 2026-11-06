> V10变更：本文保留旧版本契约供历史追溯。新直接保存、身份权限、简历及首页接口以 [V10使用与部署说明](V10-使用与部署说明.md) 为准；旧提交/审核流程已停用。

# V4 本人成员草稿与关联成果 API

V4 仅提供私有接口；未开放成员管理、身份审批、投稿审核、公开成员/成果 API 或文件上传。前端仍是 V3。API 代码完成不代表已部署到运行中的后端。

认证沿用 [auth-api.md](auth-api.md)：先 GET `/api/auth/csrf/`，登录时携带 Cookie 与 X-CSRFToken；登录后读取轮换 token，所有 POST/PATCH 继续携带 Cookie 与最新 token。不改变现有角色权限。

| 方法/路径 | 请求 | 返回 |
| --- | --- | --- |
| GET `/api/members/me/draft/` | 无 | 200，`{"draft":null}` 或本人草稿；不创建业务记录 |
| POST `/api/members/me/draft/` | `{}` | 201 初始化/复制草稿，已存在可编辑草稿则200并返回同一UUID；不授予成员角色 |
| PATCH `/api/members/me/draft/` | lock_version 必填及允许字段 | 200更新本人草稿；版本过期或当前稿已提交则409 |
| GET `/api/members/me/overview/` | 无 | 本人档案UUID、内部资格、草稿状态、有无公开版本、已公开成果数 |
| GET `/api/content/participations/` | kind/page/page_size | 200分页，仅本人关联且已发布未撤下的成果；同一成果只返回一次 |

所有已登录且未禁用角色均可维护本人草稿；CUSTOMER不因此获得投稿/管理权。没有他人档案详情端点；枚举 `/api/members/<UUID>/` 为404，管理员也不能借“本人”接口读取别人。无有效Session或缺少CSRF为403，未知/只读字段和非法日期400，初始化之前PATCH为404，数据库/审计故障脱敏503。所有私有响应 no-store。

PATCH 允许字段：display_name（≤150）、slug（≤160、仅草稿不预占公开URL）、bio（≤10000）、public_contact_email、public_contact_enabled、avatar_asset（本人持有且检查通过的图片UUID或null）、education、research_areas、alumni。

role、is_staff、is_superuser、user、member_kind、public_member_status、membership_status、state、发布/草稿指针、创建人/审核人均只读或不接受。成员类型在V5审核流程赋值，教师档案不自动等于TEACHER管理权。手机号和内部备注不在该公开资料草稿接口内。

```json
{
  "lock_version": 0,
  "display_name": "示例成员",
  "bio": "智能控制研究",
  "public_contact_email": "public@example.org",
  "public_contact_enabled": true,
  "education": [{"school":"示例大学","degree":"硕士","position":1,"is_public":false}],
  "research_areas": ["智能控制"],
  "alumni": null
}
```

education/research_areas 传入时替换整个草稿集合，各最多30项；未传保持原值。教育起止日期可空但顺序必须合法，position正整数且不重复；alumni支持null清空，graduation_year为1900至当前年+10，destination_type为WORK/STUDY/OTHER。布尔和版本号严格要求JSON boolean/integer，不能用字符串/true伪装版本号。开启公开联系必须单独提供public_contact_email，绝不自动复制账号email。

返回包含草稿id、number、lock_version、state、只读member_kind/public_member_status、上述资料和嵌套列表。GET包装在draft字段，POST/PATCH直接返回草稿对象；PATCH成功lock_version递增。保存只改草稿，已发布快照和即时隐私门保持原值；真正公开须V5审核。

成果分页沿用count/next/previous/results，默认20最大100；kind仅PAPER/PROJECT/AWARD/ACTIVITY/NEWS/BLOG/PUBLICATION/LAB_PAGE，未知筛选400。条目只含稳定内容UUID、类型、发布版本UUID、标题摘要与署名快照，不含其他草稿、内部经费、账号联络、文件真实路径。

调用示例复用auth-api文档的安全Cookie jar与`lab_write`辅助函数：

```bash
printf '%s' '{}' > "$LAB_AUTH_TMP/empty.json"
lab_write POST /api/members/me/draft/ "$LAB_AUTH_TMP/empty.json"
# empty.json 内容为 {}，draft.json 为上面经核对的请求，lock_version须取最新响应。
lab_write PATCH /api/members/me/draft/ "$LAB_AUTH_TMP/draft.json"
curl --fail-with-body -b "$LAB_AUTH_TMP/cookies" http://127.0.0.1:8000/api/members/me/overview/
curl --fail-with-body -b "$LAB_AUTH_TMP/cookies" 'http://127.0.0.1:8000/api/content/participations/?kind=PAPER&page=1'
```

以上为部署V4后的示例；本次不会自动更新生产容器，当前运行V2后端尚无这些接口。不要将真实Session、密码或请求私人数据提交Git。

## V5 扩展

身份申请、认领、公开资料审批、隐私收紧与受控文件上传详见 [协同 API](content-api.md)。本人 draft 响应增加只读 publication_consent、consent_current；公开授权与 privacy_version 绑定，收紧后旧授权不能恢复公开。本人写入在账号锁内重查 Session、角色和禁用状态；不要依赖前端页面判断权限。V4/V5 代码验收与线上部署是独立步骤，见 [部署手册](v5-deployment.md)。
