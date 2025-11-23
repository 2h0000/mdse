"""搜索服务功能测试

测试全文搜索和文档检索功能。
验证需求: 1.1, 1.2, 1.3, 1.5, 4.1
"""

import tempfile
from pathlib import Path
import pytest

from app.search_service import search_documents, get_document_by_id, render_document_html
from app.indexer import index_file
from app.db import get_connection, init_db, close_connection
from app.config import settings


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
    # 创建测试文档
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


def test_search_basic(temp_db, indexed_docs):
    """测试基本搜索功能
    
    验证需求: 1.1 - 在 SQLite FTS5 索引中执行全文搜索
    """
    results, total = search_documents("Python")
    
    assert total == 2  # doc1 和 doc3 包含 Python
    assert len(results) == 2
    
    titles = {r.title for r in results}
    assert "Python Tutorial" in titles
    assert "Python Advanced" in titles


def test_search_with_snippet(temp_db, indexed_docs):
    """测试搜索结果包含高亮片段
    
    验证需求: 1.3 - 提供包含匹配关键词的高亮片段
    """
    results, total = search_documents("programming")
    
    assert total >= 1
    assert len(results) >= 1
    
    # 验证 snippet 包含高亮标记
    for result in results:
        assert "<mark>" in result.snippet
        assert "</mark>" in result.snippet


def test_search_bm25_ranking(temp_db, indexed_docs):
    """测试 BM25 排序
    
    验证需求: 1.2 - 按相关性排序结果并使用 BM25 算法
    """
    results, total = search_documents("Python")
    
    # 验证结果按 rank 排序（rank 值越小越相关）
    if len(results) > 1:
        for i in range(len(results) - 1):
            assert results[i].rank <= results[i + 1].rank


def test_search_pagination(temp_db, indexed_docs):
    """测试分页功能
    
    验证需求: 1.5 - 返回指定范围的结果子集
    """
    # 搜索所有文档
    all_results, total = search_documents("language", limit=10, offset=0)
    
    # 测试 limit
    limited_results, _ = search_documents("language", limit=1, offset=0)
    assert len(limited_results) <= 1
    
    # 测试 offset
    if total > 1:
        offset_results, _ = search_documents("language", limit=10, offset=1)
        assert len(offset_results) == total - 1


def test_search_no_results(temp_db, indexed_docs):
    """测试无结果的搜索"""
    results, total = search_documents("nonexistent_keyword_xyz")
    
    assert total == 0
    assert len(results) == 0


def test_get_document_by_id(temp_db, indexed_docs):
    """测试根据 ID 获取文档
    
    验证需求: 4.1 - 根据文档 ID 返回完整的文档内容
    """
    # 先搜索获取一个文档 ID
    results, _ = search_documents("Python")
    assert len(results) > 0
    
    doc_id = results[0].id
    
    # 根据 ID 获取文档
    document = get_document_by_id(doc_id)
    
    assert document is not None
    assert document.id == doc_id
    assert document.title is not None
    assert document.path is not None


def test_get_document_not_found(temp_db, indexed_docs):
    """测试获取不存在的文档"""
    document = get_document_by_id(99999)
    
    assert document is None


def test_search_default_limit(temp_db, indexed_docs):
    """测试默认 limit 配置"""
    results, total = search_documents("language")
    
    # 结果数量不应超过默认 limit
    assert len(results) <= settings.default_limit


def test_search_max_limit(temp_db, indexed_docs):
    """测试最大 limit 限制"""
    # 尝试使用超过最大限制的 limit
    results, total = search_documents("language", limit=1000)
    
    # 结果数量不应超过最大 limit
    assert len(results) <= settings.max_search_limit


def test_render_document_html(temp_db, indexed_docs):
    """测试将 Markdown 渲染为 HTML
    
    验证需求: 4.2 - 将 Markdown 转换为 HTML 格式
    """
    # 先搜索获取一个文档 ID
    results, _ = search_documents("Python")
    assert len(results) > 0
    
    doc_id = results[0].id
    
    # 渲染文档为 HTML
    html = render_document_html(doc_id)
    
    assert html is not None
    assert isinstance(html, str)
    assert len(html) > 0


def test_render_document_with_code_blocks(temp_db, temp_md_root):
    """测试渲染包含代码块的文档
    
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
    
    # 索引文档
    conn = get_connection()
    from app.indexer import index_file
    index_file(conn, file_path)
    
    # 获取文档 ID
    results, _ = search_documents("Code", conn=conn)
    assert len(results) > 0
    doc_id = results[0].id
    
    # 渲染为 HTML
    html = render_document_html(doc_id, conn)
    close_connection(conn)
    
    assert html is not None
    # 验证包含代码相关的 HTML 标签
    assert "<code>" in html or "<pre>" in html


def test_render_document_with_tables(temp_db, temp_md_root):
    """测试渲染包含表格的文档
    
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
    
    # 索引文档
    conn = get_connection()
    from app.indexer import index_file
    index_file(conn, file_path)
    
    # 获取文档 ID
    results, _ = search_documents("Table", conn=conn)
    assert len(results) > 0
    doc_id = results[0].id
    
    # 渲染为 HTML
    html = render_document_html(doc_id, conn)
    close_connection(conn)
    
    assert html is not None
    # 验证包含表格 HTML 标签
    assert "<table>" in html
    assert "<tr>" in html
    assert "<td>" in html or "<th>" in html


def test_render_document_not_found(temp_db, indexed_docs):
    """测试渲染不存在的文档
    
    验证需求: 4.3 - 请求的文档 ID 不存在时返回 None
    """
    html = render_document_html(99999)
    
    assert html is None


def test_render_document_file_missing(temp_db, temp_md_root):
    """测试渲染文件已删除的文档
    
    验证需求: 4.4 - 文档文件在磁盘上不存在时返回 None
    """
    # 创建并索引文档
    content = "---\ntitle: Temp Doc\n---\n\nTemporary content."
    file_path = temp_md_root / "temp_doc.md"
    file_path.write_text(content)
    
    conn = get_connection()
    from app.indexer import index_file
    index_file(conn, file_path)
    
    # 获取文档 ID
    results, _ = search_documents("Temp", conn=conn)
    assert len(results) > 0
    doc_id = results[0].id
    
    # 删除文件
    file_path.unlink()
    
    # 尝试渲染
    html = render_document_html(doc_id, conn)
    close_connection(conn)
    
    assert html is None
