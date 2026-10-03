from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from orders.models import Order, OrderItem
from products.models import Category, Product

User = get_user_model()

CHECKOUT_DATA = {
    "full_name": "Alice A",
    "phone": "+380501234567",
    "email": "alice@example.com",
    "city": "Київ",
    "address": "Хрещатик 1",
    "postal_code": "01001",
    "payment_method": "card",
}


@pytest.fixture(autouse=True)
def _test_env(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    cache.clear()


@pytest.fixture
def user(db):
    return User.objects.create_user("alice", "alice@example.com", "pass12345!")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("bob", "bob@example.com", "pass12345!")


@pytest.fixture
def category(db):
    return Category.objects.create(name="Beer", slug="beer")


@pytest.fixture
def product(category):
    return Product.objects.create(
        name="IPA", slug="ipa", description="Hoppy ale",
        price=Decimal("50.00"), category=category, stock=5,
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def api_client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def make_order(db):
    def _make(user, product, quantity=1, status=Order.Status.PAID):
        order = Order.objects.create(
            user=user, status=status, total_price=product.price * quantity,
            full_name="A B", phone="+380501234567", email=user.email,
            shipping_address="Kyiv", payment_method=Order.PaymentMethod.CARD,
        )
        OrderItem.objects.create(
            order=order, product=product, quantity=quantity, price=product.price
        )
        return order

    return _make