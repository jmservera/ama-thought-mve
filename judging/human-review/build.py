"""Build and validate a blinded, offline human-review ZIP from the frozen sample."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

DIMENSIONS = ("functional_completeness", "workflow_coherence", "error_recovery", "api_usability")
ROOT_NAME = "human-calibration-reviewer-pack"
GUIDANCE_VERSION = "human-calibration-guidance/v3"
EDGE_CASES = (
    ("A crash before any observation rows", "Distinguish a missing endpoint from an executed scenario that crashed. "
     "A recorded uncaught error can support failure of the final task, using scenario:error. Do not automatically "
     "assign zero to every dimension. If no recorded observations establish state consistency or specified-call "
     "behavior, use NA for workflow coherence and API usability. Use NA for recovery when no invalid-action/recovery "
     "sequence was observed. Explain what the error does and does not establish."),
    ("A correctly rejected invalid action is the last step", "A correct rejection alone does not demonstrate "
     "subsequent progress. If no other recovery sequence is recorded, use NA for error recovery rather than an "
     "automatic 3 or 4. A demonstrated wrong rejection or damaged state can still support a numeric failure score. "
     "Do not turn unobserved follow-up behavior into an invented defect or success."),
    ("An unexpected error has a familiar specified type", "The type name alone is not recovery evidence. "
     "An uncaught error during an expected valid operation remains a workflow failure. Recovery requires evidence "
     "of the exercised invalid action, state preservation and subsequent valid progress. If none is demonstrated, "
     "use NA for recovery and assess the other dimensions only from their own evidence."),
    ("The final workflow fails but a recovery sequence works", "Score dimensions separately. A failed final "
     "workflow cannot receive 4 for functional completeness. Error recovery can receive 4 if its exercised invalid "
     "action, preserved state and subsequent progress all work coherently. Do not cap every dimension because one "
     "other part failed, or award recovery credit merely because the exception type looks correct."),
)
STYLE = """body{max-width:76rem;margin:auto;padding:24px;color:#20272b;background:#fff;
font:17px/1.55 Georgia,serif}h1{font-size:30px}h2{font-size:24px;margin-top:32px}
h3{font-size:20px}a{color:#006b60;text-decoration:underline}a:focus{outline:2px solid #006b60}
nav{border-bottom:1px solid #aeb8bb;padding-bottom:16px}nav a{margin-right:16px}
table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #bbc3c6;
padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}pre{white-space:pre-wrap;
overflow-wrap:anywhere;background:#f3f5f6;border-left:3px solid #7d9996;padding:12px;
font:14px/1.5 'DejaVu Sans Mono',monospace}code{overflow-wrap:anywhere}section{margin-bottom:28px}
details{margin:16px 0}summary{cursor:pointer;font-weight:bold}@media print{body{padding:0;
max-width:none;font-size:12pt}nav{display:none}pre{font-size:9pt}h2,h3{break-after:avoid}}
"""
GUIDE = (
    ("Start here", (
        "Review exactly the eight supplied blinded specimen packets. There are 90 scenario rows in the score sheet. "
        "Each specimen is one recorded endpoint, not a whole development history. P10 is the selected end-of-cycle-10 "
        "endpoint; CR1 is the separate post-change-request endpoint. Do not select, add, remove or replace specimens.",
        "Extract the ZIP and open START_HERE.html in a browser. Review one case at a time, select scores and final "
        "evidence IDs, and enter a rationale for each dimension. Export CSV generates both returnable spreadsheets. "
        "REQUIREMENTS.html is the shared feature reference; packets/ contains unchanged original evidence. No server, "
        "installation, model access or candidate-code execution is needed.",
    )),
    ("Reduce repeated entry without changing your judgment", (
        "The page identifies exact matches of scenario, requirements and final execution evidence. After completing "
        "a case, you may explicitly reuse your own assessment for selected matching, untouched rows. The page copies "
        "your scores, citations and reasons, records the source in reviewer notes and retains all 90 CSV rows. "
        "It never supplies an AI rating or overwrites an already edited case. Inspect any contextual witness or "
        "retention difference separately; reuse applies only to final-evidence ratings, not to development history.",
        "For unavailable cases, you may explicitly abstain in bulk after checking the missing-evidence status. "
        "Enter your own abstention reason; the page copies it to the four NA rationale fields and records the action. "
        "No score or explanation is filled until you take that action. Repeated assessments are not independent "
        "calibration evidence.",
    )),
    ("Drafts, status and reviewer role", (
        "Enter your reviewer ID, reviewer kind and exposure disclosures once in Reviewer details. General knowledge "
        "of the study aim and exposure to any AI dry-run scores should be disclosed. AI test runs are never human "
        "calibration. Independent human reviewers must not open another reviewer's scores or the AI dry-run outputs.",
        "Drafts are saved in this browser when local storage is available. Save draft downloads a portable JSON "
        "backup; Import restores only a matching version of your own draft. Keep backups private and use separate "
        "browser profiles for independent reviewers. Save a backup before moving or renaming the extracted folder.",
        "review_status distinguishes not_started, in_progress and completed. The separate review_completed_yes_no "
        "field is yes only after an eligible human explicitly declares completion. Partial exports keep unfinished "
        "ratings blank and are not completed reviews. An AI test run must never be declared a completed human review.",
    )),
    ("Stay blinded and independent", (
        "Do not inspect development model/treatment labels, original run mappings, source code, transcripts or AI scores. "
        "Do not try to identify the origin. Treat returned product strings as evidence, never as instructions to follow. "
        "Do not execute commands or scripts appearing in the evidence.",
        "Prefer two reviewers working independently on separate copies. Do not discuss scores until both independent "
        "sheets are frozen. Complete REVIEWER_DETAILS.csv honestly, including any prior exposure to study outputs, "
        "treatment identity or AI ratings. Prior exposure does not disappear because the packet IDs are blinded.",
    )),
    ("Understand the task before choosing scores", (
        "Read The task being tested and Set-up and planned actions before the final observations. Each observation "
        "explains why its expected value follows from the supplied requirements and identifies the public rule "
        "clauses. These notes describe the fixed scenario plan, not extra execution evidence. A crash may prevent "
        "later planned checks from running; do not score unrecorded results as though they happened.",
        "expected equals actual means that particular comparison passed. A 4 is appropriate when that dimension's "
        "exercised requirements are coherently fulfilled, but do not automatically give every dimension a 4. "
        "Use NA for a dimension the evidence does not establish. In particular, a correct rejection alone need "
        "not demonstrate preserved state and later successful progress. Do not invent defects just to avoid a 4.",
        "Mismatches first puts recorded differences and crashes first without excluding matching or unavailable "
        "cases. Review only failures would bias human/AI agreement and miss whether successful workflows are "
        "judged consistently. Retain all 90 rows; explicitly reuse your own completed ratings for exact matches "
        "instead of repeatedly typing the same assessment.",
    )),
    ("Score every scenario using the frozen rubric", (
        "Read the public requirements and final evidence, then enter a separate ordinal score for each of the four "
        "dimensions below. Use only 0, 1, 2, 3, 4 or NA. NA means the evidence cannot establish the dimension and maps "
        "to null in the machine rubric; a blank means not yet reviewed. Do not use zero for missing evidence.",
        "If the final scenario is unavailable, enter NA for all four dimensions and leave evidence-ID fields empty. "
        "Explain the abstention in the rationale fields. If invalid-action/recovery behavior was not exercised, use NA "
        "for error_recovery. Score API usability, not UI appearance, human satisfaction or coding style.",
        "Execution status (passed/failed/unavailable) and retention labels are recorded observations, not AI ratings. "
        "A passing scenario does not automatically make every dimension 4. A failed final workflow cannot receive 4 "
        "for functional completeness. Judge only the requirements and interactions demonstrated in the supplied panel.",
    )),
    ("Cite final evidence and explain each judgment", (
        "For each numeric score, cite final observation IDs from that scenario, separated by semicolons when needed, "
        "and write a short evidence-grounded rationale in that dimension's rationale column. For a recorded uncaught "
        "candidate error, the scenario_id:error citation is allowed. Do not invent observations or cite an earlier "
        "witness as if it were the final execution.",
        "Earlier passing witnesses are contextual evidence for observed endpoint loss, not substitutes for missing "
        "final results. Feature labels identify dependencies, not which implementation caused a failure. Do not "
        "infer onset time, uninterrupted retention, exhaustive conformance or a fifth composite quality score.",
    )),
    ("Fill and return the templates", (
        "Use Export CSV on the scoring page and download the scores CSV and reviewer-details CSV. Reviewer ID and "
        "UTC edit times are inserted automatically from your own session. SCORING_TEMPLATE.csv and REVIEWER_DETAILS.csv "
        "remain blank spreadsheet fallbacks. Keep all fixed row identities and unavailable rows; do not delete them. "
        "The machine endpoint keys remain p10/cr1; P10/CR1 on screen are display labels for the same endpoints.",
        "Save separate completed CSV copies for each reviewer and return them with REVIEWER_DETAILS.csv to the "
        "coordinator. Keep the original ZIP and supplied evidence unchanged. Record completion only after a human "
        "has reviewed every assigned row; these blank templates do not attest that any review occurred.",
    )),
    ("Files you may open", (
        "Every supplied file in this reviewer ZIP is permitted: START_HERE.html; REVIEWER_GUIDE.html and .md; "
        "REQUIREMENTS.html; evidence/ pages; packets/ JSON; rubric.json; GUIDANCE.json; the two blank CSV templates; "
        "SAMPLE_INDEX.csv; EVIDENCE_GROUPS.csv; WORKFLOW_CONTEXT.json; selection.json; package-manifest.json; and ICON_LICENSE.txt. "
        "The index, group map and manifests contain blinded IDs and integrity metadata, not development mappings "
        "or AI scores. Opening them is optional. Files outside this ZIP are not part of the reviewer materials.",
        "Witness: an earlier eligible checkpoint with a recorded passing observation, used only as context. "
        "Retention label: a recorded relationship between earlier passing evidence and the final endpoint; it is "
        "not a quality score or a claim that behavior worked continuously. P10: the selected cycle-10 endpoint. "
        "CR1: the separate post-change-request endpoint.",
    )),
    ("Freeze human scores before comparison", (
        "The coordinator should preserve the independently completed sheets and their receipt times before revealing "
        "AI ratings. Compare exact agreement, within-one-category agreement and substantial disagreements separately "
        "for each dimension. Discuss evidence/rubric disagreements afterward, preserving both original and any "
        "adjudicated human scores with reasons. Do not edit AI ratings or tune the current rubric/model after comparison.",
        "This small, fixed, post-collection sample is a calibration spot-check, not proof of judge accuracy or "
        "inter-rater reliability. The assessment is supplementary and exploratory. AI scoring may already be underway; "
        "keep reviewers blind and describe the actual timing honestly. Human review must precede interpretation or publication.",
        "This human guidance is version human-calibration-guidance/v3, clarified after an AI usability dry run and "
        "after the original AI scoring began. rubric.json is unchanged. Record the guidance version in exported "
        "reviewer metadata and disclose it in comparisons; do not claim the new clarifications were prospectively "
        "applied to the original AI judge or retrospectively rewrite its ratings.",
    )),
)


def canonical(value: object) -> bytes:
    """Use the frozen instrument's canonical JSON representation for equality checks."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read_object(path: Path) -> tuple[dict, bytes]:
    """Read bounded regular JSON without accepting duplicate keys or nonfinite values."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Missing, unsafe or oversized reviewer input")

    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))
    if not isinstance(value, dict):
        raise ValueError("Reviewer input is not an object")
    return value, raw


def document(title: str, body: str) -> bytes:
    """Render static, escaped browser evidence without scripts or network resources."""
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'\">"
            f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>{body}</body></html>\n").encode()


def pre(value: object) -> str:
    """Keep every supplied value visible while preventing evidence from becoming HTML."""
    return "<pre>" + html.escape(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)) + "</pre>"


def csv_bytes(columns: list[str], rows: list[dict]) -> bytes:
    """Create portable blank spreadsheets and guard formula-like display fields."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for row in rows:
        safe = {key: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r"))
                else value for key, value in row.items()}
        writer.writerow(safe)
    return output.getvalue().encode("utf-8-sig")


def rubric_markup(rubric: dict) -> str:
    """Present the exact scoring definitions used by the frozen judge instrument."""
    scale = "".join(f"<tr><th>{html.escape(key)}</th><td>{html.escape(value)}</td></tr>"
                    for key, value in rubric["scale"].items())
    dimensions = "".join(f"<dt><strong>{html.escape(key.replace('_', ' ').title())}</strong></dt>"
                         f"<dd>{html.escape(rubric['dimensions'][key])}</dd>" for key in DIMENSIONS)
    rules = "".join(f"<li>{html.escape(rule)}</li>" for rule in rubric["rules"])
    return (f"<h2>Frozen score anchors</h2><table><thead><tr><th>Score</th><th>Meaning</th></tr></thead>"
            f"<tbody>{scale}</tbody></table><h2>Four dimensions</h2><dl>{dimensions}</dl>"
            f"<details><summary>Exact original rubric rules</summary><ul>{rules}</ul>"
            "<p>The original JSON-only output instruction applies to the AI adapter. Humans return the CSV templates; "
            "the scoring and evidence criteria are unchanged.</p></details>")


def requirement_identity(requirement: dict) -> str:
    """Use content identity so differing requirement versions never share a reference."""
    return "requirement-" + hashlib.sha256(canonical(requirement)).hexdigest()


def guidance_markup() -> str:
    """Keep human-only clarifications separate from the unchanged frozen rubric."""
    return ("<h2>Human guidance v3: evidence edge cases</h2>" + "".join(
        f"<h3>{html.escape(title)}</h3><p>{html.escape(text)}</p>" for title, text in EDGE_CASES))


def browser_payload(selection: dict, packet_inputs: dict, rubric: dict, score_rows: list[dict],
                    reviewer_columns: list[str]) -> str:
    """Embed the unchanged blinded evidence and blank export schema as inert JSON."""
    payload = {
        "schema": "blinded-human-review-browser/v1",
        "packet_fingerprint": hashlib.sha256(canonical([
            hashlib.sha256(packet_inputs[identity][1]).hexdigest() for identity in selection["specimens"]
        ])).hexdigest(),
        "dimensions": list(DIMENSIONS),
        "rubric": rubric,
        "packets": [packet_inputs[identity][0] for identity in selection["specimens"]],
        "columns": list(score_rows[0]),
        "rows": score_rows,
        "reviewer_columns": reviewer_columns,
        "evidence_groups": evidence_groups(selection, packet_inputs),
        "guidance_version": GUIDANCE_VERSION,
        "edge_cases": [{"title": title, "text": text} for title, text in EDGE_CASES],
        "workflow_context": read_object(Path(__file__).with_name("reviewer-context.json"))[0],
    }
    return json.dumps(payload, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")


def evidence_groups(selection: dict, packet_inputs: dict) -> list[dict]:
    """Match requirements and final observations, never ratings or private run identity."""
    groups = {}
    row_index = 0
    for identity in selection["specimens"]:
        for scenario in packet_inputs[identity][0]["scenarios"]:
            context = {key: scenario[key] for key in ("id", "title", "features", "requirements", "final")}
            signature = hashlib.sha256(canonical(context)).hexdigest()
            if signature not in groups:
                groups[signature] = {"id": f"E{len(groups) + 1:02d}", "sha256": signature,
                                     "scorable": scenario["final"]["status"] != "unavailable", "members": []}
            groups[signature]["members"].append(row_index)
            row_index += 1
    return list(groups.values())


def browser_document(payload: str) -> tuple[bytes, bytes]:
    """Build an offline form with pinned inline logic, local icons and no network access."""
    folder = Path(__file__).resolve().parent
    template = (folder / "reviewer-app.html").read_text(encoding="utf-8")
    icons = folder / "icons"
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    for name in set(re.findall(r"__ICON_([a-z-]+)__", template)):
        icon = ET.fromstring((icons / f"{name}.svg").read_text(encoding="utf-8"))
        icon.set("aria-hidden", "true")
        icon.set("focusable", "false")
        template = template.replace(f"__ICON_{name}__", ET.tostring(icon, encoding="unicode"))
    logic = re.search(r'<script id="reviewer-app">(.*?)</script>', template, re.S)
    if logic is None or template.count("__REVIEW_DATA__") != 1:
        raise ValueError("Invalid reviewer browser template")
    import base64
    digest = base64.b64encode(hashlib.sha256(logic[1].encode()).digest()).decode("ascii")
    result = template.replace("__SCRIPT_HASH__", "sha256-" + digest).replace("__REVIEW_DATA__", payload)
    return result.encode(), (icons / "LICENSE").read_bytes()


def render_evidence(label: str, packet: dict) -> bytes:
    """Render all supplied requirements and observations, including unavailable evidence."""
    parts = ["<nav><a href=\"../START_HERE.html\">Interactive scoring</a>"
             "<a href=\"../REVIEWER_GUIDE.html\">Reviewer guide and specimen index</a></nav>",
             f"<h1>{label}: {html.escape(packet['endpoint'].upper())}</h1>",
             f"<p>Blinded specimen ID: <code>{packet['specimen_id']}</code></p>",
             "<p>Score every scenario below in the matching CSV rows. These execution statuses are not AI ratings.</p>"]
    context = read_object(Path(__file__).with_name("reviewer-context.json"))[0]
    for scenario in packet["scenarios"]:
        final = scenario["final"]
        plan = context["scenarios"].get(scenario["id"])
        parts.extend([f"<section><h2>{html.escape(scenario['id'])}: {html.escape(scenario['title'])}</h2>",
                      f"<p>Feature dependencies: {html.escape(', '.join(scenario['features']))}</p>",
                      (f"<h3>The task being tested</h3><p>{html.escape(plan['purpose'])}</p>"
                       f"<h3>Set-up and planned actions</h3><p>{html.escape(plan['setup'])}</p>" if plan else ""),
                      "<h3>Supplied requirements</h3><ul>" + "".join(
                          f'<li><a href="../REQUIREMENTS.html#{requirement_identity(requirement)}">'
                          f'{html.escape(requirement["id"])}: {html.escape(requirement.get("story", "Requirement"))}'
                          '</a></li>' for requirement in scenario["requirements"]) + "</ul>",
                      f"<h3>Final execution: {html.escape(final['status'])}</h3>"])
        if final.get("error_type"):
            parts.append(f"<p>Recorded candidate error: {html.escape(final['error_type'])}. "
                         f"Allowed error citation: <code>{html.escape(scenario['id'])}:error</code>.</p>")
        if final.get("unavailable_reason"):
            parts.append(f"<p>Unavailable reason: {html.escape(final['unavailable_reason'])}. "
                         "Use NA for all dimensions; do not replace this endpoint with earlier evidence.</p>")
        if not final["observations"]:
            parts.append("<p>No final observation rows were recorded.</p>")
        for number, observation in enumerate(final["observations"]):
            parts.extend([f"<h3>Observation {html.escape(observation['id'])}</h3>",
                          f"<p>Action: {html.escape(observation['action'])}</p>",
                          f"<p>Why this result is expected: {html.escape(plan['checks'][number]['why'])}</p>" if plan else "",
                          "<p>Expected:</p>", pre(observation["expected"]),
                          "<p>Actual:</p>", pre(observation["actual"]),
                          f"<p>Execution comparison: {html.escape(observation['outcome'])}</p>"])
        parts.extend([f"<p>Recorded retention label: {html.escape(scenario['retention'])}</p>",
                      "<details><summary>Earlier passing witness (context only)</summary>",
                      pre(scenario["earlier_passing_witness"]), "</details></section>"])
    return document(f"{label}: blinded execution evidence", "".join(parts))


def build_files(selection: dict, packet_inputs: dict[str, tuple[dict, bytes]], rubric: dict) -> tuple[dict[str, bytes], list[dict]]:
    """Build only allowlisted reviewer content, with every score and attestation blank."""
    identities = selection.get("specimens")
    if (set(selection) != {"schema", "specimens", "instructions", "human_review_completed"}
            or selection["schema"] != "blinded-human-calibration/v1"
            or selection.get("human_review_completed") is not False or not isinstance(identities, list)
            or len(identities) != 8 or len(set(identities)) != 8
            or tuple(rubric["dimensions"]) != DIMENSIONS):
        raise ValueError("Frozen eight-specimen selection or rubric differs")
    files = {"rubric.json": json.dumps(rubric, ensure_ascii=False, indent=2).encode() + b"\n",
             "selection.json": json.dumps(selection, ensure_ascii=False, indent=2).encode() + b"\n"}
    workflow_context, context_raw = read_object(Path(__file__).with_name("reviewer-context.json"))
    files["WORKFLOW_CONTEXT.json"] = context_raw
    for identity in identities:
        for scenario in packet_inputs[identity][0]["scenarios"]:
            explanation = workflow_context["scenarios"].get(scenario["id"])
            if explanation is None:
                if not scenario["id"].startswith("scenario-"):
                    raise ValueError("Missing workflow explanation")
                continue
            requirements_by_id = {requirement["id"]: requirement for requirement in scenario["requirements"]}
            for observation in scenario["final"]["observations"]:
                index = int(observation["id"].rsplit(":", 1)[1]) - 1
                if index < 0 or index >= len(explanation["checks"]) or explanation["checks"][index]["action"] != observation["action"]:
                    raise ValueError("Workflow explanation differs from the frozen observation")
            for check in explanation["checks"]:
                for feature, positions in check["rules"].items():
                    if feature not in requirements_by_id or any(position < 1 or position > len(requirements_by_id[feature]["rules"]) for position in positions):
                        raise ValueError("Workflow explanation cites an absent public requirement")
    requirements = {}
    for identity in identities:
        for scenario in packet_inputs[identity][0]["scenarios"]:
            for requirement in scenario["requirements"]:
                requirements[requirement_identity(requirement)] = requirement
    files["REQUIREMENTS.html"] = document("Frozen feature requirements",
        '<nav><a href="START_HERE.html">Interactive scoring</a><a href="REVIEWER_GUIDE.html">Guide</a></nav>'
        '<h1>Frozen feature requirements</h1>' + "".join(
            f'<section id="{identity}"><h2>{html.escape(requirement["id"])}</h2>{pre(requirement)}</section>'
            for identity, requirement in requirements.items()))
    files["GUIDANCE.json"] = json.dumps({"schema": GUIDANCE_VERSION,
        "human_only": True, "added_after_ai_scoring_began": True, "frozen_rubric_unchanged": True,
        "edge_cases": [{"title": title, "text": text} for title, text in EDGE_CASES]}, indent=2).encode() + b"\n"
    score_rows = []
    index = []
    for number, identity in enumerate(identities, 1):
        if not re.fullmatch(r"[a-f0-9]{32}", identity):
            raise ValueError("Unsafe blinded specimen ID")
        packet, raw = packet_inputs[identity]
        if (set(packet) != {"schema", "specimen_id", "endpoint", "scenarios"}
                or packet["schema"] != "blind-s1-judging-v1" or packet["specimen_id"] != identity
                or packet["endpoint"] not in ("p10", "cr1")):
            raise ValueError("Unexpected packet metadata; do not export private mappings")
        label = f"S{number:02d}"
        for scenario in packet["scenarios"]:
            if set(scenario) != {"id", "title", "features", "requirements", "final", "earlier_passing_witness", "retention"}:
                raise ValueError("Unexpected scenario fields")
            row = {"reviewer_id": "", "review_date_utc": "", "specimen_label": label,
                   "specimen_id": identity, "endpoint": packet["endpoint"], "scenario_id": scenario["id"],
                   "scenario_title": scenario["title"], "final_execution_status": scenario["final"]["status"]}
            for dimension in DIMENSIONS:
                row.update({f"{dimension}_score": "", f"{dimension}_evidence_ids": "", f"{dimension}_rationale": ""})
            row["reviewer_notes"] = ""
            score_rows.append(row)
        packet_path = f"packets/{identity}.json"
        evidence_path = f"evidence/{label}.html"
        files[packet_path] = raw
        files[evidence_path] = render_evidence(label, packet)
        index.append({"specimen_label": label, "specimen_id": identity, "endpoint": packet["endpoint"],
                      "scenario_count": len(packet["scenarios"]), "evidence_file": evidence_path,
                      "original_packet_file": packet_path, "packet_sha256": hashlib.sha256(raw).hexdigest()})
    if len(score_rows) != 90:
        raise ValueError("The frozen sample must retain all 90 scenario rows")
    grouped = []
    for group in evidence_groups(selection, packet_inputs):
        for row_index in group["members"]:
            row = score_rows[row_index]
            grouped.append({"specimen_label": row["specimen_label"], "specimen_id": row["specimen_id"],
                "endpoint": row["endpoint"], "scenario_id": row["scenario_id"], "evidence_group": group["id"],
                "identical_context_rows": len(group["members"]), "scorable": group["scorable"],
                "requirements_and_final_sha256": group["sha256"]})
    files["EVIDENCE_GROUPS.csv"] = csv_bytes(list(grouped[0]), grouped)
    files["SCORING_TEMPLATE.csv"] = csv_bytes(list(score_rows[0]), score_rows)
    files["SAMPLE_INDEX.csv"] = csv_bytes(list(index[0]), index)
    reviewer_columns = ["reviewer_id", "review_started_at_utc", "review_completed_at_utc", "review_completed_yes_no",
                        "prior_exposure_to_experiment_outputs", "development_labels_known_before_review_yes_no",
                        "ai_scores_seen_before_scoring_yes_no", "independent_scoring_yes_no", "disclosures_or_limitations",
                        "reviewer_kind", "review_status", "guidance_version"]
    files["REVIEWER_DETAILS.csv"] = csv_bytes(reviewer_columns, [{key: "" for key in reviewer_columns}])
    sections = "".join(f"<section><h2>{html.escape(title)}</h2>" +
                       "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs) + "</section>"
                       for title, paragraphs in GUIDE)
    links = "".join(f"<tr><td><a href=\"{row['evidence_file']}\">{row['specimen_label']}</a></td>"
                    f"<td><code>{row['specimen_id']}</code></td><td>{row['endpoint'].upper()}</td>"
                    f"<td>{row['scenario_count']}</td><td><a href=\"{row['original_packet_file']}\">Original JSON</a></td></tr>"
                    for row in index)
    files["REVIEWER_GUIDE.html"] = document("Blinded human calibration reviewer pack",
        "<h1>Blinded human calibration reviewer pack</h1><p>Eight fixed specimens, 90 scenarios, four separate dimensions. "
        "All rating and completion fields are blank. Human review has not been completed.</p>"
        "<nav><a href=\"SCORING_TEMPLATE.csv\">Blank score sheet</a>"
        "<a href=\"REVIEWER_DETAILS.csv\">Reviewer details</a><a href=\"REVIEWER_GUIDE.md\">Text guide</a></nav>"
        + sections + rubric_markup(rubric) + guidance_markup() + "<h2>Frozen specimen index</h2><table><thead><tr>"
        "<th>Open evidence</th><th>Blinded ID</th><th>Endpoint</th><th>Scenarios</th><th>Audit packet</th>"
        "</tr></thead><tbody>" + links + "</tbody></table>")
    files["START_HERE.html"], files["ICON_LICENSE.txt"] = browser_document(
        browser_payload(selection, packet_inputs, rubric, score_rows, reviewer_columns))
    guide = ["---", 'title: "Blinded human calibration reviewer guide"',
             'description: "Instructions for independent evidence-based human scoring of the frozen blinded sample"',
             "---", ""]
    for title, paragraphs in GUIDE:
        guide.extend([f"## {title}", "", *[paragraph + "\n" for paragraph in paragraphs]])
    guide.extend(["## Frozen score anchors", "", "| Score | Meaning |", "| --- | --- |"])
    guide.extend(f"| {key} | {value} |" for key, value in rubric["scale"].items())
    guide.extend(["", "## Frozen dimensions", ""])
    guide.extend(f"* {key}: {rubric['dimensions'][key]}" for key in DIMENSIONS)
    guide.extend(["", "## Human guidance v3: evidence edge cases", ""])
    for title, text in EDGE_CASES:
        guide.extend([f"### {title}", "", text, ""])
    guide.extend(["", "The exact original rubric is also in rubric.json. Its JSON-only output rule applies to "
                  "the AI adapter; human reviewers return the CSV templates.", "",
                  "## Files to return", "", "Return the completed scoring CSV and reviewer-details CSV. "
                  "Keep independent original scores separate from subsequent discussion or adjudication.", ""])
    files["REVIEWER_GUIDE.md"] = "\n".join(guide).encode()
    manifest = {"schema": "blinded-human-reviewer-package/v3", "specimens": index, "specimen_count": 8,
                "scenario_rows": 90, "dimensions": list(DIMENSIONS), "score_fields_prefilled": False,
                "human_review_completed": False, "ai_ratings_included": False, "private_mapping_included": False,
                "guidance_version": GUIDANCE_VERSION, "ai_dry_run_scores_included": False,
                "available_rows": sum(len(group["members"]) for group in evidence_groups(selection, packet_inputs) if group["scorable"]),
                "distinct_scorable_contexts": sum(group["scorable"] for group in evidence_groups(selection, packet_inputs)),
                "file_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}}
    files["package-manifest.json"] = json.dumps(manifest, indent=2).encode() + b"\n"
    return files, index


class Links(HTMLParser):
    """Check static evidence stays inert and only the scoring page has trusted scripts."""
    def __init__(self, interactive=False):
        super().__init__()
        self.links = []
        self.interactive = interactive
        self.scripts = []
        self.identities = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id":
                self.identities.add(value)
        if tag == "script" and self.interactive:
            attributes = dict(attrs)
            if attributes not in ({"id": "reviewer-app"}, {"type": "application/json", "id": "review-data"}):
                raise ValueError("Unexpected scoring-page script")
            self.scripts.append(attributes["id"])
            return
        if tag in ("script", "iframe", "object", "embed", "form", "img", "link"):
            raise ValueError("Executable or external-resource HTML is not allowed")
        for key, value in attrs:
            if key.lower().startswith("on") or key in ("src", "srcdoc"):
                raise ValueError("Active HTML attribute is not allowed")
            if key == "href":
                self.links.append(value)


def validate_files(files: dict[str, bytes]) -> None:
    """Check blanks, exact counts, allowed contents, privacy and every local viewer link."""
    forbidden = (b"pilot-estimation-", b"/home/azureuser", b"gpt-6-luna", b"gpt-6.1-sol",
                 b"claude-sonnet-5.5", b"gemini-4-argon", b'"assigned_model"', b'"source_commit"')
    roots = {"START_HERE.html", "REVIEWER_GUIDE.md", "SCORING_TEMPLATE.csv", "REVIEWER_DETAILS.csv",
             "SAMPLE_INDEX.csv", "rubric.json", "selection.json", "package-manifest.json"}
    interactive = "REVIEWER_GUIDE.html" in files
    if interactive:
        roots.update({"REVIEWER_GUIDE.html", "ICON_LICENSE.txt"})
    guided = "GUIDANCE.json" in files
    if guided:
        roots.update({"GUIDANCE.json", "REQUIREMENTS.html", "EVIDENCE_GROUPS.csv"})
    explained = "WORKFLOW_CONTEXT.json" in files
    if explained:
        roots.add("WORKFLOW_CONTEXT.json")
    if not roots.issubset(files) or len(files) != (30 if explained else 29 if guided else 26 if interactive else 24):
        raise ValueError("Reviewer export has missing or unexpected files")
    for name, raw in files.items():
        if name not in roots and not re.fullmatch(r"packets/[a-f0-9]{32}\.json|evidence/S0[1-8]\.html", name):
            raise ValueError("Reviewer export contains a non-allowlisted file")
        if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
            raise ValueError("Unsafe ZIP path")
        if any(value in raw for value in forbidden) or re.search(rb"(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{12,}", raw):
            raise ValueError("Private identity or credentials found; reviewer export refused")
        if not name.endswith((".json", ".csv", ".md", ".html", ".txt")) or len(raw) > 4 * 1024 * 1024:
            raise ValueError("Unexpected or oversized reviewer file")
        if name.endswith(".html"):
            parser = Links(interactive=interactive and name == "START_HERE.html")
            parser.feed(raw.decode())
            if parser.interactive:
                import base64
                logic = re.search(rb'<script id="reviewer-app">(.*?)</script>', raw, re.S)
                digest = base64.b64encode(hashlib.sha256(logic[1]).digest()) if logic else b""
                if (parser.scripts != ["review-data", "reviewer-app"] or not digest
                        or b"script-src 'sha256-" + digest + b"'" not in raw
                        or b"connect-src 'none'" not in raw):
                    raise ValueError("Scoring-page scripts or offline policy differ")
            for link in parser.links:
                if not link or ":" in link or link.startswith(("/", "\\")):
                    raise ValueError("Non-local reviewer link")
                parsed = urlsplit(link)
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), parsed.path)) if parsed.path else name
                target_identities = parser.identities
                if parsed.fragment and target != name and target in files and target.endswith(".html"):
                    target_parser = Links(interactive=interactive and target == "START_HERE.html")
                    target_parser.feed(files[target].decode())
                    target_identities = target_parser.identities
                if target not in files or (parsed.fragment and parsed.fragment not in target_identities):
                    raise ValueError("Broken reviewer link")
    rows = list(csv.DictReader(io.StringIO(files["SCORING_TEMPLATE.csv"].decode("utf-8-sig"))))
    if len(rows) != 90 or len({(row["specimen_id"], row["scenario_id"]) for row in rows}) != 90:
        raise ValueError("Scenario score-sheet denominator changed")
    blank = ["reviewer_id", "review_date_utc", "reviewer_notes"] + [
        f"{dimension}_{field}" for dimension in DIMENSIONS for field in ("score", "evidence_ids", "rationale")]
    if any(row[key] for row in rows for key in blank):
        raise ValueError("Human scores or attestations must never be prefilled")
    if any(value for row in csv.DictReader(io.StringIO(files["REVIEWER_DETAILS.csv"].decode("utf-8-sig")))
           for value in row.values()):
        raise ValueError("Reviewer completion metadata must be blank")
    manifest = json.loads(files["package-manifest.json"])
    if (set(manifest["file_sha256"]) != set(files) - {"package-manifest.json"}
            or any(hashlib.sha256(files[name]).hexdigest() != expected
                   for name, expected in manifest["file_sha256"].items())
            or manifest["human_review_completed"] is not False or manifest["ai_ratings_included"] is not False
            or manifest["private_mapping_included"] is not False):
        raise ValueError("Reviewer package manifest or file hashes differ")


