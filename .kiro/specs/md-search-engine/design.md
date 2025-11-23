# 设计文档

## 概述

Markdown 搜索引擎是一个基于 Python 的全文搜索系统，使用 FastAPI 提供 RESTful API，SQLite FTS5 实现高性能全文检索，watchdog 监控文件变化实现实时索引更新。系统采用模块化设计，支持本地开发和服务器部署。

核心特性：
- 基于 SQLite FTS5 的全文搜索，支持 BM25 排名算法
- 实时文件监控，自动增量更新索引
- Markdown 解析支持 frontmatter 和内容提取
- RESTful API 设计，易于前端集成
- 轻量级部署，单文件数据库

## 架构

系统采用分层架构：

```
┌─────────────────────────────────────┐
│         Web Layer (FastAPI)         │
│  - 路由处理                          │
│  - 请求验证                          │
│  - 响应序列化                        │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│       Service Layer                 │
│  - 搜索服务                          │
│  - 索引服务                          │
│  - 文档服务                          │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│      Data Access Layer              │
│  - SQLite 连接管理                   │
│  - FTS5 查询                         │
│  - CRUD 操作                         │
└─────────────────┬───────────────────┘
                  │
┌─────────────────▼───────────────────┐
│       Storage Layer                 │
│  - SQLite 数据库 (docs + docs_fts)  │
│  - 文件系统 (Markdown 文件)          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│    Background Services              │
│  - Watchdog 文件监听器               │
│  - 增量索引更新                      │
└─────────────────────────────────────┘
```

### 数据流

**索引流程：**
```
Markdown 文件 → 解析器 → 提取元数据/内容 → 写入 docs 表 → 写入 docs_fts 表
```

**搜索流程：**
```
用户查询 → API 验证 → FTS5 MATCH 查询 → BM25 排序 → 生成 snippet → 返回 JSON
```

**监控流程：**
```
文件变化事件 → Watchdog 捕获 → 判断文件类型 → 增量更新索引 → 提交事务
```

## 组件和接口

### 1. 配置模块 (config.py)

**职责：** 提供全局配置参数

```python
from pathlib import Path

class Config:
    MD_ROOT: Path  # Markdown 文档根目录
    DB_PATH: Path  # SQLite 数据库路径
    
    # FTS5 配置
    FTS_TOKENIZER: str = "unicode61 remove_diacritics 1"
    
    # 搜索配置
    DEFAULT_LIMIT: int = 20
    MAX_LIMIT: int = 100
    SNIPPET_TOKENS: int = 10
    
    # 监听器配置
    WATCH_RECURSIVE: bool = True
```

### 2. 数据库模块 (db.py)

**职责：** 管理 SQLite 连接和表结构

**接口：**
```python
def get_connection() -> sqlite3.Connection:
    """获取数据库连接，设置 row_factory"""
    
def init_db() -> None:
    """初始化数据库表结构"""
    
def close_connection(conn: sqlite3.Connection) -> None:
    """关闭数据库连接"""
```

**表结构：**

**docs 表：**
```sql
CREATE TABLE docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    mtime REAL NOT NULL
)
```

**docs_fts 虚拟表：**
```sql
CREATE VIRTUAL TABLE docs_fts USING fts5(
    doc_id UNINDEXED,
    title,
    content,
    path,
    tokenize = 'unicode61 remove_diacritics 1'
)
```

### 3. 索引器模块 (indexer.py)

**职责：** 扫描和索引 Markdown 文件

**接口：**
```python
def iter_md_files(root: Path) -> Iterator[Path]:
    """递归遍历目录下所有 .md 文件"""
    
def extract_text_from_md(path: Path) -> tuple[str, str, str]:
    """
    解析 Markdown 文件
    返回: (title, summary, content)
    """
    
def index_file(conn: sqlite3.Connection, path: Path) -> None:
    """索引单个文件到数据库"""
    
def full_reindex(conn: sqlite3.Connection) -> None:
    """全量重建索引"""
    
def remove_file_from_index(conn: sqlite3.Connection, path: Path) -> None:
    """从索引中删除文件"""
```

**解析逻辑：**
1. 使用 `python-frontmatter` 解析 YAML frontmatter
2. 提取 `title` 字段，如果不存在则使用文件名（去除 .md 扩展名）
3. 提取 Markdown 正文内容
4. 生成摘要：截取前 200 个字符
5. 记录文件修改时间 (mtime)

