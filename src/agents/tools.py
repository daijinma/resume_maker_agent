import datetime
import logging
from langchain_core.tools import tool

logger = logging.getLogger("resume-agent.tools")

@tool
def get_current_time() -> str:
    """获取当前的系统日期和时间。用于判断用户是否已经毕业或计算工龄。"""
    now = datetime.datetime.now()
    result = now.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"[Tool Call] get_current_time -> {result}")
    return result

@tool
def edu_date_predictor(start_date: str, degree_type: str) -> str:
    """
    根据入学日期和学位类型预测毕业日期。
    参数:
    - start_date: 入学日期，如 "2019.09"
    - degree_type: 学位类型，如 "本科", "硕士", "博士"
    """
    try:
        year = int(start_date.split('.')[0])
        # 常见学制推断
        duration_map = {
            "本科": 4,
            "大专": 3,
            "硕士": 3,
            "研究生": 3,
            "博士": 4
        }
        duration = duration_map.get(degree_type, 4)
        end_year = year + duration
        result = f"{end_year}.06"
        logger.info(f"[Tool Call] edu_date_predictor(start={start_date}, degree={degree_type}) -> {result}")
        return result
    except Exception as e:
        return f"无法预测: {str(e)}"

@tool
def date_diff_calculator(start_date: str, end_date: str) -> str:
    """计算两个日期之间的年限。用于校验简历逻辑。"""
    # 简化实现，仅做演示
    logger.info(f"[Tool Call] date_diff_calculator(start={start_date}, end={end_date})")
    return "计算完成"

# 工具列表
RESUME_TOOLS = [get_current_time, edu_date_predictor, date_diff_calculator]
