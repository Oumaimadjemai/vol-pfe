import logging
import socket
import os
import time
import requests

logger = logging.getLogger(__name__)

# Try to import eureka client
try:
    import py_eureka_client.eureka_client as eureka_client
    EUREKA_AVAILABLE = True
    print("✅ py_eureka_client imported successfully")
except ImportError as e:
    EUREKA_AVAILABLE = False
    logger.warning(f"py_eureka_client not installed: {e}")
    print(f"⚠️ py_eureka_client not installed: {e}")


def get_instance_host():
    """Get the instance host for Eureka registration"""
    host = os.getenv("EUREKA_HOST")
    if host:
        return host
    
    # For Docker, use container name
    if os.path.exists('/.dockerenv'):
        return socket.gethostname()
    
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    
    return "127.0.0.1"


def wait_for_eureka(eureka_server, max_retries=10, delay=5):
    """Wait for Eureka server to be ready"""
    print(f"\n⏳ Waiting for Eureka at {eureka_server}...")
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

    for attempt in range(max_retries):
        try:
            response = requests.get(
                f"{eureka_server}apps/",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                print(f"✅ Eureka is ready (attempt {attempt + 1})")
                return True
            print(f"⚠️ Eureka returned status {response.status_code}")
        except requests.Timeout:
            print(f"⚠️ Timeout connecting to Eureka (attempt {attempt + 1}/{max_retries})")
        except requests.ConnectionError as e:
            print(f"⚠️ Cannot connect to Eureka (attempt {attempt + 1}/{max_retries}): {e}")
        except Exception as e:
            print(f"⚠️ Eureka check error: {e}")

        if attempt < max_retries - 1:
            print(f"   Retrying in {delay}s...")
            time.sleep(delay)

    print(f"⚠️ Eureka not reachable after {max_retries} attempts — continuing anyway")
    return False


def start_eureka_client():
    """Start Eureka client for service registration"""
    print("\n" + "="*50)
    print("STARTING EUREKA CLIENT")
    print("="*50)
    
    if not EUREKA_AVAILABLE:
        print("⚠️ py_eureka_client not installed. Skipping Eureka registration.")
        return False
    
    if os.getenv("DISABLE_EUREKA", "False").lower() == "true":
        print("⚠️ Eureka disabled via DISABLE_EUREKA=True")
        return False

    try:
        eureka_server = os.getenv("EUREKA_SERVER", "http://registry:8888/eureka/").strip()
        if not eureka_server.endswith('/'):
            eureka_server += '/'

        app_name = os.getenv("EUREKA_APP_NAME", "MS-DESTINATION")
        instance_host = get_instance_host()
        instance_port = int(os.getenv("EUREKA_INSTANCE_PORT", "8002"))

        print(f"\n🔵 Registering {app_name} with Eureka...")
        print(f"   Server : {eureka_server}")
        print(f"   Host   : {instance_host}")
        print(f"   Port   : {instance_port}")

        # Wait for Eureka if configured
        if os.getenv("WAIT_FOR_EUREKA", "False").lower() == "true":
            wait_for_eureka(eureka_server)

        # Initialize Eureka client
        eureka_client.init(
            eureka_server=eureka_server,
            app_name=app_name,
            instance_host=instance_host,
            instance_port=instance_port,
            renewal_interval_in_secs=30,
            duration_in_secs=90,
        )

        print(f"✅ {app_name} registered with Eureka at {instance_host}:{instance_port}")
        logger.info(f"Eureka client started for {app_name}")
        return True

    except Exception as e:
        print(f"⚠️ Failed to start Eureka client: {e}")
        import traceback
        traceback.print_exc()
        logger.warning(f"Eureka client error (non-critical): {e}")
        return False


def stop_eureka_client():
    """Stop Eureka client"""
    if not EUREKA_AVAILABLE:
        return
    
    try:
        eureka_client.stop()
        print("🛑 Eureka client stopped")
        logger.info("Eureka client stopped")
    except Exception as e:
        logger.error(f"Error stopping Eureka client: {e}")