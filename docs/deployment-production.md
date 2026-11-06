# V7–V9 部署与生产验收边界

当前开发分支arc-update，保留系统Nginx与原PostgreSQL，不合并main。正式部署依序：完整隔离测试通过→候选镜像构建→consistent backup→check/迁移预检→兼容迁移→backend启动→health/ready/public/API匿名拒绝→观察。

```bash
cd /opt/Lab_web
sudo docker compose --profile ai config --quiet
sudo docker compose build backend
sudo docker compose --profile maintenance run --rm --no-deps migrate python manage.py check
sudo docker compose --profile maintenance run --rm --no-deps migrate python manage.py makemigrations --check --dry-run
sudo docker compose --profile maintenance run --rm --no-deps migrate python manage.py migrate --plan
bash deploy/scripts/backup.sh --output /opt/lab-web-backups/<全新发布批次>
sudo docker compose --profile maintenance run --rm --no-deps migrate python manage.py migrate --noinput
sudo docker compose --profile maintenance run --rm --no-deps migrate python manage.py migrate --check
sudo docker compose up -d --no-deps --no-build --wait backend
curl --fail http://127.0.0.1:8000/api/health/
curl --fail http://127.0.0.1:8000/api/ready/
```

候选应通过release override固定独立版本标签，保存旧镜像ID，勿覆盖已运行标签。AI默认关闭，正式启用需要独立预算决定；0.10元只授权虚构验收，worker仅在明确开启profile后运行，backend/worker镜像必须一致。

真实域名、DNS、证书尚未提供。`deploy/nginx/lab-web-https.conf.example`必须替换域名和证书路径后人工合并进原系统配置，不自动覆盖。公网HTTPS验证通过后再设置DJANGO_COOKIE_SECURE=True、精确ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS/可信代理网段及HSTS短期。可信代理需由Nginx覆盖X-Lab-Client-IP/X-Forwarded-Proto，不能盲信用户X-Forwarded-For。代理网段默认空，忽略伪造头。

当前仅HTTP环境时check --deploy的Secure Cookie/HTTPS/HSTS警告仍为生产验收阻断，不能用关闭警告假装通过。域名HTTPS、真机Safari/Android、告警、异机备份未验证。数据库运行/迁移账号现已分离；原管理员保留，backend/worker使用独立非特权角色，maintenance服务负责迁移。main合并/正式域名上线仍需独立确认。

回退先AI_ENABLED=False停止领取，保留未知账本、草稿和新schema；以旧镜像override启动兼容backend，勿反向删表或down --volumes。数据库恢复单独批准。Nginx任何改动先备份、nginx -t成功再reload，出现证书/代理异常回到语法验证过的旧配置，真实账号不在公网HTTP验证。

## 数据库运行角色

提供服务器命令 `provision_runtime_role`，仅从 LAB_RUNTIME_DB_USER/LAB_RUNTIME_DB_PASSWORD 环境读取密码（≥32字符），创建非superuser/CREATEDB/CREATEROLE运行角色并授业务表/序列及后续默认权限。必须以DB迁移管理员连接运行；环境设置 POSTGRES_RUNTIME_USER/PASSWORD 后backend/worker用运行角色，`migrate` maintenance服务保留管理员凭据，迁移命令改为 `docker compose --profile maintenance run --rm migrate`。不把运行角色提升为建测试库权限；隔离测试继续使用专用test用户。生产角色切换必须先备份、实际验证登录/写入/审计/迁移，无验证不声称已分权。

2026-11-06 已完成当前服务器应用镜像与运行角色更新，详见统一验收报告。正式HTTPS、异机备份和通知渠道未配置，不代表生产门禁全绿。

## 最新索引候选

候选标签 `lab-web-backend:v789-index-20261106`；当前原应用镜像 `lab-web-backend:v789-20261106`。content.0005/0006新增排序字段/索引/触发器并回填，应用激活前先迁移，使用maintenance管理员，backend继续非特权运行角色。迁移在发布窗口执行；较大数据集先评估索引锁表时间，本次万条合成数据只说明测试规模。发布指针触发器从已发布版本派生日期，不能把该字段当普通可编辑业务字段。

本机候选完整测试通过后仍不代表 main 合并或正式域名上线获准；按统一报告审批具体版本，再执行上方备份/迁移/启动/验证步骤。首次正式域名HTTPS上线前，补齐安全检查表的真实环境门禁。
