from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn
from pydantic import BaseModel
from typing import Any, Dict
import logging


app = FastAPI()

# CORS 완전 개방 (모든 보안 제거)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # 모든 origin 허용
    allow_credentials=True,           # 쿠키/인증 정보 허용
    allow_methods=["*"],              # 모든 HTTP 메서드 허용 (GET, POST, PUT, DELETE 등)
    allow_headers=["*"],              # 모든 헤더 허용
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fastapi-logger")

# 다른 라이브러리 로그 수준 조정
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


# 상세 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # 요청 정보 로그
    logger.info("=" * 60)
    logger.info(f"📥 [요청 들어옴] {request.method} {request.url.path}")
    logger.info(f"🌐 클라이언트 IP: {request.client.host if request.client else 'Unknown'}")
    logger.info(f"🔗 전체 URL: {request.url}")
    
    # 헤더 로그
    logger.info("📋 요청 헤더:")
    for header_name, header_value in request.headers.items():
        logger.info(f"   {header_name}: {header_value}")
    
    # 요청 본문 로그 (POST 요청인 경우)
    if request.method == "POST":
        try:
            body = await request.body()
            if body:
                body_str = body.decode('utf-8')
                logger.info(f"📦 요청 본문: {body_str}")
            else:
                logger.info("📦 요청 본문: (비어있음)")
            
            # body를 다시 사용할 수 있도록 재설정
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
        except Exception as e:
            logger.error(f"❌ 요청 본문 읽기 실패: {str(e)}")
    
    # 실제 엔드포인트 처리
    try:
        response = await call_next(request)
        logger.info(f"✅ [응답 전송] 상태 코드: {response.status_code}")
        logger.info("=" * 60)
        return response
    except Exception as e:
        logger.error(f"❌ [서버 오류] {str(e)}")
        logger.info("=" * 60)
        raise


# 404 에러 핸들러
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        logger.warning(f"⚠️ [404 NOT FOUND] 존재하지 않는 경로: {request.method} {request.url.path}")
        logger.warning(f"사용 가능한 엔드포인트:")
        logger.warning(f"  - POST /api/sayHello")
        logger.warning(f"  - GET  /docs (API 문서)")
        
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": f"경로를 찾을 수 없습니다: {request.method} {request.url.path}",
                "available_endpoints": [
                    {"method": "POST", "path": "/api/sayHello", "description": "인사 메시지 반환"},
                ],
                "tip": "API 문서를 보려면 /docs 로 접속하세요"
            }
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.post("/api/sayHello")
async def say_hello(request: Request):
    logger.info("💬 sayHello 엔드포인트 실행 중...")
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
    logger.info("💬 응답 준비 완료")
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
    print("\n" + "=" * 60)
    print("🚀 FastAPI 서버 시작!")
    print("=" * 60)
    print(f"📍 서버 주소: http://0.0.0.0:8000")
    print(f"📖 API 문서: http://localhost:8000/docs")
    print("\n등록된 엔드포인트:")
    print("  - POST /api/sayHello")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")