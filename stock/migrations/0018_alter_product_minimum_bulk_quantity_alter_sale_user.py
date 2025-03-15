# Generated by Django 5.1.5 on 2025-03-15 13:09

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0017_product_unique_product_per_category'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='minimum_bulk_quantity',
            field=models.IntegerField(default=0, help_text='Minimum quantity required for bulk pricing.'),
        ),
        migrations.AlterField(
            model_name='sale',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Seller Name'),
        ),
    ]
