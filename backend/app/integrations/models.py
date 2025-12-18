from django.db import models
from app.portfolio.models import Portfolio


class Exchange(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)


class Integration(models.Model):
    key = models.CharField(max_length=50)
    portfolio_id = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    exchange_id = models.ForeignKey(Exchange, on_delete=models.CASCADE)
