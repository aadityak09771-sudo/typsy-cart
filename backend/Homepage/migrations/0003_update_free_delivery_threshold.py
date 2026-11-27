from django.db import migrations, models
from decimal import Decimal

def update_threshold_to_89(apps, schema_editor):
    StoreSetting = apps.get_model('Homepage', 'StoreSetting')
    StoreSetting.objects.all().update(free_delivery_threshold=Decimal('89.00'))

class Migration(migrations.Migration):

    dependencies = [
        ('Homepage', '0002_storesetting_deals_end_datetime_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='storesetting',
            name='free_delivery_threshold',
            field=models.DecimalField(decimal_places=2, default=Decimal('89.00'), help_text='Cart total above which delivery is free', max_digits=8),
        ),
        migrations.RunPython(update_threshold_to_89, reverse_code=migrations.RunPython.noop),
    ]
