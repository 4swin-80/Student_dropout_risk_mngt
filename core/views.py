from .risk_utils import (
    calculate_student_risk,
    generate_risk_prediction,
)
from datetime import date
from django.db.models import Sum
from django.contrib import messages
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from functools import wraps
import mimetypes
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.shortcuts import (
    redirect,
    render,
    get_object_or_404,
)

from django.http import FileResponse, HttpResponse, JsonResponse
from django.utils import timezone
from .forms import *
from .models import *
from .reports_utils import (
    build_full_report_data,
    get_filter_options,
    generate_csv_report,
    generate_excel_report,
)


# ============================================================
# COMMON HELPERS
# ============================================================

def get_user_role(user):
    """
    Return the application role of the logged-in user.

    Django superusers are always treated as ADMIN.
    """

    if user.is_superuser:
        return "ADMIN"

    try:
        return user.profile.role
    except UserProfile.DoesNotExist:
        return None


def role_required(required_role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect("login")

            # Superusers are NOT allowed to access any application dashboard
            if request.user.is_superuser:
                messages.error(
                    request,
                    "Superuser accounts cannot access application dashboards."
                )
                return redirect("login")

            try:
                profile = request.user.profile
            except UserProfile.DoesNotExist:
                messages.error(
                    request,
                    "Your account does not have a valid role."
                )
                return redirect("login")

            # NONE or another role cannot access this dashboard
            if profile.role != required_role:
                messages.error(
                    request,
                    "You do not have permission to access this page."
                )
                return redirect("login")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def _valid_exam_percentage(marks, maximum_marks):
    """Return an examination percentage only when both marks are valid."""
    if marks is None or maximum_marks is None:
        return None
    try:
        if (not marks.is_finite() or not maximum_marks.is_finite()
                or maximum_marks <= 0 or marks < 0 or marks > maximum_marks):
            return None
        return marks * Decimal("100") / maximum_marks
    except (AttributeError, TypeError, ValueError, ArithmeticError):
        return None


def _valid_academic_percentage(marks, maximum_marks):
    """Return an academic percentage only when both marks are valid."""
    if marks is None or maximum_marks is None:
        return None
    try:
        if (not marks.is_finite() or not maximum_marks.is_finite()
                or maximum_marks <= 0 or marks < 0 or marks > maximum_marks):
            return None
        return marks * Decimal("100") / maximum_marks
    except (AttributeError, TypeError, ValueError, ArithmeticError):
        return None


# ============================================================
# HOME
# ============================================================

def home(request):
    """
    Common application entry point.

    Authenticated users go to their role dashboard.
    Unauthenticated users go to login.
    """

    if request.user.is_authenticated:
        return redirect("dashboard_redirect")

    return redirect("login")


# ============================================================
# LOGIN
# ============================================================


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            messages.error(
                request,
                "Invalid username or password.",
            )
            return render(request, "accounts/login.html")

        if not user.check_password(password):
            messages.error(
                request,
                "Invalid username or password.",
            )
            return render(request, "accounts/login.html")

        try:
            role = user.profile.role
        except UserProfile.DoesNotExist:
            messages.error(
                request,
                "Invalid username or password.",
            )
            return render(request, "accounts/login.html")

        if role not in ["ADMIN", "TEACHER", "MENTOR", "STUDENT"]:
            messages.error(
                request,
                "Invalid username or password.",
            )
            return render(request, "accounts/login.html")

        # Application role is checked before login.
        # Superusers must not enter application dashboards.
        if user.is_superuser:
            messages.error(
                request,
                "Invalid username or password.",
            )
            return render(request, "accounts/login.html")

        login(request, user)

        return redirect("dashboard_redirect")

    return render(request, "accounts/login.html")



# ============================================================
# REGISTER
# ============================================================

def register_view(request):

    if request.user.is_authenticated:
        return redirect("dashboard_redirect")

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        role = request.POST.get("role", "")

        # ----------------------------------------------------
        # Basic validation
        # ----------------------------------------------------

        if not username or not password:

            messages.error(
                request,
                "Username and password are required."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # ----------------------------------------------------
        # Password validation
        # ----------------------------------------------------

        if password != confirm_password:

            messages.error(
                request,
                "Passwords do not match."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # ----------------------------------------------------
        # Username validation
        # ----------------------------------------------------

        if User.objects.filter(username=username).exists():

            messages.error(
                request,
                "Username already exists."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # ----------------------------------------------------
        # SECURITY
        #
        # Public registration ONLY allows:
        # TEACHER
        # MENTOR
        #
        # ADMIN is deliberately rejected.
        # ----------------------------------------------------

        if role not in ["TEACHER", "MENTOR"]:

            messages.error(
                request,
                "Public registration is available only for Teachers and Mentors."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # ----------------------------------------------------
        # Create Django user
        # ----------------------------------------------------

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # ----------------------------------------------------
        # Create profile
        # ----------------------------------------------------

        UserProfile.objects.create(
            user=user,
            role=role
        )

        messages.success(
            request,
            "Registration successful. Please login."
        )

        return redirect("login")

    return render(
        request,
        "accounts/register.html"
    )


# ============================================================
# DASHBOARD REDIRECT
# ============================================================

@login_required
def dashboard_redirect(request):

    try:
        role = request.user.profile.role
    except UserProfile.DoesNotExist:
        messages.error(
            request,
            "Your account does not have a valid role."
        )
        return redirect("login")

    if role == "ADMIN":
        return redirect("admin_dashboard")

    elif role == "TEACHER":
        return redirect("teacher_dashboard")

    elif role == "MENTOR":
        return redirect("mentor_dashboard")

    elif role == "STUDENT":
        return redirect("student_dashboard")

    elif role == "NONE":
        messages.error(
            request,
            "Your account has not been assigned a role yet."
        )
        return redirect("login")

    messages.error(
        request,
        "Your account does not have a valid role."
    )
    return redirect("login")


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@role_required("ADMIN")
def admin_dashboard(request):

    total_students = Student.objects.count()

    total_teachers = Teacher.objects.count()

    total_mentors = Mentor.objects.count()

    total_departments = (
        Student.objects.values("department")
        .exclude(department__isnull=True)
        .distinct()
        .count()
    )

    high_risk_students = (
        RiskPrediction.objects
        .filter(risk_level="High")
        .values("student")
        .distinct()
        .count()
    )

    medium_risk_students = (
        RiskPrediction.objects
        .filter(risk_level="Medium")
        .values("student")
        .distinct()
        .count()
    )

    unread_alerts = Alert.objects.filter(
        is_read=False
    ).count()

    total_interventions = Intervention.objects.count()

    context = {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_mentors": total_mentors,
        "total_departments": total_departments,
        "high_risk_students": high_risk_students,
        "medium_risk_students": medium_risk_students,
        "unread_alerts": unread_alerts,
        "total_interventions": total_interventions,
    }

    return render(
        request,
        "admin/admin_dashboard.html",
        context
    )


# ============================================================
# TEACHER DASHBOARD
# ============================================================

@role_required("TEACHER")
def teacher_dashboard(request):

    total_students = Student.objects.count()

    total_attendance_records = Attendance.objects.count()

    total_academic_records = AcademicPerformance.objects.count()

    total_assignments = Assignment.objects.count()

    total_exam_results = ExamResult.objects.count()

    total_risk_predictions = RiskPrediction.objects.count()

    total_alerts = Alert.objects.count()

    context = {
        "total_students": total_students,
        "total_attendance_records": total_attendance_records,
        "total_academic_records": total_academic_records,
        "total_assignments": total_assignments,
        "total_exam_results": total_exam_results,
        "total_risk_predictions": total_risk_predictions,
        "total_alerts": total_alerts,
    }

    return render(
        request,
        "teacher/teacher_dashboard.html",
        context
    )


# ============================================================
# TEACHER - RISK SCORES
# ============================================================

@role_required("TEACHER")
def teacher_risk_scores(request):
    """
    Calculate and display current risk scores for students.
    This view does not create or modify RiskPrediction records.
    """

    students = Student.objects.all().order_by("student_id")

    risk_results = []

    for student in students:
        result = calculate_student_risk(student)

        risk_results.append({
            "student": student,
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
        })

    context = {
        "risk_results": risk_results,
        "total_students": len(risk_results),
    }

    return render(
        request,
        "teacher/risk_scores.html",
        context,
    )



# ============================================================
# TEACHER - STUDENT SUPPORT
# ============================================================

@role_required("TEACHER")
def teacher_student_support(request):
    """
    Display students with Medium, High, or Very High
    current calculated dropout risk, including their
    latest mentor support referral status.
    """

    students = Student.objects.all().order_by("student_id")

    risk_results = []

    for student in students:
        result = calculate_student_risk(student)

        if result["risk_level"] in ["Medium", "High", "Very High"]:

            latest_referral = StudentSupport.objects.filter(
                student=student
            ).order_by("-created_at").first()

            risk_results.append({
                "student": student,
                "risk_score": result["risk_score"],
                "risk_level": result["risk_level"],
                "support_status": (
                    latest_referral.status
                    if latest_referral
                    else None
                ),
            })

    context = {
        "risk_results": risk_results,
        "total_students": len(risk_results),
        "medium_count": sum(
            1 for item in risk_results
            if item["risk_level"] == "Medium"
        ),
        "high_count": sum(
            1 for item in risk_results
            if item["risk_level"] == "High"
        ),
        "very_high_count": sum(
            1 for item in risk_results
            if item["risk_level"] == "Very High"
        ),
    }

    return render(
        request,
        "teacher/student_support.html",
        context,
    )


# ============================================================
# TEACHER - INDIVIDUAL STUDENT SUPPORT REPORT
# ============================================================

@role_required("TEACHER")
def teacher_student_support_report(request, student_id):
    """
    Display a student's current risk score and academic records.
    """

    student = get_object_or_404(
        Student,
        pk=student_id,
    )

    risk_result = calculate_student_risk(student)

    attendance_records = Attendance.objects.filter(
        student=student
    ).order_by("-date")

    academic_records = AcademicPerformance.objects.filter(
        student=student
    ).order_by("subject")

    assignment_records = Assignment.objects.filter(
        student=student
    ).order_by("-created_at")

    exam_records = ExamResult.objects.filter(
        student=student
    ).order_by("-exam_date", "subject")

    context = {
        "student": student,
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_result["risk_level"],
        "attendance_records": attendance_records,
        "academic_records": academic_records,
        "assignment_records": assignment_records,
        "exam_records": exam_records,
    }

    return render(
        request,
        "teacher/student_support_report.html",
        context,
    )


# ============================================================
# TEACHER - REFER STUDENT TO MENTOR
# ============================================================

@role_required("TEACHER")
def teacher_refer_student_to_mentor(request, student_id):

    student = get_object_or_404(
        Student,
        pk=student_id,
    )

    # Only students with Medium, High, or Very High risk
    # can be referred from the Student Support page.
    risk_result = calculate_student_risk(student)

    if risk_result["risk_level"] not in [
        "Medium",
        "High",
        "Very High",
    ]:
        messages.error(
            request,
            "This student does not currently qualify for a support referral.",
        )
        return redirect("teacher_student_support")

    # Prevent a new referral while any previous referral
    # for this student is not Completed.
    active_referral_exists = StudentSupport.objects.filter(
        student=student,
    ).exclude(
        status="Completed",
    ).exists()

    if active_referral_exists:
        messages.warning(
            request,
            "This student already has an active support referral. "
            "A new referral can be created only after the existing "
            "referral is marked Completed by the mentor.",
        )

        return redirect(
            "teacher_student_support_report",
            student_id=student.pk,
        )

    # Find the mentor assigned to the student's department.
    mentors = Mentor.objects.filter(
        department=student.department,
    ).order_by("employee_id")

    if not student.department or mentors.count() != 1:
        messages.error(
            request,
            "A referral cannot be created. Ensure exactly one mentor "
            "is assigned to the student's department.",
        )
        return redirect(
            "teacher_student_support_report",
            student_id=student.pk,
        )

    mentor = mentors.first()

    if request.method == "POST":

        form = StudentSupportForm(request.POST)

        if form.is_valid():

            support = form.save(commit=False)

            support.student = student
            support.mentor = mentor
            support.teacher = get_object_or_404(
                Teacher,
                user=request.user,
            )
            support.status = "Pending"

            support.save()

            messages.success(
                request,
                "Student support referral sent to the assigned mentor.",
            )

            return redirect(
                "teacher_student_support_report",
                student_id=student.pk,
            )

    else:
        form = StudentSupportForm()

    context = {
        "form": form,
        "student": student,
        "mentor": mentor,
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_result["risk_level"],
    }

    return render(
        request,
        "teacher/refer_student_to_mentor.html",
        context,
    )



# ============================================================
# ADMIN - MONITOR STUDENT RISK SCORES
# ============================================================

@role_required("ADMIN")
def admin_risk_scores(request):
    """
    Display saved dropout risk scores for all students.
    """

    risk_results = (
        RiskPrediction.objects
        .select_related("student")
        .order_by("-prediction_date")
    )

    context = {
        "risk_results": risk_results,
        "total_students": risk_results.count(),
    }

    return render(
        request,
        "admin/risk_scores.html",
        context,
    )
    


# ============================================================
# TEACHER - VIEW HIGH-RISK STUDENT ALERTS
# ============================================================

@role_required("TEACHER")
def teacher_alerts(request):
    """
    Display students whose latest saved risk prediction
    is High or Very High.
    """

    high_risk_predictions = (
        RiskPrediction.objects
        .filter(risk_level__in=["High", "Very High"])
        .select_related("student")
        .order_by("-prediction_date")
    )

    context = {
        "high_risk_predictions": high_risk_predictions,
        "total_alerts": high_risk_predictions.count(),
    }

    return render(
        request,
        "teacher/alerts.html",
        context,
    )



# ============================================================
# ADMIN - VIEW HIGH-RISK STUDENT ALERTS
# ============================================================

@role_required("ADMIN")
def admin_alerts(request):
    """
    Display students whose saved risk predictions
    are High or Very High.
    """

    high_risk_predictions = (
        RiskPrediction.objects
        .filter(risk_level__in=["High", "Very High"])
        .select_related("student")
        .order_by("-prediction_date")
    )

    context = {
        "high_risk_predictions": high_risk_predictions,
        "total_alerts": high_risk_predictions.count(),
    }

    return render(
        request,
        "admin/alerts.html",
        context,
    )




# ============================================================
# TEACHER - GENERATE RISK PREDICTIONS
# ============================================================

@role_required("TEACHER")
def teacher_generate_predictions(request):

    if request.method != "POST":
        return redirect("teacher_risk_scores")

    students = Student.objects.all().order_by("student_id")

    if not students.exists():
        messages.warning(
            request,
            "No students are available for risk prediction."
        )
        return redirect("teacher_risk_scores")

    generated_count = 0

    for student in students:
        generate_risk_prediction(student)
        generated_count += 1

    messages.success(
        request,
        f"Risk predictions generated for {generated_count} students."
    )

    return redirect("teacher_risk_scores")




# ============================================================
# TEACHER - ATTENDANCE MANAGEMENT
# ============================================================

@role_required("TEACHER")
def attendance_create(request):

    try:
        teacher = Teacher.objects.get(
            user=request.user
        )
    except Teacher.DoesNotExist:

        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )

        return redirect("teacher_dashboard")

    if request.method == "POST":

        form = AttendanceForm(request.POST)

        if form.is_valid():

            attendance = form.save(commit=False)

            # Calculate attendance percentage
            if attendance.classes_conducted > 0:

                attendance.attendance_percentage = (
                    Decimal(attendance.classes_attended)
                    / Decimal(attendance.classes_conducted)
                    * Decimal("100")
                )

            else:

                attendance.attendance_percentage = Decimal("0")

            # Store the teacher who entered the record
            attendance.entered_by = teacher

            attendance.save()

            messages.success(
                request,
                "Attendance record added successfully."
            )

            return redirect("attendance_list")

    else:

        form = AttendanceForm()

    return render(
        request,
        "teacher/attendance_form.html",
        {
            "form": form,
        }
    )


@role_required("TEACHER")
def attendance_list(request):

    try:
        teacher = Teacher.objects.get(
            user=request.user
        )
    except Teacher.DoesNotExist:

        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )

        return redirect("teacher_dashboard")

    attendance_records = (
        Attendance.objects
        .filter(entered_by=teacher)
        .select_related("student")
        .order_by("-date", "student")
    )

    return render(
        request,
        "teacher/attendance_list.html",
        {
            "attendance_records": attendance_records,
        }
    )


# ============================================================
# TEACHER - ACADEMIC PERFORMANCE MANAGEMENT
# ============================================================

@role_required("TEACHER")
def academic_performance_create(request):

    try:
        teacher = Teacher.objects.get(
            user=request.user
        )
    except Teacher.DoesNotExist:

        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )

        return redirect("teacher_dashboard")

    if request.method == "POST":

        form = AcademicPerformanceForm(request.POST)

        if form.is_valid():

            performance = form.save(commit=False)

            # Record the teacher who entered the information
            performance.entered_by = teacher

            performance.save()

            messages.success(
                request,
                "Academic performance added successfully."
            )

            return redirect("academic_performance_list")

    else:

        form = AcademicPerformanceForm()

    return render(
        request,
        "teacher/academic_performance_form.html",
        {
            "form": form,
        }
    )


@role_required("TEACHER")
def academic_performance_list(request):

    try:
        teacher = Teacher.objects.get(
            user=request.user
        )
    except Teacher.DoesNotExist:

        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )

        return redirect("teacher_dashboard")

    performance_records = (
        AcademicPerformance.objects
        .filter(entered_by=teacher)
        .select_related("student")
        .order_by("-created_at", "student", "subject")
    )

    return render(
        request,
        "teacher/academic_performance_list.html",
        {
            "performance_records": performance_records,
        }
    )


@role_required("TEACHER")
def teacher_student_list(request):

    students = (
        Student.objects
        .select_related("department", "mentor")
        .order_by("student_id")
    )

    return render(
        request,
        "teacher/student_list.html",
        {
            "students": students
        }
    )


@role_required("TEACHER")
def assignment_create(request):

    try:
        teacher = Teacher.objects.get(user=request.user)

    except Teacher.DoesNotExist:
        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )
        return redirect("teacher_dashboard")

    if request.method == "POST":

        form = AssignmentForm(request.POST)

        if form.is_valid():

            assignment = form.save(commit=False)

            assignment.entered_by = teacher

            assignment.save()

            messages.success(
                request,
                "Assignment added successfully."
            )

            return redirect("assignment_list")

    else:
        form = AssignmentForm()

    return render(
        request,
        "teacher/assignment_form.html",
        {
            "form": form
        }
    )


