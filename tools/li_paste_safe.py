#!/usr/bin/env python3
"""li_paste_safe.py — S395. Make LinkedIn post copy survive copy-paste.

LinkedIn's editor (and copying from rendered chat) can collapse empty lines,
so paragraph breaks vanish on paste. Fix: every empty line gets one U+2800
(Braille blank), which renders as nothing but is not "empty", so the break
survives. Also: CRLF -> LF, trailing spaces stripped, single trailing newline.

Then runs the standard preflight and prints the LinkedIn UTF-16 count.

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

def preflight(s):
    issues = []
    if re.search(r"propertyatlas\.sg/news/", s):
        issues.append("PropertyAtlas article URL in body (L-SOCIAL-5)")
    if re.search(r"[$€£]?\d[\d.,]*m\b", s):
        issues.append("abbreviated million (L-SOCIAL-9)")
    if re.search(r"\b\d{1,2} (January|February|March|April|May|June|July|August|"
                 r"September|October|November|December)\b", s):
        issues.append("non-ordinal date (L-SOCIAL-10)")
    if re.search(r"\b(I|my|me|I'm|I've|I'd)\b", s.replace(REF, "")):
        issues.append("first person outside referral line (L-SOCIAL-15)")
    if re.search(r"(^|\s)#\w", s):
        issues.append("hashtag (Tony's ruling 27 Sep 2026)")
    n = u16(s)
    if n > 3000:
        issues.append(f"OVER 3,000 units: {n}")
    return n, issues

if __name__ == "__main__":
    src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else src
    out = paste_safe(open(src, encoding="utf-8").read())
    open(dst, "w", encoding="utf-8", newline="\n").write(out)
    n, issues = preflight(out)
    print(f"{dst}: {n} UTF-16 units · {out.count(BLANK)} protected blank lines")
    for i in issues: print("  ISSUE:", i)
    sys.exit(1 if issues else 0)
