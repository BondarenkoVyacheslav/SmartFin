from typing import Dict, Any

from celery import shared_task
from django.db import transaction

from .models import Portfolio, Advice


@shared_task
def recompute_portfolio_features(portfolio_id: str) -> Dict[str, Any]:
	# Placeholder: compute aggregates, pnl, allocation, risk
	return {"portfolio_id": portfolio_id, "status": "ok"}


@shared_task
def generate_advice_for_portfolio(portfolio_id: str) -> str:
	# Placeholder: call LLM/provider and store advice
	try:
		portfolio = Portfolio.objects.get(id=portfolio_id)
	except Portfolio.DoesNotExist:
		return "not_found"
	with transaction.atomic():
		Advice.objects.create(
			portfolio=portfolio,
			kind='rebalance',
			message='Stub: consider rebalancing.',
			score=None,
			payload={},
		)
	return "created"