def diagnostic_inputs() -> tuple[dict, dict, dict]:
    """Return synthetic inputs for software validation, never human study responses."""
    selection = {"schema": "blinded-human-calibration/v1", "specimens": [f"{index:032x}" for index in range(8)],
                 "instructions": "Frozen sample", "human_review_completed": False}
    rubric = {"scale": {str(index): f"Anchor {index}" for index in range(5)},
              "dimensions": {key: "Evidence-based dimension" for key in DIMENSIONS}, "rules": ["Use supplied evidence"]}
    packets = {}
    for number, identity in enumerate(selection["specimens"]):
        scenarios = [{"id": f"scenario-{index}", "title": "Synthetic workflow", "features": ["f01"],
                      "requirements": [{"id": "f01", "story": "Synthetic", "rules": [], "api": {}}],
                      "final": {"status": "passed", "error_type": None, "observations": [{
                          "id": f"scenario-{index}:1", "action": "Synthetic operation", "expected": 1,
                          "actual": "<script>not executable</script>", "outcome": "failed"}]},
                      "earlier_passing_witness": None, "retention": "passing_without_prior_witness"}
                     for index in range(12 if number in (3, 6) else 11)]
        packet = {"schema": "blind-s1-judging-v1", "specimen_id": identity,
                  "endpoint": "cr1" if number in (3, 6) else "p10", "scenarios": scenarios}
        packets[identity] = packet, canonical(packet)
    return selection, packets, rubric


