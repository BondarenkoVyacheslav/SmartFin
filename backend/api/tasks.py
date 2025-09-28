from typing import Dict, Any, List
import logging

from celery import shared_task
from django.db import transaction
from django.conf import settings

from .models import Portfolio, Advice, Transaction, Asset, Price
from .vector_service import vector_service

logger = logging.getLogger(__name__)


@shared_task
def recompute_portfolio_features(portfolio_id: str) -> Dict[str, Any]:
	"""Compute portfolio features and create embedding"""
	try:
		portfolio = Portfolio.objects.get(id=portfolio_id)
		
		# Get portfolio transactions and assets
		transactions = Transaction.objects.filter(portfolio=portfolio)
		assets = Asset.objects.filter(transactions__portfolio=portfolio).distinct()
		
		# Compute basic features
		total_value = sum(t.amount * t.price for t in transactions if t.price)
		asset_count = assets.count()
		transaction_count = transactions.count()
		
		# Create feature vector (simplified)
		features = [
			total_value / 1000000.0,  # Normalize to millions
			asset_count / 100.0,      # Normalize to hundreds
			transaction_count / 1000.0,  # Normalize to thousands
		]
		
		# Pad to 384 dimensions (sentence-transformers/all-MiniLM-L6-v2)
		embedding = features + [0.0] * (384 - len(features))
		
		# Store in vector database
		metadata = {
			"total_value": total_value,
			"asset_count": asset_count,
			"transaction_count": transaction_count,
			"user_id": str(portfolio.user_id) if portfolio.user_id else None,
		}
		
		success = vector_service.add_portfolio_embedding(portfolio_id, embedding, metadata)
		
		return {
			"portfolio_id": portfolio_id, 
			"status": "ok" if success else "error",
			"features": features
		}
	except Portfolio.DoesNotExist:
		logger.error(f"Portfolio {portfolio_id} not found")
		return {"portfolio_id": portfolio_id, "status": "not_found"}
	except Exception as e:
		logger.error(f"Error recomputing portfolio features: {e}")
		return {"portfolio_id": portfolio_id, "status": "error", "error": str(e)}


@shared_task
def generate_advice_for_portfolio(portfolio_id: str) -> str:
	"""Generate AI advice for portfolio using vector similarity"""
	try:
		portfolio = Portfolio.objects.get(id=portfolio_id)
		
		# Get portfolio features for similarity search
		transactions = Transaction.objects.filter(portfolio=portfolio)
		assets = Asset.objects.filter(transactions__portfolio=portfolio).distinct()
		
		# Create query embedding (same as in recompute_portfolio_features)
		total_value = sum(t.amount * t.price for t in transactions if t.price)
		asset_count = assets.count()
		transaction_count = transactions.count()
		
		features = [
			total_value / 1000000.0,
			asset_count / 100.0,
			transaction_count / 1000.0,
		]
		query_embedding = features + [0.0] * (384 - len(features))
		
		# Find similar portfolios
		similar_portfolios = vector_service.search_similar_portfolios(
			query_embedding, 
			limit=3,
			filters={"user_id": str(portfolio.user_id)} if portfolio.user_id else None
		)
		
		# Generate advice based on similar portfolios
		advice_message = "Consider diversifying your portfolio based on similar successful portfolios."
		if similar_portfolios:
			advice_message = f"Based on {len(similar_portfolios)} similar portfolios, consider rebalancing your assets."
		
		with transaction.atomic():
			Advice.objects.create(
				portfolio=portfolio,
				kind='rebalance',
				message=advice_message,
				score=0.8,  # Placeholder score
				payload={
					"similar_portfolios": similar_portfolios,
					"features": features
				},
			)
		
		logger.info(f"Generated advice for portfolio {portfolio_id}")
		return "created"
	except Portfolio.DoesNotExist:
		logger.error(f"Portfolio {portfolio_id} not found")
		return "not_found"
	except Exception as e:
		logger.error(f"Error generating advice: {e}")
		return "error"


@shared_task
def fetch_daily_fx_rates():
	"""Daily task to fetch FX rates"""
	from django.core.management import call_command
	try:
		call_command('fetch_fx_frankfurter')
		logger.info("Daily FX rates fetch completed")
		return "success"
	except Exception as e:
		logger.error(f"Error fetching daily FX rates: {e}")
		return "error"


@shared_task
def fetch_daily_crypto_prices():
	"""Daily task to fetch crypto prices"""
	from django.core.management import call_command
	try:
		call_command('fetch_crypto_coingecko')
		logger.info("Daily crypto prices fetch completed")
		return "success"
	except Exception as e:
		logger.error(f"Error fetching daily crypto prices: {e}")
		return "error"


@shared_task
def generate_daily_advice_for_all_portfolios():
	"""Daily task to generate advice for all active portfolios"""
	try:
		portfolios = Portfolio.objects.all()
		results = []
		
		for portfolio in portfolios:
			result = generate_advice_for_portfolio.delay(str(portfolio.id))
			results.append(result)
		
		logger.info(f"Queued advice generation for {len(portfolios)} portfolios")
		return f"queued {len(portfolios)} portfolios"
	except Exception as e:
		logger.error(f"Error queuing daily advice generation: {e}")
		return "error"


