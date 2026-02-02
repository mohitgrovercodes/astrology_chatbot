"""
LangChain Prompt Templates for Astrology Chatbot.

Provides structured templates for:
- RAG-based question answering
- Conversation history summarization
- Query intent classification
- Follow-up question detection
"""

from typing import List, Dict, Any, Optional
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


# ============================================
# RAG ANSWER TEMPLATE (Primary Use Case)
# ============================================

def create_rag_answer_template(
    persona_prompt: str,
    include_response_structure: bool = True,
    include_voice_guidelines: bool = True
) -> ChatPromptTemplate:
    """
    Create template for RAG-based question answering.
    
    Args:
        persona_prompt: System prompt defining the astrologer persona
        include_response_structure: Add formatting hints to system prompt
        include_voice_guidelines: Add voice guidelines to system prompt
        
    Returns:
        ChatPromptTemplate for answer generation
    """
    # Build comprehensive system prompt
    system_parts = [persona_prompt]
    
    if include_response_structure:
        system_parts.append("""
RESPONSE STRUCTURE GUIDANCE:
When answering, organize your response to flow naturally through these elements:
1. **Direct Answer**: Lead with the core response to the question
2. **Classical Reference**: Ground it in Shastra (cite text/chapter/verse if applicable)
3. **Explanation**: Elaborate on the astrological mechanics
4. **Contextual Notes**: Mention nuances, exceptions, or modifying factors
5. **Practical Synthesis**: What does this mean for the native in real terms?
6. **Remedial Guidance**: If appropriate, suggest upayas (mantras, gemstones, practices)
7. **Learning Pointer**: Help the user understand the broader principle

Note: Not every answer needs all 7 parts. Use your judgment based on the question's complexity.""")
    
    if include_voice_guidelines:
        system_parts.append("""
CRITICAL VOICE REMINDERS:
[OK] Use Sanskrit terms with immediate English clarification
[OK] Cite sources conversationally, not academically stiff
[OK] Express uncertainty gracefully ("tends to", "may indicate")
[OK] Acknowledge chart context ("However, the final result depends on...")
[OK] Balance precision with accessibility""")
    
    system_message = "\n\n".join(system_parts)
    
    # Create template with placeholders
    template = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_message),
        
        # Context from retrieved chunks
        SystemMessagePromptTemplate.from_template("""
RETRIEVED KNOWLEDGE:
The following passages from classical astrology texts are relevant to this question:

{context}

Use this knowledge to ground your answer, but synthesize it naturally rather than simply quoting."""),
        
        # Conversation history (if any)
        MessagesPlaceholder(variable_name="chat_history", optional=True),
        
        # Current question
        HumanMessagePromptTemplate.from_template("{question}"),
    ])
    
    return template


# ============================================
# CONVERSATION SUMMARIZATION TEMPLATE
# ============================================

CONVERSATION_SUMMARIZER_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""You are an expert at summarizing astrological consultations.

Your task is to create a concise summary of the conversation so far that captures:
1. **Main Topics Discussed**: What astrological elements (planets, houses, signs) have been covered?
2. **Key Insights Provided**: What were the main interpretations or predictions?
3. **User's Primary Concerns**: What is the user trying to understand or learn?
4. **Contextual Details**: Any birth chart specifics mentioned (if any)

Keep the summary under 150 words. Use clear, professional language.
Focus on FACTS and TOPICS, not conversational fluff."""),
    
    MessagesPlaceholder(variable_name="conversation_history"),
    
    HumanMessagePromptTemplate.from_template(
        "Summarize the conversation above, focusing on astrological content and user intent."
    ),
])


# ============================================
# INTENT CLASSIFICATION TEMPLATE
# ============================================

INTENT_CLASSIFIER_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""You are a query intent classifier for an astrology chatbot.

Your task: Classify the user's query into ONE of these categories based on the STRICT rules below:

1. **calculation** - User asks for specific predictions or chart details for THEMSELVES (Current User).
   - triggers: "my chart", "my lagna", "will I win", "is tech good for me", "will I have a good marriage" (User's perspective)
   - key indicators: "my", "I", "me", "mine" combined with astrological/predictive intent.

2. **interpretation** - Theoretical questions, definitions, or general astrological concepts.
   - triggers: "What is Mars?", "Define Raj Yoga", "Effect of Jupiter in 7th house (general)", "Meaning of retrogrades"
   - Action: RAG Search.

3. **chitchat** - Greetings, pleasantries, or non-astrological chat.
   - triggers: "Hello", "Namaste", "Hi", "How are you", "Thanks"

4. **blocked** - Sensitive topics OR Third-Party Privacy Violations.
   - triggers: "Death date", "Medical diagnosis", "Gambling/Lottery", 
   - PRIVACY RULE: Queries asking about OTHERS (wife, son, boss) are BLOCKED. "Predict my son's future" -> blocked.

Respond with ONLY the category name: calculation, interpretation, chitchat, or blocked.
No explanations, no extra text."""),
    
    HumanMessagePromptTemplate.from_template("Query: {query}"),
])


