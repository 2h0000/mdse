#!/usr/bin/env python
"""测试高亮功能的脚本"""

import re

def extract_keywords(query):
    """提取查询中的所有关键词"""
    keywords = []
    current_word = []
    
    for char in query:
        is_cjk = '\u4e00' <= char <= '\u9fff'  # 中文字符
        is_alpha = char.isalnum()  # 字母或数字
        
        if is_cjk:
            # 中文字符单独作为一个关键词
            if current_word:
                keywords.append(''.join(current_word))
                current_word = []
            keywords.append(char)
        elif is_alpha:
            # 英文字符累积成单词
            current_word.append(char)
        else:
            # 分隔符，结束当前单词
            if current_word:
                keywords.append(''.join(current_word))
                current_word = []
    
    # 添加最后一个单词
    if current_word:
        keywords.append(''.join(current_word))
    
    # 去重并过滤空字符串
    keywords = list(set([k for k in keywords if k and len(k) > 0]))
    return keywords


def test_queries():
    """测试不同的查询"""
    test_cases = [
        "机器学习",
        "机器 学习",
        "Python 机器学习",
        "深度学习 算法",
        "machine learning",
        "算法",
    ]
    
    print("=" * 60)
    print("关键词提取测试")
    print("=" * 60)
    
    for query in test_cases:
        keywords = extract_keywords(query)
        print(f"\n查询: '{query}'")
        print(f"提取的关键词: {keywords}")
        print(f"关键词数量: {len(keywords)}")


def test_highlight():
    """测试高亮功能"""
    html_content = """
    <h1>机器学习入门</h1>
    <p>机器学习是人工智能的一个分支。深度学习是机器学习的子领域。</p>
    <p>Python 是机器学习最常用的编程语言。</p>
    <p>常见的机器学习算法包括：决策树、随机森林、神经网络等。</p>
    """
    
    query = "机器 学习"
    keywords = extract_keywords(query)
    
    print("\n" + "=" * 60)
    print("高亮测试")
    print("=" * 60)
    print(f"\n原始查询: '{query}'")
    print(f"提取的关键词: {keywords}")
    print(f"\n原始 HTML:")
    print(html_content)
    
    # 模拟高亮
    result = html_content
    for keyword in keywords:
        escaped_keyword = re.escape(keyword)
        if len(keyword) == 1 and '\u4e00' <= keyword <= '\u9fff':
            pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)
        else:
            pattern = re.compile(f'\\b({escaped_keyword})\\b', re.IGNORECASE)
        result = pattern.sub(r'<mark>\1</mark>', result)
    
    print(f"\n高亮后的 HTML:")
    print(result)
    
    # 统计高亮数量
    mark_count = result.count('<mark>')
    print(f"\n高亮标记数量: {mark_count}")


if __name__ == '__main__':
    test_queries()
    test_highlight()
