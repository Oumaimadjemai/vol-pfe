# permissions.py
from rest_framework import permissions


class IsVoyageur(permissions.BasePermission):
    """Allow access only to users with role='voyageur'"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'voyageur'


class IsAdminOrAgent(permissions.BasePermission):
    """Allow access only to users with role='admin' or 'agent'"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'agent']


class IsAdmin(permissions.BasePermission):
    """Allow access only to users with role='admin'"""
    
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'admin'