@role_required("TEACHER")
def assignment_list(request):

    try:
        teacher = Teacher.objects.get(user=request.user)

    except Teacher.DoesNotExist:
        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )
        return redirect("teacher_dashboard")

    assignment_records = (
        Assignment.objects
        .filter(entered_by=teacher)
        .select_related("student")
        .order_by("-created_at", "student", "subject")
    )

    return render(
        request,
        "teacher/assignment_list.html",
        {
            "assignment_records": assignment_records
        }
    )


@role_required("TEACHER")
def exam_result_create(request):

    try:
        teacher = Teacher.objects.get(user=request.user)

    except Teacher.DoesNotExist:
        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )
        return redirect("teacher_dashboard")

    if request.method == "POST":

        form = ExamResultForm(request.POST)

        if form.is_valid():

            exam_result = form.save(commit=False)

            exam_result.entered_by = teacher

            exam_result.save()

            messages.success(
                request,
                "Examination result added successfully."
            )

            return redirect("exam_result_list")

    else:
        form = ExamResultForm()

    return render(
        request,
        "teacher/exam_result_form.html",
        {
            "form": form
        }
    )


@role_required("TEACHER")
def exam_result_list(request):

    try:
        teacher = Teacher.objects.get(user=request.user)

    except Teacher.DoesNotExist:
        messages.error(
            request,
            "Your teacher profile has not been created yet."
        )
        return redirect("teacher_dashboard")

    exam_results = (
        ExamResult.objects
        .filter(entered_by=teacher)
        .select_related("student")
        .order_by("-exam_date", "-created_at", "student", "subject")
    )

    return render(
        request,
        "teacher/exam_result_list.html",
        {
            "exam_results": exam_results
        }
    )





