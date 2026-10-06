# Capacity-Robust Drain Certificates

This repository studies **least source-drain certificates for the pending-work quiescence subproblem of sealed FIFO-tile migration**. It is a standalone, standard-library Python artifact for a finite mathematical model, not a hardware verifier, ISA emulator, migration service, or production implementation.

The mathematical proof is in `proofs/model.md`. A migration instance fixes an architectural event order P, an executable source order Q extending P, destination FIFO assignments, positive storage sizes, independent lane capacities, and unsupported operations. Source drains must be Q-ideals. Operation identities are observable. Exact state conversion and unique atomic completion ownership are separate assumptions.

The central results distinguish a safe cut from an inclusion-least cut. The general diagnostic returns either a least-cut certificate or two safe cuts whose unsafe intersection proves that no least cut exists. After unavoidable capability/order work is removed, the surviving portion of each destination lane being a Q-chain characterizes least-cut existence for **every nonnegative integer capacity vector**. For the bounded scalar encoder, necessity additionally requires representable complete residual lane loads. No minimum-cost solution is promised when no least cut exists.

## Run the small interface

From this directory, with Python 3.10 or later and no third-party Python packages:

```sh
python -m unittest discover -s tests -v
python src/cli.py analyze inputs/example.json --output certificate.json
python src/cli.py check inputs/example.json --certificate certificate.json
python src/cli.py robust inputs/example.json
```

The example's least drain is `[0, 1, 2, 3]`. The interface does not overwrite an existing output. Delete only your own disposable certificate before repeating the same `--output` command. Exit status 0 means the requested command succeeded; a rejected certificate exits 1; malformed input or an I/O error exits 2. Input and certificate JSON files are limited to one MiB each; duplicate JSON fields are rejected. A successful command is not proof that real hardware satisfies the declared contract.

A certificate is meaningful only for the complete instance with which it is checked. Recheck after changing orders, capabilities, placement, sizes, or capacities. No hash or persistent certificate cache is used.

The small interface, unit tests, and pure finite-check functions do not require the POSIX-only `resource` module. Resource limits are imported by the bounded command-line experiment runners when invoked; the complete reproduction runner below still requires POSIX.

## Exact input grammar

`inputs/example.json` is the minimal format example. `p[j]` and `q[j]` are predecessor bitmasks; all set bits must be less than j. Orders must already be transitively closed, and P must be included in Q. The interface rejects inconsistent orders rather than repairing them. Events are numbered 0 through n-1 in one supplied common topological order; that numbering fixes FIFO order and is not optimized.

The arrays `lane` and `weight` have n entries. `capacity` has between 1 and 512 entries. The `unsupported` bitmask marks operations lacking an admitted destination implementation. Event count is at most 512; sizes are positive and capacities nonnegative, with each scalar at most 2^63-1. Sums use exact integers and do not wrap. The mathematical theorems allow arbitrary finite event sets; the executable grammar has explicit bounds.

The semantic demonstrator has two unsigned registers and one carry bit per context, 1–16-bit virtual words, 1–16 contexts, and COPY, XOR, ADD, ADC. Native-width, widened, and split-limb templates are declared implementations, not arbitrary synthesized machine code. Unsupported state formats, especially carry loss, fail a global state gate and cannot be repaired by draining the current epoch.

## Reproduce the finite evidence

The bounded runner requires Linux or another POSIX system providing Python's `resource` module and `RLIMIT_AS`; it was tested on Linux. RSS units in the retained records are Linux KiB. Native Windows execution of the bounded runner is not claimed. Use the complete runner, which executes one bounded child at a time:

```sh
python reproduce.py --output results/reproduced
```

For environments with short interactive command timeouts, run resumable chunks instead:

```sh
python reproduce.py --output results/reproduced --task exact --n 0
python reproduce.py --output results/reproduced --task exact --n 1
python reproduce.py --output results/reproduced --task exact --n 2
python reproduce.py --output results/reproduced --task exact --n 3
python reproduce.py --output results/reproduced --task exact --n 4 --start 0 --stop 5
python reproduce.py --output results/reproduced --task exact --n 4 --start 5 --stop 15
python reproduce.py --output results/reproduced --task exact --n 4 --start 15 --stop 25
python reproduce.py --output results/reproduced --task exact --n 4 --start 25 --stop 40
python reproduce.py --output results/reproduced --task remaining
python reproduce.py --output results/reproduced --task reconcile
```

