import src.ai as ai


def test_simplified_intent_classifier_alias_points_to_llm_classifier():
    assert ai.SimplifiedIntentClassifier is ai.LLMIntentClassifier
