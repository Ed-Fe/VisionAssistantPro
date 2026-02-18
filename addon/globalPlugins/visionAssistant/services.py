# -*- coding: utf-8 -*-

import os
import json
import base64
import tempfile
import time
import ctypes
import re
import logging

import wx
from urllib import request, error, parse
from urllib.parse import quote, urlencode
from http import cookiejar
from uuid import uuid4

try:
    import fitz
except ImportError:
    fitz = None

import addonHandler
import config
import gui

from .constants import ADDON_NAME, CHROME_OCR_KEYS, TARGET_CODES
from .prompt_helpers import apply_prompt_template, get_prompt_text

log = logging.getLogger(__name__)
addonHandler.initTranslation()

def get_mime_type(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf': return 'application/pdf'
    if ext in ['.jpg', '.jpeg']: return 'image/jpeg'
    if ext == '.png': return 'image/png'
    if ext == '.webp': return 'image/webp'
    if ext in ['.tif', '.tiff']: return 'image/jpeg'
    if ext == '.mp3': return 'audio/mpeg'
    if ext == '.wav': return 'audio/wav'
    if ext == '.ogg': return 'audio/ogg'
    if ext == '.mp4': return 'video/mp4'
    return 'application/octet-stream'

def show_error_dialog(message):
    # Translators: Title of the error dialog box
    title = _("{name} Error").format(name=ADDON_NAME)
    wx.CallAfter(gui.messageBox, message, title, wx.OK | wx.ICON_ERROR)

def send_ctrl_v():
    try:
        user32 = ctypes.windll.user32
        VK_CONTROL = 0x11; VK_V = 0x56; KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_CONTROL, 0, 0, 0)
        user32.keybd_event(VK_V, 0, 0, 0)
        user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        log.debug("Failed to send Ctrl+V", exc_info=True)

def get_proxy_opener():
    proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
    if proxy_url:
        if "127.0.0.1" in proxy_url or "localhost" in proxy_url or ":" in proxy_url.split("/")[-1]:
             handler = request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
             return request.build_opener(handler)
    return request.build_opener()

def get_twitter_download_link(tweet_url):
    cj = cookiejar.CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(cj))
    base_url = "https://savetwitter.net/en4"
    api_url = "https://savetwitter.net/api/ajaxSearch"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'X-Requested-With': 'XMLHttpRequest', 'Referer': base_url}
    try:
        req_init = request.Request(base_url, headers=headers)
        opener.open(req_init)
        params = {'q': tweet_url, 'lang': 'en', 'cftoken': ''}
        data = urlencode(params).encode('utf-8')
        req_post = request.Request(api_url, data=data, headers=headers, method='POST')
        with opener.open(req_post) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get('status') == 'ok':
                html = res_data.get('data', '')
                match = re.search(r'href="(https?://dl\.snapcdn\.app/[^"]+)"', html)
                if match: return match.group(1)
    except Exception:
        log.debug("Failed to fetch Twitter download link", exc_info=True)
    return None

def get_instagram_download_link(insta_url):
    cj = cookiejar.CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(cj))
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://anon-viewer.com/',
        'Accept': '*/*'
    }
    opener.addheaders = list(headers.items())
    try:
        opener.open("https://anon-viewer.com/", timeout=30)
        
        if "/stories/" in insta_url:
            parts = insta_url.split("/")
            username = parts[parts.index("stories") + 1]
            api_url = f"https://anon-viewer.com/content.php?url={username}&method=allstories"
        else:
            encoded_url = quote(insta_url, safe='')
            api_url = f"https://anon-viewer.com/content.php?url={encoded_url}"

        response = opener.open(api_url, timeout=60)
        if response.getcode() == 200:
            res_content = response.read().decode('utf-8')
            data = json.loads(res_content)
            html_text = data.get('html', '')
            
            match = re.search(r'href="([^"]+anon-viewer\.com/media\.php\?media=[^"]+)"', html_text)
            if match:
                return match.group(1).replace('&amp;', '&')
            
            source_match = re.search(r'<source src="([^"]+)"', html_text)
            if source_match:
                return source_match.group(1).replace('&amp;', '&')
    except Exception:
        log.debug("Failed to fetch Instagram download link", exc_info=True)
    return None

