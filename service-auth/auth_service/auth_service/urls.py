# auth_service/urls.py - Main URLs
from django.urls import path, include
from requests import Response
from rest_framework.routers import DefaultRouter
from tenant_management.views import (
    AgencyViewSet, AgencyStaffViewSet, AgencyInvitationViewSet,
    SuperAdminAuthView, SuperAdminDashboardView
)

router = DefaultRouter()
router.register(r'agencies', AgencyViewSet, basename='agency')
router.register(r'staff', AgencyStaffViewSet, basename='staff')
router.register(r'invitations', AgencyInvitationViewSet, basename='invitation')

urlpatterns = [
    # Super admin endpoints
    path('super-admin/login/', SuperAdminAuthView.as_view(), name='super-admin-login'),
    path('super-admin/dashboard/', SuperAdminDashboardView.as_view(), name='super-admin-dashboard'),
    path('super-admin/', include(router.urls)),
    
    # Agency-specific auth (handled by TenantMiddleware)
    path('auth/', include('users.urls')),
    
    # Health checks
    path('health/', lambda request: Response({'status': 'ok'})),
    path('metrics/', lambda request: Response({'status': 'ok'})),
]