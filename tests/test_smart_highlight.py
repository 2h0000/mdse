#!/usr/bin/env python
"""测试智能优先级高亮功能"""

import re

def smart_highlight(html_content, query):
    """智能高亮函数"""
    
    # 智能提取关键词，按优先级排序
    keywords_by_priority = []
    
    # 1. 完整查询（最高优先级）
    full_query = ' '.join(query.split())
    if full_query:
        keywords_by_priority.append(('full', full_query))
    
    # 2. 提取词组片段（中等优先级）
    phrases = []
    current_phrase = []
    
    for char in query:
        if char in ' \t\n\r':
            if current_phrase:
                phrase = ''.join(current_phrase)
                if len(phrase) > 1:
                    phrases.append(phrase)
                current_phrase = []
        else:
            current_phrase.append(char)
    
    if current_phrase:
        phrase = ''.join(current_phrase)
        if len(phrase) > 1:
            phrases.append(phrase)
    
    for phrase in phrases:
        keywords_by_priority.append(('phrase', phrase))
    
    # 3. 提取单个字符（最低优先级）
    single_chars = []
    for char in query:
        is_cjk = '\u4e00' <= char <= '\u9fff'
        if is_cjk:
            single_chars.append(char)
    
    single_chars = list(set(single_chars))
    for char in single_chars:
        keywords_by_priority.append(('char', char))
    
    print(f"\n关键词优先级列表:")
    for priority, keyword in keywords_by_priority:
        print(f"  [{priority:6}] '{keyword}'")
    
    # 使用占位符
    MARK_START = '___MARK_START___'
    MARK_END = '___MARK_END___'
    
    # 先高亮完整查询和词组
    for priority, keyword in keywords_by_priority:
        if priority in ['full', 'phrase']:
            escaped_keyword = re.escape(keyword)
            has_chinese = any('\u4e00' <= c <= '\u9fff' for c in keyword)
            
            if has_chinese:
                pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)
            else:
                pattern = re.compile(f'\\b({escaped_keyword})\\b', re.IGNORECASE)
            
            html_content = pattern.sub(f'{MARK_START}\\1{MARK_END}', html_content)
    
    # 检查是否有高亮
    has_highlights = MARK_START in html_content
    
    # 如果没有找到完整匹配，才使用单字符高亮
    if not has_highlights:
        print("\n⚠️  未找到完整匹配，使用单字符高亮")
        for priority, keyword in keywords_by_priority:
            if priority == 'char':
                escaped_keyword = re.escape(keyword)
                pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)
                html_content = pattern.sub(f'{MARK_START}\\1{MARK_END}', html_content)
    else:
        print("\n✅ 找到完整匹配，不使用单字符高亮")
    
    # 替换占位符
    html_content = html_content.replace(MARK_START, '<mark>')
    html_content = html_content.replace(MARK_END, '</mark>')
    
    return html_content


def test_case(name, query, content):
    """测试用例"""
    print("\n" + "=" * 70)
    print(f"测试: {name}")
    print("=" * 70)
    print(f"搜索: '{query}'")
    print(f"\n原始内容:\n{content}")
    
    result = smart_highlight(content, query)
    
    print(f"\n高亮结果:\n{result}")
    
    # 统计高亮数量
    mark_count = result.count('<mark>')
    print(f"\n高亮标记数量: {mark_count}")


if __name__ == '__main__':
    # 测试 1：文档包含完整关键词
    test_case(
        "包含完整关键词",
        "机器学习",
        "机器学习是人工智能的一个分支。深度学习也是机器学习的子领域。"
    )
    
    # 测试 2：文档不包含完整关键词
    test_case(
        "不包含完整关键词",
        "机器学习",
        "这篇文章讨论了机器人技术和学习算法。"
    )
    
    # 测试 3：搜索多个词
    test_case(
        "搜索多个词（都存在）",
        "机器 学习",
        "机器学习是人工智能的分支。"
    )
    
    # 测试 4：搜索多个词（部分存在）
    test_case(
        "搜索多个词（部分存在）",
        "深度 学习",
        "机器学习是人工智能的分支。"
    )
    
    # 测试 5：英文搜索
    test_case(
        "英文搜索",
        "machine learning",
        "Machine Learning is a subset of AI. The machine is learning."
    )
    
    # 测试 6：中英文混合
    test_case(
        "中英文混合",
        "Python 机器学习",
        "Python 是机器学习最常用的语言。学习 Python 很重要。"
    )
