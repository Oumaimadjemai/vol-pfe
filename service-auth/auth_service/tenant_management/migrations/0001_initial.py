# tenant_management/migrations/0001_initial.py (create this file manually)
# This ensures migrations run in correct order

from django.db import migrations

class Migration(migrations.Migration):
    initial = True
    
    dependencies = [
        ('users', '0001_initial'),  # Ensure users migrations run first
    ]
    
    operations = []