# Formal Model

This document states the same content as `architecture.md` in
mathematical notation. It is intended for readers who want to verify
that the implementation respects a documented model, or who want to
adapt the engine to a different setting (e.g. continuous state, or
non-classical weights).

The engine is *classical* in the precise sense that all weights are
non-negative reals and aggregation is linear. The "quantum measurement"
language used throughout the README is interpretive: the engine
implements the *bookkeeping* of the von-Neumann measurement picture
(partition, projection, collapse, history) without amplitudes or
unitary dynamics between measurements.

## 1. State space

A *state space* is a finite set of micro-states with a probability
weight on each:

$$
\Omega = \{\omega_1, \omega_2, \ldots, \omega_n\}, \qquad
\mu : \Omega \to [0, 1], \qquad
\sum_{\omega \in \Omega} \mu(\omega) = 1.
$$

A *state* is the pair $S = (\Omega, \mu)$. The engine maintains a
single global state at any time; it is the data that
`engine.state.StateManager` mutates.

## 2. Question

A *Question* $Q$ partitions $\Omega$ into a finite, exhaustive, disjoint
family of subsets:

$$
\pi_Q : \Omega \to 2^{\Omega}, \qquad
\pi_Q(\Omega) = \{E_1, E_2, \ldots, E_k\},
$$

with $E_i \cap E_j = \emptyset$ for $i \neq j$ and
$\bigcup_i E_i = \Omega$. Each $E_i$ is called a *SET* of the partition.

A full $Q$ in the implementation carries additional parameters:

$$
Q = (\mathrm{id}, \pi_Q, h_Q, \rho_Q, \alpha_Q, \lambda_Q, \nu_Q),
$$

where $h_Q$ is the history-scope function, $\rho_Q$ the
correlation policy, $\alpha_Q$ the weight modifier, $\lambda_Q$ the
lifetime, and $\nu_Q$ the visibility. Only $\pi_Q$, $h_Q$, $\lambda_Q$,
and $\nu_Q$ are required.

## 3. Projection

Given a state $S = (\Omega, \mu)$, the *projection* of $Q$ is the
SET-indexed weight function

$$
P_Q(S) : \pi_Q(\Omega) \to [0, 1], \qquad
P_Q(S)(E_i) = \sum_{\omega \in E_i} \mu(\omega).
$$

By construction $\sum_i P_Q(S)(E_i) = 1$ when $\mu$ is normalised, so
$P_Q(S)$ is itself a probability distribution over the partition's
SETs.

If $\nu_Q \neq \mathrm{PRIVATE}$ and $\rho_Q$ is defined, the
projection is replaced by

$$
P_Q^{\mathrm{corr}}(S, \mathcal{P}, H) = \rho_Q\!\big(P_Q(S), \mathcal{P}, H\big),
$$

where $\mathcal{P}$ is the set of all projections in the current
window and $H = h_Q(\text{global history})$ is the slice of history
the Q is permitted to read.

If $\alpha_Q$ is defined, the engine then applies
$P_Q^{\mathrm{final}} = \alpha_Q(P_Q^{\mathrm{corr}})$. The
implementation does not assume any properties of $\rho_Q$ or
$\alpha_Q$ beyond the type signature; the caller is responsible for
ensuring the output is a valid distribution.

## 4. Measurement window

A *measurement window* is the tuple

$$
MW = (\mathrm{id}, t_{\mathrm{open}}, \mathcal{Q}_{MW}, \mathcal{P}_{MW}),
$$

where $t_{\mathrm{open}}$ is the open-time timestamp,
$\mathcal{Q}_{MW} = \{Q_1, \ldots, Q_n\}$ is the active question set,
and $\mathcal{P}_{MW} = \{P_{Q_1}^{\mathrm{final}}, \ldots, P_{Q_n}^{\mathrm{final}}\}$
is the projected set (populated by the engine during the PROJECTION
phase).

## 5. Collapse

The *collapse* operator takes a populated window and produces a single
SET id $R$ plus a new state $S'$.

**Step 1 — aggregate.** Let $\mathcal{E}$ be the union of all SET ids
appearing in any $P_{Q_i}^{\mathrm{final}}$:

$$
W(E) = \sum_{Q_i \in \mathcal{Q}_{MW}} P_{Q_i}^{\mathrm{final}}(E),
\qquad E \in \mathcal{E}.
$$

**Step 2 — normalise.**

$$
\widetilde{W}(E) = \frac{W(E)}{\sum_{E' \in \mathcal{E}} W(E')}.
$$

**Step 3 — sample.**

$$
R \sim \mathrm{Categorical}\!\big(\widetilde{W}\big).
$$

**Step 4 — back-resolve to micro-states.** Pick any $Q_i$ such that
$R \in \pi_{Q_i}(\Omega)$ and set $\Omega' = \pi_{Q_i}^{-1}(R)$. (Any
such $Q_i$ produces the same $\Omega'$ provided the partitions are
honestly disjoint inside each Q.)

**Step 5 — new state.** The post-collapse state is the uniform
distribution over $\Omega'$:

$$
S' = (\Omega', \mu'), \qquad
\mu'(\omega) =
\begin{cases}
\frac{1}{|\Omega'|} & \omega \in \Omega', \\
0 & \text{otherwise}.
\end{cases}
$$

This is what the README refers to as the *DIRAC delta*. The
engine never reintroduces weight on micro-states that did not survive
collapse.

## 6. Time and history

Time is defined as the cardinality of the history:

$$
T = |H|.
$$

A history entry is the quadruple

$$
H_t = (t, MW^{\mathrm{snapshot}}_t, R_t, n_t),
$$

where $MW^{\mathrm{snapshot}}_t$ is a complete record of the window
(its id, its open time, its active questions, its projected set), and
$n_t$ is the measurement number at the time of collapse.

The engine guarantees that an entry is written *if and only if* a
collapse occurred — there is no history entry for a window that never
collapsed.

## 7. Entropy

The Shannon entropy of a state is

$$
H(S) = -\sum_{\omega \in \Omega} \mu(\omega) \log_2 \mu(\omega).
$$

After a collapse, $H(S') \leq H(S)$ (equality holds only in the
degenerate case where the chosen SET already had weight 1 before
projection, which the engine handles trivially). The *information
gain* of the measurement is

$$
I = H(S) - H(S').
$$

The engine does not currently compute or expose $H(S)$; it would be a
natural addition.

## 8. Invariants, restated

The five invariants from the README, in this notation:

1. **One window, one collapse.** $\mathrm{collapse}(MW)$ is callable
   at most once for any given $MW$.
2. **State immutability during a window.** $S(t) = S(t_{\mathrm{open}})$
   for $t \in [t_{\mathrm{open}}, t_{\mathrm{collapse}})$.
3. **Q scoping.** $Q \in \mathcal{Q}_{MW}$ is valid only while $MW$ is
   open; afterwards, any access to $Q$ raises.
4. **Atomic collapse.** Steps 3 through 7 of collapse are performed in
   one method invocation with no observable intermediate state.
5. **History completeness.** Every history entry contains the full
   $MW^{\mathrm{snapshot}}$ at the time of collapse.

The implementation enforces all five at runtime via the phase state
machine and via `_invalidated` flags on Questions.

## 9. What the model does not say

- Nothing about *unitary evolution*: there is no operator that moves
  state between measurements.
- Nothing about *amplitudes or interference*: all aggregation is
  linear over non-negative reals.
- Nothing about *continuous state spaces*: $\Omega$ is finite.
- Nothing about *concurrency*: a single MW is processed by a single
  thread.

These are deliberate simplifications. Removing any of them is a
research project, not a bug fix.
