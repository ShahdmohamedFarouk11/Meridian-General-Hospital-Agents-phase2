# Meridian Hospital Network — MCP Server Lab

**Company:** Meridian Hospital Network *(fictional two-hospital regional group: MediCore Downtown, MediCore North)*

## Problem

Front-desk staff currently phone each ICU or Operating Room desk to find available resources, then manually update admissions in a shared spreadsheet. During busy periods, staff have started relying on general-purpose AI assistants to check availability and update records directly.

Allowing an LLM to interact with a hospital database without restrictions creates serious risks. An ICU bed could be double-booked, an operating room reassigned without authorization, or a patient's status accidentally changed through an unsafe model action.

To prevent these failures, we implemented an MCP server between the AI agent and the hospital database. The model can freely retrieve information, but every state-changing operation is performed only through typed MCP tools with server-side validation, authorization, and—when appropriate—human confirmation.

This README documents **Member 3's contribution**, which includes the MCP client (agent), Human-in-the-Loop integration, protocol features, end-to-end testing, and demonstration.

---

# Repository Layout

```text
.
├── .gitignore
├── README.md
├── requirements.txt
│
├── agent/
│   ├── agent.py
│   ├── mcp_protocol.py
│   └── test_e2e.py
│
├── db/
│   ├── drawsql_erd.png
│   ├── erd_dbdiagram.png
│   ├── README.md
│   ├── schema.sql
│   └── seed.sql
│
└── mcp_server/
    ├── db_helpers.py
    ├── MCP.py
    └── mock_server.py
```

---

# Running the Project

```bash
cd agent
pip install -r ../requirements.txt

python test_e2e.py
python agent.py --demo
python agent.py
```

If `ANTHROPIC_API_KEY` is not configured, the client automatically uses an offline deterministic planner together with a sampling stub, allowing all MCP protocol features to run locally.

If the API key is available, Claude is used for tool selection and sampling.

---

# MCP Tools

| Tool | Type | Doctor Authentication | Human Confirmation | Purpose |
|------|------|----------------------|-------------------|---------|
| `get_patient` | Read | No | No | Retrieve patient information |
| `list_available_icu_beds` | Read | No | No | List available ICU beds |
| `list_available_operating_rooms` | Read | No | No | List available operating rooms |
| `list_hospitals_with_available_icu` | Read | No | No | Scan hospitals while reporting progress |
| `login_as_doctor` | Write | No | No | Authenticate doctor and unlock write tools |
| `reserve_icu_bed` | Write | Yes | Last ICU bed only | Prevent unsafe ICU allocation |
| `reserve_operating_room` | Write | Yes | When reassigning a reserved room | Prevent silent operating room reassignment |
| `create_admission` | Write | Yes | Uses Sampling | Creates admission and generates justification |
| `update_patient_status` | Write | Yes | Only for irreversible states | Protect critical patient status updates |

---

# Capability Negotiation

During initialization the client requests the server capabilities:

- Elicitation
- Sampling
- Notifications

The returned capabilities are stored by the agent and checked before using protocol features.

```python
agent.supports("elicitation")
agent.supports("sampling")
```

If a capability is unavailable, the client safely avoids depending on it.

---

# MCP Features Implemented

### Capability Negotiation

The client exchanges capabilities during `initialize` and stores them for later use.

---

### Notifications

After doctor authentication the server sends:

```
notifications/tools/list_changed
```

The client refreshes the tool list automatically instead of polling continuously.

---

### Elicitation (Human-in-the-Loop)

Critical write operations pause execution until the user explicitly confirms.

Examples include:

- Reserving the last ICU bed.
- Reassigning an operating room.
- Setting a patient status to **deceased**.
- Setting a patient status to **discharged_against_medical_advice**.

---

### Sampling

Instead of allowing the server to generate text, the server requests the **client's model** to create a short admission justification.

Without an API key, an offline stub is used.

---

### Resources

Hospital policy documents are exposed as MCP Resources instead of tools.

Example:

```
policy://icu-admission
```

---

### Prompts

Parameterized prompt templates are retrieved through:

```
prompts/get
```

Example:

```
triage_summary_for_admission
```

---

### Progress Notifications

Long-running operations continuously report progress.

Example:

```
Checking MediCore Downtown...
Checking MediCore North...
```

instead of leaving the client waiting silently.

---

### Defensive Tool Design

The server enforces business rules beyond JSON Schema validation.

Examples:

- Write tools require doctor authentication.
- Occupied ICU beds cannot be reserved.
- Invalid patient IDs are rejected.
- Irreversible operations require explicit confirmation.

---

### Transport

The client communicates with the mock server through **stdio**, matching the MCP development workflow.

---

# Demo

```text
Server capabilities:
{
  "tools": {"listChanged": true},
  "elicitation": {},
  "sampling": {}
}

Tools visible before login:

get_patient
list_available_icu_beds
list_available_operating_rooms
list_hospitals_with_available_icu

USER:
Log me in as the doctor on call

Authenticated as doctor D001.
Write tools unlocked.

USER:
Which hospitals currently have available ICU beds?

Checking MediCore Downtown...
Checking MediCore North...

Result:
["MediCore Downtown","MediCore North"]

USER:
Reserve an ICU bed for the patient

Human confirmation requested:
This is the LAST available ICU bed at MediCore North.

Reservation completed.

USER:
Create the admission

Admission A001 created successfully.

Justification generated using the client's model.
```

---

# End-to-End Tests

Running

```bash
python test_e2e.py
```

produces:

```text
PASS: Capability Negotiation

PASS: Notifications

PASS: Human Confirmation

PASS: Resources

PASS: Prompts

PASS: Progress Tracking

PASS: Defensive Tool Design

PASS: Sampling

11/11 tests passed
```

---

# Production Considerations

Although the prototype demonstrates all required MCP protocol concepts, several production improvements would still be necessary:

- Replace the shared doctor session with secure authentication (JWT or similar).
- Support multiple simultaneous confirmation requests.
- Replace the offline sampling stub with a production model.
- Record audit logs for every write operation.
- Integrate with a real hospital database instead of the mock server.
