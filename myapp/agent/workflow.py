from typing import TypedDict, List, Literal
import random

# 1. Define State
class WorkflowState(TypedDict):
    messages: List[str]
    next_action: Literal["llm", "tool", "human", "exit"]
    retries: int

# 2. Define Nodes
def llm_node(state: WorkflowState) -> WorkflowState:
    last_msg = state["messages"][-1]
    
    # Simulated LLM decision-making
    if "weather" in last_msg:
        state["messages"].append("I'll check the weather API")
        state["next_action"] = "tool"
    elif "error" in last_msg:
        state["messages"].append("Attempting to fix error")
        state["retries"] += 1
        state["next_action"] = "llm" if state["retries"] < 3 else "human"
    else:
        state["messages"].append("Here's the final answer")
        state["next_action"] = "exit"
    return state

def tool_node(state: WorkflowState) -> WorkflowState:
    # Simulate API call with 20% error rate
    if random.random() < 0.2:
        state["messages"].append("API_ERROR: Weather service down")
        state["next_action"] = "llm"
    else:
        state["messages"].append("WEATHER_DATA: Sunny, 25°C")
        state["next_action"] = "llm"
    return state

def human_node(state: WorkflowState) -> WorkflowState:
    state["messages"].append("Human: Please review this issue")
    state["next_action"] = "exit"
    return state

# 3. Workflow Orchestrator
def run_workflow(initial_input: str):
    state: WorkflowState = {
        "messages": [initial_input],
        "next_action": "llm",
        "retries": 0
    }
    
    while state["next_action"] != "exit":
        current_action = state["next_action"]
        
        if current_action == "llm":
            state = llm_node(state)
        elif current_action == "tool":
            state = tool_node(state)
        elif current_action == "human":
            state = human_node(state)
            
        print(f"Step: {current_action.upper()} -> {state['messages'][-1]}")
    
    print("\nFinal workflow path:")
    for i, msg in enumerate(state["messages"]):
        print(f"{i+1}. {msg}")

# 4. Run Example
run_workflow("User: What's the weather in Paris?")