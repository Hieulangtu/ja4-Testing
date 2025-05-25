from fastapi import APIRouter, status, Depends, Request, Response
from fastapi.exceptions import HTTPException
from app.database import get_db
from app.schemas import SignUpModel,LoginModel
from app.models import User, TokenLog
from fastapi.exceptions import HTTPException
from werkzeug.security import generate_password_hash , check_password_hash
from fastapi_jwt_auth import AuthJWT
from fastapi.encoders import jsonable_encoder
from app.middleware.fingerprintHTTP_create import generate_fingerprint
from datetime import datetime
import uuid, json
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
# Import client Redis
from app.redis_client import redis_client


auth_router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

#session=Session(bind=engine)

@auth_router.get('/')
async def hello(Authorize:AuthJWT=Depends()):

    """
        ## Sample hello world route
    
    """
    try:
        Authorize.jwt_required()

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token, please log in or sign up !"
        )

    return {"message":"Hello World-please log in"}

@auth_router.post('/signup',status_code=status.HTTP_201_CREATED)
async def signup(user:SignUpModel, db: Session = Depends(get_db)):
    """
        ## Create a user
        This requires the following
        ```
                username:int
                email:str
                password:str
                is_staff:bool
                is_active:bool

        ```
    
    """


    #db_email=db.query(User).filter(User.email==user.email).first()
    stmt = select(User).where(User.email == user.email)
    result = await db.execute(stmt)
    db_email = result.scalars().first()

    if db_email is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with the email already exists"
        )

    #db_username=db.query(User).filter(User.username==user.username).first()
    stmt = select(User).where(User.username == user.username)
    result = await db.execute(stmt)
    db_username = result.scalars().first()
    
    if db_username is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with the username already exists"
        )

    new_user=User(
        username=user.username,
        email=user.email,
        password=generate_password_hash(user.password),
        is_active=user.is_active,
        is_staff=user.is_staff
    )

    db.add(new_user)

    await db.commit()

    return new_user



#login route

