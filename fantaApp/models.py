from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import uuid


class CustomUserManager(BaseUserManager):

    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username must be set')
        
        if not email:
            raise ValueError('The Email must be set') 
        
        email = self.normalize_email(email)
        user_type = extra_fields.get('user_type', 'user')
        extra_fields.setdefault('user_type', user_type)

        if user_type == 'admin':
            extra_fields['is_staff'] = True
            extra_fields['is_superuser'] = True
        elif user_type == 'staff':
            extra_fields['is_staff'] = True
            extra_fields['is_superuser'] = False
        else:
            extra_fields['is_staff'] = False
            extra_fields['is_superuser'] = False

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('user_type', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

    def create_staffuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('user_type', 'staff')
        return self.create_user(username, email, password, **extra_fields)

class CustomUser(AbstractUser):
   
    class UserType(models.TextChoices):
        USER = 'user', 'User'
        PREMIUM = 'premium', 'Premium'
        STAFF = 'staff', 'Staff'
        ADMIN = 'admin', 'Admin'

    user_type = models.CharField(
        max_length=10,
        choices=UserType.choices,
        default=UserType.USER
    )
    email = models.EmailField(unique=True, blank=False, null=False)
    birthday = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    objects = CustomUserManager()

    def is_at_least(self, level: str) -> bool:
        hierarchy = ['user', 'premium', 'staff', 'admin']
        return hierarchy.index(self.user_type) >= hierarchy.index(level)

    def __str__(self):
        return f"{self.username} ({self.user_type})"
    

    from django.db import models

class Driver(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    number = models.PositiveSmallIntegerField()
    short_name = models.CharField(max_length=3)
    team = models.ForeignKey('Team', on_delete=models.CASCADE)
    season = models.PositiveSmallIntegerField()
    api_id = models.CharField(max_length=50,unique= True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    is_valid = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.number}) - {self.short_name}"
    
    class Meta:
        ordering = ['team__name', 'first_name'] #serve a far tornare sempre i piloti in ordine alfabetico, raggruppati per squadra
        unique_together = ('number', 'season')
    
class Team(models.Model):
    name = models.CharField(max_length=50)
    short_name = models.CharField(max_length=3)
    api_id = models.CharField(max_length=50,unique= True)
    nationality = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name'] #serve a far tornare sempre i piloti in ordine alfabetico

class Circuit(models.Model):
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    api_id =  models.CharField(max_length=50, unique= True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Weekend(models.Model):
    WEEKEND_TYPES = [
        ('regular', 'Regular Weekend'),
        ('sprint', 'Sprint Weekend')
    ]

    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE)
    event_name = models.CharField(max_length=100)
    round_number = models.PositiveSmallIntegerField(null=False)
    season = models.PositiveSmallIntegerField(null=False)
    weekend_type = models.CharField(max_length=20, choices = WEEKEND_TYPES, default='regular')
    fp1_start = models.DateTimeField(null=True, blank=True)
    fp2_start = models.DateTimeField(null=True, blank=True)
    fp3_start = models.DateTimeField(null=True, blank=True)
    sprint_start = models.DateTimeField(null=True, blank=True)
    sprint_qualifying_start = models.DateTimeField(null=True, blank=True)
    qualifying_start = models.DateTimeField(null=True, blank=True)
    race_start = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(null = True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.event_name} - {self.season} (Round:{self.round_number})"

    class Meta:
        ordering = ['season', 'round_number']
        unique_together = ('circuit', 'season', 'round_number')

class Event(models.Model):
    weekend = models.ForeignKey(Weekend, on_delete=models.CASCADE,related_name='%(class)ss' )
    
    class Meta:
        abstract = True

class Race(Event):
    TYPES = [
        ('regular', 'Regular Race'),
        ('sprint', 'Sprint Race')
    ]

    type = models.CharField(max_length=20, choices = TYPES, default='regular')


    def __str__(self):
        return f"{self.weekend} - {self.type}"
    
    class Meta:
        ordering = ['weekend__round_number', '-type']
    
class Qualifying(Event):
    TYPES = [
        ('regular', 'Regular Race Qualifying'),
        ('sprint', 'Sprint Race Qualifying')
    ]

    type = models.CharField(max_length=20, choices = TYPES, default='regular')


    def __str__(self):
        return f"{self.weekend} - {self.type}"
    
    class Meta:
        ordering = ['weekend__round_number', '-type']

class RaceResult(models.Model):
    STATUS_CHOICES = [
        ('Finished', 'Finished'),
        ('Retired', 'Did Not Finish'),
        ('Lapped', 'Lapped'),
        ('Disqualified', 'Disqualified'),
        ('Did not start', 'DNS'),
    ]

    race = models.ForeignKey('Race', on_delete=models.CASCADE, related_name='entries')
    driver = models.ForeignKey('Driver', on_delete=models.CASCADE)
    position = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    starting_grid = models.IntegerField(null=True, blank=True)
    points = models.IntegerField(default=0)
    best_lap = models.SmallIntegerField(null=True, blank=True)
    fast_lap = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.race} - {self.driver.short_name} (P{self.position})"

    class Meta:
        unique_together = ('race', 'driver')
        ordering = ['race', 'position']

