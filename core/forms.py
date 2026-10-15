from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import (
    Student,
    Teacher,
    Mentor,
    Department,
    Attendance,
    AcademicPerformance,
    Assignment,
    ExamResult,
    StudentSupport,
    StudentSupportFollowUp,
)



class StudentForm(forms.ModelForm):
    student_password = forms.CharField(
        label="Student Login Password",
        required=False,
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter initial login password",
                "autocomplete": "new-password",
            }
        ),
        help_text=(
            "Required when creating a student account. "
            "Leave blank when editing an existing student."
        ),
    )

    class Meta:
        model = Student

        fields = [
            "student_id",
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "email",
            "phone",
            "address",
            "department",
            "course",
            "semester",
            "mentor",
            "admission_date",
        ]

        widgets = {
            "student_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter student ID",
                }
            ),
            "first_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter first name",
                }
            ),
            "last_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter last name",
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "gender": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter email address",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter phone number",
                }
            ),
            "address": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter address",
                    "rows": 3,
                }
            ),
            "department": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "course": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter course",
                }
            ),
            "semester": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter semester",
                    "min": "1",
                }
            ),
            "mentor": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "admission_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

        labels = {
            "student_id": "Student ID",
            "first_name": "First Name",
            "last_name": "Last Name",
            "date_of_birth": "Date of Birth",
            "gender": "Gender",
            "email": "Email Address",
            "phone": "Phone Number",
            "address": "Address",
            "department": "Department",
            "course": "Course",
            "semester": "Semester",
            "mentor": "Assigned Mentor",
            "admission_date": "Admission Date",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Password is required only when creating a new student.
        self.fields["student_password"].required = (
            not self.instance.pk
        )

        department_id = (
            self.data.get(self.add_prefix("department"))
            if self.is_bound
            else self.instance.department_id
        )

        mentor_field = self.fields["mentor"]
        mentor_field.queryset = Mentor.objects.none()
        mentor_field.required = False
        mentor_field.disabled = True

        if department_id:
            mentors = Mentor.objects.filter(
                department_id=department_id
            ).order_by("employee_id")

            mentor_field.queryset = mentors

            if mentors.count() == 1:
                mentor_field.initial = mentors.first().pk

    def clean_student_password(self):
        password = self.cleaned_data.get("student_password")

        if not self.instance.pk and not password:
            raise ValidationError(
                "Student login password is required."
            )

        if password:
            user = User(
                username=self.cleaned_data.get("student_id", ""),
                first_name=self.cleaned_data.get("first_name", ""),
                last_name=self.cleaned_data.get("last_name", ""),
                email=self.cleaned_data.get("email", ""),
            )

            validate_password(password, user=user)

        return password

    def clean(self):
        cleaned_data = super().clean()
        department = cleaned_data.get("department")

        if not department:
            cleaned_data["mentor"] = None
            return cleaned_data

        mentors = Mentor.objects.filter(
            department=department
        ).order_by("employee_id")

        mentor_count = mentors.count()

        if mentor_count == 0:
            self.add_error(
                "department",
                "No mentor is assigned to this department. "
                "Please assign a mentor before adding a student.",
            )
            cleaned_data["mentor"] = None

        elif mentor_count > 1:
            self.add_error(
                "department",
                "Multiple mentors are assigned to this department. "
                "Please ensure exactly one mentor is assigned "
                "before adding a student.",
            )
            cleaned_data["mentor"] = None

        else:
            cleaned_data["mentor"] = mentors.first()

        return cleaned_data

    def save(self, commit=True):
        student = super().save(commit=False)

        department = self.cleaned_data.get("department")

        if department:
            mentor = Mentor.objects.filter(
                department=department
            ).first()

            if mentor:
                student.mentor = mentor

        if commit:
            student.save()
            self.save_m2m()

        return student



class TeacherForm(forms.ModelForm):

    class Meta:
        model = Teacher

        fields = [
            "user",
            "employee_id",
            "department",
            "phone",
        ]

        widgets = {

            "user": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "employee_id": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter employee ID",
                }
            ),

            "department": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter phone number",
                }
            ),
        }

        labels = {
            "user": "Teacher Account",
            "employee_id": "Employee ID",
            "department": "Department",
            "phone": "Phone Number",
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # ----------------------------------------------------
        # Show only users whose application role is TEACHER
        # ----------------------------------------------------

        teacher_users = User.objects.filter(
            profile__role="TEACHER"
        ).filter(
            Q(teacher__isnull=True) |
            Q(pk=self.instance.user_id if self.instance.pk else None)
        ).distinct()

        self.fields["user"].queryset = teacher_users

        # ----------------------------------------------------
        # Display full name + username
        # ----------------------------------------------------

        self.fields["user"].label_from_instance = (
            lambda user:
            f"{user.get_full_name()} ({user.username})"
            if user.get_full_name()
            else user.username
        )

class MentorForm(forms.ModelForm):
    class Meta:
        model = Mentor
        fields = ["user", "employee_id", "department", "phone"]
        widgets = {
            "user": forms.Select(attrs={
                "class": "form-select"
            }),
            "employee_id": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter employee ID"
            }),
            "department": forms.Select(attrs={
                "class": "form-select"
            }),
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter phone number"
            }),
        }
        labels = {
            "user": "Mentor Account",
            "employee_id": "Employee ID",
            "department": "Department",
            "phone": "Phone Number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        mentor_users = User.objects.filter(
            profile__role="MENTOR"
        ).filter(
            Q(mentor__isnull=True) |
            Q(pk=self.instance.user_id if self.instance.pk else None)
        ).distinct()

        self.fields["user"].queryset = mentor_users

        self.fields["user"].label_from_instance = (
            lambda user:
            f"{user.get_full_name()} ({user.username})"
            if user.get_full_name()
            else user.username
        )

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter department name"
            }),
        }

        labels = {
            "name": "Department Name",
        }       


