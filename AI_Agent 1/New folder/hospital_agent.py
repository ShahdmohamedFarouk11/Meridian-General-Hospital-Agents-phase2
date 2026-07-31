"""
╔══════════════════════════════════════════════════════════════════╗
║        🏥 Hospital Constrained ReAct AI Agent                    ║
║        Multi-Step Reasoning with Safety Guardrails               ║
║        Powered by Gemini 2.0 Flash + Pydantic Schemas            ║
╚══════════════════════════════════════════════════════════════════╝

Architecture:
  - Constrained ReAct Loop: Thought → Action → Observation → Repeat
  - Structured Outputs enforce strict JSON schema on every LLM call
  - Safety guardrails prevent hallucinated actions or invalid tool use
  - Max 6 reasoning steps before forced escalation to human
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ─── Load Environment ───
load_dotenv()
client = genai.Client()

# ══════════════════════════════════════════════════════════════
# 1. SIMULATED HOSPITAL DATABASE
# ══════════════════════════════════════════════════════════════

PATIENTS_DB = {}
BEDS_DB = {"ICU": {}, "ER": {}, "General": {}}
DOCTORS_DB = {}
MEDICATION_FORMULARY = {}

# ══════════════════════════════════════════════════════════════
# 1.1 HOSPITAL DATA INPUT FUNCTIONS
# ══════════════════════════════════════════════════════════════

def input_patient():
    """Hospital staff registers a new patient into the system."""
    print("\n── Register New Patient ──")
    pid = input("  Patient ID (e.g. P-101): ").strip().upper()
    if not pid:
        print("  Patient ID is required."); return
    if pid in PATIENTS_DB:
        print(f"  Patient {pid} already exists."); return

    name = input("  Full Name: ").strip()
    age = input("  Age: ").strip()
    blood_type = input("  Blood Type (A+, O-, B+, AB+, etc.): ").strip()
    allergies = input("  Allergies (comma-separated, or leave empty): ").strip()
    conditions = input("  Medical Conditions (comma-separated, or leave empty): ").strip()
    medications = input("  Current Medications (comma-separated, or leave empty): ").strip()
    triage_score = input("  Triage Score (1-10): ").strip()
    cardiac_risk = input("  Cardiac Risk (LOW / MEDIUM / HIGH / CRITICAL): ").strip().upper()

    PATIENTS_DB[pid] = {
        "name": name,
        "age": int(age) if age.isdigit() else 0,
        "blood_type": blood_type,
        "allergies": [a.strip() for a in allergies.split(",")] if allergies else [],
        "conditions": [c.strip() for c in conditions.split(",")] if conditions else [],
        "medications": [m.strip() for m in medications.split(",")] if medications else [],
        "triage_score": int(triage_score) if triage_score.isdigit() else 5,
        "cardiac_risk": cardiac_risk if cardiac_risk in ("LOW", "MEDIUM", "HIGH", "CRITICAL") else "LOW",
        "last_visit": datetime.now().strftime("%Y-%m-%d"),
    }
    print(f"  Patient {pid} ({name}) registered successfully.")


def input_bed():
    """Hospital staff adds a new bed to a department."""
    print("\n── Add New Bed ──")
    dept = input("  Department (ICU / ER / General): ").strip().title()
    dept_map = {"Icu": "ICU", "Er": "ER", "General": "General"}
    dept_key = dept_map.get(dept, None)
    if not dept_key:
        print(f"  Invalid department. Choose: ICU, ER, General"); return

    bed_id = input("  Bed ID (e.g. ICU-5, ER-4, GEN-6): ").strip().upper()
    if not bed_id:
        print("  Bed ID is required."); return

    if bed_id in BEDS_DB.get(dept_key, {}):
        print(f"  Bed {bed_id} already exists in {dept_key}."); return

    bed_info = {"status": "AVAILABLE", "patient": None}
    if dept_key == "ICU":
        vent = input("  Has Ventilator? (y/n): ").strip().lower() == "y"
        mon = input("  Has Monitor? (y/n): ").strip().lower() == "y"
        bed_info["ventilator"] = vent
        bed_info["monitor"] = mon

    BEDS_DB[dept_key][bed_id] = bed_info
    print(f"  Bed {bed_id} added to {dept_key} department.")


def input_doctor():
    """Hospital staff registers an on-call doctor."""
    print("\n── Register On-Call Doctor ──")
    dept = input("  Department/Specialty (e.g. Cardiology, Neurology): ").strip().title()
    if not dept:
        print("  Department is required."); return

    name = input("  Doctor Name (e.g. Dr. Nadia Farouk): ").strip()
    ext = input("  Extension Number: ").strip()
    available = input("  Currently Available? (y/n): ").strip().lower() == "y"

    DOCTORS_DB[dept] = {"on_call": name, "available": available, "ext": ext}
    print(f"  {name} registered as on-call for {dept}.")


def input_medication():
    """Hospital staff adds a medication to the formulary."""
    print("\n── Add Medication to Formulary ──")
    name = input("  Medication Name: ").strip().title()
    if not name:
        print("  Medication name is required."); return
    if name in MEDICATION_FORMULARY:
        print(f"  {name} already in formulary."); return

    med_class = input("  Drug Class (e.g. Antibiotic, Opioid Analgesic): ").strip()
    contras = input("  Contraindications (comma-separated): ").strip()
    interactions = input("  Drug Interactions (comma-separated): ").strip()

    MEDICATION_FORMULARY[name] = {
        "class": med_class,
        "contraindications": [c.strip() for c in contras.split(",")] if contras else [],
        "interactions": [i.strip() for i in interactions.split(",")] if interactions else [],
    }
    print(f" {name} added to formulary.")


def view_all_data():
    """Display all currently registered hospital data."""
    print("\n" + "═" * 60)
    print("CURRENT HOSPITAL DATA")
    print("═" * 60)

    print(f"\nPatients ({len(PATIENTS_DB)}):")
    if not PATIENTS_DB:
        print("  (none registered)")
    for pid, p in PATIENTS_DB.items():
        print(f"  {pid}: {p['name']}, Age {p['age']}, Triage {p['triage_score']}/10, Cardiac {p['cardiac_risk']}")

    print(f"\n Beds:")
    for dept, beds in BEDS_DB.items():
        if not beds:
            print(f"  {dept}: (no beds added)")
        else:
            avail = sum(1 for b in beds.values() if b['status'] == 'AVAILABLE')
            print(f"  {dept}: {avail}/{len(beds)} available — {', '.join(beds.keys())}")

    print(f"\nDoctors ({len(DOCTORS_DB)}):")
    if not DOCTORS_DB:
        print("  (none registered)")
    for dept, doc in DOCTORS_DB.items():
        status = "🟢" if doc['available'] else "🔴"
        print(f"  {dept}: {doc['on_call']} {status} (ext {doc['ext']})")

    print(f"\nMedications ({len(MEDICATION_FORMULARY)}):")
    if not MEDICATION_FORMULARY:
        print("  (none added)")
    for med in MEDICATION_FORMULARY:
        print(f"  • {med}")
    print()

# ══════════════════════════════════════════════════════════════
# 2. PYDANTIC SCHEMAS (Constrained Output Structure)
# ══════════════════════════════════════════════════════════════

ALLOWED_ACTIONS = [
    "check_bed_availability",
    "get_patient_history",
    "check_medication_safety",
    "find_specialist",
    "allocate_bed",
    "order_lab_test",
    "escalate_to_human",
    "final_answer",
]

class AgentStep(BaseModel):
    """Strict schema for each ReAct reasoning step."""
    thought: str = Field(
        description="Step-by-step clinical reasoning. Explain WHY you chose this action."
    )
    action: Literal[
        "check_bed_availability",
        "get_patient_history",
        "check_medication_safety",
        "find_specialist",
        "allocate_bed",
        "order_lab_test",
        "escalate_to_human",
        "final_answer",
    ] = Field(
        description="The constrained tool action to execute next."
    )
    action_input: Optional[str] = Field(
        default=None,
        description="Input for the action: patient_id, department, medication name, bed_id, or final summary."
    )
    urgency: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        description="Current assessed urgency level based on available clinical data."
    )

# ══════════════════════════════════════════════════════════════
# 3. TOOL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════

def check_bed_availability(department: str = "ICU") -> str:
    """Check real-time bed availability in a hospital department."""
    dept = department.strip().upper()
    # Normalize department names
    dept_map = {"ICU": "ICU", "ER": "ER", "EMERGENCY": "ER", "GENERAL": "General", "GEN": "General"}
    dept_key = dept_map.get(dept, "ICU")

    beds = BEDS_DB.get(dept_key, {})
    if not beds:
        return f" Department '{department}' not found. Available: ICU, ER, General."

    available = [bid for bid, info in beds.items() if info["status"] == "AVAILABLE"]
    occupied = [bid for bid, info in beds.items() if info["status"] == "OCCUPIED"]

    details = []
    for bid in available:
        info = beds[bid]
        extras = []
        if info.get("ventilator"):
            extras.append("Ventilator ✓")
        if info.get("monitor"):
            extras.append("Monitor ✓")
        detail = f"  • {bid}: AVAILABLE" + (f" ({', '.join(extras)})" if extras else "")
        details.append(detail)

    result = f" {dept_key} Department — {len(available)}/{len(beds)} beds available:\n"
    result += "\n".join(details) if details else "   No beds available!"
    result += f"\n  Occupied: {', '.join(occupied)}"
    return result


def get_patient_history(patient_id: str) -> str:
    """Retrieve patient medical history, allergies, and risk factors."""
    pid = patient_id.strip().upper()
    patient = PATIENTS_DB.get(pid)
    if not patient:
        return f" Patient '{patient_id}' not found in system. Verify ID."

    return (
        f" Patient Record — {pid}:\n"
        f"  Name: {patient['name']} | Age: {patient['age']} | Blood: {patient['blood_type']}\n"
        f"   Allergies: {', '.join(patient['allergies']) if patient['allergies'] else 'None'}\n"
        f"  Conditions: {', '.join(patient['conditions']) if patient['conditions'] else 'None'}\n"
        f"  Medications: {', '.join(patient['medications']) if patient['medications'] else 'None'}\n"
        f"  Triage Score: {patient['triage_score']}/10 | Cardiac Risk: {patient['cardiac_risk']}\n"
        f"  Last Visit: {patient['last_visit']}"
    )


def check_medication_safety(medication: str, patient_id: str = None) -> str:
    """Check medication contraindications and drug interactions."""
    med_name = medication.strip().title()
    med = MEDICATION_FORMULARY.get(med_name)
    if not med:
        return f" Medication '{medication}' not in formulary. Available: {', '.join(MEDICATION_FORMULARY.keys())}"

    result = (
        f"💊 Medication Check — {med_name}:\n"
        f"  Class: {med['class']}\n"
        f"  Contraindications: {', '.join(med['contraindications'])}\n"
        f"  Interactions: {', '.join(med['interactions'])}"
    )

    # Cross-check patient allergies and current medications
    if patient_id:
        patient = PATIENTS_DB.get(patient_id.strip().upper())
        if patient:
            # Allergy check
            for allergy in patient["allergies"]:
                if allergy.lower() in med["class"].lower() or allergy.lower() in med_name.lower():
                    result += f"\n  ALLERGY ALERT: Patient is allergic to {allergy}! DO NOT ADMINISTER."
            # Interaction check
            for current_med in patient["medications"]:
                med_base = current_med.split()[0]
                if med_base in med["interactions"]:
                    result += f"\n  INTERACTION WARNING: {med_name} interacts with patient's {current_med}."

    return result


def find_specialist(department: str) -> str:
    """Find the on-call specialist for a given department."""
    dept = department.strip().title()
    # Try partial matching
    match = None
    for key in DOCTORS_DB:
        if dept.lower() in key.lower():
            match = key
            break

    if not match:
        return f" Department '{department}' not found. Available: {', '.join(DOCTORS_DB.keys())}"

    doc = DOCTORS_DB[match]
    status = "🟢 AVAILABLE" if doc["available"] else "🔴 UNAVAILABLE"
    return (
        f"On-Call Specialist — {match}:\n"
        f"  Doctor: {doc['on_call']}\n"
        f"  Status: {status}\n"
        f"  Extension: {doc['ext']}"
    )


def allocate_bed(patient_id: str, bed_id: str) -> str:
    """Allocate a specific bed to a patient (with safety checks)."""
    pid = patient_id.strip().upper()
    bid = bed_id.strip().upper()

    patient = PATIENTS_DB.get(pid)
    if not patient:
        return f" BLOCKED: Patient '{patient_id}' not found."

    # Find the bed
    for dept, beds in BEDS_DB.items():
        if bid in beds:
            if beds[bid]["status"] == "OCCUPIED":
                return f" BLOCKED: {bid} is already occupied."
            # Allocate
            beds[bid]["status"] = "OCCUPIED"
            beds[bid]["patient"] = pid
            return (
                f" ALLOCATION SUCCESS:\n"
                f"  Patient: {patient['name']} ({pid})\n"
                f"  Assigned to: {bid} ({dept} Department)\n"
                f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

    return f" BLOCKED: Bed '{bed_id}' not found in any department."


def order_lab_test(patient_id: str, test_type: str = "CBC") -> str:
    """Order a laboratory test for a patient."""
    pid = patient_id.strip().upper()
    patient = PATIENTS_DB.get(pid)
    if not patient:
        return f" Patient '{patient_id}' not found."

    test_type = test_type.strip().upper()
    valid_tests = ["CBC", "BMP", "CMP", "TROPONIN", "ABG", "COAG", "LACTATE", "BNP"]
    if test_type not in valid_tests:
        return f" Invalid test. Available: {', '.join(valid_tests)}"

    return (
        f" Lab Order Placed:\n"
        f"  Patient: {patient['name']} ({pid})\n"
        f"  Test: {test_type}\n"
        f"  Priority: STAT\n"
        f"  Estimated Results: 30-45 minutes\n"
        f"  Order Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

# Tool dispatcher
TOOLS = {
    "check_bed_availability": check_bed_availability,
    "get_patient_history": get_patient_history,
    "check_medication_safety": check_medication_safety,
    "find_specialist": find_specialist,
    "allocate_bed": allocate_bed,
    "order_lab_test": order_lab_test,
}

# ══════════════════════════════════════════════════════════════
# 4. CONSTRAINED ReAct AGENT LOOP
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a Constrained Hospital Emergency Triage AI Agent.

## STRICT RULES:
1. You MUST reason step-by-step (Thought) before choosing any Action.
2. You can ONLY use the actions listed in the schema — no others.
3. For CRITICAL/HIGH urgency: You MUST check patient history AND bed availability before allocating.
4. For medication orders: You MUST check medication safety first.
5. NEVER allocate a bed without verifying availability first.
6. If you lack enough information, use tools to gather it — do NOT guess.
7. When you have enough information to give a complete answer, use "final_answer".
8. When the situation exceeds AI capability, use "escalate_to_human".

## AVAILABLE TOOLS:
- check_bed_availability: Input = department name (ICU, ER, General)
- get_patient_history: Input = patient_id (e.g., P-101)
- check_medication_safety: Input = "medication_name|patient_id" (e.g., "Morphine|P-101")
- find_specialist: Input = department name (Cardiology, Pulmonology, etc.)
- allocate_bed: Input = "patient_id|bed_id" (e.g., "P-101|ICU-2")
- order_lab_test: Input = "patient_id|test_type" (e.g., "P-101|TROPONIN")
- escalate_to_human: Input = reason for escalation
- final_answer: Input = complete clinical summary and recommended plan

## CONTEXT SO FAR:
{context}
"""

