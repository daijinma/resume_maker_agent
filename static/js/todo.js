// 待办事项管理
import { appState } from './state.js';

export function initTodo(dom) {
    return {
        // 更新待办事项显示
        updateTodoDisplay() {
            if (!appState.sessionId || !appState.sessions[appState.sessionId]) {
                dom.todoContainer.classList.add('hidden');
                return;
            }
            
            const sessionData = appState.sessions[appState.sessionId];
            const pendingQuestions = sessionData.pending_questions_raw || sessionData.pending_questions || [];
            
            // 过滤掉已回答的问题（只显示未回答的问题）
            const unansweredQuestions = pendingQuestions.filter(q => {
                if (typeof q === 'string') {
                    return true;  // 字符串格式的问题，默认显示
                }
                if (q && typeof q === 'object') {
                    // 检查 answered 字段，如果为 true 或存在 answered_at，则过滤掉
                    return !q.answered && !q.answered_at;
                }
                return true;
            });
            
            if (unansweredQuestions.length === 0) {
                dom.todoContainer.classList.add('hidden');
                return;
            }
            
            // 显示待办容器
            dom.todoContainer.classList.remove('hidden');
            
            // 清空列表
            dom.todoList.innerHTML = '';
            
            // 添加待办项（只显示未回答的问题）
            unansweredQuestions.forEach((q, index) => {
                const li = document.createElement('li');
                li.className = 'flex items-start space-x-2 p-2 bg-white rounded border border-amber-200 hover:border-amber-300 transition';
                
                const questionText = typeof q === 'string' ? q : (q.content || String(q));
                const questionId = (q && typeof q === 'object' && q.id) ? q.id : `q_${index}`;
                const priority = (q && typeof q === 'object' && q.priority) ? q.priority : null;
                const field = (q && typeof q === 'object' && q.field) ? q.field : null;
                
                li.innerHTML = `
                    <span class="flex-shrink-0 w-5 h-5 mt-0.5 rounded-full bg-amber-200 text-amber-800 text-xs font-medium flex items-center justify-center">
                        ${index + 1}
                    </span>
                    <div class="flex-1 min-w-0">
                        <div class="text-amber-900 text-xs leading-relaxed break-words">${questionText}</div>
                        ${field ? `<div class="text-xs text-amber-600 mt-0.5">字段: ${field}</div>` : ''}
                    </div>
                `;
                
                dom.todoList.appendChild(li);
            });
        },
        
        // 待办事项折叠/展开
        toggleTodoList() {
            const svg = dom.todoToggle.querySelector('svg');
            
            if (dom.todoList.classList.contains('hidden')) {
                dom.todoList.classList.remove('hidden');
                dom.todoToggleText.textContent = '收起';
                svg.style.transform = 'rotate(0deg)';
            } else {
                dom.todoList.classList.add('hidden');
                dom.todoToggleText.textContent = '展开';
                svg.style.transform = 'rotate(180deg)';
            }
        },
        
        // 更新简历信息显示
        updateResumeDisplay() {
            if (!appState.sessionId || !appState.sessions[appState.sessionId]) {
                if (dom.resumeContainer) {
                    dom.resumeContainer.classList.add('hidden');
                }
                return;
            }
            
            const sessionData = appState.sessions[appState.sessionId];
            const resumeData = sessionData.resume_data || {};
            
            // 检查是否有数据
            const hasData = Object.keys(resumeData).length > 0 && 
                           Object.values(resumeData).some(v => {
                               if (Array.isArray(v)) return v.length > 0;
                               if (typeof v === 'object' && v !== null) return Object.keys(v).length > 0;
                               return v !== null && v !== undefined && v !== '';
                           });
            
            if (!hasData) {
                if (dom.resumeContainer) {
                    dom.resumeContainer.classList.add('hidden');
                }
                return;
            }
            
            // 显示简历容器
            if (dom.resumeContainer) {
                dom.resumeContainer.classList.remove('hidden');
                
                // 格式化 JSON 显示
                try {
                    const formattedJson = JSON.stringify(resumeData, null, 2);
                    if (dom.resumeContent) {
                        dom.resumeContent.textContent = formattedJson;
                    }
                } catch (e) {
                    console.error('格式化 resume_data 失败:', e);
                    if (dom.resumeContent) {
                        dom.resumeContent.textContent = JSON.stringify(resumeData);
                    }
                }
            }
        },
        
        // 简历信息折叠/展开
        toggleResumeList() {
            if (!dom.resumeContent || !dom.resumeToggle) return;
            
            const svg = dom.resumeToggle.querySelector('svg');
            
            // 切换 resume-content 的显示/隐藏
            if (dom.resumeContent.style.display === 'none' || dom.resumeContent.classList.contains('hidden')) {
                dom.resumeContent.style.display = 'block';
                dom.resumeContent.classList.remove('hidden');
                if (dom.resumeToggleText) dom.resumeToggleText.textContent = '收起';
                if (svg) svg.style.transform = 'rotate(0deg)';
            } else {
                dom.resumeContent.style.display = 'none';
                dom.resumeContent.classList.add('hidden');
                if (dom.resumeToggleText) dom.resumeToggleText.textContent = '展开';
                if (svg) svg.style.transform = 'rotate(180deg)';
            }
        }
    };
}

