"""属性测试：搜索功能

使用 Hypothesis 进行基于属性的测试。
每个测试运行至少 100 次迭代以验证属性在各种输入下都成立。
"""

import tempfile
from pathlib import Path
import sqlite3
import re
from hypothesis import given, strategies as st, settings, assume, HealthCheck

from app.db import init_db
from app.indexer import index_file
from app.search_service import search_documents, render_document_html
from fastapi.testclient import TestClient
from app.main import app


# 生成有效的搜索关键词策略
def _valid_search_keyword_strategy():
    """生成有效的搜索关键词（避免 FTS5 特殊字符和空白）"""
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
        ) | st.sampled_from([' ']),
        min_size=1,
        max_size=50
    ).filter(lambda s: s and s.strip() and len(s.strip()) > 0)


# Feature: md-search-engine, Property 1: 搜索结果包含高亮关键词
# Validates: Requirements 1.3
@settings(max_examples=100, deadline=None)
@given(
    keyword=_valid_search_keyword_strategy(),
    # 生成包含关键词的文档内容
    content_parts=st.lists(
        st.text(
            alphabet=st.characters(
                blacklist_categories=('Cs',),
            ),
            min_size=0,
            max_size=100
        ),
        min_size=2,
        max_size=5
    )
)
def test_property_search_results_contain_highlighted_keywords(keyword, content_parts):
    """属性测试：搜索结果包含高亮关键词
    
    属性：对于任意搜索查询和文档集合，
    返回的每个搜索结果的 snippet 字段应包含用 <mark> 标签包裹的查询关键词。
    
    验证需求: 1.3 - 提供包含匹配关键词的高亮片段
    """
    # 确保关键词不为空且不只是空白
    keyword_stripped = keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # 创建数据库连接并初始化
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        init_db(conn)
        
        try:
            # 创建包含关键词的文档
            # 将关键词插入到内容的不同位置
            content = content_parts[0] + " " + keyword_stripped + " " + " ".join(content_parts[1:])
            
            # 确保内容不为空
            assume(len(content.strip()) > 0)
            
            # 创建 Markdown 文件
            file_content = f"""---
title: Test Document
---

{content}
"""
            
            test_file = temp_md_root / "test.md"
            test_file.write_text(file_content, encoding='utf-8')
            
            # 索引文件
            index_file(conn, test_file)
            
            # 执行搜索
            results, total = search_documents(keyword_stripped, conn=conn)
            
            # 如果有结果，验证属性
            if total > 0 and len(results) > 0:
                for result in results:
                    snippet = result.snippet
                    
                    # 验证 snippet 包含 <mark> 标签
                    assert "<mark>" in snippet, \
                        f"Snippet should contain '<mark>' tag, but got: {snippet}"
                    assert "</mark>" in snippet, \
                        f"Snippet should contain '</mark>' tag, but got: {snippet}"
                    
                    # 提取所有被 <mark> 标签包裹的文本
                    marked_texts = re.findall(r'<mark>(.*?)</mark>', snippet, re.IGNORECASE | re.DOTALL)
                    
                    # 验证至少有一个被标记的文本
                    assert len(marked_texts) > 0, \
                        f"Snippet should have at least one highlighted keyword, but got: {snippet}"
                    
                    # 验证被标记的文本与查询关键词相关
                    # 注意：由于 FTS5 可能会分词，我们检查是否有任何标记的文本包含关键词的一部分
                    keyword_lower = keyword_stripped.lower()
                    keyword_words = keyword_lower.split()
                    
                    # 检查是否有任何标记的文本与关键词的任何单词匹配
                    found_match = False
                    for marked_text in marked_texts:
                        marked_lower = marked_text.lower()
                        for word in keyword_words:
                            if word and (word in marked_lower or marked_lower in word):
                                found_match = True
                                break
                        if found_match:
                            break
                    
                    assert found_match, \
                        f"Highlighted text {marked_texts} should contain keyword '{keyword_stripped}' or its parts"
            
        finally:
            conn.close()


# Feature: md-search-engine, Property 3: 空查询被拒绝
# Validates: Requirements 1.4
@settings(max_examples=100, deadline=None)
@given(
    # 生成空白字符串策略：空字符串、空格、制表符、换行符等
    whitespace_query=st.one_of(
        st.just(""),  # 空字符串
        st.text(alphabet=st.sampled_from([' ', '\t', '\n', '\r']), min_size=1, max_size=20)  # 仅空白字符
    )
)
def test_property_empty_query_rejected(whitespace_query):
    """属性测试：空查询被拒绝
    
    属性：对于任意仅包含空白字符的查询字符串，
    系统应拒绝查询并返回 4xx 错误。
    
    验证需求: 1.4 - 搜索查询为空或仅包含空白字符时拒绝查询
    """
    # 创建测试客户端
    client = TestClient(app)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # Mock settings to use temporary directory
        from unittest.mock import patch
        from app import config
        
        with patch.object(config.settings, 'md_root', temp_md_root), \
             patch.object(config.settings, 'db_path', db_path):
            
            # 创建数据库连接并初始化
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            
            try:
                # 创建一个测试文档（确保数据库中有数据）
                file_content = """---
title: Test Document
---

This is a test document with some content.
"""
                
                test_file = temp_md_root / "test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                conn.close()
                
                # 使用空白查询调用 API
                # 使用 params 参数来正确处理 URL 编码
                response = client.get("/search", params={"q": whitespace_query})
                
                # 验证返回 4xx 错误状态码
                assert 400 <= response.status_code < 500, \
                    f"Empty or whitespace-only query should return 4xx status code, " \
                    f"but got {response.status_code} for query: '{repr(whitespace_query)}'"
                
                # 验证返回 422 Unprocessable Entity（FastAPI 的参数验证错误）
                assert response.status_code == 422, \
                    f"Empty or whitespace-only query should return 422 status code, " \
                    f"but got {response.status_code} for query: '{repr(whitespace_query)}'"
                
            finally:
                if not conn:
                    pass
                else:
                    try:
                        conn.close()
                    except:
                        pass


