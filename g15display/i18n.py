"""Per-instance translations shared by the native app, LCD, and CLI.

German source messages are stable lookup keys. User content is never translated.
"""

from dataclasses import dataclass, field
import locale
import os

LANGUAGES = {"en": "English", "es": "Español", "fr": "Français", "de": "Deutsch"}


def normalize_language(value):
    code = str(value or "").replace("_", "-").split("-", 1)[0].lower()
    return code if code in LANGUAGES else "en"


def system_language():
    return normalize_language(os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
                              or os.environ.get("LANG") or locale.getlocale()[0])


@dataclass(frozen=True)
class Message:
    source: str
    values: dict = field(default_factory=dict)

    def __str__(self):
        return self.source.format(**self.values)


class Translator:
    def __init__(self, language="de"):
        self.language = normalize_language(language)

    def __call__(self, source, **values):
        if isinstance(source, BaseException):
            source = source.args[0] if source.args else str(source)
        if isinstance(source, Message):
            source, values = source.source, source.values
        source = str(source)
        translations = CATALOG.get(source)
        text = translations[self.language] if translations else source
        return text.format(**values) if values else text


# Each row contains: German source | English | Spanish | French.
# A single catalog makes missing translations and placeholder mismatches testable.
_ROWS = r'''
Uhr|Clock|Reloj|Horloge
Codex-Limits|Codex limits|Límites de Codex|Limites Codex
Laufende Codex-Aufgaben|Running Codex tasks|Tareas de Codex activas|Tâches Codex en cours
Timer|Timer|Temporizador|Minuteur
Pomodoro|Pomodoro|Pomodoro|Pomodoro
Musik|Music|Música|Musique
Netzwerk|Network|Red|Réseau
G15 Display anzeigen|Show G15 Display|Mostrar G15 Display|Afficher G15 Display
G-Tasten / Makros …|G-keys / Macros …|Teclas G / Macros …|Touches G / Macros …
Aufnahme / Wiedergabe stoppen|Stop recording / playback|Detener grabación / reproducción|Arrêter enregistrement / lecture
Display trennen|Disconnect display|Desconectar pantalla|Déconnecter l'écran
Display verbinden|Connect display|Conectar pantalla|Connecter l'écran
Zugriffseinstellungen …|Access settings …|Permisos …|Autorisations …
Beenden|Quit|Salir|Quitter
Bearbeiten|Edit|Editar|Édition
Ausschneiden|Cut|Cortar|Couper
Kopieren|Copy|Copiar|Copier
Einfügen|Paste|Pegar|Coller
Alles auswählen|Select all|Seleccionar todo|Tout sélectionner
Dein G15-Dashboard|Your G15 dashboard|Tu panel G15|Votre tableau de bord G15
Verbindung wird vorbereitet …|Preparing connection …|Preparando conexión …|Préparation de la connexion …
Live-Vorschau des 160 × 43 Pixel großen Displays|Live preview of the 160 × 43 pixel display|Vista previa de la pantalla de 160 × 43 píxeles|Aperçu de l'écran de 160 × 43 pixels
Zurück|Back|Atrás|Retour
Weiter|Next|Siguiente|Suivant
Aktion|Action|Acción|Action
Menü|Menu|Menú|Menu
Zur Uhr|Clock|Reloj|Horloge
G-Tasten …|G-keys …|Teclas G …|Touches G …
Verbinden|Connect|Conectar|Connecter
Trennen|Disconnect|Desconectar|Déconnecter
Timer & Pomodoro|Timer & Pomodoro|Temporizador y Pomodoro|Minuteur et Pomodoro
Timer (Min.)|Timer (min)|Tiempo (min)|Minuteur (min)
Arbeit (Min.)|Work (min)|Trabajo (min)|Travail (min)
Pause (Min.)|Break (min)|Descanso (min)|Pause (min)
Runden|Rounds|Rondas|Cycles
Zeiten anwenden|Apply durations|Aplicar tiempos|Appliquer
Zeiten anwenden setzt beide Timer zurück. Fenster schließen: läuft in der Menüleiste weiter.|Applying durations resets both timers. Closing the window keeps the app in the menu bar.|Aplicar tiempos reinicia ambos temporizadores. Al cerrar la ventana, la app sigue en la barra de menús.|Appliquer réinitialise les deux minuteurs. Fermer la fenêtre laisse l'app dans la barre des menus.
Datenquellen werden verbunden …|Connecting data sources …|Conectando fuentes de datos …|Connexion aux sources de données …
Zugriff …|Access …|Permisos …|Accès …
Bitte die Timerzeiten prüfen|Please check the timer settings|Revisa los tiempos|Vérifiez les durées
Die Rundenzahl muss eine ganze Zahl sein.|The round count must be a whole number.|El número de rondas debe ser entero.|Le nombre de cycles doit être entier.
G15 verbunden · Display und Tasten sind aktiv|G15 connected · Display and keys are active|G15 conectada · Pantalla y teclas activas|G15 connecté · Écran et touches actifs
Display getrennt · Vorschau und Timer laufen weiter|Display disconnected · Preview and timers continue|Pantalla desconectada · Vista previa y temporizadores activos|Écran déconnecté · Aperçu et minuteurs toujours actifs
G15 wird gesucht …|Searching for G15 …|Buscando G15 …|Recherche du G15 …
Aufgaben|Tasks|Tareas|Tâches
verbunden|connected|conectado|connecté
G15 Display wird beendet …|Quitting G15 Display …|Cerrando G15 Display …|Fermeture de G15 Display …
G-Tasten & Makros|G-keys & Macros|Teclas G y macros|Touches G et macros
Bank|Bank|Banco|Banque
G-Taste|G-key|Tecla G|Touche G
Name für die neue Aufnahme|Name for the new recording|Nombre de la grabación|Nom du nouvel enregistrement
Zum Beispiel: Textbaustein|For example: text snippet|Por ejemplo: texto guardado|Exemple : extrait de texte
Aufnehmen|Record|Grabar|Enregistrer
Stoppen|Stop|Detener|Arrêter
Testen (3 Sek.)|Test (3 sec)|Probar (3 s)|Tester (3 s)
Makro löschen|Delete macro|Borrar macro|Supprimer macro
Noch kein Makro gespeichert.|No macro saved yet.|Aún no hay macro guardada.|Aucune macro enregistrée.
Aufnehmen startet nach 3 Sekunden. Wechsle dann zum Zielprogramm. Während der Aufnahme werden Tastendrücke systemweit erfasst. Stoppen oder die MR-Taste beendet die Aufnahme.|Recording starts after 3 seconds. Switch to the target app. During recording, keyboard events are captured system-wide. Stop or MR ends recording.|La grabación empieza en 3 segundos. Cambia a la app de destino. Se capturan las teclas de todo el sistema durante la grabación. Detener o MR finaliza la grabación.|L'enregistrement commence dans 3 secondes. Passez à l'app cible. Les frappes sont capturées dans tout le système pendant l'enregistrement. Arrêter ou MR termine l'enregistrement.
Letzte G-Taste: —|Last G-key: —|Última tecla G: —|Dernière touche G : —
Aufnahme freigeben …|Allow recording …|Permitir grabación …|Autoriser l'enregistrement …
Wiedergabe freigeben …|Allow playback …|Permitir reproducción …|Autoriser la lecture …
Maximal 60 Sekunden / 500 Ereignisse. MR stoppt auch eine Wiedergabe. Fenster schließen verwirft eine laufende Aufnahme.|Maximum 60 seconds / 500 events. MR also stops playback. Closing this window discards an active recording.|Máximo 60 segundos / 500 eventos. MR también detiene la reproducción. Cerrar esta ventana descarta la grabación activa.|Maximum 60 secondes / 500 événements. MR arrête aussi la lecture. Fermer cette fenêtre annule l'enregistrement actif.
Makro gelöscht.|Macro deleted.|Macro borrada.|Macro supprimée.
noch kein Makro|no macro yet|sin macro|aucune macro
Aktive Bank: {bank}   ·   Letzte G-Taste: {key}|Active bank: {bank}   ·   Last G-key: {key}|Banco activo: {bank}   ·   Última tecla G: {key}|Banque active : {bank}   ·   Dernière touche G : {key}
{name} · {count} Ereignisse · {seconds:.1f} Sek.|{name} · {count} events · {seconds:.1f} sec|{name} · {count} eventos · {seconds:.1f} s|{name} · {count} événements · {seconds:.1f} s
G-Taste wählen und Aufnahme starten.|Choose a G-key and start recording.|Elige una tecla G y empieza a grabar.|Choisissez une touche G et lancez l'enregistrement.
G15 Display unter Eingabeüberwachung erlauben; dann erneut aufnehmen.|Allow G15 Display in Input Monitoring, then record again.|Permite G15 Display en Monitorización de entrada y vuelve a grabar.|Autorisez G15 Display dans Surveillance de l'entrée, puis réessayez.
Aufnahme beginnt in 3 Sekunden …|Recording starts in 3 seconds …|La grabación empieza en 3 segundos …|Enregistrement dans 3 secondes …
Tastaturaufnahme nicht verfügbar. Eingabeüberwachung prüfen.|Keyboard recording unavailable. Check Input Monitoring.|Grabación no disponible. Revisa Monitorización de entrada.|Enregistrement indisponible. Vérifiez Surveillance de l'entrée.
AUFNAHME AKTIV – mit Stoppen oder MR beenden.|RECORDING ACTIVE – end with Stop or MR.|GRABACIÓN ACTIVA – termina con Detener o MR.|ENREGISTREMENT ACTIF – terminez avec Arrêter ou MR.
Aufnahme unterbrochen. Das bisherige Makro bleibt erhalten.|Recording interrupted. The previous macro is preserved.|Grabación interrumpida. Se conserva la macro anterior.|Enregistrement interrompu. La macro précédente est conservée.
{bank}/{key}: {count} Ereignisse gespeichert.|{bank}/{key}: {count} events saved.|{bank}/{key}: {count} eventos guardados.|{bank}/{key} : {count} événements enregistrés.
Aufnahme verworfen; das bisherige Makro bleibt erhalten.|Recording discarded; the previous macro is preserved.|Grabación descartada; se conserva la macro anterior.|Enregistrement annulé ; la macro précédente est conservée.
Für Makros die Bedienungshilfen-Freigabe für G15 Display erteilen.|Allow G15 Display in Accessibility to play macros.|Permite G15 Display en Accesibilidad para reproducir macros.|Autorisez G15 Display dans Accessibilité pour lire les macros.
Wiedergabe {bank}/{key} gestartet.|Playback of {bank}/{key} started.|Reproducción de {bank}/{key} iniciada.|Lecture de {bank}/{key} démarrée.
Für diese G-Taste ist noch kein Makro gespeichert.|No macro is saved for this G-key.|No hay macro guardada para esta tecla G.|Aucune macro pour cette touche G.
G15 Display unter Bedienungshilfen erlauben; dann erneut testen.|Allow G15 Display in Accessibility, then test again.|Permite G15 Display en Accesibilidad y vuelve a probar.|Autorisez G15 Display dans Accessibilité, puis réessayez.
Wiedergabe in 3 Sekunden – Zielprogramm auswählen.|Playback in 3 seconds – focus the target app.|Reproducción en 3 segundos – elige la app de destino.|Lecture dans 3 secondes – passez à l'app cible.
Aufnahme in {seconds} Sekunden – Zielprogramm auswählen.|Recording in {seconds} seconds – focus the target app.|Grabación en {seconds} segundos – elige la app de destino.|Enregistrement dans {seconds} secondes – passez à l'app cible.
Wiedergabe braucht die Bedienungshilfen-Freigabe|Playback requires Accessibility permission|La reproducción requiere permiso de Accesibilidad|La lecture nécessite l'autorisation Accessibilité
Unbekanntes Tastenereignis|Unknown key event|Evento de tecla desconocido|Événement de touche inconnu
Ungültiger Tastencode|Invalid keycode|Código de tecla no válido|Code de touche invalide
Ungültige Zusatztasten|Invalid modifier flags|Modificadores no válidos|Modificateurs invalides
Ungültige Verzögerung|Invalid delay|Retardo no válido|Délai invalide
Ungültiger Makroname|Invalid macro name|Nombre de macro no válido|Nom de macro invalide
Ein Makro braucht 1 bis 500 Tastenereignisse|A macro needs 1 to 500 key events|Una macro requiere de 1 a 500 eventos de tecla|Une macro nécessite 1 à 500 événements
Ein Makro darf höchstens 60 Sekunden dauern|A macro can last at most 60 seconds|Una macro puede durar hasta 60 segundos|Une macro peut durer au maximum 60 secondes
Unbekanntes Makroformat|Unknown macro format|Formato de macro desconocido|Format de macro inconnu
Bitte M1–M3 und G1–G18 auswählen|Please select M1–M3 and G1–G18|Selecciona M1–M3 y G1–G18|Sélectionnez M1–M3 et G1–G18
Unbekannte Profilversion|Unknown profile version|Versión de perfil desconocida|Version de profil inconnue
Die Makrodatei lässt sich nicht lesen. Sie wird nicht überschrieben.|The macro file cannot be read. It will not be overwritten.|No se puede leer el archivo de macros. No se sobrescribirá.|Le fichier de macros est illisible. Il ne sera pas écrasé.
Dieses Makro wurde für ein anderes Betriebssystem aufgenommen|This macro was recorded for another operating system|Esta macro se grabó para otro sistema operativo|Cette macro a été enregistrée pour un autre système
Makro-Wiedergabe fehlgeschlagen|Macro playback failed|Error al reproducir la macro|Échec de la lecture de macro
Makro-Wiedergabe unterbrochen|Macro playback interrupted|Reproducción de macro interrumpida|Lecture de macro interrompue
Maximal 1440 Minuten und 50 Runden sind möglich.|The maximum is 1440 minutes and 50 rounds.|El máximo es 1440 minutos y 50 rondas.|Le maximum est de 1440 minutes et 50 cycles.
Das Terminal-Menü läuft noch. Dort mit Strg+C beenden; die App verbindet sich danach automatisch.|The Terminal dashboard is still running. Stop it with Ctrl+C; the app will connect automatically.|El panel de Terminal sigue activo. Deténlo con Ctrl+C; la app se conectará automáticamente.|Le tableau de bord Terminal est actif. Arrêtez-le avec Ctrl+C ; l'app se connectera automatiquement.
Die Display-Verbindung wurde beendet. Bitte die App neu starten.|The display connection stopped. Please restart the app.|Se cerró la conexión de pantalla. Reinicia la app.|La connexion à l'écran est arrêtée. Redémarrez l'app.
Timerzeiten muessen positiv und endlich sein.|Timer durations must be positive and finite.|Los tiempos deben ser positivos y finitos.|Les durées doivent être positives et finies.
Pomodoro braucht eine positive ganze Rundenzahl.|Pomodoro requires a positive whole number of rounds.|Pomodoro requiere un número entero positivo de rondas.|Pomodoro nécessite un nombre entier positif de cycles.
Codex-Verbindung beendet|Codex connection closed|Conexión de Codex cerrada|Connexion Codex fermée
Codex-Abfrage nicht verfuegbar|Codex query unavailable|Consulta de Codex no disponible|Requête Codex indisponible
Codex antwortet nicht|Codex not responding|Codex no responde|Codex ne répond pas
Codex nicht erreichbar|Codex unreachable|Codex inaccesible|Codex inaccessible
Codex CLI fehlt|Codex CLI not found|No se encuentra Codex CLI|Codex CLI introuvable
Keine Limitdaten verfuegbar|No limit data available|Sin datos de límites|Aucune donnée de limites
Keine lokalen Codex-Chats|No local Codex chats|Sin chats locales de Codex|Aucun chat Codex local
Unbenannter Chat|Unnamed chat|Chat sin nombre|Chat sans nom
Keine Standardverbindung|No default connection|Sin conexión predeterminada|Aucune connexion par défaut
Keine Netzwerkzaehler|No network counters|Sin contadores de red|Aucun compteur réseau
Keine IPv4|No IPv4|Sin IPv4|Aucune IPv4
Player nicht erreichbar|Player unreachable|Reproductor inaccesible|Lecteur inaccessible
Player antwortet nicht|Player not responding|El reproductor no responde|Le lecteur ne répond pas
Musik-Zugriff erlauben|Allow music access|Permitir acceso a música|Autoriser l'accès musical
Player-Abfrage fehlgeschlagen|Player query failed|Error al consultar reproductor|Échec de requête du lecteur
Keine Wiedergabe|Nothing playing|Sin reproducción|Aucune lecture
Player-Steuerung verweigert|Player control denied|Control de reproductor denegado|Contrôle du lecteur refusé
Wird geladen ...|Loading ...|Cargando ...|Chargement ...
Player-Steuerung fehlgeschlagen|Player control failed|Error de control del reproductor|Échec du contrôle du lecteur
Datenquelle nicht verfuegbar|Data source unavailable|Fuente de datos no disponible|Source de données indisponible
Die HIDAPI-Version unterstützt keinen gemeinsamen macOS-Zugriff.|This HIDAPI version does not support shared macOS access.|Esta versión de HIDAPI no admite acceso compartido en macOS.|Cette version de HIDAPI ne permet pas l'accès partagé sur macOS.
USB-Bibliothek fehlt. Bitte 'python -m pip install -e .' ausführen.|USB library missing. Run 'python -m pip install -e .'.|Falta la biblioteca USB. Ejecuta 'python -m pip install -e .'.|Bibliothèque USB absente. Exécutez 'python -m pip install -e .'.
Keine G15 v1 gefunden (046d:c222). Bitte USB-Verbindung prüfen.|No G15 v1 found (046d:c222). Check the USB connection.|No se encuentra G15 v1 (046d:c222). Revisa la conexión USB.|Aucun G15 v1 trouvé (046d:c222). Vérifiez la connexion USB.
Mehrere G15-Schnittstellen gefunden. Bitte nur eine G15 anschließen und 'devices' prüfen.|Multiple G15 interfaces found. Connect only one G15 and check 'devices'.|Varias interfaces G15 encontradas. Conecta una sola G15 y consulta 'devices'.|Plusieurs interfaces G15 trouvées. Connectez un seul G15 et vérifiez 'devices'.
Diese G15-Verbindung ist bereits geöffnet.|This G15 connection is already open.|Esta conexión G15 ya está abierta.|Cette connexion G15 est déjà ouverte.
Die G15 ist nicht geöffnet. Bitte 'with G15() as lcd:' verwenden.|The G15 is not open. Use 'with G15() as lcd:'.|La G15 no está abierta. Usa 'with G15() as lcd:'.|Le G15 n'est pas ouvert. Utilisez 'with G15() as lcd:'.
timeout_ms muss eine positive ganze Zahl sein.|timeout_ms must be a positive whole number.|timeout_ms debe ser un entero positivo.|timeout_ms doit être un entier positif.
Die G15-Sperrdatei gehört einem anderen Benutzer.|The G15 lock file belongs to another user.|El archivo de bloqueo G15 pertenece a otro usuario.|Le fichier de verrouillage G15 appartient à un autre utilisateur.
Ein anderes G15-Programm verwendet das Display bereits.|Another G15 program is already using the display.|Otro programa G15 ya usa la pantalla.|Un autre programme G15 utilise déjà l'écran.
G15 lässt sich nicht öffnen. Andere Display-Programme schließen; falls macOS den Zugriff verweigert, die Eingabeüberwachung für das startende Terminal bzw. Codex prüfen. Details: {details}|Cannot open G15. Close other display programs; if macOS denies access, check Input Monitoring for the launching Terminal or Codex. Details: {details}|No se puede abrir G15. Cierra otros programas de pantalla; si macOS deniega el acceso, revisa Monitorización de entrada para Terminal o Codex. Detalles: {details}|Impossible d'ouvrir le G15. Fermez les autres programmes d'écran ; si macOS refuse l'accès, vérifiez Surveillance de l'entrée pour Terminal ou Codex. Détails : {details}
Lesen der G15-Tasten fehlgeschlagen: {details}|Reading G15 keys failed: {details}|Error al leer teclas G15: {details}|Échec de lecture des touches G15 : {details}
Display-Übertragung fehlgeschlagen: {details}|Display transfer failed: {details}|Error de transferencia a pantalla: {details}|Échec du transfert à l'écran : {details}
Display-Übertragung unvollständig: {written}/{total} Bytes.|Incomplete display transfer: {written}/{total} bytes.|Transferencia incompleta: {written}/{total} bytes.|Transfert incomplet : {written}/{total} octets.
Das Bild muss {width} × {height} Pixel groß sein.|The image must be {width} × {height} pixels.|La imagen debe medir {width} × {height} píxeles.|L'image doit mesurer {width} × {height} pixels.
Das Display bietet Platz für maximal vier Textzeilen.|The display fits at most four lines of text.|La pantalla admite hasta cuatro líneas de texto.|L'écran accepte au maximum quatre lignes de texte.
UHR|CLOCK|RELOJ|HORLOGE
CODEX LIMITS|CODEX LIMITS|LIMITES CODEX|LIMITES CODEX
CODEX AKTIV|CODEX ACTIVE|CODEX ACTIVO|CODEX ACTIF
TIMER|TIMER|TEMPORIZADOR|MINUTEUR
POMODORO|POMODORO|POMODORO|POMODORO
MUSIK|MUSIC|MUSICA|MUSIQUE
NETZWERK|NETWORK|RED|RESEAU
MENUE|MENU|MENU|MENU
MENU|MENU|MENU|MENU
Woche|Week|Sem.|Sem.
Limit|Limit|Límite|Limite
misst ...|sampling ...|midiendo ...|mesure ...
FERTIG|DONE|LISTO|TERMINE
LAEUFT|RUNNING|EN MARCHA|EN COURS
GESTOPPT|STOPPED|PARADO|ARRETE
Arbeit|Work|Trabajo|Travail
Pause|Break|Descanso|Pause
PAUSE|PAUSE|PAUSA|PAUSE
START|START|INICIO|DEBUT
Neuer Abruf automatisch|Automatic retry|Reintento automatico|Nouvel essai automatique
unbekannt|unknown|desconocido|inconnu
{label}: nicht verfuegbar|{label}: unavailable|{label}: no disponible|{label} : indisponible
{remaining:.0f}% frei|{remaining:.0f}% free|{remaining:.0f}% disp|{remaining:.0f}% disp
Nur ein Limitfenster|Only one limit window|Solo un limite|Une seule limite
ZEIT|TIME|HORA|HEURE
{count} aktiv (lokale Logs)|{count} active (local logs)|{count} activas (logs locales)|{count} actives (logs locaux)
Status unklar / Log alt|Unknown / stale log|Estado dudoso / log viejo|Etat incertain / log ancien
Kein aktiver lokaler Task|No active local task|Sin tarea local activa|Aucune tache locale active
Lokal / letzte 24 Stunden|Local / last 24 hours|Local / ultimas 24 horas|Local / dernieres 24 heures
TASK|TASK|TAREA|TACHE
PLAY|PLAY|PLAY|LIRE
KW|WK|SEM|SEM
lcd.clock_button|CLOCK|RELOJ|HEURE
Ansicht|Page|Página|Page
G15-Menü läuft: L2 <, L3 >, L4 Aktion (Timer: lang=Reset), L5 Menü.|G15 dashboard: L2 <, L3 >, L4 action (hold to reset timer), L5 menu.|Panel G15: L2 <, L3 >, L4 acción (mantener para reiniciar), L5 menú.|Tableau G15 : L2 <, L3 >, L4 action (maintenir pour réinitialiser), L5 menu.
Vorschau: {path}|Preview: {path}|Vista previa: {path}|Aperçu : {path}
Bitte eine positive, endliche Sekundenzahl angeben.|Please enter a positive finite number of seconds.|Introduce un número positivo y finito de segundos.|Indiquez un nombre de secondes positif et fini.
Logitech G15 v1 – Display-Ansteuerung|Logitech G15 v1 – Display controller|Logitech G15 v1 – Control de pantalla|Logitech G15 v1 – Contrôleur d'écran
G15-Schnittstellen auflisten|List G15 interfaces|Listar interfaces G15|Lister les interfaces G15
Bis zu vier Textzeilen anzeigen|Display up to four lines of text|Mostrar hasta cuatro líneas de texto|Afficher jusqu'à quatre lignes de texte
Je Argument eine Zeile|One line per argument|Una línea por argumento|Une ligne par argument
Uhr starten; Strg+C beendet sie|Start clock; stop with Ctrl+C|Iniciar reloj; Ctrl+C para salir|Lancer l'horloge ; Ctrl+C pour arrêter
Nach dieser Dauer beenden|Stop after this duration|Salir tras esta duración|Arrêter après cette durée
G-, M- und Displaytasten live anzeigen|Show live G-, M- and display-key events|Mostrar eventos de teclas G, M y pantalla|Afficher les touches G, M et écran en direct
Tasten zusätzlich auf der G15 anzeigen|Also show key events on the G15|Mostrar teclas también en la G15|Afficher aussi les touches sur le G15
Dashboard mit Uhr, Codex, Timer, Musik und Netzwerk|Dashboard with clock, Codex, timers, music and network|Panel con reloj, Codex, temporizadores, música y red|Tableau de bord : horloge, Codex, minuteurs, musique et réseau
Nur PNG-Vorschau speichern|Save a PNG preview only|Guardar solo una vista previa PNG|Enregistrer uniquement un aperçu PNG
Display leeren|Clear display|Borrar pantalla|Effacer l'écran
Nur PNG-Vorschau speichern, ohne USB|Save a PNG preview only, without USB|Guardar solo vista previa PNG, sin USB|Enregistrer un aperçu PNG, sans USB
Keine G15 v1 gefunden (046d:c222).|No G15 v1 found (046d:c222).|No se encuentra G15 v1 (046d:c222).|Aucun G15 v1 trouvé (046d:c222).
G15 Tastentest|G15 key test|Prueba de teclas G15|Test des touches G15
G-, M-, Displaytasten|G-, M-, display keys|Teclas G, M y pantalla|Touches G, M et écran
Bitte Taste druecken|Press a key|Pulsa una tecla|Appuyez sur une touche
Tastentest läuft: G1–G18, M1–M3, MR, L1–L5, LIGHT. Strg+C beendet ihn.|Key test: G1–G18, M1–M3, MR, L1–L5, LIGHT. Stop with Ctrl+C.|Prueba: G1–G18, M1–M3, MR, L1–L5, LIGHT. Ctrl+C para salir.|Test : G1–G18, M1–M3, MR, L1–L5, LIGHT. Ctrl+C pour arrêter.
gedrückt|pressed|pulsada|appuyée
gedrueckt|pressed|pulsada|appuyee
losgelassen|released|soltada|relachee
{count} Taste(n) gehalten|{count} key(s) held|{count} tecla(s) pulsada(s)|{count} touche(s) maintenue(s)
Display-Bild übertragen (992 Bytes).|Display image transferred (992 bytes).|Imagen transferida (992 bytes).|Image transférée (992 octets).
Uhr läuft. Beenden mit Strg+C.|Clock running. Stop with Ctrl+C.|Reloj activo. Ctrl+C para salir.|Horloge active. Ctrl+C pour arrêter.
Beendet.|Stopped.|Finalizado.|Arrêté.
Fehler: {details}|Error: {details}|Error: {details}|Erreur : {details}
Sprache|Language|Idioma|Langue
'''

CATALOG = {}
for _row in _ROWS.strip().splitlines():
    _source, _en, _es, _fr = _row.split("|")
    if _source in CATALOG:
        raise ValueError(f"Duplicate translation: {_source}")
    CATALOG[_source] = {"en": _en, "es": _es, "fr": _fr, "de": _source}

CATALOG["lcd.clock_button"]["de"] = "UHR"

DAYS = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "es": ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"),
    "fr": ("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"),
    "de": ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"),
}


def date_label(now, language):
    language = normalize_language(language)
    day = DAYS[language][now.weekday()]
    date = now.strftime("%d.%m.%Y" if language == "de" else "%d/%m/%Y")
    return f"{day} {date} {Translator(language)('KW')} {now:%V}"
