"""Web views: catalog, product page, review submission."""
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .filters import ProductFilter
from .forms import AddToCartForm, ReviewForm
from .models import Category, Product, Review
from .services import user_has_purchased


class ProductListView(ListView):
    """Catalog with filtering, search, sorting and pagination."""

    template_name = "products/list.html"
    context_object_name = "products"
    paginate_by = 12
    filterset: ProductFilter

    def get_queryset(self) -> Any:
        base = (
            Product.objects.active()
            .select_related("category")
            .with_stats()
            .order_by("-created_at", "-id")
        )
        self.filterset = ProductFilter(self.request.GET, queryset=base)
        return self.filterset.qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["filter"] = self.filterset
        ctx["querystring"] = params.urlencode()
        ctx["categories"] = Category.objects.filter(parent__isnull=True).prefetch_related(
            "children"
        )
        return ctx


class ProductDetailView(DetailView):
    template_name = "products/detail.html"
    context_object_name = "product"
    queryset = Product.objects.active().select_related("category").with_stats()

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        ctx = super().get_context_data(**kwargs)
        product: Product = self.object
        user = self.request.user
        already = user.is_authenticated and product.reviews.filter(user=user).exists()
        ctx.update(
            reviews=product.reviews.select_related("user")[:50],
            already_reviewed=already,
            can_review=user_has_purchased(user, product) and not already,
            review_form=ReviewForm(),
            add_form=AddToCartForm(initial={"quantity": 1}),
        )
        return ctx


@login_required
@require_POST
def review_create(request: HttpRequest, slug: str) -> HttpResponse:
    """Create a review; only for users who bought the product, one review per user."""
    product = get_object_or_404(Product.objects.active(), slug=slug)
    if not user_has_purchased(request.user, product):
        messages.error(request, "Залишити відгук можна лише після покупки товару.")
        return redirect(product)
    if Review.objects.filter(product=product, user=request.user).exists():
        messages.error(request, "Ви вже залишили відгук на цей товар.")
        return redirect(product)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        try:
            with transaction.atomic():
                review.save()
        except IntegrityError:
            messages.error(request, "Ви вже залишили відгук на цей товар.")
        else:
            messages.success(request, "Дякуємо за відгук!")
    else:
        messages.error(request, "Перевірте дані відгуку (оцінка 1–5).")
    return redirect(product)