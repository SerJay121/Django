import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db
User = get_user_model()

REG = {
    "username": "carol", "email": "carol@example.com",
    "password1": "S3cure-pass!", "password2": "S3cure-pass!",
}


def test_register_logs_in(client):
    r = client.post(reverse("users:register"), REG)
    assert r.status_code == 302
    assert User.objects.filter(username="carol").exists()
    assert client.get(reverse("users:dashboard")).status_code == 200


def test_register_duplicate_email(client, user):
    r = client.post(reverse("users:register"), {**REG, "email": "ALICE@example.com"})
    assert r.status_code == 200
    assert not User.objects.filter(username="carol").exists()


def test_login_and_logout(client, user):
    r = client.post(reverse("users:login"), {"username": "alice", "password": "pass12345!"})
    assert r.status_code == 302
    client.post(reverse("users:logout"))
    assert client.get(reverse("users:dashboard")).status_code == 302


def test_dashboard_requires_login(client):
    assert client.get(reverse("users:dashboard")).status_code == 302


def test_order_history_filter(auth_client, user, product, make_order):
    make_order(user, product, status="paid")
    make_order(user, product, status="cancelled")
    r = auth_client.get(reverse("users:dashboard"), {"status": "paid"})
    assert len(r.context["orders"]) == 1
    assert len(auth_client.get(reverse("users:dashboard")).context["orders"]) == 2


def test_dashboard_shows_only_own_orders(auth_client, other_user, product, make_order):
    make_order(other_user, product)
    assert len(auth_client.get(reverse("users:dashboard")).context["orders"]) == 0


def test_profile_update(auth_client, user):
    auth_client.post(
        reverse("users:profile"),
        {"first_name": "Alice", "last_name": "Smith", "email": "new@example.com"},
    )
    user.refresh_from_db()
    assert user.email == "new@example.com" and user.first_name == "Alice"


def test_profile_email_must_be_unique(auth_client, user, other_user):
    r = auth_client.post(
        reverse("users:profile"),
        {"first_name": "A", "last_name": "B", "email": other_user.email},
    )
    assert r.status_code == 200
    user.refresh_from_db()
    assert user.email == "alice@example.com"


def test_password_change(auth_client, user):
    auth_client.post(
        reverse("users:password_change"),
        {"old_password": "pass12345!", "new_password1": "N3w-S3cure-pw!", "new_password2": "N3w-S3cure-pw!"},
    )
    user.refresh_from_db()
    assert user.check_password("N3w-S3cure-pw!")