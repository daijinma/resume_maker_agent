// DOM 元素引用管理
export function initDOM() {
    return {
        chatContainer: document.getElementById('chat-container'),
        userInput: document.getElementById('user-input'),
        sendBtn: document.getElementById('send-btn'),
        agentSelect: document.getElementById('agent-select'),
        sessionList: document.getElementById('session-list'),
        newSessionBtn: document.getElementById('new-session-btn'),
        refreshBtn: document.getElementById('refresh-btn'),
        sidebarToggle: document.getElementById('sidebar-toggle'),
        sidebarToggleMobile: document.getElementById('sidebar-toggle-mobile'),
        sidebar: document.getElementById('sidebar'),
        sessionIdInput: document.getElementById('session-id-input'),
        loadSessionBtn: document.getElementById('load-session-btn'),
        todoContainer: document.getElementById('todo-container'),
        todoList: document.getElementById('todo-list'),
        todoToggle: document.getElementById('todo-toggle'),
        todoToggleText: document.getElementById('todo-toggle-text'),
        resumeContainer: document.getElementById('resume-container'),
        resumeContent: document.getElementById('resume-content'),
        resumeToggle: document.getElementById('resume-toggle'),
        resumeToggleText: document.getElementById('resume-toggle-text'),
        editSessionNameBtn: document.getElementById('edit-session-name-btn')
    };
}

