"""
TED scanner

It fetches TED notices, parses the relevant TED fields, and returns dictionaries shaped for the database injector.
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


SOURCE_DOMAIN = "ted.europa.eu"
SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
DEFAULT_SINCE = "20260601"
DEFAULT_LIMIT = 50
REQUEST_PAUSE_SECONDS = 1.0

DEFAULT_CPV_DIVISIONS = [
    "72",  # IT services
    "48",  # software
    "35",  # security/defence equipment
    "33",  # medical equipment
    "85",  # health services
    "09",  # fuels/energy
    "65",  # utilities / electricity distribution
    "60",  # transport services
    "63",  # transport support / logistics-related services
    "45",  # construction
    "34",  # transport equipment, including aircraft
]

TED_NOTICE_FIELDS = [
    "publication-number",
    "notice-type",
    "notice-title",
    "publication-date",
    "buyer-name",
    "buyer-country",
    "buyer-legal-type",
    "classification-cpv",
    "procedure-type",
    "contract-nature-main-proc",
    "description-proc",
    "description-lot",
    "title-lot",
    "place-of-performance-country-proc",
    "place-of-performance-country-lot",
    "deadline-receipt-tender-date-lot",
    "deadline-receipt-tender-time-lot",
    "estimated-value-proc",
    "estimated-value-cur-proc",
    "estimated-value-lot",
    "estimated-value-cur-lot",
    "contract-duration-start-date-lot",
    "contract-duration-end-date-lot",
    "contract-duration-period-lot",
    "duration-period-value-lot",
    "duration-period-unit-lot",
]


def load_optional_api_key():
    load_dotenv(dotenv_path=PROJECT_ROOT / ".env")
    return os.environ.get("TED_API_KEY", "")


def pick_language_value(value):
    if isinstance(value, dict):
        return value.get("eng") or next(iter(value.values()), None)
    if isinstance(value, list) and value:
        return pick_language_value(value[0])
    return str(value).strip() if value else None


def flatten_values(value):
    if value is None:
        return []
    if isinstance(value, dict):
        values = []
        for item in value.values():
            values.extend(flatten_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(flatten_values(item))
        return values

    text = str(value).strip()
    return [text] if text else []


def unique_values(value):
    values = []
    for item in flatten_values(value):
        if item not in values:
            values.append(item)
    return values


def format_field(label, value):
    values = unique_values(value)
    if not values:
        return None
    return f"{label}: {', '.join(values)}"


def compose_body(notice):
    sections = [
        format_field("Procedure description", notice.get("description-proc")),
        format_field("Lot title", notice.get("title-lot")),
        format_field("Lot description", notice.get("description-lot")),
        format_field("Buyer", notice.get("buyer-name")),
        format_field("Buyer country", notice.get("buyer-country")),
        format_field("Buyer legal type", notice.get("buyer-legal-type")),
        format_field("CPV classification", notice.get("classification-cpv")),
        format_field("Procedure type", notice.get("procedure-type")),
        format_field("Contract nature", notice.get("contract-nature-main-proc")),
        format_field(
            "Place of performance",
            notice.get("place-of-performance-country-proc")
            or notice.get("place-of-performance-country-lot"),
        ),
        format_field(
            "Tender deadline date",
            notice.get("deadline-receipt-tender-date-lot"),
        ),
        format_field(
            "Tender deadline time",
            notice.get("deadline-receipt-tender-time-lot"),
        ),
        format_field(
            "Estimated procedure value",
            notice.get("estimated-value-proc"),
        ),
        format_field(
            "Estimated procedure currency",
            notice.get("estimated-value-cur-proc"),
        ),
        format_field("Estimated lot value", notice.get("estimated-value-lot")),
        format_field(
            "Estimated lot currency",
            notice.get("estimated-value-cur-lot"),
        ),
        format_field(
            "Contract start date",
            notice.get("contract-duration-start-date-lot"),
        ),
        format_field(
            "Contract end date",
            notice.get("contract-duration-end-date-lot"),
        ),
        format_field(
            "Contract duration",
            notice.get("contract-duration-period-lot")
            or notice.get("duration-period-value-lot"),
        ),
        format_field("Contract duration unit", notice.get("duration-period-unit-lot")),
    ]

    body = "\n".join(section for section in sections if section)
    if body:
        return body

    return json.dumps(notice, ensure_ascii=False)


def fetch_notices(cpv_division, since, limit, api_key, check_query_syntax=False):
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "query": (
            f"classification-cpv = {cpv_division}* "
            f"AND publication-date >= {since} "
            f"SORT BY publication-date DESC"
        ),
        "fields": TED_NOTICE_FIELDS,
        "limit": limit,
        "page": 1,
    }
    if check_query_syntax:
        payload["checkQuerySyntax"] = True

    response = requests.post(
        SEARCH_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("notices", [])


def parse_ted_notice(notice):
    publication_number = notice.get("publication-number")
    title = (
        pick_language_value(notice.get("notice-title"))
        or pick_language_value(notice.get("title-lot"))
        or publication_number
    )

    if not publication_number or not title:
        return None

    return {
        "domain": None,
        "title": title,
        "date": notice.get("publication-date"),
        "url": f"https://ted.europa.eu/en/notice/-/detail/{publication_number}",
        "source_domain": SOURCE_DOMAIN,
        "signal_type_guess": "buying_signals",
        "body": compose_body(notice),
        "external_id": publication_number,
    }


def scan_ted_notices(
    cpv_divisions=None,
    since=DEFAULT_SINCE,
    limit=DEFAULT_LIMIT,
    request_pause_seconds=REQUEST_PAUSE_SECONDS,
    check_query_syntax=False,
):
    api_key = load_optional_api_key()
    cpv_divisions = cpv_divisions or DEFAULT_CPV_DIVISIONS
    signals = []
    errors = []

    for cpv_division in cpv_divisions:
        print(f"\n=== TED CPV division {cpv_division} ===")
        try:
            notices = fetch_notices(
                cpv_division,
                since,
                limit,
                api_key,
                check_query_syntax=check_query_syntax,
            )
            parsed_signals = [
                signal
                for signal in (parse_ted_notice(notice) for notice in notices)
                if signal
            ]
            signals.extend(parsed_signals)
            print(f"Fetched {len(parsed_signals)} article-like signals.")
        except Exception as error:
            errors.append(f"{cpv_division}: {error}")
            print(f"Failed: {error}")

        if request_pause_seconds:
            time.sleep(request_pause_seconds)

    return {
        "signals": signals,
        "errors": errors,
    }


def save_scan_output(result, filename="ted_scan_output.json"):
    output_path = PROJECT_ROOT / filename

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print(f"\nSaved TED output to: {output_path}")


if __name__ == "__main__":
    result = scan_ted_notices()

    print(f"\nTED scan complete. Retrieved {len(result['signals'])} signals.")

    # Print results to terminal
    # for signal in result["signals"]:
    #     print("\n" + "=" * 80)
    #     print(f"Title: {signal['title']}")
    #     print(f"Date: {signal['date']}")
    #     print(f"URL: {signal['url']}")
    #     print(f"External ID: {signal['external_id']}")
    #     print("\nBody:")
    #     print(signal["body"])

    # Save complete result
    save_scan_output(result)
