from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from .models import CustomUser, Driver, Team, Circuit, Weekend, Championship,ChampionshipManager, League, ChampionshipPlayer,QualifyingResult,RaceResult, Race, Qualifying, PlayerQualifyingChoice, PlayerQualifyingMultiChoice, PlayerSprintQualifyingChoice, PlayerRaceChoice

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

class LeagueInline(admin.TabularInline):
    model = League
    extra = 1  # Numero di form vuoti da mostrare
    fields = ['name', 'created_at']
    readonly_fields = ['created_at']

class ChampionshipManagerInline(admin.TabularInline):
    model = ChampionshipManager
    extra = 0
    fields = ['user', 'appointed_at']
    readonly_fields = ['appointed_at']

class ChampionshipPlayerInline(admin.TabularInline):
    model = ChampionshipPlayer
    extra = 0
    fields = ['user', 'player_name', 'league', 'available_credit', 'total_score']
    readonly_fields = ['joined_at']

class PlayerQualifyingChoiceInline(admin.TabularInline):
    model = PlayerQualifyingChoice
    extra = 0
    fields = ['qualifying', 'driver', 'created_at']
    readonly_fields = ['created_at']

class PlayerQualifyingMultiChoiceInline(admin.TabularInline):
    model = PlayerQualifyingMultiChoice
    extra = 0
    fields = ['qualifying', 'selection_slot', 'driver', 'created_at']
    readonly_fields = ['created_at']

class PlayerSprintQualifyingChoiceInline(admin.TabularInline):
    model = PlayerSprintQualifyingChoice
    extra = 0
    fields = ['qualifying', 'selection_slot', 'driver', 'created_at']
    readonly_fields = ['created_at']

class PlayerRaceChoiceInline(admin.TabularInline):
    model = PlayerRaceChoice
    extra = 0
    fields = ['race', 'driver', 'spent_amount', 'credit_applied', 'is_pupillo', 'created_at']
    readonly_fields = ['created_at']

@admin.register(Championship)
class ChampionshipAdmin(admin.ModelAdmin):
    list_display = ['name', 'year', 'active', 'is_private', 'created_at']
    list_filter = ['year', 'active', 'is_private']
    search_fields = ['name']
    inlines = [LeagueInline, ChampionshipManagerInline, ChampionshipPlayerInline]

@admin.register(ChampionshipPlayer)
class ChampionshipPlayerAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'user', 'championship', 'league', 'available_credit', 'total_score', 'joined_at']
    list_filter = ['championship', 'league']
    search_fields = ['player_name', 'user__username', 'championship__name', 'league__name']
    inlines = [
        PlayerQualifyingChoiceInline,
        PlayerQualifyingMultiChoiceInline,
        PlayerSprintQualifyingChoiceInline,
        PlayerRaceChoiceInline,
    ]

@admin.register(PlayerQualifyingChoice)
class PlayerQualifyingChoiceAdmin(admin.ModelAdmin):
    list_display = ['player', 'qualifying', 'driver', 'created_at']
    list_filter = ['qualifying__weekend__season', 'qualifying__weekend', 'qualifying']
    search_fields = ['player__player_name', 'driver__first_name', 'driver__last_name']

@admin.register(PlayerQualifyingMultiChoice)
class PlayerQualifyingMultiChoiceAdmin(admin.ModelAdmin):
    list_display = ['player', 'qualifying', 'selection_slot', 'driver', 'created_at']
    list_filter = ['selection_slot', 'qualifying__weekend__season', 'qualifying__weekend', 'qualifying']
    search_fields = ['player__player_name', 'driver__first_name', 'driver__last_name']

@admin.register(PlayerSprintQualifyingChoice)
class PlayerSprintQualifyingChoiceAdmin(admin.ModelAdmin):
    list_display = ['player', 'qualifying', 'selection_slot', 'driver', 'created_at']
    list_filter = ['selection_slot', 'qualifying__weekend__season', 'qualifying__weekend', 'qualifying']
    search_fields = ['player__player_name', 'driver__first_name', 'driver__last_name']

@admin.register(PlayerRaceChoice)
class PlayerRaceChoiceAdmin(admin.ModelAdmin):
    list_display = ['player', 'race', 'driver', 'spent_amount', 'credit_applied', 'is_pupillo', 'created_at']
    list_filter = ['credit_applied', 'is_pupillo', 'race__weekend__season', 'race__weekend', 'race']
    search_fields = ['player__player_name', 'driver__first_name', 'driver__last_name']

admin.site.register(Driver)
admin.site.register(Team)
admin.site.register(Circuit)

@admin.register(Weekend)
class WeekendAdmin(admin.ModelAdmin):
    list_display = ['event_name', 'season', 'round_number', 'weekend_type']
    list_filter = ['season']
    search_fields = ['event_name', 'circuit__name']

@admin.register(QualifyingResult)
class QualifyingResultAdmin(admin.ModelAdmin):
    list_display = ['qualifying', 'driver', 'position', 'best_lap']
    list_filter = ['qualifying__weekend__season', 'qualifying__weekend', 'qualifying']
    search_fields = ['driver__first_name', 'driver__last_name', 'driver__short_name']

@admin.register(RaceResult)
class RaceResultAdmin(admin.ModelAdmin):
    list_display = ['race', 'driver', 'position', 'status', 'points']
    list_filter = ['race__weekend__season', 'race__weekend', 'race']
    search_fields = ['driver__first_name', 'driver__last_name', 'driver__short_name']

@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ['weekend', 'type']
    list_filter = ['weekend__season', 'weekend', 'type']
    search_fields = ['weekend__event_name', 'weekend__circuit__name']

@admin.register(Qualifying)
class QualifyingAdmin(admin.ModelAdmin):
    list_display = ['weekend', 'type']
    list_filter = ['weekend__season', 'weekend', 'type']
    search_fields = ['weekend__event_name', 'weekend__circuit__name']


admin.site.register(ChampionshipManager)
admin.site.register(League)

