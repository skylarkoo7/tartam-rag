from __future__ import annotations

import argparse
import html
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate multilingual Tartam chat validation report.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000/api", help="Backend API base URL")
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Output directory relative to backend folder",
    )
    parser.add_argument(
        "--chrome-bin",
        default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        help="Chrome binary path for PDF generation",
    )
    return parser.parse_args()


def _ask(client: httpx.Client, api_base: str, *, session_id: str, message: str, style_mode: str = "auto") -> dict[str, Any]:
    response = client.post(
        f"{api_base}/chat",
        json={
            "session_id": session_id,
            "message": message,
            "style_mode": style_mode,
            "top_k": 6,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


def _citation_lines(payload: dict[str, Any]) -> list[str]:
    citations = payload.get("citations", []) or []
    lines: list[str] = []
    for item in citations[:3]:
        granth = str(item.get("granth_name", ""))
        prakran = str(item.get("prakran_name", ""))
        page = item.get("page_number")
        lines.append(f"{granth} | {prakran} | p.{page}")
    return lines


def _build_markdown(results: list[dict[str, Any]]) -> str:
    stamp = datetime.now().isoformat(timespec="seconds")
    parts: list[str] = []
    parts.append("# Tartam RAG Multilingual Live Validation")
    parts.append(f"Generated at: `{stamp}`")
    parts.append("")

    for idx, item in enumerate(results, start=1):
        parts.append(f"## {idx}. {item['label']}")
        parts.append(f"- Query: `{item['question']}`")
        parts.append(f"- Session: `{item['session_id']}`")
        parts.append(f"- Answer Style: `{item['answer_style']}`")
        parts.append(f"- Not Found: `{item['not_found']}`")
        parts.append("")
        parts.append("### Answer")
        parts.append(item["answer"])
        parts.append("")
        citations = item.get("citations") or []
        if citations:
            parts.append("### Top Citations")
            for line in citations:
                parts.append(f"- {line}")
        else:
            parts.append("### Top Citations")
            parts.append("- None")
        parts.append("")

    return "\n".join(parts).strip() + "\n"


def _build_html(markdown_text: str, results: list[dict[str, Any]]) -> str:
    escaped_md = html.escape(markdown_text)

    cards: list[str] = []
    for item in results:
        citation_items = "".join(
            f"<li>{html.escape(line)}</li>" for line in (item.get("citations") or ["None"])
        )
        cards.append(
            "".join(
                [
                    "<section class='card'>",
                    f"<h2>{html.escape(item['label'])}</h2>",
                    f"<p><strong>Query:</strong> {html.escape(item['question'])}</p>",
                    f"<p><strong>Answer style:</strong> {html.escape(item['answer_style'])}</p>",
                    f"<p><strong>Not found:</strong> {str(item['not_found']).lower()}</p>",
                    "<h3>Answer</h3>",
                    f"<pre>{html.escape(item['answer'])}</pre>",
                    "<h3>Top citations</h3>",
                    f"<ul>{citation_items}</ul>",
                    "</section>",
                ]
            )
        )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Tartam Multilingual Validation</title>
  <style>
    :root {
      --bg: #fff7ef;
      --panel: #fff0e0;
      --ink: #5e3a21;
      --muted: #8a6348;
      --accent: #c9732f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 24px;
      font-family: "Noto Sans", "Noto Sans Devanagari", "Noto Sans Gujarati", "Kohinoor Devanagari", "Gujarati Sangam MN", sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.55;
    }
    h1 { margin: 0 0 8px; }
    .meta { color: var(--muted); margin-bottom: 16px; }
    .grid { display: grid; grid-template-columns: 1fr; gap: 14px; }
    .card {
      background: var(--panel);
      border: 1px solid #efc8a8;
      border-radius: 12px;
      padding: 14px;
      page-break-inside: avoid;
    }
    h2 { margin: 0 0 8px; color: var(--accent); font-size: 20px; }
    h3 { margin: 12px 0 6px; font-size: 16px; }
    p { margin: 4px 0; }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #fff8f1;
      border: 1px solid #edd4bd;
      border-radius: 8px;
      padding: 10px;
      margin: 0;
      font-family: inherit;
    }
    ul { margin: 0; padding-left: 20px; }
    .raw {
      margin-top: 20px;
      border-top: 1px dashed #dca57b;
      padding-top: 12px;
    }
  </style>
</head>
<body>
  <h1>Tartam RAG Multilingual Live Validation</h1>
  <div class="meta">Generated at: """ + html.escape(datetime.now().isoformat(timespec="seconds")) + """</div>
  <div class="grid">
    """ + "\n".join(cards) + """
  </div>
  <div class="raw">
    <h2>Raw Markdown Snapshot</h2>
    <pre>""" + escaped_md + """</pre>
  </div>
</body>
</html>
"""


def _render_pdf_with_chrome(chrome_bin: Path, html_path: Path, pdf_path: Path) -> str | None:
    if not chrome_bin.exists():
        return f"Chrome binary not found at {chrome_bin}"

    cmd = [
        str(chrome_bin),
        "--headless=new",
        "--disable-gpu",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return None
    except subprocess.CalledProcessError as exc:
        output = (exc.stderr or exc.stdout or b"").decode("utf-8", errors="ignore")
        return output[:500] or "Unknown Chrome PDF error"


def main() -> None:
    args = parse_args()

    checks = [
        {
            "label": "English",
            "session_base": "report-en",
            "question": "In ShriSingaar prakran 14, what is taught about hukam?",
        },
        {
            "label": "Hindi",
            "session_base": "report-hi",
            "question": "ShriSingaar ग्रंथ के प्रकरण 14 में हुकम के बारे में क्या बताया है?",
        },
        {
            "label": "Gujarati",
            "session_base": "report-gu",
            "question": "શ્રીસિંગાર ગ્રંથના પ્રકરણ 14 માં હુકમ વિશે શું સમજાવ્યું છે?",
        },
        {
            "label": "Hindi (Roman)",
            "session_base": "report-hi-latn",
            "question": "Shrisingaar granth ke prakran 14 me hukam ke baare me kya bataya hai?",
        },
        {
            "label": "Gujarati (Roman)",
            "session_base": "report-gu-latn",
            "question": "Shrisingaar granth na prakran 14 ma hukam vishe shu kahyu che?",
        },
    ]

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_tag = datetime.now().strftime("%Y%m%d%H%M%S")

    results: list[dict[str, Any]] = []
    with httpx.Client() as client:
        health = client.get(f"{args.api_base}/health", timeout=20.0)
        health.raise_for_status()
        health_payload = health.json()
        print("health:", json.dumps(health_payload, ensure_ascii=False))

        for item in checks:
            session_id = f"{item['session_base']}-{run_tag}"
            response = _ask(
                client,
                args.api_base,
                session_id=session_id,
                message=item["question"],
                style_mode="auto",
            )
            results.append(
                {
                    "label": item["label"],
                    "session_id": session_id,
                    "question": item["question"],
                    "answer": response.get("answer", ""),
                    "answer_style": response.get("answer_style", ""),
                    "not_found": bool(response.get("not_found", False)),
                    "citations": _citation_lines(response),
                    "raw": response,
                }
            )

    markdown_text = _build_markdown(results)
    markdown_path = output_dir / "multilingual_chat_validation.md"
    markdown_path.write_text(markdown_text, encoding="utf-8")

    html_text = _build_html(markdown_text, results)
    html_path = output_dir / "multilingual_chat_validation.html"
    html_path.write_text(html_text, encoding="utf-8")

    pdf_path = output_dir / "multilingual_chat_validation.pdf"
    pdf_error = _render_pdf_with_chrome(Path(args.chrome_bin), html_path, pdf_path)

    json_path = output_dir / "multilingual_chat_validation.json"
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"markdown={markdown_path}")
    print(f"html={html_path}")
    print(f"json={json_path}")
    if pdf_error:
        print(f"pdf_error={pdf_error}")
    else:
        print(f"pdf={pdf_path}")


if __name__ == "__main__":
    main()
