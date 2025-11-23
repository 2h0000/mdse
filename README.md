# 🔍MDSE-Markdown 搜索引擎

基于 Python 的 Markdown 文档全文搜索引擎，使用 FastAPI + SQLite FTS5 实现快速全文检索。

## 功能特性

- 🔍 基于 SQLite FTS5 的全文搜索，支持 BM25 排名算法
- 🔄 实时文件监控，自动增量更新索引
- 📝 Markdown 解析支持 frontmatter 和内容提取
- 🌐 RESTful API 设计，易于前端集成
- 🇨🇳 支持中文分词和搜索
- 📦 轻量级部署，单文件数据库
- ✨ **智能优先级高亮** - 优先高亮完整关键词，提供清晰的搜索结果
- 🎯 **文档预览** - 点击搜索结果即可预览文档内容，关键词自动高亮

## 快速开始

### 系统要求

- Python 3.9 或更高版本
- SQLite 3.9.0 或更高版本（支持 FTS5）
- 至少 100MB 可用磁盘空间

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

复制 `.env.example` 到 `.env` 并配置参数：

```bash
cp .env.example .env
```

编辑 `.env` 文件，设置 Markdown 文档目录：

```
MD_ROOT=/path/to/your/markdown/docs
DB_PATH=./data/md_search.db
LOG_LEVEL=INFO
```

**配置验证**

系统启动时会自动验证配置：

- ✅ `MD_ROOT` 目录必须存在且为目录
- ✅ `DB_PATH` 的父目录必须存在
- ✅ `LOG_LEVEL` 必须是有效值（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- ✅ `MAX_SEARCH_LIMIT` 必须在 1-1000 范围内
- ✅ `SNIPPET_TOKENS` 必须在 1-100 范围内

如果配置无效，系统会显示清晰的错误信息并拒绝启动。参考 `.env.example` 文件了解所有可用配置选项。

### 初始化数据库

```bash
python scripts/init_db.py
```

### 启动服务

开发模式：
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

生产模式：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 访问

- Web 界面: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 项目结构

```
md-search/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── db.py                # 数据库连接和初始化
│   ├── models.py            # Pydantic 模型
│   ├── indexer.py           # 索引器
│   ├── watcher.py           # 文件监听器
│   ├── search_service.py    # 搜索服务
│   ├── api.py               # API 路由
│   ├── templates/           # HTML 模板
│   └── static/              # 静态文件
│       ├── script.js        # 前端交互脚本
│       └── style.css        # 样式文件
├── docs/
│   └── features/            # 功能文档
│       ├── HIGHLIGHT_FEATURE.md      # 高亮功能说明
│       ├── HIGHLIGHT_EXAMPLES.md     # 高亮示例
│       └── SMART_HIGHLIGHT.md        # 智能高亮详解
├── tests/                   # 测试文件
├── scripts/                 # 工具脚本
├── requirements.txt         # 生产依赖
├── requirements-dev.txt     # 开发依赖
└── .env.example            # 配置示例
```

## 开发

### 安装开发依赖

```bash
pip install -r requirements-dev.txt
```

### 运行测试

```bash
pytest
```

### 代码格式化

```bash
black app/ tests/
ruff check app/ tests/
```

## API 端点

### 搜索文档

```
GET /search?q=关键词&limit=20&offset=0
```

### 获取文档详情

```
GET /docs/{doc_id}
```

## 部署指南

### 生产环境部署

#### 方案 1: 使用 Systemd（推荐）

1. **创建专用用户**

```bash
sudo useradd -r -s /bin/false mdsearch
```

2. **安装应用**

```bash
# 克隆或复制应用到服务器
sudo mkdir -p /opt/md-search
sudo cp -r . /opt/md-search/
cd /opt/md-search

# 创建虚拟环境
sudo python3 -m venv venv
sudo venv/bin/pip install -r requirements.txt

# 配置环境变量
sudo cp .env.example .env
sudo nano .env  # 编辑配置

# 创建数据目录
sudo mkdir -p /opt/md-search/data
sudo chown -R mdsearch:mdsearch /opt/md-search
```

3. **初始化数据库**

```bash
sudo -u mdsearch /opt/md-search/venv/bin/python scripts/init_db.py
```

4. **配置 Systemd 服务**

复制示例服务文件：

```bash
sudo cp deployment/md-search.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable md-search
sudo systemctl start md-search
```

5. **检查服务状态**

```bash
sudo systemctl status md-search
sudo journalctl -u md-search -f  # 查看日志
```

#### 方案 2: 使用 Gunicorn

```bash
# 安装 gunicorn
pip install gunicorn

# 启动服务
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/md-search/access.log \
  --error-logfile /var/log/md-search/error.log \
  --daemon
```

#### 配置 Nginx 反向代理

1. **安装 Nginx**

```bash
sudo apt install nginx  # Ubuntu/Debian
sudo yum install nginx  # CentOS/RHEL
```

2. **配置站点**

复制示例配置：

```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/md-search
sudo ln -s /etc/nginx/sites-available/md-search /etc/nginx/sites-enabled/
sudo nginx -t  # 测试配置
sudo systemctl reload nginx
```

3. **配置 SSL（可选但推荐）**

使用 Let's Encrypt：

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### Docker 部署（可选）

1. **构建镜像**

```bash
docker build -t md-search:latest .
```

2. **运行容器**

```bash
docker run -d \
  --name md-search \
  -p 8000:8000 \
  -v /path/to/docs:/docs:ro \
  -v /path/to/data:/app/data \
  -e MD_ROOT=/docs \
  -e DB_PATH=/app/data/md_search.db \
  md-search:latest
```