@auth_router.post('/login',status_code=200)
async def login(user:LoginModel,request: Request,response: Response, Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """     
        ## Login a user
        This requires
            ```
                username:str
                password:str
            ```
        and returns a token pair `access` and `refresh`
    """
    #db_user=db.query(User).filter(User.username==user.username).first()
    stmt = select(User).where(User.username == user.username)
    result = await db.execute(stmt)
    db_user = result.scalars().first()

    if db_user and check_password_hash(db_user.password, user.password):
        access_token=Authorize.create_access_token(subject=db_user.username)
        refresh_token=Authorize.create_refresh_token(subject=db_user.username)

        # Create sessionId 
        session_id = str(uuid.uuid4())  
        response.set_cookie(key="sessionId", value=session_id, httponly=True, max_age=604800) #store in cookie

        fingerprint = generate_fingerprint(request)

        #find in the table token_logs to see if the user has logged in before
        #existing_tokens = db.query(TokenLog).filter(TokenLog.user_id == db_user.id).all()
        stmt = select(TokenLog).where(TokenLog.user_id == db_user.id)
        result = await db.execute(stmt)
        existing_tokens = result.scalars().all() #trả về các đối tượng ORM đã được nạp vào session. Sau đó, khi bạn thay đổi thuộc tính của chúng, session nhận diện những thay đổi đó và cập nhật vào cơ sở dữ liệu khi bạn gọi commit.

        updated_access = None
        updated_refresh = None
        

        # checkig if user_id has already be used by finding in token_logs
        if existing_tokens:
            matching_tokens = None
            matching_tokens = [
                token for token in existing_tokens
                if token.fingerprint == fingerprint 
            ]

            #check if the possible device (using to log in) has already be used before
            if matching_tokens:
                # case 1: same fingerprint, same user , overwrite data in database
                for token in matching_tokens:
                    if token.type == "access_token":
                        token.token = access_token
                        updated_access = token
                    elif token.type == "refresh_token":
                        token.token = refresh_token
                        updated_refresh = token
                    token.created_at = datetime.now()
                    token.session_id = session_id
                    token.root_token=refresh_token
                # Fallback nếu thiếu một trong hai token
                if not updated_access:
                    updated_access = TokenLog(
                        fingerprint=fingerprint,
                        token=access_token,
                        type="access_token",
                        created_at=datetime.now(),
                        root_token=refresh_token,
                        session_id=session_id,
                        user_id=db_user.id
                    )
                    db.add(updated_access)

                if not updated_refresh:
                    updated_refresh = TokenLog(
                        fingerprint=fingerprint,
                        token=refresh_token,
                        type="refresh_token",
                        created_at=datetime.now(),
                        root_token=refresh_token,
                        session_id=session_id,
                        user_id=db_user.id
                    )
                    db.add(updated_refresh)

                await db.commit()
                print(f"Updated tokens for user_id={db_user.id}")
            else:
                # case 2: different request_fingerprint so user log in with other device. Handle normally
                access_log = TokenLog(
                    fingerprint=fingerprint,
                    token=access_token,
                    type="access_token",
                    created_at=datetime.now(),
                    root_token=refresh_token,
                    session_id=session_id,
                    user_id=db_user.id
                )
                updated_access = access_log

                refresh_log = TokenLog(
                    fingerprint=fingerprint,
                    token=refresh_token,
                    type="refresh_token",
                    created_at=datetime.now(),
                    root_token=refresh_token,
                    session_id=session_id,
                    user_id=db_user.id
                )
                updated_refresh = refresh_log

                db.add(access_log)
                db.add(refresh_log)
                await db.commit()
                print(f"Added new tokens for user_id={db_user.id}")
        else:
            #If user not found in token_logs
            #first time log in
            access_log = TokenLog(
                fingerprint=fingerprint,
                token=access_token,
                type="access_token",
                created_at=datetime.now(),
                root_token=refresh_token,
                session_id=session_id,
                user_id=db_user.id
            )
            updated_access = access_log

            refresh_log = TokenLog(
                fingerprint=fingerprint,
                token=refresh_token,
                type="refresh_token",
                created_at=datetime.now(),
                root_token=refresh_token,
                session_id=session_id,
                user_id=db_user.id
            )
            updated_refresh = refresh_log

            db.add(access_log)
            db.add(refresh_log)
            await db.commit()
            print(f"Added new tokens for user_id={db_user.id}")
            
        if not updated_access or not updated_refresh:
            raise HTTPException(status_code=500, detail="Internal error: token log missing.")
        #Save TokenLog to Redis cache
        access_key = f"TokenLog:{access_token}"
        refresh_key = f"TokenLog:{refresh_token}"
        access_data = {
            "id": updated_access.id,
            "fingerprint": fingerprint,
            "token": access_token,
            "type": "access_token",
            "root_token":refresh_token,
            "session_id": session_id,
            "user_id": db_user.id,
            "created_at": updated_access.created_at.isoformat()
        }
        refresh_data = {
            "id": updated_refresh.id,
            "fingerprint": fingerprint,
            "token": refresh_token,
            "type": "refresh_token",
            "root_token" : refresh_token,
            "session_id": session_id,
            "user_id": db_user.id,
            "created_at": updated_refresh.created_at.isoformat()
        }
        # set TTL: access token 15 phút, refresh token 7 ngày
        await redis_client.setex(access_key, 900, json.dumps(access_data))
        await redis_client.setex(refresh_key, 604800, json.dumps(refresh_data))


        # response
        response_data = {
            "access": access_token,
            "refresh": refresh_token,
            "sessionId":session_id
        }

        return jsonable_encoder(response_data)


    # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
    #     detail="Invalid Username Or Password"
    # )
    return JSONResponse(
       status_code=status.HTTP_401_UNAUTHORIZED,
       content={"message": "log in again"}
    )



#refreshing tokens
@auth_router.get('/refresh')
async def refresh_token(request: Request, response: Response, Authorize: AuthJWT = Depends(),db: Session = Depends(get_db)):
    """
    ## Refresh Access Token
    This endpoint creates a new access token using a valid refresh token.
    """
    # (to go to this endpoint. request has already walked through fingerprint checking middleware. So we do not need to check fingerprint again)

    try:
        # checking validation of refresh token
        Authorize.jwt_refresh_token_required()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please provide a valid refresh token"
        )

    # Take refresh token from header
    authorization_header = request.headers.get("authorization")

    refresh_token = authorization_header.split(" ", 1)[1].strip()

    # Take the user
    current_user = Authorize.get_jwt_subject()
    fingerprint = generate_fingerprint(request)
    session_id = request.cookies.get("sessionId")

    # Checking if the previous access_token created from refresh_token is still valid
    # existing_token = db.query(TokenLog).filter(
    #     TokenLog.root_token == refresh_token,
    #     TokenLog.type == "access_token"
    # ).first()
    stmt = select(TokenLog).where((TokenLog.root_token == refresh_token) & (TokenLog.type == "access_token"))
    result = await db.execute(stmt)
    existing_token = result.scalars().first()

    if existing_token:
        # if fingerprint  db_id matching -> overwrite new value of access token
        new_access_token = Authorize.create_access_token(subject=current_user)
        existing_token.token = new_access_token
        existing_token.created_at = datetime.now()
        await db.commit()
        return jsonable_encoder({"access": new_access_token})

    else:
        # if the refresh token on the same device hasn't created any valid access token yet. create new one
        new_access_token = Authorize.create_access_token(subject=current_user)
        stmt = select(User).where(User.username == current_user)
        result = await db.execute(stmt)
        user_obj = result.scalars().first()
        access_log = TokenLog(
            fingerprint=fingerprint,
            token=new_access_token,
            type="access_token",
            created_at=datetime.now(),
            root_token=refresh_token,
            session_id=session_id,
            # user_id=db.query(User).filter(User.username == current_user).first().id
            user_id = user_obj.id
        )
        db.add(access_log)
        await db.commit()
        return jsonable_encoder({"access": new_access_token})
    

@auth_router.post('/logout', status_code=status.HTTP_200_OK)
async def logout(response: Response, Authorize: AuthJWT = Depends(), db: Session = Depends(get_db)):
    try:
        Authorize.jwt_required()
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Token")
    
    # Lấy user từ token nếu cần
    user = Authorize.get_jwt_subject()
    stmt_user = select(User).where(User.username == user)
    result = await db.execute(stmt_user)
    current_user = result.scalars().first()
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # xoá tất cả token logs của user hiện tại:
    stmt = delete(TokenLog).where(TokenLog.user_id == current_user.id)
    await db.execute(stmt)
    await db.commit()
    
    # Xóa cookie chứa sessionId (nếu bạn dùng cookie để lưu session)
    response.delete_cookie("sessionId")
    
    return {"message": "Logged out successfully"}