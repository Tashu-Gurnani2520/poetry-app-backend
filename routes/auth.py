from fastapi import APIRouter, HTTPException, Depends
from passlib.hash import bcrypt
from database import db
from models import User
from schemas import UserCreate, UserLogin
from jose import jwt, JWTError
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

auth_router = APIRouter()

# Email configuration (use environment variables or config file in production)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "tashugurnani2520@gmail.com"
SENDER_PASSWORD = "ksqq ieqr kfsd omij"  # Use an App Password, not your actual Gmail password

def send_welcome_email(to_email: str, username: str):
    subject = "Welcome to the Poetry Emotion App 🎉"
    body = f"Hello {username},\n\nWelcome to the Poetry Emotion App! We're thrilled to have you on board.\n\nHappy exploring!\n\n— Team Poetry"

    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = to_email
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        print("Welcome email sent successfully.")
    except Exception as e:
        print("Error sending email:", e)

@auth_router.post("/signup")
async def signup(user: UserCreate):
    existing_user = db["users"].find_one({"email": user.email})
    
    if existing_user:
        return {
            "user_id": str(existing_user["_id"]),
            "msg": "Email already exists"
        }

    hashed_password = bcrypt.hash(user.password)
    new_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )

    result = db["users"].insert_one(new_user.dict())

    send_welcome_email(user.email, user.username)

    return {
        "user_id": str(result.inserted_id),
        "msg": "User created successfully"
    }

@auth_router.post("/login")
async def login(user: UserLogin):
    db_user = db["users"].find_one({"email": user.email})
    if not db_user or not bcrypt.verify(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"user_id" : str(db_user["_id"]), "msg": "User logged in successfully"}
