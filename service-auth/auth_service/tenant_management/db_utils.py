import logging
import secrets
import string
from django.db import connections
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


class CrossAgencyQuery:
    """Helper for cross‑agency queries (used only by super admin)"""

    @staticmethod
    def get_agency_stats(agency):
        db_alias = f"agency_{agency.id}"
        try:
            with connections[db_alias].cursor() as cursor:
                cursor.execute("SELECT role, COUNT(*) FROM users_user GROUP BY role")
                user_counts = dict(cursor.fetchall())
                cursor.execute("SELECT COUNT(*) FROM users_voyageur")
                voyageur_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM users_voyageur WHERE passport_verified = true")
                verified_count = cursor.fetchone()[0]
                return {
                    'agency_id': str(agency.id),
                    'agency_name': agency.name,
                    'users': user_counts,
                    'voyageur_count': voyageur_count,
                    'verified_passports': verified_count,
                }
        except Exception as e:
            logger.error(f"Failed to get stats for {agency.name}: {e}")
            return None


class AgencyDatabaseManager:
    """Manages agency database creation using PostgreSQL TEMPLATE (cloning)"""

    @staticmethod
    def _generate_secure_password(length=24):
        """Generate a random secure password"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _get_base_db_config():
        """Get the base database configuration from default settings"""
        default_config = settings.DATABASES['default'].copy()
        keys_to_remove = ['NAME', 'USER', 'PASSWORD', 'HOST', 'PORT']
        for key in keys_to_remove:
            default_config.pop(key, None)
        return default_config

    @staticmethod
    def create_agency_database_role(agency):
        """Create PostgreSQL role for the agency"""
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [agency.db_user])
                exists = cursor.fetchone()
                if not exists:
                    cursor.execute(f'CREATE USER "{agency.db_user}" WITH PASSWORD %s', [agency.db_password])
                    logger.info(f"Created role {agency.db_user}")
                else:
                    cursor.execute(f'ALTER USER "{agency.db_user}" WITH PASSWORD %s', [agency.db_password])
                    logger.info(f"Updated role {agency.db_user}")
        except Exception as e:
            logger.error(f"Failed to create role: {e}")
            raise

    @staticmethod
    def _setup_agency_tables(agency):
        """Setup all required tables for agency database"""
        db_alias = f"agency_{agency.id}"
        
        with connections[db_alias].cursor() as cursor:
            # 1. Fix username constraint
            try:
                cursor.execute("ALTER TABLE users_user ALTER COLUMN username DROP NOT NULL")
                logger.info("✅ Removed NOT NULL constraint from username")
            except Exception as e:
                logger.warning(f"Username constraint fix skipped: {e}")
            
            # 2. Create django_site table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS django_site (
                    id SERIAL PRIMARY KEY,
                    domain VARCHAR(100) NOT NULL,
                    name VARCHAR(50) NOT NULL
                )
            """)
            cursor.execute("""
                INSERT INTO django_site (id, domain, name) 
                VALUES (1, 'example.com', 'example.com')
                ON CONFLICT (id) DO NOTHING
            """)
            logger.info("✅ django_site table ready")
            
            # 3. Create account_emailaddress table with correct schema
            cursor.execute("DROP TABLE IF EXISTS account_emailaddress CASCADE")
            cursor.execute("""
                CREATE TABLE account_emailaddress (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(254) NOT NULL,
                    verified BOOLEAN NOT NULL DEFAULT FALSE,
                    "primary" BOOLEAN NOT NULL DEFAULT FALSE,
                    user_id INTEGER NOT NULL REFERENCES users_user(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS account_emailaddress_email_idx ON account_emailaddress(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS account_emailaddress_user_id_idx ON account_emailaddress(user_id)")
            logger.info("✅ account_emailaddress table ready")
            
            # 4. Create socialaccount tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS socialaccount_socialapp (
                    id SERIAL PRIMARY KEY,
                    provider VARCHAR(30) NOT NULL,
                    name VARCHAR(40) NOT NULL,
                    client_id VARCHAR(191) NOT NULL,
                    secret VARCHAR(191) NOT NULL,
                    key VARCHAR(191) NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS socialaccount_socialtoken (
                    id SERIAL PRIMARY KEY,
                    token TEXT NOT NULL,
                    token_secret TEXT NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    account_id INTEGER NOT NULL,
                    app_id INTEGER NOT NULL
                )
            """)
            cursor.execute(f"""
                           GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA PUBLIC TO "{agency.db_user}"
                       """)
            cursor.execute(f"""
                           GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA PUBLIC TO "{agency.db_user}"
                       """)
            logger.info("✅ socialaccount tables ready")
            
            # 5. Create authtoken table if needed
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS authtoken_token (
                    key VARCHAR(40) PRIMARY KEY,
                    created TIMESTAMP WITH TIME ZONE NOT NULL,
                    user_id INTEGER NOT NULL UNIQUE REFERENCES users_user(id) ON DELETE CASCADE
                )
            """)
            logger.info("✅ authtoken table ready")

    @staticmethod
    def create_agency_database(agency):
        """Create database for agency and setup all required tables"""
        from django.db import connection
        from psycopg2 import connect
        
        main_db_name = settings.DATABASES['default']['NAME']
        db_alias = f"agency_{agency.id}"
        
        try:
            # Step 1: Clone the database from template
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE datname = '{main_db_name}' AND pid <> pg_backend_pid()
                """)
                
                cursor.execute(f"""
                    CREATE DATABASE "{agency.db_name}"
                    OWNER "{agency.db_user}"
                    TEMPLATE "{main_db_name}"
                    ENCODING 'UTF8'
                """)
                cursor.execute(f'GRANT ALL PRIVILEGES ON DATABASE "{agency.db_name}" TO "{agency.db_user}"')
                logger.info(f"✅ Cloned database {agency.db_name}")
            
            # Step 2: Register connection
            AgencyDatabaseManager._ensure_db_connection(agency)
            
            # Step 3: Reassign ownership and setup tables
            conn = connect(
                dbname=agency.db_name,
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                host=agency.db_host,
                port=agency.db_port
            )
            conn.autocommit = True
            
            with conn.cursor() as cur:
                # Reassign ownership of all existing tables
                cur.execute(f"""
                    DO $$
                    DECLARE
                        r RECORD;
                    BEGIN
                        FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                            EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO "{agency.db_user}"';
                        END LOOP;
                        FOR r IN (SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = 'public') LOOP
                            EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO "{agency.db_user}"';
                        END LOOP;
                    END $$;
                """)
                logger.info(f"✅ Reassigned ownership to {agency.db_user}")
            
            conn.close()
            
            # Step 4: Setup required tables
            AgencyDatabaseManager._setup_agency_tables(agency)
            
            # Step 5: Register connection in Django settings
            AgencyDatabaseManager._ensure_db_connection(agency)
            
            logger.info(f"✅ Agency database {agency.name} fully setup")
            
        except Exception as e:
            logger.error(f"Failed to create database for {agency.name}: {e}")
            raise

    @staticmethod
    def drop_agency_database_role(agency):
        """Drop role – called on failure cleanup"""
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP USER IF EXISTS "{agency.db_user}"')
        except Exception as e:
            logger.error(f"Failed to drop role: {e}")

    @staticmethod
    def drop_agency_database(agency):
        """Drop database – called on failure cleanup"""
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE datname = '{agency.db_name}'
                """)
                cursor.execute(f'DROP DATABASE IF EXISTS "{agency.db_name}"')
        except Exception as e:
            logger.error(f"Failed to drop database: {e}")

    @staticmethod
    def run_migrations_for_agency(agency):
        """Setup agency database tables"""
        AgencyDatabaseManager._setup_agency_tables(agency)
        return "Agency database setup complete"

    @staticmethod
    def _ensure_db_connection(agency):
        """Register the agency database in Django settings"""
        db_alias = f"agency_{agency.id}"
        
        if db_alias not in settings.DATABASES:
            db_config = AgencyDatabaseManager._get_base_db_config()
            db_config.update({
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
            })
            settings.DATABASES[db_alias] = db_config
            logger.info(f"Registered connection for agency {agency.name}")

    @staticmethod
    def load_all_agency_connections():
        """Load all active agency databases into Django settings at startup"""
        from .models import Agency
        
        agencies = Agency.objects.filter(status='active')
        count = 0
        
        for agency in agencies:
            db_alias = f"agency_{agency.id}"
            if db_alias not in settings.DATABASES:
                db_config = AgencyDatabaseManager._get_base_db_config()
                db_config.update({
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
                })
                settings.DATABASES[db_alias] = db_config
                count += 1
        
        logger.info(f"Loaded {count} agency database connections")
        return count
    
    @staticmethod
    def get_or_create_connection(agency_id):
        """Get or create database connection for an agency"""
        from .models import Agency
        
        db_alias = f"agency_{agency_id}"
        
        if db_alias not in settings.DATABASES:
            try:
                agency = Agency.objects.get(id=agency_id)
                default_config = settings.DATABASES['default'].copy()
                keys_to_remove = ['NAME', 'USER', 'PASSWORD', 'HOST', 'PORT']
                for key in keys_to_remove:
                    default_config.pop(key, None)
                
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
                }
                logger.info(f"Created dynamic connection for agency {agency.name}")
            except Agency.DoesNotExist:
                logger.error(f"Agency {agency_id} not found")
        
        return db_alias