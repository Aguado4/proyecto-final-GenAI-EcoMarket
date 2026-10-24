import json

import pytest

from agent import config, services


@pytest.fixture(autouse=True)
def isolated_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(config, "LABELS_DIR", tmp_path / "etiquetas")
    monkeypatch.setattr(config, "TICKETS_FILE", tmp_path / "tickets.jsonl")
    services.reset_state()
    yield
    services.reset_state()


@pytest.mark.parametrize("raw", ["TRK-2001", "trk2001", "TRK 2001", "2001"])
def test_normaliza_numero_de_pedido(raw):
    assert services.normalizar_numero_pedido(raw) == "TRK-2001"


def test_consultar_pedido_enmascara_datos_personales():
    r = services.consultar_pedido("TRK-2001")
    assert r["ok"] and r["estado"] == "entregado"
    assert r["email"] == "a***@example.com"
    assert "direccion" not in r


def test_consultar_pedido_inexistente():
    r = services.consultar_pedido("TRK-9999")
    assert r == {**r, "ok": False, "error": "pedido_no_encontrado"}


@pytest.mark.parametrize(
    "pedido, kwargs, esperado",
    [
        ("TRK-2001", {}, services.ELEGIBLE),  # hogar dentro de plazo
        ("TRK-2010", {}, services.ELEGIBLE),  # hogar, día 29 de 30
        ("TRK-2002", {}, services.NO_ELEGIBLE),  # hogar fuera de plazo
        ("TRK-2002", {"producto_con_problema": True}, services.REVISION_HUMANA),
        ("TRK-2003", {}, services.FALTA_INFORMACION),  # higiene: ¿abierto?
        ("TRK-2003", {"empaque_abierto": False}, services.ELEGIBLE),
        ("TRK-2003", {"empaque_abierto": True}, services.NO_ELEGIBLE),
        ("TRK-2007", {"empaque_abierto": True, "producto_con_problema": True}, services.REVISION_HUMANA),
        ("TRK-2009", {"empaque_abierto": False}, services.NO_ELEGIBLE),  # cepillo: nunca
        ("TRK-2008", {}, services.NO_ELEGIBLE),  # perecedero
        ("TRK-2008", {"producto_con_problema": True}, services.REVISION_HUMANA),
        ("TRK-2004", {}, services.NO_ELEGIBLE),  # en tránsito
        ("TRK-2005", {}, services.NO_ELEGIBLE),  # cancelado
    ],
)
def test_reglas_de_elegibilidad(pedido, kwargs, esperado):
    assert services.verificar_elegibilidad(pedido, **kwargs)["resultado"] == esperado


def test_etiqueta_requiere_verificacion_previa():
    r = services.generar_etiqueta("TRK-2001")
    assert not r["ok"] and r["error"] == "elegibilidad_no_verificada"


def test_etiqueta_rechazada_si_no_es_elegible():
    services.verificar_elegibilidad("TRK-2002")
    r = services.generar_etiqueta("TRK-2002")
    assert not r["ok"] and r["error"] == "pedido_no_elegible"


def test_etiqueta_exitosa_y_sin_duplicados():
    services.verificar_elegibilidad("TRK-2001")
    primera = services.generar_etiqueta("TRK-2001")
    assert primera["ok"] and not primera["reenviada"]
    assert primera["codigo_rma"].startswith("RMA-2001-")
    assert primera["valida_hasta"] == "2026-10-28"

    segunda = services.generar_etiqueta("TRK-2001")
    assert segunda["reenviada"] and segunda["codigo_rma"] == primera["codigo_rma"]
    assert len(list(config.LABELS_DIR.glob("*.json"))) == 1


def test_escalamiento_crea_ticket():
    r = services.escalar_a_humano("defecto", "Desodorante abierto con defecto", "TRK-2007", "alta")
    assert r["ok"] and r["ticket_id"].startswith("TCK-")
    assert r["tiempo_estimado_respuesta"] == "4 horas hábiles"
    lines = config.TICKETS_FILE.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["numero_pedido"] == "TRK-2007"


def test_escalamiento_valida_datos():
    assert services.escalar_a_humano("", "algo")["error"] == "datos_incompletos"
    assert services.escalar_a_humano("x", "y", "TRK-0000")["error"] == "pedido_no_encontrado"
