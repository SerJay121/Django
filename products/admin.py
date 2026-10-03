from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Category, Product, Review


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent")
    list_filter = ("parent",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("parent",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_active", "rating", "units_sold")
    list_editable = ("price", "stock", "is_active")
    list_filter = ("is_active", "category")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    list_select_related = ("category",)
    actions = ["activate", "deactivate"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        return super().get_queryset(request).with_stats()  # type: ignore[attr-defined,no-any-return]

    @admin.display(description="Рейтинг", ordering="avg_rating")
    def rating(self, obj: Any) -> str:
        return f"{obj.avg_rating:.1f}" if obj.avg_rating else "—"

    @admin.display(description="Продано", ordering="sold")
    def units_sold(self, obj: Any) -> int:
        return int(obj.sold)

    def _set_active(self, request: HttpRequest, queryset: QuerySet[Product], value: bool) -> None:
        ids = list(queryset.values_list("pk", flat=True))
        updated = Product.objects.filter(pk__in=ids).update(is_active=value)
        self.message_user(request, f"Оновлено товарів: {updated}.")

    @admin.action(description="Активувати вибрані")
    def activate(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        self._set_active(request, queryset, True)

    @admin.action(description="Деактивувати вибрані")
    def deactivate(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        self._set_active(request, queryset, False)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("product__name", "user__username", "comment")
    list_select_related = ("product", "user")