def get_tiktok_download_link(tiktok_url):
    api_url = "https://www.tikwm.com/api/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }
    try:
        params = {'url': tiktok_url, 'hd': '1'}
        data = urlencode(params).encode('utf-8')
        req = request.Request(api_url, data=data, headers=headers, method='POST')
        opener = get_proxy_opener()
        with opener.open(req, timeout=120) as response:
            res = json.loads(response.read().decode('utf-8'))
            if res.get('code') == 0:
                play_url = res['data']['play']
                return play_url if play_url.startswith('http') else "https://www.tikwm.com" + play_url
    except Exception:
        log.debug("Failed to fetch TikTok download link", exc_info=True)
    return None

def _download_temp_video(url):
    try:
        req = request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with request.urlopen(req, timeout=120) as response:
            fd, path = tempfile.mkstemp(suffix=".mp4")
            os.close(fd)
            with open(path, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk: break
                    f.write(chunk)
            return path
    except Exception:
        log.debug("Failed to download temporary video", exc_info=True)
    return None

def get_file_path(title, wildcard, mode="open", multiple=False):
    style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST if mode == "open" else wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
    if multiple: style |= wx.FD_MULTIPLE
    with wx.FileDialog(gui.mainFrame, title, wildcard=wildcard, style=style) as dlg:
        if dlg.ShowModal() == wx.ID_OK:
            return dlg.GetPaths() if multiple else dlg.GetPath()
    return None

class VirtualDocument:
    def __init__(self, file_paths):
        self.file_paths = file_paths
        self.page_map = [] 
        self.total_pages = 0
        self.is_single_pdf = (len(file_paths) == 1 and file_paths[0].lower().endswith('.pdf'))
        self.single_pdf_path = file_paths[0] if self.is_single_pdf else None

    def scan(self):
        if not fitz: return
        for path in self.file_paths:
            try:
                doc = fitz.open(path)
                count = len(doc)
                for i in range(count):
                    self.page_map.append((path, i))
                doc.close()
            except Exception as e:
                log.error(f"Error scanning file {path}: {e}", exc_info=True)
        self.total_pages = len(self.page_map)

    def get_page_info(self, global_page_index):
        if 0 <= global_page_index < self.total_pages:
            return self.page_map[global_page_index]
        return None, None

    def create_merged_pdf(self, start_page, end_page):
        if not fitz: return None
        try:
            out_doc = fitz.open()
            for i in range(start_page, end_page + 1):
                f_path, f_idx = self.get_page_info(i)
                src_doc = fitz.open(f_path)
                if src_doc.is_pdf:
                    out_doc.insert_pdf(src_doc, from_page=f_idx, to_page=f_idx)
                else:
                    pdf_bytes = src_doc.convert_to_pdf(from_page=f_idx, to_page=f_idx)
                    img_pdf = fitz.open("pdf", pdf_bytes)
                    out_doc.insert_pdf(img_pdf)
                src_doc.close()
            
            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            out_doc.save(temp_path)
            out_doc.close()
            return temp_path
        except Exception as e:
            log.error(f"Error merging PDF: {e}", exc_info=True)
            return None

class ChromeOCREngine:
    @staticmethod
    def recognize(image_bytes):
        key = CHROME_OCR_KEYS[0]
        url = "https://ckintersect-pa.googleapis.com/v1/intersect/pixels"
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0", "x-goog-api-key": key}
        payload = {"imageRequests": [{"engineParameters": [{"ocrParameters": {}}], "imageBytes": base64.b64encode(image_bytes).decode('utf-8'), "imageId": str(uuid4())}]}
        try:
            req = request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
            opener = get_proxy_opener()
            with opener.open(req, timeout=120) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    regions = data['results'][0]['engineResults'][0]['ocrEngine'].get('ocrRegions', [])
                    lines = []
                    for reg in regions:
                        line_text = " ".join([w.get('detectedText', '') for w in reg.get('words', [])])
                        if line_text.strip(): lines.append(line_text)
                    return "\n".join(lines)
        except Exception as e:
            log.error(f"Chrome OCR Failed: {e}", exc_info=True)
            return None
        return None

class SmartProgrammersOCREngine:
    @staticmethod
    def recognize(image_bytes):
        url = "https://ubsa.in/smartprogrammers/SP%20Reader/extract.php"
        boundary = uuid4().hex.encode('utf-8')
        body = []
        body.append(b'--' + boundary)
        body.append(f'Content-Disposition: form-data; name="file"; filename="p.jpg"'.encode('utf-8'))
        body.append(b'Content-Type: image/jpeg')
        body.append(b'')
        body.append(image_bytes)
        body.append(b'--' + boundary + b'--')
        body.append(b'')
        try:
            req = request.Request(url, data=b'\r\n'.join(body), headers={'Content-Type': f"multipart/form-data; boundary={boundary.decode('utf-8')}"}, method="POST")
            opener = get_proxy_opener()
            with opener.open(req, timeout=120) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    text = data.get("text", "").replace("\\n", "\n")
                    return text if text.strip() else None
        except error.HTTPError as e:
            if e.code == 400:
                return None
        except Exception:
            pass
        return None

class GoogleTranslator:
    @staticmethod
    def translate(text, target_lang):
        try:
            target_code = TARGET_CODES.get(target_lang, 'en')
            base_url = "https://translate.googleapis.com/translate_a/single"
            params = {"client": "gtx", "sl": "auto", "tl": target_code, "dt": "t", "q": text}
            url = f"{base_url}?{parse.urlencode(params)}"
            req = request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            opener = get_proxy_opener()
            with opener.open(req, timeout=120) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    if data and isinstance(data, list) and len(data) > 0:
                        result_parts = [x[0] for x in data[0] if x[0]]
                        return "".join(result_parts)
        except Exception as e:
            log.error(f"Google Translate Failed: {e}", exc_info=True)
            return text 
        return text

class GeminiHandler:
    _working_key_idx = 0 
    _file_uri_keys = {}
    _max_retries = 5

    @staticmethod
    def _get_api_keys():
        raw = config.conf["VisionAssistant"]["api_key"]
        clean_raw = raw.replace('\r\n', ',').replace('\n', ',')
        return [k.strip() for k in clean_raw.split(',') if k.strip()]

    @staticmethod
    def _get_opener():
        return get_proxy_opener()

    @staticmethod
    def _handle_error(e):
        if hasattr(e, 'code'):
            # Translators: Error message for Bad Request (400)
            if e.code == 400: return _("Error 400: Bad Request (Check API Key)")
            # Translators: Error message for Forbidden (403)
            if e.code == 403: return _("Error 403: Forbidden (Check Region)")
            if e.code == 429: return "QUOTA_EXCEEDED"
            if e.code >= 500: return "SERVER_ERROR"
        return str(e)

    @staticmethod
    def _call_with_retry(func_logic, key, *args):
        last_exc = None
        for attempt in range(GeminiHandler._max_retries):
            try:
                return func_logic(key, *args)
            except error.HTTPError as e:
                err_msg = GeminiHandler._handle_error(e)
                if err_msg not in ["QUOTA_EXCEEDED", "SERVER_ERROR"]:
                    raise
                last_exc = e
            except error.URLError as e:
                last_exc = e
            if attempt < GeminiHandler._max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
        raise last_exc

    @staticmethod
    def _register_file_uri(uri, key):
        if uri and key:
            GeminiHandler._file_uri_keys[uri] = key
            while len(GeminiHandler._file_uri_keys) > 200:
                GeminiHandler._file_uri_keys.pop(next(iter(GeminiHandler._file_uri_keys)))

    @staticmethod
    def _get_registered_key(uri):
        if not uri:
            return None
        return GeminiHandler._file_uri_keys.get(uri)

    @staticmethod
    def _call_with_key(func_logic, key, *args):
        try:
            return GeminiHandler._call_with_retry(func_logic, key, *args)
        except error.HTTPError as e:
            err_msg = GeminiHandler._handle_error(e)
            if err_msg == "QUOTA_EXCEEDED":
                # Translators: Message of a dialog which may pop up while performing an AI call
                err_msg = _("Error 429: Quota Exceeded (Try later)")
            elif err_msg == "SERVER_ERROR":
                # Translators: Message of a dialog which may pop up while performing an AI call
                err_msg = _("Server Error {code}: {reason}").format(code=e.code, reason=e.reason)
            return "ERROR:" + err_msg
        except Exception as e:
            return "ERROR:" + str(e)

    @staticmethod
    def _call_with_rotation(func_logic, *args):
        keys = GeminiHandler._get_api_keys()
        if not keys: 
            # Translators: Error when no API keys are found in settings
            return "ERROR:" + _("No API Keys configured.")
        
        num_keys = len(keys)
        for i in range(num_keys):
            idx = (GeminiHandler._working_key_idx + i) % num_keys
            key = keys[idx]
            try:
                res = GeminiHandler._call_with_retry(func_logic, key, *args)
                GeminiHandler._working_key_idx = idx 
                return res
            except error.HTTPError as e:
                err_msg = GeminiHandler._handle_error(e)
                if err_msg in ["QUOTA_EXCEEDED", "SERVER_ERROR"]:
                    if i < num_keys - 1: continue
                    # Translators: Error when all available API keys fail
                    return "ERROR:" + _("All API Keys failed (Quota/Server).")
                return "ERROR:" + err_msg
            except Exception as e:
                return "ERROR:" + str(e)
        return "ERROR:" + _("Unknown error occurred.")

    @staticmethod
    def translate(text, target_lang):
        def _logic(key, txt, lang):
            model = config.conf["VisionAssistant"]["model_name"]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            quick_template = get_prompt_text("translate_quick") or "Translate to {target_lang}. Output ONLY translation."
            quick_prompt = apply_prompt_template(quick_template, [("target_lang", lang)])
            payload = {"contents": [{"parts": [{"text": quick_prompt}, {"text": txt}]}]}
            req = request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with GeminiHandler._get_opener().open(req, timeout=90) as r:
                return json.loads(r.read().decode())['candidates'][0]['content']['parts'][0]['text']
        return GeminiHandler._call_with_rotation(_logic, text, target_lang)

    @staticmethod
    def ocr_page(image_bytes):
        def _logic(key, img_data):
            model = config.conf["VisionAssistant"]["model_name"]
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            ocr_image_prompt = get_prompt_text("ocr_image_extract")
            payload = {"contents": [{"parts": [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(img_data).decode('utf-8')}}, {"text": ocr_image_prompt}]}]}
            req = request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with GeminiHandler._get_opener().open(req, timeout=120) as r:
                return json.loads(r.read().decode())['candidates'][0]['content']['parts'][0]['text']
        return GeminiHandler._call_with_rotation(_logic, image_bytes)

    @staticmethod
    def upload_and_process_batch(file_path, mime_type, page_count):
        keys = GeminiHandler._get_api_keys()
        if not keys: 
            # Translators: Error message for missing API Keys
            return [ "ERROR:" + _("No API Keys.") ]
        model = config.conf["VisionAssistant"]["model_name"]
        
        opener = GeminiHandler._get_opener()
        proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
        base_url = proxy_url.rstrip('/') if proxy_url else "https://generativelanguage.googleapis.com"
        
        for i, key in enumerate(keys):
            try:
                f_size = os.path.getsize(file_path)
                init_url = f"{base_url}/upload/v1beta/files"
                headers = {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(f_size), "X-Goog-Upload-Header-Content-Type": mime_type, "Content-Type": "application/json", "x-goog-api-key": key}
                
                req = request.Request(init_url, data=json.dumps({"file": {"display_name": "batch"}}).encode(), headers=headers, method="POST")
                with opener.open(req, timeout=120) as r: upload_url = r.headers.get("x-goog-upload-url")
                
                with open(file_path, 'rb') as f: f_data = f.read()
                req_up = request.Request(upload_url, data=f_data, headers={"Content-Length": str(f_size), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}, method="POST")
                with opener.open(req_up, timeout=180) as r:
                    res = json.loads(r.read().decode())
                    uri, name = res['file']['uri'], res['file']['name']
                
                active = False
                for attempt in range(30):
                    req_check = request.Request(f"{base_url}/v1beta/{name}", headers={"x-goog-api-key": key})
                    with opener.open(req_check, timeout=30) as r:
                        state = json.loads(r.read().decode()).get('state')
                        if state == "ACTIVE":
                            active = True
                            break
                        if state == "FAILED":
                            break
                    time.sleep(2)

                if not active:
                    if i < len(keys) - 1:
                        continue
                    return [ "ERROR:" + _("Upload failed.") ]

                GeminiHandler._register_file_uri(uri, key)
                
                url = f"{base_url}/v1beta/models/{model}:generateContent"
                prompt = get_prompt_text("ocr_document_extract")
                contents = [{"parts": [{"file_data": {"mime_type": mime_type, "file_uri": uri}}, {"text": prompt}]}]
                
                req_gen = request.Request(url, data=json.dumps({"contents": contents}).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
                with opener.open(req_gen, timeout=180) as r:
                    res = json.loads(r.read().decode())
                    text = res['candidates'][0]['content']['parts'][0]['text']
                    return text.split('[[[PAGE_SEP]]]')
                    
            except error.HTTPError as e:
                err_code = GeminiHandler._handle_error(e)
                if err_code in ["QUOTA_EXCEEDED", "SERVER_ERROR"] and i < len(keys) - 1:
                    continue
                if err_code == "QUOTA_EXCEEDED":
                    # Translators: Message of a dialog which may pop up while performing an AI call
                    err_msg = _("Error 429: Quota Exceeded (Try later)")
                elif err_code == "SERVER_ERROR":
                    # Translators: Message of a dialog which may pop up while performing an AI call
                    err_msg = _("Server Error {code}: {reason}").format(code=e.code, reason=e.reason)
                else:
                    err_msg = err_code
                return ["ERROR:" + err_msg]
            except Exception as e:
                return ["ERROR:" + str(e)]
        return ["ERROR:" + _("All keys failed.")]

    @staticmethod
    def chat(history, new_msg, file_uri, mime_type):
        def _logic(key, hist, msg, uri, mime):
            model = config.conf["VisionAssistant"]["model_name"]
            proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
            base_url = proxy_url.rstrip('/') if proxy_url else "https://generativelanguage.googleapis.com"
            url = f"{base_url}/v1beta/models/{model}:generateContent"
            
            contents = list(hist)
            if uri: 
                user_parts = [{"file_data": {"mime_type": mime, "file_uri": uri}}]
            else:
                user_parts = []
            user_parts.append({"text": msg})
            contents.append({"role": "user", "parts": user_parts})
            
            req = request.Request(url, data=json.dumps({"contents": contents}).encode(), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with GeminiHandler._get_opener().open(req, timeout=120) as r:
                return json.loads(r.read().decode())['candidates'][0]['content']['parts'][0]['text']
        forced_key = GeminiHandler._get_registered_key(file_uri) if file_uri else None
        if forced_key:
            return GeminiHandler._call_with_key(_logic, forced_key, history, new_msg, file_uri, mime_type)
        return GeminiHandler._call_with_rotation(_logic, history, new_msg, file_uri, mime_type)

    @staticmethod
    def upload_for_chat(file_path, mime_type):
        keys = GeminiHandler._get_api_keys()
        if not keys: return None
        opener = GeminiHandler._get_opener()
        proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
        base_url = proxy_url.rstrip('/') if proxy_url else "https://generativelanguage.googleapis.com"
        
        for key in keys:
            try:
                f_size = os.path.getsize(file_path)
                init_url = f"{base_url}/upload/v1beta/files"
                headers = {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(f_size), "X-Goog-Upload-Header-Content-Type": mime_type, "Content-Type": "application/json", "x-goog-api-key": key}
                req = request.Request(init_url, data=json.dumps({"file": {"display_name": os.path.basename(file_path)}}).encode(), headers=headers, method="POST")
                with opener.open(req, timeout=120) as r: upload_url = r.headers.get("x-goog-upload-url")
                with open(file_path, 'rb') as f: f_data = f.read()
                req_up = request.Request(upload_url, data=f_data, headers={"Content-Length": str(f_size), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}, method="POST")
                with opener.open(req_up, timeout=180) as r:
                    res = json.loads(r.read().decode())
                    uri, name = res['file']['uri'], res['file']['name']
                for attempt in range(30):
                    req_check = request.Request(f"{base_url}/v1beta/{name}", headers={"x-goog-api-key": key})
                    with opener.open(req_check, timeout=30) as r:
                        state = json.loads(r.read().decode()).get('state')
                        if state == "ACTIVE":
                            GeminiHandler._register_file_uri(uri, key)
                            return uri
                    time.sleep(2)
                return None 
            except Exception:
                log.debug("Failed to upload file for chat with current key", exc_info=True)
                continue
        return None

    @staticmethod
    def generate_speech(text, voice_name):
        def _logic(key, txt, voice):
            main_model = config.conf["VisionAssistant"]["model_name"]
            if "pro" in main_model.lower():
                tts_model = "gemini-2.5-pro-preview-tts"
            else:
                tts_model = "gemini-2.5-flash-preview-tts"

            proxy_url = config.conf["VisionAssistant"]["proxy_url"].strip()
            base_url = proxy_url.rstrip('/') if proxy_url else "https://generativelanguage.googleapis.com"
            url = f"{base_url}/v1beta/models/{tts_model}:generateContent"
            
            payload = {
                "contents": [{"parts": [{"text": txt}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}
                }
            }
            req = request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={"Content-Type": "application/json", "x-goog-api-key": key})
            with GeminiHandler._get_opener().open(req, timeout=600) as r:
                res = json.loads(r.read().decode())
                candidates = res.get('candidates', [])
                if not candidates: raise Exception("No candidates returned")
                content = candidates[0].get('content', {})
                parts = content.get('parts', [])
                if not parts: raise Exception("No parts in response")
                part = parts[0]
                if 'inlineData' in part: return part['inlineData']['data']
                if 'inline_data' in part: return part['inline_data']['data']
                if 'text' in part: raise Exception(f"Model refused audio: {part['text']}")
                raise Exception("Unknown response format")
        return GeminiHandler._call_with_rotation(_logic, text, voice_name)
