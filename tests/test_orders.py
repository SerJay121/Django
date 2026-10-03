import pytest
from django.core import mail
from django.urls import reverse

from orders.models import Order
from myshop.tests.conftest import CHECKOUT_DATA

pytestmark = pytest.mark.django_db


def test_checkout_requires_login(client, product):
    r = client.get(reverse("orders:checkout"))
    assert r.status_code == 302 and "/login/" in r.url


def test_checkout_creates_order(auth_client, product, django_capture_on_commit_callbacks):
    auth_client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 2})
    with django_capture_on_commit_callbacks(execute=True):
        r = auth_client.post(reverse("orders:checkout"), CHECKOUT_DATA)
    order = Order.objects.get()
    assert r.status_code == 302
    assert order.total_price == 100
    assert order.status == Order.Status.PAID
    assert order.items.get().price == product.price
    product.refresh_from_db()
    assert product.stock == 3
    assert not auth_client.session.get("cart")
    assert len(mail.outbox) == 2


def test_cash_order_is_pending(auth_client, product):
    auth_client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 1})
    auth_client.post(reverse("orders:checkout"), {**CHECKOUT_DATA, "payment_method": "cash"})
    assert Order.objects.get().status == Order.Status.PENDING


def test_invalid_form_creates_nothing(auth_client, product):
    auth_client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 1})
    r = auth_client.post(reverse("orders:checkout"), {**CHECKOUT_DATA, "phone": "abc"})
    assert r.status_code == 200
    assert Order.objects.count() == 0


def test_stock_changed_before_checkout_is_rolled_back(auth_client, product):
    auth_client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 3})
    product.stock = 1
    product.save()
    r = auth_client.post(reverse("orders:checkout"), CHECKOUT_DATA)
    assert r.status_code == 302 and r.url == reverse("orders:cart")
    assert Order.objects.count() == 0
    product.refresh_from_db()
    assert product.stock == 1


def test_empty_cart_checkout_redirects(auth_client):
    r = auth_client.post(reverse("orders:checkout"), CHECKOUT_DATA)
    assert r.url == reverse("orders:cart")


def test_cancel_restores_stock(auth_client, user, product, make_order):
    order = make_order(user, product, quantity=2)
    product.stock = 3
    product.save()
    auth_client.post(reverse("orders:cancel", args=[order.pk]))
    order.refresh_from_db()
    product.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert product.stock == 5


def test_cannot_cancel_shipped(auth_client, user, product, make_order):
    order = make_order(user, product, status=Order.Status.SHIPPED)
    auth_client.post(reverse("orders:cancel", args=[order.pk]))
    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED


def test_foreign_order_is_404(auth_client, other_user, product, make_order):
    order = make_order(other_user, product)
    assert auth_client.get(reverse("orders:detail", args=[order.pk])).status_code == 404
    assert auth_client.post(reverse("orders:cancel", args=[order.pk])).status_code == 404