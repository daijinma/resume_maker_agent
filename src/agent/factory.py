from src.agent.session import SessionManager
from src.agent.router import Router
from src.agent.workers import InfoWorker, ExperienceWorker, SkillWorker
from src.agent.inference import InferenceWorker
from src.agent.aggregator import Aggregator
from src.agent.executor import Executor
from src.agent.orchestrator import Orchestrator

# 初始化基础组件
session_manager = SessionManager()
router = Router()
workers = {
    "info": InfoWorker(),
    "experience": ExperienceWorker(),
    "skill": SkillWorker()
}
inference_worker = InferenceWorker()
aggregator = Aggregator()
executor = Executor()

# 初始化核心编排器
orchestrator = Orchestrator(
    router=router,
    workers=workers,
    inference_worker=inference_worker,
    aggregator=aggregator,
    executor=executor,
    session_manager=session_manager
)
