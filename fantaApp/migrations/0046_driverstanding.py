from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0045_deduplicate_schedule_and_add_constraints'),
    ]

    operations = [
        migrations.CreateModel(
            name='DriverStanding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveSmallIntegerField()),
                ('points', models.PositiveIntegerField(default=0)),
                ('wins', models.PositiveSmallIntegerField(default=0)),
                ('podiums', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('driver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='standings', to='fantaApp.driver')),
                ('weekend', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='driver_standings', to='fantaApp.weekend')),
            ],
            options={
                'ordering': ['weekend__season', 'weekend__round_number', 'position'],
                'unique_together': {('weekend', 'driver')},
            },
        ),
        migrations.AddIndex(
            model_name='driverstanding',
            index=models.Index(fields=['weekend', 'position'], name='fantaapp_dr_weekend_1af42e_idx'),
        ),
        migrations.AddIndex(
            model_name='driverstanding',
            index=models.Index(fields=['driver', 'weekend'], name='fantaapp_dr_driver__9da36a_idx'),
        ),
    ]
