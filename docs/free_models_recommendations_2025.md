# 免费模型推荐方案（避开 Gemini）- 2025

本文档基于 OpenRouter 提供的免费模型，推荐各 Agent 使用的模型配置。

## 模型选择原则

- **避开 Gemini 模型**：不使用任何 `google/gemini-*` 模型
- **高速优先**：对于需要快速响应的 Agent，优先选择小模型
- **质量优先**：对于核心任务（如润色、推理），选择大模型
- **上下文长度**：根据任务复杂度选择合适上下文窗口

## 推荐配置方案

| Agent 角色 | 推荐模型 | 模型 ID | 上下文长度 | 推荐理由 |
|:---|:---|:---|:---|:---|
| **Planner / Router** | Llama 3.2 3B Instruct | `meta-llama/llama-3.2-3b-instruct:free` | 131,072 | 极速响应（<2秒），意图识别准确，小模型速度快 |
| **Info Worker** | Mistral Small 3.1 24B | `mistralai/mistral-small-3.1-24b-instruct:free` | 128,000 | 平衡速度与准确性，擅长结构化数据提取 |
| **Experience Worker** | Llama 3.3 70B Instruct | `meta-llama/llama-3.3-70b-instruct:free` | 131,072 | 高质量写作和逻辑推理，适合 STAR 法则润色 |
| **Skill Worker** | Mistral Small 3.1 24B | `mistralai/mistral-small-3.1-24b-instruct:free` | 128,000 | 快速分类和提取技术关键词 |
| **Inference** | Llama 3.3 70B Instruct | `meta-llama/llama-3.3-70b-instruct:free` | 131,072 | 高质量分析，仅在必要时调用 |
| **Aggregator** | Llama 3.2 3B Instruct | `meta-llama/llama-3.2-3b-instruct:free` | 131,072 | 快速响应（<2秒），流畅对话生成 |

## 备选模型方案

### 如果需要更大上下文窗口：

- **Info Worker 备选**：
  - `mistralai/devstral-2512:free`（262,144 tokens）- 更大上下文
  - `xiaomi/mimo-v2-flash:free`（262,144 tokens）- 极大上下文，速度快

### 如果需要更高质量推理：

- **Experience Worker 备选**：
  - `meta-llama/llama-3.1-405b-instruct:free`（131,072 tokens）- 超大模型，质量更高但速度较慢
  - `nousresearch/hermes-3-llama-3.1-405b:free`（131,072 tokens）- 基于 Llama 3.1 405B 的增强版

- **Inference 备选**：
  - `meta-llama/llama-3.1-405b-instruct:free`（131,072 tokens）- 最高质量推理
  - `nousresearch/hermes-3-llama-3.1-405b:free`（131,072 tokens）- 高质量分析

### 如果需要更快响应速度：

- **Planner/Aggregator 备选**：
  - `qwen/qwen3-4b:free`（40,960 tokens）- 4B 小模型，响应极快

## 模型性能对比

### 速度优先模型（小模型，<10B）
- `meta-llama/llama-3.2-3b-instruct:free` - 3B，131K 上下文
- `qwen/qwen3-4b:free` - 4B，40K 上下文
- `google/gemma-3-4b-it:free` - 4B，32K 上下文（不建议，上下文较小）

### 平衡型模型（中等模型，10-50B）
- `mistralai/mistral-small-3.1-24b-instruct:free` - 24B，128K 上下文 ⭐推荐
- `qwen/qwen-2.5-vl-7b-instruct:free` - 7B，32K 上下文（视觉模型，不适合文本）

### 质量优先模型（大模型，>50B）
- `meta-llama/llama-3.3-70b-instruct:free` - 70B，131K 上下文 ⭐推荐
- `meta-llama/llama-3.1-405b-instruct:free` - 405B，131K 上下文（最高质量但较慢）

## 注意事项

1. **速率限制**：免费模型通常有每分钟调用次数 (RPM) 的限制，在高并发场景下需注意
2. **稳定性**：免费模型可能存在不稳定的情况，建议在生产环境考虑付费版本或备选模型
3. **上下文长度**：根据实际任务需求选择合适的上下文窗口，避免浪费
4. **成本控制**：虽然都是免费模型，但合理分配模型大小有助于控制总体响应时间

## 更新日志

- 2025-01-XX: 更新免费模型列表，避开 Gemini 模型
- 推荐使用 Llama 3.3 70B 替代 Gemini 2.0 Flash 用于高质量任务
- 保持 Llama 3.2 3B 用于快速响应任务




