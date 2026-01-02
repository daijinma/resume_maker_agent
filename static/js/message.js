// 消息显示相关
import { appState } from './state.js';

// 辅助函数：确保计时器始终在最底部
function ensureTimerAtBottom(dom) {
    const existingTimer = document.getElementById('current-timer');
    if (existingTimer && existingTimer.parentNode) {
        existingTimer.remove();
        dom.chatContainer.appendChild(existingTimer);
    }
}

export function initMessage(dom) {
    return {
        appendMessage(role, content, isJson = false, debug = null, messageId = null, isLog = false) {
            const logInfo = {
                role,
                contentLength: content?.length || 0,
                contentPreview: content?.substring(0, 100) || '',
                isJson,
                hasDebug: !!debug,
                messageId,
                isLog,
                timestamp: new Date().toISOString()
            };
            console.log(`[Message] 📝 appendMessage 调用:`, logInfo);
            // 同时在页面上显示关键信息（用于调试）
            if (isLog && content) {
                console.log(`[Message] 📋 消息内容:`, content);
            }
            
            const div = document.createElement('div');
            
            // 弱化：状态消息使用更小、更不显眼的样式
            if (role === 'agent' && !isJson && !debug && content.startsWith('---')) {
                console.log(`[Message] 📝 创建弱化状态消息`);
                div.className = 'log-message text-center my-1';
                div.textContent = content;
                
                // 添加弱化状态消息到 DOM（在中间插入）
                dom.chatContainer.appendChild(div);
                console.log(`[Message] ✅ 弱化状态消息已添加到 DOM，容器子元素数:`, dom.chatContainer.children.length);
                
                // 确保计时器始终在最底部
                ensureTimerAtBottom(dom);
                
                dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
                return div;
            }

            // 如果是 log 消息，使用 log-message 样式显示（确保所有日志都可见）
            if (isLog) {
                console.log(`[Message] 📝 创建 log 消息:`, content.substring(0, 100), 'debug:', debug);
                div.className = 'log-message';
                const textSpan = document.createElement('span');
                textSpan.textContent = content;
                div.appendChild(textSpan);
                
                // 如果有 debug 信息，也显示出来
                if (debug) {
                    const debugDiv = document.createElement('div');
                    debugDiv.className = 'debug-info mt-1';
                    let debugText = '';
                    if (debug.event) {
                        debugText += `[${debug.event}] `;
                    }
                    if (debug.agent_type || debug.agent_class) {
                        debugText += `Agent: ${debug.agent_class || debug.agent_type} | `;
                    }
                    if (debug.model_name || debug.model) {
                        debugText += `模型: ${debug.model_name || debug.model} | `;
                    }
                    if (debug.duration !== undefined) {
                        debugText += `耗时: ${debug.duration}s | `;
                    }
                    if (debug.input_tokens !== undefined || debug.output_tokens !== undefined) {
                        debugText += `Tokens: ${debug.input_tokens || 0}/${debug.output_tokens || 0}`;
                    }
                    if (debugText.endsWith(' | ')) {
                        debugText = debugText.slice(0, -3);
                    }
                    if (debugText) {
                        debugDiv.textContent = debugText;
                        div.appendChild(debugDiv);
                    }
                }
                
                const beforeAppend = dom.chatContainer.children.length;
                
                // 添加 log 消息到 DOM（在中间插入）
                dom.chatContainer.appendChild(div);
                const afterAppend = dom.chatContainer.children.length;
                console.log(`[Message] ✅ Log 消息已添加到 DOM:`, {
                    beforeAppend,
                    afterAppend,
                    className: div.className,
                    textContent: div.textContent.substring(0, 50),
                    display: window.getComputedStyle(div).display,
                    visibility: window.getComputedStyle(div).visibility,
                    opacity: window.getComputedStyle(div).opacity
                });
                
                // 确保计时器始终在最底部
                ensureTimerAtBottom(dom);
                
                dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
                return div;
            }

            div.className = `p-3 rounded-lg relative group ${role === 'user' ? 'message-user max-w-[80%]' : 'message-agent w-full'}`;
            
            // 弱化：状态更新消息使用更小的样式，与正常消息区分
            if (role === 'agent' && !isJson && !debug) {
                // 检查是否是状态消息（通常比较短或者是系统提示）
                const isStatusMessage = content.length < 100 || content.includes('处理中') || content.includes('运行中');
                if (isStatusMessage) {
                    div.classList.add('log-message', 'bg-gray-50', 'border-gray-200', 'py-1', 'px-2');
                    console.log(`[Message] 📝 应用状态消息样式`);
                }
            }

            if (messageId) div.dataset.messageId = messageId;
            
            if (isJson) {
                // 弱化：JSON调试信息使用更小的样式
                console.log(`[Message] 📝 创建 JSON 消息`);
                const pre = document.createElement('pre');
                pre.className = 'json-block overflow-x-auto';
                pre.textContent = typeof content === 'string' ? content : JSON.stringify(content, null, 2);
                div.appendChild(pre);
            } else {
                const textSpan = document.createElement('span');
                textSpan.textContent = content;
                div.appendChild(textSpan);
            }

            if (debug && debug.model) {
                const debugDiv = document.createElement('div');
                debugDiv.className = 'debug-info';
                debugDiv.textContent = `[${debug.agent}] 模型: ${debug.model} | 耗时: ${debug.duration}`;
                div.appendChild(debugDiv);
            }

            // 为用户消息增加重试按钮
            if (role === 'user') {
                const retryBtn = document.createElement('button');
                retryBtn.className = 'absolute -left-10 top-1/2 -translate-y-1/2 hidden group-hover:block p-1 text-gray-400 hover:text-indigo-600 transition';
                retryBtn.innerHTML = `
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" />
                    </svg>
                `;
                retryBtn.title = '重试此消息';
                retryBtn.onclick = () => {
                    if (appState.currentEventSource) {
                        appState.currentEventSource.close();
                        this.appendMessage('agent', '--- 已中断当前请求，正在重试 ---');
                    }
                    // 需要从外部传入重试函数
                    if (window.retryMessage) {
                        window.retryMessage(content);
                    }
                };
                div.appendChild(retryBtn);
            }
            
            const beforeAppend = dom.chatContainer.children.length;
            
            // 添加消息到 DOM
            dom.chatContainer.appendChild(div);
            const afterAppend = dom.chatContainer.children.length;
            console.log(`[Message] ✅ 消息已添加到 DOM:`, {
                role,
                beforeAppend,
                afterAppend,
                className: div.className,
                textContent: div.textContent.substring(0, 50),
                display: window.getComputedStyle(div).display,
                visibility: window.getComputedStyle(div).visibility,
                opacity: window.getComputedStyle(div).opacity,
                height: window.getComputedStyle(div).height
            });
            
            // 确保计时器始终在最底部
            ensureTimerAtBottom(dom);
            
            dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
            return div;
        }
    };
}

