from django import forms


class StoreLoginForm(forms.Form):
    email = forms.EmailField(label='メールアドレス')


class StoreRegisterForm(forms.Form):
    store_name = forms.CharField(label='店舗名', max_length=255)
    email = forms.EmailField(label='メールアドレス')


class OTPVerifyForm(forms.Form):
    otp_code = forms.CharField(label='認証コード', max_length=6)

class CustomerEmailForm(forms.Form):
    email = forms.EmailField(label='メールアドレス')


class CustomerOTPForm(forms.Form):
    otp_code = forms.CharField(label='認証コード', max_length=6)