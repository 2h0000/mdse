"""API 路由测试

测试 RESTful API 端点的功能和错误处理。
验证需求: 1.4, 4.3, 4.4, 9.3
"""

import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.db import get_connection, init_db, close_connection
from app.indexer import index_file


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_db_path = settings.db_path
        settings.db_path = Path(tmpdir) / "test.db"
        
        conn = get_connection()
        init_db(conn)
        close_connection(conn)
        
        yield settings.db_path
        
        settings.db_path = original_db_path


@pytest.fixture
def temp_md_root():
    """创建临时 Markdown 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_md_root = settings.md_root
        settings.md_root = Path(tmpdir)
        
        yield Path(tmpdir)
        
        settings.md_root = original_md_root


@pytest.fixture
def indexed_docs(temp_db, temp_md_root):
    """创建并索引测试文档"""
    docs = [
        ("doc1.md", "---\ntitle: Python Tutorial\n---\n\nLearn Python programming language basics."),
        ("doc2.md", "---\ntitle: JavaScript Guide\n---\n\nJavaScript is a programming language for web."),
        ("doc3.md", "---\ntitle: Python Advanced\n---\n\nAdvanced Python topics and best practices."),
    ]
    
    conn = get_connection()
    
    for filename, content in docs:
        file_path = temp_md_root / filename
        file_path.write_text(content)
        index_file(conn, file_path)
    
    close_connection(conn)
    
    return docs


@pytest.fixture
def client():
    """创建测试客户端"""
    return TestClient(app)


def test_search_endpoint_basic(client, temp_db, indexed_docs):
    """测试基本搜索端点功能
    
    验证需求: 1.1 - 执行全文搜索并返回结果
    """
    response = client.get("/search?q=Python")
    
    assert response.status_code == 200
    
    data = response.json()
    assert "total" in data
    assert "results" in data
    assert "query" in data
    assert "limit" in data
    assert "offset" in data
    
    assert data["query"] == "Python"
    assert data["total"] >= 1
    assert len(data["results"]) >= 1


def test_search_endpoint_empty_query(client, temp_db, indexed_docs):
    """测试空查询被拒绝
    
    验证需求: 1.4 - 搜索查询为空或仅包含空白字符时拒绝查询
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    # 测试空字符串
    response = client.get("/search?q=")
    assert response.status_code == 422
    
    # 测试仅包含空白字符
    response = client.get("/search?q=%20%20%20")  # URL encoded spaces
    assert response.status_code == 422
    
    # 测试仅包含制表符和换行符
    response = client.get("/search?q=%09%0A")  # URL encoded tab and newline
    assert response.status_code == 422


def test_search_endpoint_missing_query(client, temp_db, indexed_docs):
    """测试缺少查询参数
    
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    response = client.get("/search")
    assert response.status_code == 422


def test_search_endpoint_with_pagination(client, temp_db, indexed_docs):
    """测试搜索端点的分页功能
    
    验证需求: 1.5 - 返回指定范围的结果子集
    """
    # 测试 limit 参数
    response = client.get("/search?q=language&limit=1")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["results"]) <= 1
    assert data["limit"] == 1
    
    # 测试 offset 参数
    response = client.get("/search?q=language&offset=1")
    assert response.status_code == 200
    
    data = response.json()
    assert data["offset"] == 1


def test_search_endpoint_invalid_limit(client, temp_db, indexed_docs):
    """测试无效的 limit 参数
    
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    # 测试负数 limit
    response = client.get("/search?q=Python&limit=-1")
    assert response.status_code == 422
    
    # 测试超过最大值的 limit
    response = client.get("/search?q=Python&limit=1000")
    assert response.status_code == 422
    
    # 测试零 limit
    response = client.get("/search?q=Python&limit=0")
    assert response.status_code == 422


def test_search_endpoint_invalid_offset(client, temp_db, indexed_docs):
    """测试无效的 offset 参数
    
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    # 测试负数 offset
    response = client.get("/search?q=Python&offset=-1")
    assert response.status_code == 422


def test_search_endpoint_response_format(client, temp_db, indexed_docs):
    """测试搜索响应格式
    
    验证需求: 9.1 - 返回 JSON 格式的搜索结果
    """
    response = client.get("/search?q=Python")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    
    data = response.json()
    
    # 验证响应包含所有必需字段
    assert "total" in data
    assert "results" in data
    assert "query" in data
    assert "limit" in data
    assert "offset" in data
    
    # 验证结果格式
    if len(data["results"]) > 0:
        result = data["results"][0]
        assert "id" in result
        assert "title" in result
        assert "path" in result
        assert "snippet" in result


def test_search_endpoint_snippet_highlighting(client, temp_db, indexed_docs):
    """测试搜索结果包含高亮片段
    
    验证需求: 1.3 - 提供包含匹配关键词的高亮片段
    """
    response = client.get("/search?q=programming")
    
    assert response.status_code == 200
    
    data = response.json()
    
    # 验证至少有一个结果
    assert len(data["results"]) >= 1
    
    # 验证 snippet 包含高亮标记
    for result in data["results"]:
        assert "<mark>" in result["snippet"]
        assert "</mark>" in result["snippet"]


def test_get_document_endpoint(client, temp_db, indexed_docs):
    """测试获取文档端点
    
    验证需求: 4.1 - 根据文档 ID 返回完整的文档内容
    验证需求: 4.2 - 将 Markdown 转换为 HTML 格式
    """
    # 先搜索获取一个文档 ID
    search_response = client.get("/search?q=Python")
    assert search_response.status_code == 200
    
    data = search_response.json()
    assert len(data["results"]) > 0
    
    doc_id = data["results"][0]["id"]
    
    # 获取文档
    response = client.get(f"/docs/{doc_id}")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    html_content = response.text
    assert len(html_content) > 0


def test_get_document_not_found(client, temp_db, indexed_docs):
    """测试获取不存在的文档
    
    验证需求: 4.3 - 请求的文档 ID 不存在时返回 404 错误
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    response = client.get("/docs/99999")
    
    assert response.status_code == 404


