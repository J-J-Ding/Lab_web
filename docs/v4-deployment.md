# V4 更新部署与回退步骤（本次未执行）

V4代码在当前 `/opt/Lab_web`，正式容器仍运行旧镜像；不运行下列发布命令就不会自动增加线上API。生产迁移/更新须负责人明确批准准确提交和窗口。无需改Nginx、前端、数据库端口或用户自定义Dockerfile。

## 1. 上线前

确认V4验收报告与完整回归通过，Git状态无意外变更；保留现有Dockerfile和README，不reset/stash。先把待发布提交记录下来，确认本机就是该提交的代码。不要在有未提交用户改动时盲目pull。main合并另行确认，不在本手册自动执行。

```bash
cd /opt/Lab_web
git status --short --branch
git rev-parse HEAD
sudo docker compose config --quiet
sudo docker compose ps
```

V4只新增表/约束，无旧表删除；仍必须备份。以下命令应在同一终端逐项执行，失败即停止；不要开启shell `set -x`。

```bash
umask 077
LAB_V4_BACKUP_DIR=$(mktemp -d data/backups/before-v4-XXXXXX)
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$LAB_V4_BACKUP_DIR/database.dump"
sudo docker compose exec -T db pg_restore --list < "$LAB_V4_BACKUP_DIR/database.dump" > "$LAB_V4_BACKUP_DIR/dump-list.txt"
LAB_V4_OLD_IMAGE=$(sudo docker inspect --format '{{.Image}}' lab-web-backend-1)
printf '%s\n' "$LAB_V4_OLD_IMAGE" > "$LAB_V4_BACKUP_DIR/old-image.txt"
git rev-parse HEAD > "$LAB_V4_BACKUP_DIR/source-sha.txt"
```

确认dump非空且pg_restore读取无错误。读取目录不是恢复演练；真实恢复按独立库执行，不能覆盖生产。`.env`另行受控备份，不提交Git或打印密钥。V4未引入文件上传，无需迁移媒体，但现有静态/媒体仍应沿用既有备份策略。

## 2. 构建独立发布镜像并预检

```bash
LAB_V4_IMAGE="lab-web-backend:v4-$(git rev-parse --short HEAD)"
sudo docker build -t "$LAB_V4_IMAGE" -f deploy/docker/backend.Dockerfile .
LAB_V4_RELEASE="$LAB_V4_BACKUP_DIR/release.yml"
printf 'services:\n  backend:\n    image: %s\n' "$LAB_V4_IMAGE" > "$LAB_V4_RELEASE"
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" config --quiet
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" run --rm --no-deps backend python manage.py check
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" run --rm --no-deps backend python manage.py makemigrations --check --dry-run
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" run --rm --no-deps backend python manage.py migrate --plan
```

审批过的V4迁移应仅出现assets/members/content/workflow新增迁移。若出现删除旧表、未预期accounts迁移或连接错误，停止。完整测试只在隔离环境运行，不能在这里用生产账号开启Django测试runner。

## 3. 获批后迁移与更新后端

```bash
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" run --rm --no-deps backend python manage.py migrate --noinput
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" run --rm --no-deps backend python manage.py migrate --check
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" run --rm --no-deps backend python manage.py showmigrations
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" up -d --no-deps --no-build --wait backend
sudo docker compose -f docker-compose.yml -f "$LAB_V4_RELEASE" ps
curl --fail-with-body http://127.0.0.1:8000/api/health/
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/api/members/me/draft/
```

最后匿名草稿GET预期403，不是404。通过回环或已配置HTTPS，用受控测试账号按 [member-api.md](member-api.md)验证：GET初始null、POST初始化、PATCH版本递增、旧版本409、overview/participations、退出后403。不能在明文公网HTTP发送真实账号密码。确认旧注册登录、原九栏目、Nginx代理仍正常，数据库无公网端口，后端依旧127.0.0.1:8000。

保存release.yml路径作为后续统一运维Compose参数；不要之后随手执行只用基础文件的`up`而切回旧v2标签。V4 API测试不会自动帮真实用户创建成员档案，按需POST初始化即可。

## 4. 应用回退

优先保留新表退旧应用；不要逆迁移删除已产生的档案和成果。

```bash
LAB_V4_ROLLBACK="$LAB_V4_BACKUP_DIR/rollback.yml"
printf 'services:\n  backend:\n    image: %s\n' "$LAB_V4_OLD_IMAGE" > "$LAB_V4_ROLLBACK"
sudo docker compose -f docker-compose.yml -f "$LAB_V4_ROLLBACK" config --quiet
sudo docker compose -f docker-compose.yml -f "$LAB_V4_ROLLBACK" up -d --no-deps --no-build --wait backend
curl --fail-with-body http://127.0.0.1:8000/api/health/
```

旧镜像应在升级前确认可用，不能临时用tag猜测。若需数据库恢复，属于独立灾难操作：停止写入、备份当前现场、评估新增数据损失、负责人明确批准恢复点后再恢复；不能直接将dump灌回业务库。禁止对生产执行down -v。
