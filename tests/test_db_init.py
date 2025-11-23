"""数据库初始化示例测试

测试 docs 表和 docs_fts 虚拟表的创建。
验证需求: 5.1, 5.2
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from app.db import get_connection, init_db, close_connection
from app.config import settings


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 保存原始配置
        original_db_path = settings.db_path
        
        # 设置临时数据库路径
        settings.db_path = Path(tmpdir) / "test.db"
        
        yield settings.db_path
        
        # 恢复原始配置
        settings.db_path = original_db_path


def test_docs_table_creation(temp_db):
    """测试 docs 表创建
    
    验证需求: 5.1 - 系统应创建 docs 表用于存储文档元数据
    """
    conn = get_connection()
    init_db(conn)
    
    # 验证 docs 表存在
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='docs'
    """)
    result = cursor.fetchone()
    
    assert result is not None, "docs 表未创建"
    assert result['name'] == 'docs'
    
    # 验证表结构
    cursor.execute("PRAGMA table_info(docs)")
    columns = {row['name']: row['type'] for row in cursor.fetchall()}
    
    expected_columns = {
        'id': 'INTEGER',
        'path': 'TEXT',
        'title': 'TEXT',
        'summary': 'TEXT',
        'mtime': 'REAL'
    }
    
    for col_name, col_type in expected_columns.items():
        assert col_name in columns, f"列 {col_name} 不存在"
        assert columns[col_name] == col_type, f"列 {col_name} 类型错误"
    
    close_connection(conn)


def test_docs_fts_table_creation(temp_db):
    """测试 docs_fts 虚拟表创建
    
    验证需求: 5.2 - 系统应创建 docs_fts 虚拟表用于全文搜索
    """
    conn = get_connection()
    init_db(conn)
    
    # 验证 docs_fts 虚拟表存在
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='docs_fts'
    """)
    result = cursor.fetchone()
    
    assert result is not None, "docs_fts 虚拟表未创建"
    assert result['name'] == 'docs_fts'
    
    close_connection(conn)
