# tenant_management/views.py
from django.utils import timezone

from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User as SuperAdminUser
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from .models import *
from .serializers import*
from .permissions import *
from .db_utils import *
from .db_router import set_current_tenant_db, TenantContext
import logging

logger = logging.getLogger(__name__)


# tenant_management/views.py - Fix SuperAdminAuthView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User as SuperAdminUser
from .models import SuperAdminProfile
from .serializers import SuperAdminLoginSerializer
import logging

logger = logging.getLogger(__name__)


class SuperAdminAuthView(APIView):
    """Authentication for super admin users"""
    
    permission_classes = []
    
    def post(self, request):
        serializer = SuperAdminLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid input', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        username = serializer.validated_data.get('username')
        password = serializer.validated_data.get('password')
        
        # Authenticate using Django's auth system
        user = authenticate(request, username=username, password=password)
        
        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if user is superuser
        if not user.is_superuser:
            return Response(
                {'error': 'Not authorized as super admin'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get or create super admin profile
        profile, created = SuperAdminProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': 'super_admin',
                'can_create_agencies': True,
                'can_access_all_agencies': True,
            }
        )
        
        # Update last login IP
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR'))
        if ip:
            profile.last_login_ip = ip
            profile.save()
        
        # Generate JWT token
        refresh = RefreshToken.for_user(user)
        
        # Add custom claims
        refresh.payload['is_super_admin'] = True
        refresh.payload['role'] = profile.role
        refresh.payload['user_id'] = user.id
        refresh.payload['email'] = user.email
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'is_superuser': user.is_superuser,
            },
            'role': profile.role,
            'permissions': {
                'can_create_agencies': profile.can_create_agencies,
                'can_delete_agencies': profile.can_delete_agencies,
                'can_access_all_agencies': profile.can_access_all_agencies,
                'can_impersonate_any_user': profile.can_impersonate_any_user,
            }
        })

# tenant_management/views.py - Fixed create method

