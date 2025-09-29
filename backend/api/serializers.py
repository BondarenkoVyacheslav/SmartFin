from rest_framework import serializers
from django.contrib.auth import get_user_model
from . import models

User = get_user_model()


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Currency
        fields = "__all__"


class ExchangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Exchange
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'base_currency', 'timezone', 'is_active', 'date_joined']
        read_only_fields = ['id', 'date_joined']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'password_confirm', 'first_name', 'last_name', 'base_currency', 'timezone']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


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


