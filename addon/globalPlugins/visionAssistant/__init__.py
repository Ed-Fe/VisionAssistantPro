# -*- coding: utf-8 -*-
import sys
import os
import json
import threading
import logging
import base64
import io
import ctypes
import re
import tempfile
import time
import wave
import gc
import wx
from urllib import request, error, parse
from urllib.parse import quote, urlparse, urlencode
from http import cookiejar
from functools import wraps
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

lib_dir = os.path.join(os.path.dirname(__file__), "lib")
if lib_dir not in sys.path:
    sys.path.append(lib_dir)

try:
    import markdown as markdown_lib
except ImportError:
    markdown_lib = None

try:
    import fitz
except ImportError:
    fitz = None

import addonHandler
import globalPluginHandler
import config
import gui
import ui
import api
import textInfos
import tones
import NVDAObjects.behaviors
import scriptHandler
from .prompt_manager_dialog import PromptManagerDialog

log = logging.getLogger(__name__)
addonHandler.initTranslation()

_vision_assistant_instance = None

from .constants import (
    ADDON_NAME,
    CHROME_OCR_KEYS,
    GEMINI_VOICES,
    GITHUB_REPO,
    MODELS,
    OCR_ENGINES,
    PROMPT_VARIABLES_GUIDE,
    REFINE_PROMPT_KEYS,
    SOURCE_NAMES,
    TARGET_CODES,
    TARGET_NAMES,
)
from .markdown_utils import clean_markdown, markdown_to_html
from .prompt_helpers import (
    apply_prompt_template,
    get_builtin_default_prompts,
    get_builtin_default_prompt_map,
    get_configured_default_prompt_map,
    get_configured_default_prompts,
    get_prompt_text,
    get_refine_menu_options,
    load_configured_custom_prompts,
    migrate_prompt_config_if_needed,
    serialize_default_prompt_overrides,
    serialize_custom_prompts_v2,
)

# --- Helpers ---

def finally_(func, final):
    @wraps(func)
    def new(*args, **kwargs):
        try:
            func(*args, **kwargs)
        finally:
            final()
    return new

from .services import (
    ChromeOCREngine,
    GeminiHandler,
    GoogleTranslator,
    SmartProgrammersOCREngine,
    VirtualDocument,
    _download_temp_video,
    get_file_path,
    get_instagram_download_link,
    get_mime_type,
    get_proxy_opener,
    get_tiktok_download_link,
    get_twitter_download_link,
    send_ctrl_v,
    show_error_dialog,
)

# --- Update Manager ---
from .updater import UpdateDialog, UpdateManager

