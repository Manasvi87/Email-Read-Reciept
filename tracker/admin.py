from django.contrib import admin
from .models import TrackedEmail, EmailOpen


class EmailOpenInline(admin.TabularInline):
    model = EmailOpen
    extra = 0
    readonly_fields = ('timestamp', 'user_agent', 'ip_address')
    can_delete = False


@admin.register(TrackedEmail)
class TrackedEmailAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'subject', 'created_at', 'open_count')
    search_fields = ('recipient', 'subject')
    inlines = [EmailOpenInline]