MAX_STEPS = 6


def execute_tool(action: str, action_input: str) -> str:
    """Route the agent's chosen action to the correct tool function."""
    inp = action_input or ""

    if action == "check_bed_availability":
        return check_bed_availability(inp if inp else "ICU")

    elif action == "get_patient_history":
        return get_patient_history(inp)

    elif action == "check_medication_safety":
        parts = inp.split("|")
        med = parts[0].strip() if parts else ""
        pid = parts[1].strip() if len(parts) > 1 else None
        return check_medication_safety(med, pid)

    elif action == "find_specialist":
        return find_specialist(inp)

    elif action == "allocate_bed":
        parts = inp.split("|")
        pid = parts[0].strip() if parts else ""
        bid = parts[1].strip() if len(parts) > 1 else ""
        return allocate_bed(pid, bid)

    elif action == "order_lab_test":
        parts = inp.split("|")
        pid = parts[0].strip() if parts else ""
        test = parts[1].strip() if len(parts) > 1 else "CBC"
        return order_lab_test(pid, test)

    elif action == "escalate_to_human":
        return f" ESCALATED TO HUMAN SUPERVISOR: {inp}"

    elif action == "final_answer":
        return f" FINAL CLINICAL DECISION:\n{inp}"

    return " Unknown action — blocked by guardrail."


