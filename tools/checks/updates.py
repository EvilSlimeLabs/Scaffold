"""Ask the update client what it sees, with nothing swallowed.

    python -m tools.checks.updates
    python -m tools.checks.updates --as 0.9.0
    python -m tools.checks.updates --forget

`updates.available()` returns None for every way of failing -- no network, an
expired timestamp, a root that does not verify, tufup missing -- because the
check runs at every launch and somebody opening Scaffold to build a pack does
not want to hear about it. That is right for the window and useless the moment
something is wrong, because "up to date" and "it broke" look the same.

This runs the same client and lets everything through: what it fetched, what the
metadata claims, what the running version is taken to be, and the whole
traceback when it fails.

**It cannot tell you everything from a checkout.** `updates.ready()` needs a
compiled build, because an update replaces the executable and a checkout has
none to replace. What is checked here is everything up to that: the trusted
root, the server, the metadata, and what the client makes of them.
"""
import argparse
import json
import os
import shutil
import sys
import traceback
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from scaffold import paths
from scaffold import updates
from scaffold import version


def fetched(url):
    """A URL's status and body, without raising."""
    try:
        with urllib.request.urlopen(url, timeout=20) as answer:
            return answer.status, answer.read()
    except urllib.error.HTTPError as wrong:
        return wrong.code, b""
    except Exception as wrong:
        return None, str(wrong).encode()


def say(label, value):
    print("  %-26s %s" % (label, value))


def report_paths(pretend):
    print("\n-- what this build thinks it is " + "-" * 34)
    say("version.read()", version.read())
    say("running as", "a compiled build" if paths.frozen() else "a checkout")
    say("updates.ready()", updates.ready())
    if not updates.ready():
        say("  running_file()", updates.running_file())
        say("  trusted root on disk", os.path.isfile(updates.trusted_root()))
        try:
            import tufup.client                                # noqa: F401
            say("  tufup importable", True)
        except ImportError as wrong:
            say("  tufup importable", "no: %s" % wrong)
    say("offered channel", updates.channel(pretend) or "final releases only")
    say("metadata kept in", updates.working_dir("metadata"))


def report_server():
    print("\n-- what the server is serving " + "-" * 36)
    ok = True
    for name in ("root.json", "timestamp.json", "snapshot.json", "targets.json"):
        status, body = fetched(updates.METADATA_URL + name)
        say(name, "%s  %d bytes" % (status, len(body)))
        ok = ok and status == 200
    if not ok:
        print("\n  Some metadata is not being served. Check that GitHub Pages "
              "is set to\n  deploy from the gh-pages branch, folder / (root), "
              "and that the last\n  publish was pushed.")
        return None

    _status, body = fetched(updates.METADATA_URL + "targets.json")
    signed = json.loads(body)["signed"]
    print("\n  releases signed in:")
    for name in sorted(signed["targets"]):
        print("      %s" % name)
    say("targets expire", signed["expires"])
    for name in ("timestamp", "snapshot"):
        _s, raw = fetched(updates.METADATA_URL + name + ".json")
        say("%s expires" % name, json.loads(raw)["signed"]["expires"])
    return signed


def report_root():
    """Whether the root this build trusts is the root the server signs with.

    A build carries the root it was compiled with. Sign a release with keys
    that root does not name -- a rotation, or a second `--init-trust` over the
    top of the first -- and every check fails verification and comes back as
    "up to date".
    """
    print("\n-- the root of trust " + "-" * 45)
    here = updates.trusted_root()
    if not os.path.isfile(here):
        say("shipped root", "MISSING at %s" % here)
        return
    with open(here, encoding="utf-8") as f:
        mine = json.load(f)
    status, body = fetched(updates.METADATA_URL + "root.json")
    say("shipped root version", mine["signed"].get("version"))
    if status != 200:
        say("server root", "not served (%s)" % status)
        return
    theirs = json.loads(body)
    say("server root version", theirs["signed"].get("version"))
    same = sorted(mine["signed"]["keys"]) == sorted(theirs["signed"]["keys"])
    say("same signing keys", same)
    if not same:
        print("\n  The build was compiled against different keys from the ones "
              "signing\n  the server's metadata. Every check will fail "
              "verification and report\n  'up to date'. Rebuild after copying "
              "the current root into\n  scaffold/trust/, or re-publish with "
              "the keys the build carries.")


def report_client(pretend):
    print("\n-- what the client makes of it " + "-" * 35)
    kept = updates.working_dir("metadata")
    if os.path.isdir(kept):
        say("kept metadata", ", ".join(sorted(os.listdir(kept))) or "(empty)")
    else:
        say("kept metadata", "(nothing yet)")
    try:
        client = updates.client()
        if pretend:
            ## the client compares against the version it was handed, so a
            ## checkout can ask what a given release would be offered
            client.current_archive_info = None
            client.current_version = pretend
        found = client.check_for_updates(pre=updates.channel(pretend))
    except Exception:
        print("\n  the check raised, which the window would report as "
              "'up to date':\n")
        traceback.print_exc()
        return
    say("check_for_updates", found.version if found else "nothing newer")
    if found:
        print("\n  An update IS visible to the client. If the window still "
              "says it is up to\n  date, the difference is the running "
              "version: the window compares against\n  what "
              "version.read() reports inside the executable.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Ask the update client what it sees, without the "
                    "silence that a launch check needs.")
    ap.add_argument("--as", dest="pretend", metavar="VERSION",
                    help="ask what would be offered to this version, for "
                         "checking from a checkout")
    ap.add_argument("--forget", action="store_true",
                    help="delete the kept metadata and downloads, so the next "
                         "check starts from the root the build carries")
    args = ap.parse_args(argv)

    if args.forget:
        for part in ("metadata", "targets"):
            where = updates.working_dir(part)
            if os.path.isdir(where):
                shutil.rmtree(where)
                print("removed %s" % where)
        print("The next check starts from the shipped root.")
        return 0

    report_paths(args.pretend)
    report_server()
    report_root()
    report_client(args.pretend)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