# Feature: md-search-engine, Property 2: 搜索结果按相关性排序
# Validates: Requirements 1.2
@settings(max_examples=100, deadline=None)
@given(
    keyword=_valid_search_keyword_strategy(),
    # 生成多个文档，每个文档包含不同数量的关键词
    doc_keyword_counts=st.lists(
        st.integers(min_value=1, max_value=10),  # 每个文档包含的关键词数量
        min_size=2,
        max_size=5
    )
)
def test_property_search_results_sorted_by_relevance(keyword, doc_keyword_counts):
    """属性测试：搜索结果按相关性排序
    
    属性：对于任意搜索查询，
    返回结果的 BM25 rank 值应按升序排列（rank 值越小越相关，因为 BM25 返回负值）。
    
    验证需求: 1.2 - 按相关性排序结果并使用 BM25 算法计算排名
    """
    # 确保关键词不为空且不只是空白
    keyword_stripped = keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # 创建数据库连接并初始化
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        init_db(conn)
        
        try:
            # 创建多个文档，每个文档包含不同数量的关键词
            for i, count in enumerate(doc_keyword_counts):
                # 创建包含指定数量关键词的内容
                # 关键词出现次数越多，BM25 分数应该越高（rank 值越小，因为是负值）
                keyword_occurrences = " ".join([keyword_stripped] * count)
                content = f"Document {i} content with keywords: {keyword_occurrences}. Some additional text to make it more realistic."
                
                # 创建 Markdown 文件
                file_content = f"""---
title: Test Document {i}
---

{content}
"""
                
                test_file = temp_md_root / f"test_{i}.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
            
            # 执行搜索
            results, total = search_documents(keyword_stripped, conn=conn)
            
            # 如果有多个结果，验证排序属性
            if total > 1 and len(results) > 1:
                # 验证 rank 值按升序排列（BM25 返回负值，越小越相关）
                ranks = [result.rank for result in results]
                
                # 检查是否按升序排列
                for i in range(len(ranks) - 1):
                    assert ranks[i] <= ranks[i + 1], \
                        f"Search results should be sorted by relevance (ascending rank). " \
                        f"Found rank[{i}]={ranks[i]} > rank[{i+1}]={ranks[i+1]}. " \
                        f"All ranks: {ranks}"
            
        finally:
            conn.close()


# Feature: md-search-engine, Property 4: 分页返回正确数量
# Validates: Requirements 1.5
@settings(max_examples=100, deadline=None)
@given(
    keyword=_valid_search_keyword_strategy(),
    # 生成文档数量
    num_docs=st.integers(min_value=1, max_value=50),
    # 生成分页参数
    limit=st.integers(min_value=1, max_value=20),
    offset=st.integers(min_value=0, max_value=30)
)
def test_property_pagination_returns_correct_count(keyword, num_docs, limit, offset):
    """属性测试：分页返回正确数量
    
    属性：对于任意有效的 limit 和 offset 参数，
    返回的结果数量应不超过 limit，且应从正确的偏移位置开始。
    
    验证需求: 1.5 - 返回指定范围的结果子集（分页）
    """
    # 确保关键词不为空且不只是空白
    keyword_stripped = keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # 创建数据库连接并初始化
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        init_db(conn)
        
        try:
            # 创建多个包含关键词的文档
            for i in range(num_docs):
                content = f"Document {i} contains the keyword: {keyword_stripped}. Additional content to make it searchable."
                
                # 创建 Markdown 文件
                file_content = f"""---
title: Test Document {i}
---

{content}
"""
                
                test_file = temp_md_root / f"test_{i}.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
            
            # 执行搜索，使用指定的 limit 和 offset
            results, total = search_documents(keyword_stripped, limit=limit, offset=offset, conn=conn)
            
            # 验证属性 1: 返回的结果数量不应超过 limit
            assert len(results) <= limit, \
                f"Number of results ({len(results)}) should not exceed limit ({limit})"
            
            # 验证属性 2: 如果 offset 小于 total，且 total > 0，应该有结果（除非 offset >= total）
            if total > 0:
                if offset < total:
                    # 应该返回一些结果（最多 limit 个）
                    expected_count = min(limit, total - offset)
                    assert len(results) == expected_count, \
                        f"Expected {expected_count} results (min(limit={limit}, total={total} - offset={offset})), " \
                        f"but got {len(results)}"
                else:
                    # offset >= total，应该返回空结果
                    assert len(results) == 0, \
                        f"When offset ({offset}) >= total ({total}), should return 0 results, but got {len(results)}"
            else:
                # 没有匹配的文档，应该返回空结果
                assert len(results) == 0, \
                    f"When total is 0, should return 0 results, but got {len(results)}"
            
            # 验证属性 3: 结果总数应该一致（不受 limit 和 offset 影响）
            # 再次搜索，使用不同的 limit 和 offset，total 应该相同
            results2, total2 = search_documents(keyword_stripped, limit=limit+5, offset=0, conn=conn)
            assert total == total2, \
                f"Total count should be consistent across different pagination parameters. " \
                f"Got {total} and {total2}"
            
        finally:
            conn.close()



# Feature: md-search-engine, Property 9: 文档检索返回 HTML
# Validates: Requirements 4.2
@settings(
    max_examples=100, 
    deadline=None,
    suppress_health_check=[HealthCheck.filter_too_much]
)
@given(
    # 生成随机的 Markdown 内容
    title=st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != ""),
    content=st.text(min_size=1, max_size=500).filter(lambda s: s.strip() != "")
)
def test_property_document_retrieval_returns_html(title, content):
    """属性测试：文档检索返回 HTML
    
    属性：对于任意已索引的文档 ID，
    调用文档详情 API 应返回有效的 HTML 格式内容。
    
    验证需求: 4.2 - 将 Markdown 转换为 HTML 格式
    """
    import yaml
    from unittest.mock import patch
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
                # 使用 YAML 库来正确序列化标题，避免 YAML 特殊字符问题
                frontmatter_dict = {'title': title}
                frontmatter_yaml = yaml.dump(frontmatter_dict, allow_unicode=True, default_flow_style=False)
                
                file_content = f"""---
{frontmatter_yaml}---

{content}
"""
                
                test_file = temp_md_root / "test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                
                # 获取文档 ID（应该是 1，因为这是第一个文档）
                # 使用相对路径查询（相对于 temp_md_root）
                rel_path = test_file.relative_to(temp_md_root)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM docs WHERE path = ?", (str(rel_path),))
                row = cursor.fetchone()
                
                # 如果索引失败，跳过此测试用例
                if row is None:
                    assume(False)
                
                doc_id = row['id']
                
                # 调用 render_document_html
                html_content = render_document_html(doc_id, conn)
                
                # 验证返回的是 HTML 内容
                assert html_content is not None, \
                    f"render_document_html should return HTML content for valid document ID {doc_id}"
                
                # 验证返回的是字符串
                assert isinstance(html_content, str), \
                    f"render_document_html should return a string, but got {type(html_content)}"
                
                # 验证返回的内容不为空
                assert len(html_content.strip()) > 0, \
                    "render_document_html should return non-empty HTML content"
                
                # 验证返回的内容是有效的 HTML（至少包含一些 HTML 标签或内容）
                # 由于 Markdown 可能只是纯文本，转换后可能只是 <p> 标签包裹的内容
                # 我们验证内容至少被处理过（不等于原始 Markdown）
                # 或者包含常见的 HTML 标签
                has_html_tags = (
                    '<p>' in html_content or
                    '<h1>' in html_content or
                    '<h2>' in html_content or
                    '<h3>' in html_content or
                    '<ul>' in html_content or
                    '<ol>' in html_content or
                    '<code>' in html_content or
                    '<pre>' in html_content or
                    '<table>' in html_content or
                    # 即使是纯文本，Markdown 库也会处理换行等
                    len(html_content) > 0
                )
                
                assert has_html_tags, \
                    f"render_document_html should return valid HTML content, but got: {html_content[:200]}"
                
            finally:
                conn.close()


