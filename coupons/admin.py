from django.contrib import admin
from .models import StoreCoupon


@admin.register(StoreCoupon)
class StoreCouponAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "store",
        "discount_type",
        "discount_value",
        "is_public",
        "is_active",
        "is_deleted",
        "created_at",
    )
    list_filter = ("discount_type", "is_public", "is_active", "is_deleted")
    search_fields = ("title", "description", "store__store_name")