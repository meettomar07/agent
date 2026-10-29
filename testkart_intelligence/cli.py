"""Command line interface for Testkart Government Exam Intelligence."""

import sys

# Prevent Python 3.13 Windows C-level _asyncio access violation (CPython 3.13 Windows bug)
if sys.platform == "win32" and sys.version_info >= (3, 13):
    sys.modules["_asyncio"] = None

import argparse
from testkart_intelligence.database.connection import init_db, get_db
from testkart_intelligence.registry.service import SourceRegistryService, seed_sources_if_empty
from testkart_intelligence.discovery.engine import DiscoveryEngine


def cmd_init(args):
    """Initialize database and seed official sources."""
    print("Initializing Testkart database...")
    init_db()
    with get_db() as conn:
        count = seed_sources_if_empty(conn)
    print(f"Database initialized successfully. Seeded/updated {count} official government portals.")


def cmd_sources(args):
    """List or modify registered official sources."""
    service = SourceRegistryService()
    if args.action == "list":
        sources = service.list_sources(enabled_only=args.enabled_only)
        print(f"\n{'CODE':<10} {'STATE':<15} {'CATEGORY':<20} {'ENABLED':<8} {'DOMAIN':<25} {'NAME'}")
        print("-" * 105)
        for s in sources:
            enabled_str = "YES" if s["enabled"] else "NO"
            print(f"{s['code']:<10} {s['state']:<15} {s['category']:<20} {enabled_str:<8} {s['official_domain']:<25} {s['name']}")
        print(f"\nTotal: {len(sources)} sources")
    elif args.action == "enable":
        if not args.code:
            print("Error: --code is required for enable")
            sys.exit(1)
        ok = service.set_enabled(args.code, True)
        print(f"Source {args.code} enabled: {ok}")
    elif args.action == "disable":
        if not args.code:
            print("Error: --code is required for disable")
            sys.exit(1)
        ok = service.set_enabled(args.code, False)
        print(f"Source {args.code} disabled: {ok}")


def cmd_scan(args):
    """Trigger manual discovery scan."""
    print(f"Starting discovery scan (Source: {args.source or 'ALL ENABLED'})...")
    engine = DiscoveryEngine()
    result = engine.run_scan(scan_type="MANUAL", source_code=args.source)
    print("\nScan Results Summary:")
    print(f"  Scan ID:         {result['scan_id']}")
    print(f"  Status:          {result['status']}")
    print(f"  Sources Checked: {result['sources_checked']}")
    print(f"  Notices Found:   {result['notices_found']}")
    print(f"  Errors:          {result['errors_count']}")
    if result["error_summary"]:
        print("\nErrors encountered:")
        for err in result["error_summary"]:
            print(f"  - {err}")


def cmd_status(args):
    """Display system status, scan counts, notices, and draft stats."""
    with get_db() as conn:
        src_count = conn.execute("SELECT count(*) as c FROM official_sources").fetchone()["c"]
        enabled_src = conn.execute("SELECT count(*) as c FROM official_sources WHERE enabled = 1").fetchone()["c"]
        scan_count = conn.execute("SELECT count(*) as c FROM scan_runs").fetchone()["c"]
        notices_count = conn.execute("SELECT count(*) as c FROM canonical_notices").fetchone()["c"]
        articles_count = conn.execute("SELECT count(*) as c FROM blog_articles").fetchone()["c"]
        qa_passed = conn.execute("SELECT count(*) as c FROM blog_articles WHERE status = 'QA_PASSED'").fetchone()["c"]

    print("\n================ Testkart Intelligence Status ================")
    print(f"  Official Sources:       {src_count} total ({enabled_src} active)")
    print(f"  Discovery Scans:        {scan_count} completed")
    print(f"  Canonical Notices:      {notices_count} discovered")
    print(f"  Blog Drafts:            {articles_count} created ({qa_passed} QA passed)")
    print("============================================================\n")


