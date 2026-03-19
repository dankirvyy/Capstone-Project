"""
Management command to create an admin user
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Create an admin user for the mushroom dashboard'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username for the admin')
        parser.add_argument('email', type=str, help='Email for the admin')
        parser.add_argument('password', type=str, help='Password for the admin')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR(f'User {username} already exists'))
            return

        # Create the user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True
        )

        # Update profile to admin role
        profile = user.profile
        profile.role = 'ADMIN'
        profile.save()

        self.stdout.write(self.style.SUCCESS(f'Successfully created admin user: {username}'))
