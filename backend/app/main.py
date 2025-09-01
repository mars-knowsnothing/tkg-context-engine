from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from .api import knowledge, relations, query, chat
from .services.graphiti_service import GraphitiService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    graphiti_service = GraphitiService()
    await graphiti_service.initialize()
    app.state.graphiti_service = graphiti_service
    
    yield
    
    # Shutdown
    await graphiti_service.close()

app = FastAPI(
    title="TKG Context Engine API",
    description="Time-aware Knowledge Graph Context Management System",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(relations.router, prefix="/api/relations", tags=["relations"])
app.include_router(query.router, prefix="/api/query", tags=["query"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

@app.get("/")
async def root():
    return {"message": "TKG Context Engine API", "version": "0.1.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}