@role_required("STUDENT")
def student_dashboard(request):
    try:
        # Always resolve the student from the authenticated account.
        student = request.user.student_record

    except Student.DoesNotExist:
        return render(
            request,
            "student/student_dashboard.html",
            {
                "student": None,
                "student_profile_error": (
                    "Your student profile is not linked to this account. "
                    "Please contact the administrator."
                ),
            },
            status=403,
        )

    # --------------------------------------------------
    # ATTENDANCE SUMMARY AND HISTORY
    # --------------------------------------------------
    attendance_records = Attendance.objects.filter(
        student=student
    ).order_by("-date", "-id")

    attendance_history = []

    total_classes_conducted = 0
    total_classes_attended = 0

    for record in attendance_records:
        conducted = record.classes_conducted
        attended = record.classes_attended

        # Do not calculate misleading percentages for invalid records.
        valid_record = (
            conducted > 0
            and 0 <= attended <= conducted
        )

        if valid_record:
            percentage = (
                Decimal(attended) * Decimal("100")
                / Decimal(conducted)
            ).quantize(Decimal("0.01"))

            missed = conducted - attended

            total_classes_conducted += conducted
            total_classes_attended += attended
        else:
            percentage = None
            missed = None

        attendance_history.append({
            "date": record.date,
            "classes_conducted": conducted,
            "classes_attended": attended,
            "classes_missed": missed,
            "attendance_percentage": percentage,
            "is_valid": valid_record,
        })

    attendance_percentage = None
    total_classes_missed = None

    if total_classes_conducted > 0:
        attendance_percentage = (
            Decimal(total_classes_attended)
            * Decimal("100")
            / Decimal(total_classes_conducted)
        ).quantize(Decimal("0.01"))

        total_classes_missed = (
            total_classes_conducted - total_classes_attended
        )

    
    # --------------------------------------------------
    # ACADEMIC PERFORMANCE SUMMARY
    # --------------------------------------------------
    academic_records = AcademicPerformance.objects.filter(
        student=student
    ).values_list(
        "internal_marks",
        "total_internal_marks",
    )

    academic_percentages = []

    for marks, maximum_marks in academic_records:
        valid_record = (
            marks is not None
            and maximum_marks is not None
            and maximum_marks > 0
            and marks >= 0
            and marks <= maximum_marks
        )

        if valid_record:
            percentage = (
                Decimal(marks) * Decimal("100")
                / Decimal(maximum_marks)
            )
            academic_percentages.append(percentage)

    academic_average = None

    if academic_percentages:
        academic_average = (
            sum(academic_percentages, Decimal("0"))
            / Decimal(len(academic_percentages))
        ).quantize(Decimal("0.01"))


    # Academic performance history for this authenticated student's record only.
    academic_records = AcademicPerformance.objects.filter(
        student=student
    ).order_by("-created_at", "-id")

    academic_history = []

    for record in academic_records:
        marks = record.internal_marks
        total_marks = record.total_internal_marks

        valid_record = (
            total_marks is not None
            and total_marks > 0
            and marks is not None
            and marks >= 0
            and marks <= total_marks
        )

        if valid_record:
            percentage = (
                Decimal(marks) * Decimal("100")
                / Decimal(total_marks)
            ).quantize(Decimal("0.01"))
        else:
            percentage = None

        academic_history.append({
            "subject": record.subject,
            "marks_obtained": marks,
            "total_marks": total_marks,
            "percentage": percentage,
            "is_valid": valid_record,
            "created_at": record.created_at,
        })

    # --------------------------------------------------
    # ASSIGNMENT SUMMARY
    # --------------------------------------------------
    assignments = Assignment.objects.filter(
        student=student
    )

    assignment_count = assignments.count()

    pending_assignment_count = assignments.filter(
        status="Pending"
    ).count()

    # --------------------------------------------------
    # EXAMINATION SUMMARY
    # --------------------------------------------------
    exam_results = ExamResult.objects.filter(
        student=student
    )

    exam_count = exam_results.count()
    valid_exam_percentages = []

    for marks, maximum_marks in exam_results.values_list(
        "marks_obtained",
        "total_marks",
    ):
        percentage = _valid_exam_percentage(marks, maximum_marks)
        if percentage is not None:
            valid_exam_percentages.append(percentage)

    exam_average = None

    if valid_exam_percentages:
        exam_average = (
            sum(valid_exam_percentages, Decimal("0"))
            / Decimal(len(valid_exam_percentages))
        ).quantize(Decimal("0.01"))

    # --------------------------------------------------
    # DASHBOARD CONTEXT
    # --------------------------------------------------
    context = {
        "student": student,

        # Attendance
        "attendance_history": attendance_history,
        "attendance_percentage": attendance_percentage,
        "total_classes_conducted": total_classes_conducted,
        "total_classes_attended": total_classes_attended,
        "total_classes_missed": total_classes_missed,

        # Academic summary
        "academic_average": academic_average,
        "academic_history": academic_history,

        # Assignment summary
        "assignment_count": assignment_count,
        "pending_assignment_count": pending_assignment_count,

        # Examination summary
        "exam_count": exam_count,
        "exam_average": exam_average,
    }

    return render(
        request,
        "student/student_dashboard.html",
        context,
    )


