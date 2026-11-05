"""Pick the stored example questions most similar to the new one (a tiny RAG step).

Plain BM25 over words is enough here: the bank is small and questions are short.
The bank in examples.yaml never overlaps with the evaluation questions.
"""
import math
import pathlib
import re
from collections import Counter

import yaml

BANK = pathlib.Path(__file__).with_name("examples.yaml")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = set("the a an of in on for to by and or is are was were what which how many much did do does with per from each show me".split())


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


class ExampleIndex:
    def __init__(self, path=BANK, k1=1.5, b=0.75):
        self.examples = yaml.safe_load(open(path))
        self.docs = [_tokens(e["question"]) for e in self.examples]
        self.avgdl = sum(map(len, self.docs)) / len(self.docs)
        df = Counter(w for d in self.docs for w in set(d))
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.k1, self.b = k1, b

    def search(self, question: str, k: int = 3) -> list[dict]:
        q = _tokens(question)
        scores = []
        for i, d in enumerate(self.docs):
            tf = Counter(d)
            s = 0.0
            for w in q:
                if w in tf:
                    s += self.idf[w] * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * len(d) / self.avgdl))
            scores.append((s, i))
        scores.sort(reverse=True)
        return [self.examples[i] for s, i in scores[:k] if s > 0]
