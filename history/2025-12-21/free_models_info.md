# OpenRouter 免费模型配置信息 (2025-12-21)

本项目目前主要使用 OpenRouter 提供的免费模型，以平衡性能与成本。

## 1. 模型列表与用途

| Agent 角色 | 推荐模型 | 理由 |
| :--- | :--- | :--- |
| **Planner / Router** | `google/gemini-2.0-flash-exp:free` | 响应速度极快，意图识别准确，适合作为入口。 |
| **Info Worker** | `google/gemini-2.0-flash-exp:free` | 擅长结构化数据提取，处理基本信息效率高。 |
| **Experience Worker** | `meta-llama/llama-3.3-70b-instruct:free` | 70B 参数量，逻辑推理和文案润色能力极强，适合 STAR 法则处理。 |
| **Skill Worker** | `google/gemini-2.0-flash-exp:free` | 快速分类和提取技术关键词。 |
| **Aggregator** | `google/gemini-2.0-flash-exp:free` | 能够快速生成流畅的对话反馈。 |

## 2. 配置参考 (`src/config.py`)

```python
class Config:
    # 模型选择
    MODEL_PLANNER = "google/gemini-2.0-flash-exp:free"
    MODEL_INFO_WORKER = "google/gemini-2.0-flash-exp:free"
    MODEL_EXP_WORKER = "meta-llama/llama-3.3-70b-instruct:free"
    MODEL_SKILL_WORKER = "google/gemini-2.0-flash-exp:free"
    MODEL_AGGREGATOR = "google/gemini-2.0-flash-exp:free"
    
    # API 配置
    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_HEADERS = {
        "HTTP-Referer": "https://github.com/daijinma/resume_maker_agent",
        "X-Title": "Resume Maker Agent",
    }
```

## 3. 注意事项
- **速率限制**: 免费模型通常有每分钟调用次数 (RPM) 的限制，在高并发场景下需注意。
- **上下文长度**: Gemini 2.0 Flash 拥有极长的上下文窗口，适合处理长简历或复杂对话历史。
- **稳定性**: 免费模型可能存在不稳定的情况，建议在生产环境考虑付费版本或备选模型。
