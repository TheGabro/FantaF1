# Generated by Django 4.2.23 on 2025-07-25 18:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0034_rename_qualifyingentry_qualifyingresult_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='RaceEntry',
            new_name='RaceResult',
        ),
    ]
