from django.db import migrations
from django.contrib.postgres.operations import CreateExtension


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        # Create PostgreSQL extensions
        CreateExtension('pgcrypto'),  # For gen_random_uuid()
        CreateExtension('citext'),    # Case-insensitive text
    ]


