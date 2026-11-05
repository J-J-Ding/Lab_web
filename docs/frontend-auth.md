# V3 前端认证：开发、验证与发布

## 当前工作约定与部署状态

用户已明确授权将 V3 更新到 `/opt/Lab_web`，本目录已同步 V3 提交 `496e005`，认证页面已由现有 Nginx 提供。后续直接在当前项目修改，不再自行使用临时开发副本；具体规则见 AGENTS.md。下文的独立副本说明保留为首次 V3 实施记录，不再作为后续开发要求。公网 HTTPS 和真实账号登录验证仍未执行。

代码在 arc-update。注册、登录、个人中心使用原生 HTML/CSS/JavaScript，对接 V2 Session API；没有新增后端接口、数据库迁移或前端构建步骤。三页分别为 register.html、login.html、profile.html。

本次开发副本在 `/tmp/lab-web-v3-work`，线上部署仍在 `/opt/Lab_web`。开发完成与推送不会自动发布到线上：Nginx 直接读取线上 frontend，所以不要在该目录编辑或复制文件来预览。

## 使用流程

1. 从统一导航打开“注册”，填写用户名、密码和确认密码。新账号由后端赋予 CUSTOMER；成功后点击“前往登录”。
2. 登录后进入个人中心。刷新或访问其他栏目时，浏览器使用 HttpOnly Session Cookie 维持登录。
3. 个人中心显示后端真实身份；is_superuser 优先显示 ROOT。用户名和身份只读，只能编辑姓名/email 与本人密码。
4. 修改密码需要旧密码；当前会话保留，其他旧会话失效。退出后个人中心不显示旧资料，并跳转登录。

账号请求使用同源 /api/auth/。共享脚本先获取 CSRF Cookie，每次写操作在发送时读取最新 csrftoken；登录轮换后不使用旧 token。密码和 Session 不写入 localStorage、sessionStorage、URL 或日志。

公开页面异步加载账号导航；无 API 时原栏目仍可使用。403 按匿名和 CSRF 失败分别处理，错误不直接插入 HTML。资料写入失败不会自动重放。跨标签页通过 BroadcastChannel 只发送会话变化通知，接收方重新请求后端确认，不传账号数据或凭据；不支持该接口时仍有 focus/visibility/pageshow 检查。

## 当前服务器环境

现有 Nginx 已将 /api/ 转发到回环后端 127.0.0.1:8000，静态根目录为 /opt/Lab_web/frontend。V3 保留这些配置，不运行第二个 Nginx。尚未使用真实账号做公网 HTTP 登录；没有 HTTPS 时只使用测试账号在回环或受控环境验收。

线上 /opt/Lab_web 的 Dockerfile 和 README 本地改动保持原样。测试辅助脚本只读取该目录的 Compose/.env 配置，绝不复制密钥到开发仓库或覆盖主库。

## 浏览器测试

测试工具是独立 Python venv + Playwright，不需要 npm、Vue、React 或前端打包器。requirements.txt 只用于测试，生产 Django 依赖不变。

本服务器已准备 /tmp/lab-web-v3-venv。需要重建私有环境时（避免升级系统 Python）：

```bash
cd /tmp/lab-web-v3-work
python3 -m venv --without-pip /tmp/lab-web-v3-venv
curl -fsS https://bootstrap.pypa.io/get-pip.py -o /tmp/lab-web-v3-get-pip.py
/tmp/lab-web-v3-venv/bin/python /tmp/lab-web-v3-get-pip.py
/tmp/lab-web-v3-venv/bin/python -m pip install -r tests/browser/requirements.txt
/tmp/lab-web-v3-venv/bin/python -m playwright install --no-shell chromium
```

Chromium 如提示缺少系统库，安装必要运行库和中文/emoji 字体，不升级已有服务；本次实际安装使用了 --no-upgrade 和 --no-install-recommends，具体包在验收报告记录。

执行完整浏览器测试：

```bash
cd /tmp/lab-web-v3-work
/tmp/lab-web-v3-venv/bin/python -m unittest discover -s tests/browser -p 'test_*.py' -v
```

support.py 自动创建 lab_web_v3_browser_ 前缀的随机新库、临时 V2 后端容器、仅回环端口和 Python 同源静态/API 转发服务。数据库名和实际 current_database 双重校验。所有浏览器注册与身份夹具都落在这个隔离库，不创建真实 ROOT，不清理主库限流。

