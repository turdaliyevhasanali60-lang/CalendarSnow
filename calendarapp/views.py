from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.contrib import messages
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from datetime import date as dt_date
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import EmailOTP, Task
from .utils import generate_otp, send_otp_email # utils'dan funksiyalarni chaqirib olamiz


User = get_user_model()

class VerifiedLoginRequiredMixin:
    """Require authenticated + verified (is_active) users."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("home")
        if not request.user.is_active:
            return redirect("verify-email")
        return super().dispatch(request, *args, **kwargs)

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: make widgets play nicely with the glass UI
        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + "").strip()

class HomeView(View):
    def get(self, request):
        if request.user.is_authenticated and request.user.is_active:
            return render(request, "calendar.html")

        if request.user.is_authenticated and not request.user.is_active:
            return redirect("verify-email")

        # Google button should not crash the landing page when SocialApp is not configured yet
        try:
            site = Site.objects.get_current(request)
            google_enabled = SocialApp.objects.filter(provider="google", sites=site).exists()
        except Exception:
            google_enabled = False

        return render(request, "index-unauth.html", {"google_enabled": google_enabled})

# NEW: CalendarView
class CalendarView(VerifiedLoginRequiredMixin, View):
    login_url = "login"
    def get(self, request):
        return render(request, "calendar.html")

class LoginView(View):
    def get(self, request):
        # If already logged in and verified, go straight to calendar
        if request.user.is_authenticated and request.user.is_active:
            return redirect("calendar")

        return render(request, "login.html")

    def post(self, request):
        email = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        if not email or not password:
            return render(request, "login.html", {"error": "Email and password are required."})

        try:
            user_obj = User.objects.get(email__iexact=email)
            username = user_obj.username
        except User.DoesNotExist:
            return render(request, "login.html", {"error": "Invalid credentials."})

        user = authenticate(request, username=username, password=password)
        if not user:
            return render(request, "login.html", {"error": "Invalid credentials."})

        if not user.is_active:
            request.session["pending_email"] = user.email
            return redirect("verify-email")

        login(request, user)
        return redirect("calendar")

class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("/")  # index-unauth

    def post(self, request):
        logout(request)
        return redirect("/")

class RegisterView(View):
    def get(self, request):
        # If already logged in and verified, go straight to calendar
        if request.user.is_authenticated and request.user.is_active:
            return redirect("calendar")
        form = RegisterForm()
        return render(request, "register.html", {"form": form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if not form.is_valid():
            return render(request, "register.html", {"form": form})

        username = (form.cleaned_data.get("username") or "").strip()
        email = (form.cleaned_data.get("email") or "").strip()
        password1 = form.cleaned_data.get("password1")

        # Enforce unique email at app level
        if User.objects.filter(email__iexact=email).exists():
            form.add_error("email", "This email is already taken.")
            return render(request, "register.html", {"form": form})

        # Create inactive user
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.is_active = False
        user.save(update_fields=["is_active"])

        # Create / update OTP
        otp = generate_otp()
        EmailOTP.objects.update_or_create(
            user=user,
            defaults={
                "code": otp,
                "attempts": 0,
                "created_at": timezone.now(),
                "last_sent_at": timezone.now(),
            },
        )

        send_otp_email(to_email=user.email, otp=otp)
        request.session["pending_email"] = user.email
        return redirect("verify-email")


class VerifyEmailView(View):
    def get(self, request):
        email = request.session.get("pending_email")
        if not email:
            return render(request, "verify_email.html", {"error": "Session not found. Please register again."})

        # countdown uchun remaining seconds
        resend_remaining = 0
        try:
            user = User.objects.get(email__iexact=email)
            resend_remaining = user.email_otp.resend_remaining_seconds()
        except Exception:
            resend_remaining = 0

        return render(request, "verify_email.html", {"resend_remaining": resend_remaining})

    def post(self, request):
        otp = (request.POST.get("otp") or "").strip()
        email = request.session.get("pending_email")

        if not email:
            return render(request, "verify_email.html", {"error": "Session not found. Please register again."})

        if not otp:
            return render(request, "verify_email.html", {"error": "OTP code is required."})

        generic_error = "The code is invalid or expired."

        try:
            user = User.objects.get(email__iexact=email)
            record = user.email_otp
        except Exception:
            return render(request, "verify_email.html", {"error": generic_error})

        # eski kod?
        if record.is_expired():
            record.delete()
            return render(request, "verify_email.html", {"error": generic_error})

        # ko'p urunish?
        max_attempts = getattr(settings, "EMAIL_OTP_MAX_ATTEMPTS", 5)
        if record.attempts >= max_attempts:
            record.delete()
            return render(request, "verify_email.html", {"error": "Too many attempts. Please request a new code."})

        # noto'g'ri parol?
        if otp != record.code:
            record.attempts += 1
            record.save(update_fields=["attempts"])
            return render(request, "verify_email.html", {"error": generic_error})

        # ✅ SUCCESS
        user.is_active = True
        user.save(update_fields=["is_active"])
        record.delete()
        request.session.pop("pending_email", None)
        messages.success(request, "Email successfully verified! Please sign in.")
        return redirect("login")


class ResendOTPView(View):
    def post(self, request):
        email = request.session.get("pending_email")
        if not email:
            messages.error(request, "Session not found. Please register again.")
            return redirect("verify-email")

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            messages.success(request, "If the email exists, a new code has been sent.")
            return redirect("verify-email")

        if user.is_active:
            messages.success(request, "Email is already verified. Please sign in.")
            return redirect("login")

        record, _ = EmailOTP.objects.get_or_create(user=user)

        # cooldown
        if not record.can_resend():
            remaining = record.resend_remaining_seconds()
            messages.error(request, f"Please wait {remaining} seconds before requesting another code.")
            return redirect("verify-email")

        # Yangi OTP
        otp = generate_otp()
        record.code = otp
        record.attempts = 0
        record.created_at = timezone.now()
        record.last_sent_at = timezone.now()
        record.save()

        send_otp_email(to_email=user.email, otp=otp)

        messages.success(request, "A new verification code has been sent.")
        return redirect("verify-email")


def _parse_iso_date(value: str) -> dt_date | None:
    try:
        return dt_date.fromisoformat(value)
    except Exception:
        return None


@method_decorator([login_required, require_http_methods(["GET"])], name="dispatch")
class ApiTasksForDayView(View):
    """Return tasks ONLY for the current user and requested day."""

    def get(self, request):
        if not request.user.is_active:
            return JsonResponse({"error": "Email not verified."}, status=403)

        day_str = (request.GET.get("date") or "").strip()
        day = _parse_iso_date(day_str)
        if not day:
            return JsonResponse({"error": "Invalid or missing date (expected YYYY-MM-DD)."}, status=400)

        tasks = (
            Task.objects.filter(user=request.user, date=day)
            .order_by("is_completed", "created_at")
            .values("id", "title", "date", "is_completed")
        )
        return JsonResponse({"date": day_str, "tasks": list(tasks)})


@method_decorator([login_required, require_http_methods(["POST"])], name="dispatch")
class ApiCreateTaskView(View):
    """Create a task for the current user only."""

    def post(self, request):
        if not request.user.is_active:
            return JsonResponse({"error": "Email not verified."}, status=403)

        title = (request.POST.get("title") or "").strip()
        day_str = (request.POST.get("date") or "").strip()
        day = _parse_iso_date(day_str)

        if not title:
            return JsonResponse({"error": "Title is required."}, status=400)
        if not day:
            return JsonResponse({"error": "Invalid or missing date (expected YYYY-MM-DD)."}, status=400)

        task = Task.objects.create(user=request.user, title=title, date=day, is_completed=False)
        return JsonResponse(
            {
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "date": task.date.isoformat(),
                    "is_completed": task.is_completed,
                }
            },
            status=201,
        )


@method_decorator([login_required, require_http_methods(["POST"])], name="dispatch")
class ApiUpdateTaskView(View):
    """Update ONLY tasks owned by the current user."""

    def post(self, request, task_id: int):
        if not request.user.is_active:
            return JsonResponse({"error": "Email not verified."}, status=403)

        task = get_object_or_404(Task, id=task_id, user=request.user)

        # Optional updates
        title = request.POST.get("title")
        if title is not None:
            task.title = (title or "").strip()

        is_completed = request.POST.get("is_completed")
        if is_completed is not None:
            task.is_completed = str(is_completed).lower() in {"1", "true", "yes", "on"}

        task.save(update_fields=["title", "is_completed", "updated_at"])

        return JsonResponse(
            {
                "task": {
                    "id": task.id,
                    "title": task.title,
                    "date": task.date.isoformat(),
                    "is_completed": task.is_completed,
                }
            }
        )