class AttendanceForm(forms.ModelForm):

    class Meta:
        model = Attendance

        fields = [
            "student",
            "date",
            "classes_conducted",
            "classes_attended",
        ]

        widgets = {

            "student": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "classes_conducted": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter classes conducted",
                    "min": "0",
                }
            ),

            "classes_attended": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter classes attended",
                    "min": "0",
                }
            ),
        }

        labels = {
            "student": "Student",
            "date": "Attendance Date",
            "classes_conducted": "Classes Conducted",
            "classes_attended": "Classes Attended",
        }

    def clean(self):
        cleaned_data = super().clean()

        classes_conducted = cleaned_data.get("classes_conducted")
        classes_attended = cleaned_data.get("classes_attended")

        if (
            classes_conducted is not None
            and classes_attended is not None
            and classes_attended > classes_conducted
        ):
            raise forms.ValidationError(
                "Classes attended cannot be greater than classes conducted."
            )

        return cleaned_data       


class AcademicPerformanceForm(forms.ModelForm):

    class Meta:
        model = AcademicPerformance

        fields = [
            "student",
            "subject",
            "internal_marks",
            "total_internal_marks",
        ]

        widgets = {

            "student": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter subject name",
                }
            ),

            "internal_marks": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter marks obtained",
                    "min": "0",
                    "step": "0.01",
                }
            ),

            "total_internal_marks": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter total marks",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),
        }

        labels = {
            "student": "Student",
            "subject": "Subject",
            "internal_marks": "Internal Marks",
            "total_internal_marks": "Total Internal Marks",
        }

    def clean(self):
        cleaned_data = super().clean()

        internal_marks = cleaned_data.get("internal_marks")
        total_internal_marks = cleaned_data.get(
            "total_internal_marks"
        )

        if (
            internal_marks is not None
            and total_internal_marks is not None
            and internal_marks > total_internal_marks
        ):
            raise forms.ValidationError(
                "Internal marks cannot be greater than total internal marks."
            )

        return cleaned_data 


class AssignmentForm(forms.ModelForm):

    class Meta:
        model = Assignment

        fields = [
            "student",
            "title",
            "subject",
            "submission_date",
            "status",
            "marks",
        ]

        widgets = {

            "student": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter assignment title",
                }
            ),

            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter subject name",
                }
            ),

            "submission_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "marks": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter marks out of 20",
                    "min": "0",
                    "max": "20",
                    "step": "0.01",
                }
            ),
        }

        labels = {
            "student": "Student",
            "title": "Assignment Title",
            "subject": "Subject",
            "submission_date": "Submission Date",
            "status": "Status",
            "marks": "Marks (Out of 20)",
        }

