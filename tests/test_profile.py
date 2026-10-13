"""Changing your own password, and seeing what has happened on your account.

Until now a user who wanted a new password had to ask the owner to run a
command on the server, and nothing showed them what had been done with their
documents. Both are defensible for a five-person pilot and not for customers.

There is still **no forgotten-password flow**, because that needs email, token
storage and expiry. The product says so plainly instead of pretending: see
`test_the_ui_warns_that_there_is_no_self_service_reset`.
"""
from __future__ import annotations

from typing import Any

from fdip.adapters import keys as key_tools

CURRENT = "devpass"
NEXT = "a-much-longer-password"


def _me(client: Any) -> dict[str, Any]:
    response = client.get("/v1/auth/me")
    assert response.status_code == 200, response.text
    return response.json()


# --- changing your own password ---------------------------------------------


def test_a_user_can_change_their_own_password(client: Any) -> None:
    """The whole point: no server access required.

    Afterwards the old password must stop working, which is the half of this
    that is easy to get wrong — updating the hash while leaving a stale session
    valid would look like success and be a security bug.
    """
    changed = client.post("/v1/auth/password", json={
        "current_password": CURRENT, "new_password": NEXT,
    })
    assert changed.status_code == 204, changed.text

    client.post("/v1/auth/logout")
    stale = client.post("/v1/auth/login", json={
        "email": "dev@fdip.local", "password": CURRENT,
    })
    assert stale.status_code == 401, "the old password still works"

    fresh = client.post("/v1/auth/login", json={
        "email": "dev@fdip.local", "password": NEXT,
    })
    assert fresh.status_code == 200, fresh.text

    # Put it back, so the shared fixture account is unchanged for other tests.
    client.post("/v1/auth/password", json={
        "current_password": NEXT, "new_password": CURRENT,
    })


def test_the_current_password_is_required_and_checked(client: Any) -> None:
    """Otherwise anyone with a borrowed session takes the account permanently."""
    wrong = client.post("/v1/auth/password", json={
        "current_password": "not-the-password", "new_password": NEXT,
    })
    assert wrong.status_code == 403
    assert wrong.json()["code"] == "password_incorrect"

    # And the password is unchanged.
    client.post("/v1/auth/logout")
    assert client.post("/v1/auth/login", json={
        "email": "dev@fdip.local", "password": CURRENT,
    }).status_code == 200


def test_a_new_password_must_meet_the_policy(client: Any) -> None:
    short = client.post("/v1/auth/password", json={
        "current_password": CURRENT, "new_password": "short",
    })
    assert short.status_code == 422
    assert str(key_tools.MIN_PASSWORD_LENGTH) in short.text


def test_changing_a_password_needs_a_session(anonymous: Any) -> None:
    refused = anonymous.post("/v1/auth/password", json={
        "current_password": CURRENT, "new_password": NEXT,
    })
    assert refused.status_code == 401


def test_the_new_password_never_appears_in_a_log(client: Any, caplog: Any) -> None:
    """Rule 2.13 covers document content; a password deserves the same."""
    import logging

    caplog.set_level(logging.DEBUG)
    client.post("/v1/auth/password", json={
        "current_password": CURRENT, "new_password": NEXT,
    })
    client.post("/v1/auth/password", json={
        "current_password": NEXT, "new_password": CURRENT,
    })

    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert NEXT not in logged
    assert CURRENT not in logged


# --- account activity --------------------------------------------------------


def test_activity_lists_what_happened_on_this_project(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """Read-only, and already recorded — this exposes `audit_events`, which the
    pipeline has been writing all along."""
    document_id, _ = upload("invoice_digital")
    run_worker(client.app.state.fdip.engine)

    response = client.get("/v1/activity")
    assert response.status_code == 200, response.text
    body = response.json()

    actions = [entry["action"] for entry in body["items"]]
    assert "uploaded" in actions, actions
    entry = next(e for e in body["items"] if e["action"] == "uploaded")
    assert entry["object_type"] == "document"
    assert entry["object_id"] == document_id
    assert entry["created_at"]
    assert entry["actor"]

    # Newest first: an activity list read bottom-up is no use.
    stamps = [e["created_at"] for e in body["items"]]
    assert stamps == sorted(stamps, reverse=True)


def test_activity_carries_no_document_content(
    client: Any, upload: Any, run_worker: Any
) -> None:
    """The audit detail holds ids, codes and field paths. Never a value.

    This is the same rule as the logging one, applied to something a user can
    actually read in a browser.
    """
    document_id, _ = upload("invoice_digital")
    run_worker(client.app.state.fdip.engine)
    analysis = client.get("/v1/documents/%s/analysis" % document_id).json()
    client.post("/v1/extractions/%s/corrections" % analysis["extraction_id"], json={
        "changes": [{"path": "total", "value": "9999.00"}], "reason": "typo",
    })

    text = client.get("/v1/activity").text
    for content in ("INV-2026-0417", "SOUTHERN STEEL", "2142.72", "9999.00"):
        assert content not in text, content
    # The path is fine, and is the useful part.
    assert "total" in text


def test_activity_is_scoped_to_the_project_and_needs_a_session(
    client: Any, anonymous: Any
) -> None:
    assert anonymous.get("/v1/activity").status_code == 401

    other = client.get("/v1/activity?project_id=prj_someone_else")
    assert other.status_code == 404, "a stranger's project must not be readable"


def test_activity_limit_is_bounded(client: Any) -> None:
    """An unbounded list is a way to read the whole table in one request."""
    assert client.get("/v1/activity?limit=0").status_code == 422
    assert client.get("/v1/activity?limit=5000").status_code == 422
    assert client.get("/v1/activity?limit=25").status_code == 200
