# LLM 调用配置梳理报告

## 概述
本报告梳理了系统中所有 LLM 调用的参数配置情况，检查是否合理配置化。

## 配置文件位置
- **主配置文件**: `src/config/models.json`
- **配置加载类**: `src/config/models.py` (ModelConfig)

## 配置参数说明
所有 Agent 配置包含以下参数：
- `models`: 模型列表（支持多个备选模型，自动切换）
- `temperature`: 温度参数（控制随机性，0.0-2.0）
- `max_tokens`: 最大输出 token 数
- `timeout`: 请求超时时间（秒）

## 各 Agent 配置情况

### ✅ 已完全配置化（从配置文件读取）

#### 1. Router (`src/agents/router.py`)
- **配置类型**: `planner`
- **参数来源**: `ModelConfig.get_model_config("planner")`
- **状态**: ✅ 完全配置化
- **配置值**:
  - models: `["meta-llama/llama-3.2-3b-instruct:free", "qwen/qwen3-4b:free"]`
  - temperature: `0.3`
  - max_tokens: `4096`
  - timeout: `30.0`

#### 2. Aggregator (`src/agents/aggregator.py`)
- **配置类型**: `aggregator`
- **参数来源**: `ModelConfig.get_model_config("aggregator")`
- **状态**: ✅ 完全配置化
- **配置值**:
  - models: `["meta-llama/llama-3.2-3b-instruct:free", "qwen/qwen3-4b:free"]`
  - temperature: `0.3`
  - max_tokens: `4096`
  - timeout: `30.0`

#### 3. InferenceWorker (`src/agents/inference.py`)
- **配置类型**: `inference`
- **参数来源**: `ModelConfig.get_model_config("inference")`
- **状态**: ✅ 完全配置化
- **配置值**:
  - models: `["meta-llama/llama-3.3-70b-instruct:free", "mistralai/mistral-small-3.1-24b-instruct:free"]`
  - temperature: `0.3`
  - max_tokens: `8192`
  - timeout: `60.0`

#### 4. InfoWorker (`src/agents/info_worker.py`)
- **配置类型**: `info_worker`
- **参数来源**: `ModelConfig.get_model_config("info_worker")`
- **状态**: ✅ 完全配置化
- **配置值**:
  - models: `["mistralai/mistral-small-3.1-24b-instruct:free", "meta-llama/llama-3.2-3b-instruct:free"]`
  - temperature: `0.3`
  - max_tokens: `4096`
  - timeout: `30.0`

#### 5. ExperienceWorker (`src/agents/experience_worker.py`)
- **配置类型**: `experience_worker`
- **参数来源**: `ModelConfig.get_model_config("experience_worker")`
- **状态**: ✅ 完全配置化
- **配置值**:
  - models: `["meta-llama/llama-3.3-70b-instruct:free", "mistralai/mistral-small-3.1-24b-instruct:free"]`
  - temperature: `0.3`
  - max_tokens: `8192`
  - timeout: `60.0`

#### 6. SkillWorker (`src/agents/skill_worker.py`)
- **配置类型**: `skill_worker`
- **参数来源**: `ModelConfig.get_model_config("skill_worker")`
- **状态**: ✅ 完全配置化
- **配置值**:
  - models: `["mistralai/mistral-small-3.1-24b-instruct:free", "qwen/qwen3-4b:free"]`
  - temperature: `0.3`
  - max_tokens: `4096`
  - timeout: `30.0`

#### 7. BackgroundReasoner (`src/agents/background_reasoner.py`)
- **配置类型**: `inference`
- **参数来源**: `ModelConfig.get_model_config("inference")`
- **状态**: ✅ 完全配置化
- **配置值**: 同 InferenceWorker

### ⚠️ 部分硬编码默认值（需优化）

#### 8. SideRouter (`src/agents/side_router.py`)
- **配置类型**: `side_router`
- **参数来源**: `ModelConfig.get_model_config("side_router")`
- **状态**: ⚠️ 有硬编码默认值
- **问题**:
  ```python
  max_tokens=config.get("max_tokens", 1024),  # 硬编码默认值
  timeout=config.get("timeout", 15.0)        # 硬编码默认值
  ```
- **建议**: 移除硬编码默认值，配置文件已包含这些值
- **配置值**:
  - models: `["qwen/qwen3-4b:free", "meta-llama/llama-3.2-3b-instruct:free"]`
  - temperature: `0.3`
  - max_tokens: `1024`
  - timeout: `15.0`

#### 9. FastResponse (`src/service/dual_track_service.py`)
- **配置类型**: `fast_response`
- **参数来源**: `ModelConfig.get_model_config("fast_response")`
- **状态**: ⚠️ 有硬编码默认值
- **问题**:
  ```python
  temperature=fast_config.get("temperature", 0.3),      # 硬编码默认值
  max_tokens=fast_config.get("max_tokens", 2048),       # 硬编码默认值
  timeout=fast_config.get("timeout", 20.0)              # 硬编码默认值
  ```
