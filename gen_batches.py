# -*- coding: utf-8 -*-
"""Split questions into batch JSON files for detailed explanation writing."""
import json
import os

qs = json.load(open("questions.json", encoding="utf-8"))
os.makedirs("batches", exist_ok=True)
size = 40
for i in range(0, len(qs), size):
    chunk = []
    for q in qs[i : i + size]:
        chunk.append(
            {
                "id": q["id"],
                "question": q["question"],
                "options": q["options"],
                "answer": q.get("answer"),
                "answers": q.get("answers"),
            }
        )
    path = f"batches/batch_{i//size:02d}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunk, f, ensure_ascii=False, indent=2)
    print(path, len(chunk))
print("total batches", (len(qs) + size - 1) // size)
