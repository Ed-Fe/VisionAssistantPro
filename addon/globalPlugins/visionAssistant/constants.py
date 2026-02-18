# -*- coding: utf-8 -*-

import addonHandler
import config

addonHandler.initTranslation()

ADDON_NAME = addonHandler.getCodeAddon().manifest["summary"]
GITHUB_REPO = "mahmoodhozhabri/VisionAssistantPro"

CHROME_OCR_KEYS = [
    "AIzaSyA2KlwBX3mkFo30om9LUFYQhpqLoa_BNhE",
    "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
]

MODELS = [
    # --- 1. Recommended (Auto-Updating) ---
    # Translators: AI Model info. [Auto] = Automatic updates. (Latest) = Newest version.
    (_("[Auto]") + " Gemini Flash " + _("(Latest)"), "gemini-flash-latest"),
    (_("[Auto]") + " Gemini Flash Lite " + _("(Latest)"), "gemini-flash-lite-latest"),

    # --- 2. Current Standard (Free & Fast) ---
    # Translators: AI Model info. [Free] = Generous usage limits. (Preview) = Experimental or early-access version.
    (_("[Free]") + " Gemini 3.0 Flash " + _("(Preview)"), "gemini-3-flash-preview"),
    (_("[Free]") + " Gemini 2.5 Flash", "gemini-2.5-flash"),
    (_("[Free]") + " Gemini 2.5 Flash Lite", "gemini-2.5-flash-lite"),

    # --- 3. High Intelligence (Paid/Pro/Preview) ---
    # Translators: AI Model info. [Pro] = High intelligence/Paid tier. (Preview) = Experimental version.
    (_("[Pro]") + " Gemini 3.0 Pro " + _("(Preview)"), "gemini-3-pro-preview"),
    (_("[Pro]") + " Gemini 2.5 Pro", "gemini-2.5-pro"),
]

GEMINI_VOICES = [
    # Translators: Adjective describing a bright AI voice style.
    ("Zephyr", _("Bright")),
    # Translators: Adjective describing an upbeat AI voice style.
    ("Puck", _("Upbeat")),
    # Translators: Adjective describing an informative AI voice style.
    ("Charon", _("Informative")),
    # Translators: Adjective describing a firm AI voice style.
    ("Kore", _("Firm")),
    # Translators: Adjective describing an excitable AI voice style.
    ("Fenrir", _("Excitable")),
    # Translators: Adjective describing a youthful AI voice style.
    ("Leda", _("Youthful")),
    # Translators: Adjective describing a firm AI voice style.
    ("Orus", _("Firm")),
    # Translators: Adjective describing a breezy AI voice style.
    ("Aoede", _("Breezy")),
    # Translators: Adjective describing an easy-going AI voice style.
    ("Callirrhoe", _("Easy-going")),
    # Translators: Adjective describing a bright AI voice style.
    ("Autonoe", _("Bright")),
    # Translators: Adjective describing a breathy AI voice style.
    ("Enceladus", _("Breathy")),
    # Translators: Adjective describing a clear AI voice style.
    ("Iapetus", _("Clear")),
    # Translators: Adjective describing an easy-going AI voice style.
    ("Umbriel", _("Easy-going")),
    # Translators: Adjective describing a smooth AI voice style.
    ("Algieba", _("Smooth")),
    # Translators: Adjective describing a smooth AI voice style.
    ("Despina", _("Smooth")),
    # Translators: Adjective describing a clear AI voice style.
    ("Erinome", _("Clear")),
    # Translators: Adjective describing a gravelly AI voice style.
    ("Algenib", _("Gravelly")),
    # Translators: Adjective describing an informative AI voice style.
    ("Rasalgethi", _("Informative")),
    # Translators: Adjective describing an upbeat AI voice style.
    ("Laomedeia", _("Upbeat")),
    # Translators: Adjective describing a soft AI voice style.
    ("Achernar", _("Soft")),
    # Translators: Adjective describing a firm AI voice style.
    ("Alnilam", _("Firm")),
    # Translators: Adjective describing an even AI voice style.
    ("Schedar", _("Even")),
    # Translators: Adjective describing a mature AI voice style.
    ("Gacrux", _("Mature")),
    # Translators: Adjective describing a forward AI voice style.
    ("Pulcherrima", _("Forward")),
    # Translators: Adjective describing a friendly AI voice style.
    ("Achird", _("Friendly")),
    # Translators: Adjective describing a casual AI voice style.
    ("Zubenelgenubi", _("Casual")),
    # Translators: Adjective describing a gentle AI voice style.
    ("Vindemiatrix", _("Gentle")),
    # Translators: Adjective describing a lively AI voice style.
    ("Sadachbia", _("Lively")),
    # Translators: Adjective describing a knowledgeable AI voice style.
    ("Sadaltager", _("Knowledgeable")),
    # Translators: Adjective describing a warm AI voice style.
    ("Sulafat", _("Warm"))
]

