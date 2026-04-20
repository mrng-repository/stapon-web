import random
import secrets
import requests
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.shortcuts import render, redirect
from django.urls import reverse
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

def line_login_start(request):
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    request.session["line_login_state"] = state
    request.session["line_login_nonce"] = nonce

    params = {
        "response_type": "code",
        "client_id": settings.LINE_CHANNEL_ID,
        "redirect_uri": settings.LINE_REDIRECT_URI,
        "state": state,
        "scope": "profile openid",
        "nonce": nonce,
    }

    auth_url = "https://access.line.me/oauth2/v2.1/authorize?" + urlencode(params)
    return redirect(auth_url)


def line_login_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, "LINEログインがキャンセルされたか、エラーが発生しました。")
        return redirect("customer_login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("line_login_state")

    if not code or not state or not session_state or state != session_state:
        messages.error(request, "LINEログインの認証状態を確認できませんでした。")
        return redirect("customer_login")

    token_url = "https://api.line.me/oauth2/v2.1/token"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.LINE_REDIRECT_URI,
        "client_id": settings.LINE_CHANNEL_ID,
        "client_secret": settings.LINE_CHANNEL_SECRET,
    }

    try:
        token_response = requests.post(token_url, data=token_data, timeout=15)
        token_response.raise_for_status()
        token_json = token_response.json()
    except requests.RequestException:
        messages.error(request, "LINEとの通信に失敗しました。時間をおいて再度お試しください。")
        return redirect("customer_login")

    access_token = token_json.get("access_token")
    if not access_token:
        messages.error(request, "LINEアクセストークンの取得に失敗しました。")
        return redirect("customer_login")

    profile_url = "https://api.line.me/v2/profile"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        profile_response = requests.get(profile_url, headers=headers, timeout=15)
        profile_response.raise_for_status()
        profile_json = profile_response.json()
    except requests.RequestException:
        messages.error(request, "LINEプロフィールの取得に失敗しました。")
        return redirect("customer_login")

    line_user_id = profile_json.get("userId")
    if not line_user_id:
        messages.error(request, "LINEユーザー情報を取得できませんでした。")
        return redirect("customer_login")

    customer_user = CustomerUser.objects.filter(line_user_id=line_user_id).first()

    if customer_user is None:
        # 初回LINEログイン時は仮メールアドレスで顧客作成
        temp_email = f"line_{line_user_id}@stapon.local"

        customer_user, _ = CustomerUser.objects.get_or_create(
            email=temp_email,
            defaults={
                "line_user_id": line_user_id,
                "is_active": True,
            }
        )

        if not customer_user.line_user_id:
            customer_user.line_user_id = line_user_id
            customer_user.save(update_fields=["line_user_id"])

    login_customer(request, customer_user)

    request.session.pop("line_login_state", None)
    request.session.pop("line_login_nonce", None)

    pending_stamp_token = request.session.pop("pending_stamp_token", None)
    if pending_stamp_token:
        return redirect(f"{reverse('customer_stamp_grant')}?token={pending_stamp_token}")

    return redirect("customer_dashboard")

