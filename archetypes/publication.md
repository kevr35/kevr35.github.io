---
title: "{{ replace .Name "-" " " | title }}"
date: {{ .Date }}
author: ["****Kevin A. Reiss****"]
publication: "*Journal Name*"
tags: ["Quantum Mechanics", "Condensed Matter"]
image: "previews/nature.png" # Place in static/previews/
doi: ""
arxiv: ""
pdf: ""
external_url: ""
url_label: "Store"
build:
  render: never
  list: local
  publishResources: false
---