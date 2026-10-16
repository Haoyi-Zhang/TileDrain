# Capacity-Robust Drain Certificates

The two explanatory diagrams are self-contained Python vector figures. Install optional rendering dependencies with `python -m pip install -r scripts/requirements-schematics.txt`, then run `python scripts/draw_schematics.py` to generate them or add `--check` to verify freshness. The renderer checks the exact running and fork inputs before drawing, embeds its fonts, and requires no TeX installation. Scientific reproduction remains standard-library-only.

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

The direct safety helper accumulates exact retained loads in one event pass into at most 512 lane counters, after mask, source-ideality and support checks. Cross-lane order checks and necessity explanations are unchanged. The independently implemented validator retains its separate scalar lane sums. The selected measurement batch below uses this exact timed implementation; historical measurements are retained separately, without inferring improvement across hosts or source revisions.

An additional finite regression runs separately from the 35-test discovery suite:

```sh
python -B tests/lane_regression.py
```

Its six tests cover the complete weighted two-event domain (1,005 instances and all 3,977 subset masks), eight boundary/example instances, the first 16 frozen five-event inputs, maximum admitted event/lane counts, invalid masks and explanation priority, and the 31 declared controls. Its test-local reference enumerates source prefixes and FIFO interleavings rather than using the production feasibility formula. This is bounded implementation checking, not a fresh full campaign or a general proof. The scientific CI workflow invokes it explicitly before the unchanged full reproduction.

## Exact input grammar

`inputs/example.json` is the minimal format example. `p[j]` and `q[j]` are predecessor bitmasks; all set bits must be less than j. Orders must already be transitively closed, and P must be included in Q. The interface rejects inconsistent orders rather than repairing them. Events are numbered 0 through n-1 in one supplied common topological order; that numbering fixes FIFO order and is not optimized.

The arrays `lane` and `weight` have n entries. `capacity` has between 1 and 512 entries. The `unsupported` bitmask marks operations lacking an admitted destination implementation. Event count is at most 512; sizes are positive and capacities nonnegative, with each scalar at most 2^63-1. Sums use exact integers and do not wrap. The mathematical theorems allow arbitrary finite event sets; the executable grammar has explicit bounds.

The semantic demonstrator has two unsigned registers and one carry bit per context, 1–16-bit virtual words, 1–16 contexts, and COPY, XOR, ADD, ADC. Native-width, widened, and split-limb templates are declared implementations, not arbitrary synthesized machine code. Unsupported state formats, especially carry loss, fail a global state gate and cannot be repaired by draining the current epoch.

## Reproduce the finite evidence

The bounded runner requires Linux or another POSIX system providing Python's `resource` module and `RLIMIT_AS`; it was tested on Linux. RSS units in the retained records are Linux KiB. Native Windows execution of the bounded runner is not claimed. Use the complete runner, which executes one bounded child at a time:

```sh
python reproduce.py --output results/reproduced-single-p
```

The complete runner executes 44 exact shards: the unchanged n=0..3 intervals and all 40 single-P-index n=4 intervals [0,1) through [39,40), in that order. This retains all 729,088 n=4 instances (737,009 through n=4); it does not sample or skip cases. No smaller shard is guaranteed to finish on every host.

Start the new partition in a fresh, initially absent output directory such as `results/reproduced-single-p`. Do not copy retained campaign products into it or mix an older coarse n=4 partition with the new one: overlapping intervals remain an error. Resume only the same completed intervals in that directory; a JSON summary without its required raw product remains incomplete. The CI output directory is job-local under `RUNNER_TEMP`; its existing always-upload step retains observations without replacing the historical campaign.

For environments with short interactive command timeouts, run the same resumable partition instead (POSIX shell):

```sh
python reproduce.py --output results/reproduced-single-p --task exact --n 0
python reproduce.py --output results/reproduced-single-p --task exact --n 1
python reproduce.py --output results/reproduced-single-p --task exact --n 2
python reproduce.py --output results/reproduced-single-p --task exact --n 3
for p in $(seq 0 39); do
  python reproduce.py --output results/reproduced-single-p \
    --task exact --n 4 --start "$p" --stop "$((p + 1))" || exit 1
done
python reproduce.py --output results/reproduced-single-p --task remaining
python reproduce.py --output results/reproduced-single-p --task reconcile
```

The controller applies a 3 GiB address-space cap, a 120-second CPU ceiling and a 120-second wall timeout. A scientific child's own stricter limits still apply: `src/experiment.py` resets its CPU soft and hard limits to 40 seconds. Thus the controller's ceiling does not give that experiment 120 CPU seconds. These limits are unchanged. The complete runner remains synchronous and does not schedule background work. A slower machine can split a P-index interval into smaller nonoverlapping intervals using the same interface; this changes only the chunk partition, not the scientific input set. Do not combine overlapping result chunks. The largest retained partition uses 15 P indices after a measured bounded execution; this was an execution-granularity change, not a change to inclusion rules.

