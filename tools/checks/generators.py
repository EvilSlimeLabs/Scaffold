"""Run every generator twice and say what did not come out the same.

    python -m tools.checks.generators

**A generator has to say what a table is, never what to change it by.** One
that reads a table, adjusts it and writes it back is correct exactly once. Run
again it is wrong, and `build.py` regenerates everything before every compile,
so the answer depends on how many times the build has run. A carved pumpkin
faced a different way on alternate releases for exactly that: `faces.py` added
a half turn to its own output each time.

Nothing catches that by reading the source. Deriving one family from another is
ordinary and safe -- `faces.py` builds `azalea` and `vault` out of `cube` --
and telling that apart from a table folded back into itself is a judgement, not
a pattern. Running the generators twice settles it outright.

**This rewrites the lookup tables**, twice, which is why it is a command rather
than a test: a test that leaves the tree changed when it fails is worse than no
test. The tables end up in whatever state the second run produced, which for a
well behaved generator is the state they were already in.
"""
import argparse
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

## What a generator is allowed to write. Anything under here that differs
## between two runs is the fault this looks for.
WATCHED = (os.path.join("scaffold", "lookups"),
           os.path.join("scaffold", "Vanilla_Resource_Pack"),
           os.path.join("scaffold", "fonts"),
           os.path.join("scaffold", "images"))


def fingerprints():
    """Every watched file and what it holds, right now."""
    seen = {}
    for folder in WATCHED:
        base = os.path.join(ROOT, folder)
        for here, _dirs, files in os.walk(base):
            for name in files:
                path = os.path.join(here, name)
                with open(path, "rb") as f:
                    seen[os.path.relpath(path, ROOT)] = \
                        hashlib.sha256(f.read()).hexdigest()
    return seen


def generate(what):
    print(">> %s" % what)
    done = subprocess.run([sys.executable, "-m", "tools.generate"],
                          cwd=ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        sys.stdout.write(done.stdout)
        sys.stderr.write(done.stderr)
        sys.exit("the generators failed, so there is nothing to compare")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Run the generators twice and compare what they wrote.")
    ap.parse_args(argv)

    generate("first run")
    once = fingerprints()
    generate("second run")
    twice = fingerprints()

    moved = sorted(p for p in once if p in twice and once[p] != twice[p])
    gone = sorted(p for p in once if p not in twice)
    fresh = sorted(p for p in twice if p not in once)

    print("\nfiles watched : %d" % len(twice))
    for label, names in (("changed on the second run", moved),
                         ("written only by the first", gone),
                         ("written only by the second", fresh)):
        print("%-27s: %d" % (label, len(names)))
        for name in names[:20]:
            print("    %s" % name)
        if len(names) > 20:
            print("    ... and %d more" % (len(names) - 20))

    if moved or gone or fresh:
        print("\nA generator is folding a table back into itself. Find the one "
              "that reads what it writes and give it the value outright.")
        return 1
    print("\nEvery generator wrote the same thing twice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