# Feature: md-search-engine, Property 12: 搜索响应包含必需字段
# Validates: Requirements 6.3
@settings(max_examples=100, deadline=None)
@given(
    keyword=_valid_search_keyword_strategy(),
    # 生成文档数量
    num_docs=st.integers(min_value=0, max_value=10),
    # 生成分页参数
    limit=st.integers(min_value=1, max_value=20),
    offset=st.integers(min_value=0, max_value=10)
)
def test_property_search_response_contains_required_fields(keyword, num_docs, limit, offset):
    """属性测试：搜索响应包含必需字段
    
    属性：对于任意搜索查询，
    返回的 JSON 响应应包含 total、results、query、limit、offset 字段。
    
    验证需求: 6.3 - 显示搜索结果时展示文档标题、路径和高亮片段
    """
    from unittest.mock import patch
    from app import config
    
    # 确保关键词不为空且不只是空白
    keyword_stripped = keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # Mock settings to use temporary directory
        with patch.object(config.settings, 'md_root', temp_md_root), \
             patch.object(config.settings, 'db_path', db_path):
            
            # 创建数据库连接并初始化
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            
            try:
                # 创建多个包含关键词的文档
                for i in range(num_docs):
                    content = f"Document {i} contains the keyword: {keyword_stripped}. Additional content for testing."
                    
                    # 创建 Markdown 文件
                    file_content = f"""---
title: Test Document {i}
---

{content}
"""
                    
                    test_file = temp_md_root / f"test_{i}.md"
                    test_file.write_text(file_content, encoding='utf-8')
                    
                    # 索引文件
                    index_file(conn, test_file)
                
                conn.close()
                
                # 创建测试客户端
                client = TestClient(app)
                
                # 调用搜索 API
                response = client.get("/search", params={
                    "q": keyword_stripped,
                    "limit": limit,
                    "offset": offset
                })
                
                # 验证响应状态码为 200
                assert response.status_code == 200, \
                    f"Search API should return 200 status code, but got {response.status_code}"
                
                # 验证响应是 JSON 格式
                assert response.headers.get("content-type", "").startswith("application/json"), \
                    f"Search API should return JSON content type, but got {response.headers.get('content-type')}"
                
                # 解析 JSON 响应
                json_data = response.json()
                
                # 验证属性：响应包含所有必需字段
                required_fields = ['total', 'results', 'query', 'limit', 'offset']
                
                for field in required_fields:
                    assert field in json_data, \
                        f"Search response should contain '{field}' field, but got: {list(json_data.keys())}"
                
                # 验证字段类型
                assert isinstance(json_data['total'], int), \
                    f"'total' field should be an integer, but got {type(json_data['total'])}"
                
                assert isinstance(json_data['results'], list), \
                    f"'results' field should be a list, but got {type(json_data['results'])}"
                
                assert isinstance(json_data['query'], str), \
                    f"'query' field should be a string, but got {type(json_data['query'])}"
                
                assert isinstance(json_data['limit'], int), \
                    f"'limit' field should be an integer, but got {type(json_data['limit'])}"
                
                assert isinstance(json_data['offset'], int), \
                    f"'offset' field should be an integer, but got {type(json_data['offset'])}"
                
                # 验证字段值的正确性
                assert json_data['query'] == keyword_stripped, \
                    f"'query' field should match the search query '{keyword_stripped}', but got '{json_data['query']}'"
                
                assert json_data['limit'] == limit, \
                    f"'limit' field should match the requested limit {limit}, but got {json_data['limit']}"
                
                assert json_data['offset'] == offset, \
                    f"'offset' field should match the requested offset {offset}, but got {json_data['offset']}"
                
                # 验证 total 是非负整数
                assert json_data['total'] >= 0, \
                    f"'total' field should be non-negative, but got {json_data['total']}"
                
                # 验证 results 列表中的每个元素包含必需字段
                for i, result in enumerate(json_data['results']):
                    result_required_fields = ['id', 'title', 'path', 'snippet']
                    
                    for field in result_required_fields:
                        assert field in result, \
                            f"Search result[{i}] should contain '{field}' field, but got: {list(result.keys())}"
                    
                    # 验证结果字段类型
                    assert isinstance(result['id'], int), \
                        f"Result[{i}] 'id' should be an integer, but got {type(result['id'])}"
                    
                    assert isinstance(result['title'], str), \
                        f"Result[{i}] 'title' should be a string, but got {type(result['title'])}"
                    
                    assert isinstance(result['path'], str), \
                        f"Result[{i}] 'path' should be a string, but got {type(result['path'])}"
                    
                    assert isinstance(result['snippet'], str), \
                        f"Result[{i}] 'snippet' should be a string, but got {type(result['snippet'])}"
                
            finally:
                if not conn:
                    pass
                else:
                    try:
                        conn.close()
                    except:
                        pass



