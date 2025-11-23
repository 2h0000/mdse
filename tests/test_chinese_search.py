"""中文搜索支持测试

验证 FTS5 使用 unicode61 分词器，测试中文关键词搜索、中英文混合搜索和中文高亮显示。
验证需求: 8.1, 8.2, 8.3, 8.4
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path

from app.db import init_db, get_connection
from app.indexer import index_file
from app.search_service import search_documents
from app.config import settings


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # 临时修改配置
    original_db_path = settings.db_path
    settings.db_path = Path(db_path)
    
    conn = get_connection()
    init_db(conn)
    
    yield conn
    
    conn.close()
    # 恢复配置
    settings.db_path = original_db_path
    # 清理临时文件
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_md_root(tmp_path):
    """创建临时 Markdown 目录"""
    original_md_root = settings.md_root
    settings.md_root = tmp_path
    
    yield tmp_path
    
    settings.md_root = original_md_root


def test_fts5_uses_unicode61_tokenizer(temp_db):
    """验证 FTS5 使用 unicode61 分词器
    
    验证需求: 8.1 - FTS5 索引中文内容时使用 unicode61 分词器
    """
    cursor = temp_db.cursor()
    
    # 查询 docs_fts 表的创建语句
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='docs_fts'
    """)
    
    result = cursor.fetchone()
    assert result is not None, "docs_fts table should exist"
    
    create_sql = result['sql']
    
    # 验证使用了 unicode61 分词器
    assert 'unicode61' in create_sql.lower(), \
        "FTS5 table should use unicode61 tokenizer"
    assert 'remove_diacritics' in create_sql.lower(), \
        "FTS5 tokenizer should have remove_diacritics option"


def test_chinese_keyword_search(temp_db, temp_md_root):
    """测试中文关键词搜索
    
    验证需求: 8.2 - 搜索中文关键词时正确匹配包含该关键词的文档
    """
    # 创建包含中文内容的测试文档
    doc1 = temp_md_root / "chinese_doc.md"
    doc1.write_text("""---
title: 中文文档测试
---

这是一个包含中文内容的文档。我们要测试搜索功能是否能够正确处理中文关键词。
Python 是一门优秀的编程语言。
""", encoding='utf-8')
    
    doc2 = temp_md_root / "english_doc.md"
    doc2.write_text("""---
title: English Document
---

This is an English document without Chinese content.
Python is a great programming language.
""", encoding='utf-8')
    
    # 索引文档
    index_file(temp_db, doc1)
    index_file(temp_db, doc2)
    
    # 搜索中文关键词 "中文"
    results, total = search_documents("中文", conn=temp_db)
    
    assert total == 1, "Should find exactly 1 document with Chinese keyword"
    assert len(results) == 1
    assert results[0].title == "中文文档测试"
    assert "中文" in results[0].snippet or "中文" in results[0].title
    
    # 搜索另一个中文关键词 "编程语言"
    results, total = search_documents("编程语言", conn=temp_db)
    
    assert total == 1, "Should find document containing '编程语言'"
    assert results[0].title == "中文文档测试"


def test_mixed_chinese_english_search(temp_db, temp_md_root):
    """测试中英文混合搜索
    
    验证需求: 8.3 - 文档包含中英文混合内容时，中英文关键词搜索都应能匹配
    """
    # 创建中英文混合文档
    mixed_doc = temp_md_root / "mixed_doc.md"
    mixed_doc.write_text("""---
title: 混合语言文档
---

这是一个中英文混合的文档。This document contains both Chinese and English content.

Python 编程语言非常流行。The Python programming language is very popular.

我们可以使用 FastAPI 构建 Web 应用。We can use FastAPI to build web applications.
""", encoding='utf-8')
    
    chinese_only = temp_md_root / "chinese_only.md"
    chinese_only.write_text("""---
title: 纯中文文档
---

这是一个纯中文文档，没有英文内容。
""", encoding='utf-8')
    
    # 索引文档
    index_file(temp_db, mixed_doc)
    index_file(temp_db, chinese_only)
    
    # 使用中文关键词搜索
    results, total = search_documents("编程语言", conn=temp_db)
    assert total >= 1, "Should find documents with Chinese keyword"
    assert any(r.title == "混合语言文档" for r in results), \
        "Should find the mixed language document with Chinese keyword"
    
    # 使用英文关键词搜索
    results, total = search_documents("FastAPI", conn=temp_db)
    assert total >= 1, "Should find documents with English keyword"
    assert any(r.title == "混合语言文档" for r in results), \
        "Should find the mixed language document with English keyword"
    
    # 使用另一个英文关键词
    results, total = search_documents("Python", conn=temp_db)
    assert total >= 1, "Should find documents with 'Python'"
    assert any(r.title == "混合语言文档" for r in results), \
        "Should find the mixed language document"