class QualifyingResult(models.Model):
    qualifying = models.ForeignKey('Qualifying', on_delete=models.CASCADE, related_name='qualifying_entries')
    driver = models.ForeignKey('Driver', on_delete=models.CASCADE)

    q1_position = models.PositiveSmallIntegerField(null=True, blank=True)
    q1_time = models.DurationField(null=True, blank=True)

    q2_position = models.PositiveSmallIntegerField(null=True, blank=True)
    q2_time = models.DurationField(null=True, blank=True)

    q3_position = models.PositiveSmallIntegerField(null=True, blank=True)
    q3_time = models.DurationField(null=True, blank=True)

    best_lap = models.DurationField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.qualifying} - {self.driver.short_name} ({self.position})"

    class Meta:
        unique_together = ('qualifying', 'driver')
        ordering = ['qualifying', 'position']

class Championship(models.Model):
    name = models.CharField(max_length=100)
    year = models.IntegerField()
    active = models.BooleanField(default=True)
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


    def clean(self):
        if not self.pk:
            return  # evita di validare se il campionato non è ancora stato salvato

        if not self.managers.exists():
            raise ValidationError("The championship must have at least one manager")
        
        if self.leagues.exists():
            raise ValidationError("The championship must have at least one league")

    class Meta:
        unique_together = [('name', 'year')]

    def __str__(self):
        return f"{self.name} ({self.year})"
    
class League(models.Model):
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE, related_name='leagues')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if not self.championship:
            raise ValidationError("A league must be inside of a championship")

    def __str__(self):
        return f"{self.name} - {self.championship.name}"
    
class ChampionshipPlayer(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    championship = models.ForeignKey(Championship, on_delete=models.PROTECT, related_name='participants')
    league = models.ForeignKey(League, on_delete=models.PROTECT, related_name='participants')
    player_name = models.CharField(max_length=50)
    available_credit = models.IntegerField(default=2000)
    total_score = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if ChampionshipPlayer.objects.filter(
        championship=self.championship,
        player_name=self.player_name
        ).exclude(pk=self.pk).exists():
            raise ValidationError("Player Name alredy taken in this championship")

    class Meta:
        unique_together = [('user', 'championship'), ('player_name', 'championship')]

    def __str__(self):
        league = f" - {self.league.name}" if self.league else ""
        return f"{self.player_name} ({self.user.username}) in {self.championship.name}{league}"
    
class ChampionshipManager(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE, related_name='managers')
    appointed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'championship')

    def __str__(self):
        return f"{self.user.username} manager of {self.championship.name}"
    
class AbstractPlayerChoice(models.Model):
    """Base comune: tiene traccia di chi sceglie cosa e quanto spende."""
    player = models.ForeignKey(ChampionshipPlayer, on_delete=models.CASCADE)
    driver = models.ForeignKey(Driver, on_delete=models.PROTECT)
    cost = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        indexes = [models.Index(fields=["player", "driver"])]

class PlayerQualifyingChoice(AbstractPlayerChoice):
    qualifying = models.ForeignKey(Qualifying, on_delete=models.CASCADE)

    class Meta(AbstractPlayerChoice.Meta):
        unique_together = [("player", "qualifying")]
        
class PlayerQualifyingMultiChoice(AbstractPlayerChoice):
    qualifying = models.ForeignKey(Qualifying, on_delete=models.CASCADE)
    
    SELECTION_SLOTS = [
        ('q1_pass',  'Pass Q1'),
        ('q2_pass',  'Pass Q2'),
        ('q3_top5',  'Q3 - Top-5'),
    ]
    selection_slot = models.CharField(max_length=8, choices=SELECTION_SLOTS)

    class Meta(AbstractPlayerChoice.Meta):
        unique_together = [("player", "qualifying","selection_slot")]
        
class PlayerSprintQualifyingChoice(AbstractPlayerChoice):
    qualifying = models.ForeignKey(Qualifying, on_delete=models.CASCADE)
    
    SELECTION_SLOTS = [
        ('sq1', 'Out in SQ1'),
        ('sq2', 'Out in SQ2'),
        ('sq3', 'SQ3 (6-10)'),
    ]
    selection_slot = models.CharField(
        max_length=3,
        choices=SELECTION_SLOTS,
    )

    class Meta(AbstractPlayerChoice.Meta):
        unique_together = [("player", "qualifying", "selection_slot")]

class PlayerRaceChoice(AbstractPlayerChoice):
    race = models.ForeignKey(Race, on_delete=models.CASCADE)
    is_pupillo = models.BooleanField(default=False)

    class Meta(AbstractPlayerChoice.Meta):
        unique_together = [("player", "race", "driver")]
        