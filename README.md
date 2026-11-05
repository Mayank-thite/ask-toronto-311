# Ask Toronto 311

Ask a question in plain English about 937,312 requests Toronto residents made to 311 in 2024 and 2025. A small open-source model writes the SQL, a guard checks it, PostgreSQL runs it with read-only access, and you get a table and a chart back.

```
$ python -m ask311 "Which 5 wards had the most missed collection requests in 2025?"

ward_name               requests
Beaches-East York       5487
Toronto-Danforth        5437
Scarborough Southwest   4119
Scarborough-Rouge Park  4065
Don Valley West         3705

bar chart saved to answer.png
```

No paid API. Everything runs on a CPU with local models through [Ollama](https://ollama.com) or llama.cpp.

**Results page:** [mayank-thite.github.io/ask-toronto-311](https://mayank-thite.github.io/ask-toronto-311/)

## Results

I wrote 100 test questions and checked every answer by hand. A question counts as correct only when the agent's query returns the same result as mine (execution accuracy).

| Model (full agent) | Correct | Median answer time (4-core CPU) |
|---|---|---|
| Qwen2.5-Coder 1.5B | 64 / 100 | 5.2 s |
| Qwen2.5-Coder 3B | 73 / 100 | 6.9 s |
| Qwen2.5-Coder 7B | **83 / 100** | 12.3 s |

What each piece adds, all on the 3B model:

| Setup | Correct |
|---|---|
| Tables and columns only | 36 |
| + data notes (real values, what "open" means, the forestry move, seasons) | 55 |
| + 3 similar solved examples, found with BM25 | 73 |
| + self-correction (errors fed back, up to 2 retries) | 73 |
| + a "don't copy filters from the examples" line | 71 |

Context did the work. Data notes and examples took the same model from 36 to 73. Self-correction added nothing: once the model had context, only 3 queries failed loudly, and none of those got fixed. Almost every remaining miss ran fine and returned the wrong number, which a retry loop can't see. Full breakdown by question type and every question's outcome: [eval/REPORT.md](eval/REPORT.md).

## How it works

1. **Load** (`ask311/load.py`). The city's yearly CSVs go into PostgreSQL. 810 raw request types are grouped into 15 topics (`topics.py`), because the city renamed many types between 2024 and 2025. "Road Pothole / Road Damage" became "Road - Pot hole", so filtering on one name misses half the data.
2. **Describe** (`schema_context.py`). The prompt gets the tables plus short notes pulled from the data itself: real status and division values, the topic list, the date range, and the traps.
3. **Retrieve** (`retrieval.py`). The 3 most similar solved questions come from a bank of 24 (`examples.yaml`). None of them are test questions.
4. **Write and check** (`guard.py`). The model writes one query. sqlglot parses it, allows a single SELECT on known tables, and caps the rows at 500.
5. **Run safely** (`db.py`, `sql/schema.sql`). Queries run as `agent_ro`, a role with SELECT grants only, read-only transactions and a 15 second timeout. If a DELETE got past the parser, the database would still refuse it (there's a test for that).
6. **Fix and answer** (`agent.py`, `chart.py`). Errors and empty results go back to the model for up to 2 more tries. A line, bar or single number is picked from the shape of the result.

## Run it yourself

You need Python 3.11+, Docker (or any PostgreSQL 14+) and Ollama.

```bash
git clone https://github.com/Mayank-thite/ask-toronto-311 && cd ask-toronto-311
pip install -r requirements.txt
docker compose up -d                      # PostgreSQL on localhost:5432
PYTHONPATH=src python -m ask311.load      # downloads about 13 MB from Toronto Open Data, loads 937k rows

ollama pull qwen2.5-coder:7b
PYTHONPATH=src python -m ask311 "How many pothole requests came in during the spring of 2025?"
```

Any OpenAI-compatible endpoint works. Set `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` (see `.env.example`) to point it at llama.cpp, vLLM or a hosted API.

Run the evaluation and rebuild the report:

```bash
python eval/run_eval.py --name my-run --model qwen2.5-coder:7b   # about 25 minutes on a CPU
python eval/report.py
pytest                                                          # guardrails, scoring, all 100 gold answers
```

The numbers above came from llama.cpp's server running the Q4_K_M GGUF builds of each model.

## Problems I ran into

- **The city's CSV breaks on commas.** Division names like "Parks, Forestry & Recreation" aren't quoted, so 70,408 rows have 10 fields instead of 9. One section name has the same problem. The loader rejoins them using the known division names.
- **The files aren't UTF-8.** They're Windows-1252, and accented street names crash a UTF-8 read.
- **"Intersection" in the postal code column.** 141,355 requests were logged at an intersection, and the postal code field just says "Intersection". Those become NULL, and the notes tell the model where the street names live instead.
- **Forestry changed divisions.** It was under Parks in 2024 and under Environment, Climate & Forestry in 2025. Without a note, models answered "forestry requests" with one year only.
- **My scorer was too strict at first.** It marked "2" wrong when the answer was "February 2025" in a question already filtered to 2025, and it failed answers that gave the ward name without the count I'd included. I fixed both rules and re-scored every saved run from its stored SQL (`eval/rescore.py`), so no model was re-run to get better numbers. The rules live in `compare.py` with tests.
- **Small models copy the examples.** If a retrieved example filtered on 2025, the model often added 2025 to a question that never mentioned a year. A one-line warning in the prompt didn't fix it (71 vs 73), so I left it off and recorded the run anyway.

## Where it still fails

Of the 7B model's 17 misses, most fall into four groups: copying a year filter from an example, searching request names for words like "missed collection" instead of using the topic column, wrapping time ranges (`BETWEEN 23 AND 5` for "11 pm to 5 am" matches nothing), and two-step counts that need a subquery. Each one points at more context (a note on wrapping hours, examples of two-step counts) rather than a bigger retry loop.

## Layout

```
src/ask311/      agent, guardrails, retrieval, schema notes, topics, loader, charts, CLI
sql/schema.sql   tables, view, read-only agent role
eval/            100 questions with gold SQL, runner, re-scorer, report, saved results
docs/            results page (GitHub Pages)
tests/           127 tests; CI loads the real data into Postgres and runs them
```

## Data and licences

Data: City of Toronto Open Data, [311 Service Requests – Customer Initiated](https://open.toronto.ca/dataset/311-service-requests-customer-initiated/), under the Open Government Licence – Toronto. Qwen2.5-Coder 1.5B and 7B are Apache 2.0. The 3B model has the Qwen Research licence, which is fine for this kind of non-commercial testing. Code is MIT.
