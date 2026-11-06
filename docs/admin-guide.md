> V10变更：本文保留旧版本契约供历史追溯。新直接保存、身份权限、简历及首页接口以 [V10使用与部署说明](V10-使用与部署说明.md) 为准；旧提交/审核流程已停用。

# 管理员使用

现有ROOT用户名root_admin；密码由负责人掌握，忘记用服务器交互命令 `docker compose exec backend python manage.py changepassword root_admin` 重设，不提供默认密码。ROOT由is_superuser独立标识，普通role=CUSTOMER不影响ROOT能力。

ROOT/ADMIN/TEACHER可自审：保存完整草稿→提交审核→填写意见→审核通过。普通CUSTOMER/STUDENT不能审核。ROOT管理全部账号；ADMIN/TEACHER不能接管其他ADMIN/ROOT，ADMIN本人资料可自审。身份类型TEACHER不自动赋管理角色。

成员认领需人工核验证据，不按姓名自动绑定。公开资料需本人选择公开范围；撤销隐私即时收紧，恢复需新版本和授权。草稿投稿、驳回、撤回、归档、撤下是不同动作；有旧公开版时，新稿未批不会替换旧版。合作署名不自动授编辑权，争议必须处理。

AI页面按预览/授权/候选/确认四步操作；扫描件不冒充OCR成功；UNKNOWN计费联系服务器ROOT核对，不连续重复提交。统计只看已发布数据，未知年单列。备份/恢复和故障命令见运维手册，恢复不能默认覆盖生产。
