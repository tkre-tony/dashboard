#!/usr/bin/env python3
"""li_paste_safe.py — S395 (v2 S406). Make LinkedIn post copy survive copy-paste.

LinkedIn's editor (and copying from rendered chat) can collapse empty lines,
so paragraph breaks vanish on paste. Fix: every empty line gets one U+2800
(Braille blank), which renders as nothing but is not "empty", so the break
survives. Also: CRLF -> LF, trailing spaces stripped, single trailing newline.

Then runs the standard preflight and prints the LinkedIn UTF-16 count.

v2 (S406), Tony's rule of 18th Oct 2026 (supersedes L-SOCIAL-5 rule 4): an article
post carries "Read the full article on PropertyAtlas: <URL>" in the body, as the
first line after the lead paragraph; no first comment. A PropertyAtlas article URL
anywhere else is an issue. URLs are ignored by the million, date and first-person
checks (slugs like "s626-2m" no longer trip the million rule).

Usage:  python3 tools/li_paste_safe.py in.txt [out.txt]   (default: in place)
Exit 1 on any preflight issue or > 3,000 units.
"""
import re, sys

BLANK = "\u2800"
REF = ("If you or someone in your network is looking to lease a space, acquire an asset "
       "or explore a sale, I would be delighted to have a conversation and would greatly "
       "appreciate any referrals.")

def paste_safe(text):
    lines = [l.rstrip() for l in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1].strip(BLANK + " ") == "":
        lines.pop()
    return "\n".join(BLANK if l.strip(BLANK + " ") == "" else l for l in lines) + "\n"

def u16(s):
    return sum(2 if ord(c) > 0xFFFF else 1 for c in s)

READ_LINE = "Read the full article on PropertyAtlas: "
URL_RE = re.compile(r"https?://\S+|propertyatlas\.sg/\S*")

def _is_bold_headline(block):
    """Block written mostly in Unicode Mathematical Bold (the pseudo-headline)."""
    letters = [c for c in block if c.isalpha()]
    return bool(letters) and sum(0x1D400 <= ord(c) <= 0x1D7FF for c in letters) / len(letters) > 0.6

def article_link_issues(s):
    """Rule of 18th Oct: the article URL sits on the Read line, directly after the lead
    paragraph. The lead is the first paragraph that is neither the standing intro
    ('PropertyAtlas Newsroom — …') nor the bold pseudo-headline."""
    issues, notes = [], []
    blocks = [b.strip("\n") for b in re.split(r"\n(?:[ \u2800]*\n)+", s) if b.strip(BLANK + " \n")]
    url_blocks = [i for i, b in enumerate(blocks) if re.search(r"propertyatlas\.sg/news/", b)]
    if not url_blocks:
        notes.append("no article link (fine for reshares; article posts need the Read line)")
        return issues, notes
    for i in url_blocks:
        if not blocks[i].startswith(READ_LINE + "https://propertyatlas.sg/news/") or "\n" in blocks[i]:
            issues.append(f"article URL is not on its own line in the form '{READ_LINE}https://propertyatlas.sg/news/…'")
    if sum(len(re.findall(r"propertyatlas\.sg/news/", blocks[i])) for i in url_blocks) > 1:
        issues.append("article URL appears more than once; once, on the Read line")
    body = [i for i, b in enumerate(blocks)
            if not b.startswith("PropertyAtlas Newsroom") and not _is_bold_headline(b)]
    lead = body[0] if body else None
    if lead is None or url_blocks[0] != lead + 1:
        issues.append("Read line is not directly after the lead paragraph (rule of 18th Oct)")
    return issues, notes

def preflight(s):
    issues, notes = article_link_issues(s)
    s = URL_RE.sub(" ", s)            # remaining checks ignore URLs
    if re.search(r"[$€£]?\d[\d.,]*m\b", s):
        issues.append("abbreviated million (L-SOCIAL-9)")
    if re.search(r"\b\d{1,2} (January|February|March|April|May|June|July|August|"
                 r"September|October|November|December)\b", s):
        issues.append("non-ordinal date (L-SOCIAL-10)")
    if re.search(r"\b(I|my|me|I'm|I've|I'd)\b", s.replace(REF, "")):
        issues.append("first person outside referral line (L-SOCIAL-15)")
    if re.search(r"(^|\s)#\w", s):
        issues.append("hashtag (Tony's ruling 27 Sep 2026)")
    return issues, notes

if __name__ == "__main__":
    src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else src
    out = paste_safe(open(src, encoding="utf-8").read())
    open(dst, "w", encoding="utf-8", newline="\n").write(out)
    issues, notes = preflight(out)
    n = u16(out)                      # count the full text, URLs included
    if n > 3000:
        issues.append(f"OVER 3,000 units: {n}")
    print(f"{dst}: {n} UTF-16 units · {out.count(BLANK)} protected blank lines")
    for i in issues: print("  ISSUE:", i)
    for m in notes: print("  note:", m)
    sys.exit(1 if issues else 0)
