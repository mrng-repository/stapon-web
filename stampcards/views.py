import qrcode
import base64
from io import BytesIO
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from django.utils.safestring import mark_safe

from .models import StampCard, CustomerStampCard, StampGrantLog, RewardCoupon
from .forms import StampCardForm, StampGrantQRForm
from .qr_utils import (
    build_stamp_grant_payload,
    sign_stamp_grant_payload,
    unsign_stamp_grant_payload,
    build_stamp_grant_url,
)
from accounts.authentication import get_current_customer_user


@login_required(login_url='store_login')
def stampcard_list_create_view(request):
    active_tab = request.GET.get('tab', 'create')
    stampcards = StampCard.objects.filter(store_user=request.user)

    if request.method == 'POST':
        form = StampCardForm(request.POST)
        if form.is_valid():
            stampcard = form.save(commit=False)
            stampcard.store_user = request.user
            stampcard.save()
            messages.success(request, 'スタンプカードを作成しました。')
            return redirect(f"{reverse('stampcard_list_create')}?tab=list")
    else:
        form = StampCardForm()

    return render(
        request,
        'stampcards/stampcard_list_create.html',
        {
            'form': form,
            'stampcards': stampcards,
            'active_tab': active_tab,
        }
    )


@login_required(login_url='store_login')
def stampcard_edit_view(request, pk):
    stampcard = get_object_or_404(StampCard, pk=pk, store_user=request.user)

    if request.method == 'POST':
        form = StampCardForm(request.POST, instance=stampcard)
        if form.is_valid():
            form.save()
            messages.success(request, 'スタンプカードを更新しました。')
            return redirect(f"{reverse('stampcard_list_create')}?tab=list")
    else:
        form = StampCardForm(instance=stampcard)

    return render(
        request,
        'stampcards/stampcard_edit.html',
        {
            'form': form,
            'stampcard': stampcard,
        }
    )


@login_required(login_url='store_login')
def stampcard_delete_view(request, pk):
    stampcard = get_object_or_404(StampCard, pk=pk, store_user=request.user)

    if request.method == 'POST':
        stampcard.delete()
        messages.success(request, 'スタンプカードを削除しました。')
        return redirect(f"{reverse('stampcard_list_create')}?tab=list")

    return render(
        request,
        'stampcards/stampcard_delete_confirm.html',
        {
            'stampcard': stampcard,
        }
    )

@login_required(login_url='store_login')
def stampcard_qr_create_view(request):
    qr_url = None
    qr_image_base64 = None
    selected_card = None

    if request.method == 'POST':
        form = StampGrantQRForm(request.POST, store_user=request.user)
        if form.is_valid():
            stamp_card = form.cleaned_data['stamp_card']
            grant_count = form.cleaned_data['grant_count']
            expires_at = form.cleaned_data['expires_at']

            payload = build_stamp_grant_payload(
                store_user_id=request.user.id,
                stamp_card_id=stamp_card.id,
                grant_count=grant_count,
                expires_at=expires_at,
            )
            signed_token = sign_stamp_grant_payload(payload)
            qr_url = build_stamp_grant_url(request, signed_token)
            selected_card = stamp_card

            qr = qrcode.QRCode(
                version=1,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    else:
        form = StampGrantQRForm(store_user=request.user)

    return render(
        request,
        'stampcards/stampcard_qr_create.html',
        {
            'form': form,
            'qr_url': qr_url,
            'qr_image_base64': qr_image_base64,
            'selected_card': selected_card,
        }
    )


def customer_stamp_grant_view(request):
    token = request.GET.get('token')
    if not token:
        messages.error(request, 'QR情報が見つかりません。')
        return redirect('customer_login')

    customer_user = get_current_customer_user(request)
    if not customer_user:
        request.session['pending_stamp_token'] = token
        return redirect('customer_login')

    try:
        payload = unsign_stamp_grant_payload(token)
    except Exception:
        messages.error(request, 'QR情報が不正です。')
        return redirect('customer_stampcard_list')

    try:
        expires_at = datetime.fromisoformat(payload['expires_at'])
    except Exception:
        messages.error(request, 'QR情報の有効期限が不正です。')
        return redirect('customer_stampcard_list')

    if timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())

    if timezone.now() > expires_at:
        messages.error(request, 'このQRの有効期限は切れています。')
        return redirect('customer_stampcard_list')

    stamp_card = get_object_or_404(
        StampCard,
        id=payload['stamp_card_id'],
        store_user_id=payload['store_user_id'],
        is_active=True
    )

    grant_count = int(payload.get('grant_count', 1))

    customer_stamp_card, created = CustomerStampCard.objects.get_or_create(
        customer=customer_user,
        stamp_card=stamp_card,
        defaults={'current_stamps': 0}
    )

    customer_stamp_card.current_stamps += grant_count

    required = stamp_card.required_stamps
    reward_count = customer_stamp_card.current_stamps // required

    if reward_count > 0:
        customer_stamp_card.current_stamps = customer_stamp_card.current_stamps % required

        for _ in range(reward_count):
            RewardCoupon.objects.create(
                customer=customer_user,
                stamp_card=stamp_card,
                reward_name=stamp_card.reward_name,
            )

    customer_stamp_card.save()

    StampGrantLog.objects.create(
        customer=customer_user,
        stamp_card=stamp_card,
        store_user=stamp_card.store_user,
        grant_count=grant_count,
        qr_payload=str(payload),
    )

    messages.success(
        request,
        f'「{stamp_card.title}」にスタンプを {grant_count} 個付与しました。'
    )

    if reward_count > 0:
        coupon_url = reverse('customer_coupon_list')

        messages.success(
            request,
            mark_safe(
                f'特典クーポンを {reward_count} 枚発行しました。'
                f'<a href="{coupon_url}" style="margin-left:8px; color:#2563eb; font-weight:700;">確認する</a>'
            )
        )

    return redirect('customer_stampcard_detail', pk=customer_stamp_card.pk)