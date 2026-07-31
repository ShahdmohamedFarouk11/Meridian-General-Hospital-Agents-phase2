# test_agent.py
import sys
import os

# Ensure current directory is in Python module search path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from constrained_agent import run_constrained_agent

def get_example_patients():
    return [
        {
            "id": "P-001",
            "input": {
                "triage_level": 1,
                "age": 45,
                "needs_surgery": True,
                "needs_ventilator": False,
                "internal_bleeding": True,
                "available_doctors": 2,
                "available_or_rooms": 1,
                "available_icu_beds": 0,
                "available_ventilators": 0,
            },
            "expected": "IMMEDIATE_OR",
        },
        {
            "id": "P-002",
            "input": {
                "triage_level": 1,
                "age": 60,
                "needs_surgery": True,
                "needs_ventilator": False,
                "internal_bleeding": True,
                "available_doctors": 1,
                "available_or_rooms": 0,
                "available_icu_beds": 1,
                "available_ventilators": 1,
            },
            "expected": "WAITLIST",
        },
        {
            "id": "P-003",
            "input": {
                "triage_level": 2,
                "age": 70,
                "needs_surgery": False,
                "needs_ventilator": False,
                "internal_bleeding": False,
                "available_doctors": 3,
                "available_or_rooms": 2,
                "available_icu_beds": 2,
                "available_ventilators": 0,
            },
            "expected": "GENERAL_WARD",
        },
        {
            "id": "P-004",
            "input": {
                "triage_level": 2,
                "age": 55,
                "needs_surgery": False,
                "needs_ventilator": False,
                "internal_bleeding": False,
                "available_doctors": 2,
                "available_or_rooms": 1,
                "available_icu_beds": 0,
                "available_ventilators": 2,
            },
            "expected": "GENERAL_WARD",
        },
        {
            "id": "P-005",
            "input": {
                "triage_level": 2,
                "age": 68,
                "needs_surgery": False,
                "needs_ventilator": True,
                "internal_bleeding": False,
                "available_doctors": 2,
                "available_or_rooms": 1,
                "available_icu_beds": 1,
                "available_ventilators": 1,
            },
            "expected": "IMMEDIATE_ICU",
        },
        {
            "id": "P-006",
            "input": {
                "triage_level": 1,
                "age": 60,
                "needs_surgery": True,
                "needs_ventilator": True,
                "internal_bleeding": False,
                "available_doctors": 1,
                "available_or_rooms": 1,
                "available_icu_beds": 1,
                "available_ventilators": 1,
            },
            "expected": "IMMEDIATE_OR",
        },
        {
            "id": "P-007",
            "input": {
                "triage_level": 4,
                "age": 30,
                "needs_surgery": False,
                "needs_ventilator": False,
                "internal_bleeding": False,
                "available_doctors": 0,
                "available_or_rooms": 0,
                "available_icu_beds": 0,
                "available_ventilators": 0,
            },
            "expected": "GENERAL_WARD",
        },
        {
            "id": "P-008",
            "input": {
                "triage_level": 1,
                "age": 3,
                "needs_surgery": True,
                "needs_ventilator": False,
                "internal_bleeding": False,
                "available_doctors": 1,
                "available_or_rooms": 0,
                "available_icu_beds": 1,
                "available_ventilators": 1,
            },
            "expected": "ESCALATE_TRANSFER",
        },
    ]


class TestConstrainedTriageAgentDataset(unittest.TestCase):

    def test_example_patients_dataset(self):
        """
        Iterates over structured patient test cases and verifies agent decision logic.
        """
        patients = get_example_patients()

        for patient in patients:
            patient_id = patient["id"]
            p_input = patient["input"]
            expected_decision = patient["expected"]

            print(f"\n==========================================")
            print(f"RUNNING TEST FOR PATIENT: {patient_id}")
            print(f"Expected Outcome: {expected_decision}")
            print(f"==========================================")

            # Construct clinical prompt from structured inputs
            query = (
                f"Evaluate Patient {patient_id}: Age {p_input['age']}, "
                f"Triage Level {p_input['triage_level']}. "
                f"Needs Surgery: {p_input['needs_surgery']}, "
                f"Needs Ventilator: {p_input['needs_ventilator']}, "
                f"Internal Bleeding: {p_input['internal_bleeding']}. "
                f"Current Hospital Resources -> Doctors: {p_input['available_doctors']}, "
                f"OR Rooms: {p_input['available_or_rooms']}, "
                f"ICU Beds: {p_input['available_icu_beds']}, "
                f"Ventilators: {p_input['available_ventilators']}. "
                f"Assign triage level, evaluate resources, and determine if target outcome is '{expected_decision}'."
            )

            result = run_constrained_agent(query)

            self.assertIsNotNone(result)
            self.assertNotIn("API Error", str(result))


if __name__ == "__main__":
    unittest.main()