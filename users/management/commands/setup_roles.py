"""Create permission groups for shop staff (idempotent)."""
from typing import Any

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLES: dict[str, list[str]] = {
    "Catalog managers": [
        "add_category", "change_category", "delete_category", "view_category",
        "add_product", "change_product", "delete_product", "view_product",
        "view_review", "delete_review",
    ],
    "Order managers": ["view_order", "change_order", "view_orderitem"],
}


class Command(BaseCommand):
    help = "Create/update staff groups: Catalog managers, Order managers"

    def handle(self, *args: Any, **options: Any) -> None:
        for role, codenames in ROLES.items():
            group, _ = Group.objects.get_or_create(name=role)
            perms = Permission.objects.filter(
                codename__in=codenames, content_type__app_label__in=["products", "orders"]
            )
            group.permissions.set(perms)
            self.stdout.write(f"{role}: {perms.count()} permissions")