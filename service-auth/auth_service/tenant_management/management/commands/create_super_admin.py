# tenant_management/management/commands/create_super_admin.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tenant_management.models import SuperAdminProfile
from getpass import getpass

class Command(BaseCommand):
    help = 'Create a super admin user with full platform access'
    
    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Super admin email')
        parser.add_argument('--username', type=str, help='Super admin username')
        parser.add_argument('--role', type=str, default='owner', 
                           choices=['owner', 'super_admin', 'support', 'billing', 'viewer'])
    
    def handle(self, *args, **options):
        email = options.get('email')
        username = options.get('username')
        role = options.get('role')
        
        if not email:
            email = input("Enter super admin email: ")
        if not username:
            username = input("Enter super admin username: ")
        
        password = getpass("Enter password: ")
        password2 = getpass("Confirm password: ")
        
        if password != password2:
            self.stderr.write(self.style.ERROR("Passwords don't match"))
            return
        
        if User.objects.filter(username=username).exists():
            self.stderr.write(self.style.ERROR(f"User {username} already exists"))
            return
        
        if User.objects.filter(email=email).exists():
            self.stderr.write(self.style.ERROR(f"Email {email} already exists"))
            return
        
        # Create super admin user
        user = User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        
        # Create profile
        profile = SuperAdminProfile.objects.create(
            user=user,
            role=role,
            can_create_agencies=(role in ['owner', 'super_admin']),
            can_delete_agencies=(role == 'owner'),
            can_access_all_agencies=(role in ['owner', 'super_admin', 'support']),
            can_impersonate_any_user=(role in ['owner', 'super_admin']),
            can_view_billing=(role in ['owner', 'billing']),
        )
        
        self.stdout.write(
            self.style.SUCCESS(f"Super admin {email} created with role {role}")
        )


# tenant_management/management/commands/init_agency.py
from django.core.management.base import BaseCommand
from tenant_management.db_utils import AgencyDatabaseManager

class Command(BaseCommand):
    help = 'Initialize all agency database connections'
    
    def handle(self, *args, **options):
        self.stdout.write("Initializing agency database connections...")
        
        count = AgencyDatabaseManager.load_all_agency_connections()
        
        self.stdout.write(
            self.style.SUCCESS(f"Successfully loaded {count} agency connections")
        )