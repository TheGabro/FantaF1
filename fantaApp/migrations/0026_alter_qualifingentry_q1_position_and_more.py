# Generated by Django 5.2.3 on 2025-07-14 09:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0025_alter_race_options_rename_year_race_season_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='qualifingentry',
            name='q1_position',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='qualifingentry',
            name='q2_position',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='qualifingentry',
            name='q3_position',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
