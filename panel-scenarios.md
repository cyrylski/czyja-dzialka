# Panel — data scenarios

---

## Scenario A — Normal parcel, entrust + signature found

| Numer działki | Powierzchnia |
|---|---|
| **35/21/53/25** | 0.1234 ha |

| Właściciel | Zarządca |
|---|---|
| Miasto Poznań | Zarząd Dróg Miejskich - powierzenie |

| Rodzaj zarządzania | Sygnatura powierzenia |
|---|---|
| Wykonywanie zadań zarządcy dróg publicznych | GN-XX.6845.2.65.2013 |

---

## Scenario B — Entrust found, no signature

| Numer działki | Powierzchnia |
|---|---|
| **60/01/4/13** | 0.0892 ha |

| Właściciel | Zarządca |
|---|---|
| Miasto Poznań | Zarząd Zieleni Miejskiej |

| Rodzaj zarządzania |
|---|
| Trwały zarząd |

---

## Scenario C1 — Not in xlsx, but GEOPOZ says "roads manager"

| Numer działki | Powierzchnia |
|---|---|
| **20/41/76/8** | 0.0310 ha |

| Właściciel | Zarządca |
|---|---|
| Miasto Poznań | Prawdopodobnie Zarząd Dróg Miejskich *(brak informacji w danych GEOPOZu)* |

| Rodzaj zarządzania |
|---|
| Wykonywanie zadań zarządcy dróg publicznych |

---

## Scenario C2 — Not in xlsx, no inference possible

| Numer działki | Powierzchnia |
|---|---|
| **01/25/1/4** | — |

| Właściciel | Zarządca |
|---|---|
| Skarb Państwa | brak informacji |

| Rodzaj zarządzania |
|---|
| Własność |

---

## Scenario D — Multi-entrust parcel *(current broken behaviour)*

| Numer działki | Powierzchnia |
|---|---|
| **01/24/11/2** | 0.4501 ha |

| Właściciel | Zarządca |
|---|---|
| Miasto Poznań | Zakład Lasów Poznańskich *(Usługi Komunalne silently dropped)* |

| Rodzaj zarządzania | Sygnatura powierzenia |
|---|---|
| Trwały zarząd | GN-XIX.6845.5.48.2025 |

---

## Scenario E — Historical parcel *(no visual difference today)*

| Numer działki | Powierzchnia |
|---|---|
| **61/01/1/1** | 0.2210 ha |

| Właściciel | Zarządca |
|---|---|
| Miasto Poznań | Zarząd Komunalnych Zasobów Lokalowych |

| Rodzaj zarządzania | Sygnatura powierzenia |
|---|---|
| Trwały zarząd | GN-XVI.6845.1.28.2020 |

---

Scenarios D and E look identical to A from the user's perspective — no badge, no warning, no stacked entries.
