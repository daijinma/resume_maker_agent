// API 调用相关
import { appState } from './state.js';
import { CONFIG } from './config.js';

// SSE 流式读取工具函数（仅用于 chat）
async function* readSSEStream(response) {
    console.log('[SSE] 开始读取 SSE 流，response:', response);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let chunkCount = 0;
    let lineCount = 0;

    while (true) {
        const { done, value } = await reader.read();
        console.log(`[Message] 📋 消息内容:`, done);

        if (done) {
            console.log('[SSE] 流读取完成，总共处理了', chunkCount, '个数据块，', lineCount, '行数据');
            break;
        }

        chunkCount++;
        const chunk = decoder.decode(value, { stream: true });
        console.log(`[SSE] 收到数据块 #${chunkCount}, 长度:`, chunk.length, '内容预览:', chunk.substring(0, 100));
        
        buffer += chunk;
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            lineCount++;
            const trimmedLine = line.trim();
            
            if (!trimmedLine) {
                console.log(`[SSE] 第 ${lineCount} 行: 空行，跳过`);
                continue;
            }
            
            if (trimmedLine.startsWith(':')) {
                console.log(`[SSE] 第 ${lineCount} 行: SSE 注释行，跳过:`, trimmedLine);
                continue;
            }
            
            if (line.startsWith('data: ')) {
                try {
                    const jsonStr = line.slice(6);
                    console.log(`[SSE] 第 ${lineCount} 行: 解析 JSON 数据，原始字符串:`, jsonStr);
                    const data = JSON.parse(jsonStr);
                    console.log(`[SSE] ✅ 解析 SSE 数据成功 #${lineCount}:`, data);
                    console.log(`[SSE]   事件类型: ${data.type}, 内容长度: ${data.content?.length || 0}, accumulated长度: ${data.accumulated?.length || 0}`);
                    if (data.content) {
                        console.log(`[SSE]   内容预览: ${data.content.substring(0, 100)}`);
                    }
                    if (data.accumulated) {
                        console.log(`[SSE]   累积内容预览: ${data.accumulated.substring(0, 100)}`);
                    }
                    yield data;
                } catch (e) {
                    console.error(`[SSE] ❌ 解析 SSE 数据失败 #${lineCount}:`, e, '原始行:', line);
                }
            } else {
                // 记录非 data: 开头的行（可能是 ping 或其他格式）
                console.log(`[SSE] ⚠️ 第 ${lineCount} 行: 收到非标准 SSE 行:`, line);
            }
        }
    }
    
    // 处理剩余的 buffer
    if (buffer.trim()) {
        console.log('[SSE] 处理剩余的 buffer:', buffer);
        if (buffer.startsWith('data: ')) {
            try {
                const data = JSON.parse(buffer.slice(6));
                console.log('[SSE] ✅ 解析剩余 buffer 数据成功:', data);
                yield data;
            } catch (e) {
                console.error('[SSE] ❌ 解析剩余 buffer 失败:', e, buffer);
            }
        }
    }
}

// 方案1: 使用 EventSource API (GET 请求) - 最可靠
export function callStreamAPIWithEventSource(action, body = {}, onMessage, onError, onComplete) {
    console.log('[API] 🚀 使用 EventSource API (GET 请求)');
    console.log('[API] 请求参数:', { action, body });
    
    // 构建查询参数
    const params = new URLSearchParams({
        action,
        session_id: appState.sessionId || 'default',
    });
    
    // 添加 body 中的参数
    if (body.message) {
        params.append('message', body.message);
    }
    if (body.agent_type) {
        params.append('agent_type', body.agent_type);
    }
    if (body.limit) {
        params.append('limit', body.limit.toString());
    }
    
    const url = `/stream?${params.toString()}`;
    console.log('[API] EventSource URL:', url);
    
    const eventSource = new EventSource(url);
    
    eventSource.onopen = () => {
        console.log('[API] ✅ EventSource 连接已打开');
    };
    
    eventSource.onmessage = (event) => {
        try {
            console.log('[API] 📨 EventSource 收到原始消息:', event.data);
            const data = JSON.parse(event.data);
            console.log('[API] ✅ EventSource 解析成功:', data);
            if (onMessage) {
                onMessage(data);
            }
            
            // 如果是 final 或 error，关闭连接
            if (data.type === 'final' || data.type === 'error') {
                console.log('[API] 🏁 收到 final/error，准备关闭连接');
                setTimeout(() => {
                    eventSource.close();
                    if (onComplete) onComplete();
                }, 100);
            }
        } catch (e) {
            console.error('[API] ❌ EventSource 解析消息失败:', e, '原始数据:', event.data);
            if (onError) onError(e);
        }
    };
    
    eventSource.onerror = (error) => {
        console.error('[API] ❌ EventSource 错误:', error);
        console.error('[API] EventSource 状态:', eventSource.readyState);
        // readyState: 0=CONNECTING, 1=OPEN, 2=CLOSED
        if (eventSource.readyState === EventSource.CLOSED) {
            console.log('[API] EventSource 连接已关闭');
            if (onComplete) onComplete();
        } else if (eventSource.readyState === EventSource.CONNECTING) {
            console.log('[API] EventSource 正在重新连接...');
        } else {
            if (onError) onError(error);
        }
    };
    
    // 监听自定义事件
    eventSource.addEventListener('close', () => {
        console.log('[API] ✅ EventSource 收到关闭事件');
        eventSource.close();
        if (onComplete) onComplete();
    });
    
    // 返回关闭函数
    return () => {
        console.log('[API] 🔒 手动关闭 EventSource');
        eventSource.close();
        if (onComplete) onComplete();
    };
}

