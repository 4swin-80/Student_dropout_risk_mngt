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


# ============================================================
# ADMINISTRATOR - REPORTS & ANALYTICS TEST SUITE
# ============================================================

import io
import json
from datetime import date, timedelta
from decimal import Decimal
import openpyxl
from django.utils import timezone

from .models import (
    Attendance,
    AcademicPerformance,
    Assignment,
    ExamResult,
    RiskPrediction,
    Intervention,
    StudentSupportFollowUp,
)
from .reports_utils import (
    build_full_report_data,
    sanitize_csv_cell,
)


class AdminReportsAccessControlTests(TestCase):
    """
    Verify application-role authorization for all Reports & Analytics endpoints:
    - Page view: /admin/reports/
    - JSON API: /admin/reports/data/
    - CSV Export: /admin/reports/export/csv/
    - Excel Export: /admin/reports/export/excel/
    """

    def setUp(self):
        self.department = Department.objects.create(name="Computer Science")

        # Admin user (Application role: ADMIN)
        self.admin_user = User.objects.create_user(username="admin_user", password="password")
        UserProfile.objects.create(user=self.admin_user, role="ADMIN")

        # Teacher user (Application role: TEACHER)
        self.teacher_user = User.objects.create_user(username="teacher_user", password="password")
        UserProfile.objects.create(user=self.teacher_user, role="TEACHER")

        # Mentor user (Application role: MENTOR)
        self.mentor_user = User.objects.create_user(username="mentor_user", password="password")
        UserProfile.objects.create(user=self.mentor_user, role="MENTOR")

        # Superuser account (Explicitly restricted from application dashboards by policy)
        self.superuser = User.objects.create_superuser(username="super_user", password="password")
        UserProfile.objects.create(user=self.superuser, role="NONE")

        self.endpoints = [
            reverse("admin_reports"),
            reverse("admin_reports_data"),
            reverse("admin_reports_export_csv"),
            reverse("admin_reports_export_excel"),
        ]

    def test_unauthenticated_requests_redirect_to_login(self):
        for endpoint in self.endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("login")))

    def test_teacher_denied_access_to_all_endpoints(self):
        self.client.login(username="teacher_user", password="password")
        for endpoint in self.endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("login")))

    def test_mentor_denied_access_to_all_endpoints(self):
        self.client.login(username="mentor_user", password="password")
        for endpoint in self.endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("login")))

    def test_superuser_denied_access_by_application_dashboard_policy(self):
        self.client.login(username="super_user", password="password")
        for endpoint in self.endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse("login")))

    def test_admin_granted_access_to_all_endpoints(self):
        self.client.login(username="admin_user", password="password")
        for endpoint in self.endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200)


