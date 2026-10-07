"""`fdip` on the command line: migrate, seed, run one document, show usage.

`fdip run` exists for the reason the README leans on it: it proves the pipeline
works without a browser, a cookie or a worker process. When something is broken,
the first question is whether it is the pipeline or the API, and this answers it
in one command.

It prints field paths, statuses and page numbers -- never the extracted values.
A terminal scrollback is a log (rule 2.13), and `--show-values` has to be asked
for explicitly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fdip import PIPELINE_VERSION, __version__
from fdip.adapters.db import create_all, create_db_engine, transaction
from fdip.adapters.providers import build_model_stack
from fdip.adapters.repository import GlobalRepository, ProjectRepository
from fdip.adapters.seed import DEV_EMAIL, seed
from fdip.adapters.storage import BlobStore, sha256_bytes
from fdip.config import Settings, load_settings
from fdip.domain.statuses import JobState, Status
from fdip.pipeline.runner import JobContext, run_id_for, run_job
from fdip.worker import full_template_spec


def _settings(args: argparse.Namespace) -> Settings:
    settings = load_settings()
    settings.ensure_dirs()
    return settings


def _dev_project(engine: Any, settings: Settings) -> tuple[str, str]:
    """The dev user's first project, creating it if seeding has not run."""
    result = seed(engine, settings)
    if result.project_id:
        return str(result.user_id), str(result.project_id)
    with transaction(engine) as connection:
        repo = GlobalRepository(connection)
        user = repo.user_by_email(DEV_EMAIL)
        if user is None:
            raise SystemExit(
                "no dev account; set FDIP_DEV_SEED=1 and a non-live provider mode"
            )
        projects = repo.projects_for(str(user["id"]))
        if not projects:
            raise SystemExit("the dev account has no project")
        return str(user["id"]), str(projects[0]["id"])


