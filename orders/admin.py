from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.utils import timezone

from . import analytics
from .exceptions import OrderNotCancellable
from .models import Order, OrderItem
from .services import cancel_order


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("product", "quantity", "price")

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "payment_method", "total_price", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    search_fields = ("user__username", "user__email", "full_name", "phone")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    inlines = [OrderItemInline]
    # Статус змінюється лише діями нижче, щоб скасування завжди повертало товар на склад
    readonly_fields = ("status", "total_price", "created_at", "updated_at")
    actions = ["mark_shipped", "mark_delivered", "cancel_orders"]
    change_list_template = "admin/orders/order/change_list.html"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # замовлення створюються лише через checkout/API

    def changelist_view(
        self, request: HttpRequest, extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        extra_context = extra_context or {}
        if self.has_view_or_change_permission(request):
            extra_context.update(
                summary=analytics.sales_summary(),
                top_products=analytics.top_products(5),
                daily=analytics.revenue_by_day(14),
            )
        return super().changelist_view(request, extra_context)

    def _transition(
        self, request: HttpRequest, queryset: QuerySet[Order], src: list[str], dst: str
    ) -> None:
        ids = list(queryset.filter(status__in=src).values_list("pk", flat=True))
        Order.objects.filter(pk__in=ids).update(status=dst, updated_at=timezone.now())
        self.message_user(request, f"Оновлено замовлень: {len(ids)}.")

    @admin.action(description="Позначити як відправлені")
    def mark_shipped(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        self._transition(
            request, queryset,
            [Order.Status.PENDING, Order.Status.PAID], Order.Status.SHIPPED,
        )

    @admin.action(description="Позначити як доставлені")
    def mark_delivered(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        self._transition(request, queryset, [Order.Status.SHIPPED], Order.Status.DELIVERED)

    @admin.action(description="Скасувати (повернути товар на склад)")
    def cancel_orders(self, request: HttpRequest, queryset: QuerySet[Order]) -> None:
        done = skipped = 0
        for order in queryset:
            try:
                cancel_order(order)
                done += 1
            except OrderNotCancellable:
                skipped += 1
        self.message_user(request, f"Скасовано: {done}, пропущено: {skipped}.")