class AdminReportsFilterAndMetricsTests(TestCase):
    """
    Verify filtering logic and metric calculations:
    - Latest prediction per student without double-counting
    - Accurate unpredicted student tracking
    - Non-zero class attendance aggregation
    - 20-mark scale assignments with null marks handling
    - Overdue follow-up scheduling logic
    - Zero-denominator safety
    """

    def setUp(self):
        self.dep_cs = Department.objects.create(name="Computer Science")
        self.dep_ee = Department.objects.create(name="Electrical Engineering")

        self.teacher_user = User.objects.create_user(username="t_user", password="password")
        UserProfile.objects.create(user=self.teacher_user, role="TEACHER")
        self.teacher = Teacher.objects.create(user=self.teacher_user, employee_id="T10", department=self.dep_cs)

        self.mentor_user = User.objects.create_user(username="m_user", password="password")
        UserProfile.objects.create(user=self.mentor_user, role="MENTOR")
        self.mentor = Mentor.objects.create(user=self.mentor_user, employee_id="M10", department=self.dep_cs)

        # Student 1: CS, BCA, Sem 1
        self.s1 = Student.objects.create(
            student_id="CS01",
            first_name="Alice",
            last_name="Smith",
            department=self.dep_cs,
            course="BCA",
            semester=1,
            mentor=self.mentor,
        )

        # Student 2: CS, BCA, Sem 2
        self.s2 = Student.objects.create(
            student_id="CS02",
            first_name="Bob",
            last_name="Jones",
            department=self.dep_cs,
            course="BCA",
            semester=2,
            mentor=self.mentor,
        )

        # Student 3: EE, B.Tech, Sem 1 (Unpredicted)
        self.s3 = Student.objects.create(
            student_id="EE01",
            first_name="Charlie",
            last_name="Brown",
            department=self.dep_ee,
            course="B.Tech",
            semester=1,
            mentor=self.mentor,
        )

        # Risk Predictions:
        # S1 has an older Low prediction and a newer High prediction
        RiskPrediction.objects.create(
            student=self.s1,
            risk_score=Decimal("35.00"),
            risk_level="Low",
        )
        RiskPrediction.objects.create(
            student=self.s1,
            risk_score=Decimal("75.00"),
            risk_level="High",
        )
        # S2 has one Very High prediction
        RiskPrediction.objects.create(
            student=self.s2,
            risk_score=Decimal("85.00"),
            risk_level="Very High",
        )
        # S3 has NO prediction

        # Attendance:
        # S1: 10 attended / 10 conducted = 100%
        Attendance.objects.create(
            student=self.s1,
            date=date.today(),
            classes_conducted=10,
            classes_attended=10,
        )
        # S2: 6 attended / 10 conducted = 60%
        Attendance.objects.create(
            student=self.s2,
            date=date.today(),
            classes_conducted=10,
            classes_attended=6,
        )

        # Academic:
        AcademicPerformance.objects.create(
            student=self.s1,
            subject="Python",
            internal_marks=Decimal("80.00"),
            total_internal_marks=Decimal("100.00"),
        )
        ExamResult.objects.create(
            student=self.s1,
            exam_name="Midterm",
            subject="Python",
            marks_obtained=Decimal("70.00"),
            total_marks=Decimal("100.00"),
        )

        # Assignments:
        # One graded out of 20, one pending with marks=None
        Assignment.objects.create(
            student=self.s1,
            title="Lab 1",
            subject="Python",
            status="Submitted",
            marks=Decimal("18.00"),
        )
        Assignment.objects.create(
            student=self.s2,
            title="Lab 2",
            subject="Python",
            status="Pending",
            marks=None,
        )

        # Interventions:
        Intervention.objects.create(
            student=self.s1,
            mentor=self.mentor,
            intervention_type="Counseling",
            status="In Progress",
            intervention_date=date.today(),
            notes="Regular counseling",
        )

        # Referrals & Follow-ups:
        self.referral = StudentSupport.objects.create(
            student=self.s1,
            teacher=self.teacher,
            mentor=self.mentor,
            support_type="Remedial teaching",
            reason="Low quiz score",
            status="In Progress",
        )
        # Overdue follow-up (scheduled date in past, status=Pending)
        StudentSupportFollowUp.objects.create(
            referral=self.referral,
            scheduled_date=date.today() - timedelta(days=3),
            status="Pending",
        )
        # Completed follow-up
        StudentSupportFollowUp.objects.create(
            referral=self.referral,
            scheduled_date=date.today() - timedelta(days=1),
            status="Completed",
        )

    def test_current_risk_deduplication_and_unpredicted(self):
        data = build_full_report_data()
        summary = data["summary"]
        risk_dist = data["risk_distribution"]

        # Total distinct students
        self.assertEqual(summary["total_students"], 3)
        # S1 must only be counted once (latest: High); S2 is Very High
        self.assertEqual(summary["high_risk_count"], 1)
        self.assertEqual(summary["very_high_risk_count"], 1)
        self.assertEqual(summary["high_or_very_high_count"], 2)

        # S3 has no prediction, so unpredicted count is 1, not Very Low
        self.assertEqual(risk_dist["No Prediction"], 1)
        self.assertEqual(risk_dist["High"], 1)
        self.assertEqual(risk_dist["Very High"], 1)
        self.assertEqual(risk_dist["Low"], 0)  # S1's older Low prediction is superseded

        # Average risk score of predicted students: (75 + 85) / 2 = 80.0
        self.assertEqual(summary["average_risk_score"], 80.0)

    def test_filter_by_department(self):
        data = build_full_report_data(department_id=self.dep_cs.id)
        self.assertEqual(data["summary"]["total_students"], 2)
        self.assertEqual(data["filters"]["active"]["department_id"], self.dep_cs.id)

    def test_filter_by_course_and_semester(self):
        data = build_full_report_data(
            department_id=self.dep_cs.id,
            course="BCA",
            semester=1,
        )
        self.assertEqual(data["summary"]["total_students"], 1)
        self.assertEqual(data["summary"]["high_risk_count"], 1)

    def test_attendance_aggregation_formula(self):
        data = build_full_report_data(department_id=self.dep_cs.id)
        # Total conducted: 10 + 10 = 20, attended: 10 + 6 = 16 => 80.0%
        att = data["attendance"]
        self.assertEqual(att["total_conducted"], 20)
        self.assertEqual(att["total_attended"], 16)
        self.assertEqual(att["overall_percentage"], 80.0)

    def test_assignment_statistics_respect_20_mark_scale(self):
        data = build_full_report_data()
        acad = data["academics"]
        self.assertEqual(acad["assignment_total_count"], 2)
        self.assertEqual(acad["assignment_graded_count"], 1)
        self.assertEqual(acad["assignment_average_marks_20"], 18.0)
        self.assertEqual(acad["assignment_status"]["Submitted"], 1)
        self.assertEqual(acad["assignment_status"]["Pending"], 1)

    def test_overdue_follow_up_detection(self):
        data = build_full_report_data()
        supp = data["support_and_follow_ups"]
        self.assertEqual(supp["total_follow_ups"], 2)
        self.assertEqual(supp["completed_follow_ups"], 1)
        self.assertEqual(supp["pending_follow_ups"], 1)
        self.assertEqual(supp["overdue_follow_ups"], 1)

    def test_zero_denominator_safe_handling(self):
        dep_empty = Department.objects.create(name="Empty Dept")
        s_new = Student.objects.create(
            student_id="NEW01",
            first_name="Eve",
            department=dep_empty,
        )
        Attendance.objects.create(
            student=s_new,
            date=date.today(),
            classes_conducted=0,
            classes_attended=0,
        )
        data = build_full_report_data(department_id=dep_empty.id)
        # Should cleanly return None, not crash or 0
        self.assertIsNone(data["summary"]["average_attendance_percentage"])
        self.assertIsNone(data["attendance"]["overall_percentage"])


