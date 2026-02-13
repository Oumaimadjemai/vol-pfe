import asyncio
from threading import Thread

def start_eureka_client():
    from decouple import config
    from py_eureka_client.eureka_client import EurekaClient

    async def start_client():
        client = EurekaClient(
            eureka_server=config("EUREKA_SERVER"),
            app_name=config("EUREKA_APP_NAME"),
            instance_host=config("EUREKA_HOST"),
            instance_port=int(config("EUREKA_PORT")),
        )
        await client.start()

    # Run in a separate thread so it doesn’t block Django startup
    Thread(target=lambda: asyncio.run(start_client()), daemon=True).start()
