# V1：Django 后端与 PostgreSQL 数据库初始化

- 状态：待用户评审；本文件不是实施授权。
- 日期：2026-11-05
- 开发分支：`arc-update`；基线提交：`1f3b748`。
- 本次交付：改造 spec 和协作规则；用户批准本 spec 后才执行下述实施计划。

## 1. 现状与目标

当前 Git 已跟踪 110 个文件。`frontend/` 是 HTML、CSS、JavaScript、图片和文档组成的静态站点；导航及搜索使用 fetch 加载静态内容，没有现成业务 API。`backend/`、`database/`、`deploy/`、`docs/` 等目录主要是 `.gitkeep` 占位。`frontend/.git` 为原有嵌套仓库历史，只在本机保留，不删除、不当作子模块提交。

宿主机是 Ubuntu 24.04，已有 Python 3.12，系统 Nginx 正在监听 80 端口，检查时未发现 Docker 命令。根目录有用户提供但未跟踪的 `README.md`，描述后续开发路线；本次不改写、不顺带提交。实施时重新核对当前实际服务与端口。

目标是在保留静态站点的基础上，建立可运行、可迁移、可验证的 Django REST 后端和 PostgreSQL 数据库，为后续业务提供基础。

## 2. 范围与不实施事项

本阶段包括：Django/DRF 初始化、自定义用户模型、PostgreSQL ORM 配置及初始迁移、健康接口、容器编排、环境变量、安全忽略规则、运行文档及实际验收。

本阶段不包括：注册登录 API、JWT、角色业务权限、身份申请、简历、成员动态化、业务 CRUD、前端页面、Django Admin 管理页面、现有数据导入、域名与 HTTPS 改造。Django 内置认证组件可以安装，但不开放管理路由、不创建默认管理员账号。

不删除、重构或修改 `frontend/`；不替换系统 Nginx，不运行第二个 Nginx，不自动合并或上线。

## 3. 技术方案与默认选择

建议采用两个 Compose 服务：`backend`（Gunicorn + Django）和 `db`（PostgreSQL），系统 Nginx 继续服务现有网站。相比直接在宿主机安装 PostgreSQL，此方案能隔离依赖并明确数据库生命周期；不引入 Nginx 容器，避免与已有 80 端口冲突。以下为待评审的建议默认值，并非用户已确认的额外需求。

| 项目 | 选择 |
| --- | --- |
| Python | 3.12 slim 镜像 |
| Django | 5.2 LTS 系列 |
| Django REST Framework | 3.16 系列 |
| 数据库 | PostgreSQL 16 系列 |
| 数据库驱动 | psycopg 3 |
| WSGI | Gunicorn |
| 环境读取 | django-environ；部署值由 Compose 注入 |
| 测试 | Django TestCase / DRF APITestCase，使用真实 PostgreSQL 测试库 |

实施时核对上述系列支持关系和安全补丁，固定 Python 依赖的具体补丁版本；镜像固定系列并记录实际镜像标识，不使用 `latest`。如需改变主版本或架构，更新 spec 再评审。

