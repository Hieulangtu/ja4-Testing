from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import json
import os
class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # bảo đảm thư mục tồn tại
        os.makedirs("requests_log", exist_ok=True)
        # Hàm chuyển đổi để xử lý các giá trị không thể serialize
        def safe_serialize(obj):
            try:
                return json.dumps(obj)
            except TypeError:
                return str(obj)

        # Lấy tất cả thông tin từ request
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "path_params": dict(request.path_params),
            "client": request.client.host if request.client else None,
            "client_meta": request.client if request.client else None,
            "cookies": request.cookies,
            "scope": {k: safe_serialize(v) for k, v in request.scope.items()}
        }

        # Ghi nội dung body (nếu có)/ cẩn thận bị ăn mất body
        # body = await request.body()
        # log_data["body"] = body.decode("utf-8") if body else "No body"

        # Ghi toàn bộ log vào file requests.txt
        with open("requests_log/requests.txt", "a") as log_file:
            log_file.write(json.dumps(log_data, indent=4) + "\n\n")

        # Tiếp tục xử lý request và trả về response
        response = await call_next(request)
        return response
    

#khi kế thừa từ BaseHTTPMiddleware, buộc phải sử dụng tên dispatch để tuân thủ kiến trúc mà Starlette và FastAPI đã định nghĩa cho middleware.

#Khi bạn viết một middleware kế thừa từ BaseHTTPMiddleware, FastAPI/Starlette sẽ tự động gọi phương thức dispatch của middleware cho mỗi 
#request đến. Middleware này sẽ nhận request, thực hiện một số thao tác xử lý, và sau đó chuyển request đến bước tiếp theo trong chuỗi xử lý 
#thông qua call_next.