from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0040_alter_qualifying_weekend_alter_race_weekend'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='playerqualifyingchoice',
            name='cost',
        ),
        migrations.RemoveField(
            model_name='playerqualifyingmultichoice',
            name='cost',
        ),
        migrations.RemoveField(
            model_name='playersprintqualifyingchoice',
            name='cost',
        ),
        migrations.RenameField(
            model_name='playerracechoice',
            old_name='cost',
            new_name='spent_amount',
        ),
    ]