官方参考：[Django 5.2 发布说明](https://docs.djangoproject.com/en/5.2/releases/5.2/)、[DRF 3.16 发布说明](https://www.django-rest-framework.org/community/3.16-announcement/)。

## 4. 模块与拟修改文件

```text
backend/
  manage.py
  requirements.txt
  config/
    __init__.py
    settings.py          # 环境驱动配置；当前阶段不拆出多套环境
    urls.py              # 只挂载 /api/health/
    asgi.py
    wsgi.py
  apps/
    __init__.py
    accounts/
      __init__.py
      apps.py
      models.py          # User 与角色枚举
      migrations/
        __init__.py
        0001_initial.py
      tests/
        __init__.py
        test_models.py
    core/
      __init__.py
      apps.py
      urls.py
      views.py           # health 接口
      tests/
        __init__.py
        test_health.py
        test_settings.py
deploy/docker/
  backend.Dockerfile
docker-compose.yml
.env.example
.gitignore
.dockerignore
docs/backend-setup.md
docs/V1-验收报告.md
```

- 本轮已新增：`AGENTS.md`、本 spec；实施阶段只在需要时更新它们的状态与验收链接。
- 实施阶段新增：上述代码、迁移、配置、测试和运行文档。
- 继续保留：已有 `.gitkeep`、用户 README、静态站点、嵌套 Git 历史。
- `.dockerignore` 排除 `.git`、`.env`、前端、缓存、日志、数据备份等；构建上下文不得包含真实密钥。
- `docs/V1-验收报告.md` 只记录实际执行后的脱敏结果，不预先编造通过记录。

## 5. User 与角色约束

1. `apps.accounts.models.User` 继承 `AbstractUser`，保留 username、密码哈希及标准认证字段。
2. `AUTH_USER_MODEL = "accounts.User"` 在第一次运行任何迁移之前配置；`accounts/0001_initial.py` 必须创建该模型。
3. `role` 使用 `TextChoices`，数据库值严格为 `ADMIN`、`TEACHER`、`STUDENT`、`CUSTOMER`，默认 `CUSTOMER`；增加数据库 CheckConstraint 防止非法值绕过表单校验。
4. ROOT 只由 `is_superuser=True` 表示，绝不加入 role 枚举；超级用户也保留普通 role 字段，未指定时为 CUSTOMER，不自动设为 ADMIN。
5. 普通用户默认 `is_superuser=False`、`is_staff=False`；`create_superuser` 必须保持 Django 对这两个字段的标准校验。
6. `role=ADMIN` 或 `TEACHER` 不自动授予 Django 超级用户或 staff 权限。本阶段只建立数据结构，不宣称已实现 README 中的业务授权和安全边界。
7. 测试覆盖默认角色、四种合法角色、非法角色数据库拒绝、密码哈希、超级用户标识与 role 独立性。禁止明文存储密码。

## 6. 数据库与环境变量

- 只配置 `django.db.backends.postgresql`，无 SQLite 回退。
- `.env.example` 只放说明和非敏感示例；`DJANGO_SECRET_KEY`、`POSTGRES_PASSWORD` 留空并要求本机生成，真实 `.env` 不入库、权限限制为当前部署账号可读。
- 变量：`DJANGO_SECRET_KEY`、`DJANGO_DEBUG`（默认 False）、`DJANGO_ALLOWED_HOSTS`（默认 `127.0.0.1,localhost`）、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD`、`POSTGRES_HOST`（Compose 内为 db）、`POSTGRES_PORT`（5432）。
- 缺少必需密钥或密码时明确失败，不提供开发密钥默认值；布尔值需正确解析 `False`，不能使用 `bool("False")`。
- PostgreSQL 命名卷 `postgres_data` 持久化。数据库没有宿主机端口映射，不使用 host 网络；仅在私有 Compose 网络内访问。
- 连接设置有限超时（建议 5 秒），避免健康请求无限等待。
- 数据库健康检查使用 `pg_isready`，backend 依赖数据库 healthy 状态启动。
- 迁移由独立、可见的 `docker compose run --rm backend python manage.py migrate --noinput` 操作完成，不在 Docker build 或每个 Gunicorn worker 中隐式执行迁移。
- 测试使用独立测试数据库；记录建库所需权限，不对业务数据执行破坏性测试。后续业务上线前另行收紧运行账号权限。

## 7. 健康接口契约

`GET /api/health/` 匿名可访问，返回 JSON；不创建会话、不依赖身份登录、不返回数据库地址、版本、异常堆栈或凭据。

数据库可用时 HTTP 200：

```json
{"status":"ok","backend":"running","database":"connected"}
```

每次请求实际通过 Django connection 执行 `SELECT 1`，不只检查配置或复用缓存结果。数据库异常时捕获数据库相关异常，HTTP 503：

```json
{"status":"degraded","backend":"running","database":"unavailable"}
```

日志不得记录连接密码。接口无业务写操作；数据库通畅不等于迁移全部完成，迁移由独立验收命令检查。明确只允许 GET：使用 DRF 的方法白名单限制 HEAD、OPTIONS、POST、PUT、PATCH、DELETE 等其他方法均返回 405。自动测试覆盖 200/503、JSON 内容、匿名访问及上述方法限制；模拟故障之外，还需实际停止数据库验收故障和恢复路径。

## 8. 运行与 Nginx 边界

- Compose 只包含 backend、db；backend 映射必须为 `127.0.0.1:8000:8000`，Gunicorn 在容器内绑定 `0.0.0.0:8000`，以非 root 用户运行。
- db 不定义 `ports`。不公开 5432，不映射 Docker socket，不使用 privileged。
- 不启动 Django runserver 作为部署服务；不在镜像里保存任何 SECRET_KEY。Dockerfile 使用可覆盖的 CMD 启动 Gunicorn，不使用固定 Gunicorn ENTRYPOINT，确保 Compose run 能执行管理命令。
- 实施阶段允许安装必要 Docker Engine/Compose 插件并启动这两个服务，但不得中断现有 Nginx；安装前核对系统软件源和现有容器情况，记录安装动作。
- 不改动当前系统 Nginx 配置；本阶段通过宿主机 `http://127.0.0.1:8000/api/health/` 验收后端。
- 公网 `/api/` 反向代理留待用户确认上线时配置到现有 Nginx，届时保留请求中的 `/api/` 路径、配置实际域名允许列表；本阶段不以公网可访问作为验收条件。
- 源码保存在当前工作目录，切换开发分支可能影响直接读取该目录的服务。因此本阶段 frontend 必须无差异，新增后端只对回环地址提供服务；代码合并到 main 与公网代理上线都需要用户确认。

## 9. 实施顺序（批准之后）

- [ ] 重新确认分支为 arc-update、工作区用户改动、Nginx/端口及 Docker 状态，记录 frontend 文件基线。
- [ ] 添加忽略规则、环境模板、固定依赖、Dockerfile 和 Compose；生成本地独立密钥，不展示密钥值。
- [ ] 建立 config、accounts、core；先配置自定义 User 再生成初始迁移。
- [ ] 先写用户和健康接口测试并确认其失败，再完成最小实现及配置测试。
- [ ] 安装/验证容器工具，构建镜像，启动数据库，执行初始迁移，再启动 Gunicorn。
- [ ] 执行下述全部验收；失败定位修复并重新执行相关验收。
- [ ] 编写运行说明、脱敏验收报告；检查没有前端差异、敏感文件及数据库文件进入暂存区。
- [ ] 在 arc-update 提交并推送，交付文件清单、测试证据和下一阶段事项；等用户确认后再合并上线。

## 10. 必须实际执行的验收

以下均为未来验收命令，当前仅计划，尚未执行。命令从仓库根目录运行，真实环境变量已在本机 `.env` 配置。`docker compose config --quiet` 避免输出展开后的密钥；不得将完整展开配置复制进报告。

| 检查 | 命令 | 通过标准 |
| --- | --- | --- |
| Compose 有效性 | `docker compose config --quiet` | 退出码 0 |
| 镜像构建 | `docker compose build backend` | 成功构建 |
| 数据库启动 | `docker compose up -d db` | 数据库 healthy |
| 首次迁移 | `docker compose run --rm backend python manage.py migrate --noinput` | 成功应用初始迁移 |
| Django system check | `docker compose run --rm backend python manage.py check` | 无错误 |
| 模型迁移一致性 | `docker compose run --rm backend python manage.py makemigrations --check --dry-run` | 无新迁移，退出码 0 |
| 已应用迁移 | `docker compose run --rm backend python manage.py migrate --check` | 无未执行迁移，退出码 0 |
| 迁移清单 | `docker compose run --rm backend python manage.py showmigrations` | accounts 及依赖迁移均为 `[X]` |
| 真实数据库连接 | `docker compose run --rm backend python manage.py shell -c 'from django.db import connection; c=connection.cursor(); c.execute("SELECT 1"); assert c.fetchone() == (1,); c.close(); print("database connection OK")'` | 打印成功且退出码 0 |
| 自动化测试 | `docker compose run --rm backend python manage.py test apps.accounts apps.core --noinput` | 所有测试通过，真实 PostgreSQL 测试库 |
| 后端启动 | `docker compose up -d backend` | Gunicorn 正常运行 |
| 健康接口 | `curl --fail-with-body -i http://127.0.0.1:8000/api/health/` | HTTP 200，JSON 与成功契约完全一致 |
| 真实故障 | `docker compose stop db` 后使用 `curl -sS -i --max-time 15 http://127.0.0.1:8000/api/health/` | HTTP 503、失败 JSON，无敏感信息 |
| 恢复 | `docker compose up -d db`；等待 healthy 后再次请求接口 | HTTP 200、成功 JSON，无需重建数据库 |
| 数据持久化 | `docker compose up -d --force-recreate db`；等待 healthy 后执行 `docker compose run --rm backend python manage.py migrate --check` 并再次请求健康接口 | 不删除卷，重建后迁移仍已应用，健康接口恢复 200 |
| 端口限制 | `docker compose ps`、`ss -ltn`，检查 Compose 原始端口声明和实际映射 | 8000 仅映射 127.0.0.1；数据库无宿主机映射；无第二个 Nginx |
| 前端保留 | `git diff --exit-code 1f3b748 -- frontend/` | 零差异、退出码 0；已有首页与资源抽检正常 |
| 提交检查 | `git diff --cached --stat`、`git status --short` 及敏感文件扫描 | 无 .env、私钥、数据库文件、真实凭据 |

配置自动测试额外验证缺少密钥/密码时启动失败、DEBUG=False 解析正确、数据库 engine 不回退 SQLite。对 Docker 构建工具不可用、镜像拉取失败、依赖无法安装等阻碍，先解决再验收；无法解决时标记受阻及未通过项目，不能宣布阶段完成。

## 11. 风险、回退与后续阶段

- Docker 未安装，安装及镜像下载需要网络、磁盘和系统权限；在计划批准前不进行安装。
- 自定义 User 必须早于首次迁移；发现意外已有数据库时先核实，禁止通过删库重新初始化来掩盖问题。
- `.env` 不入库意味着 Git 备份不包含运行密钥；运维需另外安全保管。数据库命名卷也不等于备份；进入业务阶段前建立 PostgreSQL 备份和恢复流程。
- 回退新增服务可用 `docker compose down`，保留卷；禁止 `down -v`、删卷、删历史或强制推送。现有 Nginx 和静态文件不变。
- 后续合并 main 之前再次确认完整测试通过、用户批准、数据库迁移兼容性和部署目录策略；不要将切换 Git 分支当作数据库回退。
- 下一阶段需单独制定 spec，设计注册登录、ROOT/角色的业务授权边界、敏感操作保护，以及域名、HTTPS、同源代理和 CSRF 策略。不要仅凭 role 字段宣称权限已完成。

## 12. 交付与评审门槛

本 spec 评审重点：模块结构、依赖系列、ROOT 与 role 的独立关系、Compose 网络边界、暂不配置公网 API 代理、上述验收条件。

实施完成后交付实际修改文件清单、逐条执行命令、退出码和结果、失败修复记录、下一阶段注意事项；验收通过仍需用户确认才能合并 main 和上线。