def cmd_serve(args):
    """Start local editorial review dashboard web server."""
    import uvicorn
    from testkart_intelligence.config import settings
    host = args.host or settings.SERVER_HOST
    port = args.port or settings.SERVER_PORT
    print(f"\n=================================================================")
    print(f" Testkart Intelligence - Local Editorial Review Dashboard")
    print(f" URL: http://{host}:{port}")
    print(f" Mode: LOCAL DEVELOPMENT ONLY (LIVE PUBLISHING STRICTLY DISABLED)")
    print(f"=================================================================\n")
    uvicorn.run("testkart_intelligence.api.app:app", host=host, port=port, reload=False)


def cmd_scheduler(args):
    """Run local discovery scheduler in foreground."""
    import time
    from testkart_intelligence.scheduler.job_runner import ScanScheduler
    from testkart_intelligence.config import settings

    scheduler = ScanScheduler()
    print("=================================================================")
    print(" Testkart Intelligence - Twice-Daily Discovery Scan Scheduler")
    print(f" Timezone: {settings.TIMEZONE}")
    print(f" Hours:    {settings.SCAN_HOURS} (Minute: {settings.SCAN_MINUTES:02d})")
    print("=================================================================")
    scheduler.start()
    status = scheduler.get_status()
    print(f"Scheduler active. Next scheduled scan: {status['next_run_time']}")
    print("Press Ctrl+C to terminate.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping scheduler...")
        scheduler.shutdown()
        print("Scheduler stopped cleanly.")


def cmd_triage(args):
    """Run discovery triage, categorization, and recency assessment across canonical notices."""
    from testkart_intelligence.classification.classifier import NoticeClassifier
    print("Running discovery quality audit and notice triage across canonical notices...")
    res = NoticeClassifier.triage_all_notices()
    print("\n================ Discovery Triage Summary ================")
    print(f"  Total Notices Audited:    {res['total_triaged']}")
    print(f"  Duplicate Groups Found:   {res['duplicate_groups_count']} ({res['duplicate_notices_count']} notices)")
    print("\n  Classification Breakdown:")
    for cat, cnt in sorted(res["categories"].items(), key=lambda x: -x[1]):
        print(f"    - {cat:<26}: {cnt}")
    print("\n  Recency Status Breakdown:")
    for rec, cnt in sorted(res["recency"].items(), key=lambda x: -x[1]):
        print(f"    - {rec:<26}: {cnt}")
    print("=========================================================\n")


def main():
    parser = argparse.ArgumentParser(
        prog="testkart",
        description="Testkart Government Exam Intelligence System",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize database and seed official sources")
    p_init.set_defaults(func=cmd_init)

    # triage
    p_triage = subparsers.add_parser("triage", help="Triage, classify, and audit discovered notices")
    p_triage.set_defaults(func=cmd_triage)

    # serve / editorial dashboard
    p_serve = subparsers.add_parser("serve", help="Start local editorial review dashboard web server")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host interface (defaults to 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8000, help="Port (defaults to 8000)")
    p_serve.set_defaults(func=cmd_serve)

    # scheduler
    p_sched = subparsers.add_parser("scheduler", help="Run local twice-daily discovery scheduler in foreground")
    p_sched.set_defaults(func=cmd_scheduler)

    # sources
    p_src = subparsers.add_parser("sources", help="Manage official sources")
    p_src.add_argument("action", choices=["list", "enable", "disable"], default="list", nargs="?")
    p_src.add_argument("--code", help="Source code (e.g. UPSC, SSC)")
    p_src.add_argument("--enabled-only", action="store_true", help="Only show enabled sources")
    p_src.set_defaults(func=cmd_sources)

    # scan
    p_scan = subparsers.add_parser("scan", help="Run discovery scan")
    p_scan.add_argument("--source", help="Scan only specific source code")
    p_scan.set_defaults(func=cmd_scan)

    # status
    p_stat = subparsers.add_parser("status", help="Show system status and statistics")
    p_stat.set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
