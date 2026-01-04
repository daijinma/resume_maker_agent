// 会话管理
import { appState, setSessionId, setAgentType } from './state.js';
import { formatToken, formatTime, generateSessionId } from './utils.js';
import { CONFIG } from './config.js';
import { loadSessionsFromBackend, loadSessionHistory, fetchSessionTokenStats, fetchSessionPendingQuestions, updateSessionName } from './api.js';

export function initSession(dom, message, todo) {
    return {
        // 创建会话项 HTML
        createSessionItem(sessId, sessionData) {
            const isActive = sessId === appState.sessionId;
            const tokenStats = sessionData?.token_stats || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
            const pendingCount = sessionData?.pending_questions?.length || 0;
            const lastUpdated = sessionData?.last_updated || new Date().toISOString();
            const sessionName = sessionData?.session_name;
            
            const item = document.createElement('div');
            item.className = `session-item p-3 mb-2 rounded-lg cursor-pointer border border-gray-200 ${isActive ? 'active' : ''}`;
            item.dataset.sessionId = sessId;
            
            const shortId = sessId.length > 20 ? sessId.substring(0, 20) + '...' : sessId;
            const displayName = sessionName || shortId;
            
            item.innerHTML = `
                <div class="flex items-start justify-between mb-2">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <div class="font-medium text-sm text-gray-800 truncate flex-1" title="${sessionName ? `${sessionName} (${sessId})` : sessId}">${displayName}</div>
                            <button class="edit-session-name-btn flex-shrink-0 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded p-1.5 transition-all" 
                                    onclick="event.stopPropagation(); session.editSessionName('${sessId}')" 
                                    title="点击编辑会话名称">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path>
                                </svg>
                            </button>
                        </div>
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
            
            // 不再自动创建当前会话，仅当 sessionId 存在且不在列表中时才创建
            // 这样只有在用户主动创建新会话或从 URL 加载会话时才会创建
            
            // 按创建时间倒序排序（最新的在前），active 状态不影响排序
            // 使用 created_at 作为主要排序键，确保切换session时位置不变
            const sortedSessionIds = sessionIds.sort((a, b) => {
                const sessionA = appState.sessions[a] || {};
                const sessionB = appState.sessions[b] || {};
                // 确保 created_at 存在
                const createdA = sessionA.created_at || sessionA.last_updated || '';
                const createdB = sessionB.created_at || sessionB.last_updated || '';
                // 倒序：最新的在前（按创建时间）
                const timeCompare = createdB.localeCompare(createdA);
                if (timeCompare !== 0) return timeCompare;
                // 如果时间相同，使用 session_id 作为稳定排序
                return b.localeCompare(a);
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
            
            // 更新 edit 按钮状态
            this.updateEditButtonState();
            
            // 更新待办事项显示
            todo.updateTodoDisplay();
            
            // 刷新新会话的统计信息
            await this.refreshCurrentSessionStats();
            
            // 加载新会话的历史记录
            await loadSessionHistory(appState.sessionId, (role, content, isJson, debug) => {
                message.appendMessage(role, content, isJson, debug);
            });
        },
        
        // 更新 edit 按钮状态
        updateEditButtonState() {
            if (dom.editSessionNameBtn) {
                if (appState.sessionId) {
                    dom.editSessionNameBtn.disabled = false;
                    dom.editSessionNameBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                } else {
                    dom.editSessionNameBtn.disabled = true;
                    dom.editSessionNameBtn.classList.add('opacity-50', 'cursor-not-allowed');
                }
            }
        },
        
        // 创建新会话
        createNewSession() {
            setSessionId(generateSessionId());
            const now = new Date().toISOString();
            appState.sessions[appState.sessionId] = {
                token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                pending_questions: [],
                pending_questions_raw: [],
                last_updated: now,
                created_at: now,
                agent_type: appState.currentAgentType
            };
            dom.chatContainer.innerHTML = '';
            
            // 更新输入框显示
            if (dom.sessionIdInput) {
                dom.sessionIdInput.value = appState.sessionId;
            }
            
            // 更新 edit 按钮状态
            this.updateEditButtonState();
            
            this.updateSessionList();
            todo.updateTodoDisplay();
        },
        
        // 更新会话的待办事项
        updateSessionPendingQuestions(sessId, pendingQuestions) {
            if (!appState.sessions[sessId]) {
                const now = new Date().toISOString();
                appState.sessions[sessId] = {
                    token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                    pending_questions: [],
                    pending_questions_raw: [],
                    resume_data: {},
                    last_updated: now,
                    created_at: now
                };
            } else {
                // 确保 created_at 存在，如果不存在则使用 last_updated 或当前时间
                if (!appState.sessions[sessId].created_at) {
                    appState.sessions[sessId].created_at = appState.sessions[sessId].last_updated || new Date().toISOString();
                }
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
            // 更新 last_updated（用于显示，但不影响排序）
            appState.sessions[sessId].last_updated = new Date().toISOString();
            this.updateSessionList();
            // 如果当前会话的待办事项更新了，更新显示
            if (sessId === appState.sessionId) {
                todo.updateTodoDisplay();
            }
        },
        
        // 更新会话的 resume_data
        updateSessionResumeData(sessId, resumeData) {
            if (!appState.sessions[sessId]) {
                const now = new Date().toISOString();
                appState.sessions[sessId] = {
                    token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                    pending_questions: [],
                    pending_questions_raw: [],
                    resume_data: {},
                    last_updated: now,
                    created_at: now
                };
            }
            // 合并 resume_data（保留已有数据，更新新数据）
            if (resumeData && typeof resumeData === 'object') {
                appState.sessions[sessId].resume_data = {
                    ...appState.sessions[sessId].resume_data,
                    ...resumeData
                };
            }
            // 如果当前会话的 resume_data 更新了，更新显示
            if (sessId === appState.sessionId) {
                todo.updateResumeDisplay();
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
        },
        
        // 编辑会话名称
        async editSessionName(sessId) {
            const sessionData = appState.sessions[sessId];
            const currentName = sessionData?.session_name || '';
            const sessionIdDisplay = sessId.length > 30 ? sessId.substring(0, 30) + '...' : sessId;
            
            // 创建 dialog overlay
            const dialog = document.createElement('div');
            dialog.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 animate-fade-in';
            dialog.style.animation = 'fadeIn 0.2s ease-out';
            
            // 创建 dialog 内容
            const dialogContent = document.createElement('div');
            dialogContent.className = 'bg-white rounded-lg shadow-xl w-96 max-w-full mx-4 transform transition-all';
            dialogContent.style.animation = 'slideUp 0.2s ease-out';
            
            dialogContent.innerHTML = `
                <div class="p-6">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold text-gray-800">编辑会话名称</h3>
                        <button class="text-gray-400 hover:text-gray-600 close-btn" title="关闭">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    <div class="mb-4">
                        <label class="block text-sm font-medium text-gray-700 mb-2">会话名称</label>
                        <input type="text" 
                               id="session-name-input" 
                               class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition" 
                               value="${currentName.replace(/"/g, '&quot;').replace(/'/g, '&#39;')}" 
                               placeholder="输入会话名称（留空则使用默认名称）"
                               maxlength="255">
                        <p class="text-xs text-gray-500 mt-1">会话 ID: ${sessionIdDisplay}</p>
                    </div>
                    <div class="flex justify-end gap-2">
                        <button class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-md transition cancel-btn">取消</button>
                        <button class="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 transition save-btn">保存</button>
                    </div>
                </div>
            `;
            
            dialog.appendChild(dialogContent);
            document.body.appendChild(dialog);
            
            const input = dialog.querySelector('#session-name-input');
            const cancelBtn = dialog.querySelector('.cancel-btn');
            const saveBtn = dialog.querySelector('.save-btn');
            const closeBtn = dialog.querySelector('.close-btn');
            
            // 关闭 dialog 的函数
            const closeDialog = () => {
                dialogContent.style.animation = 'slideDown 0.15s ease-in';
                dialog.style.animation = 'fadeOut 0.15s ease-in';
                setTimeout(() => {
                    if (dialog.parentNode) {
                        document.body.removeChild(dialog);
                    }
                }, 150);
            };
            
            // 聚焦输入框
            setTimeout(() => {
                input.focus();
                input.select();
            }, 100);
            
            // 取消按钮
            cancelBtn.onclick = closeDialog;
            
            // 关闭按钮
            closeBtn.onclick = closeDialog;
            
            // 保存按钮
            saveBtn.onclick = async () => {
                const newName = input.value.trim() || null;
                
                // 禁用按钮，防止重复提交
                saveBtn.disabled = true;
                saveBtn.textContent = '保存中...';
                saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
                
                try {
                    await updateSessionName(sessId, newName || '');
                    
                    // 更新本地状态
                    if (!appState.sessions[sessId]) {
                        appState.sessions[sessId] = {};
                    }
                    appState.sessions[sessId].session_name = newName;
                    
                    // 更新显示
                    this.updateSessionList();
                    
                    // 更新 edit 按钮状态（虽然通常不需要，但为了保险）
                    this.updateEditButtonState();
                    
                    // 关闭 dialog
                    closeDialog();
                } catch (error) {
                    // 恢复按钮状态
                    saveBtn.disabled = false;
                    saveBtn.textContent = '保存';
                    saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                    
                    // 显示错误提示
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'mt-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2';
                    errorMsg.textContent = `更新失败: ${error.message || '未知错误'}`;
                    dialogContent.querySelector('.mb-4').appendChild(errorMsg);
                    
                    // 3秒后自动移除错误提示
                    setTimeout(() => {
                        if (errorMsg.parentNode) {
                            errorMsg.remove();
                        }
                    }, 3000);
                }
            };
            
            // 按 Enter 保存，按 Escape 取消
            input.onkeydown = (e) => {
                if (e.key === 'Enter' && !saveBtn.disabled) {
                    saveBtn.click();
                } else if (e.key === 'Escape') {
                    closeDialog();
                }
            };
            
            // 点击背景关闭
            dialog.onclick = (e) => {
                if (e.target === dialog) {
                    closeDialog();
                }
            };
        }
    };
}

