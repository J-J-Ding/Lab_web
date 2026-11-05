// 全局搜索功能 - 实时搜索data文件夹内容
(function() {
  'use strict';

  // 页面内容配置
  const PAGE_CONFIGS = [
    { url: 'data/achievements/index.html', title: '成果汇总' },
    { url: 'data/news/index.html', title: '新闻动态' },
    { url: 'data/blogs/index.html', title: '技术博客' },
    { url: 'data/projects/index.html', title: '课题项目' },
    { url: 'data/papers/index.html', title: '发表论文' },
    // 论文详情页
    { url: 'data/papers/DBFNET/index.html', title: 'DBFNET论文详情' },
    { url: 'data/competitions/index.html', title: '学科竞赛' },
    { url: 'data/publications/index.html', title: '出版刊物' },
    { url: 'data/activities/index.html', title: '团建活动' },
    { url: 'data/members/index.html', title: '团队成员' },
    { url: 'data/graduates/index.html', title: '成员去向' }
  ];

  class GlobalSearch {
    constructor() {
      this.searchInput = document.getElementById('globalSearch');
      if (!this.searchInput) return;

      this.searchResultsBox = null;
      this.pageContentCache = null; // 缓存页面内容
      this.isLoading = false;
      this.init();
    }

    async init() {
      // 预加载所有页面内容
      await this.loadPageContents();

      // 输入事件
      this.searchInput.addEventListener('input', this.debounce(async (e) => {
        const query = this.searchInput.value.trim();
        if (query.length > 0) {
          await this.performSearch(query);
        } else {
          this.hideResults();
        }
      }, 300));

      // 回车键搜索
      this.searchInput.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
          const query = this.searchInput.value.trim();
          if (query.length > 0) {
            await this.performSearchAndNavigate(query);
          }
        }
      });

      // 点击搜索框
      this.searchInput.addEventListener('focus', async () => {
        if (this.searchInput.value.trim().length > 0) {
          await this.performSearch(this.searchInput.value.trim());
        }
      });

      // 点击搜索图标
      this.searchInput.parentElement.addEventListener('click', (e) => {
        if (e.target.classList.contains('search-icon')) {
          this.searchInput.focus();
        }
      });

      // 点击页面其他地方隐藏结果
      document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container') && !e.target.closest('.search-results')) {
          this.hideResults();
        }
      });

      // ESC键隐藏
      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
          this.hideResults();
        }
      });
    }

    // 加载所有页面内容
    async loadPageContents() {
      console.log('开始加载页面内容...');
      this.pageContentCache = [];

      // 先加载配置的页面
      for (const page of PAGE_CONFIGS) {
        try {
          const response = await fetch(page.url);
          if (response.ok) {
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            // 提取所有可搜索内容
            const searchItems = this.extractSearchItems(doc, page.url);

            this.pageContentCache.push({
              ...page,
              searchItems: searchItems
            });
          }
        } catch (error) {
          console.warn(`Failed to load page: ${page.url}`, error);
        }
      }

      // 动态发现data文件夹下的所有index.html页面（包括论文详情页）
      await this.discoverAdditionalPages();

      console.log('页面内容加载完成，共加载', this.pageContentCache.length, '个页面');
    }

    // 动态发现额外页面
    async discoverAdditionalPages() {
      const additionalUrls = [];

      // 发现论文子文件夹
      const knownPages = new Set(PAGE_CONFIGS.map(p => p.url));

      try {
        // 尝试加载论文详情页
        const paperDirs = ['DBFNET']; // 可以扩展这个列表，添加新论文时只需在这里添加目录名
        for (const dir of paperDirs) {
          const url = `data/papers/${dir}/index.html`;
          if (!knownPages.has(url)) {
            additionalUrls.push({
              url: url,
              title: `${dir} - 论文详情`
            });
          }
        }
      } catch (error) {
        console.warn('Failed to discover additional pages', error);
      }

      // 加载发现的额外页面
      for (const page of additionalUrls) {
        try {
          const response = await fetch(page.url);
          if (response.ok) {
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');

            const searchItems = this.extractSearchItems(doc, page.url);

            this.pageContentCache.push({
              ...page,
              searchItems: searchItems
            });

            console.log('发现额外页面:', page.url);
          }
        } catch (error) {
          console.warn(`Failed to load additional page: ${page.url}`, error);
        }
      }
    }

    // 获取所有已知论文目录
    // 当添加新论文时，只需在此数组中添加论文目录名即可
    getKnownPaperDirs() {
      return ['DBFNET'];
    }

    // 提取可搜索的项目
    extractSearchItems(doc, pageUrl) {
      const items = [];

      // 提取标题元素 (h1, h2, h3, h4)
      doc.querySelectorAll('h1, h2, h3, h4').forEach((h, index) => {
        const text = h.textContent.trim();
        if (text && text.length > 0) {
          items.push({
            type: '标题',
            text: text,
            element: 'h' + h.tagName.charAt(1),
            priority: 1
          });
        }
      });

      // 提取卡片标题（论文、项目、新闻等）
      doc.querySelectorAll('.achievement-card h3, .news-item h3, .research-card h3, .item-title, .paper-title, .project-title').forEach((el, index) => {
        const text = el.textContent.trim();
        if (text && text.length > 0) {
          items.push({
            type: '卡片',
            text: text,
            priority: 2
          });
        }
      });

      // 提取作者信息
      doc.querySelectorAll('.achievement-author, .item-author, .author, .paper-author').forEach((el) => {
        const text = el.textContent.trim();
        if (text && text.length > 0 && text !== '作者：' && !text.startsWith('作者:')) {
          items.push({
            type: '作者',
            text: text.replace(/^(作者|Author)[:：]\s*/, ''),
            priority: 3
          });
        }
      });

      // 提取列表项内容
      doc.querySelectorAll('li').forEach((el) => {
        const text = el.textContent.trim();
        if (text && text.length > 5) {
          items.push({
            type: '列表',
            text: text,
            priority: 4
          });
        }
      });

      // 提取描述文本
      doc.querySelectorAll('p, .description, .abstract').forEach((el) => {
        const text = el.textContent.trim();
        if (text && text.length > 10 && text.length < 200) {
          items.push({
            type: '描述',
            text: text,
            priority: 5
          });
        }
      });

      return items;
    }

    // 防抖函数
    debounce(func, wait) {
      let timeout;
      return (...args) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
      };
    }

    // 执行搜索
    async performSearch(query) {
      const results = await this.searchPages(query);
      this.displayResults(results, query);
    }

    // 搜索页面
    async searchPages(query) {
      const queryLower = query.toLowerCase().trim();

      // 如果页面内容还未加载，先加载
      if (!this.pageContentCache || this.pageContentCache.length === 0) {
        console.log('页面内容未加载，正在加载...');
        await this.loadPageContents();
      }

      console.log('开始搜索:', queryLower, '缓存页面数:', this.pageContentCache.length);

      const results = [];

      this.pageContentCache.forEach(page => {
        console.log('搜索页面:', page.title, '可搜索项数:', page.searchItems ? page.searchItems.length : 0);

        // 搜索所有可搜索项
        if (page.searchItems) {
          page.searchItems.forEach(item => {
            if (item.text && item.text.toLowerCase().includes(queryLower)) {
              results.push({
                pageTitle: page.title,
                pageUrl: page.url,
                itemType: item.type,
                matchText: item.text,
                priority: item.priority
              });
            }
          });
        }
      });

      // 按优先级排序，同优先级的按相关度排序
      results.sort((a, b) => {
        if (a.priority !== b.priority) {
          return a.priority - b.priority;
        }
        // 同优先级时，精确匹配优先
        const aExact = a.matchText.toLowerCase() === queryLower;
        const bExact = b.matchText.toLowerCase() === queryLower;
        if (aExact && !bExact) return -1;
        if (!aExact && bExact) return 1;
        return 0;
      });

      // 去重（同一页面同一内容只显示一次）
      const uniqueResults = [];
      const seen = new Set();
      for (const result of results) {
        const key = `${result.pageUrl}-${result.matchText}`;
        if (!seen.has(key)) {
          seen.add(key);
          uniqueResults.push(result);
        }
      }

      return uniqueResults;
    }

    // 显示搜索结果
    displayResults(results, query) {
      if (!this.searchResultsBox) {
        this.createResultsBox();
      }

      if (results.length === 0) {
        this.searchResultsBox.innerHTML = `
          <div class="search-no-results">
            <div class="no-results-icon">🔍</div>
            <h3>未找到相关内容</h3>
            <p class="no-results-keyword">搜索关键词: "${this.escapeHtml(query)}"</p>
            <p class="no-results-tip">试试搜索其他关键词</p>
          </div>
        `;
        this.showResults();
        return;
      }

      // 分组结果，按页面分组
      const groupedResults = {};
      results.forEach(result => {
        if (!groupedResults[result.pageTitle]) {
          groupedResults[result.pageTitle] = {
            url: result.pageUrl,
            items: []
          };
        }
        // 限制每个页面最多显示5条结果
        if (groupedResults[result.pageTitle].items.length < 5) {
          groupedResults[result.pageTitle].items.push(result);
        }
      });

      const resultsHtml = Object.entries(groupedResults).map(([pageTitle, data]) => `
        <div class="search-result-group">
          <div class="search-result-group-title">${this.escapeHtml(pageTitle)}</div>
          ${data.items.map(item => `
            <div class="search-result-item" data-url="${data.url}">
              <div class="search-result-main">
                <div class="search-result-text">${this.highlightMatch(item.matchText, query)}</div>
                <div class="search-result-meta">
                  <span class="search-result-type">${this.escapeHtml(item.itemType)}</span>
                </div>
              </div>
            </div>
          `).join('')}
        </div>
      `).join('');

      this.searchResultsBox.innerHTML = `
        <div class="search-results-header">
          <span>找到 ${results.length} 个结果</span>
          <span class="close-search" onclick="document.querySelector('.search-results').classList.remove('show')">×</span>
        </div>
        <div class="search-results-list">${resultsHtml}</div>
      `;

      this.showResults();
      this.attachResultClickHandlers();
    }

    // 高亮匹配文本
    highlightMatch(text, query) {
      if (!query) return text;
      const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
      return text.replace(regex, '<mark class="search-highlight">$1</mark>');
    }

    // 转义正则特殊字符
    escapeRegex(string) {
      return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // 转义HTML
    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }

    // 创建结果框
    createResultsBox() {
      this.searchResultsBox = document.createElement('div');
      this.searchResultsBox.id = 'searchResults';
      this.searchResultsBox.className = 'search-results';

      // 添加样式
      if (!document.getElementById('searchResultsStyles')) {
        const style = document.createElement('style');
        style.id = 'searchResultsStyles';
        style.textContent = `
          #searchResults {
            position: fixed;
            top: 90px;
            right: 10px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.2);
            max-width: 350px;
            width: 90%;
            max-height: 450px;
            overflow-y: auto;
            z-index: 1002;
            display: none;
            border: 1px solid var(--border-color);
          }
          #searchResults.show {
            display: block;
            animation: slideDown 0.3s ease;
          }
          @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
          }
          .search-results-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            background: var(--bg-secondary);
            border-radius: 12px 12px 0 0;
            position: sticky;
            top: 0;
          }
          .search-results-header span:first-child {
            font-weight: 600;
            color: var(--text-primary);
            font-size: 14px;
          }
          .close-search {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: rgba(0, 0, 0, 0.05);
            border: none;
            cursor: pointer;
            font-size: 18px;
            color: var(--text-light);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            line-height: 1;
          }
          .close-search:hover {
            background: rgba(0, 0, 0, 0.1);
            color: var(--text-primary);
          }
          .search-results-list {
            padding: 10px;
          }
          .search-result-group {
            margin-bottom: 12px;
          }
          .search-result-group:last-child {
            margin-bottom: 0;
          }
          .search-result-group-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--primary-color);
            padding: 8px 12px;
            background: var(--bg-secondary);
            border-radius: 6px;
            margin-bottom: 8px;
          }
          .search-result-item {
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid transparent;
            margin-bottom: 4px;
          }
          .search-result-item:hover {
            background: var(--bg-secondary);
            border-color: var(--primary-color);
          }
          .search-result-main {
            margin-bottom: 4px;
          }
          .search-result-text {
            font-size: 14px;
            font-weight: 500;
            color: var(--text-primary);
            margin-bottom: 6px;
            line-height: 1.4;
          }
          .search-result-meta {
            font-size: 11px;
            color: var(--text-light);
          }
          .search-result-type {
            background: var(--primary-color);
            color: white;
            padding: 2px 8px;
            border-radius: 10px;
            display: inline-block;
          }
          .search-highlight {
            background: #fef08a;
            padding: 2px 4px;
            border-radius: 3px;
            color: #000;
          }
          .search-no-results {
            padding: 30px 20px;
            text-align: center;
          }
          .no-results-icon {
            font-size: 48px;
            margin-bottom: 15px;
            opacity: 0.5;
          }
          .search-no-results h3 {
            color: var(--text-secondary);
            font-size: 16px;
            margin-bottom: 15px;
          }
          .no-results-keyword {
            color: var(--primary-color);
            font-weight: 500;
            background: var(--bg-secondary);
            padding: 8px 16px;
            border-radius: 6px;
            display: inline-block;
            margin-bottom: 20px;
          }
          .no-results-tip {
            color: var(--text-light);
            font-size: 13px;
            margin-bottom: 15px;
          }
          .suggested-keywords {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
          }
          .suggested-keyword {
            background: var(--primary-color);
            color: white;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s ease;
          }
          .suggested-keyword:hover {
            background: var(--primary-dark);
          }
          @media (max-width: 768px) {
            #searchResults {
              top: auto;
              bottom: 10px;
              right: 10px;
              left: 10px;
              max-height: 50vh;
            }
            .suggested-keywords {
              flex-direction: column;
              align-items: center;
            }
          }
        `;
        document.head.appendChild(style);
      }

      document.body.appendChild(this.searchResultsBox);
    }

    // 显示结果
    showResults() {
      this.searchResultsBox.classList.add('show');
    }

    // 隐藏结果
    hideResults() {
      if (this.searchResultsBox) {
        this.searchResultsBox.classList.remove('show');
      }
    }

    // 搜索并导航
    async performSearchAndNavigate(query) {
      const results = await this.searchPages(query);
      if (results.length > 0) {
        window.location.href = results[0].url;
      }
    }

    // 附加结果点击事件
    attachResultClickHandlers() {
      const items = this.searchResultsBox.querySelectorAll('.search-result-item');
      items.forEach(item => {
        item.addEventListener('click', (e) => {
          e.preventDefault();
          const url = item.dataset.url;
          if (url) {
            window.location.href = url;
          }
        });
      });
    }
  }

  // 页面加载完成后初始化
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new GlobalSearch());
  } else {
    new GlobalSearch();
  }
})();
