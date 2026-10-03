from django.http import HttpRequest

from .cart import Cart, SessionCartStore


def cart_summary(request: HttpRequest) -> dict[str, int]:
    """Expose the number of cart items to every template (no DB queries)."""
    return {"cart_count": len(Cart(SessionCartStore(request.session)))}