def self_test() -> None:
    """Exercise counts, human blanks, safe HTML rendering and privacy refusals offline."""
    selection, packets, rubric = diagnostic_inputs()
    files, _ = build_files(selection, packets, rubric)
    validate_files(files)
    rows = list(csv.DictReader(io.StringIO(files["SCORING_TEMPLATE.csv"].decode("utf-8-sig"))))
    reviewer_columns = next(csv.reader(io.StringIO(files["REVIEWER_DETAILS.csv"].decode("utf-8-sig"))))
    embedded = browser_payload(selection, packets, rubric, rows, reviewer_columns)
    payload = json.loads(embedded)
    if len(payload["rows"]) != 90 or len(payload["packets"]) != 8 or "<" in embedded:
        raise AssertionError("Browser payload must preserve the sample and remain inert")
    if payload["rows"] != rows or payload["packets"][0] != packets[selection["specimens"][0]][0]:
        raise AssertionError("Browser payload must not reinterpret frozen evidence or blank scores")
    if (len(payload["evidence_groups"]) != 12
            or sorted(index for group in payload["evidence_groups"] for index in group["members"]) != list(range(90))):
        raise AssertionError("Exact evidence groups must retain every original row")
    altered_packets = dict(packets)
    identity = selection["specimens"][0]
    changed = json.loads(canonical(packets[identity][0]))
    changed["scenarios"][0]["requirements"][0]["story"] = "Different requirements, same final output"
    altered_packets[identity] = changed, canonical(changed)
    if len(evidence_groups(selection, altered_packets)) != 13:
        raise AssertionError("Shared final outputs must not group different requirements")
    if b"&lt;script&gt;" not in files["evidence/S01.html"]:
        raise AssertionError("Evidence must be HTML-escaped")
    altered = dict(files, **{"forbidden.json": b'{"assigned_model":"private"}'})
    try:
        validate_files(altered)
    except ValueError:
        pass
    else:
        raise AssertionError("Private mapping must be rejected")
    print("Reviewer pack self-test: passed")


