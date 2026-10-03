"""Cart logic with pluggable storage (session for the web UI, database for the API)."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction

from products.models import Product

from .exceptions import InsufficientStock, ProductUnavailable
from .models import CartItem

CART_SESSION_KEY = "cart"


class CartStore(Protocol):
    def load(self) -> dict[int, int]: ...
    def save(self, data: dict[int, int]) -> None: ...


class SessionCartStore:
    """Stores {product_id: quantity} in request.session."""

    def __init__(self, session: Any) -> None:
        self._session = session

    def load(self) -> dict[int, int]:
        raw = self._session.get(CART_SESSION_KEY, {})
        return {int(k): int(v) for k, v in raw.items()}

    def save(self, data: dict[int, int]) -> None:
        self._session[CART_SESSION_KEY] = {str(k): v for k, v in data.items()}
        self._session.modified = True


class DatabaseCartStore:
    """Stores the cart in CartItem rows (for stateless JWT clients)."""

    def __init__(self, user: AbstractBaseUser) -> None:
        self._user = user

    def load(self) -> dict[int, int]:
        rows = CartItem.objects.filter(user=self._user).values_list("product_id", "quantity")
        return dict(rows)

    def save(self, data: dict[int, int]) -> None:
        with transaction.atomic():
            CartItem.objects.filter(user=self._user).delete()
            CartItem.objects.bulk_create(
                CartItem(user=self._user, product_id=pid, quantity=qty)
                for pid, qty in data.items()
            )


@dataclass(frozen=True)
class CartLine:
    product: Product
    quantity: int

    @property
    def subtotal(self) -> Decimal:
        return self.product.price * self.quantity

    @property
    def is_available(self) -> bool:
        return self.quantity <= self.product.stock


def cart_total(lines: list[CartLine]) -> Decimal:
    return sum((line.subtotal for line in lines), Decimal("0"))


class Cart:
    """Cart with stock validation. Prices are always read from the database."""

    def __init__(self, store: CartStore) -> None:
        self._store = store
        self._data = store.load()

    def __len__(self) -> int:
        return sum(self._data.values())

    def add(self, product_id: int, quantity: int = 1, *, override: bool = False) -> None:
        """Add (or set, if override) quantity. Quantity 0 with override removes the item."""
        if quantity < 0 or (quantity == 0 and not override):
            raise ValueError("quantity must be positive")
        if override and quantity == 0:
            self.remove(product_id)
            return
        product = Product.objects.active().filter(pk=product_id).first()
        if product is None:
            raise ProductUnavailable("Товар недоступний.")
        new_qty = quantity if override else self._data.get(product_id, 0) + quantity
        if new_qty > product.stock:
            raise InsufficientStock(product.name, product.stock)
        self._data[product_id] = new_qty
        self._store.save(self._data)

    def remove(self, product_id: int) -> None:
        if self._data.pop(product_id, None) is not None:
            self._store.save(self._data)

    def clear(self) -> None:
        self._data = {}
        self._store.save(self._data)

    def lines(self) -> list[CartLine]:
        """Cart lines (one query). Deleted/inactive products are dropped from the cart."""
        products = Product.objects.active().in_bulk(list(self._data))
        stale = [pid for pid in self._data if pid not in products]
        if stale:
            for pid in stale:
                del self._data[pid]
            self._store.save(self._data)
        return [CartLine(products[pid], qty) for pid, qty in self._data.items()]

    def total(self) -> Decimal:
        return cart_total(self.lines())