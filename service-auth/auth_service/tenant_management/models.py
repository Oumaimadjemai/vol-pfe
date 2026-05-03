# tenant_management/models.py
from django.db import models
from django.conf import settings  # Add this import
from django.core.validators import MinLengthValidator, RegexValidator
from django.utils import timezone
import uuid
import secrets
import string

class Agency(models.Model):
    """
    Agency = Tenant = Organization with their own database
    Each agency has: Admin, Agents, Voyageurs (travelers)
    """
    
    PLAN_CHOICES = (
        ('basic', 'Basic - 5 agents, 100 voyageurs'),
        ('pro', 'Pro - 20 agents, 1000 voyageurs'),
        ('enterprise', 'Enterprise - Unlimited'),
    )
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Setup'),
        ('deactivated', 'Deactivated'),
    )
    
    # Core identification
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Agency/Company name")
    slug = models.SlugField(unique=True, max_length=100, help_text="URL-friendly identifier")
    
    # Domain configuration
    domain_name = models.CharField(
        max_length=255, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Custom domain (e.g., travelagency.com)"
    )
    subdomain = models.CharField(
        max_length=100, 
        unique=True, 
        blank=True, 
        null=True,
        help_text="Subdomain on main platform (e.g., agency.yourplatform.com)"
    )
    
    # Database configuration
    db_name = models.CharField(max_length=100, unique=True)
    db_user = models.CharField(max_length=100)
    db_password = models.CharField(max_length=255)
    db_host = models.CharField(max_length=255, default='postgres')
    db_port = models.IntegerField(default=5432)
    
    # Subscription & Limits
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='basic')
    max_agents = models.IntegerField(default=5)
    max_voyageurs = models.IntegerField(default=100)
    max_storage_mb = models.IntegerField(default=500)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    
    # Contact info
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    
    # Super admin reference - FIXED: Use settings.AUTH_USER_MODEL
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # Changed from SuperAdminUser
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_agencies'
    )
    
    # JSON fields for flexible configuration
    settings = models.JSONField(default=dict, blank=True, help_text="Agency-specific settings")
    features = models.JSONField(default=dict, blank=True, help_text="Enabled features")
    
    class Meta:
        verbose_name_plural = "Agencies"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.slug})"
    
    def save(self, *args, **kwargs):
        # Generate database credentials if not provided
        if not self.db_user:
            self.db_user = f"agency_{self.slug.replace('-', '_')}"
        if not self.db_password:
            alphabet = string.ascii_letters + string.digits
            self.db_password = ''.join(secrets.choice(alphabet) for _ in range(24))
        if not self.db_name:
            self.db_name = f"agency_{self.slug.replace('-', '_')}"
        
        super().save(*args, **kwargs)
    
    def get_database_url(self):
        """Get full database URL"""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    def get_domain(self):
        """Get primary domain for this agency"""
        if self.domain_name:
            return self.domain_name
        if self.subdomain:
            return f"{self.subdomain}.yourplatform.com"
        return None
    
    def is_active(self):
        return self.status == 'active'
    
    def can_add_agent(self, current_count):
        if self.plan == 'enterprise':
            return True
        return current_count < self.max_agents
    
    def can_add_voyageur(self, current_count):
        if self.plan == 'enterprise':
            return True
        return current_count < self.max_voyageurs


class AgencyStaff(models.Model):
    """
    Users belonging to an agency (admins and agents in that agency)
    This table resides in the SUPER ADMIN database (central)
    """
    
    ROLE_CHOICES = (
        ('agency_admin', 'Agency Administrator'),
        ('agency_agent', 'Agency Agent'),
        ('agency_viewer', 'Agency Viewer'),
    )
    
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='staff_members')
    user_id = models.IntegerField(help_text="ID in agency's local database")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agency_agent')
    
    # User info (cached from agency DB for quick access)
    email = models.EmailField()
    full_name = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Invitation tracking - FIXED: Use settings.AUTH_USER_MODEL
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='invited_staff'
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    # Super admin actions
    can_impersonate = models.BooleanField(default=False, help_text="Super admin can login as this user")
    
    class Meta:
        unique_together = [
            ('agency', 'user_id'),
            ('agency', 'email')
        ]
        ordering = ['agency', 'role', 'email']
    
    def __str__(self):
        return f"{self.email} - {self.agency.name} ({self.role})"


class AgencyInvitation(models.Model):
    """
    Invitations for agency staff (users within agency)
    """
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )
    
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=AgencyStaff.ROLE_CHOICES)
    
    # Invitation token
    token = models.CharField(max_length=100, unique=True)
    expires_at = models.DateTimeField()
    
    # Metadata - FIXED: Use settings.AUTH_USER_MODEL
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    def __str__(self):
        return f"Invite {self.email} to {self.agency.name}"
    
    def is_valid(self):
        return self.status == 'pending' and self.expires_at > timezone.now()


class SuperAdminProfile(models.Model):
    """
    Extended profile for super admin users
    """
    # FIXED: Use settings.AUTH_USER_MODEL
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='super_admin_profile'
    )
    
    # Role types within super admin
    ROLE_CHOICES = (
        ('owner', 'Platform Owner'),
        ('super_admin', 'Super Administrator'),
        ('support', 'Support Agent'),
        ('billing', 'Billing Manager'),
        ('viewer', 'Read Only'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='super_admin')
    
    # Permissions
    can_create_agencies = models.BooleanField(default=True)
    can_delete_agencies = models.BooleanField(default=False)
    can_access_all_agencies = models.BooleanField(default=True)
    can_impersonate_any_user = models.BooleanField(default=False)
    can_view_billing = models.BooleanField(default=False)
    
    # Two-factor authentication
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=100, blank=True)
    
    # Audit
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.role}"


class AgencyOperationLog(models.Model):
    """
    Log all actions performed on agencies (for audit)
    """
    OPERATION_TYPES = (
        ('create', 'Agency Created'),
        ('update', 'Agency Updated'),
        ('suspend', 'Agency Suspended'),
        ('activate', 'Agency Activated'),
        ('delete', 'Agency Deleted'),
        ('staff_add', 'Staff Added'),
        ('staff_remove', 'Staff Removed'),
        ('staff_role_change', 'Staff Role Changed'),
    )
    
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name='logs', null=True)
    operation = models.CharField(max_length=50, choices=OPERATION_TYPES)
    # FIXED: Use settings.AUTH_USER_MODEL
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    performed_at = models.DateTimeField(auto_now_add=True)
    
    # Details as JSON
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.operation} - {self.performed_at}"