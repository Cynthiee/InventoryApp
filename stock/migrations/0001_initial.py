# Generated by Django 5.1.5 on 2025-01-26 10:36

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
            ],
            options={
                'verbose_name': 'category',
                'verbose_name_plural': 'categories',
                'ordering': ['name'],
                'indexes': [models.Index(fields=['name'], name='stock_categ_name_462dc8_idx')],
            },
        ),
        migrations.CreateModel(
            name='InventoryStatement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(auto_now_add=True)),
                ('total_income', models.DecimalField(decimal_places=2, max_digits=15)),
                ('total_products_sold', models.IntegerField()),
                ('total_products_in_stock', models.IntegerField()),
            ],
            options={
                'ordering': ['date'],
                'indexes': [models.Index(fields=['id', 'date'], name='stock_inven_id_a60c7b_idx'), models.Index(fields=['date'], name='stock_inven_date_a7249b_idx')],
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('regular_price', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(1)])),
                ('bulk_price', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(12)])),
                ('quantity', models.IntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ('minimum_bulk_quantity', models.IntegerField(default=10)),
                ('available', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='stock.category')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='BulkSale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('quantity', models.IntegerField(validators=[django.core.validators.MinValueValidator(12)])),
                ('bulk_price_per_unit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('sale_date', models.DateTimeField(auto_now_add=True)),
                ('available', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('buyer', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bulk_sales', to='stock.product')),
            ],
            options={
                'verbose_name': 'bulk sale',
                'verbose_name_plural': 'bulk sales',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='RegularSale',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('slug', models.SlugField(max_length=200, unique=True)),
                ('description', models.TextField(blank=True)),
                ('quantity', models.IntegerField(validators=[django.core.validators.MinValueValidator(1)])),
                ('price_per_unit', models.DecimalField(decimal_places=2, max_digits=10)),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('sale_date', models.DateTimeField(auto_now_add=True)),
                ('available', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regular_sales', to='stock.product')),
                ('seller', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'regular sale',
                'verbose_name_plural': 'regular sales',
                'ordering': ['name'],
            },
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['id', 'slug'], name='stock_produ_id_f39ec1_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['name'], name='stock_produ_name_56fe90_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['-created'], name='stock_produ_created_c933a5_idx'),
        ),
        migrations.AddIndex(
            model_name='bulksale',
            index=models.Index(fields=['id', 'slug'], name='stock_bulks_id_6ef84a_idx'),
        ),
        migrations.AddIndex(
            model_name='bulksale',
            index=models.Index(fields=['name'], name='stock_bulks_name_f22e89_idx'),
        ),
        migrations.AddIndex(
            model_name='bulksale',
            index=models.Index(fields=['-created'], name='stock_bulks_created_fbc9f3_idx'),
        ),
        migrations.AddIndex(
            model_name='regularsale',
            index=models.Index(fields=['id', 'slug'], name='stock_regul_id_7a654c_idx'),
        ),
        migrations.AddIndex(
            model_name='regularsale',
            index=models.Index(fields=['name'], name='stock_regul_name_152cf2_idx'),
        ),
        migrations.AddIndex(
            model_name='regularsale',
            index=models.Index(fields=['-created'], name='stock_regul_created_1eaa5c_idx'),
        ),
    ]
