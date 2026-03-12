import datetime
from src.orchestration.orchestrator import EnhancedLangGraphOrchestrator
from src.api.routes.chat_stateless import EnhancedSessionManager, UserProfile

def main():
    # The orchestrator will auto-load its dependencies
    orchestrator = EnhancedLangGraphOrchestrator(
        intent_classifier=None,
        hybrid_retriever=None,
        prompt_builder=None,
        llm=None,
        fast_llm=None
    )
    
    manager = EnhancedSessionManager()
    # Clear session to ensure clean state
    manager.clear_session("user1010")

    # We will use user1010 profile
    user_profile = UserProfile(
        user_id="user1010",
        name="Mohit",
        date_of_birth="1995-10-01",
        time_of_birth="07:30:00",
        place_of_birth="Alwar, India",
        latitude=27.5530,
        longitude=76.6346,
        timezone="Asia/Kolkata",
        preferred_system="vedic",
    )

    # In Pydantic v2, it's model_dump(), but the code has a fallback for dict().
    # Let's use dict() for compatibility.
    user_profile_dict = user_profile.dict()

    manager.initialize_session(
        user_id=user_profile.user_id,
        user_profile=user_profile_dict,
        conversation_history=[]
    )

    print("--- Test 1: Marriage Query ---")
    
    # The process_query method expects session_data.
    # In a real scenario, this is built by the API route. We mock it here.
    session_data_q1 = {
        "chart_data": manager.get_chart_data("user1010"),
        "dasha_data": manager.get_dasha_data("user1010"),
        "transit_data": manager.get_transit_data("user1010"),
        "summary": manager.get_conversation_summary("user1010"),
        "intent_analysis": {"intent_type": "NEW_TOPIC"},
        "conversation_phase": manager.get_conversation_phase("user1010"),
        "original_user_question": "Meri shadi kab hogi ?",
        "detected_language": "hi-lat"
    }

    response1_state = orchestrator.process_query(
        query="Meri shadi kab hogi ?",
        user_id="user1010",
        conversation_history=[],
        user_profile_override=user_profile_dict,
        session_data=session_data_q1
    )
    
    response1_answer = response1_state.get('answer', '')
    print(f"Response: {response1_answer}")

    # Add the first exchange to history for the second query
    history = [
        {"role": "user", "content": "Meri shadi kab hogi ?"},
        {"role": "assistant", "content": response1_answer}
    ]
    # The session manager in the stateless route would handle this.
    # For this test, we'll manually update the history in redis.
    manager.overwrite_conversation_history(user_id="user1010", conversation_history=history)


    print("\n--- Test 2: Career Query ---")
    
    # Update session data for the second query
    session_data_q2 = {
        "chart_data": manager.get_chart_data("user1010"),
        "dasha_data": manager.get_dasha_data("user1010"),
        "transit_data": manager.get_transit_data("user1010"),
        "summary": manager.get_conversation_summary("user1010"),
        "intent_analysis": {"intent_type": "NEW_TOPIC"},
        "conversation_phase": manager.get_conversation_phase("user1010"),
        "original_user_question": "Mera career kab grow hoga ?",
        "detected_language": "hi-lat"
    }

    response2_state = orchestrator.process_query(
        query="Mera career kab grow hoga ?",
        user_id="user1010",
        conversation_history=history, # Pass the updated history
        user_profile_override=user_profile_dict,
        session_data=session_data_q2
    )
    
    print(f"Response: {response2_state.get('answer', '')}")


if __name__ == "__main__":
    main()
