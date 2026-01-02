// 工具函数

// URL 相关
export function getSessionIdFromURL() {
    const params = new URLSearchParams(window.location.search);
    return params.get('session_id');
}

export function updateURLSessionId(sessId) {
    const url = new URL(window.location);
    if (sessId) {
        url.searchParams.set('session_id', sessId);
    } else {
        url.searchParams.delete('session_id');
    }
    window.history.replaceState({}, '', url);
}

// Token 格式化函数
export function formatToken(count) {
    if (count === 0) return '0';
    if (count < 1000) return count.toString();
    if (count < 1000000) {
        const k = (count / 1000).toFixed(1);
        return k.endsWith('.0') ? k.slice(0, -2) + 'K' : k + 'K';
    }
    const m = (count / 1000000).toFixed(1);
    return m.endsWith('.0') ? m.slice(0, -2) + 'M' : m + 'M';
}

// 时间格式化
export function formatTime(dateString) {
    if (!dateString) return '刚刚';
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return '刚刚';
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}天前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

// 生成随机 session ID
export function generateSessionId() {
    return 'debug_session_' + Math.random().toString(36).substring(2, 15);
}

