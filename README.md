# Convertitore

Converti e modifica i tuoi file trascinandoli, senza caricarli su nessun sito.

Tieni premuto **Shift** mentre trascini un file dal Finder o da Esplora file: compare una ruota con le azioni possibili per quel file. Lascialo sullo spicchio che ti serve e il risultato viene salvato accanto all'originale. Funziona offline: i file restano sul tuo computer.

Gratis e open source. Creato da [@promptalluso](https://www.instagram.com/promptalluso/).

## Scarica

**[Scarica l'ultima versione](../../releases/latest)** e scegli il file per il tuo computer:

- **Mac** con chip Apple (M1 o successivi): il file che finisce in `.dmg`
- **Windows** 10 o 11 a 64 bit: il file che finisce in `-Windows.zip`

Poi segui la **[guida di installazione](INSTALLAZIONE.md)**: la prima volta il computer chiede una conferma in più, perché l'app non è firmata con un certificato a pagamento.

La versione per Mac Intel non è ancora pronta.

## Cosa fa

| File | Azioni |
|---|---|
| Foto | PNG, JPEG, WebP, AVIF, TIFF, BMP, GIF, PDF. Modifica (esposizione, contrasto, saturazione, nitidezza), sfondo, annotazioni, ritaglio, area oscurata, rimozione dei metadati, testo dalla foto (OCR), riduzione, rotazione, compressione |
| PDF | Unisci, dividi, ruota, estrai pagine, comprimi, ottimizza, esporta il testo, rendi ricercabile un PDF scansionato (OCR), pagine in PNG, JPEG o WebP |
| Video | MP4, MOV, WebM, MKV, GIF, MP3. Comprimi, 720p, 1080p, taglia, dividi, ritaglia, cambia velocità, copri un'area con un rettangolo nero, salva un fotogramma, unisci più video |
| Audio | MP3, M4A, WAV, FLAC. Comprimi, taglia, mono, stereo, livello dei canali, normalizza il volume, bip su un intervallo |
| Sottotitoli | SRT, VTT, testo semplice |

Mentre lavora, in alto sullo schermo compare una pillola che mostra l'avanzamento e poi il risultato, con un pulsante per aprire il file nel Finder.

C'è anche una finestra completa, dal menu dell'icona nella barra in alto (su Windows nell'area di notifica), per convertire fino a 100 file insieme.

## Privacy

L'app non carica file, non raccoglie statistiche e non richiede un account. Il riconoscimento del testo (OCR) funziona offline.

Non è uno strumento di anonimizzazione: la rimozione dei metadati crea un PNG nuovo, ma converti solo file di cui ti fidi.

## Limiti di questa versione

- Mac con chip Apple e Windows 10/11 a 64 bit. L'app non è firmata: la [guida](INSTALLAZIONE.md) spiega come aprirla la prima volta.
- I file su iCloud devono essere scaricati sul Mac (nel Finder: tasto destro > Scarica ora).
- L'app non si avvia da sola all'accensione del computer.
- Su Windows il materiale vetro di macOS non c'è: finestre e ruota hanno uno sfondo pieno.

## Per sviluppatori

Serve Python 3.12, sul sistema operativo di destinazione:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -e . pyinstaller==6.22.3
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python packaging/build.py
.venv/bin/python packaging/smoke.py dist
```

`packaging/build.py` crea l'app e il `.dmg` in `dist/`. Il test `tests/test_wheel_actions.py` prova ogni spicchio della ruota per ogni tipo di file.

## Licenza e crediti

GPL-3.0-only. Vedi [LICENSE](LICENSE) e [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Il progetto parte dalla versione desktop open source di [Open Tangerine](https://github.com/sintaxerrorpvtltd/Open-Tangerine) (GPL-3.0), con nome, icona e interfaccia diversi.

L'app include FFmpeg 7.1, compilato con licenza GPL. Il codice sorgente di quella versione è disponibile su [ffmpeg.org/releases/ffmpeg-7.1.tar.xz](https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz). Il binario proviene dal pacchetto [imageio-ffmpeg 0.6.0](https://github.com/imageio/imageio-ffmpeg).
