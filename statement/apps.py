from django.apps import AppConfig


class StatementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'statement'

    def ready(self):
        import statement.signals