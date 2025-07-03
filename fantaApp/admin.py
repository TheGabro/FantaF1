from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.core.exceptions import ValidationError
from .models import CustomUser, Driver, Team, Circuit, Race, Championship

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'type', 'is_staff', 'is_superuser']
    list_filter = ['type', 'is_staff', 'is_superuser']

    fieldsets = UserAdmin.fieldsets + (
        ('Informazioni aggiuntive', {'fields': ('type', 'birthday', 'active', 'deleted_at')}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informazioni aggiuntive', {'fields': ('type',)}),
    )

    def save_model(self, request, obj, form, change):
        # Impedisce assegnazione non valida di ruolo admin
        if obj.type == CustomUser.Role.ADMIN and not obj.is_superuser:
            raise ValidationError("Un utente con ruolo 'admin' deve avere anche is_superuser=True.")

        # Impedisce assegnazione non valida di ruolo staff
        if obj.type == CustomUser.Role.STAFF and not obj.is_staff:
            raise ValidationError("Un utente con ruolo 'staff' deve avere anche is_staff=True.")

        # Logica automatica per impostare il ruolo coerente
        if obj.is_superuser:
            obj.type = CustomUser.Role.ADMIN
        elif obj.is_staff and obj.type == CustomUser.Role.USER:
            obj.type = CustomUser.Role.STAFF
        elif not obj.is_staff and obj.type == CustomUser.Role.STAFF:
            obj.type = CustomUser.Role.USER
        obj.save()

admin.site.register(Driver)
admin.site.register(Team)
admin.site.register(Circuit)
admin.site.register(Race)
admin.site.register(Championship)

