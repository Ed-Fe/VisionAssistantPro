# -*- coding: utf-8 -*-

import re


def clean_markdown(text):
    if not text:
        return ""
    text = re.sub(r'\*\*|__|[*_]', '', text)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'^\s*-\s+', '', text, flags=re.MULTILINE)
    return text.strip()


def markdown_to_html(text, full_page=False):
    if not text:
        return ""

    html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
    html = re.sub(r'__(.*?)__', r'<i>\1</i>', html)
    html = re.sub(r'^### (.*)', r'<h3>\1</h3>', html, flags=re.M)
    html = re.sub(r'^## (.*)', r'<h2>\1</h2>', html, flags=re.M)
    html = re.sub(r'^# (.*)', r'<h1>\1</h1>', html, flags=re.M)

    lines = html.split('\n')
    in_table = False
    new_lines = []
    table_style = 'border="1" style="border-collapse: collapse; width: 100%; margin-bottom: 10px;"'
    td_style = 'style="padding: 5px; border: 1px solid #ccc;"'

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') or (stripped.count('|') > 1 and len(stripped) > 5):
            if not in_table:
                new_lines.append(f'<table {table_style}>')
                in_table = True
            if '---' in stripped:
                continue
            row_content = stripped.strip('|').split('|')
            cells = "".join([f'<td {td_style}>{c.strip()}</td>' for c in row_content])
            new_lines.append(f'<tr>{cells}</tr>')
        else:
            if in_table:
                new_lines.append('</table>')
                in_table = False
            if stripped:
                new_lines.append(line + "<br>")
            else:
                new_lines.append("<br>")
    if in_table:
        new_lines.append('</table>')
    html_body = "".join(new_lines)

    if not full_page:
        return html_body
    return f"""<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><style>body{{font-family:\"Segoe UI\",Arial,sans-serif;line-height:1.6;padding:20px;color:#333;max-width:800px;margin:0 auto}}h1,h2,h3{{color:#2c3e50;border-bottom:1px solid #eee;padding-bottom:5px}}pre{{background-color:#f4f4f4;padding:10px;border-radius:5px;overflow-x:auto;font-family:Consolas,monospace}}code{{background-color:#f4f4f4;padding:2px 5px;border-radius:3px;font-family:Consolas,monospace}}table{{border-collapse:collapse;width:100%;margin-bottom:10px}}td,th{{border:1px solid #ccc;padding:8px;text-align:left}}strong,b{{color:#000;font-weight:bold}}li{{margin-bottom:5px}}</style></head><body>{html_body}</body></html>"""
