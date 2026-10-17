# October17 broad rerun artifacts

Application/test source: `099e1b524472447b292f2a16044216a5aa495531`.
These are new runs, not replacements for October15 evidence.

Raw JUnit XML and logs are preserved losslessly as gzip archives to avoid adding
megabytes of repeated synthetic stdout to the repository. Decompress a COPY for
inspection; do not edit the archived reports. Summary and SHA256 values are in
`../BROAD_RETEST_2026-10-17.md`.

The strict backend report intentionally retains its42 blocked outcomes and seven
engineering failures. Reviewed service/tooling reports are separate evidence, not
a rewritten or greenwashed full-suite result. Counts include pytest subtests;
suite totals, parent case records and assertion outcomes are not interchangeable.
