import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_add_respects_stock(client, product):  # stock = 5
    url = reverse("orders:cart_add", args=[product.pk])
    client.post(url, {"quantity": 3})
    client.post(url, {"quantity": 3})  # 6 > 5 → відхилено
    assert client.session["cart"] == {str(product.pk): 3}


def test_update_and_remove(client, product):
    client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 2})
    client.post(reverse("orders:cart_update", args=[product.pk]), {"quantity": 4})
    assert client.session["cart"] == {str(product.pk): 4}
    client.post(reverse("orders:cart_update", args=[product.pk]), {"quantity": 0})
    assert client.session["cart"] == {}


def test_cart_page_total(client, product):
    client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 2})
    r = client.get(reverse("orders:cart"))
    assert r.context["total"] == 100


def test_invalid_quantity_rejected(client, product):
    client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 0})
    assert not client.session.get("cart")


def test_remove(client, product):
    client.post(reverse("orders:cart_add", args=[product.pk]), {"quantity": 1})
    client.post(reverse("orders:cart_remove", args=[product.pk]))
    assert client.session["cart"] == {}