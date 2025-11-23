#!/usr/bin/env python3
"""数据库初始化脚本

初始化数据库表结构并执行全量索引。

验证需求: 5.3, 5.4
使用方法:
    python scripts/init_db.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db import get_connection, init_db
from app.indexer import full_reindex
from app.config import settings


def main():
    """主函数：初始化数据库并执行全量索引"""
    print("=" * 60)
    print("Markdown 搜索引擎 - 数据库初始化")
    print("=" * 60)
    
    # 验证配置
    print(f"\n配置信息:")
    print(f"  Markdown 根目录: {settings.md_root}")
    print(f"  数据库路径: {settings.db_path}")
    
    # 检查 Markdown 根目录是否存在
    if not settings.md_root.exists():
        print(f"\n错误: Markdown 根目录不存在: {settings.md_root}")
        print("请检查配置文件或环境变量 MD_ROOT")
        sys.exit(1)
    
    print(f"\n步骤 1: 初始化数据库表结构...")
    try:
        conn = get_connection()
        init_db(conn)
        print("  ✓ 数据库表创建成功")
    except Exception as e:
        print(f"  ✗ 数据库初始化失败: {e}")
        sys.exit(1)
    
    print(f"\n步骤 2: 执行全量索引...")
    try:
        # 统计文件数量
        from app.indexer import iter_md_files
        md_files = list(iter_md_files(settings.md_root))
        total_files = len(md_files)
        print(f"  发现 {total_files} 个 Markdown 文件")
        
        # 执行全量重建
        full_reindex(conn)
        print(f"  ✓ 索引构建成功")
        
        # 验证索引结果
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM docs")
        indexed_count = cursor.fetchone()['count']
        print(f"  已索引 {indexed_count} 个文档")
        
    except Exception as e:
        print(f"  ✗ 索引构建失败: {e}")
        conn.close()
        sys.exit(1)
    finally:
        conn.close()
    
    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)
    print("\n可以使用以下命令启动服务器:")
    print("  uvicorn app.main:app --reload")
    print()


if __name__ == "__main__":
    main()
