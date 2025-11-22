# config/settings_marketdata_tests.py
from .settings import *  # базовые настройки

# Минимальный набор приложений, которых достаточно,
# чтобы крутился Django и ничего лишнего не грузилось
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "apps.account",      # твой кастомный User (account.auth_user)
    "apps.core",
    "apps.marketdata",
]

# На всякий случай отключаем миграции для тяжёлых приложений,
# чтобы они не пытались подниматься в тестовой БД
MIGRATION_MODULES = {
    "market": None,
    "portfolio": None,
    "analytics": None,
    "integrations": None,
    "llm": None,
}