Every scientific child has a 3 GiB address-space cap, a 120-second CPU ceiling, and a 120-second wall timeout. The retained campaign used 40-second child limits; the current limits allow for slower shared runners without changing any scientific input or comparison. The complete runner remains synchronous and does not schedule background work. A slower machine can split a P-index interval into smaller nonoverlapping intervals using the same interface; this changes only the chunk partition, not the scientific input set. Do not combine overlapping result chunks. The largest retained partition uses 15 P indices after a measured bounded execution; this was an execution-granularity change, not a change to inclusion rules.

The final reconciliation checks raw exact rows against chunk summaries, capacity-group totals, complete P-index coverage, all scientific summary values against the retained campaign, and decompressed deterministic scientific result files. CPU time, wall time, and RSS are observations and are not expected to match across machines. It does not require identical gzip headers, file timestamps, fonts, private paths, omitted caches, network access, or external accounts. Run the documented commands from a clean extraction rather than treating retained results as a fresh run.

The full domain is all naturally numbered P,Q posets with P included in Q for n=0..4, all two-lane assignments, all unsupported masks, unit sizes, and every capacity from zero through each lane's occupancy. This is not a sample of realistic programs or all unlabeled processor architectures. The independent oracle enumerates source permutation prefixes and destination FIFO interleavings; it does not call the feasibility normal form to classify order legality. It short-circuits once a bad target trace is found, so its trace counter is neither a unique-trace count nor the size of a fully explored hardware execution space. A second validator reconstructs each instance and certificate from primitive serialized fields, recomputes source ideality, support, exact lane loads, and cross-lane order, and checks necessity explanations or no-least witnesses without calling the producer, production checker, or oracle.

`inputs/fork.json` specifies the four-event weighted first-fork example in the proof document and manuscript. Its clean-checked two-cut witness is retained as `results/fork-example.json`; `results/final-extraction-check.json` records the final interface and unit-test execution. This is explanatory input, not an additional sampled workload in the campaign counts.

`inputs/weighted.json` contains exactly 512 frozen five-event weighted instances. `inputs/epochs.json` contains exactly 256 generated programs with bounded migration proposals. Reproduction consumes these files directly. Generator seeds and algorithms are provided for provenance, not as a requirement to obtain identical future pseudo-random-library behavior. `src/inputs.py` refuses to replace different frozen inputs.

## What is measured

The retained exact campaign contains 737,009 instances: 712,957 have a least cut and 24,052 do not. All diagnoses agree with the independent small oracle. The capacity-universal audit covers 92,597 fixed contracts and identifies 81,815 robust contracts and 10,782 constructive obstructions. Its effective-alignment fast path is checked on 655,587 capacity instances.

Structural baselines on the same exact domain show that capability closure alone is unsafe on 267,802 instances (36.34%), while capability plus mandatory-order closure but no capacity treatment is unsafe on 231,824 (31.45%). Across the 712,957 least cases, certificates select 2,389,340 source completions versus 2,843,906 for drain-all, a difference of 454,566 events (15.98% of the drain-all event count in those cases). These are structural event counts, not eliminated work, time, energy, or speedup.

A complete weighted microdomain contains 11,465 fixed contracts and 100,973 capacity instances through three events, two lanes, event sizes in `{1,2}`, and every bounded capacity vector. It has 98,875 least and 2,098 no-least outcomes; 10,529 contracts are capacity-robust and 936 have independently validated obstructions. Producer, permutation/interleaving oracle, independent validator, applicable fast path, and universal classification have zero recorded disagreement or certificate failure.

Additional evidence comprises 512 frozen larger weighted cases; 131,040 adapter comparisons; 21,840 small-width and 192 multibyte boundary state round trips; 256 synthetic epochs with 4,088 completions and 631 accepted transfers; and 31 declared negative/positive boundary controls. The retained Linux reproduction ran 29 unit tests, including a rectangularity/completeness audit for the evidence ledgers. The current suite has 30 tests after adding a regression for importing finite-check functions and running controls without POSIX `resource`; all 30 pass on the current Windows check host. Counts do not establish practical workload breadth. Repeated-migration scheduling is bounded, not exhaustive. The separately implemented paths share the input grammar and Python runtime; they are not proof-assistant developments.