测试结束只停止自己创建的临时服务并删除该隔离库。不要替换脚本中的数据库保护，也不要用 remove-orphans、down -v 或模糊命名批量清理正式容器。用例异常导致进程被强制终止时，先核对明确的本次临时容器/库名，再单独清理，不能猜测主库名称。

正常成功流程连接真实 V2 API，没有 mock 登录成功；另外明确模拟 503/429 等错误，验证前端失败提示。写请求 CSRF 错误也实际发往后端检查 403 和数据库无变化。关闭 trace/HAR/storageState 导出，不把密码、Cookie 或网络请求体写入报告。

桌面、平板及手机尺寸为 1440×900、768×1024、390×844、320×800。截图默认保存在 /tmp/lab-web-v3-evidence（可用 LAB_V3_EVIDENCE 指定另一私有产物目录）；截图只含临时账号。此目录为本机临时证据，代码和报告持久化到 Git，截图如需长期保存应另行安全保管。

## Django 回归与线上保留检查

从现有部署目录只运行检查和自动创建隔离库的测试，不应用迁移或更新服务：

```bash
cd /opt/Lab_web
sudo docker compose run --rm backend python manage.py check
sudo docker compose run --rm backend python manage.py makemigrations --check --dry-run
sudo docker compose run --rm backend python manage.py migrate --check
sudo docker compose run --rm backend python manage.py test --noinput --verbosity 2
curl --fail-with-body http://127.0.0.1:8000/api/health/
sudo docker compose ps
```

运行浏览器测试前后对线上 frontend 文件、Nginx 配置和主库用户信息分别计算摘要，核实无变化；摘要不输出密码哈希或个人资料。后台测试使用 test_lab_web，与浏览器临时库也分开。

## 发布步骤：必须另获用户确认，当前未执行

以下为发布操作说明，不能作为本阶段自动执行的授权。先由用户确认代码、测试、部署范围和要发布的准确提交，再按仓库规则决定合并 main；不得以开发分支已推送为由上线。

1. 保留原发布提交和静态文件备份，安全保存 .env/数据库备份。查看 git status、现有 Dockerfile/README 等改动，禁止 reset --hard 或自动 stash 导致当前文件变化。
2. 取得已经用户确认的 main 发布提交或指定发布 SHA；git fetch 只读取远程，先审查本地与目标提交的准确差异，确认没有用户文件冲突。当前只有原 Dockerfile/README 改动且目标未修改这些文件时，Git 快进不会覆盖它们；有其他改动时先人工处理，不强制操作。
3. 仅在用户授权部署后，将线上工作目录快进到准确发布提交。示例中的 SHA 必须替换为已经确认的值，不能盲目用远程最新提交。

```bash
cd /opt/Lab_web
git status --short --branch
git fetch origin
LAB_RELEASE_SHA='填写已批准的发布提交SHA'
git diff --name-status HEAD "$LAB_RELEASE_SHA"
# 在确认差异和本地改动安全后执行；此行会实际更新线上静态文件。
git merge --ff-only "$LAB_RELEASE_SHA"
```

V3 不需要数据库 migrate、重新构建后端镜像或重启 Nginx/数据库。禁止为了前端更新重建数据卷。部署后刷新旧标签页缓存，确认使用新版 navbar-loader.js 和 auth.js?v=3。

4. 验证静态文件、既有 API 和容器；通过实际 HTTPS/受控环境测试账号确认三页同源联调。没有 HTTPS 时不要输入真实账号密码。

```bash
curl -I http://127.0.0.1/register.html
curl -I http://127.0.0.1/login.html
curl -I http://127.0.0.1/profile.html
curl -I http://127.0.0.1/js/auth.js?v=3
curl -I http://127.0.0.1/css/auth.css?v=3
curl --fail-with-body http://127.0.0.1/api/health/
sudo docker compose ps
```

静态 profile.html 返回 200 是正常的，个人资料由受保护 API 提供；未登录时 JavaScript 隐藏资料并跳转登录，不能把静态 HTML 200 当作有权读取账号。

## 回退

发布前记录准确旧 SHA 并备份本次前端文件。授权回退时只恢复本次新增认证页面、auth.js/auth.css、统一导航和导航加载器到对应旧版本；不对整仓库 reset，不碰 Dockerfile/README、本地环境或数据库。不通过删除用户、反向迁移或 down -v 回退前端。同步恢复相匹配的导航和脚本并清理浏览器缓存，避免旧新资源混用。

实际通过/失败/错误/跳过数量、截图检查、修复记录和线上摘要检查见 V3-验收报告.md；未执行的发布、HTTPS 和真实账号验证必须保持“未验证”标记。
