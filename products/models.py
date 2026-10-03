"""Catalog models: categories, products and reviews."""
from __future__ import annotations

from collections import defaultdict

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Count, IntegerField, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse


class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def descendant_ids(self) -> list[int]:
        """Return this category id plus ids of all nested categories (one query)."""
        children: dict[int | None, list[int]] = defaultdict(list)
        for pk, parent_id in Category.objects.values_list("pk", "parent_id"):
            children[parent_id].append(pk)
        result = [self.pk]
        stack = [self.pk]
        while stack:
            for child in children.get(stack.pop(), []):
                result.append(child)
                stack.append(child)
        return result


class ProductQuerySet(models.QuerySet["Product"]):
    def active(self) -> ProductQuerySet:
        return self.filter(is_active=True)

    def with_stats(self) -> ProductQuerySet:
        """Annotate avg_rating, reviews_count and sold (units in non-cancelled orders)."""
        from orders.models import Order, OrderItem

        sold = (
            OrderItem.objects.filter(product=OuterRef("pk"))
            .exclude(order__status=Order.Status.CANCELLED)
            .order_by()
            .values("product")
            .annotate(total=Sum("quantity"))
            .values("total")
        )
        return self.annotate(
            avg_rating=Avg("reviews__rating"),
            reviews_count=Count("reviews", distinct=True),
            sold=Coalesce(Subquery(sold, output_field=IntegerField()), 0),
        )


class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    image = models.ImageField(upload_to="products/", blank=True)
    is_active = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["is_active", "-created_at"]),
            models.Index(fields=["price"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gte=0), name="product_price_non_negative"),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("products:detail", kwargs={"slug": self.slug})


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="one_review_per_user"),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_5"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} — {self.rating}/5 ({self.user})"