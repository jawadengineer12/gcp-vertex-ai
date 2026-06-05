import os
import logging
from google import genai
from google.genai import types

LOGGER = logging.getLogger(__name__)


def generate_layout(user_prompt: str, matched_context_examples: list) -> str | None:
    """Takes user prompt and structural matches to generate layout data via Vertex AI."""

    # Instantiate the standard modern Google GenAI Client pointing to Vertex AI gateway
    client = genai.Client(
        vertexai=True,
        project="indesign-layout-ai",
        location="us-central1"
    )

    system_instruction = (
        "You are an expert AI layout engineering backend assistant.\n"
        "Your sole task is to generate structural layout data based on the provided user design brief.\n"
        "CRITICAL RULES:\n"
        "1. Return ONLY a raw JSON structure matching your target layout schema rules.\n"
        "2. Do NOT include any markdown code blocks, backticks (such as ```json), or wrapping symbols.\n"
        "3. Do NOT include any conversational text, descriptions, introductions, or closing remarks.\n"
        "4. Start your response directly with '{' and end exactly with '}'.\n"
        "5. Emphasize that element positions/size fields are allowed to extend outside page boundaries for bleeds."
    )

    # Reconstruct few-shot context matching the exact properties in your prompt library
    context_string = "\n\n".join([
        f"Matched Design Example (Page Index {ex['pageIndex']}):\n{ex['expected_layout_json']}"
        for ex in matched_context_examples
    ])

    combined_prompt = (
        f"Use the following structural design references for scaling, rules, and alignment patterns:\n"
        f"{context_string}\n\n"
        f"Now, generate a brand new layout specification for this designer instruction:\n"
        f"\"{user_prompt}\""
    )

    print("\n--- [STAGE 2: SENDING TO GEMINI VIA VERTEX AI] ---")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=combined_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.2,  # Kept low for deterministic structural accuracy
            ),
        )
        return response.text

    except Exception as e:
        print(f"\n[ERROR]: Stage 2 Inference failed: {str(e)}")
        return None
