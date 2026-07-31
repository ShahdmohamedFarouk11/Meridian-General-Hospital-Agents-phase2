#!/usr/bin/env python3
"""
agent/agent.py
--------------
MediCore Hospital Network -- Agent / MCP Client
Owner: Member 3 (Agent & Human-in-the-Loop Integration)
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mcp_protocol import JsonRpcEndpoint  # noqa: E402

DEFAULT_SERVER_ARGS = [
    sys.executable,
    os.path.join(os.path.dirname(__file__), "..", "mcp_server", "mock_server.py"),
]

# Point at real mcp_server when ready, e.g.:
# MCP_SERVER_CMD="python3 ../mcp_server/MCP.py"
SERVER_ARGS = os.environ.get("MCP_SERVER_CMD", "").split() or DEFAULT_SERVER_ARGS


class MediCoreAgent:
    def __init__(self, auto_confirm: bool = False):
        self.endpoint: JsonRpcEndpoint | None = None
        self.proc: asyncio.subprocess.Process | None = None
        self.server_capabilities = {}
        self.tools = []
        self.auto_confirm = auto_confirm
        self.scripted_answers: list[bool] = []

    async def start(self):
        self.proc = await asyncio.create_subprocess_exec(
            *SERVER_ARGS, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        )
        self.endpoint = JsonRpcEndpoint(
            self.proc.stdout, self.proc.stdin,
            request_handler=self._handle_server_request,
            notification_handler=self._handle_server_notification,
            name="client",
        )
        self._reader_task = asyncio.create_task(self.endpoint.run())

        init_result = await self.endpoint.send_request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {"elicitation": {}, "sampling": {}},
            "clientInfo": {"name": "medicore-agent", "version": "0.1.0"},
        })
        self.server_capabilities = init_result.get("capabilities", {})
        await self.endpoint.send_notification("initialized", {})

        await self._refresh_tools()

    async def stop(self):
        if self.proc:
            self.proc.terminate()
            await self.proc.wait()

    async def _refresh_tools(self):
        result = await self.endpoint.send_request("tools/list", {})
        self.tools = result.get("tools", [])

    def supports(self, capability: str) -> bool:
        return capability in self.server_capabilities

    async def _handle_server_request(self, method: str, params: dict):
        if method == "elicitation/create":
            return await self._handle_elicitation(params)
        if method == "sampling/createMessage":
            return await self._handle_sampling(params)
        raise ValueError(f"client cannot handle server request: {method}")

    async def _handle_elicitation(self, params: dict):
        message = params.get("message", "Confirm this action?")
        print(f"\n[ELICITATION] Server is pausing for human confirmation:\n  {message}")

        if self.scripted_answers:
            decision = self.scripted_answers.pop(0)
            print(f"[ELICITATION] (scripted test answer) -> {decision}")
        elif self.auto_confirm:
            decision = True
        else:
            raw = input("  Confirm? [y/N]: ").strip().lower()
            decision = raw == "y"

        return {"action": "accept" if decision else "decline", "content": {"confirm": decision}}

    async def _handle_sampling(self, params: dict):
        messages = params.get("messages", [])
        prompt_text = " ".join(
            m.get("content", {}).get("text", "") for m in messages if m.get("role") == "user"
        )
        text = await call_llm_for_sampling(prompt_text)
        return {"role": "assistant", "content": {"type": "text", "text": text}, "model": "client-llm"}

    async def _handle_server_notification(self, method: str, params: dict):
        if method == "notifications/tools/list_changed":
            before = {t["name"] for t in self.tools}
            await self._refresh_tools()
            after = {t["name"] for t in self.tools}
            new_tools = after - before
            if new_tools:
                print(f"[NOTIFICATION] tools/list_changed -> newly available: {sorted(new_tools)}")
        elif method == "notifications/progress":
            pct = params.get("progress", 0)
            total = params.get("total", 1)
            msg = params.get("message", "")
            bar = "#" * pct + "-" * max(total - pct, 0)
            print(f"[PROGRESS] [{bar}] {pct}/{total} {msg}")

    async def call_tool(self, name: str, arguments: dict):
        return await self.endpoint.send_request("tools/call", {"name": name, "arguments": arguments})

    async def read_resource(self, uri: str):
        return await self.endpoint.send_request("resources/read", {"uri": uri})

    async def get_prompt(self, name: str, arguments: dict):
        return await self.endpoint.send_request("prompts/get", {"name": name, "arguments": arguments})


async def call_llm_for_sampling(prompt_text: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return f"[offline-stub justification] {prompt_text[:80]}..."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-4-6", max_tokens=150,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    except Exception as e:
        return f"[sampling call failed, offline stub used: {e}]"


def decide_next_tool_call(user_message: str, tools: list, conversation: list) -> dict | None:
    text = user_message.lower()
    if "log" in text and ("in" in text or "authenticate" in text):
        return {"name": "login_as_doctor", "arguments": {"doctor_id": "D001", "pin": "1234"}}
    if "reserve" in text and "icu" in text:
        return {"name": "reserve_icu_bed", "arguments": {"patient_id": "P001", "bed_id": "ICU-B1"}}
    if "reserve" in text and ("operating" in text or "room" in text):
        return {"name": "reserve_operating_room", "arguments": {"patient_id": "P001", "room_id": "OR-1"}}
    if "icu" in text and "hospitals" in text:
        return {"name": "list_hospitals_with_available_icu", "arguments": {}}
    if "icu bed" in text or "available icu" in text:
        return {"name": "list_available_icu_beds", "arguments": {}}
    if "operating room" in text:
        return {"name": "list_available_operating_rooms", "arguments": {}}
    if "admission" in text or "admit" in text:
        return {"name": "create_admission",
                "arguments": {"patient_id": "P001", "doctor_id": "D001", "room_id": "OR-1"}}
    return None


async def run_llm_agent_turn(agent: MediCoreAgent, user_message: str):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            claude_tools = [
                {"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
                for t in agent.tools
            ]
            resp = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=500, tools=claude_tools,
                messages=[{"role": "user", "content": user_message}],
            )
            for block in resp.content:
                if getattr(block, "type", "") == "tool_use":
                    return {"name": block.name, "arguments": block.input}
            return None
        except Exception as e:
            print(f"[warn] live LLM call failed ({e}); falling back to offline planner")
    return decide_next_tool_call(user_message, agent.tools, [])


DEMO_SCRIPT = [
    "Log me in as the doctor on call",
    "Which hospitals currently have available ICU beds?",
    "Reserve an ICU bed for the patient",
    "Create the admission",
]


async def run_demo():
    agent = MediCoreAgent(auto_confirm=True)
    await agent.start()
    print(f"Server capabilities: {json.dumps(agent.server_capabilities, indent=2)}")
    print(f"Tools visible before login: {[t['name'] for t in agent.tools]}\n")

    for turn in DEMO_SCRIPT:
        print(f"\n>>> USER: {turn}")
        call = await run_llm_agent_turn(agent, turn)
        if not call:
            print("(agent had nothing actionable to do for this turn)")
            continue
        print(f"[AGENT] calling tool: {call['name']}({call['arguments']})")
        result = await agent.call_tool(call["name"], call["arguments"])
        print(f"[RESULT] {result}")

    await agent.stop()


async def run_interactive():
    agent = MediCoreAgent(auto_confirm=False)
    await agent.start()
    print("MediCore agent ready. Type a request (or 'quit').")
    while True:
        user_message = input("\nyou> ").strip()
        if user_message.lower() in ("quit", "exit"):
            break
        call = await run_llm_agent_turn(agent, user_message)
        if not call:
            print("(no matching tool for that request in this demo planner)")
            continue
        result = await agent.call_tool(call["name"], call["arguments"])
        print(f"result> {result}")
    await agent.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="run the fixed demo script")
    args = parser.parse_args()
    asyncio.run(run_demo() if args.demo else run_interactive())
