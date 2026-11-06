> V10变更：本文保留旧版本契约供历史追溯。新直接保存、身份权限、简历及首页接口以 [V10使用与部署说明](V10-使用与部署说明.md) 为准；旧提交/审核流程已停用。

# V2 用户认证与角色权限 API

后端仍绑定服务器回环地址 `http://127.0.0.1:8000`；当前系统 Nginx 已有 `/api/` 反向代理，此为检查到的部署现状。V3 注册/登录/个人中心代码和独立测试说明见 [前端认证说明](frontend-auth.md)，尚未授权发布到原静态网站。用户管理网页仍未开发，API 契约不变。

## 认证约定

采用 Django 数据库 Session。先 GET `/api/auth/csrf/`，再在写请求中同时携带 Cookie 和 `X-CSRFToken`；注册和登录也强制要求 CSRF。登录成功会轮换 CSRF Cookie，后续读取新的 token。Session 只通过 HttpOnly、SameSite=Lax 的 Cookie 传递，JSON 不返回 Session 或密码哈希。

当前为回环 HTTP，`DJANGO_COOKIE_SECURE=False`；未来 HTTPS 上线时必须启用 Secure Cookie，并单独评审真实域名、CSRF 可信来源与 Nginx 代理。不要将本机调试配置直接改成公网放行。

受保护接口无有效 Session 返回 403；登录错误、账号不存在、禁用账号统一返回 400；参数错误 400；管理对象不存在或不可见 404；方法不允许 405；登录达限 429（Retry-After 为秒数）；数据库/审计不可用时敏感操作回滚并返回脱敏 503。

## 接口清单

| 方法与路径 | 请求 JSON | 权限与结果 |
| --- | --- | --- |
| GET /api/auth/csrf/ | 无 | 公开，200，设置 csrftoken Cookie |
| POST /api/auth/register/ | username、password；可选 first_name、last_name、email | 公开但需 CSRF；201，固定 CUSTOMER，不自动登录 |
| POST /api/auth/login/ | username、password | 公开但需 CSRF；200，安全用户对象与 Session Cookie |
| POST /api/auth/logout/ | `{}` | 已登录、需 CSRF；204，当前 Session 失效 |
| GET /api/auth/me/ | 无 | 已登录；200，仅本人 |
| PATCH /api/auth/me/ | 可选 first_name、last_name、email | 已登录、需 CSRF；200，未知/只读字段拒绝 |
| POST /api/auth/change-password/ | old_password、new_password | 已登录、需 CSRF；204；当前登录保留，其他旧登录失效 |
| GET /api/admin/users/ | 无；查询参数 page、page_size | ROOT/ADMIN/TEACHER；200，count/next/previous/results；默认 20，最大 100 |
| POST /api/admin/users/ | username、password；可选姓名、email、role、is_active | 管理者、需 CSRF；201，默认 CUSTOMER |
| GET /api/admin/users/{id}/ | 无 | 管理者；200，需对象权限 |
| PATCH /api/admin/users/{id}/ | first_name、last_name、email、role、is_active 的子集 | 管理者、需 CSRF；200，需对象权限 |
| POST /api/admin/users/{id}/reset-password/ | new_password | 管理者、需 CSRF；204，目标所有旧登录失效 |
| GET /api/health/ | 无 | 保留 V1；200/503，真实数据库连接检查 |

安全用户对象字段：id、username、first_name、last_name、email、role、is_active、is_superuser、date_joined。is_superuser 仅为只读 ROOT 标记。所有输入采用白名单，用户名创建后不可修改；密码最长 128 字符，调用 Django 密码强度验证器，不能直接 PATCH password。

ROOT 能管理全部用户并赋予 ADMIN；ADMIN/TEACHER 只能管理非 ROOT 的 CUSTOMER/STUDENT/TEACHER、只能赋予这三种角色。管理列表隐藏 ADMIN/ROOT，直接访问也返回 404。非 ROOT 不能改变自己的 role。CUSTOMER/STUDENT 不能调用任何管理接口。is_staff 单独存在，不授予业务权限；任何 API 都拒绝写 is_staff/is_superuser/groups/user_permissions。

## ROOT 初始化（由部署人员操作）

```bash
cd /opt/Lab_web
sudo docker compose exec backend python manage.py init_root --username <你选定的用户名>
```

在终端交互输入两次密码。没有默认 ROOT 密码，不支持 password 命令行参数，也不会将现有同名账号提升为 ROOT 或重置密码。命令使用强度校验、标准哈希和事务审计。没有安全终端输入时拒绝回退到明文回显。