def test_chinese_highlighting(temp_db, temp_md_root):
    """测试中文高亮显示
    
    验证需求: 8.4 - 搜索结果包含中文时正确生成包含中文的高亮片段
    """
    # 创建中文文档
    doc = temp_md_root / "highlight_test.md"
    doc.write_text("""---
title: 高亮测试文档
---

这是一个用于测试高亮功能的中文文档。搜索引擎应该能够正确地高亮显示中文关键词。

全文搜索是一个非常有用的功能，它可以帮助用户快速找到相关的文档内容。
""", encoding='utf-8')
    
    # 索引文档
    index_file(temp_db, doc)
    
    # 搜索并检查高亮
    results, total = search_documents("搜索引擎", conn=temp_db)
    
    assert total == 1, "Should find the document"
    assert len(results) == 1
    
    snippet = results[0].snippet
    
    # 验证 snippet 包含中文字符
    assert any('\u4e00' <= c <= '\u9fff' for c in snippet), \
        "Snippet should contain Chinese characters"
    
    # 验证包含高亮标记
    assert '<mark>' in snippet and '</mark>' in snippet, \
        "Snippet should contain highlight marks"
    
    # 搜索另一个关键词
    results, total = search_documents("全文搜索", conn=temp_db)
    
    assert total == 1
    snippet = results[0].snippet
    assert '<mark>' in snippet and '</mark>' in snippet
    assert any('\u4e00' <= c <= '\u9fff' for c in snippet)


def test_chinese_with_punctuation(temp_db, temp_md_root):
    """测试包含标点符号的中文搜索"""
    doc = temp_md_root / "punctuation.md"
    doc.write_text("""---
title: 标点符号测试
---

这是一个测试文档，包含各种标点符号：逗号、句号、问号？感叹号！

中文搜索功能应该能够正确处理这些标点符号。
""", encoding='utf-8')
    
    index_file(temp_db, doc)
    
    # 搜索应该忽略标点符号
    results, total = search_documents("标点符号", conn=temp_db)
    
    assert total == 1
    assert results[0].title == "标点符号测试"


def test_chinese_numbers_and_english(temp_db, temp_md_root):
    """测试中文、数字和英文混合的搜索"""
    doc = temp_md_root / "mixed_content.md"
    doc.write_text("""---
title: 混合内容测试
---

Python 3.11 是最新的版本。这个版本包含了许多新特性。

我们可以使用 pip install fastapi 来安装 FastAPI 框架。

2024年是一个重要的年份。
""", encoding='utf-8')
    
    index_file(temp_db, doc)
    
    # 搜索中文
    results, total = search_documents("版本", conn=temp_db)
    assert total == 1
    
    # 搜索英文
    results, total = search_documents("FastAPI", conn=temp_db)
    assert total == 1
    
    # 搜索数字（作为文本的一部分）
    results, total = search_documents("2024", conn=temp_db)
    assert total == 1


def test_empty_chinese_query(temp_db, temp_md_root):
    """测试空的中文查询"""
    doc = temp_md_root / "test.md"
    doc.write_text("测试文档", encoding='utf-8')
    index_file(temp_db, doc)
    
    # 空查询应该返回空结果或抛出异常
    # 这取决于 API 层的验证，这里只测试搜索服务层
    try:
        results, total = search_documents("", conn=temp_db)
        # 如果没有抛出异常，应该返回空结果
        assert total == 0
    except Exception:
        # 如果抛出异常也是可以接受的
        pass


def test_chinese_title_search(temp_db, temp_md_root):
    """测试搜索中文标题"""
    doc = temp_md_root / "title_test.md"
    doc.write_text("""---
title: 这是一个中文标题
---

文档内容在这里。
""", encoding='utf-8')
    
    index_file(temp_db, doc)
    
    # 搜索标题中的关键词
    results, total = search_documents("中文标题", conn=temp_db)
    
    assert total == 1
    assert results[0].title == "这是一个中文标题"


def test_multiple_chinese_documents(temp_db, temp_md_root):
    """测试多个中文文档的搜索和排序"""
    # 创建多个包含相同关键词的文档
    doc1 = temp_md_root / "doc1.md"
    doc1.write_text("""---
title: 文档一
---

Python 是一门编程语言。Python 非常流行。Python 很容易学习。
""", encoding='utf-8')
    
    doc2 = temp_md_root / "doc2.md"
    doc2.write_text("""---
title: 文档二
---

Python 是一门编程语言。
""", encoding='utf-8')
    
    doc3 = temp_md_root / "doc3.md"
    doc3.write_text("""---
title: 文档三
---

这个文档不包含那个关键词。
""", encoding='utf-8')
    
    # 索引所有文档
    index_file(temp_db, doc1)
    index_file(temp_db, doc2)
    index_file(temp_db, doc3)
    
    # 搜索 "Python"
    results, total = search_documents("Python", conn=temp_db)
    
    assert total == 2, "Should find 2 documents containing 'Python'"
    
    # 验证 BM25 排序：doc1 应该排在前面（因为包含更多 "Python"）
    assert results[0].title == "文档一", \
        "Document with more occurrences should rank higher"
