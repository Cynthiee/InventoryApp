# Generated by Django 5.1.5 on 2025-03-08 15:23

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0008_alter_sale_user'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='quantity',
            field=models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(0)]),
        ),
    ]
