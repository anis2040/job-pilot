"""Tests for job.fetcher_utils.strip_tags — HTML→clean-text for all providers."""
from job.fetcher_utils import strip_tags, clip_description, LIST_DESC_LIMIT, FULL_DESC_LIMIT


def test_unescapes_entities():
    assert strip_tags("Goods &amp; Services") == "Goods & Services"
    assert "&nbsp;" not in strip_tags("a&nbsp;b")
    assert strip_tags("a&nbsp;&nbsp;b") == "a b"  # nbsp normalized + collapsed


def test_list_items_become_single_bullets():
    out = strip_tags("<ul><li>Build X</li><li>Do Y</li></ul>")
    assert out == "• Build X\n• Do Y"  # no double-spacing between bullets


def test_block_tags_become_newlines():
    assert strip_tags("<p>About</p><p>Team</p>") == "About\nTeam"
    assert strip_tags("Line1<br>Line2") == "Line1\nLine2"


def test_title_stays_single_line():
    # strip_tags also runs on titles — must not inject newlines when there are
    # no block tags, only unescape.
    assert strip_tags("Senior Engineer at Acme &amp; Co") == "Senior Engineer at Acme & Co"


def test_collapses_space_runs():
    assert strip_tags("challenges   for    some") == "challenges for some"


def test_idempotent_on_clean_text():
    once = strip_tags("R&amp;D team")
    assert once == "R&D team"
    assert strip_tags(once) == "R&D team"  # already-clean text unchanged


def test_empty_safe():
    assert strip_tags("") == ""
    assert strip_tags(None) == ""


# ── clip_description ────────────────────────────────────────────────────────────

def test_clip_description_defaults_to_uncapped():
    long = "x" * 9000
    assert clip_description(long) == long  # LIST_DESC_LIMIT=0 means no cap


def test_clip_description_explicit_limit_zero_is_uncapped():
    long = "y" * 9000
    assert clip_description(long, 0) == long


def test_clip_description_explicit_limit_caps():
    long = "z" * 9000
    assert len(clip_description(long, 500)) == 500


def test_clip_description_empty_and_none_safe():
    assert clip_description("") == ""
    assert clip_description(None) == ""
