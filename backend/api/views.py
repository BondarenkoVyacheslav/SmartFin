from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
try:
    from rest_framework_simplejwt.tokens import RefreshToken
except Exception:  # simplejwt may be absent in some envs
    RefreshToken = None
from .models import Currency, Exchange, AppUser, Portfolio, Asset, AssetIdentifier, Transaction, Price, FxRate, Integration, Advice
from .serializers import (
	CurrencySerializer,
	ExchangeSerializer,
	AppUserSerializer,
	PortfolioSerializer,
	AssetSerializer,
	AssetIdentifierSerializer,
	TransactionSerializer,
	PriceSerializer,
	FxRateSerializer,
	IntegrationSerializer,
	AdviceSerializer,
)


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Currency.objects.all().order_by('code')
	serializer_class = CurrencySerializer


class ExchangeViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Exchange.objects.all().order_by('code')
	serializer_class = ExchangeSerializer


class AppUserViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = AppUser.objects.all().order_by('created_at')
	serializer_class = AppUserSerializer


class PortfolioViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Portfolio.objects.all().order_by('created_at')
	serializer_class = PortfolioSerializer


class AssetViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Asset.objects.all().order_by('symbol')
	serializer_class = AssetSerializer


class AssetIdentifierViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = AssetIdentifier.objects.all().order_by('id_type')
	serializer_class = AssetIdentifierSerializer


class TransactionViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Transaction.objects.all().order_by('-tx_time')
	serializer_class = TransactionSerializer


class PriceViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Price.objects.select_related('asset', 'currency').all().order_by('-ts')
	serializer_class = PriceSerializer
	filterset_fields = ['asset', 'currency', 'source', 'interval']
	ordering_fields = ['ts', 'price']
	search_fields = []


class FxRateViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = FxRate.objects.select_related('base_currency', 'quote_currency').all().order_by('-ts')
	serializer_class = FxRateSerializer
	filterset_fields = ['base_currency', 'quote_currency', 'source']
	ordering_fields = ['ts', 'rate']
	search_fields = []


class IntegrationViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Integration.objects.all().order_by('-created_at')
	serializer_class = IntegrationSerializer


class AdviceViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Advice.objects.all().order_by('-created_at')
	serializer_class = AdviceSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if RefreshToken is None:
            return Response({"detail": "JWT not available"}, status=status.HTTP_501_NOT_IMPLEMENTED)
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"detail": "Missing refresh token"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Logged out"})
