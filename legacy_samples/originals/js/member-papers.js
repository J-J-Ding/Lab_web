// 成员论文自动加载系统
// 在成员详情页中，自动显示该成员参与的所有论文

class MemberPapersLoader {
    constructor(memberId) {
        this.memberId = memberId;
        this.papersContainer = document.getElementById('member-papers');
        if (!this.papersContainer) return;
        this.loadPapers();
    }

    async loadPapers() {
        try {
            // 获取所有论文文件夹
            const papersResponse = await fetch('../data/papers/index.html');
            const papersHtml = await papersResponse.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(papersHtml, 'text/html');

            // 获取所有论文卡片的链接
            const paperLinks = doc.querySelectorAll('.item-card .item-link[href*="index.html"]');
            const paperCards = doc.querySelectorAll('.item-card');

            let hasPapers = false;

            for (let i = 0; i < paperLinks.length; i++) {
                const paperUrl = paperLinks[i].getAttribute('href');
                if (!paperUrl.includes('index.html')) continue;

                    // 获取论文详情页URL
                    const paperDetailUrl = paperUrl.startsWith('.') ? paperUrl : '../../../' + paperUrl;

                try {
                    const response = await fetch(paperDetailUrl);
                    const html = await response.text();
                    const paperDoc = parser.parseFromString(html, 'text/html');

                    // 检查该论文是否包含当前成员
                    const authors = paperDoc.querySelectorAll('.paper-author-link');
                    let isAuthor = false;

                    authors.forEach(author => {
                        const authorHref = author.getAttribute('href');
                        if (authorHref && authorHref.includes('#' + this.memberId)) {
                            isAuthor = true;
                        }
                    });

                    if (isAuthor) {
                        hasPapers = true;
                        this.addPaperCard(paperDoc, paperDetailUrl);
                    }
                } catch (e) {
                    console.error('Error loading paper:', e);
                }
            }

            if (!hasPapers) {
                this.papersContainer.innerHTML = '<div class="empty-state"><p>暂无发表论文</p></div>';
            }
        } catch (error) {
            console.error('Error loading papers:', error);
            this.papersContainer.innerHTML = '<div class="empty-state"><p>加载失败，请稍后重试</p></div>';
        }
    }

    addPaperCard(paperDoc, paperUrl) {
        const title = paperDoc.querySelector('.paper-title')?.textContent || '未命名论文';
        const meta = Array.from(paperDoc.querySelectorAll('.paper-meta-value'))
            .map(el => el.textContent).join(' | ');

        const abstract = paperDoc.querySelector('.paper-abstract')?.textContent || '';
        const frameworkImg = paperDoc.querySelector('.paper-framework-image')?.getAttribute('src');

        const paperCard = document.createElement('div');
        paperCard.className = 'paper-item';
        paperCard.innerHTML = `
            <div class="paper-preview">
                <img src="${frameworkImg ? '../../../' + frameworkImg : '../../../../lab-logo.png'}" alt="${title}" onerror="this.src='../../../../lab-logo.png'">
            </div>
            <div class="paper-info">
                <h3><a href="${paperUrl}">${title}</a></h3>
                <div class="paper-meta">${meta}</div>
                <div class="paper-abstract">${abstract.substring(0, 150)}...</div>
            </div>
        `;

        this.papersContainer.appendChild(paperCard);
    }
}

// 页面加载完成后自动初始化
document.addEventListener('DOMContentLoaded', function() {
    // 从URL中获取成员ID
    const pathParts = window.location.pathname.split('/');
    const memberFolder = pathParts[pathParts.length - 2];
    const memberId = memberFolder; // 使用文件夹名作为成员ID

    if (memberId) {
        new MemberPapersLoader(memberId);
    }
});