Structural timing uses synthetic instances of 16–512 events. For the retained 512-event rows, medians computed from `results/campaign/scaling.csv` are 80/68/48 ms for general analysis, certificate checking, and the aligned construction on the sparse shape, and 112/96/80 ms on the dense shape. `results/campaign/scaling-environment.json` links that CSV to its provenance: the original run retained one-worker status, repetition count, resource limits, and the `time.process_time` timer choice, but did not record CPU model/architecture, Python implementation/version, OS version, container/virtualization visibility, or clock resolution. Those fields are explicitly unknown and no later host is substituted. Fresh scaling runs emit a run-matched environment record automatically. Some CPU intervals are zero at the observed accounting resolution; they do not establish zero overhead. Timings are environment-specific Python checking cost, not device migration latency, throughput, energy, silicon area, or deployment performance.

## Files and evidence

`.github/workflows/scientific-checks.yml` is configured for the flat artifact repository root on Ubuntu 24.04, on pushes to `main` or manual dispatch. It runs the existing material-integrity gate and complete POSIX reproduction, including scientific reconciliation, with a 12-minute whole-command timeout, a 15-minute job timeout, and 120-second per-child limits. The outer shell also bounds virtual memory to 3 GiB and CPU time to 600 seconds. Raw outputs and diagnostics are uploaded even when a gate fails. Workflow configuration alone is not evidence of an executed run; it does not build the sibling manuscript.
The workflow completed in run 37443748741. All 25 recorded invocations exited successfully, including the unit suite and three documented interfaces. Direct comparison covers all 737,009 exact rows, the other deterministic result files, and all 36 scaling rows apart from measured CPU intervals. Summed child intervals were 105.73 wall seconds and 105.64 CPU seconds; maximum recorded child RSS was 166,492 KiB. Run-matched scaling metadata records Python 3.12.14, Linux x86-64 and an AMD EPYC 9V45 host. `results/measurements/` retains the current invocation records, reconciliation, scaling CSV and host record without replacing the older campaign timings.

`src/` contains structural analysis, certificate validation, arithmetic/state adapters, the permutation oracle, and bounded experiments. `proofs/model.md` contains the complete written arguments and explicit counterexamples. `results/campaign/` contains claim-linked raw rows, traces, certificates, summaries, and the partial historical scaling-environment record. `results/summary/` contains reconciled manuscript data. `results/resource-usage.csv` retains measured CPU, wall-time, RSS, and command records for the final 24-invocation campaign. `results/clean-reproduction.json` records full deterministic reconciliation, while `results/clean-reproduction-resources.json` and `results/clean-reproduction-invocations.jsonl` retain the corresponding measured invocations. The fresh run's `clean-reproduction-scaling.csv` and `clean-reproduction-scaling-environment.json` are a matched pair kept for provenance; they are not the manuscript timing source. The final extraction rechecks unchanged scientific sources and frozen inputs; its separate smoke record does not pretend to be a second full campaign. `claim_evidence_ledger.csv` maps material claims to proofs, programs, inputs, and raw results. `literature_matrix.csv` records the completed 12-paper TACO, five-paper influential/award, and five-paper adjacent-venue calibration; `reference_audit.csv` records all 36 cited bibliography keys, identifiers, manuscript roles, and metadata checks; `external_resources.csv` records acquisition and use. No experimental upstream baseline code is embedded or silently modified.

## Limits and research status

This is an internal research artifact. Atomic state/descriptor transfer, truthful front-end dependencies, exact operation templates, and single completion ownership are assumptions. Crashes, asynchronous I/O, DMA, speculation visible to the environment, cache coherence, weak-memory hardware, new admissions during transfer, remapping optimization, and real application performance are excluded. Safe finite traces do not imply progress: a migration-only schedule can keep work pending forever.

The mathematical argument, certificate checker, finite campaign, 36-entry cited reference audit, and prescribed 12+5+5 full-paper calibration are complete for this internal packet. That calibration narrows the retained delta to the residual-lane-chain criterion over all independent capacity vectors and its least/no-least certificates. It is not an exhaustive priority search, an independent review, or a guarantee of venue significance or acceptance. Physical integration, application value, and hardware performance remain unmeasured.


## License

New code and accompanying generated scientific materials are offered under the MIT terms in `LICENSE`, to the extent copyright applies. This does not assert exclusive copyright in AI-generated material. Scholarly papers listed in the resource ledger are cited, not redistributed or relicensed. Publisher typesetting files are not part of this standalone repository.
