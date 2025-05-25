import json, time, uuid, pathlib
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse
from fastapi import Request
from typing import Callable

LOG_PATH = pathlib.Path("logs/requests.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)  # ./logs

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Ghi 1 dòng JSON/ request vào logs/requests.log"""

    async def dispatch(self, request: Request, call_next: Callable):
        t0 = time.time()

        # ---- 1. Đọc body và giữ lại cho route ----
        body_bytes = await request.body()
        # Giới hạn log 1 MB để tránh file khổng lồ
        body_preview = body_bytes[:1_000_000].decode(errors="replace")

        # Tạo request mới để truyền tiếp (body đã “tiêu” phải bọc lại)
        async def receive() -> dict:
            return {"type": "http.request", "body": body_bytes}

        request = Request(request.scope, receive)

        # ---- 2. Gọi route ----
        response: Response = await call_next(request)

        # ---- 3. Thu thập meta ----
        client_host, client_port = None, None
        if request.client:
            client_host, client_port = request.client

        log_item = {
            "id": str(uuid.uuid4()),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": int((time.time() - t0) * 1000),
            "client_ip": request.headers.get("x-forwarded-for", client_host),
            "client_port": client_port,
            "headers": dict(request.headers),
            "cookies": request.cookies,
            "query": dict(request.query_params),
            "path_params": request.path_params,
            "ja4": request.headers.get("x-ja4") or request.headers.get("x-client-ja4"),
            "body": body_preview,
        }

        # ---- 4. Ghi file (JSON-Lines) ----
        with LOG_PATH.open("a", encoding="utf-8") as f:
            json.dump(log_item, f, ensure_ascii=False)
            f.write("\n")

        return response