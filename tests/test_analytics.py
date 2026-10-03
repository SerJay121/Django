import json

import pytest
from django.urls import reverse

from orders.analytics import low_stock, sales_summary, top_products, user_activity

pytestmark = pytest.mark.django_db


def test_summary_excludes_cancelled(user, product, make_order):
    make_order(user, product, quantity=2)
    make_order(user, product, quantity=1, status="cancelled")
    s = sales_summary()
    assert s["orders_count"] == 1 and s["revenue"] == 100
    assert top_products()[0]["units_sold"] == 2


def test_low_stock_and_activity(user, product, make_order):
    make_order(user, product)
    make_order(user, product)
    assert low_stock(5)[0]["name"] == "IPA"
    assert user_activity()["repeat_customers"] == 1


def test_admin_changelist_has_analytics(admin_client, user, product, make_order):
    make_order(user, product)
    r = admin_client.get(reverse("admin:orders_order_changelist"))
    assert r.status_code == 200
    assert r.context["summary"]["orders_count"] == 1


def _gql(client, query):
    return client.post(
        "/graphql/", data=json.dumps({"query": query}), content_type="application/json"
    ).json()


def test_graphql_staff_only(client, admin_client):
    q = "{ salesSummary { ordersCount } }"
    assert "errors" in _gql(client, q)
    assert _gql(admin_client, q)["data"]["salesSummary"]["ordersCount"] == 0