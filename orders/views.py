"""Web views: cart (session), checkout and order pages."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from products.forms import AddToCartForm

from .cart import Cart, SessionCartStore, cart_total
from .exceptions import ShopError
from .forms import CheckoutForm, UpdateCartForm
from .models import Order
from .services import cancel_order, create_order


def _cart(request: HttpRequest) -> Cart:
    return Cart(SessionCartStore(request.session))


def _safe_next(request: HttpRequest, default_name: str) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return reverse(default_name)


def cart_detail(request: HttpRequest) -> HttpResponse:
    lines = _cart(request).lines()
    return render(request, "orders/cart.html", {"lines": lines, "total": cart_total(lines)})


@require_POST
def cart_add(request: HttpRequest, product_id: int) -> HttpResponse:
    form = AddToCartForm(request.POST)
    if form.is_valid():
        try:
            _cart(request).add(product_id, form.cleaned_data["quantity"])
        except ShopError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Товар додано до кошика.")
    else:
        messages.error(request, "Некоректна кількість.")
    return redirect(_safe_next(request, "orders:cart"))


@require_POST
def cart_update(request: HttpRequest, product_id: int) -> HttpResponse:
    form = UpdateCartForm(request.POST)
    if form.is_valid():
        try:
            _cart(request).add(product_id, form.cleaned_data["quantity"], override=True)
        except ShopError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Кошик оновлено.")
    else:
        messages.error(request, "Некоректна кількість.")
    return redirect("orders:cart")


@require_POST
def cart_remove(request: HttpRequest, product_id: int) -> HttpResponse:
    _cart(request).remove(product_id)
    messages.info(request, "Товар видалено з кошика.")
    return redirect("orders:cart")


@login_required
def checkout(request: HttpRequest) -> HttpResponse:
    cart = _cart(request)
    lines = cart.lines()
    if not lines:
        messages.info(request, "Ваш кошик порожній.")
        return redirect("orders:cart")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = create_order(
                    user=request.user,
                    cart=cart,
                    full_name=form.cleaned_data["full_name"],
                    phone=form.cleaned_data["phone"],
                    email=form.cleaned_data["email"],
                    shipping_address=form.shipping_address(),
                    payment_method=form.cleaned_data["payment_method"],
                )
            except ShopError as exc:
                messages.error(request, str(exc))
                return redirect("orders:cart")
            messages.success(request, f"Замовлення №{order.pk} оформлено. Дякуємо!")
            return redirect(order)
    else:
        user = request.user
        form = CheckoutForm(
            initial={"full_name": user.get_full_name(), "email": user.email}
        )
    return render(
        request, "orders/checkout.html",
        {"form": form, "lines": lines, "total": cart_total(lines)},
    )


@login_required
def order_detail(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product"), pk=pk, user=request.user
    )
    return render(request, "orders/order_detail.html", {"order": order})


@login_required
@require_POST
def order_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        cancel_order(order)
    except ShopError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Замовлення скасовано.")
    return redirect(order)