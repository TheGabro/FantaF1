from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0041_refactor_choice_spent_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='playerqualifyingmultichoice',
            name='selection_slot',
            field=models.CharField(
                choices=[
                    ('q1_pass', 'Pass Q1'),
                    ('q2_pass', 'Pass Q2'),
                    ('q3_top3', 'Q3 - Top-3'),
                ],
                max_length=8,
            ),
        ),
        migrations.AlterUniqueTogether(
            name='playerqualifyingmultichoice',
            unique_together={('player', 'qualifying', 'driver')},
        ),
    ]
