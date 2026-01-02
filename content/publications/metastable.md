---
title: "The Metastable State of Fermi-Pasta-Ulam-Tsingou Models"
date: 2023-02-06
author: ["****Kevin A. Reiss****", "David K. Campbell"]
tags: ["Nonlinear Dynamics", "Metastability", "FPUT"]
image: "previews/metastable.png"
abstract: |
  Classical statistical mechanics has long relied on assumptions such as the equipartition theorem to understand the behavior of the  complicated systems of many particles. The successes of this approach are well known, but there are also many well-known issues with classical theories. For some of these, the introduction of quantum mechanics is necessary, e.g., the ultraviolet catastrophe. However, more recently, the validity of assumptions such as the equipartition of energy in classical systems was called into question. For instance, a detailed analysis of a simplified model for blackbody radiation was apparently able to deduce the Stefan--Boltzmann law using purely classical statistical mechanics. This novel approach involved a careful analysis of a "metastable" state which greatly delays the approach to equilibrium. In this paper, we perform a broad analysis of such a metastable state in the classical Fermi--Pasta--Ulam--Tsingou (FPUT) models. We treat both the $\alpha$-FPUT and $\beta$-FPUT models, exploring both quantitative and qualitative behavior. After introducing the models, we validate our methodology by reproducing the well-known FPUT recurrences in both models and confirming earlier results on how the strength of the recurrences depends on a single system parameter. We establish that the metastable state in the FPUT models can be defined by using a single degree-of-freedom measure---the spectral entropy ($\eta$)---and show that this measure has the power to quantify the distance from equipartition. For the $\alpha$-FPUT model, a comparison to the integrable Toda lattice allows us to define rather clearly the lifetime of the metastable state for the standard initial conditions. We next devise a method to measure the lifetime of the metastable state $t_m$ in the $\alpha$-FPUT model that reduces the sensitivity to the exact initial conditions. Our procedure involves averaging over random initial phases in the plane of initial conditions, the $P_1$-$Q_1$ plane. Applying this procedure gives us a power-law scaling for $t_m$, with the important result that the power laws for different system sizes collapse down to the same exponent as $E\alpha^2\rightarrow0$. We examine the energy spectrum $E(k)$ over time in the $\alpha$-FPUT model and again compare the results to those of the Toda model. This analysis
  tentatively supports a method for an irreversible energy dissipation process suggested by Onorato et al.: four-wave and six-wave resonances as described by the "wave turbulence" theory. We next apply a similar approach to the $\beta$-FPUT model. Here, we explore in particular the different behavior for the two different signs of $\beta$. Finally, we describe a procedure for calculating $t_m$ in the $\beta$-FPUT model, a very different task than for the $\alpha$-FPUT model, because the $\beta$-FPUT model is not a truncation of an integrable nonlinear model.
bibtex: |
  @article{reissMetastableStateFermi2023,
    title = {The Metastable State of Fermi-Pasta-Ulam-Tsingou Models},
    author = {Reiss, Kevin A. and Campbell, David K.},
    year = 2023,
    month = feb,
    journal = {Entropy},
    volume = {25},
    number = {2},
    pages = {300},
    publisher = {Multidisciplinary Digital Publishing Institute},
    issn = {1099-4300},
    doi = {10.3390/e25020300},
    url = {https://www.mdpi.com/1099-4300/25/2/300}
  }

publication: "*Entropy*, vol. 25, no. 2"
doi: "10.3390/e25020300"
build:
  render: never
  list: local
  publishResources: false
---