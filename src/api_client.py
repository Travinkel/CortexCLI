import httpx
from typing import List, Dict, Any

class RightLearningClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}"}

    async def get_due_atoms(self, limit: int = 20) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/Atoms/due",
                headers=self.headers,
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()

    async def get_curriculums(self) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/Curriculum",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()
