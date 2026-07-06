from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates a demo admin user if it does not exist'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        email = 'admin@hospital.com'
        password = 'admin'

        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(email=email, password=password, role='admin')
            self.stdout.write(self.style.SUCCESS(f"Usuario demo creado: {email} / {password}"))
        else:
            self.stdout.write(self.style.WARNING(f"Usuario demo {email} ya existe."))
