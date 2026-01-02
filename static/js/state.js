// 应用状态管理
import { getSessionIdFromURL, generateSessionId, updateURLSessionId } from './utils.js';
import { CONFIG } from './config.js';

// 全局应用状态
export const appState = {
    sessionId: null,
    currentAgentType: CONFIG.DEFAULT_AGENT_TYPE,
    sessions: {},
    startTime: null,
    timerInterval: null,
    currentEventSource: null
};

// 初始化状态
export function initState() {
    const urlSessionId = getSessionIdFromURL();
    appState.sessionId = urlSessionId || generateSessionId();
    
    if (urlSessionId) {
        updateURLSessionId(appState.sessionId);
    }
    
    // 初始化当前会话
    if (!appState.sessions[appState.sessionId]) {
        appState.sessions[appState.sessionId] = {
            token_stats: { input_tokens: 0, output_tokens: 0, total_tokens: 0 },
            pending_questions: [],
            pending_questions_raw: [],
            last_updated: new Date().toISOString(),
            agent_type: CONFIG.DEFAULT_AGENT_TYPE
        };
    }
}

// 更新会话 ID
export function setSessionId(newSessionId) {
    appState.sessionId = newSessionId;
    updateURLSessionId(newSessionId);
}

// 更新 Agent 类型
export function setAgentType(agentType) {
    appState.currentAgentType = agentType;
}

