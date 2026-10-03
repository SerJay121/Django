"""Sales analytics (aggregations/annotations) shared by the admin and GraphQL."""
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from products.models import Product

from .models import Order

ZERO = Decimal("0")


def _valid_orders() -> Any:
    return Order.objects.exclude(status=Order.Status.CANCELLED)


def sales_summary() -> dict[str, Any]:
    """Revenue, orders count and average order value (cancelled orders excluded)."""
    return _valid_orders().aggregate(
        revenue=Coalesce(Sum("total_price"), ZERO, output_field=DecimalField()),
        orders_count=Count("id"),
        average_order_value=Coalesce(Avg("total_price"), ZERO, output_field=DecimalField()),
    )


def top_products(limit: int = 5) -> list[dict[str, Any]]:
    valid = ~Q(order_items__order__status=Order.Status.CANCELLED)
    line_revenue = ExpressionWrapper(
        F("order_items__quantity") * F("order_items__price"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    return list(
        Product.objects.annotate(
            units_sold=Sum("order_items__quantity", filter=valid),
            revenue=Sum(line_revenue, filter=valid),
        )
        .filter(units_sold__gt=0)
        .order_by("-units_sold", "-revenue", "pk")
        .values("id", "name", "units_sold", "revenue")[:limit]
    )


def revenue_by_day(days: int = 30) -> list[dict[str, Any]]:
    since = timezone.now() - timedelta(days=days)
    return list(
        _valid_orders()
        .filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total_price"), orders_count=Count("id"))
        .order_by("day")
    )


def low_stock(threshold: int = 5) -> list[dict[str, Any]]:
    return list(
        Product.objects.active()
        .filter(stock__lte=threshold)
        .order_by("stock", "pk")
        .values("id", "name", "stock")
    )


def user_activity(days: int = 30) -> dict[str, int]:
    """Total users, users active in the last N days, and repeat customers (>=2 orders)."""
    since = timezone.now() - timedelta(days=days)
    return {
        "users_total": get_user_model().objects.count(),
        "active_users": _valid_orders()
        .filter(created_at__gte=since)
        .values("user")
        .distinct()
        .count(),
        "repeat_customers": _valid_orders()
        .values("user")
        .annotate(n=Count("id"))
        .filter(n__gte=2)
        .count(),
    }