"""Order notification emails (user + shop admin)."""
import logging
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import BadHeaderError, send_mail

from .models import Order

logger = logging.getLogger(__name__)


def _render(order: Order) -> str:
    lines = [
        f"Замовлення №{order.pk} ({order.get_status_display()})",
        f"Отримувач: {order.full_name}, {order.phone}",
        f"Адреса: {order.shipping_address}",
        f"Оплата: {order.get_payment_method_display()}",
        "",
    ]
    for item in order.items.all():
        lines.append(f"- {item.product.name} × {item.quantity} = {item.subtotal} ₴")
    lines += ["", f"Разом: {order.total_price} ₴"]
    return "\n".join(lines)


def send_order_emails(order_id: int) -> None:
    """Send confirmation to the customer and a notification to the admin.

    Runs after commit, so a mail failure must never break the already saved order:
    transport errors are logged instead of propagated.
    """
    try:
        order = Order.objects.prefetch_related("items__product").get(pk=order_id)
        body = _render(order)
        send_mail(
            f"Ваше замовлення №{order.pk} прийнято",
            body, settings.DEFAULT_FROM_EMAIL, [order.email],
        )
        send_mail(
            f"Нове замовлення №{order.pk}",
            body, settings.DEFAULT_FROM_EMAIL, [settings.SHOP_ADMIN_EMAIL],
        )
    except (OSError, SMTPException, BadHeaderError):
        logger.exception("Failed to send emails for order %s", order_id)