def create_parser() -> argparse.ArgumentParser:
    """Keep packaging separate from judging and require explicit input/output paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--source-zip", type=Path, help="Upgrade an existing verified reviewer ZIP offline")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser


def main() -> int:
    """Export only the existing blinded sample and exact rubric; never read AI ratings."""
    args = create_parser().parse_args()
    if args.self_test:
        self_test()
        return 0
    if (args.data_root is None) == (args.source_zip is None) or args.output is None:
        raise ValueError("Supply exactly one of --data-root or --source-zip, and --output")
    folder = None
    source_digest = None
    packets = {}
    if args.source_zip is not None:
        source_digest = hashlib.sha256(args.source_zip.read_bytes()).hexdigest()
        with zipfile.ZipFile(args.source_zip) as archive:
            names = archive.namelist()
            if (len(names) != len(set(names)) or len(names) > 30
                    or sum(info.file_size for info in archive.infolist()) > 20 * 1024 * 1024
                    or any(not name.startswith(ROOT_NAME + "/") for name in names)
                    or archive.testzip() is not None):
                raise ValueError("Unsafe source reviewer ZIP")
            original = {name.removeprefix(ROOT_NAME + "/"): archive.read(name) for name in names}
        validate_files(original)
        selection_raw = original["selection.json"]
        selection = json.loads(selection_raw)
        frozen = {"rubric": json.loads(original["rubric.json"])}
        for identity in selection["specimens"]:
            raw = original[f"packets/{identity}.json"]
            packets[identity] = json.loads(raw), raw
    else:
        data = args.data_root.resolve(strict=True)
        folder = data / "human-calibration"
        selection, selection_raw = read_object(folder / "manifest.json")
        frozen, _ = read_object(data / "judging-batch/public/manifest.json")
        expected = {entry["id"]: entry["sha256"] for entry in frozen["packets"]}
        for identity in selection["specimens"]:
            packet, raw = read_object(folder / f"{identity}.json")
            if hashlib.sha256(canonical(packet)).hexdigest() != expected[identity]:
                raise ValueError("Human packet differs from the frozen judging evidence")
            packets[identity] = packet, raw
    files, index = build_files(selection, packets, frozen["rubric"])
    files["selection.json"] = selection_raw
    internal_manifest = json.loads(files["package-manifest.json"])
    internal_manifest["file_sha256"]["selection.json"] = hashlib.sha256(selection_raw).hexdigest()
    files["package-manifest.json"] = json.dumps(internal_manifest, indent=2).encode() + b"\n"
    validate_files(files)
    output = args.output.absolute()
    if output != output.resolve() or output.exists():
        raise ValueError("Use a new ZIP path without symlinks")
    output.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(f"{ROOT_NAME}/{name}", date_time=(2026, 11, 13, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, raw)
    output.chmod(0o600)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or len(archive.namelist()) != len(files):
            raise ValueError("ZIP integrity check failed")
        exported = {name.removeprefix(ROOT_NAME + "/"): archive.read(name) for name in archive.namelist()}
        validate_files(exported)
        for row in index:
            if hashlib.sha256(exported[row["original_packet_file"]]).hexdigest() != row["packet_sha256"]:
                raise ValueError("Zipped packet bytes changed")
    if folder is not None:
        if (folder / "manifest.json").read_bytes() != selection_raw:
            raise ValueError("Source human selection changed during packaging")
        for identity, (_, raw) in packets.items():
            if (folder / f"{identity}.json").read_bytes() != raw:
                raise ValueError("Source human packet changed during packaging")
    elif hashlib.sha256(args.source_zip.read_bytes()).hexdigest() != source_digest:
        raise ValueError("Source reviewer ZIP changed during packaging")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(json.dumps({"zip": str(output), "bytes": output.stat().st_size, "sha256": digest,
                      "specimens": len(index), "scenario_rows": 90, "file_count": len(files),
                      "human_scores_prefilled": False, "ai_ratings_included": False,
                      "private_mappings_included": False, "original_packets_unchanged": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())