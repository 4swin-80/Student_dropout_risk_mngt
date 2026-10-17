"""
Shared reporting and analytics logic for Administrator Dashboard.
Provides metric calculation, filter validation, aggregation,
JSON serialization, CSV formatting, and Excel generation.
"""

from decimal import Decimal
import io
import csv
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    openpyxl = None
    HAS_OPENPYXL = False

from .models import (
    Department,
    Student,
    Attendance,
    AcademicPerformance,
    Assignment,
    ExamResult,
    RiskPrediction,
    Intervention,
    StudentSupport,
    StudentSupportFollowUp,
)


def sanitize_csv_cell(value):
    """
    Prevent formula injection in CSV cells.
    If a string starts with =, +, -, or @, prefix with a single quote.
    """
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{val_str}"
    return val_str


def get_filter_options(department_id=None, course=None):
    """
    Retrieve valid options for Department, Course, and Semester dropdowns.
    Restricts course and semester options based on higher-level filter selections.
    """
    departments = list(
        Department.objects.all().order_by("name").values("id", "name")
    )

    course_qs = Student.objects.exclude(course="").exclude(course__isnull=True)
    if department_id:
        course_qs = course_qs.filter(department_id=department_id)
    courses = list(
        course_qs.values_list("course", flat=True).distinct().order_by("course")
    )

    sem_qs = Student.objects.exclude(semester__isnull=True)
    if department_id:
        sem_qs = sem_qs.filter(department_id=department_id)
    if course:
        sem_qs = sem_qs.filter(course=course)
    semesters = list(
        sem_qs.values_list("semester", flat=True).distinct().order_by("semester")
    )

    return {
        "departments": departments,
        "courses": courses,
        "semesters": semesters,
    }


def validate_and_filter_students(department_id=None, course=None, semester=None):
    """
    Validate filter parameters and return:
      - filtered student queryset
      - normalized filter dictionary with display names
    """
    students = Student.objects.all()
    active_filters = {
        "department_id": None,
        "department_name": "All Departments",
        "course": None,
        "semester": None,
    }

    # Department filter validation
    if department_id:
        try:
            dep_id_int = int(department_id)
            department = Department.objects.filter(id=dep_id_int).first()
            if department:
                students = students.filter(department=department)
                active_filters["department_id"] = department.id
                active_filters["department_name"] = department.name
        except (ValueError, TypeError):
            pass

    # Course filter validation
    if course and isinstance(course, str) and course.strip():
        valid_courses = Student.objects.exclude(course="").exclude(course__isnull=True)
        if active_filters["department_id"]:
            valid_courses = valid_courses.filter(department_id=active_filters["department_id"])
        course_clean = course.strip()
        if valid_courses.filter(course=course_clean).exists():
            students = students.filter(course=course_clean)
            active_filters["course"] = course_clean

    # Semester filter validation
    if semester is not None and str(semester).strip():
        try:
            sem_int = int(str(semester).strip())
            valid_semesters = Student.objects.exclude(semester__isnull=True)
            if active_filters["department_id"]:
                valid_semesters = valid_semesters.filter(department_id=active_filters["department_id"])
            if active_filters["course"]:
                valid_semesters = valid_semesters.filter(course=active_filters["course"])
            if valid_semesters.filter(semester=sem_int).exists():
                students = students.filter(semester=sem_int)
                active_filters["semester"] = sem_int
        except (ValueError, TypeError):
            pass

    return students, active_filters


def get_latest_risk_predictions(student_queryset):
    """
    Get the single latest saved RiskPrediction per student in the queryset.
    Returns a dict: {student_id: {'risk_score': Decimal, 'risk_level': str, 'prediction_date': datetime}}
    """
    predictions = (
        RiskPrediction.objects.filter(student__in=student_queryset)
        .order_by("-prediction_date", "-id")
        .values("student_id", "risk_score", "risk_level", "prediction_date")
    )
    latest_by_student = {}
    for p in predictions:
        sid = p["student_id"]
        if sid not in latest_by_student:
            latest_by_student[sid] = p
    return latest_by_student


