# V8 统计接口

GET `/api/public/stats/overview/`、`/annual/`：匿名公开汇总及年度序列。

GET `/api/stats/me/`：本人创建/草稿/待审/公开与参与公开成果数量，不接受 member_id。

GET `/api/admin/stats/overview/`、`/review/`、`/export/`：管理者运营、审核时长、受控CSV。非管理者403，跨角色资料不额外暴露。

公开及管理查询只接受 year_from/year_to、kind、category；同名多参数和未知参数400，范围最多20年。响应 `{metric_version,as_of,filters,data}`，所有响应 no-store。网页 `/statistics.html` 和 `/manage/statistics.html` 提供等价表格和柱图/空态/错误；个人中心“科研成果统计”是入口。

统计总数以 [口径字典](statistics-dictionary.md) 为准。导出10次/认证限流窗口，超10000行需缩窄筛选；审核记录写入失败时导出整体失败，不返回未审计文件。
