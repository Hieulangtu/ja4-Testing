from hashlib import sha256
from fastapi import Request, Depends, HTTPException
from app.models import TokenLog
from app.database import SessionLocal
from sqlalchemy import select
from app.redis_client import redis_client
import json

#session=Session(bind=engine)
def normalize_header_value(header_value: str) -> str:
    """ 
    :param header_value: value of header input.
    :return: value of header after normalized.
    """
    # Tách các thành phần, loại bỏ khoảng trắng đầu/cuối và chỉ giữ các phần không rỗng
    parts = [part.strip() for part in header_value.split(',') if part.strip()]
    # sort
    parts.sort()
    # join
    normalized = ', '.join(parts)
    return normalized

def generate_fingerprint(request: Request) -> str:
    """
    Create fingerprint from header in request.

    Args:
        request (Request): object request handled by FastAPI.

    Returns:
        str: value hash SHA256 of fingerprint.
    """
    # Parameters from request's header 
    user_agent = request.headers.get("user-agent", "")
    accept_language = request.headers.get("accept-language", "")
    accept_encoding= request.headers.get("accept-encoding", "")
    sec_ch_ua = request.headers.get("sec-ch-ua", "")
    sec_ch_ua_platform = request.headers.get("sec-ch-ua-platform", "")
    sec_ch_ua_mobile = request.headers.get("sec-ch-ua-mobile", "")
    #ip_address = request.client.host   #fastAPI
    ip_address = request.headers.get("x-real-ip",request.client.host) # from nginx
    # ip_port= request.client.port
    #ja4 = request.headers.get("x-client-ja4") #from nginx
    ja4 = request.headers.get("x-ja4","")

    #normalize-chuẩn hóa
    sec_ch_ua = normalize_header_value(sec_ch_ua)
    accept_encoding = normalize_header_value(accept_encoding)
    accept_language = normalize_header_value(accept_language)


    # Take information about browser
    #order changes, not this way
    #sec_ch_ua_list = [item.strip() for item in sec_ch_ua.split(",")]
    #important_sec_ch_ua = sec_ch_ua_list[1] if "Chromium" in sec_ch_ua_list[0] else sec_ch_ua_list[0]

    # Create request_fingerprint 
    fingerprint_string = f"{sec_ch_ua}-{user_agent}-{sec_ch_ua_platform}-{accept_language}-{sec_ch_ua_mobile}-{ip_address}-{accept_encoding}-{ja4}"
    fingerprint_hash = sha256(fingerprint_string.encode()).hexdigest()

    #write to file
    # with open("fingerprints_log/fingerprintsV4.txt", "a") as log_file:
    #     log_file.write(f"{fingerprint_hash}   {sec_ch_ua}\n\n")

    return fingerprint_hash

async def fingerprint_middleware(request: Request, call_next):
    # URL from request
    url_path = request.url.path

    # Cases that don't need request_fingerprint (not yet)
    exclude_paths = ["auth/signup", "auth/login", "openapi.json", "8000", "/docs", "/","favicon.ico" ]
    if any(url_path.endswith(path) for path in exclude_paths):
        return await call_next(request)
    
    #other cases (need request_fingerprint)
    fingerprint_hash = generate_fingerprint(request)
    session_id = request.cookies.get("sessionId")
    # checking if header has Authorization 
    authorization_header = request.headers.get("authorization")
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    
    #take the token
    token = request.headers.get("authorization").split(" ", 1)[1].strip()
    redis_key = f"TokenLog:{token}"


    # 1. Check data in Redis
    token_data = await redis_client.get(redis_key)
    if token_data:
        token_obj = json.loads(token_data)
        if token_obj.get("fingerprint") == fingerprint_hash and token_obj.get("session_id") == session_id:
            # good
            return await call_next(request)
        else:
            # if not matching, delete token in Redis
            await redis_client.delete(redis_key)
            # in the same time, delete corresponding data in PostgreSQL
            async with SessionLocal() as db:
                stmt = select(TokenLog).where(TokenLog.token == token)
                result = await db.execute(stmt)
                token_entry = result.scalars().first()
                if token_entry:
                    await db.delete(token_entry)
                    await db.commit()
            raise HTTPException(status_code=401, detail="Log in please")

    # 2. if not finding tokenlog in Redis, checking in PostgreSQL
    async with SessionLocal() as db:
       stmt = select(TokenLog).where(TokenLog.token == token)
       result = await db.execute(stmt)
       token_entry = result.scalars().first()
    
       if not token_entry:
         raise HTTPException(status_code=401, detail="Invalid token-can't be found")

       if token_entry.fingerprint == fingerprint_hash and token_entry.session_id == session_id:
            # OK: let request go through
            # save/update to redis
            # update cache Redis for next time
            # build key for token (use token for key)
            token_obj = {
                "id": token_entry.id,
                "fingerprint": token_entry.fingerprint,
                "token": token_entry.token,
                "type": token_entry.type,
                "session_id": token_entry.session_id,
                "user_id": token_entry.user_id,
                "created_at": token_entry.created_at.isoformat()
            }
            # create TTL base on type
            ttl = 900 if token_entry.type == "access_token" else 604800
            await redis_client.setex(redis_key, ttl, json.dumps(token_obj))
            #response
            response = await call_next(request)
            return response
       else:
         #  if fingerprint or session_id is not matching, delete token 
         await db.delete(token_entry)
         await db.commit()
         raise HTTPException(status_code=401, detail="Log in please")
