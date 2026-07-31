# MediCore Hospital Network — MCP Server Lab

**Company:** MediCore Hospital Network (fictional 2-hospital regional group: MediCore Downtown, MediCore North)

**Problem:** Front-desk staff currently phone each ICU/OR desk by hand to find an open bed or room, and write admissions into a shared spreadsheet. During surges, staff have started asking a general chatbot to "just check the spreadsheet and update it," which is exactly the failure mode this lab is about — an LLM with raw, unscoped access to a hospital resource-allocation system. A bed could be double-booked, a room reassigned out from under a patient already in it, or a patient marked "deceased" by an unconfirmed model action. We built an MCP server that sits between the agent and the hospital database so the model can look things up freely, but every state-changing action goes through typed tools with server-side validation, authorization, and — where the stakes are real — a human sign-off.

This README documents **Member 3's** piece: the agent/client, the human-in-the-loop (elicitation) wiring, the end-to-end tests, and the demo transcript. (Database/ERD is Member 1's `db/`; server protocol internals are Member 2's `mcp_server/`.)

## Repository layout (this submission)

```
agent/
  agent.py            <- MCP client + agent loop (Member 3's core deliverable)
  mcp_protocol.py      <- minimal JSON-RPC/MCP transport shared by client + test stub
  test_e2e.py           <- fixed end-to-end tests, one per protocol concern
  requirements.txt
  .env.example
testing_stub/
  mock_server.py        <- NOT the real server. A stand-in fixture for mcp_server/
                            so agent.py and test_e2e.py can run independently of
                            Members 1 & 2's code landing. Swap MCP_SERVER_CMD to
                            point at the real server once merged.
README.md               <- this file
```

## Running it

```bash
cd agent
pip install -r requirements.txt          # optional, only needed for live Claude calls
cp .env.example .env                     # optional: add ANTHROPIC_API_KEY for live tool-use/sampling
python3 test_e2e.py                      # run the fixed test suite
python3 agent.py --demo                  # run the scripted demo transcript below
python3 agent.py                         # interactive mode, real human confirmations
```

Without `ANTHROPIC_API_KEY` set, the agent still runs end-to-end: tool selection falls back to a small deterministic planner and `sampling/createMessage` returns an offline stub, so the *protocol mechanics* (handshake, notifications, elicitation, progress, resources, prompts) are fully exercised without needing network access. Set the key to see Claude actually choosing tools and drafting the sampled justification text.

## Tools (read vs. write) and why each write tool needs what it needs

| Tool | Read/Write | Requires doctor auth? | Elicitation? | Why |
|---|---|---|---|---|
| `get_patient` | read | no | no | no state change |
| `list_available_icu_beds` | read | no | no | no state change |
| `list_available_operating_rooms` | read | no | no | no state change |
| `list_hospitals_with_available_icu` | read | no | no | long-running, multi-hospital — reports progress instead of blocking |
| `login_as_doctor` | write (auth) | no | no | this *is* the role-change trigger for `tools/list_changed` |
| `reserve_icu_bed` | write | **yes** | **yes, if last bed at that hospital** | reserving the last ICU bed is a scarcity decision with real clinical consequence — schema/type-checking alone can't express "is this wise," so a human confirms |
| `reserve_operating_room` | write | **yes** | **yes, if reassigning a room held by another patient** | prevents silently bumping a patient already scheduled for surgery |
| `create_admission` | write | **yes** | no (uses **sampling** instead) | not a confirm/deny decision — the useful step here is asking the *client's* model to draft a clinical justification note, which a human physician still reviews on the record afterward |
| `update_patient_status` | write | **yes** | **yes, if status is `deceased` or `discharged_against_medical_advice`** | irreversible record changes get a confirmation; routine status moves (e.g. `admitted` → `in_surgery`) do not, so elicitation isn't a blanket tax on every write |

**If a client connects without elicitation/sampling capability:** the agent checks `server_capabilities` from `initialize` before assuming either exists (`agent.supports("elicitation")` / `agent.supports("sampling")`). In our mock server, elicitation-gated tools are only reachable by a client that declared elicitation support in the first place; a client without it would need to fail closed on those tools rather than silently skip the confirmation — that's the failure mode this table is designed to prevent, and is exactly why capability negotiation happens before any tool is trusted.

## Where each protocol concern is implemented (client side)