验收过程中仅在隔离数据库创建临时 ROOT；业务库中的真实 ROOT 留给部署人员自行初始化。

## curl 请求示例

以下以本机 API 为例。先准备私有临时目录和 Cookie jar；密码用交互输入生成请求文件，避免出现在 shell 历史和命令行参数中。不要启用 shell 的 `set -x`，不要分享 Cookie 文件。

```bash
cd /opt/Lab_web
umask 077
LAB_AUTH_TMP=$(mktemp -d)
export LAB_AUTH_TMP
read -r -p '登录/注册用户名: ' LAB_AUTH_USERNAME
export LAB_AUTH_USERNAME

python3 - <<'PY'
import getpass, json, os
from pathlib import Path
root = Path(os.environ['LAB_AUTH_TMP'])
username = os.environ['LAB_AUTH_USERNAME']
password = getpass.getpass('密码: ')
(root / 'login.json').write_text(json.dumps({'username': username, 'password': password}))
PY

curl --fail-with-body -sS -c "$LAB_AUTH_TMP/cookies" \
  http://127.0.0.1:8000/api/auth/csrf/
```

定义两个辅助函数。`lab_csrf` 每次从最新 Cookie jar 读取 token；`lab_write` 的第三个参数为私有 JSON 请求文件。

```bash
lab_csrf() {
  python3 - "$LAB_AUTH_TMP/cookies" <<'PY'
import sys
from http.cookiejar import MozillaCookieJar
jar = MozillaCookieJar(sys.argv[1])
jar.load(ignore_discard=True, ignore_expires=True)
print(next(c.value for c in jar if c.name == 'csrftoken'))
PY
}
lab_write() {
  curl --fail-with-body -sS -X "$1" \
    -b "$LAB_AUTH_TMP/cookies" -c "$LAB_AUTH_TMP/cookies" \
    -H 'Content-Type: application/json' -H "X-CSRFToken: $(lab_csrf)" \
    --data-binary "@$3" "http://127.0.0.1:8000$2"
}
```

注册、登录、查询和修改本人资料：

```bash
# 新账号才执行注册；ROOT/已存在账号跳过这行。
lab_write POST /api/auth/register/ "$LAB_AUTH_TMP/login.json"
lab_write POST /api/auth/login/ "$LAB_AUTH_TMP/login.json"
curl --fail-with-body -sS -b "$LAB_AUTH_TMP/cookies" http://127.0.0.1:8000/api/auth/me/
printf '%s' '{"first_name":"示例姓名","email":"user@example.org"}' > "$LAB_AUTH_TMP/profile.json"
lab_write PATCH /api/auth/me/ "$LAB_AUTH_TMP/profile.json"
```

修改自身密码，交互填写旧、新密码：

```bash
python3 - <<'PY'
import getpass, json, os
from pathlib import Path
payload = {'old_password': getpass.getpass('旧密码: '), 'new_password': getpass.getpass('新密码: ')}
(Path(os.environ['LAB_AUTH_TMP']) / 'change.json').write_text(json.dumps(payload))
PY
lab_write POST /api/auth/change-password/ "$LAB_AUTH_TMP/change.json"
```

管理接口示例需要当前登录身份有管理权限；普通账号会收到 403。创建用户时密码同样交互填写；ADMIN/TEACHER 使用 CUSTOMER、STUDENT 或 TEACHER，ROOT 才能使用 ADMIN。

```bash
curl --fail-with-body -sS -b "$LAB_AUTH_TMP/cookies" 'http://127.0.0.1:8000/api/admin/users/?page=1&page_size=20'
read -r -p '新账号用户名: ' LAB_NEW_USERNAME
export LAB_NEW_USERNAME
python3 - <<'PY'
import getpass, json, os
from pathlib import Path
payload = {'username': os.environ['LAB_NEW_USERNAME'], 'password': getpass.getpass('新账号密码: '), 'role': 'STUDENT'}
(Path(os.environ['LAB_AUTH_TMP']) / 'create.json').write_text(json.dumps(payload))
PY
lab_write POST /api/admin/users/ "$LAB_AUTH_TMP/create.json"

# 将 123 替换为实际可管理用户 ID。
curl --fail-with-body -sS -b "$LAB_AUTH_TMP/cookies" http://127.0.0.1:8000/api/admin/users/123/
printf '%s' '{"role":"TEACHER","is_active":true}' > "$LAB_AUTH_TMP/manage.json"
lab_write PATCH /api/admin/users/123/ "$LAB_AUTH_TMP/manage.json"
python3 - <<'PY'
import getpass, json, os
from pathlib import Path
(Path(os.environ['LAB_AUTH_TMP']) / 'reset.json').write_text(json.dumps({'new_password': getpass.getpass('目标账号的新密码: ')}))
PY
lab_write POST /api/admin/users/123/reset-password/ "$LAB_AUTH_TMP/reset.json"

printf '%s' '{}' > "$LAB_AUTH_TMP/empty.json"
lab_write POST /api/auth/logout/ "$LAB_AUTH_TMP/empty.json"
# 操作完成后删除自己的临时凭据文件。
rm -r -- "$LAB_AUTH_TMP"
unset LAB_AUTH_TMP LAB_AUTH_USERNAME LAB_NEW_USERNAME
```

