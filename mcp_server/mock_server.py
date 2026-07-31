#!/usr/bin/env python3
"""
testing_stub/mock_server.py
----------------------------
Stand-in MCP server for MediCore so agent/agent.py and test_e2e.py
can run end-to-end independently of the official mcp SDK.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent"))
from mcp_protocol import JsonRpcEndpoint, stdio_streams_for_this_process  # noqa: E402


PATIENTS = {
    "P001": {"patient_id": "P001", "name": "Amina Hassan", "age": 67,
             "condition": "post-op cardiac", "status": "waiting_admission"},
    "P002": {"patient_id": "P002", "name": "Omar Fathi", "age": 34,
             "condition": "trauma, stable", "status": "waiting_admission"},
}

ICU_BEDS = {
    "ICU-A1": {"bed_id": "ICU-A1", "hospital": "MediCore Downtown", "available": True},
    "ICU-A2": {"bed_id": "ICU-A2", "hospital": "MediCore Downtown", "available": False},
    "ICU-B1": {"bed_id": "ICU-B1", "hospital": "MediCore North", "available": True},
}

OPERATING_ROOMS = {
    "OR-1": {"room_id": "OR-1", "hospital": "MediCore Downtown", "available": True,
             "reserved_for": None},
    "OR-2": {"room_id": "OR-2", "hospital": "MediCore North", "available": False,
             "reserved_for": "P099"},
}

ADMISSIONS = {}

ICU_POLICY_DOC = (
    "MediCore ICU Admission & Prioritization Policy (v3):\n"
    "1. ICU beds are allocated by clinical acuity, not arrival order.\n"
    "2. When a hospital has exactly one ICU bed remaining, admission requires\n"
    "   explicit sign-off from an attending physician before the reservation\n"
    "   is finalized.\n"
    "3. Reassigning an operating room already reserved for another patient\n"
    "   requires the reassigning physician to confirm the original patient\n"
    "   has been rescheduled.\n"
    "4. Patient status changes to 'deceased' or 'discharged_against_medical_advice'\n"
    "   are irreversible in the record and require explicit confirmation.\n"
)

TRIAGE_PROMPT_TEMPLATE = (
    "Summarize the clinical picture for patient {patient_id} in 2-3 sentences "
    "for the admitting physician, and state whether ICU-level care appears "
    "warranted based on the condition on file."
)


class MediCoreMockServer:
    def __init__(self):
        self.endpoint: JsonRpcEndpoint | None = None
        self.role = "front_desk"
        self.client_capabilities = {}
        self.server_capabilities = {
            "tools": {"listChanged": True},
            "resources": {"listChanged": False},
            "prompts": {"listChanged": False},
            "elicitation": {},
            "sampling": {},
            "progress": {},
        }

    def read_tools(self):
        return [
            {"name": "get_patient", "description": "Retrieve patient details.",
             "inputSchema": {"type": "object",
                              "properties": {"patient_id": {"type": "string", "pattern": "^P[0-9]{3}$"}},
                              "required": ["patient_id"], "additionalProperties": False}},
            {"name": "list_available_icu_beds", "description": "Retrieve all available ICU beds.",
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "list_available_operating_rooms", "description": "Retrieve all available operating rooms.",
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"name": "list_hospitals_with_available_icu",
             "description": "Retrieve hospitals with available ICU beds (long-running, reports progress).",
             "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
        ]

    def write_tools(self):
        return [
            {"name": "reserve_icu_bed", "description": "Reserve an ICU bed for a patient.",
             "inputSchema": {"type": "object",
                              "properties": {
                                  "patient_id": {"type": "string", "pattern": "^P[0-9]{3}$"},
                                  "bed_id": {"type": "string", "pattern": "^ICU-[A-Z][0-9]$"},
                              },
                              "required": ["patient_id", "bed_id"], "additionalProperties": False}},
            {"name": "reserve_operating_room", "description": "Reserve an operating room for a patient.",
             "inputSchema": {"type": "object",
                              "properties": {
                                  "patient_id": {"type": "string", "pattern": "^P[0-9]{3}$"},
                                  "room_id": {"type": "string", "pattern": "^OR-[0-9]+$"},
                              },
                              "required": ["patient_id", "room_id"], "additionalProperties": False}},
            {"name": "create_admission", "description": "Create a new admission record.",
             "inputSchema": {"type": "object",
                              "properties": {
                                  "patient_id": {"type": "string", "pattern": "^P[0-9]{3}$"},
                                  "doctor_id": {"type": "string", "pattern": "^D[0-9]{3}$"},
                                  "room_id": {"type": "string"},
                              },
                              "required": ["patient_id", "doctor_id", "room_id"], "additionalProperties": False}},
            {"name": "update_patient_status", "description": "Update a patient's status.",
             "inputSchema": {"type": "object",
                              "properties": {
                                  "patient_id": {"type": "string", "pattern": "^P[0-9]{3}$"},
                                  "status": {"type": "string",
                                             "enum": ["waiting_admission", "admitted", "in_surgery",
                                                      "discharged", "discharged_against_medical_advice",
                                                      "deceased"]},
                              },
                              "required": ["patient_id", "status"], "additionalProperties": False}},
            {"name": "login_as_doctor",
             "description": "Authenticate as a physician to unlock write access (triggers tools/list_changed).",
             "inputSchema": {"type": "object",
                              "properties": {"doctor_id": {"type": "string", "pattern": "^D[0-9]{3}$"},
                                              "pin": {"type": "string"}},
                              "required": ["doctor_id", "pin"], "additionalProperties": False}},
        ]

    def visible_tools(self):
        return self.read_tools() + (self.write_tools() if self.role == "doctor" else [])

    async def handle_request(self, method: str, params: dict):
        if method == "initialize":
            self.client_capabilities = params.get("capabilities", {})
            return {
                "protocolVersion": "2025-06-18",
                "capabilities": self.server_capabilities,
                "serverInfo": {"name": "medicore-mock-server", "version": "0.1.0"},
            }

        if method == "tools/list":
            return {"tools": self.visible_tools()}

        if method == "resources/list":
            return {"resources": [{"uri": "policy://icu-admission", "name": "ICU Admission Policy",
                                    "mimeType": "text/plain"}]}

        if method == "resources/read":
            if params.get("uri") == "policy://icu-admission":
                return {"contents": [{"uri": "policy://icu-admission", "mimeType": "text/plain",
                                       "text": ICU_POLICY_DOC}]}
            raise ValueError("unknown resource uri")

        if method == "prompts/list":
            return {"prompts": [{"name": "triage_summary_for_admission",
                                  "description": "Draft a triage summary for an admitting physician",
                                  "arguments": [{"name": "patient_id", "required": True}]}]}

        if method == "prompts/get":
            pid = params.get("arguments", {}).get("patient_id", "{patient_id}")
            return {"messages": [{"role": "user", "content": {"type": "text",
                                   "text": TRIAGE_PROMPT_TEMPLATE.format(patient_id=pid)}}]}

        if method == "tools/call":
            return await self.call_tool(params.get("name"), params.get("arguments", {}))

        raise ValueError(f"unhandled method: {method}")

    async def handle_notification(self, method: str, params: dict):
        if method == "initialized":
            return

    async def call_tool(self, name: str, args: dict):
        read_names = {t["name"] for t in self.read_tools()}
        write_names = {t["name"] for t in self.write_tools()}

        if name in write_names and name != "login_as_doctor" and self.role != "doctor":
            return {"isError": True, "content": [{"type": "text",
                    "text": "authorization denied: write tools require an authenticated doctor session"}]}

        if name == "login_as_doctor":
            if args.get("pin") == "1234":
                self.role = "doctor"
                await self.endpoint.send_notification("notifications/tools/list_changed", {})
                return {"content": [{"type": "text", "text": f"Authenticated as doctor {args['doctor_id']}. "
                                     f"Write tools unlocked."}]}
            return {"isError": True, "content": [{"type": "text", "text": "invalid pin"}]}

        if name == "get_patient":
            p = PATIENTS.get(args["patient_id"])
            if not p:
                return {"isError": True, "content": [{"type": "text", "text": "patient not found"}]}
            return {"content": [{"type": "text", "text": str(p)}]}

        if name == "list_available_icu_beds":
            beds = [b for b in ICU_BEDS.values() if b["available"]]
            return {"content": [{"type": "text", "text": str(beds)}]}

        if name == "list_available_operating_rooms":
            rooms = [r for r in OPERATING_ROOMS.values() if r["available"]]
            return {"content": [{"type": "text", "text": str(rooms)}]}

        if name == "list_hospitals_with_available_icu":
            hospitals = sorted({b["hospital"] for b in ICU_BEDS.values()})
            found = []
            for i, h in enumerate(hospitals, start=1):
                await asyncio.sleep(0.3)
                await self.endpoint.send_notification(
                    "notifications/progress",
                    {"progress": i, "total": len(hospitals), "message": f"checked {h}"},
                )
                if any(b["hospital"] == h and b["available"] for b in ICU_BEDS.values()):
                    found.append(h)
            return {"content": [{"type": "text", "text": str(found)}]}

        if name == "reserve_icu_bed":
            bed = ICU_BEDS.get(args["bed_id"])
            if not bed:
                return {"isError": True, "content": [{"type": "text", "text": "unknown bed_id"}]}
            if not bed["available"]:
                return {"isError": True, "content": [{"type": "text", "text": "bed is not available"}]}
            if args["patient_id"] not in PATIENTS:
                return {"isError": True, "content": [{"type": "text", "text": "unknown patient_id"}]}

            hospital_beds = [b for b in ICU_BEDS.values() if b["hospital"] == bed["hospital"]]
            remaining_available = sum(1 for b in hospital_beds if b["available"])
            if remaining_available <= 1:
                confirmed = await self.endpoint.send_request(
                    "elicitation/create",
                    {"message": f"This is the LAST available ICU bed at {bed['hospital']}. "
                                f"Confirm reserving {args['bed_id']} for {args['patient_id']}?",
                     "requestedSchema": {"type": "object",
                                          "properties": {"confirm": {"type": "boolean"}},
                                          "required": ["confirm"]}},
                )
                if not confirmed.get("content", {}).get("confirm"):
                    return {"isError": True, "content": [{"type": "text",
                            "text": "reservation cancelled: human did not confirm"}]}

            bed["available"] = False
            return {"content": [{"type": "text", "text": f"Reserved {args['bed_id']} for {args['patient_id']}"}]}

        if name == "reserve_operating_room":
            room = OPERATING_ROOMS.get(args["room_id"])
            if not room:
                return {"isError": True, "content": [{"type": "text", "text": "unknown room_id"}]}
            if not room["available"] and room["reserved_for"]:
                confirmed = await self.endpoint.send_request(
                    "elicitation/create",
                    {"message": f"{args['room_id']} is currently reserved for patient "
                                f"{room['reserved_for']}. Confirm the original patient has been "
                                f"rescheduled before reassigning to {args['patient_id']}?",
                     "requestedSchema": {"type": "object",
                                          "properties": {"confirm": {"type": "boolean"}},
                                          "required": ["confirm"]}},
                )
                if not confirmed.get("content", {}).get("confirm"):
                    return {"isError": True, "content": [{"type": "text",
                            "text": "reassignment cancelled: human did not confirm"}]}
            room["available"] = False
            room["reserved_for"] = args["patient_id"]
            return {"content": [{"type": "text", "text": f"Reserved {args['room_id']} for {args['patient_id']}"}]}

        if name == "create_admission":
            if args["patient_id"] not in PATIENTS:
                return {"isError": True, "content": [{"type": "text", "text": "unknown patient_id"}]}

            justification = "(no sampling capability on this client)"
            if "sampling" in self.client_capabilities:
                patient = PATIENTS[args["patient_id"]]
                sample = await self.endpoint.send_request(
                    "sampling/createMessage",
                    {"messages": [{"role": "user", "content": {"type": "text",
                        "text": f"In one sentence, write a clinical admission justification for "
                                f"{patient['name']} ({patient['condition']})."}}],
                     "maxTokens": 100},
                )
                justification = sample.get("content", {}).get("text", justification)

            admission_id = f"A{len(ADMISSIONS) + 1:03d}"
            ADMISSIONS[admission_id] = {"admission_id": admission_id, **args, "justification": justification}
            PATIENTS[args["patient_id"]]["status"] = "admitted"
            return {"content": [{"type": "text",
                    "text": f"Created admission {admission_id}. Justification: {justification}"}]}

        if name == "update_patient_status":
            if args["patient_id"] not in PATIENTS:
                return {"isError": True, "content": [{"type": "text", "text": "unknown patient_id"}]}
            if args["status"] in ("deceased", "discharged_against_medical_advice"):
                confirmed = await self.endpoint.send_request(
                    "elicitation/create",
                    {"message": f"Setting status to '{args['status']}' is irreversible in the record. "
                                f"Confirm for {args['patient_id']}?",
                     "requestedSchema": {"type": "object",
                                          "properties": {"confirm": {"type": "boolean"}},
                                          "required": ["confirm"]}},
                )
                if not confirmed.get("content", {}).get("confirm"):
                    return {"isError": True, "content": [{"type": "text",
                            "text": "status change cancelled: human did not confirm"}]}
            PATIENTS[args["patient_id"]]["status"] = args["status"]
            return {"content": [{"type": "text", "text": f"Updated {args['patient_id']} status "
                                                            f"to {args['status']}"}]}

        return {"isError": True, "content": [{"type": "text", "text": f"unknown tool: {name}"}]}


async def main():
    reader, writer = await stdio_streams_for_this_process()
    server = MediCoreMockServer()
    endpoint = JsonRpcEndpoint(reader, writer, request_handler=server.handle_request,
                                notification_handler=server.handle_notification, name="server")
    server.endpoint = endpoint
    await endpoint.run()


if __name__ == "__main__":
    asyncio.run(main())
