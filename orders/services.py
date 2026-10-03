"""Order creation and cancellation (transactional, stock-safe)."""
from decimal import Decimal
from functools import partial

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.db.models import F

from products.models import Product

from .cart import Cart
from .emails import send_order_emails
from .exceptions import EmptyCart, InsufficientStock, OrderNotCancellable, ProductUnavailable
from .models import Order, OrderItem


@transaction.atomic
def create_order(
    *,
    user: AbstractBaseUser,
    cart: Cart,
    full_name: str,
    phone: str,
    email: str,
    shipping_address: str,
    payment_method: str,
) -> Order:
    """Create an order from the cart, decrement stock under row locks, send emails on commit."""
    wanted = {line.product.pk: line.quantity for line in cart.lines()}
    if not wanted:
        raise EmptyCart("Кошик порожній.")

    # Блокуємо рядки в порядку pk — захист від гонки та deadlock
    products = {
        p.pk: p
        for p in Product.objects.select_for_update()
        .filter(pk__in=wanted, is_active=True)
        .order_by("pk")
    }
    for pid, qty in wanted.items():
        product = products.get(pid)
        if product is None:
            raise ProductUnavailable("Один із товарів більше недоступний.")
        if qty > product.stock:
            raise InsufficientStock(product.name, product.stock)

    # Оплата імітується: картка → одразу "paid", готівка → "pending"
    status = Order.Status.PAID if payment_method == Order.PaymentMethod.CARD else Order.Status.PENDING
    order = Order.objects.create(
        user=user,
        status=status,
        full_name=full_name,
        phone=phone,
        email=email,
        shipping_address=shipping_address,
        payment_method=payment_method,
    )

    items: list[OrderItem] = []
    total = Decimal("0")
    for pid, qty in wanted.items():
        product = products[pid]
        product.stock -= qty
        product.save(update_fields=["stock", "updated_at"])
        items.append(OrderItem(order=order, product=product, quantity=qty, price=product.price))
        total += product.price * qty
    OrderItem.objects.bulk_create(items)

    order.total_price = total
    order.save(update_fields=["total_price", "updated_at"])
    cart.clear()
    transaction.on_commit(partial(send_order_emails, order.pk))
    return order


@transaction.atomic
def cancel_order(order: Order) -> Order:
    """Cancel a pending/paid order and return its items to stock."""
    locked = Order.objects.select_for_update().get(pk=order.pk)
    if locked.status not in Order.CANCELLABLE_STATUSES:
        raise OrderNotCancellable("Це замовлення вже не можна скасувати.")
    for product_id, quantity in locked.items.values_list("product_id", "quantity"):
        Product.objects.filter(pk=product_id).update(stock=F("stock") + quantity)
    locked.status = Order.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    return locked