# Mathematical contract and complete cut proofs

This is a mathematical proof document, not a proof-assistant development. Executable checks in this repository exhaust only their explicitly enumerated finite domains. The generic order-ideal and simulation arguments are standard techniques; the claimed object of study is their exact specialization to sealed FIFO-tile migration with capability and storage constraints.

## 1. Machines and observations

Let E={0,...,n-1} be a finite set of pending operations whose identities are architecturally observable. A strict order is an irreflexive transitive relation. P is the required architectural completion order; Q is a declared executable source order and P is a subset of Q. Both follow the displayed numbering. The numbering is part of the input, not an implicit optimization variable.

Each operation e denotes a total deterministic function F_e on canonical architectural states, together with its visible result. An abstract completion of e is enabled exactly when all its pending P predecessors are complete. It atomically changes the state by F_e and emits (e,result). Any P-linear extension is a permitted full completion trace; prefixes have the corresponding prefix semantics. This specification does not equate all linear extensions' final values, and it is not a commercial memory-consistency model. For the generated ALU programs, a conservative dependence P further guarantees that conflicting operations keep their source-program order.

A source is assumed able to realize any chosen Q-linear extension, with finite completion of each enabled operation. A drain D is a Q-ideal: y in D and x Q y imply x in D. The source completes D in a Q-linear extension, without interspersing completions outside D. Such a schedule exists: topologically sort Q restricted to D, then Q restricted to E\D. No edge goes from the latter to the former because D is an ideal. Their concatenation is a full Q-linear extension. Conversely, every prefix of a Q-linear extension is an ideal.

A fixed map lane:E->{0,...,k-1} assigns each retained operation to a destination FIFO. H orders all pairs i<j on the same lane and no cross-lane pairs. Destination behavior consists of every interleaving of its lane FIFOs. Event e occupies a fixed positive integer number s_e of abstract storage units until completion. Each lane has an independent capacity C_l>=0. U is the set of operations for which no admitted destination implementation is supplied. Exported canonical state and separately reserved helper storage must already satisfy a global state-compatibility gate. Failure of that gate is not represented merely by U and is not repairable by a cut theorem.

A structurally feasible cut is a Q-ideal D satisfying: (i) U subset D; (ii) for every lane l, sum of s_e over e not in D on l is at most C_l; and (iii) every destination completion order of E\D is legal under P. This is a relation on a fixed input. No lane remapping, future admission, synthesized fence, speculative rollback, fault, delayed external write, or hidden environmental enabling condition is included.

## 2. Order separation and forced earlier endpoints

**Lemma 1 (FIFO order separation).** For R subset E, every H-linear extension of R is a P-linear extension of R if and only if P restricted to R is a subset of H restricted to R.

*Proof.* Inclusion suffices because each required pair is then respected by every H-linear extension. For necessity, suppose a P b with a,b in R but not a H b. Because P follows the numbering, a<b. If a and b shared a lane, a H b, a contradiction. Thus they are on different lanes and incomparable in H. Complete b's lane prefix through b before completing a, interleaving any other lanes arbitrarily while preserving each lane order. This is an H-linear extension with b before a, and it violates P. The emitted identities distinguish the bad order even if the operations happen to commute or return equal values. Q does not constrain the destination. Q is used only to characterize the source cut. QED.

Define T={a: there exists b with a P b and lane(a)!=lane(b)}.

**Lemma 2 (mandatory earlier endpoint).** Every feasible D contains T, and hence contains down_Q(U union T), where down_Q includes its argument reflexively.

*Proof.* Take a in T with witness b. If b belongs to D, then a belongs to D because P subset Q and D is an ideal. If b does not belong to D but a also does not, Lemma 1 supplies an illegal destination order. Both alternatives force a into D. Unsupported operations must be in D by definition. Source ideality closes both sets downward. QED.

**Theorem 1 (feasibility normal form).** A set D is feasible exactly when D is a Q-ideal, it contains down_Q(U union T), and its residual per-lane sums fit capacity.

*Proof.* Necessity follows from the definition and Lemma 2. For sufficiency, U is drained and storage fits. A residual P pair cannot cross lanes because its earlier endpoint would belong to T subset D. Therefore P restricted to the residual is a subset of H, and Lemma 1 gives the required trace condition. QED.

**Corollary 1 (upward closure among ideals).** If D is feasible and D subset D' with D' a Q-ideal, then D' is feasible.

*Proof.* D' still contains all mandatory operations. Positive storage sizes imply that removing additional operations cannot increase a residual sum. Apply Theorem 1. QED.

