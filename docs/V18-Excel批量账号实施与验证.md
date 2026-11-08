# V18 Excel批量账号实施与验证

2026-11-08，按已批准V18方案和Root不受资料完整性限制的补充要求实施，目录`/opt/Lab_web`，分支`arc-update`。

## 使用入口

Root登录 → 团队管理 → Excel批量创建账号（`/manage/account-import.html`）。下载模板后填写序号、用户名、初始密码、账号身份、是否启用、姓名；上传预览，全部校验通过后确认创建。每页显示5行，重新打开带batch参数的地址可查看结果。

- xlsx，最多2 MiB、500个非空数据行。Teacher/Student/Customer（区分大小写），状态正常/已注销。
- 密码留空使用私有配置默认初始密码；非空按行使用并执行现有密码规则。姓名可空，非空创建账号后初始化成员姓名。不会改已有账号。
- 预览无密码，错误可下载不含密码的CSV。重复用户名（包括已注销）、公式、外部链接、多数据表、错误表头、额外非空列、超限压缩内容均拒绝。无效行使整批不能确认。

## 实现与边界

- 固定openpyxl3.1.5、defusedxml0.7.1、cryptography50.0.2及传递依赖；MIT/PSF/Apache-BSD开源许可，运行不依赖外部文档服务。解析在512 MiB、8秒CPU和12秒墙钟超时的子进程中执行，限制ZIP条目、解压体积、压缩比、XML大小与工作表范围。
- 原xlsx不持久存储。仅通过校验的行以Fernet加密暂存于私有媒体目录下account_imports，文件权限0600、目录0700、15分钟有效。独立ACCOUNT_IMPORT_KEY保存在服务器私有.env，数据库、日志、审计和接口不保留明文密码。
- 数据库AccountImportBatch仅保存Root归属、脱敏预览、错误、状态、有效期与创建账号ID。Root专用接口、CSRF、按本人访问控制；默认密码在预览时解析冻结。
- 确认入队后由独立`account-import-worker`处理，避免500次密码哈希超出HTTP时限。先计算哈希，事务内重新核对Root有效身份、批次状态及用户名占用，再整批创建账号、姓名及审计。失败整批回滚；重复确认不重复创建。
- 完成／失败／过期后清理密文；后台进程每轮检查到期批次，运行超过10分钟的中断租约标为过期。另有cleanup_account_imports命令；孤立文件超过15分钟也清理。过期密文即使清理延迟也不能解密确认。
- worker使用同一后端镜像、最小权限数据库用户、内部网络、512 MiB和1 CPU限制，独立心跳健康检查，不启用AI worker。备份脚本已增加停启该进程，保证备份期间无导入写入。
- RootProfileInput允许邮箱、电话、性别、政治面貌留空；Root页面取消资料必填标记和required阻拦。部分更新不清空未提交字段；Root毕业去向可仅填单位，毕业年份允许缺省。字段类型、枚举、唯一性、文件权限和审计仍执行，普通成员校验不变。
- 轮播管理明确显示当前AUTO/MANUAL来源；AUTO保存图片后不再声称首页已生效，而是提示切换手动。原轮播模式、图片和排序保持不变。

## 实际验证

- `LAB_TEST_STAGE=v7 python3 tests/support/v4_environment.py manage test apps.accounts.tests.test_v18_batch_accounts apps.content.tests.test_v17_carousel apps.content.tests.test_v14 apps.members.tests.test_v16_cv --noinput`：30项通过，14.992秒，`/tmp/v18-final-tests.log`。
- 后续Root毕业资料输入改为StrictSerializer，并检查并发清理文件竞态；V18专项10项再次通过，9.344秒，`/tmp/v18-root-final.log`。单事务500人、任意姓名初始化失败整批回滚、占用冲突、重复确认、默认/自定义密码、注销、跨Root隔离、Root权限撤销、到期清理和文件删除均有用例。
- `LAB_TEST_STAGE=v7 python3 tests/support/v4_environment.py browser /tmp/lab-web-v3-venv/bin/python test_v18_batch_accounts.py`：真实浏览器通过，34.511秒，`/tmp/v18-browser3.log`。覆盖下载模板、重复错误后修正重传、7行分页、预览不含密码、确认后状态、刷新恢复结果、自定义与默认密码登录、已注销拒绝登录、Root仅姓名保存和姓名初始化。已查看截图`.browser-artifacts/v7/v18-import-result.png`。
- `makemigrations --check --dry-run`：No changes detected（`/tmp/v18-schema.log`）。修改JS执行Node语法检查、`git diff --check`通过。
- 真实运行验证：Root虚构账号只填姓名成功；上传2行Excel，真实后台服务异步完成创建；确认逐行自定义/默认密码哈希正确、姓名正确，状态按已注销创建，没有临时对外公开新成员，完成后storage_key清空且临时文件清理。页面无JS错误。日志`/tmp/v18-live.log`。
- 虚构Root及导入账号已注销、撤销旧会话，保留审计；现有活跃账号仍仅root_admin、djj，原有账号密码、状态未修改。

