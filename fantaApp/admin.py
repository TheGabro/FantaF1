from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from .models import CustomUser, Driver, Team, Circuit, Weekend, Championship,ChampionshipManager, League, ChampionshipPlayer,QualifyingEntry,RaceEntry, Race

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'user_type', 'is_staff', 'is_superuser']
    list_filter = ['user_type', 'is_staff', 'is_superuser']

    fieldsets = UserAdmin.fieldsets + (
        ('Additional information', {'fields': ('user_type', 'birthday', 'active', 'deleted_at')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional information', {'fields': ('user_type',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }
        ),
        ('Additional information', {'fields': ('user_type',)})
    )

    def save_model(self, request, obj, form, change):
        # Impedisce assegnazione non valida di ruolo admin
        if obj.user_type == CustomUser.UserType.ADMIN and not obj.is_superuser:
            raise ValidationError("Un utente con ruolo 'admin' deve avere anche is_superuser=True.")

        # Impedisce assegnazione non valida di ruolo staff
        if obj.user_type == CustomUser.UserType.STAFF and not obj.is_staff:
            raise ValidationError("Un utente con ruolo 'staff' deve avere anche is_staff=True.")

        # Logica automatica per impostare il ruolo coerente
        if obj.is_superuser:
            obj.user_type = CustomUser.UserType.ADMIN
        elif obj.is_staff and obj.user_type == CustomUser.UserType.USER:
            obj.user_type = CustomUser.UserType.STAFF
        elif not obj.is_staff and obj.user_type == CustomUser.UserType.STAFF:
            obj.user_type = CustomUser.UserType.USER
        obj.save()

admin.site.register(Driver)
admin.site.register(Team)
admin.site.register(Circuit)
admin.site.register(Weekend)
admin.site.register(Championship)
admin.site.register(ChampionshipManager)
admin.site.register(League)
admin.site.register(ChampionshipPlayer)
admin.site.register(QualifyingEntry)
admin.site.register(RaceEntry)
admin.site.register(Race)

