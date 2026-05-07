import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
from datetime import datetime

# --- 1. 기본 설정 및 UI 구성 ---
st.set_page_config(page_title="CS 전문 상담 챗봇", page_icon="🎧")
st.title("🎧 쇼핑몰 고객 만족 센터")
st.caption("고객님의 불편사항을 경청하고 신속하게 도와드리겠습니다.")

# 사이드바 설정 (모델 선택 및 API 키 관리)
with st.sidebar:
    st.header("⚙️ 설정")
    selected_model = st.selectbox(
        "사용할 모델 선택",
        ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash"],
        index=0
    )
    
    # API 키 확인 (secrets 우선, 없을 경우 직접 입력)
    api_key = st.secrets.get("GEMINI_API_KEY", "")
    if not api_key:
        api_key = st.text_input("Gemini API Key를 입력하세요", type="password")
    
    if st.button("대화 기록 초기화"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.info(f"현재 모델: {selected_model}")

# --- 2. 데이터 로드 및 시스템 프롬프트 구성 ---
def load_faq_data():
    """CSV 데이터를 로드하여 시스템 명령문에 포함될 텍스트로 변환"""
    file_path = "faq_data.csv"
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            return f"\n\n[CSV 참조 데이터]\n{df.to_markdown(index=False)}"
        except Exception:
            return ""
    return ""

faq_context = load_faq_data()

# 시스템 인스트럭션 정의
base_instruction = (
    "당신은 쇼핑몰의 전문 고객 상담사입니다. 사용자의 불편/불만에 대해 정중하고 공감 어린 말투로 응답하세요.\n"
    "사용자의 불편 사항을 구체적(무엇이/언제/어디서/어떻게)으로 정리하여 수집하고, 이를 사내 담당자에게 전달한다는 취지를 안내하세요.\n"
    "대화의 마지막 단계에서는 담당자가 확인 후 회신할 수 있도록 사용자의 이메일 주소를 요청하세요.\n"
    "만약 사용자가 연락처 제공을 거부하면: '죄송하지만, 연락처 정보를 받지 못하여 담당자의 검토 내용을 직접 안내해 드리기 어렵습니다.'라고 정중히 마무리하세요."
)

if faq_context:
    base_instruction += (
        f"\n{faq_context}\n"
        "답변 시 위 [CSV 참조 데이터]를 우선적으로 확인하여 안내하세요. "
        "데이터에 없는 내용이라면 임의로 지어내지 말고 '담당 부서 확인 후 안내해 드리겠습니다'라고 답변하세요."
    )

# --- 3. 세션 상태(Session State) 초기화 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 4. 챗봇 엔진 및 대화 출력 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=selected_model,
        system_instruction=base_instruction
    )

    # 대화 내역 표시 (UI)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 채팅 입력창
    if prompt := st.chat_input("불편하신 점을 말씀해 주세요."):
        # 사용자 메시지 저장
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 모델 응답 생성
        with st.chat_message("assistant"):
            try:
                # 메모리 최적화: 최근 6턴(12개 메시지)만 컨텍스트로 전달
                history_for_model = [
                    {"role": m["role"], "parts": [m["content"]]} 
                    for m in st.session_state.messages[-12:]
                ]
                
                # API 호출
                chat_session = model.start_chat(history=history_for_model[:-1])
                response = chat_session.send_message(prompt)
                
                full_response = response.text
                st.markdown(full_response)
                
                # 어시스턴트 메시지 저장
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                # 429 ResourceExhausted 에러 처리 및 일반 에러 대응
                if "429" in str(e):
                    st.error("현재 사용량이 많아 응답이 지연되고 있습니다. 1분 뒤에 다시 시도해 주세요.")
                else:
                    st.error(f"오류가 발생했습니다: {str(e)}")

    # --- 5. 로그 저장 및 다운로드 기능 ---
    if st.session_state.messages:
        st.divider()
        log_df = pd.DataFrame(st.session_state.messages)
        csv_data = log_df.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label="💾 전체 대화 내역 다운로드 (CSV)",
            data=csv_data,
            file_name=f"chat_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
else:
    st.warning("API 키를 설정해야 대화를 시작할 수 있습니다.")
