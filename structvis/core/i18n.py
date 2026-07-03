"""
Lightweight internationalization for Flovis.

Default language is English. UI strings in the code are English literals wrapped
in ``t(...)``; the Polish translation is looked up in ``_PL`` (english -> polish).
Missing keys fall back to the English text, so the app never shows blanks.

The chosen language is persisted in a small JSON settings file so it is
remembered across runs.
"""
from __future__ import annotations

from . import settings as _settings

_LANG = "en"


def _load():
    global _LANG
    lang = str(_settings.get("language", "en")).lower()
    _LANG = "pl" if lang.startswith("pl") else "en"


def _save():
    # merge-write: never clobbers other settings keys (theme, hide_welcome)
    _settings.set_value("language", _LANG)


def set_language(lang: str):
    """Set active language ('en' or 'pl') and persist it."""
    global _LANG
    _LANG = "pl" if str(lang).lower().startswith("pl") else "en"
    _save()


def get_language() -> str:
    return _LANG


def t(s: str) -> str:
    """Translate an English source string to the active language."""
    if _LANG == "pl":
        return _PL.get(s, s)
    return s


# english -> polish. Uzupelniane recznie; brakujace klucze -> tekst angielski.
_PL: dict[str, str] = {
    # --- ogolne / okno ---
    "Flovis - airfoil & wing analysis": "Flovis - analiza profili i skrzydel",
    "simplified aerodynamic analysis of flying models":
        "uproszczona analiza aerodynamiczna modeli latajacych",
    "Language:": "Jezyk:",
    "Ready.": "Gotowy.",
    "English": "English",
    "Polski": "Polski",
    # --- menu Plik ---
    "&File": "&Plik",
    "New": "Nowy",
    "Open...": "Otworz...",
    "Save": "Zapisz",
    "Save as...": "Zapisz jako...",
    "Export PDF...": "Eksport PDF...",
    "Quit": "Zakoncz",
    "New project.": "Nowy projekt.",
    "Open project": "Otworz projekt",
    "Flovis project (*.flovis)": "Projekt Flovis (*.flovis)",
    "Read error": "Blad odczytu",
    "Loaded project: {}": "Wczytano projekt: {}",
    "Save project": "Zapisz projekt",
    "Saved: {}": "Zapisano: {}",
    "Save error": "Blad zapisu",
    # --- zakladki ---
    "  Templates 3D  ": "  Szablony 3D  ",
    "  Airfoil  ": "  Profile  ",
    "  Analysis  ": "  Analiza  ",
    "  3D Model  ": "  Model 3D  ",
    "  Report  ": "  Raport  ",
    # --- onboarding ---
    "Welcome to Flovis": "Witaj w Flovis",
    "Where do we start?": "Od czego zaczniemy?",
    "Pick one option - you can change it any time.":
        "Wybierz jedna z opcji - mozesz to zmienic w kazdej chwili.",
    "Start from a template": "Zacznij od szablonu",
    "A ready aircraft layout to edit and analyze.":
        "Gotowy uklad samolotu do edycji i analizy.",
    "Load a STEP model (.stp)": "Wczytaj model STEP (.stp)",
    "Analyze exact CAD geometry.": "Analiza dokladnej geometrii z CAD.",
    "Edit an airfoil": "Edytuj profil",
    "Airfoil generator and interactive editor.":
        "Generator i interaktywny edytor profili lotniczych.",
    "Open a project (.flovis)": "Otworz projekt (.flovis)",
    "Load a previously saved project.": "Wczytaj zapisany wczesniej projekt.",
    "Skip": "Pomin",
    # --- Templates tab ---
    "Aircraft layout": "Uklad samolotu",
    "Configuration": "Konfiguracja",
    "Mass": "Masa",
    "Center of gravity x": "Srodek ciezkosci x",
    "Set as current model": "Ustaw jako biezacy model",
    "Loaded layout: {}": "Zaladowano uklad: {}",
    "Span [m]": "Rozpietosc [m]",
    "Root chord [m]": "Cieciwa nasady [m]",
    "Tip chord [m]": "Cieciwa konca [m]",
    "Sweep [deg]": "Skos [deg]",
    "Dihedral [deg]": "Wznios [deg]",
    "Position X [m]": "Pozycja X [m]",
    "Root airfoil": "Profil nasady",
    # --- layouts (Layout enum values, must match exactly) ---
    "Low wing (classic)": "Dolnoplat klasyczny",
    "High wing": "Gornoplat",
    "Twin boom": "Uklad z belkami",
    "Pusher": "Silnik pchajacy",
    "Flying wing": "Latajace skrzydlo",
    "Canard": "Kaczka (canard)",
    # --- surface names ---
    "Wing": "Skrzydlo",
    "Horizontal tail": "Usterzenie poziome",
    "Vertical tail": "Usterzenie pionowe",
    "Wing area: {a} cm2   |   MAC: {m} mm   |   aspect ratio AR: {ar}":
        "Powierzchnia skrzydla: {a} cm2   |   MAC: {m} mm   |   wydluzenie AR: {ar}",
    # --- Airfoil tab ---
    "NACA generator": "Generator NACA",
    "e.g. 2412 or 00011-0.825-35": "np. 2412 lub 00011-0.825-35",
    "Notation": "Notacja",
    "Modified profile (4-digit)": "Profil zmodyfikowany (4-cyfrowy)",
    "LE radius factor": "Wsp. promienia natarcia",
    "Max thickness position": "Polozenie max grubosci",
    "Number of points": "Liczba punktow",
    "Sharp trailing edge": "Ostra krawedz splywu",
    "Generate airfoil": "Generuj profil",
    "Editor (drag points with the mouse)": "Edytor (przeciagaj punkty myszka)",
    "Undo": "Cofnij", "Redo": "Ponow",
    "Insert point": "Wstaw punkt", "Delete point": "Usun punkt",
    "Smooth": "Wygladz", "Repanel": "Repanelizacja",
    "Snap to chord": "Snap do cieciwy",
    "Show 'before' (after smoothing)": "Pokaz 'przed' (po wygladzaniu)",
    "Thickness scale": "Skala grubosci",
    "File": "Plik", "Load .dat": "Wczytaj .dat",
    "Save .dat (Selig)": "Zapisz .dat (Selig)", "Use in analysis": "Uzyj w analizie",
    "Airfoil polars (2D)": "Bieguny profilu (2D)",
    "Reynolds number": "Liczba Reynoldsa",
    "Automatic (XFoil/NeuralFoil)": "Automatyczny (XFoil/NeuralFoil)",
    "Method": "Metoda", "Compute polars": "Policz bieguny",
    "Generation error": "Blad generowania", "Load airfoil": "Wczytaj profil",
    "Airfoil (*.dat *.txt)": "Profil (*.dat *.txt)", "Save airfoil": "Zapisz profil",
    "Selig airfoil (*.dat)": "Profil Selig (*.dat)", "Saved": "Zapisano",
    "Airfoil saved:\n{}": "Profil zapisany:\n{}",
    "Airfoil set as current for analysis.": "Profil ustawiony jako biezacy do analizy.",
    "Points: {n}   |   max thickness: {tk}% @ {tp}%c   |   camber: {cm}% @ {cp}%c":
        "Punkty: {n}   |   grubosc max: {tk}% @ {tp}%c   |   strzalka: {cm}% @ {cp}%c",
    "Warning: ": "Uwaga: ", "Geometry OK.": "Geometria poprawna.",
    "Geometry": "Geometria",
    "Fix the airfoil geometry before running polars.":
        "Popraw geometrie profilu przed analiza biegunow.",
    "Computing...": "Liczenie...", "Airfoil polar analysis...": "Analiza biegunow profilu...",
    "2D analysis error": "Blad analizy 2D",
    "Cp available only from XFoil": "Cp dostepne tylko z XFoila",
    "Cp distribution": "Rozklad Cp", "Polars ready ({}).": "Bieguny gotowe ({}).",
    # --- Analysis tab ---
    "Analysis setup": "Konfiguracja analizy", "Velocity": "Predkosc",
    "Automatic (VLM/analytic)": "Automatyczny (VLM/analityczny)",
    "AVL (accurate mode)": "AVL (tryb dokladny)", "Analytic": "Analityczny",
    "Solver": "Solver", "Run template analysis": "Uruchom analize szablonu",
    "Exact analysis (.stp)": "Analiza dokladna (.stp)",
    "Load STEP and analyze": "Wczytaj STEP i analizuj",
    "ready (gmsh)": "gotowe (gmsh)",
    "MISSING gmsh - install: pip install gmsh": "BRAK gmsh - zainstaluj: pip install gmsh",
    "STEP engine: {}": "Silnik STEP: {}", "Results": "Wyniki",
    "Static margin [%MAC]": "Zapas statecz. [%MAC]", "Neutral point [m]": "Pkt neutralny [m]",
    "No model": "Brak modelu",
    "Set up a model in the Templates tab first.":
        "Najpierw skonfiguruj model w zakladce Szablony.",
    "Analysis running...": "Analiza w toku...", "Analysis error": "Blad analizy",
    "STEP engine missing": "Brak silnika STEP",
    "STEP analysis requires gmsh.\nInstall:  pip install gmsh":
        "Analiza STEP wymaga gmsh.\nZainstaluj:  pip install gmsh",
    "Load STEP model": "Wczytaj model STEP",
    "STEP analysis running...": "Analiza STEP w toku...",
    "Loading geometry...": "Wczytywanie geometrii...",
    "STEP analysis: loading and meshing...": "Analiza STEP: wczytywanie i siatkowanie...",
    "Loading and meshing STEP geometry...": "Wczytywanie i siatkowanie geometrii STEP...",
    "Done: {n} panels. Planform: span {s} m, chord {c} m, airfoil {a}.":
        "Gotowe: {n} paneli. Obrys: rozp. {s} m, cieciwa {c} m, profil {a}.",
    "STEP geometry with the Cp field is now in the 3D Model tab.":
        "Geometria STEP z rozkladem Cp jest juz w zakladce Model 3D.",
    "View the Cp field in the 3D Model tab ('Apply Cp' button).":
        "Pole Cp obejrzysz w zakladce Model 3D (przycisk 'Nalozy Cp').",
    "STEP analysis finished": "Analiza STEP zakonczona",
    "Method: {m}\nSTEP panels: {n}\nCL_alpha = {cla} /rad\n(L/D)_max = {ld}\n\n":
        "Metoda: {m}\nPaneli STEP: {n}\nCL_alpha = {cla} /rad\n(L/D)_max = {ld}\n\n",
    "STEP analysis error.": "Blad analizy STEP.", "STEP analysis failed.": "Analiza STEP nie powiodla sie.",
    "STEP analysis error": "Blad analizy STEP", "Polar": "Biegunowa",
    "Efficiency": "Doskonalosc", "Analysis ready ({}).": "Analiza gotowa ({}).",
    # --- 3D Model tab ---
    "3D view": "Widok 3D", "Show current model": "Pokaz biezacy model",
    "Apply pressure field (Cp)": "Nalozy rozklad cisnienia (Cp)", "Reset view": "Resetuj widok",
    "Layers": "Warstwy", "Wings / tails": "Skrzydla / usterzenia", "Fuselage": "Kadlub",
    "CG and neutral point": "CG i punkt neutralny",
    "Load a model from the Templates tab to see the 3D body here. After an analysis the pressure map is applied.":
        "Wczytaj model z zakladki Szablony, aby zobaczyc bryle 3D. Po analizie nalozy sie mapa cisnienia.",
    "The 3D view appears here once a model is loaded.":
        "Widok 3D pojawi sie tutaj po wczytaniu modelu.",
    "3D view unavailable": "Widok 3D niedostepny",
    "Could not initialize the PyVista/VTK view:\n": "Nie udalo sie zainicjowac widoku PyVista/VTK:\n",
    "Rotate with the mouse, zoom with the scroll wheel. Cp is applied after a panel/STEP analysis.":
        "Obracaj mysza, przyblizaj scrollem. Cp nalozy sie po analizie panelowej/STEP.",
    "No results": "Brak wynikow",
    "Run an analysis first (Analysis / STEP).": "Najpierw uruchom analize (Analiza / STEP).",
    "Computing the surface pressure distribution...": "Licze rozklad cisnienia na powierzchni...",
    "Pressure distribution (Cp) running...": "Rozklad cisnienia (Cp) w toku...",
    "Cp field: blue = suction (low pressure), red = stagnation (high pressure). Rotate with the mouse.":
        "Rozklad Cp: niebieski = podcisnienie (ssanie), czerwony = nadcisnienie (spietrzenie). Obracaj mysza.",
    "Pressure distribution ready.": "Rozklad cisnienia gotowy.",
    # --- Report tab ---
    "AI model:": "Model AI:", "Refresh models": "Odswiez modele",
    "Analysis type:": "Rodzaj analizy:", "Generate AI interpretation": "Generuj interpretacje AI",
    "Written interpretation": "Interpretacja slowna",
    "The interpretation from the Ollama model will appear here.\nYou can also type/edit the text manually before export.":
        "Tu pojawi sie interpretacja z modelu Ollama.\nMozesz tez wpisac/poprawic tekst recznie przed eksportem.",
    "Export PDF report": "Eksportuj raport PDF", "Run an analysis first.": "Najpierw uruchom analize.",
    "Ollama offline": "Ollama offline",
    "Ollama was not found at localhost:11434.\nStart 'ollama serve' and try again.":
        "Nie wykryto Ollama na localhost:11434.\nUruchom 'ollama serve' i sprobuj ponownie.",
    "Model missing": "Brak modelu", "Generating...": "Generowanie...",
    "The AI model is analyzing the data... Large models (e.g. qwen3:30b) may think for ~1-2 min before writing. Please wait.":
        "Model AI analizuje dane... Duze modele (np. qwen3:30b) moga myslec ~1-2 min zanim zaczna pisac. Prosze czekac.",
    "Generating AI interpretation...": "Generowanie interpretacji AI...",
    " (reasoning: {} chars)": " (rozumowanie: {} znakow)",
    "The AI model is working... {s} s{extra}. The answer will appear below.":
        "Model AI pracuje... {s} s{extra}. Odpowiedz pojawi sie ponizej.",
    "The model is writing the answer...": "Model pisze odpowiedz...",
    "The model returned no text. Try another model (list above) or the 'Short assessment' preset.":
        "Model nie zwrocil tekstu. Sprobuj innego modelu (lista wyzej) lub presetu 'Krotka ocena'.",
    "Interpretation ready. You can edit it before export.":
        "Interpretacja gotowa. Mozesz ja edytowac przed eksportem.",
    "Interpretation ready.": "Interpretacja gotowa.", "AI generation error.": "Blad generowania AI.",
    "AI error": "Blad AI", "Save report": "Zapisz raport", "Done": "Gotowe",
    "Report saved:\n{}": "Raport zapisany:\n{}", "Export error": "Blad eksportu",
    # --- AI presets + hints ---
    "Full analysis": "Pelna analiza", "Short assessment": "Krotka ocena",
    "Build tips": "Porady konstrukcyjne",
    "Model '{m}' was not found in Ollama.\nPull it with:\n\n    ollama pull {m}\n\nAlso make sure the server is running: 'ollama serve'.":
        "Nie znaleziono modelu '{m}' w Ollama.\nPobierz go:\n\n    ollama pull {m}\n\nUpewnij sie tez, ze dziala serwer: 'ollama serve'.",
}
_load()
