# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid


class User(AbstractUser):
    """Custom user model that extends Django's AbstractUser with additional fields"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Keep email as unique and required
    email = models.EmailField(unique=True)
    # Additional fields from AppUser
    base_currency = models.ForeignKey('Currency', models.SET_NULL, blank=True, null=True)
    timezone = models.CharField(max_length=100, default='UTC')
    twofa_secret = models.CharField(max_length=255, blank=True, null=True)

    # Override username to make it optional (we'll use email as primary identifier)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)

    # Use email as the username field for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        pass
    
    def save(self, *args, **kwargs):
        # Auto-generate username from email if not provided
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)


class Advice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    portfolio = models.ForeignKey('Portfolio', models.CASCADE)
    kind = models.TextField()
    message = models.TextField()
    score = models.DecimalField(max_digits=8, decimal_places=4, blank=True, null=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'advice'


class Asset(models.Model):
    ASSET_CLASS_CHOICES = [
        ('stock', 'Stock'),
        ('bond', 'Bond'),
        ('fund', 'Fund'),
        ('crypto', 'Cryptocurrency'),
        ('fiat', 'Fiat Currency'),
        ('metal', 'Precious Metal'),
        ('cash', 'Cash'),
        ('deposit', 'Deposit'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    class_field = models.CharField(max_length=20, choices=ASSET_CLASS_CHOICES, db_column='class', default='other')
    symbol = models.TextField()
    name = models.TextField()
    trading_currency = models.ForeignKey('Currency', models.CASCADE, blank=True, null=True)
    isin = models.TextField(blank=True, null=True)
    exchange = models.ForeignKey('Exchange', models.CASCADE, blank=True, null=True)
    metadata = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'asset'
        unique_together = (('symbol', 'exchange'),)


class AssetIdentifier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    asset = models.ForeignKey(Asset, models.CASCADE)
    id_type = models.TextField()
    id_value = models.TextField()

    class Meta:
        db_table = 'asset_identifier'
        unique_together = (('id_type', 'id_value'), ('asset', 'id_type'),)


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.SET_NULL, blank=True, null=True)
    ts = models.DateTimeField(auto_now_add=True)
    action = models.TextField()
    target_type = models.TextField(blank=True, null=True)
    target_id = models.UUIDField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    details = models.JSONField(default=dict)

    class Meta:
        db_table = 'audit_log'



class Currency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    code = models.TextField(unique=True)
    name = models.TextField()
    decimals = models.IntegerField(default=2)
    is_crypto = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'currency'




class Exchange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    code = models.TextField(unique=True)
    name = models.TextField()
    country = models.TextField(blank=True, null=True)
    timezone = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'exchange'


class FxRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    base_currency = models.ForeignKey(Currency, models.CASCADE, related_name='base_fx_rates')
    quote_currency = models.ForeignKey(Currency, models.CASCADE, related_name='quote_fx_rates')
    ts = models.DateTimeField()
    rate = models.DecimalField(max_digits=38, decimal_places=10)
    source = models.TextField()

    class Meta:
        db_table = 'fx_rate'
        unique_together = (('base_currency', 'quote_currency', 'ts', 'source'),)


class Integration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)
    provider = models.TextField()
    display_name = models.TextField()
    status = models.TextField(default='active')
    credentials_encrypted = models.TextField()
    last_sync_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'integration'
        unique_together = (('user', 'provider', 'display_name'),)


class Portfolio(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, models.CASCADE)
    name = models.TextField()
    base_currency = models.ForeignKey(Currency, models.CASCADE)
    settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portfolio'
        unique_together = (('user', 'name'),)


class Price(models.Model):
    PRICE_INTERVAL_CHOICES = [
        ('tick', 'Tick'),
        ('min', 'Minute'),
        ('hour', 'Hour'),
        ('day', 'Day'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    asset = models.ForeignKey(Asset, models.CASCADE)
    ts = models.DateTimeField()
    price = models.DecimalField(max_digits=38, decimal_places=10)
    currency = models.ForeignKey(Currency, models.CASCADE)
    source = models.TextField()
    interval = models.CharField(max_length=10, choices=PRICE_INTERVAL_CHOICES, default='day')
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'price'
        unique_together = (('asset', 'ts', 'source', 'interval'),)


class Transaction(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('transfer_in', 'Transfer In'),
        ('transfer_out', 'Transfer Out'),
        ('dividend', 'Dividend'),
        ('coupon', 'Coupon'),
        ('interest', 'Interest'),
        ('fee', 'Fee'),
        ('split', 'Split'),
        ('merge', 'Merge'),
        ('adjustment', 'Adjustment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    portfolio = models.ForeignKey(Portfolio, models.CASCADE)
    asset = models.ForeignKey(Asset, models.CASCADE)
    tx_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='buy')
    tx_time = models.DateTimeField()
    quantity = models.DecimalField(max_digits=38, decimal_places=18, default=0)
    price = models.DecimalField(max_digits=38, decimal_places=10, blank=True, null=True)
    price_currency = models.ForeignKey(Currency, models.CASCADE, blank=True, null=True)
    fee = models.DecimalField(max_digits=38, decimal_places=10, default=0)
    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict)
    linked_tx = models.ForeignKey('self', models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transaction'
