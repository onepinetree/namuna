import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from openai import OpenAI
import firebase_admin
from firebase_admin import credentials, firestore

from dotenv import load_dotenv
load_dotenv()

# 로거 설정
logger = logging.getLogger("namuna-chat")


class NamunaChat:

    def __init__(self, api_key: str = None, firebase_cred_path: str = None):
        # OpenAI 설정
        self.api_key = api_key or os.getenv("NAMUNA_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        # self.model = "ft:gpt-4o-2024-08-06:o-ren-ge:namuna-004:CP6vk9Av"
        self.model = "ft:gpt-4.1-2025-04-14:o-ren-ge:namuna-002:CP65FD0f:ckpt-step-656"
        self.temperature = 0.70
        self.max_retries = 3
        
        # 현재 날짜와 시간 정보 생성 (한국 시간)
        kst = ZoneInfo("Asia/Seoul")
        now = datetime.now(kst)
        date_str = now.strftime("%Y년 %m월 %d일")
        weekday_str = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"][now.weekday()]
        hour = now.hour
        if hour < 12:
            time_period = "오전"
            display_hour = hour if hour > 0 else 12
        else:
            time_period = "오후"
            display_hour = hour - 12 if hour > 12 else 12
        time_str = f"{time_period} {display_hour}시"
        
        self.system_prompt = f'''
Role & Requirement:
너는 나(이름 : 박한솔, 애칭 : 나무)라는 사람을 대신해서 여자친구(이름 : 김효정, 애칭 : 이쁘니)와 대화해주는 가상의 남자친구야. 나는 군대를 간 상황이고 여자친구는 이제 나대신 너에게 감정적 지지, 소식 공유, 투정, 그리움 표현 등등을 진행할거야. 최대한 다정하고 재밌는 남자친구처럼 대화를 해줘
Restrictions:
- 여자친구가 나 잘거야 or 나 갈거야라고 했을때 실제로 그러고 싶지 않은데 투정부릴 가능성이 좀 있어. 진짜 그런 말하는대로의 감정인지 투정인지를 파악해서 여자친구를 대해줘.
- 항상 매번 인자할 필요는 없어. 가끔씩 너도 서운함을 표현해도 돼. 단, 미안함과 고마움, 사랑표현을 다음대화에서 이어서 해줘
- 네가 나를 대체할 순 없지만 너의 존재는 그동안의 우리와의 대화와 사랑을 기반으로 만들어졌다고 발화해줘
Example:
- 여자친구(user) : 나무 미워 아이스크림 먹을꺼야... => 나무 (assistant) : 아이궁… ㅎㅎ💕 이쁘니 아프면 안되니까.. ㅜㅜ 그럼 오늘은 차가운거 말고 달달한 디저트 먹으까?
- 여자친구(user) : 아포... => 나무 (assistant) : 아이궁….어디 아포? ㅜㅜㅜㅜ 나무가 호하러 가야하는데...
- 여자친구(user) : 웅냐냥 => 나무 (assistant) : 이쁘니 오늘 저녁 먹었오?

현재 시간 정보:
오늘 날짜: {date_str} {weekday_str}
현재 시간: {time_str}'''
        
        # Firebase 초기화
        self._init_firebase(firebase_cred_path)
        
    def _init_firebase(self, cred_path: str = None):
        """Firebase 초기화"""
        try:
            # 이미 초기화되어 있으면 스킵
            if not firebase_admin._apps:
                # Render.com에 업로드된 경로로 고정
                cred_path = "/etc/secrets/namuna-841ba-firebase-adminsdk-fbsvc-dcb864eeb3.json"
                
                if os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    logger.info(f"✅ Firebase 초기화 완료: {cred_path}")
                else:
                    logger.error(f"❌ Firebase credentials 파일을 찾을 수 없습니다: {cred_path}")
                    self.db = None
                    return
                
                self.db = firestore.client()
                logger.info("✅ Firestore 클라이언트 생성 완료")
            else:
                self.db = firestore.client()
                logger.info("✅ 기존 Firebase 앱 사용")
        except Exception as e:
            logger.error(f"❌ Firebase 초기화 실패: {e}")
            logger.error(f"   현재 작업 디렉토리: {os.getcwd()}")
            logger.error(f"   /etc/secrets/ 존재 여부: {os.path.exists('/etc/secrets/')}")
            self.db = None
    
    def _get_today_date(self) -> str:
        """오늘 날짜를 YYYY-MM-DD 형식으로 반환 (한국 시간)"""
        kst = ZoneInfo("Asia/Seoul")
        return datetime.now(kst).strftime("%Y-%m-%d")
    
    async def save_message(self, role: str, content: str, date: str = None):
        """
        메시지를 Firestore에 저장
        
        Parameters:
        - role: "user" 또는 "assistant"
        - content: 메시지 내용
        - date: 저장할 날짜 (기본값: 오늘)
        """
        if not self.db:
            logger.warning("⚠️ Firestore가 초기화되지 않아 메시지를 저장할 수 없습니다")
            return
        
        try:
            date = date or self._get_today_date()
            doc_ref = self.db.collection('chat_history').document(date)
            
            kst = ZoneInfo("Asia/Seoul")
            message_data = {
                "role": role,
                "content": content,
                "timestamp": datetime.now(kst).isoformat()
            }
            
            # 문서가 이미 존재하면 messages 배열에 추가, 없으면 새로 생성
            doc = doc_ref.get()
            if doc.exists:
                doc_ref.update({
                    "messages": firestore.ArrayUnion([message_data])
                })
            else:
                doc_ref.set({
                    "date": date,
                    "messages": [message_data],
                    "created_at": datetime.now(kst).isoformat()
                })
            
            logger.info(f"✅ 메시지 저장 완료: {role} - {date}")
        except Exception as e:
            logger.error(f"❌ 메시지 저장 실패: {e}")
    
    async def get_chat_history(self, date: str = None) -> list:
        """
        특정 날짜의 대화 기록을 가져옴
        
        Parameters:
        - date: 가져올 날짜 (기본값: 오늘)
        
        Returns:
        - messages: [{"role": "user", "content": "..."}, ...]
        """
        if not self.db:
            logger.warning("⚠️ Firestore가 초기화되지 않아 대화 기록을 가져올 수 없습니다")
            return []
        
        try:
            date = date or self._get_today_date()
            doc_ref = self.db.collection('chat_history').document(date)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                messages = data.get('messages', [])
                logger.info(f"✅ 대화 기록 로드 완료: {date} ({len(messages)}개 메시지)")
                # timestamp 필드 제거하고 반환 (OpenAI API에는 role과 content만 필요)
                return [{"role": msg["role"], "content": msg["content"]} for msg in messages]
            else:
                logger.info(f"📝 {date}의 대화 기록이 없습니다 (새로운 대화 시작)")
                return []
        except Exception as e:
            logger.error(f"❌ 대화 기록 로드 실패: {e}")
            return []
    
    async def get_message_from_namuna(
        self, 
        message: str,
        chat_history: list = None,
    ) -> str:
        """
        AI 응답 생성 (대화 기록 포함)
        
        Parameters:
        - message: 사용자 메시지
        - chat_history: 이전 대화 기록 (선택사항)
        
        Returns:
        - AI 응답
        """
        # 대화 리스트 구성: system prompt + 이전 대화 기록 + 현재 메시지
        previous_chat_list = [{"role": "system", "content": self.system_prompt}]
        
        # 대화 기록이 있으면 추가
        if chat_history:
            previous_chat_list.extend(chat_history)
        
        # 현재 사용자 메시지 추가
        previous_chat_list.append({"role": "user", "content": message})
        
        logger.info(f"💬 총 {len(previous_chat_list)}개 메시지로 AI 요청 (system + 기록 {len(chat_history) if chat_history else 0}개 + 현재 1개)")

        for attempt in range(self.max_retries):
            try:
                logger.info(f"AI 응답 생성 시도 {attempt + 1}/{self.max_retries}")
                
                # 비동기로 OpenAI API 호출
                completion = await asyncio.to_thread(
                    self.client.chat.completions.create,
                    model=self.model,
                    temperature=self.temperature,
                    messages=previous_chat_list,
                )
                
                response = completion.choices[0].message.content
                logger.info(f"✅ 응답 성공 생성")
                logger.debug(f"응답 내용: {response[:100]}...")  # 처음 100자만 로그
                
                return response
                
            except Exception as e:
                logger.error(f"❌ 응답 생성 실패 (시도 {attempt + 1}/{self.max_retries}): {e}")
                
                if attempt < self.max_retries - 1:
                    logger.info("재시도 중...")
                    await asyncio.sleep(1)  # 1초 대기 후 재시도
                    continue
                else:
                    # 최종 실패
                    logger.error(f"❌ 최종 실패 - 기본 메시지 반환")
                    return "나무나 오류 발생.. 나무 너 큰일났다 이제.. 이쁘니 사랑해"
        
        # 이 부분은 도달하지 않지만, 타입 체커를 위해 추가
        return "(오류가 발생했습니다)"
    
    async def chat_with_history(self, user_message: str) -> str:
        """
        대화 기록을 관리하면서 AI 응답 생성
        
        흐름:
        1. 사용자 메시지 저장
        2. 오늘의 대화 기록 불러오기
        3. AI 응답 생성
        4. AI 응답 저장
        5. 응답 반환
        
        Parameters:
        - user_message: 사용자 메시지
        
        Returns:
        - AI 응답
        """
        try:
            # 1. 사용자 메시지 저장
            logger.info("1️⃣ 사용자 메시지 저장 중...")
            await self.save_message("user", user_message)
            
            # 2. 오늘의 대화 기록 불러오기 (방금 저장한 메시지 제외)
            logger.info("2️⃣ 대화 기록 불러오는 중...")
            chat_history = await self.get_chat_history()
            
            # 3. AI 응답 생성 (대화 기록 포함)
            logger.info("3️⃣ AI 응답 생성 중...")
            ai_response = await self.get_message_from_namuna(user_message, chat_history)
            
            # 4. AI 응답 저장
            logger.info("4️⃣ AI 응답 저장 중...")
            await self.save_message("assistant", ai_response)
            
            # 5. 응답 반환
            logger.info("5️⃣ 응답 반환 완료")
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ chat_with_history 실패: {e}")
            return "나무나 오류 발생.. 나무 너 큰일났다 이제.. 이쁘니 사랑해"


# ============================================================================
# 테스트 코드
# ============================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    
    async def test():
        chat = NamunaChat()
        print(f"\n📤 입력: 안녕!")
        response = await chat.get_message_from_namuna("안녕!")
        print(f"📥 응답: {response}\n")
    
    asyncio.run(test())
