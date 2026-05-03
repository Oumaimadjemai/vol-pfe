import requests
import json

def test_eureka():
    """Test Eureka connection and service registration"""
    
    # Your Eureka server URL
    eureka_server = "http://localhost:8888/eureka/"
    
    # Headers to request JSON format
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    print(f"Testing Eureka connection at: {eureka_server}")
    
    # Test 1: Check if Eureka is reachable with JSON header
    try:
        response = requests.get(f"{eureka_server}apps/", headers=headers, timeout=5)
        print(f"\n1. Eureka reachable: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"   ✅ Eureka is responding with valid JSON")
                
                # List all registered services
                applications = data.get('applications', {}).get('application', [])
                if applications:
                    if not isinstance(applications, list):
                        applications = [applications]
                    
                    print(f"\n2. Registered services:")
                    for app in applications:
                        app_name = app.get('name')
                        instances = app.get('instance', [])
                        if not isinstance(instances, list):
                            instances = [instances]
                        print(f"   - {app_name}: {len(instances)} instance(s)")
                        for inst in instances:
                            host = inst.get('ipAddr', inst.get('hostName'))
                            port = inst.get('port', {})
                            if isinstance(port, dict):
                                port = port.get('$')
                            status = inst.get('status')
                            print(f"     • {host}:{port} (Status: {status})")
                else:
                    print("\n2. No services registered in Eureka yet")
                    
            except ValueError as e:
                print(f"   ❌ Eureka returned non-JSON response: {e}")
                print(f"   Response preview: {response.text[:200]}")
        else:
            print(f"   ❌ Eureka returned status {response.status_code}")
            
    except requests.Timeout:
        print("   ❌ Eureka connection timeout - Server not responding")
    except requests.ConnectionError:
        print("   ❌ Cannot connect to Eureka - Is it running?")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # Test 2: Check specific service
    service_name = "AUTH-SERVICE"
    print(f"\n3. Checking service '{service_name}':")
    try:
        response = requests.get(f"{eureka_server}apps/{service_name}", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Service found!")
            app = data.get('application', {})
            instances = app.get('instance', [])
            if instances:
                if not isinstance(instances, list):
                    instances = [instances]
                for inst in instances:
                    host = inst.get('ipAddr', inst.get('hostName'))
                    port = inst.get('port', {})
                    if isinstance(port, dict):
                        port = port.get('$')
                    status = inst.get('status')
                    print(f"   • Instance: {host}:{port} (Status: {status})")
            else:
                print(f"   ⚠️  Service found but no instances")
        elif response.status_code == 404:
            print(f"   ❌ Service '{service_name}' not found in Eureka")
            # List all services again
            all_apps = requests.get(f"{eureka_server}apps/", headers=headers, timeout=5)
            if all_apps.status_code == 200:
                data = all_apps.json()
                apps = data.get('applications', {}).get('application', [])
                if apps:
                    if not isinstance(apps, list):
                        apps = [apps]
                    service_names = [app.get('name') for app in apps if app.get('name')]
                    print(f"   Available services: {service_names}")
        else:
            print(f"   ❌ Status: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    test_eureka()