## 限流与审计

登录限额默认同一 IP+用户名 15 分钟 10 次、同一 IP 15 分钟 60 次，所有尝试计数，成功也不清零。环境变量 AUTH_LOGIN_WINDOW_SECONDS、AUTH_LOGIN_ACCOUNT_IP_LIMIT、AUTH_LOGIN_IP_LIMIT 必须为正整数。计数在 PostgreSQL 中共享，不因 worker 重启而重置；只信任 REMOTE_ADDR，不信任任意 X-Forwarded-For。当前回环/Docker 网关可能共享 IP 限额，未来公网代理需单独评审可信代理链。

定期清理过期计数和过期 Session，可由部署人员按运维计划执行；本阶段不自动安装系统定时任务：

```bash
sudo docker compose exec -T backend python manage.py clear_auth_throttles
sudo docker compose exec -T backend python manage.py clearsessions
```

审计表 accounts_authauditlog 记录账号创建、登录、退出、密码修改/重置、角色、启停、资料修改以及敏感管理拒绝。敏感成功操作与审计共用事务；审计不可写则操作回滚。日志只保留字段名和非敏感角色/启停前后值，不存密码、哈希、Cookie、Session/CSRF token 或姓名/email 值。没有审计修改/删除 API。

## ECS 更新与验收

先保管 `.env` 和数据库备份，确认 Git 状态并记录原镜像 ID；本服务器已有未提交 Dockerfile 修改，禁止直接 reset 或覆盖。其他没有本地改动的部署副本可 `git pull --ff-only origin arc-update`；main 合并和公网发布仍需用户确认。

数据库备份示例（输出文件权限 0600，文件名按实际时间调整；使用新文件避免覆盖旧备份）：

```bash
umask 077
LAB_BACKUP_FILE=$(mktemp data/backups/before-v2-XXXXXX)
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$LAB_BACKUP_FILE"
sudo docker compose exec -T db pg_restore --list < "$LAB_BACKUP_FILE" > /dev/null
```

确认备份成功后执行；若任一步失败先修复，不继续启动或声明部署成功：

```bash
sudo docker compose config --quiet
sudo docker compose build backend
sudo docker compose run --rm backend python manage.py check
sudo docker compose run --rm backend python manage.py makemigrations --check --dry-run
sudo docker compose run --rm backend python manage.py test --noinput --verbosity 2
sudo docker compose up -d --wait db
sudo docker compose run --rm backend python manage.py migrate --noinput
sudo docker compose run --rm backend python manage.py migrate --check
sudo docker compose run --rm backend python manage.py showmigrations
sudo docker compose up -d --wait backend
sudo docker compose ps
curl --fail-with-body http://127.0.0.1:8000/api/health/
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/auth/me/
sudo docker compose exec -T backend python manage.py shell -c 'from django.db import connection; c=connection.cursor(); c.execute("SELECT 1"); assert c.fetchone()==(1,); c.close(); print("database OK")'
```

预期 health 成功、匿名 me 为 403、数据库连接成功、迁移无 pending、backend/db healthy；8000 仅回环、5432 无宿主机映射。构建网络仍需代理的环境沿用 V1 运行说明。增加的迁移是 accounts/0002 与 sessions/0001，不重写原表或重置已有用户。

完整真实 HTTP 验证使用 `backend/apps/accounts/tests/http_smoke.py`：仅允许数据库名以 lab_web_v2_http_ 开头且没有用户的独立库，临时服务不发布端口，使用随机临时凭据和真正 Cookie/CSRF 请求；禁止指向业务库。执行步骤和本次具体结果见 V2 验收报告。单元/事务测试同样自动创建 test_lab_web，不清空业务库。

回退保留新增数据库表/列，不反向删除审计或 Session 数据。选择之前保管的 V1 镜像（本服务器标签 lab-web-backend:before-v2），用仅覆盖 backend.image 的临时 Compose 文件启动旧应用；不要执行 down -v 或删库。本次尚未进行整库恢复演练或公网 HTTPS 验收。
