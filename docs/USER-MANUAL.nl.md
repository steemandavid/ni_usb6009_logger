# NI USB-6009 Logger — Gebruikershandleiding

**Softwareversie:** 1.1.0 · **Platform:** Windows 10/11 (64-bit) · **Taal:** Nederlands
(English version: [USER-MANUAL.en.md](USER-MANUAL.en.md))

---

## Inhoud

1. [Wat deze software doet](#1-wat-deze-software-doet)
2. [Wat u nodig hebt](#2-wat-u-nodig-hebt)
3. [Veiligheid eerst](#3-veiligheid-eerst)
4. [De hardware aansluiten](#4-de-hardware-aansluiten)
5. [De software installeren](#5-de-software-installeren)
6. [Het programma voor het eerst starten](#6-het-programma-voor-het-eerst-starten)
7. [Het hoofdvenster](#7-het-hoofdvenster)
8. [Instellingen die voor elke modus gelden](#8-instellingen-die-voor-elke-modus-gelden)
9. [Gegevens loggen (tabblad Log)](#9-gegevens-loggen-tabblad-log)
10. [Kalibreren (tabblad Calibrate)](#10-kalibreren-tabblad-calibrate)
11. [Ontsteken (tabblad Ignite)](#11-ontsteken-tabblad-ignite)
12. [De live grafiek](#12-de-live-grafiek)
13. [Uitvoerbestanden en de herstelkopie](#13-uitvoerbestanden-en-de-herstelkopie)
14. [De opdrachtregelversie gebruiken](#14-de-opdrachtregelversie-gebruiken)
15. [Problemen oplossen](#15-problemen-oplossen)
16. [Verwijderen](#16-verwijderen)
17. [Technische referentie en limieten](#17-technische-referentie-en-limieten)

> **Let op:** de knoppen, tabbladen en velden in het programma zijn in het Engels. In
> deze handleiding staan ze daarom tussen **vetgedrukte Engelse namen**, met uitleg in
> het Nederlands.

---

## 1. Wat deze software doet

De NI USB-6009 Logger maakt van een **USB-6009** meetapparaat van National Instruments
(de "DAQ") een datalogger voor een testopstelling. Het programma kan:

- **Loggen**: analoge spanningen (AI) en eventueel digitale ingangen (DI) opslaan in
  een **CSV**- of **Excel-bestand (.xlsx)**, met een live grafiek tijdens de meting.
- **Kalibreren**: op het scherm een rustig, gemiddeld getal per kanaal tonen, zonder
  een bestand te schrijven — om sensoren op nul te zetten of te controleren vóór een
  test.
- **Ontsteken**: een veilige ontstekingssequentie in stappen uitvoeren (zoemer als
  waarschuwing, controle op doorgang en lekstroom van de ontsteker, ingedrukt houden
  om te vuren, bevestiging van de stroom) en het hele verloop loggen.
- **Uw gegevens beschermen**: elke log- of ontstekingsrun wordt ook als
  *herstelkopie* op schijf geschreven. Na een crash, stroomuitval of losgetrokken
  kabel gaat wat al gemeten was dus niet verloren.

Er zijn twee programma's met dezelfde motor:

| Programma | Voor | Starten via |
|---|---|---|
| **NI USB-6009 Logger** (GUI) | Normaal gebruik door de operator | Startmenu / bureaubladpictogram |
| `ni_usb6009_logger` (opdrachtregel) | Scripts, gevorderde gebruikers | Een terminal — zie [hoofdstuk 14](#14-de-opdrachtregelversie-gebruiken) |

Deze handleiding richt zich op het grafische programma.

## 2. Wat u nodig hebt

| Onderdeel | Opmerking |
|---|---|
| NI **USB-6009** | Met USB-kabel. |
| Een Windows-pc | Windows 10 of 11, 64-bit, met een vrije USB-poort. |
| **NI-DAQmx-driver** | Gratis van NI. De installer kan die meebrengen (zie hoofdstuk 5). |
| Installer | `NI6009Logger_Setup_1.1.0.exe` (of nieuwer). |
| Sensoren / signalen | Aangesloten op de USB-6009 zoals beschreven in hoofdstuk 4. |
| *Alleen voor ontsteking:* relaisbord, zoemer, shuntweerstand van 1 Ω, weerstand van 47 kΩ, ontstekingsvoeding, zekering | Zie hoofdstuk 11 en het schema in 4.5. |

> **Schijfruimte:** de NI-DAQmx-driver alleen al is enkele honderden MB. Het programma zelf is klein.

## 3. Veiligheid eerst

Lees dit vóór u iets aansluit, zeker als u de ontstekingsfunctie gebruikt.

- **De USB-6009 mag nooit de stroom van de ontsteker voeren.** Hij *meet* alleen de
  kleine spanning over de shuntweerstand en *schakelt een relais* via een driver.
- Stuur een relaisspoel altijd aan via een **transistor of driverchip (bv. ULN2803)**,
  nooit rechtstreeks vanaf een uitgangspin van de DAQ. Plaats een
  **vrijloopdiode (flyback)** over de spoel.
- **Beveilig** de ontstekingsvoeding met een passende zekering.
- Houd de ontstekingsbedrading waar mogelijk fysiek **gescheiden** van de
  DAQ-bedrading, of gebruik isolatie (optocoupler of een geïsoleerde
  stroomversterker).
- **Doe eerst een proefrun** met een dummy-belasting (bv. een weerstand of lampje) in
  plaats van een echte ontsteker, en met de ontsteker **niet in de motor**.
- Niemand mag in de buurt van het testobject zijn terwijl de zoemer klinkt of FIRE
  mogelijk is.
- Ziet u iets verkeerd gaan: druk op **ABORT** of sluit gewoon het programma — beide
  zetten de uitgangslijnen LAAG (relais uit, zoemer uit).

## 4. De hardware aansluiten

### 4.1 De klemmen van de USB-6009

Het apparaat heeft 32 schroefklemmen (twee rijen van 16, onder afneembare kapjes).
Nummers en namen staan op het etiket van het apparaat.

| Klem | Signaal | Klem | Signaal |
|---|---|---|---|
| 1 | GND | 17 | P0.0 (digitaal) |
| 2 | AI 0 (+) | 18 | P0.1 |
| 3 | AI 4 (AI 0 − bij differentieel) | 19 | P0.2 |
| 4 | GND | 20 | P0.3 |
| 5 | AI 1 (+) | 21 | P0.4 |
| 6 | AI 5 (AI 1 − bij differentieel) | 22 | P0.5 |
| 7 | GND | 23 | P0.6 |
| 8 | AI 2 (+) | 24 | P0.7 |
| 9 | AI 6 (AI 2 − bij differentieel) | 25 | P1.0 |
| 10 | GND | 26 | P1.1 |
| 11 | AI 3 (+) | 27 | P1.2 |
| 12 | AI 7 (AI 3 − bij differentieel) | 28 | P1.3 |
| 13 | GND | 29 | PFI 0 |
| 14 | AO 0 | 30 | +2,5 V |
| 15 | AO 1 | 31 | +5 V |
| 16 | GND | 32 | GND |

(Controleer altijd aan de hand van het etiket op uw eigen apparaat.) Deze software
gebruikt de **analoge ingangen** (AI 0–7) en de **digitale lijnen** (poort 0: lijnen
0–7, poort 1: lijnen 0–3). De analoge uitgangen worden niet gebruikt.

Benamingen in het programma:

| Op het apparaat | In het programma |
|---|---|
| AI 0 … AI 7 | `ai0` … `ai7` |
| P0.0 … P0.7 | `port0/line0` … `port0/line7` |
| P1.0 … P1.3 | `port1/line0` … `port1/line3` |

### 4.2 Het apparaat op de pc aansluiten

1. **Installeer eerst de software** (hoofdstuk 5), zodat de driver klaarstaat, en
   steek daarna de USB-6009 in. (Eerst aansluiten kan ook; Windows installeert de
   driver dan achteraf.)
2. Sluit de USB-kabel rechtstreeks aan op een USB-poort van de pc — vermijd hubs
   zonder eigen voeding en lange verlengkabels.
3. Het ledje van het apparaat gaat branden/knipperen zodra het herkend is. Wacht een
   paar seconden.
4. Het programma herkent het apparaat zelf, meestal als **Dev1**. Wilt u dit
   controleren of hernoemen, gebruik dan *NI MAX* (Measurement & Automation Explorer,
   met de driver geïnstalleerd) → *Devices and Interfaces*.

### 4.3 De analoge ingangen aansluiten

Kies per meting een van twee methoden (de instelling geldt voor alle gelogde kanalen
— het is het veld **Term config**):

**RSE — enkelvoudig (standaard).** Elk signaal heeft twee draden: signaal → `AI n`
en signaalmassa → een willekeurige `GND`-klem. Werkt op alle acht kanalen (ai0–ai7).
Gebruik dit voor sensoren die een massa delen met de DAQ; de eenvoudigste bedrading.

**DIFF — differentieel.** Elk signaal gebruikt een *paar* klemmen: `+` naar `AI n`,
`−` naar de bijbehorende partnerklem (zie de tabel: ai0 gebruikt klemmen 2 en 3, ai1
klemmen 5 en 6, ai2 klemmen 8 en 9, ai3 klemmen 11 en 12). Betere ruisonderdrukking
voor kleine of zwevende signalen. **Alleen ai0–ai3** zijn beschikbaar in DIFF-modus,
omdat ai4–ai7 de partnerpennen zijn. Gebruik geen ai4–ai7-kanaal tegelijk met het
DIFF-kanaal dat dezelfde klem gebruikt.

Het ingangsbereik is maximaal ±10 V. **Leg nooit meer dan ±10 V aan** (ten opzichte
van GND), anders kan de ingang beschadigd raken. Gebruik voor grotere signalen een
spanningsdeler.

> De USB-6009 heeft **geen** "NRSE"-modus, ook al accepteert de opdrachtregel dat
> woord. Gebruik RSE of DIFF.

### 4.4 Digitale ingangen aansluiten (optioneel)

Sluit een digitaal signaal (0 V = laag, tot 5 V = hoog) aan tussen `P0.x` (of `P1.x`)
en `GND`. Digitale ingangen zijn **statisch**: het programma leest ze één keer per
gegevensblok (chunk) en herhaalt die waarde op alle rijen van het blok. Verklein de
*Chunk size* om ze vaker te bemonsteren (zie hoofdstuk 8).

### 4.5 De ontstekingsketen aansluiten (alleen voor de Ignite-functie)

Dit hoofdstuk beschrijft de referentiebedrading die bij de standaardinstellingen van
de software hoort.

**Onderdelen**

- **Relais** (via een driver/transistor zoals een ULN2803 of MOSFET, met vrijloopdiode)
  om de ontsteker te schakelen. De relaiscontacten voeren de ontstekingsstroom.
- **Zoemer** (aangestuurd vanaf een digitale uitgang van de DAQ, via een transistor
  als hij meer nodig heeft dan de paar mA van de DAQ).
- **Shuntweerstand**: 1,0 Ω, minstens 2 W, lage inductie, in het massapad van de
  ontsteker.
- **Biasweerstand**: 47 kΩ, van ontstekings-+V naar het knooppunt ontsteker/shunt. Die
  geeft een piepkleine teststroom (~0,25 mA bij 12 V) waarmee wordt gecontroleerd dat
  de ontsteker aangesloten is.

**Verbindingen**

```
 Ontstekings-+V ──► Relaiscontact (NO) ──► Ontsteker (+)
                                            Ontsteker (−) ──┬──► 1 Ω shunt ──► Ontstekings-GND
 Ontstekings-+V ──► 47 kΩ ───────────────────────────────────┤ (knooppunt)
                                                             └──► DAQ  AI+ (standaard ai2)
 DAQ GND (AI GND) ──────────────────────────────────────────────► Ontstekings-GND

 DAQ port1/line0 ──► relaisdriver (relaisspoel)   (standaardlijn "igniter relay")
 DAQ port1/line1 ──► zoemerdriver                 (standaardlijn "buzzer")
```

**Hoe de controles werken**

| Relais | Stroom die vloeit | Spanning over 1 Ω | Gebruikt voor |
|---|---|---|---|
| Open | alleen de biasstroom (~0,25 mA bij 12 V) | ~0,25 mV | **Doorgangs**controle — ontsteker is aangesloten |
| Gesloten | volledige ontstekingsstroom (typisch 3–6 A) | 3–6 V | **Vuurbevestiging** |

De software berekent stroom = gemeten spanning ÷ shuntweerstand en vergelijkt die met
drie limieten (in te stellen op het tabblad Ignite, zie hoofdstuk 11).

**Verplicht:** neem het stroommeetkanaal (bijvoorbeeld `ai2`) op in de lijst
*AI channels* aan de linkerkant van het venster. Zie hoofdstuk 11.

> Stel bij bovenstaande bedrading **Term config** en **Sense term config** in op
> **RSE**. Sluit u de shunt differentieel aan, gebruik dan DIFF en een kanaal uit
> ai0–ai3.

### 4.6 Controlelijst vóór het inschakelen

- [ ] Elke signaaldraad zit op de bedoelde klem en geen enkele draad raakt een andere.
- [ ] Geen enkele ingang krijgt meer dan ±10 V.
- [ ] DAQ-GND en ontstekings-GND zijn verbonden zoals in het schema.
- [ ] De ontstekingsvoeding staat **uit** (en is beveiligd met een zekering) tijdens het opstellen.
- [ ] De ontsteker is voor de eerste test een dummy-belasting / niet in een motor geplaatst.

## 5. De software installeren

### 5.1 De installer uitvoeren

1. Dubbelklik op **`NI6009Logger_Setup_<versie>.exe`**.
2. Toont Windows **"Windows heeft uw pc beveiligd"** (SmartScreen), klik dan op
   **Meer informatie** en daarna op **Toch uitvoeren**. Deze melding verschijnt omdat
   de installer nog niet digitaal is ondertekend; dat is normaal.
3. Sta de beheerdersmelding toe (de installer heeft beheerdersrechten nodig).
4. Aanvaard de licentie (MIT) en klik op **Volgende**.
5. Kies de installatiemap (de standaard `C:\Program Files\NI USB-6009 Logger` is goed).
6. **Onderdelen** (indien getoond):
   - *NI USB-6009 Logger application* — wordt altijd geïnstalleerd.
   - *NI-DAQmx driver runtime* — laat dit **aangevinkt** als de NI-driver nog niet op
     deze pc staat. Hij installeert zichzelf zonder vragen en kan enkele minuten
     duren.
7. **Extra taken:**
   - *Create a desktop shortcut* (bureaubladsnelkoppeling) — optioneel.
   - *Test the installation now* (test de installatie nu) — laat **aangevinkt**.
8. Klik op **Installeren**, wacht en klik op **Voltooien**.

### 5.2 Het resultaat van de installatietest lezen

Als u de test aangevinkt liet, meldt een venster een van drie resultaten:

| Melding | Betekenis / wat te doen |
|---|---|
| **Driver OK and USB-6009 detected — everything works.** | Klaar. |
| **Driver OK. No DAQ device found yet.** | Prima als het apparaat niet is aangesloten. Sluit de USB-6009 aan; het programma vindt hem zelf. |
| **The NI-DAQmx driver is not working yet.** | Herstart de pc één keer en start het programma opnieuw. Lukt het nog niet, installeer dan NI-DAQmx van ni.com (zie 5.3). |

### 5.3 Als de NI-DAQmx-driver ontbreekt

Bevatte uw installer de driver niet, dan meldt het programma dit bij het opstarten en
biedt het een knop **Open download page** aan. Download en installeer **NI-DAQmx** van
ni.com (zoek "NI-DAQmx download"), herstart de pc indien gevraagd en start het
programma opnieuw.

### 5.4 De Python-versie installeren (alleen voor gevorderde gebruikers)

Niet nodig als u de installer gebruikt. Voor de opdrachtregeltool of ontwikkeling, met
Python 3.10+ en de reeds geïnstalleerde NI-DAQmx-driver:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .[excel]        # opdrachtregeltool + Excel-uitvoer
pip install -e .[gui,excel]    # ook het grafische programma (ni_usb6009_gui)
```

## 6. Het programma voor het eerst starten

1. Steek de USB-6009 in.
2. Start **NI USB-6009 Logger** via het Startmenu of het bureaubladpictogram.
3. De venstertitel toont de versie. In de statusbalk leest u
   **"DAQ detected: Dev1 (USB-6009)"**.

Ziet u in plaats daarvan:

| Statusbalk | Betekenis |
|---|---|
| *No DAQ detected — waiting for device…* | Het apparaat is niet aangesloten of nog niet herkend. Controleer de kabel; het programma zoekt om de 2 seconden opnieuw, of druk op **Refresh**. |
| *NI configuration service not running…* | Een Windows-service van NI is gestopt. Zie [problemen oplossen](#15-problemen-oplossen). |

Uw instellingen worden onthouden tussen sessies, dus de tweede keer ziet het venster
eruit zoals u het achterliet.

## 7. Het hoofdvenster

```
┌───────────────────┬─ Output file: [pad………………………] [Browse…] ────────────────┐
│ INSTELLINGENPANEEL│ ┌ Log │ Calibrate │ Ignite │ Recovery ───────────────────┐ │
│  DAQ device [ ▼ ] │ │ (inhoud van het gekozen tabblad)                       │ │
│  AI channels      │ │                                                         │ │
│  DI lines         │ │        live grafiek / uitlezingen / knoppen             │ │
│  Sample rate      │ │                                                         │ │
│  Chunk size       │ └─────────────────────────────────────────────────────────┘ │
│  Term config      │                                                             │
│  AI range         │                                                             │
│  Duration         │                                                             │
└───────────────────┴─────────────────────────  statusbalk ─────────────────────┘
```

- **Links: instellingenpaneel** — instellingen die voor elke modus gelden.
- **Rechtsboven: Output file** — waar de gegevens worden bewaard; gedeeld door *Log*
  en *Ignite*.
- **Tabbladen:** *Log*, *Calibrate*, *Ignite*, *Recovery*.
- **Statusbalk** (onderaan): apparaatstatus, en tijdens een run het aantal samples, de
  verstreken tijd en de datasnelheid.
- Een **logvenster** herhaalt de berichten van het programma.

## 8. Instellingen die voor elke modus gelden

| Veld | Wat in te vullen | Standaard |
|---|---|---|
| **DAQ device** | Kies uit de lijst. Die wordt automatisch ingevuld. U kunt een naam typen als het apparaat niet in de lijst staat. **Refresh** zoekt opnieuw. | `Dev1` |
| **AI channels** | Te meten analoge kanalen, gescheiden door komma's: `ai0` of `ai0,ai1,ai2`. Minstens één is vereist. | `ai0` |
| **DI lines** | Optionele digitale ingangen. `port0/line0:7` (een heel bereik) of `port0/line0,port0/line3`. Leeg laten voor geen. Alleen `port0/line0-7` en `port1/line0-3` bestaan. Een naam als `D0` wordt geweigerd. | leeg |
| **Sample rate** | Samples per seconde **per kanaal**, 1–48 000 Hz. | 1000 Hz |
| **Chunk size** | Aantal samples dat in één keer van het apparaat wordt gelezen. Bepaalt ook hoe vaak de digitale ingangen worden gelezen: één keer per chunk. | 1000 |
| **Term config** | `RSE` (enkelvoudig) of `DIFF` (differentieel). Zie 4.3. | RSE |
| **AI range** | Verwachte minimum- en maximumspanning, −10 V … +10 V. Bepaalt ook de verticale as van de grafiek. | −10 tot +10 V |
| **Duration** | Looptijd in seconden. `0` toont "run until Stop" (tot Stop). | tot Stop |

**Belangrijke limiet — totale snelheid.** De USB-6009 kan hooguit **48 000 samples per
seconde *in totaal*** meten, verdeeld over alle kanalen. De maximale samplefrequentie
is dus 48 000 ÷ aantal kanalen (4 kanalen → 12 000 Hz; 8 kanalen → 6 000 Hz). Het
programma controleert dit vóór het starten en meldt het maximum.

**Digitale bemonsteringssnelheid.** Digitale ingangen worden één keer per chunk
gelezen. Bij 1000 Hz met een chunk van 1000 krijgt u één digitale meting per seconde;
met een chunk van 100 tien per seconde. Kleinere chunks betekenen meer leesacties,
maar er zijn verder geen nadelen.

Alle instellingen worden bewaard wanneer u een run start en wanneer u het programma
sluit.

## 9. Gegevens loggen (tabblad Log)

### 9.1 Stappen

1. Vul het instellingenpaneel in (hoofdstuk 8).
2. Klik op **Browse…** naast *Output file* en kies waar u wilt opslaan. De voorgestelde
   plaats is `Documenten\NI6009 Logs\ni_<apparaat>_<datum>_<tijd>.csv`. Kies **CSV**
   of **Excel (.xlsx)** via het bestandstype, of via de extensie die u typt.
3. **Start** is pas beschikbaar als een uitvoerbestand is gekozen en een apparaat
   beschikbaar is. Klik op **Start**.
4. Volg de live grafiek (hoofdstuk 12) en de statusbalk.
5. De run eindigt als de *Duration* verstreken is, of wanneer u op **Stop** klikt.
6. Een samenvattingsvenster verschijnt met een knop **Open folder** die u naar uw
   bestanden brengt.

### 9.2 Bestaande bestanden worden nooit overschreven

Bestaat de gekozen naam al, dan wordt `_1`, `_2`, … aan de nieuwe bestandsnaam
toegevoegd. De naam die na uw keuze in het vak *Output file* staat, is exact de naam
die geschreven wordt.

### 9.3 Wat staat er in het bestand

Eén rij per meetogenblik, met deze kolommen:

| Kolom | Betekenis |
|---|---|
| `timestamp_iso` | Datum en tijd waarop de sample **genomen** werd (niet wanneer hij van het apparaat werd gelezen). |
| `sample_index` | Teller van de sample, beginnend bij 0. |
| Eén kolom per AI-kanaal | Spanning in volt (`ai0`, `ai1`, …). |
| Eén kolom per DI-lijn | 0 of 1 (`port0/line0`, …). Dezelfde waarde herhaald binnen een chunk. |

**CSV** opent in Excel of elke teksteditor. **XLSX** is een echt Excel-werkboek; let
op: een XLSX-bestand komt pas op schijf als de run *eindigt* (de altijd weggeschreven
[herstelkopie](#13-uitvoerbestanden-en-de-herstelkopie) beschermt u ondertussen).

## 10. Kalibreren (tabblad Calibrate)

Gebruik dit om rustige, gemiddelde waarden te bekijken — bijvoorbeeld om een
krachtopnemer op nul te zetten of een sensor te controleren — **zonder** iets op te
slaan. Er is geen uitvoerbestand nodig.

Instellingen op het tabblad:

| Veld | Betekenis | Standaard |
|---|---|---|
| **Moving-average window** | Seconden aan gegevens die voor elke getoonde waarde gemiddeld worden. `0` schakelt middeling uit. | 5 s |
| **Screen output rate** | Hoe vaak per seconde de uitlezing ververst. | 1 Hz |
| **Internal sample rate** | Hoe snel de hardware bemonstert om het gemiddelde te voeden. | 100 Hz |

1. Stel kanalen en terminalconfiguratie in op het instellingenpaneel.
2. Klik op **Start calibration**.
3. De grote uitlezing toont het voortschrijdend gemiddelde per kanaal; de grafiek toont
   de ruwe signalen.
4. Klik op **Stop** als u klaar bent.

Het gemiddelde heeft één volledig venster nodig om te stabiliseren: wacht bij een
venster van 5 s ongeveer 5 s na een wijziging voordat u de waarde afleest.

## 11. Ontsteken (tabblad Ignite)

> ⚠ **Veiligheidskritische functie.** Lees eerst hoofdstuk 3 en 4.5. Doe een volledige
> proefrun met een dummy-belasting en **zonder** ontsteker in de motor vóór echt
> gebruik.

### 11.1 Instellingen

| Veld | Betekenis | Standaard |
|---|---|---|
| **Buzzer DO line** | Digitale uitgang die de zoemer aanstuurt. | `port1/line1` |
| **Igniter relay DO line** | Digitale uitgang die het relais aanstuurt. | `port1/line0` |
| **Current-sense AI** | Analoge ingang die de spanning over de shunt meet. | `ai2` |
| **Sense term config** | RSE of DIFF voor dat kanaal (moet bij uw bedrading passen). | RSE |
| **Shunt resistance** | Waarde van uw shunt, in ohm. | 1,0 Ω |
| **Continuity minimum** | Minimale biasstroom die bewijst dat de ontsteker aangesloten is. | 0,2 mA |
| **Leak maximum** | Vloeit er vóór het vuren méér stroom dan dit, dan wordt het systeem geblokkeerd. | 5 mA |
| **Fire-confirm minimum** | Stroom die *tijdens* de puls gezien moet worden om ontsteking te bevestigen. | 300 mA |
| **Buzzer warning time** | Hoe lang de waarschuwingszoemer klinkt vóór het loggen start. | 15 s |
| **Stabilize time** | Tijd tussen het begin van het loggen en het beschikbaar worden van FIRE. | 1 s |
| **Relay pulse time** | Hoe lang het relais aan blijft. | 1 s |

Verder nodig:

- Een **uitvoerbestand** (ontsteking logt altijd).
- Het **stroommeetkanaal in de lijst "AI channels"** (bv. `ai0,ai2`). De USB-6009 kan
  maar één analoge meting tegelijk uitvoeren, dus de bevestigingsstroom wordt uit
  dezelfde lopende meting gehaald. Laat u het weg, dan gebeurt de puls nog steeds,
  maar de bevestigingsmeting kan als fout worden gemeld.
- Zoemer- en relaislijnen moeten echte uitgangslijnen zijn (`port0/line0-7` of
  `port1/line0-3`) en verschillend van elkaar.

### 11.2 Het veiligheidspaneel

Vier leds: **DO lines LOW**, **Continuity**, **No leak current**, **Igniter relay**;
een statusregel (met de live stroom in mA tijdens het scherpstellen); een balk die
toont hoe lang u FIRE ingedrukt houdt; en de knoppen **ARM**, **FIRE**, **ABORT**.

### 11.3 De sequentie, stap voor stap

| Stap | Wat u doet | Wat het systeem doet |
|---|---|---|
| **1. ARM** | Klik op **ARM** en bevestig het dialoogvenster ("buzzer will sound… relay stays OFF"). | Start de sessie. Zet eerst beide uitgangslijnen LAAG. |
| **2. Arming** | Wacht (u kunt altijd ABORT gebruiken). | De **zoemer klinkt** gedurende de waarschuwingstijd terwijl de stroom wordt gemeten en live getoond. |
| **3. Controle** | — | **Geslaagd:** doorgang gezien en geen lek → gaat verder. **Mislukt:** zoemer uit en de melding *"INHIBITED by safety failsafe"* met de reden (lekstroom te hoog, of geen doorgang). FIRE wordt **nooit aangeboden** en het relais wordt nooit bekrachtigd. |
| **4. Logging** | Wacht. | Het loggen start. Na de stabilisatietijd wordt **FIRE ingeschakeld**. |
| **5. FIRE** | **Houd FIRE 2 seconden ingedrukt** (de balk vult zich; te vroeg loslaten annuleert). | Het relais wordt aangezet voor de pulsduur, de stroom wordt getoetst aan *Fire-confirm minimum*, daarna gaat het relais uit. |
| **6. ABORT** | Klik op elk moment op **ABORT**. | Stopt alles; de uitgangslijnen gaan LAAG. |

Ingebouwde regels:

- FIRE is nooit beschikbaar voordat het systeem klaar is en wordt weer uitgeschakeld
  na de puls, na een blokkade, of wanneer de sessie eindigt.
- De stroomlimieten worden gecontroleerd door de kern van het programma, niet door de
  knoppen — dezelfde bescherming als in de opdrachtregelversie.
- Blijft de stroom tijdens de puls onder *Fire-confirm minimum*, dan vraagt een
  waarschuwing u bedrading, voeding en ontsteker te controleren. Het relais maakt zijn
  puls toch af en schakelt uit.
- Een sterk **negatieve** stroom (shunt omgekeerd aangesloten) blokkeert het
  scherpstellen met een duidelijke melding.
- **Venster sluiten = ABORT.** Een venster "stopping safely" blijft staan tot de
  uitgangslijnen bevestigd LAAG zijn; daarna sluit het programma.
- Een losgetrokken USB-kabel tijdens een run stopt de sessie; de uitgangen gaan LAAG en
  de tot dan toe weggeschreven gegevens blijven bewaard.

### 11.4 Voorgestelde proefrun

1. Sluit alles aan met een dummy-belasting (bv. een geschikte weerstand of lampje) in
   plaats van een ontsteker, of zonder ontstekingsvoeding, en met de ontsteker niet in
   de motor.
2. Stel voor de test een korte waarschuwingstijd in (bv. 5 s).
3. ARM → bevestig → kijk naar de leds: Continuity licht op, de leak-led blijft OK.
4. Koppel de dummy-belasting los en doe opnieuw ARM → verwacht *INHIBITED (no
   continuity)*.
5. Sluit weer aan, ARM, wacht op FIRE, houd het ingedrukt → u hoort/ziet het relais 1 s
   klikken; controleer de gelogde stroom.
6. Druk op ABORT tijdens een nieuwe scherpstelling → controleer dat alles stilvalt.

## 12. De live grafiek

- Eén gekleurde lijn per AI-kanaal met legende; X-as = seconden sinds het begin van de
  run, Y-as = volt (uw *AI range*).
- Ze toont ongeveer de laatste 60 seconden; het geheugengebruik blijft constant hoe
  lang u ook meet. Het **bestand** bevat *alle* gegevens.
- **view:** keuzelijst rechtsboven: **follow live** (loopt mee met nieuwe gegevens) of
  **pause view** (bevriest het beeld zodat u kunt in- en uitzoomen en schuiven; de
  opname gaat door).
- Zoom met het muiswiel; sleep om te schuiven (in pauze).

## 13. Uitvoerbestanden en de herstelkopie

### 13.1 Herstelkopie

Voor elke log- of ontstekingsrun schrijft het programma een tweede, parallel bestand:

```
<uw uitvoermap>\recovery\<uw bestandsnaam>_recovery.csv
```

- Het is altijd een CSV, na elke chunk naar schijf geschreven (een XLSX komt pas aan
  het einde op schijf).
- Eindigt de run normaal, dan wordt het hernoemd naar `…_recovery_OK.csv`.
- Na een crash, losgetrokken kabel, abort of een fout staat er **geen** `_OK` in de
  naam — de gedeeltelijke gegevens zijn veilig en klaar om hersteld te worden.

### 13.2 Het tabblad Recovery

Toont de herstelbestanden (nieuwste eerst) met hun status (**OK** of
**INTERRUPTED**, onderbroken) en grootte, uit de submap `recovery` van de huidige
uitvoermap en uit de standaard logmap. Het ververst bij het opstarten, wanneer u het
tabblad opent en na elke run.

- **Refresh** — opnieuw zoeken.
- **Copy to…** — kopieert het geselecteerde bestand naar een plaats naar keuze.
  Mislukt het kopiëren, dan krijgt u een melding met de reden.

### 13.3 Waar staat alles?

| Wat | Waar |
|---|---|
| Standaard gegevensmap | `Documenten\NI6009 Logs` |
| Herstelkopieën | submap `recovery\` naast uw uitvoerbestand |
| Uw instellingen | Windows-register `HKCU\Software\steeman.be\NI USB-6009 Logger` (door het programma beheerd) |

## 14. De opdrachtregelversie gebruiken

Voor scripts opent u **PowerShell** (met de Python-installatie actief, hoofdstuk 5.4)
en voert u `ni_usb6009_logger` uit. Een kanaallijst is de enige verplichte optie.

```powershell
ni_usb6009_logger --help
```

### 14.1 Voorbeelden

```powershell
# ai0 loggen op 1000 Hz, automatisch benoemd bestand onder .\logs, eerste 10 rijen tonen
ni_usb6009_logger --device Dev1 --channels ai0 --rate 1000 --term RSE --print-first 10

# Twee analoge + vier digitale lijnen, eigen CSV
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --digital port0/line0:3 `
  --rate 100 --outfile .\logs\run.csv

# Excel-uitvoer, 30 seconden, voortgangsbalk
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --rate 500 `
  --outfile .\logs\run.xlsx --duration 30 --progress bar

# Differentieel
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --rate 1000 --term DIFF

# Kalibratie (alleen scherm, voortschrijdend gemiddelde van 5 s)
ni_usb6009_logger --device Dev1 --channels ai0,ai1 --calibrate --calib-window 5 `
  --calib-sample-rate 100 --rate 1

# Ontsteking met zoemer, relais en stroommeting als beveiliging
ni_usb6009_logger --device Dev1 --channels ai0,ai2 --rate 1000 --term RSE `
  --ignite --buzzer-line port1/line1 --igniter-line port1/line0 `
  --igniter-sense-ai ai2 --sense-term RSE --shunt-ohms 1.0 `
  --continuity-min-ma 0.2 --leak-max-ma 5 --fire-confirm-ma 300
```

(In `cmd.exe` gebruikt u `^` in plaats van de backtick om een regel voort te zetten.)

### 14.2 Opties

| Optie | Betekenis | Standaard |
|---|---|---|
| `--device` | Apparaatnaam (zoals in NI MAX) | `Dev1` |
| `--channels` | AI-kanalen, bv. `ai0,ai1` (verplicht) | — |
| `--digital` | DI-lijnen, bv. `port0/line0:7` | geen |
| `--rate` | Samplefrequentie (Hz) | 1000 (1 bij kalibratie) |
| `--chunk` | Samples per leesactie | 1000 |
| `--vmin`, `--vmax` | Verwacht spanningsbereik | −10, 10 |
| `--term` | `RSE` of `DIFF` (`NRSE` wordt aanvaard maar door dit apparaat geweigerd) | RSE |
| `--outfile` | Uitvoerpad; automatisch benoemd in `.\logs` indien weggelaten | — |
| `--format` | `csv` of `xlsx` (anders uit de extensie) | csv |
| `--duration` | Seconden; weglaten om te lopen tot Ctrl+C | — |
| `--progress` | `auto`, `none`, `counter`, `bar` | auto |
| `--update-interval` | Seconden tussen voortgangsupdates | 0,5 |
| `--print-first` | De eerste N rijen tonen | 0 |
| `--debug` | Extra diagnose-uitvoer | uit |
| `--calibrate` | Kalibratiemodus | uit |
| `--calib-window` | Venster van het voortschrijdend gemiddelde (s, 0 = uit) | 5 |
| `--calib-show-raw` | Toon ook ruwe waarden | uit |
| `--calib-sample-rate` | Interne frequentie bij kalibratie (Hz) | 100 |
| `--ignite` | Ontstekingssequentie inschakelen | uit |
| `--buzzer-line`, `--igniter-line` | Uitgangslijnen (verplicht bij `--ignite`) | — |
| `--arm-seconds` | Waarschuwingstijd van de zoemer | 15 |
| `--stabilize-seconds` | Wachttijd na het starten van het loggen | 1 |
| `--pulse-seconds` | Inschakeltijd van het relais | 1 |
| `--igniter-sense-ai` | Kanaal dat de shunt meet, bv. `ai2` | — |
| `--shunt-ohms` | Waarde van de shunt | 1,0 |
| `--continuity-min-ma` / `--leak-max-ma` / `--fire-confirm-ma` | Stroomlimieten | 0,2 / 5 / 300 |
| `--sense-rate` | Samplefrequentie van de stroommeting (Hz) | 100 |
| `--sense-term` | Terminalconfiguratie voor het meetkanaal van de stroom | DIFF |

Let op: de standaardwaarde van `--sense-term` op de opdrachtregel is **DIFF**, terwijl
de GUI RSE toont; stel dit expliciet in zodat het bij uw bedrading past.

### 14.3 Stoppen en afsluitcodes

- Eén keer **Ctrl+C** = nette stop (de huidige chunk wordt afgewerkt, bestanden sluiten,
  uitgangen LAAG). Een **tweede** Ctrl+C breekt onmiddellijk af (afsluitcode 130) als
  het apparaat vastzit.
- Afsluitcode **2** = een instelling werd vóór het starten geweigerd (met uitleg).

## 15. Problemen oplossen

| Symptoom | Oorzaak / oplossing |
|---|---|
| Het programma meldt dat de **NI-DAQmx-driver ontbreekt** en sluit | Klik op *Open download page*, installeer NI-DAQmx, herstart de pc en start het programma opnieuw. |
| **"No DAQ detected — waiting for device…"** | Controleer USB-kabel en -poort; probeer een andere poort. Druk op **Refresh**. Controleer of het apparaat in NI MAX verschijnt. U kunt ook `Dev1` in het apparaatveld typen. |
| **"NI configuration service not running"** of een fout met *MIG* | Achtergrondservices van NI zijn gestopt. Herstart de pc. Anders, in een PowerShell **als administrator**: `Get-Service *NI* \| Sort-Object Status, Name` en dan `Start-Service -Name "nidevldu","mxssvr","nimDNSResponder"`; of herstart de service *NI Configuration Manager* in de Windows-*Services*. |
| **Start / ARM is grijs** | Geen apparaat beschikbaar, of (bij Log/Ignite) nog geen uitvoerbestand gekozen. |
| Dialoogvenster **"Cannot start"** | Een instelling is ongeldig; de melding noemt het veld. Typisch: samplefrequentie × kanalen boven 48 000; DIFF op ai4–ai7; verkeerde naam van een digitale lijn; AI-minimum boven maximum; lege kanaallijst. |
| Digitale lijn **`D0` geweigerd** | Gebruik de volledige naam: `port0/line0`. |
| **Run gestopt, venster "check USB cable"** | Het apparaat werd losgekoppeld. De tot dan toe weggeschreven gegevens staan in de uitvoer- *en* herstelbestanden die in het venster genoemd worden. Steek opnieuw in en start een nieuwe run. |
| **Arming meldt "INHIBITED — no continuity"** | Ontsteker niet aangesloten, biasweerstand ontbreekt, meetdraad los, of *Continuity minimum* te hoog ingesteld. |
| **"INHIBITED — leak current"** | Er vloeit stroom vóór het vuren: kortsluiting, vochtige/vuile verbinding, verkeerde bedrading, klevend relais. Herstel dit vóór u opnieuw probeert; verhoog de limiet niet om er gewoon voorbij te geraken. |
| Melding over omgekeerde stroom | De shunt- of AI-draden zijn verwisseld. |
| **Waarschuwing fire-confirm** | De stroom tijdens de puls bleef onder de limiet: controleer voedingsspanning, zekering, ontsteker, shuntwaarde en bedrading. |
| Waarden zijn ruiserig of driften | Gebruik DIFF-bedrading, kortere/afgeschermde draden en een gemeenschappelijke massa; gebruik Calibrate met een langer gemiddelde. |
| Excel-bestand ontbreekt na een crash | XLSX wordt pas op het einde geschreven. Gebruik het tabblad **Recovery** en kopieer de `…_recovery.csv`. |
| SmartScreen-waarschuwing bij installatie | Klik op *Meer informatie* → *Toch uitvoeren*. |

## 16. Verwijderen

*Windows-instellingen → Apps → NI USB-6009 Logger → Verwijderen*, of *Startmenu → NI
USB-6009 Logger → Uninstall NI USB-6009 Logger*. Uw gegevensbestanden in
`Documenten\NI6009 Logs` worden **niet** verwijderd. De NI-DAQmx-driver is een apart
product en blijft geïnstalleerd (verwijder hem apart via *Apps* als u hem niet meer
nodig hebt).

## 17. Technische referentie en limieten

| Onderdeel | Waarde |
|---|---|
| Analoge ingangen | 8 enkelvoudig (RSE) of 4 differentieel (DIFF, ai0–ai3), max. ±10 V |
| Maximale bemonstering | 48 000 S/s in totaal, gedeeld door alle kanalen |
| Digitale lijnen | port0/line0–7, port1/line0–3; statisch (niet geklokt) |
| Terminalmodi | alleen RSE, DIFF (geen NRSE) |
| Digitale momentopname | Eén keer per chunk |
| Tijdstempels | Teruggerekend naar het moment waarop elke sample genomen werd |
| Bestandsformaten | CSV, XLSX |
| Overschrijfbeveiliging | Altijd; achtervoegsel `_1`, `_2`… |
| Herstel | CSV, na elke chunk weggeschreven; `_OK` bij nette afsluiting |
| Geheugen live grafiek | Begrensd; venster van ~60 s |
| Timing bij ontsteking | De AI-stroom wordt in blokjes van ~20 ms gelezen, zodat het relais op tijd opent en ABORT binnen één blokje werkt |
| Besturingssysteem | Windows 10/11 64-bit |
| Niet meegeleverd | NI-driverbestanden (apart geïnstalleerd door NI-DAQmx) |

**Testen zonder hardware:** met de omgevingsvariabele `NI_USB6009_FAKE=1` start het
programma met een ingebouwd nepapparaat (geen driver nodig); handig voor training en
demo's. Het is toegeeflijker dan het echte apparaat. Voor een realistischere test maakt
u in NI MAX een *gesimuleerde USB-6009* aan (*Devices and Interfaces → Create New →
NI-DAQmx Simulated Device*).

**Zelftest:** `NI6009Logger.exe --selftest` (vanuit de installatiemap) toont één regel en
geeft 0 terug (driver en apparaat OK), 1 (driver OK, geen apparaat) of 2 (driver
ontbreekt of NI-service draait niet).

---

© 2025 David Steeman · MIT-licentie · [steeman.be](https://steeman.be)
