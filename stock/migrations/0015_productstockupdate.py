# Generated by Django 5.1.5 on 2025-03-10 23:11

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0014_inventorystatementitem_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductStockUpdate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(auto_now_add=True)),
                ('quantity_change', models.IntegerField(help_text='Positive for received stock, negative for sold stock.')),
                ('notes', models.TextField(blank=True, null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stock_updates', to='stock.product')),
            ],
        ),
    ]
