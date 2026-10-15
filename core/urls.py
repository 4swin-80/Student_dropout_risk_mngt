from django.urls import path

from . import views


urlpatterns = [

    # Common
    path("", views.home, name="home"),

    # Authentication
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # Dashboard redirect
    path(
        "dashboard/",
        views.dashboard_redirect,
        name="dashboard_redirect"
    ),

    # Role dashboards
    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin_dashboard"
    ),

    path(
        "teacher-dashboard/",
        views.teacher_dashboard,
        name="teacher_dashboard"
    ),

    path(
        "mentor-dashboard/",
        views.mentor_dashboard,
        name="mentor_dashboard"
    ),

    # Student Management - Admin Only
path(
    "students/",
    views.student_list,
    name="student_list"
),

path(
    "students/add/",
    views.student_create,
    name="student_create"
),

path(
    "students/<int:student_id>/",
    views.student_detail,
    name="student_detail"
),

path(
    "students/<int:student_id>/edit/",
    views.student_update,
    name="student_update"
),

path(
    "students/<int:student_id>/delete/",
    views.student_delete,
    name="student_delete"
),

# ============================================================
# ADMIN - TEACHER MANAGEMENT
# ============================================================

path(
    "teachers/",
    views.teacher_list,
    name="teacher_list"
),

path(
    "teachers/add/",
    views.teacher_create,
    name="teacher_create"
),

path(
    "teachers/<int:teacher_id>/",
    views.teacher_detail,
    name="teacher_detail"
),

path(
    "teachers/<int:teacher_id>/edit/",
    views.teacher_update,
    name="teacher_update"
),

path(
    "teachers/<int:teacher_id>/delete/",
    views.teacher_delete,
    name="teacher_delete"
),

path(
    "teacher/attendance/",
    views.attendance_list,
    name="attendance_list",
),

path(
    "teacher/attendance/add/",
    views.attendance_create,
    name="attendance_create",
),

path(
    "teacher/academic-performance/",
    views.academic_performance_list,
    name="academic_performance_list",
),

path(
    "teacher/academic-performance/add/",
    views.academic_performance_create,
    name="academic_performance_create",
),

path(
    "teacher/assignments/add/",
    views.assignment_create,
    name="assignment_create"
),

path(
    "teacher/assignments/",
    views.assignment_list,
    name="assignment_list"
),

path(
    "teacher/students/",
    views.teacher_student_list,
    name="teacher_student_list"
),

path(
    "teacher/exam-results/add/",
    views.exam_result_create,
    name="exam_result_create"
),

path(
    "teacher/exam-results/",
    views.exam_result_list,
    name="exam_result_list"
),

path(
    "mentor/assigned-students/",
    views.mentor_assigned_students,
    name="mentor_assigned_students",
),


path(
    "mentor/student-support/",
    views.mentor_student_support,
    name="mentor_student_support",
),


path(
    "mentor/student-support/<int:support_id>/",
    views.mentor_review_student_support,
    name="mentor_review_student_support",
),


path(
    "mentor/student-support/<int:support_id>/update-status/",
    views.mentor_update_student_support_status,
    name="mentor_update_student_support_status",
),


path(
    "teacher/risk-scores/",
    views.teacher_risk_scores,
    name="teacher_risk_scores",
),

path(
    "teacher/alerts/",
    views.teacher_alerts,
    name="teacher_alerts",
),

path(
    "admin/alerts/",
    views.admin_alerts,
    name="admin_alerts",
),


path(
    "admin/risk-scores/",
    views.admin_risk_scores,
    name="admin_risk_scores",
),

path(
    "admin/reports/",
    views.admin_reports,
    name="admin_reports",
),

path(
    "admin/reports/data/",
    views.admin_reports_data,
    name="admin_reports_data",
),

path(
    "admin/reports/export/csv/",
    views.admin_reports_export_csv,
    name="admin_reports_export_csv",
),

path(
    "admin/reports/export/excel/",
    views.admin_reports_export_excel,
    name="admin_reports_export_excel",
),


path(
    "mentor/risk-scores/",
    views.mentor_risk_scores,
    name="mentor_risk_scores",
),


path(
    "teacher/student-support/",
    views.teacher_student_support,
    name="teacher_student_support",
),


path(
    "teacher/student-support/report/<int:student_id>/",
    views.teacher_student_support_report,
    name="teacher_student_support_report",
),

path(
    "teacher/student-support/refer/<int:student_id>/",
    views.teacher_refer_student_to_mentor,
    name="teacher_refer_student_to_mentor",
),


path(
    "mentor/alerts/",
    views.mentor_risk_alerts,
    name="mentor_risk_alerts",
),

path(
    "mentor/track-follow-ups/",
    views.mentor_track_follow_ups,
    name="mentor_track_follow_ups",
),
path(
    "mentor/track-follow-ups/schedule/<int:support_id>/",
    views.mentor_schedule_follow_up,
    name="mentor_schedule_follow_up",
),
path(
    "mentor/track-follow-ups/<int:follow_up_id>/",
    views.mentor_follow_up_detail,
    name="mentor_follow_up_detail",
),
path(
    "mentor/track-follow-ups/<int:follow_up_id>/complete/",
    views.mentor_complete_follow_up,
    name="mentor_complete_follow_up",
),


path(
    "teacher/generate-predictions/",
    views.teacher_generate_predictions,
    name="teacher_generate_predictions",
),

path(
    "student-dashboard/",
    views.student_dashboard,
    name="student_dashboard",
),

path(
    "student-profile/",
    views.student_profile,
    name="student_profile",
),


path("mentors/", views.mentor_list, name="mentor_list"),
path("mentors/add/", views.mentor_create, name="mentor_create"),
path("mentors/<int:mentor_id>/", views.mentor_detail, name="mentor_detail"),
path("mentors/<int:mentor_id>/edit/", views.mentor_update, name="mentor_update"),
path("mentors/<int:mentor_id>/delete/", views.mentor_delete, name="mentor_delete"),

path("departments/", views.department_list, name="department_list"),
path("departments/add/", views.department_create, name="department_create"),
path("departments/<int:department_id>/", views.department_detail, name="department_detail"),
path("departments/<int:department_id>/edit/", views.department_update, name="department_update"),
path("departments/<int:department_id>/delete/", views.department_delete, name="department_delete"),

]