def clean(self):
    cleaned_data = super().clean()

    status = cleaned_data.get("status")
    marks = cleaned_data.get("marks")

    if marks is not None and marks > 20:
        raise forms.ValidationError(
            "Assignment marks cannot be greater than 20."
        )

    if status == "Submitted" and marks is None:
        raise forms.ValidationError(
            "Marks are required for a submitted assignment."
        )

    return cleaned_data   


class ExamResultForm(forms.ModelForm):

    class Meta:
        model = ExamResult

        fields = [
            "student",
            "exam_name",
            "subject",
            "marks_obtained",
            "total_marks",
            "exam_date",
        ]

        widgets = {

            "student": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),

            "exam_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter exam name",
                }
            ),

            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter subject name",
                }
            ),

            "marks_obtained": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter marks obtained",
                    "min": "0",
                    "step": "0.01",
                }
            ),

            "total_marks": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter total marks",
                    "min": "0.01",
                    "step": "0.01",
                }
            ),

            "exam_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

        labels = {
            "student": "Student",
            "exam_name": "Exam Name",
            "subject": "Subject",
            "marks_obtained": "Marks Obtained",
            "total_marks": "Total Marks",
            "exam_date": "Exam Date",
        }

    def clean(self):

        cleaned_data = super().clean()

        marks_obtained = cleaned_data.get("marks_obtained")
        total_marks = cleaned_data.get("total_marks")

        if (
            marks_obtained is not None
            and total_marks is not None
            and marks_obtained > total_marks
        ):
            raise forms.ValidationError(
                "Marks obtained cannot be greater than total marks."
            )

        return cleaned_data

# ============================================================
# TEACHER - REFER STUDENT TO MENTOR
# ============================================================

class StudentSupportForm(forms.ModelForm):

    class Meta:
        model = StudentSupport

        fields = [
            "support_type",
            "reason",
            "teacher_notes",
        ]

        widgets = {
            "support_type": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Explain why this student needs support."
                    ),
                }
            ),
            "teacher_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": (
                        "Add any additional notes for the mentor (optional)."
                    ),
                }
            ),
        }

        labels = {
            "support_type": "Type of Support",
            "reason": "Reason for Referral",
            "teacher_notes": "Additional Notes for Mentor",
        }

    def clean_reason(self):
        reason = self.cleaned_data.get("reason", "").strip()

        if not reason:
            raise forms.ValidationError(
                "Please provide a reason for referring this student."
            )

        return reason   


# ============================================================
# MENTOR - UPDATE STUDENT SUPPORT STATUS
# ============================================================

class MentorStudentSupportStatusForm(forms.ModelForm):

    class Meta:
        model = StudentSupport

        fields = [
            "status",
        ]

        widgets = {
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }

        labels = {
            "status": "Referral Status",
        }


class StudentSupportFollowUpForm(forms.ModelForm):
    class Meta:
        model = StudentSupportFollowUp
        fields = ["scheduled_date", "notes"]
        widgets = {
            "scheduled_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Enter follow-up notes (optional)",
                }
            ),
        }
        labels = {
            "scheduled_date": "Scheduled Follow-up Date",
            "notes": "Initial Notes",
        }

    def clean_scheduled_date(self):
        from datetime import date

        scheduled_date = self.cleaned_data["scheduled_date"]

        if scheduled_date < date.today():
            raise forms.ValidationError(
                "The scheduled follow-up date cannot be in the past."
            )

        return scheduled_date


class CompleteStudentSupportFollowUpForm(forms.ModelForm):
    class Meta:
        model = StudentSupportFollowUp
        fields = ["notes", "outcome"]
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe what was discussed or done",
                }
            ),
            "outcome": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Record the follow-up result or outcome",
                }
            ),
        }
        labels = {
            "notes": "Follow-up Notes",
            "outcome": "Outcome / Result",
        }

    def clean(self):
        cleaned_data = super().clean()

        notes = cleaned_data.get("notes", "").strip()
        outcome = cleaned_data.get("outcome", "").strip()

        if not notes:
            self.add_error(
                "notes",
                "Follow-up notes are required before completion.",
            )

        if not outcome:
            self.add_error(
                "outcome",
                "The follow-up outcome is required before completion.",
            )

        return cleaned_data