BASE_LANGUAGES = [
    ("Arabic", "ar"), ("Bulgarian", "bg"), ("Chinese", "zh"), ("Czech", "cs"), ("Danish", "da"),
    ("Dutch", "nl"), ("English", "en"), ("Finnish", "fi"), ("French", "fr"),
    ("German", "de"), ("Greek", "el"), ("Hebrew", "he"), ("Hindi", "hi"),
    ("Hungarian", "hu"), ("Indonesian", "id"), ("Italian", "it"), ("Japanese", "ja"),
    ("Korean", "ko"), ("Nepali", "ne"), ("Norwegian", "no"), ("Persian", "fa"), ("Polish", "pl"),
    ("Portuguese", "pt"), ("Romanian", "ro"), ("Russian", "ru"), ("Spanish", "es"),
    ("Swedish", "sv"), ("Thai", "th"), ("Turkish", "tr"), ("Ukrainian", "uk"),
    ("Vietnamese", "vi")
]
SOURCE_LIST = [("Auto-detect", "auto")] + BASE_LANGUAGES
SOURCE_NAMES = [x[0] for x in SOURCE_LIST]
TARGET_LIST = BASE_LANGUAGES
TARGET_NAMES = [x[0] for x in TARGET_LIST]
TARGET_CODES = {x[0]: x[1] for x in BASE_LANGUAGES}

OCR_ENGINES = [
    # Translators: OCR Engine option (Fast but less formatted)
    (_("Chrome (Fast)"), "chrome"),
    # Translators: OCR Engine option (Slower but better formatting)
    (_("Gemini (Formatted)"), "gemini")
]

confspec = {
    "proxy_url": "string(default='')",
    "api_key": "string(default='')",
    "model_name": "string(default='gemini-flash-lite-latest')",
    "target_language": "string(default='English')",
    "source_language": "string(default='Auto-detect')",
    "ai_response_language": "string(default='English')",
    "smart_swap": "boolean(default=True)",
    "captcha_mode": "string(default='navigator')",
    "custom_prompts": "string(default='')",
    "custom_prompts_v2": "string(default='')",
    "default_refine_prompts": "string(default='')",
    "check_update_startup": "boolean(default=False)",
    "clean_markdown_chat": "boolean(default=True)",
    "copy_to_clipboard": "boolean(default=False)",
    "skip_chat_dialog": "boolean(default=False)",
    "ocr_engine": "string(default='chrome')",
    "tts_voice": "string(default='Puck')"
}

config.conf.spec["VisionAssistant"] = confspec

PROMPT_TRANSLATE = """
Task: Translate the text below to "{target_lang}".

Configuration:
- Target Language: "{target_lang}"
- Swap Language: "{swap_target}"
- Smart Swap: {smart_swap}

Rules:
1. DEFAULT: Translate the input strictly to "{target_lang}".
2. MIXED CONTENT: If the text contains mixed languages (e.g., Arabic content with English UI terms like 'Reply', 'From', 'Forwarded'), translate EVERYTHING to "{target_lang}".
3. EXCEPTION: If (and ONLY if) the input is already completely in "{target_lang}" AND "Smart Swap" is True, then translate to "{swap_target}".

Constraints:
- Output ONLY the translation.
- Do NOT translate actual programming code (Python, C++, etc.) or URLs.
- Translate ALL UI elements, menus, and interface labels.

Input Text:
{text_content}
"""

PROMPT_UI_LOCATOR = "Analyze UI (Size: {width}x{height}). Request: '{query}'. Output JSON: {{\"x\": int, \"y\": int, \"found\": bool}}."

REFINE_PROMPT_KEYS = ("summarize", "fix_grammar", "fix_translate", "explain")

LEGACY_REFINER_TOKENS = {
    "summarize": "[summarize]",
    "fix_grammar": "[fix_grammar]",
    "fix_translate": "[fix_translate]",
    "explain": "[explain]",
}