@role_required("STUDENT")
def student_notifications(request):
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return render(
            request,
            "student/student_dashboard.html",
            {
                "student": None,
                "student_profile_error": (
                    "Your student profile is not linked to this account. "
                    "Please contact the administrator."
                ),
            },
            status=403,
        )

    notifications = StudentNotification.objects.filter(student=student)
    unread_count = notifications.filter(is_read=False).count()
    total_count = notifications.count()
    return render(
        request,
        "student/student_notifications.html",
        {
            "notifications": notifications,
            "total_count": total_count,
            "unread_count": unread_count,
            "read_count": total_count - unread_count,
        },
    )


@role_required("STUDENT")
@require_POST
def student_notification_mark_read(request, notification_id):
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return HttpResponse("Student profile is not linked to this account.", status=403)

    notification = get_object_or_404(
        StudentNotification, pk=notification_id, student=student
    )
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        messages.success(request, "Notification marked as read.")
    return redirect("student_notifications")


@role_required("ADMIN")
def admin_student_notification_create(request):
    form = StudentNotificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        notification = form.save(commit=False)
        notification.created_by = request.user
        notification.save()
        messages.success(request, "Student notification created.")
        return redirect("admin_student_notification_create")
    return render(
        request, "admin/student_notification_form.html", {"form": form}
    )


@role_required("STUDENT")
def student_examination_results(request):
    """Show examination results belonging only to the signed-in student."""
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return render(
            request,
            "student/student_dashboard.html",
            {
                "student": None,
                "student_profile_error": (
                    "Your student profile is not linked to this account. "
                    "Please contact the administrator."
                ),
            },
            status=403,
        )

    exam_results = ExamResult.objects.filter(student=student).order_by(
        "-exam_date", "-created_at", "-id"
    )
    exam_rows = []
    valid_percentages = []
    valid_result_count = 0
    awaiting_marks_count = 0

    for result in exam_results:
        percentage = _valid_exam_percentage(
            result.marks_obtained, result.total_marks
        )
        awaiting_marks = (
            result.marks_obtained is None or result.total_marks is None
        )
        if percentage is not None:
            valid_result_count += 1
            valid_percentages.append(percentage)
        if awaiting_marks:
            awaiting_marks_count += 1
        exam_rows.append({
            "result": result,
            "percentage": percentage.quantize(Decimal("0.01"))
            if percentage is not None else None,
            "awaiting_marks": awaiting_marks,
        })

    exam_average = None
    if valid_percentages:
        exam_average = (
            sum(valid_percentages, Decimal("0"))
            / Decimal(len(valid_percentages))
        ).quantize(Decimal("0.01"))

    return render(
        request,
        "student/student_examination_results.html",
        {
            "student": student,
            "exam_rows": exam_rows,
            "exam_record_count": len(exam_rows),
            "valid_result_count": valid_result_count,
            "awaiting_marks_count": awaiting_marks_count,
            "exam_average": exam_average,
        },
    )


@role_required("STUDENT")
def student_performance(request):
    """Show read-only performance charts for the signed-in student."""
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return render(
            request,
            "student/student_dashboard.html",
            {
                "student": None,
                "student_profile_error": (
                    "Your student profile is not linked to this account. "
                    "Please contact the administrator."
                ),
            },
            status=403,
        )

    academic_records = AcademicPerformance.objects.filter(
        student=student
    ).order_by("created_at", "id")
    exam_results = ExamResult.objects.filter(
        student=student
    ).order_by("exam_date", "created_at", "id")

    academic_points = []
    academic_percentages = []
    for record in academic_records:
        percentage = _valid_academic_percentage(
            record.internal_marks, record.total_internal_marks
        )
        if percentage is None:
            continue
        percentage = percentage.quantize(Decimal("0.01"))
        academic_percentages.append(percentage)
        academic_points.append({
            "label": record.subject,
            "percentage": float(percentage),
        })

    exam_points = []
    exam_percentages = []
    dated_exam_points = []
    for result in exam_results:
        percentage = _valid_exam_percentage(result.marks_obtained, result.total_marks)
        if percentage is None:
            continue
        percentage = percentage.quantize(Decimal("0.01"))
        exam_percentages.append(percentage)
        label = f"{result.exam_name} — {result.subject} (#{result.pk})"
        point = {"label": label, "percentage": float(percentage)}
        exam_points.append(point)
        if result.exam_date:
            dated_exam_points.append({
                "label": f"{result.exam_date.isoformat()} — {label}",
                "date": result.exam_date.isoformat(),
                "percentage": float(percentage),
            })

    academic_average = (
        (sum(academic_percentages, Decimal("0")) / len(academic_percentages))
        .quantize(Decimal("0.01")) if academic_percentages else None
    )
    exam_average = (
        (sum(exam_percentages, Decimal("0")) / len(exam_percentages))
        .quantize(Decimal("0.01")) if exam_percentages else None
    )
    has_trend = len(dated_exam_points) >= 2

    return render(request, "student/student_performance.html", {
        "student": student,
        "academic_average": academic_average,
        "exam_average": exam_average,
        "valid_academic_record_count": len(academic_points),
        "valid_exam_record_count": len(exam_points),
        "academic_chart_data": academic_points,
        "exam_chart_data": exam_points,
        "performance_trend_data": dated_exam_points if has_trend else [],
        "has_performance_trend": has_trend,
    })


