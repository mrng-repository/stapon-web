from django.urls import path
from .views import (
    customer_stampcard_list_view,
    customer_stampcard_detail_view,
    customer_coupon_list_view,
    customer_coupon_detail_view,
    customer_coupon_present_view,
    customer_coupon_use_view,
)

urlpatterns = [
    path('', customer_stampcard_list_view, name='customer_stampcard_list'),
    path('<int:pk>/', customer_stampcard_detail_view, name='customer_stampcard_detail'),
    path('coupons/', customer_coupon_list_view, name='customer_coupon_list'),
    
    path('coupons/<int:pk>/', customer_coupon_detail_view, name='customer_coupon_detail'),
    path('coupons/<int:pk>/present/', customer_coupon_present_view, name='customer_coupon_present'),
    path('coupons/<int:pk>/use/', customer_coupon_use_view, name='customer_coupon_use'),
]