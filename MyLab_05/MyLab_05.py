from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import os
import time
from pymongo import MongoClient
from bson import ObjectId
import redis
import json 

# Настройка SQLAlchemy
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db/postgres")
engine = create_engine(DATABASE_URL)

# Настройка Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://cache:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Секретный ключ для подписи JWT
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

# Подключение к MongoDB
MONGO_URI = "mongodb://root:pass@mongo:27017/"
mongo_client = MongoClient(MONGO_URI)
mongo_db = mongo_client["carpooling"]
mongo_users_collection = mongo_db["users"]

# Модель данных для пользователя
class UserMongo(BaseModel):
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

class Route(BaseModel):
    id: int
    user_id: int
    start_point: str
    end_point: str

# Модель SQLAlchemy
class TripDB(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    companions = Column(ARRAY(Integer), default=[])
    date = Column(datetime)

class RouteDB(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    start_point = Column(String, index=True)
    end_point = Column(String, index=True)

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


# POST /users - Создать нового пользователя (требует аутентификации)
@app.post("/users", response_model=UserMongo)
def create_user(user: UserMongo, current_user: str = Depends(get_current_client)):
    user_dict = user.dict()
    user_dict["hashed_password"] = pwd_context.hash(user_dict["hashed_password"])
    user_id = mongo_users_collection.insert_one(user_dict).inserted_id
    user_dict["id"] = str(user_id)
    return user_dict

# GET /users/{username} - Получить пользователя по логину (требует аутентификации)
@app.get("/users/{username}", response_model=UserMongo)
def get_user_by_username(username: str, current_user: str = Depends(get_current_client)):
    user = mongo_users_collection.find_one({"username": username})
    if user:
        user["id"] = str(user["_id"])
        return user
    raise HTTPException(status_code=404, detail="User not found")

# GET /users/{first_last} - Получить пользователя по маске имени и фамилии (требует аутентификации)
@app.get("/users", response_model=List[UserMongo])
def search_users_by_name(
    first_name: str, last_name: str, current_user: str = Depends(get_current_client)
):
    users = list(mongo_users_collection.find({"firstname": {"$regex": firstname, "$options": "i"}, "lastname": {"$regex": lastname, "$options": "i"}}))
    for user in users:
        user["id"] = str(user["_id"])
    return users

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

# POST /routes - Создать новую поездку (требует аутентификации)
@app.post("/routes", response_model=Route)
def create_route(route: Route, db: Session = Depends(get_db), current_user: str = Depends(get_current_client)):
    db_route = RouteDB(**route.dict())
    db.add(db_route)
    db.commit()
    db.refresh(db_route)

    # Обновление кеша
    cache_key = f"routes:user_id:{route.user_id}"
    routes = db.query(RouteDB).filter(RouteDB.user_id == route.user_id).all()
    redis_client.set(cache_key, json.dumps([route.dict() for route in routes]))

    return route

# GET /routes - Получить маршруты пользователя
@app.get("/routes", response_model=List[Route])
def get_user_routes(user_id: int, db: Session = Depends(get_db), current_user: str = Depends(get_current_client)):
    cache_key = f"routes:user_id:{user_id}"
    cached_routes = redis_client.get(cache_key)

    if cached_routes:
        return [Route(**route) for route in json.loads(cached_routes)]

    routes = db.query(RouteDB).filter(RouteDB.user_id == user_id).all()
    if routes:
        redis_client.set(cache_key, json.dumps([route.dict() for route in routes]))

    return routes

# Создание тестовых двнных:
def load_test_data():
    # Проверка существования пользователя перед добавлением
    def add_user(username, first_name, last_name, hashed_password, email):
        user = mongo_users_collection.find_one({"username": username})
        if not user:
            user = {
                "username": username,
                "first_name": first_name,
                "last_name": last_name,
                "hashed_password": hashed_password,
                "email": email,
            }
            mongo_users_collection.insert_one(user)

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

    db = SessionLocal()
    
    # Проверка существования поездки перед добавлением
    def add_trip(id, user_id, companions, date):
        trip = db.query(TripDB).filter(TripDB.id == id, TripDB.user_id == user_id, TripDB.date == date).first()
        if not trip:
            trip = TripDB(
                id=id,
                user_id=user_id,
                companions=companions,
                date=date,
            )
            db.add(trip)
    
    # Проверка существования маршрута перед добавлением
    def add_route(user_id, start_point, end_point):
        route = db.query(RouteDB).filter(RouteDB.user_id == user_id, RouteDB.start_point == start_point, RouteDB.end_point == end_point).first()
        if not route:
            route = RouteDB(
                user_id=user_id,
                start_point=start_point,
                end_point=end_point,
            )
            db.add(route)
    
    # Создание тестовых поездок
    add_trip(id=1, user_id=1, companions=[2], date="2023-12-25T10:00:00")
    add_trip(id=2, user_id=2, companions=[1], date="2023-12-25T12:00:00")

    # Создание тестовых маршрутов
    add_route(user_id=1, start_point="Moscow", end_point="St. Petersburg")
    add_route(user_id=2, start_point="St. Petersburg", end_point="Moscow")

    db.commit()
    db.close()

def wait_for_db(retries=10, delay=5):
    for _ in range(retries):
        try:
            mongo_client.admin.command('ismaster')
            print("Database is ready!")
            return
        except Exception as e:
            print(f"Database not ready yet: {e}")
            time.sleep(delay)
    raise Exception("Could not connect to the database")

    

# Запуск сервера
# http://localhost:8000/openapi.json swagger
# http://localhost:8000/docs портал документации

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    wait_for_db()
    load_test_data()