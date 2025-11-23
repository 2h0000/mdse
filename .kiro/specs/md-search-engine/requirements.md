# 需求文档

## 简介

本系统是一个基于 Python 的 Markdown 文档全文搜索引擎，使用 FastAPI + SQLite FTS5 实现快速全文检索，支持文件监控自动更新索引，可部署在本地或服务器环境。

## 术语表

- **系统 (System)**: 指 Markdown 搜索引擎整体应用
- **FTS5**: SQLite 的全文搜索扩展模块
- **索引器 (Indexer)**: 扫描并解析 Markdown 文件构建搜索索引的组件
- **监听器 (Watcher)**: 监控文件系统变化并触发索引更新的组件
- **搜索服务 (Search Service)**: 提供全文搜索功能的 API 服务
- **文档 (Document)**: 指单个 Markdown 文件及其元数据
- **Frontmatter**: Markdown 文件头部的 YAML 格式元数据
- **高亮片段 (Snippet)**: 搜索结果中包含匹配关键词的文本摘要

## 需求

### 需求 1

**用户故事:** 作为用户，我希望能够快速搜索大量 Markdown 文档的内容，以便快速找到相关信息。

#### 验收标准

1. WHEN 用户提交搜索查询 THEN 系统 SHALL 在 SQLite FTS5 索引中执行全文搜索并返回匹配结果
2. WHEN 搜索返回结果 THEN 系统 SHALL 按相关性排序结果并使用 BM25 算法计算排名
3. WHEN 显示搜索结果 THEN 系统 SHALL 提供包含匹配关键词的高亮片段
4. WHEN 搜索查询为空或仅包含空白字符 THEN 系统 SHALL 拒绝查询并返回错误信息
5. WHERE 用户指定分页参数 THEN 系统 SHALL 返回指定范围的结果子集

### 需求 2

**用户故事:** 作为用户，我希望系统能够解析 Markdown 文件的标题和内容，以便搜索时能够匹配文件的所有文本信息。

#### 验收标准

1. WHEN 索引器处理 Markdown 文件 THEN 系统 SHALL 解析 frontmatter 并提取标题字段
2. WHEN frontmatter 中不存在标题 THEN 系统 SHALL 使用文件名作为默认标题
3. WHEN 索引器提取文档内容 THEN 系统 SHALL 将 Markdown 正文转换为纯文本用于索引
4. WHEN 索引器处理文档 THEN 系统 SHALL 存储文件路径、标题、摘要和修改时间
5. WHEN 生成文档摘要 THEN 系统 SHALL 截取内容的前 200 个字符作为摘要

### 需求 3

**用户故事:** 作为用户，我希望系统能够自动监控文件变化并更新索引，以便搜索结果始终反映最新的文档内容。

#### 验收标准

1. WHEN Markdown 文件被创建 THEN 系统 SHALL 自动将该文件添加到搜索索引
2. WHEN Markdown 文件被修改 THEN 系统 SHALL 自动更新该文件在索引中的内容
3. WHEN Markdown 文件被删除 THEN 系统 SHALL 自动从索引中移除该文件的记录
4. WHEN 监听器检测到文件变化 THEN 系统 SHALL 在 5 秒内完成索引更新
5. WHEN 非 Markdown 文件发生变化 THEN 系统 SHALL 忽略该事件

### 需求 4

**用户故事:** 作为用户，我希望能够查看完整的文档内容，以便在搜索结果中找到目标后阅读全文。

#### 验收标准

1. WHEN 用户请求查看文档详情 THEN 系统 SHALL 根据文档 ID 返回完整的文档内容
2. WHEN 返回文档内容 THEN 系统 SHALL 将 Markdown 转换为 HTML 格式
3. WHEN 请求的文档 ID 不存在 THEN 系统 SHALL 返回 404 错误
4. WHEN 文档文件在磁盘上不存在 THEN 系统 SHALL 返回 404 错误并提示文件丢失
5. WHEN 渲染 Markdown THEN 系统 SHALL 支持代码块和表格扩展语法

### 需求 5

**用户故事:** 作为系统管理员，我希望能够初始化数据库并构建初始索引，以便系统首次启动时能够正常工作。