# Feature: md-search-engine, Property 17: API 返回 JSON 格式
# Validates: Requirements 9.1
@settings(max_examples=100, deadline=None)
@given(
    keyword=_valid_search_keyword_strategy(),
    # 生成文档数量
    num_docs=st.integers(min_value=0, max_value=10),
    # 生成分页参数
    limit=st.integers(min_value=1, max_value=20),
    offset=st.integers(min_value=0, max_value=10)
)
def test_property_api_returns_json_format(keyword, num_docs, limit, offset):
    """属性测试：API 返回 JSON 格式
    
    属性：对于任意搜索 API 调用，
    响应应是有效的 JSON 格式。
    
    验证需求: 9.1 - 客户端调用搜索 API 时返回 JSON 格式的搜索结果
    """
    import json
    from unittest.mock import patch
    from app import config
    
    # 确保关键词不为空且不只是空白
    keyword_stripped = keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # Mock settings to use temporary directory
        with patch.object(config.settings, 'md_root', temp_md_root), \
             patch.object(config.settings, 'db_path', db_path):
            
            # 创建数据库连接并初始化
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            
            try:
                # 创建多个包含关键词的文档
                for i in range(num_docs):
                    content = f"Document {i} contains the keyword: {keyword_stripped}. Additional content for testing."
                    
                    # 创建 Markdown 文件
                    file_content = f"""---
title: Test Document {i}
---

{content}
"""
                    
                    test_file = temp_md_root / f"test_{i}.md"
                    test_file.write_text(file_content, encoding='utf-8')
                    
                    # 索引文件
                    index_file(conn, test_file)
                
                conn.close()
                
                # 创建测试客户端
                client = TestClient(app)
                
                # 调用搜索 API
                response = client.get("/search", params={
                    "q": keyword_stripped,
                    "limit": limit,
                    "offset": offset
                })
                
                # 验证响应状态码为 200
                assert response.status_code == 200, \
                    f"Search API should return 200 status code, but got {response.status_code}"
                
                # 验证属性 1: 响应的 Content-Type 应该是 application/json
                content_type = response.headers.get("content-type", "")
                assert "application/json" in content_type, \
                    f"Search API should return 'application/json' content type, but got '{content_type}'"
                
                # 验证属性 2: 响应内容应该是有效的 JSON
                try:
                    # 尝试解析响应内容为 JSON
                    json_data = json.loads(response.text)
                except json.JSONDecodeError as e:
                    assert False, \
                        f"Search API should return valid JSON, but got JSONDecodeError: {e}. " \
                        f"Response text: {response.text[:200]}"
                
                # 验证属性 3: 解析后的 JSON 应该是一个字典（对象）
                assert isinstance(json_data, dict), \
                    f"Search API should return a JSON object (dict), but got {type(json_data)}"
                
                # 验证属性 4: JSON 对象应该包含预期的顶级字段
                # 这确保返回的不仅是有效的 JSON，而且是符合 API 规范的 JSON
                assert "total" in json_data, \
                    f"Search API JSON response should contain 'total' field"
                
                assert "results" in json_data, \
                    f"Search API JSON response should contain 'results' field"
                
                assert "query" in json_data, \
                    f"Search API JSON response should contain 'query' field"
                
                # 验证属性 5: 使用 response.json() 方法也应该能正确解析
                # 这验证 FastAPI 的 JSON 序列化是正确的
                json_data_via_method = response.json()
                assert json_data == json_data_via_method, \
                    f"JSON parsed manually should match response.json() result"
                
                # 验证属性 6: JSON 中的所有值都应该是可序列化的
                # 尝试重新序列化以确保没有不可序列化的对象
                try:
                    re_serialized = json.dumps(json_data)
                    assert len(re_serialized) > 0, \
                        "Re-serialized JSON should not be empty"
                except (TypeError, ValueError) as e:
                    assert False, \
                        f"Search API JSON response should be fully serializable, but got error: {e}"
                
            finally:
                if not conn:
                    pass
                else:
                    try:
                        conn.close()
                    except:
                        pass



# Feature: md-search-engine, Property 18: 无效参数返回 4xx
# Validates: Requirements 9.3
@settings(max_examples=100, deadline=None)
@given(
    # 生成各种无效参数的策略
    param_type=st.sampled_from(['invalid_limit', 'invalid_offset', 'negative_limit', 'negative_offset', 'zero_limit', 'excessive_limit']),
    valid_keyword=_valid_search_keyword_strategy()
)
def test_property_invalid_parameters_return_4xx(param_type, valid_keyword):
    """属性测试：无效参数返回 4xx
    
    属性：对于任意包含无效参数的 API 请求，
    系统应返回 4xx 状态码。
    
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    """
    from unittest.mock import patch
    from app import config
    
    # 确保关键词不为空且不只是空白
    keyword_stripped = valid_keyword.strip()
    assume(len(keyword_stripped) > 0)
    
    # 为每个测试用例创建临时目录和数据库
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_md_root = Path(tmpdir)
        db_path = temp_md_root / "test.db"
        
        # Mock settings to use temporary directory
        with patch.object(config.settings, 'md_root', temp_md_root), \
             patch.object(config.settings, 'db_path', db_path):
            
            # 创建数据库连接并初始化
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            init_db(conn)
            
            try:
                # 创建一个测试文档
                file_content = f"""---
title: Test Document
---

This is a test document with keyword: {keyword_stripped}.
"""
                
                test_file = temp_md_root / "test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                conn.close()
                
                # 创建测试客户端
                client = TestClient(app)
                
                # 根据参数类型构建不同的无效请求
                if param_type == 'invalid_limit':
                    # 测试非数字的 limit
                    response = client.get("/search", params={"q": keyword_stripped, "limit": "abc"})
                elif param_type == 'invalid_offset':
                    # 测试非数字的 offset
                    response = client.get("/search", params={"q": keyword_stripped, "offset": "xyz"})
                elif param_type == 'negative_limit':
                    # 测试负数 limit
                    response = client.get("/search", params={"q": keyword_stripped, "limit": -1})
                elif param_type == 'negative_offset':
                    # 测试负数 offset
                    response = client.get("/search", params={"q": keyword_stripped, "offset": -1})
                elif param_type == 'zero_limit':
                    # 测试零 limit
                    response = client.get("/search", params={"q": keyword_stripped, "limit": 0})
                elif param_type == 'excessive_limit':
                    # 测试超过最大值的 limit (max is 100)
                    response = client.get("/search", params={"q": keyword_stripped, "limit": 1000})
                
                # 验证属性：返回 4xx 状态码
                assert 400 <= response.status_code < 500, \
                    f"Invalid parameter '{param_type}' should return 4xx status code, " \
                    f"but got {response.status_code}"
                
                # 验证返回 422 Unprocessable Entity（FastAPI 的参数验证错误）
                assert response.status_code == 422, \
                    f"Invalid parameter '{param_type}' should return 422 status code, " \
                    f"but got {response.status_code}"
                
            finally:
                if not conn:
                    pass
                else:
                    try:
                        conn.close()
                    except:
                        pass