def run_hospital_agent(user_prompt: str):
    """Main Constrained ReAct Agent execution loop."""
    print("=" * 65)
    print("  HOSPITAL CONSTRAINED ReAct AGENT")
    print("=" * 65)
    print(f" Input: {user_prompt}\n")

    context = f"User Request: {user_prompt}\n"
    step_history = []

    for step_num in range(1, MAX_STEPS + 1):
        print(f"{'─' * 60}")
        print(f"  STEP {step_num}/{MAX_STEPS}")
        print(f"{'─' * 60}")

        # Build prompt with accumulated context
        full_prompt = SYSTEM_PROMPT.format(context=context)

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction="Respond ONLY with valid JSON matching the schema.",
                    temperature=0.0,
                    response_mime_type="application/json",
                    response_schema=AgentStep,
                ),
            )

            # Parse and validate structured output
            step = AgentStep.model_validate_json(response.text)

        except Exception as e:
            print(f"  LLM/Parsing Error: {e}")
            print("  Forcing escalation to human supervisor.")
            step = AgentStep(
                thought="Failed to parse LLM output. Escalating for safety.",
                action="escalate_to_human",
                action_input="LLM output parsing failure — manual review required.",
                urgency="CRITICAL",
            )

        # Display the agent's reasoning
        print(f"   Thought:  {step.thought}")
        print(f"   Urgency:  {step.urgency}")
        print(f"    Action:   {step.action}")
        print(f"   Input:    {step.action_input}")

        # Execute the tool
        observation = execute_tool(step.action, step.action_input)
        print(f"  Observation:\n    {observation.replace(chr(10), chr(10) + '    ')}")

        # Record step
        step_record = {
            "step": step_num,
            "thought": step.thought,
            "action": step.action,
            "input": step.action_input,
            "urgency": step.urgency,
            "observation": observation,
        }
        step_history.append(step_record)

        # Update context for next iteration
        context += (
            f"\n--- Step {step_num} ---\n"
            f"Thought: {step.thought}\n"
            f"Action: {step.action}({step.action_input})\n"
            f"Observation: {observation}\n"
        )

        # Terminal conditions
        if step.action in ("final_answer", "escalate_to_human"):
            print(f"\n{'=' * 65}")
            print(f" Agent completed in {step_num} step(s).")
            print(f"{'=' * 65}")
            break
    else:
        # Max steps reached
        print(f"\n{'=' * 65}")
        print(f"  Max steps ({MAX_STEPS}) reached — auto-escalating to human.")
        print(f"{'=' * 65}")

    # Print full trace summary
    print(f"\n{'━' * 65}")
    print(" FULL REASONING TRACE:")
    print(f"{'━' * 65}")
    for s in step_history:
        print(f"  Step {s['step']}: [{s['urgency']}] {s['action']}({s['input']})")
    print(f"{'━' * 65}\n")

    return step_history


