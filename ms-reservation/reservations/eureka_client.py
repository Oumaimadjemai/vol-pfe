import asyncio
from threading import Thread
from decouple import config
from py_eureka_client.eureka_client import EurekaClient
import logging

logger = logging.getLogger(__name__)


def start_eureka_client():
    """Start Eureka client in a separate thread"""
    try:
        # Get configuration from environment
        eureka_server = config("EUREKA_SERVER", default="http://localhost:8888/")
        app_name = config("EUREKA_APP_NAME", default="ms-reservation")
        instance_host = config("EUREKA_HOST", default="localhost")
        instance_port = int(config("EUREKA_INSTANCE_PORT", default="8001"))
        
        print(f"\n🔵 Starting Eureka client for {app_name}...")
        print(f"   Server: {eureka_server}")
        print(f"   Host: {instance_host}")
        print(f"   Port: {instance_port}")
        
        async def start_client():
            try:
                client = EurekaClient(
                    eureka_server=eureka_server,
                    app_name=app_name,
                    instance_host=instance_host,
                    instance_port=instance_port,
                    renewal_interval_in_secs=30,
                    duration_in_secs=90
                )
                await client.start()
                print(f"✅ {app_name} successfully registered with Eureka!")
                return client
            except Exception as e:
                print(f"❌ Failed to start Eureka client: {e}")
                logger.error(f"Eureka client error: {e}", exc_info=True)
                return None

        # Run in a separate thread so it doesn't block Django startup
        thread = Thread(target=lambda: asyncio.run(start_client()), daemon=True)
        thread.start()
        print("   Eureka client thread started")
        
    except Exception as e:
        print(f"❌ Error in start_eureka_client: {e}")
        logger.error(f"Error starting Eureka client: {e}", exc_info=True)