# Come installare Convertitore su Mac

Serve un Mac con chip Apple (M1, M2, M3, M4 o successivi). La versione per Mac Intel e quella per Windows non sono ancora pronte.

## 1. Scarica l'app

1. Apri la pagina **Releases** di questa repository, nella colonna a destra.
2. Nell'ultima versione, scarica il file che finisce in `.dmg`.

## 2. Installala

1. Fai doppio clic sul file `.dmg` che hai scaricato.
2. Nella finestra che si apre, trascina **Convertitore** nella cartella **Applicazioni**.
3. Espelli il disco "Convertitore" dalla barra laterale del Finder.

## 3. Aprila la prima volta

L'app è gratuita e non è firmata con un certificato Apple a pagamento. Per questo il Mac, la prima volta, la blocca con un avviso simile a "Apple non può verificare che Convertitore sia privo di malware". È normale: il codice è tutto pubblico in questa repository.

1. Apri **Applicazioni** e fai doppio clic su **Convertitore**. Comparirà l'avviso: premi **Fine** (o **Annulla**).
2. Apri **Impostazioni di Sistema** → **Privacy e sicurezza**.
3. Scorri in basso: vedrai "Convertitore è stato bloccato". Premi **Apri comunque** e conferma con la password o Touch ID.

Questo passaggio serve solo la prima volta.

## 4. Usala

- Dopo l'avvio, l'app resta nella **barra dei menu** in alto, vicino all'orologio.
- Inizia a trascinare un file dal Finder o dalla Scrivania e **tieni premuto Shift**: compare la ruota con i formati disponibili per quel file.
- Porta il file sul formato che vuoi e rilascia. Il file nuovo viene salvato **accanto all'originale**. L'originale non viene toccato.
- In alto sullo schermo compare una pillola: mostra che l'app sta lavorando, poi il risultato. Premi **Mostra** per aprire il file nel Finder.
- Fermati un attimo sul centro della ruota per passare alla pagina successiva, con altre azioni: per esempio taglia, ritaglia, oscura e velocità per i video, oppure modifica, sfondo e ritaglia per le foto.
- Se trascini più video o più PDF insieme, la ruota propone di unirli.
- Dal menu nella barra in alto puoi aprire la finestra completa, mettere in pausa il gesto o chiudere l'app.

Funziona offline: i file non vengono caricati su internet.

La prima volta che converti un file da Download, Scrivania o Documenti, il Mac chiede se Convertitore può accedere a quella cartella. Premi **Consenti**: serve perché l'app salva il file nuovo accanto all'originale. Lo chiede una volta per cartella.

## Se qualcosa non va

- **Non succede niente quando rilasci**: controlla di aver lasciato il file sopra uno spicchio, non al centro della ruota.
- **Il video non si apre o compare "il file è su iCloud"**: il file non è davvero sul Mac. Nel Finder fai tasto destro sul file → **Scarica ora**, poi riprova.
- **La ruota non compare**: controlla che l'icona sia nella barra dei menu. Se non c'è, riapri Convertitore da Applicazioni. Per ora l'app non si avvia da sola all'accensione del Mac.
- **"Convertitore è danneggiato e non può essere aperto"**: è il blocco che il Mac applica alle app scaricate e non firmate. Apri l'app **Terminale**, incolla questo comando e premi Invio, poi riapri Convertitore:

  ```
  xattr -dr com.apple.quarantine /Applications/Convertitore.app
  ```
