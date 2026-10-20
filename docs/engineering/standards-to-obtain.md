# Standards and Inputs to Obtain

**As of:** 2026-10-20. The documents the owner must provide so that the cited values can be verified
(gap analysis P3, WI-10) and the high-rise phase can start. The PDFs themselves are copyrighted (BIS) and
the repository is public: put them in the **git-ignored** folder `_local/standards/` (subfolders as listed),
never in the repository.

Put each PDF in the subfolder shown, named `<number>_<year>.pdf`, e.g. `IS_456_2000.pdf`.
Include every amendment issued for that edition, as a separate `..._Amd<N>.pdf` or inside the same PDF.
Editions marked "latest" must be checked on the BIS site (standardsbis.bis.gov.in) when buying.

## A. Needed now: verify the existing low/mid-rise RC frame design (gap-analysis P3)

| Done | Folder | Standard | Used for in StructOptima |
|---|---|---|---|
| [ ] | core/ | IS 456:2000 + all amendments | all member design, Table 16A/18/19/20/26, Annex E, Cl 20.5, 23.2, 25, 26, 34, 38–40 |
| [ ] | core/ | IS 1893 (Part 1):2016 + amendments | zone factors, spectrum, I, R, period, drift, irregularities |
| [ ] | core/ | IS 13920:2016 + amendments | SCWB, joint shear, confining steel (Ash), end zones |
| [ ] | core/ | IS 875 (Part 1):1987 | unit weights of materials |
| [ ] | core/ | IS 875 (Part 2):1987 | imposed (live) loads by occupancy |
| [ ] | core/ | IS 875 (Part 3):2015 + amendments | wind speed, k1–k4, Cpe/Cpi, gust factor |
| [ ] | core/ | IS 875 (Part 5):1987 | load combinations, special loads |
| [ ] | core/ | SP 16:1980 | design aids, used as an independent benchmark |
| [ ] | core/ | SP 34:1987 | reinforcement detailing (laps, anchorage, drawings) |
| [ ] | core/ | IS 1786 (latest) | rebar grades and properties (Fe415/Fe500/Fe500D/Fe550D) |
| [ ] | foundations/ | IS 1904 (latest) | general foundation requirements |
| [ ] | foundations/ | IS 6403:1981 | bearing capacity of shallow foundations |
| [ ] | site/ | IS 2502 (latest) | bending and fixing of bars (BBS shapes) |
| [ ] | site/ | IS 10262:2019 | concrete mix proportioning (Site Tools mix design) |
| [ ] | site/ | IS 516 (latest, Part 1) | cube testing (cube register) |
| [ ] | site/ | NBC 2016, Part 4 (Fire) and Part 6 (Structural Design) | fire rating by height, structural provisions |
| [ ] | quantities/ (lower priority) | IS 1200 (relevant parts), IS 1077, IS 2250, IS 1661, IS 1905 | quantity measurement, bricks, mortar, plaster, masonry |

## B. Needed for high-rise buildings (next phase)

| Done | Folder | Standard | Why |
|---|---|---|---|
| [ ] | highrise/ | IS 16700 (latest, tall concrete buildings) | the governing code for tall RC buildings: height limits, systems, drift, dynamic analysis, walls |
| [ ] | highrise/ | IS 875 (Part 3):2015, dynamic wind clauses (already in A) | gust factor and across-wind response for tall/slender buildings |
| [ ] | highrise/ | IS 1893 (Part 1):2016, response spectrum clauses (already in A) | modal / response-spectrum analysis is required above the equivalent-static limits |
| [ ] | highrise/ | IS 13920:2016, special shear wall clauses (already in A) | shear walls and cores, boundary elements, coupling beams |
| [ ] | foundations/ | IS 2911 (Part 1/Sec 2) (latest) | bored cast-in-situ piles |
| [ ] | foundations/ | IS 2911 (Part 4) (latest) | pile load tests |
| [ ] | foundations/ | IS 2950 (Part 1) (latest) | raft foundations |
| [ ] | highrise/ | IS 16172 (latest) | mechanical couplers (rebar splicing in heavy columns and walls) |
| [ ] | highrise/ (only if used) | IS 3370 (Part 1 and 2) (latest) | water-retaining tanks (terrace / underground tanks) |
| [ ] | highrise/ (only if used) | IS 1343 (latest) | post-tensioned slabs |
| [ ] | highrise/ (only if used) | IS 800:2007 | any steel members (roof structures, connections) |

## C. Non-code material for high-rise (put in `_local/highrise-inputs/`)

1. **Scope decisions, written in `_local/highrise-inputs/scope.md`:**
   - target height or number of storeys, and the seismic zones to support;
   - structural system: moment frame, frame plus shear walls/core, or flat slab plus core;
   - basements and podium: yes/no and how many;
   - transfer floors and floating columns (recommended: not supported);
   - occupancy.
2. **Plans of at least one real or realistic high-rise (DXF):** basement, podium, typical floor and terrace plans,
   with the lift/stair core, shafts and floor heights.
3. **A geotechnical investigation report** for that site: SBC and settlement, pile capacities, subgrade modulus,
   groundwater level, liquefaction assessment.
4. **Independent benchmark results:** an ETABS/STAAD model output, or a published worked example of a tall building
   (periods and mode shapes, base shear, drifts, a few member forces). The new 3D engine will be checked against it.
5. **Material availability:** concrete grades (M30–M60?) and steel grade (Fe500D / Fe550D) used locally.
6. **Local requirements:** the building bye-laws and fire rules that set the high-rise height threshold.
7. **The reviewing engineer:** the name of a licensed structural engineer willing to review benchmarks and sign off
   decisions (required before anything is marked verified).