The qualifier "among ideals" matters. An arbitrary superset can break source executability, so feasibility is not an upward-closed Boolean predicate on all subsets without first imposing ideality. The all-event set E is always structurally feasible. This does not assert that an incompatible canonical-state format becomes compatible.

## 3. Exact leastness diagnosis for arbitrary Q

Let up_Q(e)={e} union {f:e Q f}, and M_e=E\up_Q(e).

**Lemma 3 (maximal exclusion).** M_e is the greatest Q-ideal not containing e.

*Proof.* If y belongs to M_e and x Q y, x cannot equal e or follow e, since transitivity would then make y follow e. Thus x belongs to M_e. If an ideal D omits e, it must omit all Q successors of e: otherwise its downward closure would contain e. Hence D subset M_e. QED.

Let the nonempty family of feasible cuts be C. Define F={e: M_e is infeasible}.

**Theorem 2 (leastness dichotomy).** F equals the intersection of all cuts in C. A least feasible cut exists if and only if F is feasible, in which case F is that unique inclusion-least cut. Otherwise there are two feasible cuts A,B whose intersection is infeasible. Their pair certifies that no least cut exists.

*Proof.* If a feasible D omits e, Lemma 3 gives D subset M_e. Since M_e is an ideal, Corollary 1 makes M_e feasible. Conversely, if M_e is feasible it is itself a feasible cut omitting e. Thus e belongs to every feasible cut exactly when M_e is infeasible, proving the intersection statement. An intersection of ideals is an ideal. If F is feasible, it belongs to C and is contained in every member, so it is least and unique as a least element. If a least cut L exists, L equals the intersection of C, hence equals F and F is feasible.

For an explicit witness when F is infeasible, start A=E. For each e not in F, consider the feasible cut M_e. Replace A by A intersection M_e only while the intersection remains feasible. The intersection of all these M_e is F: each e outside F is removed by its own M_e, and every element of F lies in each feasible M_e. Because F is infeasible, there is a first step with A feasible, B=M_e feasible, but A intersection B infeasible. If a least feasible L existed, L would be contained in A intersection B; their intersection is an ideal and upward closure from L would make it feasible, a contradiction. QED.

This theorem is a direct application of monotonicity on an ideal lattice. It is stated explicitly to expose, rather than conceal, the standard reasoning. The nontrivial architectural obligation preceding it is the exact feasibility normal form and the necessity of its observation, source-order and storage assumptions.

The forced set can also be written without feasibility calls:

F = down_Q(U union T) union {e : for some lane l, sum_{f in up_Q(e), lane(f)=l} s_f > C_l}.

Indeed, apply Theorem 1 to M_e. Its residual is exactly up_Q(e). It omits an element of U or T exactly when e is below such an element. Its remaining possible failure is the displayed capacity test. This form yields local necessity witnesses.

## 4. Source-aligned FIFO fast path

Assume each lane is a chain of Q: whenever i<j are on the same lane, i Q j. Write lane l's complete list as e_1,...,e_m. Let p_l be the smallest r in {0,...,m} such that sum_{j=r+1}^m s_{e_j} <= C_l. Define K_l={e_1,...,e_{p_l}} and K=union_l K_l.

**Lemma 4 (forced capacity prefix).** Every feasible D contains K.

*Proof.* Take e_j in K_l. Minimality of p_l and positive sizes imply that the suffix sum starting at e_j exceeds C_l. If e_j is retained, no later e_t on that lane may be drained: source ideality and e_j Q e_t would force e_j to be drained as well. The entire suffix would then remain and exceed capacity. Hence e_j must be drained. QED.

**Theorem 3 (least aligned drain).** D*=down_Q(U union T union K) is feasible and is contained in every feasible cut. All feasible cuts are exactly the Q-ideals containing D*.

*Proof.* Lemmas 2 and 4 force each seed in every feasible cut, and ideality forces D*. Conversely, D* is an ideal and includes U and T. Removing K alone fits every lane by construction; D* removes at least K, so positive sizes imply that its residual also fits. Theorem 1 makes D* feasible. Corollary 1 then characterizes all feasible cuts. QED.

**Corollary 2 (cost scope).** D* minimizes every set-inclusion-monotone drain cost. For strictly positive additive event costs it is the unique cost minimizer. With nonnegative costs, additional zero-cost events may give other minimizers.

*Proof.* D* is contained in every feasible D. Apply cost monotonicity; strict positivity makes every proper superset strictly more costly. QED.

This does not minimize transfer time, source completion makespan, destination execution time, or energy. Those quantities need not be inclusion monotone: completing more events may reduce copied bytes or overlap work. It also does not optimize Q or the lane map.

