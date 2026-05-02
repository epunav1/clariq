from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from routes import billing

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="CLARIQ API",
    description="AI-native universal commerce intelligence platform",
    version="0.4.0"
)

# CORS configuration
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://tryclariq.netlify.app",
    "https://tryclariq.com",
    "https://www.tryclariq.com",
    "https://beautiful-halva-c6f6b6.netlify.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from routes import query, connections, upload, auth
app.include_router(query.router)
app.include_router(connections.router)
app.include_router(upload.router)
app.include_router(auth.router)
app.include_router(billing.router)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
