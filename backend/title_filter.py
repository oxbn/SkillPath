"""Shared literal/regex title filtering with a total execution budget."""
import time

import regex

MAX_FILTER_LENGTH = 200
FILTER_TIMEOUT = 0.1


class TitleFilterError(ValueError):
    pass


def filter_titles(postings, title=None, regex_mode=False):
    if not title:
        return postings
    if len(title) > MAX_FILTER_LENGTH:
        raise TitleFilterError(f"Title filter must be at most {MAX_FILTER_LENGTH} characters.")
    if not regex_mode:
        needle = title.casefold()
        return [p for p in postings if needle in p["title"].casefold()]
    try:
        pattern = regex.compile(title, regex.IGNORECASE)
    except regex.error as error:
        raise TitleFilterError(f"Bad title filter: {error}") from error
    deadline = time.monotonic() + FILTER_TIMEOUT
    matches = []
    try:
        for posting in postings:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if pattern.search(posting["title"], timeout=remaining):
                matches.append(posting)
    except TimeoutError as error:
        raise TitleFilterError("Title regex exceeded its time limit. Use a simpler expression.") from error
    return matches
