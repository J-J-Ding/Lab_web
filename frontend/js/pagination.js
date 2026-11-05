// 通用分页功能
(function() {
  // 分页相关变量
  let currentPage = 1;
  const itemsPerPage = 5;
  let itemsData = [];

  // 初始化分页
  function initPagination(data) {
    itemsData = data;
    currentPage = 1;
    renderPagination();
  }

  // 获取当前页的项目
  function getCurrentPageItems() {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return itemsData.slice(startIndex, endIndex);
  }

  // 计算总页数
  function getTotalPages() {
    return Math.ceil(itemsData.length / itemsPerPage);
  }

  // 渲染分页控件
  function renderPagination() {
    const paginationContainer = document.getElementById('pagination');
    if (!paginationContainer) return;

    const totalPages = getTotalPages();

    if (totalPages <= 1) {
      paginationContainer.innerHTML = '';
      return;
    }

    let paginationHTML = `
      <button class="pagination-btn" onclick="goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>
        上一页
      </button>
      <div class="pagination-pages">
    `;

    for (let i = 1; i <= totalPages; i++) {
      paginationHTML += `
        <button class="pagination-page ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">
          ${i}
        </button>
      `;
    }

    paginationHTML += `
      </div>
      <button class="pagination-btn" onclick="goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>
        下一页
      </button>
      <span class="pagination-info">
        第 ${currentPage} / ${totalPages} 页，共 ${itemsData.length} 项
      </span>
    `;

    paginationContainer.innerHTML = paginationHTML;
  }

  // 跳转到指定页
  window.goToPage = function(page) {
    const totalPages = getTotalPages();

    if (page < 1 || page > totalPages) return;

    currentPage = page;

    // 重新渲染内容（调用各页面的 renderContent 函数）
    if (typeof window.renderContent === 'function') {
      window.renderContent();
    }

    // 重新渲染分页
    renderPagination();

    // 滚动到列表顶部
    const contentList = document.getElementById('contentList');
    if (contentList) {
      contentList.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // 获取当前页数据
  window.getCurrentPageItems = function() {
    return getCurrentPageItems();
  };

  // 暴露初始化函数
  window.initPagination = initPagination;
  window.getCurrentPage = function() {
    return currentPage;
  };
})();
