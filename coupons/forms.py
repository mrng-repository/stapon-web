from django import forms
from .models import StoreCoupon


class StoreCouponForm(forms.ModelForm):
    start_at = forms.DateTimeField(
        label="利用開始日時",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )
    end_at = forms.DateTimeField(
        label="利用終了日時",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        input_formats=["%Y-%m-%dT%H:%M"],
    )

    class Meta:
        model = StoreCoupon
        fields = [
            "title",
            "description",
            "discount_type",
            "discount_value",
            "start_at",
            "end_at",
            "usage_note",
            "is_public",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            if self.instance.start_at:
                self.initial["start_at"] = self.instance.start_at.strftime("%Y-%m-%dT%H:%M")
            if self.instance.end_at:
                self.initial["end_at"] = self.instance.end_at.strftime("%Y-%m-%dT%H:%M")

    def clean(self):
        cleaned_data = super().clean()
        discount_type = cleaned_data.get("discount_type")
        discount_value = cleaned_data.get("discount_value")
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if start_at and end_at and start_at >= end_at:
            raise forms.ValidationError("利用終了日時は利用開始日時より後にしてください。")

        if discount_type in [StoreCoupon.DISCOUNT_TYPE_AMOUNT, StoreCoupon.DISCOUNT_TYPE_PERCENT]:
            if discount_value in [None, ""]:
                raise forms.ValidationError("金額値引き・割引率の場合は割引値を入力してください。")

        if discount_type == StoreCoupon.DISCOUNT_TYPE_PERCENT and discount_value is not None:
            if discount_value < 1 or discount_value > 100:
                raise forms.ValidationError("割引率は1〜100の範囲で入力してください。")

        if discount_type == StoreCoupon.DISCOUNT_TYPE_FREE:
            cleaned_data["discount_value"] = None

        return cleaned_data