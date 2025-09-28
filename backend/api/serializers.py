from rest_framework import serializers
from . import models


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Currency
        fields = "__all__"


class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Exchange
        fields = "__all__"


class AppUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AppUser
        fields = "__all__"


class PortfolioSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Portfolio
        fields = "__all__"


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Asset
        fields = "__all__"


class AssetIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetIdentifier
        fields = "__all__"


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Transaction
        fields = "__all__"


class PriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Price
        fields = "__all__"


class FxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.FxRate
        fields = "__all__"


class IntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Integration
        fields = "__all__"


class AdviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Advice
        fields = "__all__"


