import pytest

from backend.title_filter import TitleFilterError, filter_titles


def test_literal_search_does_not_interpret_regex():
    postings = [{"title": "C++ Engineer"}, {"title": "Data Engineer"}]
    assert filter_titles(postings, "C++") == postings[:1]
    assert filter_titles(postings, "engineer|data") == []
    assert filter_titles(postings, "engineer|data", True) == postings


@pytest.mark.parametrize("title", ["[", "a" * 201])
def test_invalid_filters(title):
    with pytest.raises(TitleFilterError):
        filter_titles([{"title": "Engineer"}], title, True)


def test_pathological_regex_is_interrupted():
    with pytest.raises(TitleFilterError, match="time limit"):
        filter_titles([{"title": "a" * 100000 + "!"}], "(a+)+$", True)
