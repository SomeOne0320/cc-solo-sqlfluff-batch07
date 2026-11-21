"""Tests covering the LintedFile class and it's methods."""

import logging
from unittest import mock

import pytest

from sqlfluff.core import Linter
from sqlfluff.core.config import FluffConfig
from sqlfluff.core.linter import LintedFile
from sqlfluff.core.linter.patch import FixPatch
from sqlfluff.core.templaters import RawFileSlice


@pytest.mark.parametrize(
    "source_slices,source_patches,raw_source_string,expected_result",
    # NOTE: For all of these examples we're not setting the patch_category
    # of the fix patches. They're not used at this step so irrelevant for
    # testing.
    [
        # Trivial example
        ([slice(0, 1)], [], "a", "a"),
        # Simple replacement
        (
            [slice(0, 1), slice(1, 2), slice(2, 3)],
            [FixPatch(slice(1, 2), "d", "", slice(1, 2), "b", "b")],
            "abc",
            "adc",
        ),
        # Simple insertion
        (
            [slice(0, 1), slice(1, 1), slice(1, 2)],
            [FixPatch(slice(1, 1), "b", "", slice(1, 1), "", "")],
            "ac",
            "abc",
        ),
        # Simple deletion
        (
            [slice(0, 1), slice(1, 2), slice(2, 3)],
            [FixPatch(slice(1, 2), "", "", slice(1, 2), "b", "b")],
            "abc",
            "ac",
        ),
        # Illustrative templated example (although practically at
        # this step, the routine shouldn't care if it's templated).
        (
            [slice(0, 2), slice(2, 7), slice(7, 9)],
            [FixPatch(slice(2, 3), "{{ b }}", "", slice(2, 7), "b", "{{b}}")],
            "a {{b}} c",
            "a {{ b }} c",
        ),
    ],
)
def test__linted_file__build_up_fixed_source_string(
    source_slices, source_patches, raw_source_string, expected_result, caplog
):
    """Test _build_up_fixed_source_string.

    This is part of fix_string().
    """
    with caplog.at_level(logging.DEBUG, logger="sqlfluff.linter"):
        result = LintedFile._build_up_fixed_source_string(
            source_slices, source_patches, raw_source_string
        )
    assert result == expected_result


@pytest.mark.parametrize(
    "source_patches,source_only_slices,raw_source_string,expected_result",
    # NOTE: For all of these examples we're not setting the patch_category
    # of the fix patches. They're not used at this step so irrelevant for
    # testing.
    [
        # Trivial example.
        # No edits in a single character file. Slice should be one
        # character long.
        ([], [], "a", [slice(0, 1)]),
        # Simple replacement.
        # We've yielded a patch to change a single character. This means
        # we should get only slices for that character, and for the
        # unchanged file around it.
        (
            [FixPatch(slice(1, 2), "d", "", slice(1, 2), "b", "b")],
            [],
            "abc",
            [slice(0, 1), slice(1, 2), slice(2, 3)],
        ),
        # Templated no fixes.
        # A templated file, but with no fixes, so no subdivision of the
        # file is required and we should just get a single slice.
        (
            [],
            [],
            "a {{ b }} c",
            [slice(0, 11)],
        ),
        # Templated example with a source-only slice.
        # A templated file, but with no fixes, so no subdivision of the
        # file is required and we should just get a single slice. While
        # there is handling for "source only" slices like template
        # comments, in this case no additional slicing is required
        # because no edits have been made.
        (
            [],
            [RawFileSlice("{# b #}", "comment", 2)],
            "a {# b #} c",
            [slice(0, 11)],
        ),
        # Templated fix example with a source-only slice.
        # We're making an edit adjacent to a source only slice. Edits
        # _before_ source only slices currently don't trigger additional
        # slicing. This is fine.
        (
            [FixPatch(slice(0, 1), "a ", "", slice(0, 1), "a", "a")],
            [RawFileSlice("{# b #}", "comment", 1)],
            "a{# b #}c",
            [slice(0, 1), slice(1, 9)],
        ),
        # Templated fix example with a source-only slice.
        # We've made an edit directly _after_ a source only slice
        # which should trigger the logic to ensure that the source
        # only slice isn't included in the source mapping of the
        # edit.
        # TODO: given that the logic is based on the _type_
        # of the slice (e.g. comment), would we handle a
        # template tag which returns an empty string correctly?
        (
            [FixPatch(slice(1, 2), " c", "", slice(8, 9), "c", "c")],
            [RawFileSlice("{# b #}", "comment", 1)],
            "a{# b #}cc",
            [slice(0, 1), slice(1, 8), slice(8, 9), slice(9, 10)],
        ),
        # Templated example with a source-only slice.
        # Here we're making the fix to the templated slice. This
        # checks that we don't duplicate or fumble the slice
        # generation when we're explicitly trying to edit the source.
        # TODO: Should we be using the fix type (e.g. "source")
        # to somehow determine whether the fix is "safe"?
        (
            [FixPatch(slice(2, 2), "{# fixed #}", "", slice(2, 9), "", "")],
            [RawFileSlice("{# b #}", "comment", 2)],
            "a {# b #} c",
            [slice(0, 2), slice(2, 9), slice(9, 11)],
        ),
        # Illustrate potential templating bug (case from JJ01).
        # In this case we have fixes for all our tempolated sections
        # and they are all close to each other and so may be either
        # skipped or duplicated if the logic is not precise.
        (
            [
                FixPatch(
                    templated_slice=slice(14, 14),
                    fixed_raw="{%+ if true -%}",
                    patch_category="source",
                    source_slice=slice(14, 27),
                    templated_str="",
                    source_str="{%+if true-%}",
                ),
                FixPatch(
                    templated_slice=slice(14, 14),
                    fixed_raw="{{ ref('foo') }}",
                    patch_category="source",
                    source_slice=slice(28, 42),
                    templated_str="",
                    source_str="{{ref('foo')}}",
                ),
                FixPatch(
                    templated_slice=slice(17, 17),
                    fixed_raw="{%- endif %}",
                    patch_category="source",
                    source_slice=slice(43, 53),
                    templated_str="",
                    source_str="{%-endif%}",
                ),
            ],
            [
                RawFileSlice(
                    raw="{%+if true-%}",
                    slice_type="block_start",
                    source_idx=14,
                    block_idx=0,
                ),
                RawFileSlice(
                    raw="{%-endif%}",
                    slice_type="block_end",
                    source_idx=43,
                    block_idx=1,
                ),
            ],
            "SELECT 1 from {%+if true-%} {{ref('foo')}} {%-endif%}",
            [
                slice(0, 14),
                slice(14, 27),
                slice(27, 28),
                slice(28, 42),
                slice(42, 43),
                slice(43, 53),
            ],
        ),
    ],
)
def test__linted_file__slice_source_file_using_patches(
    source_patches, source_only_slices, raw_source_string, expected_result, caplog
):
    """Test _slice_source_file_using_patches.

    This is part of fix_string().
    """
    with caplog.at_level(logging.DEBUG, logger="sqlfluff.linter"):
        result = LintedFile._slice_source_file_using_patches(
            source_patches, source_only_slices, raw_source_string
        )
    assert result == expected_result


