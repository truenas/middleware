function navigateToVersion(version) {
    document.location = "../" + version;
}

// Maintain sidebar scroll position across page navigation
(function() {
    const STORAGE_KEY = 'truenas_api_sidebar_scroll';
    
    // Save scroll position before page unload
    function saveScrollPosition() {
        const sidebar = document.querySelector('.sphinxsidebar');
        if (sidebar) {
            sessionStorage.setItem(STORAGE_KEY, sidebar.scrollTop);
        }
    }
    
    // Restore scroll position after page load
    function restoreScrollPosition() {
        const sidebar = document.querySelector('.sphinxsidebar');
        const savedPosition = sessionStorage.getItem(STORAGE_KEY);
        
        if (sidebar && savedPosition) {
            sidebar.scrollTop = parseInt(savedPosition, 10);
        }
    }
    
    // Setup event listeners
    window.addEventListener('beforeunload', saveScrollPosition);
    
    // Restore position when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', restoreScrollPosition);
    } else {
        restoreScrollPosition();
    }
    
    // Also save position when sidebar links are clicked
    document.addEventListener('click', function(e) {
        const target = e.target;
        if (target.matches('.sphinxsidebar a')) {
            saveScrollPosition();
        }
    });
})();
