from django import forms
from .models import StampCard


class StampCardForm(forms.ModelForm):
    class Meta:
        model = StampCard
        fields = ['title', 'required_stamps', 'reward_name', 'description', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': '例: 来店スタンプカード'}),
            'required_stamps': forms.NumberInput(attrs={'placeholder': '例: 5', 'min': '1'}),
            'reward_name': forms.TextInput(attrs={'placeholder': '例: コーヒー30円引き'}),
            'description': forms.Textarea(attrs={'rows': 4, 'placeholder': '例: 5個たまると1回使えるクーポンを付与'}),
        }

class StampGrantQRForm(forms.Form):
    stamp_card = forms.ModelChoiceField(
        queryset=StampCard.objects.none(),
        label='対象スタンプカード'
    )
    grant_count = forms.IntegerField(
        min_value=1,
        initial=1,
        label='付与数'
    )
    expires_at = forms.DateTimeField(
        label='有効期限',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )

    def __init__(self, *args, **kwargs):
        store_user = kwargs.pop('store_user', None)
        super().__init__(*args, **kwargs)

        if store_user is not None:
            self.fields['stamp_card'].queryset = StampCard.objects.filter(
                store_user=store_user,
                is_active=True
            )