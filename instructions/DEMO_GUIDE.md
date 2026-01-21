## Szybkie uruchomienie (demo)

### Wymagania
- Docker + Docker Compose
- Python 3.13+
- (opcjonalnie) `OPENAI_API_KEY` dla odpowiedzi LLM

### Instalacja i start
1) Uruchom Neo4j:
```
docker-compose up -d
```

2) Utworz wirtualne srodowisko i zainstaluj zaleznosci:
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3) Wygeneruj dane i zaladuj do bazy:
```
python -m src.data.generator --candidates 50 --rfps 5 --seed 42
python -m src.data.loader
```

4) Zbuduj wektory dla NaiveRAG:
```
python -m src.scripts.prep_vectors
```

5) Uruchom UI:
```
streamlit run src/app.py
```

### Co testowac (checklista)
- **Chat Assistant**:
  - Tryb **GraphRAG (Logic)**: zapytaj o liczby/metryki (np. "How many Python developers are available next month?").
  - Tryb **NaiveRAG (Semantic)**: zapytaj o profile kandydatow (np. "Senior React developer with Node.js").
  - Sprawdz przełącznik **Use LLM for NaiveRAG answers** i limit kontekstu.
- **BI Dashboard**:
  - Sprawdz liczniki i wykresy po zaladowaniu danych.
  - Kliknij **Save dashboard evidence** (powstaje `docs/ui_dashboard_evidence.json`).
- **Candidates Browser / RFP Browser**:
  - Otworz szczegoly kandydatow i RFP, sprawdz czy dane wygladaja sensownie.

### Szybkie testy w konsoli (opcjonalnie)
```
python src/scripts/seed_bi_fixtures.py
python tests/verify_bi_questions.py
python tests/verify_bi_core20.py
python -m src.scripts.run_chat_bi_e2e --limit 10
```

> Wskazowka: bez `OPENAI_API_KEY` dziala GraphRAG logika i NaiveRAG retrieval, ale odpowiedzi LLM beda pomijane.
