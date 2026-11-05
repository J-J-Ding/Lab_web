// 统一导航栏加载器 - 支持本地和 GitHub Pages
function loadNavbar() {
    const navbarContainer = document.getElementById('navbar-container');
    if (!navbarContainer) {
        console.warn('导航栏容器未找到');
        return;
    }

    // 获取当前页面信息
    const currentUrl = window.location.href;
    const currentPath = window.location.pathname;
    const pathSegments = currentPath.split('/').filter(Boolean);

    // 计算导航栏文件的相对路径
    const navbarPath = calculateNavbarPath(pathSegments);
    console.log('当前路径:', currentPath, '导航栏路径:', navbarPath);

    // 构建完整的导航栏 URL
    const navbarUrl = new URL(navbarPath, currentUrl).href;

    fetch(navbarUrl, { cache: 'no-store' })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(html => {
            navbarContainer.innerHTML = html;

            // 等待 DOM 渲染完成后修正链接
            requestAnimationFrame(() => {
                fixAllNavbarLinks(pathSegments);
                setActiveNavItem();
                initializeSearch();
            });
        })
        .catch(error => {
            console.error('加载导航栏失败:', error);
            navbarContainer.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #666; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; margin: 10px;">
                    <strong>导航栏加载失败</strong><br>
                    <small>路径: ${navbarPath}</small><br>
                    <small>错误: ${error.message}</small>
                </div>`;
        });
}

// 计算导航栏文件的相对路径
// 统一导航栏文件位置: data/navbar-unified.html
function calculateNavbarPath(pathSegments) {
    // 查找 data 目录的位置
    const dataIndex = pathSegments.indexOf('data');

    if (dataIndex === -1) {
        // 根目录页面，如: /index.html 或 /Lab_test/index.html
        return 'data/navbar-unified.html';
    }

    // data 目录或其子目录下的页面
    // 当前目录路径段（去掉文件名）
    const currentDirSegments = pathSegments.slice(0, -1);
    // data 目录路径段
    const dataDirSegments = pathSegments.slice(0, dataIndex + 1);

    // 计算从当前目录回退到 data 目录需要多少层
    const levelsBack = currentDirSegments.length - dataDirSegments.length;

    // 构建相对路径
    const relativePath = '../'.repeat(levelsBack) + 'navbar-unified.html';
    return relativePath;
}

// 修正导航栏中的所有链接路径
function fixAllNavbarLinks(pathSegments) {
    console.log('[fixAllNavbarLinks] 开始修正导航栏链接');

    // 查找 data 目录的位置
    const dataIndex = pathSegments.indexOf('data');

    // 修正 logo 链接
    const logoLink = document.querySelector('.nav-logo');
    if (logoLink) {
        const logoHref = calculateRelativePath('index.html', pathSegments, dataIndex);
        console.log('Logo 链接修正为:', logoHref);
        logoLink.setAttribute('href', logoHref);
    }

    // 修正 logo 图片
    const logoImg = document.querySelector('.nav-logo img');
    if (logoImg) {
        const logoSrc = calculateRelativePath('lab-logo.png', pathSegments, dataIndex);
        console.log('Logo 图片修正为:', logoSrc);
        logoImg.setAttribute('src', logoSrc);
    }

    // 修正所有导航链接（排除 logo）
    const navLinks = document.querySelectorAll('.nav-menu a:not(.nav-logo)');
    navLinks.forEach(link => {
        const originalHref = link.getAttribute('href');

        // 跳过外链和锚点
        if (!originalHref || originalHref.startsWith('#') || /^(https?:)?\/\//i.test(originalHref)) {
            return;
        }

        // 计算新的相对路径
        const newHref = calculateRelativePath(originalHref, pathSegments, dataIndex);
        link.setAttribute('href', newHref);
    });

    console.log('[fixAllNavbarLinks] 完成');
}

// 计算目标路径相对于当前页面的相对路径
function calculateRelativePath(targetPath, pathSegments, dataIndex) {
    // 如果没有 data 目录（根目录页面）
    if (dataIndex === -1) {
        // 目标已经在根目录下，直接返回
        return targetPath;
    }

    // 判断目标是否在 data 目录下
    const isDataTarget = targetPath.startsWith('data/');

    // 当前目录路径段（去掉文件名）
    const currentDirSegments = pathSegments.slice(0, -1);

    let levelsBack, finalTarget;

    if (isDataTarget) {
        // 目标在 data 目录下，回退到 data 目录即可
        const dataDirSegments = pathSegments.slice(0, dataIndex + 1);
        levelsBack = currentDirSegments.length - dataDirSegments.length;
        // 去掉 data/ 前缀
        finalTarget = targetPath.substring(5);
    } else {
        // 目标不在 data 目录下（如 index.html, lab-logo.png），回退到根目录
        // 需要减去 dataIndex（从 Lab_test/ 开始算起）
        levelsBack = currentDirSegments.length - dataIndex;
        finalTarget = targetPath;
    }

    // 构建相对路径
    const relativePath = '../'.repeat(levelsBack) + finalTarget;
    return relativePath;
}

// 设置当前页面的导航项为激活状态
function setActiveNavItem() {
    const navLinks = document.querySelectorAll('.nav-menu a');
    if (!navLinks.length) return;

    // 规范化路径
    function normalizePath(p) {
        p = decodeURIComponent(p || '/');
        p = p.replace(/\/index\.html?$/i, '/');
        p = p.replace(/\/+$/, '/');
        return p;
    }

    const currentPath = normalizePath(window.location.pathname);
    let bestLink = null;
    let bestScore = -1;

    navLinks.forEach(link => {
        link.classList.remove('active');

        const href = link.getAttribute('href');
        if (!href) return;

        // 跳过外链和锚点
        if (href.startsWith('#') || /^(https?:)?\/\//i.test(href)) return;

        // 使用当前页面 URL 作为基础来解析相对路径
        let linkPath;
        try {
            linkPath = normalizePath(new URL(href, window.location.href).pathname);
        } catch (e) {
            return;
        }

        // 计算匹配分数
        let score = -1;

        if (currentPath === linkPath) {
            // 完全匹配
            score = 1000000 + linkPath.length;
        } else {
            // 前缀匹配（用于子页面）
            const isPrefix =
                linkPath !== '/' &&
                currentPath.startsWith(linkPath) &&
                (linkPath.endsWith('/') || currentPath.charAt(linkPath.length) === '/');

            if (isPrefix) {
                score = linkPath.length;
            }

            // 首页兜底
            if (linkPath === '/' && currentPath === '/') {
                score = Math.max(score, 1);
            }
        }

        if (score > bestScore) {
            bestScore = score;
            bestLink = link;
        }
    });

    if (bestLink) {
        bestLink.classList.add('active');
        console.log('✅ 激活导航项:', bestLink.textContent.trim());
    }
}

// 初始化搜索功能
function initializeSearch() {
    const searchInput = document.getElementById('globalSearch');
    if (searchInput) {
        searchInput.addEventListener('input', function(e) {
            const searchTerm = e.target.value.trim();
            if (searchTerm.length > 2) {
                console.log('搜索关键词:', searchTerm);
                // 这里可以添加实际的搜索逻辑
            }
        });
    }
}

// 页面加载完成后加载导航栏
document.addEventListener('DOMContentLoaded', loadNavbar);