## 5. Capacity-robust alignment after unavoidable completion

Let B=down_Q(U union T) and R=E\B. Call the input effectively aligned when every destination lane restricted to R is a Q-chain. This is weaker than aligning every event: an incomparable event already forced into B does not constrain the surviving FIFO. For fixed P,Q,lane,U and positive sizes, call the input capacity-robust when a least feasible cut exists for every vector of nonnegative integer independent lane capacities. This definition varies capacities only, not operation semantics, source order, placement or sizes.

**Theorem 4 (exact capacity-robustness criterion).** An input is capacity-robust if and only if it is effectively aligned. In the aligned case, form each lane's shortest capacity-removal prefix K_l using only R, and put K=union_l K_l. Then its least cut is down_Q(B union K).

*Proof of sufficiency.* Every feasible cut already contains B by Theorem 1. A retained element of a residual lane forces every later residual lane element to remain because that lane is a Q-chain. Hence the suffix argument of Lemma 4 forces K in every feasible cut. Removing B and K fits every capacity, and closing downward can only remove more events. Theorem 1 gives feasibility and leastness exactly as in Theorem 3. This works for every capacity vector, including empty residual lanes and zero capacities.

*Proof of necessity.* Suppose some residual lane S is not a Q-chain. Repeatedly remove its unique minimal element for as long as such an element exists. In a finite poset a unique minimal element precedes every other element: following predecessors from any element must end at a minimal element, and uniqueness identifies it. Thus the removed prefix J is a chain below every element still present. Because S is not a chain, this procedure reaches a nonempty tail V with at least two minimal elements, rather than exhausting S.

No element e of V precedes all of V. Otherwise it would be V's unique minimal element. Therefore every cone up_Q(e) intersect V is a proper subset of V. Positive sizes imply

C = max_{e in V} sum_{f in up_Q(e) intersect V} s_f < sum_{f in V} s_f.

Set the chosen lane's capacity to C. Give every other lane its complete residual load; these other capacities impose no additional restriction above B. For any e in R, its Q-upset cannot intersect B: otherwise ideality of B would force e into B. In the chosen lane, each element of J has all of V above it, so its upper-cone load exceeds C and it is forced. Each element of V has an upper-cone load on that lane at most C and loads on all other lanes at most their full-load capacities. It is not in B, so the explicit forced-set formula of Theorem 2 shows that it is not forced. Consequently the intersection F of all feasible cuts contains precisely J from S. Its residual on this lane is V and exceeds C, so F is infeasible. By Theorem 2 no least cut exists at this capacity vector. This proves the contrapositive and constructs an obstruction. QED.

The necessity proof does not infer nonexistence merely from an arbitrary incomparable pair: that pair could already be forced by B or preceded by a compulsory serial prefix. Stripping the unique-minimum prefix and using the first remaining fork is essential. Cross-lane Q edges do not invalidate the argument because cone loads already include their transitive consequences.

**Corollary 3 (precise encoder boundary).** If every complete residual lane load fits the implementation's maximum scalar capacity, the same criterion is exact over its admitted capacity range. Every capacity above a full load is equivalent to that full load, and the constructed obstruction uses no larger capacity. Without this representable-total assumption, the mathematical theorem still holds but necessity over the *truncated encoded capacity range* need not hold. For example, take u Q j and v Q j, with u,v incomparable, all on one lane, and give all three events size M, where M is the largest encoded capacity. Every encoded capacity C<M forces all events; C=M has least cut {u,v}. The lane is unaligned but its no-least obstruction C=2M is outside that encoded domain. The repository explicitly rejects an unrepresentable obstruction instead of claiming a represented counterexample.

The generic structure behind the criterion is the interaction of positive threshold constraints with ideals. We do not claim a new general theory of lattice-linear predicates. Its use here is an exact static contract: after unavoidable capability and order work is removed, source-chain lane layouts guarantee a canonical least migration cut under independently varying capacity budgets. It does not optimize a layout or infer a physical capacity allocation policy.

**Worked first-fork example (manuscript Figure 2).** Take P empty, Q generated by 0<1, 0<2, 1<3 and 2<3, one FIFO (0,1,2,3), U empty, and sizes (2,3,4,1). The unique-minimum prefix is J={0}; V={1,2,3} has weight 8. The residual upper-cone weights of 1,2,3 are respectively 4,5,1, so the constructed capacity is 5. Both A={0,1} and B'={0,2} are Q-ideals; their retained weights are 5 and 4. Their intersection {0} retains weight 8 and is infeasible. This is a specified mathematical example, not an extra sampled workload. Its input is retained in inputs/fork.json.

