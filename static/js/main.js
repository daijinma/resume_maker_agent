// 主入口文件
import { initDOM } from './dom.js';
import { initState } from './state.js';
import { appState, setAgentType } from './state.js';
import { getSessionIdFromURL } from './utils.js';
import { initMessage } from './message.js';
import { initSession } from './session.js';
import { initTodo } from './todo.js';
import { initChat } from './chat.js';
import { initUI } from './ui.js';
import { loadSessionHistory } from './api.js';

// 初始化应用
async function init() {
    // 初始化状态
    initState();
    
    // 初始化 DOM 引用
    const dom = initDOM();
    
    // 初始化各个模块
    const message = initMessage(dom);
    const todo = initTodo(dom);
    const session = initSession(dom, message, todo);
    const chat = initChat(dom, message, session);
    const ui = initUI(dom);
    
    // 将 session 对象暴露到全局作用域，以便在 HTML 中访问
    window.session = session;
    
    // 更新输入框显示当前 session_id（可能为 null）
    if (dom.sessionIdInput) {
        dom.sessionIdInput.value = appState.sessionId || '';
    }
    
    // 初始化会话列表和待办事项
    session.updateSessionList();
    session.updateEditButtonState();
    todo.updateTodoDisplay();
    todo.updateResumeDisplay();
    
    // 绑定事件
    dom.newSessionBtn.addEventListener('click', () => session.createNewSession());
    dom.refreshBtn?.addEventListener('click', () => session.refreshCurrentSessionStats());
    dom.sidebarToggle?.addEventListener('click', () => ui.toggleSidebar());
    dom.sidebarToggleMobile?.addEventListener('click', () => ui.toggleSidebar());
    dom.todoToggle?.addEventListener('click', () => todo.toggleTodoList());
    dom.resumeToggle?.addEventListener('click', () => todo.toggleResumeList());
    
    // 绑定编辑会话名称按钮
    if (dom.editSessionNameBtn) {
        dom.editSessionNameBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (appState.sessionId) {
                session.editSessionName(appState.sessionId);
            } else {
                console.warn('没有当前会话，无法编辑会话名称');
            }
        });
    } else {
        console.error('编辑会话名称按钮未找到');
    }
    
    // 绑定加载会话按钮
    if (dom.loadSessionBtn) {
        dom.loadSessionBtn.addEventListener('click', () => {
            const sessId = dom.sessionIdInput.value.trim();
            if (sessId) {
                session.loadSessionById(sessId);
            }
        });
    }
    
    // 绑定输入框回车事件
    if (dom.sessionIdInput) {
        dom.sessionIdInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const sessId = dom.sessionIdInput.value.trim();
                if (sessId) {
                    session.loadSessionById(sessId);
                }
            }
        });
    }
    
    // 绑定发送消息事件
    dom.sendBtn.addEventListener('click', () => chat.sendMessage());
    dom.userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') chat.sendMessage();
    });
    
    // 从后端加载会话列表
    await session.loadSessionsFromBackend();
    
    // 如果 URL 中有 session_id，加载历史记录
    const urlSessionId = getSessionIdFromURL();
    if (urlSessionId && urlSessionId === appState.sessionId) {
        // 加载历史记录
        await loadSessionHistory(appState.sessionId, (role, content, isJson, debug) => {
            message.appendMessage(role, content, isJson, debug);
        });
        
        // 根据会话的 agent_type 设置 select
        const sessionData = appState.sessions[appState.sessionId];
        if (sessionData && sessionData.agent_type && dom.agentSelect) {
            dom.agentSelect.value = sessionData.agent_type;
            setAgentType(sessionData.agent_type);
        }
    }
    
    // 初始化时刷新当前会话的统计
    await session.refreshCurrentSessionStats();
}

// 启动应用
init().catch(console.error);