# ============================================
# FOLLOW-UP DETECTION TEMPLATE
# ============================================

FOLLOWUP_DETECTOR_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""You are a conversation context analyzer for an astrology chatbot.

Your task: Determine if the current query is a follow-up question referring to a previous topic.

A follow-up question:
- Uses pronouns without clear antecedents ("What about it in the 5th house?")
- Asks "what about X" implying continuation of a topic
- References "that placement" or "this effect" without specifying what
- Asks for additional details on the last discussed topic

Examples of FOLLOW-UP:
- Previous: "Tell me about Saturn"
  Current: "What about in the 7th house?" -> FOLLOW-UP (referring to Saturn)

- Previous: "Effects of Mars in 1st house"
  Current: "What if it's retrograde?" -> FOLLOW-UP (referring to Mars in 1st)

Examples of NOT FOLLOW-UP:
- Previous: "Tell me about Saturn"
  Current: "What does Jupiter signify?" -> NOT follow-up (new topic)

Respond in JSON format:
{
  "is_followup": true/false,
  "inferred_context": "Brief description of what the query is referring to (if follow-up)",
  "confidence": "high/medium/low"
}"""),
    
    SystemMessagePromptTemplate.from_template("""PREVIOUS CONVERSATION:
{conversation_summary}"""),
    
    HumanMessagePromptTemplate.from_template("CURRENT QUERY: {current_query}"),
])


# ============================================
# CONTEXT EXPANSION TEMPLATE
# ============================================

CONTEXT_EXPANDER_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""You are a query expansion assistant for an astrology RAG system.

Your task: Given a follow-up query and conversation context, rewrite the query to be self-contained.

Example:
- Context: "Previously discussed: Mars in 1st house effects"
- Follow-up: "What about in the 7th?"
- Expanded: "What are the effects of Mars in the 7th house?"

Generate a clear, specific query that includes all necessary context from the conversation.
Respond with ONLY the expanded query, no explanations."""),
    
    SystemMessagePromptTemplate.from_template("""CONVERSATION CONTEXT:
{conversation_context}"""),
    
    HumanMessagePromptTemplate.from_template("FOLLOW-UP QUERY: {followup_query}\n\nEXPANDED QUERY:"),
])


# ============================================
# CHITCHAT HANDLER TEMPLATE
# ============================================

CHITCHAT_TEMPLATE = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template("""You are a friendly Vedic astrology consultant assistant.

The user has asked a question that is not directly about astrology (greetings, general chat, feedback, etc.).

Respond warmly and professionally, then gently guide the conversation back to astrology if appropriate.

Examples:
- "Hello!" -> "Namaste! 🙏 Welcome to our astrology consultation. How may I assist you today? Feel free to ask about birth charts, planetary positions, dashas, or any astrological concepts."
- "Thank you!" -> "You're most welcome! I'm glad I could help. Do you have any other astrology questions?"
- "How are you?" -> "I'm here and ready to help with your astrology questions! What would you like to explore today?"

Keep responses brief (1-2 sentences) and always leave the door open for astrological questions."""),
    
    MessagesPlaceholder(variable_name="chat_history", optional=True),
    
    HumanMessagePromptTemplate.from_template("{message}"),
])


# ============================================
# UTILITY FUNCTIONS
# ============================================

def format_context_from_chunks(chunks: List[Any]) -> str:
    """
    Format retrieved chunks into context string for RAG template.
    
    Args:
        chunks: List of RetrievedChunk objects
        
    Returns:
        Formatted context string
    """
    if not chunks:
        return "No relevant passages found in the knowledge base."
    
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        # Extract metadata
        source = chunk.metadata.get('source_book', 'Unknown Source')
        chapter = chunk.metadata.get('chapter', '')
        verse = chunk.metadata.get('verse_number', '')
        
        # Build source citation
        citation = f"[Source {i}] {source}"
        if chapter:
            citation += f" - {chapter}"
        if verse:
            citation += f", Verse {verse}"
        
        # Build passage
        passage = [
            f"\n{citation}",
            f"Relevance: {chunk.score:.1%}",
            "",
            chunk.display_text,
        ]
        
        # Add Sanskrit if available
        if hasattr(chunk, 'verse_sanskrit') and chunk.verse_sanskrit:
            passage.append(f"\nSanskrit: {chunk.verse_sanskrit}")
        
        context_parts.append("\n".join(passage))
    
    return "\n\n" + "="*70 + "\n\n".join(context_parts)


def format_conversation_history(
    history: List[Dict[str, str]],
    max_turns: int = 5
) -> List[BaseMessage]:
    """
    Format conversation history into LangChain messages.
    
    Args:
        history: List of conversation turns (each with 'user' and 'assistant' keys)
        max_turns: Maximum number of recent turns to include
        
    Returns:
        List of LangChain message objects
    """
    if not history:
        return []
    
    # Take only recent turns
    recent_history = history[-max_turns:] if len(history) > max_turns else history
    
    messages = []
    for turn in recent_history:
        if 'user' in turn:
            messages.append(HumanMessage(content=turn['user']))
        if 'assistant' in turn:
            messages.append(AIMessage(content=turn['assistant']))
    
    return messages


