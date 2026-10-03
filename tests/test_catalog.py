from decimal import Decimal

import pytest
from django.urls import reverse

from products.models import Category, Product

pytestmark = pytest.mark.django_db


def _bulk(category, n):
    for i in range(n):
        Product.objects.create(
            name=f"Beer {i}", slug=f"beer-{i}", description=f"desc {i}",
            price=Decimal(10 + i), category=category, stock=1,
        )


def test_pagination(client, category):
    _bulk(category, 15)
    page1 = client.get(reverse("products:list"))
    page2 = client.get(reverse("products:list"), {"page": 2})
    assert len(page1.context["products"]) == 12
    assert len(page2.context["products"]) == 3


def test_price_filter(client, category):
    _bulk(category, 10)  # prices 10..19
    r = client.get(reverse("products:list"), {"min_price": 15, "max_price": 17})
    assert sorted(p.price for p in r.context["products"]) == [15, 16, 17]


def test_search_in_name_and_description(client, category):
    Product.objects.create(name="Lager", slug="lager", description="crisp and golden",
                           price=Decimal("10"), category=category, stock=1)
    Product.objects.create(name="Stout", slug="stout-x", description="dark",
                           price=Decimal("10"), category=category, stock=1)
    assert len(client.get(reverse("products:list"), {"q": "lag"}).context["products"]) == 1
    assert len(client.get(reverse("products:list"), {"q": "golden"}).context["products"]) == 1


def test_category_filter_includes_children(client, category, product):
    child = Category.objects.create(name="Stout", slug="stout", parent=category)
    Product.objects.create(name="S", slug="s", price=Decimal("30"), category=child, stock=1)
    r = client.get(reverse("products:list"), {"category": "beer"})
    assert len(r.context["products"]) == 2
    r = client.get(reverse("products:list"), {"category": "stout"})
    assert len(r.context["products"]) == 1


def test_sorting_by_price(client, category):
    _bulk(category, 3)
    asc = client.get(reverse("products:list"), {"sort": "price"}).context["products"]
    desc = client.get(reverse("products:list"), {"sort": "-price"}).context["products"]
    assert asc[0].price < desc[0].price


def test_inactive_hidden_and_invalid_filter_safe(client, category, product):
    Product.objects.filter(pk=product.pk).update(is_active=False)
    assert len(client.get(reverse("products:list")).context["products"]) == 0
    assert client.get(reverse("products:list"), {"min_price": "abc"}).status_code == 200


def test_product_detail(client, product):
    r = client.get(product.get_absolute_url())
    assert r.status_code == 200
    assert not r.context["can_review"]