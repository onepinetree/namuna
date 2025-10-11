from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
import uvicorn
import logging
import httpx
import asyncio
from chat import NamunaChat

app = FastAPI()

# NamunaChat 전역 인스턴스
namuna_chat = None

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("fastapi-logger")
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)


# 시작 이벤트: NamunaChat 초기화
@app.on_event("startup")
async def startup_event():
    global namuna_chat
    logger.info("🚀 서버 시작: NamunaChat 초기화 중...")
    try:
        namuna_chat = NamunaChat()
        logger.info("✅ NamunaChat 초기화 완료")
    except Exception as e:
        logger.error(f"❌ NamunaChat 초기화 실패: {e}")
        raise


# 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("=" * 60)
    logger.info(f"📥 [요청 들어옴] {request.method} {request.url.path}")
    logger.info(f"🌐 클라이언트 IP: {request.client.host if request.client else 'Unknown'}")
    logger.info(f"🔗 전체 URL: {request.url}")
    
    logger.info("📋 요청 헤더:")
    for header_name, header_value in request.headers.items():
        logger.info(f"   {header_name}: {header_value}")
    
    if request.method == "POST":
        try:
            body = await request.body()
            if body:
                body_str = body.decode('utf-8')
                logger.info(f"📦 요청 본문: {body_str}")
            else:
                logger.info("📦 요청 본문: (비어있음)")
            
            async def receive():
                return {"type": "http.request", "body": body}
            request._receive = receive
        except Exception as e:
            logger.error(f"❌ 요청 본문 읽기 실패: {str(e)}")
    
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
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": f"경로를 찾을 수 없습니다: {request.method} {request.url.path}",
                "available_endpoints": [
                    {"method": "POST", "path": "/api/namuna_chat", "description": "나무나 AI 챗봇 (콜백 방식)"},
                ],
                "tip": "API 문서를 보려면 /docs 로 접속하세요"
            }
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})





# 🔹 새로운 콜백 엔드포인트
@app.post("/api/namuna_chat")
async def namuna_chat_callback(request: Request, background_tasks: BackgroundTasks):
    logger.info("🔄 namuna_chat 엔드포인트 실행 중...")
    
    try:
        # 요청 본문 파싱
        body = await request.json()
        
        # callbackUrl 추출
        callback_url = body.get("userRequest", {}).get("callbackUrl")
        user_message = body.get("userRequest", {}).get("utterance", "")
        
        logger.info(f"📞 콜백 URL 추출: {callback_url}")
        logger.info(f"💬 사용자 발화: {user_message}")
        
        if not callback_url:
            logger.warning("⚠️ callbackUrl이 없습니다. 일반 응답으로 처리합니다.")
            # callbackUrl이 없으면 일반 응답
            return JSONResponse(status_code=200, content={
                "version": "2.0",
                "template": {
                    "outputs": [
                        {
                            "simpleText": {
                                "text": "hello I'm Namuna. 이쁘니 미안해 오류 발생"
                            }
                        }
                    ]
                }
            })
        
        # 백그라운드 작업으로 콜백 처리 등록
        background_tasks.add_task(process_callback, callback_url, user_message)
        
        # 즉시 응답 (useCallback: true)
        immediate_response = {
            "version": "2.0",
            "useCallback": True,
            "data": {
                "text": "나무나 생각중.. ☺️ "
            }
        }
        
        logger.info("✅ 즉시 응답 전송 완료 (useCallback: true)")
        return JSONResponse(status_code=200, content=immediate_response)
        
    except Exception as e:
        logger.error(f"❌ 에러 발생: {str(e)}")
        return JSONResponse(status_code=500, content={
            "error": "Internal Server Error",
            "message": str(e)
        })


# 🔹 콜백 처리 함수 (백그라운드 작업)
async def process_callback(callback_url: str, user_message: str):
    """
    시간이 걸리는 작업을 처리하고 결과를 callbackUrl로 전송
    """
    try:
        logger.info("🔧 백그라운드 작업 시작...")
        
        # NamunaChat으로 AI 응답 생성 (전역 인스턴스 사용)
        ai_response = await namuna_chat.get_message_from_namuna(user_message)
        logger.info(f"🤖 AI 응답 생성 완료: {ai_response[:50]}...")
        
        # 최종 응답 데이터 생성
        final_response = {
            "version": "2.0",
            "template": {
                "outputs": [
                    {
                        "simpleText": {
                            "text": ai_response
                        }
                    }
                ]
            }
        }
        
        # callbackUrl로 최종 응답 전송
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"📤 콜백 URL로 최종 응답 전송 중: {callback_url}")
            response = await client.post(callback_url, json=final_response)
            
            if response.status_code == 200:
                logger.info("✅ 콜백 전송 성공!")
                callback_result = response.json()
                logger.info(f"📥 콜백 응답: {callback_result}")
            else:
                logger.error(f"❌ 콜백 전송 실패: 상태 코드 {response.status_code}")
                logger.error(f"응답 내용: {response.text}")
                
    except Exception as e:
        logger.error(f"❌ 콜백 처리 중 에러 발생: {str(e)}")


# 🔹 콜백 응답 수신용 엔드포인트 (테스트용 - 실제로는 카카오 서버가 처리)
# @app.post("/callback/result")
# async def callback_result(request: Request):
#     """
#     콜백 응답을 받는 엔드포인트 (테스트/디버깅용)
#     실제 환경에서는 카카오 서버가 직접 처리하므로 이 엔드포인트는 필요 없음
#     """
#     body = await request.json()
#     logger.info("📨 콜백 결과 수신:")
#     logger.info(f"{body}")
#     return JSONResponse(status_code=200, content={"status": "received"})


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 나무나 AI 챗봇 서버 시작!")
    print("=" * 60)
    print(f"📍 서버 주소: http://0.0.0.0:8000")
    print(f"📖 API 문서: http://localhost:8000/docs")
    print("\n등록된 엔드포인트:")
    print("  - POST /api/namuna_chat (나무나 AI 챗봇 - 콜백 방식)")
    print("=" * 60 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")