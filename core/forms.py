from django import forms

from .models import Student


class StudentForm(forms.ModelForm):

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
        