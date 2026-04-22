from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .forms import StoreCouponForm
from .models import StoreCoupon


def store_coupon_list_view(request):
    if not request.user.is_authenticated:
        return redirect("store_login")

    store_user = request.user

    coupons = StoreCoupon.objects.filter(
        store=store_user,
        is_deleted=False
    ).order_by("-created_at")

    context = {
        "coupons": coupons,
    }
    return render(request, "coupons/store_coupon_list.html", context)


def store_coupon_create_view(request):
    if not request.user.is_authenticated:
        return redirect("store_login")

    store_user = request.user

    if request.method == "POST":
        form = StoreCouponForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.store = store_user
            coupon.save()
            messages.success(request, "通常クーポンを作成しました。")
            return redirect("store_coupon_list")
    else:
        form = StoreCouponForm()

    context = {
        "form": form,
        "page_title": "通常クーポン作成",
        "submit_label": "作成する",
    }
    return render(request, "coupons/store_coupon_form.html", context)


def store_coupon_edit_view(request, coupon_id):
    if not request.user.is_authenticated:
        return redirect("store_login")

    store_user = request.user

    coupon = get_object_or_404(
        StoreCoupon,
        id=coupon_id,
        store=store_user,
        is_deleted=False,
    )

    if request.method == "POST":
        form = StoreCouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, "通常クーポンを更新しました。")
            return redirect("store_coupon_list")
    else:
        form = StoreCouponForm(instance=coupon)

    context = {
        "form": form,
        "coupon": coupon,
        "page_title": "通常クーポン編集",
        "submit_label": "更新する",
    }
    return render(request, "coupons/store_coupon_form.html", context)


def store_coupon_delete_view(request, coupon_id):
    if not request.user.is_authenticated:
        return redirect("store_login")

    store_user = request.user

    coupon = get_object_or_404(
        StoreCoupon,
        id=coupon_id,
        store=store_user,
        is_deleted=False,
    )

    if request.method == "POST":
        coupon.soft_delete()
        messages.success(request, "通常クーポンを削除しました。")
        return redirect("store_coupon_list")

    context = {
        "coupon": coupon,
    }
    return render(request, "coupons/store_coupon_delete_confirm.html", context)