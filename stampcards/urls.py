from django.urls import path
from .views import (
    stampcard_list_create_view,
    stampcard_edit_view,
    stampcard_delete_view,
    stampcard_qr_create_view,
    customer_stamp_grant_view,
)

urlpatterns = [
    path('', stampcard_list_create_view, name='stampcard_list_create'),
    path('<int:pk>/edit/', stampcard_edit_view, name='stampcard_edit'),
    path('<int:pk>/delete/', stampcard_delete_view, name='stampcard_delete'),
    path('qr/create/', stampcard_qr_create_view, name='stampcard_qr_create'),
    path('grant/', customer_stamp_grant_view, name='customer_stamp_grant'),
]