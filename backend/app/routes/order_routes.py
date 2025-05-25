from fastapi import APIRouter,status,Depends
from fastapi.exceptions import HTTPException
from fastapi_jwt_auth import AuthJWT
from app.models import User,Order
from app.schemas import OrderModel,OrderStatusModel
from app.database import get_db
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import select

order_router=APIRouter(
    prefix="/orders",
    tags=['orders']
)

#session=Session(bind=engine)

@order_router.get('/')
async def hello(Authorize:AuthJWT=Depends()):

    """
        ## A sample hello world route
        This returns Hello world
    """

    try:
        Authorize.jwt_required()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )
    return {"message":"Hello World"}


@order_router.post('/order',status_code=status.HTTP_201_CREATED)
async def place_an_order(order:OrderModel,Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """
        ## Placing an Order
        This requires the following
        - quantity : integer
        - pizza_size: str
    
    """


    try:
        Authorize.jwt_required()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )

    current_user=Authorize.get_jwt_subject()

    #user=db.query(User).filter(User.username==current_user).first()
    stmt = select(User).where(User.username == current_user)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


    new_order=Order(
        pizza_size=order.pizza_size,
        quantity=order.quantity
    )

    new_order.user=user

    db.add(new_order)

    await db.commit()


    response={
        "pizza_size":new_order.pizza_size,
        "quantity":new_order.quantity,
        "id":new_order.id,
        "order_status":new_order.order_status
    }

    return jsonable_encoder(response)



    
@order_router.get('/orders')
async def list_all_orders(Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """
        ## List all orders
        This lists all  orders made. It can be accessed by superusers
        
    
    """


    try:
        Authorize.jwt_required()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )

    current_user=Authorize.get_jwt_subject()

    #user=db.query(User).filter(User.username==current_user).first()
    stmt = select(User).where(User.username == current_user)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if user.is_staff:
        #orders=db.query(Order).all()
        stmt_orders = select(Order)
        result_orders = await db.execute(stmt_orders)
        orders = result_orders.scalars().all()

        return jsonable_encoder(orders)

    raise  HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not a superuser"
        )


@order_router.get('/orders/{id}')
async def get_order_by_id(id:int,Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """
        ## Get an order by its ID
        This gets an order by its ID and is only accessed by a superuser
        

    """


    try:
        Authorize.jwt_required()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )

    user=Authorize.get_jwt_subject()

    #current_user=db.query(User).filter(User.username==user).first()
    stmt = select(User).where(User.username == user)
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if current_user.is_staff:
        #order=db.query(Order).filter(Order.id==id).first()
        stmt_order = select(Order).where(Order.id == id)
        result_order = await db.execute(stmt_order)
        order = result_order.scalars().first()

        if order:
            return jsonable_encoder(order)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not alowed to carry out request"
        )

    
@order_router.get('/user/orders')
async def get_user_orders(Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """
        ## Get a current user's orders
        This lists the orders made by the currently logged in users
    
    """


    try:
        Authorize.jwt_required()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )

    user=Authorize.get_jwt_subject()

    #current_user=db.query(User).filter(User.username==user).first()
    stmt = select(User).where(User.username == user)
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    #return jsonable_encoder(current_user.orders)
    if current_user:
        # Nếu relationship orders được cài đặt theo lazy load, bạn có thể trả về current_user.orders.
        # Tuy nhiên, trong async session, để đảm bảo load đầy đủ, có thể cần truy vấn riêng.
        stmt_orders = select(Order).where(Order.user_id == current_user.id)
        result_orders = await db.execute(stmt_orders)
        orders = result_orders.scalars().all()
        return jsonable_encoder(orders)
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@order_router.get('/user/order/{id}/')
async def get_specific_order(id:int,Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """
        ## Get a specific order by the currently logged in user
        This returns an order by ID for the currently logged in user
    
    """


    try:
        Authorize.jwt_required()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Token"
        )

    user=Authorize.get_jwt_subject()

    #current_user=db.query(User).filter(User.username==user).first()
    stmt = select(User).where(User.username == user)
    result = await db.execute(stmt)
    current_user = result.scalars().first()



    if current_user:
        # query specific order of current user
        stmt_order = select(Order).where(Order.id == id, Order.user_id == current_user.id)
        result_order = await db.execute(stmt_order)
        order = result_order.scalars().first()
        if order:
            return jsonable_encoder(order)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No order with such id")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")




@order_router.put('/order/update/{id}/')
async def update_order(id:int,order:OrderModel,Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):
    """
        ## Updating an order
        This udates an order and requires the following fields
        - quantity : integer
        - pizza_size: str

        *Only the owner of the order can update it.
    
    """

    try:
        Authorize.jwt_required()

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Token")
    
    user = Authorize.get_jwt_subject()
    stmt_user = select(User).where(User.username == user)
    result_user = await db.execute(stmt_user)
    current_user = result_user.scalars().first()

    if not current_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    stmt_order = select(Order).where(Order.id == id, Order.user_id == current_user.id)
    result_order = await db.execute(stmt_order)
    order_to_update = result_order.scalars().first()

    #order_to_update=db.query(Order).filter(Order.id==id).first()
   

    if order_to_update:
        order_to_update.quantity = order.quantity
        order_to_update.pizza_size = order.pizza_size
        await db.commit()
        await db.refresh(order_to_update)
        return jsonable_encoder(order_to_update)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or you are not authorized to update it")



    
@order_router.patch('/order/update/{id}/')
async def update_order_status(id:int,
        order:OrderStatusModel,
        Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):


    """
        ## Update an order's status
        This is for updating an order's status and requires ` order_status ` in str format
    """
    try:
        Authorize.jwt_required()

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Token")

    user=Authorize.get_jwt_subject()

    #current_user=db.query(User).filter(User.username==user).first()
    stmt = select(User).where(User.username == user)
    result = await db.execute(stmt)
    current_user = result.scalars().first()

    if current_user and current_user.is_staff:
        #order_to_update=db.query(Order).filter(Order.id==id).first()
        stmt_order = select(Order).where(Order.id == id)
        result_order = await db.execute(stmt_order)
        order_to_update = result_order.scalars().first()

        if order_to_update:
            order_to_update.order_status = order.order_status
            await db.commit()
            await db.refresh(order_to_update)
            return jsonable_encoder(order_to_update)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not allowed to carry out request")




@order_router.delete('/order/delete/{id}/',status_code=status.HTTP_204_NO_CONTENT)
async def delete_an_order(id:int,Authorize:AuthJWT=Depends(), db: Session = Depends(get_db)):

    """
        ## Delete an Order
        This deletes an order by its ID
    """

    try:
        Authorize.jwt_required()

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,detail="Invalid Token")
    
    user = Authorize.get_jwt_subject()
    # Lấy thông tin người dùng hiện tại
    stmt_user = select(User).where(User.username == user)
    result_user = await db.execute(stmt_user)
    current_user = result_user.scalars().first()

    if not current_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Nếu user là staff, cho phép xóa bất kỳ order nào
    
    if current_user.is_staff:
        stmt_order = select(Order).where(Order.id == id)
    else:
        # Nếu không phải staff, chỉ cho phép xóa order của chính user
        stmt_order = select(Order).where(Order.id == id, Order.user_id == current_user.id)

    result_order = await db.execute(stmt_order)
    order_to_delete = result_order.scalars().first()



    # return order_to_delete
    if order_to_delete:
        await db.delete(order_to_delete)
        await db.commit()
        return jsonable_encoder(order_to_delete)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or not authorized")