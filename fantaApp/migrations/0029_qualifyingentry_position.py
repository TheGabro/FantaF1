# Generated by Django 5.2.3 on 2025-07-15 09:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0028_remove_raceentry_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='qualifyingentry',
            name='position',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
