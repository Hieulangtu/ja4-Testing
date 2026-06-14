from dotenv import load_dotenv
from app.database import engine, Base  
load_dotenv(".env")     # đọc biến trước khi bất kỳ module nào lấy os.getenv
from fastapi import FastAPI, Request
from app.routes.auth_routes import auth_router
from app.routes.order_routes import order_router
from fastapi_jwt_auth import AuthJWT
from app.schemas import Settings
import inspect, re
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.openapi.utils import get_openapi
import json
import time
from app.middleware.middleware_request import LogRequestMiddleware
from hashlib import sha256
from app.middleware.fingerprintHTTP_create import fingerprint_middleware
from app.middleware.fingerprintHTTP_create import generate_fingerprint
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.models import delete_expired_tokens
from contextlib import asynccontextmanager
from app.middleware.request_logger import RequestLoggerMiddleware


#scheduler = BackgroundScheduler()
scheduler = AsyncIOScheduler()

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Handle start and end by Lifespan Event"""
#     # start scheduler
#     scheduler.add_job(delete_expired_tokens, 'interval', minutes=1)  # run every 1 minute
#     scheduler.start()
#     print("Scheduler started!")

#     # when code starts
#     yield

#     # when ends
#     scheduler.shutdown()
#     print("Scheduler shut down!")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Đợi Postgres sẵn (thử 10 lần, mỗi 2 giây)
    from sqlalchemy.exc import OperationalError
    for _ in range(10):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except OperationalError:
            import asyncio, time
            print(" Waiting for Postgres…")
            await asyncio.sleep(2)
    else:
        raise RuntimeError("Postgres not ready!")

    scheduler.add_job(delete_expired_tokens, "interval", minutes=1)
    scheduler.start()
    print("Scheduler started ")
    yield
    scheduler.shutdown()
    print("Scheduler stopped ")

app=FastAPI(lifespan=lifespan)

#writes requests to requests.txt
#app.add_middleware(LogRequestMiddleware)
app.add_middleware(RequestLoggerMiddleware)   
app.middleware("http")(fingerprint_middleware)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title = "Pizza Delivery API",
        version = "1.0",
        description = "An API for a Pizza Delivery Service",
        routes = app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "Bearer Auth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Enter: **'Bearer &lt;JWT&gt;'**, where JWT is the access token"
        }
    }

    # Get all routes where jwt_optional() or jwt_required
    api_router = [route for route in app.routes if isinstance(route, APIRoute)]

    for route in api_router:
        path = getattr(route, "path")
        endpoint = getattr(route,"endpoint")
        methods = [method.lower() for method in getattr(route, "methods")]

        for method in methods:
            # access_token
            if (
                re.search("jwt_required", inspect.getsource(endpoint)) or
                re.search("fresh_jwt_required", inspect.getsource(endpoint)) or
                re.search("jwt_optional", inspect.getsource(endpoint))
            ):
                openapi_schema["paths"][path][method]["security"] = [
                    {
                        "Bearer Auth": []
                    }
                ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

@app.get("/", tags=["ja4 check"])
async def ja4_echo(req: Request):
    """
    return JA4 fingerprint from Nginx add to header. 
    only for checking .
    """
    return {
        "x-ja4": req.headers.get("x-ja4"),
        "x-ja4-string": req.headers.get("x-ja4-string"),
        "ip_address": req.headers.get("x-real-ip",req.client.host),
        "fingerprintHTTP":    generate_fingerprint(req)     
    }


@AuthJWT.load_config
def get_config():
    return Settings()

app.include_router(auth_router)
app.include_router(order_router)