@role_required("STUDENT")
def student_assignments(request):
    """Show assignment records belonging only to the signed-in student."""
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return render(
            request,
            "student/student_dashboard.html",
            {
                "student": None,
                "student_profile_error": (
                    "Your student profile is not linked to this account. "
                    "Please contact the administrator."
                ),
            },
            status=403,
        )

    assignments = Assignment.objects.filter(student=student).order_by(
        "-created_at", "-id"
    )
    assignment_rows = []
    for assignment in assignments:
        marks = assignment.marks
        assignment_rows.append({
            "assignment": assignment,
            "valid_marks": marks is not None and Decimal("0") <= marks <= Decimal("20"),
        })

    context = {
        "student": student,
        "assignment_rows": assignment_rows,
        "assignment_count": assignments.count(),
        "pending_assignment_count": assignments.filter(status="Pending").count(),
        "submitted_assignment_count": assignments.filter(status="Submitted").count(),
        "late_assignment_count": assignments.filter(status="Late").count(),
    }
    return render(request, "student/student_assignments.html", context)


@role_required("STUDENT")
def student_profile(request):
    """Show only the student record linked to the authenticated account."""
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return render(
            request,
            "student/student_profile.html",
            {
                "student": None,
                "student_profile_error": (
                    "Your student profile is not linked to this account. "
                    "Please contact the administrator."
                ),
            },
            status=403,
        )

    if request.method == "POST":
        form = StudentProfileForm(
            request.POST,
            request.FILES,
            instance=student,
        )
        if form.is_valid():
            previous_photo_name = student.profile_photo.name
            photo_changed = bool(request.FILES.get("profile_photo"))
            form.save()
            if photo_changed and previous_photo_name:
                student.profile_photo.storage.delete(previous_photo_name)
            messages.success(request, "Your profile has been updated.")
            return redirect("student_profile")
    else:
        form = StudentProfileForm(instance=student)

    return render(
        request,
        "student/student_profile.html",
        {"student": student, "form": form},
    )


@role_required("STUDENT")
def student_profile_photo(request):
    """Serve the authenticated student's own profile photo."""
    try:
        student = request.user.student_record
    except Student.DoesNotExist:
        return HttpResponse(status=403)

    if not student.profile_photo:
        return HttpResponse(status=404)

    content_type = mimetypes.guess_type(student.profile_photo.name)[0]
    response = FileResponse(
        student.profile_photo.open("rb"),
        content_type=content_type or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response



# ============================================================
# MENTOR DASHBOARD
# ============================================================

@role_required("MENTOR")
def mentor_dashboard(request):

    try:
        mentor = Mentor.objects.get(
            user=request.user
        )

        assigned_students = Student.objects.filter(
            mentor=mentor
        )

        assigned_student_count = assigned_students.count()

        high_risk_students = (
            RiskPrediction.objects
            .filter(
                student__mentor=mentor,
                risk_level="High"
            )
            .values("student")
            .distinct()
            .count()
        )

        medium_risk_students = (
            RiskPrediction.objects
            .filter(
                student__mentor=mentor,
                risk_level="Medium"
            )
            .values("student")
            .distinct()
            .count()
        )

        intervention_count = Intervention.objects.filter(
            mentor=mentor
        ).count()

        follow_up_count = Intervention.objects.filter(
            mentor=mentor,
            status="Follow-up Required"
        ).count()

        alert_count = Alert.objects.filter(
            student__mentor=mentor,
            is_read=False
        ).count()

    except Mentor.DoesNotExist:

        # The account may have been registered as a
        # MENTOR but the Mentor record has not yet been
        # created by the administrator.

        assigned_student_count = 0
        high_risk_students = 0
        medium_risk_students = 0
        intervention_count = 0
        follow_up_count = 0
        alert_count = 0

    context = {
        "assigned_student_count": assigned_student_count,
        "high_risk_students": high_risk_students,
        "medium_risk_students": medium_risk_students,
        "intervention_count": intervention_count,
        "follow_up_count": follow_up_count,
        "alert_count": alert_count,
    }

    return render(
        request,
        "mentor/mentor_dashboard.html",
        context
    )


# ============================================================
# MENTOR - ASSIGNED STUDENTS
# ============================================================

@role_required("MENTOR")
def mentor_assigned_students(request):

    try:
        mentor = Mentor.objects.get(
            user=request.user
        )

    except Mentor.DoesNotExist:

        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )

        return redirect("mentor_dashboard")

    assigned_students = (
        Student.objects
        .filter(mentor=mentor)
        .select_related("department")
        .order_by("student_id")
    )

    context = {
        "assigned_students": assigned_students,
    }

    return render(
        request,
        "mentor/assigned_students.html",
        context
    )




# ============================================================
# MENTOR - STUDENT SUPPORT & INTERVENTIONS
# ============================================================

@role_required("MENTOR")
def mentor_student_support(request):

    try:
        mentor = Mentor.objects.get(
            user=request.user
        )

    except Mentor.DoesNotExist:

        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )

        return redirect("mentor_dashboard")

    support_referrals = (
        StudentSupport.objects
        .filter(mentor=mentor)
        .select_related(
            "student",
            "teacher",
            "mentor",
            "student__department",
        )
        .order_by("-created_at")
    )

    pending_count = support_referrals.filter(
        status="Pending"
    ).count()

    context = {
        "support_referrals": support_referrals,
        "pending_count": pending_count,
    }

    return render(
        request,
        "mentor/student_support.html",
        context
    )



# ============================================================
# MENTOR - REVIEW STUDENT SUPPORT REFERRAL
# ============================================================

@role_required("MENTOR")
def mentor_review_student_support(request, support_id):

    try:
        mentor = Mentor.objects.get(
            user=request.user
        )

    except Mentor.DoesNotExist:

        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )

        return redirect("mentor_dashboard")

    support = get_object_or_404(
        StudentSupport.objects.select_related(
            "student",
            "teacher",
            "mentor",
            "student__department",
        ),
        pk=support_id,
        mentor=mentor,
    )

    context = {
        "support": support,
    }

    return render(
        request,
        "mentor/review_student_support.html",
        context
    )



# ============================================================
# MENTOR - UPDATE STUDENT SUPPORT STATUS
# ============================================================

@role_required("MENTOR")
def mentor_update_student_support_status(request, support_id):

    if request.method != "POST":
        return redirect("mentor_student_support")

    try:
        mentor = Mentor.objects.get(
            user=request.user
        )

    except Mentor.DoesNotExist:

        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )

        return redirect("mentor_dashboard")

    support = get_object_or_404(
        StudentSupport,
        pk=support_id,
        mentor=mentor,
    )

    form = MentorStudentSupportStatusForm(
        request.POST,
        instance=support,
    )

    if form.is_valid():

        form.save()

        messages.success(
            request,
            "Student support referral status updated successfully."
        )

    else:

        messages.error(
            request,
            "Unable to update the referral status. Please select a valid status."
        )

    return redirect(
        "mentor_review_student_support",
        support_id=support.pk,
    )


