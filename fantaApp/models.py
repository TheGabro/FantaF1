from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import uuid

class CustomUserManager(BaseUserManager):

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username must be set')
        
        if not email:
            raise ValueError('The Email must be set') 
        
        email = self.normalize_email(email)
        role = extra_fields.get('role', 'user')
        extra_fields.setdefault('role', role)

        if role == 'admin':
            extra_fields['is_staff'] = True
            extra_fields['is_superuser'] = True
        elif role == 'staff':
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
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)

    def create_staffuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', False)
        extra_fields.setdefault('role', 'staff')
        return self.create_user(username, email, password, **extra_fields)

class CustomUser(AbstractUser):
   
    class Role(models.TextChoices):
        USER = 'user', 'User'
        PREMIUM = 'premium', 'Premium'
        STAFF = 'staff', 'Staff'
        ADMIN = 'admin', 'Admin'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.USER
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
        return hierarchy.index(self.role) >= hierarchy.index(level)

    def __str__(self):
        return f"{self.username} ({self.role})"
    

    from django.db import models

class Driver(models.Model):
    name = models.CharField(max_length=50)
    surname = models.CharField(max_length=50)
    number = models.IntegerField()
    short_name = models.CharField(max_length=3)  # ad es. 'VER' per Verstappen
    team = models.ForeignKey('Team', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    is_valid = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} {self.surname} ({self.number}) - {self.short_name}"
    
    class Meta:
        ordering = ['team__name', 'name'] #serve a far tornare sempre i piloti in ordine alfabetico, raggruppati per squadra
    
class Team(models.Model):
    name = models.CharField(max_length=50)
    short_name = models.CharField(max_length=3) 
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
    continent = models.CharField(max_length=50)
    state = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Race(models.Model):
    RACE_TYPES = [
        ('regular', 'Regular Race'),
        ('sprint', 'Sprint Race')
    ]

    circuit = models.ForeignKey(Circuit, on_delete=models.CASCADE)
    year = models.IntegerField()
    week = models.IntegerField()
    fp1_start = models.DateTimeField(null=True, blank=True)
    fp2_start = models.DateTimeField(null=True, blank=True)
    fp3_start = models.DateTimeField(null=True, blank=True)
    sprint_start = models.DateTimeField(null=True, blank=True)
    qualifying_start = models.DateTimeField(null=True, blank=True)
    race_start = models.DateTimeField(null=True, blank=True)
    race_type = models.CharField(max_length=20, choices=RACE_TYPES, default='regular')
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.circuit.name} - {self.year} (W{self.week})"

    class Meta:
        ordering = ['year', 'week']
        unique_together = ('circuit', 'year', 'week')

class RaceEntry(models.Model):
    STATUS_CHOICES = [
        ('finished', 'Finished'),
        ('dnf', 'Did Not Finish'),
        ('disqualified', 'Disqualified'),
        ('dns', 'Did Not Start'),
        ('retired', 'Retired'),
    ]

    race = models.ForeignKey('Race', on_delete=models.CASCADE, related_name='entries')
    driver = models.ForeignKey('Driver', on_delete=models.CASCADE)
    position = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    starting_grid = models.IntegerField(null=True, blank=True)
    points = models.IntegerField(default=0)
    best_lap = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.driver.short_name} - {self.race} (P{self.position})"

    class Meta:
        unique_together = ('race', 'driver')
        ordering = ['race', 'position']

class QualifingEntry(models.Model):
    race = models.ForeignKey('Race', on_delete=models.CASCADE, related_name='qualifing_entries')
    driver = models.ForeignKey('Driver', on_delete=models.CASCADE)

    q1_position = models.IntegerField(null=True, blank=True)
    q1_time = models.DurationField(null=True, blank=True)

    q2_position = models.IntegerField(null=True, blank=True)
    q2_time = models.DurationField(null=True, blank=True)

    q3_position = models.IntegerField(null=True, blank=True)
    q3_time = models.DurationField(null=True, blank=True)

    best_lap = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.driver.short_name} - {self.race} (Quali)"

    class Meta:
        unique_together = ('race', 'driver')
        ordering = ['race', 'q3_position']

