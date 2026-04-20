from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from datetime import timedelta


class StoreUserManager(BaseUserManager):
    def create_user(self, email, store_name, password=None, **extra_fields):
        if not email:
            raise ValueError('メールアドレスは必須です')
        email = self.normalize_email(email)
        user = self.model(email=email, store_name=store_name, **extra_fields)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, store_name='Admin', password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        user = self.create_user(email=email, store_name=store_name, **extra_fields)
        if password:
            user.set_password(password)
            user.save(using=self._db)
        return user


class StoreUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    store_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    google_user_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    line_user_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    objects = StoreUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['store_name']

    def __str__(self):
        return f"{self.store_name} ({self.email})"


class EmailOTP(models.Model):
    PURPOSE_CHOICES = [
        ('login', 'ログイン'),
        ('register', '新規登録'),
    ]

    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    @classmethod
    def default_expiry(cls):
        return timezone.now() + timedelta(minutes=10)

    def __str__(self):
        return f"{self.email} - {self.purpose}"
    
class CustomerUser(models.Model):
    email = models.EmailField(unique=True)
    line_user_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    google_user_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    display_name = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class CustomerEmailOTP(models.Model):
    email = models.EmailField()
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, default='login')
    is_used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expires_at