"""Domain errors raised by the cart and order services."""


class ShopError(Exception):
    """Base class; its message is safe to show to the user."""


class EmptyCart(ShopError):
    pass


class ProductUnavailable(ShopError):
    pass


class InsufficientStock(ShopError):
    def __init__(self, product_name: str, available: int) -> None:
        super().__init__(
            f"Недостатньо товару «{product_name}» на складі (доступно: {available})."
        )
        self.available = available


class OrderNotCancellable(ShopError):
    pass