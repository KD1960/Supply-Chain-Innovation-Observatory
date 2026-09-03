# 2026-Q3 — re-export ABI/INFORM with abstracts

**Why:** every ABI/INFORM export so far was ProQuest's default *Citation only*,
which carries no abstract. Trade press has been reaching the matcher as about
26 words of subject headings instead of prose. Re-exporting fixes three things
at once — the abstracts, the lexicon (v9 → **v10**, two technologies retired and
two tightened), and the window, which was three days short at the back end.

**Window for all of them: 2026-07-01 to 2026-09-30.**

---

## Before you start

**1. Delete the fifteen files already there.** They are v9 terms on the old
window with no abstracts, and there are now **twelve** exports rather than
fifteen — the `terms5` files have no successor and would be imported as stale
extras. From the project folder:

```bash
rm '/Users/kevindooley/Claude/Projects/Supply chain innovation'/data/manual/2026-Q3/abi_inform-*
```

**2. In ProQuest, choose the export option that includes the abstract** —
"Citation, abstract & indexing", not the default "Citation only". This is the
whole point of the exercise; if it is missed, `--import-manual` will now say so
rather than letting it pass.

**3. Clear the marked-items list between exports.** It accumulates, and the
importer refuses overlapping files.

**4. An empty result still needs a file** — a zero-record export plus its
`.meta.yaml` with `records: 0`. That is what separates *looked and found
nothing* from *never looked*.

---

## 1. `abi_inform-SupplyChainDive-terms1.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Dive")) AND ("warehouse robot" OR "piece picking" OR "sidewalk robot" OR "autonomous truck" OR "shore power" OR "WMS" OR "advanced planning system" OR "demand forecasting" OR "digital matching" OR "language model" OR "blockchain provenance" OR "cold chain sensor" OR "micro fulfilment" OR "positive train control" OR "quantum inspired optimisation") AND pd(2026-07-01-2026-09-30)
```

## 2. `abi_inform-SupplyChainDive-terms2.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Dive")) AND ("AMR" OR "humanoid robot" OR "delivery drone" OR "electric semi" OR "enterprise resource planning" OR "manufacturing execution system" OR "APS" OR "control tower" OR "vehicle routing" OR "item level rfid" OR "critical mineral supply chain" OR "active packaging" OR "automated damage inspection" OR "inland port" OR "green logistics") AND pd(2026-07-01-2026-09-30)
```

## 3. `abi_inform-SupplyChainDive-terms3.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Dive")) AND ("AMRs" OR "autonomous yard truck" OR "BVLOS" OR "hydrogen truck" OR "ERP" OR "MES" OR "agentic sourcing" OR "transportation management system" OR "MAPF" OR "digital product passport" OR "battery free" OR "additive manufacturing" OR "risk monitoring platform" OR "private 5g network") AND pd(2026-07-01-2026-09-30)
```

## 4. `abi_inform-SupplyChainDive-terms4.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Dive")) AND ("AS/RS" OR "automated terminal" OR "robotic welding" OR "truck charging hub" OR "warehouse management system" OR "sales and operations planning" OR "digital twin" OR "TMS" OR "last mile" OR "gs1 sunrise" OR "smart label" OR "microfactory" OR "intermodal terminal" OR "UWB") AND pd(2026-07-01-2026-09-30)
```

## 5. `abi_inform-ModernMaterialsHandling-terms1.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("warehouse robot" OR "piece picking" OR "sidewalk robot" OR "autonomous truck" OR "shore power" OR "WMS" OR "advanced planning system" OR "demand forecasting" OR "digital matching" OR "language model" OR "blockchain provenance" OR "cold chain sensor" OR "micro fulfilment" OR "positive train control" OR "quantum inspired optimisation") AND pd(2026-07-01-2026-09-30)
```

## 6. `abi_inform-ModernMaterialsHandling-terms2.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("AMR" OR "humanoid robot" OR "delivery drone" OR "electric semi" OR "enterprise resource planning" OR "manufacturing execution system" OR "APS" OR "control tower" OR "vehicle routing" OR "item level rfid" OR "critical mineral supply chain" OR "active packaging" OR "automated damage inspection" OR "inland port" OR "green logistics") AND pd(2026-07-01-2026-09-30)
```

## 7. `abi_inform-ModernMaterialsHandling-terms3.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("AMRs" OR "autonomous yard truck" OR "BVLOS" OR "hydrogen truck" OR "ERP" OR "MES" OR "agentic sourcing" OR "transportation management system" OR "MAPF" OR "digital product passport" OR "battery free" OR "additive manufacturing" OR "risk monitoring platform" OR "private 5g network") AND pd(2026-07-01-2026-09-30)
```

## 8. `abi_inform-ModernMaterialsHandling-terms4.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("AS/RS" OR "automated terminal" OR "robotic welding" OR "truck charging hub" OR "warehouse management system" OR "sales and operations planning" OR "digital twin" OR "TMS" OR "last mile" OR "gs1 sunrise" OR "smart label" OR "microfactory" OR "intermodal terminal" OR "UWB") AND pd(2026-07-01-2026-09-30)
```

## 9. `abi_inform-SupplyChainManagementReview-terms1.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("warehouse robot" OR "piece picking" OR "sidewalk robot" OR "autonomous truck" OR "shore power" OR "WMS" OR "advanced planning system" OR "demand forecasting" OR "digital matching" OR "language model" OR "blockchain provenance" OR "cold chain sensor" OR "micro fulfilment" OR "positive train control" OR "quantum inspired optimisation") AND pd(2026-07-01-2026-09-30)
```

## 10. `abi_inform-SupplyChainManagementReview-terms2.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("AMR" OR "humanoid robot" OR "delivery drone" OR "electric semi" OR "enterprise resource planning" OR "manufacturing execution system" OR "APS" OR "control tower" OR "vehicle routing" OR "item level rfid" OR "critical mineral supply chain" OR "active packaging" OR "automated damage inspection" OR "inland port" OR "green logistics") AND pd(2026-07-01-2026-09-30)
```

## 11. `abi_inform-SupplyChainManagementReview-terms3.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("AMRs" OR "autonomous yard truck" OR "BVLOS" OR "hydrogen truck" OR "ERP" OR "MES" OR "agentic sourcing" OR "transportation management system" OR "MAPF" OR "digital product passport" OR "battery free" OR "additive manufacturing" OR "risk monitoring platform" OR "private 5g network") AND pd(2026-07-01-2026-09-30)
```

## 12. `abi_inform-SupplyChainManagementReview-terms4.ris`

- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("AS/RS" OR "automated terminal" OR "robotic welding" OR "truck charging hub" OR "warehouse management system" OR "sales and operations planning" OR "digital twin" OR "TMS" OR "last mile" OR "gs1 sunrise" OR "smart label" OR "microfactory" OR "intermodal terminal" OR "UWB") AND pd(2026-07-01-2026-09-30)
```

---

## When the files are in

```bash
python -m observatory.run --import-manual
```

It will name any export still missing, and any that arrived without abstracts.
Then regenerate the quarter:

```bash
python -m observatory.run --quarter 2026-Q3
```