3. **使用 Docker Compose**

```bash
docker-compose up -d
```

### 性能优化建议

1. **数据库优化**
   - 定期运行 `VACUUM` 清理数据库
   - 使用 `PRAGMA optimize` 优化查询计划

2. **Worker 数量**
   - 推荐 workers = (2 × CPU 核心数) + 1
   - 单核服务器：2-3 workers
   - 双核服务器：4-5 workers

3. **文件监控**
   - 大量文件时考虑增加系统 inotify 限制：
   ```bash
   echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
   sudo sysctl -p
   ```

4. **日志管理**
   - 配置日志轮转（logrotate）
   - 定期清理旧日志文件

### 监控和维护

#### 健康检查

```bash
# 检查服务是否运行
curl http://localhost:8000/

# 检查搜索功能
curl "http://localhost:8000/search?q=test"
```

#### 备份

```bash
# 备份数据库
cp /opt/md-search/data/md_search.db /backup/md_search_$(date +%Y%m%d).db

# 自动备份脚本（添加到 crontab）
0 2 * * * cp /opt/md-search/data/md_search.db /backup/md_search_$(date +\%Y\%m\%d).db
```

#### 更新应用

```bash
# 停止服务
sudo systemctl stop md-search

# 更新代码
cd /opt/md-search
sudo -u mdsearch git pull  # 或复制新文件

# 更新依赖
sudo -u mdsearch venv/bin/pip install -r requirements.txt

# 重启服务
sudo systemctl start md-search
```

### 故障排查

#### 服务无法启动

1. 检查日志：`sudo journalctl -u md-search -n 50`
2. 验证配置文件：确保 `.env` 中的路径存在
3. 检查权限：确保 mdsearch 用户有读写权限
4. 验证 Python 环境：`/opt/md-search/venv/bin/python --version`

#### 搜索结果为空

1. 检查索引是否构建：`sqlite3 data/md_search.db "SELECT COUNT(*) FROM docs;"`
2. 重建索引：`python scripts/init_db.py`
3. 检查文档目录权限

#### 文件监控不工作

1. 检查 inotify 限制：`cat /proc/sys/fs/inotify/max_user_watches`
2. 手动触发索引更新：重启服务
3. 查看监听器日志

### 安全建议

系统已实施以下安全加固措施：

1. **查询字符串长度限制** - 最大 500 字符，防止性能问题
2. **路径遍历防护** - 防止访问文档根目录外的文件
3. **CORS 策略配置** - 可配置允许的跨域源
4. **数据库文件权限** - 自动设置为 600（仅所有者可读写）

详细的安全文档请参考：[docs/SECURITY.md](docs/SECURITY.md)

#### 生产环境安全配置

1. **配置 CORS 允许的源**
   ```bash
   # .env
   CORS_ORIGINS=https://example.com,https://app.example.com
   ```

2. **防火墙配置**
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

3. **限制访问**
   - 使用 Nginx 配置 IP 白名单
   - 配置 HTTP Basic Auth（如需要）

4. **文件权限**
   ```bash
   sudo chmod 600 /opt/md-search/.env
   sudo chmod 600 /opt/md-search/data/md_search.db
   ```

5. **定期更新**
   - 保持系统和依赖包更新
   - 订阅安全公告
   - 定期检查日志中的安全警告

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件


## 🆕 新功能：智能高亮

### 功能概述

搜索结果中的文档预览现在支持**智能优先级高亮**：

- ✅ **优先高亮完整关键词** - 搜索"机器学习"时，优先高亮完整的"机器学习"
- ✅ **自动滚动定位** - 打开预览时自动滚动到第一个高亮位置
- ✅ **中英文混合支持** - 完美支持中英文混合搜索
- ✅ **视觉效果优化** - 清晰的黄色高亮，带脉冲动画

### 工作原理

**三级优先级策略**：
1. **完整查询**（最高优先级）- 如"机器学习"
2. **词组片段**（中等优先级）- 如"机器"、"学习"
3. **单个字符**（最低优先级）- 仅在找不到完整匹配时使用

**示例**：

搜索：`机器学习`

- 文档包含"机器学习" → 高亮完整的"**机器学习**"
- 文档只有"机器人"和"学习" → 高亮"**机**"、"**器**"、"**学**"、"**习**"

### 详细文档

- [高亮功能说明](docs/features/HIGHLIGHT_FEATURE.md)
- [智能高亮详解](docs/features/SMART_HIGHLIGHT.md)
- [高亮示例](docs/features/HIGHLIGHT_EXAMPLES.md)

### 使用方法

1. 在搜索框输入关键词
2. 点击任意搜索结果
3. 右侧预览面板会显示文档内容，关键词自动高亮
4. 页面自动滚动到第一个高亮位置

## 更新日志

### v0.2.0 (2025-11-23)

**新增功能**：
- ✨ 智能优先级高亮系统
- 🎯 文档预览面板
- 📍 自动滚动到高亮位置
- 🎨 优化的视觉效果和动画

**改进**：
- 🔧 改进中文搜索支持
- 📝 完善的功能文档
- 🧪 添加高亮功能测试

**技术细节**：
- 实现三级优先级高亮算法
- 优化前端交互体验
- 添加占位符机制避免重复高亮

### v0.1.0 (初始版本)

- 🔍 基础全文搜索功能
- 🔄 实时文件监控
- 🇨🇳 中文分词支持
- 🌐 RESTful API