# ============================================================
# MENTOR - VIEW ASSIGNED STUDENT RISK SCORES
# ============================================================

@role_required("MENTOR")
def mentor_risk_scores(request):
    """
    Calculate and display risk scores for students
    assigned to the logged-in mentor.
    """

    try:
        mentor = Mentor.objects.get(user=request.user)

    except Mentor.DoesNotExist:
        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )
        return redirect("mentor_dashboard")

    assigned_students = (
        Student.objects
        .filter(mentor=mentor)
        .order_by("student_id")
    )

    risk_results = []

    for student in assigned_students:
        result = calculate_student_risk(student)

        risk_results.append({
            "student": student,
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
        })

    context = {
        "risk_results": risk_results,
        "total_students": len(risk_results),
    }

    return render(
        request,
        "mentor/risk_scores.html",
        context,
    )



# ============================================================
# MENTOR - VIEW ASSIGNED STUDENT RISK ALERTS
# ============================================================

@role_required("MENTOR")
def mentor_risk_alerts(request):
    """
    Display High and Very High risk predictions
    for students assigned to the logged-in mentor.
    """

    try:
        mentor = Mentor.objects.get(user=request.user)

    except Mentor.DoesNotExist:
        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )
        return redirect("mentor_dashboard")

    high_risk_predictions = (
        RiskPrediction.objects
        .filter(
            student__mentor=mentor,
            risk_level__in=["High", "Very High"],
        )
        .select_related("student")
        .order_by("-prediction_date")
    )

    context = {
        "high_risk_predictions": high_risk_predictions,
        "total_alerts": high_risk_predictions.count(),
    }

    return render(
        request,
        "mentor/alerts.html",
        context,
    )
    



# ============================================================
# LOGOUT
# ============================================================

@login_required
def logout_view(request):

    logout(request)

    messages.success(
        request,
        "You have been logged out successfully."
    )

    return redirect("login")

# ============================================================
# ADMIN - TEACHER MANAGEMENT
# ============================================================

@role_required("ADMIN")
def teacher_list(request):

    teachers = Teacher.objects.select_related(
        "user",
        "department",
    ).order_by(
        "employee_id"
    )

    context = {
        "teachers": teachers,
    }

    return render(
        request,
        "admin/teachers/teacher_list.html",
        context
    )

@role_required("ADMIN")
def teacher_create(request):

    if request.method == "POST":

        form = TeacherForm(request.POST)

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Teacher added successfully."
            )

            return redirect("teacher_list")

    else:

        form = TeacherForm()

    context = {
        "form": form,
        "page_title": "Add Teacher",
        "submit_text": "Add Teacher",
    }

    return render(
        request,
        "admin/teachers/teacher_form.html",
        context
    )   

@role_required("ADMIN")
def teacher_detail(request, teacher_id):

    teacher = get_object_or_404(
        Teacher.objects.select_related(
            "user",
            "department",
        ),
        id=teacher_id
    )

    context = {
        "teacher": teacher,
    }

    return render(
        request,
        "admin/teachers/teacher_detail.html",
        context
    ) 

@role_required("ADMIN")
def teacher_update(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id
    )

    if request.method == "POST":

        form = TeacherForm(
            request.POST,
            instance=teacher
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Teacher updated successfully."
            )

            return redirect(
                "teacher_detail",
                teacher_id=teacher.id
            )

    else:

        form = TeacherForm(
            instance=teacher
        )

    context = {
        "form": form,
        "page_title": "Edit Teacher",
        "submit_text": "Update Teacher",
        "teacher": teacher,
    }

    return render(
        request,
        "admin/teachers/teacher_form.html",
        context
    )

@role_required("ADMIN")
def teacher_delete(request, teacher_id):

    teacher = get_object_or_404(
        Teacher,
        id=teacher_id
    )

    if request.method == "POST":

        teacher.delete()

        messages.success(
            request,
            "Teacher deleted successfully."
        )

        return redirect("teacher_list")

    context = {
        "teacher": teacher,
    }

    return render(
        request,
        "admin/teachers/teacher_confirm_delete.html",
        context
    )  


@role_required("ADMIN")
def mentor_list(request):
    mentors = Mentor.objects.select_related(
        "user", "department"
    ).order_by("employee_id")

    context = {
        "mentors": mentors
    }

    return render(
        request,
        "admin/mentors/mentor_list.html",
        context
    )


@role_required("ADMIN")
def mentor_create(request):
    if request.method == "POST":
        form = MentorForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Mentor added successfully."
            )
            return redirect("mentor_list")

    else:
        form = MentorForm()

    context = {
        "form": form,
        "page_title": "Add Mentor",
        "submit_text": "Add Mentor",
    }

    return render(
        request,
        "admin/mentors/mentor_form.html",
        context
    )


@role_required("ADMIN")
def mentor_detail(request, mentor_id):
    mentor = get_object_or_404(
        Mentor.objects.select_related(
            "user", "department"
        ),
        id=mentor_id
    )

    context = {
        "mentor": mentor
    }

    return render(
        request,
        "admin/mentors/mentor_detail.html",
        context
    )


@role_required("ADMIN")
def mentor_update(request, mentor_id):
    mentor = get_object_or_404(
        Mentor,
        id=mentor_id
    )

    if request.method == "POST":
        form = MentorForm(
            request.POST,
            instance=mentor
        )

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Mentor updated successfully."
            )
            return redirect(
                "mentor_detail",
                mentor_id=mentor.id
            )

    else:
        form = MentorForm(instance=mentor)

    context = {
        "form": form,
        "page_title": "Edit Mentor",
        "submit_text": "Update Mentor",
        "mentor": mentor,
    }

    return render(
        request,
        "admin/mentors/mentor_form.html",
        context
    )


@role_required("ADMIN")
def mentor_delete(request, mentor_id):
    mentor = get_object_or_404(
        Mentor,
        id=mentor_id
    )

    if request.method == "POST":
        mentor.delete()
        messages.success(
            request,
            "Mentor deleted successfully."
        )
        return redirect("mentor_list")

    context = {
        "mentor": mentor
    }

    return render(
        request,
        "admin/mentors/mentor_confirm_delete.html",
        context
    )


@role_required("ADMIN")
def department_list(request):
    departments = Department.objects.all().order_by("name")

    context = {
        "departments": departments
    }

    return render(
        request,
        "admin/departments/department_list.html",
        context
    )


@role_required("ADMIN")
def department_create(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Department added successfully."
            )
            return redirect("department_list")

    else:
        form = DepartmentForm()

    context = {
        "form": form,
        "page_title": "Add Department",
        "submit_text": "Add Department",
    }

    return render(
        request,
        "admin/departments/department_form.html",
        context
    )


@role_required("ADMIN")
def department_detail(request, department_id):
    department = get_object_or_404(
        Department,
        id=department_id
    )

    context = {
        "department": department
    }

    return render(
        request,
        "admin/departments/department_detail.html",
        context
    )


@role_required("ADMIN")
def department_update(request, department_id):
    department = get_object_or_404(
        Department,
        id=department_id
    )

    if request.method == "POST":
        form = DepartmentForm(
            request.POST,
            instance=department
        )

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Department updated successfully."
            )
            return redirect(
                "department_detail",
                department_id=department.id
            )

    else:
        form = DepartmentForm(
            instance=department
        )

    context = {
        "form": form,
        "page_title": "Edit Department",
        "submit_text": "Update Department",
        "department": department,
    }

    return render(
        request,
        "admin/departments/department_form.html",
        context
    )


