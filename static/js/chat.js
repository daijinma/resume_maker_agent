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
            // 检查是否有当前会话
            if (!appState.sessionId) {
                alert('请先创建新会话或选择一个现有会话');
                return;
            }
            
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
            
            // 处理 ReAct 循环步骤事件
            if (data.type === 'react_step') {
                console.log(`[Chat] 🔄 处理 ReAct 步骤 #${eventCount}:`, data.step, data.iteration);
                
                // 检查是否是 ReAct 模式
                const isReactMode = appState.currentAgentType === 'react';
                
                if (isReactMode) {
                    // ReAct 模式：使用专用样式
                    const stepDiv = document.createElement('div');
                    stepDiv.className = `react-step ${data.step}`;
                    
                    // 步骤图标和名称映射
                    const stepInfo = {
                        'think': { icon: '💭', name: '思考', emoji: '💭' },
                        'act': { icon: '⚡', name: '执行', emoji: '⚡' },
                        'observe': { icon: '👁️', name: '观察', emoji: '👁️' },
                        'evaluate': { icon: '✅', name: '评估', emoji: '✅' }
                    }[data.step] || { icon: '📌', name: data.step, emoji: '📌' };
                    
                    // 创建头部
                    const header = document.createElement('div');
                    header.className = 'react-step-header';
                    header.innerHTML = `
                        <span class="react-step-badge">第 ${data.iteration} 轮</span>
                        <span>${stepInfo.emoji} ${stepInfo.name}</span>
                        <span style="flex: 1;"></span>
                        <span style="font-size: 0.7rem; opacity: 0.7;">${data.description || ''}</span>
                    `;
                    stepDiv.appendChild(header);
                    
                    // 添加统计信息
                    if (data.model || data.duration || data.input_tokens || data.output_tokens) {
                        const statsDiv = document.createElement('div');
                        statsDiv.className = 'react-step-stats';
                        const stats = [];
                        if (data.model) stats.push(`模型: ${data.model}`);
                        if (data.duration) stats.push(`耗时: ${data.duration.toFixed(2)}s`);
                        if (data.input_tokens || data.output_tokens) {
                            const total = (data.input_tokens || 0) + (data.output_tokens || 0);
                            stats.push(`Token: ${total} (输入: ${data.input_tokens || 0}, 输出: ${data.output_tokens || 0})`);
                        }
                        statsDiv.textContent = stats.join(' | ');
                        stepDiv.appendChild(statsDiv);
                    }
                    
                    // 添加内容（如果有）
                    if (data.content) {
                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'react-step-content';
                        contentDiv.textContent = data.content;
                        stepDiv.appendChild(contentDiv);
                    }
                    
                    // 添加工具调用信息（如果有）
                    if (data.tool_calls && data.tool_calls.length > 0) {
                        const toolCallsDiv = document.createElement('div');
                        toolCallsDiv.className = 'react-tool-calls';
                        toolCallsDiv.style.marginTop = '0.5rem';
                        
                        data.tool_calls.forEach((toolCall, index) => {
                            const toolCallItem = document.createElement('div');
                            toolCallItem.className = 'react-tool-call-item';
                            toolCallItem.style.marginBottom = '0.5rem';
                            toolCallItem.style.border = '1px solid #e5e7eb';
                            toolCallItem.style.borderRadius = '0.375rem';
                            toolCallItem.style.overflow = 'hidden';
                            
                            // 工具调用头部（可点击展开/折叠）
                            const toolHeader = document.createElement('div');
                            toolHeader.className = 'react-tool-call-header';
                            toolHeader.style.padding = '0.5rem';
                            toolHeader.style.backgroundColor = '#f9fafb';
                            toolHeader.style.cursor = 'pointer';
                            toolHeader.style.display = 'flex';
                            toolHeader.style.alignItems = 'center';
                            toolHeader.style.justifyContent = 'space-between';
                            toolHeader.style.userSelect = 'none';
                            
                            const toolNameSpan = document.createElement('span');
                            toolNameSpan.style.fontWeight = '600';
                            toolNameSpan.style.color = '#6366f1';
                            toolNameSpan.textContent = `🔧 ${toolCall.tool_name || '未知工具'}`;
                            
                            const expandIcon = document.createElement('span');
                            expandIcon.className = 'react-tool-expand-icon';
                            expandIcon.textContent = '▼';
                            expandIcon.style.transition = 'transform 0.2s';
                            expandIcon.style.fontSize = '0.75rem';
                            expandIcon.style.color = '#6b7280';
                            
                            toolHeader.appendChild(toolNameSpan);
                            toolHeader.appendChild(expandIcon);
                            
                            // 工具调用详情（默认折叠）
                            const toolDetails = document.createElement('div');
                            toolDetails.className = 'react-tool-call-details';
                            toolDetails.style.display = 'none';
                            toolDetails.style.padding = '0.5rem';
                            toolDetails.style.backgroundColor = '#ffffff';
                            toolDetails.style.borderTop = '1px solid #e5e7eb';
                            
                            // 工具参数
                            if (toolCall.tool_args) {
                                const argsDiv = document.createElement('div');
                                argsDiv.style.marginBottom = '0.5rem';
                                const argsLabel = document.createElement('div');
                                argsLabel.style.fontSize = '0.7rem';
                                argsLabel.style.fontWeight = '600';
                                argsLabel.style.color = '#4b5563';
                                argsLabel.style.marginBottom = '0.25rem';
                                argsLabel.textContent = '📥 参数:';
                                argsDiv.appendChild(argsLabel);
                                
                                const argsContent = document.createElement('pre');
                                argsContent.style.fontSize = '0.7rem';
                                argsContent.style.color = '#6b7280';
                                argsContent.style.backgroundColor = '#f9fafb';
                                argsContent.style.padding = '0.5rem';
                                argsContent.style.borderRadius = '0.25rem';
                                argsContent.style.overflowX = 'auto';
                                argsContent.textContent = JSON.stringify(toolCall.tool_args, null, 2);
                                argsDiv.appendChild(argsContent);
                                toolDetails.appendChild(argsDiv);
                            }
                            
                            // 工具输出结果
                            if (toolCall.tool_output !== undefined && toolCall.tool_output !== null) {
                                const outputDiv = document.createElement('div');
                                const outputLabel = document.createElement('div');
                                outputLabel.style.fontSize = '0.7rem';
                                outputLabel.style.fontWeight = '600';
                                outputLabel.style.color = '#4b5563';
                                outputLabel.style.marginBottom = '0.25rem';
                                outputLabel.textContent = '📤 结果:';
                                outputDiv.appendChild(outputLabel);
                                
                                const outputContent = document.createElement('pre');
                                outputContent.style.fontSize = '0.7rem';
                                outputContent.style.color = '#059669';
                                outputContent.style.backgroundColor = '#ecfdf5';
                                outputContent.style.padding = '0.5rem';
                                outputContent.style.borderRadius = '0.25rem';
                                outputContent.style.overflowX = 'auto';
                                outputContent.style.whiteSpace = 'pre-wrap';
                                outputContent.style.wordBreak = 'break-word';
                                
                                // 格式化输出（如果是对象或数组，使用 JSON 格式化）
                                let outputText = '';
                                if (typeof toolCall.tool_output === 'object') {
                                    try {
                                        outputText = JSON.stringify(toolCall.tool_output, null, 2);
                                    } catch (e) {
                                        outputText = String(toolCall.tool_output);
                                    }
                                } else {
                                    outputText = String(toolCall.tool_output);
                                }
                                outputContent.textContent = outputText;
                                outputDiv.appendChild(outputContent);
                                toolDetails.appendChild(outputDiv);
                            }
                            
                            // 工具调用耗时
                            if (toolCall.duration !== undefined && toolCall.duration !== null) {
                                const durationDiv = document.createElement('div');
                                durationDiv.style.fontSize = '0.65rem';
                                durationDiv.style.color = '#9ca3af';
                                durationDiv.style.marginTop = '0.5rem';
                                durationDiv.textContent = `⏱️ 耗时: ${toolCall.duration.toFixed(2)}s`;
                                toolDetails.appendChild(durationDiv);
                            }
                            
                            // 点击头部展开/折叠
                            let isExpanded = false;
                            toolHeader.addEventListener('click', () => {
                                isExpanded = !isExpanded;
                                toolDetails.style.display = isExpanded ? 'block' : 'none';
                                expandIcon.textContent = isExpanded ? '▲' : '▼';
                                expandIcon.style.transform = isExpanded ? 'rotate(0deg)' : 'rotate(0deg)';
                            });
                            
                            toolCallItem.appendChild(toolHeader);
                            toolCallItem.appendChild(toolDetails);
                            toolCallsDiv.appendChild(toolCallItem);
                        });
                        
                        stepDiv.appendChild(toolCallsDiv);
                    }
                    
                    // 添加到聊天容器
                    dom.chatContainer.appendChild(stepDiv);
                    // 取消自动滚动：dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
                } else {
                    // 非 ReAct 模式：使用简化显示
                    const stepDiv = document.createElement('div');
                    stepDiv.className = 'p-2 rounded-lg mb-2 border-l-4 bg-gray-50 border-gray-400';
                    stepDiv.textContent = `[ReAct] 第 ${data.iteration} 轮 - ${data.step}: ${data.description || ''}`;
                    stepDiv.style.fontSize = '0.85rem';
                    dom.chatContainer.appendChild(stepDiv);
                    // 取消自动滚动：dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
                }
                
                return { finalStreamingMessageDiv, finalAccumulatedContent };
            }
            
            // 确保所有 status 类型的消息都显示
            if (data.type === 'status') {
                console.log(`[Chat] ✅ 显示 status 消息 #${eventCount}:`, data.content);
                message.appendMessage('agent', data.content, false, data.debug, null, true);
            } else if (data.type === 'partial') {
                console.log(`[Chat] 📝 处理 partial 事件 #${eventCount}`);
                
                // 检查是否是 ReAct 模式
                const isReactMode = appState.currentAgentType === 'react';
                
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
                
                if (isReactMode) {
                    // ReAct 模式：根据步骤信息创建或找到对应的输出块
                    const reactIteration = data.react_iteration || 0;
                    const reactStep = data.react_step || 'unknown';
                    const outputId = `react-output-${reactIteration}-${reactStep}`;
                    
                    let outputDiv = document.getElementById(outputId);
                    
                    if (!outputDiv) {
                        // 创建新的输出块，标识步骤信息
                        outputDiv = document.createElement('div');
                        outputDiv.id = outputId;
                        outputDiv.className = 'react-output';
                        
                        // 添加步骤标识头部
                        const stepHeader = document.createElement('div');
                        stepHeader.style.fontSize = '0.7rem';
                        stepHeader.style.fontWeight = '600';
                        stepHeader.style.color = '#6366f1';
                        stepHeader.style.marginBottom = '0.5rem';
                        stepHeader.style.display = 'flex';
                        stepHeader.style.alignItems = 'center';
                        stepHeader.style.gap = '0.5rem';
                        
                        const stepBadge = document.createElement('span');
                        stepBadge.className = 'react-step-badge';
                        stepBadge.textContent = `第 ${reactIteration} 轮`;
                        stepHeader.appendChild(stepBadge);
                        
                        const stepName = document.createElement('span');
                        const stepNames = {
                            'think': '💭 思考输出',
                            'act': '⚡ 执行输出',
                            'observe': '👁️ 观察输出',
                            'evaluate': '✅ 评估输出',
                            'final': '📝 最终答案'
                        };
                        stepName.textContent = stepNames[reactStep] || `📌 ${reactStep} 输出`;
                        stepHeader.appendChild(stepName);
                        
                        outputDiv.appendChild(stepHeader);
                        
                        const contentSpan = document.createElement('div');
                        contentSpan.className = 'react-output-content';
                        contentSpan.style.whiteSpace = 'pre-wrap';
                        contentSpan.style.wordBreak = 'break-word';
                        outputDiv.appendChild(contentSpan);
                        dom.chatContainer.appendChild(outputDiv);
                    }
                    
                    // 更新输出内容
                    const contentSpan = outputDiv.querySelector('.react-output-content');
                    if (contentSpan) {
                        contentSpan.textContent = currentContent;
                    }
                } else {
                    // 非 ReAct 模式：使用原有逻辑
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
                }
                
                // 确保计时器始终在最底部
                const existingTimer = document.getElementById('current-timer');
                if (existingTimer && existingTimer.parentNode) {
                    existingTimer.remove();
                    dom.chatContainer.appendChild(existingTimer);
                }
                
                // 取消自动滚动：dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
            } else if (data.type === 'final') {
                console.log(`[Chat] 🏁 收到 final 事件 #${eventCount}`);
                clearInterval(appState.timerInterval);
                appState.timerInterval = null;
                
                const endTime = Date.now();
                const totalTime = ((endTime - appState.startTime) / 1000).toFixed(2);
                
                // 检查是否是 ReAct 模式
                const isReactMode = appState.currentAgentType === 'react';
                
                if (isReactMode) {
                    // ReAct 模式：移除临时输出块，创建最终答案块
                    const tempOutput = document.getElementById('react-current-output');
                    if (tempOutput) {
                        tempOutput.remove();
                    }
                    
                    // 创建最终答案块
                    const finalAnswerDiv = document.createElement('div');
                    finalAnswerDiv.className = 'react-output';
                    finalAnswerDiv.style.borderLeftColor = '#10b981';
                    finalAnswerDiv.style.backgroundColor = '#ecfdf5';
                    
                    const finalLabel = document.createElement('div');
                    finalLabel.style.fontSize = '0.75rem';
                    finalLabel.style.fontWeight = '600';
                    finalLabel.style.color = '#059669';
                    finalLabel.style.marginBottom = '0.5rem';
                    finalLabel.textContent = '✅ 最终答案:';
                    finalAnswerDiv.appendChild(finalLabel);
                    
                    const finalContent = data.content || finalAccumulatedContent || '';
                    const contentDiv = document.createElement('div');
                    contentDiv.style.whiteSpace = 'pre-wrap';
                    contentDiv.textContent = finalContent;
                    finalAnswerDiv.appendChild(contentDiv);
                    
                    // 添加调试信息
                    if (data.debug) {
                        const debugDiv = document.createElement('div');
                        debugDiv.className = 'react-step-stats';
                        debugDiv.style.marginTop = '0.5rem';
                        let debugText = '';
                        if (data.debug.iterations) {
                            debugText += `迭代次数: ${data.debug.iterations} | `;
                        }
                        if (data.debug.model) {
                            debugText += `模型: ${data.debug.model} | `;
                        }
                        if (data.debug.total_tokens) {
                            debugText += `总 Token: ${data.debug.total_tokens} | `;
                        }
                        if (data.debug.duration) {
                            debugText += `总耗时: ${data.debug.duration.toFixed(2)}s`;
                        }
                        if (debugText.endsWith(' | ')) {
                            debugText = debugText.slice(0, -3);
                        }
                        if (debugText) {
                            debugDiv.textContent = debugText;
                            finalAnswerDiv.appendChild(debugDiv);
                        }
                    }
                    
                    dom.chatContainer.appendChild(finalAnswerDiv);
                } else {
                    // 非 ReAct 模式：使用原有逻辑
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
                }
                
                if (data.pending_questions) {
                    session.updateSessionPendingQuestions(appState.sessionId, data.pending_questions);
                }
                
                // 更新 resume_data
                if (data.resume_data) {
                    session.updateSessionResumeData(appState.sessionId, data.resume_data);
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
                // 取消自动滚动：dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
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
            // 取消自动滚动：dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;

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
