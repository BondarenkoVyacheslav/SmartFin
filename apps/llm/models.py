# apps/llm/models.py
import uuid
from django.db import models
from django.utils import timezone


class Advice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    portfolio = models.ForeignKey(
        'portfolio.Portfolio',
        on_delete=models.CASCADE,
        db_column='portfolio_id',
        related_name='advices',
    )
    kind = models.TextField()
    message = models.TextField()
    score = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        # важное: указываем схему+таблицу ровно как в БД
        db_table = 'llm"."advice'
        verbose_name = 'Совет (LLM)'
        verbose_name_plural = 'Советы (LLM)'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message[:64]}"
