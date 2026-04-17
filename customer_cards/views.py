from django.shortcuts import render, get_object_or_404, redirect
from accounts.decorators import customer_login_required
from stampcards.models import CustomerStampCard, RewardCoupon
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta


@customer_login_required
def customer_stampcard_list_view(request):
    customer_stampcards = CustomerStampCard.objects.filter(
        customer=request.customer_user
    ).select_related('stamp_card', 'stamp_card__store_user')

    return render(
        request,
        'customer_cards/customer_stampcard_list.html',
        {
            'customer_user': request.customer_user,
            'customer_stampcards': customer_stampcards,
        }
    )


@customer_login_required
def customer_stampcard_detail_view(request, pk):
    customer_stampcard = get_object_or_404(
        CustomerStampCard.objects.select_related('stamp_card', 'stamp_card__store_user'),
        pk=pk,
        customer=request.customer_user
    )

    required_stamps = customer_stampcard.stamp_card.required_stamps
    current_stamps = customer_stampcard.current_stamps
    remaining_stamps = max(required_stamps - current_stamps, 0)

    return render(
        request,
        'customer_cards/customer_stampcard_detail.html',
        {
            'customer_user': request.customer_user,
            'customer_stampcard': customer_stampcard,
            'required_stamps': required_stamps,
            'current_stamps': current_stamps,
            'remaining_stamps': remaining_stamps,
        }
    )

@customer_login_required
def customer_coupon_list_view(request):
    available_coupons = RewardCoupon.objects.filter(
        customer=request.customer_user,
        status='available'
    ).select_related(
        'stamp_card',
        'stamp_card__store_user'
    ).order_by('-issued_at')

    threshold = timezone.now() - timedelta(hours=1)

    used_coupons = RewardCoupon.objects.filter(
        customer=request.customer_user,
        status='used',
        used_at__gte=threshold
    ).select_related(
        'stamp_card',
        'stamp_card__store_user'
    ).order_by('-used_at', '-issued_at')

    return render(
        request,
        'customer_cards/coupon_list.html',
        {
            'customer_user': request.customer_user,
            'available_coupons': available_coupons,
            'used_coupons': used_coupons,
        }
    )

@customer_login_required
def customer_coupon_detail_view(request, pk):
    coupon = get_object_or_404(
        RewardCoupon.objects.select_related('stamp_card', 'stamp_card__store_user'),
        pk=pk,
        customer=request.customer_user
    )

    return render(
        request,
        'customer_cards/coupon_detail.html',
        {
            'customer_user': request.customer_user,
            'coupon': coupon,
        }
    )


@customer_login_required
def customer_coupon_present_view(request, pk):
    coupon = get_object_or_404(
        RewardCoupon.objects.select_related('stamp_card', 'stamp_card__store_user'),
        pk=pk,
        customer=request.customer_user,
        status='available'
    )

    return render(
        request,
        'customer_cards/coupon_present.html',
        {
            'customer_user': request.customer_user,
            'coupon': coupon,
            'present_seconds': 60,
        }
    )


@customer_login_required
def customer_coupon_use_view(request, pk):
    coupon = get_object_or_404(
        RewardCoupon,
        pk=pk,
        customer=request.customer_user,
        status='available'
    )

    if request.method == 'POST':
        coupon.status = 'used'
        coupon.used_at = timezone.now()
        coupon.save()

        messages.success(request, f'「{coupon.reward_name}」を使用済みにしました。')
        return redirect('customer_coupon_list')

    return redirect('customer_coupon_detail', pk=coupon.pk)