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
]