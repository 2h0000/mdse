"""属性测试：索引器功能

使用 Hypothesis 进行基于属性的测试。
每个测试运行至少 100 次迭代以验证属性在各种输入下都成立。
"""

import tempfile
from pathlib import Path
import yaml
from hypothesis import given, strategies as st, settings

from app.indexer import extract_text_from_md


# Feature: md-search-engine, Property 5: Frontmatter 标题提取
# Validates: Requirements 2.1
@settings(max_examples=100)
@given(
    title=st.text(
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # 排除代理字符和控制字符
            blacklist_characters=('\n', '\r', '\0')  # 排除换行和空字符
        ),
        min_size=1,
        max_size=200
    )
)
def test_property_frontmatter_title_extraction(title):
    """属性测试：Frontmatter 标题提取
    
    属性：对于任意包含 frontmatter 的 Markdown 文件，
    如果 frontmatter 中存在 title 字段，
    索引后的文档标题应等于该字段值。
    
    验证需求: 2.1 - 解析 frontmatter 并提取标题
    """
    # 为每个测试用例创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        
        # 创建带有 frontmatter 的 Markdown 文件
        # 使用 YAML 库来正确序列化标题，避免 YAML 特殊字符问题
        frontmatter_dict = {'title': title}
        frontmatter_yaml = yaml.dump(frontmatter_dict, allow_unicode=True, default_flow_style=False)
        
        content = f"""---
{frontmatter_yaml}---

This is some test content.
"""
        
        test_file = temp_md_root / "test.md"
        test_file.write_text(content, encoding='utf-8')
        
        # 提取文本
        title_original, title_segmented, summary, content_original, content_segmented = extract_text_from_md(test_file)
        
        # 验证属性：提取的标题应该等于 frontmatter 中的 title 字段
        assert title_original == title, f"Expected title '{title}', but got '{title_original}'"


# Feature: md-search-engine, Property 6: 文档摘要长度限制
# Validates: Requirements 2.5
@settings(max_examples=100)
@given(
    content=st.text(
        alphabet=st.characters(
            blacklist_categories=('Cs',),  # 排除代理字符
        ),
        min_size=0,
        max_size=5000  # 测试各种长度的内容，包括超过 200 字符的
    )
)
def test_property_summary_length_limit(content):
    """属性测试：文档摘要长度限制
    
    属性：对于任意 Markdown 文档，
    生成的摘要长度应不超过 200 个字符。
    
    验证需求: 2.5 - 生成文档摘要（前 200 字符）
    """
    # 为每个测试用例创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        
        # 创建 Markdown 文件
        test_file = temp_md_root / "test.md"
        test_file.write_text(content, encoding='utf-8')
        
        # 提取文本
        title_original, title_segmented, summary, content_original, content_segmented = extract_text_from_md(test_file)
        
        # 验证属性：摘要长度应不超过 200 个字符
        assert len(summary) <= 200, f"Summary length {len(summary)} exceeds 200 characters"


# Feature: md-search-engine, Property 10: 索引幂等性
# Validates: Requirements 5.5
@settings(max_examples=100)
@given(
    title=st.text(
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),
            blacklist_characters=('\n', '\r', '\0')
        ),
        min_size=1,
        max_size=100
    ),
    content=st.text(
        alphabet=st.characters(
            blacklist_categories=('Cs',),
        ),
        min_size=0,
        max_size=1000
    ),
    index_count=st.integers(min_value=2, max_value=5)  # 索引 2-5 次
)
def test_property_indexing_idempotency(title, content, index_count):
    """属性测试：索引幂等性
    
    属性：对于任意 Markdown 文件，
    多次索引同一文件应只在数据库中产生一条记录。
    
    验证需求: 5.5 - 使用 UPSERT 操作避免重复记录
    """
    import sqlite3
    import yaml
    from unittest.mock import patch
    from app.db import init_db
    from app.indexer import index_file
    from app import config
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # Mock settings to use temporary directory
        with patch.object(config.settings, 'md_root', temp_md_root):
            # 创建数据库连接并初始化
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            
            try:
                # 创建带有 frontmatter 的 Markdown 文件
                frontmatter_dict = {'title': title}
                frontmatter_yaml = yaml.dump(frontmatter_dict, allow_unicode=True, default_flow_style=False)
                
                file_content = f"""---
{frontmatter_yaml}---

{content}
"""
                
                test_file = temp_md_root / "test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 多次索引同一文件
                for _ in range(index_count):
                    index_file(conn, test_file)
                
                # 验证属性：docs 表中应该只有一条记录
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                docs_count = cursor.fetchone()['count']
                
                assert docs_count == 1, f"Expected 1 record in docs table after {index_count} indexing operations, but got {docs_count}"
                
                # 验证属性：docs_fts 表中应该只有一条记录
                cursor.execute("SELECT COUNT(*) as count FROM docs_fts")
                fts_count = cursor.fetchone()['count']
                
                assert fts_count == 1, f"Expected 1 record in docs_fts table after {index_count} indexing operations, but got {fts_count}"
                
                # 验证记录的内容是正确的
                cursor.execute("SELECT title, path FROM docs")
                doc = cursor.fetchone()
                assert doc['title'] == title, f"Expected title '{title}', but got '{doc['title']}'"
                
            finally:
                conn.close()


