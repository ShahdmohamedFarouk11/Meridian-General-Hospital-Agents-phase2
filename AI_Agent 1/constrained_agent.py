import os
import time
import json
from enum import Enum
from typing import Literal, Dict, Any, Optional
from dotenv import load_dotenv

from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

from tools import (
    assign_triage_level,
    check_hospital_resources,
    get_patient_history,
    assess_surgery_risk,
    check_transfer_options,
    allocate_resource,
)

load_dotenv()

class AllowedActions(str, Enum):
    ASSIGN_TRIAGE_LEVEL = "assign_triage_level"
    CHECK_RESOURCES = "check_hospital_resources"
    GET_PATIENT_HISTORY = "get_patient_history"
    ASSESS_SURGERY_RISK = "assess_surgery_risk"
    CHECK_TRANSFERS = "check_transfer_options"
    ALLOCATE_RESOURCE = "allocate_resource"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    FINAL_DECISION = "final_decision"

# Pydantic schema strictly defining types
class ConstrainedAgentStep(BaseModel):
    thought: str = Field(description="Clinical reasoning for the current step.")
    urgency_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(description="Patient urgency level.")
    action: AllowedActions = Field(description="Action to execute next.")
    action_input_str: str = Field(
        default="{}", 
        description="Parameters for the action as a valid JSON string (e.g. '{\"triage_level\": 1, \"patient_id\": \"P-001\"}'). Use lowercase true/false for booleans."
    )

# Using llama-3.3-70b-versatile for precise tool output syntax
llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0)
structured_llm = llm.with_structured_output(ConstrainedAgentStep)

tools_map = {
    AllowedActions.ASSIGN_TRIAGE_LEVEL: assign_triage_level,
    AllowedActions.CHECK_RESOURCES: check_hospital_resources,
    AllowedActions.GET_PATIENT_HISTORY: get_patient_history,
    AllowedActions.ASSESS_SURGERY_RISK: assess_surgery_risk,
    AllowedActions.CHECK_TRANSFERS: check_transfer_options,
    AllowedActions.ALLOCATE_RESOURCE: allocate_resource,
}

SYSTEM_PROMPT = """You are an Emergency Hospital Triage AI Agent.

STRICT EXECUTION PROTOCOL:
1. First step: Use 'assign_triage_level'. Pass parameters extracted from Current Task (e.g., triage_level, patient_id).
2. Second step: Use 'check_hospital_resources'. Pass parameters extracted from Current Task (e.g., available_doctors, available_or_rooms, available_icu_beds, available_ventilators).
3. Third step: Choose 'final_decision'.

RULES:
- NEVER execute an action that is ALREADY listed in Executed Actions.
- Extract relevant clinical and resource variables from Current Task into `action_input_str`.
- If both 'assign_triage_level' AND 'check_hospital_resources' are done, your ONLY allowed next action is 'final_decision'.
- Format `action_input_str` as a valid JSON string (use lowercase true/false for booleans and numbers for integers)."""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("user", "Executed Actions:\n{executed_actions}\n\nExecution History:\n{history}\n\nCurrent Task: {input}")
])

def run_constrained_agent(user_query: str, max_steps: int = 5):
    history = []
    executed_actions = set()
    print(f"\n[Task Started]: {user_query}\n" + "-" * 50)

    for step_num in range(1, max_steps + 1):
        history_text = "\n".join(history) if history else "None"
        executed_text = ", ".join(executed_actions) if executed_actions else "None"
        
        formatted_prompt = prompt.format_messages(
            executed_actions=executed_text, 
            history=history_text, 
            input=user_query
        )

        step_output = None
        # Retries for API calls / rate limits
        for attempt in range(3):
            try:
                step_output = structured_llm.invoke(formatted_prompt)
                break
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg:
                    print(f"Rate limit hit. Retrying in 3 seconds... (Attempt {attempt+1})")
                    time.sleep(3)
                else:
                    print(f"Invocation error: {e}")
                    time.sleep(1)

        if not step_output:
            print("Failed to get response from Model. Terminating run.")
            break

        print(f"\n--- Step {step_num} ---")
        print(f"Thought: {step_output.thought}")
        print(f"Urgency: {step_output.urgency_level}")
        print(f"Action Chosen: {step_output.action.value}")
        print(f"Input JSON: {step_output.action_input_str}")

        action_name = step_output.action.value

        if step_output.action == AllowedActions.FINAL_DECISION:
            print("\n[FINAL DECISION REACHED]")
            return step_output.thought

        if step_output.action == AllowedActions.ESCALATE_TO_HUMAN:
            print("\n[ESCALATED TO HUMAN DOCTOR]")
            return f"Escalated to doctor: {step_output.thought}"

        # Hard guardrail against duplicate tools
        if action_name in executed_actions:
            warning_msg = f"Action '{action_name}' was ALREADY executed! You MUST select 'final_decision' or a different action."
            print(f"System Enforcement: {warning_msg}")
            history.append(warning_msg)
            continue

        tool_func = tools_map.get(step_output.action)
        if tool_func:
            # Parse parameters safely
            try:
                action_args = json.loads(step_output.action_input_str) if step_output.action_input_str else {}
            except Exception:
                action_args = {}

            try:
                observation = tool_func(**action_args)
                print(f"Observation: {observation}")
                history.append(f"Action '{action_name}' executed. Result: {observation}")
                executed_actions.add(action_name)
            except Exception as e:
                error_msg = f"Action '{action_name}' failed with error: {str(e)}"
                print(f"Error Caught: {error_msg}")
                history.append(error_msg)

        time.sleep(1)

    return "Safety Timeout: Reached maximum allowed steps."