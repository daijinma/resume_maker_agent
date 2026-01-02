"""
模型配置
"""
import os
import json
import re
import logging
import threading
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("resume-agent.config")


class ModelConfig:
    """LLM 模型配置 - 从 JSON 文件加载"""
    
    _config: Optional[Dict[str, Any]] = None
    _config_path: Optional[Path] = None
    
    # 模型轮询机制：为每个agent类型维护一个计数器，避免并发agent使用同一模型
    _model_index_counters: Dict[str, int] = {}
    _counter_lock = threading.Lock()
    
    # 向后兼容：保留旧的类属性（从 JSON 或环境变量获取）
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    BASE_URL = "https://openrouter.ai/api/v1"
    DEFAULT_HEADERS = {
        "HTTP-Referer": "https://github.com/copilot",
        "X-Title": "Resume Multi-Agent System",
    }
    ENABLE_BACKGROUND_REASONING = os.getenv("ENABLE_BACKGROUND_REASONING", "true").lower() == "true"
    
    @classmethod
    def _get_config_path(cls) -> Path:
        """获取配置文件路径"""
        if cls._config_path is None:
            base_dir = Path(__file__).parent
            cls._config_path = base_dir / "models.json"
        return cls._config_path
    
    @classmethod
    def _substitute_env_vars(cls, value: Any) -> Any:
        """递归替换配置值中的环境变量"""
        if isinstance(value, str):
            # 替换 ${VAR_NAME} 格式的环境变量
            def replace_env(match):
                var_name = match.group(1)
                return os.getenv(var_name, match.group(0))
            return re.sub(r'\$\{([^}]+)\}', replace_env, value)
        elif isinstance(value, dict):
            return {k: cls._substitute_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [cls._substitute_env_vars(item) for item in value]
        else:
            return value
    
    @classmethod
    def _load_config(cls) -> Dict[str, Any]:
        """从 JSON 文件加载配置"""
        if cls._config is not None:
            return cls._config
        
        config_path = cls._get_config_path()
        
        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
            cls._config = cls._get_default_config()
            return cls._config
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
            
            # 替换环境变量
            cls._config = cls._substitute_env_vars(raw_config)
            
            # 更新类属性以保持向后兼容
            if "openrouter" in cls._config:
                openrouter = cls._config["openrouter"]
                cls.OPENROUTER_API_KEY = openrouter.get("api_key") or cls.OPENROUTER_API_KEY
                cls.BASE_URL = openrouter.get("base_url", cls.BASE_URL)
                cls.DEFAULT_HEADERS = openrouter.get("default_headers", cls.DEFAULT_HEADERS)
            
            logger.info(f"成功加载配置文件: {config_path}")
            return cls._config
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 配置文件格式错误: {e}，使用默认配置")
            cls._config = cls._get_default_config()
            return cls._config
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            cls._config = cls._get_default_config()
            return cls._config
    
    @classmethod
    def _get_default_config(cls) -> Dict[str, Any]:
        """获取默认配置（向后兼容）"""
        return {
            "openrouter": {
                "api_key": cls.OPENROUTER_API_KEY,
                "base_url": cls.BASE_URL,
                "default_headers": cls.DEFAULT_HEADERS
            },
            "agents": {
                "planner": {
                    "models": ["meta-llama/llama-3.2-3b-instruct:free"],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "timeout": 30.0
                },
                "info_worker": {
                    "models": ["mistralai/mistral-small-3.1-24b-instruct:free"],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "timeout": 30.0
                },
                "experience_worker": {
                    "models": ["meta-llama/llama-3.3-70b-instruct:free"],
                    "temperature": 0.3,
                    "max_tokens": 8192,
                    "timeout": 60.0
                },
                "skill_worker": {
                    "models": ["mistralai/mistral-small-3.1-24b-instruct:free"],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "timeout": 30.0
                },
                "inference": {
                    "models": ["meta-llama/llama-3.3-70b-instruct:free"],
                    "temperature": 0.3,
                    "max_tokens": 8192,
                    "timeout": 60.0
                },
                "aggregator": {
                    "models": ["meta-llama/llama-3.2-3b-instruct:free"],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                    "timeout": 30.0
                },
                "fast_response": {
                    "models": ["qwen/qwen3-4b:free"],
                    "temperature": 0.3,
                    "max_tokens": 2048,
                    "timeout": 20.0
                }
            }
        }
    
    @classmethod
    def get_model_config(cls, agent_type: str) -> Dict[str, Any]:
        """
        获取指定 Agent 的完整配置
        
        Args:
            agent_type: Agent 类型（如 "planner", "info_worker" 等）
        
        Returns:
            Dict: 包含 models, temperature, max_tokens, timeout 的配置字典
        """
        config = cls._load_config()
        agents = config.get("agents", {})
        
        if agent_type not in agents:
            logger.warning(f"未找到 Agent 配置: {agent_type}，使用默认配置")
            return {
                "models": ["meta-llama/llama-3.2-3b-instruct:free"],
                "temperature": 0.3,
                "max_tokens": 4096,
                "timeout": 30.0,
                "initial_model_index": 0
            }
        
        agent_config = agents[agent_type].copy()
        
        # 确保 models 是列表格式（向后兼容）
        if isinstance(agent_config.get("models"), str):
            agent_config["models"] = [agent_config["models"]]
        elif not isinstance(agent_config.get("models"), list):
            agent_config["models"] = ["meta-llama/llama-3.2-3b-instruct:free"]
        
        # 确保 models 列表不为空
        if not agent_config["models"]:
            agent_config["models"] = ["meta-llama/llama-3.2-3b-instruct:free"]
        
        # 使用轮询机制分配初始模型索引，避免并发agent使用同一模型
        initial_index = cls._get_next_model_index(agent_type, len(agent_config["models"]))
        agent_config["initial_model_index"] = initial_index
        
        return agent_config
    
    @classmethod
    def _get_next_model_index(cls, agent_type: str, model_count: int) -> int:
        """
        为指定agent类型获取下一个模型索引（轮询机制）
        
        Args:
            agent_type: Agent 类型
            model_count: 可用模型数量
        
        Returns:
            int: 初始模型索引（0 到 model_count-1）
        """
        with cls._counter_lock:
            if agent_type not in cls._model_index_counters:
                cls._model_index_counters[agent_type] = 0
            
            # 获取当前索引并递增
            current_index = cls._model_index_counters[agent_type]
            cls._model_index_counters[agent_type] = (current_index + 1) % model_count
            
            logger.debug(f"Agent [{agent_type}] 分配初始模型索引: {current_index} (共 {model_count} 个模型)")
            return current_index
    
    @classmethod
    def get_openrouter_config(cls) -> Dict[str, Any]:
        """
        获取 OpenRouter 基础配置
        
        Returns:
            Dict: 包含 api_key, base_url, default_headers 的配置字典
        """
        config = cls._load_config()
        openrouter = config.get("openrouter", {})
        
        # 如果 api_key 是环境变量占位符，尝试从环境变量获取
        api_key = openrouter.get("api_key")
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            var_name = api_key[2:-1]
            api_key = os.getenv(var_name, api_key)
        
        return {
            "api_key": api_key or cls.OPENROUTER_API_KEY,
            "base_url": openrouter.get("base_url", cls.BASE_URL),
            "default_headers": openrouter.get("default_headers", cls.DEFAULT_HEADERS)
        }
    
    # 向后兼容：保留旧的属性访问方式（类属性）
    @classmethod
    def _get_legacy_model(cls, agent_type: str) -> str:
        """获取旧格式的单个模型（向后兼容）"""
        config = cls.get_model_config(agent_type)
        models = config.get("models", [])
        return models[0] if models else "meta-llama/llama-3.2-3b-instruct:free"
    
    # 向后兼容：动态类属性（通过 __getattr__ 实现）
    def __getattr__(self, name: str):
        """向后兼容：支持 ModelConfig.MODEL_PLANNER 等旧属性访问"""
        legacy_mapping = {
            "MODEL_PLANNER": "planner",
            "MODEL_INFO_WORKER": "info_worker",
            "MODEL_EXP_WORKER": "experience_worker",
            "MODEL_SKILL_WORKER": "skill_worker",
            "MODEL_INFERENCE": "inference",
            "MODEL_AGGREGATOR": "aggregator",
            "MODEL_FAST_RESPONSE": "fast_response"
        }
        
        if name in legacy_mapping:
            return self._get_legacy_model(legacy_mapping[name])
        
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    @classmethod
    def __getattr__(cls, name: str):
        """向后兼容：支持类级别的属性访问"""
        legacy_mapping = {
            "MODEL_PLANNER": "planner",
            "MODEL_INFO_WORKER": "info_worker",
            "MODEL_EXP_WORKER": "experience_worker",
            "MODEL_SKILL_WORKER": "skill_worker",
            "MODEL_INFERENCE": "inference",
            "MODEL_AGGREGATOR": "aggregator",
            "MODEL_FAST_RESPONSE": "fast_response"
        }
        
        if name in legacy_mapping:
            return cls._get_legacy_model(legacy_mapping[name])
        
        raise AttributeError(f"'{cls.__name__}' object has no attribute '{name}'")

