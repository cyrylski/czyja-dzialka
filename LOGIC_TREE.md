# Parcel Logic Tree

How `buildCard()` decides what to display when a user taps the map.
Source: [`index.html:431–540`](index.html).

---

## Viewing this diagram

| Tool | How |
|---|---|
| **GitHub** | Push the file — renders automatically in the repo browser |
| **VS Code** | Install [Markdown Preview Mermaid Support](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid), then `Cmd+Shift+V` |
| **Browser** | Paste the code block below into [mermaid.live](https://mermaid.live) |
| **Obsidian** | Opens natively — no plugin needed |

---

## Decision tree

```mermaid
flowchart TD
    A([User taps map]) --> B[GET /dzialka?lat&lon]
    B --> C[Fetch: EGIB WMS · XLSX powierzenia · KLASOUZYTKI_EGIB]
    C --> D[Compute flags\nisMulti · hasPow · isRoads · isCityOwned\nisSkarb · isChurch · isMixedOwnership · isGminnaEntity]

    D --> E{XLSX entry\nfor this parcel?}

    E -- "powList.length > 1" --> B1["✅ B1 — Multi-manager grid\nTą działką zarządza kilka jednostek\nshowWlasc = true"]
    E -- "powList.length = 1" --> B2["✅ B2 — Single manager hero\np.opis + sygnatura\nshowWlasc = true"]

    E -- "powList empty\n→ infer from EGIB" --> F

    F{"isRoads?\nWLAD ∋ 'dróg publicznych'\nOR 'dr' ∈ klasouzytki.split(',')"}

    F -- Yes --> G{isCityOwned?}
    G -- Yes --> B3["🛣️ B3 — ZDM confirmed\nZarząd Dróg Miejskich\n(city road — Art. 19 ust. 5 UoDP)\nshowWlasc = true"]
    G -- No --> G2{isSkarb?}
    G2 -- Yes --> B4a["🛣️ B4a — ZDM probable\nprawdopodobnie Zarząd Dróg Miejskich\n(SP road — may be GDDKiA or ZDW)\nshowWlasc = true"]
    G2 -- No --> G3{"isPowiat\nOR isGminnaEntity?"}
    G3 -- Yes --> H
    G3 -- No --> B4b["⚠️ B4b — ZDM uncertain\nsklasyfikowana jako droga — zarządca niepewny\n(private owner, may be internal road)\nshowWlasc = true"]

    F -- No --> H{isChurch?\nwlasc ∋ 'kościoły'\nOR 'związki wyznaniowe'}
    H -- Yes --> B5["⛪ B5 — Religious entity\nowner IS the manager\nUstawa o gwarancjach wolności sumienia\nshowWlasc = false"]

    H -- No --> I{isSkarb?\nwlasc ∋ 'Skarb Państwa'}

    I -- Yes --> J{WLAD value?}
    J -- "∋ 'Użytkowanie wieczyste'" --> B6["🏛️ B6 — SP in UW\nWGN supervises on behalf of SP\nArt. 232 KC\nshowWlasc = true"]
    J -- "∋ 'Gospodarowanie zasobem'" --> B7["🏛️ B7 — SP unit / office\nArt. 11+23 UGN\nshowWlasc = true"]
    J -- "∋ 'Trwały zarząd'" --> B7b["🏛️ B7b — SP/city unit in TZ\nArt. 43 UGN\nshowWlasc = true"]
    J -- "none matched" --> B8["🏛️ B8 — SP fallback\nDziałka należy do Skarbu Państwa\nshowWlasc = true"]

    I -- No --> K{isGminnaEntity?\n!isCityOwned && !isSkarb\n&& wlasc ∋ 'gminna'}
    K -- Yes --> B9a["🏙️ B9a — Municipal company\nspółka gminy / jednostka gminna\nMust come before B9\nshowWlasc = true"]

    K -- No --> L{isCityOwned?\nwlasc ∋ 'Miasto Poznań'}
    L -- No --> B9["🟠 B9 — Private / other owner\norange hero = wlasc\nMiasto nie jest właścicielem\nshowWlasc = false"]

    L -- Yes --> M{isMixedOwnership\n&& Zasoby?\nisCityOwned &&\nwlasc ∋ 'osoba fizyczna' &&\nWLAD ∋ 'Gospodarowanie zasobem'}
    M -- Yes --> B10["🏢 B10 — Mixed ownership\ngrant under housing community\nshowWlasc = false"]

    M -- No --> N{WLAD value?}
    N -- "∋ 'Gospodarowanie zasobem'" --> B11["🏙️ B11 — WGN\nWydział Gospodarki Nieruchomościami\nshowWlasc = true"]
    N -- "∋ 'Użytkowanie wieczyste'" --> B12["🏙️ B12 — City parcel in UW\nArt. 232 KC\nshowWlasc = true"]
    N -- "∋ 'Trwały zarząd'" --> B13["🏙️ B13 — City TZ\njednostka miejska — Art. 43 UGN\nshowWlasc = true"]
    N -- "none matched" --> B14["❓ B14 — Unknown / fallback\nbrak informacji\nMonitor: EGIB vocab may change"]
```

---

## Panel output zones

Every branch renders the same three zones:

| Zone | Content | When hidden |
|---|---|---|
| **Hero** | Manager name (blue) or owner name (orange for B9) + contextual note | Never |
| **Data grid** | Numer działki · Właściciel · Powierzchnia | Właściciel hidden when `showWlasc = false` |
| **Rodzaj powierzenia** | Raw WLAD value | Hidden when WLAD is empty or `"—"` |

`showWlasc = false` in B5, B9, B10 — the owner name is already shown in the hero zone.
