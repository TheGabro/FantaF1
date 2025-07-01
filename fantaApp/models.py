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


