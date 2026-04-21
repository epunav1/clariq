from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.query import router as query_router
from routes.connections import router as connections_router
from routes.upload import router as upload_router
from routes.auth import router as auth_router

app = FastAPI(title="CLARIQ API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(query_router)
app.include_router(connections_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"api": "healthy", "snowflake": "connected"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)