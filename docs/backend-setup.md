# 后端运行说明（V1 + V2）

当前包含 Django/DRF、PostgreSQL、Session 认证和角色权限管理 API，以及 `GET /api/health/`。V2 接口、CSRF、ROOT 初始化与请求示例见 [认证 API 说明](auth-api.md)。已有 `frontend/` 和系统 Nginx 继续原样运行；后端仍只绑定服务器回环地址；当前系统 Nginx 已配置 `/api/` 同源代理，V3 保留原配置。前端认证开发与发布边界见 [V3 说明](frontend-auth.md)。

## 环境准备

需要 Docker Engine、Compose v2、空闲的宿主机 127.0.0.1:8000。Ubuntu 可通过系统可信软件源安装 `docker.io docker-compose-v2 docker-buildx`；安装后确认 `sudo docker version`、`sudo docker compose version` 正常。不需要安装第二个 Nginx，也不需要在宿主机安装 PostgreSQL 或 Python 依赖。

以下命令从仓库根目录执行。使用 sudo 访问 Docker；不需要把 Docker socket 改为所有人可写。无 sudo 的 Docker 环境可去掉命令中的 sudo。

从 `.env.example` 建立 `.env`，分别生成 `DJANGO_SECRET_KEY` 和 `POSTGRES_PASSWORD`，不要复用密码。首次部署可以运行下面脚本；如果 `.env` 已存在，脚本会拒绝覆盖，避免使现有数据库密码失配。

```bash
python3 - <<'PY'
from pathlib import Path
import os
import secrets

content = Path('.env.example').read_text()
content = content.replace('DJANGO_SECRET_KEY=\n', 'DJANGO_SECRET_KEY=' + secrets.token_urlsafe(64) + '\n')
content = content.replace('POSTGRES_PASSWORD=\n', 'POSTGRES_PASSWORD=' + secrets.token_urlsafe(40) + '\n')
fd = os.open('.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w') as file:
    file.write(content)
print('Created .env with permissions 0600; secret values hidden.')
PY
```

不要 `cat .env` 或把 `docker compose config` 的完整输出贴入日志；检查配置使用 `sudo docker compose config --quiet`。真实 `.env` 已被 Git 和构建上下文排除，应另行安全备份。

| 变量 | 含义 |
| --- | --- |
| DJANGO_SECRET_KEY | 必填，独立随机密钥 |
| DJANGO_DEBUG | 默认 False；部署保持 False |
| DJANGO_ALLOWED_HOSTS | 默认 127.0.0.1,localhost，不使用通配符 |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | 必填，库名、账号、独立密码 |
| POSTGRES_HOST / POSTGRES_PORT | Compose 内使用 db / 5432 |

缺少或留空必需密钥时启动会失败，不会回退到开发密钥或 SQLite。当前不自动从 Django 读取文件，Compose 负责把 `.env` 中的指定变量注入容器。

## 首次启动

```bash
sudo docker compose config --quiet
sudo docker compose build backend
sudo docker compose up -d --wait db
sudo docker compose run --rm backend python manage.py migrate --noinput
sudo docker compose up -d --wait backend
curl --fail-with-body http://127.0.0.1:8000/api/health/
```

成功返回 HTTP 200：

```json
{"status":"ok","backend":"running","database":"connected"}
```

数据库连接失败返回 HTTP 503：

```json
{"status":"degraded","backend":"running","database":"unavailable"}
```

只允许 GET，其他方法返回 405。接口每次执行真实 `SELECT 1`，但不证明迁移已全部应用，迁移状态另行检查。

启动不会自动迁移或创建超级用户；不要先用 Django 默认 User 迁移再切换模型。`accounts.User` 自第一条迁移起即为认证用户模型。容器内 Gunicorn 监听 0.0.0.0:8000；宿主机仅映射 127.0.0.1:8000。数据库没有映射到宿主机，5432 无需安全组放行。

数据库只连接 internal backend 网络；后端同时连接该网络与 host_access 桥接网络，支持宿主机回环端口发布。不要将后端改为只连接 internal 网络：本服务器 Docker 29 下会出现容器内部健康、宿主机端口却未发布的情况。host_access 不连接数据库，也不是 host 网络模式。

## 检查和测试

```bash
sudo docker compose run --rm backend python manage.py check
sudo docker compose run --rm backend python manage.py makemigrations --check --dry-run
sudo docker compose run --rm backend python manage.py migrate --check
sudo docker compose run --rm backend python manage.py showmigrations
sudo docker compose run --rm backend python manage.py shell -c 'from django.db import connection; c=connection.cursor(); c.execute("SELECT 1"); assert c.fetchone() == (1,); c.close(); print("database connection OK")'
sudo docker compose run --rm backend python manage.py test --noinput
sudo docker compose ps
ss -ltn
```

