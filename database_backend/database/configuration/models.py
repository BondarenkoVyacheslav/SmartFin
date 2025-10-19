from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=12, blank=True, null=True)

    def __str__(self):
        return self.username


User = get_user_model()


class AssetType(models.Model):
    """Тип актива (крипта, акции, облигации, недвижимость и т.д.)"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Тип актива"
        verbose_name_plural = "Тип активов"

    def __str__(self):
        return self.name


class Asset(models.Model):
    """Справочник всех возможных активов"""
    name = models.CharField(max_length=255)
    symbol = models.CharField(max_length=30, blank=True, null=True)
    asset_type = models.ForeignKey(AssetType, on_delete=models.CASCADE, related_name="assets")

    class Meta:
        verbose_name = "Актив"
        verbose_name_plural = "Активы"

    def __str__(self):
        return f"{self.name} ({self.symbol or self.asset_type})"


class Portfolio(models.Model):
    """Портфель конкретного пользователя"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="portfolios")
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Портфель"
        verbose_name_plural = "Портфели"

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class PortfolioAsset(models.Model):
    """Связка между портфелем и активом"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="in_portfolios")
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="assets")
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    avg_buy_price = models.DecimalField(max_digits=20, decimal_places=8)
    update_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Актив в портфеле"
        verbose_name_plural = "Активы в портфеле"
        unique_together = ('portfolio', 'asset')

    def __str__(self):
        return f"{self.portfolio.name} {self.asset.name}"


class Transaction(models.Model):
    """История операций с активами"""
    TRANSACTION_TYPES = [
        ("buy", "Покупка"),
        ("sell", "Продажа"),
    ]

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="transactions")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=20, decimal_places=8)
    price = models.DecimalField(max_digits=20, decimal_places=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"

    def __str__(self):
        return f"{self.transaction_type.upper()} {self.asset.symbol or self.asset.name}"
