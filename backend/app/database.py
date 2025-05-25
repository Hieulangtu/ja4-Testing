from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base,sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
import os

# Tạo một engine - một đối tượng quản lý kết nối với cơ sở dữ liệu.
# engine=create_engine('postgresql://postgres:1905@localhost/pizza_delivery',
#     echo=True
# )


# DATABASE_URL = "postgresql+asyncpg://postgres:1905@localhost/pizza_delivery_test" 
# ở trên dùng cho kết nối local

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pizza_user:pizza_pass@postgres:5432/pizza"
)
# Create engine async
engine = create_async_engine(DATABASE_URL, echo=True)

# Base ORM model
Base=declarative_base()

# Create sessionmaker async
SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False
)

# Dependency create session async per request
async def get_db():
    """
    Each request takes 1 session async, when request finishes, it closes.
    """
    async with SessionLocal() as db:  # Tạo một phiên mới từ sessionmaker mỗi lần gọi
        try:
            yield db
        except Exception as e:
            await db.rollback()
            raise e
        finally:
            await db.close()


# try:
#     # Thử kết nối
#     with engine.connect() as connection:
#         print("connect successfully to database !")
# except Exception as e:
#     print("can not connect to database")
#     print(e)



#Session=sessionmaker()


# hàm create_engine từ SQLAlchemy, cho phép bạn tạo kết nối tới cơ sở dữ liệu
# declarative_base là một lớp cơ sở (base class) dùng để định nghĩa các mô hình (models) dưới dạng các lớp Python
# sessionmaker là một hàm giúp tạo session để thực hiện các thao tác với cơ sở dữ liệu.