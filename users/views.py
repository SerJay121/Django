"""Account views: registration, dashboard with order history, profile, password."""
from typing import Any

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from orders.models import Order

from .forms import ProfileForm, RegisterForm

User = get_user_model()


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "users/register.html"
    success_url = reverse_lazy("users:dashboard")

    def form_valid(self, form: RegisterForm) -> HttpResponse:
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, "Акаунт створено. Ласкаво просимо!")
        return response


class DashboardView(LoginRequiredMixin, ListView):
    """Order history with optional ?status= filter."""

    template_name = "users/dashboard.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self) -> QuerySet[Order]:
        qs = Order.objects.filter(user=self.request.user).prefetch_related("items")
        status = self.request.GET.get("status", "")
        if status in Order.Status.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["querystring"] = params.urlencode()
        ctx["statuses"] = Order.Status.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        return ctx


class ProfileUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    form_class = ProfileForm
    template_name = "users/profile.html"
    success_url = reverse_lazy("users:profile")
    success_message = "Профіль оновлено."

    def get_object(self, queryset: Any = None) -> Any:
        return self.request.user


class PasswordChange(LoginRequiredMixin, SuccessMessageMixin, PasswordChangeView):
    template_name = "users/password_change.html"
    success_url = reverse_lazy("users:dashboard")
    success_message = "Пароль змінено."