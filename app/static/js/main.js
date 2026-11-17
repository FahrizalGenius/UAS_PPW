/**
 * PPW-PageRank Main JavaScript
 * Handles sidebar toggling, UI interactions, form resets, and notifications.
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Sidebar Toggle Logic
    const sidebarToggle = document.getElementById('sidebarToggle');
    const body = document.body;

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function (e) {
            e.preventDefault();
            if (window.innerWidth >= 992) {
                // Desktop toggle (mini sidebar)
                body.classList.toggle('sidebar-toggled');
            } else {
                // Mobile toggle (drawer)
                body.classList.toggle('sidebar-open');
            }
        });
    }

    // Close mobile sidebar when clicking backdrop
    document.addEventListener('click', function (e) {
        if (window.innerWidth < 992 && body.classList.contains('sidebar-open')) {
            const sidebar = document.getElementById('sidebar');
            if (sidebar && !sidebar.contains(e.target) && !sidebarToggle.contains(e.target)) {
                body.classList.remove('sidebar-open');
            }
        }
    });

    // 2. Initialize Bootstrap Tooltips if Bootstrap is loaded
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // 3. Form Reset confirmation/handler for Web Crawling Form
    const btnResetCrawler = document.getElementById('btnResetCrawler');
    const crawlForm = document.getElementById('crawlForm');

    if (btnResetCrawler && crawlForm) {
        btnResetCrawler.addEventListener('click', function () {
            crawlForm.reset();
            const startUrlInput = document.getElementById('start_url');
            const maxPagesInput = document.getElementById('max_pages');
            if (startUrlInput) startUrlInput.value = 'https://trunojoyo.ac.id/';
            if (maxPagesInput) maxPagesInput.value = '300';
        });
    }
});
