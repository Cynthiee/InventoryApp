# Generated by Django 5.1.5 on 2025-03-03 10:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0003_alter_bulksale_options_alter_regularsale_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='description',
        ),
    ]
