"""Shared catalog filters (used by both the web UI and the REST API)."""
import django_filters as df
from django.db.models import Q, QuerySet

from .models import Category, Product


class ProductFilter(df.FilterSet):
    """Filtering: q (name/description), category (slug incl. children), price range, sort."""

    q = df.CharFilter(method="filter_q", label="Пошук")
    category = df.CharFilter(method="filter_category", label="Категорія (slug)")
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte", label="Ціна від")
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte", label="Ціна до")
    sort = df.OrderingFilter(
        fields=(("price", "price"), ("created_at", "newest"), ("sold", "popularity")),
        label="Сортування (price, newest, popularity; '-' для спадання)",
    )

    class Meta:
        model = Product
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))

    def filter_category(
        self, queryset: QuerySet[Product], name: str, value: str
    ) -> QuerySet[Product]:
        category = Category.objects.filter(slug=value).first()
        if category is None:
            return queryset.none()
        return queryset.filter(category_id__in=category.descendant_ids())