On a failed child, the controller prints its return code, termination signal number/name when available, and captured standard output/error. It also appends the same failure-only record to `reproduction-failures.jsonl` outside temporary scientific stages. A controller wall timeout is distinguished from a returned termination signal; a signal alone does not identify whether a CPU limit, memory pressure or an external action caused termination. Exact enumeration emits flushed progress on standard error before and after each P index, with cumulative completed instance counts. No partial output or failure diagnostic is a completed-result marker. The complete scientific comparisons and nonzero failure exit remain mandatory.

The six portable diagnostics regressions run explicitly before reproduction in scientific CI:

```sh
python -B tests/reproduction_diagnostics_regression.py
```

They check failure formatting, partial timeout output, exact domain sizes by independent graph reachability, and one-event scientific output with in-memory capture. They do not exercise POSIX limits or complete a failed campaign.

The partition regression is also an explicit pre-campaign CI step:

```sh
python -B tests/partition_regression.py
```

It checks full P-index/count coverage, split raw-row/counter equivalence through two events, and actual capacity/aggregation rejection of gaps, overlaps and corruption with in-memory I/O. Its two controller admission/resume checks require POSIX `resource` and are explicitly skipped on unsupported hosts; Linux CI runs them. These tests do not constitute a fresh complete campaign. The historical 25- and 61-invocation receipts below retain their original partitions and observations, not current execution counts.

The final reconciliation checks raw exact rows against chunk summaries, capacity-group totals, complete P-index coverage, all scientific summary values against the retained campaign, and decompressed deterministic scientific result files. CPU time, wall time, and RSS are observations and are not expected to match across machines. It does not require identical gzip headers, file timestamps, fonts, private paths, omitted caches, network access, or external accounts. Run the documented commands from a clean extraction rather than treating retained results as a fresh run.

The full domain is all naturally numbered P,Q posets with P included in Q for n=0..4, all two-lane assignments, all unsupported masks, unit sizes, and every capacity from zero through each lane's occupancy. This is not a sample of realistic programs or all unlabeled processor architectures. The independent oracle enumerates source permutation prefixes and destination FIFO interleavings; it does not call the feasibility normal form to classify order legality. It short-circuits once a bad target trace is found, so its trace counter is neither a unique-trace count nor the size of a fully explored hardware execution space. A second validator reconstructs each instance and certificate from primitive serialized fields, recomputes source ideality, support, exact lane loads, and cross-lane order, and checks necessity explanations or no-least witnesses without calling the producer, production checker, or oracle.

`inputs/fork.json` specifies the four-event weighted first-fork example in the proof document and manuscript. Its clean-checked two-cut witness is retained as `results/fork-example.json`; `results/final-extraction-check.json` records the final interface and unit-test execution. This is explanatory input, not an additional sampled workload in the campaign counts.

`inputs/weighted.json` contains exactly 512 frozen five-event weighted instances. `inputs/epochs.json` contains exactly 256 generated programs with bounded migration proposals. Reproduction consumes these files directly. Generator seeds and algorithms are provided for provenance, not as a requirement to obtain identical future pseudo-random-library behavior. `src/inputs.py` refuses to replace different frozen inputs.

## What is measured

The retained exact campaign contains 737,009 instances: 712,957 have a least cut and 24,052 do not. All diagnoses agree with the independent small oracle. The capacity-universal audit covers 92,597 fixed contracts and identifies 81,815 robust contracts and 10,782 constructive obstructions. Its effective-alignment fast path is checked on 655,587 capacity instances.

Structural baselines on the same exact domain show that capability closure alone is unsafe on 267,802 instances (36.34%), while capability plus mandatory-order closure but no capacity treatment is unsafe on 231,824 (31.45%). Across the 712,957 least cases, certificates select 2,389,340 source completions versus 2,843,906 for drain-all, a difference of 454,566 events (15.98% of the drain-all event count in those cases). These are structural event counts, not eliminated work, time, energy, or speedup.

A complete weighted microdomain contains 11,465 fixed contracts and 100,973 capacity instances through three events, two lanes, event sizes in `{1,2}`, and every bounded capacity vector. It has 98,875 least and 2,098 no-least outcomes; 10,529 contracts are capacity-robust and 936 have independently validated obstructions. Producer, permutation/interleaving oracle, independent validator, applicable fast path, and universal classification have zero recorded disagreement or certificate failure.

Additional evidence comprises 512 frozen larger weighted cases; 131,040 adapter comparisons; 21,840 small-width and 192 multibyte boundary state round trips; 256 synthetic epochs with 4,088 completions and 631 accepted transfers; and 31 declared negative/positive boundary controls. The retained Linux reproduction records its 29-test suite separately. The current discovery suite has 35 tests, including portable finite-function imports, evidence-record checks, the pinned Wharf preprint, and four measurement-source/schema/zero-interval regressions. Repeated-migration scheduling is bounded, and the separately implemented paths share the input grammar and Python runtime. The mathematical results are supplied as written proofs alongside these finite checks.

