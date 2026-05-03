# tenant_management/middleware.py
import re
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseNotFound
from .models import Agency
from .db_router import set_current_tenant_db, clear_current_tenant_db, ensure_agency_connection

class TenantMiddleware(MiddlewareMixin):
    
    SUPER_ADMIN_PATHS = [
        '/super-admin/',
        '/admin/',
        '/health/',
        '/metrics/',
    ]
    
    def process_request(self, request):
        # Check super admin paths
        if any(request.path.startswith(path) for path in self.SUPER_ADMIN_PATHS):
            request.is_super_admin_request = True
            request.agency = None
            set_current_tenant_db('default')
            return None
        
        host = request.get_host().split(':')[0]
        
        # Check for localhost or 127.0.0.1 (super admin)
        if host == 'localhost' or host == '127.0.0.1':
            request.is_super_admin_request = True
            request.agency = None
            set_current_tenant_db('default')
            return None
        
        # Handle nip.io domains (e.g., testagency.127.0.0.1.nip.io)
        if '.127.0.0.1.nip.io' in host or '.localhost.nip.io' in host:
            subdomain = host.split('.')[0]
            try:
                agency = Agency.objects.get(subdomain=subdomain, status='active')
                request.agency = agency
                request.is_super_admin_request = False
                db_alias = ensure_agency_connection(str(agency.id))
                set_current_tenant_db(db_alias)
                return None
            except Agency.DoesNotExist:
                pass
        
        # Handle regular localhost subdomains
        if '.localhost' in host:
            subdomain = host.split('.')[0]
            try:
                agency = Agency.objects.get(subdomain=subdomain, status='active')
                request.agency = agency
                request.is_super_admin_request = False
                db_alias = ensure_agency_connection(str(agency.id))
                set_current_tenant_db(db_alias)
                return None
            except Agency.DoesNotExist:
                pass
        
        # Handle real domains
        try:
            agency = Agency.objects.get(domain_name=host, status='active')
            request.agency = agency
            request.is_super_admin_request = False
            db_alias = ensure_agency_connection(str(agency.id))
            set_current_tenant_db(db_alias)
            return None
        except Agency.DoesNotExist:
            pass
        
        return HttpResponseNotFound(f"No agency found for domain: {host}")
    
    def process_response(self, request, response):
        clear_current_tenant_db()
        return response