- **建议**: 移除硬编码默认值，配置文件已包含这些值
- **配置值**:
  - models: `["qwen/qwen3-4b:free", "meta-llama/llama-3.2-3b-instruct:free"]`
  - temperature: `0.3`
  - max_tokens: `2048`
  - timeout: `20.0`

### ❌ 完全硬编码（需重构）

#### 10. Executor (`src/agents/executor.py`)
- **状态**: ❌ 完全硬编码，未使用配置系统
- **问题**:
  ```python
  self.model = "meta-llama/llama-3.3-70b-instruct:free"  # 硬编码模型
  temperature=0.3,  # 硬编码温度
  # 缺少 max_tokens 和 timeout 配置
  ```
- **建议**: 
  1. 在 `models.json` 中添加 `executor` 配置
  2. 使用 `ModelConfig.get_model_config("executor")` 获取配置
  3. 统一使用 `BaseAgent` 或至少使用配置系统
- **当前配置**:
  - model: `meta-llama/llama-3.3-70b-instruct:free`
  - temperature: `0.3`
  - max_tokens: 未设置（使用模型默认值）
  - timeout: 未设置（使用客户端默认值）

## 配置合理性分析

### 模型选择
- **小模型** (3b-4b): Router, Aggregator, SideRouter, FastResponse, SkillWorker
  - ✅ 合理：用于简单路由、聚合、快速响应
- **中等模型** (24b): InfoWorker
  - ✅ 合理：用于信息提取
- **大模型** (70b): ExperienceWorker, InferenceWorker
  - ✅ 合理：用于复杂推理和深度分析

### Temperature 设置
- **统一为 0.3**: ✅ 合理
  - 所有 Agent 都使用 0.3，保证输出稳定性和一致性
  - 适合结构化数据提取和决策任务

### Max Tokens 设置
- **1024**: SideRouter - ✅ 合理（简单路由判断）
- **2048**: FastResponse - ✅ 合理（简短确认回复）
- **4096**: Router, Aggregator, InfoWorker, SkillWorker - ✅ 合理（标准任务）
- **8192**: ExperienceWorker, InferenceWorker - ✅ 合理（复杂分析任务）

### Timeout 设置
- **15秒**: SideRouter - ✅ 合理（快速判断）
- **20秒**: FastResponse - ✅ 合理（快速响应）
- **30秒**: Router, Aggregator, InfoWorker, SkillWorker - ✅ 合理（标准任务）
- **60秒**: ExperienceWorker, InferenceWorker - ✅ 合理（复杂任务，需要更长时间）

## 发现的问题

### 1. 硬编码默认值问题
- **SideRouter**: 有硬编码默认值，但配置文件已包含
- **FastResponse**: 有硬编码默认值，但配置文件已包含
- **影响**: 如果配置文件缺失字段，会使用硬编码值，但实际配置文件完整，这些默认值不会生效

### 2. Executor 未配置化
- **严重性**: 中等
- **影响**: 
  - 无法通过配置文件调整模型和参数
  - 与其他 Agent 不一致
  - 缺少 max_tokens 和 timeout 控制

### 3. 配置一致性
- **BaseAgent 默认值**: `temperature=0.3` 在 BaseAgent 构造函数中也有默认值
- **建议**: 保持一致性，所有 Agent 都从配置读取，BaseAgent 的默认值仅作为最后兜底

## 建议改进

### 优先级 1: 移除不必要的硬编码默认值
1. **SideRouter**: 移除 `max_tokens` 和 `timeout` 的硬编码默认值
2. **FastResponse**: 移除 `temperature`, `max_tokens`, `timeout` 的硬编码默认值

### 优先级 2: 配置化 Executor
1. 在 `models.json` 中添加 `executor` 配置
2. 重构 `Executor` 类，使用配置系统
3. 考虑统一使用 `BaseAgent` 基类

### 优先级 3: 配置验证
1. 在 `ModelConfig.get_model_config()` 中添加配置验证
2. 确保所有必需字段存在
3. 提供清晰的错误提示

## 总结

### 配置化程度
- ✅ **完全配置化**: 7 个 Agent (70%)
- ⚠️ **部分硬编码**: 2 个 Agent (20%)
- ❌ **未配置化**: 1 个 Agent (10%)

### 配置合理性
- ✅ 模型选择合理（根据任务复杂度选择）
- ✅ Temperature 设置统一且合理
- ✅ Max Tokens 设置符合任务需求
- ✅ Timeout 设置符合任务复杂度

### 总体评价
系统整体配置化程度较高，参数设置合理。主要改进点是：
1. 移除不必要的硬编码默认值（SideRouter, FastResponse）
2. 配置化 Executor 类
3. 增强配置验证机制

