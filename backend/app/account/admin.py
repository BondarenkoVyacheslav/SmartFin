from django.contrib import admin
from django.contrib.admin import ModelAdmin

import app.account.models


@admin.register(app.account.models.User)
class UserAdmin(ModelAdmin):
    pass