- **Capability negotiation** — `MediCoreAgent.start()` sends `initialize`, stores `server_capabilities`, and `supports()` gates any elicitation/sampling-dependent behavior. See `agent.py`.
- **Notifications** — `_handle_server_notification()` reacts to `notifications/tools/list_changed` by re-running `tools/list` and diffing, rather than polling or assuming a static tool set.
- **Elicitation** — `_handle_elicitation()` is registered as the handler for server → client `elicitation/create` requests; it pauses (real `input()` in interactive mode) and returns `{"action": "accept"/"decline"}`.
- **Sampling** — `_handle_sampling()` handles server → client `sampling/createMessage` by calling *this client's* model (`call_llm_for_sampling`), not the server's own model, and returns the drafted text.
- **Resources** — `read_resource()` fetches the ICU admission policy document via `resources/read` rather than wrapping it in a tool.
- **Prompts** — `get_prompt()` fetches the parameterized `triage_summary_for_admission` template via `prompts/get`.
- **Progress tracking** — `_handle_server_notification()` renders `notifications/progress` events as a live bar instead of blocking silently during `list_hospitals_with_available_icu`.
- **Defensive tool design** — exercised from the client in `test_defensive_tool_design()`: unauthenticated write calls are rejected (handler-level authz), and reserving an already-taken bed is rejected by server-side validation independent of the JSON Schema.
- **Transport** — the agent spawns the server over **stdio** for local development (`asyncio.create_subprocess_exec`), matching the project's dev-phase transport; `MCP_SERVER_CMD` in `.env` is the swap point for Streamable HTTP once the team moves the real server there.

## Demo transcript (`python3 agent.py --demo`)

```
Server capabilities: {"tools": {"listChanged": true}, "elicitation": {}, "sampling": {}, ...}
Tools visible before login: ['get_patient', 'list_available_icu_beds',
                              'list_available_operating_rooms', 'list_hospitals_with_available_icu']

>>> USER: Log me in as the doctor on call
[AGENT] calling tool: login_as_doctor({'doctor_id': 'D001', 'pin': '1234'})
[RESULT] Authenticated as doctor D001. Write tools unlocked.

>>> USER: Which hospitals currently have available ICU beds?
[AGENT] calling tool: list_hospitals_with_available_icu({})
[NOTIFICATION] tools/list_changed -> newly available:
    ['create_admission', 'login_as_doctor', 'reserve_icu_bed',
     'reserve_operating_room', 'update_patient_status']
[PROGRESS] [#-] 1/2 checked MediCore Downtown
[PROGRESS] [##] 2/2 checked MediCore North
[RESULT] ['MediCore Downtown', 'MediCore North']

>>> USER: Reserve an ICU bed for the patient
[AGENT] calling tool: reserve_icu_bed({'patient_id': 'P001', 'bed_id': 'ICU-B1'})
[ELICITATION] Server is pausing for human confirmation:
  This is the LAST available ICU bed at MediCore North. Confirm reserving ICU-B1 for P001?
[RESULT] Reserved ICU-B1 for P001

>>> USER: Create the admission
[AGENT] calling tool: create_admission({'patient_id': 'P001', 'doctor_id': 'D001', 'room_id': 'OR-1'})
[RESULT] Created admission A001. Justification: [drafted by client's model from patient condition on file]
```

*(A recorded walkthrough of the interactive mode — with a real human typing `y`/`N` at the elicitation prompt — should be attached alongside this README as the actual submission recording.)*

## End-to-end test results (`python3 test_e2e.py`)

All 11 fixed checks pass, one or more per protocol concern:

```
PASS: 1. capability_negotiation: server declares elicitation+sampling+notifications
PASS: 2. notifications: write tools hidden before doctor login
PASS: 2. notifications: tools/list_changed unlocked write tools after login
PASS: 3. elicitation: last-bed reservation paused for human, then approved
PASS: 3b. elicitation: irreversible status change is BLOCKED when human declines
PASS: 4. resources: ICU policy document readable via resources/read (not a tool)
PASS: 5. prompts: parameterized triage_summary_for_admission template resolves patient_id
PASS: 6. progress_tracking: long-running scan reported >1 progress notification
PASS: 7a. defensive_design: write tool rejected without doctor authentication
PASS: 7b. defensive_design: server rejects reserving an already-unavailable bed
PASS: 8. sampling: create_admission used the CLIENT's model to draft a justification
11/11 passed
```

## What we'd still worry about in production

- The mock server's "doctor" role is a single boolean flip on a shared session; a real deployment needs per-request identity (JWT/session token) rather than session-global role state.
- Elicitation currently blocks the single in-flight tool call; a real UI would need a way to show *which* pending confirmation belongs to *which* in-flight agent action if multiple are queued.
- The offline sampling stub is fine for CI, but the clinical-justification text it produces when a real key **is** set still needs a human physician's sign-off before it's treated as part of the medical record — the tool result says "drafted," not "approved."
