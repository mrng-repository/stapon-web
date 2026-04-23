import random
import secrets
import requests
from datetime import timedelta
from urllib.parse import urlencode

from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import login, logout
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction

from .models import StoreUser, EmailOTP, CustomerUser, CustomerEmailOTP, OAuthState
from stampcards.models import StampCard, CustomerStampCard, StampGrantLog, RewardCoupon
from .forms import (
    StoreLoginForm,
    StoreRegisterForm,
    OTPVerifyForm,
    CustomerEmailForm,
    CustomerOTPForm,
)
from .authentication import login_customer, logout_customer
from .decorators import customer_login_required


def _make_temp_email(prefix, social_user_id):
    return f"{prefix}_{social_user_id}@stapon.local"


def generate_otp():
    return str(random.randint(100000, 999999))


def _is_temp_email(email):
    return bool(email and email.endswith("@stapon.local"))


def _customer_login_method(customer_user):
    if getattr(customer_user, "line_user_id", None):
        return "LINE"
    if getattr(customer_user, "google_user_id", None):
        return "Google"
    return "メール"


def _store_login_method(store_user):
    if getattr(store_user, "line_user_id", None):
        return "LINE"
    if getattr(store_user, "google_user_id", None):
        return "Google"
    return "メール"


def _restore_customer_user(customer_user, *, email=None, google_user_id=None, line_user_id=None, display_name=None):
    update_fields = []

    if email and customer_user.email != email:
        customer_user.email = email
        update_fields.append("email")

    if google_user_id and customer_user.google_user_id != google_user_id:
        customer_user.google_user_id = google_user_id
        update_fields.append("google_user_id")

    if line_user_id and customer_user.line_user_id != line_user_id:
        customer_user.line_user_id = line_user_id
        update_fields.append("line_user_id")

    if display_name is not None and customer_user.display_name != display_name:
        customer_user.display_name = display_name
        update_fields.append("display_name")

    if customer_user.is_deleted:
        customer_user.is_deleted = False
        update_fields.append("is_deleted")

    if customer_user.deleted_at is not None:
        customer_user.deleted_at = None
        update_fields.append("deleted_at")

    if not customer_user.is_active:
        customer_user.is_active = True
        update_fields.append("is_active")

    if update_fields:
        customer_user.save(update_fields=update_fields)

    return customer_user


def _restore_store_user(store_user, *, email=None, store_name=None, google_user_id=None, line_user_id=None):
    update_fields = []

    if email and store_user.email != email:
        store_user.email = email
        update_fields.append("email")

    if store_name and store_user.store_name != store_name:
        store_user.store_name = store_name
        update_fields.append("store_name")

    if google_user_id and store_user.google_user_id != google_user_id:
        store_user.google_user_id = google_user_id
        update_fields.append("google_user_id")

    if line_user_id and store_user.line_user_id != line_user_id:
        store_user.line_user_id = line_user_id
        update_fields.append("line_user_id")

    if store_user.is_deleted:
        store_user.is_deleted = False
        update_fields.append("is_deleted")

    if store_user.deleted_at is not None:
        store_user.deleted_at = None
        update_fields.append("deleted_at")

    if not store_user.is_active:
        store_user.is_active = True
        update_fields.append("is_active")

    if update_fields:
        store_user.save(update_fields=update_fields)

    return store_user


@customer_login_required
def customer_account_view(request):
    customer_user = request.customer_user

    page_subtext = customer_user.display_name or customer_user.email
    account_email = None if _is_temp_email(customer_user.email) else customer_user.email
    login_method = _customer_login_method(customer_user)

    return render(
        request,
        "accounts/customer_account.html",
        {
            "customer_user": customer_user,
            "page_subtext": page_subtext,
            "account_email": account_email,
            "login_method": login_method,
        }
    )


def store_account_view(request):
    if not request.user.is_authenticated:
        return redirect("store_login")

    store_user = request.user
    page_subtext = store_user.store_name
    account_email = None if _is_temp_email(store_user.email) else store_user.email
    login_method = _store_login_method(store_user)

    return render(
        request,
        "accounts/store_account.html",
        {
            "store_user": store_user,
            "page_subtext": page_subtext,
            "account_email": account_email,
            "login_method": login_method,
        }
    )


