# Beats

Desktopová aplikace pro zobrazování hudebního rytmu (BPM) pomocí červené tečky.

## Instalace

### Pomocí pip (doporučeno)

Pro instalaci závislostí spusťte:

```bash
pip install -r requirements.txt
```

### Jako balíček

Můžete také nainstalovat aplikaci přímo:

```bash
pip install .
```

### Standalone binární soubor

Aplikaci můžete stáhnout jako hotový binární soubor ze sekce **Releases** na GitHubu, nebo ji sestavit sami:

1. Nainstalujte PyInstaller: `pip install pyinstaller`
2. Spusťte sestavení: `pyinstaller --onefile --windowed --name beats main.py`
3. Výsledný soubor naleznete v adresáři `dist/beats`.

---

## Použití

Spusťte aplikaci pomocí:

```bash
python main.py
```

Nebo pokud jste ji nainstalovali jako balíček:

```bash
beats
```

## Funkce

- Zobrazení červené tečky v pravém horním rohu podle BPM.
- Označení začátku taktu (1. doba červená, 2.-4. doba zelená).
- Správa seznamu skladeb v systémové liště.
- Globální klávesové zkratky `CTRL+ALT+šipka vlevo/vpravo` pro přepínání skladeb.
- Indikace čísla skladby přímo v ikoně v tray a na obrazovce při změně.