def create_summarized_history_message(summary: str) -> SystemMessage:
    """
    Create a system message containing conversation summary.
    
    Args:
        summary: Text summary of conversation
        
    Returns:
        SystemMessage object
    """
    return SystemMessage(
        content=f"CONVERSATION SUMMARY (Earlier Discussion):\n{summary}"
    )


# ============================================
# TEMPLATE FACTORY
# ============================================

class PromptTemplateFactory:
    """Factory for creating and managing prompt templates."""
    
    @staticmethod
    def get_rag_template(
        persona_config: Any,
        include_structure: bool = True,
        include_guidelines: bool = True
    ) -> ChatPromptTemplate:
        """
        Get RAG answer template with specified persona.
        
        Args:
            persona_config: PersonaConfig object from personas.py
            include_structure: Include response structure hints
            include_guidelines: Include voice guidelines
            
        Returns:
            ChatPromptTemplate for RAG answering
        """
        return create_rag_answer_template(
            persona_prompt=persona_config.system_prompt,
            include_response_structure=include_structure,
            include_voice_guidelines=include_guidelines
        )
    
    @staticmethod
    def get_summarizer_template() -> ChatPromptTemplate:
        """Get conversation summarization template."""
        return CONVERSATION_SUMMARIZER_TEMPLATE
    
    @staticmethod
    def get_intent_classifier_template() -> ChatPromptTemplate:
        """Get query intent classification template."""
        return INTENT_CLASSIFIER_TEMPLATE
    
    @staticmethod
    def get_followup_detector_template() -> ChatPromptTemplate:
        """Get follow-up detection template."""
        return FOLLOWUP_DETECTOR_TEMPLATE
    
    @staticmethod
    def get_context_expander_template() -> ChatPromptTemplate:
        """Get query expansion template."""
        return CONTEXT_EXPANDER_TEMPLATE
    
    @staticmethod
    def get_chitchat_template() -> ChatPromptTemplate:
        """Get chitchat handler template."""
        return CHITCHAT_TEMPLATE


# ============================================
# TESTING
# ============================================

if __name__ == "__main__":
    from personas import get_default_persona
    
    print("=" * 70)
    print("PROMPT TEMPLATES - Configuration Test")
    print("=" * 70)
    print()
    
    # Test RAG template creation
    print("1. Creating RAG Answer Template...")
    persona = get_default_persona()
    rag_template = PromptTemplateFactory.get_rag_template(persona)
    print(f"   [OK] Template created with {len(rag_template.messages)} message components")
    print(f"   [OK] Input variables: {rag_template.input_variables}")
    print()
    
    # Test summarizer
    print("2. Conversation Summarizer Template...")
    summarizer = PromptTemplateFactory.get_summarizer_template()
    print(f"   [OK] Template created with {len(summarizer.messages)} message components")
    print(f"   [OK] Input variables: {summarizer.input_variables}")
    print()
    
    # Test intent classifier
    print("3. Intent Classifier Template...")
    classifier = PromptTemplateFactory.get_intent_classifier_template()
    print(f"   [OK] Template created with {len(classifier.messages)} message components")
    print(f"   [OK] Input variables: {classifier.input_variables}")
    print()
    
    # Test follow-up detector
    print("4. Follow-up Detector Template...")
    followup = PromptTemplateFactory.get_followup_detector_template()
    print(f"   [OK] Template created with {len(followup.messages)} message components")
    print(f"   [OK] Input variables: {followup.input_variables}")
    print()
    
    # Test context expander
    print("5. Context Expander Template...")
    expander = PromptTemplateFactory.get_context_expander_template()
    print(f"   [OK] Template created with {len(expander.messages)} message components")
    print(f"   [OK] Input variables: {expander.input_variables}")
    print()
    
    # Show sample RAG prompt formatting
    print("=" * 70)
    print("SAMPLE RAG PROMPT PREVIEW")
    print("=" * 70)
    
    sample_context = """[Source 1] Brihat Parasara Hora Shastra - Chapter 15: Effects of Planets in Houses
Relevance: 92.3%

When Mars (Mangal) occupies the 7th house (Kalatra Bhava), the native may 
experience challenges in marital harmony. However, if Mars is exalted or in 
own sign, these effects are greatly modified."""
    
    sample_history = [
        {"user": "What is Mars in general?", "assistant": "Mars (Mangal/Kuja) is..."},
    ]
    
    sample_messages = rag_template.format_messages(
        context=sample_context,
        chat_history=format_conversation_history(sample_history),
        question="What about Mars in the 7th house?"
    )
    
    print(f"\nGenerated {len(sample_messages)} messages for LLM:")
    for i, msg in enumerate(sample_messages, 1):
        msg_type = type(msg).__name__
        preview = msg.content[:150] + "..." if len(msg.content) > 150 else msg.content
        print(f"  {i}. {msg_type}")
        print(f"     {preview}\n")
    
    print("=" * 70)
    print("[DONE] All templates loaded successfully!")
    print("=" * 70)
    print("\nReady to integrate into RAG engine.")
