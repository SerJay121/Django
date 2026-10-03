import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from orders.models import Order
from products.models import Review

pytestmark = pytest.mark.django_db

ORDER_DATA = {
    "full_name": "Alice A", "phone": "+380501234567", "email": "alice@example.com",
    "shipping_address": "Kyiv, Khreshchatyk 1", "payment_method": "card",
}


def test_jwt_flow(db):
    c = APIClient()
    reg = {"username": "dave", "email": "dave@example.com", "password": "S3cure-pass!"}
    assert c.post(reverse("api:register"), reg, format="json").status_code == 201
    tokens = c.post(
        reverse("api:login"), {"username": "dave", "password": "S3cure-pass!"}, format="json"
    ).json()
    assert {"access", "refresh"} <= tokens.keys()
    assert c.get(reverse("api:order-list")).status_code == 401
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert c.get(reverse("api:order-list")).status_code == 200
    refreshed = c.post(reverse("api:token_refresh"), {"refresh": tokens["refresh"]}, format="json")
    assert refreshed.status_code == 200 and "access" in refreshed.json()


def test_register_weak_password_and_duplicate_email(user):
    c = APIClient()
    weak = {"username": "x", "email": "x@example.com", "password": "123"}
    assert c.post(reverse("api:register"), weak, format="json").status_code == 400
    dup = {"username": "y", "email": "alice@example.com", "password": "S3cure-pass!"}
    assert c.post(reverse("api:register"), dup, format="json").status_code == 400


def test_products_public_list_filter_and_detail(db, product):
    c = APIClient()
    r = c.get(reverse("api:product-list"), {"q": "hoppy", "min_price": 10})
    assert r.status_code == 200 and r.json()["count"] == 1
    assert c.get(reverse("api:product-list"), {"q": "nothing"}).json()["count"] == 0
    assert c.get(reverse("api:product-detail", args=[product.pk])).status_code == 200


def test_cart_requires_auth(db):
    assert APIClient().get(reverse("api:cart")).status_code == 401


def test_cart_crud_and_stock_limit(api_client, product):
    url = reverse("api:cart")
    r = api_client.post(url, {"product_id": product.pk, "quantity": 2}, format="json")
    assert r.status_code == 200 and r.json()["total"] == "100.00"
    assert api_client.post(url, {"product_id": product.pk, "quantity": 9}, format="json").status_code == 400
    r = api_client.patch(url, {"product_id": product.pk, "quantity": 4}, format="json")
    assert r.json()["items"][0]["quantity"] == 4
    r = api_client.delete(url, {"product_id": product.pk})
    assert r.json()["items"] == []


def test_create_order_from_cart(api_client, product):
    api_client.post(reverse("api:cart"), {"product_id": product.pk, "quantity": 2}, format="json")
    r = api_client.post(reverse("api:order-list"), ORDER_DATA, format="json")
    assert r.status_code == 201
    assert r.json()["total_price"] == "100.00"
    product.refresh_from_db()
    assert product.stock == 3
    assert api_client.get(reverse("api:cart")).json()["items"] == []


def test_create_order_with_empty_cart(api_client):
    r = api_client.post(reverse("api:order-list"), ORDER_DATA, format="json")
    assert r.status_code == 400


def test_orders_are_private(api_client, other_user, product, make_order):
    foreign = make_order(other_user, product)
    assert api_client.get(reverse("api:order-detail", args=[foreign.pk])).status_code == 404
    assert api_client.delete(reverse("api:order-detail", args=[foreign.pk])).status_code == 404
    assert api_client.get(reverse("api:order-list")).json()["count"] == 0


def test_cancel_via_delete_and_patch(api_client, user, product, make_order):
    o1 = make_order(user, product, quantity=2)
    assert api_client.delete(reverse("api:order-detail", args=[o1.pk])).status_code == 204
    o1.refresh_from_db()
    assert o1.status == Order.Status.CANCELLED
    o2 = make_order(user, product)
    url = reverse("api:order-detail", args=[o2.pk])
    assert api_client.patch(url, {"status": "delivered"}, format="json").status_code == 400
    assert api_client.patch(url, {"status": "cancelled"}, format="json").status_code == 200
    assert api_client.delete(url).status_code == 400  # вже скасовано


def test_reviews_api(api_client, user, product, make_order):
    url = reverse("api:product-reviews", args=[product.pk])
    assert api_client.post(url, {"rating": 5, "comment": "x"}, format="json").status_code == 400
    make_order(user, product)
    assert api_client.post(url, {"rating": 5, "comment": "x"}, format="json").status_code == 201
    assert api_client.post(url, {"rating": 4}, format="json").status_code == 400
    assert Review.objects.count() == 1
    assert APIClient().get(url).json()["count"] == 1


def test_review_post_requires_auth(product):
    r = APIClient().post(
        reverse("api:product-reviews", args=[product.pk]), {"rating": 5}, format="json"
    )
    assert r.status_code == 401


def test_swagger_available(client):
    assert client.get(reverse("schema")).status_code == 200
    assert client.get(reverse("docs")).status_code == 200