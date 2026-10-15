from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("NONE", "None"),
        ("ADMIN", "Administrator"),
        ("TEACHER", "Teacher"),
        ("MENTOR", "Mentor"),
        ("STUDENT", "Student"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES
    )

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Mentor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    phone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Student(models.Model):
    GENDER_CHOICES = [
        ("Male", "Male"),
        ("Female", "Female"),
        ("Other", "Other"),
    ]

    student_id = models.CharField(max_length=50, unique=True)
    
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_record",
    )


    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True
    )

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)

    address = models.TextField(blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    course = models.CharField(max_length=100, blank=True)
    semester = models.PositiveIntegerField(null=True, blank=True)

    mentor = models.ForeignKey(
        Mentor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students"
    )

    admission_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student_id} - {self.first_name} {self.last_name}"


class Attendance(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="attendance_records"
    )

    date = models.DateField()

    classes_conducted = models.PositiveIntegerField(default=0)
    classes_attended = models.PositiveIntegerField(default=0)

    attendance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    entered_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.date}"


class AcademicPerformance(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="academic_records"
    )

    subject = models.CharField(max_length=100)

    internal_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    total_internal_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )

    entered_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.subject}"


class Assignment(models.Model):
    STATUS_CHOICES = [
        ("Submitted", "Submitted"),
        ("Pending", "Pending"),
        ("Late", "Late"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=100)

    submission_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending"
    )

    marks = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(20),
        ]
    )

    entered_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.title}"


class ExamResult(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="exam_results"
    )

    exam_name = models.CharField(max_length=100)
    subject = models.CharField(max_length=100)

    marks_obtained = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    total_marks = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100
    )

    exam_date = models.DateField(null=True, blank=True)

    entered_by = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.exam_name} - {self.subject}"


class RiskPrediction(models.Model):
    RISK_LEVEL_CHOICES = [
        ("Very Low", "Very Low"),
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
        ("Very High", "Very High"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="risk_predictions"
    )

    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    risk_level = models.CharField(
        max_length=20,
        choices=RISK_LEVEL_CHOICES
    )

    prediction_date = models.DateTimeField(
        auto_now_add=True
    )

    model_version = models.CharField(
        max_length=50,
        blank=True
    )

    is_alert_generated = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student} - {self.risk_level} ({self.risk_score})"


class Alert(models.Model):
    ALERT_LEVEL_CHOICES = [
        ("Medium", "Medium"),
        ("High", "High"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="alerts"
    )

    risk_prediction = models.ForeignKey(
        RiskPrediction,
        on_delete=models.CASCADE,
        related_name="alerts"
    )

    title = models.CharField(max_length=200)
    message = models.TextField()

    alert_level = models.CharField(
        max_length=20,
        choices=ALERT_LEVEL_CHOICES
    )

    is_read = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.title}"


class Intervention(models.Model):
    INTERVENTION_CHOICES = [
        ("Counseling", "Counseling"),
        ("Mentoring", "Mentoring"),
        ("Financial Assistance", "Financial Assistance"),
        ("Psychological Guidance", "Psychological Guidance"),
    ]

    STATUS_CHOICES = [
        ("Planned", "Planned"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Follow-up Required", "Follow-up Required"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="interventions"
    )

    mentor = models.ForeignKey(
        Mentor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interventions"
    )

    intervention_type = models.CharField(
        max_length=50,
        choices=INTERVENTION_CHOICES
    )

    notes = models.TextField()

    intervention_date = models.DateField()

    follow_up_date = models.DateField(
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Planned"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.intervention_type}"


# ============================================================
# TEACHER - STUDENT SUPPORT REFERRALS
# ============================================================

class StudentSupport(models.Model):

    SUPPORT_TYPE_CHOICES = [
        ("Remedial teaching", "Remedial Teaching"),
        ("Doubt-clearing session", "Doubt-Clearing Session"),
        ("Assignment assistance", "Assignment Assistance"),
        ("Exam preparation", "Exam Preparation"),
        ("Attendance counselling", "Attendance Counselling"),
        ("Other academic support", "Other Academic Support"),
    ]

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Accepted", "Accepted"),
        ("In Progress", "In Progress"),
        ("Completed", "Completed"),
        ("Follow-up Required", "Follow-up Required"),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="support_referrals",
    )

    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_support_referrals",
    )

    mentor = models.ForeignKey(
        Mentor,
        on_delete=models.PROTECT,
        related_name="student_support_referrals",
    )

    support_type = models.CharField(
        max_length=50,
        choices=SUPPORT_TYPE_CHOICES,
    )

    reason = models.TextField()

    teacher_notes = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="Pending",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return (
            f"{self.student} - "
            f"{self.support_type} - "
            f"{self.status}"
        )


# ============================================================
# MENTOR - STUDENT SUPPORT FOLLOW-UP TRACKING
# ============================================================

class StudentSupportFollowUp(models.Model):

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
    ]

    referral = models.ForeignKey(
        StudentSupport,
        on_delete=models.CASCADE,
        related_name="follow_ups",
    )

    scheduled_date = models.DateField()

    notes = models.TextField(
        blank=True,
    )

    outcome = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="Pending",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["scheduled_date", "-created_at"]

    def __str__(self):
        return (
            f"{self.referral.student} - "
            f"Follow-up on {self.scheduled_date} - "
            f"{self.status}"
        )