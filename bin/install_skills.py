#!/usr/bin/env python3
"""Install the generated skills where an assistant will actually find them.

`out/skills/` is where the emission step writes; ~/.claude/skills is where
Claude Code looks. Copying between them sounds like a job for `cp`, and it
nearly is, except for one thing that breaks the skills silently.

Every skill ends with a mandatory check loop:

    ./framezero check draft.txt --like <handle>

That relative path is correct in the repo and meaningless everywhere else, and
a writer drafting a reel is not sitting in the repo. The command fails, the
agent shrugs, and the one step that keeps a draft honest quietly stops running.
So the installed copy gets the absolute path baked in, while the source keeps
the relative one and stays portable.

  python3 bin/install_skills.py            # install
  python3 bin/install_skills.py --dry-run  # show what would happen
  python3 bin/install_skills.py --uninstall
"""
import argparse, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "out" / "skills"
DEST = pathlib.Path.home() / ".claude" / "skills"
CLI = ROOT / "framezero"

# Only the command form is rewritten. Prose that mentions the tool by name is
# left alone -- "`./framezero hooks` now reports it at 3/15" is a sentence
# about a measurement, not an instruction to run anything, and expanding it to
# an absolute path there just makes the skill harder to read.
CMD = re.compile(r"(?<![`\w])\./framezero(?=\s+\S)")


def targets():
    if not SRC.is_dir():
        sys.exit(f"nothing to install: {SRC} does not exist — "
                 "generate the skills first (see prompts/emit.md)")
    out = sorted(d for d in SRC.iterdir()
                 if d.is_dir() and (d / "SKILL.md").is_file())
    if not out:
        sys.exit(f"no skills in {SRC} — a skill is a directory with a SKILL.md")
    return out


def install(dry):
    n_files = n_rewritten = 0
    for d in targets():
        dst = DEST / d.name
        print(f"  {d.name} -> {dst}")
        if not dry:
            shutil.rmtree(dst, ignore_errors=True)
            dst.mkdir(parents=True)
        for f in sorted(d.rglob("*")):
            if f.is_dir():
                continue
            rel = f.relative_to(d)
            n_files += 1
            if f.suffix == ".md":
                text = f.read_text()
                new, k = CMD.subn(str(CLI), text)
                if k:
                    n_rewritten += k
                if not dry:
                    (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                    (dst / rel).write_text(new)
            elif not dry:
                (dst / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst / rel)
    verb = "would install" if dry else "installed"
    print(f"\n  {verb} {len(targets())} skills, {n_files} files, "
          f"{n_rewritten} command paths made absolute")
    if not dry:
        print(f"  remove them with: python3 {pathlib.Path(__file__).name} --uninstall")


def uninstall(dry):
    gone = 0
    for d in targets():
        dst = DEST / d.name
        if dst.exists():
            print(f"  removing {dst}")
            gone += 1
            if not dry:
                shutil.rmtree(dst)
    print(f"\n  {'would remove' if dry else 'removed'} {gone} skills")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()
    print(f"  source: {SRC}\n  dest:   {DEST}\n")
    (uninstall if a.uninstall else install)(a.dry_run)


if __name__ == "__main__":
    main()
