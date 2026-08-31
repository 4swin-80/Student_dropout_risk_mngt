from django.urls import path
from . import views

urlpatterns = [
    path('', views.test, name='home'),
    path('test/', views.test, name='test'),
]
