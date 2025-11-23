"""索引器功能测试

测试 Markdown 文件解析和索引功能。
验证需求: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import tempfile
from pathlib import Path
import pytest

from app.indexer import (
    iter_md_files,
    extract_text_from_md,
    index_file,
    full_reindex,
    remove_file_from_index
)
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


def test_iter_md_files(temp_md_root):
    """测试 Markdown 文件遍历功能"""
    # 创建测试文件
    (temp_md_root / "test1.md").write_text("# Test 1")
    (temp_md_root / "test2.md").write_text("# Test 2")
    (temp_md_root / "test.txt").write_text("Not markdown")
    
    # 创建子目录
    subdir = temp_md_root / "subdir"
    subdir.mkdir()
    (subdir / "test3.md").write_text("# Test 3")
    
    # 遍历文件
    md_files = list(iter_md_files(temp_md_root))
    md_names = {f.name for f in md_files}
    
    assert len(md_files) == 3
    assert "test1.md" in md_names
    assert "test2.md" in md_names
    assert "test3.md" in md_names
    assert "test.txt" not in md_names


def test_extract_text_with_frontmatter(temp_md_root):
    """测试带 frontmatter 的文档解析
    
    验证需求: 2.1 - 解析 frontmatter 并提取标题
    """
    content = """---
title: Test Document
author: Test Author
---

This is the content of the document.
It has multiple lines.
"""
    test_file = temp_md_root / "test.md"
    test_file.write_text(content)
    
    title_original, title_segmented, summary, content_original, content_segmented = extract_text_from_md(test_file)
    
    assert title_original == "Test Document"
    assert "This is the content" in content_original
    assert len(summary) <= 200


def test_extract_text_without_frontmatter(temp_md_root):
    """测试不带 frontmatter 的文档解析
    
    验证需求: 2.2 - 使用文件名作为默认标题
    """
    content = "# Heading\n\nThis is content without frontmatter."
    test_file = temp_md_root / "my_document.md"
    test_file.write_text(content)
    
    title_original, title_segmented, summary, content_original, content_segmented = extract_text_from_md(test_file)
    
    assert title_original == "my_document"  # 文件名（不含扩展名）
    assert "This is content" in content_original


def test_extract_text_summary_length(temp_md_root):
    """测试摘要长度限制
    
    验证需求: 2.5 - 生成文档摘要（前 200 字符）
    """
    # 创建超过 200 字符的内容
    content = "A" * 300
    test_file = temp_md_root / "long.md"
    test_file.write_text(content)
    
    title_original, title_segmented, summary, content_original, content_segmented = extract_text_from_md(test_file)
    
    assert len(summary) == 200
    assert summary == "A" * 200


def test_index_file(temp_db, temp_md_root):
    """测试单文件索引功能
    
    验证需求: 2.4 - 存储文件路径、标题、摘要和修改时间
    """
    content = """---
title: Index Test
---

Content for indexing test.
"""
    test_file = temp_md_root / "index_test.md"
    test_file.write_text(content)
    
    conn = get_connection()
    index_file(conn, test_file)
    
    # 验证 docs 表
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM docs WHERE path = ?", ("index_test.md",))
    row = cursor.fetchone()
    
    assert row is not None
    assert row['title'] == "Index Test"
    assert row['summary'] == "Content for indexing test."
    assert row['mtime'] > 0
    
    # 验证 docs_fts 表
    cursor.execute("SELECT * FROM docs_fts WHERE doc_id = ?", (row['id'],))
    fts_row = cursor.fetchone()
    
    assert fts_row is not None
    assert fts_row['title'] == "Index Test"
    assert "Content for indexing" in fts_row['content']
    
    close_connection(conn)


def test_index_file_upsert(temp_db, temp_md_root):
    """测试索引 UPSERT 功能
    
    验证需求: 5.5 - 使用 UPSERT 操作避免重复记录
    """
    test_file = temp_md_root / "upsert_test.md"
    test_file.write_text("Original content")
    
    conn = get_connection()
    
    # 第一次索引
    index_file(conn, test_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM docs")
    count1 = cursor.fetchone()['count']
    
    # 修改文件并再次索引
    test_file.write_text("Updated content")
    index_file(conn, test_file)
    
    cursor.execute("SELECT COUNT(*) as count FROM docs")
    count2 = cursor.fetchone()['count']
    
    # 应该只有一条记录
    assert count1 == 1
    assert count2 == 1
    
    # 验证内容已更新
    cursor.execute("SELECT * FROM docs_fts WHERE path = ?", ("upsert_test.md",))
    row = cursor.fetchone()
    assert "Updated content" in row['content']
    
    close_connection(conn)


def test_full_reindex(temp_db, temp_md_root):
    """测试全量重建索引
    
    验证需求: 5.3, 5.4 - 扫描所有文件并清空旧索引
    """
    # 创建多个文件
    (temp_md_root / "file1.md").write_text("Content 1")
    (temp_md_root / "file2.md").write_text("Content 2")
    
    conn = get_connection()
    
    # 先索引一个不存在的文件（模拟旧数据）
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO docs (path, title, summary, mtime)
        VALUES ('old_file.md', 'Old', 'Old content', 0)
    """)
    conn.commit()
    
    # 执行全量重建
    full_reindex(conn)
    
    # 验证只有当前存在的文件被索引
    cursor.execute("SELECT COUNT(*) as count FROM docs")
    count = cursor.fetchone()['count']
    assert count == 2
    
    cursor.execute("SELECT path FROM docs ORDER BY path")
    paths = [row['path'] for row in cursor.fetchall()]
    assert "file1.md" in paths
    assert "file2.md" in paths
    assert "old_file.md" not in paths
    
    close_connection(conn)


def test_remove_file_from_index(temp_db, temp_md_root):
    """测试从索引中删除文件
    
    验证需求: 3.3 - 自动从索引中移除删除的文件
    """
    test_file = temp_md_root / "to_remove.md"
    test_file.write_text("Content to remove")
    
    conn = get_connection()
    
    # 先索引文件
    index_file(conn, test_file)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM docs")
    count_before = cursor.fetchone()['count']
    assert count_before == 1
    
    # 删除文件
    remove_file_from_index(conn, test_file)
    
    cursor.execute("SELECT COUNT(*) as count FROM docs")
    count_after = cursor.fetchone()['count']
    assert count_after == 0
    
    # 验证 FTS 表也被清理
    cursor.execute("SELECT COUNT(*) as count FROM docs_fts")
    fts_count = cursor.fetchone()['count']
    assert fts_count == 0
    
    close_connection(conn)