def cmd_migrate(args: argparse.Namespace) -> int:
    settings = _settings(args)
    engine = create_db_engine(settings.db_url)
    create_all(engine)
    print("schema created at %s" % settings.db_url)
    engine.dispose()
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    settings = _settings(args)
    engine = create_db_engine(settings.db_url)
    create_all(engine)
    result = seed(engine, settings)
    print("template %s" % result.template_id)
    if result.user_id:
        print("dev user %s, project %s" % (DEV_EMAIL, result.project_id))
    else:
        print("no dev account (FDIP_DEV_SEED off, or live mode)")
    engine.dispose()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run one document through the whole pipeline, in process."""
    path = Path(args.document)
    if not path.is_file():
        raise SystemExit("no such file: %s" % path)
    settings = _settings(args)
    engine = create_db_engine(settings.db_url)
    create_all(engine)
    _, project_id = _dev_project(engine, settings)

    data = path.read_bytes()
    digest = sha256_bytes(data)
    _, blob_path = BlobStore(settings.blob_dir).put(data)

    with transaction(engine) as connection:
        repo = ProjectRepository(connection, project_id)
        existing = repo.document_by_hash(digest)
        document_id = str(existing["id"]) if existing else repo.create_document(
            filename=path.name, mime="application/pdf", byte_size=len(data),
            sha256=digest, blob_path=blob_path, status=Status.PROCESSING.value,
            origin="cli",
        )
        job_id = repo.create_job(
            document_id=document_id, run_id=run_id_for(digest, "analysis"),
            state=JobState.RECEIVED.value, mode="cli",
        )
        spent = repo.month_ai_cost()

    models = build_model_stack(settings, already_spent_usd=spent)
    print("mode=%s model=%s thinking=%s pipeline=%s"
          % (settings.provider_mode, settings.model, settings.extract_thinking,
             PIPELINE_VERSION))
    outcome = run_job(JobContext(
        engine=engine, settings=settings, models=models, project_id=project_id,
        document_id=document_id, job_id=job_id, blob_path=blob_path,
        spec=full_template_spec(), purpose="analysis",
    ), digest)

    if not outcome.get("extraction_id"):
        print("status=%s error_code=%s"
              % (outcome.get("status"), outcome.get("error_code")))
        engine.dispose()
        return 1

    with transaction(engine) as connection:
        repo = ProjectRepository(connection, project_id)
        extraction = repo.extraction(str(outcome["extraction_id"]))
        fields = repo.fields(str(outcome["extraction_id"]))
        validations = repo.validations(str(outcome["extraction_id"]))
        evidence = repo.evidence_for([str(row["id"]) for row in fields])

        assert extraction is not None
        print()
        print("document  %s" % document_id)
        print("extraction %s v%d" % (extraction["id"], extraction["version"]))
        print("type      %s" % extraction["document_type"])
        print("status    %s" % extraction["status"])
        print("tokens    in %d out %d, $%.5f, %.1fs"
              % (extraction["input_tokens"], extraction["output_tokens"],
                 extraction["cost_usd"], extraction["seconds"]))
        print()
        print("%-34s %-14s %-11s %s"
              % ("FIELD", "STATUS", "MATCH", "EVIDENCE"))
        print("-" * 78)
        for row in fields:
            boxes = evidence.get(str(row["id"]), [])
            where = ", ".join(
                "p%d" % item["page"] for item in boxes[:3]
            ) or "-"
            line = "%-34s %-14s %-11s %s" % (
                str(row["path"])[:34], row["status"], row["match"], where,
            )
            if args.show_values:
                line += "  = " + str(row["value_json"])[:40]
            print(line)
        if validations:
            print()
            print("VALIDATION")
            for row in validations:
                print("  [%s] %s: %s" % (row["severity"], row["code"], row["message"]))
        if extraction["reasons"]:
            print()
            print("REASONS")
            for reason in extraction["reasons"]:
                print("  " + str(reason))
    engine.dispose()
    return 0 if outcome.get("status") == Status.COMPLETED.value else 0


def cmd_usage(args: argparse.Namespace) -> int:
    settings = _settings(args)
    engine = create_db_engine(settings.db_url)
    create_all(engine)
    _, project_id = _dev_project(engine, settings)
    with transaction(engine) as connection:
        repo = ProjectRepository(connection, project_id)
        rows = repo.usage(args.month)
    print(json.dumps({
        "month": args.month or "this month",
        "documents": sum(int(r["documents"]) for r in rows),
        "pages": sum(int(r["pages"]) for r in rows),
        "ai_cost_usd": round(sum(float(r["ai_cost_usd"]) for r in rows), 6),
    }, indent=2))
    engine.dispose()
    return 0


def cmd_openapi(args: argparse.Namespace) -> int:
    """Write `openapi.json`. The UI agent reads that file, not a running server."""
    from fdip.api.app import openapi_document

    target = Path(args.out)
    document = openapi_document()
    target.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("wrote %s (%d paths)" % (target, len(document.get("paths", {}))))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fdip", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="create the schema").set_defaults(fn=cmd_migrate)
    sub.add_parser("seed", help="seed the template and the dev account").set_defaults(
        fn=cmd_seed
    )

    run = sub.add_parser("run", help="run one document through the pipeline")
    run.add_argument("document")
    run.add_argument("--schema", default="invoice@1",
                     help="accepted for symmetry with the API; the CLI always"
                          " runs the full template, which is what an interactive"
                          " upload does")
    run.add_argument("--show-values", action="store_true",
                     help="print extracted values; off by default because a"
                          " terminal scrollback is a log (rule 2.13)")
    run.set_defaults(fn=cmd_run)

    usage = sub.add_parser("usage", help="pages and AI cost for a month")
    usage.add_argument("--month", default=None, help="YYYY-MM")
    usage.set_defaults(fn=cmd_usage)

    openapi = sub.add_parser("openapi", help="write openapi.json")
    openapi.add_argument("--out", default="openapi.json")
    openapi.set_defaults(fn=cmd_openapi)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