DEFAULT_SYSTEM_PROMPTS = (
    {
        "key": "summarize",
        # Translators: Section header for text refinement prompts in Prompt Manager.
        "section": _("Refine"),
        # Translators: Label for the text summarization prompt.
        "label": _("Summarize"),
        "prompt": "Summarize the text below in {response_lang}.",
    },
    {
        "key": "fix_grammar",
        # Translators: Section header for text refinement prompts in Prompt Manager.
        "section": _("Refine"),
        # Translators: Label for the grammar correction prompt.
        "label": _("Fix Grammar"),
        "prompt": "Fix grammar in the text below. Output ONLY the fixed text.",
    },
    {
        "key": "fix_translate",
        # Translators: Section header for text refinement prompts in Prompt Manager.
        "section": _("Refine"),
        # Translators: Label for the grammar correction and translation prompt.
        "label": _("Fix Grammar & Translate"),
        "prompt": "Fix grammar and translate to {target_lang}.{swap_instruction} Output ONLY the result.",
    },
    {
        "key": "explain",
        # Translators: Section header for text refinement prompts in Prompt Manager.
        "section": _("Refine"),
        # Translators: Label for the text explanation prompt.
        "label": _("Explain"),
        "prompt": "Explain the text below in {response_lang}.",
    },
    {
        "key": "translate_main",
        # Translators: Section header for translation-related prompts in Prompt Manager.
        "section": _("Translation"),
        # Translators: Label for the smart translation prompt.
        "label": _("Smart Translation"),
        "prompt": PROMPT_TRANSLATE.strip(),
    },
    {
        "key": "translate_quick",
        # Translators: Section header for translation-related prompts in Prompt Manager.
        "section": _("Translation"),
        # Translators: Label for the quick translation prompt.
        "label": _("Quick Translation"),
        "prompt": "Translate to {target_lang}. Output ONLY translation.",
    },
    {
        "key": "document_chat_system",
        # Translators: Section header for document-related prompts in Prompt Manager.
        "section": _("Document"),
        # Translators: Label for the initial context prompt in document chat.
        "label": _("Document Chat Context"),
        "prompt": "STRICTLY Respond in {response_lang}. Use Markdown formatting. Analyze the attached content to answer.",
    },
    {
        "key": "document_chat_ack",
        # Translators: Section header for advanced/internal prompts in Prompt Manager.
        "section": _("Advanced"),
        # Translators: Label for the AI's acknowledgement reply in document chat.
        "label": _("Document Chat Bootstrap Reply"),
        "internal": True,
        "prompt": "Context received. Ready for questions.",
    },
    {
        "key": "vision_navigator_object",
        # Translators: Section header for image analysis prompts in Prompt Manager.
        "section": _("Vision"),
        # Translators: Label for the prompt used to analyze the current navigator object.
        "label": _("Navigator Object Analysis"),
        "prompt": (
            "Analyze this image. Describe the layout, visible text, and UI elements. "
            "Use Markdown formatting (headings, lists) to organize the description. "
            "Language: {response_lang}. Ensure the response is strictly in {response_lang}. "
            "IMPORTANT: Start directly with the description content. Do not add introductory "
            "sentences like 'Here is the analysis' or 'The image shows'."
        ),
    },
    {
        "key": "vision_fullscreen",
        # Translators: Section header for image analysis prompts in Prompt Manager.
        "section": _("Vision"),
        # Translators: Label for the prompt used to analyze the entire screen.
        "label": _("Full Screen Analysis"),
        "prompt": (
            "Analyze this image. Describe the layout, visible text, and UI elements. "
            "Use Markdown formatting (headings, lists) to organize the description. "
            "Language: {response_lang}. Ensure the response is strictly in {response_lang}. "
            "IMPORTANT: Start directly with the description content. Do not add introductory "
            "sentences like 'Here is the analysis' or 'The image shows'."
        ),
    },
    {
        "key": "vision_followup_context",
        # Translators: Section header for advanced/internal prompts in Prompt Manager.
        "section": _("Advanced"),
        # Translators: Label for the follow-up context in image analysis chat.
        "label": _("Vision Follow-up Context"),
        "internal": True,
        "prompt": "Image Context. Target Language: {response_lang}",
    },
    {
        "key": "vision_followup_suffix",
        # Translators: Section header for advanced/internal prompts in Prompt Manager.
        "section": _("Advanced"),
        # Translators: Label for the rule enforced during image analysis follow-up questions.
        "label": _("Vision Follow-up Answer Rule"),
        "internal": True,
        "prompt": "Answer strictly in {response_lang}",
    },
    {
        "key": "video_analysis",
        # Translators: Section header for video analysis prompts in Prompt Manager.
        "section": _("Video"),
        # Translators: Label for the video content analysis prompt.
        "label": _("Video Analysis"),
        "prompt": (
            "Analyze this video. Provide a detailed description of the visual content and a "
            "summary of the audio. IMPORTANT: Write the entire response STRICTLY in "
            "{response_lang} language."
        ),
    },
    {
        "key": "audio_transcription",
        # Translators: Section header for audio-related prompts in Prompt Manager.
        "section": _("Audio"),
        # Translators: Label for the audio file transcription prompt.
        "label": _("Audio Transcription"),
        "prompt": "Transcribe this audio in {response_lang}.",
    },
    {
        "key": "dictation_transcribe",
        # Translators: Section header for audio-related prompts in Prompt Manager.
        "section": _("Audio"),
        # Translators: Label for the smart voice dictation prompt.
        "label": _("Smart Dictation"),
        "prompt": (
            "Transcribe speech. Use native script. Fix stutters. If there is no speech, silence, "
            "or background noise only, write exactly: [[[NOSPEECH]]]"
        ),
    },
    {
        "key": "ocr_image_extract",
        # Translators: Section header for OCR-related prompts in Prompt Manager.
        "section": _("OCR"),
        # Translators: Label for the OCR prompt used for image text extraction.
        "label": _("OCR Image Extraction"),
        "prompt": (
            "Extract all visible text from this image. Strictly preserve original formatting "
            "(headings, lists, tables) using Markdown. Do not output any system messages or "
            "code block backticks (```). Output ONLY the raw content."
        ),
    },
    {
        "key": "ocr_document_extract",
        # Translators: Section header for OCR-related prompts in Prompt Manager.
        "section": _("OCR"),
        # Translators: Label for the OCR prompt used for document text extraction.
        "label": _("OCR Document Extraction"),
        "prompt": (
            "Extract all visible text from this document. Strictly preserve original formatting "
            "(headings, lists, tables) using Markdown. You MUST insert the exact delimiter "
            "'[[[PAGE_SEP]]]' immediately after the content of every single page. Do not output "
            "any system messages or code block backticks (```). Output ONLY the raw content."
        ),
    },
    {
        "key": "ocr_document_translate",
        # Translators: Section header for document-related prompts in Prompt Manager.
        "section": _("Document"),
        # Translators: Label for the combined OCR and translation prompt for documents.
        "label": _("Document OCR + Translate"),
        "prompt": (
            "Extract all text from this document. Preserve formatting (Markdown). Then translate "
            "the content to {target_lang}. Output ONLY the translated content. Do not add "
            "explanations."
        ),
    },
    {
        "key": "captcha_solver_base",
        # Translators: Section header for CAPTCHA-related prompts in Prompt Manager.
        "section": _("CAPTCHA"),
        # Translators: Label for the CAPTCHA solving prompt.
        "label": _("CAPTCHA Solver"),
        "internal": True,
        "prompt": (
            "Blind user. Return CAPTCHA code only. If NO CAPTCHA is detected in the image, "
            "strictly return: [[[NO_CAPTCHA]]].{captcha_extra}"
        ),
    },
    {
        "key": "refine_files_only",
        # Translators: Section header for advanced/internal prompts in Prompt Manager.
        "section": _("Advanced"),
        # Translators: Label for the fallback prompt when only files are provided in Refine.
        "label": _("Refine Files-Only Fallback"),
        "internal": True,
        "prompt": "Analyze these files.",
    },
)

PROMPT_VARIABLES_GUIDE = (
    # Translators: Description and input type for the [selection] variable in the Variables Guide.
    ("[selection]", _("Currently selected text"), _("Text")),
    # Translators: Description for the [clipboard] variable in the Variables Guide.
    ("[clipboard]", _("Clipboard content"), _("Text")),
    # Translators: Description and input type for the [screen_obj] variable in the Variables Guide.
    ("[screen_obj]", _("Screenshot of the navigator object"), _("Image")),
    # Translators: Description for the [screen_full] variable in the Variables Guide.
    ("[screen_full]", _("Screenshot of the entire screen"), _("Image")),
    # Translators: Description and input type for the [file_ocr] variable in the Variables Guide.
    ("[file_ocr]", _("Select image/PDF/TIFF for text extraction"), _("Image, PDF, TIFF")),
    # Translators: Description and input type for the [file_read] variable in the Variables Guide.
    ("[file_read]", _("Select document for reading"), _("TXT, Code, PDF")),
    # Translators: Description and input type for the [file_audio] variable in the Variables Guide.
    ("[file_audio]", _("Select audio file for analysis"), _("MP3, WAV, OGG")),
)
