# 1) Imports
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub

from tools import (
    check_hospital_resources,
    get_patient_history,
    assess_surgery_risk,
    check_transfer_options,
    allocate_resource
)

# 2) Load environment
load_dotenv()

# 3) Create Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

# 4) Define tools
tools = [
    Tool(
        name="check_hospital_resources",
        func=check_hospital_resources,
        description="Check available hospital resources."
    ),

    Tool(
        name="get_patient_history",
        func=get_patient_history,
        description="Get patient medical history."
    ),

    Tool(
        name="assess_surgery_risk",
        func=assess_surgery_risk,
        description="Assess surgery risk."
    ),

    Tool(
        name="check_transfer_options",
        func=check_transfer_options,
        description="Check transfer options."
    ),

    Tool(
        name="allocate_resource",
        func=allocate_resource,
        description="Allocate hospital resource."
    )
]

# 5) Create ReAct Agent
agent = create_react_agent(
    llm,
    tools
)

# 6) Agent Executor
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True
)