@role_required("ADMIN")
def department_delete(request, department_id):
    department = get_object_or_404(
        Department,
        id=department_id
    )

    if request.method == "POST":
        department.delete()
        messages.success(
            request,
            "Department deleted successfully."
        )
        return redirect("department_list")

    context = {
        "department": department
    }

    return render(
        request,
        "admin/departments/department_confirm_delete.html",
        context
    )


# ============================================================
# ADMIN - STUDENT MANAGEMENT
# ============================================================

@role_required("ADMIN")
def student_list(request):

    students = Student.objects.select_related(
        "department",
        "mentor",
    ).order_by("student_id")

    context = {
        "students": students,
    }

    return render(
        request,
        "admin/students/student_list.html",
        context
    )



@role_required("ADMIN")
def student_create(request):
    if request.method == "POST":
        form = StudentForm(request.POST)

        if form.is_valid():
            student_id = form.cleaned_data["student_id"]

            # Do not reuse an unrelated existing account.
            if User.objects.filter(username=student_id).exists():
                form.add_error(
                    "student_id",
                    "An account with this Student ID already exists. "
                    "Please resolve the username conflict.",
                )
            else:
                try:
                    with transaction.atomic():
                        student = form.save(commit=False)

                        user = User.objects.create_user(
                            username=student_id,
                            password=form.cleaned_data[
                                "student_password"
                            ],
                            first_name=student.first_name,
                            last_name=student.last_name,
                            email=student.email,
                        )

                        profile, created = (
                            UserProfile.objects.get_or_create(
                                user=user,
                                defaults={"role": "STUDENT"},
                            )
                        )

                        if profile.role != "STUDENT":
                            raise ValidationError(
                                "The new account has an "
                                "unexpected application role."
                            )

                        student.user = user
                        student.save()
                        form.save_m2m()

                    messages.success(
                        request,
                        "Student and login account created successfully.",
                    )

                    return redirect("student_list")

                except ValidationError as exc:
                    form.add_error(None, exc)
                except IntegrityError:
                    form.add_error(
                        "student_id",
                        "This Student ID conflicts with an existing record or "
                        "login account. No changes were saved.",
                    )

    else:
        form = StudentForm()

    mentor_options = {}

    for department in Department.objects.all():
        mentors = Mentor.objects.filter(
            department=department
        ).order_by("employee_id")

        mentor_options[str(department.pk)] = [
            {
                "id": mentor.pk,
                "label": str(mentor),
            }
            for mentor in mentors
        ]

    context = {
        "form": form,
        "page_title": "Add Student",
        "submit_text": "Add Student",
        "mentor_options": mentor_options,
    }

    return render(
        request,
        "admin/students/student_form.html",
        context,
    )



@role_required("ADMIN")
def student_detail(request, student_id):

    student = get_object_or_404(
        Student.objects.select_related(
            "department",
            "mentor",
        ),
        id=student_id
    )

    context = {
        "student": student,
    }

    return render(
        request,
        "admin/students/student_detail.html",
        context
    )



@role_required("ADMIN")
def student_update(request, student_id):
    student = get_object_or_404(
        Student,
        id=student_id,
    )

    if request.method == "POST":
        form = StudentForm(
            request.POST,
            instance=student,
        )

        if form.is_valid():
            new_student_id = form.cleaned_data["student_id"]

            conflicting_users = User.objects.filter(
                username=new_student_id,
            )

            if student.user_id:
                conflicting_users = conflicting_users.exclude(
                    pk=student.user_id,
                )

            candidate_user = None
            unsafe_collision = False
            if not student.user_id:
                candidate_user = conflicting_users.first()

            if candidate_user:
                try:
                    candidate_profile = candidate_user.profile
                except UserProfile.DoesNotExist:
                    candidate_profile = None

                identity_matches = (
                    candidate_user.first_name.strip().casefold()
                    == form.cleaned_data["first_name"].strip().casefold()
                    and candidate_user.last_name.strip().casefold()
                    == form.cleaned_data["last_name"].strip().casefold()
                    and bool(candidate_user.email.strip())
                    and candidate_user.email.strip().casefold()
                    == form.cleaned_data["email"].strip().casefold()
                )
                if (
                    not candidate_profile
                    or candidate_profile.role != "STUDENT"
                    or hasattr(candidate_user, "student_record")
                    or not identity_matches
                ):
                    form.add_error(
                        "student_id",
                        "A login account already uses this Student ID, but its "
                        "Student role or identity cannot be safely verified. "
                        "Have an administrator resolve the account and profile "
                        "before linking it.",
                    )
                    candidate_user = None
                    unsafe_collision = True

            if unsafe_collision:
                pass
            elif conflicting_users.exists() and student.user_id and conflicting_users.first().pk != student.user_id:
                form.add_error("student_id", "This Student ID is already used by another login account.")
            else:
                try:
                    with transaction.atomic():
                        updated_student = form.save(commit=False)

                        linked_user = updated_student.user or candidate_user
                        new_password = form.cleaned_data.get("student_password")

                        if linked_user is None and new_password:
                            linked_user = User.objects.create_user(
                                username=new_student_id,
                                password=new_password,
                                first_name=updated_student.first_name,
                                last_name=updated_student.last_name,
                                email=updated_student.email,
                            )

                            profile, created = UserProfile.objects.get_or_create(
                                user=linked_user,
                                defaults={"role": "STUDENT"},
                            )

                            if profile.role != "STUDENT":
                                raise ValidationError(
                                    "The account has an unexpected application role."
                                )

                        if linked_user is not None:
                            try:
                                profile = linked_user.profile
                            except UserProfile.DoesNotExist:
                                profile = None
                            if not profile or profile.role != "STUDENT":
                                raise ValidationError(
                                    "This account does not have the STUDENT application role. "
                                    "An administrator must resolve its role before linking."
                                )
                            linked_user.username = new_student_id
                            linked_user.first_name = updated_student.first_name
                            linked_user.last_name = updated_student.last_name
                            linked_user.email = updated_student.email

                            update_fields = [
                                "username",
                                "first_name",
                                "last_name",
                                "email",
                            ]

                            if new_password:
                                linked_user.set_password(new_password)
                                update_fields.append("password")

                            linked_user.save(update_fields=update_fields)
                            updated_student.user = linked_user


                        updated_student.save()
                        form.save_m2m()

                    messages.success(
                        request,
                        "Student information updated successfully.",
                    )

                    return redirect(
                        "student_detail",
                        student_id=student.id,
                    )

                except ValidationError as exc:
                    form.add_error(None, exc)
                except IntegrityError:
                    form.add_error(
                        "student_id",
                        "This Student ID conflicts with an existing "
                        "record or login account. No changes were saved.",
                    )

    else:
        form = StudentForm(instance=student)

    mentor_options = {}

    for department in Department.objects.all():
        mentors = Mentor.objects.filter(
            department=department,
        ).order_by("employee_id")

        mentor_options[str(department.pk)] = [
            {
                "id": mentor.pk,
                "label": str(mentor),
            }
            for mentor in mentors
        ]

    context = {
        "form": form,
        "student": student,
        "page_title": "Edit Student",
        "submit_text": "Update Student",
        "mentor_options": mentor_options,
    }

    return render(
        request,
        "admin/students/student_form.html",
        context,
    )


@role_required("ADMIN")
def student_delete(request, student_id):

    student = get_object_or_404(
        Student,
        id=student_id
    )

    if request.method == "POST":

        student.delete()

        messages.success(
            request,
            "Student deleted successfully."
        )

        return redirect("student_list")

    context = {
        "student": student,
    }

    return render(
        request,
        "admin/students/student_confirm_delete.html",
        context
    )


