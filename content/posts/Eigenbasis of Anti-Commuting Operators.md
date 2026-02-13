---
title: Eigenbasis of Anti-Commuting Operators
summary: ""
date: 2026-02-13
math: true
---

Suppose that we have two operators $A$ and $B$ such that:

$$
AB=-BA.
$$

In other words, they anti-commute. What can we say about their eigenbasis? It is well known that for *commuting* operators, they *share* an eigenbasis, i.e. their eigenkets are identical. 

First, let's look at the representation of $B$ in the basis defined by the eigenbasis of $A$. Let $A=\sum_{i} a_i\ket{a_i}\bra{a_i}$ be the spectral decomposition of $A$. Then,

$$
\bra{a_i}(AB+BA)\ket{a_j} = (a_i+a_j)\bra{a_i}B\ket{a_j}=0 \tag{1}
$$

This tells us immediately that if $a_i\neq-a_j$, then $\bra{a_i}B\ket{a_j}=0$. One immediate consequence is that if all of the eigenvalues of $A$ are nonzero, then the diagonal of $B$ in the $A$ basis is 0, since the diagonal is where $a_i=a_j$ and $a_i=-a_j$ is only met if $a_i=0$. Then sum of the diagonal elements of $B$ is 0 as well -- and since the trace is basis-independent, this is the trace of $B$. That is to say, if $A$ is invertible (has no zero-eigenvalues) then any operator which anti-commutes with $A$ will have to have 0 trace.

Another consequence of Equation (1) is that the matrix elements of $B$ in the $A$ basis are only nonzero for entries where $a_i=-a_j$. This tells us that unless an invertible operator has at least one set of eigenvalues which are each others negation, that operator can only anti-commute with the zero operator.

If $A$ is invertible, has distinct eigenvalues, and has an odd dimension (e.g. 3x3) then $B$ is singular. 

<!-- The hypothesis is that for anti-commuting their eigenkets will be minimally similar. Let's start with the spectral decomposition of the operators:

$$
A = \sum_i a_i \ket{a_i}\bra{a_i},
$$

and:

$$
B = \sum_i b_i \ket{b_i}\bra{b_i},
$$

where $a_i$ and $b_i$ are the eigenvalues of $A$ and $B$ respectively.  -->