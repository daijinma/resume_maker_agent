// UI 交互管理
export function initUI(dom) {
    return {
        // 侧边栏切换
        toggleSidebar() {
            dom.sidebar.classList.toggle('open');
        }
    };
}