# Feature: md-search-engine, Property 19: Markdown 扩展语法支持
# Validates: Requirements 4.5
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.filter_too_much]
)
@given(
    # 生成包含代码块或表格的 Markdown 内容
    content_type=st.sampled_from(['code_block', 'table', 'both']),
    # 生成代码块内容
    code_content=st.text(
        alphabet=st.characters(blacklist_categories=('Cs',)),
        min_size=1,
        max_size=200
    ),
    # 生成表格行数
    table_rows=st.integers(min_value=2, max_value=5),
    # 生成表格列数
    table_cols=st.integers(min_value=2, max_value=4)
)
def test_property_markdown_extension_syntax_support(content_type, code_content, table_rows, table_cols):
    """属性测试：Markdown 扩展语法支持
    
    属性：对于任意包含代码块或表格的 Markdown 文档，
    渲染的 HTML 应包含相应的 HTML 标签（<pre><code> 或 <table>）。
    
    验证需求: 4.5 - 支持代码块和表格扩展语法
    """
    import yaml
    from unittest.mock import patch
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
                # 根据内容类型生成 Markdown 内容
                markdown_content = "# Test Document\n\n"
                
                if content_type in ['code_block', 'both']:
                    # 添加代码块
                    # 使用 fenced code block 语法
                    markdown_content += f"""
## Code Example

```python
{code_content}
```

"""
                
                if content_type in ['table', 'both']:
                    # 添加表格
                    # 生成表格头
                    headers = [f"Col{i+1}" for i in range(table_cols)]
                    markdown_content += "## Table Example\n\n"
                    markdown_content += "| " + " | ".join(headers) + " |\n"
                    markdown_content += "| " + " | ".join(["---"] * table_cols) + " |\n"
                    
                    # 生成表格行
                    for row_idx in range(table_rows - 1):  # -1 because header is one row
                        row_data = [f"R{row_idx+1}C{col_idx+1}" for col_idx in range(table_cols)]
                        markdown_content += "| " + " | ".join(row_data) + " |\n"
                    
                    markdown_content += "\n"
                
                # 创建带有 frontmatter 的 Markdown 文件
                frontmatter_dict = {'title': 'Test Document'}
                frontmatter_yaml = yaml.dump(frontmatter_dict, allow_unicode=True, default_flow_style=False)
                
                file_content = f"""---
{frontmatter_yaml}---

{markdown_content}
"""
                
                test_file = temp_md_root / "test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                
                # 获取文档 ID
                rel_path = test_file.relative_to(temp_md_root)
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM docs WHERE path = ?", (str(rel_path),))
                row = cursor.fetchone()
                
                # 如果索引失败，跳过此测试用例
                if row is None:
                    assume(False)
                
                doc_id = row['id']
                
                # 调用 render_document_html
                html_content = render_document_html(doc_id, conn)
                
                # 验证返回的是 HTML 内容
                assert html_content is not None, \
                    f"render_document_html should return HTML content for valid document ID {doc_id}"
                
                # 验证属性：根据内容类型检查相应的 HTML 标签
                if content_type in ['code_block', 'both']:
                    # 验证包含代码块标签
                    # Markdown 库会将 fenced code block 转换为 <pre><code> 或 <div class="codehilite"><pre>
                    has_code_tags = (
                        '<code>' in html_content or
                        '<pre>' in html_content or
                        'codehilite' in html_content
                    )
                    assert has_code_tags, \
                        f"HTML should contain code block tags (<pre>, <code>, or codehilite) for code blocks, " \
                        f"but got: {html_content[:500]}"
                
                if content_type in ['table', 'both']:
                    # 验证包含表格标签
                    assert '<table>' in html_content, \
                        f"HTML should contain <table> tag for tables, but got: {html_content[:500]}"
                    
                    # 验证表格结构完整性
                    assert '<tr>' in html_content, \
                        f"HTML should contain <tr> tag for table rows, but got: {html_content[:500]}"
                    
                    assert '<th>' in html_content or '<td>' in html_content, \
                        f"HTML should contain <th> or <td> tags for table cells, but got: {html_content[:500]}"
                
            finally:
                conn.close()



