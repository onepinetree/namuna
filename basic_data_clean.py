# basic_data_clean.py
# 
# TODO:
# 1. CSV 파일 읽기 및 기본 전처리
# 2. 한 사람이 연속으로 보낸 메시지 합치기 (data_clean.py와 동일)
# 3. user -> assistant 1턴 쌍으로 데이터 구성
# 4. 필터링 키워드 체크 로직 구현
# 5. 필터링된 대화만 JSONL 파일로 저장
# 6. 통계 출력 (총 대화, 필터링된 대화, 저장된 대화)

import pandas as pd
import json
from datetime import datetime, timedelta


def filter_and_clean_message(content, filter_keywords):
    """
    메시지에서 필터링 키워드를 포함한 라인만 제거
    
    로직:
    1. 메시지를 \n으로 split
    2. 각 라인에 필터링 키워드가 포함되어 있으면 제거
    3. 남은 라인들을 \n으로 다시 합침
    4. 모든 라인이 제거되면 빈 문자열 반환
    
    Parameters:
    - content: 메시지 내용
    - filter_keywords: 필터링할 키워드 리스트
    
    Returns:
    - (cleaned_content, is_empty)
      - cleaned_content: 필터링된 메시지 내용
      - is_empty: True면 모든 내용이 제거됨 (전체 대화 제거해야 함)
    
    예시:
    - "사진" → ("", True) - 사진만 있으니 전체 제거
    - "이모티콘\n밥먹는중" → ("밥먹는중", False) - 이모티콘만 제거
    - "사진\n이모티콘" → ("", True) - 모두 필터링 키워드니 전체 제거
    """
    if not filter_keywords:
        return content, False
    
    # 메시지를 줄 단위로 분리
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # 해당 라인에 필터링 키워드가 포함되어 있는지 확인
        has_keyword = False
        for keyword in filter_keywords:
            if keyword in line:
                has_keyword = True
                break
        
        # 필터링 키워드가 없는 라인만 유지
        if not has_keyword:
            cleaned_lines.append(line)
    
    # 정리된 내용
    cleaned_content = '\n'.join(cleaned_lines)
    
    # 남은 내용이 없거나 공백만 있으면 빈 메시지로 간주
    is_empty = len(cleaned_content.strip()) == 0
    
    return cleaned_content, is_empty