## 6. Certificates and decidability

For a proposed least cut D, the validator first checks input well-formedness and Theorem 1's equivalent direct postconditions. It then requires one necessity explanation for every e in D. An explanation names a root r with e=r or e Q r and one of:

* Unsupported: r belongs to U.
* Missing order: r P b for some b on another lane.
* Over-capacity upper cone: for a named lane l, up_Q(r)'s residual sum on l exceeds C_l.
* Aligned suffix shortcut: r's lane suffix exceeds capacity and each later lane element is a Q successor of r.

Every root is necessarily drained by Lemma 2 or the corresponding capacity argument. Source closure forces e. Therefore a feasible D with a valid explanation for every member is contained in every feasible cut, so is least. Conversely, when a least cut exists, the formula for F supplies a permitted explanation for each member. The aligned synthesis also supplies these witnesses. Necessity certificates are therefore sound and complete for the admitted fixed grammar; the implementation is finite executable validation, not a mechanized proof of the Python interpreter.

A no-least certificate contains two sorted lists A,B. The validator checks that both are feasible and their intersection is infeasible. Theorem 2 establishes soundness, and its constructive proof establishes completeness. It need not run the synthesis algorithm to validate either certificate form. A no-least certificate is not a migration cut or a minimum-cost solution.

With n<=512, k<=512, n-bit predecessor masks, positive event sizes and capacities at most 2^63-1, all loops terminate and integer sums are exact Python integers. The mathematical theorem has arbitrary finite n; 512 is an implementation admission bound. A sum needs at most 63+ceil(log2(max(1,n))) bits, rather than silently wrapping at 64 bits. The straightforward maximal-exclusion implementation uses n safety queries and at most n witness-intersection queries. With explicit relations, each query costs O(n^2+kn) elementary relation/arithmetic operations, giving O(n^3+kn^2) overall plus input parsing. These are bit-complexity-sensitive bounds: arithmetic operates on O(63+log n)-bit sums and masks have n bits. The aligned formula and a direct certificate check use O(n^2+kn) such operations. No exponential order enumeration is required by either algorithm.

## 7. Boundaries, including hardness

**Counterexample A (alignment removed).** Let E={0,1}, P=Q empty, one destination FIFO 0 before 1, unit sizes, capacity one, U empty. Both {0} and {1} are feasible, but their intersection is empty and exceeds capacity. Thus a least drain need not exist. This does not violate Theorem 3 because that FIFO is not a Q chain.

**Counterexample B (independent capacity replaced by a pool).** Let two independent source events occupy separate one-element destination lanes but share a total retained-storage budget one. Both singleton drains are feasible and their intersection is infeasible. Here each lane individually is a Q chain, but the pooled budget does not have chain support. Independent lane budgets in Theorem 3 cannot silently be replaced by shared memory.

**Proposition 1 (weighted choice is NP-complete).** In the unbounded mathematical family (not the fixed 512-event encoder), deciding whether a feasible cut of additive cost at most B exists is NP-complete for binary-encoded weights, even for P=Q empty, one destination FIFO, and U empty.

*Proof.* Membership in NP follows by guessing D and checking capacity and cost in polynomial time. Reduce PARTITION with positive integers a_1,...,a_n of total 2B. Give event i size a_i and cost a_i; use capacity B. Any subset is a Q-ideal and every destination sequence is P-legal. Residual capacity requires sum_{i in D} a_i >= B. Cost at most B requires the reverse inequality. Thus a feasible cut within cost B exists exactly when a partition of sum B exists. The construction is polynomial in the binary input length. This is a weak NP-hardness reduction; no strong NP-hardness claim is made. QED.

This is the familiar knapsack obstruction exposed inside the migration model, not a new hardness principle. Diagnosing that no least cut exists does not solve this weighted choice problem.

**Counterexample C (leastness is not monotone in capacity).** With n>=2 independent source events of unit size assigned to one destination FIFO, capacity zero forces D=E and gives a least cut. Any capacity c with 0<c<n permits all sufficiently large drains but their intersection is empty and infeasible, hence no least cut exists. Capacity at least n makes the empty cut feasible and least. Increasing capacity never removes a feasible cut, but the existence of a least cut can change from true to false to true.

**Counterexample D (observation quotient).** Two commuting operations returning identical untagged results can have observationally identical orders after erasing event identities. Lemma 1's distinguishing counterexample is then unavailable. The cut conditions remain sufficient under any deterministic observation projection, because projection preserves trace inclusion, but necessity/minimality need not survive.

