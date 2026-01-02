---
title: "The Metastable State of Fermi-Pasta-Ulam-Tsingou Models"
date: 2022-05-04
author: ["****Kevin A. Reiss****"]
publication: "*Senior Honors Thesis*"
tags: ["Nonlinear Dynamics", "Metastability", "Thesis", "FPUT"]
image: "previews/thesis.jpg"
abstract: |
  Classical statistical mechanics has long relied on assumptions like the equipartition theorem to solve complicated systems of many particles. The successes of this approach are many, but there are also many well-known issues with classical theories for which the introduction of quantum mechanics is necessary, e.g. the ultraviolet catastrophe. However, more recently, the validity of assumptions like this have been called into question. A more careful analysis of a simplified model for blackbody radiation was able to elicit the Stefan-Boltzmann law using purely classical statistical mechanics. The novel approach was a careful analysis of a "metastable" state which delays the approach to equilibrium.

  In this thesis we perform a broad analysis of the metastable state in the $\alpha$-FPUT and $\beta$-FPUT models, both quantitative and qualitative. We start with a visualization of the metastable using spectral entropy ($\eta$). This single degree of freedom has the power to quantify the distance to equipartition. A comparison to the integrable Toda model allows us to define the lifetime of the metastable state.

  We visualize the strength of recurrences in the $\alpha$-FPUT model, yielding the surprising result that the recurrence strength is a function only of the essential system parameter $R=\left(N+1\right)^{3/2}\sqrt{E\alpha^2}$ for the $\alpha$-FPUT model. We devise a method to measure the lifetime of the metastable state $t_m$ in the $\alpha$-FPUT model. Our procedure involves averaging over random initial phases in the $P_1$-$Q_1$ plane. This bin average provides a relevant length distance, the standard deviation, from which we then determine when the $\alpha$-FPUT model trajectories break off from the entropy of the Toda model. Applying this procedure gives us a power law scaling for $t_m$, with the surprising result that the power laws for different system sizes collapse down to the same exponent as $E\alpha^2\rightarrow0$.

  We explore the spectrum of the $\alpha$-FPUT model, compared to that of the Toda model. This analysis suggestively demonstrates a method for an irreversible energy dissipation process proven by Onorato et al.: four-wave and six-wave resonances. These preliminary results appear to confirm the presence of these resonances, but more work is needed on the subject. A similar depiction is given for the $\beta$-FPUT model. We explore different behavior for the two different signs of $\beta$. Last, we describe a procedure for calculating $t_m$ in the $\beta$-FPUT model, a very different task than for the $\alpha$-FPUT model since the $\beta$-FPUT model is not the truncation of an integrable model.
bibtex: |
  @phdthesis{reissMetastableStateFermi2022,
    title = {The Metastable State of Fermi-Pasta-Ulam-Tsingou Models},
    author = {Reiss, Kevin A.},
    year = 2022,
    month = may
  }

doi: ""
arxiv: ""
pdf: "papers/ReissHonorsThesis.pdf"
build:
  render: never
  list: local
  publishResources: false
---