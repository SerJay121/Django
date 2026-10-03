"""Order, order items and the persistent (API) cart."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse

from products.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Очікує"
        PAID = "paid", "Оплачено"
        SHIPPED = "shipped", "Відправлено"
        DELIVERED = "delivered", "Доставлено"
        CANCELLED = "cancelled", "Скасовано"

    class PaymentMethod(models.TextChoices):
        CARD = "card", "Картка (імітація)"
        CASH = "cash", "Оплата при отриманні"

    PURCHASED_STATUSES = (Status.PAID, Status.SHIPPED, Status.DELIVERED)
    CANCELLABLE_STATUSES = (Status.PENDING, Status.PAID)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    shipping_address = models.TextField()
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"Замовлення №{self.pk}"

    def get_absolute_url(self) -> str:
        return reverse("orders:detail", kwargs={"pk": self.pk})


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # знімок ціни

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="one_line_per_product"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="orderitem_qty_gte_1"),
        ]

    def __str__(self) -> str:
        return f"{self.product} × {self.quantity}"

    @property
    def subtotal(self) -> Decimal:
        return self.price * self.quantity


class CartItem(models.Model):
    """Cart row for API clients (the web UI keeps its cart in the session)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart_items"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="one_cart_row_per_product"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="cartitem_qty_gte_1"),
        ]