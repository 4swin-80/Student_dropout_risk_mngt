from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    UserProfile,
    Department,
    Teacher,
    Mentor,
    Student,
    Attendance,
    AcademicPerformance,
    Assignment,
    ExamResult,
    RiskPrediction,
    Alert,
    Intervention,
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "get_role",
        "is_staff",
    )
    list_select_related = ("profile",)

    @admin.display(description="Role")
    def get_role(self, obj):
        if hasattr(obj, "profile"):
            return obj.profile.get_role_display()
        return "-"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = (
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
    )


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "get_name", "department", "phone")
    search_fields = (
        "employee_id",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    list_filter = ("department",)

    @admin.display(description="Name")
    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "get_name", "department", "phone")
    search_fields = (
        "employee_id",
        "user__username",
        "user__first_name",
        "user__last_name",
    )
    list_filter = ("department",)

    @admin.display(description="Name")
    def get_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "student_id",
        "first_name",
        "last_name",
        "department",
        "course",
        "semester",
        "mentor",
    )

    search_fields = (
        "student_id",
        "first_name",
        "last_name",
        "email",
    )

    list_filter = (
        "gender",
        "department",
        "course",
        "semester",
    )

    ordering = ("student_id",)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "date",
        "classes_conducted",
        "classes_attended",
        "attendance_percentage",
        "entered_by",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
    )

    list_filter = (
        "date",
        "entered_by",
    )

    ordering = ("-date",)


@admin.register(AcademicPerformance)
class AcademicPerformanceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "subject",
        "internal_marks",
        "total_internal_marks",
        "entered_by",
        "created_at",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "subject",
    )

    list_filter = (
        "subject",
        "entered_by",
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "title",
        "subject",
        "status",
        "marks",
        "submission_date",
        "entered_by",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "title",
        "subject",
    )

    list_filter = (
        "status",
        "subject",
        "entered_by",
    )


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "exam_name",
        "subject",
        "marks_obtained",
        "total_marks",
        "exam_date",
        "entered_by",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "exam_name",
        "subject",
    )

    list_filter = (
        "exam_name",
        "subject",
        "exam_date",
        "entered_by",
    )


@admin.register(RiskPrediction)
class RiskPredictionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "risk_score",
        "risk_level",
        "prediction_date",
        "is_alert_generated",
        "model_version",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
    )

    list_filter = (
        "risk_level",
        "is_alert_generated",
        "prediction_date",
    )

    ordering = ("-prediction_date",)

    readonly_fields = (
        "prediction_date",
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "title",
        "alert_level",
        "is_read",
        "created_at",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "title",
        "message",
    )

    list_filter = (
        "alert_level",
        "is_read",
        "created_at",
    )

    ordering = ("-created_at",)


@admin.register(Intervention)
class InterventionAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "mentor",
        "intervention_type",
        "intervention_date",
        "follow_up_date",
        "status",
    )

    search_fields = (
        "student__student_id",
        "student__first_name",
        "student__last_name",
        "mentor__user__username",
        "notes",
    )

    list_filter = (
        "intervention_type",
        "status",
        "intervention_date",
    )

    ordering = ("-intervention_date",)