def store_login_view(request):
    if request.method == 'POST':
        form = StoreLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            store_user = StoreUser.objects.filter(email=email).first()
            if not store_user:
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
            store_name = form.cleaned_data['store_name'].strip()
            email = form.cleaned_data['email']

            existing_by_email = StoreUser.objects.filter(email=email).first()
            existing_by_store_name = StoreUser.objects.filter(store_name=store_name).first()

            if existing_by_email and not existing_by_email.is_deleted:
                messages.error(request, 'このメールアドレスはすでに登録されています。')
                return redirect('store_login')

            if existing_by_store_name and not existing_by_store_name.is_deleted and existing_by_store_name.email != email:
                messages.error(request, 'この店舗名はすでに使用されています。')
                return redirect('store_register')

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
            otp_record.save(update_fields=['is_used'])

            if purpose == 'register':
                store_name = request.session.get('store_name')

                with transaction.atomic():
                    user = StoreUser.objects.filter(email=email).first()

                    if user:
                        if not user.is_deleted:
                            messages.error(request, 'このメールアドレスはすでに登録されています。')
                            return redirect('store_login')

                        duplicate_store = StoreUser.objects.filter(
                            store_name=store_name,
                            is_deleted=False
                        ).exclude(pk=user.pk).exists()
                        if duplicate_store:
                            messages.error(request, 'この店舗名はすでに使用されています。')
                            return redirect('store_register')

                        user = _restore_store_user(
                            user,
                            email=email,
                            store_name=store_name,
                        )
                    else:
                        if StoreUser.objects.filter(store_name=store_name, is_deleted=False).exists():
                            messages.error(request, 'この店舗名はすでに使用されています。')
                            return redirect('store_register')

                        user = StoreUser.objects.create_user(
                            email=email,
                            store_name=store_name
                        )
            else:
                user = StoreUser.objects.filter(email=email).first()
                if not user:
                    messages.error(request, 'アカウントが見つかりません。')
                    return redirect('store_login')

                if user.is_deleted:
                    messages.error(request, '退会済みアカウントです。新規登録画面から再登録してください。')
                    request.session.pop('otp_email', None)
                    request.session.pop('otp_purpose', None)
                    request.session.pop('store_name', None)
                    return redirect('store_register')

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

    account_email = None if _is_temp_email(request.user.email) else request.user.email

    return render(
        request,
        'accounts/store_dashboard.html',
        {
            'page_subtext': request.user.store_name,
            'account_email': account_email,
        }
    )


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
            otp.save(update_fields=['is_used'])

            customer_user = CustomerUser.objects.filter(email=email).first()

            if customer_user:
                if customer_user.is_deleted:
                    customer_user = _restore_customer_user(customer_user, email=email)
            else:
                customer_user = CustomerUser.objects.create(
                    email=email,
                    is_active=True,
                )

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

    if request.customer_user.display_name:
        page_subtext = request.customer_user.display_name
    else:
        page_subtext = request.customer_user.email

    account_email = None if _is_temp_email(request.customer_user.email) else request.customer_user.email

    return render(
        request,
        'accounts/customer_dashboard.html',
        {
            'customer_user': request.customer_user,
            'available_coupon_count': available_coupon_count,
            'page_subtext': page_subtext,
            'account_email': account_email,
        }
    )


def customer_logout_view(request):
    logout_customer(request)
    return redirect('customer_login')


