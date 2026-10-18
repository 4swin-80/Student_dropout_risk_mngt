# Student Dropout Risk Management System

A Django web application for recording student attendance and academic activity, identifying students who may need support, and coordinating follow-up between administrators, teachers, mentors, and students.

## Features

- Role-based accounts and dashboards for administrators, teachers, mentors, and students.
- Student, department, teacher, and mentor records.
- Attendance, academic performance, assignments, and examination result tracking.
- Risk scores and alerts based on student records.
- Student support referrals, mentor follow-ups, and notifications.
- Administrative reports and downloadable data exports.

## Requirements

- Python 3.10 or newer
- pip
- Git (to clone or push the project)

## Local setup

Run these commands from the directory containing `manage.py` (`student_mngt/`):

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The development server is available at <http://127.0.0.1:8000/>. The Django administration site is at <http://127.0.0.1:8000/django-admin/>.

The app reads variables from `.env` when present, or from the process environment. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, and `DJANGO_ALLOWED_HOSTS` before deployment. Keep `DJANGO_DEBUG` disabled in production and use a private, randomly generated secret key. `.env` files, the SQLite database, and uploaded media are excluded from Git.

The project uses SQLite by default. Migrations create the application tables in the local database.

## GitHub

The project repository is intended for:

<https://github.com/4swin-80/Student_dropout_risk_mngt>

After reviewing the changes, commit and push the `main` branch with:

```cmd
git add .
git commit -m "Prepare student dropout risk management project"
git push -u origin main
```

## Project layout

```text
student_mngt/
|-- core/                 # Models, views, forms, migrations, templates, and static assets
|-- student_mngt/         # Django project configuration
|-- manage.py
|-- requirements.txt
`-- README.md
```
