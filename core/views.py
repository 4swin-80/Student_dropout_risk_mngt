from django.contrib import messages
from decimal import Decimal
from functools import wraps
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import (
    redirect,
    render,
    get_object_or_404,
)

from .forms import *
from .models import *


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
                "Invalid username or password."
            )
            return render(
                request,
                "accounts/login.html"
            )

        # Check username + password only
        if not user.check_password(password):
            messages.error(
                request,
                "Invalid username or password."
            )
            return render(
                request,
                "accounts/login.html"
            )

        # Check UserProfile role only
        try:
            role = user.profile.role
        except UserProfile.DoesNotExist:
            messages.error(
                request,
                "Invalid username or password."
            )
            return render(
                request,
                "accounts/login.html"
            )

        # NONE = invalid login
        if role == "NONE":
            messages.error(
                request,
                "Invalid username or password."
            )
            return render(
                request,
                "accounts/login.html"
            )

        # Only these three roles can enter
        if role == "ADMIN":
            login(request, user)
            return redirect("admin_dashboard")

        elif role == "TEACHER":
            login(request, user)
            return redirect("teacher_dashboard")

        elif role == "MENTOR":
            login(request, user)
            return redirect("mentor_dashboard")

        # Any unexpected role
        messages.error(
            request,
            "Invalid username or password."
        )
        return render(
            request,
            "accounts/login.html"
        )

    return render(
        request,
        "accounts/login.html"
    )


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

            return redirect("attendance_create")

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

            return redirect(
                "academic_performance_create"
            )

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

            return redirect("assignment_create")

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

            form.save()

            messages.success(
                request,
                "Student added successfully."
            )

            return redirect("student_list")

    else:

        form = StudentForm()

    context = {
        "form": form,
        "page_title": "Add Student",
        "submit_text": "Add Student",
    }

    return render(
        request,
        "admin/students/student_form.html",
        context
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
        id=student_id
    )

    if request.method == "POST":

        form = StudentForm(
            request.POST,
            instance=student
        )

        if form.is_valid():

            form.save()

            messages.success(
                request,
                "Student information updated successfully."
            )

            return redirect(
                "student_detail",
                student_id=student.id
            )

    else:

        form = StudentForm(
            instance=student
        )

    context = {
        "form": form,
        "student": student,
        "page_title": "Edit Student",
        "submit_text": "Update Student",
    }

    return render(
        request,
        "admin/students/student_form.html",
        context
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