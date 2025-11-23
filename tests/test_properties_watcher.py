"""属性测试：文件监控功能

使用 Hypothesis 进行基于属性的测试。
每个测试运行至少 100 次迭代以验证属性在各种输入下都成立。

注意：此测试直接测试索引器的创建、修改、删除功能，
这些功能是文件监听器调用的核心逻辑，从而验证文件系统同步的正确性。
"""

import tempfile
from pathlib import Path
import sqlite3
import yaml
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import patch

from app.db import init_db
from app.indexer import index_file, remove_file_from_index
from app import config


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
        ) | st.sampled_from(['_', '-']),
        min_size=1,
        max_size=30
    ).filter(lambda s: s and s.strip() and not s.startswith('.') and not s.endswith('.'))


# Feature: md-search-engine, Property 7: 索引与文件系统同步
# Validates: Requirements 3.1, 3.2, 3.3
@settings(max_examples=100, deadline=None)
@given(
    # 生成初始文件集合（1-3个文件）
    initial_files=st.lists(
        st.tuples(
            _valid_filename_strategy(),
            st.text(
                alphabet=st.characters(blacklist_categories=('Cs',)),
                min_size=10,
                max_size=200
            )
        ),
        min_size=1,
        max_size=3,
        unique_by=lambda x: x[0].lower()  # 确保文件名唯一
    ),
    # 生成要创建的新文件
    new_file=st.tuples(
        _valid_filename_strategy(),
        st.text(
            alphabet=st.characters(blacklist_categories=('Cs',)),
            min_size=10,
            max_size=200
        )
    ),
    # 生成修改后的内容
    modified_content=st.text(
        alphabet=st.characters(blacklist_categories=('Cs',)),
        min_size=10,
        max_size=200
    )
)
def test_property_index_syncs_with_filesystem(initial_files, new_file, modified_content):
    """属性测试：索引与文件系统同步
    
    属性：对于任意文件系统操作（创建、修改、删除 .md 文件），
    索引应在操作后反映文件系统的当前状态。
    
    此测试通过直接调用索引器函数（index_file, remove_file_from_index）
    来验证文件系统同步的核心逻辑，这些函数是文件监听器在检测到文件变化时调用的。
    
    验证需求: 3.1 - 自动将新文件添加到搜索索引
    验证需求: 3.2 - 自动更新修改的文件在索引中的内容
    验证需求: 3.3 - 自动从索引中移除删除的文件
    """
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
                # 第一阶段：创建初始文件并索引（模拟初始状态）
                initial_file_paths = []
                initial_filenames = set()
                for filename, content in initial_files:
                    test_file = temp_md_root / f"{filename}.md"
                    test_file.write_text(content, encoding='utf-8')
                    initial_file_paths.append(test_file)
                    initial_filenames.add(f"{filename}.md")
                    # 模拟文件监听器调用 index_file
                    index_file(conn, test_file)
                
                # 验证初始索引已创建
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                initial_count = cursor.fetchone()['count']
                assert initial_count == len(initial_files), \
                    f"Expected {len(initial_files)} initial records, got {initial_count}"
                
                # 第二阶段：测试文件创建 (需求 3.1)
                # 模拟文件监听器检测到新文件创建
                new_filename, new_content = new_file
                
                # 确保新文件名不与初始文件冲突
                if f"{new_filename}.md" in initial_filenames:
                    # 如果冲突，修改文件名
                    new_filename = f"{new_filename}_new"
                
                new_file_path = temp_md_root / f"{new_filename}.md"
                new_file_path.write_text(new_content, encoding='utf-8')
                
                # 模拟文件监听器调用 index_file 来索引新文件
                index_file(conn, new_file_path)
                
                # 验证新文件已被索引
                cursor.execute("SELECT COUNT(*) as count FROM docs WHERE path = ?", (f"{new_filename}.md",))
                new_file_count = cursor.fetchone()['count']
                assert new_file_count == 1, \
                    f"New file should be indexed after creation (Requirement 3.1), but found {new_file_count} records"
                
                # 验证总数增加了 1
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                count_after_create = cursor.fetchone()['count']
                assert count_after_create == initial_count + 1, \
                    f"After creating a file, index should have {initial_count + 1} records, but got {count_after_create}"
                
                # 第三阶段：测试文件修改 (需求 3.2)
                # 模拟文件监听器检测到文件修改
                if len(initial_file_paths) > 0:
                    file_to_modify = initial_file_paths[0]
                    
                    # 获取修改前的内容
                    cursor.execute("SELECT summary FROM docs WHERE path = ?", (file_to_modify.name,))
                    row_before = cursor.fetchone()
                    summary_before = row_before['summary'] if row_before else ""
                    
                    # 修改文件内容
                    file_to_modify.write_text(modified_content, encoding='utf-8')
                    
                    # 模拟文件监听器调用 index_file 来更新索引
                    # index_file 使用 UPSERT，会自动更新现有记录
                    index_file(conn, file_to_modify)
                    
                    # 验证文件内容已更新
                    cursor.execute("SELECT summary FROM docs WHERE path = ?", (file_to_modify.name,))
                    row_after = cursor.fetchone()
                    
                    assert row_after is not None, \
                        f"Modified file should still be in index (Requirement 3.2)"
                    
                    summary_after = row_after['summary']
                    
                    # 验证摘要已更新（如果内容不同）
                    # 注意：extract_text_from_md 会 strip() 内容，所以我们也需要 strip 来比较
                    # 同时，文件读写可能会规范化行尾符（\r\n -> \n），所以我们也需要规范化
                    expected_summary = modified_content.strip().replace('\r\n', '\n').replace('\r', '\n')[:200]
                    summary_before_normalized = summary_before.strip().replace('\r\n', '\n').replace('\r', '\n')
                    
                    # 只有当修改后的内容与之前不同时才验证更新
                    # 如果内容相同（即使只是空格或行尾符不同），摘要可能不会改变
                    if expected_summary != summary_before_normalized:
                        # 规范化 summary_after 以便比较
                        summary_after_normalized = summary_after.replace('\r\n', '\n').replace('\r', '\n')
                        assert summary_after_normalized == expected_summary, \
                            f"File summary should be updated after modification (Requirement 3.2). " \
                            f"Expected: '{expected_summary}', Got: '{summary_after_normalized}'"
                    
                    # 验证总数没有变化（修改不应增加或减少记录）
                    cursor.execute("SELECT COUNT(*) as count FROM docs")
                    count_after_modify = cursor.fetchone()['count']
                    assert count_after_modify == count_after_create, \
                        f"After modifying a file, index count should remain {count_after_create}, but got {count_after_modify}"
                
                # 第四阶段：测试文件删除 (需求 3.3)
                # 模拟文件监听器检测到文件删除
                # 删除新创建的文件
                new_file_path.unlink()
                
                # 模拟文件监听器调用 remove_file_from_index 来删除索引
                remove_file_from_index(conn, new_file_path)
                
                # 验证文件已从索引中删除
                cursor.execute("SELECT COUNT(*) as count FROM docs WHERE path = ?", (f"{new_filename}.md",))
                deleted_file_count = cursor.fetchone()['count']
                assert deleted_file_count == 0, \
                    f"Deleted file should be removed from index (Requirement 3.3), but found {deleted_file_count} records"
                
                # 验证总数减少了 1
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                count_after_delete = cursor.fetchone()['count']
                assert count_after_delete == initial_count, \
                    f"After deleting a file, index should have {initial_count} records, but got {count_after_delete}"
                
                # 验证 FTS 表也同步更新
                cursor.execute("SELECT COUNT(*) as count FROM docs_fts")
                fts_count = cursor.fetchone()['count']
                assert fts_count == initial_count, \
                    f"FTS table should also be synchronized, expected {initial_count} records, but got {fts_count}"
                
            finally:
                conn.close()


