# apps/account/models.py
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    Кастомный пользователь Django, маппится на существующую таблицу account.auth_user.
    Таблица уже есть -> managed=False, Django её не создаёт/не меняет.
    """
    class Meta:
        db_table = 'account"."auth_user'
        managed = False