import re

import pytest

from backend.database import DATA, split_sections
from backend.tests.test_workflow import start


def read(client, claim_id, document, section):
    return client.post(
        f"/api/claims/{claim_id}/reads", json={"document": document, "section": section}
    )


def search(client, query):
    return client.get("/api/sections/search", params={"query": query}).json()


def test_list_sections(client):
    sections = client.get("/api/sections").json()
    assert len(sections) == 26
    assert [s["document"] for s in sections] == ["policy_wording"] * 12 + [
        "claims_manual"
    ] * 14
    assert sections[0] == {
        "document": "policy_wording",
        "section": 1,
        "title": "Your plan",
    }
    assert sections[9]["title"] == "How we work out your payment"
    assert sections[12 + 8] == {
        "document": "claims_manual",
        "section": 9,
        "title": "Repeat claims",
    }
    assert "text" not in sections[0]


@pytest.mark.parametrize(
    ("document", "name"),
    [("policy_wording", "policy_wording.md"), ("claims_manual", "claims_manual.md")],
)
def test_sections_hold_the_text_under_each_heading(client, document, name):
    markdown = (DATA / name).read_text(encoding="utf-8")
    headings = re.findall(r"^## (\d+)\. (.+)$", markdown, re.MULTILINE)
    start(client, "CLM-1001")
    for number, title in headings:
        section = read(client, "CLM-1001", document, int(number)).json()
        assert section["title"] == title
        after = markdown.split(f"## {number}. {title}\n", 1)[1]
        assert after.lstrip().startswith(section["text"])
        assert "\n## " not in section["text"]


def test_split_sections():
    markdown = (
        "# Title\n\nIntro.\n\n## 1. One\n\nFirst.\n\n## 2. Two\n\nSecond.\nMore.\n"
    )
    assert split_sections(markdown) == [
        (1, "One", "First."),
        (2, "Two", "Second.\nMore."),
    ]


def test_search_finds_the_wild_animals_note(client):
    results = search(client, "giraffe")
    assert [(r["document"], r["section"], r["title"]) for r in results] == [
        ("claims_manual", 7, "Interpretation notes")
    ]
    assert len(results[0]["matches"]) == 1
    assert results[0]["matches"][0].startswith("**Wild animals.**")


def test_search_ranks_by_the_words_found(client):
    results = search(client, "meals without receipts")
    assert len(results) == 5
    assert (results[0]["document"], results[0]["section"]) == ("claims_manual", 10)


def test_search_ignores_short_and_common_words(client):
    assert search(client, "zebra") == []
    assert search(client, "the and of a") == []
    assert search(client, "") == []


def test_read_section(client):
    start(client, "CLM-1001")
    response = read(client, "CLM-1001", "policy_wording", 3)
    assert response.status_code == 200
    section = response.json()
    assert (section["document"], section["section"]) == ("policy_wording", 3)
    assert section["title"] == "Trip Delay"
    assert "waiting period" in section["text"]


def test_sections_read_are_noted_on_the_claim(client):
    start(client, "CLM-1001")
    read(client, "CLM-1001", "policy_wording", 3)
    read(client, "CLM-1001", "claims_manual", 10)
    read(client, "CLM-1001", "policy_wording", 3)
    assert client.get("/api/claims/CLM-1001").json()["sections_read"] == [
        {"document": "policy_wording", "section": 3, "title": "Trip Delay"},
        {"document": "claims_manual", "section": 10, "title": "Meals without receipts"},
    ]
    assert client.get("/api/claims/CLM-1002").json()["sections_read"] == []


def test_read_section_needs_a_claim_in_progress(client):
    response = read(client, "CLM-1001", "policy_wording", 3)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 is not in progress"
    assert read(client, "CLM-9999", "policy_wording", 3).status_code == 404


def test_read_section_needs_a_known_section(client):
    start(client, "CLM-1001")
    response = read(client, "CLM-1001", "policy_wording", 99)
    assert response.status_code == 404
    assert response.json()["detail"] == "The policy wording has no section 99"
    assert read(client, "CLM-1001", "brochure", 1).status_code == 422
    assert client.get("/api/claims/CLM-1001").json()["sections_read"] == []
