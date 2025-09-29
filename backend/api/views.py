from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
try:
    from rest_framework_simplejwt.tokens import RefreshToken
except Exception:  # simplejwt may be absent in some envs
    RefreshToken = None
from django.contrib.auth import get_user_model
from .models import Currency, Exchange, Portfolio, Asset, AssetIdentifier, Transaction, Price, FxRate, Integration, Advice

User = get_user_model()
from .serializers import (
	CurrencySerializer,
	ExchangeSerializer,
	UserSerializer,
	UserRegistrationSerializer,
	PortfolioSerializer,
	AssetSerializer,
	AssetIdentifierSerializer,
	TransactionSerializer,
	PriceSerializer,
	FxRateSerializer,
	IntegrationSerializer,
	AdviceSerializer,
)
from .tasks import generate_advice_for_portfolio, recompute_portfolio_features


class CurrencyViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Currency.objects.all().order_by('code')
	serializer_class = CurrencySerializer


class ExchangeViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Exchange.objects.all().order_by('code')
	serializer_class = ExchangeSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = User.objects.all().order_by('date_joined')
	serializer_class = UserSerializer


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


class UserRegistrationView(APIView):
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "user": UserSerializer(user).data,
                "message": "User created successfully"
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


class AISuggestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        portfolio_id = request.data.get('portfolio_id')
        if not portfolio_id:
            return Response({"detail": "portfolio_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Queue both feature recomputation and advice generation
        recompute_task = recompute_portfolio_features.delay(portfolio_id)
        advice_task = generate_advice_for_portfolio.delay(portfolio_id)
        
        return Response({
            "status": "queued",
            "tasks": {
                "recompute_features": recompute_task.id,
                "generate_advice": advice_task.id
            }
        })


class VectorSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Search for similar portfolios using vector similarity"""
        from .vector_service import vector_service
        
        portfolio_id = request.data.get('portfolio_id')
        limit = request.data.get('limit', 5)
        
        if not portfolio_id:
            return Response({"detail": "portfolio_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get portfolio features for similarity search
            portfolio = Portfolio.objects.get(id=portfolio_id)
            transactions = Transaction.objects.filter(portfolio=portfolio)
            assets = Asset.objects.filter(transactions__portfolio=portfolio).distinct()
            
            # Create query embedding
            total_value = sum(t.amount * t.price for t in transactions if t.price)
            asset_count = assets.count()
            transaction_count = transactions.count()
            
            features = [
                total_value / 1000000.0,
                asset_count / 100.0,
                transaction_count / 1000.0,
            ]
            query_embedding = features + [0.0] * (384 - len(features))
            
            # Search for similar portfolios
            similar_portfolios = vector_service.search_similar_portfolios(
                query_embedding, 
                limit=limit,
                filters={"user_id": str(portfolio.user_id)} if portfolio.user_id else None
            )
            
            return Response({
                "similar_portfolios": similar_portfolios,
                "query_features": features
            })
        except Portfolio.DoesNotExist:
            return Response({"detail": "Portfolio not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
