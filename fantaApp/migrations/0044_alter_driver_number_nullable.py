from django.db import migrations, models


def replace_placeholder_driver_numbers(apps, schema_editor):
    Driver = apps.get_model('fantaApp', 'Driver')
    Driver.objects.filter(number=0).update(number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0043_playerracechoice_credit_applied'),
    ]

    operations = [
        migrations.AlterField(
            model_name='driver',
            name='number',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(
            replace_placeholder_driver_numbers,
            migrations.RunPython.noop,
        ),
    ]