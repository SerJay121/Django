"""Business rules for the catalog."""
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from orders.models import Order, OrderItem

from .models import Product


def user_has_purchased(user: AbstractBaseUser | AnonymousUser, product: Product) -> bool:
    """True if the user has a paid/shipped/delivered order containing the product."""
    if not user.is_authenticated:
        return False
    return OrderItem.objects.filter(
        order__user=user, product=product, order__status__in=Order.PURCHASED_STATUSES
    ).exists()