def calculate_summary_metrics(students, latest_predictions):
    """
    Compute Section C summary cards data.
    Distinguishes unavailable/missing data (None) from zero.
    """
    total_students = students.count()

    high_risk_count = sum(
        1 for p in latest_predictions.values() if p["risk_level"] == "High"
    )
    very_high_risk_count = sum(
        1 for p in latest_predictions.values() if p["risk_level"] == "Very High"
    )

    if latest_predictions:
        total_score = sum(
            (Decimal(str(p["risk_score"])) for p in latest_predictions.values()),
            Decimal("0"),
        )
        avg_risk_score = round(float(total_score / Decimal(len(latest_predictions))), 2)
    else:
        avg_risk_score = None

    # Attendance overall
    att_agg = Attendance.objects.filter(student__in=students).aggregate(
        conducted=Sum("classes_conducted"),
        attended=Sum("classes_attended"),
    )
    cond = att_agg["conducted"] or 0
    attd = att_agg["attended"] or 0
    if cond > 0:
        avg_attendance_pct = round((float(attd) / float(cond)) * 100.0, 2)
    else:
        avg_attendance_pct = None

    # Academic overall (combining internal assessment and exams)
    acad_agg = AcademicPerformance.objects.filter(student__in=students).aggregate(
        internal_obtained=Sum("internal_marks"),
        internal_total=Sum("total_internal_marks"),
    )
    exam_agg = ExamResult.objects.filter(student__in=students).aggregate(
        exam_obtained=Sum("marks_obtained"),
        exam_total=Sum("total_marks"),
    )

    comb_obtained = Decimal("0")
    comb_total = Decimal("0")
    has_academic = False

    if acad_agg["internal_total"] and acad_agg["internal_total"] > Decimal("0"):
        comb_obtained += Decimal(str(acad_agg["internal_obtained"] or 0))
        comb_total += Decimal(str(acad_agg["internal_total"]))
        has_academic = True

    if exam_agg["exam_total"] and exam_agg["exam_total"] > Decimal("0"):
        comb_obtained += Decimal(str(exam_agg["exam_obtained"] or 0))
        comb_total += Decimal(str(exam_agg["exam_total"]))
        has_academic = True

    if has_academic and comb_total > Decimal("0"):
        avg_academic_pct = round(float((comb_obtained / comb_total) * Decimal("100")), 2)
    else:
        avg_academic_pct = None

    return {
        "total_students": total_students,
        "high_risk_count": high_risk_count,
        "very_high_risk_count": very_high_risk_count,
        "high_or_very_high_count": high_risk_count + very_high_risk_count,
        "average_risk_score": avg_risk_score,
        "average_attendance_percentage": avg_attendance_pct,
        "average_academic_performance": avg_academic_pct,
    }


def calculate_risk_distribution(students, latest_predictions):
    """
    Calculate counts for distinct students in each risk tier.
    Students without a saved prediction are counted as 'No Prediction'.
    """
    total_students = students.count()
    distribution = {
        "Very Low": 0,
        "Low": 0,
        "Medium": 0,
        "High": 0,
        "Very High": 0,
        "No Prediction": 0,
    }

    predicted_student_count = len(latest_predictions)
    for p in latest_predictions.values():
        lvl = p.get("risk_level")
        if lvl in distribution:
            distribution[lvl] += 1

    distribution["No Prediction"] = max(0, total_students - predicted_student_count)
    return distribution


