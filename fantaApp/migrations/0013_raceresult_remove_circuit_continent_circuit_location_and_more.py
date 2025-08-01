# Generated by Django 4.2.23 on 2025-07-10 14:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0012_championshipplayer_available_credit_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RaceResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.RemoveField(
            model_name='circuit',
            name='continent',
        ),
        migrations.AddField(
            model_name='circuit',
            name='location',
            field=models.CharField(default='nessuno', max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='race',
            name='round_number',
            field=models.IntegerField(default=1),
            preserve_default=False,
        ),
    ]
