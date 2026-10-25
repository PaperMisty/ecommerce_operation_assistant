# 电商运营助手 - Nginx 生产级部署与 SSL 证书配置指南

本文档提供 Nginx 部署、本地开发自签名证书配置、生产环境 Let's Encrypt 证书自动化申请及日常运维指南。

---

## 1. 快速入门与环境准备

### 1.1 安装 Nginx (Ubuntu / Debian)

执行以下命令安装 Nginx：

```bash
sudo apt update
sudo apt install -y nginx
```

### 1.2 部署配置文件

创建软链接将当前配置文件挂载至 Nginx 配置目录：

```bash
# 1. 建立 SSL 证书目录
sudo mkdir -p /etc/nginx/ssl

# 2. 创建站点软链接
sudo ln -sf /home/ubuntu/projects/ecommerce_operation_assistant/deploy/nginx/ecommerce.conf /etc/nginx/sites-available/ecommerce.conf
sudo ln -sf /etc/nginx/sites-available/ecommerce.conf /etc/nginx/sites-enabled/ecommerce.conf

# 3. 移除 Nginx 默认站点（避免 80 端口冲突）
sudo rm -f /etc/nginx/sites-enabled/default
```

### 1.3 权限排查（避免静态文件 403 Forbidden）

Nginx Worker 进程默认以 `www-data` 用户运行。请确保 Nginx 对前端目录路径具备执行权限（`+x`）：

```bash
# 赋予家目录与项目路径的遍历执行权限
chmod o+x /home/ubuntu
chmod -R 755 /home/ubuntu/projects/ecommerce_operation_assistant/frontend/dist
```

---

## 2. 本地开发环境：mkcert 快速生成授信证书 (3 分钟)

`mkcert` 是零配置的本地自签 CA 证书生成工具。它会自动将本地 CA 写入系统及浏览器根证书信任库，避免浏览器提示“不安全连接”。

### 2.1 安装 mkcert

在 Ubuntu / WSL2 环境执行：

```bash
# 1. 安装依赖包
sudo apt install -y libnss3-tools curl

# 2. 下载 mkcert 二进制文件
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo mv mkcert-v*-linux-amd64 /usr/local/bin/mkcert

# 3. 验证安装
mkcert -version
```

### 2.2 生成并安装本地信任根证书

```bash
# 安装本地 Root CA
mkcert -install
```

> **WSL2 / Windows 提示**：若在 Windows 宿主机浏览器中访问 WSL2 内的服务，需在 Windows PowerShell (管理员模式) 中同样运行 `choco install mkcert` 并执行 `mkcert -install`，或将 WSL2 生成的 CA 根证书导出并导入 Windows 受信任的根证书颁发机构。

### 2.3 生成项目 SSL 证书

生成针对 `localhost` 和 `127.0.0.1` 的证书，并移动至目标目录：

```bash
# 生成证书
mkcert localhost 127.0.0.1

# 移动至 Nginx 标准证书路径
sudo mv localhost+1.pem /etc/nginx/ssl/ecommerce.crt
sudo mv localhost+1-key.pem /etc/nginx/ssl/ecommerce.key

# 设置证书权限
sudo chmod 600 /etc/nginx/ssl/ecommerce.key
sudo chmod 644 /etc/nginx/ssl/ecommerce.crt
```

---

## 3. 生产环境：Certbot & Let's Encrypt 证书自动化

Let's Encrypt 提供免费、受现代浏览器全面信任的 TLS 证书。

### 3.1 安装 Certbot

推荐使用 Snap 或 apt 安装 Certbot 及其 Nginx 插件：

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

### 3.2 申请证书

将 `ecommerce.conf` 中的 `server_name localhost;` 修改为你的真实公网域名（如 `assistant.yourdomain.com`）。

#### 方式 A：使用 Nginx 插件全自动申请（推荐）

Certbot 会自动验证域名并识别 Nginx 配置：

```bash
sudo certbot --nginx -d assistant.yourdomain.com
```

#### 方式 B：Webroot 独立申请并映射到标准路径

如果需要保持统一的证书路径 `/etc/nginx/ssl/`：

```bash
# 1. 创建 ACME 验证目录
sudo mkdir -p /var/www/certbot

# 2. 申请证书
sudo certbot certonly --webroot -w /var/www/certbot -d assistant.yourdomain.com

# 3. 软链接至 Nginx 配置文件指定的标准位置
sudo ln -sf /etc/letsencrypt/live/assistant.yourdomain.com/fullchain.pem /etc/nginx/ssl/ecommerce.crt
sudo ln -sf /etc/letsencrypt/live/assistant.yourdomain.com/privkey.pem /etc/nginx/ssl/ecommerce.key
```

### 3.3 自动化续期验证

Let's Encrypt 证书有效期为 90 天。Certbot 已默认注册 systemd 定时任务或 cron。

执行模拟续期命令以验证自动化机制：

```bash
sudo certbot renew --dry-run
```

若需续期成功后自动重载 Nginx，可配置续期钩子（Deploy Hook）：

```bash
# 在续期成功后触发平滑重载
sudo certbot renew --deploy-hook "systemctl reload nginx"
```

---

## 4. Nginx 运维与检查命令清单

| 操作任务 | 执行命令 | 说明 |
| :--- | :--- | :--- |
| **语法检查** | `sudo nginx -t` | 每次修改配置文件后**必须**先运行此命令 |
| **无感重载** | `sudo systemctl reload nginx` | 平滑加载新配置，不中断存量连接 |
| **服务重启** | `sudo systemctl restart nginx` | 强制重启服务进程 |
| **状态查看** | `sudo systemctl status nginx` | 查看进程运行状态与启动日志 |
| **实时访问日志** | `tail -f /var/log/nginx/ecommerce_access.log` | 实时查看 HTTP 请求与状态码 |
| **实时错误日志** | `tail -f /var/log/nginx/ecommerce_error.log` | 排查 502/403 错误的必备手段 |

---

## 5. 关键安全与反向代理设计说明

1. **强制 HTTPS 301 重定向**：所有 80 端口 HTTP 请求统一跳转，杜绝中间人劫持与明文传输。
2. **现代加密协议**：禁用 TLS 1.0 与 TLS 1.1，仅放行 TLS 1.2 与 TLS 1.3，配合高安全性加密套件。
3. **协议识别与安全 Cookie 下发**：
   - 配置 `proxy_set_header X-Forwarded-Proto https;` 与 `proxy_set_header Host $host;`。
   - 后端 FastAPI / Uvicorn 据此感知客户端连接形态，确保安全下发 `HttpOnly` 与 `Secure` 属性的 Session / JWT Cookie。
4. **前端 SPA 路由支持**：使用 `try_files $uri $uri/ /index.html;` 避免浏览器刷新路由页面产生 404 错误。
5. **AI 流式输出优化**：显式配置 `proxy_buffering off;`，彻底关闭代理缓冲区，确保后端 SSE (Server-Sent Events) 与大模型打字机流式输出零延迟到达用户终端。