# ══════════════════════════════════════════════════════════════
# 5. INTERACTIVE CLI
# ══════════════════════════════════════════════════════════════

def main():
    print("\n" + "╔" + "═" * 63 + "╗")
    print("║  🏥  Hospital Constrained ReAct Agent — Interactive Mode     ║")
    print("╚" + "═" * 63 + "╝\n")

    while True:
        print("┌─────────────────────────────────────────┐")
        print("│          📋 MAIN MENU                   │")
        print("├─────────────────────────────────────────┤")
        print("│  [1] Register a Patient                 │")
        print("│  [2] Add a Bed                          │")
        print("│  [3] Register a Doctor                  │")
        print("│  [4] Add a Medication                   │")
        print("│  [5] View All Hospital Data             │")
        print("│  [6] Run AI Agent (enter scenario)      │")
        print("│  [0] Exit                               │")
        print("└─────────────────────────────────────────┘")

        choice = input("\n  Select option: ").strip()

        if choice == "1":
            input_patient()
        elif choice == "2":
            input_bed()
        elif choice == "3":
            input_doctor()
        elif choice == "4":
            input_medication()
        elif choice == "5":
            view_all_data()
        elif choice == "6":
            if not PATIENTS_DB:
                print("\n  No patients registered yet. Please register at least one patient first.")
                continue
            prompt = input("\n  Enter clinical scenario: ").strip()
            if prompt:
                run_hospital_agent(prompt)
        elif choice == "0" or choice.lower() in ("exit", "quit", "q"):
            print(" Agent shutting down. Stay safe!")
            break
        else:
            print("  Invalid option. Try again.")


if __name__ == "__main__":
    main()