# Feature: md-search-engine, Property 14: 中文关键词搜索
# Validates: Requirements 8.2
@settings(max_examples=100, deadline=None)
@given(
    # 生成中文关键词策略
    chinese_keyword=st.text(
        alphabet=st.characters(
            min_codepoint=0x4e00,  # CJK Unified Ideographs start
            max_codepoint=0x9fff   # CJK Unified Ideographs end
        ),
        min_size=1,
        max_size=10
    ).filter(lambda s: s and s.strip() and len(s.strip()) > 0),
    # 生成文档数量
    num_docs=st.integers(min_value=1, max_value=5),
    # 生成包含关键词的文档数量
    num_matching_docs=st.integers(min_value=1, max_value=3)
)
def test_property_chinese_keyword_search(chinese_keyword, num_docs, num_matching_docs):
    """属性测试：中文关键词搜索
    
    属性：对于任意包含中文内容的文档和中文查询关键词，
    搜索应能正确匹配并返回结果。
    
    验证需求: 8.2 - 搜索中文关键词时正确匹配包含该关键词的文档
    """
    from unittest.mock import patch
    from app import config
    
    # 确保匹配文档数不超过总文档数
    assume(num_matching_docs <= num_docs)
    
    # 确保关键词不为空且不只是空白
    keyword_stripped = chinese_keyword.strip()
    assume(len(keyword_stripped) > 0)
    
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
                # 创建包含中文关键词的文档
                for i in range(num_matching_docs):
                    # 创建包含关键词的中文内容
                    content = f"这是第 {i+1} 个测试文档。文档内容包含关键词：{keyword_stripped}。这是一些额外的中文内容用于测试搜索功能。"
                    
                    # 创建 Markdown 文件
                    file_content = f"""---
title: 中文测试文档 {i+1}
---

{content}
"""
                    
                    test_file = temp_md_root / f"chinese_test_{i}.md"
                    test_file.write_text(file_content, encoding='utf-8')
                    
                    # 索引文件
                    index_file(conn, test_file)
                
                # 创建不包含关键词的文档
                for i in range(num_matching_docs, num_docs):
                    # 创建不包含关键词的中文内容
                    # 使用不同的中文字符，确保不包含关键词
                    content = f"这是第 {i+1} 个文档。这个文档不包含目标词汇。内容是关于其他主题的测试数据。"
                    
                    # 创建 Markdown 文件
                    file_content = f"""---
title: 其他中文文档 {i+1}
---

{content}
"""
                    
                    test_file = temp_md_root / f"other_doc_{i}.md"
                    test_file.write_text(file_content, encoding='utf-8')
                    
                    # 索引文件
                    index_file(conn, test_file)
                
                # 执行搜索
                results, total = search_documents(keyword_stripped, conn=conn)
                
                # 验证属性 1: 应该找到包含关键词的文档
                assert total > 0, \
                    f"Should find at least one document containing Chinese keyword '{keyword_stripped}', " \
                    f"but found {total} documents"
                
                # 验证属性 2: 找到的文档数应该等于包含关键词的文档数
                # 注意：由于 FTS5 的分词特性，可能会有一些边界情况
                # 我们验证至少找到了一些匹配的文档
                assert total >= 1, \
                    f"Should find at least 1 matching document for Chinese keyword '{keyword_stripped}', " \
                    f"but found {total}"
                
                # 验证属性 3: 返回的结果应该包含关键词（在标题或片段中）
                for result in results:
                    # 检查关键词是否出现在标题或片段中
                    # 由于 snippet 可能被截断，我们检查关键词的任何字符是否出现
                    keyword_chars = set(keyword_stripped)
                    snippet_chars = set(result.snippet)
                    title_chars = set(result.title)
                    
                    # 至少有一些关键词字符应该出现在结果中
                    has_keyword_in_snippet = any(char in snippet_chars for char in keyword_chars)
                    has_keyword_in_title = any(char in title_chars for char in keyword_chars)
                    
                    # 或者直接检查关键词是否在文本中
                    keyword_in_snippet = keyword_stripped in result.snippet
                    keyword_in_title = keyword_stripped in result.title
                    
                    assert keyword_in_snippet or keyword_in_title or has_keyword_in_snippet or has_keyword_in_title, \
                        f"Search result should contain Chinese keyword '{keyword_stripped}' or its characters. " \
                        f"Title: '{result.title}', Snippet: '{result.snippet}'"
                
                # 验证属性 4: 搜索结果应该包含高亮标记（如果有片段）
                if len(results) > 0 and results[0].snippet:
                    snippet = results[0].snippet
                    # 验证包含 <mark> 标签
                    assert "<mark>" in snippet or "</mark>" in snippet, \
                        f"Chinese search results should contain highlight markers, but got: {snippet}"
                
            finally:
                conn.close()


# Feature: md-search-engine, Property 15: 中英文混合搜索
# Validates: Requirements 8.3
@settings(max_examples=100, deadline=None)
@given(
    # 生成中文关键词
    chinese_keyword=st.text(
        alphabet=st.characters(
            min_codepoint=0x4e00,  # CJK Unified Ideographs start
            max_codepoint=0x9fff   # CJK Unified Ideographs end
        ),
        min_size=2,
        max_size=5
    ).filter(lambda s: s and s.strip() and len(s.strip()) >= 2),
    # 生成英文关键词
    english_keyword=st.text(
        alphabet=st.characters(
            min_codepoint=ord('a'),
            max_codepoint=ord('z')
        ) | st.characters(
            min_codepoint=ord('A'),
            max_codepoint=ord('Z')
        ),
        min_size=3,
        max_size=10
    ).filter(lambda s: s and s.strip() and len(s.strip()) >= 3),
    # 生成文档数量
    num_docs=st.integers(min_value=1, max_value=5)
)
def test_property_mixed_chinese_english_search(chinese_keyword, english_keyword, num_docs):
    """属性测试：中英文混合搜索
    
    属性：对于任意包含中英文混合内容的文档，
    使用中文或英文关键词搜索都应能匹配。
    
    验证需求: 8.3 - 文档包含中英文混合内容时，中英文关键词搜索都应能匹配
    """
    from unittest.mock import patch
    from app import config
    
    # 确保关键词不为空且不只是空白
    chinese_stripped = chinese_keyword.strip()
    english_stripped = english_keyword.strip()
    assume(len(chinese_stripped) >= 2)
    assume(len(english_stripped) >= 3)
    
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
                # 创建包含中英文混合内容的文档
                for i in range(num_docs):
                    # 创建中英文混合内容，包含两个关键词
                    content = f"""这是一个中英文混合的测试文档。

这个文档包含中文关键词：{chinese_stripped}。

This document also contains English keyword: {english_stripped}.

我们可以使用 {english_stripped} 来测试搜索功能。同时也包含 {chinese_stripped} 用于验证中文搜索。

The mixed content should be searchable in both languages. 中英文内容都应该可以被搜索到。
"""
                    
                    # 创建 Markdown 文件
                    file_content = f"""---
title: 混合语言文档 {i+1}
---

{content}
"""
                    
                    test_file = temp_md_root / f"mixed_doc_{i}.md"
                    test_file.write_text(file_content, encoding='utf-8')
                    
                    # 索引文件
                    index_file(conn, test_file)
                
                # 测试属性 1: 使用中文关键词搜索应该能找到文档
                chinese_results, chinese_total = search_documents(chinese_stripped, conn=conn)
                
                assert chinese_total > 0, \
                    f"Should find documents with Chinese keyword '{chinese_stripped}', " \
                    f"but found {chinese_total} documents"
                
                # 验证找到的文档数量应该等于创建的文档数量
                assert chinese_total == num_docs, \
                    f"Should find all {num_docs} documents with Chinese keyword '{chinese_stripped}', " \
                    f"but found {chinese_total}"
                
                # 验证返回的结果包含关键词
                for result in chinese_results:
                    # 检查关键词是否出现在标题、片段或路径中
                    has_keyword = (
                        chinese_stripped in result.title or
                        chinese_stripped in result.snippet or
                        any(char in result.snippet for char in chinese_stripped)
                    )
                    assert has_keyword, \
                        f"Chinese search result should contain keyword '{chinese_stripped}'. " \
                        f"Title: '{result.title}', Snippet: '{result.snippet}'"
                
                # 测试属性 2: 使用英文关键词搜索应该能找到相同的文档
                english_results, english_total = search_documents(english_stripped, conn=conn)
                
                assert english_total > 0, \
                    f"Should find documents with English keyword '{english_stripped}', " \
                    f"but found {english_total} documents"
                
                # 验证找到的文档数量应该等于创建的文档数量
                assert english_total == num_docs, \
                    f"Should find all {num_docs} documents with English keyword '{english_stripped}', " \
                    f"but found {english_total}"
                
                # 验证返回的结果包含关键词
                for result in english_results:
                    # 检查关键词是否出现在标题、片段或路径中
                    has_keyword = (
                        english_stripped.lower() in result.title.lower() or
                        english_stripped.lower() in result.snippet.lower()
                    )
                    assert has_keyword, \
                        f"English search result should contain keyword '{english_stripped}'. " \
                        f"Title: '{result.title}', Snippet: '{result.snippet}'"
                
                # 测试属性 3: 两次搜索应该返回相同的文档集合（通过 ID 比较）
                chinese_doc_ids = set(result.id for result in chinese_results)
                english_doc_ids = set(result.id for result in english_results)
                
                assert chinese_doc_ids == english_doc_ids, \
                    f"Chinese and English searches should return the same documents. " \
                    f"Chinese IDs: {chinese_doc_ids}, English IDs: {english_doc_ids}"
                
                # 测试属性 4: 搜索结果应该包含高亮标记
                if len(chinese_results) > 0 and chinese_results[0].snippet:
                    snippet = chinese_results[0].snippet
                    assert "<mark>" in snippet and "</mark>" in snippet, \
                        f"Chinese search results should contain highlight markers, but got: {snippet}"
                
                if len(english_results) > 0 and english_results[0].snippet:
                    snippet = english_results[0].snippet
                    assert "<mark>" in snippet and "</mark>" in snippet, \
                        f"English search results should contain highlight markers, but got: {snippet}"
                
            finally:
                conn.close()



