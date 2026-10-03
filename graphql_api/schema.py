"""GraphQL analytics (staff only). Endpoint: /graphql/ — field names are camelCase."""
from typing import Any

import graphene
from graphql import GraphQLError

from orders import analytics


def _require_staff(info: Any) -> None:
    user = info.context.user
    if not (user.is_authenticated and user.is_staff):
        raise GraphQLError("Недостатньо прав.")


class SalesSummaryType(graphene.ObjectType):
    revenue = graphene.Decimal()
    orders_count = graphene.Int()
    average_order_value = graphene.Decimal()


class TopProductType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    units_sold = graphene.Int()
    revenue = graphene.Decimal()


class StockType(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    stock = graphene.Int()


class DailyRevenueType(graphene.ObjectType):
    day = graphene.Date()
    revenue = graphene.Decimal()
    orders_count = graphene.Int()


class UserActivityType(graphene.ObjectType):
    users_total = graphene.Int()
    active_users = graphene.Int()
    repeat_customers = graphene.Int()


class Query(graphene.ObjectType):
    sales_summary = graphene.Field(SalesSummaryType)
    top_products = graphene.List(TopProductType, limit=graphene.Int(default_value=5))
    low_stock = graphene.List(StockType, threshold=graphene.Int(default_value=5))
    revenue_trend = graphene.List(DailyRevenueType, days=graphene.Int(default_value=30))
    user_activity = graphene.Field(UserActivityType, days=graphene.Int(default_value=30))

    def resolve_sales_summary(self, info: Any) -> dict[str, Any]:
        _require_staff(info)
        return analytics.sales_summary()

    def resolve_top_products(self, info: Any, limit: int) -> list[dict[str, Any]]:
        _require_staff(info)
        return analytics.top_products(max(1, min(limit, 100)))

    def resolve_low_stock(self, info: Any, threshold: int) -> list[dict[str, Any]]:
        _require_staff(info)
        return analytics.low_stock(threshold)

    def resolve_revenue_trend(self, info: Any, days: int) -> list[dict[str, Any]]:
        _require_staff(info)
        return analytics.revenue_by_day(max(1, min(days, 365)))

    def resolve_user_activity(self, info: Any, days: int) -> dict[str, int]:
        _require_staff(info)
        return analytics.user_activity(max(1, min(days, 365)))


schema = graphene.Schema(query=Query)