// 方案2: 使用 fetch + ReadableStream (POST 请求) - 当前方案
export async function* callStreamAPIWithFetch(action, body = {}) {
    const requestBody = {
        action,
        session_id: appState.sessionId,
        ...body
    };
    console.log('[API] 🚀 使用 Fetch API (POST 请求)');
    console.log('[API] 发送流式请求:', requestBody);
    
    const response = await fetch('/stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
    });

    console.log('[API] 收到响应，status:', response.status, 'headers:', Object.fromEntries(response.headers.entries()));
    console.log('[API] Content-Type:', response.headers.get('Content-Type'));
    console.log('[API] response.body:', response.body);

    if (!response.ok) {
        const errorText = await response.text();
        console.error('[API] ❌ HTTP 错误:', response.status, errorText);
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
    }

    // 检查 Content-Type
    const contentType = response.headers.get('Content-Type') || '';
    if (!contentType.includes('text/event-stream') && !contentType.includes('text/plain')) {
        console.warn('[API] ⚠️ Content-Type 可能不正确:', contentType);
    }

    console.log('[API] ✅ 响应正常，开始读取 SSE 流');
    return readSSEStream(response);
}

// 方案3: 使用 fetch-event-source 库风格 (POST 请求)
// 需要安装: npm install @microsoft/fetch-event-source
// 或者使用 polyfill
export async function* callStreamAPIWithFetchEventSource(action, body = {}) {
    console.log('[API] 🚀 使用 Fetch-Event-Source 风格 (POST 请求)');
    
    // 检查是否安装了 fetch-event-source
    if (typeof window !== 'undefined' && window.fetchEventSource) {
        console.log('[API] 使用 fetch-event-source 库');
        // 使用库的实现
        const { fetchEventSource } = window.fetchEventSource;
        const requestBody = {
            action,
            session_id: appState.sessionId,
            ...body
        };
        
        const events = [];
        let resolveNext;
        let promise = new Promise(r => resolveNext = r);
        
        await fetchEventSource('/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody),
            onmessage(event) {
                try {
                    const data = JSON.parse(event.data);
                    events.push(data);
                    resolveNext();
                    promise = new Promise(r => resolveNext = r);
                } catch (e) {
                    console.error('[API] ❌ 解析事件失败:', e);
                }
            },
            onerror(err) {
                console.error('[API] ❌ Fetch-Event-Source 错误:', err);
            }
        });
        
        // 返回生成器
        while (events.length > 0 || promise) {
            if (events.length > 0) {
                yield events.shift();
            } else {
                await promise;
            }
        }
    } else {
        console.log('[API] fetch-event-source 库未安装，回退到 Fetch API');
        return callStreamAPIWithFetch(action, body);
    }
}

// 默认使用 Fetch API (向后兼容)
export async function* callStreamAPI(action, body = {}) {
    // 尝试使用 EventSource (GET) 如果可能
    // 否则使用 Fetch API (POST)
    console.log('[API] 使用默认方案: Fetch API (POST)');
    return callStreamAPIWithFetch(action, body);
}

