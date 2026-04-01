from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0042_alter_playerqualifyingmultichoice_slot_and_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerracechoice',
            name='credit_applied',
            field=models.BooleanField(default=False),
        ),
    ]