## 部署

- 操作前备份`/opt/lab-web-backups/v18-20261108-34c5664c`，COMPLETE检查通过。
- 镜像统一`lab-web-backend:v18-20261108-01`；执行accounts.0004_accountimportbatch、members.0013_alter_alumnidestination_graduation_year成功，运行角色授权重新核对。
- backend、account-import-worker、PostgreSQL均healthy，迁移检查通过，`/api/ready/`返回ready。前端缓存键同步更新，实际前后端验证通过，未合并main。构建与部署日志`/tmp/v18-build-final.log`、`/tmp/v18-release.log`。
- 导入加密密钥及默认密码仅写服务器私有.env；.env.example只列空变量名。备份恢复时需保留该私有密钥；更换密钥会使未完成批次失效，需要重新上传，不应尝试绕过校验。

## 回退

关闭批量创建入口并停止account-import-worker即可暂停新导入，保留既有账号、批次摘要及审计。已创建账号若需撤销按批次明确选择后注销，不能直接删除资料或成果。新增表和可空字段保留，避免破坏性反向迁移。轮播来源仍可切回AUTO。

## 依赖参考

- openpyxl读取参数与链接控制：https://openpyxl.readthedocs.io/en/3.1/api/openpyxl.reader.excel.html
- openpyxl安全建议（defusedxml）：https://pypi.org/project/openpyxl/
- Fernet有效期与认证加密：https://cryptography.io/en/latest/fernet/

## 身份名称修正（2026-11-08）

按用户要求，模板下拉选项、说明及导入规则统一为严格区分大小写的Teacher/Student/Customer，分别映射数据库TEACHER/STUDENT/CUSTOMER。移除小写及custom兼容写法；原账号角色不变。新增大小写拒绝用例，原导入测试与浏览器测试数据同步更新为规范值。

修正验证：11项专项测试通过（9.820秒，/tmp/role-tests.log），真实浏览器模板与整批导入流程通过（53.164秒，/tmp/role-browser.log）。运行镜像已同步v18-20261108-02，备份/opt/lab-web-backups/v18-role-20261108-71730bba；实际运行环境核验模板下拉及三种角色映射正确，未创建额外账号，ready正常。

## 首页轮播首屏微调（2026-11-08）

修复首页静态hero及DOMContentLoaded先挂载Logo、接口返回后再替换上传图片造成的跳变。初始只保留统一深蓝背景及首屏高度；收到确定的轮播结果后加载图片，首张解码完成再淡入，计时从此开始，首图高优先级。会话变化时清除旧轮播且不提前挂载Logo，旧异步解码回调不会重新显示旧图。只有接口确定无有效图片时才使用Logo回退，维持5秒轮播与小点操作。

真实浏览器在实际网站拦截并延迟首页API验证：数据返回前没有Logo和轮播图片；释放请求后真实图片加载解码成功、aria-busy=false，5.2秒后切到第二张；明确空结果仍显示Logo回退；无JS错误。JS语法和git diff检查通过。静态资源与缓存键已直接更新服务器，无需后端或数据库变更。

## 加入我们页面排版（2026-11-08）

将contact.html页面标题、面包屑与顶部导航入口统一为“加入我们”，去除后台内容标题造成的重复“联系我们”。页面整理为申请加入与联系团队两块：三步申请说明、按当前账号显示原有投递／资料入口、联系邮箱及已发布补充正文；保留富文本与附件，不更改投递权限和链接。桌面双栏、手机单栏，统一文字层次和间距。实际浏览器验证标题、三步说明、投递入口和邮箱可见，无重复标题，390px无横向溢出、无JS错误；JS语法与补丁检查通过。静态资源已更新服务器，未修改数据库与后端。
