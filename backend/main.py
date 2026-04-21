from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.query import router as query_router
from routes.connections import router as connections_router
from routes.upload import router as upload_router

app = FastAPI(title="CLARIQ API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router, prefix="/api")
app.include_router(connections_router, prefix="/api")
app.include_router(upload_router, prefix="/api")


@app.get("/")
def root():
    return {"status": "CLARIQ is live", "version": "0.3.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
