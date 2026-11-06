> V10变更：本文保留旧版本契约供历史追溯。新直接保存、身份权限、简历及首页接口以 [V10使用与部署说明](V10-使用与部署说明.md) 为准；旧提交/审核流程已停用。

# V6 公共 API

公共接口只读、无需登录，Session 不增加其可见范围。所有响应 `Cache-Control: no-store`，写请求 405。当前实现不使用共享响应缓存，撤下、隐私收紧和资产引用变更在下一次请求立即生效。已获批准的旧版本在新稿待审期间保持展示。正文作为纯文本渲染，不执行 HTML/Markdown。

| GET 路径 | 范围和参数 |
| --- | --- |
| `/api/public/content/` | 当前 PUBLISHED 指针且 visibility_gate 开启；kind、year、category、q |
| `/api/public/content/{uuid}/` | 同一对象公开快照，不含 working_revision 或内部经费 |
| `/api/public/members/` | 已发布 ACTIVE/ALUMNI、public_visible、未合并；member_kind、direction、status、year、q |
| `/api/public/members/{slug}/` | 当前 slug 和历史 MemberSlug 均可，返回当前 slug |
| `/api/public/members/{slug}/achievements/` | 当前公开版本参与关系派生成果；kind、year |
| `/api/public/projects/{uuid}/outputs/` | 项目与输出双方均公开；kind、year |
| `/api/public/graduates/` | 同一成员库 ALUMNI，alumni_visible 且该去向明确公开；year、degree |
| `/api/public/pages/{key}/` | 仅 home/about 当前批准快照 |
| `/api/public/legacy/?path=…` | 规范旧 HTML 路径映射到当前公开对象；未发布/撤下时统一 404 |
| `/api/public/assets/{uuid}/` | CLEAN、PUBLIC、未到期、被当前公开版本实际引用的图片/附件 |

列表返回 `{count,next,previous,results}`；默认 20、最大 100，正整数 page/page_size。内容按业务日期降序、UUID 稳定排序；成员按公开姓名和 UUID。q 为 2–100 字符，只查发布的标题、摘要、正文或公开成员资料。未知/重复参数、非法年份、过长参数、非法枚举为 400；无对象或不可见为 404；数据库不可用为安全的 503，不泄露数据库细节。年份 1900–2200，kind 为现有八种 ContentKind。页码越界由分页器返回 404。列表页提供搜索、年份和翻页；其他筛选可按 API 参数调用。

```bash
curl --fail 'http://127.0.0.1:8000/api/public/content/?kind=PAPER&year=2026&page_size=20'
curl --fail 'http://127.0.0.1:8000/api/public/members/?member_kind=STUDENT&status=ACTIVE'
```

内容返回 id、kind、revision、title、summary、date、detail、contributions、projects、assets。贡献者名称/单位使用批准署名，不使用私下修改的当前姓名；不公开账号 ID、内部经费、审批意见、草稿数量、文件原始路径。只有当前公开成员才带 member_slug。关联私有项目的标题不出现在公共响应。

成员响应只包含公开姓名、简介、身份类型、方向、状态。联系方式必须同时通过即时 contact_visible 与快照 public_contact_enabled；教育只含 education_visible 下 is_public 条目；去向同时判断 alumni_visible/is_public。账号注册邮箱、电话、管理备注永不混入。头像使用受控资产 URL，不能构造 storage_key 直链。

旧路径允许中文和空格，按 URL 编码传参；规范化后必须是 `/data/.../index.html`。拒绝外站 URL、路径穿越、重复编码、反斜线及控制字符。返回值是本站固定 content.html/member.html 路径，不是任意跳转。旧媒体原地址在本次示例结构调整后为 404，不回退离线文件。

公开附件只能由当前批准引用决定；文件本身标记 PUBLIC 仍不足以绕过撤下。证明文件 purpose=proof 永不通过公共下载。PDF/DOCX 作为附件下载，图片以固定 MIME 提供，均 nosniff、no-store。详见 [媒体说明](media-storage.md)。

私有投稿、用户管理及本人资料继续使用 [协同 API](content-api.md) 与 [认证 API](auth-api.md)，不提供 include_private 参数。正式后端部署前新公共 API 尚不可用；前端明确提示错误，不返回旧静态私密正文。