# ============================================================
# MENTOR - TRACK STUDENT SUPPORT FOLLOW-UPS
# ============================================================

@role_required("MENTOR")
def mentor_track_follow_ups(request):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )
        return redirect("mentor_dashboard")

    today = date.today()

    # Retrieve follow-ups assigned to the logged-in mentor.
    follow_ups = (
        StudentSupportFollowUp.objects.filter(
            referral__mentor=mentor
        )
        .select_related(
            "referral",
            "referral__student",
            "referral__teacher",
            "referral__mentor",
        )
    )

    # Read filter parameters.
    selected_status = request.GET.get("status", "").strip()
    selected_student = request.GET.get("student", "").strip()
    selected_date = request.GET.get("date", "").strip()

    # Apply status filter.
    if selected_status == "Overdue":
        follow_ups = follow_ups.filter(
            status="Pending",
            scheduled_date__lt=today,
        )
    elif selected_status in ["Pending", "Completed"]:
        follow_ups = follow_ups.filter(
            status=selected_status
        )

    # Apply student filter.
    if selected_student.isdigit():
        follow_ups = follow_ups.filter(
            referral__student_id=int(selected_student)
        )

    # Apply scheduled-date filter.
    if selected_date:
        follow_ups = follow_ups.filter(
            scheduled_date=selected_date
        )

    # Calculate summary counts for all follow-ups
    # assigned to this mentor, independent of filters.
    mentor_follow_ups = StudentSupportFollowUp.objects.filter(
        referral__mentor=mentor
    )

    pending_count = mentor_follow_ups.filter(
        status="Pending"
    ).count()

    completed_count = mentor_follow_ups.filter(
        status="Completed"
    ).count()

    overdue_count = mentor_follow_ups.filter(
        status="Pending",
        scheduled_date__lt=today,
    ).count()

    upcoming_count = mentor_follow_ups.filter(
        status="Pending",
        scheduled_date__gte=today,
    ).count()

    # Retrieve students who have follow-up records
    # under referrals assigned to this mentor.
    students = (
        Student.objects.filter(
            support_referrals__mentor=mentor,
            support_referrals__follow_ups__isnull=False,
        )
        .distinct()
        .order_by("first_name", "last_name")
    )

    context = {
        "follow_ups": follow_ups.order_by(
            "scheduled_date",
            "-created_at",
        ),
        "students": students,
        "selected_status": selected_status,
        "selected_student": selected_student,
        "selected_date": selected_date,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "overdue_count": overdue_count,
        "upcoming_count": upcoming_count,
        "today": today,
    }

    return render(
        request,
        "mentor/track_follow_ups.html",
        context,
    )



@role_required("MENTOR")
def mentor_schedule_follow_up(request, support_id):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )
        return redirect("mentor_dashboard")

    referral = get_object_or_404(
        StudentSupport.objects.select_related("student", "mentor"),
        pk=support_id,
        mentor=mentor,
    )

    if request.method == "POST":
        form = StudentSupportFollowUpForm(request.POST)

        if form.is_valid():
            follow_up = form.save(commit=False)
            follow_up.referral = referral
            follow_up.status = "Pending"
            follow_up.save()

            # Update the parent referral status automatically.
            referral.status = "Follow-up Required"
            referral.save()

            messages.success(
                request,
                "Follow-up scheduled successfully. "
                "Referral status updated to Follow-up Required."
            )
            return redirect("mentor_track_follow_ups")
    else:
        form = StudentSupportFollowUpForm()

    context = {
        "form": form,
        "referral": referral,
    }

    return render(
        request,
        "mentor/schedule_follow_up.html",
        context,
    )


@role_required("MENTOR")
def mentor_follow_up_detail(request, follow_up_id):
    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )
        return redirect("mentor_dashboard")

    follow_up = get_object_or_404(
        StudentSupportFollowUp.objects.select_related(
            "referral",
            "referral__student",
            "referral__teacher",
            "referral__mentor",
        ),
        pk=follow_up_id,
        referral__mentor=mentor,
    )

    return render(
    request,
    "mentor/follow_up_detail.html",
    {
        "follow_up": follow_up,
        "today": date.today(),
    },
)



@role_required("MENTOR")
def mentor_complete_follow_up(request, follow_up_id):
    if request.method != "POST":
        return redirect("mentor_track_follow_ups")

    try:
        mentor = Mentor.objects.get(user=request.user)
    except Mentor.DoesNotExist:
        messages.error(
            request,
            "Your mentor profile has not been created yet."
        )
        return redirect("mentor_dashboard")

    follow_up = get_object_or_404(
        StudentSupportFollowUp.objects.select_related("referral"),
        pk=follow_up_id,
        referral__mentor=mentor,
    )

    if follow_up.status == "Completed":
        messages.warning(
            request,
            "This follow-up has already been completed."
        )
        return redirect(
            "mentor_follow_up_detail",
            follow_up_id=follow_up.pk,
        )

    form = CompleteStudentSupportFollowUpForm(
        request.POST,
        instance=follow_up,
    )

    if form.is_valid():
        completed_follow_up = form.save(commit=False)
        completed_follow_up.status = "Completed"
        completed_follow_up.save()

        # Automatically complete the associated referral.
        referral = completed_follow_up.referral
        referral.status = "Completed"
        referral.save()

        messages.success(
            request,
            "Follow-up completed successfully. "
            "The associated referral status is now Completed."
        )
    else:
        messages.error(
            request,
            "Please provide both follow-up notes and an outcome."
        )

    return redirect(
        "mentor_follow_up_detail",
        follow_up_id=follow_up.pk,
    )


# ============================================================
# ADMINISTRATOR - REPORTS & ANALYTICS
# ============================================================

@role_required("ADMIN")
def admin_reports(request):
    """
    Render dedicated Reports & Analytics dashboard page for administrators.
    """
    filter_options = get_filter_options()
    context = {
        "departments": filter_options["departments"],
        "courses": filter_options["courses"],
        "semesters": filter_options["semesters"],
    }
    return render(
        request,
        "admin/reports.html",
        context,
    )


@role_required("ADMIN")
def admin_reports_data(request):
    """
    Provide JSON analytics data for dynamic dashboard filtering and Chart.js.
    """
    department_id = request.GET.get("department")
    course = request.GET.get("course")
    semester = request.GET.get("semester")

    report_data = build_full_report_data(
        department_id=department_id,
        course=course,
        semester=semester,
    )

    return JsonResponse(report_data, safe=False)


@role_required("ADMIN")
def admin_reports_export_csv(request):
    """
    Export current aggregate report data as a downloadable CSV.
    Enforces active filters and formula-injection sanitization.
    """
    department_id = request.GET.get("department")
    course = request.GET.get("course")
    semester = request.GET.get("semester")

    report_data = build_full_report_data(
        department_id=department_id,
        course=course,
        semester=semester,
    )

    csv_content = generate_csv_report(report_data)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"student_dropout_risk_report_{timestamp}.csv"

    response = HttpResponse(
        csv_content,
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@role_required("ADMIN")
def admin_reports_export_excel(request):
    """
    Export current aggregate report data as a multi-sheet Excel (.xlsx) workbook.
    """
    department_id = request.GET.get("department")
    course = request.GET.get("course")
    semester = request.GET.get("semester")

    report_data = build_full_report_data(
        department_id=department_id,
        course=course,
        semester=semester,
    )

    try:
        excel_bytes = generate_excel_report(report_data)
    except RuntimeError as e:
        messages.error(request, str(e))
        return redirect("admin_reports")

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"student_dropout_risk_report_{timestamp}.xlsx"

    response = HttpResponse(
        excel_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
