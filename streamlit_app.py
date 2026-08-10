"""Small Streamlit client for the hosted layout API."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import streamlit as st

from core.config import AppConfig


def api_request(
    base_url: str,
    api_key: str,
    path: str,
    payload: dict | None = None,
    timeout: int = 900,
) -> tuple[int, dict]:
    """Send one JSON request and preserve structured HTTP error responses."""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("API URL must be a valid http:// or https:// address.")

    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}/{path.lstrip('/')}",
        data=data,
        method="POST" if payload is not None else "GET",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status, raw = response.status, response.read()
    except HTTPError as error:
        status, raw = error.code, error.read()
    except (URLError, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise RuntimeError(f"Could not reach the API: {reason}") from error

    try:
        body = json.loads(raw) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"API returned invalid JSON (HTTP {status}).") from error
    if not isinstance(body, dict):
        raise RuntimeError(f"API returned an unexpected response (HTTP {status}).")
    return status, body


def _clear_run() -> None:
    for key in ("request_id", "answers", "missing_fields", "result", "active_request"):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith("answer_"):
            del st.session_state[key]


def _error_message(status: int, body: dict) -> str:
    detail = body.get("detail") or body.get("error") or "Unexpected API response"
    return f"HTTP {status}: {detail}"


def _submit(answers: dict[str, str | None]) -> None:
    active = st.session_state["active_request"]
    payload = {
        "request_id": st.session_state.get("request_id"),
        "prompt": active["prompt"],
        "template_id": active["template_id"],
        "answers": answers,
        "publish": active["publish"],
    }
    try:
        with st.spinner("Generating and validating the layout..."):
            status, body = api_request(
                st.session_state["api_url"],
                st.session_state["api_key"],
                "/v1/layouts",
                payload,
            )
    except (RuntimeError, ValueError) as error:
        st.error(str(error))
        return

    if body.get("status") == "needs_input" and status == 200:
        st.session_state["request_id"] = body["request_id"]
        st.session_state["answers"] = answers
        st.session_state["missing_fields"] = body.get("missing_fields", [])
    elif body.get("status") in {"completed", "publish_failed"} and "layout" in body:
        st.session_state["result"] = body
        st.session_state.pop("missing_fields", None)
    else:
        st.error(_error_message(status, body))


def _show_result(result: dict) -> None:
    published = result.get("publisher")
    if result.get("status") == "publish_failed":
        st.error("Layout generated successfully, but publishing failed.")
    elif published:
        st.success(f"Layout published successfully (HTTP {published['status_code']}).")
        with st.expander("Publishing response"):
            st.json(published, expanded=True)
    else:
        st.success("Layout generated successfully. It was not published.")

    timing = result.get("timing_ms", {})
    if timing:
        labels = {
            "retrieval": "Retrieval",
            "reranking": "Reranking",
            "generation": "Generation",
            "validation": "Validation",
            "total": "Total",
        }
        columns = st.columns(len(labels))
        for column, (key, label) in zip(columns, labels.items()):
            column.metric(label, f"{timing.get(key, 0)} ms")

    layout = result["layout"]
    st.subheader("Validated layout JSON")
    st.json(layout, expanded=True)
    st.download_button(
        "Download JSON",
        json.dumps(layout, indent=2),
        file_name=f"{result.get('request_id', 'layout')}.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="Layout Generator", page_icon="📐", layout="wide")
    st.title("Layout Generator")
    st.caption("Generate and validate an InDesign layout through the existing API.")

    st.session_state.setdefault("api_url", AppConfig.LAYOUT_API_URL)
    st.session_state.setdefault("api_key", AppConfig.LAYOUT_API_KEY)
    st.session_state.setdefault("templates", [])

    with st.sidebar:
        st.header("API connection")
        with st.form("connection"):
            st.text_input("API URL", key="api_url")
            st.text_input("API key", type="password", key="api_key")
            connect = st.form_submit_button("Connect", use_container_width=True)
        if connect:
            st.session_state["templates"] = []
            if not st.session_state["api_key"]:
                st.error("Enter the API key.")
            else:
                try:
                    status, body = api_request(
                        st.session_state["api_url"],
                        st.session_state["api_key"],
                        "/v1/templates",
                        timeout=30,
                    )
                except (RuntimeError, ValueError) as error:
                    st.error(str(error))
                else:
                    templates = body.get("templates", [])
                    if status == 200 and templates:
                        st.session_state["templates"] = templates
                        _clear_run()
                        st.success("Connected.")
                    else:
                        st.error(_error_message(status, body))

    templates = st.session_state["templates"]
    if not templates:
        st.info("Enter the FastAPI connection details and select **Connect**.")
        return

    names = {template["id"]: template["name"] for template in templates}
    with st.form("generation"):
        template_id = st.selectbox(
            "Template",
            names,
            format_func=names.get,
        )
        prompt = st.text_area(
            "Describe your layout",
            placeholder="Create a magazine article about sustainable architecture...",
            height=140,
        )
        publish = st.toggle(
            "Publish result",
            help="When enabled, the API sends the validated JSON to the configured publisher.",
        )
        generate = st.form_submit_button("Generate layout", type="primary")

    if generate:
        if not prompt.strip():
            st.error("Describe the layout before generating.")
        else:
            _clear_run()
            st.session_state["active_request"] = {
                "prompt": prompt.strip(),
                "template_id": template_id,
                "publish": publish,
            }
            _submit({})

    missing_fields = st.session_state.get("missing_fields", [])
    if missing_fields:
        st.subheader("A few more details")
        st.caption("Leave a field blank to use its standard placeholder.")
        with st.form("missing_details"):
            for field in missing_fields:
                st.text_input(
                    field["question"],
                    key=f"answer_{field['name']}",
                    placeholder=(
                        "https://example.com/image.jpg"
                        if field.get("type") == "image"
                        else field.get("placeholder", "")
                    ),
                )
            continue_generation = st.form_submit_button("Continue", type="primary")
        if continue_generation:
            answers = dict(st.session_state.get("answers", {}))
            answers.update(
                {
                    field["name"]: st.session_state[f"answer_{field['name']}"].strip()
                    or None
                    for field in missing_fields
                }
            )
            _submit(answers)

    result = st.session_state.get("result")
    if result:
        _show_result(result)
        if st.button("Start over"):
            _clear_run()
            st.rerun()


if __name__ == "__main__":
    main()
