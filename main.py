import requests
import certifi
import os
from typing import Optional
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime


os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "19Qm+au/fneSwUbcDMOXN3M2yRACl+9GT8c5OSQ7NVFVX0dFlgkB25b7/Rgc4CLH2fq4jshZibA3ZFCEl0Qsgqfp6e2Yte3tzfBZl31mT99QZYS2FIUNzOdBalFoFSDiDwhZV7pbgXOc9lBIJUbnJAdB04t89/1O/w1cDnyilFU="
os.environ["GOOGLE_API_KEY"] = ""
# Gemini key
app = FastAPI(title="GPS SOS API")

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)



class OptionalLocationRequest(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()

# 廣播 LINE
def send_text_broadcast(text: str):
    url = "https://api.line.me/v2/bot/message/broadcast"
    headers = {"Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messages":[{"type":"text","text":text}]}
    r = requests.post(url, headers=headers, json=payload, verify=certifi.where())
    print(f"[LINE] status={r.status_code}, response={r.text}")

# 簡單地址解析 (Nominatim)
def get_address_from_coordinates(lat, lon):
    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {"lat":lat, "lon":lon, "format":"json", "zoom":18}
        headers = {"User-Agent": "GPS-SOS-App"}
        res = requests.get(url, params=params, headers=headers, timeout=10)
        data = res.json()
        return data.get("display_name", f"{lat},{lon}")
    except:
        return f"{lat},{lon}"

# WebSocket 管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception as e:
                print(f"⚠️ 廣播失敗，移除 client: {e}")
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    print("📡 WebSocket 客戶端已連線")
    try:
        while True:
            data = await ws.receive_text()
            print("WebSocket 收到:", data)
            if data.lower() == "sos":
                print("📢 廣播給前端")
                await manager.broadcast("sos")
    except WebSocketDisconnect:
        manager.disconnect(ws)
        print("❌ WebSocket 客戶端斷線")



@app.post("/sos/button")
async def sos_button_trigger(loc: OptionalLocationRequest, request: Request):
    client_ip = request.client.host
    timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    if not loc or loc.latitude is None or loc.longitude is None:
        return {"error":"沒有 GPS"}
    address = get_address_from_coordinates(loc.latitude, loc.longitude)
    msg = f"🚨 緊急求救！\n時間: {timestamp}\n位置: {address}"
    print(msg)
    send_text_broadcast(msg)
    return {"status":"SOS 已發送","location":{"latitude":loc.latitude,"longitude":loc.longitude,"address":address,"ip":client_ip}}