class AgencyViewSet(viewsets.ModelViewSet):
    """Complete CRUD for Agencies with automatic isolated database creation (via TEMPLATE clone)"""

    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get_serializer_class(self):
        if self.action == 'create':
            return AgencyCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return AgencyUpdateSerializer
        elif self.action == 'stats':
            return AgencyStatsSerializer
        return AgencySerializer

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'super_admin_profile'):
            profile = user.super_admin_profile
            if profile.role == 'viewer':
                return Agency.objects.filter(status='active')
            elif profile.role == 'support':
                return Agency.objects.all()
        return Agency.objects.all().order_by('-created_at')

    def create(self, request, *args, **kwargs):
        """Create a new agency with its own isolated database (cloned from super_admin_db)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Get admin_email and admin_name from request (the serializer may have stored it)
        admin_email = request.data.get('admin_email')
        admin_name = request.data.get('admin_name', '')

        if not admin_email:
            return Response(
                {'error': 'admin_email is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Build agency data without admin fields
        agency_data = {
            'name': request.data.get('name'),
            'slug': request.data.get('slug'),
            'subdomain': request.data.get('subdomain'),
            'plan': request.data.get('plan', 'basic'),
            'contact_email': request.data.get('contact_email'),
            'created_by': request.user,
            'status': 'pending',
            'db_name': f"agency_{request.data.get('slug')}",
            'db_user': f"agency_{request.data.get('slug')}",
            'db_password': AgencyDatabaseManager._generate_secure_password(),
            'db_host': 'postgres',
            'db_port': 5432,
        }

        # Create agency record in the central database
        agency = Agency.objects.create(**agency_data)

        try:
            # 1. Create PostgreSQL role
            AgencyDatabaseManager.create_agency_database_role(agency)

            # 2. Clone the entire database using TEMPLATE (all tables, indexes, etc.)
            AgencyDatabaseManager.create_agency_database(agency)

            # 3. Add the connection to Django settings
            AgencyDatabaseManager._ensure_db_connection(agency)

            # 4. No need to run migrations – the clone contains everything

            # 5. Create initial admin user inside the new agency database
            admin_user = self._create_agency_admin_user(agency, admin_email, admin_name)

            # 6. Link to the central staff table
            AgencyStaff.objects.create(
                agency=agency,
                user_id=admin_user.id,
                email=admin_email,
                full_name=admin_name or admin_email,
                role='agency_admin',
                invited_by=request.user,
                accepted_at=timezone.now()
            )

            # 7. Activate the agency
            agency.status = 'active'
            agency.activated_at = timezone.now()
            agency.save()

            # 8. Log the operation
            AgencyOperationLog.objects.create(
                agency=agency,
                operation='create',
                performed_by=request.user,
                details={'admin_email': admin_email, 'plan': agency.plan},
                ip_address=request.META.get('REMOTE_ADDR')
            )

            # 9. Send welcome email (optional)
            self._send_welcome_email(agency, admin_user)

            return Response(AgencySerializer(agency).data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Failed to create agency {agency.name}: {str(e)}")
            # Cleanup: drop the database and role if creation failed
            try:
                AgencyDatabaseManager.drop_agency_database(agency)
            except:
                pass
            try:
                AgencyDatabaseManager.drop_agency_database_role(agency)
            except:
                pass
            agency.delete()
            return Response(
                {'error': f'Failed to create agency: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    
    def _create_agency_admin_user(self, agency, email, name=""):
     """Create the initial admin user in agency's database using raw SQL to avoid permission issues"""
     import secrets
     import string
     from django.db import connections
    
     db_alias = f"agency_{agency.id}"
    
    # Generate temporary password (hashed)
     from django.contrib.auth.hashers import make_password
     temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
     hashed_password = make_password(temp_password)
    
    # Split name
     first_name = name.split()[0] if name else ''
     last_name = name.split()[-1] if len(name.split()) > 1 else ''
    
     try:
        with connections[db_alias].cursor() as cursor:
            # Insert user directly using SQL
            cursor.execute("""
                INSERT INTO users_user (
                    password, last_login, is_superuser, username, 
                    first_name, last_name, email, is_staff, 
                    is_active, date_joined, role, is_blocked, 
                    updated_at, features, is_cross_agency
                ) VALUES (
                    %s, NULL, %s, %s, %s, %s, %s, %s, %s, 
                    NOW(), %s, %s, NOW(), %s, %s
                ) RETURNING id
            """, [
                hashed_password,           # password
                True,                      # is_superuser
                email.split('@')[0],       # username
                first_name,                # first_name
                last_name,                 # last_name
                email,                     # email
                True,                      # is_staff
                True,                      # is_active
                'admin',                   # role
                False,                     # is_blocked
                '[]',                      # features
                False                      # is_cross_agency
            ])
            
            user_id = cursor.fetchone()[0]
            
            # Create voyageur profile
            cursor.execute("""
                INSERT INTO users_voyageur (
                    nom, prenom, sexe, telephone, pays, wilaya, commune, user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                last_name,      # nom
                first_name,     # prenom
                'homme',        # sexe
                '',             # telephone
                '',             # pays
                '',             # wilaya
                '',             # commune
                user_id         # user_id
            ])
            
            logger.info(f"Created admin user {email} for agency {agency.name}")
            
            # Create a dummy User instance to return
            from users.models import User
            return User(id=user_id, email=email)
            
     except Exception as e:
        logger.error(f"Failed to create admin user: {e}")
        raise
    
    
    def _send_welcome_email(self, agency, admin_user):
        """Send a welcome email to the agency admin"""
        try:
            send_mail(
                subject=f'Welcome to {settings.PLATFORM_NAME} – Your Agency "{agency.name}" is Ready!',
                message=f"""
Dear Administrator,

Your agency "{agency.name}" has been successfully created.

Login Details:
- Email: {admin_user.email}
- Temporary Password: (set via password reset)

Agency Portal: {agency.get_domain() or f'http://{agency.subdomain}.{settings.MAIN_DOMAIN}:8000'}

Please log in and change your password immediately.

Best regards,
{settings.PLATFORM_NAME} Team
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_user.email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
class AgencyStaffViewSet(viewsets.ModelViewSet):
    """Manage staff members across agencies"""
    
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = AgencyStaffSerializer
    
    def get_queryset(self):
        agency_id = self.request.query_params.get('agency')
        if agency_id:
            return AgencyStaff.objects.filter(agency_id=agency_id)
        return AgencyStaff.objects.all().select_related('agency')
    
    @action(detail=True, methods=['post'])
    def impersonate(self, request, pk=None):
        """
        Super admin impersonates an agency user
        """
        staff_member = self.get_object()
        
        # Check permission
        if not request.user.super_admin_profile.can_impersonate_any_user:
            if not staff_member.can_impersonate:
                return Response(
                    {'error': 'Not authorized to impersonate this user'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Generate a special JWT for impersonation
        refresh = RefreshToken()
        
        # Add impersonation claims
        refresh.payload['is_impersonating'] = True
        refresh.payload['original_user_id'] = request.user.id
        refresh.payload['impersonated_user_id'] = staff_member.user_id
        refresh.payload['agency_id'] = str(staff_member.agency_id)
        refresh.payload['role'] = staff_member.role
        
        # Also add custom claims for the impersonated user
        refresh.payload['user_email'] = staff_member.email
        refresh.payload['user_name'] = staff_member.full_name
        
        # Log impersonation
        AgencyOperationLog.objects.create(
            agency=staff_member.agency,
            operation='staff_impersonate',
            performed_by=request.user,
            details={
                'impersonated_user': staff_member.email,
                'impersonated_role': staff_member.role
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'is_impersonating': True,
            'original_user': {
                'id': request.user.id,
                'email': request.user.email,
            },
            'impersonated_user': {
                'id': staff_member.user_id,
                'email': staff_member.email,
                'role': staff_member.role,
                'agency': {
                    'id': str(staff_member.agency.id),
                    'name': staff_member.agency.name,
                }
            }
        })


class AgencyInvitationViewSet(viewsets.ModelViewSet):
    """Manage invitations for agency staff"""
    
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = AgencyInvitationSerializer
    queryset = AgencyInvitation.objects.all().order_by('-invited_at')
    
    def perform_create(self, serializer):
        import secrets
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timezone.timedelta(days=7)
        
        invitation = serializer.save(
            token=token,
            expires_at=expires_at,
            invited_by=self.request.user,
            status='pending'
        )
        
        # Send invitation email
        self._send_invitation_email(invitation)
        
        # Log
        AgencyOperationLog.objects.create(
            agency=invitation.agency,
            operation='staff_invite',
            performed_by=self.request.user,
            details={'email': invitation.email, 'role': invitation.role},
            ip_address=self.request.META.get('REMOTE_ADDR')
        )
    
    def _send_invitation_email(self, invitation):
        invite_link = f"{settings.FRONTEND_URL}/accept-invitation?token={invitation.token}"
        
        send_mail(
            subject=f'Invitation to join {invitation.agency.name} on {settings.PLATFORM_NAME}',
            message=f"""
            You have been invited to join {invitation.agency.name} as a {invitation.role}.
            
            Click here to accept: {invite_link}
            
            This invitation expires in 7 days.
            
            Best regards,
            {settings.PLATFORM_NAME} Team
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False
        )


class SuperAdminDashboardView(generics.GenericAPIView):
    """Dashboard for super admin with aggregated statistics"""
    
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    
    def get(self, request):
        total_agencies = Agency.objects.count()
        active_agencies = Agency.objects.filter(status='active').count()
        suspended_agencies = Agency.objects.filter(status='suspended').count()
        pending_agencies = Agency.objects.filter(status='pending').count()
        
        total_staff = AgencyStaff.objects.count()
        
        # Recent activity
        recent_logs = AgencyOperationLog.objects.all().order_by('-performed_at')[:50]
        
        # Agency statistics from their own databases (async would be better)
        # This is simplified - consider using celery for this
        agency_stats = []
        for agency in Agency.objects.filter(status='active')[:10]:
            stats = CrossAgencyQuery.get_agency_stats(agency)
            if stats:
                agency_stats.append(stats)
        
        return Response({
            'summary': {
                'total_agencies': total_agencies,
                'active_agencies': active_agencies,
                'suspended_agencies': suspended_agencies,
                'pending_agencies': pending_agencies,
                'total_staff': total_staff,
            },
            'recent_activity': [
                {
                    'operation': log.operation,
                    'agency': log.agency.name if log.agency else None,
                    'performed_by': log.performed_by.email if log.performed_by else None,
                    'performed_at': log.performed_at,
                    'details': log.details
                }
                for log in recent_logs
            ],
            'top_agencies': agency_stats,
        })