# CI/CD Integration

## Using [GitHub Actions](https://github.com/features/actions) to Annotate PRs

There are two way to utilize SQLFluff to annotate Github PRs.

1. When `sqlfluff lint` is run with the `--format github-annotation-native`
   option, it produces output formatted as [Github workflow commands](https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-a-notice-message) which
   are converted into pull request annotations by Github.

2. When `sqlfluff lint` is run with the `--format github-annotation`
   option, it produces output compatible with this [action from yuzutech](https://github.com/yuzutech/annotations-action).
   Which uses Github API to annotate the SQL in [GitHub pull requests](https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

::: warning WARNING
GitHub currently limits the number of annotations displayed per workflow run when
using `github-annotation-native`. If you have many violations you may find only
the first 10 are shown. This is not something SQLFluff can control; we recommend
using the second option above and the [action from yuzutech](https://github.com/yuzutech/annotations-action)
if you need full annotation coverage. Track the [GitHub Actions feature request](https://github.com/orgs/community/discussions/68471)
for updates on this limitation.
:::

For more information and examples on using SQLFluff in GitHub Actions, see the
[sqlfluff-github-actions repository](https://github.com/sqlfluff/sqlfluff-github-actions).

## Streaming results with JSON Lines

For large batches, the regular serialised formats are only written once every
file has been linted. If you want to start processing results before a run
finishes, use `--format jsonl`. Each file is written as a single, complete JSON
object as soon as that file is linted, with a newline after it. Clean and
unclean files both get a line, each file appears exactly once, and there is no
surrounding array or trailing summary record.

Each line uses the same per-file fields as one entry of the `--format json`
output (`filepath`, `violations`, `statistics` and `timings`). In parallel runs,
lines arrive in completion order, which may differ from the order of the input
paths.

```bash
# Process each result as it becomes available.
sqlfluff lint my_project --format jsonl | while IFS= read -r line; do
    process_result "$line"
done

# Or write to a file which can be tailed while the lint is still running.
sqlfluff lint my_project --format jsonl --write-output lint-results.jsonl
```

When `--write-output` is set, results go only to that file and not to stdout.
Logging, progress bars, colours and diagnostics are kept off the JSON lines.
For `--bench`, the timing tables are written to stderr instead of stdout so the
output remains machine readable.

## Using GitLab CI Code Quality reports

When `sqlfluff lint` is run with the `--format gitlab` option, it produces a
[GitLab Code Quality report](https://docs.gitlab.com/ci/testing/code_quality/#code-quality-report-format)
(the Code Climate issue format). GitLab can ingest that file and show findings
in merge requests.

A typical job writes the report with `--write-output` and publishes it as a
`codequality` artifact:

```yaml
lint-sql:
  image:
    name: sqlfluff/sqlfluff
    entrypoint: [""]
  script:
    - sqlfluff lint --format gitlab --write-output gl-code-quality-report.json
  artifacts:
    reports:
      codequality: gl-code-quality-report.json
```
