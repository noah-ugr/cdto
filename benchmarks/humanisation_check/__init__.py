"""
Humanisation check for gpt-oss:20b under Planner-Executor (paper, Subsection 4.1).

The dataset requests were humanised by gpt-oss:20b itself, so its P-E scores
could benefit from reading its own phrasing. Three conditions on the same
samples (same base configuration, instructions, ground truth and sample IDs):

- A: the logged gpt-oss:20b results (old server, original requests), read
  from the re-scored JSONs.
- B: new server, original requests (server control).
- C: new server, requests re-humanised by a model of another family.

C - B is the humanisation effect; B - A only checks that the new server
reproduces the old one.

Pipeline (each step is a module run with ``python -m``):

1. ``select_samples``   fixed-seed sample IDs, 25 per level.
2. ``rehumanise``       new requests with the original humaniser code and
                        prompt; only the model changes.
3. ``fidelity``         identifiers and values of every instruction present
                        in each new request (flags, never drops).
4. ``run_paired``       B and C interleaved sample by sample with the
                        original runner code and configuration.
5. ``compare``          paired A/B/C comparison.

``ollama_api`` and ``provenance`` gather the server and original-run facts
for the manifest; ``collect_server_info.py`` runs on the Ollama host over SSH.
Everything is written to ``benchmarks/results/humanisation_check/<run_id>/``.

``Modelfile.gpt-oss-20b-ctx32k`` is the model for ``run_paired
--derived-model``: gpt-oss:20b with ``num_ctx 32768`` and nothing else, for
servers whose default context (4096) is too short. Create it on the Ollama
host with ``ollama create gpt-oss-20b-ctx32k -f Modelfile.gpt-oss-20b-ctx32k``.
"""