### 4. 监听器模块 (watcher.py)

**职责：** 监控文件系统变化并触发索引更新

**接口：**
```python
class MdEventHandler(FileSystemEventHandler):
    def on_created(self, event: FileSystemEvent) -> None:
        """处理文件创建事件"""
        
    def on_modified(self, event: FileSystemEvent) -> None:
        """处理文件修改事件"""
        
    def on_deleted(self, event: FileSystemEvent) -> None:
        """处理文件删除事件"""

def start_watcher(root: Path) -> Observer:
    """启动文件监听器"""
```

**事件处理逻辑：**
- 过滤非 .md 文件
- 创建/修改：调用 `index_file()`
- 删除：调用 `remove_file_from_index()`
- 每次操作后立即提交事务

### 5. 搜索服务模块 (search_service.py)

**职责：** 提供搜索功能

**接口：**
```python
def search_documents(
    query: str,
    limit: int = 20,
    offset: int = 0
) -> tuple[list[SearchResult], int]:
    """
    执行全文搜索
    返回: (结果列表, 总数)
    """
    
def get_document_by_id(doc_id: int) -> Optional[Document]:
    """根据 ID 获取文档"""
    
def render_document_html(doc_id: int) -> str:
    """渲染文档为 HTML"""
```

**搜索查询：**
```sql
SELECT 
    d.id,
    d.title,
    d.path,
    snippet(docs_fts, 1, '<mark>', '</mark>', '...', 10) AS snippet,
    bm25(docs_fts) AS rank
FROM docs_fts
JOIN docs d ON d.id = docs_fts.doc_id
WHERE docs_fts MATCH ?
ORDER BY rank
LIMIT ? OFFSET ?
```

### 6. API 模块 (api.py)

**职责：** 定义 RESTful API 端点

**端点：**

**GET /search**
- 参数：`q` (查询字符串), `limit` (可选), `offset` (可选)
- 响应：`SearchResponse`
- 验证：查询字符串不能为空

**GET /docs/{doc_id}**
- 参数：`doc_id` (路径参数)
- 响应：HTML 内容
- 错误：404 如果文档不存在