Structural timing uses synthetic instances of 16–512 events. The active paper input is the complete triplet in `results/scaling/`, with its source/run identity in `provenance.json`. The 512-event medians round to 135/108/78 ms for general analysis, certificate checking, and aligned construction on the sparse shape, and 186/158/131 ms on the dense shape. This batch ran on CPython 3.12.15, Linux x86-64 and AMD EPYC 9V74, with one worker, three repetitions, 3 GiB address-space and 40 CPU-second limits. Each method has a separate `time.process_time` interval; construction and output are excluded. The raw 108 intervals retain 23 zeros. The API's nominal 1 ns resolution differs from the roughly millisecond accounting steps visible in small cases; no timing ratio or zero-overhead inference is reported. These are structural Python checking costs. Historical campaign host fields remain explicitly unknown and are not filled from later runs.

Run `python src/scaling_report.py` to validate the selected bundle and recompute every cell's median/range in milliseconds. The build, aggregation and reconciliation share its complete schema/group checks. Aggregation still uses each explicit campaign/output directory for scientific counts; it does not combine historical counts with another run's timing subsection. Reproduction output may not overwrite `results/scaling/`.

## Files and evidence

`.github/workflows/scientific-checks.yml` is configured for the flat artifact repository root on Ubuntu 24.04, on pushes to `main` or manual dispatch. It runs the existing material-integrity gate, the lane, diagnostics and partition regressions and complete POSIX reproduction, including scientific reconciliation, with a 12-minute whole-command timeout, a 15-minute job timeout, and 120-second controller per-child ceilings (the experiment's 40-second CPU cap still applies). The outer shell also bounds virtual memory to 3 GiB and CPU time to 600 seconds. Raw outputs and diagnostics are uploaded even when a gate fails. Workflow configuration alone is not evidence of an executed run; it does not build the sibling manuscript.
The older workflow run 37443748741 completed 25 recorded invocations, including controller reconciliation. Their summed intervals were 105.73 wall seconds and 105.64 CPU seconds; maximum recorded child RSS was 166,492 KiB. Its CPython 3.12.14/AMD EPYC 9V45 observations remain in `results/measurements/`; the original generation's `scaling.json` remains in that run's artifact, rather than beside this retained subset. Those records describe an older per-lane-scan helper and are not current paper timings.

The selected timings come from successful run 38595253317 at source commit `4b44f61406cb65b83b6311874ab56c4b1445685e`. Its digest-bound raw output contains all 61 invocations and a complete scaling triplet. Raw comparison reproduced all 737,009 exact rows, the other deterministic files, and all scaling non-timing fields. `results/scaling/provenance.json` records the run, original archive digest, selected file identities and exact timed-source modules. The suite's 3.397 CPU/3.397 wall seconds and 29,080 KiB peak RSS measure the whole scaling child, separately from per-method intervals.

`src/` contains structural analysis, certificate validation, arithmetic/state adapters, the permutation oracle, bounded experiments, and the shared measurement reader. `proofs/model.md` contains the complete written arguments and explicit counterexamples. `results/campaign/` contains claim-linked raw rows, traces, certificates, summaries, and the partial historical scaling-environment record. `results/summary/` contains the historical campaign aggregation; active paper timing comes solely from `results/scaling/`. `results/resource-usage.csv` retains measured CPU, wall-time, RSS, and command records for the historical 24-invocation campaign. `results/clean-reproduction.json` records full deterministic reconciliation, while `results/clean-reproduction-resources.json` and `results/clean-reproduction-invocations.jsonl` retain the corresponding measured invocations. The clean run's `clean-reproduction-scaling.csv` and `clean-reproduction-scaling-environment.json` remain a separate matched pair, outside the active timing input. The final extraction rechecks unchanged scientific sources and frozen inputs; its separate smoke record does not pretend to be a second full campaign. `claim_evidence_ledger.csv` maps material claims to proofs, programs, inputs, and raw results. `literature_matrix.csv` records the completed 12-paper TACO, five-paper influential/award, and five-paper adjacent-venue calibration; `reference_audit.csv` retains 36 citation records with identifiers, manuscript roles, and metadata checks; the current manuscript cites 50 entries; `external_resources.csv` records acquisition and use. No experimental upstream baseline code is embedded or silently modified.

## Model scope

The model assumes atomic state/descriptor transfer, truthful front-end dependencies, exact operation templates, and single completion ownership. Crashes, asynchronous I/O, DMA, speculation visible to the environment, cache coherence, weak-memory hardware, new admissions during transfer, remapping optimization, and real application performance are excluded. Safe finite traces do not imply progress: a migration-only schedule can keep work pending forever.

The artifact contains the written mathematical argument, certificate checker, finite campaign, a retained 36-entry reference audit, and the 12+5+5 literature comparison. The literature comparison identifies the residual-lane-chain criterion over all independent capacity vectors and its least/no-least certificates as the model-specific contribution. Physical integration, application value, and hardware performance remain unmeasured.


## License

New code and accompanying generated scientific materials are offered under the MIT terms in `LICENSE`, to the extent copyright applies. This does not assert exclusive copyright in every accompanying material. Scholarly papers listed in the resource ledger are cited, not redistributed or relicensed. Publisher typesetting files are not part of this standalone repository.
