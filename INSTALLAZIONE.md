# Come installare Convertitore

- [Su Mac](#mac) (chip Apple M1 o successivi)
- [Su Windows](#windows) (Windows 10 o 11, 64 bit)

La versione per Mac Intel non è ancora pronta.

<a id="mac"></a>
# Su Mac

Serve un Mac con chip Apple (M1, M2, M3, M4 o successivi).

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

<a id="windows"></a>
# Su Windows

Serve Windows 10 o Windows 11 a 64 bit.

## 1. Scarica ed estrai l'app

1. Apri la pagina **Releases** di questa repository, nella colonna a destra.
2. Nell'ultima versione, scarica il file che finisce in `-Windows.zip`.
3. Fai clic destro sul file scaricato e scegli **Estrai tutto**, poi **Estrai**. Non avviare l'app da dentro lo zip: non funzionerebbe.
4. Sposta la cartella **Convertitore** dove preferisci, per esempio in Documenti.

## 2. Aprila la prima volta

Apri la cartella **Convertitore** e fai doppio clic su **Convertitore.exe**.

L'app non è firmata con un certificato a pagamento, quindi la prima volta Windows mostra la schermata blu "**Windows ha protetto il PC**". È normale: il codice è tutto pubblico in questa repository.

1. Clicca **Ulteriori informazioni**.
2. Clicca **Esegui comunque**.

Questo passaggio serve solo la prima volta. Per ritrovarla facilmente, fai clic destro su **Convertitore.exe** e scegli **Aggiungi a Start**.

## 3. Usala

- Dopo l'avvio, l'app resta nell'**area di notifica** in basso a destra, vicino all'orologio. Se non vedi l'icona, clicca sulla freccetta **^**.
- Inizia a trascinare un file da Esplora file o dal Desktop e **tieni premuto Shift**: compare la ruota con le azioni per quel file.
- Porta il file sullo spicchio che vuoi e rilascia. Il file nuovo viene salvato **accanto all'originale**.
- In alto sullo schermo compare una pillola che mostra l'avanzamento e poi il risultato. Premi **Mostra** per aprire la cartella.
- Dal menu dell'icona nell'area di notifica puoi aprire la finestra completa, mettere in pausa il gesto o chiudere l'app.

## Se qualcosa non va

- **L'antivirus blocca o mette in quarantena l'app**: succede a volte con le app gratuite non firmate. Puoi ripristinarla dalla Sicurezza di Windows (Protezione da virus e minacce > Cronologia protezione).
- **"Manca un file" o l'app non parte**: assicurati di aver estratto tutto lo zip e di avviare **Convertitore.exe** dalla cartella estratta.
- **La ruota non compare**: controlla che l'icona sia nell'area di notifica. Per ora l'app non si avvia da sola all'accensione del PC.
