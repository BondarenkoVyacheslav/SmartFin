from celery.schedules import crontab

# Celery Beat schedule configuration
CELERY_BEAT_SCHEDULE = {
    'fetch-daily-fx-rates': {
        'task': 'api.tasks.fetch_daily_fx_rates',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9:00 AM UTC
    },
    'fetch-daily-crypto-prices': {
        'task': 'api.tasks.fetch_daily_crypto_prices',
        'schedule': crontab(hour=9, minute=30),  # Daily at 9:30 AM UTC
    },
    'generate-daily-advice': {
        'task': 'api.tasks.generate_daily_advice_for_all_portfolios',
        'schedule': crontab(hour=10, minute=0),  # Daily at 10:00 AM UTC
    },
}
