#!/usr/bin/env python3
"""
從 JSON 文件遷移數據到 PostgreSQL 數據庫
"""

import json
import asyncio
import asyncpg
import os
from pathlib import Path

# 數據庫連接配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "resume_agent_db",
    "user": "resume_agent",
    "password": "resume_agent_pass"
}

JSON_FILE = "sessions.json"


async def migrate_sessions():
    """遷移會話數據"""
    # 讀取 JSON 文件
    if not os.path.exists(JSON_FILE):
        print(f"未找到 {JSON_FILE}，跳過遷移")
        return
    
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        sessions_data = json.load(f)
    
    if not sessions_data:
        print("JSON 文件中沒有數據，跳過遷移")
        return
    
    # 連接數據庫
    conn = await asyncpg.connect(**DB_CONFIG)
    
    try:
        migrated_count = 0
        for session_id, session_data in sessions_data.items():
            # 提取數據
            resume_data = session_data.get("resume_data", {})
            question_queue = session_data.get("question_queue", {})
            background_reasoning_status = session_data.get("background_reasoning_status", "pending")
            last_reasoning_time = session_data.get("last_reasoning_time")
            
            # 插入或更新會話
            await conn.execute("""
                INSERT INTO sessions (session_id, resume_data, question_queue, 
                                   background_reasoning_status, last_reasoning_time)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (session_id) 
                DO UPDATE SET
                    resume_data = EXCLUDED.resume_data,
                    question_queue = EXCLUDED.question_queue,
                    background_reasoning_status = EXCLUDED.background_reasoning_status,
                    last_reasoning_time = EXCLUDED.last_reasoning_time,
                    updated_at = CURRENT_TIMESTAMP
            """, session_id, json.dumps(resume_data), json.dumps(question_queue),
                background_reasoning_status, last_reasoning_time)
            
            # 遷移問題佇列
            questions = question_queue.get("questions", [])
            for q in questions:
                question_id = q.get("id", f"q_{migrated_count}")
                await conn.execute("""
                    INSERT INTO question_queue 
                    (session_id, question_id, content, priority, field, reason, answered)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (session_id, question_id) DO NOTHING
                """, session_id, question_id, q.get("content", ""), 
                    q.get("priority", 99), q.get("field"), q.get("reason"),
                    question_id in question_queue.get("answered", []))
            
            migrated_count += 1
            print(f"已遷移會話: {session_id}")
        
        print(f"\n遷移完成！共遷移 {migrated_count} 個會話")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate_sessions())

