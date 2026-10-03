from django import forms

from .models import Review


class AddToCartForm(forms.Form):
    quantity = forms.IntegerField(min_value=1, max_value=99, initial=1, label="Кількість")


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.Select(choices=[(i, str(i)) for i in range(1, 6)]),
            "comment": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"rating": "Оцінка", "comment": "Коментар"}