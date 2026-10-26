"""
SMS and Call Log backup exporter and modern interactive HTML viewer generator.
Exports Android telephony data to standard JSON, SMS Backup & Restore XML,
and a standalone offline HTML viewer.
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from xml.sax.saxutils import escape as xml_escape

from core.adb_manager import AdbManager

logger = logging.getLogger(__name__)


def _format_timestamp(ts_ms: Union[int, float, str]) -> str:
    """Converts millisecond or second epoch timestamp to human readable format."""
    try:
        ts = float(ts_ms)
        # If timestamp is in milliseconds (typical Android telephony)
        if ts > 100000000000:
            ts /= 1000.0
        return datetime.fromtimestamp(ts).strftime("%b %d, %Y %I:%M:%S %p")
    except Exception:
        return str(ts_ms)


def _format_duration(duration_sec: Union[int, float, str]) -> str:
    """Formats call duration in seconds to MM:SS or human string."""
    try:
        sec = int(duration_sec)
        if sec == 0:
            return "0s"
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"
    except Exception:
        return f"{duration_sec}s"


def _clean_xml_attr(val: Any) -> str:
    """Safely escapes text for XML attribute values, protecting quotes and invalid XML characters."""
    s = str(val if val is not None else "")
    # Remove ASCII control characters invalid in XML 1.0
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s)
    return xml_escape(s, entities={'"': "&quot;", "'": "&apos;"})


class SmsExporter:
    """Exports SMS messages and Call logs from Android device via content provider queries."""

    SMS_URI = "content://sms"
    SMS_PROJECTION = "_id:thread_id:address:person:date:type:body:read:status"

    CALL_URI = "content://call_log/calls"
    CALL_PROJECTION = "_id:number:date:duration:type:name"

    def __init__(self, adb_manager: Optional[AdbManager] = None) -> None:
        self.adb = adb_manager or AdbManager()

    def export_sms_and_calls(
        self,
        serial: str,
        output_dir: Union[str, Path],
    ) -> Dict[str, Any]:
        """
        Queries Android telephony content providers, parses records, and writes:
        - sms_backup.json
        - call_log_backup.json
        - sms_backup.xml (SMS Backup & Restore compatible)
        - calls_backup.xml
        - sms_viewer.html (Offline responsive chat & call log viewer)

        Args:
            serial: Device serial.
            output_dir: Destination directory on PC.

        Returns:
            Dictionary with export statistics and file paths.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # 1. Query SMS
        sms_cmd = f"content query --uri {self.SMS_URI} --projection {self.SMS_PROJECTION}"
        sms_raw = self.adb.run_shell(serial, sms_cmd, timeout=60)
        messages = self.parse_sms_query(sms_raw)

        # 2. Query Call Logs
        call_cmd = f"content query --uri {self.CALL_URI} --projection {self.CALL_PROJECTION}"
        call_raw = self.adb.run_shell(serial, call_cmd, timeout=60)
        calls = self.parse_call_query(call_raw)

        # 3. Save JSON backups
        sms_json_path = out_path / "sms_backup.json"
        with open(sms_json_path, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)

        call_json_path = out_path / "call_log_backup.json"
        with open(call_json_path, "w", encoding="utf-8") as f:
            json.dump(calls, f, indent=2, ensure_ascii=False)

        # 4. Generate XML backups (SMS Backup & Restore compatible)
        sms_xml_path = out_path / "sms_backup.xml"
        self.generate_sms_xml(messages, sms_xml_path)

        calls_xml_path = out_path / "calls_backup.xml"
        self.generate_calls_xml(calls, calls_xml_path)

        # 5. Generate Standalone Interactive HTML Viewer
        html_path = out_path / "sms_viewer.html"
        self.generate_html_viewer(messages, calls, html_path)

        return {
            "sms_count": len(messages),
            "call_count": len(calls),
            "sms_json": str(sms_json_path),
            "call_json": str(call_json_path),
            "sms_xml": str(sms_xml_path),
            "calls_xml": str(calls_xml_path),
            "viewer_html": str(html_path),
        }

    @classmethod
    def parse_sms_query(cls, raw_output: str) -> List[Dict[str, Any]]:
        """
        Parses `content query --uri content://sms` output.
        Handles multiline bodies, embedded commas, null values, and special characters.
        """
        if not raw_output or "Row: " not in raw_output:
            return []

        rows: List[Dict[str, Any]] = []

        # Split output into Row chunks
        # Each row begins with "Row: <digits> "
        row_chunks = re.split(r"(?m)^Row:\s*\d+\s+", raw_output)

        for chunk in row_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # Standard projection keys
            # _id, thread_id, address, person, date, type, body, read, status
            # Extract body by known surrounding boundaries
            # Pattern: _id=..., thread_id=..., address=..., person=..., date=..., type=..., body=... , read=..., status=...
            m_body = re.search(
                r"_id=(?P<_id>[^,]+),\s*"
                r"thread_id=(?P<thread_id>[^,]+),\s*"
                r"address=(?P<address>[^,]+),\s*"
                r"person=(?P<person>[^,]+),\s*"
                r"date=(?P<date>[^,]+),\s*"
                r"type=(?P<type>[^,]+),\s*"
                r"body=(?P<body>.*?),\s*"
                r"read=(?P<read>[^,]+),\s*"
                r"status=(?P<status>[^,\r\n]+)",
                chunk,
                re.DOTALL,
            )

            if m_body:
                def clean(v: str) -> Optional[str]:
                    v = v.strip()
                    return None if v == "null" else v

                date_val = clean(m_body.group("date"))
                date_int = int(date_val) if date_val and date_val.isdigit() else 0

                type_val = clean(m_body.group("type"))
                type_int = int(type_val) if type_val and type_val.isdigit() else 1

                read_val = clean(m_body.group("read"))
                read_int = int(read_val) if read_val and read_val.isdigit() else 1

                record = {
                    "_id": clean(m_body.group("_id")),
                    "thread_id": clean(m_body.group("thread_id")),
                    "address": clean(m_body.group("address")) or "Unknown",
                    "person": clean(m_body.group("person")),
                    "date": date_int,
                    "readable_date": _format_timestamp(date_int),
                    "type": type_int,  # 1 = Received, 2 = Sent
                    "body": m_body.group("body"),
                    "read": read_int,
                    "status": clean(m_body.group("status")) or "-1",
                }
                rows.append(record)
            else:
                # Fallback simple key-value parser for lines
                entry: Dict[str, Any] = {}
                for part in re.split(r",\s*(?=[a-zA-Z_]+[=])", chunk):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        entry[k] = None if v == "null" else v
                if entry and "_id" in entry:
                    try:
                        entry["date"] = int(entry.get("date") or 0)
                        entry["type"] = int(entry.get("type") or 1)
                    except ValueError:
                        pass
                    entry["readable_date"] = _format_timestamp(entry.get("date", 0))
                    rows.append(entry)

        return rows

    @classmethod
    def parse_call_query(cls, raw_output: str) -> List[Dict[str, Any]]:
        """
        Parses `content query --uri content://call_log/calls` output.
        """
        if not raw_output or "Row: " not in raw_output:
            return []

        rows: List[Dict[str, Any]] = []
        row_chunks = re.split(r"(?m)^Row:\s*\d+\s+", raw_output)

        for chunk in row_chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # _id, number, date, duration, type, name
            m = re.search(
                r"_id=(?P<_id>[^,]+),\s*"
                r"number=(?P<number>[^,]+),\s*"
                r"date=(?P<date>[^,]+),\s*"
                r"duration=(?P<duration>[^,]+),\s*"
                r"type=(?P<type>[^,]+),\s*"
                r"name=(?P<name>.*)",
                chunk,
                re.DOTALL,
            )

            if m:
                def clean(v: str) -> Optional[str]:
                    v = v.strip()
                    return None if v == "null" else v

                date_val = clean(m.group("date"))
                date_int = int(date_val) if date_val and date_val.isdigit() else 0

                duration_val = clean(m.group("duration"))
                duration_int = int(duration_val) if duration_val and duration_val.isdigit() else 0

                type_val = clean(m.group("type"))
                type_int = int(type_val) if type_val and type_val.isdigit() else 1

                rows.append({
                    "_id": clean(m.group("_id")),
                    "number": clean(m.group("number")) or "Unknown",
                    "date": date_int,
                    "readable_date": _format_timestamp(date_int),
                    "duration": duration_int,
                    "duration_formatted": _format_duration(duration_int),
                    "type": type_int,  # 1=Incoming, 2=Outgoing, 3=Missed, 5=Rejected
                    "name": clean(m.group("name")) or "Unknown",
                })

        return rows

    @classmethod
    def generate_sms_xml(cls, messages: List[Dict[str, Any]], output_file: Union[str, Path]) -> None:
        """
        Generates standard XML backup file compatible with SMS Backup & Restore.
        """
        lines = [
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>",
            "<!-- File Created By Kinetix Engine -->",
            f'<smses count="{len(messages)}" backup_set="{datetime.now().isoformat()}" backup_date="{int(datetime.now().timestamp() * 1000)}">',
        ]

        for m in messages:
            address = _clean_xml_attr(m.get("address", "") or "Unknown")
            date = _clean_xml_attr(m.get("date", "0"))
            mtype = _clean_xml_attr(m.get("type", "1"))
            body = _clean_xml_attr(m.get("body", "") or "")
            read = _clean_xml_attr(m.get("read", "1"))
            status = _clean_xml_attr(m.get("status", "-1"))
            readable_date = _clean_xml_attr(m.get("readable_date", ""))
            contact_name = _clean_xml_attr(m.get("person", "") or "(Unknown)")

            line = (
                f'  <sms protocol="0" address="{address}" date="{date}" type="{mtype}" '
                f'subject="null" body="{body}" toa="null" sc_toa="null" service_center="null" '
                f'read="{read}" status="{status}" locked="0" date_sent="0" '
                f'readable_date="{readable_date}" contact_name="{contact_name}" />'
            )
            lines.append(line)

        lines.append("</smses>")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    @classmethod
    def generate_calls_xml(cls, calls: List[Dict[str, Any]], output_file: Union[str, Path]) -> None:
        """Generates standard Call Log XML backup file."""
        lines = [
            "<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>",
            "<!-- File Created By Kinetix Engine -->",
            f'<calls count="{len(calls)}">',
        ]

        for c in calls:
            number = _clean_xml_attr(c.get("number", "") or "Unknown")
            duration = _clean_xml_attr(c.get("duration", "0"))
            date = _clean_xml_attr(c.get("date", "0"))
            mtype = _clean_xml_attr(c.get("type", "1"))
            readable_date = _clean_xml_attr(c.get("readable_date", ""))
            contact_name = _clean_xml_attr(c.get("name", "") or "Unknown")

            line = (
                f'  <call number="{number}" duration="{duration}" date="{date}" '
                f'type="{mtype}" readable_date="{readable_date}" contact_name="{contact_name}" />'
            )
            lines.append(line)

        lines.append("</calls>")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    @classmethod
    def generate_html_viewer(
        cls,
        messages: List[Dict[str, Any]],
        calls: List[Dict[str, Any]],
        output_file: Union[str, Path],
    ) -> None:
        """
        Generates a sleek, fully responsive, standalone HTML5/CSS3/Vanilla JS viewer.
        No external CDN dependencies needed. Works 100% offline.
        Features search, conversation thread grouping, chat bubbles, and call logs.
        """
        sms_json_str = json.dumps(messages, ensure_ascii=False)
        call_json_str = json.dumps(calls, ensure_ascii=False)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MobilePCSync Telephony Archive</title>
