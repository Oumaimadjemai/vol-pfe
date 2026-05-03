from kafka import KafkaProducer
import json

print("🚀 Script started...")

try:
    print("⏳ Creating producer...")

    producer = KafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        request_timeout_ms=5000,
        api_version=(0, 10)
    )

    print("✅ Producer created")

    print("📤 Sending message...")
    future = producer.send('user-events', {'test': 'message'})

    result = future.get(timeout=10)

    print("✅ SUCCESS!")
    print(result)

    producer.close()

except Exception as e:
    print("❌ ERROR:", e)

print("🏁 Script finished")