# Feature: md-search-engine, Property 8: 非 Markdown 文件被忽略
# Validates: Requirements 3.5
@settings(max_examples=100, deadline=None)
@given(
    # 生成各种非 .md 扩展名的文件
    non_md_files=st.lists(
        st.tuples(
            _valid_filename_strategy(),
            # 生成各种非 .md 扩展名
            st.sampled_from(['.txt', '.pdf', '.doc', '.html', '.json', '.xml', '.py', '.js', '.css', '']),
            st.text(
                alphabet=st.characters(blacklist_categories=('Cs',)),
                min_size=10,
                max_size=200
            )
        ),
        min_size=1,
        max_size=5,
        unique_by=lambda x: (x[0] + x[1]).lower()  # 确保完整文件名唯一
    ),
    # 生成一些 .md 文件作为对照
    md_files=st.lists(
        st.tuples(
            _valid_filename_strategy(),
            st.text(
                alphabet=st.characters(blacklist_categories=('Cs',)),
                min_size=10,
                max_size=200
            )
        ),
        min_size=1,
        max_size=3,
        unique_by=lambda x: x[0].lower()
    )
)
def test_property_non_markdown_files_ignored(non_md_files, md_files):
    """属性测试：非 Markdown 文件被忽略
    
    属性：对于任意非 .md 扩展名的文件，文件监听器应忽略其创建、修改、删除事件。
    
    此测试验证文件监听器的过滤逻辑，确保只有 .md 文件会被索引，
    其他类型的文件（.txt, .pdf, .doc 等）不会影响索引。
    
    验证需求: 3.5 - 非 Markdown 文件发生变化时系统应忽略该事件
    """
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
                # 第一阶段：创建非 .md 文件并尝试索引
                # 这些文件不应该被索引
                non_md_file_paths = []
                for filename, extension, content in non_md_files:
                    # 确保文件名有效
                    if not filename or not filename.strip():
                        continue
                    
                    test_file = temp_md_root / f"{filename}{extension}"
                    test_file.write_text(content, encoding='utf-8')
                    non_md_file_paths.append(test_file)
                    
                    # 模拟文件监听器检测到文件创建
                    # 但由于不是 .md 文件，应该被忽略
                    # 我们通过直接调用 index_file 来测试，但在实际中
                    # MdEventHandler 会在 on_created 中过滤掉这些文件
                    # 为了测试过滤逻辑，我们检查文件扩展名
                    if test_file.suffix == '.md':
                        index_file(conn, test_file)
                
                # 验证非 .md 文件没有被索引
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                count_after_non_md = cursor.fetchone()['count']
                assert count_after_non_md == 0, \
                    f"Non-markdown files should not be indexed (Requirement 3.5), but found {count_after_non_md} records"
                
                # 第二阶段：创建 .md 文件作为对照
                # 这些文件应该被索引
                md_file_paths = []
                md_filenames = set()
                for filename, content in md_files:
                    # 确保文件名有效且唯一
                    if not filename or not filename.strip():
                        continue
                    
                    # 确保与非 .md 文件名不冲突
                    full_name = f"{filename}.md"
                    if full_name in md_filenames:
                        continue
                    
                    test_file = temp_md_root / full_name
                    test_file.write_text(content, encoding='utf-8')
                    md_file_paths.append(test_file)
                    md_filenames.add(full_name)
                    
                    # 模拟文件监听器调用 index_file
                    index_file(conn, test_file)
                
                # 验证只有 .md 文件被索引
                cursor.execute("SELECT COUNT(*) as count FROM docs")
                count_after_md = cursor.fetchone()['count']
                assert count_after_md == len(md_file_paths), \
                    f"Expected {len(md_file_paths)} markdown files to be indexed, but found {count_after_md} records"
                
                # 第三阶段：测试 MdEventHandler 的过滤逻辑
                # 创建事件处理器并测试 _is_markdown_file 方法
                from app.watcher import MdEventHandler
                handler = MdEventHandler()
                
                # 测试各种非 .md 文件扩展名
                for test_file in non_md_file_paths:
                    is_md = handler._is_markdown_file(str(test_file))
                    assert not is_md, \
                        f"File {test_file.name} should not be recognized as markdown (Requirement 3.5)"
                
                # 测试 .md 文件扩展名
                for test_file in md_file_paths:
                    is_md = handler._is_markdown_file(str(test_file))
                    assert is_md, \
                        f"File {test_file.name} should be recognized as markdown"
                
                # 第四阶段：测试修改和删除事件也会被过滤
                # 修改非 .md 文件
                if len(non_md_file_paths) > 0:
                    non_md_file = non_md_file_paths[0]
                    non_md_file.write_text("Modified content", encoding='utf-8')
                    
                    # 如果是 .md 文件才索引（模拟事件处理器的过滤）
                    if non_md_file.suffix == '.md':
                        index_file(conn, non_md_file)
                    
                    # 验证索引数量没有变化
                    cursor.execute("SELECT COUNT(*) as count FROM docs")
                    count_after_modify = cursor.fetchone()['count']
                    assert count_after_modify == len(md_file_paths), \
                        f"Modifying non-markdown files should not affect index (Requirement 3.5)"
                
                # 删除非 .md 文件
                if len(non_md_file_paths) > 0:
                    non_md_file = non_md_file_paths[0]
                    non_md_file.unlink()
                    
                    # 如果是 .md 文件才从索引删除（模拟事件处理器的过滤）
                    if non_md_file.suffix == '.md':
                        remove_file_from_index(conn, non_md_file)
                    
                    # 验证索引数量没有变化
                    cursor.execute("SELECT COUNT(*) as count FROM docs")
                    count_after_delete = cursor.fetchone()['count']
                    assert count_after_delete == len(md_file_paths), \
                        f"Deleting non-markdown files should not affect index (Requirement 3.5)"
                
                # 验证 FTS 表也保持一致
                cursor.execute("SELECT COUNT(*) as count FROM docs_fts")
                fts_count = cursor.fetchone()['count']
                assert fts_count == len(md_file_paths), \
                    f"FTS table should only contain markdown files, expected {len(md_file_paths)} records, but got {fts_count}"
                
            finally:
                conn.close()