## 8. Complete arithmetic identities for the finite template grammar

For virtual width w>=1 let M=2^w and 0<=a,b<M, c in {0,1}. COPY returns b and preserves c. XOR returns bitwise a xor b and preserves c. ADD uses t=a+b; ADC uses t=a+b+c. Both return (t mod M, floor(t/M)). Because t<=2M-1, the carry is a single bit.

A widened implementation may use a physical unsigned width W>=w+1, but must compute the visible carry at bit w, not bit W. The mathematical sum t fits W bits because t<2^(w+1)<=2^W. Taking its low w bits and bit w therefore exactly gives the virtual result. Wider physical arithmetic with the physical carry flag instead returns zero for a=M-1,b=1 and w<W, while the virtual carry is one. Opcode agreement alone is insufficient.

For split arithmetic choose 1<=b0<=w (the implementation uses ceil(w/2)), L=2^b0 and H=2^(w-b0). Decompose a=a_h L+a_l and b=b_h L+b_l with low limbs in [0,L). For carry-in z (zero for ADD, c for ADC), let u=a_l+b_l+z, r_l=u mod L, c_l=floor(u/L). Let v=a_h+b_h+c_l, r_h=v mod H, c_h=floor(v/H). For H=1 the high limb is identically zero but the high-stage carry still exists. Direct substitution gives t=(v L)+r_l=(c_h H+r_h)L+r_l=c_h M+(r_h L+r_l). Since 0<=r_h L+r_l<M, quotient/remainder uniqueness proves the exact virtual result and carry. Splitting COPY and XOR limbwise is exact because these operations do not mix bit positions. No speculative intermediate result is externally emitted; scratch computations precede one atomic commit.

Serialization of each register in exactly ceil(w/8) bytes is a bijection between admitted w-bit values and the subset of byte strings whose unused high bits are zero. Explicit byte order reverses representation, not the represented integer. The carry occupies one checked byte in {0,1}. Decoding must check exact length, unused bits, carry range and declared width/byte order. Encoding followed by decoding in the same declared byte order is the identity. A target that cannot preserve a carry bit is globally incompatible even if the current epoch is empty: a later ADC of two zero operands distinguishes carry zero from carry one. Draining all pending operations does not repair this defect.

## 9. Migration composition and progress

Relate a concrete machine and abstract machine when their canonical states agree, completed event identities agree, pending event descriptors agree, the concrete pending execution order refines P, and exactly one owner may commit. At an operation boundary a concrete adapter's silent finite helper steps leave architectural state and observations unchanged; its single commit matches the corresponding abstract F_e by Section 8. A source completion during a certified drain is P-enabled because the completed set was a P-ideal, P subset Q, and the selected drain prefix respects Q. An accepted state transfer preserves canonical state and the residual descriptors and is silent. Its destination order refines residual P by Lemma 1. Disabling the donor before enabling a unique receiver preserves the ownership invariant.

**Theorem 5 (conditional finite-trace refinement).** Starting in related states, any finite sequence of completions and accepted migrations yields an architectural trace admitted by the abstract event machine and equal canonical state after each completion.

*Proof.* Induct on the finite sequence of concrete steps. Silent helper steps and accepted transfers leave the abstract state and trace unchanged and preserve the relation by their preconditions. At a commit, unique ownership and membership in the pending set prevent duplicates; the order invariant makes the event abstractly enabled; Section 8 gives the same result and state; removing exactly that event preserves equality of completed and pending sets. These are all concrete step types. Repeat the argument across any finite number of accepted migrations. QED.

The theorem assumes the descriptor-producing front end, P extraction, declared capabilities, atomicity and ownership contract are truthful. The checker validates a finite mathematical packet; it does not attest real hardware or implement a failure-tolerant distributed consensus protocol. Crashes, external DMA and asynchronous I/O are excluded.

Trace safety alone does not prove progress: two compatible destinations can exchange an unchanged pending epoch forever without any completion. Suppose instead there are at most B consecutive accepted migrations while pending work remains, every selected enabled operation finishes its bounded helper sequence, and the scheduler eventually selects an enabled event. A finite poset with pending elements has a minimal enabled event. Thus a completion occurs after at most B migrations, reducing pending count by one. Induction on N pending events bounds accepted migrations before completion of the epoch by B*N, excluding any optional transfers after the epoch is empty. Helper execution and scheduling assumptions are necessary; the statement is not a physical time bound.

New epochs compose only under a fresh admission check that their pending operations are executable on the current source. A target's ability to finish one residual epoch is not permission to admit arbitrary future unsupported instructions.
