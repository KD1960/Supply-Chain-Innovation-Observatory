# 2026-Q3 — exports still to run

Window **2026-07-01 to 2026-09-30** for all of them. This is a change:
the sheet used to ask for 2026-06-29 to 2026-09-27, three days short of
what the report counts at the back end. Fixed 2026-09-01.

Save each file to `data/manual/2026-Q3/` under exactly the name given.
**Clear ProQuest's marked-items list between exports** — it accumulates,
and the importer will refuse the files.

**An empty result still needs a file.** Save a zero-record export (or an
empty file) plus its `.meta.yaml` sidecar with `records: 0`. That is the
difference between 'we looked and found nothing' and 'we did not look',
and it is the whole point of the record.

---

## 1. `scopus-14784092.ris`

- **Database:** Scopus
- **Window:** 2026-07-01 to 2026-09-30

```
(ISSN(1478-4092)) AND PUBYEAR = 2026
```

## 2. `abi_inform-ModernMaterialsHandling-terms1.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("warehouse robot" OR "humanoid robot" OR "BVLOS" OR "truck charging hub" OR "WMS" OR "APS" OR "transportation management system" OR "last mile" OR "blockchain provenance" OR "active packaging" OR "risk monitoring platform" OR "private 5g network" OR "SCADA") AND pd(2026-07-01-2026-09-30)
```

## 3. `abi_inform-ModernMaterialsHandling-terms2.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("AMR" OR "autonomous yard truck" OR "robotic welding" OR "shore power" OR "manufacturing execution system" OR "agentic ai" OR "TMS" OR "language model" OR "critical mineral supply chain" OR "additive manufacturing" OR "nearshoring" OR "UWB") AND pd(2026-07-01-2026-09-30)
```

## 4. `abi_inform-ModernMaterialsHandling-terms3.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("AMRs" OR "automated terminal" OR "autonomous truck" OR "enterprise resource planning" OR "MES" OR "digital twin" OR "digital matching" OR "item level rfid" OR "battery free" OR "microfactory" OR "intermodal terminal" OR "quantum inspired optimisation") AND pd(2026-07-01-2026-09-30)
```

## 5. `abi_inform-ModernMaterialsHandling-terms4.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("AS/RS" OR "sidewalk robot" OR "electric semi" OR "ERP" OR "sales and operations planning" OR "demand forecasting" OR "vehicle routing" OR "digital product passport" OR "smart label" OR "micro fulfilment" OR "positive train control" OR "greenhouse gas emission") AND pd(2026-07-01-2026-09-30)
```

## 6. `abi_inform-ModernMaterialsHandling-terms5.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Modern Materials Handling")) AND ("piece picking" OR "delivery drone" OR "hydrogen truck" OR "warehouse management system" OR "advanced planning system" OR "control tower" OR "MAPF" OR "gs1 sunrise" OR "cold chain sensor" OR "automated damage inspection" OR "inland port" OR "critical infrastructure") AND pd(2026-07-01-2026-09-30)
```

## 7. `abi_inform-SupplyChainManagementReview-terms1.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("warehouse robot" OR "humanoid robot" OR "BVLOS" OR "truck charging hub" OR "WMS" OR "APS" OR "transportation management system" OR "last mile" OR "blockchain provenance" OR "active packaging" OR "risk monitoring platform" OR "private 5g network" OR "SCADA") AND pd(2026-07-01-2026-09-30)
```

## 8. `abi_inform-SupplyChainManagementReview-terms2.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("AMR" OR "autonomous yard truck" OR "robotic welding" OR "shore power" OR "manufacturing execution system" OR "agentic ai" OR "TMS" OR "language model" OR "critical mineral supply chain" OR "additive manufacturing" OR "nearshoring" OR "UWB") AND pd(2026-07-01-2026-09-30)
```

## 9. `abi_inform-SupplyChainManagementReview-terms3.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("AMRs" OR "automated terminal" OR "autonomous truck" OR "enterprise resource planning" OR "MES" OR "digital twin" OR "digital matching" OR "item level rfid" OR "battery free" OR "microfactory" OR "intermodal terminal" OR "quantum inspired optimisation") AND pd(2026-07-01-2026-09-30)
```

## 10. `abi_inform-SupplyChainManagementReview-terms4.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("AS/RS" OR "sidewalk robot" OR "electric semi" OR "ERP" OR "sales and operations planning" OR "demand forecasting" OR "vehicle routing" OR "digital product passport" OR "smart label" OR "micro fulfilment" OR "positive train control" OR "greenhouse gas emission") AND pd(2026-07-01-2026-09-30)
```

## 11. `abi_inform-SupplyChainManagementReview-terms5.ris`

- **Database:** ProQuest ABI/INFORM
- **Window:** 2026-07-01 to 2026-09-30

```
(PUB.EXACT("Supply Chain Management Review")) AND ("piece picking" OR "delivery drone" OR "hydrogen truck" OR "warehouse management system" OR "advanced planning system" OR "control tower" OR "MAPF" OR "gs1 sunrise" OR "cold chain sensor" OR "automated damage inspection" OR "inland port" OR "critical infrastructure") AND pd(2026-07-01-2026-09-30)
```

---

## Before re-running Journal of Commerce

All five batches ran and all five came back empty, across roughly
sixty-six terms in a quarter. Supply Chain Dive returned 30 over the
same terms and window, so the likely cause is that the title string
does not resolve — `sources.yaml` already records DC Velocity,
FreightWaves and Material Handling & Logistics failing the same way
under `PUB.EXACT`.

Two diagnostic searches settle it, and neither needs an export:

```
PUB.EXACT("Journal of Commerce")
```

If that returns zero with no term filter and no date filter, the title
is wrong rather than the quarter being quiet. Then run:

```
PUB("Journal of Commerce")
```

and read the publication names ProQuest offers — the indexed title is
often a variant such as "Journal of Commerce (Online)". Send me the
exact string and I will correct `sources.yaml`; if nothing resolves, it
joins the three already recorded as not indexed, so nobody asks again.
