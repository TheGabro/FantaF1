# Generated by Django 4.2.23 on 2025-07-13 13:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0023_driver_season'),
    ]

    operations = [
        migrations.AlterField(
            model_name='race',
            name='modified_at',
            field=models.DateTimeField(null=True),
        ),
    ]
