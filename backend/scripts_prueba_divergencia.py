import numpy as np
from langchain_ollama import OllamaEmbeddings

emb = OllamaEmbeddings(model="nomic-embed-text")

def coseno(a, b):
    a, b = np.array(a), np.array(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))

pares = [
    ("La sesión es el periodo de uso continuo del usuario",
     "La sesión es el evento de conexión del usuario"),
    ("El sistema valida que el campo no esté vacío",
     "El sistema verifica que el campo tenga contenido"),
]
for i1, i2 in pares:
    sim = coseno(emb.embed_query(i1), emb.embed_query(i2))
    print(f"{sim:.3f}  {'debate' if sim < 0.75 else 'aceptado'}")