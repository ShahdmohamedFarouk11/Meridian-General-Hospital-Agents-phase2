# tools.py

def assign_triage_level(triage_level=None, patient_id: str = None, **kwargs):
    """Records the clinical triage severity level dynamically based on input."""
    # استخراج الرقم سواء مرره الـ Agent كـ argument مباشر أو داخل kwargs
    level = triage_level if triage_level is not None else kwargs.get("triage_level", "Unknown")
    patient_info = f" for patient {patient_id}" if patient_id else ""
    
    return f"Patient triage level recorded as: Triage Level {level}{patient_info}"


def check_hospital_resources(
    available_doctors: int = None, 
    available_or_rooms: int = None, 
    available_icu_beds: int = None, 
    available_ventilators: int = None, 
    **kwargs
):
    """Checks hospital resources dynamically using exact parameters provided by the agent/test."""
    # قراءة القيم المستخرجة من الـ Test دون فرض أرقام ثابتة
    resources = {
        "doctors": available_doctors if available_doctors is not None else kwargs.get("doctors", "N/A"),
        "OR_rooms": available_or_rooms if available_or_rooms is not None else kwargs.get("or_rooms", "N/A"),
        "ICU_beds": available_icu_beds if available_icu_beds is not None else kwargs.get("icu_beds", "N/A"),
        "ventilators": available_ventilators if available_ventilators is not None else kwargs.get("ventilators", "N/A"),
    }
    return f"Hospital Resource Status: {resources}"


def get_patient_history(patient_id: str = None, age: int = None, internal_bleeding: bool = None, **kwargs):
    """Retrieves patient medical history using dynamic patient details."""
    p_id = patient_id if patient_id else kwargs.get("id", "Unknown")
    p_age = age if age is not None else kwargs.get("age", "N/A")
    bleeding = internal_bleeding if internal_bleeding is not None else kwargs.get("internal_bleeding", "N/A")
    
    return f"Patient {p_id}: Record retrieved (Age: {p_age}, Internal Bleeding: {bleeding})."


def assess_surgery_risk(needs_surgery: bool = None, internal_bleeding: bool = None, **kwargs):
    """Evaluates surgical intervention risk based on patient-specific flags."""
    surgery = needs_surgery if needs_surgery is not None else kwargs.get("needs_surgery", False)
    bleeding = internal_bleeding if internal_bleeding is not None else kwargs.get("internal_bleeding", False)
    
    risk_level = "CRITICAL" if (surgery and bleeding) else ("HIGH" if surgery or bleeding else "LOW")
    return {"surgery_required": surgery, "risk_level": risk_level}


def check_transfer_options(patient_id: str = None, **kwargs):
    """Checks transfer options dynamically if resources are constrained."""
    p_id = patient_id if patient_id else kwargs.get("patient_id", "Current Patient")
    return f"Transfer Options for {p_id}: Nearby facility City Central Hospital is available (ICU & OR open)."


def allocate_resource(resource_type: str = None, patient_id: str = None, **kwargs):
    """Allocates specified medical resource dynamically."""
    res_type = resource_type if resource_type else kwargs.get("resource", "Required Resource")
    p_id = patient_id if patient_id else kwargs.get("patient_id", "Patient")
    
    return f"Successfully allocated {res_type} for patient {p_id}."