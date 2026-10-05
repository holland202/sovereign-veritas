# Provenance of the store logs in this folder

The nine `store_events.jsonl` files in `results/obs1/run/` were written by the registered run at implementation
`0ba3aa7` (2026-10-04, 19:37:08–19:37:09 -0500) but were **not committed** with the evidence bundle at `2d0766d`:
the repository's `.gitignore` excluded `*.jsonl`. Amos Tipton found the gap on 2026-10-05.

They are published here from the same working copy, not regenerated. What supports that, and what does not:

- Their modification times are the registered run's (the same second as that run's `comparator.json`).
- Each one equals, event for event, the `events` list of the `observer_after.json` committed at `2d0766d` for the
  same case.
- The working copy was moved aside and restored once, intact, so that the post-lint rerun (`56d09ab`) could write its
  own bundle elsewhere; that rerun did not write into this folder.
- Not available: a hash of these bytes recorded before today. Their originality rests on the points above, not on a
  commitment made at run time.

sha256 of each, at publication:
2bb925847debb377ead14638f8152640154749858789713c34970084f107b392  results/obs1/run/AT-1/store_events.jsonl
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  results/obs1/run/AT-2/store_events.jsonl
f66f4d20a984cbb14e9606e00180176b72b64e098fc736c911bf4e252f561a4d  results/obs1/run/AT-3/store_events.jsonl
9e8f93fbd76447c2ef12aa6f8799bd16db6819d5add8a5a81945126ac12952ed  results/obs1/run/AT-4-DW/store_events.jsonl
d726a54da582c6ac805246de6df5f1a6d3b0ee19cf58eb61cd8a1fd83500677c  results/obs1/run/AT-4/store_events.jsonl
be7c6c83386fe4ce07d3da52cd684eaa245006554fa591d95f39888a76546cb0  results/obs1/run/controls/P7_broken_store/AT-4-DW/store_events.jsonl
a7aa5f7363c4f4de71d60f7b3b132f86053ca6e6373c08dbf69a7354b0e610c3  results/obs1/run/controls/P8_no_reconcile/AT-4-DW/store_events.jsonl
b8cab258d7a2a7fd5c3b20009422b12f2cba2dbc3b7bdf57245a77cc627c4522  results/obs1/run/controls/P8_no_reconcile/AT-4/store_events.jsonl
98d018e6e111814ca64dc2ec6d66066f917a55703bbc6f0c5c7343f504caab89  results/obs1/run/controls/P9_stale_permission/AT-2/store_events.jsonl
