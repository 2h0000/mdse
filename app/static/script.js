/**
 * Markdown 搜索引擎前端交互脚本
 * 
 * 提供搜索结果交互和文档预览功能
 */

/**
 * 初始化搜索页面交互
 */
function initSearchPage() {
    // 为所有文档链接添加点击事件
    const docLinks = document.querySelectorAll('.doc-link');
    docLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const docId = this.getAttribute('data-doc-id');
            showDocumentPreview(docId);
        });
    });

    // 为结果项添加点击事件（点击整个卡片也能预览）
    const resultItems = document.querySelectorAll('.result-item');
    resultItems.forEach(item => {
        item.addEventListener('click', function(e) {
            // 如果点击的是链接，让链接处理
            if (e.target.classList.contains('doc-link')) {
                return;
            }
            const docId = this.getAttribute('data-doc-id');
            showDocumentPreview(docId);
        });
    });

    // 关闭预览按钮
    const closeBtn = document.getElementById('close-preview');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeDocumentPreview);
    }

    // ESC 键关闭预览
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeDocumentPreview();
        }
    });
}

/**
 * 显示文档预览
 * @param {string|number} docId - 文档 ID
 */
async function showDocumentPreview(docId) {
    const preview = document.getElementById('doc-preview');
    const previewContent = document.getElementById('preview-content');
    const previewTitle = document.getElementById('preview-title');

    if (!preview || !previewContent) {
        console.error('Preview elements not found');
        return;
    }

    // 显示预览面板
    preview.classList.remove('hidden');

    // 显示加载状态
    previewContent.innerHTML = '<p class="loading">加载中...</p>';
    previewTitle.textContent = '文档预览';

    try {
        // 获取当前搜索关键词（从搜索框或 URL 参数）
        const searchInput = document.getElementById('search-input');
        const searchQuery = searchInput ? searchInput.value : '';
        
        // 构建 URL，如果有搜索关键词则添加到参数中
        let url = `/docs/${docId}`;
        if (searchQuery && searchQuery.trim()) {
            url += `?q=${encodeURIComponent(searchQuery.trim())}`;
        }
        
        // 获取文档内容
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const html = await response.text();
        
        // 显示文档内容
        previewContent.innerHTML = html;

        // 更新标题（从内容中提取第一个 h1 或使用默认标题）
        const firstH1 = previewContent.querySelector('h1');
        if (firstH1) {
            previewTitle.textContent = firstH1.textContent;
        }

        // 平滑滚动到顶部
        previewContent.scrollTop = 0;
        
        // 如果有高亮的内容，滚动到第一个高亮位置
        const firstMark = previewContent.querySelector('mark');
        if (firstMark) {
            firstMark.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }

    } catch (error) {
        console.error('Failed to load document:', error);
        previewContent.innerHTML = `
            <div class="error-message" style="text-align: center; padding: 2rem; color: #ef4444;">
                <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">😔 加载失败</p>
                <p style="color: #64748b; font-size: 0.9rem;">无法加载文档内容，请稍后重试</p>
            </div>
        `;
    }
}

/**
 * 关闭文档预览
 */
function closeDocumentPreview() {
    const preview = document.getElementById('doc-preview');
    if (preview) {
        preview.classList.add('hidden');
    }
}

/**
 * 高亮搜索关键词（如果需要额外的客户端高亮）
 * @param {string} text - 要高亮的文本
 * @param {string} query - 搜索查询
 * @returns {string} 高亮后的 HTML
 */
function highlightText(text, query) {
    if (!query) return text;
    
    const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
    return text.replace(regex, '<mark>$1</mark>');
}

/**
 * 转义正则表达式特殊字符
 * @param {string} str - 要转义的字符串
 * @returns {string} 转义后的字符串
 */
function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * 防抖函数
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// 导出函数供全局使用
window.initSearchPage = initSearchPage;
window.showDocumentPreview = showDocumentPreview;
window.closeDocumentPreview = closeDocumentPreview;
