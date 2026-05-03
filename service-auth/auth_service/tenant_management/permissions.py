# tenant_management/permissions.py
from rest_framework.permissions import BasePermission
from .models import SuperAdminProfile

class IsSuperAdmin(BasePermission):
    """Check if user is a super admin"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.is_superuser


class IsSuperAdminOwner(BasePermission):
    """Check if user is platform owner (highest level)"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_superuser:
            return False
        
        if hasattr(request.user, 'super_admin_profile'):
            return request.user.super_admin_profile.role == 'owner'
        
        return False


class CanCreateAgency(BasePermission):
    """Permission to create new agencies"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_superuser:
            return False
        
        if hasattr(request.user, 'super_admin_profile'):
            return request.user.super_admin_profile.can_create_agencies
        
        return True


class CanDeleteAgency(BasePermission):
    """Permission to delete agencies"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_superuser:
            return False
        
        if hasattr(request.user, 'super_admin_profile'):
            return request.user.super_admin_profile.can_delete_agencies
        
        return False


class CanAccessAllAgencies(BasePermission):
    """Permission to access all agencies data"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_superuser:
            return False
        
        if hasattr(request.user, 'super_admin_profile'):
            return request.user.super_admin_profile.can_access_all_agencies
        
        return True


class CanImpersonateUser(BasePermission):
    """Permission to impersonate agency users"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if not request.user.is_superuser:
            return False
        
        if hasattr(request.user, 'super_admin_profile'):
            return request.user.super_admin_profile.can_impersonate_any_user
        
        return False