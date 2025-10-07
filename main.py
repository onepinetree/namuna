from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import BaseModel
from typing import Any, Dict

app = FastAPI()

# CORS 완전 개방 (모든 보안 제거)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # 모든 origin 허용
    allow_credentials=True,           # 쿠키/인증 정보 허용
    allow_methods=["*"],              # 모든 HTTP 메서드 허용 (GET, POST, PUT, DELETE 등)
    allow_headers=["*"],              # 모든 헤더 허용
)

# 요청 본문 로깅을 위한 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response


@app.post("/api/sayHello")
async def say_hello(request: Request):
    response_body = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleText": {
                        "text": "hello I'm Ryan"
                    }
                }
            ]
        }
    }
    
    return JSONResponse(status_code=200, content=response_body)


# @app.post("/api/showHello")
# async def show_hello(request: Request):
#     # 요청 본문 출력
#     body = await request.json()
#     print(body)
    
#     response_body = {
#         "version": "2.0",
#         "template": {
#             "outputs": [
#                 {
#                     "simpleImage": {
#                         "imageUrl": "https://t1.daumcdn.net/friends/prod/category/M001_friends_ryan2.jpg",
#                         "altText": "hello I'm Ryan"
#                     }
#                 }
#             ]
#         }
#     }
    
#     return JSONResponse(status_code=200, content=response_body)


if __name__ == "__main__":
    print("Example skill server listening on port 3000!")
    uvicorn.run(app, host="0.0.0.0", port=8000)