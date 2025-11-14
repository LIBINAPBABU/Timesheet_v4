from django.apps import AppConfig
from jobs import updater

class EmployeeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Employee'
    def ready(self) -> None:
        pass
        # updater.start_scheduler()
