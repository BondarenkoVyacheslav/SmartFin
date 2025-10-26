# apps/account/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # кладём M2M в свою схему через явные промежуточные модели
    groups = models.ManyToManyField(
        'auth.Group',
        through='UserGroup',
        related_name='user_set',
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        through='UserUserPermission',
        related_name='user_set',
        blank=True,
    )

    class Meta:
        db_table = 'account"."auth_user'
        managed = True

class UserGroup(models.Model):
    user = models.ForeignKey('account.User', on_delete=models.CASCADE, db_column='user_id')
    group = models.ForeignKey('auth.Group', on_delete=models.CASCADE, db_column='group_id')

    class Meta:
        db_table = 'account"."user_groups'
        managed = True
        unique_together = (('user', 'group'),)

class UserUserPermission(models.Model):
    user = models.ForeignKey('account.User', on_delete=models.CASCADE, db_column='user_id')
    permission = models.ForeignKey('auth.Permission', on_delete=models.CASCADE, db_column='permission_id')

    class Meta:
        db_table = 'account"."user_user_permissions'
        managed = True
        unique_together = (('user', 'permission'),)

