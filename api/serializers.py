"""DRF serializers."""
from typing import Any

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from orders.models import Order, OrderItem
from products.models import Product, Review
from products.services import user_has_purchased

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "password")
        extra_kwargs = {"email": {"required": True}}

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Користувач із таким email вже існує.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        candidate = User(**{k: v for k, v in attrs.items() if k != "password"})
        try:
            password_validation.validate_password(attrs["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Any:
        return User.objects.create_user(**validated_data)


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    avg_rating = serializers.FloatField(read_only=True, allow_null=True)
    reviews_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "description", "price", "category",
            "image", "stock", "avg_rating", "reviews_count",
        )
        read_only_fields = fields


class ReviewSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Review
        fields = ("id", "user", "rating", "comment", "created_at")
        read_only_fields = ("id", "user", "created_at")

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        user = self.context["request"].user
        product = self.context["product"]
        if not user_has_purchased(user, product):
            raise serializers.ValidationError("Залишити відгук можна лише після покупки товару.")
        if Review.objects.filter(product=product, user=user).exists():
            raise serializers.ValidationError("Ви вже залишили відгук на цей товар.")
        return attrs


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "product_name", "quantity", "price")
        read_only_fields = fields


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "status", "total_price", "full_name", "phone", "email",
            "shipping_address", "payment_method", "created_at", "items",
        )
        read_only_fields = fields


class OrderCreateSerializer(serializers.Serializer):
    """Order is created from the user's server-side cart (see /api/cart/)."""

    full_name = serializers.CharField(max_length=150)
    phone = serializers.RegexField(r"^\+?[0-9\s\-()]{9,18}$", max_length=20)
    email = serializers.EmailField()
    shipping_address = serializers.CharField()
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices)


class OrderStatusSerializer(serializers.Serializer):
    """Customers may only cancel their orders; other transitions are done by staff."""

    status = serializers.ChoiceField(choices=[(Order.Status.CANCELLED, "Скасовано")])


class CartProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ("id", "name", "slug", "price", "stock")


class CartLineSerializer(serializers.Serializer):
    product = CartProductSerializer()
    quantity = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)


class CartSerializer(serializers.Serializer):
    items = CartLineSerializer(many=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)


class CartAddSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)


class CartSetSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=0, max_value=99)