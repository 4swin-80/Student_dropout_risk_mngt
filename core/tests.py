from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import (
    Department,
    Mentor,
    Student,
    StudentSupport,
    Teacher,
    UserProfile,
)


class TeacherStudentSupportReferralTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="Computer Science",
        )

        self.teacher_user = User.objects.create_user(
            username="teacher",
            password="password",
        )
        UserProfile.objects.create(
            user=self.teacher_user,
            role="TEACHER",
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id="T001",
            department=self.department,
        )

        self.mentor_user = User.objects.create_user(
            username="mentor",
            password="password",
        )
        UserProfile.objects.create(
            user=self.mentor_user,
            role="MENTOR",
        )
        self.mentor = Mentor.objects.create(
            user=self.mentor_user,
            employee_id="M001",
            department=self.department,
        )

        self.student = Student.objects.create(
            student_id="S001",
            first_name="Asha",
            last_name="Kumar",
            department=self.department,
        )

        StudentSupport.objects.create(
            student=self.student,
            teacher=self.teacher,
            mentor=self.mentor,
            support_type="Remedial teaching",
            reason="Existing active referral",
            status="Pending",
        )

    def test_duplicate_referral_warning_stays_on_student_report(self):
        self.client.login(
            username="teacher",
            password="password",
        )

        response = self.client.get(
            reverse(
                "teacher_refer_student_to_mentor",
                kwargs={"student_id": self.student.pk},
            ),
            follow=True,
        )

        self.assertRedirects(
            response,
            reverse(
                "teacher_student_support_report",
                kwargs={"student_id": self.student.pk},
            ),
        )
        self.assertTemplateUsed(
            response,
            "teacher/student_support_report.html",
        )
        self.assertContains(
            response,
            "This student already has an active support referral.",
        )
        self.assertEqual(
            StudentSupport.objects.filter(student=self.student).count(),
            1,
        )
