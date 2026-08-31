from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from .models import UserProfile


def home(request):
    """
    Common entry point.

    If user is authenticated, send them to their
    appropriate dashboard.
    Otherwise show login page.
    """

    if request.user.is_authenticated:
        return redirect("dashboard_redirect")

    return redirect("login")


def login_view(request):

    if request.user.is_authenticated:
        return redirect("dashboard_redirect")

    if request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect("dashboard_redirect")

        messages.error(
            request,
            "Invalid username or password."
        )

    return render(
        request,
        "accounts/login.html"
    )


def register_view(request):

    if request.user.is_authenticated:
        return redirect("dashboard_redirect")

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        role = request.POST.get("role")

        # -------------------------
        # Basic validation
        # -------------------------

        if not username or not password:
            messages.error(
                request,
                "Username and password are required."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # -------------------------
        # Password validation
        # -------------------------

        if password != confirm_password:
            messages.error(
                request,
                "Passwords do not match."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # -------------------------
        # Username validation
        # -------------------------

        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                "Username already exists."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # -------------------------
        # SECURITY:
        # Only Teacher and Mentor
        # can register publicly.
        # -------------------------

        if role not in ["TEACHER", "MENTOR"]:

            messages.error(
                request,
                "Public registration is available only for Teachers and Mentors."
            )

            return render(
                request,
                "accounts/register.html"
            )

        # -------------------------
        # Create User
        # -------------------------

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # -------------------------
        # Create UserProfile
        # -------------------------

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


@login_required
def dashboard_redirect(request):

    # Django superuser = Administrator
    if request.user.is_superuser:
        return redirect("admin_dashboard")

    try:
        role = request.user.profile.role

    except UserProfile.DoesNotExist:

        messages.error(
            request,
            "User role is not configured."
        )

        logout(request)

        return redirect("login")

    if role == "ADMIN":
        return redirect("admin_dashboard")

    elif role == "TEACHER":
        return redirect("teacher_dashboard")

    elif role == "MENTOR":
        return redirect("mentor_dashboard")

    messages.error(
        request,
        "Invalid user role."
    )

    logout(request)

    return redirect("login")


@login_required
def admin_dashboard(request):

    if not (
        request.user.is_superuser
        or request.user.profile.role == "ADMIN"
    ):
        messages.error(
            request,
            "You are not authorized to access this dashboard."
        )

        return redirect("dashboard_redirect")

    return render(
        request,
        "admin/admin_dashboard.html"
    )


@login_required
def teacher_dashboard(request):

    if request.user.profile.role != "TEACHER":
        messages.error(
            request,
            "You are not authorized to access this dashboard."
        )

        return redirect("dashboard_redirect")

    return render(
        request,
        "teacher/teacher_dashboard.html"
    )


@login_required
def mentor_dashboard(request):

    if request.user.profile.role != "MENTOR":
        messages.error(
            request,
            "You are not authorized to access this dashboard."
        )

        return redirect("dashboard_redirect")

    return render(
        request,
        "mentor/mentor_dashboard.html"
    )


@login_required
def logout_view(request):

    logout(request)

    messages.success(
        request,
        "You have been logged out successfully."
    )

    return redirect("login")
