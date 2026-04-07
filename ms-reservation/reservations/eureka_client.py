import asyncio
from threading import Thread
from decouple import config
import py_eureka_client.eureka_client as eureka_client
import logging
import socket
import os
import requests
import time

logger = logging.getLogger(__name__)


def get_instance_host():
    """Get the appropriate host for Eureka registration"""
    # First try environment variable
    host = config("EUREKA_HOST", default=None)
    if host:
        return host
    
    # Try to get the container/host IP
    try:
        # For Docker containers, use hostname
        hostname = socket.gethostname()
        # Try to resolve IP
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    
    # Fallback to localhost
    return "127.0.0.1"


def wait_for_eureka(eureka_server, max_retries=5, delay=2):
    """Wait for Eureka server to be ready"""
    # Clean the URL - remove any comments or whitespace
    eureka_server = eureka_server.strip().split('#')[0].strip()
    
    print(f"\n⏳ Waiting for Eureka server at {eureka_server}...")
    
    # Headers to request JSON
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(f"{eureka_server}apps/", headers=headers, timeout=3)
            if response.status_code == 200:
                try:
                    response.json()
                    print(f"✅ Eureka server is ready (attempt {attempt + 1})")
                    return True
                except:
                    print(f"⚠️  Eureka returned non-JSON response (attempt {attempt + 1})")
            else:
                print(f"⚠️  Eureka returned status {response.status_code} (attempt {attempt + 1})")
        except requests.Timeout:
            print(f"⚠️  Timeout connecting to Eureka (attempt {attempt + 1})")
        except requests.ConnectionError:
            print(f"⚠️  Cannot connect to Eureka (attempt {attempt + 1})")
        except Exception as e:
            print(f"⚠️  Error: {e} (attempt {attempt + 1})")
        
        if attempt < max_retries - 1:
            print(f"   Retrying in {delay} seconds...")
            time.sleep(delay)
    
    print(f"❌ Could not connect to Eureka after {max_retries} attempts")
    return False


def start_eureka_client():
    """Start Eureka client using the correct initialization method"""
    try:
        # Get configuration from environment
        eureka_server_raw = config("EUREKA_SERVER", default="http://localhost:8888/eureka/")
        # Clean the URL - remove any comments or whitespace
        eureka_server = eureka_server_raw.strip().split('#')[0].strip()
        
        app_name = config("EUREKA_APP_NAME", default="MS-RESERVATION")
        instance_host = get_instance_host()
        instance_port = int(config("EUREKA_INSTANCE_PORT", default="8001"))
        
        # Ensure eureka_server ends with /
        if not eureka_server.endswith('/'):
            eureka_server += '/'
        
        print(f"\n🔵 Starting Eureka client for {app_name}...")
        print(f"   Server: {eureka_server}")
        print(f"   Host: {instance_host}")
        print(f"   Port: {instance_port}")
        
        # Wait for Eureka to be ready
        if not wait_for_eureka(eureka_server):
            print(f"⚠️  Continuing without Eureka registration...")
            return False
        
        # Prepare Eureka client parameters
        eureka_params = {
            "eureka_server": eureka_server,
            "app_name": app_name,
            "instance_host": instance_host,
            "instance_port": instance_port,
            "renewal_interval_in_secs": 30,
            "duration_in_secs": 90,
            "instance_id": f"{instance_host}:{app_name}:{instance_port}"
        }
        
        # Add authentication if provided
        eureka_user = config("EUREKA_USER", default=None)
        eureka_password = config("EUREKA_PASSWORD", default=None)
        if eureka_user and eureka_password:
            eureka_params["eureka_user"] = eureka_user
            eureka_params["eureka_password"] = eureka_password
        
        # Initialize Eureka client
        eureka_client.init(**eureka_params)
        
        print(f"✅ {app_name} successfully registered with Eureka!")
        print(f"   Instance ID: {eureka_params['instance_id']}")
        print(f"   Status: UP")
        
        # Verify registration
        time.sleep(3)
        headers = {'Accept': 'application/json'}
        try:
            response = requests.get(f"{eureka_server}apps/{app_name}", headers=headers, timeout=5)
            if response.status_code == 200:
                print(f"   ✅ Registration verified in Eureka")
            else:
                print(f"   ⚠️  Registration not yet visible (status {response.status_code})")
        except Exception as e:
            print(f"   ⚠️  Could not verify registration: {e}")
        
        logger.info(f"Eureka client started successfully for {app_name}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to start Eureka client: {e}")
        logger.error(f"Eureka client error: {e}", exc_info=True)
        return False


def stop_eureka_client():
    """Stop the Eureka client"""
    try:
        eureka_client.stop()
        logger.info("Eureka client stopped successfully")
        print("🛑 Eureka client stopped")
    except Exception as e:
        logger.error(f"Error stopping Eureka client: {e}")
        print(f"⚠️  Error stopping Eureka client: {e}")


# Auto-start only if not disabled
if os.getenv("DISABLE_EUREKA", "False").lower() != "true":
    auto_start = os.getenv("AUTO_START_EUREKA", "True").lower() == "true"
    if auto_start and not os.getenv("RUN_MAIN") == "true":
        import threading
        threading.Timer(2.0, start_eureka_client).start()