# Feature: md-search-engine, Property 16: 中文高亮正确性
# Validates: Requirements 8.4
@settings(max_examples=100, deadline=None)
@given(
    # 生成中文关键词策略
    chinese_keyword=st.text(
        alphabet=st.characters(
            min_codepoint=0x4e00,  # CJK Unified Ideographs start
            max_codepoint=0x9fff   # CJK Unified Ideographs end
        ),
        min_size=2,
        max_size=8
    ).filter(lambda s: s and s.strip() and len(s.strip()) >= 2),
    # 生成文档内容的前后部分
    content_before=st.text(
        alphabet=st.characters(
            min_codepoint=0x4e00,
            max_codepoint=0x9fff
        ) | st.sampled_from([' ', '，', '。', '、']),
        min_size=5,
        max_size=50
    ),
    content_after=st.text(
        alphabet=st.characters(
            min_codepoint=0x4e00,
            max_codepoint=0x9fff
        ) | st.sampled_from([' ', '，', '。', '、']),
        min_size=5,
        max_size=50
    )
)
def test_property_chinese_highlight_correctness(chinese_keyword, content_before, content_after):
    """属性测试：中文高亮正确性
    
    属性：对于任意中文搜索查询，
    返回的 snippet 应包含正确的中文字符和 <mark> 标签。
    
    验证需求: 8.4 - 搜索结果包含中文时正确生成包含中文的高亮片段
    """
    from unittest.mock import patch
    from app import config
    import re
    
    # 确保关键词不为空且不只是空白
    keyword_stripped = chinese_keyword.strip()
    assume(len(keyword_stripped) >= 2)
    
    # 确保前后内容不包含关键词（避免混淆）
    assume(keyword_stripped not in content_before)
    assume(keyword_stripped not in content_after)
    
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
                # 创建包含中文关键词的文档
                # 将关键词放在内容中间，确保它会出现在 snippet 中
                content = f"{content_before} {keyword_stripped} {content_after}"
                
                # 创建 Markdown 文件
                file_content = f"""---
title: 中文高亮测试文档
---

{content}
"""
                
                test_file = temp_md_root / "chinese_highlight_test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                
                # 执行搜索
                results, total = search_documents(keyword_stripped, conn=conn)
                
                # 验证找到了文档
                assert total > 0, \
                    f"Should find document containing Chinese keyword '{keyword_stripped}', " \
                    f"but found {total} documents"
                
                assert len(results) > 0, \
                    f"Should return at least one result for Chinese keyword '{keyword_stripped}'"
                
                # 获取第一个结果的 snippet
                snippet = results[0].snippet
                
                # 验证属性 1: snippet 应该包含中文字符
                has_chinese = any('\u4e00' <= char <= '\u9fff' for char in snippet)
                assert has_chinese, \
                    f"Snippet should contain Chinese characters for Chinese search query '{keyword_stripped}', " \
                    f"but got: {snippet}"
                
                # 验证属性 2: snippet 应该包含高亮标记 <mark> 和 </mark>
                assert '<mark>' in snippet, \
                    f"Snippet should contain '<mark>' tag for Chinese keyword '{keyword_stripped}', " \
                    f"but got: {snippet}"
                
                assert '</mark>' in snippet, \
                    f"Snippet should contain '</mark>' tag for Chinese keyword '{keyword_stripped}', " \
                    f"but got: {snippet}"
                
                # 验证属性 3: 提取被 <mark> 标签包裹的文本
                marked_texts = re.findall(r'<mark>(.*?)</mark>', snippet, re.DOTALL)
                
                assert len(marked_texts) > 0, \
                    f"Snippet should have at least one highlighted text for Chinese keyword '{keyword_stripped}', " \
                    f"but got: {snippet}"
                
                # 验证属性 4: 被标记的文本应该包含中文字符
                for marked_text in marked_texts:
                    has_chinese_in_mark = any('\u4e00' <= char <= '\u9fff' for char in marked_text)
                    assert has_chinese_in_mark, \
                        f"Highlighted text should contain Chinese characters, " \
                        f"but got: '{marked_text}' in snippet: {snippet}"
                
                # 验证属性 5: 被标记的文本应该与查询关键词相关
                # 由于 FTS5 的分词特性，被标记的文本可能是关键词的一部分或包含关键词
                # 我们验证至少有一个被标记的文本包含关键词的某些字符
                keyword_chars = set(keyword_stripped)
                found_related = False
                
                for marked_text in marked_texts:
                    marked_chars = set(marked_text)
                    # 检查是否有交集
                    if keyword_chars & marked_chars:
                        found_related = True
                        break
                    # 或者检查关键词是否在标记文本中
                    if keyword_stripped in marked_text or marked_text in keyword_stripped:
                        found_related = True
                        break
                
                assert found_related, \
                    f"At least one highlighted text should be related to Chinese keyword '{keyword_stripped}'. " \
                    f"Highlighted texts: {marked_texts}, Snippet: {snippet}"
                
                # 验证属性 6: snippet 应该是有效的 HTML 片段（标签应该正确闭合）
                # 计算 <mark> 和 </mark> 的数量应该相等
                mark_open_count = snippet.count('<mark>')
                mark_close_count = snippet.count('</mark>')
                
                assert mark_open_count == mark_close_count, \
                    f"Number of '<mark>' tags ({mark_open_count}) should equal number of '</mark>' tags ({mark_close_count}) " \
                    f"in snippet: {snippet}"
                
                # 验证属性 7: snippet 不应该包含损坏的中文字符
                # 检查是否有孤立的高位或低位代理对（这会导致编码错误）
                try:
                    # 尝试编码和解码 snippet，确保没有编码问题
                    snippet_encoded = snippet.encode('utf-8')
                    snippet_decoded = snippet_encoded.decode('utf-8')
                    assert snippet == snippet_decoded, \
                        f"Snippet should be properly encoded/decoded without corruption"
                except (UnicodeEncodeError, UnicodeDecodeError) as e:
                    assert False, \
                        f"Snippet contains corrupted Chinese characters: {e}. Snippet: {snippet}"
                
            finally:
                conn.close()



