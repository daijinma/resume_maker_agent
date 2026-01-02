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
            
            if (pendingQuestions.length === 0) {
                dom.todoContainer.classList.add('hidden');
                return;
            }
            
            // 显示待办容器
            dom.todoContainer.classList.remove('hidden');
            
            // 清空列表
            dom.todoList.innerHTML = '';
            
            // 添加待办项
            pendingQuestions.forEach((q, index) => {
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
        }
    };
}

