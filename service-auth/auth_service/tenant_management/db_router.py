# tenant_management/db_router.py
import threading
from django.conf import settings

_thread_local = threading.local()


class TenantContext:
    """Context manager for tenant database switching"""
    
    def __init__(self, db_alias):
        self.db_alias = db_alias
        self.previous_db = None
    
    def __enter__(self):
        self.previous_db = get_current_tenant_db()
        set_current_tenant_db(self.db_alias)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_db:
            set_current_tenant_db(self.previous_db)
        else:
            clear_current_tenant_db()


def set_current_tenant_db(db_alias):
    """Set the current tenant database for this thread/request"""
    _thread_local.current_tenant_db = db_alias


def get_current_tenant_db():
    """Get current tenant database alias"""
    return getattr(_thread_local, 'current_tenant_db', 'default')


def clear_current_tenant_db():
    """Clear current tenant database"""
    if hasattr(_thread_local, 'current_tenant_db'):
        del _thread_local.current_tenant_db


def ensure_agency_connection(agency_id):
    """Dynamically create database connection for an agency if it doesn't exist"""
    from .models import Agency
    
    db_alias = f"agency_{agency_id}"
    
    if db_alias not in settings.DATABASES:
        try:
            agency = Agency.objects.get(id=agency_id)
            
            # Get base config from default database
            default_config = settings.DATABASES['default'].copy()
            keys_to_remove = ['NAME', 'USER', 'PASSWORD', 'HOST', 'PORT']
            for key in keys_to_remove:
                default_config.pop(key, None)
            
            # Add agency-specific config
            settings.DATABASES[db_alias] = {
                **default_config,
                'NAME': agency.db_name,
                'USER': agency.db_user,
                'PASSWORD': agency.db_password,
                'HOST': agency.db_host,
                'PORT': agency.db_port,
                'CONN_MAX_AGE': 60,
                'CONN_HEALTH_CHECKS': False,
                'AUTOCOMMIT': True,
                'TIME_ZONE': settings.TIME_ZONE,
                'ATOMIC_REQUESTS': False,
            }
        except Agency.DoesNotExist:
            pass
    
    return db_alias


class MultiTenantRouter:
    """Database router that routes based on tenant context."""
    
    SUPER_ADMIN_MODELS = {
        'tenant_management': None,
        'contenttypes': None,
        'sessions': None,
        'admin': None,
        'auth': None,
    }
    
    def _is_super_admin_model(self, model):
        app_label = model._meta.app_label
        return app_label in self.SUPER_ADMIN_MODELS
    
    def db_for_read(self, model, **hints):
        if self._is_super_admin_model(model):
            return 'default'
        
        current_db = get_current_tenant_db()
        if current_db and current_db != 'default':
            return current_db
        
        return 'default'
    
    def db_for_write(self, model, **hints):
        if self._is_super_admin_model(model):
            return 'default'
        
        current_db = get_current_tenant_db()
        if current_db and current_db != 'default':
            return current_db
        
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        db1 = getattr(obj1, '_state', None)
        db2 = getattr(obj2, '_state', None)
        
        if db1 and db2:
            return db1.db == db2.db
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.SUPER_ADMIN_MODELS:
            return db == 'default'
        
        if db == 'default':
            return False
        
        return True