def create_simple_finetuning_data(
    csv_file, 
    session_gap_minutes=30, 
    output_file='basic_finetuning_data.jsonl', 
    filter_keywords=None
):
    """
    카카오톡 CSV를 1턴(user-assistant 쌍)씩 JSONL로 변환
    
    Parameters:
    - csv_file: 입력 CSV 파일 경로
    - session_gap_minutes: 새 세션으로 분리할 시간 간격 (분)
    - output_file: 출력 JSONL 파일 경로
    - filter_keywords: 필터링할 키워드 리스트 (해당 키워드 포함 시 제외)
    """
    
    # TODO 1: CSV 파일 읽기
    print("📂 CSV 파일 읽는 중...")
    df = pd.read_csv(csv_file, header=None, names=['timestamp', 'sender', 'message'])
    print(f"  총 {len(df)}개 메시지 로드됨")
    
    conversations = []  # 최종 1턴씩 저장할 리스트
    
    # 현재 처리 중인 메시지 관련 변수
    last_sender = None
    last_time = None
    accumulated_messages = []  # 같은 사람이 연속으로 보낸 메시지 누적
    
    # 1턴 구성을 위한 임시 변수
    current_user_message = None
    current_assistant_message = None
    
    # 통계 변수
    total_turns = 0
    partially_filtered_turns = 0  # 일부 라인만 필터링된 대화
    completely_removed_turns = 0  # 모든 내용이 필터링되어 제거된 대화
    saved_turns = 0
    
    # TODO 2, 3: 메시지 처리 및 1턴 구성
    print("\n💬 메시지 처리 중...")
    
    for _, row in df.iterrows():
        # 빈 행 스킵
        if pd.isna(row['timestamp']) or pd.isna(row['sender']) or pd.isna(row['message']):
            continue
        
        current_time = pd.to_datetime(row['timestamp'])
        
        # 새 세션 시작 조건: 시간 간격이 큼
        if last_time and (current_time - last_time) > timedelta(minutes=session_gap_minutes):
            # 이전에 누적된 메시지가 있다면 저장
            if accumulated_messages:
                role = "assistant" if last_sender == "박한솔" else "user"
                merged_content = "\n".join(accumulated_messages)
                
                if role == "user":
                    current_user_message = merged_content
                else:
                    current_assistant_message = merged_content
                
                accumulated_messages = []
            
            # 세션이 끝났으므로 현재 턴 초기화
            current_user_message = None
            current_assistant_message = None
            last_sender = None
        
        # TODO 2: 같은 발신자가 연속으로 메시지 보낸 경우 합치기
        if row['sender'] == last_sender:
            # 같은 사람이 연속으로 보냄 -> 누적
            accumulated_messages.append(row['message'])
        else:
            # 발신자가 바뀜
            # 이전 발신자의 메시지를 저장
            if accumulated_messages:
                role = "assistant" if last_sender == "박한솔" else "user"
                merged_content = "\n".join(accumulated_messages)
                
                if role == "user":
                    current_user_message = merged_content
                else:
                    current_assistant_message = merged_content
                
                # TODO 3: user -> assistant 1턴 완성 시 저장
                if current_user_message and current_assistant_message:
                    total_turns += 1
                    
                    # TODO 4: 필터링 키워드 체크 및 라인 단위 필터링
                    cleaned_user, user_is_empty = filter_and_clean_message(current_user_message, filter_keywords)
                    cleaned_assistant, assistant_is_empty = filter_and_clean_message(current_assistant_message, filter_keywords)
                    
                    # user나 assistant 중 하나라도 빈 메시지면 전체 대화 제거
                    if user_is_empty or assistant_is_empty:
                        completely_removed_turns += 1
                    else:
                        # 부분 필터링 통계
                        if cleaned_user != current_user_message or cleaned_assistant != current_assistant_message:
                            partially_filtered_turns += 1
                        
                        # TODO 5: 필터링 통과 -> 저장
                        conversations.append({
                            "messages": [
                                {"role": "user", "content": cleaned_user},
                                {"role": "assistant", "content": cleaned_assistant}
                            ]
                        })
                        saved_turns += 1
                    
                    # 저장 후 초기화
                    current_user_message = None
                    current_assistant_message = None
            
            # 새 발신자 메시지 시작
            accumulated_messages = [row['message']]
            last_sender = row['sender']
        
        last_time = current_time
    
    # 마지막 메시지 처리
    if accumulated_messages:
        role = "assistant" if last_sender == "박한솔" else "user"
        merged_content = "\n".join(accumulated_messages)
        
        if role == "user":
            current_user_message = merged_content
        else:
            current_assistant_message = merged_content
        
        # 마지막 1턴 저장
        if current_user_message and current_assistant_message:
            total_turns += 1
            
            cleaned_user, user_is_empty = filter_and_clean_message(current_user_message, filter_keywords)
            cleaned_assistant, assistant_is_empty = filter_and_clean_message(current_assistant_message, filter_keywords)
            
            if user_is_empty or assistant_is_empty:
                completely_removed_turns += 1
            else:
                if cleaned_user != current_user_message or cleaned_assistant != current_assistant_message:
                    partially_filtered_turns += 1
                
                conversations.append({
                    "messages": [
                        {"role": "user", "content": cleaned_user},
                        {"role": "assistant", "content": cleaned_assistant}
                    ]
                })
                saved_turns += 1
    
    # TODO 5: JSONL 파일로 저장
    print("\n💾 JSONL 파일 저장 중...")
    with open(output_file, 'w', encoding='utf-8') as f:
        for conv in conversations:
            f.write(json.dumps(conv, ensure_ascii=False) + '\n')
    
    # TODO 6: 통계 출력
    print(f"\n✅ 변환 완료!")
    print(f"\n📊 통계:")
    print(f"  총 1턴 대화: {total_turns}개")
    print(f"  └─ 부분 필터링: {partially_filtered_turns}개 (일부 라인만 제거)")
    print(f"  └─ 완전 제거: {completely_removed_turns}개 (모든 내용이 필터링 키워드)")
    print(f"  └─ 저장된 대화: {saved_turns}개")
    
    if filter_keywords:
        print(f"\n🔍 필터링 키워드 ({len(filter_keywords)}개):")
        for keyword in filter_keywords:
            print(f"  - '{keyword}'")
    
    print(f"\n💾 파일 저장: {output_file}")
    
    return conversations


# 실행 예시
if __name__ == "__main__":
    # 필터링할 키워드 리스트 (이 단어들이 포함된 대화는 제외됨)
    filter_keywords = [
        '네이버 지도', 
        '이미지', 
        '사진', 
        '동영상', 
        '파일', 
        '위치',
        '삭제된 메시지',
        '이모티콘'
    ]
    
    # 사용법
    conversations = create_simple_finetuning_data(
        csv_file='chat_adjusted.csv',
        session_gap_minutes=30,
        output_file='basic_finetuning_data.jsonl',
        filter_keywords=filter_keywords
    )
    
    # 샘플 출력
    print("\n📝 샘플 대화 5개:")
    for i, conv in enumerate(conversations[:5], 1):
        print(f"\n{'='*60}")
        print(f"[대화 {i}]")
        for msg in conv['messages']:
            preview = msg['content'][:80].replace('\n', ' ')
            print(f"  {msg['role']:10s}: {preview}...")
        
        # 검증
        first_role = conv['messages'][0]['role']
        last_role = conv['messages'][1]['role']
        status = "✅" if first_role == "user" and last_role == "assistant" else "❌"
        print(f"  {status} 형식: {first_role} → {last_role}")
