import os
import time
from dotenv import load_dotenv

from langchain_groq.chat_models import ChatGroq
from langchain.agents import create_agent as create_react_agent
from langgraph.constants import END
from langgraph.graph import StateGraph

from prompts import planner_prompt, architect_prompt, coder_system_prompt
from states import Plan, TaskPlan, CoderState
from tools import read_file, write_file, list_files, get_current_directory

# ================== Setup ==================
_ = load_dotenv()

api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY environment variable is not set.")

llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=api_key)


# ================== Utils ==================
def invoke_with_retry(runnable, input_data, max_retries=3):
    """Invoke a runnable with retry + exponential backoff for rate limits."""
    for attempt in range(max_retries):
        try:
            return runnable.invoke(input_data)
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate_limit" in msg:
                wait = 2 ** attempt * 5  # 5s, 10s, 20s
                print(f"[Retry] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded due to rate limiting.")


# ================== Agents ==================
def planner_agent(state: dict) -> dict:
    """Converts user prompt into a structured Plan."""
    user_prompt = state["user_prompt"]

    resp = invoke_with_retry(
        llm.with_structured_output(Plan),
        planner_prompt(user_prompt),
    )

    if resp is None:
        raise ValueError("Planner did not return a valid response.")

    return {**state, "plan": resp}


def architect_agent(state: dict) -> dict:
    """Creates TaskPlan from Plan."""
    plan: Plan = state["plan"]

    resp = invoke_with_retry(
        llm.with_structured_output(TaskPlan),
        architect_prompt(plan=plan.model_dump_json()),
    )

    if resp is None:
        raise ValueError("Architect did not return a valid response.")

    print("\n[Architect Output]")
    print(resp.model_dump_json(indent=2))

    return {**state, "task_plan": resp}


def coder_agent(state: dict) -> dict:
    """LangGraph tool-using coder agent."""
    coder_state: CoderState = state.get("coder_state")

    if coder_state is None:
        coder_state = CoderState(task_plan=state["task_plan"], current_step_idx=0)

    steps = coder_state.task_plan.implementation_steps

    if coder_state.current_step_idx >= len(steps):
        print("\n[Coder] All steps completed.")
        return {**state, "coder_state": coder_state, "status": "DONE"}

    current_task = steps[coder_state.current_step_idx]
    existing_content = read_file.run(current_task.filepath)

    system_prompt = coder_system_prompt()
    user_prompt = (
        f"Task: {current_task.task_description}\n"
        f"File: {current_task.filepath}\n"
        f"Existing content:\n{existing_content}\n"
    )

    coder_tools = [read_file, write_file, list_files, get_current_directory]
    react_agent = create_react_agent(llm, coder_tools)

    print(f"\n[Coder] Step {coder_state.current_step_idx + 1}/{len(steps)}")
    print(f"-> Working on: {current_task.filepath}")

    invoke_with_retry(
        react_agent,
        {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        },
    )

    coder_state.current_step_idx += 1

    # Delay to avoid rate limits
    time.sleep(5)

    return {**state, "coder_state": coder_state}


# ================== LangGraph ==================
graph = StateGraph(dict)

graph.add_node("planner", planner_agent)
graph.add_node("architect", architect_agent)
graph.add_node("coder", coder_agent)

graph.add_edge("planner", "architect")
graph.add_edge("architect", "coder")

graph.add_conditional_edges(
    "coder",
    lambda s: "END" if s.get("status") == "DONE" else "coder",
    {"END": END, "coder": "coder"},
)

graph.set_entry_point("planner")
agent = graph.compile()


# ================== Run ==================
if __name__ == "__main__":
    result = agent.invoke(
        {"user_prompt": "Build a colourful modern todo app in html css and js"},
        {"recursion_limit": 100},
    )

    print("\n========== FINAL STATE ==========")
    print(result)
