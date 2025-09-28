from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Transaction, Portfolio
from .tasks import recompute_portfolio_features


@receiver([post_save, post_delete], sender=Transaction)
def on_transaction_change(sender, instance: Transaction, **kwargs):
	portfolio_id = str(instance.portfolio_id)
	recompute_portfolio_features.delay(portfolio_id)


@receiver(post_save, sender=Portfolio)
def on_portfolio_change(sender, instance: Portfolio, created: bool, **kwargs):
	recompute_portfolio_features.delay(str(instance.id))