def calculate_risk_trends(students):
    """
    Group historical RiskPrediction records by month of prediction_date.
    Returns chronological timeline data.
    """
    records = (
        RiskPrediction.objects.filter(student__in=students)
        .annotate(month=TruncMonth("prediction_date"))
        .values("month", "risk_level")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    monthly_map = {}
    for r in records:
        if not r["month"]:
            continue
        m_str = r["month"].strftime("%Y-%m")
        if m_str not in monthly_map:
            monthly_map[m_str] = {
                "period": m_str,
                "Very Low": 0,
                "Low": 0,
                "Medium": 0,
                "High": 0,
                "Very High": 0,
                "total": 0,
            }
        lvl = r["risk_level"]
        cnt = r["count"]
        if lvl in monthly_map[m_str]:
            monthly_map[m_str][lvl] += cnt
        monthly_map[m_str]["total"] += cnt

    timeline = [monthly_map[k] for k in sorted(monthly_map.keys())]
    return timeline


def calculate_attendance_analytics(students):
    """
    Calculate attendance overview metrics and monthly attendance trend.
    """
    att_qs = Attendance.objects.filter(student__in=students)
    agg = att_qs.aggregate(
        total_conducted=Sum("classes_conducted"),
        total_attended=Sum("classes_attended"),
        records_count=Count("id"),
    )
    conducted = agg["total_conducted"] or 0
    attended = agg["total_attended"] or 0
    overall_pct = (
        round((float(attended) / float(conducted)) * 100.0, 2)
        if conducted > 0
        else None
    )

    # Monthly attendance trends
    monthly_trends = (
        att_qs.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(
            conducted=Sum("classes_conducted"),
            attended=Sum("classes_attended"),
        )
        .order_by("month")
    )

    trend_list = []
    for m in monthly_trends:
        if not m["month"]:
            continue
        m_cond = m["conducted"] or 0
        m_attd = m["attended"] or 0
        pct = round((float(m_attd) / float(m_cond)) * 100.0, 2) if m_cond > 0 else 0.0
        trend_list.append({
            "period": m["month"].strftime("%Y-%m"),
            "conducted": m_cond,
            "attended": m_attd,
            "percentage": pct,
        })

    return {
        "overall_percentage": overall_pct,
        "total_conducted": conducted,
        "total_attended": attended,
        "records_count": agg["records_count"] or 0,
        "trends": trend_list,
    }


def calculate_academic_analytics(students):
    """
    Calculate internal marks, exam marks, and assignment statistics.
    Assignments are evaluated strictly on the 0-20 scale.
    """
    # Internal assessments
    acad_agg = AcademicPerformance.objects.filter(student__in=students).aggregate(
        total_obtained=Sum("internal_marks"),
        total_possible=Sum("total_internal_marks"),
        records_count=Count("id"),
    )
    int_marks = acad_agg["total_obtained"] or Decimal("0")
    int_max = acad_agg["total_possible"] or Decimal("0")
    internal_pct = (
        round(float((int_marks / int_max) * Decimal("100")), 2)
        if int_max > Decimal("0")
        else None
    )

    # Exam results
    exam_agg = ExamResult.objects.filter(student__in=students).aggregate(
        total_obtained=Sum("marks_obtained"),
        total_possible=Sum("total_marks"),
        records_count=Count("id"),
    )
    ex_marks = exam_agg["total_obtained"] or Decimal("0")
    ex_max = exam_agg["total_possible"] or Decimal("0")
    exam_pct = (
        round(float((ex_marks / ex_max) * Decimal("100")), 2)
        if ex_max > Decimal("0")
        else None
    )

    # Assignments
    assign_qs = Assignment.objects.filter(student__in=students)
    status_counts = {"Submitted": 0, "Pending": 0, "Late": 0}
    for item in assign_qs.values("status").annotate(count=Count("id")):
        st = item["status"]
        if st in status_counts:
            status_counts[st] = item["count"]

    graded_qs = assign_qs.filter(marks__isnull=False)
    graded_agg = graded_qs.aggregate(
        total_marks=Sum("marks"),
        graded_count=Count("id"),
    )
    graded_count = graded_agg["graded_count"] or 0
    total_assign_marks = graded_agg["total_marks"] or Decimal("0")
    avg_assignment_marks = (
        round(float(total_assign_marks / Decimal(graded_count)), 2)
        if graded_count > 0
        else None
    )

    return {
        "internal_percentage": internal_pct,
        "internal_records_count": acad_agg["records_count"] or 0,
        "exam_percentage": exam_pct,
        "exam_records_count": exam_agg["records_count"] or 0,
        "assignment_status": status_counts,
        "assignment_total_count": assign_qs.count(),
        "assignment_graded_count": graded_count,
        "assignment_average_marks_20": avg_assignment_marks,
    }


def calculate_intervention_analytics(students):
    """
    Aggregate formal interventions, teacher support referrals, and mentor follow-ups
    by status for the administrator's intervention and support activity chart.
    """
    interv_qs = Intervention.objects.filter(student__in=students)
    referral_qs = StudentSupport.objects.filter(student__in=students)
    followup_qs = StudentSupportFollowUp.objects.filter(
        referral__student__in=students
    )
    status_counts = {
        "Planned": 0,
        "Pending": 0,
        "Accepted": 0,
        "In Progress": 0,
        "Completed": 0,
        "Follow-up Required": 0,
    }
    for queryset in (interv_qs, referral_qs, followup_qs):
        for item in queryset.values("status").annotate(count=Count("id")):
            st = item["status"]
            if st in status_counts:
                status_counts[st] += item["count"]

    # Intervention type distribution
    type_counts = {
        "Counseling": 0,
        "Mentoring": 0,
        "Financial Assistance": 0,
        "Psychological Guidance": 0,
    }
    for item in interv_qs.values("intervention_type").annotate(count=Count("id")):
        t = item["intervention_type"]
        if t in type_counts:
            type_counts[t] = item["count"]

    return {
        "total_interventions": interv_qs.count(),
        "total_tracked_activities": (
            interv_qs.count() + referral_qs.count() + followup_qs.count()
        ),
        "status_distribution": status_counts,
        "type_distribution": type_counts,
    }


def calculate_support_and_follow_up_analytics(students):
    """
    Calculate referral and follow-up metrics.
    Overdue follow-up is a pending follow-up scheduled before today's local date.
    """
    ref_qs = StudentSupport.objects.filter(student__in=students)
    ref_status_counts = {
        "Pending": 0,
        "Accepted": 0,
        "In Progress": 0,
        "Completed": 0,
        "Follow-up Required": 0,
    }
    for item in ref_qs.values("status").annotate(count=Count("id")):
        st = item["status"]
        if st in ref_status_counts:
            ref_status_counts[st] = item["count"]

    # Follow-ups linked to the filtered student referrals
    followup_qs = StudentSupportFollowUp.objects.filter(referral__student__in=students)
    pending_followups = followup_qs.filter(status="Pending").count()
    completed_followups = followup_qs.filter(status="Completed").count()

    today = timezone.localdate()
    overdue_followups = followup_qs.filter(
        status="Pending",
        scheduled_date__lt=today,
    ).count()

    return {
        "total_referrals": ref_qs.count(),
        "referral_status_distribution": ref_status_counts,
        "total_follow_ups": followup_qs.count(),
        "pending_follow_ups": pending_followups,
        "completed_follow_ups": completed_followups,
        "overdue_follow_ups": overdue_followups,
    }


def calculate_department_comparisons(active_filters):
    """
    Compute aggregate metrics for all departments to allow cross-department comparisons.
    If a department filter is active, that department is marked with is_active=True.
    """
    departments = Department.objects.all().order_by("name")
    comparisons = []

    for dep in departments:
        dep_students = Student.objects.filter(department=dep)
        total_dep_students = dep_students.count()

        # Risk metrics
        dep_predictions = get_latest_risk_predictions(dep_students)
        high_risk = sum(1 for p in dep_predictions.values() if p["risk_level"] == "High")
        very_high_risk = sum(1 for p in dep_predictions.values() if p["risk_level"] == "Very High")

        if dep_predictions:
            total_score = sum(
                (Decimal(str(p["risk_score"])) for p in dep_predictions.values()),
                Decimal("0"),
            )
            avg_risk = round(float(total_score / Decimal(len(dep_predictions))), 2)
        else:
            avg_risk = None

        # Attendance metrics
        att_agg = Attendance.objects.filter(student__in=dep_students).aggregate(
            conducted=Sum("classes_conducted"),
            attended=Sum("classes_attended"),
        )
        cond = att_agg["conducted"] or 0
        attd = att_agg["attended"] or 0
        avg_att = round((float(attd) / float(cond)) * 100.0, 2) if cond > 0 else None

        # Academic performance
        acad_agg = AcademicPerformance.objects.filter(student__in=dep_students).aggregate(
            obtained=Sum("internal_marks"),
            total=Sum("total_internal_marks"),
        )
        exam_agg = ExamResult.objects.filter(student__in=dep_students).aggregate(
            obtained=Sum("marks_obtained"),
            total=Sum("total_marks"),
        )
        c_obt = Decimal("0")
        c_tot = Decimal("0")
        has_acad = False
        if acad_agg["total"] and acad_agg["total"] > Decimal("0"):
            c_obt += Decimal(str(acad_agg["obtained"] or 0))
            c_tot += Decimal(str(acad_agg["total"]))
            has_acad = True
        if exam_agg["total"] and exam_agg["total"] > Decimal("0"):
            c_obt += Decimal(str(exam_agg["obtained"] or 0))
            c_tot += Decimal(str(exam_agg["total"]))
            has_acad = True
        avg_acad = (
            round(float((c_obt / c_tot) * Decimal("100")), 2)
            if has_acad and c_tot > Decimal("0")
            else None
        )

        referrals_count = StudentSupport.objects.filter(student__in=dep_students).count()
        interventions_count = Intervention.objects.filter(student__in=dep_students).count()
        completed_follow_ups = StudentSupportFollowUp.objects.filter(
            referral__student__in=dep_students,
            status="Completed",
        ).count()

        is_active = (active_filters.get("department_id") == dep.id)

        comparisons.append({
            "department_id": dep.id,
            "department_name": dep.name,
            "is_selected": is_active,
            "total_students": total_dep_students,
            "high_risk_count": high_risk,
            "very_high_risk_count": very_high_risk,
            "high_or_very_high_count": high_risk + very_high_risk,
            "average_risk_score": avg_risk,
            "average_attendance_percentage": avg_att,
            "average_academic_percentage": avg_acad,
            "total_referrals": referrals_count,
            "total_interventions": interventions_count,
            "completed_follow_ups": completed_follow_ups,
        })

    return comparisons


def build_full_report_data(department_id=None, course=None, semester=None):
    """
    Main aggregator function.
    Validates filters, builds querysets, executes shared reporting logic,
    and returns a structured Python dictionary suitable for JSON serialization,
    CSV generation, and Excel creation.
    """
    students, active_filters = validate_and_filter_students(
        department_id=department_id,
        course=course,
        semester=semester,
    )
    latest_predictions = get_latest_risk_predictions(students)

    summary = calculate_summary_metrics(students, latest_predictions)
    risk_dist = calculate_risk_distribution(students, latest_predictions)
    risk_trends = calculate_risk_trends(students)
    attendance = calculate_attendance_analytics(students)
    academics = calculate_academic_analytics(students)
    interventions = calculate_intervention_analytics(students)
    support = calculate_support_and_follow_up_analytics(students)
    dep_comparisons = calculate_department_comparisons(active_filters)

    filter_options = get_filter_options(
        department_id=active_filters["department_id"],
        course=active_filters["course"],
    )

    report_timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    return {
        "metadata": {
            "title": "Student Dropout Risk Management System - Reports & Analytics",
            "generated_at": report_timestamp,
        },
        "filters": {
            "active": active_filters,
            "options": filter_options,
        },
        "summary": summary,
        "risk_distribution": risk_dist,
        "risk_trends": risk_trends,
        "attendance": attendance,
        "academics": academics,
        "interventions": interventions,
        "support_and_follow_ups": support,
        "department_comparisons": dep_comparisons,
    }


# ============================================================
# CSV EXPORT GENERATOR
# ============================================================

def generate_csv_report(report_data):
    """
    Generate aggregate CSV report string from shared report data.
    Ensures formula-injection sanitization and UTF-8 compatibility.
    Zero student-level rows included.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    meta = report_data["metadata"]
    filters = report_data["filters"]["active"]
    summary = report_data["summary"]

    # Title & Metadata
    writer.writerow([sanitize_csv_cell(meta["title"])])
    writer.writerow(["Generated At", sanitize_csv_cell(meta["generated_at"])])
    writer.writerow([])

    # Active Filters
    writer.writerow(["FILTER PARAMETERS"])
    writer.writerow(["Department", sanitize_csv_cell(filters["department_name"])])
    writer.writerow(["Course", sanitize_csv_cell(filters["course"] or "All Courses")])
    writer.writerow(["Semester", sanitize_csv_cell(str(filters["semester"]) if filters["semester"] else "All Semesters")])
    writer.writerow([])

    # Summary Metrics
    writer.writerow(["EXECUTIVE SUMMARY"])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Students", summary["total_students"]])
    writer.writerow(["Students with High Risk", summary["high_risk_count"]])
    writer.writerow(["Students with Very High Risk", summary["very_high_risk_count"]])
    writer.writerow(["High or Very High Risk Total", summary["high_or_very_high_count"]])
    writer.writerow([
        "Average Current Risk Score",
        f"{summary['average_risk_score']:.2f}" if summary["average_risk_score"] is not None else "N/A",
    ])
    writer.writerow([
        "Average Attendance Percentage",
        f"{summary['average_attendance_percentage']:.2f}%" if summary["average_attendance_percentage"] is not None else "N/A",
    ])
    writer.writerow([
        "Average Academic Performance",
        f"{summary['average_academic_performance']:.2f}%" if summary["average_academic_performance"] is not None else "N/A",
    ])
    writer.writerow([])

    # Risk Distribution
    writer.writerow(["CURRENT RISK DISTRIBUTION"])
    writer.writerow(["Risk Level", "Student Count"])
    for lvl, count in report_data["risk_distribution"].items():
        writer.writerow([sanitize_csv_cell(lvl), count])
    writer.writerow([])

    # Attendance & Academics
    writer.writerow(["ATTENDANCE & ACADEMICS SUMMARY"])
    att = report_data["attendance"]
    acad = report_data["academics"]
    writer.writerow(["Overall Attendance Percentage", f"{att['overall_percentage']:.2f}%" if att["overall_percentage"] is not None else "N/A"])
    writer.writerow(["Total Classes Conducted", att["total_conducted"]])
    writer.writerow(["Total Classes Attended", att["total_attended"]])
    writer.writerow(["Internal Assessment Performance", f"{acad['internal_percentage']:.2f}%" if acad["internal_percentage"] is not None else "N/A"])
    writer.writerow(["Examination Performance", f"{acad['exam_percentage']:.2f}%" if acad["exam_percentage"] is not None else "N/A"])
    writer.writerow([
        "Average Assignment Marks (Scale: 0 - 20)",
        f"{acad['assignment_average_marks_20']:.2f} / 20" if acad["assignment_average_marks_20"] is not None else "N/A",
    ])
    writer.writerow([])

    # Assignment Submissions
    writer.writerow(["ASSIGNMENT SUBMISSION STATUS"])
    writer.writerow(["Status", "Count"])
    for st, count in acad["assignment_status"].items():
        writer.writerow([sanitize_csv_cell(st), count])
    writer.writerow([])

    # Interventions & Support
    writer.writerow(["INTERVENTIONS & SUPPORT"])
    writer.writerow(["Metric", "Count"])
    interv = report_data["interventions"]
    supp = report_data["support_and_follow_ups"]
    writer.writerow(["Total Intervention & Support Activities", interv["total_tracked_activities"]])
    for st, count in interv["status_distribution"].items():
        writer.writerow([f"Activity Status - {sanitize_csv_cell(st)}", count])
    writer.writerow(["Total Referrals", supp["total_referrals"]])
    for st, count in supp["referral_status_distribution"].items():
        writer.writerow([f"Referral Status - {sanitize_csv_cell(st)}", count])
    writer.writerow(["Total Follow-ups", supp["total_follow_ups"]])
    writer.writerow(["Pending Follow-ups", supp["pending_follow_ups"]])
    writer.writerow(["Completed Follow-ups", supp["completed_follow_ups"]])
    writer.writerow(["Overdue Follow-ups", supp["overdue_follow_ups"]])
    writer.writerow([])

    # Department Comparisons
    writer.writerow(["DEPARTMENT COMPARISONS"])
    writer.writerow([
        "Department Name",
        "Total Students",
        "High/Very High Risk",
        "Avg Risk Score",
        "Avg Attendance %",
        "Avg Academic %",
        "Referrals",
        "Interventions",
        "Completed Follow-ups",
    ])
    for dep in report_data["department_comparisons"]:
        writer.writerow([
            sanitize_csv_cell(dep["department_name"]),
            dep["total_students"],
            dep["high_or_very_high_count"],
            f"{dep['average_risk_score']:.2f}" if dep["average_risk_score"] is not None else "N/A",
            f"{dep['average_attendance_percentage']:.2f}%" if dep["average_attendance_percentage"] is not None else "N/A",
            f"{dep['average_academic_percentage']:.2f}%" if dep["average_academic_percentage"] is not None else "N/A",
            dep["total_referrals"],
            dep["total_interventions"],
            dep["completed_follow_ups"],
        ])

    return output.getvalue()


# ============================================================
# EXCEL EXPORT GENERATOR
# ============================================================

def generate_excel_report(report_data):
    """
    Generate multi-sheet Excel (.xlsx) workbook using openpyxl.
    Sheets:
      1. Overview
      2. Risk Analytics
      3. Attendance & Academics
      4. Assignments
      5. Interventions & Follow-ups
      6. Department Comparisons
    """
    if not HAS_OPENPYXL:
        raise RuntimeError(
            "Excel export requires the 'openpyxl' package. Please install it using: pip install openpyxl"
        )

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1F2937")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="4B5563")
    bold_font = Font(name="Calibri", size=10, bold=True)
    regular_font = Font(name="Calibri", size=10)

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    accent_fill = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="E5E7EB"),
        right=Side(style="thin", color="E5E7EB"),
        top=Side(style="thin", color="E5E7EB"),
        bottom=Side(style="thin", color="E5E7EB"),
    )

    def style_header_row(ws, row_idx, max_col):
        for col_idx in range(1, max_col + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

    def auto_adjust_columns(ws):
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                if val:
                    max_len = max(max_len, len(val))
            ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    meta = report_data["metadata"]
    filters = report_data["filters"]["active"]
    summary = report_data["summary"]

    # ----------------------------------------------------
    # Sheet 1: Overview
    # ----------------------------------------------------
    ws1 = wb.create_sheet(title="Overview")
    ws1.views.sheetView[0].showGridLines = True
    ws1.cell(row=1, column=1, value=meta["title"]).font = title_font
    ws1.cell(row=2, column=1, value=f"Generated: {meta['generated_at']}").font = subtitle_font

    ws1.cell(row=4, column=1, value="Active Filter Scope").font = bold_font
    ws1.cell(row=5, column=1, value="Department:").font = bold_font
    ws1.cell(row=5, column=2, value=filters["department_name"]).font = regular_font
    ws1.cell(row=6, column=1, value="Course:").font = bold_font
    ws1.cell(row=6, column=2, value=filters["course"] or "All Courses").font = regular_font
    ws1.cell(row=7, column=1, value="Semester:").font = bold_font
    ws1.cell(row=7, column=2, value=filters["semester"] if filters["semester"] else "All Semesters").font = regular_font

    ws1.cell(row=9, column=1, value="Metric").font = header_font
    ws1.cell(row=9, column=2, value="Aggregate Value").font = header_font
    style_header_row(ws1, 9, 2)

    overview_rows = [
        ("Total Students", summary["total_students"]),
        ("Students with High Risk", summary["high_risk_count"]),
        ("Students with Very High Risk", summary["very_high_risk_count"]),
        ("High or Very High Risk Proportion", summary["high_or_very_high_count"]),
        ("Average Current Risk Score", f"{summary['average_risk_score']:.2f}" if summary["average_risk_score"] is not None else "N/A"),
        ("Average Attendance Percentage", f"{summary['average_attendance_percentage']:.2f}%" if summary["average_attendance_percentage"] is not None else "N/A"),
        ("Average Academic Performance", f"{summary['average_academic_performance']:.2f}%" if summary["average_academic_performance"] is not None else "N/A"),
    ]
    for idx, (m, v) in enumerate(overview_rows, start=10):
        c1 = ws1.cell(row=idx, column=1, value=m)
        c2 = ws1.cell(row=idx, column=2, value=v)
        c1.font = regular_font
        c2.font = bold_font
        c1.border = thin_border
        c2.border = thin_border
    auto_adjust_columns(ws1)

    # ----------------------------------------------------
    # Sheet 2: Risk Analytics
    # ----------------------------------------------------
    ws2 = wb.create_sheet(title="Risk Analytics")
    ws2.views.sheetView[0].showGridLines = True
    ws2.cell(row=1, column=1, value="Current Dropout Risk Distribution").font = title_font
    ws2.cell(row=3, column=1, value="Risk Level")
    ws2.cell(row=3, column=2, value="Student Count")
    ws2.cell(row=3, column=3, value="Percentage of Cohort")
    style_header_row(ws2, 3, 3)

    tot = summary["total_students"]
    r_idx = 4
    for lvl, cnt in report_data["risk_distribution"].items():
        pct_str = f"{(cnt / tot * 100):.1f}%" if tot > 0 else "N/A"
        ws2.cell(row=r_idx, column=1, value=lvl).font = regular_font
        ws2.cell(row=r_idx, column=2, value=cnt).font = regular_font
        ws2.cell(row=r_idx, column=3, value=pct_str).font = regular_font
        for c in range(1, 4):
            ws2.cell(row=r_idx, column=c).border = thin_border
        r_idx += 1

    # Historical trends
    r_idx += 2
    ws2.cell(row=r_idx, column=1, value="Historical Risk Trends (Period Counts)").font = title_font
    r_idx += 2
    headers = ["Period", "Very Low", "Low", "Medium", "High", "Very High", "Total Predictions"]
    for c_i, h in enumerate(headers, start=1):
        ws2.cell(row=r_idx, column=c_i, value=h)
    style_header_row(ws2, r_idx, len(headers))
    r_idx += 1

    trends = report_data["risk_trends"]
    if trends:
        for t in trends:
            ws2.cell(row=r_idx, column=1, value=t["period"]).font = regular_font
            ws2.cell(row=r_idx, column=2, value=t["Very Low"]).font = regular_font
            ws2.cell(row=r_idx, column=3, value=t["Low"]).font = regular_font
            ws2.cell(row=r_idx, column=4, value=t["Medium"]).font = regular_font
            ws2.cell(row=r_idx, column=5, value=t["High"]).font = regular_font
            ws2.cell(row=r_idx, column=6, value=t["Very High"]).font = regular_font
            ws2.cell(row=r_idx, column=7, value=t["total"]).font = bold_font
            for c in range(1, len(headers) + 1):
                ws2.cell(row=r_idx, column=c).border = thin_border
            r_idx += 1
    else:
        ws2.cell(row=r_idx, column=1, value="No historical risk trend data available for current selection.").font = regular_font
    auto_adjust_columns(ws2)

    # ----------------------------------------------------
    # Sheet 3: Attendance & Academics
    # ----------------------------------------------------
    ws3 = wb.create_sheet(title="Attendance & Academics")
    ws3.views.sheetView[0].showGridLines = True
    ws3.cell(row=1, column=1, value="Attendance & Academic Performance Summary").font = title_font

    ws3.cell(row=3, column=1, value="Domain / Metric")
    ws3.cell(row=3, column=2, value="Value")
    style_header_row(ws3, 3, 2)

    att = report_data["attendance"]
    acad = report_data["academics"]
    metrics_rows = [
        ("Overall Attendance Percentage", f"{att['overall_percentage']:.2f}%" if att["overall_percentage"] is not None else "N/A"),
        ("Total Classes Conducted", att["total_conducted"]),
        ("Total Classes Attended", att["total_attended"]),
        ("Internal Assessment Performance", f"{acad['internal_percentage']:.2f}%" if acad["internal_percentage"] is not None else "N/A"),
        ("Internal Records Count", acad["internal_records_count"]),
        ("Examination Performance", f"{acad['exam_percentage']:.2f}%" if acad["exam_percentage"] is not None else "N/A"),
        ("Examination Records Count", acad["exam_records_count"]),
    ]
    for idx, (m, v) in enumerate(metrics_rows, start=4):
        c1 = ws3.cell(row=idx, column=1, value=m)
        c2 = ws3.cell(row=idx, column=2, value=v)
        c1.font = regular_font
        c2.font = regular_font
        c1.border = thin_border
        c2.border = thin_border

    # Attendance Trends
    start_r = 13
    ws3.cell(row=start_r, column=1, value="Monthly Attendance History").font = title_font
    start_r += 2
    ws3.cell(row=start_r, column=1, value="Period")
    ws3.cell(row=start_r, column=2, value="Classes Conducted")
    ws3.cell(row=start_r, column=3, value="Classes Attended")
    ws3.cell(row=start_r, column=4, value="Attendance %")
    style_header_row(ws3, start_r, 4)
    start_r += 1

    if att["trends"]:
        for t in att["trends"]:
            ws3.cell(row=start_r, column=1, value=t["period"]).font = regular_font
            ws3.cell(row=start_r, column=2, value=t["conducted"]).font = regular_font
            ws3.cell(row=start_r, column=3, value=t["attended"]).font = regular_font
            ws3.cell(row=start_r, column=4, value=f"{t['percentage']:.2f}%").font = regular_font
            for c in range(1, 5):
                ws3.cell(row=start_r, column=c).border = thin_border
            start_r += 1
    else:
        ws3.cell(row=start_r, column=1, value="No monthly attendance records available.").font = regular_font
    auto_adjust_columns(ws3)

    # ----------------------------------------------------
    # Sheet 4: Assignments
    # ----------------------------------------------------
    ws4 = wb.create_sheet(title="Assignments")
    ws4.views.sheetView[0].showGridLines = True
    ws4.cell(row=1, column=1, value="Assignment Analytics (Max Marks: 20)").font = title_font

    ws4.cell(row=3, column=1, value="Submission Status")
    ws4.cell(row=3, column=2, value="Count")
    style_header_row(ws4, 3, 2)
    cur_r = 4
    for st, count in acad["assignment_status"].items():
        ws4.cell(row=cur_r, column=1, value=st).font = regular_font
        ws4.cell(row=cur_r, column=2, value=count).font = regular_font
        ws4.cell(row=cur_r, column=1).border = thin_border
        ws4.cell(row=cur_r, column=2).border = thin_border
        cur_r += 1

    cur_r += 2
    ws4.cell(row=cur_r, column=1, value="Assignment Metric").font = bold_font
    ws4.cell(row=cur_r, column=2, value="Value").font = bold_font
    style_header_row(ws4, cur_r, 2)
    cur_r += 1

    assign_summary = [
        ("Total Assignments Created", acad["assignment_total_count"]),
        ("Assignments with Marks Recorded", acad["assignment_graded_count"]),
        ("Average Marks (out of 20 maximum)", f"{acad['assignment_average_marks_20']:.2f} / 20" if acad["assignment_average_marks_20"] is not None else "N/A"),
    ]
    for m, v in assign_summary:
        ws4.cell(row=cur_r, column=1, value=m).font = regular_font
        ws4.cell(row=cur_r, column=2, value=v).font = regular_font
        ws4.cell(row=cur_r, column=1).border = thin_border
        ws4.cell(row=cur_r, column=2).border = thin_border
        cur_r += 1
    auto_adjust_columns(ws4)

    # ----------------------------------------------------
    # Sheet 5: Interventions & Follow-ups
    # ----------------------------------------------------
    ws5 = wb.create_sheet(title="Interventions & Follow-ups")
    ws5.views.sheetView[0].showGridLines = True
    ws5.cell(row=1, column=1, value="Interventions & Follow-up Tracking").font = title_font

    interv = report_data["interventions"]
    supp = report_data["support_and_follow_ups"]

    ws5.cell(row=3, column=1, value="Intervention & Support Activity Status")
    ws5.cell(row=3, column=2, value="Count")
    style_header_row(ws5, 3, 2)
    cur_r = 4
    ws5.cell(row=cur_r, column=1, value="Total Intervention & Support Activities").font = regular_font
    ws5.cell(row=cur_r, column=2, value=interv["total_tracked_activities"]).font = regular_font
    ws5.cell(row=cur_r, column=1).border = thin_border
    ws5.cell(row=cur_r, column=2).border = thin_border
    cur_r += 1
    for st, count in interv["status_distribution"].items():
        ws5.cell(row=cur_r, column=1, value=st).font = regular_font
        ws5.cell(row=cur_r, column=2, value=count).font = regular_font
        ws5.cell(row=cur_r, column=1).border = thin_border
        ws5.cell(row=cur_r, column=2).border = thin_border
        cur_r += 1

    cur_r += 2
    ws5.cell(row=cur_r, column=1, value="Student Support Referrals & Follow-ups").font = title_font
    cur_r += 2
    ws5.cell(row=cur_r, column=1, value="Metric")
    ws5.cell(row=cur_r, column=2, value="Value")
    style_header_row(ws5, cur_r, 2)
    cur_r += 1

    supp_rows = [
        ("Total Referrals", supp["total_referrals"]),
        ("Referrals Pending", supp["referral_status_distribution"]["Pending"]),
        ("Referrals Accepted", supp["referral_status_distribution"]["Accepted"]),
        ("Referrals In Progress", supp["referral_status_distribution"]["In Progress"]),
        ("Referrals Completed", supp["referral_status_distribution"]["Completed"]),
        ("Total Follow-ups", supp["total_follow_ups"]),
        ("Completed Follow-ups", supp["completed_follow_ups"]),
        ("Pending Follow-ups", supp["pending_follow_ups"]),
        ("Overdue Follow-ups (Scheduled < Today)", supp["overdue_follow_ups"]),
    ]
    for m, v in supp_rows:
        ws5.cell(row=cur_r, column=1, value=m).font = regular_font
        ws5.cell(row=cur_r, column=2, value=v).font = regular_font
        ws5.cell(row=cur_r, column=1).border = thin_border
        ws5.cell(row=cur_r, column=2).border = thin_border
        cur_r += 1
    auto_adjust_columns(ws5)

    # ----------------------------------------------------
    # Sheet 6: Department Comparisons
    # ----------------------------------------------------
    ws6 = wb.create_sheet(title="Department Comparisons")
    ws6.views.sheetView[0].showGridLines = True
    ws6.cell(row=1, column=1, value="Department Comparative Analytics").font = title_font

    headers = [
        "Department Name",
        "Total Students",
        "High/Very High Risk",
        "Avg Risk Score",
        "Avg Attendance %",
        "Avg Academic %",
        "Total Referrals",
        "Total Interventions",
        "Completed Follow-ups",
    ]
    ws6.cell(row=3, column=1, value=headers[0])
    for c_i, h in enumerate(headers, start=1):
        ws6.cell(row=3, column=c_i, value=h)
    style_header_row(ws6, 3, len(headers))

    cur_r = 4
    for dep in report_data["department_comparisons"]:
        ws6.cell(row=cur_r, column=1, value=dep["department_name"]).font = regular_font
        ws6.cell(row=cur_r, column=2, value=dep["total_students"]).font = regular_font
        ws6.cell(row=cur_r, column=3, value=dep["high_or_very_high_count"]).font = regular_font
        ws6.cell(row=cur_r, column=4, value=f"{dep['average_risk_score']:.2f}" if dep["average_risk_score"] is not None else "N/A").font = regular_font
        ws6.cell(row=cur_r, column=5, value=f"{dep['average_attendance_percentage']:.2f}%" if dep["average_attendance_percentage"] is not None else "N/A").font = regular_font
        ws6.cell(row=cur_r, column=6, value=f"{dep['average_academic_percentage']:.2f}%" if dep["average_academic_percentage"] is not None else "N/A").font = regular_font
        ws6.cell(row=cur_r, column=7, value=dep["total_referrals"]).font = regular_font
        ws6.cell(row=cur_r, column=8, value=dep["total_interventions"]).font = regular_font
        ws6.cell(row=cur_r, column=9, value=dep["completed_follow_ups"]).font = regular_font

        if dep["is_selected"]:
            for c_i in range(1, len(headers) + 1):
                ws6.cell(row=cur_r, column=c_i).fill = accent_fill

        for c_i in range(1, len(headers) + 1):
            ws6.cell(row=cur_r, column=c_i).border = thin_border

        cur_r += 1
    auto_adjust_columns(ws6)

    # Save to buffer
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    return excel_buffer.getvalue()
