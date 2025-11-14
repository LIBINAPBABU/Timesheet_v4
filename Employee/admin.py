from django.contrib import admin
from .models import users
from .forms import usersForm
from django.contrib.auth.admin import UserAdmin

# Register your models here.
class usersAdmin(UserAdmin):
    model = users
    add_form = usersForm

    fieldsets = (
        *UserAdmin.fieldsets,(
            'Additional Fields',
            {
                'fields':(
                    'phone',
                    'role',
                    'reporting_to',
                    'designation'
                )
            }
        )

    )

admin.site.register(users,usersAdmin)