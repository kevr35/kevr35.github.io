---
title: "Simultaneous Observables"
summary: ""
date: 2026-02-12
math: true
---

In quantum mechanics, if two observables do not commute ($[A,B]\neq0$), we generally say that they are not simultaneously observable and do not share an eigenbasis. However, this is not necessarily true for all states! For example, consider **L**$^2$ and $L_z$. They commute, and we assign separate quantum numbers to their eigenvalues: $l$ for **L**$^2$ and $m$ for $L_z$. However, $L_z$ does not commute with $L_x$ or $L_y$. In particular:

$$
[L_p,L_q]=i\hbar\epsilon_{pqr}L_r.
$$

However, the state with $l=0$ immediately tells us the value of the quantum number $m$ -- it's also 0. The interesting thing about this state is that it also has definite $L_x=L_y=L_z=0$. There is a subset of the whole Hilbert space which may be a simultaneous eigenbasis for two non-commuting observables. That is to say, there are exceptional states $\ket\psi$ such that:

$$
AB\ket\psi = BA\ket\psi,
$$

even if $[A,B]\neq0$. Which states are these? Well, it might have already occurred to you, that $\ket\psi$ has to be in the *kernel* (or null space) of the commutator $[A,B]$. That is since, from the previous equation:

$$
AB\ket\psi - BA\ket\psi = (AB-BA)\ket\psi = [A,B]\ket\psi = 0.
$$

Knowing the measurement of these observables simultaneously does not violate the uncertainty relation, since for these states, $\langle[A,B]\rangle=0$,

$$
\Delta A ~ \Delta B \geq \frac{1}{2}\langle[A,B]\rangle=0.
$$

Therefore, only observables whose commutator is *full rank* will not share any eigenstates. For example,

$$
[x,p] = i\hbar
$$

Since the commutation between $x$ and $p$ is proportional to the identity, which has no kernel, there are no states with certain $x$ that also have certain $p$. Back to our angular momentum example, for the $\ket{l=0}$ state, we have:

$$
[L_p,L_q]\ket{l=0}=i\hbar\epsilon_{pqr}L_r\ket{l=0}=0,
$$

which verifies that this state is in the null space of the commutator of any of the angular momenta axes.
