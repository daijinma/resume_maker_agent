"""简易演示流程：调度 Planner/Executor/Tooling 三层构件，模拟一次聊天生成简历的过程。"""
from agent import Executor, Planner, Tooling
from typing import Dict, List


def run_demo_flow() -> None:
    planner = Planner()
    executor = Executor()
    tooling = Tooling()

    # 模拟用户的前两轮输入
    planner.ingest_user_message("我是一名金融分析师，最近负责某基金的定量分析项目，准备投研岗位简历。")
    planner.state.pending_questions.append("请补充该项目的量化成果（如增长率/收益）。")
    print("用户：我是一名金融分析师...投研岗位")
    print("Planner：", planner.next_action())

    planner.ingest_user_message("项目达成了 15% 的年化收益，团队 5 人，我负责模型建模。")
    print("用户：补充成果、团队信息")
    print("Planner：", planner.next_action())

    # 生成正文前先获取岗位默认模板
    role = "投研+量化模型"
    templates = tooling.fetch_template(role)

    structured_context: Dict[str, str] = {
        "project": "负责某基金的量化分析模型，从数据清洗、特征工程到回测和部署，成果 15% 年化收益。",
        "skill": "熟练使用 Python、Pandas、NumPy，掌握因子分析与风险管理框架。",
    }

    generated_sections: List[str] = []
    print("\n--- 生成简历各模块 ---")
    for section, details in structured_context.items():
        section_text = executor.generate_section(section, details)
        if not executor.validate(section_text)["contains_result"]:
            section_text += "（请在后续中继续丰富成果数据）"
        refined = tooling.refine_language(section_text)
        generated_sections.append(refined)
        print(refined)

    print("\n--- 生成模板参考 ---")
    for key, template in templates.items():
        print(f"{key} 模板：{template}")

    print("\n完成：已根据简历意图生成基础段落，后续可用 LLM 替换 Executor 内容生成段。")


if __name__ == "__main__":
    run_demo_flow()
