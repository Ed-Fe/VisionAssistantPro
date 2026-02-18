# -*- coding: utf-8 -*-

import json
import threading
import logging
import os
import re
import tempfile

import wx
from urllib import request

import addonHandler
import gui
import ui
from .constants import ADDON_NAME
from .markdown_utils import clean_markdown
from .services import show_error_dialog

log = logging.getLogger(__name__)
addonHandler.initTranslation()

class UpdateDialog(wx.Dialog):
    def __init__(self, parent, version, name, changes):
        # Translators: Title of update confirmation dialog
        super().__init__(parent, title=_("Update Available"), size=(500, 450))
        self.Centre()
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Translators: Message asking user to update. {version} is version number.
        msg = _("A new version ({version}) of {name} is available.").format(version=version, name=name)
        header = wx.StaticText(panel, label=msg)
        vbox.Add(header, 0, wx.ALL, 15)
        
        # Translators: Label for the changes text box
        change_lbl = wx.StaticText(panel, label=_("Changes:"))
        vbox.Add(change_lbl, 0, wx.LEFT | wx.RIGHT, 15)
        
        self.changes_ctrl = wx.TextCtrl(panel, value=changes, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        vbox.Add(self.changes_ctrl, 1, wx.EXPAND | wx.ALL, 15)
        
        # Translators: Question to download and install
        question = wx.StaticText(panel, label=_("Download and Install?"))
        vbox.Add(question, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Button to accept update
        self.yes_btn = wx.Button(panel, wx.ID_YES, label=_("&Yes"))
        # Translators: Button to reject update
        self.no_btn = wx.Button(panel, wx.ID_NO, label=_("&No"))
        
        btn_sizer.Add(self.yes_btn, 0, wx.RIGHT, 10)
        btn_sizer.Add(self.no_btn, 0)
        vbox.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 15)
        
        panel.SetSizer(vbox)
        self.yes_btn.SetDefault()
        self.yes_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES))
        self.no_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_NO))

class UpdateManager:
    def __init__(self, repo_name):
        self.repo_name = repo_name
        self.current_version = addonHandler.getCodeAddon().manifest['version']

    def check_for_updates(self, silent=True):
        threading.Thread(target=self._check_thread, args=(silent,), daemon=True).start()

    def _check_thread(self, silent):
        try:
            url = f"https://api.github.com/repos/{self.repo_name}/releases/latest"
            req = request.Request(url, headers={"User-Agent": "NVDA-Addon"})
            with request.urlopen(req, timeout=60) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    latest_tag = data.get("tag_name", "").lstrip("v")
                    if self._compare_versions(latest_tag, self.current_version) > 0:
                        download_url = None
                        for asset in data.get("assets", []):
                            if asset["name"].endswith(".nvda-addon"):
                                download_url = asset["browser_download_url"]
                                break
                        if download_url:
                            raw_changes = data.get("body", "")
                            
                            clean_changes = re.split(r'SHA256|Checklist|---', raw_changes, flags=re.I)[0].strip()
                            clean_changes = clean_markdown(clean_changes)
                            
                            wx.CallAfter(self._prompt_update, latest_tag, download_url, clean_changes)
                        elif not silent:
                            # Translators: Error message when an update is found but the addon file is missing from GitHub.
                            msg = _("Update found but no .nvda-addon file in release.")
                            show_error_dialog(msg)
                    elif not silent:
                        # Translators: Status message informing the user they are already on the latest version.
                        msg = _("You have the latest version.")
                        wx.CallAfter(ui.message, msg)
        except Exception as e:
            if not silent:
                msg = _("Update check failed: {error}").format(error=e)
                show_error_dialog(msg)

    def _compare_versions(self, v1, v2):
        try:
            parts1 = [int(x) for x in v1.split('.')]
            parts2 = [int(x) for x in v2.split('.')]
            return (parts1 > parts2) - (parts1 < parts2)
        except Exception:
            return 0 if v1 == v2 else 1

    def _prompt_update(self, version, url, changes):
        dlg = UpdateDialog(gui.mainFrame, version, ADDON_NAME, changes)
        if dlg.ShowModal() == wx.ID_YES:
            threading.Thread(target=self._download_install_worker, args=(url,), daemon=True).start()
        dlg.Destroy()

    def _download_install_worker(self, url):
        try:
            # Translators: Message shown while downloading update
            msg = _("Downloading update...")
            wx.CallAfter(ui.message, msg)
            temp_dir = tempfile.gettempdir()
            file_path = os.path.join(temp_dir, "VisionAssistant_Update.nvda-addon")
            with request.urlopen(url) as response, open(file_path, 'wb') as out_file:
                out_file.write(response.read())
            wx.CallAfter(os.startfile, file_path)
        except Exception as e:
            # Translators: Error message for download failure
            msg = _("Download failed: {error}").format(error=e)
            show_error_dialog(msg)

# --- UI Classes ---
