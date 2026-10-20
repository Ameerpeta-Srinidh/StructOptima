#!/usr/bin/env bash
# Build StructOptima-Formulas.pdf from the .tex source (Tectonic downloads the LaTeX packages on first use).
set -euo pipefail
cd "$(dirname "$0")"
if command -v tectonic >/dev/null; then
    tectonic -X compile StructOptima-Formulas.tex
else
    pdflatex -interaction=nonstopmode StructOptima-Formulas.tex >/dev/null
    pdflatex -interaction=nonstopmode StructOptima-Formulas.tex >/dev/null
    rm -f StructOptima-Formulas.{aux,log,out,toc}
fi
