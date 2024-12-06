from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os

# Настройка SQLAlchemy
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db/postgres")
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Секретный ключ для подписи JWT
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

# Модель данных для пользователя
class User(BaseModel):
    id: int
    username: str
    firstname: str
    lastname: str
    email: str
    hashed_password: str
    age: Optional[int] = None

class Trip(BaseModel):
    id: int
    user_id: int
    companions: List[int] = []
    date: datetime

# Модель SQLAlchemy
class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    firstname = Column(String)
    lastname = Column(String)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    age = Column(int, Optional, default=None)

class TripDB(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    companions = Column(ARRAY(Integer), default=[])
    date = Column(datetime)

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Настройка паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Настройка OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Зависимости для получения текущего пользователя
async def get_current_client(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        else:
            return username
    except JWTError:
        raise credentials_exception

# Создание и проверка JWT токенов
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Маршрут для получения токена
@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    user = db.query(UserDB).filter(UserDB.username == form_data.username).first()
    db.close()

    if user and pwd_context.verify(form_data.password, user.hashed_password):
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

# GET /users/{username} - Получить пользователя по логину (требует аутентификации)
@app.get("/users/{username}", response_model=User)
def get_user_username(username: str, current_user: str = Depends(get_current_client)):
    db = SessionLocal()
    user = db.query(UserDB).filter(UserDB.username == username).first()
    db.close()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# GET /users/{first_last} - Получить пользователя по маске имени и фамилии (требует аутентификации)
@app.get("/users/{username}", response_model=User)
def get_user_firstname(firstname: str, lastname: str, current_user: str = Depends(get_current_client)):
    db = SessionLocal()
    users = (
        db.query(UserDB)
        .filter(
            UserDB.first_name.ilike(f"%{firstname}%"), UserDB.last_name.ilike(f"%{lastname}%")
        )
        .all()
    )
    db.close()
    return users

# POST /users - Создать нового пользователя (требует аутентификации)
@app.post("/users", response_model=User)
def create_user(user: User, current_user: str = Depends(get_current_client)):
    db = SessionLocal()
    db_user = UserDB(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    db.close()
    return user

# POST /trips - Создать новую поездку (требует аутентификации)
@app.post("/trips", response_model=Trip)
def create_trip(trip: Trip, current_user: str = Depends(get_current_client)):
    db = SessionLocal()
    db_trips = TripDB(**trip.dict())
    db.add(db_trips)
    db.commit()
    db.refresh(db_trips)
    db.close()
    return trip

# PUT /trips/{trip_id}/companions - Подключение пользователей к поездке
@app.post("/trips/{trip_id}/companions", response_model=Trip)
def add_to_trip(trip_id: int, user_id: int, current_user: str = Depends(get_current_client)):
    db = SessionLocal()
    trip = db.query(TripDB).filter(TripDB.id == trip_id).first()
    if trip:
        if user_id not in trip.companions:
            trip.companions.append(user_id)
            db.commit()
            db.refresh(trip)
        db.close()
        return trip
    db.close()
    raise HTTPException(status_code=404, detail="Trip not found")

# GET /trips/{trip_id} - Получение информации о поездке
@app.get("/trips/{trip_id}", response_model=Trip)
def get_trip_info(trip_id: int, current_user: str = Depends(get_current_client)):
    db = SessionLocal()
    trip = db.query(TripDB).filter(TripDB.id == trip_id).first()
    db.close()
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


# Создание тестовых аккаунтов
def create_test():
    db = SessionLocal()

    # Добавление пользователя с проверкой существования
    def add_user(username, firstname, lastname, email, hashed_password, age=None):
        user = db.query(UserDB).filter(UserDB.username == username).first()
        if not user:
            user = UserDB(
                username=username,
                firstname=firstname,
                lastname=lastname,
                email=email,
                hashed_password=hashed_password,
                age=age
            )
            db.add(user)

    # Создание мастер-пользователя
    add_user(
        username="admin",
        first_name="Admin",
        last_name="Admin",
        hashed_password=pwd_context.hash("secret"),
        email="admin_secret@example.ru",
    )

    # Создание обычных пользователей
    add_user(
        username="DVDzuba",
        first_name="Dmitry",
        last_name="Dzuba",
        hashed_password=pwd_context.hash("teacher_password"),
        email="ddzuba@yandex.ru",
    )

    add_user(
        username="Kiros",
        first_name="Kirill",
        last_name="Ostrovskiy",
        hashed_password=pwd_context.hash("student_password"),
        email="kvostrovskij@mai.education; ",
    )

    db.commit()
    db.close()

# Запуск сервера
# http://localhost:8000/openapi.json swagger
# http://localhost:8000/docs портал документации

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    create_test()