@pytest.mark.parametrize(
    "case",
    [
        dict(
            name="utf8_create",
            fname="test.sql",
            encoding="utf-8",
            existing=None,
            update="def",
            expected="def",
        ),
        dict(
            name="utf8_update",
            fname="test.sql",
            encoding="utf-8",
            existing="abc",
            update="def",
            expected="def",
        ),
        dict(
            name="utf8_special_char",
            fname="test.sql",
            encoding="utf-8",
            existing="abc",
            update="→",  # Special utf-8 character
            expected="→",
        ),
        dict(
            name="incorrect_encoding",
            fname="test.sql",
            encoding="Windows-1252",
            existing="abc",
            update="→",  # Not valid in Windows-1252
            expected="abc",  # File should be unchanged
        ),
    ],
    ids=lambda case: case["name"],
)
def test_safe_create_replace_file(case, tmp_path):
    """Test creating or updating .sql files, various content and encoding."""
    p = tmp_path / case["fname"]
    if case["existing"]:
        p.write_text(case["existing"])
    try:
        LintedFile._safe_create_replace_file(
            str(p), str(p), case["update"], case["encoding"]
        )
    except Exception:
        pass
    actual = p.read_text(encoding=case["encoding"])
    assert case["expected"] == actual


@pytest.mark.parametrize(
    "failure",
    [
        # os.chmod failing (e.g. EPERM/EACCES on a restrictive/foreign target dir).
        dict(target="os.chmod", exc=PermissionError("chmod denied")),
        # shutil.move failing (e.g. read-only target, ENOSPC, cross-device edge).
        dict(target="shutil.move", exc=OSError("move failed")),
    ],
    ids=lambda failure: failure["target"],
)
def test_safe_create_replace_file_cleans_up_on_failure(failure, tmp_path):
    """A failure after the temp file is written must not orphan it.

    ``_safe_create_replace_file`` writes to a temp file (created with
    ``delete=False``) before replacing the target, so if chmod or move fails
    afterwards the temp file must be removed rather than left next to the user's
    file (where, sharing the .sql suffix, it looks like a real one).
    """
    p = tmp_path / "test.sql"
    p.write_text("original")
    target = f"sqlfluff.core.linter.linted_file.{failure['target']}"
    with mock.patch(target, side_effect=failure["exc"]):
        with pytest.raises(type(failure["exc"])):
            LintedFile._safe_create_replace_file(str(p), str(p), "updated", "utf-8")
    # The original file is untouched and no temp file was left behind.
    assert p.read_text() == "original"
    assert [entry.name for entry in tmp_path.iterdir()] == ["test.sql"]