// 普通 REST API 调用
async function callRestAPI(url, options = {}) {
    const response = await fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
}

// 加载会话列表
export async function loadSessionsFromBackend(onUpdate) {
    try {
        const data = await callRestAPI(`/api/sessions?limit=${CONFIG.SESSIONS_LIMIT}`);
        if (data.sessions) {
            // 更新 sessions 对象，保留已有的 token_stats 等信息
            data.sessions.forEach(sess => {
                if (!appState.sessions[sess.session_id]) {
                    appState.sessions[sess.session_id] = {
                        token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                        pending_questions: [],
                        pending_questions_raw: [],
                        last_updated: sess.updated_at || sess.created_at,
                        created_at: sess.created_at || sess.updated_at || new Date().toISOString()
                    };
                }
                // 更新 agent_type、session_name、last_updated 和 created_at
                appState.sessions[sess.session_id].agent_type = sess.agent_type || CONFIG.DEFAULT_AGENT_TYPE;
                appState.sessions[sess.session_id].session_name = sess.session_name || null;
                appState.sessions[sess.session_id].last_updated = sess.updated_at || sess.created_at;
                // 如果后端返回了 created_at，优先使用它（确保排序稳定）
                if (sess.created_at) {
                    appState.sessions[sess.session_id].created_at = sess.created_at;
                } else if (!appState.sessions[sess.session_id].created_at) {
                    // 如果没有 created_at，使用 updated_at 或当前时间
                    appState.sessions[sess.session_id].created_at = sess.updated_at || new Date().toISOString();
                }
            });
            if (onUpdate) onUpdate();
        }
    } catch (error) {
        console.error('加载会话列表失败:', error);
    }
}

// 加载会话历史
export async function loadSessionHistory(sessId, onMessage) {
    if (!sessId) return;
    
    try {
        const data = await callRestAPI(`/api/sessions/${sessId}/history?limit=${CONFIG.HISTORY_LIMIT}`);
        if (data.history && data.history.length > 0 && onMessage) {
            data.history.forEach(msg => {
                const role = msg.role;
                if (role === 'user' || role === 'agent' || role === 'assistant') {
                    const displayRole = (role === 'assistant') ? 'agent' : role;
                    onMessage(displayRole, msg.content, false, null);
                }
            });
        }
    } catch (error) {
        console.error('加载会话历史失败:', error);
        if (onMessage) onMessage('agent', `⚠️ 加载会话历史失败: ${error.message}`);
    }
}

// 获取会话 token 统计
export async function fetchSessionTokenStats(sessId, onUpdate) {
    try {
        const data = await callRestAPI(`/api/sessions/${sessId}/token-stats`);
        if (!appState.sessions[sessId]) {
            const now = new Date().toISOString();
            appState.sessions[sessId] = {
                token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
                pending_questions: [],
                last_updated: now,
                created_at: now
            };
        } else {
            // 确保 created_at 存在
            if (!appState.sessions[sessId].created_at) {
                appState.sessions[sessId].created_at = appState.sessions[sessId].last_updated || new Date().toISOString();
            }
        }
        // 支持两种数据格式：直接有total字段，或者嵌套在result中
        if (data.total) {
            appState.sessions[sessId].token_stats = data.total;
        } else if (data.result && data.result.total) {
            appState.sessions[sessId].token_stats = data.result.total;
        }
        // 如果返回了 agent_type，更新它
        if (data.agent_type) {
            appState.sessions[sessId].agent_type = data.agent_type;
        }
        appState.sessions[sessId].last_updated = new Date().toISOString();
        if (onUpdate) onUpdate();
    } catch (error) {
        console.error('获取 token 统计失败:', error);
    }
}

// 获取会话的待办事项
export async function fetchSessionPendingQuestions(sessId, onUpdate) {
    try {
        const data = await callRestAPI(`/api/sessions/${sessId}/pending-questions`);
        if (data.pending_questions && onUpdate) {
            onUpdate(sessId, data.pending_questions);
        }
    } catch (error) {
        // 静默失败，不影响其他功能
        console.debug('获取待办事项失败（可能不支持）:', error);
    }
}

// 更新会话名称
export async function updateSessionName(sessId, name) {
    return await callRestAPI(`/api/sessions/${sessId}/name?name=${encodeURIComponent(name)}`, {
        method: 'PUT'
    });
}

