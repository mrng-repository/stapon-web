from django import forms
from accounts.models import StoreUser


class StoreLoginForm(forms.Form):
    email = forms.EmailField(label='メールアドレス')


class StoreRegisterForm(forms.Form):
    store_name = forms.CharField(label='店舗名', max_length=255)
    email = forms.EmailField(label='メールアドレス')

    def clean_store_name(self):
        store_name = self.cleaned_data['store_name'].strip()

        if StoreUser.objects.filter(store_name=store_name, is_deleted=False).exists():
            raise forms.ValidationError('この店舗名はすでに使用されています。')

        return store_name


class OTPVerifyForm(forms.Form):
    otp_code = forms.CharField(label='認証コード', max_length=6)


class CustomerEmailForm(forms.Form):
    email = forms.EmailField(label='メールアドレス')


class CustomerOTPForm(forms.Form):
    otp_code = forms.CharField(label='認証コード', max_length=6)