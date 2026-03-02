# Projekt-Notiz (Ziel + aktueller Stand)

## Eigentliche Aufgabe
- Jede Kreatur soll eine eigene KI (eigenes Genome/Gehirn) haben.
- Evolution soll immer bessere Kreaturen erzeugen.
- Regel: In Epoche 1 ueberleben alle.
- Ab Epoche 2 sollen nur die besten Gene ueberleben und sich fortpflanzen.
- Mutation soll bleiben, damit die Population nicht in lokalen Optima stecken bleibt.

## Agenten-Idee (kurz)
- Jeder Agent = 1 Kreatur mit eigenem Genome.
- Pro Epoche:
  1. Fitness aller Kreaturen bewerten
  2. Eltern aus den besten waehlen
  3. Crossover (Gene mischen)
  4. Mutation (zufaellige Aenderungen)
  5. Neue Generation erzeugen

## Was bereits umgesetzt ist
- Desktop-Version (Tkinter): `ai leanr walk.py`
  - Strengere Selektion eingebaut.
  - Regel "Epoche 1 alle, danach nur Beste" eingebaut.
  - HUD zeigt `survive` und `cull`.
  - Stabilitaetsfix fuer Muskel-Restlaengen.

- Android-faehige Kivy-Version: `main.py`
  - Eigene Evolutionssimulation als Kivy-App.
  - Regel "Epoche 1 alle, ab Epoche 2 nur beste Gene" ist aktiv.
  - Statusanzeige zeigt Generation, Bestwert, Survival/Cull.

- APK-Build-Konfig vorhanden:
  - `buildozer.spec`
  - `requirements.txt`

## Aktueller Blocker
- APK-Release-Build ist noch nicht fertig, weil WSL/Ubuntu-Setup auf Windows noch nicht komplett abgeschlossen wurde.
- Ohne Linux-Umgebung (WSL) laeuft Buildozer hier nicht stabil zu Ende.

## Naechster konkreter Schritt
1. WSL/Ubuntu fertig installieren.
2. Ubuntu einmal initialisieren.
3. In Ubuntu: Build-Dependencies + `buildozer android release`.
4. Ergebnis: signierte Release-APK in `bin/`.

## Hardware-Einschaetzung fuer lokale LLMs (gemessen)
- CPU: Ryzen 5 2600X (6C/12T)
- RAM: 16 GB
- GPU: RX 580 (4 GB VRAM)
- Empfehlung: 3B-7B quantisierte Modelle (Q4/Q5), 13B+ eher langsam.
