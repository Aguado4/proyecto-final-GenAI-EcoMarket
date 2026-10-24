"""Lógica de negocio simulada de EcoMarket (sin LLM).

Estas funciones representan los "sistemas externos" con los que el agente
interactúa: sistema de pedidos, motor de reglas de devolución, generador
de etiquetas y mesa de ayuda. Son deterministas y se prueban en
tests/test_services.py sin necesidad de llamar al modelo.

Todas devuelven un dict con la clave "ok": False + "error" cuando la
operación falla, para que el agente pueda explicarle el fallo al cliente.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any

from agent import config

ELEGIBLE = "elegible"
NO_ELEGIBLE = "no_elegible"
REVISION_HUMANA = "requiere_revision_humana"
FALTA_INFORMACION = "falta_informacion"

# Resultado de la última verificación de elegibilidad por pedido. La
# etiqueta solo se genera si aquí hay un "elegible": así el agente no
# puede saltarse la verificación aunque el LLM lo intente.
_verificaciones: dict[str, dict[str, Any]] = {}


@lru_cache(maxsize=1)
def _pedidos() -> dict[str, dict[str, Any]]:
    return json.loads((config.DATA_DIR / "pedidos.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _productos() -> dict[str, dict[str, Any]]:
    return json.loads((config.DATA_DIR / "productos.json").read_text(encoding="utf-8"))


def normalizar_numero_pedido(numero: str) -> str:
    """Acepta 'TRK-2001', 'trk2001', 'TRK 2001' o '2001'."""
    digits = re.sub(r"\D", "", numero or "")
    return f"TRK-{digits}" if digits else (numero or "").strip().upper()


def _error(codigo: str, mensaje: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": codigo, "mensaje": mensaje, **extra}


def _enmascarar_email(email: str) -> str:
    usuario, _, dominio = email.partition("@")
    return f"{usuario[:1]}***@{dominio}" if dominio else "***"


def consultar_pedido(numero_pedido: str) -> dict[str, Any]:
    numero = normalizar_numero_pedido(numero_pedido)
    pedido = _pedidos().get(numero)
    if pedido is None:
        return _error(
            "pedido_no_encontrado",
            f"No existe ningún pedido con el número {numero}.",
            numero_pedido=numero,
        )

    datos = {k: v for k, v in pedido.items() if k not in ("email", "direccion")}
    datos["email"] = _enmascarar_email(pedido.get("email", ""))
    producto = _productos().get(pedido["producto"], {})
    datos["categoria"] = producto.get("categoria", "desconocida")
    return {"ok": True, "numero_pedido": numero, **datos}


def verificar_elegibilidad(
    numero_pedido: str,
    empaque_abierto: bool | None = None,
    producto_con_problema: bool = False,
    motivo: str = "",
) -> dict[str, Any]:
    numero = normalizar_numero_pedido(numero_pedido)
    pedido = _pedidos().get(numero)
    if pedido is None:
        return _error(
            "pedido_no_encontrado",
            f"No existe ningún pedido con el número {numero}.",
            numero_pedido=numero,
        )

    nombre_producto = pedido["producto"]
    producto = _productos().get(nombre_producto)
    if producto is None:
        return _error(
            "producto_sin_politica",
            f"El producto '{nombre_producto}' no tiene una política de devolución registrada.",
            numero_pedido=numero,
        )

    base = {
        "ok": True,
        "numero_pedido": numero,
        "producto": nombre_producto,
        "categoria": producto["categoria"],
        "motivo": motivo,
    }

    def resultado(estado: str, razon: str, siguiente_paso: str, **extra: Any) -> dict[str, Any]:
        r = {**base, "resultado": estado, "razon": razon, "siguiente_paso": siguiente_paso, **extra}
        _verificaciones[numero] = r
        return r

    if pedido["estado"] == "cancelado":
        return resultado(
            NO_ELEGIBLE,
            "El pedido fue cancelado antes del envío, así que no hay un producto que devolver.",
            "informar_al_cliente",
        )
    if pedido["estado"] != "entregado":
        return resultado(
            NO_ELEGIBLE,
            f"El pedido aún no ha sido entregado (estado: {pedido['estado']}). "
            "La devolución se puede solicitar una vez se reciba el producto.",
            "informar_al_cliente",
        )

    fecha_entrega = date.fromisoformat(pedido["fecha_entrega_real"])
    dias_desde_entrega = (config.SIMULATED_TODAY - fecha_entrega).days
    fecha_limite = fecha_entrega + timedelta(days=config.RETURN_WINDOW_DAYS)
    dentro_de_plazo = dias_desde_entrega <= config.RETURN_WINDOW_DAYS
    plazo = {
        "fecha_entrega": fecha_entrega.isoformat(),
        "dias_desde_entrega": dias_desde_entrega,
        "fecha_limite_devolucion": fecha_limite.isoformat(),
        "dias_restantes": max(config.RETURN_WINDOW_DAYS - dias_desde_entrega, 0),
    }

    politica = producto["politica_devolucion"]

    if producto["es_perecedero"]:
        if producto_con_problema:
            return resultado(
                REVISION_HUMANA,
                "Los alimentos no se devuelven, pero si llegaron dañados o vencidos "
                "EcoMarket ofrece reemplazo o reembolso como excepción, tras revisar el caso.",
                "escalar_a_agente_humano",
                **plazo,
            )
        return resultado(
            NO_ELEGIBLE,
            "Los alimentos y productos perecederos no se pueden devolver por razones sanitarias.",
            "informar_al_cliente",
            **plazo,
        )

    if politica == "no_devolvible":
        if producto_con_problema:
            return resultado(
                REVISION_HUMANA,
                "Este producto de higiene no admite devolución, pero al tener un defecto "
                "un agente puede evaluar un reemplazo.",
                "escalar_a_agente_humano",
                **plazo,
            )
        return resultado(
            NO_ELEGIBLE,
            "Este producto es de uso íntimo y no admite devolución, ni siquiera sin abrir.",
            "informar_al_cliente",
            **plazo,
        )

    if politica == "no_devolvible_si_abierto":
        if empaque_abierto is None:
            return resultado(
                FALTA_INFORMACION,
                "Para productos de higiene la regla depende de si el empaque fue abierto.",
                "preguntar_al_cliente_si_el_empaque_fue_abierto",
                **plazo,
            )
        if empaque_abierto:
            if producto_con_problema:
                return resultado(
                    REVISION_HUMANA,
                    "El empaque fue abierto, pero el producto tiene un defecto: es una "
                    "excepción que revisa un agente humano (reemplazo o reembolso parcial).",
                    "escalar_a_agente_humano",
                    **plazo,
                )
            return resultado(
                NO_ELEGIBLE,
                "Los productos de higiene con el empaque abierto no se pueden devolver por razones de salud.",
                "informar_al_cliente",
                **plazo,
            )

    if not dentro_de_plazo:
        if producto_con_problema:
            return resultado(
                REVISION_HUMANA,
                f"El plazo de {config.RETURN_WINDOW_DAYS} días ya venció, pero el cliente "
                "reporta un problema con el producto: lo revisa un agente humano.",
                "escalar_a_agente_humano",
                **plazo,
            )
        return resultado(
            NO_ELEGIBLE,
            f"El plazo de {config.RETURN_WINDOW_DAYS} días desde la entrega ya venció "
            f"(han pasado {dias_desde_entrega} días).",
            "informar_al_cliente",
            **plazo,
        )

    return resultado(
        ELEGIBLE,
        f"El producto cumple la política y está dentro del plazo de {config.RETURN_WINDOW_DAYS} días.",
        "generar_etiqueta_devolucion",
        **plazo,
    )


def _ruta_etiqueta(numero: str):
    return config.LABELS_DIR / f"{numero}.json"


def generar_etiqueta(numero_pedido: str) -> dict[str, Any]:
    numero = normalizar_numero_pedido(numero_pedido)
    pedido = _pedidos().get(numero)
    if pedido is None:
        return _error(
            "pedido_no_encontrado",
            f"No existe ningún pedido con el número {numero}.",
            numero_pedido=numero,
        )

    existente = _ruta_etiqueta(numero)
    if existente.exists():
        etiqueta = json.loads(existente.read_text(encoding="utf-8"))
        return {"ok": True, "reenviada": True, **etiqueta}

    verificacion = _verificaciones.get(numero)
    if verificacion is None:
        return _error(
            "elegibilidad_no_verificada",
            "Antes de generar la etiqueta hay que verificar la elegibilidad del pedido.",
            numero_pedido=numero,
        )
    if verificacion["resultado"] != ELEGIBLE:
        return _error(
            "pedido_no_elegible",
            f"No se puede generar la etiqueta: {verificacion['razon']}",
            numero_pedido=numero,
            resultado_verificacion=verificacion["resultado"],
        )

    emision = config.SIMULATED_TODAY
    etiqueta = {
        "codigo_rma": f"RMA-{numero.removeprefix('TRK-')}-{uuid.uuid4().hex[:6].upper()}",
        "numero_pedido": numero,
        "cliente": pedido["cliente"],
        "producto": pedido["producto"],
        "direccion_recoleccion": f"{pedido['direccion']}, {pedido['ciudad_destino']}",
        "transportista": "EcoEnvíos",
        "fecha_emision": emision.isoformat(),
        "valida_hasta": (emision + timedelta(days=config.LABEL_VALIDITY_DAYS)).isoformat(),
        "costo_envio": "Prepagado por EcoMarket",
        "instrucciones": [
            "Empaca el producto con sus accesorios, idealmente en el empaque original.",
            "Imprime la etiqueta y pégala en un lugar visible del paquete.",
            "Entrégalo en un punto autorizado o espera la recolección en tu dirección.",
            "El reembolso se procesa 5 a 7 días hábiles después de recibir el producto.",
        ],
        "generada_en": datetime.now().isoformat(timespec="seconds"),
    }
    config.LABELS_DIR.mkdir(parents=True, exist_ok=True)
    existente.write_text(json.dumps(etiqueta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "reenviada": False, **etiqueta}


def escalar_a_humano(motivo: str, resumen: str, numero_pedido: str | None = None, prioridad: str = "normal") -> dict[str, Any]:
    if not (motivo or "").strip() or not (resumen or "").strip():
        return _error("datos_incompletos", "Para escalar el caso se necesita un motivo y un resumen.")

    numero = normalizar_numero_pedido(numero_pedido) if numero_pedido else None
    if numero and numero not in _pedidos():
        return _error(
            "pedido_no_encontrado",
            f"No existe ningún pedido con el número {numero}.",
            numero_pedido=numero,
        )

    prioridad = prioridad if prioridad in ("normal", "alta") else "normal"
    ticket = {
        "ticket_id": f"TCK-{uuid.uuid4().hex[:6].upper()}",
        "numero_pedido": numero,
        "motivo": motivo.strip(),
        "resumen": resumen.strip(),
        "prioridad": prioridad,
        "tiempo_estimado_respuesta": "4 horas hábiles" if prioridad == "alta" else "24 horas hábiles",
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    }
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    with config.TICKETS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ticket, ensure_ascii=False) + "\n")
    return {"ok": True, **ticket}


def reset_state() -> None:
    _verificaciones.clear()
    _pedidos.cache_clear()
    _productos.cache_clear()
