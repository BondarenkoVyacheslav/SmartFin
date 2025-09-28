from django.urls import path, include
from rest_framework.routers import DefaultRouter
try:
    from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
except Exception:  # package may be missing in some environments
    TokenObtainPairView = None
    TokenRefreshView = None
    TokenVerifyView = None
from .views import (
    CurrencyViewSet,
    ExchangeViewSet,
    AppUserViewSet,
    PortfolioViewSet,
    AssetViewSet,
    AssetIdentifierViewSet,
    TransactionViewSet,
    PriceViewSet,
    FxRateViewSet,
    IntegrationViewSet,
    AdviceViewSet,
    LogoutView,
)

router = DefaultRouter()
router.register(r'currencies', CurrencyViewSet, basename='currency')
router.register(r'exchanges', ExchangeViewSet, basename='exchange')
router.register(r'users', AppUserViewSet, basename='appuser')
router.register(r'portfolios', PortfolioViewSet, basename='portfolio')
router.register(r'assets', AssetViewSet, basename='asset')
router.register(r'asset-identifiers', AssetIdentifierViewSet, basename='assetidentifier')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'prices', PriceViewSet, basename='price')
router.register(r'fx-rates', FxRateViewSet, basename='fxrate')
router.register(r'integrations', IntegrationViewSet, basename='integration')
router.register(r'advice', AdviceViewSet, basename='advice')

urlpatterns = [
    path('', include(router.urls)),
]

if TokenObtainPairView and TokenRefreshView:
    urlpatterns += [
        path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
        path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
        path('auth/logout/', LogoutView.as_view(), name='auth_logout'),
    ]


