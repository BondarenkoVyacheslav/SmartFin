from rest_framework import serializers

from configuration import models


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.CustomUser
        fields = ('id', 'username', 'email', 'phone_number',)


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.AssetType
        fields = ('id', 'name', 'description')


class AssetSerializer(serializers.ModelSerializer):
    asset_type = AssetTypeSerializer()

    class Meta:
        model = models.Asset
        fields = ('id', 'name', 'symbol', 'asset_type')


class PortfolioSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = models.Portfolio
        fields = ('id', 'user', 'name', 'created_at')


class PortfolioAssetSerializer(serializers.ModelSerializer):
    asset = AssetSerializer()
    portfolio = PortfolioSerializer()

    class Meta:
        model = models.PortfolioAsset
        fields = ('id', 'portfolio', 'asset', 'quantity', 'avg_buy_price', 'update_at')


class TransactionSerializer(serializers.ModelSerializer):
    asset = AssetSerializer()
    portfolio = PortfolioSerializer()

    class Meta:
        model = models.Transaction
        fields = ('id', 'portfolio', 'asset', 'transaction_type', 'amount', 'price', 'created_at')