def line_login_start(request):
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    if request.session.session_key is None:
        request.session.save()

    print("=== LINE customer start ===")
    print("session_key(before) =", request.session.session_key)
    print("state =", state)
    print("redirect_uri =", settings.LINE_REDIRECT_URI)
    print("host =", request.get_host())
    print("is_secure =", request.is_secure())
    print("existing_line_login_state(before) =", request.session.get("line_login_state"))

    OAuthState.objects.create(
        provider="line",
        purpose="customer_line_login",
        state=state,
        session_key=request.session.session_key,
        payload={
            "nonce": nonce,
        },
        expires_at=OAuthState.default_expiry(),
    )

    request.session["line_login_state"] = state
    request.session["line_login_nonce"] = nonce
    request.session.save()

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

    print("=== LINE customer callback ===")
    print("code =", request.GET.get("code"))
    print("state =", request.GET.get("state"))
    print("session_state =", request.session.get("line_login_state"))
    print("session_key =", request.session.session_key)
    print("full_path =", request.get_full_path())

    if error:
        messages.error(request, "LINEログインがキャンセルされたか、エラーが発生しました。")
        return redirect("customer_login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("line_login_state")

    if not code or not state:
        messages.error(request, "LINEログインの認証状態を確認できませんでした。")
        return redirect("customer_login")

    oauth_state = OAuthState.objects.filter(
        provider="line",
        purpose="customer_line_login",
        state=state,
        is_used=False,
    ).order_by("-created_at").first()

    if not oauth_state:
        print("=== LINE customer mismatch: oauth_state not found ===")
        print("code =", code)
        print("state =", state)
        print("session_state =", session_state)
        print("session_key =", request.session.session_key)
        print("referer =", request.META.get("HTTP_REFERER"))
        print("user_agent =", request.META.get("HTTP_USER_AGENT"))
        messages.error(request, "LINEログインの認証状態を確認できませんでした。")
        return redirect("customer_login")

    if oauth_state.is_expired():
        print("=== LINE customer mismatch: oauth_state expired ===")
        print("code =", code)
        print("state =", state)
        print("session_state =", session_state)
        print("session_key =", request.session.session_key)
        print("referer =", request.META.get("HTTP_REFERER"))
        print("user_agent =", request.META.get("HTTP_USER_AGENT"))
        messages.error(request, "LINEログインの有効期限が切れています。もう一度お試しください。")
        return redirect("customer_login")

    oauth_state.is_used = True
    oauth_state.save(update_fields=["is_used"])

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
    line_display_name = profile_json.get("displayName", "")

    if not line_user_id:
        messages.error(request, "LINEユーザー情報を取得できませんでした。")
        return redirect("customer_login")

    customer_user = CustomerUser.objects.filter(line_user_id=line_user_id).first()

    if customer_user is None:
        temp_email = _make_temp_email("line", line_user_id)
        customer_user = CustomerUser.objects.filter(email=temp_email).first()

        if customer_user:
            customer_user = _restore_customer_user(
                customer_user,
                email=temp_email,
                line_user_id=line_user_id,
                display_name=line_display_name,
            )
        else:
            customer_user = CustomerUser.objects.create(
                email=temp_email,
                line_user_id=line_user_id,
                display_name=line_display_name,
                is_active=True,
            )
    else:
        customer_user = _restore_customer_user(
            customer_user,
            line_user_id=line_user_id,
            display_name=line_display_name or customer_user.display_name,
        )

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

    google_key = f"google:{google_sub}"

    customer_user = CustomerUser.objects.filter(google_user_id=google_key).first()

    if customer_user is None:
        if email:
            existing_user = CustomerUser.objects.filter(email=email).first()
            if existing_user:
                customer_user = _restore_customer_user(
                    existing_user,
                    email=email,
                    google_user_id=google_key,
                )
            else:
                customer_user = CustomerUser.objects.create(
                    email=email,
                    google_user_id=google_key,
                    is_active=True,
                )
        else:
            temp_email = _make_temp_email("google", google_sub)
            existing_user = CustomerUser.objects.filter(email=temp_email).first()
            if existing_user:
                customer_user = _restore_customer_user(
                    existing_user,
                    email=temp_email,
                    google_user_id=google_key,
                )
            else:
                customer_user = CustomerUser.objects.create(
                    email=temp_email,
                    google_user_id=google_key,
                    is_active=True,
                )
    else:
        customer_user = _restore_customer_user(customer_user, google_user_id=google_key)

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

    store_user = StoreUser.objects.filter(google_user_id=google_key).first()

    if store_user is None and email:
        store_user = StoreUser.objects.filter(email=email).first()
        if store_user:
            if store_user.google_user_id and store_user.google_user_id != google_key:
                messages.error(request, "このGoogleアカウントは別の店舗アカウントに連携されています。")
                return redirect("store_login")

            store_user = _restore_store_user(
                store_user,
                email=email,
                google_user_id=google_key,
            )

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

    if StoreUser.objects.filter(store_name=store_name, is_deleted=False).exists():
        messages.error(request, "この店舗名はすでに使用されています。")
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

    with transaction.atomic():
        existing_by_google = StoreUser.objects.filter(google_user_id=google_key).first()
        if existing_by_google and not existing_by_google.is_deleted:
            messages.error(request, "このGoogleアカウントは既に店舗アカウントに登録されています。ログインしてください。")
            return redirect("store_login")

        existing_by_email = StoreUser.objects.filter(email=email).first()
        existing_by_store_name = StoreUser.objects.filter(store_name=store_name).first()

        if existing_by_store_name and not existing_by_store_name.is_deleted:
            target = existing_by_email or existing_by_google
            if not target or existing_by_store_name.pk != target.pk:
                messages.error(request, "この店舗名はすでに使用されています。")
                return redirect("store_register")

        if existing_by_email:
            user = _restore_store_user(
                existing_by_email,
                email=email,
                store_name=store_name,
                google_user_id=google_key,
            )
        elif existing_by_google:
            user = _restore_store_user(
                existing_by_google,
                email=email,
                store_name=store_name,
                google_user_id=google_key,
            )
        else:
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


def _build_line_auth_url(redirect_uri, state):
    params = {
        "response_type": "code",
        "client_id": settings.LINE_CHANNEL_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "profile",
    }
    return "https://access.line.me/oauth2/v2.1/authorize?" + urlencode(params)


def _fetch_line_profile(code, redirect_uri):
    token_url = "https://api.line.me/oauth2/v2.1/token"
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": settings.LINE_CHANNEL_ID,
        "client_secret": settings.LINE_CHANNEL_SECRET,
    }

    token_response = requests.post(token_url, data=token_data, timeout=15)
    token_response.raise_for_status()
    token_json = token_response.json()

    access_token = token_json.get("access_token")
    if not access_token:
        raise ValueError("LINEアクセストークンを取得できませんでした。")

    profile_response = requests.get(
        "https://api.line.me/v2/profile",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    profile_response.raise_for_status()
    return profile_response.json()


def store_line_login_start(request):
    state = secrets.token_urlsafe(32)

    print("=== LINE store login start ===")
    print("session_key(before) =", request.session.session_key)
    print("state =", state)
    print("redirect_uri =", settings.STORE_LINE_REDIRECT_URI)
    print("host =", request.get_host())
    print("is_secure =", request.is_secure())

    request.session["store_line_login_state"] = state
    request.session.save()

    auth_url = _build_line_auth_url(settings.STORE_LINE_REDIRECT_URI, state)
    return redirect(auth_url)


def store_line_login_callback(request):
    error = request.GET.get("error")
    if error:
        messages.error(request, "LINEログインがキャンセルされたか、エラーが発生しました。")
        return redirect("store_login")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("store_line_login_state")

    if not code or not state or not session_state or state != session_state:
        messages.error(request, "LINEログインの認証状態を確認できませんでした。")
        return redirect("store_login")

    try:
        profile = _fetch_line_profile(code, settings.STORE_LINE_REDIRECT_URI)
    except (requests.RequestException, ValueError):
        messages.error(request, "LINEとの通信に失敗しました。時間をおいて再度お試しください。")
        return redirect("store_login")

    line_user_id = profile.get("userId")
    if not line_user_id:
        messages.error(request, "LINEユーザー情報を取得できませんでした。")
        return redirect("store_login")

    store_user = StoreUser.objects.filter(line_user_id=line_user_id).first()

    request.session.pop("store_line_login_state", None)

    if not store_user:
        messages.error(request, "このLINEアカウントは店舗アカウントに登録されていません。新規アカウント作成をしてください。")
        return redirect("store_register")

    if store_user.is_deleted:
        messages.error(request, "退会済みアカウントです。新規登録画面から再登録してください。")
        return redirect("store_register")

    login(request, store_user)
    return redirect("store_dashboard")


def store_line_register_start(request):
    if request.method != "POST":
        return redirect("store_register")

    store_name = request.POST.get("store_name", "").strip()

    if not store_name:
        messages.error(request, "店舗名を入力してください。")
        return redirect("store_register")

    if StoreUser.objects.filter(store_name=store_name, is_deleted=False).exists():
        messages.error(request, "この店舗名はすでに使用されています。")
        return redirect("store_register")

    state = secrets.token_urlsafe(32)

    print("=== LINE store register start ===")
    print("session_key(before) =", request.session.session_key)
    print("state =", state)
    print("store_name =", store_name)
    print("redirect_uri =", settings.STORE_LINE_REGISTER_REDIRECT_URI)
    print("host =", request.get_host())
    print("is_secure =", request.is_secure())

    request.session["store_line_register_state"] = state
    request.session["pending_store_line_register_store_name"] = store_name
    request.session.save()

    auth_url = _build_line_auth_url(settings.STORE_LINE_REGISTER_REDIRECT_URI, state)
    return redirect(auth_url)


def store_line_register_callback(request):
    error = request.GET.get("error")

    print("=== LINE store register callback ===")
    print("code =", request.GET.get("code"))
    print("state =", request.GET.get("state"))
    print("session_state =", request.session.get("store_line_register_state"))
    print("session_key =", request.session.session_key)
    print("full_path =", request.get_full_path())

    if error:
        messages.error(request, "LINE認証がキャンセルされたか、エラーが発生しました。")
        return redirect("store_register")

    code = request.GET.get("code")
    state = request.GET.get("state")
    session_state = request.session.get("store_line_register_state")
    store_name = request.session.get("pending_store_line_register_store_name")

    if not code or not state or not session_state or state != session_state:
        messages.error(request, "LINE認証の状態を確認できませんでした。")
        return redirect("store_register")

    if not store_name:
        messages.error(request, "店舗名の入力からやり直してください。")
        return redirect("store_register")

    try:
        profile = _fetch_line_profile(code, settings.STORE_LINE_REGISTER_REDIRECT_URI)
    except (requests.RequestException, ValueError):
        messages.error(request, "LINEとの通信に失敗しました。時間をおいて再度お試しください。")
        return redirect("store_register")

    line_user_id = profile.get("userId")
    if not line_user_id:
        messages.error(request, "LINEユーザー情報を取得できませんでした。")
        return redirect("store_register")

    temp_email = _make_temp_email("store_line", line_user_id)

    with transaction.atomic():
        existing_by_line = StoreUser.objects.filter(line_user_id=line_user_id).first()
        if existing_by_line and not existing_by_line.is_deleted:
            messages.error(request, "このLINEアカウントは既に店舗アカウントに登録されています。ログインしてください。")
            return redirect("store_login")

        existing_by_email = StoreUser.objects.filter(email=temp_email).first()
        existing_by_store_name = StoreUser.objects.filter(store_name=store_name).first()

        if existing_by_store_name and not existing_by_store_name.is_deleted:
            target = existing_by_email or existing_by_line
            if not target or existing_by_store_name.pk != target.pk:
                messages.error(request, "この店舗名はすでに使用されています。")
                return redirect("store_register")

        if existing_by_email:
            user = _restore_store_user(
                existing_by_email,
                email=temp_email,
                store_name=store_name,
                line_user_id=line_user_id,
            )
        elif existing_by_line:
            user = _restore_store_user(
                existing_by_line,
                email=temp_email,
                store_name=store_name,
                line_user_id=line_user_id,
            )
        else:
            user = StoreUser.objects.create_user(
                email=temp_email,
                store_name=store_name,
            )
            user.line_user_id = line_user_id
            user.save(update_fields=["line_user_id"])

    request.session.pop("store_line_register_state", None)
    request.session.pop("pending_store_line_register_store_name", None)

    login(request, user)
    return redirect("store_dashboard")


def _deactivate_customer_assets(customer_user):
    CustomerStampCard.objects.filter(customer=customer_user).delete()
    StampGrantLog.objects.filter(customer=customer_user).delete()
    RewardCoupon.objects.filter(customer=customer_user).delete()


def _deactivate_store_assets(store_user):
    store_cards = StampCard.objects.filter(store_user=store_user)

    CustomerStampCard.objects.filter(stamp_card__store_user=store_user).delete()
    StampGrantLog.objects.filter(store_user=store_user).delete()
    RewardCoupon.objects.filter(stamp_card__store_user=store_user).delete()
    store_cards.delete()


@customer_login_required
def customer_delete_confirm_view(request):
    customer_user = request.customer_user

    if request.method == "POST":
        with transaction.atomic():
            _deactivate_customer_assets(customer_user)

            customer_user.is_deleted = True
            customer_user.deleted_at = timezone.now()
            customer_user.is_active = False
            customer_user.save(update_fields=["is_deleted", "deleted_at", "is_active"])

        logout_customer(request)
        messages.success(request, "退会処理が完了しました。")
        return redirect("customer_login")

    return render(request, "accounts/customer_delete_confirm.html")


def store_delete_confirm_view(request):
    if not request.user.is_authenticated:
        return redirect("store_login")

    store_user = request.user

    if request.method == "POST":
        with transaction.atomic():
            _deactivate_store_assets(store_user)

            store_user.is_deleted = True
            store_user.deleted_at = timezone.now()
            store_user.is_active = False
            store_user.save(update_fields=["is_deleted", "deleted_at", "is_active"])

        logout(request)
        messages.success(request, "退会処理が完了しました。")
        return redirect("store_login")

    return render(request, "accounts/store_delete_confirm.html")