def google_login_start(request):
    state = secrets.token_urlsafe(32)
    request.session["google_login_state"] = state

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def google_login_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, "Googleログインがキャンセルされたか、エラーが発生しました。")
        return redirect("customer_login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("google_login_state")

    if not code or not state or not session_state or state != session_state:
        messages.error(request, "Googleログインの認証状態を確認できませんでした。")
        return redirect("customer_login")

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        token_response = requests.post(token_url, data=token_data, timeout=15)
        token_response.raise_for_status()
        token_json = token_response.json()
    except requests.RequestException:
        messages.error(request, "Googleとの通信に失敗しました。時間をおいて再度お試しください。")
        return redirect("customer_login")

    access_token = token_json.get("access_token")
    if not access_token:
        messages.error(request, "Googleアクセストークンの取得に失敗しました。")
        return redirect("customer_login")

    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        userinfo_response = requests.get(userinfo_url, headers=headers, timeout=15)
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except requests.RequestException:
        messages.error(request, "Googleユーザー情報の取得に失敗しました。")
        return redirect("customer_login")

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")

    if not google_sub:
        messages.error(request, "Googleユーザー情報を取得できませんでした。")
        return redirect("customer_login")

    # 既存仕様に合わせて、line_user_id をGoogle識別子保管にも流用する最小構成
    google_key = f"google:{google_sub}"

    customer_user = CustomerUser.objects.filter(line_user_id=google_key).first()

    if customer_user is None:
        if email:
            customer_user, _ = CustomerUser.objects.get_or_create(
                email=email,
                defaults={
                    "line_user_id": google_key,
                    "is_active": True,
                }
            )
            if not customer_user.line_user_id:
                customer_user.line_user_id = google_key
                customer_user.save(update_fields=["line_user_id"])
        else:
            temp_email = f"google_{google_sub}@stapon.local"
            customer_user, _ = CustomerUser.objects.get_or_create(
                email=temp_email,
                defaults={
                    "line_user_id": google_key,
                    "is_active": True,
                }
            )

    login_customer(request, customer_user)

    request.session.pop("google_login_state", None)

    pending_stamp_token = request.session.pop("pending_stamp_token", None)
    if pending_stamp_token:
        return redirect(f"{reverse('customer_stamp_grant')}?token={pending_stamp_token}")

    return redirect("customer_dashboard")

def store_google_login_start(request):
    state = secrets.token_urlsafe(32)
    request.session["store_google_login_state"] = state

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.STORE_GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def store_google_login_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, "Googleログインがキャンセルされたか、エラーが発生しました。")
        return redirect("store_login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("store_google_login_state")

    if not code or not state or not session_state or state != session_state:
        messages.error(request, "Googleログインの認証状態を確認できませんでした。")
        return redirect("store_login")

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.STORE_GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        token_response = requests.post(token_url, data=token_data, timeout=15)
        token_response.raise_for_status()
        token_json = token_response.json()
    except requests.RequestException:
        messages.error(request, "Googleとの通信に失敗しました。時間をおいて再度お試しください。")
        return redirect("store_login")

    access_token = token_json.get("access_token")
    if not access_token:
        messages.error(request, "Googleアクセストークンの取得に失敗しました。")
        return redirect("store_login")

    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        userinfo_response = requests.get(userinfo_url, headers=headers, timeout=15)
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except requests.RequestException:
        messages.error(request, "Googleユーザー情報の取得に失敗しました。")
        return redirect("store_login")

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")

    if not google_sub:
        messages.error(request, "Googleユーザー情報を取得できませんでした。")
        return redirect("store_login")

    google_key = f"google:{google_sub}"

    # 1. 既にGoogle連携済みならそれでログイン
    store_user = StoreUser.objects.filter(google_user_id=google_key).first()

    # 2. 未連携なら、既存StoreUser.emailとGoogleメールの一致で連携
    if store_user is None and email:
        store_user = StoreUser.objects.filter(email=email).first()
        if store_user:
            # 別アカウントに同じgoogle_user_idが入る事故防止
            if not store_user.google_user_id:
                store_user.google_user_id = google_key
                store_user.save(update_fields=["google_user_id"])
            elif store_user.google_user_id != google_key:
                messages.error(request, "このGoogleアカウントは別の店舗アカウントに連携されています。")
                return redirect("store_login")

    # 3. 一致しなければ新規作成せず停止
    if store_user is None:
        messages.error(request, "このGoogleアカウントは店舗アカウントに登録されていません。先に店舗登録を行ってください。")
        return redirect("store_register")

    login(request, store_user)
    request.session.pop("store_google_login_state", None)

    return redirect("store_dashboard")

def store_google_register_start(request):
    if request.method != "POST":
        return redirect("store_register")

    store_name = request.POST.get("store_name", "").strip()

    if not store_name:
        messages.error(request, "店舗名を入力してください。")
        return redirect("store_register")

    state = secrets.token_urlsafe(32)
    request.session["store_google_register_state"] = state
    request.session["pending_store_google_register_store_name"] = store_name

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.STORE_GOOGLE_REGISTER_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return redirect(auth_url)


def store_google_register_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, "Google認証がキャンセルされたか、エラーが発生しました。")
        return redirect("store_register")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("store_google_register_state")
    store_name = request.session.get("pending_store_google_register_store_name")

    if not code or not state or not session_state or state != session_state:
        messages.error(request, "Google認証の状態を確認できませんでした。")
        return redirect("store_register")

    if not store_name:
        messages.error(request, "店舗名の入力からやり直してください。")
        return redirect("store_register")

    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.STORE_GOOGLE_REGISTER_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    try:
        token_response = requests.post(token_url, data=token_data, timeout=15)
        token_response.raise_for_status()
        token_json = token_response.json()
    except requests.RequestException:
        messages.error(request, "Googleとの通信に失敗しました。時間をおいて再度お試しください。")
        return redirect("store_register")

    access_token = token_json.get("access_token")
    if not access_token:
        messages.error(request, "Googleアクセストークンの取得に失敗しました。")
        return redirect("store_register")

    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    try:
        userinfo_response = requests.get(userinfo_url, headers=headers, timeout=15)
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()
    except requests.RequestException:
        messages.error(request, "Googleユーザー情報の取得に失敗しました。")
        return redirect("store_register")

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")

    if not google_sub or not email:
        messages.error(request, "Googleアカウントのメール情報を取得できませんでした。")
        return redirect("store_register")

    google_key = f"google:{google_sub}"

    # すでにGoogle連携済みなら新規作成しない
    if StoreUser.objects.filter(google_user_id=google_key).exists():
        messages.error(request, "このGoogleアカウントは既に店舗アカウントに登録されています。ログインしてください。")
        return redirect("store_login")

    # メールアドレスが既存なら新規作成しない
    if StoreUser.objects.filter(email=email).exists():
        messages.error(request, "このGoogleメールアドレスは既に登録されています。ログインしてください。")
        return redirect("store_login")

    user = StoreUser.objects.create_user(
        email=email,
        store_name=store_name,
    )
    user.google_user_id = google_key
    user.save(update_fields=["google_user_id"])

    login(request, user)

    request.session.pop("store_google_register_state", None)
    request.session.pop("pending_store_google_register_store_name", None)

    return redirect("store_dashboard")