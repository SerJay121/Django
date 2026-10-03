"""Load demo categories and products."""
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand

from products.models import Category, Product


class Command(BaseCommand):
    help = "Create demo categories and products (skips if products exist)"

    def handle(self, *args: Any, **options: Any) -> None:
        if Product.objects.exists():
            self.stdout.write("Products already exist, skipping.")
            return
        beer = Category.objects.create(name="Пиво", slug="beer")
        ipa = Category.objects.create(name="IPA", slug="ipa", parent=beer)
        stout = Category.objects.create(name="Стаут", slug="stout", parent=beer)
        snacks = Category.objects.create(name="Снеки", slug="snacks")
        demo = [
            ("Hazy IPA", "hazy-ipa", "Соковите хмельове IPA", "89.00", ipa, 40),
            ("West Coast IPA", "west-coast-ipa", "Гірке класичне IPA", "95.00", ipa, 25),
            ("Imperial Stout", "imperial-stout", "Темне насичене пиво", "120.00", stout, 15),
            ("Milk Stout", "milk-stout", "М'який солодкуватий стаут", "99.00", stout, 30),
            ("Pale Ale", "pale-ale", "Збалансований ель", "79.00", beer, 50),
            ("Крекери з сиром", "cheese-crackers", "Снеки до пива", "45.00", snacks, 100),
            ("Сушені кальмари", "squid", "Класичний снек", "65.00", snacks, 3),
            ("Арахіс солений", "peanuts", "Смажений арахіс", "39.00", snacks, 0),
        ]
        for name, slug, desc, price, cat, stock in demo:
            Product.objects.create(
                name=name, slug=slug, description=desc,
                price=Decimal(price), category=cat, stock=stock,
            )
        self.stdout.write(self.style.SUCCESS(f"Created {len(demo)} products."))