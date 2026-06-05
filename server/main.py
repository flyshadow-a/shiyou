# server/main.py
from __future__ import annotations

from fastapi import FastAPI

from server.routers import health, strategy, images, reports, feasibility, files


app = FastAPI(
    title="Shiyou Backend API",
    version="1.0.0",
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["strategy"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(feasibility.router, prefix="/api/feasibility", tags=["feasibility"])

# 这个是新增的通用文件接口：
# /api/files/latest-model
# /api/files/download/latest-model
# /api/files/latest-sea
# /api/files/download/latest-sea
app.include_router(files.router, prefix="/api/files", tags=["files"])