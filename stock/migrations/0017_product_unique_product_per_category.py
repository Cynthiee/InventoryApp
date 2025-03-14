# Generated by Django 5.1.5 on 2025-03-14 17:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0016_inventorystatement_total_income_and_more'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(fields=('category', 'name'), name='unique_product_per_category'),
        ),
    ]
