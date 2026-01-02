// 聊天功能
import { appState, setAgentType } from './state.js';
import { CONFIG } from './config.js';
import { 
    callStreamAPI, 
    callStreamAPIWithEventSource
} from './api.js';

export function initChat(dom, message, session) {
    let retryMessageFn = null;
    
    // 暴露重试函数给全局
    window.retryMessage = (content) => {
        if (retryMessageFn) {
            retryMessageFn(content);
        }
    };
    
    return {
        // 发送消息
        async sendMessage() {
            const msg = dom.userInput.value.trim();
            if (!msg) return;
            dom.userInput.value = '';
            
            setAgentType(dom.agentSelect.value);
            message.appendMessage('user', msg);
            
            // 弱化：显示agent类型提示，但使用更小的样式
            const agentName = CONFIG.AGENT_NAMES[appState.currentAgentType] || appState.currentAgentType;
            message.appendMessage('agent', `--- 使用 ${agentName} 處理中 ---`);
            
            // 保存重试函数
            retryMessageFn = () => this.startChatStream(msg);
            
            // 统一使用流式接口
            await this.startChatStream(msg);
        },
        
        // 处理 SSE 事件的通用方法
        handleSSEEvent(data, eventCount, streamingMessageDivs, finalStreamingMessageDiv, finalAccumulatedContent, dom, message, session, timerDiv) {
            console.log(`[Chat] 📨 处理 SSE 事件 #${eventCount}:`, data.type);
            
            // 确保所有 status 类型的消息都显示
            if (data.type === 'status') {
                console.log(`[Chat] ✅ 显示 status 消息 #${eventCount}:`, data.content);
                message.appendMessage('agent', data.content, false, data.debug, null, true);
            } else if (data.type === 'partial') {
                console.log(`[Chat] 📝 处理 partial 事件 #${eventCount}`);
                
                // 处理流式 partial 事件，实现打字机效果
                let currentContent = '';
                if (data.accumulated !== undefined && data.accumulated !== null) {
                    currentContent = data.accumulated;
                } else if (data.content) {
                    finalAccumulatedContent += data.content;
                    currentContent = finalAccumulatedContent;
                } else {
                    console.warn(`[Chat] ⚠️ Partial 事件既没有 accumulated 也没有 content`);
                    return { finalStreamingMessageDiv, finalAccumulatedContent };
                }
                
                finalAccumulatedContent = currentContent;
                
                // 如果还没有创建最终流式消息元素，创建一个
                if (!finalStreamingMessageDiv) {
                    console.log(`[Chat] 🆕 创建新的最终流式消息元素`);
                    
                    finalStreamingMessageDiv = document.createElement('div');
                    finalStreamingMessageDiv.className = 'p-3 rounded-lg relative group message-agent w-full';
                    finalStreamingMessageDiv.id = 'final-streaming-message';
                    const contentSpan = document.createElement('span');
                    contentSpan.id = 'streaming-content';
                    contentSpan.style.whiteSpace = 'pre-wrap';
                    finalStreamingMessageDiv.appendChild(contentSpan);
                    dom.chatContainer.appendChild(finalStreamingMessageDiv);
                }
                
                // 更新消息内容
                const contentSpan = finalStreamingMessageDiv.querySelector('#streaming-content');
                if (contentSpan) {
                    contentSpan.textContent = currentContent;
                }
                
                // 确保计时器始终在最底部
                const existingTimer = document.getElementById('current-timer');
                if (existingTimer && existingTimer.parentNode) {
                    existingTimer.remove();
                    dom.chatContainer.appendChild(existingTimer);
                }
                
                dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
            } else if (data.type === 'final') {
                console.log(`[Chat] 🏁 收到 final 事件 #${eventCount}`);
                clearInterval(appState.timerInterval);
                appState.timerInterval = null;
                
                const endTime = Date.now();
                const totalTime = ((endTime - appState.startTime) / 1000).toFixed(2);
                
                if (finalStreamingMessageDiv) {
                    const contentSpan = finalStreamingMessageDiv.querySelector('#streaming-content');
                    if (contentSpan) {
                        const finalContent = data.content || finalAccumulatedContent || '';
                        contentSpan.textContent = finalContent;
                    }
                    
                    if (data.debug) {
                        const existingDebug = finalStreamingMessageDiv.querySelector('.debug-info');
                        if (existingDebug) existingDebug.remove();
                        const debugDiv = document.createElement('div');
                        debugDiv.className = 'debug-info mt-1 text-xs text-gray-500';
                        let debugText = '';
                        if (data.debug.agent_type || data.debug.agent_class) {
                            debugText += `Agent: ${data.debug.agent_class || data.debug.agent_type} | `;
                        }
                        if (data.debug.model_name || data.debug.model) {
                            debugText += `模型: ${data.debug.model_name || data.debug.model} | `;
                        }
                        if (debugText.endsWith(' | ')) {
                            debugText = debugText.slice(0, -3);
                        }
                        if (debugText) {
                            debugDiv.textContent = debugText;
                            finalStreamingMessageDiv.appendChild(debugDiv);
                        }
                    }
                    finalStreamingMessageDiv.removeAttribute('id');
                } else {
                    const finalContent = data.content || '';
                    message.appendMessage('agent', finalContent, false, data.debug);
                }
                
                if (data.pending_questions) {
                    session.updateSessionPendingQuestions(appState.sessionId, data.pending_questions);
                }
                
                session.refreshCurrentSessionStats();
                
                // 确保计时器在最底部
                const existingTimer = document.getElementById('current-timer');
                if (existingTimer && existingTimer.parentNode) {
                    existingTimer.remove();
                }
                
                timerDiv.className = 'text-center text-sm font-semibold text-green-600 my-3 p-2 bg-green-50 rounded-lg border border-green-200';
                timerDiv.textContent = `✅ 消息處理完成，總耗時: ${totalTime}s | Agent: ${data.agent_type || appState.currentAgentType}`;
                timerDiv.id = '';
                
                // 将计时器添加到底部
                dom.chatContainer.appendChild(timerDiv);
                dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
            } else if (data.type === 'error') {
                console.error(`[Chat] ❌ 收到 error 事件 #${eventCount}:`, data.content);
                clearInterval(appState.timerInterval);
                appState.timerInterval = null;
                timerDiv.remove();
                
                if (finalStreamingMessageDiv) {
                    finalStreamingMessageDiv.remove();
                }
                
                message.appendMessage('agent', `錯誤: ${data.content}`);
            }
            
            return { finalStreamingMessageDiv, finalAccumulatedContent };
        },
        
        // 开始聊天流
        async startChatStream(messageText) {
            if (appState.currentEventSource) {
                appState.currentEventSource.close();
            }
            if (appState.timerInterval) {
                clearInterval(appState.timerInterval);
            }

            appState.startTime = Date.now();
            
            // 创建计时器，但先不添加到 DOM，等所有消息添加后再添加到底部
            const timerDiv = document.createElement('div');
            timerDiv.className = 'text-center text-sm font-semibold text-indigo-600 my-3 p-2 bg-indigo-50 rounded-lg border border-indigo-200';
            timerDiv.id = 'current-timer';
            timerDiv.textContent = '正在思考中: 0.0s';
            // 先添加到 DOM，但会在每次添加消息后移到底部
            dom.chatContainer.appendChild(timerDiv);
            dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;

            appState.timerInterval = setInterval(() => {
                const elapsed = ((Date.now() - appState.startTime) / 1000).toFixed(1);
                const agentName = CONFIG.AGENT_NAMES[appState.currentAgentType] || appState.currentAgentType;
                timerDiv.textContent = `⚡ ${agentName} 運行中: ${elapsed}s`;
            }, CONFIG.TIMER_UPDATE_INTERVAL);

            try {
                let streamingMessageDivs = new Map();
                let finalStreamingMessageDiv = null;
                let finalAccumulatedContent = '';
                let eventCount = 0;
                
                console.log('[Chat] 🚀 开始流式处理，消息:', messageText, 'agent_type:', appState.currentAgentType);
                
                // 选择 SSE 方案：EventSource (GET) 或 Fetch (POST)
                const useEventSource = true; // 设置为 true 使用 EventSource API (推荐)
                
                if (useEventSource) {
                    // 方案1: EventSource API (GET 请求) - 最可靠
                    console.log('[Chat] 📡 使用 EventSource API (GET 请求)');
                    
                    await new Promise((resolve, reject) => {
                        const closeEventSource = callStreamAPIWithEventSource(
                            'chat',
                            {
                                message: messageText,
                                agent_type: appState.currentAgentType
                            },
                            (data) => {
                                eventCount++;
                                const result = this.handleSSEEvent(
                                    data, eventCount, streamingMessageDivs, 
                                    finalStreamingMessageDiv, finalAccumulatedContent,
                                    dom, message, session, timerDiv
                                );
                                if (result) {
                                    finalStreamingMessageDiv = result.finalStreamingMessageDiv;
                                    finalAccumulatedContent = result.finalAccumulatedContent;
                                }
                                
                                if (data.type === 'final' || data.type === 'error') {
                                    resolve();
                                }
                            },
                            (error) => {
                                console.error('[Chat] ❌ EventSource 错误:', error);
                                clearInterval(appState.timerInterval);
                                appState.timerInterval = null;
                                const timerDiv = document.getElementById('current-timer');
                                if (timerDiv) timerDiv.remove();
                                message.appendMessage('agent', `錯誤: ${error.message || error}`);
                                reject(error);
                            },
                            () => {
                                console.log('[Chat] ✅ EventSource 完成');
                                resolve();
                            }
                        );
                        
                        // 保存关闭函数
                        appState.currentEventSource = { close: closeEventSource };
                    });
                } else {
                    // 方案2: Fetch API (POST 请求) - 当前方案
                    console.log('[Chat] 📡 使用 Fetch API (POST 请求)');
                    for await (const data of callStreamAPI('chat', {
                        message: messageText,
                        agent_type: appState.currentAgentType
                    })) {
                        eventCount++;
                        const result = this.handleSSEEvent(
                            data, eventCount, streamingMessageDivs,
                            finalStreamingMessageDiv, finalAccumulatedContent,
                            dom, message, session, timerDiv
                        );
                        if (result) {
                            finalStreamingMessageDiv = result.finalStreamingMessageDiv;
                            finalAccumulatedContent = result.finalAccumulatedContent;
                        }
                    }
                }
                
                console.log(`[Chat] ✅ 流式处理完成，总共处理了 ${eventCount} 个事件`);
            } catch (error) {
                console.error('[Chat] ❌ SSE 連接失敗:', error);
                clearInterval(appState.timerInterval);
                appState.timerInterval = null;
                const timerDiv = document.getElementById('current-timer');
                if (timerDiv) timerDiv.remove();
                message.appendMessage('agent', `錯誤: ${error.message}`);
            }
        }
    };
}