**GET /**
- 响应：搜索页面 HTML

### 7. 主应用模块 (main.py)

**职责：** 创建和配置 FastAPI 应用

```python
app = FastAPI(title="Markdown Search Engine")

@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库和监听器"""
    init_db()
    start_watcher(Config.MD_ROOT)

@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
```

## 数据模型

### Pydantic 模型

```python
class SearchResult(BaseModel):
    id: int
    title: str
    path: str
    snippet: str

class SearchResponse(BaseModel):
    total: int
    results: list[SearchResult]
    query: str
    limit: int
    offset: int

class Document(BaseModel):
    id: int
    path: str
    title: str
    summary: str
    mtime: float
```

### 数据库模型

**docs 表字段：**
- `id`: 主键，自增
- `path`: 文件路径，唯一索引
- `title`: 文档标题
- `summary`: 文档摘要（前 200 字符）
- `mtime`: 文件修改时间戳

**docs_fts 表字段：**
- `doc_id`: 关联 docs.id，不参与分词
- `title`: 标题，参与全文搜索
- `content`: 正文内容，参与全文搜索
- `path`: 文件路径，参与全文搜索

## 正确性属性

*属性是指在系统所有有效执行中都应该成立的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性是人类可读规范和机器可验证正确性保证之间的桥梁。*


### 属性反思

在编写正确性属性之前，我需要识别并消除冗余：

**冗余分析：**
- 属性 1.1（搜索返回匹配结果）和属性 1.3（高亮片段包含关键词）可以合并，因为高亮验证已经隐含了匹配验证
- 属性 3.1、3.2、3.3（文件创建/修改/删除）可以合并为一个综合的"索引同步"属性
- 属性 2.4（存储所有字段）已经被其他属性覆盖（标题提取、摘要生成等）
- 属性 4.1（返回文档内容）和 4.2（转换为 HTML）可以合并

**保留的核心属性：**
- 搜索结果高亮和排序
- Markdown 解析和索引
- 文件监控同步
- 分页正确性
- 错误处理
- 中文支持

### 正确性属性列表

**属性 1: 搜索结果包含高亮关键词**
*对于任意* 搜索查询和文档集合，返回的每个搜索结果的 snippet 字段应包含用 `<mark>` 标签包裹的查询关键词
**验证需求: 1.3**

**属性 2: 搜索结果按相关性排序**
*对于任意* 搜索查询，返回结果的 BM25 rank 值应按降序排列（rank 值越小越相关）
**验证需求: 1.2**

**属性 3: 空查询被拒绝**
*对于任意* 仅包含空白字符的查询字符串，系统应拒绝查询并返回 4xx 错误
**验证需求: 1.4**

**属性 4: 分页返回正确数量**
*对于任意* 有效的 limit 和 offset 参数，返回的结果数量应不超过 limit，且应从正确的偏移位置开始
**验证需求: 1.5**

**属性 5: Frontmatter 标题提取**
*对于任意* 包含 frontmatter 的 Markdown 文件，如果 frontmatter 中存在 title 字段，索引后的文档标题应等于该字段值
**验证需求: 2.1**

**属性 6: 文档摘要长度限制**
*对于任意* Markdown 文档，生成的摘要长度应不超过 200 个字符
**验证需求: 2.5**

**属性 7: 索引与文件系统同步**
*对于任意* 文件系统操作（创建、修改、删除 .md 文件），索引应在操作后反映文件系统的当前状态
**验证需求: 3.1, 3.2, 3.3**

**属性 8: 非 Markdown 文件被忽略**
*对于任意* 非 .md 扩展名的文件，文件监听器应忽略其创建、修改、删除事件
**验证需求: 3.5**

**属性 9: 文档检索返回 HTML**
*对于任意* 已索引的文档 ID，调用文档详情 API 应返回有效的 HTML 格式内容
**验证需求: 4.2**

**属性 10: 索引幂等性**
*对于任意* Markdown 文件，多次索引同一文件应只在数据库中产生一条记录
**验证需求: 5.5**

**属性 11: 全量重建清空旧数据**
*对于任意* 初始索引状态，执行全量重建后，索引应只包含当前文件系统中存在的文件
**验证需求: 5.4**

**属性 12: 搜索响应包含必需字段**
*对于任意* 搜索查询，返回的 JSON 响应应包含 total、results、query、limit、offset 字段
**验证需求: 6.3**

**属性 13: 配置重载生效**
*对于任意* 配置修改，系统重启后应使用新的配置值
**验证需求: 7.4**

**属性 14: 中文关键词搜索**
*对于任意* 包含中文内容的文档和中文查询关键词，搜索应能正确匹配并返回结果
**验证需求: 8.2**

**属性 15: 中英文混合搜索**
*对于任意* 包含中英文混合内容的文档，使用中文或英文关键词搜索都应能匹配
**验证需求: 8.3**

**属性 16: 中文高亮正确性**
*对于任意* 中文搜索查询，返回的 snippet 应包含正确的中文字符和 `<mark>` 标签
**验证需求: 8.4**

**属性 17: API 返回 JSON 格式**
*对于任意* 搜索 API 调用，响应应是有效的 JSON 格式
**验证需求: 9.1**

**属性 18: 无效参数返回 4xx**
*对于任意* 包含无效参数的 API 请求，系统应返回 4xx 状态码
**验证需求: 9.3**

**属性 19: Markdown 扩展语法支持**
*对于任意* 包含代码块或表格的 Markdown 文档，渲染的 HTML 应包含相应的 HTML 标签（`<pre><code>` 或 `<table>`）
**验证需求: 4.5**

**属性 20: 音调符号标准化**
*对于任意* 带音调符号的文本，搜索不带音调的关键词应能匹配
**验证需求: 8.5**

## 错误处理

### 错误类型和处理策略

**1. 输入验证错误**
- 空查询字符串 → 返回 422 Unprocessable Entity
- 无效的 limit/offset → 返回 422 Unprocessable Entity
- 超出最大 limit → 自动截断到 MAX_LIMIT

**2. 资源不存在错误**
- 文档 ID 不存在 → 返回 404 Not Found
- 文件在磁盘上不存在 → 返回 404 Not Found，提示 "File not found on disk"

**3. 数据库错误**
- 连接失败 → 返回 503 Service Unavailable
- 查询超时 → 返回 504 Gateway Timeout
- 完整性约束违反 → 记录日志，返回 500 Internal Server Error

**4. 文件系统错误**
- 配置的根目录不存在 → 启动失败，记录错误日志
- 文件读取权限不足 → 跳过该文件，记录警告日志
- 文件编码错误 → 尝试多种编码，失败则跳过并记录警告

**5. 解析错误**
- Frontmatter 格式错误 → 忽略 frontmatter，使用文件名作为标题
- Markdown 解析失败 → 使用原始文本内容

### 错误响应格式

```python
class ErrorResponse(BaseModel):
    error: str
    detail: str
    timestamp: datetime
```

### 日志策略

- **INFO**: 正常操作（启动、索引文件、搜索请求）
- **WARNING**: 可恢复错误（文件读取失败、解析错误）
- **ERROR**: 严重错误（数据库连接失败、配置错误）
- **DEBUG**: 详细调试信息（SQL 查询、文件路径）

## 测试策略

### 单元测试

使用 `pytest` 作为测试框架，测试覆盖：

**1. 索引器模块测试**
- 测试 frontmatter 解析（有/无 title）
- 测试摘要生成（短文本、长文本）
- 测试文件遍历（嵌套目录）

**2. 搜索服务测试**
- 测试基本搜索功能
- 测试分页逻辑
- 测试空结果处理

**3. API 端点测试**
- 使用 `TestClient` 测试所有端点
- 测试参数验证
- 测试错误响应格式

**4. 数据库测试**
- 使用内存数据库 (`:memory:`)
- 测试表创建
- 测试 UPSERT 逻辑

### 基于属性的测试

使用 `hypothesis` 作为属性测试框架，配置每个测试运行至少 100 次迭代。

**测试标注格式：**
每个属性测试必须使用以下格式标注：
```python
# Feature: md-search-engine, Property X: [属性描述]
```

**属性测试覆盖：**

1. **搜索功能属性测试**
   - 属性 1: 高亮关键词
   - 属性 2: 结果排序
   - 属性 3: 空查询拒绝
   - 属性 4: 分页正确性

2. **索引功能属性测试**
   - 属性 5: Frontmatter 提取
   - 属性 6: 摘要长度
   - 属性 10: 索引幂等性
   - 属性 11: 全量重建

3. **文件监控属性测试**
   - 属性 7: 索引同步
   - 属性 8: 文件过滤

4. **文档渲染属性测试**
   - 属性 9: HTML 输出
   - 属性 19: Markdown 扩展

5. **中文支持属性测试**
   - 属性 14: 中文搜索
   - 属性 15: 混合语言
   - 属性 16: 中文高亮
   - 属性 20: 音调标准化

6. **API 属性测试**
   - 属性 12: 响应字段
   - 属性 17: JSON 格式
   - 属性 18: 错误状态码

**生成器策略：**
- 使用 `hypothesis.strategies` 生成随机 Markdown 内容
- 生成包含中英文混合的文本
- 生成各种边界情况（空文件、超长文件、特殊字符）
- 生成有效和无效的 API 参数

### 集成测试

**端到端测试场景：**
1. 启动应用 → 初始化数据库 → 全量索引 → 执行搜索 → 验证结果
2. 创建文件 → 等待监听器 → 搜索新文件 → 验证能找到
3. 修改文件 → 等待监听器 → 搜索更新内容 → 验证结果更新
4. 删除文件 → 等待监听器 → 搜索删除文件 → 验证找不到

### 测试数据

**测试文档集：**
- 纯英文文档
- 纯中文文档
- 中英文混合文档
- 包含代码块的文档
- 包含表格的文档
- 带 frontmatter 的文档
- 不带 frontmatter 的文档
- 空文档
- 超长文档（>10000 字符）

## 性能考虑

### 索引性能

**优化策略：**
- 批量插入：使用事务批量提交多个文件
- 增量更新：只更新变化的文件，不重建整个索引
- 异步索引：文件监听器使用后台线程处理索引更新

**预期性能：**
- 索引速度：约 100-200 文件/秒（取决于文件大小）
- 内存占用：基线 ~50MB + 索引大小

### 搜索性能

**优化策略：**
- FTS5 自动优化：定期运行 `INSERT INTO docs_fts(docs_fts) VALUES('optimize')`
- 结果缓存：对热门查询使用 LRU 缓存（可选）
- 限制结果数：强制最大 limit 避免大量数据传输

**预期性能：**
- 搜索延迟：<100ms（10000 文档规模）
- 并发支持：SQLite 支持多读单写

### 数据库大小

**估算：**
- 每个文档平均 5KB 内容
- 10000 文档 ≈ 50MB 原始内容
- FTS5 索引 ≈ 原始内容的 30-50%
- 总数据库大小 ≈ 65-75MB

## 部署架构

### 本地开发模式

```
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**特点：**
- 自动重载代码变化
- 单进程运行
- 适合开发调试

### 生产服务器模式

**方案 1: Uvicorn + Systemd**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**方案 2: Gunicorn + Uvicorn Workers**
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

**Nginx 反向代理配置：**
```nginx
server {
    listen 80;
    server_name md.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    
    location /static {
        alias /path/to/app/static;
    }
}
```

### 容器化部署（可选）

**Dockerfile 示例：**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Docker Compose：**
```yaml
version: '3.8'
services:
  md-search:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./docs:/docs:ro
      - ./data:/app/data
    environment:
      - MD_ROOT=/docs
      - DB_PATH=/app/data/md_search.db
```

## 安全考虑

### 输入验证

- 查询字符串长度限制（最大 500 字符）
- 路径遍历防护：验证文件路径在配置的根目录内
- SQL 注入防护：使用参数化查询

### 访问控制

- 文件系统隔离：只能访问配置的文档目录
- API 速率限制：使用 `slowapi` 限制请求频率（可选）
- CORS 配置：根据需要配置跨域策略

### 数据保护

- 数据库文件权限：设置为 600（仅所有者可读写）
- 日志脱敏：不记录敏感文件内容
- 错误信息：生产环境不暴露内部路径和堆栈

## 可扩展性

### 未来增强方向

**1. 高级搜索功能**
- 布尔查询（AND, OR, NOT）
- 短语搜索（"exact phrase"）
- 通配符搜索（prefix*）
- 字段特定搜索（title:keyword）

**2. 模糊搜索**
- 集成 `rapidfuzz` 进行二次排序
- 拼写纠正建议

**3. 多语言支持**
- 可配置的分词器
- 语言检测和自适应分词

**4. 性能优化**
- Redis 缓存热门查询
- 读写分离（多个只读副本）
- 分布式索引（多个数据库分片）

**5. 功能增强**
- 标签系统
- 收藏夹
- 搜索历史
- 相关文档推荐

## 依赖管理

### 核心依赖

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-frontmatter>=1.0.0
markdown>=3.5.0
watchdog>=3.0.0
pydantic>=2.0.0
jinja2>=3.1.0
```

### 开发依赖

```
pytest>=7.4.0
pytest-asyncio>=0.21.0
hypothesis>=6.90.0
httpx>=0.25.0  # for TestClient
black>=23.0.0
ruff>=0.1.0
```

### 可选依赖

```
rapidfuzz>=3.0.0  # 模糊搜索
slowapi>=0.1.9    # 速率限制
gunicorn>=21.0.0  # 生产服务器
```

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
│   ├── templates/
│   │   ├── base.html
│   │   ├── search.html
│   │   └── doc.html
│   └── static/
│       ├── style.css
│       └── script.js
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # pytest fixtures
│   ├── test_indexer.py
│   ├── test_search.py
│   ├── test_api.py
│   ├── test_watcher.py
│   └── test_properties.py   # 属性测试
├── scripts/
│   └── init_db.py           # 初始化脚本
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── README.md
└── pyproject.toml
```

## 配置示例

### .env 文件

```bash
MD_ROOT=/path/to/markdown/docs
DB_PATH=./data/md_search.db
LOG_LEVEL=INFO
MAX_SEARCH_LIMIT=100
SNIPPET_TOKENS=10
```

### config.py 实现

```python
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    md_root: Path
    db_path: Path = Path("./md_search.db")
    log_level: str = "INFO"
    max_search_limit: int = 100
    snippet_tokens: int = 10
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## 总结

本设计文档定义了一个完整的 Markdown 搜索引擎系统，具有以下特点：

1. **高性能全文搜索**：基于 SQLite FTS5，支持 BM25 排名
2. **实时索引更新**：使用 watchdog 监控文件变化
3. **完整的 Markdown 支持**：解析 frontmatter 和扩展语法
4. **RESTful API 设计**：易于集成和扩展
5. **中文友好**：支持中文分词和搜索
6. **可靠的错误处理**：完善的错误处理和日志记录
7. **灵活部署**：支持本地开发和生产服务器
8. **全面的测试**：单元测试 + 属性测试保证正确性

系统设计遵循模块化原则，各组件职责清晰，易于维护和扩展。
