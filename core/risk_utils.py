from decimal import Decimal
from .models import RiskPrediction

from .models import (
    Student,
    Attendance,
    AcademicPerformance,
    Assignment,
    ExamResult,
)


# ============================================================
# RISK WEIGHTS
# ============================================================

ATTENDANCE_WEIGHT = Decimal("0.30")
ACADEMIC_WEIGHT = Decimal("0.25")
ASSIGNMENT_WEIGHT = Decimal("0.20")
EXAM_WEIGHT = Decimal("0.25")


# ============================================================
# RISK LEVEL
# ============================================================



def percentage_to_risk(percentage):
    """
    Convert a performance percentage into a gradual risk score.
    Higher performance means lower risk.
    """

    percentage = Decimal(str(percentage))
    percentage = max(Decimal("0"), min(Decimal("100"), percentage))

    return Decimal("100") - percentage



def get_risk_level(risk_score):
    """
    Convert the overall risk score into a risk level.
    """

    risk_score = Decimal(str(risk_score))

    if risk_score <= Decimal("20"):
        return "Very Low"

    if risk_score <= Decimal("40"):
        return "Low"

    if risk_score <= Decimal("60"):
        return "Medium"

    if risk_score <= Decimal("80"):
        return "High"

    return "Very High"



def calculate_assignment_risk(student):
    records = Assignment.objects.filter(student=student)

    if not records.exists():
        return Decimal("100")

    graded_records = records.filter(marks__isnull=False)

    if not graded_records.exists():
        return Decimal("100")

    total_marks = sum(
        (record.marks for record in graded_records),
        Decimal("0")
    )

    maximum_marks = Decimal("20") * graded_records.count()

    percentage = (
        total_marks / maximum_marks
    ) * Decimal("100")

    return percentage_to_risk(percentage)



# ============================================================
# ATTENDANCE RISK
# ============================================================


def calculate_attendance_risk(student):
    records = Attendance.objects.filter(student=student)

    if not records.exists():
        return Decimal("100")

    total_conducted = sum(
        record.classes_conducted for record in records
    )
    total_attended = sum(
        record.classes_attended for record in records
    )

    if total_conducted <= 0:
        return Decimal("100")

    attendance_percentage = (
        Decimal(total_attended) / Decimal(total_conducted)
    ) * Decimal("100")

    return percentage_to_risk(attendance_percentage)



# ============================================================
# ACADEMIC PERFORMANCE RISK
# ============================================================


def calculate_academic_risk(student):
    records = AcademicPerformance.objects.filter(student=student)

    valid_records = [
        record for record in records
        if record.total_internal_marks > 0
    ]

    if not valid_records:
        return Decimal("100")

    total_marks = sum(
        (record.internal_marks for record in valid_records),
        Decimal("0")
    )
    maximum_marks = sum(
        (record.total_internal_marks for record in valid_records),
        Decimal("0")
    )

    if maximum_marks <= 0:
        return Decimal("100")

    percentage = (total_marks / maximum_marks) * Decimal("100")

    return percentage_to_risk(percentage)



# ============================================================
# ASSIGNMENT RISK
# ============================================================




def calculate_exam_risk(student):
    """
    Calculate examination risk using actual maximum marks.
    """

    records = ExamResult.objects.filter(student=student)

    valid_records = [
        record for record in records
        if record.total_marks > 0
    ]

    if not valid_records:
        return Decimal("100")

    total_marks = sum(
        (record.marks_obtained for record in valid_records),
        Decimal("0")
    )

    maximum_marks = sum(
        (record.total_marks for record in valid_records),
        Decimal("0")
    )

    if maximum_marks <= 0:
        return Decimal("100")

    percentage = (
        total_marks / maximum_marks
    ) * Decimal("100")

    return percentage_to_risk(percentage)



# ============================================================
# OVERALL RISK SCORE
# ============================================================

def calculate_risk_score(student):
    """
    Calculate the overall rule-based dropout risk score.
    """

    attendance_risk = calculate_attendance_risk(student)
    academic_risk = calculate_academic_risk(student)
    assignment_risk = calculate_assignment_risk(student)
    exam_risk = calculate_exam_risk(student)

    risk_score = (
        (attendance_risk * ATTENDANCE_WEIGHT)
        + (academic_risk * ACADEMIC_WEIGHT)
        + (assignment_risk * ASSIGNMENT_WEIGHT)
        + (exam_risk * EXAM_WEIGHT)
    )

    risk_score = max(
        Decimal("0"),
        min(Decimal("100"), risk_score)
    )

    return risk_score.quantize(Decimal("0.01"))


# ============================================================
# COMPLETE RISK RESULT
# ============================================================

def calculate_student_risk(student):
    """
    Return the complete rule-based risk result.
    """

    risk_score = calculate_risk_score(student)

    return {
        "risk_score": risk_score,
        "risk_level": get_risk_level(risk_score),
    }


def generate_risk_prediction(student):
    """
    Calculate and save a student's rule-based risk prediction.
    Update the existing prediction if one is available.
    """

    risk_result = calculate_student_risk(student)

    prediction, created = RiskPrediction.objects.update_or_create(
        student=student,
        defaults={
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
            "model_version": "Rule-Based-v1",
            "is_alert_generated": False,
        },
    )

    return prediction

