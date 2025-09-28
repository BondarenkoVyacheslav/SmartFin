# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Advice(models.Model):
    id = models.UUIDField(primary_key=True)
    portfolio = models.ForeignKey('Portfolio', models.DO_NOTHING)
    kind = models.TextField()
    message = models.TextField()
    score = models.DecimalField(max_digits=8, decimal_places=4, blank=True, null=True)
    payload = models.JSONField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'advice'


class AppUser(models.Model):
    id = models.UUIDField(primary_key=True)
    email = models.TextField(unique=True)  # This field type is a guess.
    password_hash = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    twofa_secret = models.TextField(blank=True, null=True)
    base_currency = models.ForeignKey('Currency', models.DO_NOTHING, blank=True, null=True)
    timezone = models.TextField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = 'app_user'


class Asset(models.Model):
    id = models.UUIDField(primary_key=True)
    class_field = models.TextField(db_column='class')  # Field renamed because it was a Python reserved word. This field type is a guess.
    symbol = models.TextField()
    name = models.TextField()
    trading_currency = models.ForeignKey('Currency', models.DO_NOTHING, blank=True, null=True)
    isin = models.TextField(blank=True, null=True)
    exchange = models.ForeignKey('Exchange', models.DO_NOTHING, blank=True, null=True)
    metadata = models.JSONField()
    is_active = models.BooleanField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'asset'
        unique_together = (('symbol', 'exchange'),)


class AssetIdentifier(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey(Asset, models.DO_NOTHING)
    id_type = models.TextField()
    id_value = models.TextField()

    class Meta:
        db_table = 'asset_identifier'
        unique_together = (('id_type', 'id_value'), ('asset', 'id_type'),)


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(AppUser, models.DO_NOTHING, blank=True, null=True)
    ts = models.DateTimeField()
    action = models.TextField()
    target_type = models.TextField(blank=True, null=True)
    target_id = models.UUIDField(blank=True, null=True)
    ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    details = models.JSONField()

    class Meta:
        db_table = 'audit_log'


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class Currency(models.Model):
    id = models.UUIDField(primary_key=True)
    code = models.TextField(unique=True)
    name = models.TextField()
    decimals = models.IntegerField()
    is_crypto = models.BooleanField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'currency'


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.SmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


class Exchange(models.Model):
    id = models.UUIDField(primary_key=True)
    code = models.TextField(unique=True)
    name = models.TextField()
    country = models.TextField(blank=True, null=True)
    timezone = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'exchange'


class FxRate(models.Model):
    id = models.UUIDField(primary_key=True)
    base_currency = models.ForeignKey(Currency, models.DO_NOTHING)
    quote_currency = models.ForeignKey(Currency, models.DO_NOTHING, related_name='fxrate_quote_currency_set')
    ts = models.DateTimeField()
    rate = models.DecimalField(max_digits=38, decimal_places=10)
    source = models.TextField()

    class Meta:
        db_table = 'fx_rate'
        unique_together = (('base_currency', 'quote_currency', 'ts', 'source'),)


class Integration(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(AppUser, models.DO_NOTHING)
    provider = models.TextField()
    display_name = models.TextField()
    status = models.TextField()
    credentials_encrypted = models.TextField()
    last_sync_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = 'integration'
        unique_together = (('user', 'provider', 'display_name'),)


class Portfolio(models.Model):
    id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(AppUser, models.DO_NOTHING)
    name = models.TextField()
    base_currency = models.ForeignKey(Currency, models.DO_NOTHING)
    settings = models.JSONField()
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = 'portfolio'
        unique_together = (('user', 'name'),)


class Price(models.Model):
    id = models.UUIDField(primary_key=True)
    asset = models.ForeignKey(Asset, models.DO_NOTHING)
    ts = models.DateTimeField()
    price = models.DecimalField(max_digits=38, decimal_places=10)
    currency = models.ForeignKey(Currency, models.DO_NOTHING)
    source = models.TextField()
    interval = models.TextField()  # This field type is a guess.
    metadata = models.JSONField()
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'price'
        unique_together = (('asset', 'ts', 'source', 'interval'),)


class Transaction(models.Model):
    id = models.UUIDField(primary_key=True)
    portfolio = models.ForeignKey(Portfolio, models.DO_NOTHING)
    asset = models.ForeignKey(Asset, models.DO_NOTHING)
    tx_type = models.TextField()  # This field type is a guess.
    tx_time = models.DateTimeField()
    quantity = models.DecimalField(max_digits=38, decimal_places=18)
    price = models.DecimalField(max_digits=38, decimal_places=10, blank=True, null=True)
    price_currency = models.ForeignKey(Currency, models.DO_NOTHING, blank=True, null=True)
    fee = models.DecimalField(max_digits=38, decimal_places=10)
    notes = models.TextField(blank=True, null=True)
    metadata = models.JSONField()
    linked_tx = models.ForeignKey('self', models.DO_NOTHING, blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = 'transaction'
