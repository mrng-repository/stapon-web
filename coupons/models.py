from django.db import models
from django.utils import timezone
from accounts.models import StoreUser


class StoreCoupon(models.Model):
    DISCOUNT_TYPE_AMOUNT = "amount"
    DISCOUNT_TYPE_PERCENT = "percent"
    DISCOUNT_TYPE_FREE = "free"

    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_TYPE_AMOUNT, "金額値引き"),
        (DISCOUNT_TYPE_PERCENT, "割引率"),
        (DISCOUNT_TYPE_FREE, "無料"),
    ]

    store = models.ForeignKey(
        StoreUser,
        on_delete=models.CASCADE,
        related_name="store_coupons",
        verbose_name="店舗ユーザー",
    )
    title = models.CharField("クーポン名", max_length=100)
    description = models.TextField("説明", blank=True)
    discount_type = models.CharField(
        "割引種別",
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
    )
    discount_value = models.PositiveIntegerField(
        "割引値",
        null=True,
        blank=True,
        help_text="金額値引きなら金額、割引率なら%を入力。無料の場合は空でOKです。",
    )
    start_at = models.DateTimeField("利用開始日時")
    end_at = models.DateTimeField("利用終了日時")
    usage_note = models.TextField("利用条件メモ", blank=True)

    is_public = models.BooleanField("公開状態", default=True)
    is_active = models.BooleanField("有効状態", default=True)

    is_deleted = models.BooleanField("削除済み", default=False)
    deleted_at = models.DateTimeField("削除日時", null=True, blank=True)

    created_at = models.DateTimeField("作成日時", auto_now_add=True)
    updated_at = models.DateTimeField("更新日時", auto_now=True)

    class Meta:
        verbose_name = "通常クーポン"
        verbose_name_plural = "通常クーポン"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def is_available_now(self):
        now = timezone.now()
        return (
            not self.is_deleted
            and self.is_active
            and self.start_at <= now <= self.end_at
        )

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])