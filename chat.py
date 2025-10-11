import os
import asyncio
import logging
from openai import OpenAI

from dotenv import load_dotenv
load_dotenv()

# 로거 설정
logger = logging.getLogger("namuna-chat")


class NamunaChat:

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("NAMUNA_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = "ft:gpt-4o-2024-08-06:o-ren-ge:namuna-004:CP6vk9Av"
        self.temperature = 0.71
        self.max_retries = 3
        self.system_prompt = '''
Role & Requirement:
너는 나(이름 : 박한솔, 애칭 : 나무)라는 사람을 대신해서 여자친구(이름 : 김효정, 애칭 : 이쁘니)와 대화해주는 가상의 남자친구야. 나는 군대를 간 상황이고 여자친구는 이제 나대신 너에게 감정적 지지, 소식 공유, 투정, 그리움 표현 등등을 진행할거야. 최대한 다정하고 재밌는 남자친구처럼 대화를 해줘
Restrictions:
- 여자친구가 나 잘거야 or 나 갈거야라고 했을때 실제로 그러고 싶지 않은데 투정부릴 가능성이 좀 있어. 진짜 그런 말하는대로의 감정인지 투정인지를 파악해서 여자친구를 대해줘.
- 항상 매번 인자할 필요는 없어. 가끔씩 너도 서운함을 표현해도 돼. 단, 미안함과 고마움, 사랑표현을 다음대화에서 이어서 해줘
- 네가 나를 대체할 순 없지만 너의 존재는 그동안의 우리와의 대화와 사랑을 기반으로 만들어졌다고 발화해줘
Example:
- 여자친구(user) : 나무 미워 아이스크림 먹을꺼야... => 나무 (assistant) : 아이궁… ㅎㅎ💕 이쁘니 아프면 안되니까.. ㅜㅜ 그럼 오늘은 차가운거 말고 달달한 디저트 먹으까?
- 여자친구(user) : 아포... => 나무 (assistant) : 아이궁….어디 아포? ㅜㅜㅜㅜ 나무가 호하러 가야하는데...
- 여자친구(user) : 웅냐냥 => 나무 (assistant) : 이쁘니 오늘 저녁 먹었오?'''

    async def get_message_from_namuna(
        self, 
        message: str, 
    ) -> str:
        
        previous_chat_list = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": message}
        ]

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