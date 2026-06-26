# Cadence read/write VC-ship

Scaffold to wejście WRITE w VC-ship: dostarczenie end-to-end jasno zdefiniowanego pomysłu/feature'u,
**wstrzyknięte przy Scaffoldzie, dowiezione przy Release**. Operator prowadzi fazę PREP, która musi być doprowadzona do perfekcji
aż do **zera pytań**, bo przez cały cykl **nikt nie jest dostępny** — operator widzi tylko
artefakty pośrednie. Środek to naprzemienne cykle read-write: **cadence read/write**.

## Kolejność (kanoniczna)

```
Scaffold(W) → Implement(W) → Review(R) → Workflow(W) → Follow-up(R)
→ Marbles/chaos(W) → Audit(R) → Polarize/order(W) → Dou(R) → Hydrate(W) → Release(W) → Fanfary
```

- **WRITE** (tworzy, zostawia artefakt): Scaffold · Implement · Workflow · Marbles · Polarize · Hydrate · Release
- **READ** (weryfikuje, falsyfikuje artefakt): Review · Follow-up · Audit · Dou
- **Inwariant cadence:** żaden WRITE nie idzie dalej, dopóki następny READ go nie zweryfikuje. Review weryfikuje Implement;
  Follow-up weryfikuje Workflow; Audit weryfikuje Marbles; Dou weryfikuje Polarize. To inwariant measure-core
  podniesiony z jednostki planu na warstwę orkiestracji.

## Przekazanie: scaffold ↔ operator

- **Scaffold POSIADA brainstorm→plan (WRITE).** Pisze plan z kolumną `state` i `Vector`
  na każde cięcie.
- **vc-operator CZYTA kolumnę `state` → trigger/stop (dispatch).** Latarnia pisze; flota
  wypływa. Artefakt przekazania = plan (np. `EMIL.md` / `SCAFFOLD.md`) z jego kolumną `state`.

## Cztery reguły planowania (dlaczego scaffold musi być opancerzony)

1. **Front-loaduj do scaffoldu, nie w locie.** Całe podejmowanie decyzji przesuwa się do przodu; nikt nie odpowiada
   w locie. Architektura, scope, cięcia (pojedyncze/wiele/projekt), acceptance, kształt dispatchu — wszystko tutaj.
2. **Każdy artefakt samowystarczalny + falsyfikowalny przez następny READ.** Brief zakłada brak człowieka po
   drugiej stronie; faza READ (review/audit/dou) musi umieć go obalić bez operatora.
3. **Research-first / anty-pamięć jest krytyczny dla bezpieczeństwa, nie kosmetyczny.** W autonomicznym pipelinie agent
   komponujący z pamięci to cichy dryf, którego operator nie wyłapie na żywo. Checkpoint orientacji to
   bezpiecznik (zobacz SKILL.md → Checkpoint orientacji).
4. **Kształtuj plany wokół cadence, nie wokół „jednego dispatchu".** Każde cięcie deklaruje, w której fazie read-write
   żyje i jaki artefakt zostawia dla następnej. Tracker to widoczność-przez-artefakty.
