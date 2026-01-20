from django.db import models
from app.portfolio.models import Portfolio


class Exchange(models.Model):
    KIND_EXCHANGE = "exchange"
    KIND_BROKER = "broker"
    KIND_WALLET = "wallet"
    KIND_BLOCKCHAIN = "blockchain"

    KIND_CHOICES = [
        (KIND_EXCHANGE, "Exchange"),
        (KIND_BROKER, "Broker"),
        (KIND_WALLET, "Wallet"),
        (KIND_BLOCKCHAIN, "Blockchain"),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_EXCHANGE)


class Integration(models.Model):
    key = models.CharField(max_length=50)
    api_key = models.CharField(max_length=255, blank=True, null=True)
    api_secret = models.CharField(max_length=255, blank=True, null=True)
    passphrase = models.CharField(max_length=255, blank=True, null=True)
    token = models.TextField(blank=True, null=True)
    access_token = models.TextField(blank=True, null=True)
    refresh_token = models.TextField(blank=True, null=True)
    secret = models.TextField(blank=True, null=True)
    client_id = models.CharField(max_length=255, blank=True, null=True)
    account_id = models.CharField(max_length=255, blank=True, null=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)
    refresh_expires_at = models.DateTimeField(blank=True, null=True)
    extra_params = models.JSONField(default=dict, blank=True)
    portfolio_id = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    exchange_id = models.ForeignKey(Exchange, on_delete=models.CASCADE)


class WalletAddress(models.Model):
    portfolio_id = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    integration_id = models.ForeignKey(Integration, on_delete=models.CASCADE, blank=True, null=True)
    network = models.CharField(max_length=64)
    address = models.CharField(max_length=255)
    tag = models.CharField(max_length=255, blank=True, null=True)
    label = models.CharField(max_length=255, blank=True, null=True)
    asset_symbol = models.CharField(max_length=32, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    extra_params = models.JSONField(default=dict, blank=True)
