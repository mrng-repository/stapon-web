from django.urls import path
from . import views

urlpatterns = [
    path("", views.store_coupon_list_view, name="store_coupon_list"),
    path("create/", views.store_coupon_create_view, name="store_coupon_create"),
    path("<int:coupon_id>/edit/", views.store_coupon_edit_view, name="store_coupon_edit"),
    path("<int:coupon_id>/delete/", views.store_coupon_delete_view, name="store_coupon_delete"),
]