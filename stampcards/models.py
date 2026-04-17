from django.db import models
from django.conf import settings
from django.utils import timezone



class StampCard(models.Model):
    store_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stamp_cards'
    )
    title = models.CharField(max_length=100, verbose_name='カード名')
    required_stamps = models.PositiveIntegerField(verbose_name='必要スタンプ数')
    reward_name = models.CharField(max_length=100, verbose_name='特典名')
    description = models.TextField(blank=True, verbose_name='説明')
    is_active = models.BooleanField(default=True, verbose_name='有効')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'スタンプカード'
        verbose_name_plural = 'スタンプカード'

    def __str__(self):
        return f"{self.title} ({self.store_user.store_name})"

class CustomerStampCard(models.Model):
    customer = models.ForeignKey(
        'accounts.CustomerUser',
        on_delete=models.CASCADE,
        related_name='customer_stamp_cards'
    )
    stamp_card = models.ForeignKey(
        StampCard,
        on_delete=models.CASCADE,
        related_name='customer_stamp_cards'
    )
    current_stamps = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('customer', 'stamp_card')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.customer.email} - {self.stamp_card.title}"


class StampGrantLog(models.Model):
    customer = models.ForeignKey(
        'accounts.CustomerUser',
        on_delete=models.CASCADE,
        related_name='stamp_grant_logs'
    )
    stamp_card = models.ForeignKey(
        StampCard,
        on_delete=models.CASCADE,
        related_name='stamp_grant_logs'
    )
    store_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stamp_grant_logs'
    )
    grant_count = models.PositiveIntegerField(default=1)
    qr_payload = models.TextField(blank=True)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-granted_at']

    def __str__(self):
        return f"{self.customer.email} +{self.grant_count} ({self.stamp_card.title})"

class RewardCoupon(models.Model):
    STATUS_CHOICES = [
        ('available', '利用可能'),
        ('used', '使用済み'),
    ]

    customer = models.ForeignKey(
        'accounts.CustomerUser',
        on_delete=models.CASCADE,
        related_name='reward_coupons'
    )
    stamp_card = models.ForeignKey(
        'StampCard',
        on_delete=models.CASCADE,
        related_name='reward_coupons'
    )
    reward_name = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available'
    )

    issued_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.customer.email} - {self.reward_name} ({self.status})"