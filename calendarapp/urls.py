from django.urls import path
from .views import *

urlpatterns = [
    path("", HomeView.as_view(), name="home"),

    path('calendar/', CalendarView.as_view(), name="calendar"),

    path("api/tasks-for-day/", ApiTasksForDayView.as_view(), name="api_tasks_for_day"),
    path("api/create-task/", ApiCreateTaskView.as_view(), name="api_create_task"),
    path("api/update-task/<int:task_id>/", ApiUpdateTaskView.as_view(), name="api_update_task"),

    path("register/", RegisterView.as_view(), name="register"),

    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),

    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),

    path("login/", LoginView.as_view(), name="login"),

    path("logout/", LogoutView.as_view(), name="logout"),
]