def test_safe_create_replace_file_cleans_up_on_encoding_error(tmp_path):
    """An encoding failure while writing must not orphan the temp file."""
    p = tmp_path / "test.sql"
    p.write_text("original")
    # A right-arrow is not representable in Windows-1252, so the write raises.
    with pytest.raises(UnicodeEncodeError):
        LintedFile._safe_create_replace_file(str(p), str(p), "\u2192", "Windows-1252")
    assert p.read_text() == "original"
    assert [entry.name for entry in tmp_path.iterdir()] == ["test.sql"]


def test__linted_file__fix_string_generates_patches_when_not_precomputed():
    """fix_string() should generate patches when a fixed tree is present.

    This covers the compatibility path for `LintedFile` instances which contain
    a fixed parse tree but do not already carry precomputed `source_patches`.
    """
    sql = "SELECT\n  1\n"
    config = FluffConfig(overrides={"dialect": "ansi", "rules": "LT02"})
    linted = Linter(config=config).lint_string(sql, fix=True)
    legacy_linted = linted._replace(source_patches=None)

    fixed_sql, changed = legacy_linted.fix_string()

    assert changed
    assert fixed_sql == "SELECT\n    1\n"


def test__linted_file__slice_source_file_using_patches_does_not_mutate_inputs():
    """The slicing step must leave both input lists usable for repeated calls.

    The previous implementation consumed ``source_only_slices`` with ``pop(0)``
    so calling ``fix_string()`` twice no longer saw any template fragments.
    """
    source_only_slices = [
        RawFileSlice("{# a #}", "comment", 0),
        RawFileSlice("{# b #}", "comment", 7),
    ]
    source_patches = [
        FixPatch(slice(7, 8), "x", "", slice(7, 8), "c", "c"),
    ]
    raw_source_string = "{# a #}{# b #}c"
    expected_slices = LintedFile._slice_source_file_using_patches(
        source_patches, source_only_slices, raw_source_string
    )

    # The inputs are untouched...
    assert [slc.source_idx for slc in source_only_slices] == [0, 7]
    # ...and a second call yields exactly the same result.
    second_slices = LintedFile._slice_source_file_using_patches(
        source_patches, source_only_slices, raw_source_string
    )
    assert second_slices == expected_slices


def _make_scaled_linted_file(n):
    """Build a templated LintedFile with O(n) patches and source-only slices.

    Each iteration adds a Jinja comment (a source-only template fragment) plus
    fixable statements, so template fragments, fix points and source length
    all grow together with ``n``.
    """
    sql = (
        "\n".join("{# comment %d #}\nselect  b_%d ;" % (i, i) for i in range(n)) + "\n"
    )
    config = FluffConfig(
        overrides={
            "dialect": "ansi",
            "templater": "jinja",
            "rules": "CV06,LT01",
        }
    )
    return Linter(config=config).lint_string(sql, fix=True)


def test__linted_file__fix_string_is_repeatable_with_template_fragments():
    """Repeated fix_string() calls return identical results without exhaustion.

    Regression test for the writeback phase: neither the prepared source
    patches nor the source-only template slices may be consumed while building
    the corrected text, so calling ``fix_string()`` repeatedly on the same
    lint result must always give the same string and the same changed flag.
    """
    linted = _make_scaled_linted_file(20)
    assert linted.source_patches
    n_patches = len(linted.source_patches)
    n_source_only = len(linted.templated_file.source_only_slices())
    assert n_source_only == 20

    first_output = linted.fix_string()
    for _ in range(3):
        assert linted.fix_string() == first_output

    fixed_sql, changed = first_output
    assert changed
    # Every template comment is retained...
    for i in range(20):
        assert "{# comment %d #}" % i in fixed_sql
    # ...and every fix was applied, with newlines and unedited text preserved.
    for i in range(20):
        assert "select b_%d;" % i in fixed_sql
    # The prepared fix list was not used up.
    assert len(linted.source_patches) == n_patches
    assert len(linted.templated_file.source_only_slices()) == n_source_only


