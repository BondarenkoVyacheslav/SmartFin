from django.shortcuts import render
from rest_framework.viewsets import ModelViewSet
from rest_framework.generics import ListAPIView

from configuration import serializers, models


class UserViewSet(ModelViewSet):
    serializer_class = serializers.UserSerializer
    queryset = models.CustomUser.objects.all()


class AssetTypeViewSet(ModelViewSet):
    serializer_class = serializers.AssetTypeSerializer
    queryset = models.AssetType.objects.all()


class AssetViewSet(ModelViewSet):
    serializer_class = serializers.AssetSerializer
    queryset = models.Asset.objects.all().prefetch_related('asset_type')


class PortfolioViewSet(ModelViewSet):
    serializer_class = serializers.PortfolioSerializer
    queryset = models.Portfolio.objects.all().prefetch_related('user')


class PortfolioAssetViewSet(ModelViewSet):
    serializer_class = serializers.PortfolioAssetSerializer
    queryset = models.PortfolioAsset.objects.all().prefetch_related('asset', 'portfolio')

    def get_queryset(self):
        queryset = super().get_queryset()
        portfolio_id = self.request.query_params.get('portfolio_id')
        if portfolio_id:
            queryset = queryset.filter(portfolio_id=portfolio_id)
        return queryset


class TransactionViewSet(ModelViewSet):
    serializer_class = serializers.TransactionSerializer
    queryset = models.Transaction.objects.all().prefetch_related('asset', 'portfolio')

    #проверить как будет приходить postfolio_id из другого сервиса