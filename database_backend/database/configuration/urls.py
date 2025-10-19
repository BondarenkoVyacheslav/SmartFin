from rest_framework.routers import SimpleRouter

from configuration import views

router = SimpleRouter()
router.register(r'users', views.UserViewSet )
router.register(r'assets-type', views.AssetTypeViewSet)
router.register(r'asset', views.AssetViewSet)
router.register(r'portfolios', views.PortfolioViewSet)
router.register(r'portfolio-assets', views.PortfolioAssetViewSet)
router.register(r'transactions', views.TransactionViewSet)

urlpatterns = router.urls