测试使用独立的 `test_lab_web` 数据库（随 POSTGRES_DB 改变），测试结束清理该测试库，不清空主库。PostgreSQL 官方镜像首次初始化时创建的 POSTGRES_USER 为数据库超级用户，因此具备测试建库权限；本阶段不使用真实业务数据。投入业务使用前应分离迁移、运行、测试账号，限制运行账号权限。

不要在生产数据库旁运行不明来源的测试，也不要将测试数据库名配置为真实业务数据库。

故障/恢复测试只操作本项目容器，测试期间 backend 将返回 503：

```bash
sudo docker compose stop db
curl -sS -i --max-time 15 http://127.0.0.1:8000/api/health/
sudo docker compose up -d --wait db
curl --fail-with-body http://127.0.0.1:8000/api/health/
sudo docker compose up -d --wait --force-recreate db
sudo docker compose run --rm backend python manage.py migrate --check
curl --fail-with-body http://127.0.0.1:8000/api/health/
```

检查容器日志可用 `sudo docker compose logs --tail=100 backend db`，分享前确认没有敏感信息。数据库真实密码不应出现在应用日志中。

## 角色边界

普通用户默认 CUSTOMER，允许 ADMIN、TEACHER、STUDENT、CUSTOMER；数据库约束禁止 ROOT 等其他值。ROOT 表示 `is_superuser=True`，与 role 独立。默认超级用户也保留 CUSTOMER role，角色不自动设置 is_staff 或 is_superuser。

V2 已实现注册、登录、个人资料/密码及管理用户 API，按 ROOT/业务角色执行权限检查；尚未开发前端管理页面、身份申请或简历等业务。具体权限和字段白名单见认证 API 说明。

## 数据与停机

数据库保存在 Compose 命名卷 `lab-web_postgres_data`（取决于 Compose 项目名称），不是仓库文件。`sudo docker compose down` 停止并移除本项目容器和网络，保留卷；不要使用 `down -v` 或手工删除卷来解决迁移错误。

修改 `.env` 的 POSTGRES_PASSWORD 不会自动修改已经初始化的数据库用户密码。需要轮换密码时另行安排数据库 ALTER ROLE 与环境配置同步，禁止通过删库重新初始化来轮换。

代码版本回退不会回退数据库；后续包含业务数据的迁移必须先评估兼容性、备份和恢复方案。命名卷持久化不是备份，Git 也不会备份数据库与 `.env`。

## 本服务器网络与后续上线

本次环境拉取 Docker Hub 需要已有的本地 HTTP 代理。安装时增加了 `/etc/systemd/system/docker.service.d/lab-web-proxy.conf`，为 Docker daemon 指定 127.0.0.1:18080；该配置只属于本服务器，不写进镜像或 Compose。如果换服务器或代理停止，先排查 daemon 拉取镜像网络。只有确需调整 daemon 时才安排重启 Docker，避免打断其他容器。

构建客户端也可能需要代理来获取镜像认证令牌。容器构建步骤中的 pip 通过临时构建覆盖文件使用宿主机回环代理；仅构建使用 host 网络，运行服务仍使用 Compose 内部网络。本服务器实际使用：

```bash
cat > /tmp/lab-web-build-proxy.yml <<'YAML'
services:
  backend:
    build:
      network: host
      args:
        HTTP_PROXY: http://127.0.0.1:18080
        HTTPS_PROXY: http://127.0.0.1:18080
        NO_PROXY: localhost,127.0.0.1,::1
YAML
sudo env HTTPS_PROXY=http://127.0.0.1:18080 HTTP_PROXY=http://127.0.0.1:18080 NO_PROXY=localhost,127.0.0.1,::1 docker compose -f docker-compose.yml -f /tmp/lab-web-build-proxy.yml build backend
```

这不是应用运行时变量，不应添加到 `.env` 或镜像中。

依赖和镜像通过官方 PyPI / Docker Hub 获取；锁定的 Python 依赖见 requirements.txt，验收使用的镜像标识见验收报告。

当前仍在 arc-update。V3 检查时系统 Nginx 已有 `/api/` 代理，本次不修改它；前端代码仅在独立副本开发，部署和 main 合并另获确认。公网 HTTPS、可信代理、域名和 CSRF 部署策略仍需按实际入口评审。
