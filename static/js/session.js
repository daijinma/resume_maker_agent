// 会话管理
import { appState, setSessionId, setAgentType } from './state.js';
import { formatToken, formatTime, generateSessionId } from './utils.js';
import { CONFIG } from './config.js';
import { loadSessionsFromBackend, loadSessionHistory, fetchSessionTokenStats, fetchSessionPendingQuestions } from './api.js';

export function initSession(dom, message, todo) {
    return {
        // 创建会话项 HTML
        createSessionItem(sessId, sessionData) {
            const isActive = sessId === appState.sessionId;
            const tokenStats = sessionData?.token_stats || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
            const pendingCount = sessionData?.pending_questions?.length || 0;
            const lastUpdated = sessionData?.last_updated || new Date().toISOString();
            
            const item = document.createElement('div');
            item.className = `session-item p-3 mb-2 rounded-lg cursor-pointer border border-gray-200 ${isActive ? 'active' : ''}`;
            item.dataset.sessionId = sessId;
            
            const shortId = sessId.length > 20 ? sessId.substring(0, 20) + '...' : sessId;
            
            item.innerHTML = `
                <div class="flex items-start justify-between mb-2">
                    <div class="flex-1 min-w-0">
                        <div class="font-medium text-sm text-gray-800 truncate" title="${sessId}">${shortId}</div>
                        <div class="text-xs text-gray-500 mt-1">${formatTime(lastUpdated)}</div>
                    </div>
                </div>
                <div class="space-y-1">
                    <div class="text-xs text-gray-600">
                        <span class="font-medium">Token:</span> 
                        <span class="text-indigo-600">${formatToken(tokenStats.input_tokens)} / ${formatToken(tokenStats.output_tokens)} / ${formatToken(tokenStats.total_tokens)}</span>
                    </div>
                    ${pendingCount > 0 ? `
                        <div class="text-xs text-amber-600 flex items-center">
                            <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"></path>
                            </svg>
                            ${pendingCount} 个待办
                        </div>
                    ` : ''}
                </div>
            `;
            
            item.onclick = () => this.switchSession(sessId);
            return item;
        },
        
        // 更新会话列表显示
        updateSessionList() {
            dom.sessionList.innerHTML = '';
            const sessionIds = Object.keys(appState.sessions);
            
            // 确保当前会话在列表中
            if (!appState.sessions[appState.sessionId]) {
                appState.sessions[appState.sessionId] = {
                    token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                    pending_questions: [],
                    last_updated: new Date().toISOString(),
                    agent_type: appState.currentAgentType
                };
            }
            
            // 按 last_updated 倒序排序（最新的在前）
            const sortedSessionIds = sessionIds.sort((a, b) => {
                const timeA = appState.sessions[a]?.last_updated || '';
                const timeB = appState.sessions[b]?.last_updated || '';
                return timeB.localeCompare(timeA);
            });
            
            sortedSessionIds.forEach(sessId => {
                const item = this.createSessionItem(sessId, appState.sessions[sessId]);
                dom.sessionList.appendChild(item);
            });
        },
        
        // 切换会话
        async switchSession(newSessionId) {
            if (newSessionId === appState.sessionId) return;
            
            setSessionId(newSessionId);
            dom.chatContainer.innerHTML = '';
            
            // 更新输入框显示
            if (dom.sessionIdInput) {
                dom.sessionIdInput.value = appState.sessionId;
            }
            
            // 获取会话信息并设置 agent_type
            const sessionData = appState.sessions[appState.sessionId];
            if (sessionData?.agent_type) {
                if (dom.agentSelect) {
                    dom.agentSelect.value = sessionData.agent_type;
                    setAgentType(sessionData.agent_type);
                }
            }
            
            // 更新会话列表高亮
            this.updateSessionList();
            
            // 更新待办事项显示
            todo.updateTodoDisplay();
            
            // 刷新新会话的统计信息
            await this.refreshCurrentSessionStats();
            
            // 加载新会话的历史记录
            await loadSessionHistory(appState.sessionId, (role, content, isJson, debug) => {
                message.appendMessage(role, content, isJson, debug);
            });
        },
        
        // 创建新会话
        createNewSession() {
            setSessionId(generateSessionId());
            appState.sessions[appState.sessionId] = {
                token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                pending_questions: [],
                pending_questions_raw: [],
                last_updated: new Date().toISOString(),
                agent_type: appState.currentAgentType
            };
            dom.chatContainer.innerHTML = '';
            
            // 更新输入框显示
            if (dom.sessionIdInput) {
                dom.sessionIdInput.value = appState.sessionId;
            }
            
            this.updateSessionList();
            todo.updateTodoDisplay();
        },
        
        // 更新会话的待办事项
        updateSessionPendingQuestions(sessId, pendingQuestions) {
            if (!appState.sessions[sessId]) {
                appState.sessions[sessId] = {
                    token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                    pending_questions: [],
                    pending_questions_raw: [],
                    last_updated: new Date().toISOString()
                };
            }
            // 保存原始数据（用于显示）
            if (Array.isArray(pendingQuestions)) {
                appState.sessions[sessId].pending_questions_raw = pendingQuestions;
                // 同时保存简化格式（用于会话列表显示数量）
                appState.sessions[sessId].pending_questions = pendingQuestions.map(q => {
                    if (typeof q === 'string') {
                        return q;
                    } else if (q && typeof q === 'object' && q.content) {
                        return q.content;
                    }
                    return String(q);
                });
            } else {
                appState.sessions[sessId].pending_questions = [];
                appState.sessions[sessId].pending_questions_raw = [];
            }
            appState.sessions[sessId].last_updated = new Date().toISOString();
            this.updateSessionList();
            // 如果当前会话的待办事项更新了，更新显示
            if (sessId === appState.sessionId) {
                todo.updateTodoDisplay();
            }
        },
        
        // 刷新当前会话的统计信息
        async refreshCurrentSessionStats() {
            if (!appState.sessionId) return;
            await Promise.all([
                fetchSessionTokenStats(appState.sessionId, () => this.updateSessionList()),
                fetchSessionPendingQuestions(appState.sessionId, (sessId, questions) => {
                    this.updateSessionPendingQuestions(sessId, questions);
                })
            ]);
        },
        
        // 从后端加载会话列表
        async loadSessionsFromBackend() {
            await loadSessionsFromBackend(() => this.updateSessionList());
        },
        
        // 加载指定 session_id 的会话
        async loadSessionById(sessId) {
            if (!sessId || sessId.trim() === '') {
                alert('请输入有效的 Session ID');
                return;
            }
            
            const trimmedSessId = sessId.trim();
            // 如果会话不在本地 sessions 中，先获取会话信息
            if (!appState.sessions[trimmedSessId]) {
                await this.loadSessionsFromBackend();
            }
            await this.switchSession(trimmedSessId);
        }
    };
}

