"""Coseno con casos conocidos, mínimo entre pares y decisión del umbral."""
import math

import pytest

from app.divergence import coseno, decidir, evaluar_divergencia, similitud_minima_entre_pares
from app.models import Estado, Interpretacion


@pytest.mark.parametrize(
    "a, b, esperado",
    [
        ([1, 0], [1, 0], 1.0),  # idénticos
        ([1, 0], [0, 1], 0.0),  # ortogonales
        ([1, 0], [-1, 0], -1.0),  # opuestos
        ([1, 2, 3], [2, 4, 6], 1.0),  # misma dirección, otra magnitud
        ([1, 0], [1, 1], math.sqrt(2) / 2),  # 45 grados
        ([3, 4], [4, 3], 24 / 25),  # (12+12)/(5·5)
    ],
)
def test_coseno_casos_conocidos(a, b, esperado):
    assert coseno(a, b) == pytest.approx(esperado, abs=1e-12)


def test_coseno_simetrico():
    assert coseno([0.2, 0.9, -0.1], [0.5, 0.1, 0.3]) == pytest.approx(coseno([0.5, 0.1, 0.3], [0.2, 0.9, -0.1]))


def test_coseno_vector_nulo_no_definido():
    with pytest.raises(ValueError):
        coseno([0, 0], [1, 0])


def test_coseno_dimensiones_distintas():
    with pytest.raises(ValueError):
        coseno([1, 0, 0], [1, 0])


def test_minimo_entre_pares_con_tres_interpretaciones():
    r = similitud_minima_entre_pares([[1, 0], [1, 1], [0, 1]])
    assert r.valor == pytest.approx(0.0)
    assert r.par == (0, 2)
    assert len(r.pares) == 3


def test_minimo_necesita_dos():
    with pytest.raises(ValueError):
        similitud_minima_entre_pares([[1, 0]])


def test_decision_en_el_umbral_exacto_acepta():
    assert decidir(0.75, 0.75) == Estado.ACEPTADO_DIRECTO
    assert decidir(0.7499, 0.75) == Estado.EN_DEBATE


class EmbeddingsFijos:
    modelo = "falso"

    def __init__(self, tabla):
        self.tabla = tabla

    def vectorizar(self, textos):
        return [self.tabla[t] for t in textos]


def test_evaluar_divergencia_registra_par_y_umbral():
    i = [
        Interpretacion(id="I1", significado="a", parafrasis_del_requisito="p1"),
        Interpretacion(id="I2", significado="b", parafrasis_del_requisito="p2"),
        Interpretacion(id="I3", significado="c", parafrasis_del_requisito="p3"),
    ]
    emb = EmbeddingsFijos({"p1": [1, 0], "p2": [1, 0.1], "p3": [0, 1]})
    r = evaluar_divergencia("sesión", i, emb, umbral=0.75)
    assert r.decision == Estado.EN_DEBATE
    assert r.par_minimo == ("I1", "I3")
    assert r.payload()["umbral"] == 0.75
    assert set(r.pares) == {"I1-I2", "I1-I3", "I2-I3"}