<style>
  :root {{
    --bg-main: #0f172a;
    --bg-card: #1e293b;
    --bg-card-hover: #334155;
    --border: #334155;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --accent: #3b82f6;
    --accent-glow: rgba(59, 130, 246, 0.25);
    --bubble-in: #334155;
    --bubble-out: #2563eb;
    --tag-incoming: #10b981;
    --tag-outgoing: #3b82f6;
    --tag-missed: #ef4444;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg-main);
    color: var(--text-primary);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}

  header {{
    background: #020617;
    border-bottom: 1px solid var(--border);
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .header-brand {{
    display: flex;
    align-items: center;
    gap: 12px;
  }}

  .header-brand h1 {{
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #fff;
  }}

  .badge {{
    background: var(--accent);
    color: #fff;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
  }}

  .nav-tabs {{
    display: flex;
    gap: 8px;
  }}

  .nav-tab {{
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-secondary);
    padding: 6px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.875rem;
    font-weight: 500;
    transition: all 0.15s ease;
  }}

  .nav-tab.active {{
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    box-shadow: 0 0 12px var(--accent-glow);
  }}

  .main-container {{
    flex: 1;
    display: flex;
    overflow: hidden;
  }}

  /* Messages layout */
  .sidebar {{
    width: 360px;
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    background: #090d16;
  }}

  .search-box {{
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }}

  .search-box input {{
    width: 100%;
    background: #1e293b;
    border: 1px solid var(--border);
    color: #fff;
    padding: 8px 12px;
    border-radius: 6px;
    outline: none;
    font-size: 0.875rem;
  }}

  .search-box input:focus {{
    border-color: var(--accent);
  }}

  .threads-list {{
    flex: 1;
    overflow-y: auto;
  }}

  .thread-item {{
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    cursor: pointer;
    display: flex;
    gap: 12px;
    align-items: center;
    transition: background 0.15s ease;
  }}

  .thread-item:hover {{
    background: #172033;
  }}

  .thread-item.active {{
    background: #1e293b;
    border-left: 3px solid var(--accent);
  }}

  .avatar {{
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.95rem;
    color: #fff;
    flex-shrink: 0;
  }}

  .thread-info {{
    flex: 1;
    min-width: 0;
  }}

  .thread-header {{
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
  }}

  .thread-name {{
    font-weight: 600;
    font-size: 0.9rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .thread-time {{
    font-size: 0.72rem;
    color: var(--text-secondary);
    flex-shrink: 0;
  }}

  .thread-snippet {{
    font-size: 0.8rem;
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}

  .chat-pane {{
    flex: 1;
    display: flex;
    flex-direction: column;
    background: var(--bg-main);
  }}

  .chat-header {{
    padding: 12px 20px;
    background: #020617;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}

  .chat-header-title {{
    font-weight: 700;
    font-size: 1.05rem;
  }}

  .chat-header-sub {{
    font-size: 0.8rem;
    color: var(--text-secondary);
  }}

  .messages-stream {{
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}

  .msg-row {{
    display: flex;
    flex-direction: column;
    max-width: 68%;
  }}

  .msg-row.received {{
    align-self: flex-start;
  }}

  .msg-row.sent {{
    align-self: flex-end;
  }}

  .bubble {{
    padding: 10px 14px;
    border-radius: 14px;
    font-size: 0.9rem;
    line-height: 1.45;
    word-break: break-word;
    white-space: pre-wrap;
  }}

  .msg-row.received .bubble {{
    background: var(--bubble-in);
    color: #f1f5f9;
    border-bottom-left-radius: 2px;
  }}

  .msg-row.sent .bubble {{
    background: var(--bubble-out);
    color: #fff;
    border-bottom-right-radius: 2px;
  }}

  .msg-meta {{
    font-size: 0.7rem;
    color: var(--text-secondary);
    margin-top: 4px;
    display: flex;
    gap: 6px;
  }}

  .msg-row.sent .msg-meta {{
    justify-content: flex-end;
  }}

  /* Call logs view */
  .call-view {{
    flex: 1;
    display: none;
    flex-direction: column;
    padding: 24px;
    overflow-y: auto;
  }}

  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
  }}

  .stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 16px;
    border-radius: 10px;
  }}

  .stat-card .label {{
    font-size: 0.78rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-weight: 600;
  }}

  .stat-card .value {{
    font-size: 1.5rem;
    font-weight: 700;
    margin-top: 4px;
  }}

  .call-table-wrap {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }}

  th {{
    text-align: left;
    padding: 12px 16px;
    background: #0f172a;
    border-bottom: 1px solid var(--border);
    font-weight: 600;
    color: var(--text-secondary);
  }}

  td {{
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }}

  tr:hover td {{
    background: #27354a;
  }}

  .tag {{
    display: inline-block;
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 0.75rem;
    font-weight: 600;
  }}

  .tag.incoming {{ background: rgba(16, 185, 129, 0.2); color: var(--tag-incoming); }}
  .tag.outgoing {{ background: rgba(59, 130, 246, 0.2); color: var(--tag-outgoing); }}
  .tag.missed {{ background: rgba(239, 68, 68, 0.2); color: var(--tag-missed); }}

  .empty-state {{
    margin: auto;
    text-align: center;
    color: var(--text-secondary);
  }}
</style>
</head>
<body>

<header>
  <div class="header-brand">
    <h1>MobilePCSync Archive</h1>
    <span class="badge" id="totalBadge">0 Items</span>
  </div>
  <div class="nav-tabs">
    <button class="nav-tab active" id="tabMsgBtn" onclick="switchTab('messages')">Messages</button>
    <button class="nav-tab" id="tabCallBtn" onclick="switchTab('calls')">Call Logs</button>
  </div>
</header>

<div class="main-container">
  <!-- Messages Section -->
  <div class="main-container" id="msgSection">
    <div class="sidebar">
      <div class="search-box">
        <input type="text" id="searchInput" placeholder="Search contacts or messages..." oninput="filterThreads()">
      </div>
      <div class="threads-list" id="threadsContainer"></div>
    </div>
    <div class="chat-pane" id="chatPane">
      <div class="empty-state">Select a conversation from the sidebar</div>
    </div>
  </div>

  <!-- Call Logs Section -->
  <div class="call-view" id="callSection">
    <div class="stats-grid" id="statsGrid"></div>
    <div class="call-table-wrap">
      <table>
        <thead>
          <tr>
            <th>Type</th>
            <th>Contact / Number</th>
            <th>Duration</th>
            <th>Date & Time</th>
          </tr>
        </thead>
        <tbody id="callTableBody"></tbody>
      </table>
    </div>
  </div>
</div>

<script id="sms-data" type="application/json">{sms_json_str}</script>
<script id="call-data" type="application/json">{call_json_str}</script>

<script>
  let allMessages = [];
  let allCalls = [];
  let threads = {{}};
  let activeThreadId = null;

  try {{
    allMessages = JSON.parse(document.getElementById('sms-data').textContent || '[]');
    allCalls = JSON.parse(document.getElementById('call-data').textContent || '[]');
  }} catch (e) {{
    console.error('Error parsing data:', e);
  }}

  document.getElementById('totalBadge').innerText =
    `${{allMessages.length}} Messages | ${{allCalls.length}} Calls`;

  function initThreads() {{
    threads = {{}};
    allMessages.forEach(msg => {{
      const key = msg.address || 'Unknown';
      if (!threads[key]) {{
        threads[key] = {{
          address: key,
          name: msg.person || key,
          messages: [],
          lastTime: 0
        }};
      }}
      threads[key].messages.push(msg);
      if (msg.date > threads[key].lastTime) {{
        threads[key].lastTime = msg.date;
      }}
    }});

    // Sort messages in each thread chronologically
    Object.values(threads).forEach(t => {{
      t.messages.sort((a, b) => a.date - b.date);
    }});

    renderThreadsList();
    const firstKey = Object.keys(threads)[0];
    if (firstKey) {{
      selectThread(firstKey);
    }}
  }}

  function renderThreadsList(filter = '') {{
    const container = document.getElementById('threadsContainer');
    container.innerHTML = '';
    const q = filter.toLowerCase();

    const sorted = Object.values(threads).sort((a, b) => b.lastTime - a.lastTime);

    sorted.forEach(t => {{
      const lastMsg = t.messages[t.messages.length - 1];
      const matchName = t.name.toLowerCase().includes(q) || t.address.toLowerCase().includes(q);
      const matchBody = t.messages.some(m => (m.body || '').toLowerCase().includes(q));

      if (q && !matchName && !matchBody) return;

      const item = document.createElement('div');
      item.className = 'thread-item' + (t.address === activeThreadId ? ' active' : '');
      item.onclick = () => selectThread(t.address);

      const initials = (t.name || t.address || '?').substring(0, 2).toUpperCase();
      const lastBody = lastMsg ? (lastMsg.body || '') : '';
      const dateStr = lastMsg ? lastMsg.readable_date.split(' ')[0] : '';

      item.innerHTML = `
        <div class="avatar">${{initials}}</div>
        <div class="thread-info">
          <div class="thread-header">
            <span class="thread-name">${{escapeHtml(t.name)}}</span>
            <span class="thread-time">${{escapeHtml(dateStr)}}</span>
          </div>
          <div class="thread-snippet">${{escapeHtml(lastBody)}}</div>
        </div>
      `;
      container.appendChild(item);
    }});
  }}

  function selectThread(address) {{
    activeThreadId = address;
    renderThreadsList(document.getElementById('searchInput').value);

    const thread = threads[address];
    const pane = document.getElementById('chatPane');
    if (!thread) return;

    pane.innerHTML = `
      <div class="chat-header">
        <div>
          <div class="chat-header-title">${{escapeHtml(thread.name)}}</div>
          <div class="chat-header-sub">${{escapeHtml(thread.address)}} · ${{thread.messages.length}} messages</div>
        </div>
      </div>
      <div class="messages-stream" id="msgStream"></div>
    `;

    const stream = document.getElementById('msgStream');
    thread.messages.forEach(m => {{
      const isSent = (m.type == 2);
      const row = document.createElement('div');
      row.className = 'msg-row ' + (isSent ? 'sent' : 'received');
      row.innerHTML = `
        <div class="bubble">${{escapeHtml(m.body || '')}}</div>
        <div class="msg-meta">
          <span>${{escapeHtml(m.readable_date)}}</span>
          ${{isSent ? '<span>✓</span>' : ''}}
        </div>
      `;
      stream.appendChild(row);
    }});

    stream.scrollTop = stream.scrollHeight;
  }}

  function filterThreads() {{
    const q = document.getElementById('searchInput').value;
    renderThreadsList(q);
  }}

  function initCalls() {{
    const grid = document.getElementById('statsGrid');
    const incoming = allCalls.filter(c => c.type == 1).length;
    const outgoing = allCalls.filter(c => c.type == 2).length;
    const missed = allCalls.filter(c => c.type == 3 || c.type == 5).length;
    const totalSec = allCalls.reduce((acc, c) => acc + (c.duration || 0), 0);

    grid.innerHTML = `
      <div class="stat-card"><div class="label">Total Calls</div><div class="value">${{allCalls.length}}</div></div>
      <div class="stat-card"><div class="label">Incoming</div><div class="value" style="color:var(--tag-incoming)">${{incoming}}</div></div>
      <div class="stat-card"><div class="label">Outgoing</div><div class="value" style="color:var(--tag-outgoing)">${{outgoing}}</div></div>
      <div class="stat-card"><div class="label">Missed</div><div class="value" style="color:var(--tag-missed)">${{missed}}</div></div>
    `;

    const tbody = document.getElementById('callTableBody');
    tbody.innerHTML = '';
    allCalls.forEach(c => {{
      const tr = document.createElement('tr');
      let tagClass = 'incoming';
      let tagLabel = 'Incoming';
      if (c.type == 2) {{ tagClass = 'outgoing'; tagLabel = 'Outgoing'; }}
      else if (c.type == 3 || c.type == 5) {{ tagClass = 'missed'; tagLabel = 'Missed'; }}

      tr.innerHTML = `
        <td><span class="tag ${{tagClass}}">${{tagLabel}}</span></td>
        <td><strong>${{escapeHtml(c.name || c.number)}}</strong><br><span style="font-size:0.75rem;color:var(--text-secondary)">${{escapeHtml(c.number)}}</span></td>
        <td>${{escapeHtml(c.duration_formatted || c.duration + 's')}}</td>
        <td>${{escapeHtml(c.readable_date)}}</td>
      `;
      tbody.appendChild(tr);
    }});
  }}

  function switchTab(tab) {{
    document.getElementById('tabMsgBtn').className = 'nav-tab' + (tab === 'messages' ? ' active' : '');
    document.getElementById('tabCallBtn').className = 'nav-tab' + (tab === 'calls' ? ' active' : '');

    document.getElementById('msgSection').style.display = (tab === 'messages' ? 'flex' : 'none');
    document.getElementById('callSection').style.display = (tab === 'calls' ? 'flex' : 'none');
  }}

  function escapeHtml(str) {{
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }}

  initThreads();
  initCalls();
</script>
</body>
</html>"""

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