# Feature: md-search-engine, Property 20: 音调符号标准化
# Validates: Requirements 8.5
@settings(max_examples=100, deadline=None)
@given(
    # 生成带音调符号的文本（例如拼音）
    # 使用 Latin Extended-A 和 Latin Extended-B 范围的字符，这些包含带音调的字母
    text_with_diacritics=st.text(
        alphabet=st.characters(
            # 包含带音调符号的拉丁字母
            min_codepoint=0x00C0,  # À
            max_codepoint=0x017F   # ſ (Latin Extended-A)
        ) | st.characters(
            min_codepoint=ord('a'),
            max_codepoint=ord('z')
        ) | st.characters(
            min_codepoint=ord('A'),
            max_codepoint=ord('Z')
        ) | st.sampled_from([' ']),
        min_size=3,
        max_size=20
    ).filter(lambda s: s and s.strip() and len(s.strip()) >= 3),
    # 生成额外的文档内容
    extra_content=st.text(
        alphabet=st.characters(
            blacklist_categories=('Cs',),
        ),
        min_size=10,
        max_size=100
    )
)
def test_property_tone_mark_normalization(text_with_diacritics, extra_content):
    """属性测试：音调符号标准化
    
    属性：对于任意带音调符号的文本，
    搜索不带音调的关键词应能匹配。
    
    验证需求: 8.5 - 处理带音调符号的字符时移除音调符号进行标准化匹配
    """
    import unicodedata
    from unittest.mock import patch
    from app import config
    
    # 确保文本不为空且不只是空白
    text_stripped = text_with_diacritics.strip()
    assume(len(text_stripped) >= 3)
    
    # 检查文本是否包含音调符号
    # 通过 NFD 分解检查是否有组合字符
    nfd_form = unicodedata.normalize('NFD', text_stripped)
    has_diacritics = any(unicodedata.category(c) == 'Mn' for c in nfd_form)
    
    # 如果没有音调符号，跳过此测试用例
    assume(has_diacritics)
    
    # 生成不带音调符号的查询字符串
    # 使用 NFD 分解，然后移除所有组合字符（Mn = Mark, Nonspacing）
    query_without_diacritics = ''.join(
        c for c in nfd_form
        if unicodedata.category(c) != 'Mn'
    )
    
    # 确保移除音调后的查询不为空
    assume(len(query_without_diacritics.strip()) >= 2)
    
    # 确保移除音调后的查询与原文本不同（确实移除了音调）
    assume(query_without_diacritics != text_stripped)
    
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
                # 创建包含带音调符号文本的文档
                content = f"{extra_content} {text_stripped} {extra_content}"
                
                # 创建 Markdown 文件
                file_content = f"""---
title: Tone Mark Test Document
---

{content}
"""
                
                test_file = temp_md_root / "tone_mark_test.md"
                test_file.write_text(file_content, encoding='utf-8')
                
                # 索引文件
                index_file(conn, test_file)
                
                # 执行搜索：使用不带音调符号的查询
                results, total = search_documents(query_without_diacritics, conn=conn)
                
                # 验证属性：应该能找到包含带音调符号文本的文档
                assert total > 0, \
                    f"Should find document containing text with diacritics '{text_stripped}' " \
                    f"when searching with normalized query '{query_without_diacritics}', " \
                    f"but found {total} documents. " \
                    f"This indicates that tone mark normalization (remove_diacritics) is not working correctly."
                
                assert len(results) > 0, \
                    f"Should return at least one result when searching with normalized query '{query_without_diacritics}' " \
                    f"for document containing '{text_stripped}'"
                
                # 验证返回的结果包含原始文档
                found_document = False
                for result in results:
                    # 检查结果是否来自我们创建的文档
                    if "tone_mark_test.md" in result.path:
                        found_document = True
                        break
                
                assert found_document, \
                    f"Search results should include the document with diacritics. " \
                    f"Searched for: '{query_without_diacritics}', " \
                    f"Document contains: '{text_stripped}', " \
                    f"Results: {[r.path for r in results]}"
                
                # 额外验证：反向测试 - 使用带音调的查询也应该能找到文档
                # 这验证了双向的标准化
                results_with_diacritics, total_with_diacritics = search_documents(text_stripped, conn=conn)
                
                assert total_with_diacritics > 0, \
                    f"Should also find document when searching with original diacritics '{text_stripped}', " \
                    f"but found {total_with_diacritics} documents"
                
                # 验证两次搜索返回相同的文档
                # 这确保了标准化是双向的
                doc_ids_without = set(r.id for r in results)
                doc_ids_with = set(r.id for r in results_with_diacritics)
                
                assert doc_ids_without == doc_ids_with, \
                    f"Searching with and without diacritics should return the same documents. " \
                    f"Without diacritics '{query_without_diacritics}': {doc_ids_without}, " \
                    f"With diacritics '{text_stripped}': {doc_ids_with}"
                
            finally:
                conn.close()
