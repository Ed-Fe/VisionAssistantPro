# -*- coding: utf-8 -*-

import os
import json
import io
import tempfile
import threading
import gc
import wave
import logging

import wx

import addonHandler
import config
import gui
import ui
import api
import textInfos
import tones
import scriptHandler

from .prompt_manager_dialog import PromptManagerDialog
from .constants import (
    ADDON_NAME,
    GEMINI_VOICES,
    MODELS,
    OCR_ENGINES,
    PROMPT_VARIABLES_GUIDE,
    SOURCE_NAMES,
    TARGET_NAMES,
)
from .markdown_utils import clean_markdown, markdown_to_html
from .prompt_helpers import (
    get_configured_default_prompts,
    load_configured_custom_prompts,
    serialize_custom_prompts_v2,
    serialize_default_prompt_overrides,
)
from .services import GeminiHandler, get_file_path, get_mime_type, show_error_dialog

log = logging.getLogger(__name__)
addonHandler.initTranslation()

class VisionQADialog(wx.Dialog):
    def __init__(self, parent, title, initial_text, context_data, callback_fn, extra_info=None, raw_content=None, status_callback=None, announce_on_open=True, allow_questions=True):
        super(VisionQADialog, self).__init__(parent, title=title, size=(550, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.context_data = context_data 
        self.callback_fn = callback_fn
        self.extra_info = extra_info
        self.chat_history = [] 
        self.raw_content = raw_content
        self.status_callback = status_callback
        self.announce_on_open = announce_on_open
        self.allow_questions = allow_questions
        
        mainSizer = wx.BoxSizer(wx.VERTICAL)
        # Translators: Label for the AI response text area in a chat dialog
        lbl_text = _("AI Response:")
        lbl = wx.StaticText(self, label=lbl_text)
        mainSizer.Add(lbl, 0, wx.ALL, 5)
        self.outputArea = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        mainSizer.Add(self.outputArea, 1, wx.EXPAND | wx.ALL, 5)
        
        self.should_clean = config.conf["VisionAssistant"]["clean_markdown_chat"]
        display_text = clean_markdown(initial_text) if self.should_clean else initial_text
        if display_text:
            # Translators: Format for displaying AI message in a chat dialog
            init_msg = _("AI: {text}\n").format(text=display_text)
            self.outputArea.AppendText(init_msg)
            if config.conf["VisionAssistant"]["copy_to_clipboard"]:
                api.copyToClip(raw_content if raw_content else display_text)
        
        if not (extra_info and extra_info.get('skip_init_history')):
             self.chat_history.append({"role": "model", "parts": [{"text": initial_text}]})

        self.inputArea = None
        if allow_questions:
            # Translators: Label for user input field in a chat dialog
            ask_text = _("Ask:")
            inputLbl = wx.StaticText(self, label=ask_text)
            mainSizer.Add(inputLbl, 0, wx.ALL, 5)
            self.inputArea = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER, size=(-1, 30))
            mainSizer.Add(self.inputArea, 0, wx.EXPAND | wx.ALL, 5)
        
        btnSizer = wx.BoxSizer(wx.HORIZONTAL)
        self.askBtn = None
        if allow_questions:
            # Translators: Button to send message in a chat dialog
            self.askBtn = wx.Button(self, label=_("Send"))
        # Translators: Button to view the content in a formatted HTML window
        self.viewBtn = wx.Button(self, label=_("View Formatted"))
        self.viewBtn.Bind(wx.EVT_BUTTON, self.onView)
        # Translators: Button to save only the result content without chat history
        self.saveContentBtn = wx.Button(self, label=_("Save Content"))
        self.saveContentBtn.Bind(wx.EVT_BUTTON, self.onSaveContent)
        # Translators: Button to save chat in a chat dialog
        self.saveBtn = wx.Button(self, label=_("Save Chat"))
        # Translators: Button to close chat dialog
        self.closeBtn = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
        
        self.saveBtn.Enable(bool(initial_text.strip()))
        self.viewBtn.Enable(bool(self.raw_content))
        self.saveContentBtn.Enable(bool(self.raw_content))

        if self.askBtn:
            btnSizer.Add(self.askBtn, 0, wx.ALL, 5)
        btnSizer.Add(self.viewBtn, 0, wx.ALL, 5)
        btnSizer.Add(self.saveContentBtn, 0, wx.ALL, 5)
        btnSizer.Add(self.saveBtn, 0, wx.ALL, 5)
        btnSizer.Add(self.closeBtn, 0, wx.ALL, 5)
        mainSizer.Add(btnSizer, 0, wx.ALIGN_RIGHT)
        
        self.SetSizer(mainSizer)
        if self.inputArea:
            self.inputArea.SetFocus()
        else:
            self.outputArea.SetFocus()
        if self.askBtn:
            self.askBtn.Bind(wx.EVT_BUTTON, self.onAsk)
        self.saveBtn.Bind(wx.EVT_BUTTON, self.onSave)
        if self.inputArea:
            self.inputArea.Bind(wx.EVT_TEXT_ENTER, self.onAsk)
        if display_text and self.announce_on_open:
            wx.CallLater(300, ui.message, display_text)

    def onAsk(self, event):
        if not self.inputArea:
            return
        question = self.inputArea.Value
        if not question.strip(): return
        # Translators: Format for displaying User message in a chat dialog
        user_msg = _("\nYou: {text}\n").format(text=question)
        self.outputArea.AppendText(user_msg)
        self.inputArea.Clear()
        # Translators: Message shown while processing in a chat dialog
        msg = _("Thinking...")
        ui.message(msg)
        threading.Thread(target=self.process_question, args=(question,), daemon=True).start()

    def process_question(self, question):
        result_tuple = self.callback_fn(self.context_data, question, self.chat_history, self.extra_info)
        response_text, _ = result_tuple
        if response_text:
            if not (self.extra_info and self.extra_info.get('file_context')):
                 self.chat_history.append({"role": "user", "parts": [{"text": question}]})
                 self.chat_history.append({"role": "model", "parts": [{"text": response_text}]})
            final_text = clean_markdown(response_text) if self.should_clean else response_text
            wx.CallAfter(self.update_response, final_text, response_text)

    def update_response(self, display_text, raw_text=None):
        if raw_text:
            self.raw_content = raw_text
            self.viewBtn.Enable(True)
            self.saveContentBtn.Enable(True)
        # Translators: Format for displaying AI message in a chat dialog
        ai_msg = _("AI: {text}\n").format(text=display_text)
        self.outputArea.AppendText(ai_msg)
        self.saveBtn.Enable(True)
        if config.conf["VisionAssistant"]["copy_to_clipboard"]:
            api.copyToClip(raw_text if raw_text else display_text)
        self.outputArea.ShowPosition(self.outputArea.GetLastPosition())
        ui.message(display_text)

    def report_save(self, msg):
        if self.status_callback: self.status_callback(msg)
        else: ui.message(msg)

    def onView(self, event):
        full_html = ""
        # Translators: Format for displaying User message in a chat dialog
        user_label = _("\nYou: {text}\n").format(text="").strip()
        # Translators: Format for displaying AI message in a chat dialog
        ai_label = _("AI: {text}\n").format(text="").strip()
        
        if self.chat_history:
            for item in self.chat_history:
                role = item.get("role", "")
                text = item.get("parts", [{}])[0].get("text", "")
                if role == "user":
                    safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    full_html += f"<h2>{user_label}</h2><p>{safe_text}</p>"
                elif role == "model":
                    formatted_text = markdown_to_html(text, full_page=False)
                    full_html += f"<h2>{ai_label}</h2>{formatted_text}<hr>"
        
        if not full_html and self.raw_content:
             formatted_text = markdown_to_html(self.raw_content, full_page=False)
             full_html += f"<h2>{ai_label}</h2>{formatted_text}"

        if not full_html: return
        try:
            # Translators: Title of the formatted result window
            ui.browseableMessage(full_html, _("Formatted Conversation"), isHtml=True)
        except Exception as e:
            # Translators: Error message if viewing fails
            msg = _("Error displaying content: {error}").format(error=e)
            show_error_dialog(msg)

    def onSave(self, event):
        # Translators: Save dialog title
        path = get_file_path(_("Save Chat Log"), "Text files (*.txt)|*.txt", mode="save")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f: f.write(self.outputArea.GetValue())
                # Translators: Message shown on successful save of a file.
                self.report_save(_("Saved."))
            except Exception as e:
                # Translators: Message in the error dialog when saving fails.
                msg = _("Save failed: {error}").format(error=e)
                show_error_dialog(msg)

    def onSaveContent(self, event):
        # Translators: Save dialog title
        path = get_file_path(_("Save Result"), "HTML files (*.html)|*.html", mode="save")
        if path:
            try:
                full_html = markdown_to_html(self.raw_content, full_page=True)
                with open(path, "w", encoding="utf-8") as f: f.write(full_html)
                # Translators: Message on successful save
                self.report_save(_("Saved."))
            except Exception as e:
                # Translators: Message in the error dialog when saving fails.
                msg = _("Save failed: {error}").format(error=e)
                show_error_dialog(msg)

class SettingsPanel(gui.settingsDialogs.SettingsPanel):
    title = ADDON_NAME
    def makeSettings(self, settingsSizer):
        # --- Connection Group ---
        # Translators: Title of the settings group for connection and updates
        groupLabel = _("Connection")
        self.connectionBox = wx.StaticBox(self, label=groupLabel)
        connectionSizer = wx.StaticBoxSizer(self.connectionBox, wx.VERTICAL)
        cHelper = gui.guiHelper.BoxSizerHelper(self.connectionBox, sizer=connectionSizer)

        # Translators: Label for API Key input
        apiLabel = wx.StaticText(self.connectionBox, label=_("Gemini API Key (Separate multiple keys with comma or newline):"))
        cHelper.addItem(apiLabel)
        
        api_value = config.conf["VisionAssistant"]["api_key"]
        
        self.apiKeyCtrl_hidden = wx.TextCtrl(self.connectionBox, value=api_value, style=wx.TE_PASSWORD, size=(-1, -1))
        
        self.apiKeyCtrl_visible = wx.TextCtrl(self.connectionBox, value=api_value, style=wx.TE_MULTILINE | wx.TE_DONTWRAP, size=(-1, 60))
        self.apiKeyCtrl_visible.Hide()
        
        cHelper.addItem(self.apiKeyCtrl_hidden)
        cHelper.addItem(self.apiKeyCtrl_visible)
        
        # Translators: Checkbox to toggle API Key visibility
        self.showApiCheck = wx.CheckBox(self.connectionBox, label=_("Show API Key"))
        self.showApiCheck.Bind(wx.EVT_CHECKBOX, self.onToggleApiVisibility)
        cHelper.addItem(self.showApiCheck)
        
        model_display_names = [opt[0] for opt in MODELS]
        # Translators: Label for Model selection
        self.model = cHelper.addLabeledControl(_("AI Model:"), wx.Choice, choices=model_display_names)
        current_id = config.conf["VisionAssistant"]["model_name"]
        try:
            index = next(i for i, v in enumerate(MODELS) if v[1] == current_id)
            self.model.SetSelection(index)
        except StopIteration: self.model.SetSelection(0)

        # Translators: Label for Proxy URL input
        self.proxyUrl = cHelper.addLabeledControl(_("Proxy URL:"), wx.TextCtrl)
        self.proxyUrl.Value = config.conf["VisionAssistant"]["proxy_url"]

        # Translators: Checkbox to enable/disable automatic update checks on NVDA startup
        self.checkUpdateStartup = cHelper.addItem(wx.CheckBox(self.connectionBox, label=_("Check for updates on startup")))
        self.checkUpdateStartup.Value = config.conf["VisionAssistant"]["check_update_startup"]
        # Translators: Checkbox to toggle markdown cleaning in chat windows
        self.cleanMarkdown = cHelper.addItem(wx.CheckBox(self.connectionBox, label=_("Clean Markdown in Chat")))
        self.cleanMarkdown.Value = config.conf["VisionAssistant"]["clean_markdown_chat"]
        # Translators: Checkbox to enable copying AI responses to clipboard
        self.copyToClipboard = cHelper.addItem(wx.CheckBox(self.connectionBox, label=_("Copy AI responses to clipboard")))
        self.copyToClipboard.Value = config.conf["VisionAssistant"]["copy_to_clipboard"]
        # Translators: Checkbox to skip chat window and only speak AI responses
        self.skipChatDialog = cHelper.addItem(wx.CheckBox(self.connectionBox, label=_("Direct Output (No Chat Window)")))
        self.skipChatDialog.Value = config.conf["VisionAssistant"]["skip_chat_dialog"]
        settingsSizer.Add(connectionSizer, 0, wx.EXPAND | wx.ALL, 5)

        # --- Translation Languages Group ---
        # Translators: Title of the settings group for translation languages configuration
        groupLabel = _("Translation Languages")
        langBox = wx.StaticBox(self, label=groupLabel)
        langSizer = wx.StaticBoxSizer(langBox, wx.VERTICAL)
        lHelper = gui.guiHelper.BoxSizerHelper(langBox, sizer=langSizer)

        # Translators: Label for Source Language selection
        self.sourceLang = lHelper.addLabeledControl(_("Source:"), wx.Choice, choices=SOURCE_NAMES)
        try: self.sourceLang.SetSelection(SOURCE_NAMES.index(config.conf["VisionAssistant"]["source_language"]))
        except: self.sourceLang.SetSelection(0)
        
        # Translators: Label for Target Language selection
        self.targetLang = lHelper.addLabeledControl(_("Target:"), wx.Choice, choices=TARGET_NAMES)
        try: self.targetLang.SetSelection(TARGET_NAMES.index(config.conf["VisionAssistant"]["target_language"]))
        except: self.targetLang.SetSelection(0)
        
        # Translators: Label for AI Response Language selection
        self.aiResponseLang = lHelper.addLabeledControl(_("AI Response:"), wx.Choice, choices=TARGET_NAMES)
        try: self.aiResponseLang.SetSelection(TARGET_NAMES.index(config.conf["VisionAssistant"]["ai_response_language"]))
        except: self.aiResponseLang.SetSelection(0)

        # Translators: Checkbox for Smart Swap feature
        self.smartSwap = lHelper.addItem(wx.CheckBox(langBox, label=_("Smart Swap")))
        self.smartSwap.Value = config.conf["VisionAssistant"]["smart_swap"]
        settingsSizer.Add(langSizer, 0, wx.EXPAND | wx.ALL, 5)

        # --- Document Reader Settings ---
        # Translators: Title of settings group for Document Reader features
        groupLabel = _("Document Reader")
        docBox = wx.StaticBox(self, label=groupLabel)
        docSizer = wx.StaticBoxSizer(docBox, wx.VERTICAL)
        dHelper = gui.guiHelper.BoxSizerHelper(docBox, sizer=docSizer)

        # Translators: Label for OCR Engine selection
        self.ocr_sel = dHelper.addLabeledControl(_("OCR Engine:"), wx.Choice, choices=[x[0] for x in OCR_ENGINES])
        curr_ocr = config.conf["VisionAssistant"]["ocr_engine"]
        try:
            o_idx = next(i for i, v in enumerate(OCR_ENGINES) if v[1] == curr_ocr)
            self.ocr_sel.SetSelection(o_idx)
        except: self.ocr_sel.SetSelection(0)

        voice_choices = [f"{v[0]} - {v[1]}" for v in GEMINI_VOICES]
        # Translators: Label for TTS Voice selection
        self.voice_sel = dHelper.addLabeledControl(_("TTS Voice:"), wx.Choice, choices=voice_choices)
        curr_voice = config.conf["VisionAssistant"]["tts_voice"]
        try:
            v_idx = next(i for i, v in enumerate(GEMINI_VOICES) if v[0] == curr_voice)
            self.voice_sel.SetSelection(v_idx)
        except: self.voice_sel.SetSelection(1)
        settingsSizer.Add(docSizer, 0, wx.EXPAND | wx.ALL, 5)

        # --- CAPTCHA Group ---
        # Translators: Title of the settings group for CAPTCHA options
        groupLabel = _("CAPTCHA")
        capBox = wx.StaticBox(self, label=groupLabel)
        capSizer = wx.StaticBoxSizer(capBox, wx.VERTICAL)
        capHelper = gui.guiHelper.BoxSizerHelper(capBox, sizer=capSizer)
        # Translators: Label for CAPTCHA capture method selection
        self.captchaMode = capHelper.addLabeledControl(_("Capture Method:"), wx.Choice, choices=[
            # Translators: A choice for capture method. Captures only the specific object under the NVDA navigator cursor.
            _("Navigator Object"),
            # Translators: A choice for capture method. Captures the entire visible screen area.
            _("Full Screen")
        ])
        self.captchaMode.SetSelection(0 if config.conf["VisionAssistant"]["captcha_mode"] == 'navigator' else 1)
        settingsSizer.Add(capSizer, 0, wx.EXPAND | wx.ALL, 5)

        self.defaultPromptItems = get_configured_default_prompts()
        self.customPromptItems = load_configured_custom_prompts()

        # --- Prompt Manager Group ---
        # Translators: Title of the settings group for prompt management
        groupLabel = _("Prompts")
        promptsBox = wx.StaticBox(self, label=groupLabel)
        promptsSizer = wx.StaticBoxSizer(promptsBox, wx.VERTICAL)
        pHelper = gui.guiHelper.BoxSizerHelper(promptsBox, sizer=promptsSizer)
        # Translators: Description for the prompt manager button.
        pHelper.addItem(wx.StaticText(promptsBox, label=_("Manage default and custom prompts.")))
        # Translators: Button label to open prompt manager dialog.
        self.managePromptsBtn = wx.Button(promptsBox, label=_("Manage Prompts..."))
        self.managePromptsBtn.Bind(wx.EVT_BUTTON, self.onManagePrompts)
        pHelper.addItem(self.managePromptsBtn)
        self.promptsSummary = wx.StaticText(promptsBox)
        pHelper.addItem(self.promptsSummary)
        self._refreshPromptSummary()
        settingsSizer.Add(promptsSizer, 0, wx.EXPAND | wx.ALL, 5)

    def _refreshPromptSummary(self):
        # Translators: Summary text for prompt counts in settings.
        summary = _("Default prompts: {defaultCount}, Custom prompts: {customCount}").format(
            defaultCount=len(self.defaultPromptItems),
            customCount=len(self.customPromptItems),
        )
        self.promptsSummary.SetLabel(summary)

    def onManagePrompts(self, event):
        top = wx.GetTopLevelParent(self)
        dlg = PromptManagerDialog(
            self,
            self.defaultPromptItems,
            self.customPromptItems,
            PROMPT_VARIABLES_GUIDE,
        )
        try:
            if dlg.ShowModal() == wx.ID_OK:
                self.defaultPromptItems = dlg.get_default_items()
                self.customPromptItems = dlg.get_custom_items()
                self._refreshPromptSummary()
        finally:
            dlg.Destroy()
            if top:
                top.Enable(True)
                top.SetFocus()

    def onToggleApiVisibility(self, event):
        if self.showApiCheck.IsChecked():
            self.apiKeyCtrl_visible.SetValue(self.apiKeyCtrl_hidden.GetValue())
            self.apiKeyCtrl_hidden.Hide()
            self.apiKeyCtrl_visible.Show()
        else:
            self.apiKeyCtrl_hidden.SetValue(self.apiKeyCtrl_visible.GetValue())
            self.apiKeyCtrl_visible.Hide()
            self.apiKeyCtrl_hidden.Show()
        
        self.connectionBox.GetParent().Layout()

    def onSave(self):
        val = self.apiKeyCtrl_visible.GetValue() if self.showApiCheck.IsChecked() else self.apiKeyCtrl_hidden.GetValue()
        config.conf["VisionAssistant"]["api_key"] = val.strip()
        config.conf["VisionAssistant"]["model_name"] = MODELS[self.model.GetSelection()][1]
        config.conf["VisionAssistant"]["proxy_url"] = self.proxyUrl.Value.strip()
        config.conf["VisionAssistant"]["source_language"] = SOURCE_NAMES[self.sourceLang.GetSelection()]
        config.conf["VisionAssistant"]["target_language"] = TARGET_NAMES[self.targetLang.GetSelection()]
        config.conf["VisionAssistant"]["ai_response_language"] = TARGET_NAMES[self.aiResponseLang.GetSelection()]
        config.conf["VisionAssistant"]["smart_swap"] = self.smartSwap.Value
        config.conf["VisionAssistant"]["check_update_startup"] = self.checkUpdateStartup.Value
        config.conf["VisionAssistant"]["clean_markdown_chat"] = self.cleanMarkdown.Value
        config.conf["VisionAssistant"]["copy_to_clipboard"] = self.copyToClipboard.Value
        config.conf["VisionAssistant"]["skip_chat_dialog"] = self.skipChatDialog.Value
        config.conf["VisionAssistant"]["captcha_mode"] = 'navigator' if self.captchaMode.GetSelection() == 0 else 'fullscreen'
        config.conf["VisionAssistant"]["custom_prompts_v2"] = serialize_custom_prompts_v2(self.customPromptItems)
        config.conf["VisionAssistant"]["custom_prompts"] = ""
        config.conf["VisionAssistant"]["default_refine_prompts"] = serialize_default_prompt_overrides(self.defaultPromptItems)
        config.conf["VisionAssistant"]["ocr_engine"] = OCR_ENGINES[self.ocr_sel.GetSelection()][1]
        config.conf["VisionAssistant"]["tts_voice"] = GEMINI_VOICES[self.voice_sel.GetSelection()][0]

class RangeDialog(wx.Dialog):
    def __init__(self, parent, total_pages):
        # Translators: Title of the PDF options dialog
        super().__init__(parent, title=_("Options"), size=(350, 320))
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Translators: Label showing total pages found
        sizer.Add(wx.StaticText(self, label=_("Total Pages (All Files): {count}").format(count=total_pages)), 0, wx.ALL, 10)
        
        # Translators: Box title for page range selection
        box_range = wx.StaticBoxSizer(wx.VERTICAL, self, _("Range"))
        g_sizer = wx.FlexGridSizer(2, 2, 10, 10)
        # Translators: Label for start page
        g_sizer.Add(wx.StaticText(self, label=_("From:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_from = wx.SpinCtrl(self, min=1, max=total_pages, initial=1)
        g_sizer.Add(self.spin_from, 1, wx.EXPAND)
        # Translators: Label for end page
        g_sizer.Add(wx.StaticText(self, label=_("To:")), 0, wx.ALIGN_CENTER_VERTICAL)
        self.spin_to = wx.SpinCtrl(self, min=1, max=total_pages, initial=total_pages)
        g_sizer.Add(self.spin_to, 1, wx.EXPAND)
        box_range.Add(g_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(box_range, 0, wx.EXPAND | wx.ALL, 10)

        # Translators: Box title for translation options
        box_trans = wx.StaticBoxSizer(wx.VERTICAL, self, _("Translation"))
        # Translators: Checkbox to enable translation
        self.chk_trans = wx.CheckBox(self, label=_("Translate Output"))
        box_trans.Add(self.chk_trans, 0, wx.ALL, 5)
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Label for target language
        h_sizer.Add(wx.StaticText(self, label=_("Target:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.cmb_lang = wx.Choice(self, choices=TARGET_NAMES)
        self.cmb_lang.SetSelection(0)
        h_sizer.Add(self.cmb_lang, 1)
        box_trans.Add(h_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(box_trans, 0, wx.EXPAND | wx.ALL, 10)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Button to start processing
        btn_ok = wx.Button(self, wx.ID_OK, label=_("Start"))
        btn_ok.SetDefault()
        # Translators: Button to cancel
        btn_cancel = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
        btn_sizer.Add(btn_ok, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_cancel, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        self.SetSizer(sizer)

        self.chk_trans.Bind(wx.EVT_CHECKBOX, self.on_check)
        self.cmb_lang.Disable()

    def on_check(self, event):
        self.cmb_lang.Enable(self.chk_trans.IsChecked())

    def get_settings(self):
        return {
            'start': self.spin_from.GetValue() - 1,
            'end': self.spin_to.GetValue() - 1,
            'translate': self.chk_trans.IsChecked(),
            'lang': TARGET_NAMES[self.cmb_lang.GetSelection()]
        }

class ChatDialog(wx.Dialog):
    instance = None

    def __init__(self, parent, file_path):
        # Translators: Title of the chat dialog
        super().__init__(parent, title=_("Ask about Document"), size=(600, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        ChatDialog.instance = self
        self.file_path = file_path
        self.file_uri = None
        self.mime_type = get_mime_type(file_path)
        self.history = []
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Translators: Label showing the analyzed file name
        lbl_info = wx.StaticText(self, label=_("File: {name}").format(name=os.path.basename(file_path)))
        sizer.Add(lbl_info, 0, wx.ALL, 5)
        self.display = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        sizer.Add(self.display, 1, wx.EXPAND | wx.ALL, 10)
        # Translators: Status message while uploading
        self.display.SetValue(_("Uploading to Gemini...\n"))
        
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Label for the chat input field
        input_sizer.Add(wx.StaticText(self, label=_("Your Question:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.input = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER, size=(-1, 30))
        self.input.Bind(wx.EVT_TEXT_ENTER, self.on_send)
        input_sizer.Add(self.input, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Translators: Button to send message
        self.btn_send = wx.Button(self, label=_("Send"))
        self.btn_send.Bind(wx.EVT_BUTTON, self.on_send)
        self.btn_send.Disable()
        input_sizer.Add(self.btn_send, 0)
        sizer.Add(input_sizer, 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(sizer)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        threading.Thread(target=self.init_upload, daemon=True).start()

    def on_close(self, event):
        ChatDialog.instance = None
        self.Destroy()

    def init_upload(self):
        uri = GeminiHandler.upload_for_chat(self.file_path, self.mime_type)
        if uri and not str(uri).startswith("ERROR:"):
            self.file_uri = uri
            wx.CallAfter(self.on_ready)
        else:
            err_msg = str(uri)[6:] if uri else _("Upload failed.")
            wx.CallAfter(show_error_dialog, err_msg)
            wx.CallAfter(self.Close)

    def on_ready(self):
        # Translators: Message when ready to chat
        self.display.AppendText(_("Ready! Ask your questions.\n"))
        self.btn_send.Enable()
        self.input.SetFocus()

    def on_send(self, event):
        msg = self.input.GetValue().strip()
        if not msg: return
        self.input.Clear()
        self.display.AppendText(f"You: {msg}\n")
        # Translators: Message showing AI is thinking
        ui.message(_("Thinking..."))
        threading.Thread(target=self.do_chat, args=(msg,), daemon=True).start()

    def do_chat(self, msg):
        resp = GeminiHandler.chat(self.history, msg, self.file_uri, self.mime_type)
        
        if str(resp).startswith("ERROR:"):
            show_error_dialog(resp[6:])
            if _vision_assistant_instance:
                # Translators: Initial status when the add-on is doing nothing
                _vision_assistant_instance.current_status = _("Idle")
            return

        self.history.append({"role": "user", "parts": [{"text": msg}]})
        self.history.append({"role": "model", "parts": [{"text": resp}]})
        wx.CallAfter(self.display.AppendText, f"AI: {resp}\n\n")
        # Translators: Spoken prefix for AI response
        wx.CallAfter(ui.message, _("AI: ") + resp)

class DocumentViewerDialog(wx.Dialog):
    def __init__(self, parent, virtual_doc, settings):
        # Translators: Title of the Document Reader window.
        title_text = f"{ADDON_NAME} - {_('Document Reader')}"
        super().__init__(parent, title=title_text, size=(800, 600), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        self.v_doc = virtual_doc
        self.start_page = settings['start']
        self.end_page = settings['end']
        self.do_translate = settings['translate']
        self.target_lang = settings['lang']
        self.range_count = self.end_page - self.start_page + 1
        self.page_cache = {}
        self.current_page = self.start_page
        self.thread_pool = ThreadPoolExecutor(max_workers=5)
        
        self.init_ui()
        self.Centre()
        threading.Thread(target=self.start_auto_processing, daemon=True).start()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        # Translators: Initial status message
        self.lbl_status = wx.StaticText(panel, label=_("Initializing..."))
        vbox.Add(self.lbl_status, 0, wx.ALL, 5)
        self.txt_content = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        vbox.Add(self.txt_content, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        hbox_nav = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Button to go to previous page
        self.btn_prev = wx.Button(panel, label=_("Previous (Ctrl+PageUp)"))
        self.btn_prev.Bind(wx.EVT_BUTTON, self.on_prev)
        hbox_nav.Add(self.btn_prev, 0, wx.RIGHT, 5)
        # Translators: Button to go to next page
        self.btn_next = wx.Button(panel, label=_("Next (Ctrl+PageDown)"))
        self.btn_next.Bind(wx.EVT_BUTTON, self.on_next)
        hbox_nav.Add(self.btn_next, 0, wx.RIGHT, 15)
        # Translators: Label for Go To Page
        hbox_nav.Add(wx.StaticText(panel, label=_("Go to:")), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        choices = [str(i+1) for i in range(self.start_page, self.end_page + 1)]
        self.cmb_pages = wx.Choice(panel, choices=choices)
        self.cmb_pages.Bind(wx.EVT_CHOICE, self.on_page_select)
        hbox_nav.Add(self.cmb_pages, 0, wx.RIGHT, 15)
        vbox.Add(hbox_nav, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        hbox_actions = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Button to Ask questions about the document
        self.btn_ask = wx.Button(panel, label=_("Ask AI (Alt+A)"))
        self.btn_ask.Bind(wx.EVT_BUTTON, self.on_ask)
        hbox_actions.Add(self.btn_ask, 0, wx.RIGHT, 5)
        
        # Translators: Button to force re-scan
        self.btn_gemini = wx.Button(panel, label=_("Re-scan with Gemini (Alt+R)"))
        self.btn_gemini.Bind(wx.EVT_BUTTON, self.on_gemini_scan)
        hbox_actions.Add(self.btn_gemini, 0, wx.RIGHT, 5)
        
        # Translators: Button to generate audio
        self.btn_tts = wx.Button(panel, label=_("Generate Audio (Alt+G)"))
        self.btn_tts.Bind(wx.EVT_BUTTON, self.on_tts)
        hbox_actions.Add(self.btn_tts, 0, wx.RIGHT, 5)

        # Translators: Button to view formatted content
        self.btn_view = wx.Button(panel, label=_("View Formatted"))
        self.btn_view.Bind(wx.EVT_BUTTON, self.on_view)
        hbox_actions.Add(self.btn_view, 0, wx.RIGHT, 5)

        # Translators: Button to save text
        self.btn_save = wx.Button(panel, label=_("Save (Alt+S)"))
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save_all)
        hbox_actions.Add(self.btn_save, 0)
        
        vbox.Add(hbox_actions, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        btn_close = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.Destroy())
        vbox.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(vbox)
        accel_tbl = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, wx.WXK_PAGEDOWN, self.btn_next.GetId()),
            (wx.ACCEL_CTRL, wx.WXK_PAGEUP, self.btn_prev.GetId()),
            (wx.ACCEL_CTRL, ord('S'), self.btn_save.GetId()),
            (wx.ACCEL_ALT, ord('S'), self.btn_save.GetId()),
            (wx.ACCEL_ALT, ord('A'), self.btn_ask.GetId()),
            (wx.ACCEL_ALT, ord('R'), self.btn_gemini.GetId()),
            (wx.ACCEL_ALT, ord('G'), self.btn_tts.GetId())
        ])
        self.SetAcceleratorTable(accel_tbl)
        self.cmb_pages.SetSelection(0)
        self.update_view()
        self.txt_content.SetFocus()

    def start_auto_processing(self):
        engine = config.conf["VisionAssistant"]["ocr_engine"]
        
        if engine == 'gemini':
            threading.Thread(target=self.gemini_scan_batch_thread, daemon=True).start()
        else:
            for i in range(self.start_page, self.end_page + 1):
                self.thread_pool.submit(self.process_page_worker, i)

    def process_page_worker(self, page_num):
        if page_num in self.page_cache: return
        text = self._get_page_text_logic(page_num)
        self.page_cache[page_num] = text
        if page_num == self.current_page:
            wx.CallAfter(self.update_view)
            # Translators: Spoken message when the current page is ready
            wx.CallAfter(ui.message, _("Page {num} ready").format(num=page_num + 1))

    def _get_page_text_logic(self, page_num):
        file_path, page_idx = self.v_doc.get_page_info(page_num)
        if not file_path: return ""
        try:
            doc = fitz.open(file_path)
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_bytes = pix.tobytes("jpg")
            doc.close()
            engine = config.conf["VisionAssistant"]["ocr_engine"]
            text = None
            if engine == 'gemini':
                try: text = GeminiHandler.ocr_page(img_bytes)
                except: text = None
            if not text or not text.strip() or engine == 'chrome':
                text = ChromeOCREngine.recognize(img_bytes)
                if not text or not text.strip():
                    text = SmartProgrammersOCREngine.recognize(img_bytes)
            if not text or not text.strip():
                # Translators: Placeholder text when OCR fails
                text = _("[OCR failed. Try Gemini Re-scan.]")
            if self.do_translate and text and "[OCR failed" not in text:
                if engine == 'gemini':
                    text = GeminiHandler.translate(text, self.target_lang)
                else:
                    text = GoogleTranslator.translate(text, self.target_lang)
            return text
        except: 
            # Translators: Error message for page processing failure
            return _("Error processing page.")

    def update_view(self):
        rel_page = self.current_page - self.start_page + 1
        # Translators: Status label format
        self.lbl_status.SetLabel(_("Page {current} of {total}").format(current=rel_page, total=self.range_count))
        if self.current_page in self.page_cache:
            self.txt_content.SetValue(self.page_cache[self.current_page])
            self.txt_content.SetInsertionPoint(0)
            self.txt_content.SetFocus()
        else:
            # Translators: Status when page is loading
            self.txt_content.SetValue(_("Processing in background..."))
            self.txt_content.SetInsertionPoint(0)
            self.txt_content.SetFocus()
        self.btn_prev.Enable(self.current_page > self.start_page)
        self.btn_next.Enable(self.current_page < self.end_page)

    def load_page(self, page_num):
        if page_num < self.start_page or page_num > self.end_page: return
        self.current_page = page_num
        self.cmb_pages.SetSelection(page_num - self.start_page)
        # Translators: Spoken message when switching pages
        ui.message(_("Page {num}").format(num=page_num + 1))
        self.update_view()

    def on_prev(self, event):
        if self.current_page > self.start_page: self.load_page(self.current_page - 1)

    def on_next(self, event):
        if self.current_page < self.end_page: self.load_page(self.current_page + 1)

    def on_page_select(self, event):
        self.load_page(self.start_page + self.cmb_pages.GetSelection())

    def on_view(self, event):
        full_html = []
        for i in range(self.start_page, self.end_page + 1):
            if i in self.page_cache:
                page_text = self.page_cache[i]
                page_content = markdown_to_html(page_text, full_page=False)
                # Translators: Heading for each page in the formatted content view.
                page_label = _("Page {num}").format(num=i+1)
                full_html.append(f"<h2>{page_label}</h2>")
                full_html.append(page_content)
                full_html.append("<hr>")
        
        if not full_html:
            text = self.txt_content.GetValue()
            if not text: return
            full_html.append(markdown_to_html(text, full_page=False))
        
        combined_html = "".join(full_html)
        try:
            # Translators: Title of the formatted result window
            ui.browseableMessage(combined_html, _("Formatted Content"), isHtml=True)
        except Exception as e:
            show_error_dialog(str(e))

    def on_gemini_scan(self, event):
        if not config.conf["VisionAssistant"]["api_key"]:
            wx.MessageBox(_("Please configure Gemini API Key."), _("Error"), wx.ICON_ERROR)
            return
        menu = wx.Menu()
        # Translators: Menu option for current page
        item_curr = menu.Append(wx.ID_ANY, _("Current Page"))
        # Translators: Menu option for all pages
        item_all = menu.Append(wx.ID_ANY, _("All Pages (In Range)"))
        self.Bind(wx.EVT_MENU, self.do_rescan_current, item_curr)
        self.Bind(wx.EVT_MENU, self.do_rescan_all, item_all)
        self.PopupMenu(menu)
        menu.Destroy()

    def do_rescan_current(self, event):
        if self.current_page in self.page_cache: del self.page_cache[self.current_page]
        self.update_view()
        # Translators: Message during manual scan
        ui.message(_("Scanning with Gemini..."))
        threading.Thread(target=self.gemini_scan_single_thread, args=(self.current_page,), daemon=True).start()

    def gemini_scan_single_thread(self, page_num):
        try:
            file_path, page_idx = self.v_doc.get_page_info(page_num)
            doc = fitz.open(file_path)
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            text = GeminiHandler.ocr_page(pix.tobytes("jpg"))
            doc.close()
            if self.do_translate: text = GeminiHandler.translate(text, self.target_lang)
            self.page_cache[page_num] = text
            if self.current_page == page_num: 
                wx.CallAfter(self.update_view)
                # Translators: Message when scan is complete
                wx.CallAfter(ui.message, _("Scan complete"))
        except: pass

    def do_rescan_all(self, event):
        threading.Thread(target=self.gemini_scan_batch_thread, daemon=True).start()

    def gemini_scan_batch_thread(self):
        # Translators: Message when batch scan starts
        msg = _("Batch Processing Started")
        if _vision_assistant_instance: _vision_assistant_instance.current_status = msg
        wx.CallAfter(ui.message, msg)
        
        for i in range(self.start_page, self.end_page + 1):
            if i in self.page_cache: del self.page_cache[i]
        wx.CallAfter(self.update_view)
        
        upload_path = self.v_doc.create_merged_pdf(self.start_page, self.end_page)
        if not upload_path:
            # Translators: Error message if PDF creation fails
            wx.CallAfter(self.lbl_status.SetLabel, _("Error creating temporary PDF."))
            return

        try:
            count = (self.end_page - self.start_page) + 1
            results = GeminiHandler.upload_and_process_batch(upload_path, "application/pdf", count)
            
            if not results or (len(results) == 1 and str(results[0]).startswith("ERROR:")):
                err_msg = results[0][6:] if results else _("Unknown error")
                # Translators: Message reported when batch scan fails
                error_text = _("Scan failed: {err}").format(err=err_msg)
                for i in range(self.start_page, self.end_page + 1):
                    self.page_cache[i] = error_text
                
                wx.CallAfter(self.update_view)
                wx.CallAfter(ui.message, error_text)
                return

            for i, text_part in enumerate(results):
                if i >= count: break
                idx = self.start_page + i
                clean = text_part.strip()
                if self.do_translate:
                    clean = GeminiHandler.translate(clean, self.target_lang)
                self.page_cache[idx] = clean

            wx.CallAfter(self.update_view)
            # Translators: Message when batch scan is complete
            final_msg = _("Batch Scan Complete")
            if _vision_assistant_instance: 
                # Translators: Initial status when the add-on is doing nothing
                _vision_assistant_instance.current_status = _("Idle")
            wx.CallAfter(ui.message, final_msg)
        finally:
            if upload_path and os.path.exists(upload_path):
                try: os.remove(upload_path)
                except: pass

    def on_tts(self, event):
        if not config.conf["VisionAssistant"]["api_key"]:
            wx.MessageBox(_("Please configure Gemini API Key."), _("Error"), wx.ICON_ERROR)
            return
        menu = wx.Menu()
        # Translators: Menu option for TTS current page
        item_curr = menu.Append(wx.ID_ANY, _("Generate for Current Page"))
        # Translators: Menu option for TTS all pages
        item_all = menu.Append(wx.ID_ANY, _("Generate for All Pages (In Range)"))
        self.Bind(wx.EVT_MENU, self.do_tts_current, item_curr)
        self.Bind(wx.EVT_MENU, self.do_tts_all, item_all)
        self.PopupMenu(menu)
        menu.Destroy()

    def do_tts_current(self, event):
        text = self.txt_content.GetValue().strip()
        if not text: 
            # Translators: Error message when text field is empty
            wx.MessageBox(_("No text to read."), "Error")
            return
        self._save_tts(text)

    def do_tts_all(self, event):
        threading.Thread(target=self.tts_batch_thread, daemon=True).start()

    def tts_batch_thread(self):
        full_text = []
        # Translators: Message while gathering text
        wx.CallAfter(ui.message, _("Gathering text for audio..."))
        for i in range(self.start_page, self.end_page + 1):
            while i not in self.page_cache: time.sleep(0.1)
            full_text.append(self.page_cache[i])
        final_text = "\n".join(full_text).strip()
        if not final_text: return
        wx.CallAfter(self._save_tts, final_text)

    def _save_tts(self, text):
        # Translators: File dialog title for saving audio
        path = get_file_path(_("Save Audio"), "MP3 Files (*.mp3)|*.mp3|WAV Files (*.wav)|*.wav", mode="save")
        if path:
            voice = config.conf["VisionAssistant"]["tts_voice"]
            threading.Thread(target=self.tts_worker, args=(text, voice, path), daemon=True).start()

    def tts_worker(self, text, voice, path):
        # Translators: Message while generating audio
        msg = _("Generating Audio...")
        if _vision_assistant_instance: _vision_assistant_instance.current_status = msg
        wx.CallAfter(ui.message, msg)
        try:
            audio_b64 = GeminiHandler.generate_speech(text, voice)
            if not audio_b64 or len(audio_b64) < 100:
                 wx.CallAfter(wx.MessageBox, f"TTS Error: {audio_b64}", "Error", wx.ICON_ERROR)
                 return
            missing_padding = len(audio_b64) % 4
            if missing_padding: audio_b64 += '=' * (4 - missing_padding)
            pcm_data = base64.b64decode(audio_b64)

            if path.lower().endswith(".mp3"):
                import subprocess
                lame_path = os.path.join(os.path.dirname(__file__), "lib", "lame.exe")
                if not os.path.exists(lame_path):
                    wx.CallAfter(wx.MessageBox, _("lame.exe not found in lib folder."), "Error", wx.ICON_ERROR)
                    return
                
                process = subprocess.Popen(
                    [lame_path, "-r", "-s", "24", "-m", "m", "-b", "128", "--bitwidth", "16", "--resample", "24", "-q", "0", "-", path],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                )

                process.communicate(input=pcm_data)
            else:
                with wave.open(path, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(24000)
                    wf.writeframes(pcm_data)

            # Translators: Spoken message when audio is saved
            res_msg = _("Audio Saved")
            if _vision_assistant_instance: _vision_assistant_instance.current_status = _("Idle")
            wx.CallAfter(ui.message, res_msg)
            wx.CallAfter(wx.MessageBox, _("Audio file generated and saved successfully."), _("Success"), wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            if _vision_assistant_instance: _vision_assistant_instance.current_status = _("Idle")
            wx.CallAfter(wx.MessageBox, f"TTS Error: {e}", "Error", wx.ICON_ERROR)

    def on_ask(self, event):
        if not config.conf["VisionAssistant"]["api_key"]:
            wx.MessageBox(_("Please configure Gemini API Key."), _("Error"), wx.ICON_ERROR)
            return
        if ChatDialog.instance:
            ChatDialog.instance.Raise()
            ChatDialog.instance.SetFocus()
            return
        file_path, _ = self.v_doc.get_page_info(self.current_page)
        if file_path: 
            dlg = ChatDialog(self, file_path)
            dlg.Show()

    def on_save_all(self, event):
        # Translators: File dialog filter for saving text/html
        wildcard = "Text File (*.txt)|*.txt|HTML File (*.html)|*.html"
        # Translators: File dialog title for saving
        path = get_file_path(_("Save"), wildcard, mode="save")
        if path:
            is_html = path.lower().endswith('.html')
            self.btn_save.Disable()
            threading.Thread(target=self.save_thread, args=(path, is_html), daemon=True).start()

    def save_thread(self, path, is_html):
        full_content = []
        try:
            for i in range(self.start_page, self.end_page + 1):
                # Translators: Message showing save progress
                wx.CallAfter(self.lbl_status.SetLabel, _("Saving Page {num}...").format(num=i+1))
                while i not in self.page_cache: time.sleep(0.1)
                txt = self.page_cache[i]
                if is_html:
                    h = markdown_to_html(txt)
                    if "<body>" in h: h = h.split("<body>")[1].split("</body>")[0]
                    full_content.append(f"<hr><h2>Page {i+1}</h2>{h}")
                else:
                    full_content.append(f"--- Page {i+1} ---\n{txt}\n")
            with open(path, "w", encoding="utf-8") as f:
                if is_html: f.write(f"<html><body>{''.join(full_content)}</body></html>")
                else: f.write("\n".join(full_content))
            # Translators: Status label when save is complete
            wx.CallAfter(self.lbl_status.SetLabel, _("Saved"))
            # Translators: Message box content for successful save
            wx.CallAfter(wx.MessageBox, _("File saved successfully."), _("Success"), wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Save Error: {e}", "Error", wx.ICON_ERROR)
        finally: wx.CallAfter(self.btn_save.Enable)

