import pytest
from django.urls import reverse

from products.models import Review

pytestmark = pytest.mark.django_db


def _post(client, product, rating=5):
    return client.post(
        reverse("products:review", args=[product.slug]), {"rating": rating, "comment": "Good"}
    )


def test_review_requires_purchase(auth_client, product):
    _post(auth_client, product)
    assert Review.objects.count() == 0


def test_pending_order_does_not_count(auth_client, user, product, make_order):
    make_order(user, product, status="pending")
    _post(auth_client, product)
    assert Review.objects.count() == 0


def test_review_after_purchase_once(auth_client, user, product, make_order):
    make_order(user, product)
    _post(auth_client, product)
    _post(auth_client, product, rating=1)  # дубль
    assert Review.objects.count() == 1
    assert Review.objects.get().rating == 5


def test_invalid_rating_rejected(auth_client, user, product, make_order):
    make_order(user, product)
    _post(auth_client, product, rating=9)
    assert Review.objects.count() == 0


def test_review_requires_login(client, product):
    r = _post(client, product)
    assert r.status_code == 302 and "/login/" in r.url