from .dialogs import ChatDialog, DocumentViewerDialog, RangeDialog, SettingsPanel, VisionQADialog

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = ADDON_NAME
    
    last_translation = "" 
    is_recording = False
    temp_audio_file = os.path.join(tempfile.gettempdir(), "vision_dictate.wav")
    
    translation_cache = {}
    _last_source_text = None
    _last_params = None
    update_timer = None
    
    # Translators: Initial status when the add-on is doing nothing
    current_status = _("Idle")

    def __init__(self):
        super(GlobalPlugin, self).__init__()
        global _vision_assistant_instance
        _vision_assistant_instance = self
        try:
            migrate_prompt_config_if_needed()
        except Exception as e:
            log.warning(f"Prompt config migration failed: {e}")
        gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(SettingsPanel)
        
        self.updater = UpdateManager(GITHUB_REPO)
        
        self.va_menu = wx.Menu()
        
        # Translators: Menu item for Document Reader
        item_doc = self.va_menu.Append(wx.ID_ANY, _("&Document Reader..."))
        self.va_menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(self._open_document_reader), item_doc)
        
        # Translators: Menu item for Audio Transcription
        item_audio = self.va_menu.Append(wx.ID_ANY, _("Transcribe &Audio File..."))
        self.va_menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(self._open_audio), item_audio)
        
        # Translators: Menu item for Video Analysis
        item_video = self.va_menu.Append(wx.ID_ANY, _("Analyze &Video URL..."))
        self.va_menu.Bind(wx.EVT_MENU, lambda e: wx.CallAfter(self._open_video_dialog), item_video)
        
        self.va_menu.AppendSeparator()
        
        # Translators: Menu item to open settings
        item_settings = self.va_menu.Append(wx.ID_ANY, _("&Settings..."))
        self.va_menu.Bind(wx.EVT_MENU, self.on_settings_click, item_settings)
        
        # Translators: Menu item to check for updates
        item_update = self.va_menu.Append(wx.ID_ANY, _("Check for &Update"))
        self.va_menu.Bind(wx.EVT_MENU, lambda e: self.updater.check_for_updates(silent=False), item_update)
        
        # Translators: Menu item to open documentation
        item_help = self.va_menu.Append(wx.ID_ANY, _("Docu&mentation"))
        self.va_menu.Bind(wx.EVT_MENU, self.on_help_click, item_help)
        
        # Translators: Menu item for donations
        item_donate = self.va_menu.Append(wx.ID_ANY, _("D&onate"))
        self.va_menu.Bind(wx.EVT_MENU, self.on_donate_click, item_donate)
        
        self.tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        # Translators: The name of the addon's sub-menu in the NVDA Tools menu.
        self.va_submenu_item = self.tools_menu.AppendSubMenu(self.va_menu, _("Vision Assistant"))
        
        self.refine_dlg = None
        self.refine_menu_dlg = None
        self.vision_dlg = None
        self.doc_dlg = None
        self.translation_dlg = None
        self.toggling = False
        
        if config.conf["VisionAssistant"]["check_update_startup"]:
            self.update_timer = wx.CallLater(10000, self.updater.check_for_updates, True)

    def _browse_and_run(self, worker_fn, wildcard, multiple=False):
        # Translators: Standard title for opening a file
        title = _("Open")
        path = get_file_path(title, wildcard, multiple=multiple)
        if path:
            threading.Thread(target=worker_fn, args=(path,), daemon=True).start()


    def _open_document_reader(self):
        # Translators: File dialog filter for supported files
        wc = _("Supported Files") + "|*.pdf;*.jpg;*.jpeg;*.png;*.tif;*.tiff"
        self._browse_and_run(self._scan_and_open, wc, multiple=True)

    def _scan_and_open(self, paths):
        try:
            if not fitz:
                # Translators: Error when PyMuPDF is missing
                wx.CallAfter(wx.MessageBox, _("PyMuPDF library is missing."), "Error", wx.ICON_ERROR)
                return
            v_doc = VirtualDocument(paths)
            v_doc.scan() 
            if v_doc.total_pages == 0:
                 # Translators: Error when no pages found
                 wx.CallAfter(wx.MessageBox, _("No readable pages found."), "Error", wx.ICON_ERROR)
                 return
            if v_doc.total_pages == 1:
                settings = {'start': 0, 'end': 0, 'translate': False, 'lang': TARGET_NAMES[0]}
                wx.CallAfter(lambda: DocumentViewerDialog(gui.mainFrame, v_doc, settings).Show())
            else:
                wx.CallAfter(self._show_range_dialog, v_doc)
        except Exception as e:
            log.error(f"Error opening files: {e}", exc_info=True)

    def _show_range_dialog(self, v_doc):
        range_dlg = RangeDialog(gui.mainFrame, v_doc.total_pages)
        if range_dlg.ShowModal() == wx.ID_OK:
            wx.CallAfter(lambda: DocumentViewerDialog(gui.mainFrame, v_doc, range_dlg.get_settings()).Show())
        range_dlg.Destroy()

    def getScript(self, gesture):
        if not self.toggling:
            return super(GlobalPlugin, self).getScript(gesture)
        
        script = super(GlobalPlugin, self).getScript(gesture)
        if not script:
            script = finally_(self.script_error, self.finish)
        return finally_(script, self.finish)

    def finish(self):
        self.toggling = False
        self.clearGestureBindings()
        self.bindGestures(self.__gestures)

    def script_error(self, gesture):
        tones.beep(120, 100)

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Activates the Command Layer for quick access to all features."))
    def script_activateLayer(self, gesture):
        if self.toggling:
            self.script_error(gesture)
            return
        
        self.bindGestures(self.__VisionGestures)
        self.toggling = True
        tones.beep(500, 100)

    def terminate(self):
        global _vision_assistant_instance
        try:
            if hasattr(self, 'va_submenu_item') and self.va_submenu_item:
                self.tools_menu.Remove(self.va_submenu_item.GetId())
            
            gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SettingsPanel)
            
            if LauncherDialog.instance:
                LauncherDialog.instance.Destroy()
        except: pass
        
        if hasattr(self, 'update_timer') and self.update_timer and self.update_timer.IsRunning():
            self.update_timer.Stop()
        
        for dlg in [self.refine_dlg, self.refine_menu_dlg, self.vision_dlg, self.doc_dlg, self.translation_dlg]:
            if dlg:
                try: dlg.Destroy()
                except: pass
        
        if self.is_recording:
            try:
                ctypes.windll.winmm.mciSendStringW('close all', None, 0, 0)
            except: pass
        
        self.translation_cache = {}
        self._last_source_text = None
        _vision_assistant_instance = None
        gc.collect()

    def report_status(self, msg):
        self.current_status = msg
        ui.message(msg)

    def _handle_direct_output(self, text, raw_text=None):
        if not config.conf["VisionAssistant"]["skip_chat_dialog"]:
            return False
            
        if config.conf["VisionAssistant"]["copy_to_clipboard"]:
            api.copyToClip(raw_text if raw_text else text)
            
        cleaned = clean_markdown(text)
        ui.message(cleaned)
        return True

    def script_showHelp(self, gesture):
        if self.toggling: self.finish()
        help_msg = (
            "T: " + _("Translates the selected text or navigator object.") + "\n" + \
            "Shift+T: " + _("Translates the text currently in the clipboard.") + "\n" + \
            "R: " + _("Opens a menu to Explain, Summarize, or Fix the selected text.") + "\n" + \
            "O: " + _("Performs OCR and description on the entire screen.") + "\n" + \
            "V: " + _("Describes the current object (Navigator Object).") + "\n" + \
            "D: " + _("Opens the Document Reader for detailed page-by-page analysis (PDF/Images).") + "\n" + \
            "F: " + _("Recognizes text from a selected image or PDF file.") + "\n" + \
            "A: " + _("Transcribes a selected audio file.") + "\n" + \
            "Shift+V: " + _("Analyzes a YouTube, Instagram, Twitter or TikTok video URL.") + "\n" + \
            "C: " + _("Attempts to solve a CAPTCHA on the screen or navigator object.") + "\n" + \
            "S: " + _("Records voice, transcribes it using AI, and types the result.") + "\n" + \
            "L: " + _("Announces the current status of the add-on.") + "\n" + \
            "U: " + _("Checks for updates manually.") + "\n" + \
            "H: " + _("Shows a list of available commands in the layer.")
)
        # Translators: Title of the help dialog
        ui.browseableMessage(help_msg, _("{name} Help").format(name=ADDON_NAME))

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Announces the current status of the add-on."))
    def script_announceStatus(self, gesture):
        if self.toggling: self.finish()
        # Translators: Status message when the add-on is doing nothing
        idle_msg = _("Idle")
        msg = self.current_status if self.current_status else idle_msg
        ui.message(msg)

    def _browse_file(self, wildcard):
        # Translators: Standard title for opening a file
        return get_file_path(_("Open"), wildcard)

    def _upload_file_to_gemini(self, file_path, mime_type):
        api_key = config.conf["VisionAssistant"]["api_key"].strip()
        keys = GeminiHandler._get_api_keys()
        if not keys: return None
        key_idx = GeminiHandler._working_key_idx % len(keys)
        api_key = keys[key_idx]

        proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
        base_url = proxy_url.rstrip('/') if proxy_url else "https://generativelanguage.googleapis.com"
        
        try:
            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)
            
            initial_url = f"{base_url}/upload/v1beta/files"
            headers_init = {
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(file_size),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
            metadata = {"file": {"display_name": filename}}
            req_init = request.Request(initial_url, data=json.dumps(metadata).encode('utf-8'), headers=headers_init, method="POST")
            
            with get_proxy_opener().open(req_init, timeout=30) as response:
                upload_url = response.headers.get("x-goog-upload-url")
                
            if not upload_url: return None

            with open(file_path, "rb") as f:
                file_data = f.read()
                
            headers_upload = {
                "Content-Length": str(file_size),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize"
            }
            req_upload = request.Request(upload_url, data=file_data, headers=headers_upload, method="POST")
            
            file_name_id = None
            with get_proxy_opener().open(req_upload, timeout=300) as response:
                if response.status == 200:
                    res_json = json.loads(response.read().decode('utf-8'))
                    file = res_json.get('file', {})
                    file_name_id = file.get('name')
                    
            if not file_name_id: return None

            check_url = f"{base_url}/v1beta/{file_name_id}"
            for attempt in range(30):
                try:
                    req_check = request.Request(check_url, headers={"x-goog-api-key": api_key})
                    with get_proxy_opener().open(req_check, timeout=10) as response:
                        state_data = json.loads(response.read().decode('utf-8'))
                        state = state_data.get('state')
                        if state == "ACTIVE":
                            file_uri = state_data.get('uri')
                            GeminiHandler._register_file_uri(file_uri, api_key)
                            return file_uri
                        elif state == "FAILED":
                            return None
                except: pass
                time.sleep(2)
                
            return None 

        except error.URLError as e:
            # Translators: Message of a dialog which may pop up while trying to upload a file
            msg = _("Upload Connection Error: {reason}").format(reason=e.reason)
            self.report_status(msg)
            show_error_dialog(msg)
            return None
        except error.HTTPError as e:
            # Translators: Message of a dialog which may pop up while trying to upload a file
            msg = _("Upload Server Error {code}: {reason}").format(code=e.code, reason=e.reason)
            self.report_status(msg)
            show_error_dialog(msg)
            return None
        except Exception as e:
            # Translators: Message of a dialog which may pop up while trying to upload a file
            msg = _("File Upload Error: {error}").format(error=e)
            self.report_status(msg)
            show_error_dialog(msg)
            return None



    def _call_gemini_safe(self, prompt_or_contents, attachments=[], json_mode=False):
        def _has_parts(contents):
            for item in contents:
                if not isinstance(item, dict):
                    continue
                parts = item.get("parts", [])
                for part in parts:
                    if isinstance(part, dict) and part:
                        return True
            return False

        if isinstance(prompt_or_contents, list):
            if not _has_parts(prompt_or_contents):
                # Translators: Error message when there's no content to send
                err_msg = _("Nothing to send.")
                self.report_status(_("Error"))
                show_error_dialog(err_msg)
                return None
        else:
            if not prompt_or_contents and not attachments:
                # Translators: Error message when there's no content to send
                err_msg = _("Nothing to send.")
                self.report_status(_("Error"))
                show_error_dialog(err_msg)
                return None

        def _logic(key, p_or_c, atts, j_mode):
            model = config.conf["VisionAssistant"]["model_name"]
            proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
            base_url = proxy_url.rstrip('/') if proxy_url else "https://generativelanguage.googleapis.com"
            url = f"{base_url}/v1beta/models/{model}:generateContent"
            headers = {"Content-Type": "application/json; charset=UTF-8", "x-goog-api-key": key}
            
            contents = []
            if isinstance(p_or_c, list):
                contents = p_or_c
            else:
                parts = []
                for att in atts:
                    if 'file_uri' in att:
                        parts.append({"file_data": {"mime_type": att['mime_type'], "file_uri": att['file_uri']}})
                    else:
                        parts.append({"inline_data": {"mime_type": att['mime_type'], "data": att['data']}})
                if p_or_c:
                    parts.append({"text": p_or_c})
                contents = [{"parts": parts}]
                
            data = {
                "contents": contents,
                "generationConfig": {"temperature": 0.0, "topK": 40},
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
            if j_mode: data["generationConfig"]["response_mime_type"] = "application/json"

            req = request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with get_proxy_opener().open(req, timeout=600) as response:
                if response.status == 200:
                    res = json.loads(response.read().decode('utf-8'))
                    if not res.get('candidates'): return None
                    candidate = res['candidates'][0]
                    if candidate.get('finishReason') == 'SAFETY':
                        # Translators: Error message when AI refuses to answer due to safety guidelines
                        return "ERROR:" + _("Error: Response blocked by AI safety filters.")
                    content = candidate.get('content', {})
                    parts = content.get('parts', [])
                    if parts and 'text' in parts[0]:
                        return parts[0]['text'].strip()
                    return None

        forced_key = None
        if attachments:
            for att in attachments:
                file_uri = att.get("file_uri") if isinstance(att, dict) else None
                registered_key = GeminiHandler._get_registered_key(file_uri)
                if registered_key:
                    forced_key = registered_key
                    break

        if forced_key:
            res = GeminiHandler._call_with_key(_logic, forced_key, prompt_or_contents, attachments, json_mode)
        else:
            res = GeminiHandler._call_with_rotation(_logic, prompt_or_contents, attachments, json_mode)
        
        if isinstance(res, str) and res.startswith("ERROR:"):
            err_msg = res[6:]
            # Translators: Status reported when an error occurs
            self.report_status(_("Error"))
            show_error_dialog(err_msg)
            return None
            
        return res

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Records voice, transcribes it using AI, and types the result."))
    def script_smartDictation(self, gesture):
        if self.toggling: self.finish()
        if not self.is_recording:
            self.is_recording = True
            tones.beep(800, 100)
            try:
                ctypes.windll.winmm.mciSendStringW('open new type waveaudio alias myaudio', None, 0, 0)
                ctypes.windll.winmm.mciSendStringW('record myaudio', None, 0, 0)
                # Translators: Message reported when dictation starts
                msg = _("Listening...")
                self.report_status(msg)
            except Exception as e:
                # Translators: Message in an error dialog which can pop up while trying dictation.
                msg = _("Audio Hardware Error: {error}").format(error=e)
                show_error_dialog(msg)
                self.is_recording = False
        else:
            self.is_recording = False
            tones.beep(500, 100)
            try:
                ctypes.windll.winmm.mciSendStringW(f'save myaudio "{self.temp_audio_file}"', None, 0, 0)
                ctypes.windll.winmm.mciSendStringW('close myaudio', None, 0, 0)
                # Translators: Message reported when processing dictation
                msg = _("Typing...")
                self.report_status(msg)
                threading.Thread(target=self._thread_dictation, daemon=True).start()
            except Exception as e:
                # Translators: Message in an error dialog which can pop up while trying dictation.
                msg = _("Save Recording Error: {error}").format(error=e)
                show_error_dialog(msg)

    def _thread_dictation(self):
        try:
            if not os.path.exists(self.temp_audio_file): return
            
            try:
                with wave.open(self.temp_audio_file, "rb") as wave_file:
                    frame_rate = wave_file.getframerate()
                    n_frames = wave_file.getnframes()
                    duration = n_frames / float(frame_rate)
                
                if duration < 1.0:
                    # Translators: Message reported when the AI detects silence or empty speech
                    msg = _("No speech detected.")
                    wx.CallAfter(self.report_status, msg)
                    try: os.remove(self.temp_audio_file)
                    except: pass
                    return
            except Exception:
                pass

            with open(self.temp_audio_file, "rb") as f:
                audio_data = base64.b64encode(f.read()).decode('utf-8')
            
            dictation_template = get_prompt_text("dictation_transcribe") or (
                "Transcribe speech. Use native script. Fix stutters. If there is no speech, "
                "silence, or background noise only, write exactly: [[[NOSPEECH]]]"
            )
            p = apply_prompt_template(dictation_template, [("response_lang", config.conf["VisionAssistant"]["ai_response_language"])])
            
            res = self._call_gemini_safe(p, attachments=[{'mime_type': 'audio/wav', 'data': audio_data}])
            
            if res:
                clean_res = res.strip()
                if "[[[NOSPEECH]]]" in clean_res:
                    # Translators: Message reported when the AI detects silence or empty speech
                    msg = _("No speech detected.")
                    wx.CallAfter(self.report_status, msg)
                else:
                    cleaned_text = clean_markdown(res)
                    wx.CallAfter(self._paste_text, cleaned_text)
            else: 
                # Translators: Message reported while trying dictation.
                msg = _("No speech recognized or Error.")
                wx.CallAfter(self.report_status, msg)
            
            try: os.remove(self.temp_audio_file)
            except: pass
        except: pass

    def _paste_text(self, text):
        api.copyToClip(text)
        send_ctrl_v()
        wx.CallLater(300, self._announce_paste, text)

    def _announce_paste(self, text):
        preview = text[:100]
        # Translators: Message reported when dictation is complete
        msg = _("Typed: {text}").format(text=preview)
        self.report_status(msg)

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Translates the selected text or navigator object."))
    def script_translateSmart(self, gesture):
        if self.toggling: self.finish()
        text = self._get_text_smart()
        
        if not text:
            # Translators: Message reported when calling translation command
            msg = _("No text found.")
            self.report_status(msg)
            return
            
        # Translators: Message reported when calling translation command
        msg = _("Translating...")
        self.report_status(msg)
        threading.Thread(target=self._thread_translate, args=(text,), daemon=True).start()

    def _thread_translate(self, text):
        s = config.conf["VisionAssistant"]["source_language"]
        t = config.conf["VisionAssistant"]["target_language"]
        swap = config.conf["VisionAssistant"]["smart_swap"]
        fallback = "English" if s == "Auto-detect" else s
        
        current_params = f"{t}|{swap}"
        if text == self._last_source_text and current_params == self._last_params and self.last_translation:
            wx.CallAfter(self._announce_translation, self.last_translation)
            return

        translation_template = get_prompt_text("translate_main")
        p = apply_prompt_template(translation_template, [
            ("target_lang", t),
            ("swap_target", fallback),
            ("smart_swap", str(swap)),
            ("text_content", text),
        ])
        res = self._call_gemini_safe(p)
        if res:
            clean_res = clean_markdown(res)
            self._last_source_text = text
            self._last_params = current_params
            self.last_translation = clean_res
            wx.CallAfter(self._announce_translation, clean_res)

    def _announce_translation(self, text):
        if config.conf["VisionAssistant"]["copy_to_clipboard"] and not config.conf["VisionAssistant"]["skip_chat_dialog"]:
            api.copyToClip(text)
        # Translators: Message reported when calling translation command
        msg = _("Translated: {text}").format(text=text)
        self.report_status(msg)
        if self._handle_direct_output(text):
            return
        wx.CallAfter(self._open_translation_dialog, text)

    def _open_translation_dialog(self, text):
        if self.translation_dlg:
            try: self.translation_dlg.Destroy()
            except: pass
            self.translation_dlg = None

        def noop_callback(ctx, q, history, extra):
            return None, None

        # Translators: Dialog title for Translation results
        self.translation_dlg = VisionQADialog(
            gui.mainFrame, 
            _("{name} - Translation").format(name=ADDON_NAME), 
            text, 
            None, 
            noop_callback, 
            extra_info={'skip_init_history': True},
            raw_content=text,
            status_callback=self.report_status,
            announce_on_open=False,
            allow_questions=False
        )
        self.translation_dlg.Show()
        self.translation_dlg.Raise()

    def _get_text_smart(self):
        focus_obj = api.getFocusObject()
        if not focus_obj: return None

        if hasattr(focus_obj, "treeInterceptor") and focus_obj.treeInterceptor:
            try:
                info = focus_obj.treeInterceptor.makeTextInfo(textInfos.POSITION_SELECTION)
                if info and info.text and not info.text.isspace():
                    return info.text
            except: pass

        try:
            info = focus_obj.makeTextInfo(textInfos.POSITION_SELECTION)
            if info and info.text and not info.text.isspace():
                return info.text
        except: pass

        if isinstance(focus_obj, NVDAObjects.behaviors.EditableText):
            try:
                info = focus_obj.makeTextInfo(textInfos.POSITION_ALL)
                if info and info.text and not info.text.isspace():
                    return info.text
            except: pass
        
        if isinstance(focus_obj, NVDAObjects.behaviors.Terminal):
            try:
                info = focus_obj.makeTextInfo(textInfos.POSITION_ALL)
                return info.text
            except: pass

        try:
            obj = api.getNavigatorObject()
            if not obj: return None
            
            content = []
            if getattr(obj, 'name', None): content.append(obj.name)
            if getattr(obj, 'value', None): content.append(obj.value)
            if getattr(obj, 'description', None): content.append(obj.description)
            
            if hasattr(obj, 'makeTextInfo'):
                try: 
                    ti = obj.makeTextInfo(textInfos.POSITION_ALL)
                    if ti.text and len(ti.text) < 2000: 
                        content.append(ti.text)
                except: pass
                
            final_text = " ".join(list(dict.fromkeys([c for c in content if c and not c.isspace()])))
            return final_text if final_text else None
        except Exception: 
            return None

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Opens a menu to Explain, Summarize, or Fix the selected text."))
    def script_refineText(self, gesture):
        if self.toggling: self.finish()
        if self.refine_menu_dlg:
            self.refine_menu_dlg.Raise()
            self.refine_menu_dlg.SetFocus()
            return
        
        captured_text = self._get_text_smart()
        if not captured_text: captured_text = "" 
        
        wx.CallLater(100, self._open_refine_dialog, captured_text)

    def _open_refine_dialog(self, captured_text):
        options = get_refine_menu_options()
        if not options:
            prompt_map = get_builtin_default_prompt_map()
            for key in REFINE_PROMPT_KEYS:
                if key in prompt_map:
                    item = prompt_map[key]
                    options.append((item["label"], item["prompt"]))
        
        display_choices = [opt[0] for opt in options]
        
        self.refine_menu_dlg = wx.SingleChoiceDialog(
            gui.mainFrame,
            # Translators: Title of the Refine dialog
            _("Choose action:"),
            # Translators: main message of the Refine dialog
            _("Refine"),
            display_choices,
        )
        
        self.refine_menu_dlg.Raise()
        self.refine_menu_dlg.SetFocus()
        
        if self.refine_menu_dlg.ShowModal() == wx.ID_OK:
            selection_index = self.refine_menu_dlg.GetSelection()
            custom_content = options[selection_index][1]

            file_paths = []
            needs_file = False
            wc = "Files|*.*"
            
            if "[file_ocr]" in custom_content:
                needs_file = True
                wc = "Images/PDF/TIFF|*.png;*.jpg;*.webp;*.pdf;*.tif;*.tiff"
            elif "[file_read]" in custom_content:
                needs_file = True
                wc = "Documents|*.txt;*.py;*.md;*.html;*.pdf;*.tif;*.tiff"
            elif "[file_audio]" in custom_content:
                needs_file = True
                wc = "Audio|*.mp3;*.wav;*.ogg"
            
            if needs_file:
                # Translators: Standard title for opening a file
                dlg = wx.FileDialog(gui.mainFrame, _("Open"), wildcard=wc, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE)
                if dlg.ShowModal() == wx.ID_OK:
                    file_paths = dlg.GetPaths()
                    file_paths.sort()
                    wx.CallLater(200, lambda: threading.Thread(target=self._thread_refine, args=(captured_text, custom_content, file_paths), daemon=True).start())
                dlg.Destroy()
            else:
                # Translators: Message while processing request of the refine text command
                msg = _("Processing...")
                self.report_status(msg)
                threading.Thread(target=self._thread_refine, args=(captured_text, custom_content, None), daemon=True).start()
        
        self.refine_menu_dlg.Destroy()
        self.refine_menu_dlg = None

    def _thread_refine(self, captured_text, custom_content, file_paths=None):
        target_lang = config.conf["VisionAssistant"]["target_language"]
        source_lang = config.conf["VisionAssistant"]["source_language"]
        smart_swap = config.conf["VisionAssistant"]["smart_swap"]
        resp_lang = config.conf["VisionAssistant"]["ai_response_language"]
        
        if file_paths and isinstance(file_paths, str):
            file_paths = [file_paths]
        elif not file_paths:
            file_paths = []

        prompt_text = custom_content
        attachments = []
        fallback = "English" if source_lang == "Auto-detect" else source_lang
        swap_instr = f" If text is in {target_lang}, translate to {fallback}." if smart_swap else ""
        prompt_text = apply_prompt_template(prompt_text, [
            ("target_lang", target_lang),
            ("source_lang", source_lang),
            ("response_lang", resp_lang),
            ("swap_target", fallback),
            ("swap_instruction", swap_instr),
        ])
        
        if "[fix_translate]" in prompt_text:
            prompt_text = prompt_text.replace("[fix_translate]", 
                f"Fix grammar and translate to {target_lang}.{swap_instr} Output ONLY the result.")
        
        prompt_text = prompt_text.replace("[summarize]", f"Summarize the text below in {resp_lang}.")
        prompt_text = prompt_text.replace("[fix_grammar]", "Fix grammar in the text below. Output ONLY the fixed text.")
        prompt_text = prompt_text.replace("[explain]", f"Explain the text below in {resp_lang}.")
        
        used_selection = False
        if "[selection]" in prompt_text: 
            prompt_text = prompt_text.replace("[selection]", captured_text)
            used_selection = True
            
        if "[clipboard]" in prompt_text: 
            prompt_text = prompt_text.replace("[clipboard]", api.getClipData())
        
        if "[screen_obj]" in prompt_text:
            d, w, h = self._capture_navigator()
            if d: attachments.append({'mime_type': 'image/png', 'data': d})
            prompt_text = prompt_text.replace("[screen_obj]", "")
            
        if "[screen_full]" in prompt_text:
            d, w, h = self._capture_fullscreen()
            if d: attachments.append({'mime_type': 'image/png', 'data': d})
            prompt_text = prompt_text.replace("[screen_full]", "")
            
        if file_paths:
            # Translators: Message reported when executing the refine command
            msg = _("Uploading file...")
            wx.CallAfter(self.report_status, msg)
            
            for f_path in file_paths:
                try:
                    mime_type = get_mime_type(f_path)
                    ext = os.path.splitext(f_path)[1].lower()
                    
                    if "[file_ocr]" in prompt_text:
                        if ext in ['.pdf', '.tif', '.tiff'] and fitz:
                            try:
                                doc = fitz.open(f_path)
                                for i in range(len(doc)):
                                    page = doc.load_page(i)
                                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                                    data = base64.b64encode(pix.tobytes("jpg")).decode('utf-8')
                                    attachments.append({'mime_type': 'image/jpeg', 'data': data})
                                doc.close()
                            except: pass
                        else:
                            file_uri = self._upload_file_to_gemini(f_path, mime_type)
                            if file_uri:
                                 attachments.append({'mime_type': mime_type, 'file_uri': file_uri})
                    
                    elif "[file_read]" in prompt_text:
                        file_uri = self._upload_file_to_gemini(f_path, mime_type)
                        if file_uri:
                            attachments.append({'mime_type': mime_type, 'file_uri': file_uri})
                        else:
                             try:
                                with open(f_path, "rb") as f: raw = f.read()
                                txt = raw.decode('utf-8')
                                prompt_text += f"\n\nFile Content ({os.path.basename(f_path)}):\n{txt}\n"
                             except: pass

                    elif "[file_audio]" in prompt_text:
                        file_uri = self._upload_file_to_gemini(f_path, mime_type)
                        if file_uri:
                            attachments.append({'mime_type': mime_type, 'file_uri': file_uri})
                except: pass

            prompt_text = prompt_text.replace("[file_ocr]", "").replace("[file_read]", "").replace("[file_audio]", "")
            
            if not prompt_text.strip() and attachments:
                 prompt_text = get_prompt_text("refine_files_only") or "Analyze these files."
            
        if captured_text and not used_selection and not file_paths:
            prompt_text += f"\n\n---\nInput Text:\n{captured_text}\n---\n"
            
        # Translators: Message reported when executing the refine command
        msg = _("Analyzing...")
        wx.CallAfter(self.report_status, msg)
        res = self._call_gemini_safe(prompt_text, attachments=attachments)
        
        if res:
             self.current_status = _("Idle")
             if not self._handle_direct_output(res):
                 wx.CallAfter(self._open_refine_result_dialog, res, attachments, captured_text, prompt_text)

    def _open_refine_result_dialog(self, result_text, attachments, original_text, initial_prompt):
        if self.refine_dlg:
            try: self.refine_dlg.Destroy()
            except: pass

        def refine_callback(ctx, q, history, extra):
            atts, orig, first_p = ctx
            parts = [{"text": q}]
            current_user_msg = {"role": "user", "parts": parts}
            
            messages = []
            
            if len(history) <= 1: 
                sys_parts = [{"text": first_p}]
                for att in atts:
                    if 'file_uri' in att:
                        sys_parts.append({"file_data": {"mime_type": att['mime_type'], "file_uri": att['file_uri']}})
                    elif 'data' in att:
                        sys_parts.append({"inline_data": {"mime_type": att['mime_type'], "data": att['data']}})
                
                messages.append({"role": "user", "parts": sys_parts})
                if history: messages.append(history[0])
            else:
                messages.extend(history)
            
            messages.append(current_user_msg)
            return self._call_gemini_safe(messages), None

        context = (attachments, original_text, initial_prompt)
        has_file_context = any('file_uri' in a for a in attachments)
        # Translators: Title of Refine Result dialog
        self.refine_dlg = VisionQADialog(
            gui.mainFrame, 
            _("{name} - Refine Result").format(name=ADDON_NAME), 
            result_text, 
            context, 
            refine_callback, 
            extra_info={'file_context': has_file_context, 'skip_init_history': False},
            raw_content=result_text,
            status_callback=self.report_status
        )
        self.refine_dlg.Show()
        self.refine_dlg.Raise()

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Recognizes text from a selected image or PDF file."))
    def script_fileOCR(self, gesture):
        if self.toggling: self.finish()
        wx.CallLater(100, self._open_file_ocr_dialog)

    def _open_file_ocr_dialog(self):
        wc = "Files|*.pdf;*.jpg;*.jpeg;*.png;*.webp;*.tif;*.tiff"
        self._browse_and_run(self._pre_process_ocr, wc, multiple=True)

    def _pre_process_ocr(self, paths):
        try:
            if not fitz:
                # Translators: Error when PyMuPDF is missing
                wx.CallAfter(wx.MessageBox, _("PyMuPDF library is missing."), "Error", wx.ICON_ERROR)
                return
            v_doc = VirtualDocument(paths)
            v_doc.scan()
            if v_doc.total_pages == 0:
                # Translators: Error when no pages found
                wx.CallAfter(wx.MessageBox, _("No readable pages found."), "Error", wx.ICON_ERROR)
                return
            if v_doc.total_pages == 1:
                threading.Thread(target=self._process_file_ocr, args=(v_doc, 0, 0), daemon=True).start()
            else:
                wx.CallAfter(self._show_ocr_range_dialog, v_doc)
        except Exception as e:
            log.error(f"Error preparing OCR: {e}")

    def _show_ocr_range_dialog(self, v_doc):
        range_dlg = RangeDialog(gui.mainFrame, v_doc.total_pages)
        if range_dlg.ShowModal() == wx.ID_OK:
            settings = range_dlg.get_settings()
            threading.Thread(target=self._process_file_ocr, args=(v_doc, settings['start'], settings['end']), daemon=True).start()
        range_dlg.Destroy()

    def _process_file_ocr(self, v_doc, start_page, end_page):
        engine = config.conf["VisionAssistant"]["ocr_engine"]
        target_lang = config.conf["VisionAssistant"]["target_language"]
        
        # Translators: Message reported when calling the OCR file recognition command
        msg = _("Uploading & Extracting...")
        wx.CallAfter(self.report_status, msg)
        
        if engine == 'chrome':
            def chrome_page_worker(page_idx):
                try:
                    file_path, internal_idx = v_doc.get_page_info(page_idx)
                    doc = fitz.open(file_path)
                    page = doc.load_page(internal_idx)
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_bytes = pix.tobytes("jpg")
                    doc.close()
                    
                    txt = ChromeOCREngine.recognize(img_bytes)
                    if not txt: return ""
                    
                    if target_lang != "English":
                        txt = GoogleTranslator.translate(txt, target_lang)
                    return f"--- Page {page_idx + 1} ---\n{txt}\n"
                except Exception as e:
                    return f"Error on page {page_idx + 1}: {e}\n"

            with ThreadPoolExecutor(max_workers=5) as executor:
                results_gen = executor.map(chrome_page_worker, range(start_page, end_page + 1))
                full_text = "\n".join(results_gen).strip()

            if not full_text:
                self.current_status = _("Idle")
                # Translators: Error shown when OCR finds no text in the selected files
                wx.CallAfter(show_error_dialog, _("No text detected in the selected file(s)."))
                return
            
            self.current_status = _("Idle")
            if not self._handle_direct_output(full_text):
                wx.CallAfter(self._open_doc_chat_dialog, full_text, [], full_text, full_text)
                
        else: # Gemini Engine
            upload_path = v_doc.create_merged_pdf(start_page, end_page)
            if not upload_path:
                # Translators: Error message if PDF creation fails
                wx.CallAfter(self.report_status, _("Error creating PDF."))
                return

            mime_type = "application/pdf"
            file_uri = self._upload_file_to_gemini(upload_path, mime_type)
            if not file_uri:
                try: os.remove(upload_path)
                except: pass
                self.current_status = _("Idle")
                wx.CallAfter(self.report_status, _("Upload failed."))
                return
            attachments = [{'mime_type': mime_type, 'file_uri': file_uri}]
            
            ocr_translate_template = get_prompt_text("ocr_document_translate")
            p = apply_prompt_template(ocr_translate_template, [("target_lang", target_lang)])
            res = self._call_gemini_safe(p, attachments=attachments)
            
            try: os.remove(upload_path)
            except: pass

            if isinstance(res, str) and not res.strip():
                self.current_status = _("Idle")
                # Translators: Error shown when OCR finds no text in the selected files
                wx.CallAfter(show_error_dialog, _("No text detected in the selected file(s)."))
                return

            if res:
                if not self._handle_direct_output(res):
                    wx.CallAfter(self._open_doc_chat_dialog, res, attachments, res, res)
            else:
                self.current_status = _("Idle")

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Opens the Document Reader for detailed page-by-page analysis (PDF/Images)."))
    def script_analyzeDocument(self, gesture):
        if self.toggling: self.finish()
        wx.CallAfter(self._open_document_reader)

    def _open_doc_chat_dialog(self, init_msg, initial_attachments, doc_text, raw_text_for_save=None):
        if self.doc_dlg:
            try: 
                self.doc_dlg.Destroy()
            except: pass
            self.doc_dlg = None

        def doc_callback(ctx_atts, q, history, dum2):
            lang = config.conf["VisionAssistant"]["ai_response_language"]
            system_template = get_prompt_text("document_chat_system")
            system_instr = apply_prompt_template(system_template, [("response_lang", lang)])
            context_parts = []
            if ctx_atts:
                for att in ctx_atts:
                    if 'file_uri' in att:
                        context_parts.append({"file_data": {"mime_type": att['mime_type'], "file_uri": att['file_uri']}})
                    elif 'data' in att:
                        context_parts.append({"inline_data": {"mime_type": att['mime_type'], "data": att['data']}})
            elif doc_text and not history:
                context_parts.append({"text": f"Document OCR text:\n{doc_text}"})
            context_parts.append({"text": f"Context: {system_instr}"})
            messages = []
            messages.append({"role": "user", "parts": context_parts})
            ack_text = get_prompt_text("document_chat_ack") or "Context received. Ready for questions."
            messages.append({"role": "model", "parts": [{"text": ack_text}]})
            if history: messages.extend(history)
            messages.append({"role": "user", "parts": [{"text": q}]})
            return self._call_gemini_safe(messages), None
            
        # Translators: Dialog title for a Chat dialog
        self.doc_dlg = VisionQADialog(
            gui.mainFrame, 
            _("{name} - Chat").format(name=ADDON_NAME), 
            init_msg, 
            initial_attachments, 
            doc_callback, 
            extra_info={'skip_init_history': True},
            raw_content=raw_text_for_save,
            status_callback=self.report_status
        )
        self.doc_dlg.Show()
        self.doc_dlg.Raise()

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Performs OCR and description on the entire screen."))
    def script_ocrFullScreen(self, gesture):
        if self.toggling: self.finish()
        self._start_vision(True)

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Describes the current object (Navigator Object)."))
    def script_describeObject(self, gesture):
        if self.toggling: self.finish()
        self._start_vision(False)

    def _start_vision(self, full):
        if full: d, w, h = self._capture_fullscreen()
        else: d, w, h = self._capture_navigator()
        if d:
            # Translators: Message reported when calling an image analysis command
            msg = _("Scanning...")
            self.report_status(msg)
            wx.CallLater(100, lambda: threading.Thread(target=self._thread_vision, args=(d, w, h, full), daemon=True).start())
        else: 
            # Translators: Message reported when calling an image analysis command
            msg = _("Capture failed.")
            self.report_status(msg)

    def _thread_vision(self, img, w, h, full=False):
        lang = config.conf["VisionAssistant"]["ai_response_language"]
        vision_key = "vision_fullscreen" if full else "vision_navigator_object"
        vision_template = get_prompt_text(vision_key)
        p = apply_prompt_template(vision_template, [
            ("response_lang", lang),
            ("width", w),
            ("height", h),
        ])
        att = [{'mime_type': 'image/png', 'data': img}]
        res = self._call_gemini_safe(p, attachments=att)
        if res:
            self.current_status = _("Idle")
            if not self._handle_direct_output(res):
                wx.CallAfter(self._open_vision_dialog, res, att, None)
        else:
            self.current_status = _("Idle")
        
    def _open_vision_dialog(self, text, atts, size):
        if self.vision_dlg:
            try: self.vision_dlg.Destroy()
            except: pass

        def cb(atts, q, history, sz):
            lang = config.conf["VisionAssistant"]["ai_response_language"]
            followup_suffix_template = get_prompt_text("vision_followup_suffix") or "Answer strictly in {response_lang}"
            followup_suffix = apply_prompt_template(followup_suffix_template, [("response_lang", lang)])
            current_user_msg = {"role": "user", "parts": [{"text": f"{q} ({followup_suffix})"}]}
            messages = []
            initial_history = (not history) or (len(history) == 1 and history[0].get("role") == "model")
            if initial_history:
                parts = []
                for att in atts:
                    parts.append({"inline_data": {"mime_type": att['mime_type'], "data": att['data']}})
                followup_context_template = get_prompt_text("vision_followup_context") or "Image Context. Target Language: {response_lang}"
                followup_context = apply_prompt_template(followup_context_template, [("response_lang", lang)])
                parts.append({"text": followup_context})
                messages.append({"role": "user", "parts": parts})
                if history and history[0].get("role") == "model":
                    messages.append(history[0])
                else:
                    messages.append({"role": "model", "parts": [{"text": text}]})
            else:
                messages.extend(history)
            messages.append(current_user_msg)
            return self._call_gemini_safe(messages), None
            
        # Translators: Dialog title for Image Analysis
        self.vision_dlg = VisionQADialog(
            gui.mainFrame, 
            _("{name} - Image Analysis").format(name=ADDON_NAME), 
            text, 
            atts, 
            cb, 
            None,
            raw_content=text,
            status_callback=self.report_status
        )
        self.vision_dlg.Show()
        self.vision_dlg.Raise()

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Transcribes a selected audio file."))
    def script_transcribeAudio(self, gesture):
        if self.toggling: self.finish()
        wx.CallLater(100, self._open_audio)

    def _open_audio(self):
        wc = "Audio|*.mp3;*.wav;*.ogg"
        self._browse_and_run(self._thread_audio, wc)

    def _thread_audio(self, path):
        try:
            # Translators: Message reported when calling the audio transcription command
            msg = _("Uploading...")
            wx.CallAfter(self.report_status, msg)
            mime_type = get_mime_type(path)
            
            file_uri = self._upload_file_to_gemini(path, mime_type)
            if not file_uri: 
                self.current_status = _("Idle")
                return

            # Translators: Message reported when calling the audio transcription command
            msg = _("Analyzing...")
            wx.CallAfter(self.report_status, msg)
            lang = config.conf["VisionAssistant"]["ai_response_language"]
            audio_template = get_prompt_text("audio_transcription")
            p = apply_prompt_template(audio_template, [("response_lang", lang)])
            
            att = [{'mime_type': mime_type, 'file_uri': file_uri}]
            res = self._call_gemini_safe(p, attachments=att)
            
            if res:
                self.current_status = _("Idle")
                if not self._handle_direct_output(res):
                    wx.CallAfter(self._open_doc_chat_dialog, res, att, res, res)
            else:
                self.current_status = _("Idle")
        except: 
            # Translators: Generic error message when audio processing fails
            msg = _("Error processing audio.")
            wx.CallAfter(self.report_status, msg)
            self.current_status = _("Idle")

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Analyzes a YouTube, Instagram, Twitter or TikTok video URL."))
    def script_analyzeOnlineVideo(self, gesture):
        if self.toggling: self.finish()
        wx.CallLater(100, self._open_video_dialog)

    def _open_video_dialog(self):
        # Translators: Title for the video URL entry dialog
        title = _("YouTube / Instagram / Twitter / TikTok Analysis")
        # Translators: Label for the text entry in video dialog
        msg = _("Enter Video URL (YouTube/Instagram/Twitter/TikTok):")
        dlg = wx.TextEntryDialog(gui.mainFrame, msg, title)
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            url = dlg.GetValue()
            if url.strip():
                threading.Thread(target=self._thread_video, args=(url,), daemon=True).start()
        dlg.Destroy()

    def _thread_video(self, url):
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower()
            if not domain:
                # Translators: Error message when the URL is invalid
                wx.CallAfter(self.report_status, _("Error: Invalid URL."))
                return
        except:
            wx.CallAfter(self.report_status, _("Error: Invalid URL."))
            return

        is_youtube = any(d in domain for d in ["youtube.com", "youtu.be"])
        is_insta = "instagram.com" in domain
        is_twitter = any(d in domain for d in ["twitter.com", "x.com"])
        is_tiktok = "tiktok.com" in domain

        if not (is_youtube or is_insta or is_twitter or is_tiktok):
            # Translators: Error message when the platform is not supported
            wx.CallAfter(self.report_status, _("Error: Unsupported platform. Only YouTube, Instagram, Twitter, and TikTok are supported."))
            return

        # Translators: Message reported when processing video link
        wx.CallAfter(self.report_status, _("Processing Video..."))
        
        lang = config.conf["VisionAssistant"]["ai_response_language"]
        video_template = get_prompt_text("video_analysis")
        p = apply_prompt_template(video_template, [("response_lang", lang)])

        chat_attachments = []

        if is_insta or is_twitter or is_tiktok:
            if is_insta:
                direct_link = get_instagram_download_link(url)
                err_msg = _("Error: Could not extract Instagram video.")
            elif is_twitter:
                direct_link = get_twitter_download_link(url)
                err_msg = _("Error: Could not extract Twitter video.")
            else:
                direct_link = get_tiktok_download_link(url)
                err_msg = _("Error: Could not extract TikTok video.")

            if not direct_link:
                wx.CallAfter(self.report_status, err_msg)
                return
            
            # Translators: Message reported when downloading video
            wx.CallAfter(self.report_status, _("Downloading Video..."))
            temp_path = _download_temp_video(direct_link)
            
            if not temp_path:
                # Translators: Error message when video download fails
                wx.CallAfter(self.report_status, _("Error: Download failed."))
                return

            # Translators: Message reported when uploading video to AI
            wx.CallAfter(self.report_status, _("Uploading to AI..."))
            try:
                file_uri = self._upload_file_to_gemini(temp_path, "video/mp4")
                if file_uri:
                    chat_attachments = [{'mime_type': 'video/mp4', 'file_uri': file_uri}]
                    # Translators: Message reported when AI is analyzing the video
                    wx.CallAfter(self.report_status, _("Analyzing..."))
                    res = self._call_gemini_safe(p, attachments=chat_attachments)
                    if res:
                        self.current_status = _("Idle")
                        if not self._handle_direct_output(res):
                            wx.CallAfter(self._open_doc_chat_dialog, res, chat_attachments, res, res)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        elif is_youtube:
            # Translators: Message reported when analyzing YouTube video
            wx.CallAfter(self.report_status, _("Analyzing YouTube..."))
            chat_attachments = [{'mime_type': 'video/mp4', 'file_uri': url}]
            res = self._call_gemini_safe(p, attachments=chat_attachments)
            if res:
                self.current_status = _("Idle")
                if not self._handle_direct_output(res):
                    wx.CallAfter(self._open_doc_chat_dialog, res, chat_attachments, res, res)
            else:
                self.current_status = _("Idle")

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Attempts to solve a CAPTCHA on the screen or navigator object."))
    def script_solveCaptcha(self, gesture):
        if self.toggling: self.finish()
        mode = config.conf["VisionAssistant"]["captcha_mode"]
        if mode == 'fullscreen': d, w, h = self._capture_fullscreen()
        else: d, w, h = self._capture_navigator()
        
        is_gov = False
        try:
            if api.getForegroundObject() and "پنجره ملی خدمات دولت هوشمند" in api.getForegroundObject().name: 
                is_gov = True
        except: pass

        if d:
            # Translators: Message reported when calling the CAPTCHA solving command
            msg = _("Solving...")
            self.report_status(msg)
            threading.Thread(target=self._thread_cap, args=(d, is_gov), daemon=True).start()
        else: 
            # Translators: Message reported when calling the CAPTCHA solving command
            msg = _("Capture failed.")
            self.report_status(msg)
        
    def _thread_cap(self, d, is_gov):
        cap_template = get_prompt_text("captcha_solver_base") or (
            "Blind user. Return CAPTCHA code only. If NO CAPTCHA is detected in the image, "
            "strictly return: [[[NO_CAPTCHA]]].{captcha_extra}"
        )
        cap_extra = " Read 5 Persian digits, convert to English." if is_gov else " Convert to English digits."
        p = apply_prompt_template(cap_template, [("captcha_extra", cap_extra)])
        
        r = self._call_gemini_safe(p, attachments=[{'mime_type': 'image/png', 'data': d}])
        if r:
            self.current_status = _("Idle")
            if "[[[NO_CAPTCHA]]]" in r:
                # Translators: Message reported when AI cannot find any CAPTCHA in the image
                wx.CallAfter(self.report_status, _("No CAPTCHA detected."))
            else:
                wx.CallAfter(self._finish_captcha, r)
        else: 
            # Translators: Message reported when calling the CAPTCHA solving command
            msg = _("Failed.")
            wx.CallAfter(self.report_status, msg)
            self.current_status = _("Idle")

    def _finish_captcha(self, text):
        if config.conf["VisionAssistant"]["copy_to_clipboard"]:
            api.copyToClip(text)
        send_ctrl_v()
        # Translators: Message reported when calling the CAPTCHA solving command
        msg = _("Captcha: {text}").format(text=text)
        wx.CallLater(200, self.report_status, msg)

    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Checks for updates manually."))
    def script_checkUpdate(self, gesture):
        if self.toggling: self.finish()
        # Translators: Message reported when calling the update command
        msg = _("Checking for updates...")
        self.report_status(msg)
        self.updater.check_for_updates(silent=False)

    def _capture_navigator(self):
        try:
            obj = api.getNavigatorObject()
            if not obj or not obj.location: return None,0,0
            x,y,w,h = obj.location
            if w<1 or h<1: return None,0,0
            bmp = wx.Bitmap(w,h)
            wx.MemoryDC(bmp).Blit(0,0,w,h,wx.ScreenDC(),x,y)
            s = io.BytesIO()
            bmp.ConvertToImage().SaveFile(s, wx.BITMAP_TYPE_PNG)
            return base64.b64encode(s.getvalue()).decode('utf-8'),w,h
        except: return None,0,0
    def _capture_fullscreen(self):
        try:
            w,h = wx.GetDisplaySize()
            bmp = wx.Bitmap(w,h)
            wx.MemoryDC(bmp).Blit(0,0,w,h,wx.ScreenDC(),0,0)
            s = io.BytesIO()
            bmp.ConvertToImage().SaveFile(s, wx.BITMAP_TYPE_PNG)
            return base64.b64encode(s.getvalue()).decode('utf-8'),w,h
        except: return None,0,0
    
    # Translators: Script description for Input Gestures dialog
    @scriptHandler.script(description=_("Translates the text currently in the clipboard."))
    def script_translateClipboard(self, gesture):
        if self.toggling: self.finish()
        t = api.getClipData()
        if t: 
            # Translators: Message when calling the command to translate from clipboard
            msg = _("Translating Clipboard...")
            self.report_status(msg)
            threading.Thread(target=self._thread_translate, args=(t,), daemon=True).start()
        else:
            # Translators: Message when calling the command to translate from clipboard
            msg = _("Clipboard empty.")
            self.report_status(msg)

    def on_settings_click(self, event):
        instance = getattr(gui.settingsDialogs.NVDASettingsDialog, "instance", None)
        if instance:
            try:
                instance.Enable(True)
                instance.Raise()
                instance.SetFocus()
                # Translators: Message shown when settings dialog is already open
                ui.message(_("Settings dialog is already open."))
                return
            except:
                gui.settingsDialogs.NVDASettingsDialog.instance = None

        def _open():
            try:
                gui.settingsDialogs.NVDASettingsDialog(gui.mainFrame, SettingsPanel)
            except Exception:
                # Translators: Message shown when settings dialog is already open
                ui.message(_("Settings dialog is already open."))
        
        wx.CallAfter(_open)

    def on_help_click(self, event):
        # Translators: Message when opening documentation
        self.report_status(_("Opening documentation..."))
        addon = addonHandler.getCodeAddon()
        doc_path = addon.getDocFilePath("readme.html")
        if doc_path:
            try:
                os.startfile(doc_path)
            except Exception as e:
                show_error_dialog(str(e))
        else:
            # Translators: Error when help file is missing
            show_error_dialog(_("Documentation file not found."))

    def on_donate_click(self, event):
        try:
            curr_dir = os.path.dirname(__file__)
            if curr_dir not in sys.path:
                sys.path.append(curr_dir)
            import donate_dialog
            wx.CallAfter(donate_dialog.requestDonations, gui.mainFrame)
        except Exception as e:
            show_error_dialog(str(e))

    __gestures = {
        "kb:NVDA+shift+v": "activateLayer",
    }
    
    __VisionGestures = {
        "kb:t": "translateSmart",
        "kb:r": "refineText",
        "kb:o": "ocrFullScreen",
        "kb:v": "describeObject",
        "kb:d": "analyzeDocument",
        "kb:f": "fileOCR",
        "kb:a": "transcribeAudio",
        "kb:c": "solveCaptcha",
        "kb:l": "announceStatus",
        "kb:s": "smartDictation",
        "kb:u": "checkUpdate",
        "kb:shift+t": "translateClipboard",
        "kb:shift+v": "analyzeOnlineVideo",
        "kb:h": "showHelp",
    }