class AdminReportsExportTests(TestCase):
    """
    Verify CSV and Excel export formats, privacy restrictions, and formula sanitization.
    """

    def setUp(self):
        self.admin_user = User.objects.create_user(username="admin_exporter", password="password")
        UserProfile.objects.create(user=self.admin_user, role="ADMIN")
        self.client.login(username="admin_exporter", password="password")

        self.dep = Department.objects.create(name="Data Science")
        self.student = Student.objects.create(
            student_id="SECURE01",
            first_name="ConfidentialFirst",
            last_name="ConfidentialLast",
            email="confidential@example.com",
            phone="9998887777",
            department=self.dep,
        )
        RiskPrediction.objects.create(
            student=self.student,
            risk_score=Decimal("65.00"),
            risk_level="High",
        )

    def test_csv_export_structure_and_privacy(self):
        response = self.client.get(reverse("admin_reports_export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue("text/csv" in response["Content-Type"])
        self.assertTrue("attachment" in response["Content-Disposition"])

        content = response.content.decode("utf-8")
        # Check headings
        self.assertIn("EXECUTIVE SUMMARY", content)
        self.assertIn("CURRENT RISK DISTRIBUTION", content)
        self.assertIn("DEPARTMENT COMPARISONS", content)

        # Privacy verification: No individual student identifiers must leak in export
        self.assertNotIn("SECURE01", content)
        self.assertNotIn("ConfidentialFirst", content)
        self.assertNotIn("ConfidentialLast", content)
        self.assertNotIn("confidential@example.com", content)
        self.assertNotIn("9998887777", content)

    def test_csv_formula_injection_sanitization(self):
        self.assertEqual(sanitize_csv_cell("=SUM(A1:A10)"), "'=SUM(A1:A10)")
        self.assertEqual(sanitize_csv_cell("+12345"), "'+12345")
        self.assertEqual(sanitize_csv_cell("-CmdPrompt"), "'-CmdPrompt")
        self.assertEqual(sanitize_csv_cell("@ExternalLink"), "'@ExternalLink")
        self.assertEqual(sanitize_csv_cell("Normal Text"), "Normal Text")

    def test_excel_export_structure_and_sheets(self):
        response = self.client.get(reverse("admin_reports_export_excel"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue("openxmlformats" in response["Content-Type"])

        # Load workbook from response bytes
        wb = openpyxl.load_workbook(io.BytesIO(response.content))
        expected_sheets = [
            "Overview",
            "Risk Analytics",
            "Attendance & Academics",
            "Assignments",
            "Interventions & Follow-ups",
            "Department Comparisons",
        ]
        self.assertEqual(wb.sheetnames, expected_sheets)

        # Verify no individual student identifiers in any sheet
        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            for row in ws.iter_rows(values_only=True):
                for cell_val in row:
                    val_str = str(cell_val or "")
                    self.assertNotIn("SECURE01", val_str)
                    self.assertNotIn("ConfidentialFirst", val_str)
                    self.assertNotIn("ConfidentialLast", val_str)

