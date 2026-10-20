"""Conservative, inspectable context rules; these are labels, not semantic certainty."""
import re
from bisect import bisect_right, bisect_left

SECTION_LABELS = {
    "required": ("requirements", "qualifications", "what you bring", "what we're looking for", "required skills", "technical skills", "skills", "responsibilities"),
    "optional": ("nice to have", "preferred qualifications", "bonus", "preferred skills"),
    "incidental": ("about us", "about the company", "benefits", "perks", "equal opportunity"),
}
REQUIREMENT = re.compile(
    r"\b(experience|proficien\w*|knowledge|familiar\w*|skills?|expertise|must|require[ds]?|"
    r"you (?:will|have)|you'll|ability to)\b", re.I
)
OPTIONAL = re.compile(r"\b(preferred|nice to have|bonus|a plus|optional)\b", re.I)
INCIDENTAL = re.compile(r"\b(equal opportunity|benefits include|our mission|we were founded)\b", re.I)


def section_label(line):
    heading = line.strip().strip("#*: -").casefold()
    for label, headings in SECTION_LABELS.items():
        if heading in headings:
            return label
    return None


def paragraphs(text):
    """Yield paragraphs with the most recent recognized section label."""
    section = "unknown"
    for line in text.splitlines():
        section = section_label(line) or section
        yield line, section


class TextContext:
    def __init__(self, text):
        self.text = text
        # Preserve punctuation inside names such as Node.js and .NET.
        boundaries = list(re.finditer(r"\n|(?<=[.!?])\s+", text))
        self.ends = [0, *(m.end() for m in boundaries)]
        self.starts = [*(m.start() for m in boundaries), len(text)]
        self.sections = []
        self.offsets = []
        self.cues = {}
        section, offset = "unknown", 0
        for line in text.splitlines(keepends=True):
            section = section_label(line) or section
            self.offsets.append(offset)
            self.sections.append(section)
            offset += len(line)

    def evidence(self, start, end):
        left = self.ends[bisect_right(self.ends, start) - 1]
        right = self.starts[bisect_left(self.starts, end)]
        section = self.sections[bisect_right(self.offsets, start) - 1]
        key = (left, right)
        if key not in self.cues:
            sentence = self.text[left:right]
            self.cues[key] = tuple(bool(rule.search(sentence)) for rule in (OPTIONAL, REQUIREMENT, INCIDENTAL))
        return classify(self.text, start, end, left, right, section, self.cues[key])


def classify(text, start, end, left, right, section, cues):
    optional, required, incidental = cues
    prefix = text[max(left, start - 120):start]
    suffix = text[end:min(right, end + 120)]
    # Scope negation to this mention, rather than every skill in its sentence.
    negative_before = re.search(
        r"\b(?:no|without|not)\s+(?:(?:prior|previous|any)\s+)?"
        r"(?:(?:experience|knowledge|expertise)\s+(?:in|with|of)\s+)?$", prefix, re.I
    )
    negative_after = re.match(
        r"\s+(?:(?:experience|knowledge)\s+)?(?:(?:is|are)\s+)?(?:not required|unnecessary)\b", suffix, re.I
    )
    if negative_before or negative_after:
        label = "negated"
    elif optional:
        label = "optional"
    elif required:
        label = "optional" if section == "optional" else "required"
    elif incidental:
        label = "incidental"
    else:
        label = section
    excerpt_start = max(left, start - 160)
    excerpt_end = min(right, max(end, excerpt_start + 400))
    excerpt = text[excerpt_start:excerpt_end].strip()
    return {"text": excerpt, "start": start, "end": end, "classification": label}