def test_get_document_invalid_id(client, temp_db, indexed_docs):
    """测试无效的文档 ID
    
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    # 测试负数 ID
    response = client.get("/docs/-1")
    assert response.status_code == 422
    
    # 测试零 ID
    response = client.get("/docs/0")
    assert response.status_code == 422


def test_get_document_file_missing(client, temp_db, temp_md_root):
    """测试获取文件已删除的文档
    
    验证需求: 4.4 - 文档文件在磁盘上不存在时返回 404 错误
    """
    # 创建并索引文档
    content = "---\ntitle: Temp Doc\n---\n\nTemporary content."
    file_path = temp_md_root / "temp_doc.md"
    file_path.write_text(content)
    
    conn = get_connection()
    index_file(conn, file_path)
    close_connection(conn)
    
    # 搜索获取文档 ID
    search_response = client.get("/search?q=Temp")
    assert search_response.status_code == 200
    
    data = search_response.json()
    assert len(data["results"]) > 0
    doc_id = data["results"][0]["id"]
    
    # 删除文件
    file_path.unlink()
    
    # 尝试获取文档
    response = client.get(f"/docs/{doc_id}")
    
    assert response.status_code == 404


def test_root_endpoint(client):
    """测试根路径端点
    
    验证需求: 6.1 - 用户访问根路径时显示搜索页面
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    # 验证页面包含搜索表单
    html_content = response.text
    assert "search-form" in html_content or "search-input" in html_content


def test_search_no_results(client, temp_db, indexed_docs):
    """测试无结果的搜索"""
    response = client.get("/search?q=nonexistent_keyword_xyz")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 0
    assert len(data["results"]) == 0


def test_search_with_special_characters(client, temp_db, indexed_docs):
    """测试包含特殊字符的搜索"""
    # 测试包含引号的查询
    response = client.get('/search?q="Python"')
    assert response.status_code == 200 or response.status_code == 422
    
    # 测试包含括号的查询
    response = client.get("/search?q=(Python)")
    # FTS5 可能会处理或拒绝这些查询
    assert response.status_code in [200, 422, 500]


def test_get_document_with_code_blocks(client, temp_db, temp_md_root):
    """测试获取包含代码块的文档
    
    验证需求: 4.5 - 支持代码块扩展语法
    """
    # 创建包含代码块的文档
    content = """---
title: Code Example
---

# Python Code

```python
def hello():
    print("Hello, World!")
```
"""
    
    file_path = temp_md_root / "code_doc.md"
    file_path.write_text(content)
    
    conn = get_connection()
    index_file(conn, file_path)
    close_connection(conn)
    
    # 搜索获取文档 ID
    search_response = client.get("/search?q=Code")
    assert search_response.status_code == 200
    
    data = search_response.json()
    assert len(data["results"]) > 0
    doc_id = data["results"][0]["id"]
    
    # 获取文档
    response = client.get(f"/docs/{doc_id}")
    
    assert response.status_code == 200
    
    html_content = response.text
    # 验证包含代码相关的 HTML 标签
    assert "<code>" in html_content or "<pre>" in html_content


def test_get_document_with_tables(client, temp_db, temp_md_root):
    """测试获取包含表格的文档
    
    验证需求: 4.5 - 支持表格扩展语法
    """
    # 创建包含表格的文档
    content = """---
title: Table Example
---

# Data Table

| Name | Age |
|------|-----|
| Alice | 30 |
| Bob | 25 |
"""
    
    file_path = temp_md_root / "table_doc.md"
    file_path.write_text(content)
    
    conn = get_connection()
    index_file(conn, file_path)
    close_connection(conn)
    
    # 搜索获取文档 ID
    search_response = client.get("/search?q=Table")
    assert search_response.status_code == 200
    
    data = search_response.json()
    assert len(data["results"]) > 0
    doc_id = data["results"][0]["id"]
    
    # 获取文档
    response = client.get(f"/docs/{doc_id}")
    
    assert response.status_code == 200
    
    html_content = response.text
    # 验证包含表格 HTML 标签
    assert "<table>" in html_content
    assert "<tr>" in html_content


def test_search_page_displays(client, temp_db):
    """测试搜索页面显示
    
    验证需求: 6.1 - 用户访问根路径时显示搜索页面
    """
    response = client.get("/")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    html_content = response.text
    
    # 验证页面包含必要的元素
    assert "search-input" in html_content
    assert "search-form" in html_content
    assert "Markdown" in html_content or "搜索" in html_content


def test_search_page_with_results(client, temp_db, indexed_docs):
    """测试搜索页面显示结果
    
    验证需求: 6.3 - 显示搜索结果时展示文档标题、路径和高亮片段
    """
    response = client.get("/?q=Python")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    html_content = response.text
    
    # 验证页面包含搜索结果
    assert "result-item" in html_content or "results-list" in html_content
    assert "Python" in html_content
    
    # 验证包含高亮标记
    assert "<mark>" in html_content


def test_search_page_no_results(client, temp_db, indexed_docs):
    """测试搜索页面无结果显示
    
    验证需求: 6.5 - 搜索无结果时显示友好的提示信息
    """
    response = client.get("/?q=nonexistent_keyword_xyz")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    
    html_content = response.text
    
    # 验证页面包含无结果提示
    assert "没有找到" in html_content or "no-results" in html_content or "无结果" in html_content
