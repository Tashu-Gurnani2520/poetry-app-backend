from fastapi import FastAPI
from routes.auth import auth_router
from routes.classify import classify_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:8000", "http://<YOUR_LOCAL_IP>:8000"] for more safety
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth")
app.include_router(classify_router, prefix="/classify")

@app.get("/")
async def root():
    return {"msg": "Welcome to the Poetry App API"}