# 辅助函数：生成有效的文件名
def _valid_filename_strategy():
    """生成有效的文件名（避免 Windows 保留字符）"""
    return st.text(
        alphabet=st.characters(
            min_codepoint=ord('a'),
            max_codepoint=ord('z')
        ) | st.characters(
            min_codepoint=ord('A'),
            max_codepoint=ord('Z')
        ) | st.characters(
            min_codepoint=ord('0'),
            max_codepoint=ord('9')
        ) | st.sampled_from(['_', '-', '.']),
        min_size=1,
        max_size=50
    ).filter(lambda s: s and s.strip() and not s.startswith('.') and not s.endswith('.'))


# Feature: md-search-engine, Property 11: 全量重建清空旧数据
# Validates: Requirements 5.4
@settings(max_examples=100, deadline=None)
@given(
    # 生成初始文件集合（1-5个文件）
    initial_files=st.lists(
        st.tuples(
            _valid_filename_strategy(),
            st.text(
                alphabet=st.characters(blacklist_categories=('Cs',)),
                min_size=0,
                max_size=500
            )
        ),
        min_size=1,
        max_size=5,
        unique_by=lambda x: x[0].lower()  # 确保文件名唯一（不区分大小写，适配 Windows）
    ),
    # 生成重建后的文件集合（1-5个文件）
    rebuild_files=st.lists(
        st.tuples(
            _valid_filename_strategy(),
            st.text(
                alphabet=st.characters(blacklist_categories=('Cs',)),
                min_size=0,
                max_size=500
            )
        ),
        min_size=1,
        max_size=5,
        unique_by=lambda x: x[0].lower()  # 确保文件名唯一（不区分大小写，适配 Windows）
    )
)
def test_property_full_rebuild_clears_old_data(initial_files, rebuild_files):
    """属性测试：全量重建清空旧数据
    
    属性：对于任意初始索引状态，
    执行全量重建后，索引应只包含当前文件系统中存在的文件。
    
    验证需求: 5.4 - 清空现有索引并重新构建
    """
    import sqlite3
    from unittest.mock import patch
    from app.db import init_db
    from app.indexer import index_file, full_reindex
    from app import config
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # Mock settings to use temporary directory
        with patch.object(config.settings, 'md_root', temp_md_root):
            # 创建数据库连接并初始化
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            
            try:
                # 第一阶段：创建初始文件并索引
                initial_file_paths = []
                for filename, content in initial_files:
                    test_file = temp_md_root / f"{filename}.md"
                    test_file.write_text(content, encoding='utf-8')
                    initial_file_paths.append(test_file)
                    index_file(conn, test_file)
                
                # 验证初始索引已创建
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                initial_count = cursor.fetchone()['count']
                assert initial_count == len(initial_files), f"Expected {len(initial_files)} initial records, got {initial_count}"
                
                # 第二阶段：删除所有初始文件，创建新的文件集合
                for file_path in initial_file_paths:
                    if file_path.exists():
                        file_path.unlink()
                
                rebuild_file_paths = []
                for filename, content in rebuild_files:
                    test_file = temp_md_root / f"{filename}.md"
                    test_file.write_text(content, encoding='utf-8')
                    rebuild_file_paths.append(test_file)
                
                # 第三阶段：执行全量重建
                full_reindex(conn)
                
                # 验证属性：索引应只包含重建后的文件
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                final_count = cursor.fetchone()['count']
                
                assert final_count == len(rebuild_files), \
                    f"After full rebuild, expected {len(rebuild_files)} records, but got {final_count}"
                
                # 验证 FTS 表也同步更新
                cursor.execute("SELECT COUNT(*) as count FROM docs_fts")
                fts_count = cursor.fetchone()['count']
                
                assert fts_count == len(rebuild_files), \
                    f"After full rebuild, expected {len(rebuild_files)} FTS records, but got {fts_count}"
                
                # 验证索引中的文件路径确实是重建后的文件
                cursor.execute("SELECT path FROM docs ORDER BY path")
                indexed_paths = {row['path'] for row in cursor.fetchall()}
                
                expected_paths = {f"{filename}.md" for filename, _ in rebuild_files}
                
                assert indexed_paths == expected_paths, \
                    f"Indexed paths {indexed_paths} do not match expected paths {expected_paths}"
                
                # 验证旧文件不在索引中
                old_paths = {f"{filename}.md" for filename, _ in initial_files}
                overlap = indexed_paths & old_paths
                
                # 只有在没有重叠的情况下才验证（因为可能随机生成了相同的文件名）
                if not overlap:
                    assert len(indexed_paths & old_paths) == 0, \
                        f"Old files should not be in index after rebuild, but found: {indexed_paths & old_paths}"
                
            finally:
                conn.close()
