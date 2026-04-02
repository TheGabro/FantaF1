from django.db import migrations
from django.db.models import Count


def _move_related(model, fk_name, source_obj, target_obj):
    unique_groups = list(model._meta.unique_together or [])
    unique_fields = next((list(group) for group in unique_groups if fk_name in group), None)

    for obj in model.objects.filter(**{fk_name: source_obj}):
        if unique_fields:
            lookup = {}
            for field_name in unique_fields:
                lookup[field_name] = target_obj if field_name == fk_name else getattr(obj, field_name)
            if model.objects.filter(**lookup).exclude(pk=obj.pk).exists():
                obj.delete()
                continue

        setattr(obj, fk_name, target_obj)
        obj.save(update_fields=[fk_name])


def _merge_event_group(event_model, fk_name, source_weekend, target_weekend, related_models):
    target_events = {
        event.type: event
        for event in event_model.objects.filter(weekend=target_weekend)
    }

    for source_event in event_model.objects.filter(weekend=source_weekend).order_by('-id'):
        target_event = target_events.get(source_event.type)
        if target_event is None:
            source_event.weekend = target_weekend
            source_event.save(update_fields=['weekend'])
            target_events[source_event.type] = source_event
            continue

        for related_model in related_models:
            _move_related(related_model, fk_name, source_event, target_event)

        source_event.delete()


def deduplicate_schedule(apps, schema_editor):
    Weekend = apps.get_model('fantaApp', 'Weekend')
    Race = apps.get_model('fantaApp', 'Race')
    Qualifying = apps.get_model('fantaApp', 'Qualifying')
    RaceResult = apps.get_model('fantaApp', 'RaceResult')
    QualifyingResult = apps.get_model('fantaApp', 'QualifyingResult')
    PlayerRaceChoice = apps.get_model('fantaApp', 'PlayerRaceChoice')
    PlayerQualifyingChoice = apps.get_model('fantaApp', 'PlayerQualifyingChoice')
    PlayerQualifyingMultiChoice = apps.get_model('fantaApp', 'PlayerQualifyingMultiChoice')
    PlayerSprintQualifyingChoice = apps.get_model('fantaApp', 'PlayerSprintQualifyingChoice')

    duplicate_groups = (
        Weekend.objects.values('season', 'round_number')
        .annotate(count=Count('id'))
        .filter(count__gt=1)
    )

    for group in duplicate_groups:
        weekends = list(
            Weekend.objects.filter(
                season=group['season'],
                round_number=group['round_number'],
            ).order_by('-id')
        )
        keeper = weekends[0]

        for duplicate in weekends[1:]:
            _merge_event_group(
                Race,
                'race',
                duplicate,
                keeper,
                [RaceResult, PlayerRaceChoice],
            )
            _merge_event_group(
                Qualifying,
                'qualifying',
                duplicate,
                keeper,
                [
                    QualifyingResult,
                    PlayerQualifyingChoice,
                    PlayerQualifyingMultiChoice,
                    PlayerSprintQualifyingChoice,
                ],
            )
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('fantaApp', '0044_alter_driver_number_nullable'),
    ]

    operations = [
        migrations.RunPython(deduplicate_schedule, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='weekend',
            unique_together={('season', 'round_number')},
        ),
        migrations.AlterUniqueTogether(
            name='race',
            unique_together={('weekend', 'type')},
        ),
        migrations.AlterUniqueTogether(
            name='qualifying',
            unique_together={('weekend', 'type')},
        ),
    ]