def test__linted_file__fix_string_writeback_edge_cases():
    """The writeback phase handles all boundary-shaped edits correctly."""

    def lint(sql, rules=None, templater="raw"):
        overrides = {"dialect": "ansi", "templater": templater}
        if rules:
            overrides["rules"] = rules
        return Linter(config=FluffConfig(overrides=overrides)).lint_string(
            sql, fix=True
        )

    # Empty file without a triggering rule stays empty.
    empty, empty_changed = lint("", rules="CV06").fix_string()
    assert (empty, empty_changed) == ("", False)

    # Non-English characters must not shift any edit positions.
    sql = "select  1 as 名称, '日本語' from 表 where x  =  1\n"
    fixed, changed = lint(sql).fix_string()
    assert changed
    assert "名称" in fixed and "日本語" in fixed and "表" in fixed
    # A second application is idempotent and identical to the first.
    assert lint(sql).fix_string() == (fixed, changed)

    # Adjacent fixes combining an insertion and a deletion on a boundary.
    fixed, changed = lint("select a  ,  b ;\n", rules="CV06,LT01").fix_string()
    assert (fixed, changed) == ("select a, b;\n", True)

    # A pure insertion at the start of the file (leading blank lines removed).
    fixed, changed = lint("\n\nselect 1\n", rules="LT13").fix_string()
    assert (fixed, changed) == ("select 1\n", True)

    # A file with no fixes keeps every character, including template comments.
    unchanged = "{# keep #}\nSELECT 1;\n"
    fixed, changed = lint(unchanged, templater="jinja").fix_string()
    assert (fixed, changed) == (unchanged, False)


def test__linted_file__fix_string_keeps_explicit_template_edits():
    """Fixes which edit the template itself must not be dropped during writeback."""
    sql = "{%if true%}SELECT 1;\n{%endif%}\n"
    config = FluffConfig(
        overrides={
            "dialect": "ansi",
            "templater": "jinja",
            "rules": "JJ01",
        }
    )
    linted = Linter(config=config).lint_string(sql, fix=True)
    # The Jinja edits are carried as explicit source patches.
    assert linted.source_patches
    assert all(patch.patch_category == "source" for patch in linted.source_patches)

    fixed, changed = linted.fix_string()
    assert changed
    assert fixed == "{% if true %}SELECT 1;\n{% endif %}\n"
    # Repeated application gives the same result and does not consume patches.
    assert linted.fix_string() == (fixed, changed)


def test__linted_file__writeback_scales_linearly():
    """Doubling fragments and fixes must roughly double writeback work.

    This guards against a regression back to the quadratic behaviour caused by
    ``list.pop(0)`` slicing and the nested patch scan/string concatenation.
    The check counts the actual slice-equality comparisons performed while
    building the fixed string rather than measuring wall-clock time, so it is
    not flaky under varying machine load.
    """
    small = _make_scaled_linted_file(25)
    large = _make_scaled_linted_file(50)

    def writeback_with_comparison_count(linted):
        patches = linted.source_patches
        source_only = linted.templated_file.source_only_slices()
        source_str = linted.templated_file.source_str
        slices = LintedFile._slice_source_file_using_patches(
            patches, source_only, source_str
        )

        # Wrap each patch so we can observe how often its source slice is
        # compared against a slice. A nested scan compares every patch with
        # every slice; a linear merge visits each patch a constant number of
        # times.
        class CountingPatch:
            def __init__(self, patch):
                self._patch = patch

            @property
            def source_slice(self):
                class CountingSlice:
                    def __init__(self, real_slice, counter_ref):
                        self._real = real_slice
                        self._counter = counter_ref

                    def _count(self):
                        self._counter[0] += 1

                    def __eq__(self, other):
                        self._count()
                        return self._real == other

                    def __lt__(self, other):
                        self._count()
                        return self._real < other

                    @property
                    def start(self):
                        return self._real.start

                    @property
                    def stop(self):
                        return self._real.stop

                return CountingSlice(self._patch.source_slice, counter_ref)

            def __getattr__(self, name):
                return getattr(self._patch, name)

        counter_ref = [0]
        counted_patches = [CountingPatch(patch) for patch in patches]
        result = LintedFile._build_up_fixed_source_string(
            slices, counted_patches, source_str
        )
        return result, slices, patches, source_only, counter_ref[0]

    (
        small_result,
        small_slices,
        small_patches,
        small_source_only,
        small_comparisons,
    ) = writeback_with_comparison_count(small)
    (
        large_result,
        large_slices,
        large_patches,
        large_source_only,
        large_comparisons,
    ) = writeback_with_comparison_count(large)

    # Inputs doubled in every dimension...
    assert len(large_patches) == 2 * len(small_patches)
    assert len(large_source_only) == 2 * len(small_source_only)
    # ...and so did the amount of slicing/output work, rather than quadrupling.
    assert len(large_slices) == 2 * len(small_slices)
    # The outputs themselves are correct and internally consistent.
    assert small_result == small.fix_string()[0]
    assert large_result == large.fix_string()[0]
    # A nested scan would have quadrupled the comparison count when the
    # inputs doubled; the linear merge stays within a small factor of two
    # (boundary effects mean it need not be exactly 2x).
    assert small_comparisons <= 2 * len(small_slices)
    assert large_comparisons <= 2 * len(large_slices)
    assert large_comparisons <= 3 * small_comparisons
