# tenant_management/serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User as SuperAdminUser
from .models import Agency, AgencyStaff, AgencyInvitation, SuperAdminProfile, AgencyOperationLog
from django.core.validators import validate_email
import re


class AgencySerializer(serializers.ModelSerializer):
    """Base serializer for Agency"""
    
    domain_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    plan_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Agency
        fields = [
            'id', 'name', 'slug', 'domain_name', 'subdomain',
            'plan', 'plan_display', 'status', 'status_display',
            'max_agents', 'max_voyageurs',
            'contact_email', 'contact_phone', 'address', 'website',
            'created_at', 'updated_at', 'activated_at',
            'settings', 'features',
            'domain_display',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'activated_at']
    
    def get_domain_display(self, obj):
        return obj.get_domain()
    
    def get_status_display(self, obj):
        status_map = {
            'active': 'Active',
            'suspended': 'Suspended',
            'pending': 'Pending Setup',
            'deactivated': 'Deactivated',
        }
        return status_map.get(obj.status, obj.status)
    
    def get_plan_display(self, obj):
        plan_map = {
            'basic': 'Basic',
            'pro': 'Professional',
            'enterprise': 'Enterprise',
        }
        return plan_map.get(obj.plan, obj.plan)


# tenant_management/serializers.py - Fixed version

from rest_framework import serializers
from .models import Agency


class AgencyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new agencies"""
    
    admin_email = serializers.EmailField(required=True, write_only=True)
    admin_name = serializers.CharField(required=False, write_only=True, allow_blank=True)
    
    class Meta:
        model = Agency
        fields = [
            'name', 'slug', 'domain_name', 'subdomain',
            'plan', 'contact_email', 'contact_phone', 
            'address', 'website', 'max_agents', 'max_voyageurs',
            'admin_email', 'admin_name', 'features', 'settings'
        ]
    
    def validate_slug(self, value):
        """Validate slug format"""
        import re
        if not re.match(r'^[a-z0-9-]+$', value):
            raise serializers.ValidationError(
                "Slug can only contain lowercase letters, numbers, and hyphens"
            )
        
        if Agency.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Agency with this slug already exists")
        
        return value
    
    def validate_subdomain(self, value):
        if value:
            import re
            if not re.match(r'^[a-z0-9-]+$', value):
                raise serializers.ValidationError(
                    "Subdomain can only contain lowercase letters, numbers, and hyphens"
                )
            
            if Agency.objects.filter(subdomain=value).exists():
                raise serializers.ValidationError("Subdomain already taken")
        
        return value
    
    def validate_domain_name(self, value):
        if value:
            if Agency.objects.filter(domain_name=value).exists():
                raise serializers.ValidationError("Domain name already in use")
        return value
    
    def validate(self, attrs):
        """Validate and store admin_email in validated_data"""
        # Make sure admin_email is present
        if not attrs.get('admin_email'):
            raise serializers.ValidationError({'admin_email': 'admin_email is required'})
        return attrs
    
    def create(self, validated_data):
        # Remove admin_email and admin_name before creating agency
        admin_email = validated_data.pop('admin_email', None)
        admin_name = validated_data.pop('admin_name', None)
        
        # Create the agency without admin fields
        agency = Agency.objects.create(**validated_data)
        
        # Store admin data in a place the view can access
        self.context['admin_email'] = admin_email
        self.context['admin_name'] = admin_name
        
        return agency
class AgencyUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating agencies"""
    
    class Meta:
        model = Agency
        fields = [
            'name', 'domain_name', 'subdomain', 'plan',
            'max_agents', 'max_voyageurs', 'contact_email',
            'contact_phone', 'address', 'website', 'settings', 'features'
        ]
    
    def validate_subdomain(self, value):
        if value:
            if Agency.objects.exclude(id=self.instance.id).filter(subdomain=value).exists():
                raise serializers.ValidationError("Subdomain already taken")
        return value


class AgencyStaffSerializer(serializers.ModelSerializer):
    """Serializer for agency staff"""
    
    agency_name = serializers.CharField(source='agency.name', read_only=True)
    
    class Meta:
        model = AgencyStaff
        fields = [
            'id', 'agency', 'agency_name', 'user_id', 'role',
            'email', 'full_name', 'is_active', 'invited_by',
            'invited_at', 'accepted_at', 'can_impersonate'
        ]
        read_only_fields = ['id', 'invited_at', 'accepted_at']


class AgencyInvitationSerializer(serializers.ModelSerializer):
    """Serializer for agency invitations"""
    
    class Meta:
        model = AgencyInvitation
        fields = [
            'id', 'agency', 'email', 'role', 'token',
            'expires_at', 'invited_by', 'invited_at',
            'accepted_at', 'status'
        ]
        read_only_fields = ['id', 'token', 'invited_at', 'expires_at', 'status']
        extra_kwargs = {
            'agency': {'required': True},
            'email': {'required': True},
            'role': {'required': True},
        }


class SuperAdminProfileSerializer(serializers.ModelSerializer):
    """Serializer for super admin profile"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = SuperAdminProfile
        fields = [
            'id', 'user', 'user_email', 'role',
            'can_create_agencies', 'can_delete_agencies',
            'can_access_all_agencies', 'can_impersonate_any_user',
            'can_view_billing', 'two_factor_enabled',
            'last_login_ip', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SuperAdminUserSerializer(serializers.ModelSerializer):
    """Serializer for super admin user"""
    
    profile = SuperAdminProfileSerializer(source='super_admin_profile', read_only=True)
    
    class Meta:
        model = SuperAdminUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined', 'profile']



class SuperAdminLoginSerializer(serializers.Serializer):
    """Login serializer for super admin - simplified"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, data):
        if not data.get('username'):
            raise serializers.ValidationError({'username': 'Username is required'})
        if not data.get('password'):
            raise serializers.ValidationError({'password': 'Password is required'})
        return data

class AgencyStatsSerializer(serializers.Serializer):
    """Statistics for an agency"""
    
    agency_id = serializers.UUIDField()
    agency_name = serializers.CharField()
    users = serializers.DictField()
    voyageur_count = serializers.IntegerField()
    verified_passports = serializers.IntegerField()