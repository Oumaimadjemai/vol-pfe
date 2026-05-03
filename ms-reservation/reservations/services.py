import requests
import logging
from typing import Dict, List, Optional
import time
import os
from threading import Lock

from django.core.cache import cache as _cache

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Cache key helpers — single place to change prefixes
# ------------------------------------------------------------------ #

def _vk(voyageur_id):           return f"voyageur:{voyageur_id}"
def _vuk(user_id):              return f"voyageur_by_user:{user_id}"
def _pk(passenger_id):          return f"passenger:{passenger_id}"
def _ppk(passenger_id):         return f"passengers_for_voyageur:{passenger_id}"


class AuthServiceClient:
    """
    Cache-first HTTP client for ms-auth.

    Cache hierarchy (all populated by both the Kafka consumer and HTTP responses):
      voyageur:{id}            → full voyageur dict
      voyageur_by_user:{uid}   → voyageur_id int (pointer)
      passenger:{id}           → full passenger dict

    TTLs are intentionally generous (2 h) because the Kafka consumer
    invalidates/updates entries on every mutation event from ms-auth.
    """

    _instance = None
    _lock = Lock()

    _VOYAGEUR_TTL  = 7200   # 2 h
    _PASSENGER_TTL = 7200
    _EUREKA_TTL    = 60     # re-discover every 60 s

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, request=None):
        if self._initialized:
            self.request = request
            return

        self.request = request
        self.service_name    = os.getenv("AUTH_SERVICE_NAME",       "AUTH-SERVICE")
        self.eureka_server   = os.getenv("EUREKA_SERVER",           "http://localhost:8888/eureka/")
        self.timeout         = int(os.getenv("AUTH_SERVICE_TIMEOUT", "10"))   # was 30 — trim it
        self._service_url    = None
        self._last_fetch     = 0
        self._cache_ttl      = int(os.getenv("SERVICE_DISCOVERY_CACHE_TTL", "60"))
        self._fallback_url   = os.getenv("AUTH_SERVICE_FALLBACK_URL", "http://localhost:8000")
        self._use_eureka     = os.getenv("USE_EUREKA_DISCOVERY", "True").lower() == "true"
        self._initialized    = True

        if self.eureka_server and not self.eureka_server.endswith('/'):
            self.eureka_server += '/'

    # ------------------------------------------------------------------ #
    # Service discovery (unchanged logic, trimmed retries/timeouts)
    # ------------------------------------------------------------------ #

    def _get_service_from_eureka(self) -> Optional[str]:
        if not self._use_eureka:
            return None
        try:
            headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
            url = f"{self.eureka_server}apps/{self.service_name}"
            response = requests.get(url, headers=headers, timeout=3)   # was 5 s
            if response.status_code != 200:
                return None
            data       = response.json()
            instances  = data.get('application', {}).get('instance', [])
            if not instances:
                return None
            if not isinstance(instances, list):
                instances = [instances]
            inst = instances[0]
            host = inst.get('ipAddr') or inst.get('hostName') or 'localhost'
            port_info = inst.get('port', {})
            port = port_info.get('$', 8000) if isinstance(port_info, dict) else (port_info or 8000)
            return f"http://{host}:{port}"
        except Exception as e:
            logger.warning(f"Eureka discovery error: {e}")
            return None

    def _get_service_url(self) -> str:
        now = time.time()
        if self._service_url and (now - self._last_fetch) < self._cache_ttl:
            return self._service_url
        if self._use_eureka:
            url = self._get_service_from_eureka()
            if url:
                self._service_url = url
                self._last_fetch  = now
                return url
        self._service_url = self._fallback_url
        self._last_fetch  = now
        return self._fallback_url

    def _refresh_service_url(self):
        self._service_url = None
        self._last_fetch  = 0

    # ------------------------------------------------------------------ #
    # HTTP transport — trimmed retries to avoid piling up latency
    # ------------------------------------------------------------------ #

    def _get_auth_headers(self) -> Dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.request:
            auth = None
            if hasattr(self.request, 'headers'):
                auth = self.request.headers.get('Authorization')
            if not auth and hasattr(self.request, 'META'):
                auth = self.request.META.get('HTTP_AUTHORIZATION')
            if auth:
                headers['Authorization'] = auth
        return headers

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        2 attempts max (was 3).  Retry delay dropped to 0.3 s (was 1 s).
        Caller supplies timeout via kwargs or falls back to self.timeout.
        """
        max_retries  = 2
        retry_delay  = 0.3
        kwargs.setdefault('timeout', self.timeout)

        for attempt in range(max_retries):
            try:
                url = f"{self._get_service_url()}{endpoint}"
                logger.debug(f"{method} {url} (attempt {attempt + 1})")
                response = requests.request(method, url, **kwargs)
                if response.status_code < 500:
                    return response
                logger.warning(f"Server error {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    self._refresh_service_url()
            except (requests.Timeout, requests.ConnectionError) as e:
                logger.warning(f"Request error attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    self._refresh_service_url()
                else:
                    raise
        return None

    # ------------------------------------------------------------------ #
    # Internal cache helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _set(key: str, value, ttl: int = 3600):
        _cache.set(key, value, timeout=ttl)

    @staticmethod
    def _get(key: str):
        return _cache.get(key)

    # ------------------------------------------------------------------ #
    # Business methods — all cache-first
    # ------------------------------------------------------------------ #

    def get_voyageur_by_user_id(self, user_id: int) -> Optional[Dict]:
        """Cache-first. Pointer key → full object key → HTTP fallback."""
        voyageur_id = self._get(_vuk(user_id))
        if voyageur_id:
            cached = self._get(_vk(voyageur_id))
            if cached:
                logger.debug(f"Cache hit: voyageur for user {user_id}")
                return cached

        try:
            headers  = self._get_auth_headers()
            response = self._make_request('GET', f"/auth/voyageurs/by-user/{user_id}/",
                                          headers=headers)
            if response and response.status_code == 200:
                data = response.json()
                self._warm_voyageur_cache(data)
                return data
            if response and response.status_code == 404:
                return None
            logger.error(f"get_voyageur_by_user_id failed: "
                         f"{response.status_code if response else 'no response'}")
            return None
        except Exception as e:
            logger.error(f"get_voyageur_by_user_id error: {e}")
            return None

    def get_voyageur_by_id(self, voyageur_id: int) -> Optional[Dict]:
        """Cache-first."""
        cached = self._get(_vk(voyageur_id))
        if cached:
            logger.debug(f"Cache hit: voyageur {voyageur_id}")
            return cached

        try:
            headers  = self._get_auth_headers()
            response = self._make_request('GET', f"/auth/voyageurs/{voyageur_id}/",
                                          headers=headers)
            if response and response.status_code == 200:
                data = response.json()
                self._warm_voyageur_cache(data)
                return data
            logger.error(f"get_voyageur_by_id failed: "
                         f"{response.status_code if response else 'no response'}")
            return None
        except Exception as e:
            logger.error(f"get_voyageur_by_id error: {e}")
            return None

    def _warm_voyageur_cache(self, data: Dict):
        """Write both cache keys from a single voyageur payload."""
        vid = data.get('id')
        uid = data.get('user_id') or (data.get('user', {}) or {}).get('id')
        if vid:
            self._set(_vk(vid), data, self._VOYAGEUR_TTL)
        if uid:
            self._set(_vuk(uid), vid, self._VOYAGEUR_TTL)

    def get_passenger(self, passenger_id: int) -> Optional[Dict]:
        """Cache-first."""
        cached = self._get(_pk(passenger_id))
        if cached:
            logger.debug(f"Cache hit: passenger {passenger_id}")
            return cached

        try:
            headers  = self._get_auth_headers()
            response = self._make_request('GET', f"/auth/passengers/{passenger_id}/",
                                          headers=headers)
            if response and response.status_code == 200:
                data = response.json()
                self._set(_pk(passenger_id), data, self._PASSENGER_TTL)
                return data
            if response and response.status_code == 404:
                return None
            logger.error(f"get_passenger failed: "
                         f"{response.status_code if response else 'no response'}")
            return None
        except Exception as e:
            logger.error(f"get_passenger error: {e}", exc_info=True)
            return None

    def get_passengers_bulk(self, passenger_ids: List[int]) -> Dict[int, Dict]:
        """
        Fetch many passengers with a single cache scan + minimal HTTP calls.
        Returns a dict keyed by passenger_id.

        Hot path for the book() action — replaces the N-HTTP-calls loop.
        """
        result   = {}
        missing  = []

        # 1. Drain cache
        for pid in passenger_ids:
            cached = self._get(_pk(pid))
            if cached:
                result[pid] = cached
            else:
                missing.append(pid)

        # 2. Fetch only the misses
        for pid in missing:
            data = self.get_passenger(pid)   # writes cache as a side-effect
            if data:
                result[pid] = data

        return result

    def get_passengers_by_voyageur(self, voyageur_id: int) -> List[Dict]:
        endpoint = f"/auth/passengers/by-voyageur/{voyageur_id}/"
        try:
            headers  = self._get_auth_headers()
            response = self._make_request('GET', endpoint, headers=headers)
            if response and response.status_code == 200:
                data = response.json()
                rows = data if isinstance(data, list) else data.get('results', [])
                # Warm passenger cache as a side-effect
                for p in rows:
                    if p.get('id'):
                        self._set(_pk(p['id']), p, self._PASSENGER_TTL)
                return rows
            return []
        except Exception as e:
            logger.error(f"get_passengers_by_voyageur error: {e}")
            return []

    def create_passenger(self, passenger_data: Dict, voyageur_id: int) -> Optional[Dict]:
        passenger_data['voyageur'] = voyageur_id
        try:
            headers  = self._get_auth_headers()
            response = self._make_request('POST', "/auth/passengers/create/",
                                          json=passenger_data, headers=headers)
            if response and response.status_code in [200, 201]:
                data = response.json()
                if data.get('id'):
                    self._set(_pk(data['id']), data, self._PASSENGER_TTL)
                return data
            logger.error(f"create_passenger failed: "
                         f"{response.status_code if response else 'no response'} "
                         f"{response.text if response else ''}")
            return None
        except Exception as e:
            logger.error(f"create_passenger error: {e}")
            return None

    def health_check(self) -> bool:
        try:
            response = self._make_request('GET', "/auth/health/",
                                          headers=self._get_auth_headers(), timeout=3)
            return response is not None and response.status_code == 200
        except Exception:
            return False