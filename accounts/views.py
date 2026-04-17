from django.shortcuts import render
from django.urls import reverse

# Create your views here.
import random
from datetime import timedelta
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings

from .models import StoreUser, EmailOTP, CustomerUser, CustomerEmailOTP
from stampcards.models import RewardCoupon
from .forms import (
    StoreLoginForm,
    StoreRegisterForm,
    OTPVerifyForm,
    CustomerEmailForm,
    CustomerOTPForm,
)
from .authentication import login_customer, logout_customer
from .decorators import customer_login_required


def generate_otp():
    return str(random.randint(100000, 999999))


def store_login_view(request):
    if request.method == 'POST':
        form = StoreLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            if not StoreUser.objects.filter(email=email).exists():
                messages.error(request, 'このメールアドレスは登録されていません。')
                return redirect('store_register')

            otp = generate_otp()
            EmailOTP.objects.create(
                email=email,
                otp_code=otp,
                purpose='login',
                expires_at=EmailOTP.default_expiry()
            )

            send_mail(
                '認証コード',
                f'あなたの認証コードは {otp} です。',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            request.session['otp_email'] = email
            request.session['otp_purpose'] = 'login'
            return redirect('otp_verify')
    else:
        form = StoreLoginForm()

    return render(request, 'accounts/store_login.html', {'form': form})


def store_register_view(request):
    if request.method == 'POST':
        form = StoreRegisterForm(request.POST)
        if form.is_valid():
            store_name = form.cleaned_data['store_name']
            email = form.cleaned_data['email']

            if StoreUser.objects.filter(email=email).exists():
                messages.error(request, 'このメールアドレスはすでに登録されています。')
                return redirect('store_login')

            otp = generate_otp()
            EmailOTP.objects.create(
                email=email,
                otp_code=otp,
                purpose='register',
                expires_at=EmailOTP.default_expiry()
            )

            send_mail(
                '認証コード',
                f'あなたの認証コードは {otp} です。',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            request.session['otp_email'] = email
            request.session['otp_purpose'] = 'register'
            request.session['store_name'] = store_name
            return redirect('otp_verify')
    else:
        form = StoreRegisterForm()

    return render(request, 'accounts/store_register.html', {'form': form})


def otp_verify_view(request):
    email = request.session.get('otp_email')
    purpose = request.session.get('otp_purpose')

    if not email or not purpose:
        return redirect('store_login')

    if request.method == 'POST':
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']

            otp_record = EmailOTP.objects.filter(
                email=email,
                purpose=purpose,
                otp_code=otp_code,
                is_used=False
            ).order_by('-created_at').first()

            if not otp_record:
                messages.error(request, '認証コードが正しくありません。')
                return redirect('otp_verify')

            if otp_record.is_expired():
                messages.error(request, '認証コードの有効期限が切れています。')
                return redirect('store_login')

            otp_record.is_used = True
            otp_record.save()

            if purpose == 'register':
                store_name = request.session.get('store_name')
                user = StoreUser.objects.create_user(
                    email=email,
                    store_name=store_name
                )
            else:
                user = StoreUser.objects.get(email=email)

            login(request, user)

            request.session.pop('otp_email', None)
            request.session.pop('otp_purpose', None)
            request.session.pop('store_name', None)

            return redirect('store_dashboard')
    else:
        form = OTPVerifyForm()

    return render(request, 'accounts/otp_verify.html', {'form': form, 'email': email})


def store_dashboard_view(request):
    if not request.user.is_authenticated:
        return redirect('store_login')

    return render(request, 'accounts/store_dashboard.html')

def store_logout_view(request):
    logout(request)
    return redirect('store_login')

def customer_login_view(request):
    if request.method == 'POST':
        form = CustomerEmailForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            otp_code = str(random.randint(100000, 999999))

            CustomerEmailOTP.objects.create(
                email=email,
                otp_code=otp_code,
                expires_at=timezone.now() + timedelta(minutes=5)
            )

            # ここを変更
            send_mail(
                '認証コード',
                f'あなたの認証コードは {otp_code} です。',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )

            request.session['customer_email'] = email
            return redirect('customer_otp_verify')
    else:
        form = CustomerEmailForm()

    return render(request, 'accounts/customer_login.html', {'form': form})

def customer_otp_verify_view(request):
    email = request.session.get('customer_email')

    if not email:
        return redirect('customer_login')

    if request.method == 'POST':
        form = CustomerOTPForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']

            otp = CustomerEmailOTP.objects.filter(
                email=email,
                otp_code=otp_code,
                is_used=False
            ).order_by('-created_at').first()

            if not otp:
                messages.error(request, '認証コードが正しくありません。')
                return redirect('customer_otp_verify')

            if otp.is_expired():
                messages.error(request, '認証コードの有効期限が切れています。')
                return redirect('customer_login')

            otp.is_used = True
            otp.save()

            customer_user, created = CustomerUser.objects.get_or_create(email=email)
            login_customer(request, customer_user)

            request.session.pop('customer_email', None)

            pending_stamp_token = request.session.pop('pending_stamp_token', None)
            if pending_stamp_token:
                return redirect(f"{reverse('customer_stamp_grant')}?token={pending_stamp_token}")

            return redirect('customer_dashboard')
    else:
        form = CustomerOTPForm()

    return render(
        request,
        'accounts/customer_otp_verify.html',
        {
            'form': form,
            'email': email,
        }
    )

@customer_login_required
def customer_dashboard_view(request):
    available_coupon_count = RewardCoupon.objects.filter(
        customer=request.customer_user,
        status='available'
    ).count()

    return render(
        request,
        'accounts/customer_dashboard.html',
        {
            'customer_user': request.customer_user,
            'available_coupon_count': available_coupon_count,
        }
    )

def customer_logout_view(request):
    logout_customer(request)
    return redirect('customer_login')