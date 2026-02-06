from typing import TypedDict, List, Literal
import random

from yaafpy.adapters import as_middleware
from yaafpy.types import ExecContext, AgentConfig
from yaafpy.workflows import Workflow

from .steps import ( 
                    router, 
                    build_prompt_process_time, 
                    query_llm, 
                    parse_json, 
                    build_prompt_follow_up, 
                    build_prompt_get_update_info,
                    load_data,
                    user_input_guardrail,
                    process_location,
                    time_output_guardrail,
                    state_output_guardrail,
                    persist_state,
                    persist_message,
                    add_message,
                    follow_up_processing
                    )



transform_time_Agent = Workflow()
transform_time_Agent.use(build_prompt_process_time)
transform_time_Agent.use(query_llm)
transform_time_Agent.use(parse_json)
transform_time_Agent.use(time_output_guardrail)


ask_follow_Agent = Workflow()
ask_follow_Agent.use(build_prompt_follow_up)
ask_follow_Agent.use(query_llm)
ask_follow_Agent.use(parse_json)
ask_follow_Agent.use(follow_up_processing)
ask_follow_Agent.use(add_message)
ask_follow_Agent.use(persist_message)

state_managment_Agent = Workflow()
state_managment_Agent.use(user_input_guardrail)
state_managment_Agent.use(load_data)
state_managment_Agent.use(build_prompt_get_update_info)
state_managment_Agent.use(query_llm)
state_managment_Agent.use(parse_json)
state_managment_Agent.use(state_output_guardrail)
state_managment_Agent.use(add_message)
state_managment_Agent.use(process_location)
state_managment_Agent.use(as_middleware(transform_time_Agent))
state_managment_Agent.use(persist_state)



booking_assitant_Agent = Workflow()
booking_assitant_Agent.use(as_middleware(state_managment_Agent),name="update_state")
booking_assitant_Agent.use(router, name="what_is_next_action")
booking_assitant_Agent.use(as_middleware(ask_follow_Agent),name="ask_follow_up")


