import httpx

from progressos_bot.schemas import ProgressOSActionRequest, ProgressOSActionResponse


class ProgressOSClient:
    def __init__(self, base_url: str, token: str, endpoint: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._timeout = timeout_seconds

    async def submit_action(self, request: ProgressOSActionRequest) -> ProgressOSActionResponse:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}{self._endpoint}",
                headers=self._headers,
                json=request.model_dump(mode="json"),
            )
            response.raise_for_status()
            return ProgressOSActionResponse.model_validate(response.json())

