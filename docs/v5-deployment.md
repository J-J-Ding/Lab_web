# V5 ECS 更新部署手册

**以下是待用户批准后执行的部署步骤，本次没有执行线上构建、迁移、容器替换或 Nginx 更新。** 源代码已直接修改 `/opt/Lab_web`；当前运行后端仍是旧镜像。静态新入口可能已被原网站读取，在后端尚未更新时提示协同功能尚未部署。不要把这当作完整 V5 已上线。

## 1. 确认版本与建立候选镜像

在已确认的提交执行；保留用户未提交的 Dockerfile、README，不使用 reset/clean 覆盖。开发分支部署仅在得到明确批准后执行，不自动合并 main。

```bash
cd /opt/Lab_web
git status --short
git log -1 --oneline
umask 077
V5_RELEASE=$(git rev-parse --short HEAD)
V5_BACKUP=/opt/lab-web-backups/v5-$(date +%Y%m%d-%H%M%S)
mkdir -p "$V5_BACKUP"
chmod 700 "$V5_BACKUP"
cat > "$V5_BACKUP/release.yml" <<EOF_RELEASE
services:
  backend:
    image: lab-web-backend:v5-$V5_RELEASE
EOF_RELEASE
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" config --quiet
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" build backend
```

候选使用独立镜像标签，避免覆盖正在使用的 `lab-web-backend:v2`。若构建缓存报 parent snapshot 缺失，只对候选执行同一 build 命令加 `--no-cache`；不要 prune 或重启 Docker。不要输出包含真实凭据的 compose config。

## 2. 维护窗口与配套备份

得到停写批准后，停止后端，保留 PostgreSQL 运行。先记录镜像和容器状态，备份数据库及匹配的私有文件，任何一步失败均停止后续升级。

```bash
sudo docker compose ps > "$V5_BACKUP/containers.txt"
sudo docker inspect lab-web-backend-1 --format '{{.Image}}' > "$V5_BACKUP/old-image.txt"
sudo docker compose stop backend
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$V5_BACKUP/database.dump"
test -s "$V5_BACKUP/database.dump"
sudo docker compose exec -T db pg_restore --list < "$V5_BACKUP/database.dump" > "$V5_BACKUP/database-manifest.txt"
```

V5 首次部署前旧后端没有私有媒体卷。检查旧容器挂载：

```bash
sudo docker inspect lab-web-backend-1 --format '{{range .Mounts}}{{println .Destination .Name}}{{end}}' > "$V5_BACKUP/mounts.txt"
```

若记录存在 `/app/private_media`，必须另行保存该实际卷的完整文件备份后再迁移；可用已构建镜像、只读挂载该卷运行 tar，不启动应用。示例中的卷名须按 mounts.txt 替换，不能猜测或备份测试卷：

```bash
# 仅已有媒体卷时执行；先设置并核对实际卷名
# V5_MEDIA_VOLUME=实际卷名
# sudo docker run --rm --user 0 --entrypoint tar --mount "type=volume,src=$V5_MEDIA_VOLUME,dst=/media,readonly" "lab-web-backend:v5-$V5_RELEASE" -C /media -cf - . > "$V5_BACKUP/private-media.tar"
# tar -tf "$V5_BACKUP/private-media.tar" > "$V5_BACKUP/private-media-manifest.txt"
chmod 600 "$V5_BACKUP"/*
```

首次无媒体卷要在备份记录注明“升级前无媒体卷”。不要把备份、环境变量或证据文件提交 Git。

## 3. 迁移及启动

所有后续命令继续携带相同 release override：

```bash
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" run --rm --no-deps backend python manage.py check
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" run --rm --no-deps backend python manage.py makemigrations --check --dry-run
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" run --rm --no-deps backend python manage.py migrate --plan
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" run --rm --no-deps backend python manage.py migrate --noinput
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" run --rm --no-deps backend python manage.py migrate --check
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" up -d --no-deps --no-build --wait backend
```

不得在生产执行 Django test；隔离回归命令见验收报告。若迁移失败，先定位并修复或恢复旧后端；不能宣布成功。新卷通过镜像中的 app 所属目录初始化权限，不对宿主机开放数据库端口。数据库已有 V2 时会按依赖顺序补齐 V4 和 V5 迁移。

## 4. 保留原 Nginx，只调整上传上限

当前 `/etc/nginx/sites-enabled/default` 指向 `/etc/nginx/sites-available/default`，原 root 为 `/opt/Lab_web/frontend`，`/api/` 反代 `127.0.0.1:8000`。部署批准后备份现有配置并用 sudoedit 在已有 `/api/` location 内添加：

```nginx
client_max_body_size 11m;
```

保留原 proxy_pass、请求头、静态路由与移动端页面；不新增服务器或媒体 alias。随后执行 `sudo nginx -t`，成功后才 `sudo systemctl reload nginx`。原默认上传限制可能拒绝大于 1MiB 的合法文件。

## 5. 更新后验证与回退

```bash
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" ps
curl --fail http://127.0.0.1:8000/api/health/
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" exec -T backend python manage.py check
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" exec -T backend python manage.py migrate --check
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"'
sudo docker compose -f docker-compose.yml -f "$V5_BACKUP/release.yml" logs --tail 80 backend
```

核对 health 同时报告数据库正常、容器 healthy、匿名受保护接口返回 403 而非 404、数据库无公网端口、后端仅监听宿主机 127.0.0.1:8000。仅用测试账号在回环或受控 HTTPS 验证 Session/CSRF、投稿审批、头像/证明下载权限、退出失效、旧公开版隔离和管理历史；没有 HTTPS 不用真实账号在公网 HTTP 登录。不要打印或共享 Cookie。自审规则现以 V6.1 为准：ROOT、ADMIN、TEACHER 均可自审；ADMIN 仍不能接管其他 ADMIN/ROOT 私密资料。

异常回退使用记录的旧镜像构建单独 rollback override，再以该 override `up -d --no-deps --no-build --wait backend`；恢复对应旧前端版本/入口前保留用户改动。保留新增数据库表、审计和媒体，不反向迁移、不 drop、不对生产 down --volumes。恢复数据库/媒体备份属于另行批准的数据恢复操作。Nginx 若有变更，恢复备份后先 nginx -t 再 reload。V6 再处理公共数据迁移，V7 AI 未启用。
