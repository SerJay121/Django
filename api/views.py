"""REST API views."""
from typing import Any

from django.db import IntegrityError, transaction
from drf_spectacular.utils import (
    OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view,
)
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.cart import Cart, DatabaseCartStore, cart_total
from orders.exceptions import ShopError
from orders.models import Order
from orders.services import cancel_order, create_order
from products.filters import ProductFilter
from products.models import Product

from .serializers import (
    CartAddSerializer, CartSerializer, CartSetSerializer, OrderCreateSerializer,
    OrderSerializer, OrderStatusSerializer, ProductSerializer, RegisterSerializer,
    ReviewSerializer,
)


class RegisterView(generics.CreateAPIView):
    """Create an account. Then obtain tokens via POST /api/users/login/."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """Products list (pagination, filters, search `q`, sorting `sort`) and details."""

    queryset = Product.objects.active().select_related("category").with_stats()
    serializer_class = ProductSerializer
    filterset_class = ProductFilter
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(
        methods=["GET"], responses=ReviewSerializer(many=True), summary="List product reviews"
    )
    @extend_schema(
        methods=["POST"], request=ReviewSerializer, responses={201: ReviewSerializer},
        summary="Add a review (only after purchase)",
    )
    @action(detail=True, methods=["get", "post"], url_path="reviews", filterset_class=None)
    def reviews(self, request: Request, pk: str | None = None) -> Response:
        product = self.get_object()
        if request.method == "GET":
            page = self.paginate_queryset(product.reviews.select_related("user"))
            return self.get_paginated_response(ReviewSerializer(page, many=True).data)

        serializer = ReviewSerializer(
            data=request.data, context={"request": request, "product": product}
        )
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save(product=product, user=request.user)
        except IntegrityError as exc:
            raise ValidationError("Ви вже залишили відгук на цей товар.") from exc
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    create=extend_schema(
        request=OrderCreateSerializer, responses={201: OrderSerializer},
        summary="Create order from the current cart",
    ),
    update=extend_schema(
        request=OrderStatusSerializer, responses=OrderSerializer, summary="Cancel order"
    ),
    partial_update=extend_schema(
        request=OrderStatusSerializer, responses=OrderSerializer, summary="Cancel order"
    ),
    destroy=extend_schema(responses={204: None}, summary="Cancel order"),
)
class OrderViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """The user's own orders. Foreign orders are invisible (404)."""

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = None

    def get_queryset(self) -> Any:
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user).prefetch_related("items__product")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = create_order(
                user=request.user,
                cart=Cart(DatabaseCartStore(request.user)),
                **serializer.validated_data,
            )
        except ShopError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def _cancel(self, order: Order) -> Order:
        try:
            return cancel_order(order)
        except ShopError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        order = self.get_object()
        OrderStatusSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(OrderSerializer(self._cancel(order)).data)

    def destroy(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self._cancel(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartView(APIView):
    """Server-side cart of the authenticated user (stored in the database)."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _cart(request: Request) -> Cart:
        return Cart(DatabaseCartStore(request.user))

    @staticmethod
    def _response(cart: Cart) -> Response:
        lines = cart.lines()
        return Response(CartSerializer({"items": lines, "total": cart_total(lines)}).data)

    @staticmethod
    def _apply(cart: Cart, product_id: int, quantity: int, override: bool) -> None:
        try:
            cart.add(product_id, quantity, override=override)
        except ShopError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    @extend_schema(responses=CartSerializer)
    def get(self, request: Request) -> Response:
        return self._response(self._cart(request))

    @extend_schema(
        request=CartAddSerializer, responses=CartSerializer,
        summary="Add quantity of a product to the cart",
        examples=[OpenApiExample("Add", value={"product_id": 1, "quantity": 2}, request_only=True)],
    )
    def post(self, request: Request) -> Response:
        data = CartAddSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        cart = self._cart(request)
        self._apply(cart, data.validated_data["product_id"], data.validated_data["quantity"], False)
        return self._response(cart)

    @extend_schema(
        request=CartSetSerializer, responses=CartSerializer,
        summary="Set quantity (0 removes the item)",
        examples=[OpenApiExample("Set", value={"product_id": 1, "quantity": 5}, request_only=True)],
    )
    def patch(self, request: Request) -> Response:
        data = CartSetSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        cart = self._cart(request)
        self._apply(cart, data.validated_data["product_id"], data.validated_data["quantity"], True)
        return self._response(cart)

    @extend_schema(
        parameters=[OpenApiParameter("product_id", int, required=False)],
        responses=CartSerializer,
        summary="Remove one product (?product_id=) or clear the whole cart",
    )
    def delete(self, request: Request) -> Response:
        cart = self._cart(request)
        raw = request.query_params.get("product_id")
        if raw is None:
            cart.clear()
        elif raw.isdigit():
            cart.remove(int(raw))
        else:
            raise ValidationError({"product_id": "Має бути цілим числом."})
        return self._response(cart)