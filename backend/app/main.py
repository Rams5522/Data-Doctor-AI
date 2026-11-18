from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from app.api.v1 import api_router

app = FastAPI(title="DataDoctor AI", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api")

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "DataDoctor AI"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)