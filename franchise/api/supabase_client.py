import httpx
from typing import Dict, Any, List, Optional
from .config import settings

class SupabaseClient:
    """
    Supabase PostgREST HTTP REST 클라이언트
    - SUPABASE_SERVICE_ROLE_KEY 가 설정되면 RLS를 우회하여 프로덕션 테이블에 직접 영속화
    - 미설정 시 SUPABASE_PUBLISHABLE_KEY로 작동
    """
    def __init__(self):
        self.base_url = settings.SUPABASE_URL.rstrip("/") + "/rest/v1"

    def _headers(self, prefer: str = "return=representation") -> Dict[str, str]:
        key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_PUBLISHABLE_KEY
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": prefer
        }

    def select(self, table: str, params: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self.base_url}/{table}", headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json()

    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(f"{self.base_url}/{table}", headers=self._headers(), json=data)
            resp.raise_for_status()
            res = resp.json()
            return res[0] if isinstance(res, list) and len(res) > 0 else res

    def update(self, table: str, query_filter: Dict[str, str], data: Dict[str, Any]) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.patch(f"{self.base_url}/{table}", headers=self._headers(), params=query_filter, json=data)
            resp.raise_for_status()
            return resp.json()

    def delete(self, table: str, query_filter: Dict[str, str]) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.delete(f"{self.base_url}/{table}", headers=self._headers(), params=query_filter)
            resp.raise_for_status()
            return resp.json()

db = SupabaseClient()
