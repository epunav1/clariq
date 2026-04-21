from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.query import router

app = FastAPI(title="CLARIQ API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"status": "CLARIQ is live", "version": "0.1.0"}