#### 验收标准

1. WHEN 执行数据库初始化 THEN 系统 SHALL 创建 docs 表用于存储文档元数据
2. WHEN 执行数据库初始化 THEN 系统 SHALL 创建 docs_fts 虚拟表用于全文搜索
3. WHEN 执行全量重建索引 THEN 系统 SHALL 扫描配置目录下的所有 Markdown 文件
4. WHEN 执行全量重建索引 THEN 系统 SHALL 清空现有索引并重新构建
5. WHEN 索引单个文件 THEN 系统 SHALL 使用 UPSERT 操作避免重复记录

### 需求 6

**用户故事:** 作为用户，我希望系统提供 Web 界面进行搜索，以便通过浏览器方便地使用搜索功能。

#### 验收标准

1. WHEN 用户访问根路径 THEN 系统 SHALL 显示搜索页面
2. WHEN 用户在搜索页面提交查询 THEN 系统 SHALL 调用搜索 API 并显示结果列表
3. WHEN 显示搜索结果 THEN 系统 SHALL 展示文档标题、路径和高亮片段
4. WHEN 用户点击搜索结果 THEN 系统 SHALL 在右侧预览区域显示完整文档内容
5. WHEN 搜索无结果 THEN 系统 SHALL 显示友好的提示信息

### 需求 7

**用户故事:** 作为开发者，我希望系统配置灵活可调，以便适应不同的部署环境和文档目录结构。

#### 验收标准

1. WHEN 系统启动 THEN 系统 SHALL 从配置文件读取 Markdown 文档根目录路径
2. WHEN 系统启动 THEN 系统 SHALL 从配置文件读取数据库文件路径
3. WHEN 配置的路径不存在 THEN 系统 SHALL 记录错误并拒绝启动
4. WHERE 用户修改配置文件 THEN 系统 SHALL 在重启后应用新配置
5. WHEN 配置文件格式错误 THEN 系统 SHALL 提供清晰的错误信息

### 需求 8

**用户故事:** 作为用户，我希望搜索支持中文分词，以便能够准确搜索中文文档内容。

#### 验收标准

1. WHEN FTS5 索引中文内容 THEN 系统 SHALL 使用 unicode61 分词器处理文本
2. WHEN 搜索中文关键词 THEN 系统 SHALL 正确匹配包含该关键词的文档
3. WHEN 文档包含中英文混合内容 THEN 系统 SHALL 同时支持中英文关键词搜索
4. WHEN 搜索结果包含中文 THEN 系统 SHALL 正确生成包含中文的高亮片段
5. WHEN 处理带音调符号的字符 THEN 系统 SHALL 移除音调符号进行标准化匹配

### 需求 9

**用户故事:** 作为开发者，我希望系统提供 RESTful API，以便将来可以集成其他前端框架或客户端。

#### 验收标准

1. WHEN 客户端调用搜索 API THEN 系统 SHALL 返回 JSON 格式的搜索结果
2. WHEN 客户端调用文档详情 API THEN 系统 SHALL 返回 HTML 格式的文档内容
3. WHEN API 请求参数无效 THEN 系统 SHALL 返回 4xx 状态码和错误描述
4. WHEN API 处理过程中发生错误 THEN 系统 SHALL 返回 5xx 状态码和错误信息
5. WHEN 系统启动 THEN 系统 SHALL 在根路径提供 API 文档页面

### 需求 10

**用户故事:** 作为系统管理员，我希望系统能够在服务器环境稳定运行，以便为多个用户提供搜索服务。

#### 验收标准

1. WHEN 系统部署到服务器 THEN 系统 SHALL 支持通过 uvicorn 或 gunicorn 启动
2. WHEN 系统在生产环境运行 THEN 系统 SHALL 记录访问日志和错误日志
3. WHEN 多个请求并发访问 THEN 系统 SHALL 正确处理 SQLite 连接并发
4. WHEN 系统长时间运行 THEN 系统 SHALL 保持监听器和索引服务稳定运行
5. WHERE 使用反向代理 THEN 系统 SHALL 正确处理代理头信息
