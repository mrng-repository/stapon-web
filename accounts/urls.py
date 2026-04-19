from django.urls import path
from .views import (
    store_login_view,
    store_register_view,
    otp_verify_view,
    store_dashboard_view,
    store_logout_view,
    customer_login_view,
    customer_otp_verify_view,
    customer_dashboard_view,
    customer_logout_view,
)
from . import views

urlpatterns = [
    path('login/', store_login_view, name='store_login'),
    path('register/', store_register_view, name='store_register'),
    path('otp/verify/', otp_verify_view, name='otp_verify'),
    path('dashboard/', store_dashboard_view, name='store_dashboard'),
    path('logout/', store_logout_view, name='store_logout'),
    path('customer/login/', customer_login_view, name='customer_login'),
    path('customer/otp/', customer_otp_verify_view, name='customer_otp_verify'),
    path('customer/dashboard/', customer_dashboard_view, name='customer_dashboard'),
    path('customer/logout/', customer_logout_view, name='customer_logout'),
    path("auth/line/login/", views.line_login_start, name="line_login_start"),
    path("auth/line/callback/", views.line_login_callback, name="line_login_callback"),
    path("auth/google/login/", views.google_login_start, name="google_login_start"),
    path("auth/google/callback/", views.google_login_callback, name="google_login_callback"),
    path("auth/google/store/login/", views.store_google_login_start, name="store_google_login_start"),
    path("auth/google/store/callback/", views.store_google_login_callback, name="store_google_login_callback"),
]