from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from fantaApp.models import Race, Driver, QualifyingEntry
from fantaApp.services.jolpicaSource import get_qualyfication_result


class Command(BaseCommand):
    help = "Import last qualyfication result"

